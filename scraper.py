import json
import re
import time
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

CATEGORIES = [
    {
        "id": "75102510",
        "name": "Программируемые реле",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele",
    },
    {
        "id": "751025",
        "name": "Модули расширения и ПЛК",
        "url": "https://www.etm.ru/catalog/751025_programmiruemye_rele_moduli_rasshirenija",
    },
]

KNOWN_BRANDS = [
    "ОВЕН",
    "INNOCONT",
    "ONI",
    "Segnetics",
    "КЭАЗ",
    "EKF",
    "Finder",
    "Schneider",
    "ABB",
    "Siemens",
    "Chint",
    "IEK",
    "DKC",
    "WAGO",
    "Rievtech",
    "DEKraft",
    "Relpol",
    "MeyerTec",
]


def extract_card_data(link_el, category_name):
    href = link_el.get_attribute("href") or ""
    m = re.search(r"/cat/nn/(\d+)", href)
    if not m:
        return None

    etm_code = m.group(1)
    card_url = f"https://www.etm.ru/cat/nn/{etm_code}"

    # Поднимаемся до карточки товара
    card_container = link_el.evaluate_handle(
        """el => {
        let cur = el;
        for (let i = 0; i < 8; i++) {
            if (!cur.parentElement) break;
            cur = cur.parentElement;
            if (cur.innerText && (cur.innerText.includes('В корзину') || cur.innerText.includes('Код товара'))) {
                return cur;
            }
        }
        return el.parentElement;
    }"""
    )

    text = ""
    try:
        text = card_container.as_element().inner_text()
    except Exception:
        text = link_el.inner_text()

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    name = "—"
    brand = "—"
    vendor_code = "—"
    price = 0.0
    stock_etm = 0
    stock_vendor = 0

    # 1. Извлекаем название из ссылки или заголовка
    link_title = link_el.inner_text().strip()
    if len(link_title) > 5:
        name = link_title
    else:
        for l in lines:
            if len(l) > 20 and not any(
                k in l
                for k in [
                    "Код товара",
                    "Артикул",
                    "В корзину",
                    "₽",
                    "Показано",
                    "Упаковка",
                ]
            ):
                name = l
                break

    # 2. Артикул и производитель
    for i, line in enumerate(lines):
        if "Артикул:" in line:
            parts = line.split("Артикул:")
            if len(parts) > 1 and parts[1].strip():
                vendor_code = parts[1].strip()
            elif i + 1 < len(lines):
                vendor_code = lines[i + 1].strip()

        for b in KNOWN_BRANDS:
            if b.lower() == line.strip().lower() or (
                b.lower() in line.lower() and len(line) < 30
            ):
                if brand == "—":
                    brand = b

    # Резервное определение бренда из названия
    if brand == "—":
        for b in KNOWN_BRANDS:
            if b.lower() in name.lower():
                brand = b
                break

    # 3. Цена (первое число перед ₽)
    for line in lines:
        if "₽" in line:
            # Ищем числа вида 17 446.00 или 2960.01
            matches = re.findall(r"(\d[\d\s]*[.,]?\d*)\s*₽", line)
            if matches:
                clean = (
                    matches[0]
                    .replace(" ", "")
                    .replace("\xa0", "")
                    .replace(",", ".")
                )
                try:
                    price = float(clean)
                    break
                except ValueError:
                    pass

    # 4. Остатки (например "39 шт.", "36 шт.")
    stock_matches = re.findall(r"(\d+)\s*шт", text)
    if stock_matches:
        stock_etm = int(stock_matches[0])
        if len(stock_matches) > 1:
            stock_vendor = int(stock_matches[1])

    return {
        "category": category_name,
        "etm_code": etm_code,
        "brand": brand,
        "vendor_code": vendor_code,
        "name": name,
        "price": price,
        "stock_etm": stock_etm,
        "stock_vendor": stock_vendor,
        "url": card_url,
    }


def main():
    collected_dict = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",  # если нет Chrome, укажите "msedge"
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--window-size=1920,1080",
            ],
        )

        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )
        page = context.new_page()

        for cat in CATEGORIES:
            print(f"\n==========================================")
            print(f"Категория: {cat['name']}")
            print(f"==========================================")

            # Проходим первые 3 страницы в каждой категории
            for p_num in range(1, 4):
                page_url = f"{cat['url']}?page={p_num}"
                print(f"\nЗагрузка страницы {p_num}: {page_url}")

                try:
                    page.goto(
                        page_url,
                        wait_until="domcontentloaded",
                        timeout=50000,
                    )

                    # Ждем появления карточек
                    page.wait_for_selector("a[href*='/cat/nn/']", timeout=25000)

                    # Медленный скролл для прогрузки всех 24 карточек
                    for scroll_pos in [600, 1400, 2200, 3200]:
                        page.evaluate(f"window.scrollTo(0, {scroll_pos})")
                        page.wait_for_timeout(500)

                    # Находим все ссылки на товары
                    all_links = page.query_selector_all("a[href*='/cat/nn/']")
                    print(
                        f"Найдено ссылок товаров на странице: {len(all_links)}"
                    )

                    page_added = 0
                    for link in all_links:
                        item = extract_card_data(link, cat["name"])
                        if item and item["etm_code"] not in collected_dict:
                            # Пропускаем пустые заглушки без названия
                            if item["name"] != "—":
                                collected_dict[item["etm_code"]] = item
                                page_added += 1

                    print(
                        f"Успешно добавлено со страницы {p_num}: {page_added} (Всего в базе: {len(collected_dict)})"
                    )

                except Exception as e:
                    print(f"Ошибка/таймаут на странице {p_num}: {e}")
                    continue

        browser.close()

    items = list(collected_dict.values())
    print(f"\nСбор завершен! Всего уникальных позиций в базе: {len(items)}")

    payload = {
        "last_updated": datetime.now(timezone.utc).strftime(
            "%d.%m.%Y %H:%M UTC"
        ),
        "total_items": len(items),
        "items": items,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("Файл data.json успешно записан.")


if __name__ == "__main__":
    main()

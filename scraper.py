from datetime import datetime, timezone
import json
import re
import time
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


def parse_page_products(page, category_name):
    products = []

    # Дожидаемся появления хотя бы одного товара на странице
    try:
        page.wait_for_selector(
            "text=Код товара", timeout=25000
        )  # гарантированный маркер карточки
    except Exception:
        print("Маркер 'Код товара' не найден вовремя")

    # Ищем карточки: берем все блоки, содержащие фразу 'Код товара'
    card_elements = page.query_selector_all(
        "xpath=//*[contains(text(), 'Код товара')]/ancestor::div[contains(@class, 'card') or contains(@class, 'item') or string-length(text()) < 1500][last()]"
    )

    # Если xpath не нашел, используем поиск по ссылкам каталога /cat/nn/
    if not card_elements:
        card_elements = page.query_selector_all("a[href*='/cat/nn/']")

    print(f"Обнаружено блоков карточек: {len(card_elements)}")

    for el in card_elements:
        try:
            text = el.inner_text().strip()
            if not text or "Код товара" not in text:
                continue

            lines = [l.strip() for l in text.split("\n") if l.strip()]

            etm_code = "—"
            vendor_code = "—"
            brand = "—"
            name = "—"
            price = 0.0
            stock_etm = 0
            stock_vendor = 0

            # 1. Извлечение кода ЭТМ и ссылки
            link_el = el.query_selector("a[href*='/cat/nn/']")
            if link_el:
                href = link_el.get_attribute("href") or ""
                m = re.search(r"/cat/nn/(\d+)", href)
                if m:
                    etm_code = m.group(1)
                name = link_el.inner_text().strip()

            if etm_code == "—":
                m = re.search(r"Код товара:\s*ETM(\d+)", text, re.IGNORECASE)
                if not m:
                    m = re.search(r"Код товара:\s*(\d+)", text, re.IGNORECASE)
                if m:
                    etm_code = m.group(1)

            if etm_code == "—":
                continue

            card_url = f"https://www.etm.ru/cat/nn/{etm_code}"

            # 2. Артикул и производитель
            for i, line in enumerate(lines):
                if "Артикул:" in line:
                    parts = line.split("Артикул:")
                    if len(parts) > 1 and parts[1].strip():
                        vendor_code = parts[1].strip()
                    elif i + 1 < len(lines):
                        vendor_code = lines[i + 1].strip()

                # Бренд обычно идет отдельной короткой строкой перед артикулом или под ним
                for known_brand in [
                    "ОВЕН",
                    "INNOCONT",
                    "ONI",
                    "Segnetics",
                    "КЭАЗ",
                    "Finder",
                    "Schneider",
                    "ABB",
                    "Siemens",
                    "Chint",
                    "IEK",
                    "DKC",
                    "WAGO",
                    "Relpol",
                    "DEKraft",
                ]:
                    if known_brand.lower() in line.lower():
                        brand = known_brand
                        break

            # 3. Наименование (если не определилось по ссылке)
            if name == "—" or len(name) < 5:
                for line in lines:
                    if len(line) > 25 and not any(
                        x in line
                        for x in [
                            "Код товара",
                            "Артикул",
                            "В корзину",
                            "Показано",
                        ]
                    ):
                        name = line
                        break

            # 4. Цена (ищем строчку с ₽ или руб)
            for line in lines:
                if "₽" in line or "руб" in line.lower():
                    # Берем первую найденную цену
                    nums = re.findall(r"\d[\d\s]*[.,]?\d*", line)
                    if nums:
                        clean_num = (
                            nums[0].replace(" ", "").replace("\xa0", "")
                        )
                        clean_num = clean_num.replace(",", ".")
                        try:
                            price = float(clean_num)
                            break
                        except ValueError:
                            pass

            # 5. Остатки (например, "39 шт.", "36 шт.")
            stock_matches = re.findall(r"(\d+)\s*шт", text)
            if stock_matches:
                stock_etm = int(stock_matches[0])
                if len(stock_matches) > 1:
                    stock_vendor = int(stock_matches[1])

            products.append(
                {
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
            )
        except Exception:
            continue

    return products


def main():
    collected_dict = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",  # если нет Chrome, укажите "msedge"
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        context = browser.new_context(
            viewport={"width": 1600, "height": 1000},
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )
        page = context.new_page()

        for cat in CATEGORIES:
            print(f"\n--- Сканирование: {cat['name']} ---")

            # Проходим первые 4 страницы (примерно 100 товаров на категорию)
            for p_num in range(1, 5):
                target_url = (
                    cat["url"]
                    if p_num == 1
                    else f"{cat['url']}?page={p_num}&rows=48"
                )
                print(f"Стр. {p_num}: {target_url}")

                try:
                    page.goto(
                        target_url,
                        wait_until="domcontentloaded",
                        timeout=50000,
                    )
                    page.wait_for_timeout(4000)

                    # Плавная прокрутка для срабатывания lazy-loading
                    for scroll_step in [300, 800, 1500, 2500]:
                        page.evaluate(f"window.scrollTo(0, {scroll_step})")
                        page.wait_for_timeout(400)

                    items = parse_page_products(page, cat["name"])
                    for it in items:
                        collected_dict[it["etm_code"]] = it

                    print(
                        f"На стр. {p_num} собрано: {len(items)} | Всего уникальных: {len(collected_dict)}"
                    )

                    if len(items) == 0:
                        break

                except Exception as e:
                    print(f"Ошибка при загрузке страницы {p_num}: {e}")
                    break

        browser.close()

    final_list = list(collected_dict.values())
    print(f"\nСбор завершен! Всего уникальных позиций: {len(final_list)}")

    payload = {
        "last_updated": datetime.now(timezone.utc).strftime(
            "%d.%m.%Y %H:%M UTC"
        ),
        "total_items": len(final_list),
        "items": final_list,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

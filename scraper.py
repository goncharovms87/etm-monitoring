import json
import os
import re
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

CATEGORIES = [
    {
        "id": "75102510",
        "name": "Программируемые реле",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele",
    },
    {
        "id": "751025",
        "name": "Модули расширения и контроллеры",
        "url": "https://www.etm.ru/catalog/751025_programmiruemye_rele_moduli_rasshirenija",
    },
]


def run():
    all_products = {}

    with sync_playwright() as p:
        # Запуск с отключением флагов ботов
        browser = p.chromium.launch(
    channel="chrome",  # если установлен Google Chrome (или "msedge", если Edge)
    headless=True,
    args=[
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-blink-features=AutomationControlled",
    ],
)

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1600, "height": 900},
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )

        page = context.new_page()

        # Скрываем признаки webdriver
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)

        for cat in CATEGORIES:
            print(f"\n--- Сканирование категории: {cat['name']} ---")

            for page_num in range(1, 4):  # Первые 3 страницы каждого раздела
                url = (
                    cat["url"]
                    if page_num == 1
                    else f"{cat['url']}?page={page_num}"
                )
                print(f"Загрузка: {url}")

                try:
                    res = page.goto(
                        url, wait_until="domcontentloaded", timeout=45000
                    )
                    page.wait_for_timeout(4000)

                    title = page.title()
                    print(f"Заголовок страницы: '{title}'")

                    # Прокручиваем вниз для ленивой загрузки (lazy-load) товаров
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                    page.wait_for_timeout(2000)
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2000)

                except Exception as e:
                    print(f"Ошибка при открытии {url}: {e}")
                    continue

                # Ищем все ссылки на товары вида /cat/nn/XXXXXX
                links = page.query_selector_all("a[href*='/cat/nn/']")
                print(
                    f"Найдено ссылок вида /cat/nn/ на странице: {len(links)}"
                )

                if not links:
                    # Проверяем, не вылезла ли капча/защита
                    content_snip = page.inner_text("body")[:300].replace(
                        "\n", " "
                    )
                    print(f"Текст страницы (первые 300 символов): {content_snip}")
                    break

                for link in links:
                    try:
                        href = link.get_attribute("href") or ""
                        match = re.search(r"/cat/nn/(\d+)", href)
                        if not match:
                            continue

                        etm_id = match.group(1)
                        full_url = f"https://www.etm.ru/cat/nn/{etm_id}"

                        card_text = link.inner_text().strip()
                        # Если текст в самой ссылке пустой (ссылка-картинка), поднимаемся к родительской карточке
                        if len(card_text) < 5:
                            parent = link.evaluate_handle(
                                "el => el.closest('div[class*=\"card\"], article, div[class*=\"item\"]')"
                            )
                            if parent:
                                card_text = parent.as_element().inner_text()

                        lines = [
                            l.strip()
                            for l in card_text.split("\n")
                            if l.strip()
                        ]

                        name = "—"
                        brand = "—"
                        vendor_code = "—"
                        price = 0
                        stock_etm = 0
                        stock_vendor = 0

                        # Извлекаем данные из строк карточки
                        for line in lines:
                            l_lower = line.lower()
                            if any(
                                kw in l_lower
                                for kw in [
                                    "реле",
                                    "модуль",
                                    "плк",
                                    "контроллер",
                                    "блок",
                                    "панель",
                                ]
                            ):
                                if name == "—":
                                    name = line
                            if "арт" in l_lower or "код" in l_lower:
                                vendor_code = (
                                    line.split(":")[-1]
                                    .replace("Арт.", "")
                                    .strip()
                                )
                            if "₽" in line or "руб" in l_lower:
                                digits = "".join(filter(str.isdigit, line))
                                if digits:
                                    price = int(digits)
                            if (
                                "склад этм" in l_lower
                                or "в наличии" in l_lower
                                or "на складе" in l_lower
                            ):
                                digits = "".join(filter(str.isdigit, line))
                                stock_etm = int(digits) if digits else 1
                            if (
                                "производ" in l_lower
                                or "изготовит" in l_lower
                                or "поставщик" in l_lower
                            ):
                                digits = "".join(filter(str.isdigit, line))
                                stock_vendor = int(digits) if digits else 1

                        if name == "—" and len(lines) > 0:
                            name = lines[0]

                        # Определение производителя из наименования (ОВЕН, ONI, Segnetics, Finder, Chint и т.д.)
                        for b in [
                            "ОВЕН",
                            "ONI",
                            "Segnetics",
                            "КЭАЗ",
                            "MeyerTec",
                            "Finder",
                            "Schneider",
                            "ABB",
                            "Siemens",
                            "Chint",
                            "IEK",
                            "DKC",
                            "WAGO",
                        ]:
                            if b.lower() in name.lower():
                                brand = b
                                break

                        if etm_id not in all_products:
                            all_products[etm_id] = {
                                "category": cat["name"],
                                "etm_code": etm_id,
                                "brand": brand,
                                "vendor_code": vendor_code,
                                "name": name,
                                "price": price,
                                "stock_etm": stock_etm,
                                "stock_vendor": stock_vendor,
                                "url": full_url,
                            }
                    except Exception:
                        continue

        browser.close()

    items_list = list(all_products.values())
    print(f"\nВсего успешно собрано уникальных товаров: {len(items_list)}")

    # Сохраняем результат
    payload = {
        "last_updated": datetime.utcnow().strftime("%d.%m.%Y %H:%M UTC"),
        "total_items": len(items_list),
        "items": items_list,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    run()

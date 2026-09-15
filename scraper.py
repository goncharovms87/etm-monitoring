import json
import os
import re
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

# Категории: Программируемые реле и ПЛК/Свободнопрограммируемые модули
CATEGORIES = [
    {
        "id": "75102510",
        "name": "Программируемые реле",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele",
    },
    {
        "id": "751025",
        "name": "Модули расширения и программируемые контроллеры",
        "url": "https://www.etm.ru/catalog/751025_programmiruemye_rele_moduli_rasshirenija",
    },
]


def extract_stock_values(item):
    """Извлечение остатков на складе ЭТМ и складе производителя."""
    stock_etm = 0
    stock_vendor = 0

    # Проверка через структуру остатков stocks
    stocks = item.get("stocks") or item.get("remains") or []
    if isinstance(stocks, list):
        for s in stocks:
            stype = str(s.get("type", "")).lower()
            cnt = s.get("count", 0) or s.get("quantity", 0)
            if "etm" in stype or "local" in stype or "склад" in stype:
                stock_etm += int(cnt) if str(cnt).isdigit() else 0
            elif (
                "vendor" in stype or "producer" in stype or "изготовит" in stype
            ):
                stock_vendor += int(cnt) if str(cnt).isdigit() else 0
    elif isinstance(stocks, dict):
        stock_etm = (
            stocks.get("etm")
            or stocks.get("local")
            or item.get("remains_etm", 0)
            or 0
        )
        stock_vendor = (
            stocks.get("vendor")
            or stocks.get("remote")
            or item.get("remains_vendor", 0)
            or 0
        )

    return int(stock_etm or 0), int(stock_vendor or 0)


def extract_price(item):
    """Извлечение розничной/базовой цены."""
    price_data = item.get("price") or item.get("prices") or {}
    if isinstance(price_data, dict):
        val = (
            price_data.get("val")
            or price_data.get("value")
            or price_data.get("final")
        )
        if val:
            return float(val)
    elif isinstance(price_data, (int, float)):
        return float(price_data)
    return 0.0


def scrape_category(page, cat_info):
    collected_products = []
    page_num = 1
    max_pages = 10  # Глубина обхода страниц каталога

    while page_num <= max_pages:
        target_url = f"{cat_info['url']}?page={page_num}"
        print(f"[{cat_info['name']}] Обработка страницы {page_num}...")

        intercepted_items = []

        def handle_response(response):
            # Перехват JSON-ответов выдачи каталога
            if (
                "catalog" in response.url
                or "product" in response.url
                or "search" in response.url
            ):
                if (
                    "json" in response.headers.get("content-type", "")
                    and response.status == 200
                ):
                    try:
                        data = response.json()
                        rows = (
                            data.get("data")
                            or data.get("products")
                            or data.get("items")
                            or []
                        )
                        if isinstance(rows, list) and len(rows) > 0:
                            intercepted_items.extend(rows)
                    except Exception:
                        pass

        page.on("response", handle_response)

        try:
            page.goto(target_url, wait_until="networkidle", timeout=45000)
            page.wait_for_timeout(3000)
        except Exception:
            # Если networkidle зависает, дожидаемся DOM
            page.wait_for_timeout(5000)

        page.remove_listener("response", handle_response)

        if intercepted_items:
            for item in intercepted_items:
                # Внутренний идентификатор (номенклатурный номер ЭТМ)
                product_id = (
                    item.get("id") or item.get("code") or item.get("etm_code")
                )
                if not product_id:
                    continue

                etm_id = str(product_id)
                card_url = f"https://www.etm.ru/cat/nn/{etm_id}"

                brand = "—"
                if isinstance(item.get("brand"), dict):
                    brand = item["brand"].get("name", "—")
                elif item.get("brand"):
                    brand = str(item.get("brand"))
                elif item.get("producer"):
                    brand = str(item.get("producer"))

                vendor_code = (
                    item.get("vendor_code")
                    or item.get("article")
                    or item.get("vendorCode")
                    or "—"
                )
                name = item.get("name") or item.get("title") or "—"
                stock_etm, stock_vendor = extract_stock_values(item)
                price = extract_price(item)

                collected_products.append(
                    {
                        "category": cat_info["name"],
                        "etm_code": etm_id,
                        "brand": brand,
                        "vendor_code": str(vendor_code),
                        "name": name,
                        "price": price,
                        "stock_etm": stock_etm,
                        "stock_vendor": stock_vendor,
                        "url": card_url,
                    }
                )

        # Резервный сбор прямо из DOM, если API зашифровано или перестроено
        dom_cards = page.query_selector_all(
            "a[href*='/cat/nn/'], a[href*='/catalog/']"
        )
        for link in dom_cards:
            href = link.get_attribute("href") or ""
            match = re.search(r"/cat/nn/(\d+)", href)
            if match:
                etm_id = match.group(1)
                text_content = link.inner_text().strip().split("\n")
                collected_products.append(
                    {
                        "category": cat_info["name"],
                        "etm_code": etm_id,
                        "brand": "—",
                        "vendor_code": "—",
                        "name": (
                            text_content[0]
                            if text_content
                            else f"Товар {etm_id}"
                        ),
                        "price": 0.0,
                        "stock_etm": 0,
                        "stock_vendor": 0,
                        "url": f"https://www.etm.ru/cat/nn/{etm_id}",
                    }
                )

        # Если на странице ничего не найдено — останавливаем пагинацию раздела
        if not intercepted_items and not dom_cards:
            break

        page_num += 1

    return collected_products


def main():
    all_rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()

        for category in CATEGORIES:
            rows = scrape_category(page, category)
            all_rows.extend(rows)

        browser.close()

    # Дедупликация позиций по коду ЭТМ
    unique_map = {}
    for r in all_rows:
        code = r["etm_code"]
        if (
            code not in unique_map
            or unique_map[code]["name"] == f"Товар {code}"
        ):
            unique_map[code] = r

    final_items = list(unique_map.values())
    payload = {
        "last_updated": datetime.utcnow().strftime("%d.%m.%Y %H:%M UTC"),
        "total_items": len(final_items),
        "items": final_items,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Готово. Успешно записано {len(final_items)} позиций.")


if __name__ == "__main__":
    main()

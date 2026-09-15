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
        "name": "Модули расширения и ПЛК",
        "url": "https://www.etm.ru/catalog/751025_programmiruemye_rele_moduli_rasshirenija",
    },
]


def extract_items_from_json(obj, target_list):
    """Рекурсивный поиск товаров в ответах API ЭТМ."""
    if isinstance(obj, dict):
        # Проверяем, похож ли объект на карточку товара ЭТМ
        has_id = any(k in obj for k in ["id", "code", "etm_code", "etmCode"])
        has_name = any(k in obj for k in ["name", "title", "nameRu"])

        if has_id and has_name and isinstance(obj.get("name"), str):
            code = str(obj.get("code") or obj.get("id") or obj.get("etm_code"))
            if code.isdigit() and len(code) >= 5:
                # Извлечение бренда
                brand = "—"
                if isinstance(obj.get("brand"), dict):
                    brand = obj["brand"].get("name", "—")
                elif isinstance(obj.get("producer"), dict):
                    brand = obj["producer"].get("name", "—")
                elif obj.get("brand"):
                    brand = str(obj.get("brand"))
                elif obj.get("producer"):
                    brand = str(obj.get("producer"))

                # Артикул
                vendor_code = (
                    obj.get("vendor_code")
                    or obj.get("vendorCode")
                    or obj.get("article")
                    or "—"
                )

                # Цена
                price = 0
                price_data = obj.get("price") or obj.get("prices") or {}
                if isinstance(price_data, dict):
                    price = (
                        price_data.get("val")
                        or price_data.get("value")
                        or price_data.get("final")
                        or 0
                    )
                elif isinstance(price_data, (int, float)):
                    price = price_data

                # Остатки
                stock_etm = 0
                stock_vendor = 0
                stocks = obj.get("stocks") or obj.get("remains") or []
                if isinstance(stocks, list):
                    for s in stocks:
                        stype = str(s.get("type", "")).lower()
                        qty = s.get("count", 0) or s.get("quantity", 0) or 0
                        if any(
                            x in stype
                            for x in ["etm", "local", "склад", "город"]
                        ):
                            stock_etm += int(qty) if str(qty).isdigit() else 0
                        elif any(
                            x in stype
                            for x in ["vendor", "remote", "изготов", "постав"]
                        ):
                            stock_vendor += (
                                int(qty) if str(qty).isdigit() else 0
                            )
                elif isinstance(stocks, dict):
                    stock_etm = (
                        stocks.get("etm")
                        or stocks.get("local")
                        or obj.get("remains_etm")
                        or 0
                    )
                    stock_vendor = (
                        stocks.get("vendor")
                        or stocks.get("remote")
                        or obj.get("remains_vendor")
                        or 0
                    )

                target_list.append(
                    {
                        "etm_code": code,
                        "brand": brand,
                        "vendor_code": str(vendor_code),
                        "name": obj.get("name", "—"),
                        "price": float(price or 0),
                        "stock_etm": int(stock_etm or 0),
                        "stock_vendor": int(stock_vendor or 0),
                        "url": f"https://www.etm.ru/cat/nn/{code}",
                    }
                )
                return

        for v in obj.values():
            extract_items_from_json(v, target_list)

    elif isinstance(obj, list):
        for item in obj:
            extract_items_from_json(item, target_list)


def main():
    collected_dict = {}

    with sync_playwright() as p:
        # Используем установленный Chrome/Edge в системе
        browser = p.chromium.launch(
            channel="chrome",  # если нет Chrome, укажите "msedge"
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        context = browser.new_context(
            viewport={"width": 1600, "height": 900},
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )
        page = context.new_page()

        # Слушаем сетевой трафик браузера для перехвата API-ответов каталога
        def on_response(response):
            if response.status == 200 and "json" in response.headers.get(
                "content-type", ""
            ):
                try:
                    data = response.json()
                    temp_items = []
                    extract_items_from_json(data, temp_items)
                    for item in temp_items:
                        collected_dict[item["etm_code"]] = item
                except Exception:
                    pass

        page.on("response", on_response)

        for cat in CATEGORIES:
            print(f"Обработка категории: {cat['name']} ({cat['url']})")
            for p_num in range(1, 4):  # Первые 3 страницы
                page_url = (
                    f"{cat['url']}?page={p_num}" if p_num > 1 else cat["url"]
                )
                try:
                    page.goto(
                        page_url, wait_until="domcontentloaded", timeout=40000
                    )
                    # Ждем подгрузки данных по сети
                    page.wait_for_timeout(3000)

                    # Прокручиваем страницу вниз, чтобы стриггерить загрузку остатков
                    page.evaluate(
                        "window.scrollTo(0, document.body.scrollHeight / 2)"
                    )
                    page.wait_for_timeout(1500)
                    page.evaluate(
                        "window.scrollTo(0, document.body.scrollHeight)"
                    )
                    page.wait_for_timeout(2000)
                except Exception as e:
                    print(f"Таймаут или ошибка на странице {page_url}: {e}")

        browser.close()

    result_items = list(collected_dict.values())
    print(f"Итого собрано уникальных товаров: {len(result_items)}")

    payload = {
        "last_updated": datetime.utcnow().strftime("%d.%m.%Y %H:%M UTC"),
        "total_items": len(result_items),
        "items": result_items,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

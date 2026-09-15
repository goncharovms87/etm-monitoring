import json
import os
import time
from datetime import datetime
import requests

# Целевые группы каталога
CATEGORIES = [
    {"id": "751025", "name": "Программируемые реле и модули расширения"},
    {"id": "75102510", "name": "Программируемые реле"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.etm.ru/catalog/",
}


def fetch_category_items(category_id):
    items = []
    page = 1
    page_size = 50

    while True:
        # Внутренний API-эндпоинт каталога ЭТМ
        # При необходимости параметры адаптируются под актуальную сигнатуру запроса в Network DevTools
        url = f"https://api.etm.ru/catalog/v2/products?category_id={category_id}&page={page}&limit={page_size}"

        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            if response.status_code != 200:
                # Если срабатывает WAF/CAPTCHA, логируем и выходим
                print(
                    f"Категория {category_id}, страница {page}: статус {response.status_code}"
                )
                break

            data = response.json()
            products = data.get("data", []) or data.get("products", [])

            if not products:
                break

            for p in products:
                # Извлечение остатков: склад ЭТМ и склад производителя
                stocks = p.get("stocks", {})
                stock_etm = (
                    stocks.get("etm", 0)
                    or p.get("remains_etm", 0)
                    or p.get("stock_local", 0)
                )
                stock_vendor = (
                    stocks.get("vendor", 0)
                    or p.get("remains_vendor", 0)
                    or p.get("stock_remote", 0)
                )

                # Цена
                price_info = p.get("price", {})
                price_val = (
                    price_info.get("value")
                    if isinstance(price_info, dict)
                    else p.get("price", 0)
                )

                items.append(
                    {
                        "category_id": category_id,
                        "brand": p.get("brand", {}).get(
                            "name", p.get("manufacturer", "—")
                        ),
                        "vendor_code": p.get(
                            "vendor_code", p.get("article", "—")
                        ),
                        "etm_code": p.get("code", "—"),
                        "name": p.get("name", "—"),
                        "price": price_val,
                        "stock_etm": stock_etm,
                        "stock_vendor": stock_vendor,
                        "url": f"https://www.etm.ru/catalog/{category_id}/{p.get('id', '')}",
                    }
                )

            # Проверка пагинации
            total = data.get("meta", {}).get("total", len(products))
            if page * page_size >= total:
                break

            page += 1
            time.sleep(1.5)  # Задержка во избежание рейт-лимитов

        except Exception as err:
            print(f"Ошибка парсинга: {err}")
            break

    return items


def main():
    all_products = []
    for cat in CATEGORIES:
        print(f"Сбор данных: {cat['name']} ({cat['id']})...")
        items = fetch_category_items(cat["id"])
        all_products.extend(items)

    # Убираем дубликаты по артикулу/коду ЭТМ
    unique_items = {item["etm_code"]: item for item in all_products}.values()

    payload = {
        "last_updated": datetime.utcnow().strftime("%d.%m.%Y %H:%M UTC"),
        "total_items": len(unique_items),
        "items": list(unique_items),
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Успешно сохранено {len(unique_items)} позиций.")


if __name__ == "__main__":
    main()

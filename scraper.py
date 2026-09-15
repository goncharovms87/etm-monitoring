from datetime import datetime, timezone
import json
import os
import re
import sys
import time
from playwright.sync_api import sync_playwright

# Принудительно выставляем UTF-8 для консоли Windows
sys.stdout.reconfigure(encoding="utf-8")

# Целевые категории оборудования ЭТМ
CATEGORIES = [
    {
        "id": "751010",
        "name": "Контроллеры и модули свободнопрограммируемые",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye",
        "max_pages": 15,
    },
    {
        "id": "751025",
        "name": "Модули расширения и программируемые реле",
        "url": "https://www.etm.ru/catalog/751025_programmiruemye_rele_moduli_rasshirenija",
        "max_pages": 15,
    },
    {
        "id": "75102510",
        "name": "Программируемые реле",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele",
        "max_pages": 15,
    },
]

# Целевые бренды промышленной автоматизации
TARGET_BRANDS = [
    {
        "name": "ОВЕН",
        "aliases": [
            "овен",
            "owen",
            "пр100",
            "пр102",
            "пр103",
            "пр200",
            "пр205",
            "плк110",
            "плк210",
            "плк200",
        ],
    },
    {"name": "ONI", "aliases": ["oni", "plrs", "plrk"]},
    {"name": "EKF", "aliases": ["ekf", "про-реле", "pro-relay", "pro-logic"]},
    {
        "name": "Rievtech",
        "aliases": ["rievtech", "pr-12", "pr-18", "pr-24", "sr-12", "sr-22"],
    },
    {
        "name": "Systeme Electric",
        "aliases": ["systeme electric", "систэм электрик", "systeme", "se "],
    },
    {"name": "DKC", "aliases": ["dkc", "дкс"]},
    {
        "name": "Segnetics",
        "aliases": ["segnetics", "сегнетикс", "pixel", "smh", "matrix"],
    },
    {
        "name": "ЕвроАвтоматика",
        "aliases": ["евроавтоматика", "fif", "f&f", "евроавтоматика fif"],
    },
    {
        "name": "Тракт-Автоматика",
        "aliases": ["тракт-автоматика", "тракт автоматика", "тракт"],
    },
    {"name": "КЭАЗ", "aliases": ["кэаз", "keaz", "optilogic"]},
    {
        "name": "Schneider Electric",
        "aliases": ["schneider electric", "schneider", "zelio", "modicon"],
    },
    {"name": "Siemens", "aliases": ["siemens", "logo!", "s7-1200", "simatic"]},
    {"name": "Finder", "aliases": ["finder", "optan"]},
    {"name": "INNOCONT", "aliases": ["innocont"]},
    {"name": "Autonics", "aliases": ["autonics"]},
]

# Стоп-слова для исключения силовой электроники и радиодеталей
STOP_WORDS = [
    "диод",
    "тиристор",
    "симистор",
    "igbt",
    "конденсатор",
    "варистор",
    "резистор",
    "транзистор",
    "электролитический",
    "косинусный",
    "предохранитель",
]


def identify_brand(name, vendor_code, raw_text=""):
    """Определение бренда по справочнику."""
    combined = f"{name} {vendor_code} {raw_text}".lower()
    for b in TARGET_BRANDS:
        for alias in b["aliases"]:
            if (
                re.search(
                    r"(?<![a-zA-Zа-яА-Я0-9])"
                    + re.escape(alias)
                    + r"(?![a-zA-Zа-яА-Я0-9])",
                    combined,
                )
                or alias in combined
            ):
                return b["name"]
    return "Другой"


def is_target_product(name, brand):
    """Фильтрация: оставляем только целевые ПЛК/реле и отсекаем радиодетали."""
    name_lower = name.lower()

    # 1. Отсекаем по стоп-словам
    if any(sw in name_lower for sw in STOP_WORDS):
        return False

    # 2. Если производитель из целевого пула — точно берем
    if brand != "Другой":
        return True

    # 3. Если производитель не в списке, но в названии ключевые термины автоматизации
    keywords = [
        "контроллер",
        "плк",
        "plc",
        "программируем",
        "модуль расширения",
        "модуль ввода",
        "модуль вывода",
        "логический модуль",
        "программируемое реле",
    ]
    if any(k in name_lower for k in keywords):
        return True

    return False


def parse_product_obj(item, category_name):
    """Парсинг JSON-объекта товара из сетевого ответа API ЭТМ."""
    if not isinstance(item, dict):
        return None

    code = str(
        item.get("code")
        or item.get("id")
        or item.get("goodsId")
        or item.get("etmCode")
        or ""
    )
    if not code.isdigit() or len(code) < 5:
        return None

    name = item.get("name") or item.get("title") or item.get("fullName") or ""
    if not name or len(name) < 5:
        return None

    vendor_code = (
        item.get("vendorCode")
        or item.get("vendor_code")
        or item.get("article")
        or "—"
    )

    # Извлечение бренда
    brand_val = ""
    if isinstance(item.get("producer"), dict):
        brand_val = item["producer"].get("name", "")
    elif isinstance(item.get("brand"), dict):
        brand_val = item["brand"].get("name", "")
    elif isinstance(item.get("producer"), str):
        brand_val = item["producer"]
    elif isinstance(item.get("brand"), str):
        brand_val = item["brand"]

    brand = identify_brand(name + " " + brand_val, str(vendor_code))
    if brand == "Другой" and brand_val:
        brand = brand_val.strip()

    # Цена
    price = 0.0
    price_obj = item.get("price") or item.get("prices") or {}
    if isinstance(price_obj, dict):
        price = float(
            price_obj.get("value")
            or price_obj.get("val")
            or price_obj.get("final")
            or 0
        )
    elif isinstance(price_obj, (int, float)):
        price = float(price_obj)

    # Остатки
    stock_etm = 0
    stock_vendor = 0
    stocks = item.get("stocks") or item.get("remains") or []
    if isinstance(stocks, list):
        for s in stocks:
            stype = str(s.get("type", "")).lower()
            qty = s.get("count", 0) or s.get("quantity", 0) or 0
            qty = int(qty) if str(qty).isdigit() else 0
            if any(
                x in stype
                for x in ["etm", "local", "склад", "город", "наличи"]
            ):
                stock_etm += qty
            elif any(
                x in stype for x in ["vendor", "remote", "изготов", "постав"]
            ):
                stock_vendor += qty
    elif isinstance(stocks, dict):
        stock_etm = int(stocks.get("etm", 0) or stocks.get("local", 0) or 0)
        stock_vendor = int(
            stocks.get("vendor", 0) or stocks.get("remote", 0) or 0
        )

    return {
        "category": category_name,
        "etm_code": code,
        "brand": brand,
        "vendor_code": str(vendor_code).strip(),
        "name": str(name).strip(),
        "price": price,
        "stock_etm": stock_etm,
        "stock_vendor": stock_vendor,
        "url": f"https://www.etm.ru/cat/nn/{code}",
    }


def recursive_find_products(data, category_name, out_list):
    """Рекурсивный поиск товаров в ответах API."""
    if isinstance(data, dict):
        prod = parse_product_obj(data, category_name)
        if prod:
            out_list.append(prod)
            return
        for v in data.values():
            recursive_find_products(v, category_name, out_list)
    elif isinstance(data, list):
        for elem in data:
            recursive_find_products(elem, category_name, out_list)


def fallback_dom_cards(page, category_name):
    """Резервный сбор из разметки страницы."""
    js = """
    () => {
        const out = [];
        const links = Array.from(document.querySelectorAll('a[href*="/cat/nn/"]'));
        const seen = new Set();

        for (const a of links) {
            const m = (a.getAttribute('href') || '').match(/\\/cat\\/nn\\/(\\d+)/);
            if (!m) continue;
            const code = m[1];
            if (seen.has(code)) continue;
            seen.add(code);

            let box = a;
            for (let i = 0; i < 5; i++) {
                if (!box.parentElement || box.parentElement.tagName === 'MAIN') break;
                box = box.parentElement;
                if (box.innerText && (box.innerText.includes('В корзину') || box.innerText.includes('₽'))) break;
            }

            const txt = (box ? box.innerText : a.innerText).replace(/\\u00a0/g, ' ');
            const lines = txt.split('\\n').map(s => s.trim()).filter(Boolean);

            let name = a.innerText.trim();
            let vendor = '—';
            let price = 0;
            let stock1 = 0, stock2 = 0;

            for (let i = 0; i < lines.length; i++) {
                if (lines[i].includes('Артикул:')) {
                    vendor = lines[i].replace('Артикул:', '').trim() || (lines[i+1] || '—').trim();
                }
                if (lines[i].includes('₽') && price === 0) {
                    const pm = lines[i].match(/([\\d\\s]+(?:[.,]\\d{2})?)\\s*₽/);
                    if (pm) price = parseFloat(pm[1].replace(/\\s+/g, '').replace(',', '.')) || 0;
                }
            }

            const sm = Array.from(txt.matchAll(/(\\d+)\\s*шт/g));
            if (sm.length > 0) stock1 = parseInt(sm[0][1], 10) || 0;
            if (sm.length > 1) stock2 = parseInt(sm[1][1], 10) || 0;

            out.push({
                etm_code: code,
                vendor_code: vendor,
                name: name.length > 10 ? name : (lines[0] || '—'),
                price: price,
                stock_etm: stock1,
                stock_vendor: stock2,
                raw: txt,
                url: 'https://www.etm.ru/cat/nn/' + code
            });
        }
        return out;
    }
    """
    raw = page.evaluate(js)
    res = []
    for r in raw:
        b = identify_brand(r["name"], r["vendor_code"], r["raw"])
        res.append(
            {
                "category": category_name,
                "etm_code": r["etm_code"],
                "brand": b,
                "vendor_code": r["vendor_code"],
                "name": r["name"],
                "price": r["price"],
                "stock_etm": r["stock_etm"],
                "stock_vendor": r["stock_vendor"],
                "url": r["url"],
            }
        )
    return res


def main():
    collected_dict = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
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

        network_buffer = []

        def handle_response(response):
            try:
                ct = response.headers.get("content-type", "")
                if response.status == 200 and (
                    "json" in ct or "javascript" in ct
                ):
                    if any(
                        x in response.url
                        for x in [
                            "catalog",
                            "goods",
                            "product",
                            "search",
                            "api",
                        ]
                    ):
                        network_buffer.append(response.json())
            except Exception:
                pass

        page.on("response", handle_response)

        for cat in CATEGORIES:
            print(f"\n==========================================")
            print(f"Категория: {cat['name']}")
            print(f"==========================================")

            max_p = cat.get("max_pages", 15)

            for p_num in range(1, max_p + 1):
                url = (
                    f"{cat['url']}?page={p_num}&rows=48"
                    if p_num > 1
                    else f"{cat['url']}?rows=48"
                )
                print(f"Загрузка страницы {p_num} из {max_p}: {url}")
                network_buffer.clear()

                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(2500)

                    # Плавная прокрутка для подгрузки динамических элементов
                    for scroll_y in [1200, 2400, 3600]:
                        page.evaluate(f"window.scrollTo(0, {scroll_y})")
                        page.wait_for_timeout(400)

                except Exception as e:
                    print(f"Ошибка загрузки страницы {p_num}: {e}")
                    break

                # 1. Проверяем ответы от API
                page_items = []
                for chunk in network_buffer:
                    recursive_find_products(chunk, cat["name"], page_items)

                # 2. Резервный сбор из DOM
                if len(page_items) < 10:
                    dom_items = fallback_dom_cards(page, cat["name"])
                    for di in dom_items:
                        page_items.append(di)

                new_added = 0
                for it in page_items:
                    # Фильтруем стоп-слова и нецелевые детали
                    if not is_target_product(it["name"], it["brand"]):
                        continue

                    code = it["etm_code"]
                    if code not in collected_dict:
                        collected_dict[code] = it
                        new_added += 1
                    else:
                        if (
                            collected_dict[code]["price"] == 0
                            and it["price"] > 0
                        ):
                            collected_dict[code]["price"] = it["price"]

                print(
                    f"Стр. {p_num}: получено валидных {len(page_items)}, новых в базе: {new_added} | Итого: {len(collected_dict)}"
                )

                if len(page_items) == 0:
                    print("Товары на странице отсутствуют. Категория завершена.")
                    break

        browser.close()

    final_list = list(collected_dict.values())
    print(f"\n==========================================")
    print(
        f"Сбор успешно завершен! Всего валидных позиций автоматизации: {len(final_list)}"
    )
    print(f"==========================================")

    payload = {
        "last_updated": datetime.now(timezone.utc).strftime(
            "%d.%m.%Y %H:%M UTC"
        ),
        "total_items": len(final_list),
        "items": final_list,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("Файл data.json успешно записан.")


if __name__ == "__main__":
    main()

import os
import sys

# Принудительно задаем кодировку UTF-8 для логов Windows
sys.stdout.reconfigure(encoding='utf-8')

import json
import re
import time
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

CATEGORIES = [
    {
        "id": "751010",
        "name": "Контроллеры и модули свободнопрограммируемые",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye",
        "max_pages": 15
    },
    {
        "id": "751025",
        "name": "Модули расширения и программируемые реле",
        "url": "https://www.etm.ru/catalog/751025_programmiruemye_rele_moduli_rasshirenija",
        "max_pages": 15
    },
    {
        "id": "75102510",
        "name": "Программируемые реле",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele",
        "max_pages": 15
    }
]

TARGET_BRANDS = [
    {"name": "ОВЕН", "aliases": ["овен", "owen", "пр100", "пр102", "пр103", "пр200", "пр205", "плк110", "плк210", "плк200"]},
    {"name": "ONI", "aliases": ["oni", "plrs", "plrk"]},
    {"name": "EKF", "aliases": ["ekf", "про-реле", "pro-relay", "pro-logic"]},
    {"name": "Rievtech", "aliases": ["rievtech", "pr-12", "pr-18", "pr-24", "sr-12", "sr-22"]},
    {"name": "Systeme Electric", "aliases": ["systeme electric", "систэм электрик", "systeme", "se "]},
    {"name": "DKC", "aliases": ["dkc", "дкс"]},
    {"name": "Segnetics", "aliases": ["segnetics", "сегнетикс", "pixel", "smh", "matrix"]},
    {"name": "ЕвроАвтоматика", "aliases": ["евроавтоматика", "fif", "f&f", "евроавтоматика fif"]},
    {"name": "Тракт-Автоматика", "aliases": ["тракт-автоматика", "тракт автоматика", "тракт"]},
    {"name": "КЭАЗ", "aliases": ["кэаз", "keaz", "optilogic"]},
    {"name": "Schneider Electric", "aliases": ["schneider electric", "schneider", "zelio", "modicon"]},
    {"name": "Siemens", "aliases": ["siemens", "logo!", "s7-1200", "simatic"]},
    {"name": "Finder", "aliases": ["finder", "optan"]},
    {"name": "INNOCONT", "aliases": ["innocont"]},
    {"name": "Autonics", "aliases": ["autonics"]}
]

STOP_WORDS = [
    "диод", "тиристор", "симистор", "igbt", "конденсатор", 
    "варистор", "резистор", "транзистор", "электролитический", "косинусный", "предохранитель"
]

def identify_brand(text, vendor_code):
    combined = f"{text} {vendor_code}".lower()
    for b in TARGET_BRANDS:
        for alias in b["aliases"]:
            if re.search(r'(?<![a-zA-Zа-яА-Я0-9])' + re.escape(alias) + r'(?![a-zA-Zа-яА-Я0-9])', combined) or alias in combined:
                return b["name"]
    return "Другой"

def is_target_product(name, brand):
    name_lower = name.lower()
    if any(sw in name_lower for sw in STOP_WORDS):
        return False
    if brand != "Другой":
        return True
    keywords = ["контроллер", "плк", "plc", "программируем", "модуль расширения", "модуль ввода", "модуль вывода", "логический модуль"]
    return any(k in name_lower for k in keywords)

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
            for (let i = 0; i < 7; i++) {
                if (!cur.parentElement || cur.parentElement.tagName === 'BODY' || cur.parentElement.tagName === 'MAIN') break;
                cur = cur.parentElement;
                if (cur.innerText && (cur.innerText.includes('В корзину') || cur.innerText.includes('Код товара:'))) {
                    return cur;
                }
            }
            return el.parentElement;
        }"""
    )

    text = ""
    try:
        text = card_container.as_element().inner_text().replace('\u00a0', ' ')
    except Exception:
        text = (link_el.inner_text() or '').replace('\u00a0', ' ')

    lines = [l.strip() for l in text.split('\n') if l.strip()]

    name = link_el.inner_text().strip().replace('\u00a0', ' ')
    if len(name) < 15:
        for l in lines:
            if len(l) > 25 and not any(k in l for k in ["Код товара", "Артикул", "В корзину", "₽", "Показано", "Упаковка"]):
                name = l
                break

    vendor_code = "—"
    for i, line in enumerate(lines):
        if "Артикул:" in line:
            parts = line.split("Артикул:")
            if len(parts) > 1 and parts[1].strip():
                vendor_code = parts[1].strip()
            elif i + 1 < len(lines):
                vendor_code = lines[i+1].strip()
            break

    brand = identify_brand(text, vendor_code)

    price = 0.0
    price_regex = r'([0-9][0-9\s]{0,10}(?:[.,][0-9]{2})?)\s*(?:₽|руб)'
    price_match = re.search(price_regex, text, re.IGNORECASE)
    if price_match:
        clean = price_match.group(1).replace(' ', '').replace(',', '.')
        try:
            price = float(clean)
        except ValueError:
            price = 0.0

    stock_etm = 0
    stock_vendor = 0
    stock_matches = re.findall(r'(\d+)\s*шт', text)
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
        "url": card_url
    }

def main():
    collected_dict = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--window-size=1920,1080"
            ]
        )

        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU",
            timezone_id="Europe/Moscow"
        )
        page = context.new_page()

        for cat in CATEGORIES:
            print(f"\n==========================================")
            print(f"Категория: {cat['name']}")
            print(f"==========================================")

            max_p = cat.get("max_pages", 15)

            for p_num in range(1, max_p + 1):
                page_url = f"{cat['url']}?page={p_num}" if p_num > 1 else cat["url"]
                print(f"Загрузка страницы {p_num} из {max_p}: {page_url}")

                try:
                    page.goto(page_url, wait_until="domcontentloaded", timeout=45000)

                    # ГАРАНТИРОВАННОЕ ОЖИДАНИЕ КАРТОЧЕК
                    try:
                        page.wait_for_selector("a[href*='/cat/nn/']", timeout=25000)
                    except Exception:
                        print("Карточки не появились вовремя, пробуем собрать текущее состояние...")

                    # Пошаговая прокрутка для подгрузки всех 24 карточек
                    for scroll_pos in [700, 1500, 2400, 3200]:
                        page.evaluate(f"window.scrollTo(0, {scroll_pos})")
                        page.wait_for_timeout(400)

                    # Собираем все ссылки на товары
                    all_links = page.query_selector_all("a[href*='/cat/nn/']")
                    print(f"Найдено ссылок на странице {p_num}: {len(all_links)}")

                    page_added = 0
                    for link in all_links:
                        item = extract_card_data(link, cat["name"])
                        if not item:
                            continue
                        
                        # Фильтруем радиодетали (диоды, конденсаторы)
                        if not is_target_product(item["name"], item["brand"]):
                            continue

                        code = item["etm_code"]
                        if code not in collected_dict:
                            if item["name"] != "—":
                                collected_dict[code] = item
                                page_added += 1
                        else:
                            # Обновляем цену, если раньше была 0
                            if collected_dict[code]["price"] == 0 and item["price"] > 0:
                                collected_dict[code]["price"] = item["price"]

                    print(f"Добавлено со страницы {p_num}: {page_added} | Всего в базе: {len(collected_dict)}")

                    # Если ссылок нет совсем — категория закончилась
                    if len(all_links) == 0:
                        print("Страница пуста. Переход к следующей категории.")
                        break

                except Exception as e:
                    print(f"Ошибка на странице {p_num}: {e}")
                    continue

        browser.close()

    items = list(collected_dict.values())
    print(f"\n==========================================")
    print(f"Сбор завершен! Всего уникальных позиций в базе: {len(items)}")
    print(f"==========================================")

    payload = {
        "last_updated": datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC"),
        "total_items": len(items),
        "items": items
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("Файл data.json успешно записан.")

if __name__ == "__main__":
    main()

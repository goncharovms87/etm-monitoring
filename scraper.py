import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")

# Целевые категории
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

# Целевые бренды (без пересечений подстрок)
TARGET_BRANDS = [
    {"name": "КЭАЗ", "patterns": [r"\bкэаз\b", r"\bkeaz\b", r"optilogic"]},
    {"name": "Autonics", "patterns": [r"autonics", r"\btc[34][a-z]", r"\btk4[a-z]", r"\btas-"]},
    {"name": "ОВЕН", "patterns": [r"\bовен\b", r"\bowen\b", r"\bпр10[023]\b", r"\bпр20[05]\b", r"\bплк[12]10\b", r"\bплк200\b"]},
    {"name": "ONI", "patterns": [r"\boni\b", r"plc-410", r"plrs-", r"plrk-"]},
    {"name": "EKF", "patterns": [r"\bekf\b", r"про-реле", r"pro-relay", r"pro-logic"]},
    {"name": "Rievtech", "patterns": [r"rievtech", r"\bpr-[12][0-9]\b", r"\bsr-[12][0-9]\b"]},
    {"name": "Systeme Electric", "patterns": [r"systeme electric", r"систэм электрик", r"\bsysteme\b", r"\bsm3[a-z0-9]"]},
    {"name": "DKC", "patterns": [r"\bdkc\b", r"\bдкс\b", r"\bc1000\b"]},
    {"name": "Segnetics", "patterns": [r"segnetics", r"сегнетикс", r"pixel", r"smh", r"matrix"]},
    {"name": "ЕвроАвтоматика", "patterns": [r"евроавтоматика", r"\bf&f\b", r"\bfif\b"]},
    {"name": "Тракт-Автоматика", "patterns": [r"тракт-автоматика", r"тракт автоматика"]},
    {"name": "Schneider Electric", "patterns": [r"schneider electric", r"schneider", r"zelio", r"modicon"]},
    {"name": "Siemens", "patterns": [r"siemens", r"logo!", r"s7-1200", r"s7-1500", r"simatic"]},
    {"name": "Finder", "patterns": [r"\bfinder\b", r"optan"]},
    {"name": "INNOCONT", "patterns": [r"innocont"]},
]

STOP_WORDS = [
    "диод", "тиристор", "симистор", "igbt", "конденсатор", 
    "варистор", "резистор", "транзистор", "электролитический", "косинусный", "предохранитель"
]

TARGET_KEYWORDS = [
    "контроллер",
    "плк",
    "plc",
    "программируем",
    "модуль расширения",
    "модуль ввода",
    "модуль вывода",
    "логический модуль",
    "процессорный модуль",
    "модуль",
    "программируемое реле",
    "интеллектуальное реле",
    "реле интеллектуальное",
    "контроллер программируемый",
]


def identify_brand(text, vendor_code):
    combined = f"{text} {vendor_code}".lower()
    for b in TARGET_BRANDS:
        for p in b["patterns"]:
            if re.search(p, combined):
                return b["name"]
    return "Другой"


def is_target_product(name, brand):
    name_lower = name.lower()
    if any(sw in name_lower for sw in STOP_WORDS):
        return False
    return any(k in name_lower for k in TARGET_KEYWORDS)


def extract_card_data(link_el, category_name):
    href = link_el.get_attribute("href") or ""
    m = re.search(r"/cat/nn/(\d+)", href)
    if not m:
        return None

    etm_code = m.group(1)
    card_url = f"https://www.etm.ru/cat/nn/{etm_code}"

    # Контейнер карточки до кнопки корзины/наличия
    card_container = link_el.evaluate_handle(
        """el => {
            let cur = el;
            for (let i = 0; i < 9; i++) {
                if (!cur.parentElement || cur.parentElement.tagName === 'BODY' || cur.parentElement.tagName === 'MAIN') break;
                cur = cur.parentElement;
                if (cur.innerText && (cur.innerText.includes('В корзину') || cur.innerText.includes('В корзине') || cur.innerText.includes('По запросу'))) {
                    return cur;
                }
            }
            return el.parentElement ? el.parentElement.parentElement : el;
        }"""
    )

    try:
        text = card_container.as_element().inner_text().replace('\u00a0', ' ')
    except Exception:
        text = (link_el.inner_text() or '').replace('\u00a0', ' ')

    lines = [l.strip() for l in text.split('\n') if l.strip()]

    # 1. Наименование
    name = link_el.inner_text().strip().replace('\u00a0', ' ')
    if len(name) < 15:
        for l in lines:
            if len(l) > 25 and not any(k in l for k in ["Код товара", "Артикул", "В корзину", "₽", "Показано", "Упаковка"]):
                name = l
                break

    # 2. Артикул: очистка от склеенного текста
    vendor_code = "—"
    for i, line in enumerate(lines):
        if "Артикул:" in line:
            raw_v = line.replace("Артикул:", "").strip()
            if not raw_v and i + 1 < len(lines):
                raw_v = lines[i + 1].strip()
            # Отсекаем хвосты вроде 'Упаковка:', ценников и названий брендов
            raw_v = re.split(r"(?:Упаковка|ONI|ОВЕН|EKF|КЭАЗ|Systeme|DKC|₽|\d+\s*шт)", raw_v, flags=re.IGNORECASE)[0].strip()
            if raw_v:
                vendor_code = raw_v[:40]
            break

    # 3. Производитель
    brand = identify_brand(text, vendor_code)

    # 4. Цена
    price = 0.0
    price_regex = r'([0-9][0-9\s]{0,10}(?:[.,][0-9]{2})?)\s*(?:₽|руб)'
    price_match = re.search(price_regex, text, re.IGNORECASE)
    if price_match:
        clean = price_match.group(1).replace(' ', '').replace(',', '.')
        try:
            price = float(clean)
        except ValueError:
            price = 0.0

    # 5. Остатки
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

                    try:
                        page.wait_for_selector("a[href*='/cat/nn/']", timeout=25000)
                    except Exception:
                        pass

                    for scroll_pos in [700, 1500, 2400, 3200]:
                        page.evaluate(f"window.scrollTo(0, {scroll_pos})")
                        page.wait_for_timeout(350)

                    page.wait_for_timeout(1000)

                    all_links = page.query_selector_all("a[href*='/cat/nn/']")
                    print(f"Найдено ссылок на странице {p_num}: {len(all_links)}")

                    page_added = 0
                    for link in all_links:
                        item = extract_card_data(link, cat["name"])
                        if not item:
                            continue

                        if not is_target_product(item["name"], item["brand"]):
                            continue

                        code = item["etm_code"]
                        if code not in collected_dict:
                            if item["name"] != "—":
                                collected_dict[code] = item
                                page_added += 1
                        else:
                            if collected_dict[code]["price"] == 0 and item["price"] > 0:
                                collected_dict[code]["price"] = item["price"]

                    print(f"Добавлено со страницы {p_num}: {page_added} | Всего в базе: {len(collected_dict)}")

                    if len(all_links) == 0:
                        print(f"Страница {p_num} пуста. Категория завершена.\n")
                        break

                except Exception as e:
                    print(f"Ошибка при обработке страницы {p_num}: {e}")
                    continue

        browser.close()

    items = list(collected_dict.values())
    print(f"\n==========================================")
    print(f"Сбор завершен! Всего позиций: {len(items)}")
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

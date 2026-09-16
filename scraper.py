import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")

# Выверенный список рабочих срезов каталога ЭТМ
CATEGORIES = [
    # --- КЭАЗ ---
    {
        "brand_hint": "КЭАЗ",
        "name": "КЭАЗ: OptiLogic",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye-23_keaz",
        "max_pages": 3,
    },
    # --- Rievtech ---
    {
        "brand_hint": "Rievtech",
        "name": "Rievtech: ПЛК и модули",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye-4094_rievtech",
        "max_pages": 3,
    },
    {
        "brand_hint": "Rievtech",
        "name": "Rievtech: Реле",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele-4094_rievtech",
        "max_pages": 3,
    },
    # --- Systeme Electric (SR1, SM3, контроллеры) ---
    {
        "brand_hint": "Systeme Electric",
        "name": "Systeme Electric: ПЛК и реле",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye-164_se_systeme",
        "max_pages": 8,
    },
    # --- ОВЕН ---
    {
        "brand_hint": "ОВЕН",
        "name": "ОВЕН: ПЛК и модули МВ/МУ",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye-2216_oven",
        "max_pages": 8,
    },
    {
        "brand_hint": "ОВЕН",
        "name": "ОВЕН: Программируемые реле ПР",
        "url": "https://www.etm.ru/catalog/751025_programmiruemye_rele_moduli_rasshirenija-20_owen",
        "max_pages": 6,
    },
    # --- ONI ---
    {
        "brand_hint": "ONI",
        "name": "ONI: ПЛК-410 и модули",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye?searchValue=ONI",
        "max_pages": 6,
    },
    {
        "brand_hint": "ONI",
        "name": "ONI: Реле PLR",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele-1775_oni",
        "max_pages": 3,
    },
    # --- EKF ---
    {
        "brand_hint": "EKF",
        "name": "EKF: Реле PRO-Relay",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele-760_ekf",
        "max_pages": 4,
    },
    {
        "brand_hint": "EKF",
        "name": "EKF: ПЛК PRO-Logic",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye?searchValue=EKF",
        "max_pages": 5,
    },
    # --- DKC ---
    {
        "brand_hint": "DKC",
        "name": "DKC: C1000",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye-138_dkc",
        "max_pages": 4,
    },
    # --- Segnetics ---
    {
        "brand_hint": "Segnetics",
        "name": "Segnetics: Контроллеры",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye?searchValue=Segnetics",
        "max_pages": 4,
    },
    # --- ЕвроАвтоматика ---
    {
        "brand_hint": "ЕвроАвтоматика",
        "name": "ЕвроАвтоматика F&F",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele?searchValue=Евроавтоматика",
        "max_pages": 3,
    },
    # --- Schneider Electric ---
    {
        "brand_hint": "Schneider Electric",
        "name": "Schneider Electric: ПЛК",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye-8_schneider_electric",
        "max_pages": 5,
    },
    {
        "brand_hint": "Schneider Electric",
        "name": "Schneider Electric: Zelio Logic",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele-2282_se_schneider",
        "max_pages": 4,
    },
    # --- Siemens ---
    {
        "brand_hint": "Siemens",
        "name": "Siemens: LOGO!",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele-60000121_siemens",
        "max_pages": 4,
    },
]

TARGET_BRANDS = [
    {"name": "КЭАЗ", "patterns": [r"\bкэаз\b", r"\bkeaz\b", r"optilogic", r"гжик"]},
    {"name": "Rievtech", "patterns": [r"rievtech", r"\bpr-[12][0-9]\b", r"\bsr-[12][0-9]\b", r"\bba-[0-9]"]},
    {"name": "ОВЕН", "patterns": [r"\bовен\b", r"\bowen\b", r"\bпр10[023]\b", r"\bпр20[05]\b", r"\bплк[12]10\b", r"\bплк200\b", r"\bм[вук][12]10\b"]},
    {"name": "ONI", "patterns": [r"\boni\b", r"plc-410", r"plrs-", r"plrk-"]},
    {"name": "EKF", "patterns": [r"\bekf\b", r"про-реле", r"pro-relay", r"pro-logic"]},
    {"name": "Systeme Electric", "patterns": [r"systeme electric", r"систэм электрик", r"\bsysteme\b", r"\bsm3[a-z0-9]", r"\bzr1"]},
    {"name": "DKC", "patterns": [r"\bdkc\b", r"\bдкс\b", r"\bc1000\b"]},
    {"name": "Segnetics", "patterns": [r"segnetics", r"сегнетикс", r"pixel", r"smh", r"matrix"]},
    {"name": "ЕвроАвтоматика", "patterns": [r"евроавтоматика", r"\bf&f\b", r"\bfif\b"]},
    {"name": "Schneider Electric", "patterns": [r"schneider electric", r"schneider", r"zelio", r"modicon"]},
    {"name": "Siemens", "patterns": [r"siemens", r"logo!", r"s7-1200", r"s7-1500", r"simatic"]},
    {"name": "Autonics", "patterns": [r"autonics", r"\btc[34][a-z]", r"\btk4[a-z]"]},
    {"name": "Finder", "patterns": [r"\bfinder\b", r"optan"]},
]

STOP_WORDS = [
    "диод", "тиристор", "симистор", "igbt", "конденсатор",
    "варистор", "резистор", "транзистор", "электролитический", "косинусный", "предохранитель"
]


def identify_brand(text, vendor_code, fallback_brand=""):
    combined = f"{text} {vendor_code}".lower()
    for b in TARGET_BRANDS:
        for p in b["patterns"]:
            if re.search(p, combined):
                return b["name"]
    return fallback_brand if fallback_brand else "Другой"


def is_target_product(name):
    name_lower = name.lower()
    if any(sw in name_lower for sw in STOP_WORDS):
        return False
    if "модуль" in name_lower or "контроллер" in name_lower:
        return True
    automation_terms = [
        "плк", "plc", "программируем", "логический", 
        "интеллектуальное реле", "реле интеллектуальное", "блок питания", "панель оператора"
    ]
    return any(term in name_lower for term in automation_terms)


def scroll_page_completely(page):
    """Пошаговый скролл вниз для триггера виртуализации всех 48 карточек."""
    for _ in range(6):
        page.evaluate("window.scrollBy(0, 1000)")
        page.wait_for_timeout(350)
    page.wait_for_timeout(600)
    page.evaluate("window.scrollTo(0, 300)")
    page.wait_for_timeout(300)


def extract_card_data(link_el, default_brand):
    href = link_el.get_attribute("href") or ""
    m = re.search(r"/cat/nn/(\d+)", href)
    if not m:
        return None

    etm_code = m.group(1)
    card_url = f"https://www.etm.ru/cat/nn/{etm_code}"

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

    # Наименование
    name = link_el.inner_text().strip().replace('\u00a0', ' ')
    if len(name) < 15:
        for l in lines:
            if len(l) > 25 and not any(k in l for k in ["Код товара", "Артикул", "В корзину", "₽", "Показано", "Упаковка"]):
                name = l
                break

    # Артикул
    vendor_code = "—"
    for i, line in enumerate(lines):
        if "Артикул:" in line:
            after = line.split("Артикул:", 1)[1].strip()
            if after:
                clean_v = re.split(r"(?:\s{2,}|Упаковка|Код|В корзину|₽)", after)[0].strip()
                if clean_v and clean_v != name:
                    vendor_code = clean_v
                    break
            elif i + 1 < len(lines):
                candidate = lines[i + 1].strip()
                if candidate and candidate != name and not candidate.startswith("ПЛК") and len(candidate) < 35:
                    vendor_code = candidate
                    break

    # Производитель
    brand = identify_brand(text, vendor_code, default_brand)

    # Цена
    price = 0.0
    price_regex = r'([0-9][0-9\s]{0,10}(?:[.,][0-9]{2})?)\s*(?:₽|руб)'
    price_match = re.search(price_regex, text, re.IGNORECASE)
    if price_match:
        clean = price_match.group(1).replace(' ', '').replace(',', '.')
        try:
            price = float(clean)
        except ValueError:
            price = 0.0

    # Остатки
    stock_etm = 0
    stock_vendor = 0
    stock_matches = re.findall(r'(\d+)\s*шт', text)
    if stock_matches:
        stock_etm = int(stock_matches[0])
        if len(stock_matches) > 1:
            stock_vendor = int(stock_matches[1])

    return {
        "category": default_brand,
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
            print(f"Сбор: {cat['name']}")
            print(f"==========================================")

            max_p = cat.get("max_pages", 4)

            for p_num in range(1, max_p + 1):
                delim = "&" if "?" in cat["url"] else "?"
                page_url = f"{cat['url']}{delim}rows=48&delivery=all"
                if p_num > 1:
                    page_url += f"&page={p_num}"

                print(f"Загрузка стр. {p_num} из {max_p}: {page_url}")

                try:
                    page.goto(page_url, wait_until="domcontentloaded", timeout=45000)

                    try:
                        page.wait_for_selector("a[href*='/cat/nn/']", timeout=18000)
                    except Exception:
                        pass

                    scroll_page_completely(page)

                    all_links = page.query_selector_all("a[href*='/cat/nn/']")
                    print(f"Найдено ссылок: {len(all_links)}")

                    if len(all_links) == 0:
                        print("Товары на странице отсутствуют. Срез завершен.\n")
                        break

                    page_added = 0
                    for link in all_links:
                        item = extract_card_data(link, cat["brand_hint"])
                        if not item:
                            continue

                        if not is_target_product(item["name"]):
                            continue

                        code = item["etm_code"]
                        if code not in collected_dict:
                            if item["name"] != "—":
                                collected_dict[code] = item
                                page_added += 1
                        else:
                            if collected_dict[code]["price"] == 0 and item["price"] > 0:
                                collected_dict[code]["price"] = item["price"]

                    print(f"Добавлено со стр. {p_num}: {page_added} | Всего в базе: {len(collected_dict)}")

                except Exception as e:
                    print(f"Ошибка при обработке: {e}")
                    continue

        browser.close()

    items = list(collected_dict.values())
    print(f"\n==========================================")
    print(f"Сбор завершен! Всего уникальных позиций: {len(items)}")
    print(f"==========================================")

    payload = {
        "last_updated": datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC"),
        "total_items": len(items),
        "items": items
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("Файл data.json успешно сохранен.")


if __name__ == "__main__":
    main()

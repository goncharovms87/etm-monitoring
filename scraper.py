import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")

# Выверенные срезы каталога (с принудительным показом всех позиций)
CATEGORIES = [
    # --- КЭАЗ (все 24 позиции OptiLogic) ---
    {
        "brand_hint": "КЭАЗ",
        "name": "КЭАЗ (OptiLogic)",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye-23_keaz",
        "max_pages": 2,
    },
    # --- Rievtech ---
    {
        "brand_hint": "Rievtech",
        "name": "Rievtech (Контроллеры и модули)",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye-4094_rievtech",
        "max_pages": 2,
    },
    {
        "brand_hint": "Rievtech",
        "name": "Rievtech (Программируемые реле)",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele-4094_rievtech",
        "max_pages": 2,
    },
    # --- Systeme Electric ---
    {
        "brand_hint": "Systeme Electric",
        "name": "Systeme Electric (Контроллеры и модули)",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye-164_se_systeme",
        "max_pages": 4,
    },
    {
        "brand_hint": "Systeme Electric",
        "name": "Systeme Electric (Реле интеллектуальные)",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele-164_se_systeme",
        "max_pages": 4,
    },
    # --- ОВЕН ---
    {
        "brand_hint": "ОВЕН",
        "name": "ОВЕН (Контроллеры и модули)",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye-2216_oven",
        "max_pages": 5,
    },
    {
        "brand_hint": "ОВЕН",
        "name": "ОВЕН (Программируемые реле)",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele-2216_oven",
        "max_pages": 5,
    },
    # --- ONI ---
    {
        "brand_hint": "ONI",
        "name": "ONI (Контроллеры и модули)",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye?searchValue=ONI",
        "max_pages": 4,
    },
    {
        "brand_hint": "ONI",
        "name": "ONI (Программируемые реле)",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele-1775_oni",
        "max_pages": 4,
    },
    # --- EKF ---
    {
        "brand_hint": "EKF",
        "name": "EKF (Программируемые реле)",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele-760_ekf",
        "max_pages": 4,
    },
    {
        "brand_hint": "EKF",
        "name": "EKF (Контроллеры PRO-Logic)",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye?searchValue=EKF",
        "max_pages": 4,
    },
    # --- DKC ---
    {
        "brand_hint": "DKC",
        "name": "DKC (Модули и контроллеры)",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye-138_dkc",
        "max_pages": 4,
    },
    # --- Segnetics ---
    {
        "brand_hint": "Segnetics",
        "name": "Segnetics (Контроллеры)",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye?searchValue=Segnetics",
        "max_pages": 4,
    },
    # --- Schneider Electric ---
    {
        "brand_hint": "Schneider Electric",
        "name": "Schneider Electric (Реле Zelio / ПЛК)",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele-2282_se_schneider",
        "max_pages": 4,
    },
    # --- Siemens ---
    {
        "brand_hint": "Siemens",
        "name": "Siemens (LOGO! / Simatic)",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele-60000121_siemens",
        "max_pages": 4,
    },
]

TARGET_BRANDS = [
    {"name": "КЭАЗ", "patterns": [r"\bкэаз\b", r"\bkeaz\b", r"optilogic", r"гжик"]},
    {"name": "Rievtech", "patterns": [r"rievtech", r"\bpr-[12][0-9]\b", r"\bsr-[12][0-9]\b", r"\bba-[0-9]"]},
    {"name": "ОВЕН", "patterns": [r"\bовен\b", r"\bowen\b", r"\bпр10[023]\b", r"\bпр20[05]\b", r"\bплк[12]10\b", r"\bплк200\b", r"\bм[вук]110\b", r"\bм[вук]210\b"]},
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
    # Оставляем любые модули и контроллеры
    if "модуль" in name_lower or "контроллер" in name_lower:
        return True
    automation_terms = ["плк", "plc", "программируем", "логический", "интеллектуальное реле", "реле интеллектуальное", "блок питания", "панель оператора"]
    return any(term in name_lower for term in automation_terms)


def scroll_page_completely(page):
    """Плавный скролл страницы сверху донизу для прогрузки всех виртуальных карточек."""
    prev_count = 0
    for _ in range(8):
        page.evaluate("window.scrollBy(0, 1200)")
        page.wait_for_timeout(400)
        curr_count = len(page.query_selector_all("a[href*='/cat/nn/']"))
        if curr_count > prev_count:
            prev_count = curr_count
        else:
            # Делаем еще один шаг вниз
            page.evaluate("window.scrollBy(0, 1600)")
            page.wait_for_timeout(400)
    # Возвращаемся немного вверх, чтобы обновились верхние элементы
    page.evaluate("window.scrollTo(0, 500)")
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

    # 1. Наименование
    name = link_el.inner_text().strip().replace('\u00a0', ' ')
    if len(name) < 15:
        for l in lines:
            if len(l) > 25 and not any(k in l for k in ["Код товара", "Артикул", "В корзину", "₽", "Показано", "Упаковка"]):
                name = l
                break

    # 2. Артикул
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

    # 3. Бренд
    brand = identify_brand(text, vendor_code, default_brand)

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
                # КРИТИЧЕСКИ ВАЖНО: rows=48 и delivery=all отключают скрытие заказных товаров
                page_url = f"{cat['url']}{delim}rows=48&delivery=all"
                if p_num > 1:
                    page_url += f"&page={p_num}"

                print(f"Загрузка страницы {p_num} из {max_p}: {page_url}")

                try:
                    page.goto(page_url, wait_until="domcontentloaded", timeout=45000)

                    try:
                        page.wait_for_selector("a[href*='/cat/nn/']", timeout=20000)
                    except Exception:
                        pass

                    # Прокручиваем всю страницу до конца
                    scroll_page_completely(page)

                    all_links = page.query_selector_all("a[href*='/cat/nn/']")
                    print(f"Найдено ссылок: {len(all_links)}")

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

                    print(f"Добавлено со страницы {p_num}: {page_added} | Всего в базе: {len(collected_dict)}")

                    # Если ссылок меньше 10 на первой странице, дальше переходить нет смысла
                    if len(all_links) < 30 and p_num > 1:
                        break

                except Exception as e:
                    print(f"Ошибка при обработке: {e}")
                    continue

        browser.close()

    items = list(collected_dict.values())
    print(f"\n==========================================")
    print(f"Сбор завершен! Всего валидных позиций: {len(items)}")
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

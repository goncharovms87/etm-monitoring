import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


sys.stdout.reconfigure(encoding="utf-8")


# ============================================================
# CONFIG
# ============================================================

BASE_URL = "https://www.etm.ru"
ROWS_PER_PAGE = 48
MAX_PAGES_SAFETY = 1000
MAX_SCROLL_ROUNDS = 60
SCROLL_PAUSE_MS = 500
PAGE_TIMEOUT_MS = 60000
SELECTOR_TIMEOUT_MS = 20000
RETRIES = 3
SAVE_EVERY_CATEGORY = True

OUTPUT_FILE = "data_v2.json"
ERROR_LOG_FILE = "errors_v2.json"

# Original working slices from v1.
# max_pages is intentionally removed: v2 discovers the end automatically.
CATEGORIES = [
    {
        "brand_hint": "КЭАЗ",
        "name": "КЭАЗ: OptiLogic",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye-23_keaz",
    },
    {
        "brand_hint": "Rievtech",
        "name": "Rievtech: ПЛК и модули",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye-4094_rievtech",
    },
    {
        "brand_hint": "Rievtech",
        "name": "Rievtech: Реле",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele-4094_rievtech",
    },
    {
        "brand_hint": "Systeme Electric",
        "name": "Systeme Electric: ПЛК и реле",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye-164_se_systeme",
    },
    {
        "brand_hint": "ОВЕН",
        "name": "ОВЕН: ПЛК и модули МВ/МУ",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye-2216_oven",
    },
    {
        "brand_hint": "ОВЕН",
        "name": "ОВЕН: Программируемые реле ПР",
        "url": "https://www.etm.ru/catalog/751025_programmiruemye_rele_moduli_rasshirenija-20_owen",
    },
    {
        "brand_hint": "ONI",
        "name": "ONI: ПЛК-410 и модули",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye?searchValue=ONI",
    },
    {
        "brand_hint": "ONI",
        "name": "ONI: Реле PLR",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele-1775_oni",
    },
    {
        "brand_hint": "EKF",
        "name": "EKF: Реле PRO-Relay",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele-760_ekf",
    },
    {
        "brand_hint": "EKF",
        "name": "EKF: ПЛК PRO-Logic",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye?searchValue=EKF",
    },
    {
        "brand_hint": "DKC",
        "name": "DKC: C1000",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye-138_dkc",
    },
    {
        "brand_hint": "Segnetics",
        "name": "Segnetics: Контроллеры",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye?searchValue=Segnetics",
    },
    {
        "brand_hint": "ЕвроАвтоматика",
        "name": "ЕвроАвтоматика F&F",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele?searchValue=Евроавтоматика",
    },
    {
        "brand_hint": "Schneider Electric",
        "name": "Schneider Electric: ПЛК",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye-8_schneider_electric",
    },
    {
        "brand_hint": "Schneider Electric",
        "name": "Schneider Electric: Zelio Logic",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele-2282_se_schneider",
    },
    {
        "brand_hint": "Siemens",
        "name": "Siemens: LOGO!",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele-60000121_siemens",
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
    "варистор", "резистор", "транзистор", "электролитический",
    "косинусный", "предохранитель"
]


PRODUCT_TYPES = {
    "PLC": [
        r"\bплк\b", r"\bplc\b", r"programmable logic", r"контроллер",
        r"контроллер программируем", r"программируемый контроллер"
    ],
    "Programmable relay": [
        r"программируем.*реле", r"реле.*программируем", r"\bПР\b",
        r"\bplr\b", r"zelio", r"logo!"
    ],
    "I/O module": [
        r"\bмодуль.*в/в\b", r"\bмодуль.*ввода\b", r"\bмодуль.*вывода\b",
        r"\bi/o\b", r"\binput.*output\b", r"модуль расширения",
        r"модуль.*дискрет", r"модуль.*аналог"
    ],
    "Communication module": [
        r"коммуникац", r"связи", r"ethernet", r"modbus", r"profibus",
        r"profinet", r"canopen", r"rs-485", r"rs485"
    ],
    "HMI": [
        r"панель оператора", r"\bhmi\b", r"операторская панель"
    ],
    "Power supply": [
        r"блок питания", r"источник питания"
    ],
}


def normalize_space(value):
    return re.sub(r"\s+", " ", (value or "").replace("\u00a0", " ")).strip()


def normalize_text(value):
    return normalize_space(value).lower()


def set_query(url, **params):
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update(params)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def product_id_from_href(href):
    m = re.search(r"/cat/nn/(\d+)", href or "")
    return m.group(1) if m else None


def identify_brand(text, vendor_code="", fallback_brand=""):
    combined = normalize_text(f"{text} {vendor_code}")

    # First: exact/strong manufacturer patterns.
    matches = []
    for brand in TARGET_BRANDS:
        score = 0
        for pattern in brand["patterns"]:
            if re.search(pattern, combined, re.I):
                score += 1
        if score:
            matches.append((score, brand["name"]))

    if matches:
        matches.sort(reverse=True)
        return matches[0][1]

    return fallback_brand or "Другой"


def classify_product(name, category_name="", brand=""):
    text = normalize_text(f"{name} {category_name} {brand}")

    for sw in STOP_WORDS:
        if re.search(rf"\b{re.escape(sw)}\b", text):
            return "Other"

    scores = {}
    for product_type, patterns in PRODUCT_TYPES.items():
        score = sum(bool(re.search(p, text, re.I)) for p in patterns)
        if score:
            scores[product_type] = score

    if not scores:
        return "Other"

    # More specific categories have priority over generic controller match.
    priority = [
        "Communication module",
        "I/O module",
        "Programmable relay",
        "HMI",
        "Power supply",
        "PLC",
    ]
    best_score = max(scores.values())
    candidates = [x for x in priority if scores.get(x) == best_score]
    return candidates[0] if candidates else max(scores, key=scores.get)


def is_probably_relevant(name, category_name="", brand=""):
    return classify_product(name, category_name, brand) != "Other"


def extract_price(text):
    # Prefer normal currency amounts; return 0 when no reliable amount exists.
    matches = re.findall(
        r"(?<!\d)(\d{1,3}(?:[\s\u00a0]\d{3})*(?:[.,]\d{2})?)\s*(?:₽|руб\.?|руб\b)",
        text or "",
        re.I
    )
    if not matches:
        return 0.0

    try:
        return float(matches[0].replace(" ", "").replace("\u00a0", "").replace(",", "."))
    except ValueError:
        return 0.0


def extract_article(lines):
    patterns = [
        r"Артикул\s*:\s*(.+)",
        r"Артикул\s+(.+)",
        r"Производитель\s*:\s*.+?\s+Артикул\s*:\s*(.+)",
    ]

    for line in lines:
        line = normalize_space(line)
        for pattern in patterns:
            m = re.search(pattern, line, re.I)
            if m:
                value = normalize_space(m.group(1))
                value = re.split(r"(?:Упаковка|Код товара|В корзину|В корзине|По запросу|₽|руб)", value, flags=re.I)[0]
                if value and len(value) <= 100:
                    return value

    return "—"


def extract_stock(text):
    """
    Conservative stock parser.
    We keep raw text too, because ETM page layout can change and blindly
    assigning first/second 'шт' is unsafe.
    """
    normalized = normalize_space(text)
    stock_etm = None
    stock_vendor = None

    etm_patterns = [
        r"(?:ЭТМ|на складе ЭТМ|склад ЭТМ)[^0-9]{0,40}(\d+)\s*шт",
        r"(\d+)\s*шт[^.\n]{0,40}(?:ЭТМ|склад ЭТМ)",
    ]
    vendor_patterns = [
        r"(?:поставщик|склад поставщика)[^0-9]{0,40}(\d+)\s*шт",
        r"(\d+)\s*шт[^.\n]{0,40}(?:поставщик|склад поставщика)",
    ]

    for p in etm_patterns:
        m = re.search(p, normalized, re.I)
        if m:
            stock_etm = int(m.group(1))
            break

    for p in vendor_patterns:
        m = re.search(p, normalized, re.I)
        if m:
            stock_vendor = int(m.group(1))
            break

    return stock_etm, stock_vendor


def get_card_container(link_el):
    try:
        handle = link_el.evaluate_handle(
            """el => {
                let cur = el;
                for (let i = 0; i < 10; i++) {
                    if (!cur || !cur.parentElement ||
                        cur.parentElement.tagName === 'BODY' ||
                        cur.parentElement.tagName === 'MAIN') break;
                    cur = cur.parentElement;
                    const t = cur.innerText || '';
                    if (t.includes('В корзину') ||
                        t.includes('В корзине') ||
                        t.includes('По запросу')) return cur;
                }
                return el.parentElement || el;
            }"""
        )
        return handle.as_element()
    except Exception:
        return None


def extract_card_data(link_el, category):
    href = link_el.get_attribute("href") or ""
    etm_code = product_id_from_href(href)
    if not etm_code:
        return None

    card_url = f"{BASE_URL}/cat/nn/{etm_code}"

    container = get_card_container(link_el)
    try:
        text = normalize_space(container.inner_text()) if container else ""
    except Exception:
        text = ""

    if not text:
        try:
            text = normalize_space(link_el.inner_text())
        except Exception:
            text = ""

    try:
        name = normalize_space(link_el.inner_text())
    except Exception:
        name = ""

    lines = [normalize_space(x) for x in text.split("\n") if normalize_space(x)]

    if len(name) < 5:
        for line in lines:
            if len(line) >= 10 and not re.search(
                r"Код товара|Артикул|В корзину|₽|Показано|Упаковка",
                line,
                re.I,
            ):
                name = line
                break

    vendor_code = extract_article(lines)
    brand = identify_brand(text, vendor_code, category["brand_hint"])
    product_type = classify_product(name, category["name"], brand)
    price = extract_price(text)
    stock_etm, stock_vendor = extract_stock(text)

    return {
        "category": category["name"],
        "brand_hint": category["brand_hint"],
        "etm_code": etm_code,
        "brand": brand,
        "product_type": product_type,
        "vendor_code": vendor_code,
        "name": name or "—",
        "price": price,
        "stock_etm": stock_etm,
        "stock_vendor": stock_vendor,
        "url": card_url,
        "source_page": None,
    }


def collect_visible_links(page):
    result = {}
    for link in page.locator("a[href*='/cat/nn/']").all():
        try:
            href = link.get_attribute("href") or ""
            pid = product_id_from_href(href)
            if pid:
                result[pid] = href
        except Exception:
            continue
    return result


def scroll_until_stable(page):
    """
    Collect links while scrolling, so virtualized cards are not lost.
    Returns every unique product ID observed during the scan.
    """
    observed = {}
    stable_rounds = 0
    previous_height = -1
    previous_count = -1

    for _ in range(MAX_SCROLL_ROUNDS):
        current = collect_visible_links(page)
        observed.update(current)

        metrics = page.evaluate(
            """() => ({
                y: window.scrollY,
                h: document.documentElement.scrollHeight,
                vh: window.innerHeight
            })"""
        )

        at_bottom = metrics["y"] + metrics["vh"] >= metrics["h"] - 50

        if len(observed) == previous_count and metrics["h"] == previous_height:
            stable_rounds += 1
        else:
            stable_rounds = 0

        if at_bottom and stable_rounds >= 2:
            break

        previous_count = len(observed)
        previous_height = metrics["h"]

        page.evaluate("window.scrollBy(0, Math.max(800, window.innerHeight * 0.85))")
        page.wait_for_timeout(SCROLL_PAUSE_MS)

    return observed


def detect_pagination_end(page, current_ids, previous_page_ids, page_num):
    """
    Stronger end-of-pagination test:
    - no products;
    - repeated exact product set;
    - explicit 'next' button disabled, when detectable.
    """
    if not current_ids:
        return True, "empty_page"

    if previous_page_ids and current_ids == previous_page_ids:
        return True, "repeated_product_set"

    selectors = [
        "button[aria-label*='След']",
        "a[aria-label*='След']",
        "button:has-text('Следующая')",
        "a:has-text('Следующая')",
        "button:has-text('Далее')",
        "a:has-text('Далее')",
    ]

    for selector in selectors:
        try:
            loc = page.locator(selector)
            if loc.count():
                for i in range(loc.count()):
                    el = loc.nth(i)
                    disabled = el.is_disabled() if el.evaluate("e => 'disabled' in e") else False
                    cls = (el.get_attribute("class") or "").lower()
                    aria = (el.get_attribute("aria-disabled") or "").lower()
                    if disabled or "disabled" in cls or aria == "true":
                        return True, "next_disabled"
        except Exception:
            pass

    return False, ""


def save_json(path, payload):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def merge_item(existing, new):
    if existing is None:
        return new

    # Prefer non-empty/newer information without destroying useful data.
    for key in ["name", "vendor_code", "url"]:
        if (not existing.get(key) or existing.get(key) == "—") and new.get(key):
            existing[key] = new[key]

    if existing.get("brand") in (None, "", "Другой") and new.get("brand") not in (None, "", "Другой"):
        existing["brand"] = new["brand"]

    if existing.get("product_type") in (None, "", "Other") and new.get("product_type") != "Other":
        existing["product_type"] = new["product_type"]

    if not existing.get("price") and new.get("price"):
        existing["price"] = new["price"]

    for key in ["stock_etm", "stock_vendor"]:
        if existing.get(key) is None and new.get(key) is not None:
            existing[key] = new[key]

    existing.setdefault("source_pages", [])
    page = new.get("source_page")
    if page and page not in existing["source_pages"]:
        existing["source_pages"].append(page)

    return existing


def process_category(page, category, collected, errors):
    stats = {
        "pages_processed": 0,
        "pages_empty": 0,
        "products_observed": 0,
        "products_new": 0,
        "repeated_pages": 0,
        "errors": 0,
    }

    previous_page_ids = None

    for page_num in range(1, MAX_PAGES_SAFETY + 1):
        page_url = set_query(
            category["url"],
            rows=ROWS_PER_PAGE,
            delivery="all",
            page=page_num,
        )

        print(f"\n[{category['name']}] Страница {page_num}: {page_url}")

        success = False

        for attempt in range(1, RETRIES + 1):
            try:
                page.goto(page_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)

                try:
                    page.wait_for_selector(
                        "a[href*='/cat/nn/']",
                        timeout=SELECTOR_TIMEOUT_MS,
                    )
                except PlaywrightTimeoutError:
                    pass

                page.wait_for_timeout(1000)

                links = scroll_until_stable(page)
                current_ids = set(links.keys())

                stats["pages_processed"] += 1
                stats["products_observed"] += len(current_ids)

                print(f"  Уникальных ID на странице/скролле: {len(current_ids)}")

                if not current_ids:
                    stats["pages_empty"] += 1
                    success = True
                    return stats

                repeated = bool(previous_page_ids and current_ids == previous_page_ids)
                if repeated:
                    stats["repeated_pages"] += 1

                # Extract only after collecting the complete visible/virtualized set.
                for etm_code, href in links.items():
                    locator = page.locator(f"a[href*='/cat/nn/{etm_code}']").first

                    try:
                        item = extract_card_data(locator, category)
                    except Exception as exc:
                        errors.append({
                            "category": category["name"],
                            "page": page_num,
                            "etm_code": etm_code,
                            "url": f"{BASE_URL}/cat/nn/{etm_code}",
                            "error": repr(exc),
                            "attempt": attempt,
                        })
                        continue

                    if not item:
                        continue

                    item["source_page"] = page_num
                    item["category_url"] = category["url"]

                    # IMPORTANT: retain all observed products.
                    # Relevance is a classification field, not a collection filter.
                    key = item["etm_code"]
                    before = key in collected
                    collected[key] = merge_item(collected.get(key), item)

                    if not before:
                        stats["products_new"] += 1

                end, reason = detect_pagination_end(
                    page,
                    current_ids,
                    previous_page_ids,
                    page_num,
                )

                previous_page_ids = current_ids
                success = True

                if end:
                    print(f"  Конец среза: {reason}")
                    return stats

                break

            except Exception as exc:
                stats["errors"] += 1
                errors.append({
                    "category": category["name"],
                    "page": page_num,
                    "url": page_url,
                    "error": repr(exc),
                    "attempt": attempt,
                })
                print(f"  Ошибка, попытка {attempt}/{RETRIES}: {exc}")
                page.wait_for_timeout(1500 * attempt)

        if not success:
            # Continue with next page only after all retries failed.
            print(f"  Страница {page_num} пропущена после {RETRIES} попыток.")

    errors.append({
        "category": category["name"],
        "page": MAX_PAGES_SAFETY,
        "error": "MAX_PAGES_SAFETY reached; pagination may not have been detected.",
    })

    return stats


def main():
    collected = {}
    errors = []
    category_stats = {}

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

        for category in CATEGORIES:
            print("\n" + "=" * 70)
            print(f"СБОР: {category['name']}")
            print("=" * 70)

            stats = process_category(page, category, collected, errors)
            category_stats[category["name"]] = stats

            if SAVE_EVERY_CATEGORY:
                partial_payload = {
                    "last_updated": datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC"),
                    "parser_version": "2.0",
                    "status": "partial",
                    "total_items": len(collected),
                    "category_stats": category_stats,
                    "items": list(collected.values()),
                    "errors": errors,
                }
                save_json(OUTPUT_FILE, partial_payload)

            print(f"Итого после категории: {len(collected)} товаров")

        browser.close()

    items = list(collected.values())

    # Recalculate relevance after complete collection.
    for item in items:
        item["relevant_for_automation_research"] = is_probably_relevant(
            item.get("name", ""),
            item.get("category", ""),
            item.get("brand", ""),
        )

    type_stats = {}
    brand_stats = {}

    for item in items:
        pt = item.get("product_type", "Other")
        br = item.get("brand", "Другой")
        type_stats[pt] = type_stats.get(pt, 0) + 1
        brand_stats[br] = brand_stats.get(br, 0) + 1

    payload = {
        "last_updated": datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC"),
        "parser_version": "2.0",
        "status": "complete",
        "total_items": len(items),
        "statistics": {
            "by_product_type": dict(sorted(type_stats.items(), key=lambda x: (-x[1], x[0]))),
            "by_brand": dict(sorted(brand_stats.items(), key=lambda x: (-x[1], x[0]))),
        },
        "category_stats": category_stats,
        "items": items,
        "errors": errors,
    }

    save_json(OUTPUT_FILE, payload)
    save_json(ERROR_LOG_FILE, errors)

    print("\n" + "=" * 70)
    print(f"СБОР ЗАВЕРШЕН. Уникальных товаров: {len(items)}")
    print(f"Ошибок/предупреждений: {len(errors)}")
    print(f"JSON: {OUTPUT_FILE}")
    print(f"LOG:  {ERROR_LOG_FILE}")
    print("=" * 70)


if __name__ == "__main__":
    main()

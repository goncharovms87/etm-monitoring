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
# НАСТРОЙКИ
# ============================================================

MAX_PAGES_SAFETY = 25
NAVIGATION_TIMEOUT = 45000
PRODUCT_WAIT_TIMEOUT = 18000
NAVIGATION_RETRIES = 3

CATEGORIES = [
    # --- КЭАЗ ---
    {
        "brand_hint": "КЭАЗ",
        "name": "КЭАЗ: OptiLogic",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye-23_keaz",
    },
    # --- Rievtech ---
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
    # --- Systeme Electric ---
    {
        "brand_hint": "Systeme Electric",
        "name": "Systeme Electric: ПЛК и реле",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye-164_se_systeme",
    },
    # --- ОВЕН ---
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
    # --- ONI ---
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
    # --- EKF ---
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
    # --- DKC ---
    {
        "brand_hint": "DKC",
        "name": "DKC: C1000",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye-138_dkc",
    },
    # --- Segnetics ---
    {
        "brand_hint": "Segnetics",
        "name": "Segnetics: Контроллеры",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye?searchValue=Segnetics",
    },
    # --- Тракт-Автоматика ---
    {
        "brand_hint": "Тракт-Автоматика",
        "name": "Тракт-Автоматика: Контроллеры и модули",
        "url": "https://www.etm.ru/catalog/751010_kontrollery_i_moduli_svobodnoprogrammiruemye?searchValue=Тракт",
    },
    # --- ЕвроАвтоматика ---
    {
        "brand_hint": "ЕвроАвтоматика",
        "name": "ЕвроАвтоматика F&F",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele?searchValue=Евроавтоматика",
    },
    # --- Schneider Electric ---
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
    # --- Siemens ---
    {
        "brand_hint": "Siemens",
        "name": "Siemens: LOGO!",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele-60000121_siemens",
    },
]

TARGET_BRANDS = [
    {"name": "КЭАЗ", "patterns": [r"\bкэаз\b", r"\bkeaz\b", r"optilogic"]},
    {"name": "Rievtech", "patterns": [r"rievtech", r"\bpr-[12][0-9]\b", r"\bsr-[12][0-9]\b", r"\bba-[0-9]"]},
    {"name": "ОВЕН", "patterns": [r"\bовен\b", r"\bowen\b", r"\bпр10[023]\b", r"\bпр20[05]\b", r"\bплк[12]10\b", r"\bплк200\b", r"\bм[вук][12]10\b"]},
    {"name": "ONI", "patterns": [r"\boni\b", r"plc-410", r"plrs-", r"plrk-"]},
    {"name": "EKF", "patterns": [r"\bekf\b", r"про-реле", r"pro-relay", r"pro-logic"]},
    {"name": "Systeme Electric", "patterns": [r"systeme electric", r"систэм электрик", r"\bsysteme\b", r"\bsm3[a-z0-9]", r"\bzr1"]},
    {"name": "DKC", "patterns": [r"\bdkc\b", r"\bдкс\b", r"\bc1000\b"]},
    {"name": "Segnetics", "patterns": [r"segnetics", r"сегнетикс", r"pixel", r"smh", r"matrix"]},
    {"name": "Тракт-Автоматика", "patterns": [r"тракт[- ]автоматика", r"\bтракт\b"]},
    {"name": "ЕвроАвтоматика", "patterns": [r"евроавтоматика", r"\bf&f\b", r"\bfif\b"]},
    {"name": "Schneider Electric", "patterns": [r"schneider electric", r"\bschneider\b", r"zelio", r"modicon"]},
    {"name": "Siemens", "patterns": [r"siemens", r"logo!", r"s7-1200", r"s7-1500", r"simatic"]},
    {"name": "Autonics", "patterns": [r"autonics", r"\btc[34][a-z]", r"\btk4[a-z]"]},
    {"name": "Finder", "patterns": [r"\bfinder\b", r"optan"]},
]

STOP_WORDS = [
    "диод", "тиристор", "симистор", "igbt", "конденсатор",
    "варистор", "резистор", "транзистор", "электролитический",
    "косинусный", "предохранитель"
]

PRODUCT_TYPE_PATTERNS = {
    "PLC": [
        r"\bплк\b", r"\bplc\b", r"программируемый логический контроллер",
        r"programmable logic controller", r"контроллер.*программ",
    ],
    "Programmable relay": [
        r"программируем.*реле", r"реле.*программируем",
        r"интеллектуальн.*реле", r"smart relay",
        r"\bplr\b", r"\bpr[- ]\d", r"zelio", r"logo!",
    ],
    "I/O module": [
        r"модуль.*вход", r"модуль.*выход", r"модуль.*в/в",
        r"модуль.*ввода", r"модуль.*вывода",
        r"\bi/?o\b", r"input.*output", r"ввод.*вывод",
        r"блок\s+(?:в/?в|ввода[- ]вывода)",
    ],
    "Communication module": [
        r"коммуникационн.*модул", r"модул.*связ",
        r"ethernet.*модул", r"modbus.*модул",
        r"profinet.*модул", r"profibus.*модул",
        r"gateway", r"шлюз",
    ],
    "HMI": [
        r"панель оператора", r"операторская панель",
        r"\bhmi\b", r"сенсорн.*панел", r"панел.*оператор",
    ],
    "Power supply": [
        r"блок питания", r"источник питания", r"power supply",
    ],
}


def normalize_text(value):
    return re.sub(r"\s+", " ", (value or "").replace("\xa0", " ")).strip()


def build_page_url(base_url, page_number):
    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["delivery"] = "all"
    query["rows"] = "48"
    if page_number > 1:
        query["page"] = str(page_number)
    else:
        query.pop("page", None)

    return urlunsplit((
        parts.scheme,
        parts.netloc,
        parts.path,
        urlencode(query, doseq=True),
        parts.fragment,
    ))


def clean_article_brand(value):
    if not value or value == "—":
        return "—"
    brands_regex = r"(?:\s+|\n)+(?:КЭАЗ|Rievtech|ОВЕН|ONI|EKF|Systeme(?:\s+Electric)?|DKC|ДКС|Segnetics|Тракт[- ]Автоматика|Тракт|ЕвроАвтоматика|Schneider(?:\s+Electric)?|Siemens|Autonics|Finder|KEAZ|OWEN)\b.*$"
    cleaned = re.sub(brands_regex, "", value, flags=re.IGNORECASE).strip()
    return cleaned if cleaned else value.strip()


def identify_brand(text, vendor_code, fallback_brand=""):
    combined = normalize_text(f"{text} {vendor_code}").lower()
    for b in TARGET_BRANDS:
        for pattern in b["patterns"]:
            if re.search(pattern, combined, re.IGNORECASE):
                return b["name"]
    return fallback_brand or "Другой"


def classify_product(name, full_text=""):
    text = normalize_text(f"{name} {full_text}").lower()
    if any(sw in text for sw in STOP_WORDS):
        return "Excluded"

    for product_type in [
        "Communication module",
        "I/O module",
        "HMI",
        "Programmable relay",
        "PLC",
        "Power supply",
    ]:
        for pattern in PRODUCT_TYPE_PATTERNS[product_type]:
            if re.search(pattern, text, re.IGNORECASE):
                return product_type

    if "модуль" in text:
        return "Other module"
    if "контроллер" in text:
        return "Other controller"
    return "Other"


def parse_price(text):
    patterns = [
        r"([0-9][0-9\s]{0,12}(?:[.,][0-9]{2})?)\s*(?:₽|руб\.?)",
        r"([0-9][0-9\s]{0,12}(?:[.,][0-9]{2})?)\s*р\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        value = match.group(1).replace(" ", "").replace(",", ".")
        try:
            return float(value)
        except ValueError:
            pass
    return 0.0


def parse_stock(text):
    """
    Точный парсинг остатков с учетом разделителей тысяч (1 943 шт.):
    - Захватывает группы цифр с пробелами перед 'шт'
    - Корректно раскладывает по складам [ЭТМ, Вендор]
    """
    # Заменяем неразрывные пробелы на обычные
    norm = normalize_text(text).replace("\u00a0", " ")
    stock_etm = 0
    stock_vendor = 0

    # Захватываем число с возможными пробелами внутри тысяч: например "1 943", "12 214"
    raw_matches = re.findall(r"(\d[\d\s]{0,8})\s*шт\b", norm, re.IGNORECASE)
    
    matches = []
    for m in raw_matches:
        cleaned = re.sub(r"\s+", "", m)
        if cleaned.isdigit():
            val = int(cleaned)
            # Отсекаем мусор и аномалии более 50 000 шт
            if val < 50000:
                matches.append(val)

    # Стандартная плитка ЭТМ: [Склад ЭТМ, Склад вендора]
    if len(matches) >= 2:
        stock_etm = matches[0]
        stock_vendor = matches[1]
    elif len(matches) == 1:
        # Если блок остатка только один:
        if any(w in norm.lower() for w in ["позже", "склад поставщика", "производит", "под заказ"]):
            stock_vendor = matches[0]
        else:
            stock_etm = matches[0]

    return stock_etm, stock_vendor, matches


def parse_vendor_code(lines):
    for i, line in enumerate(lines):
        if "Артикул:" in line:
            after = line.split("Артикул:", 1)[1].strip()
            if after:
                clean = re.split(
                    r"(?:\s{2,}|\n|Упаковка|Код товара|В корзину|₽|руб\.?)",
                    after,
                    maxsplit=1,
                )[0].strip()
                clean = clean_article_brand(clean)
                if clean and len(clean) < 80:
                    return clean

            if i + 1 < len(lines):
                candidate = lines[i + 1].strip()
                candidate = clean_article_brand(candidate)
                if (
                    candidate
                    and len(candidate) < 80
                    and candidate != lines[0]
                    and not candidate.startswith(("В корзину", "Упаковка"))
                ):
                    return candidate
    return "—"


def extract_name_from_card(card_text):
    lines = [
        normalize_text(x)
        for x in card_text.splitlines()
        if normalize_text(x)
    ]
    if not lines:
        return "—"

    excluded_fragments = (
        "код товара", "артикул", "в корзину", "в корзине",
        "показано", "упаковка", "цена", "руб", "₽",
    )
    for line in lines:
        low = line.lower()
        if len(line) >= 15 and not any(x in low for x in excluded_fragments):
            return line
    return lines[0]


def extract_cards_bulk(page, default_brand):
    cards = page.evaluate(
        """
        ({defaultBrand}) => {
            const links = Array.from(document.querySelectorAll("a[href*='/cat/nn/']"));
            const result = [];
            const seen = new Set();

            function normalize(s) {
                return (s || "").replace(/\\u00a0/g, " ").replace(/\\s+/g, " ").trim();
            }

            function getContainer(link) {
                let cur = link;
                for (let i = 0; i < 10; i++) {
                    if (!cur.parentElement) break;
                    cur = cur.parentElement;
                    const t = cur.innerText || "";
                    if (
                        t.includes("В корзину") ||
                        t.includes("В корзине") ||
                        t.includes("По запросу") ||
                        t.includes("Артикул:")
                    ) {
                        return cur;
                    }
                }
                return link.parentElement || link;
            }

            for (const link of links) {
                const href = link.getAttribute("href") || "";
                const match = href.match(/\\/cat\\/nn\\/(\\d+)/);
                if (!match) continue;

                const etmCode = match[1];
                if (seen.has(etmCode)) continue;
                seen.add(etmCode);

                const container = getContainer(link);
                const text = normalize(container.innerText || link.innerText || "");
                const name = normalize(link.innerText || "");

                result.push({
                    etm_code: etmCode,
                    href: href,
                    name: name,
                    card_text: text,
                    default_brand: defaultBrand
                });
            }
            return result;
        }
        """,
        {"defaultBrand": default_brand},
    )
    return cards or []


def card_to_item(card, category):
    etm_code = card["etm_code"]
    name = normalize_text(card.get("name", ""))
    card_text = normalize_text(card.get("card_text", ""))

    if len(name) < 15:
        name = extract_name_from_card(card_text)

    lines = [
        normalize_text(x)
        for x in card_text.splitlines()
        if normalize_text(x)
    ]

    vendor_code = parse_vendor_code(lines)
    brand = identify_brand(card_text, vendor_code, category["brand_hint"])
    vendor_code = clean_article_brand(vendor_code)

    price = parse_price(card_text)
    stock_etm, stock_vendor, stock_all = parse_stock(card_text)
    product_type = classify_product(name, card_text)
    card_url = f"https://www.etm.ru/cat/nn/{etm_code}"

    return {
        "category": category["name"],
        "category_brand_hint": category["brand_hint"],
        "etm_code": etm_code,
        "brand": brand,
        "vendor_code": vendor_code,
        "name": name or "—",
        "product_type": product_type,
        "price": price,
        "stock_etm": stock_etm,
        "stock_vendor": stock_vendor,
        "stock_all": stock_all,
        "url": card_url,
        "sources": [category["name"]],
    }


def merge_item(existing, new_item):
    if existing is None:
        return new_item

    for key in [
        "brand", "vendor_code", "name", "price",
        "stock_etm", "stock_vendor", "stock_all",
    ]:
        old = existing.get(key)
        new = new_item.get(key)

        if key == "price":
            if (not old or old == 0) and new:
                existing[key] = new
        elif key == "stock_all":
            if len(new or []) > len(old or []):
                existing[key] = new
        else:
            if (
                (not old or old == "—" or old == "Другой")
                and new
                and new not in ("—", "Другой")
            ):
                existing[key] = new

    existing["sources"] = sorted(
        set(existing.get("sources", [])) | set(new_item.get("sources", []))
    )
    return existing


def scroll_page(page):
    try:
        page.wait_for_selector("a[href*='/cat/nn/']", timeout=15000)
    except Exception:
        pass

    for y in [1000, 2200, 3600, 5200]:
        page.evaluate(f"window.scrollTo(0, {y})")
        page.wait_for_timeout(500)

    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(600)
    page.evaluate("window.scrollTo(0, 300)")
    page.wait_for_timeout(300)


def navigate_with_retry(page, url):
    last_error = None
    for attempt in range(1, NAVIGATION_RETRIES + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT)
            try:
                page.wait_for_selector("a[href*='/cat/nn/']", timeout=PRODUCT_WAIT_TIMEOUT)
            except PlaywrightTimeoutError:
                pass
            return True
        except Exception as exc:
            last_error = exc
            print(f"  Попытка перехода {attempt}/{NAVIGATION_RETRIES} неудачна: {exc}")
            if attempt < NAVIGATION_RETRIES:
                time.sleep(1.0 * attempt)

    print(f"  ОШИБКА загрузки страницы: {last_error}")
    return False


def collect_category(page, category, collected, stats, errors):
    page_number = 1
    previous_page_signature = None

    while page_number <= MAX_PAGES_SAFETY:
        page_url = build_page_url(category["url"], page_number)
        print(f"\n  Страница {page_number}: {page_url}")

        if not navigate_with_retry(page, page_url):
            errors.append({
                "category": category["name"],
                "page": page_number,
                "url": page_url,
                "error": "navigation_failed",
            })
            break

        scroll_page(page)
        cards = extract_cards_bulk(page, category["brand_hint"])

        if not cards:
            print("  Товарные карточки не найдены — срез завершен.")
            break

        page_signature = tuple(sorted(card["etm_code"] for card in cards))
        if page_number > 1 and page_signature == previous_page_signature:
            print("  Страница повторяет предыдущую — остановка пагинации.")
            break
        previous_page_signature = page_signature

        added = 0
        relevant = 0

        for card in cards:
            item = card_to_item(card, category)
            if item["product_type"] == "Excluded":
                continue

            relevant += 1
            code = item["etm_code"]

            if code not in collected:
                collected[code] = item
                added += 1
            else:
                merge_item(collected[code], item)

        stats["pages"] += 1
        stats["cards_seen"] += len(cards)
        stats["relevant"] += relevant
        stats["added"] += added

        print(
            f"  Найдено на странице: {len(cards)} | Новых: {added} | Всего в базе: {len(collected)}"
        )

        if added == 0 and page_number > 1:
            print("  Новые позиции отсутствуют — завершение среза.")
            break

        page_number += 1


def save_with_history(payload):
    """
    Сохраняет ежедневный срез в history/YYYY-MM-DD.json,
    рассчитывает дельты за сутки и вычисляет чистую уходимость
    (продажи) со складов ЭТМ и поставщиков за 1, 7 и 30 дней.
    """
    os.makedirs("history", exist_ok=True)
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_history_file = os.path.join("history", f"{today_str}.json")

    # 1. Формируем снимок за сегодня (все ключи строго str)
    daily_snapshot = {}
    for item in payload.get("items", []):
        code = str(item.get("etm_code", ""))
        if not code:
            continue
        daily_snapshot[code] = {
            "price": item.get("price", 0.0),
            "stock_etm": item.get("stock_etm", 0),
            "stock_vendor": item.get("stock_vendor", 0),
        }

    try:
        with open(today_history_file, "w", encoding="utf-8") as f:
            json.dump(daily_snapshot, f, ensure_ascii=False)
    except Exception as e:
        print(f"  Внимание: не удалось записать снимок {today_history_file}: {e}")

    # 2. Загружаем все исторические файлы, отсортированные по дате
    history_files = sorted(
        [f for f in os.listdir("history") if f.endswith(".json")]
    )

    history_snapshots = []
    for hf in history_files:
        path = os.path.join("history", hf)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    history_snapshots.append((hf.replace(".json", ""), data))
        except Exception as e:
            print(f"  Пропуск поврежденного файла {hf}: {e}")

    # 3. Подготовка структур для подсчета уходимости (чистого расхода)
    sales_map = {}
    for item in payload.get("items", []):
        code = str(item.get("etm_code", ""))
        sales_map[code] = {
            "etm_1d": 0, "vendor_1d": 0,
            "etm_7d": 0, "vendor_7d": 0,
            "etm_30d": 0, "vendor_30d": 0,
        }

    num_snaps = len(history_snapshots)
    if num_snaps >= 2:
        for i in range(1, num_snaps):
            prev_snap = history_snapshots[i - 1][1]
            cur_snap = history_snapshots[i][1]
            days_from_end = num_snaps - 1 - i  # 0 - вчера -> сегодня

            for code, cur_data in cur_snap.items():
                code_str = str(code)
                if code_str not in prev_snap:
                    continue

                if code_str not in sales_map:
                    sales_map[code_str] = {
                        "etm_1d": 0, "vendor_1d": 0,
                        "etm_7d": 0, "vendor_7d": 0,
                        "etm_30d": 0, "vendor_30d": 0,
                    }

                prev_data = prev_snap[code_str]
                prev_etm = prev_data.get("stock_etm", 0)
                cur_etm = cur_data.get("stock_etm", 0)
                prev_v = prev_data.get("stock_vendor", 0)
                cur_v = cur_data.get("stock_vendor", 0)

                # Продажа = только если остаток уменьшился и вчера было > 0
                sold_etm = (prev_etm - cur_etm) if (prev_etm > 0 and cur_etm < prev_etm) else 0
                sold_v = (prev_v - cur_v) if (prev_v > 0 and cur_v < prev_v) else 0

                if days_from_end == 0:
                    sales_map[code_str]["etm_1d"] += sold_etm
                    sales_map[code_str]["vendor_1d"] += sold_v

                if days_from_end < 7:
                    sales_map[code_str]["etm_7d"] += sold_etm
                    sales_map[code_str]["vendor_7d"] += sold_v

                if days_from_end < 30:
                    sales_map[code_str]["etm_30d"] += sold_etm
                    sales_map[code_str]["vendor_30d"] += sold_v

    # 4. Получаем данные вчерашнего дня (предпоследний срез)
    yesterday_data = history_snapshots[-2][1] if num_snaps >= 2 else {}

    # 5. Обогащаем товары метриками
    default_sales = {
        "etm_1d": 0, "vendor_1d": 0,
        "etm_7d": 0, "vendor_7d": 0,
        "etm_30d": 0, "vendor_30d": 0,
    }

    for item in payload.get("items", []):
        code = str(item.get("etm_code", ""))
        prev = yesterday_data.get(code)

        if prev:
            old_price = prev.get("price", 0.0)
            cur_price = item.get("price", 0.0)
            item["price_diff"] = round(cur_price - old_price, 2) if old_price > 0 and cur_price > 0 else 0.0
            item["stock_etm_diff"] = item.get("stock_etm", 0) - prev.get("stock_etm", 0)
            item["stock_vendor_diff"] = item.get("stock_vendor", 0) - prev.get("stock_vendor", 0)
            item["is_new"] = False
        else:
            item["price_diff"] = 0.0
            item["stock_etm_diff"] = 0
            item["stock_vendor_diff"] = 0
            item["is_new"] = bool(yesterday_data)

        # Безопасное присвоение структуры продаж
        item["sales"] = sales_map.get(code, default_sales)

    # 6. Сохраняем data.json
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main():
    started = time.time()
    collected = {}
    errors = []

    overall_stats = {
        "categories": 0,
        "pages": 0,
        "cards_seen": 0,
        "relevant": 0,
        "added": 0,
    }
    category_stats = []

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

        try:
            for index, category in enumerate(CATEGORIES, start=1):
                print("\n" + "=" * 72)
                print(f"[{index}/{len(CATEGORIES)}] СБОР: {category['name']}")
                print("=" * 72)

                before_count = len(collected)
                local_stats = {
                    "category": category["name"],
                    "pages": 0,
                    "cards_seen": 0,
                    "relevant": 0,
                    "added": 0,
                    "unique_after": 0,
                }

                try:
                    collect_category(
                        page,
                        category,
                        collected,
                        local_stats,
                        errors,
                    )
                except Exception as exc:
                    print(f"  КРИТИЧЕСКАЯ ОШИБКА СРЕЗА: {exc}")
                    errors.append({
                        "category": category["name"],
                        "error": repr(exc),
                    })

                local_stats["unique_after"] = len(collected)
                local_stats["unique_added"] = len(collected) - before_count
                category_stats.append(local_stats)

                for key in ("pages", "cards_seen", "relevant", "added"):
                    overall_stats[key] += local_stats[key]

                overall_stats["categories"] += 1
                print(f"\n  Итог среза: +{local_stats['unique_added']} SKU | Всего в базе: {len(collected)}")

        finally:
            browser.close()

    items = list(collected.values())
    type_stats = {}
    brand_stats = {}

    for item in items:
        pt = item.get("product_type", "Other")
        br = item.get("brand", "Другой")
        type_stats[pt] = type_stats.get(pt, 0) + 1
        brand_stats[br] = brand_stats.get(br, 0) + 1

    elapsed = time.time() - started

    payload = {
        "last_updated": datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC"),
        "parser_version": "3.6-history-fixed",
        "elapsed_seconds": round(elapsed, 1),
        "total_items": len(items),
        "statistics": {
            **overall_stats,
            "by_product_type": dict(sorted(type_stats.items(), key=lambda x: (-x[1], x[0]))),
            "by_brand": dict(sorted(brand_stats.items(), key=lambda x: (-x[1], x[0]))),
        },
        "category_statistics": category_stats,
        "errors": errors,
        "items": items,
    }

    # Вызов сохранения истории и обогащения дельтами
    save_with_history(payload)

    with open("errors.json", "w", encoding="utf-8") as f:
        json.dump(
            {"last_updated": payload["last_updated"], "errors": errors},
            f,
            ensure_ascii=False,
            indent=2,
        )

    print("\n" + "=" * 72)
    print("СБОР УСПЕШНО ЗАВЕРШЕН")
    print("=" * 72)
    print(f"Всего уникальных SKU: {len(items)}")
    print(f"Обработано страниц: {overall_stats['pages']}")
    print(f"Время выполнения: {elapsed / 60:.1f} мин.")
    print("Файлы data.json, errors.json и история обновлены.")


if __name__ == "__main__":
    main()

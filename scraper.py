import json
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

ROWS_PER_PAGE = 48
MAX_PAGES_SAFETY = 1000
NAVIGATION_TIMEOUT = 45000
PRODUCT_WAIT_TIMEOUT = 12000

# Сколько циклов скролла максимум делаем на странице.
# Значительно меньше старого фиксированного "6 x 1000 px":
# скроллим адаптивно и останавливаемся, когда количество карточек
# перестало расти.
MAX_SCROLL_ROUNDS = 18
SCROLL_STEP = 1400
SCROLL_WAIT_MS = 180
STABLE_ROUNDS_REQUIRED = 3

# Повторная попытка перехода на страницу при сетевых/временных ошибках.
NAVIGATION_RETRIES = 3

# ВАЖНО:
# max_pages из старого кода удален как рабочее ограничение.
# Парсер идет по страницам до фактического окончания каталога.
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


# Бренды, которые умеем распознавать.
# Если бренд встречается в каталоге, но отдельного среза выше нет,
# он НЕ будет автоматически найден: URL среза все равно нужен.
TARGET_BRANDS = [
    {"name": "КЭАЗ", "patterns": [r"\bкэаз\b", r"\bkeaz\b", r"optilogic"]},
    {"name": "Rievtech", "patterns": [r"rievtech", r"\bpr-[12][0-9]\b", r"\bsr-[12][0-9]\b", r"\bba-[0-9]"]},
    {"name": "ОВЕН", "patterns": [r"\bовен\b", r"\bowen\b", r"\bпр10[023]\b", r"\bпр20[05]\b", r"\bплк[12]10\b", r"\bплк200\b", r"\bм[вук][12]10\b"]},
    {"name": "ONI", "patterns": [r"\boni\b", r"plc-410", r"plrs-", r"plrk-"]},
    {"name": "EKF", "patterns": [r"\bekf\b", r"про-реле", r"pro-relay", r"pro-logic"]},
    {"name": "Systeme Electric", "patterns": [r"systeme electric", r"систэм электрик", r"\bsysteme\b", r"\bsm3[a-z0-9]", r"\bzr1"]},
    {"name": "DKC", "patterns": [r"\bdkc\b", r"\bдкс\b", r"\bc1000\b"]},
    {"name": "Segnetics", "patterns": [r"segnetics", r"сегнетикс", r"pixel", r"smh", r"matrix"]},
    {"name": "ЕвроАвтоматика", "patterns": [r"евроавтоматика", r"\bf&f\b", r"\bfif\b"]},
    {"name": "Schneider Electric", "patterns": [r"schneider electric", r"\bschneider\b", r"zelio", r"modicon"]},
    {"name": "Siemens", "patterns": [r"siemens", r"logo!", r"s7-1200", r"s7-1500", r"simatic"]},
    {"name": "Autonics", "patterns": [r"autonics", r"\btc[34][a-z]", r"\btk4[a-z]"]},
    {"name": "Finder", "patterns": [r"\bfinder\b", r"optan"]},
]


STOP_WORDS = [
    "диод", "тиристор", "симистор", "igbt", "конденсатор",
    "варистор", "резистор", "транзистор", "электролитический",
    "косинусный", "предохранитель",
]


# Более точные признаки типа товара.
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
    """Надежно добавляет rows/delivery/page независимо от наличия ? в URL."""
    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))

    query["rows"] = str(ROWS_PER_PAGE)
    query["delivery"] = "all"

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


def identify_brand(text, vendor_code, fallback_brand=""):
    """
    Сначала используем fallback для брендового среза, если в карточке
    нет явного противоречащего бренда. Это снижает ошибки, когда название
    содержит серию/протокол другого производителя.
    """
    combined = normalize_text(f"{text} {vendor_code}").lower()

    for b in TARGET_BRANDS:
        for pattern in b["patterns"]:
            if re.search(pattern, combined, re.IGNORECASE):
                return b["name"]

    return fallback_brand or "Другой"


def classify_product(name, full_text=""):
    """
    Классификация выполняется ПОСЛЕ сбора, а не во время поиска карточек.
    Это позволяет не потерять потенциально интересные позиции.
    """
    text = normalize_text(f"{name} {full_text}").lower()

    if any(sw in text for sw in STOP_WORDS):
        return "Excluded"

    # Приоритет более специфичных типов.
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

    # "модуль" или "контроллер" сохраняем как потенциально интересный,
    # но не притворяемся, что точно знаем его тип.
    if "модуль" in text:
        return "Other module"

    if "контроллер" in text:
        return "Other controller"

    return "Other"


def is_candidate_name(name):
    """
    Только легкий фильтр мусора на этапе сбора.
    Основная классификация выполняется позднее.
    """
    text = normalize_text(name).lower()

    if not text:
        return False

    if any(sw in text for sw in STOP_WORDS):
        return False

    candidate_terms = (
        "плк", "plc", "контроллер", "модуль", "реле",
        "программируем", "панель оператора", "hmi",
        "блок питания", "источник питания", "programmable",
        "logic", "zelio", "logo!", "simatic", "modicon",
    )

    return any(term in text for term in candidate_terms)


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
    Не предполагаем, что первая/вторая цифра перед 'шт' всегда означает
    конкретный склад. Сохраняем все найденные значения и первые два —
    для совместимости со старым JSON.
    """
    matches = [
        int(x.replace(" ", ""))
        for x in re.findall(r"(\d[\d\s]*)\s*шт\b", text, re.IGNORECASE)
    ]

    stock_etm = matches[0] if matches else 0
    stock_vendor = matches[1] if len(matches) > 1 else 0

    return stock_etm, stock_vendor, matches


def parse_vendor_code(lines):
    for i, line in enumerate(lines):
        if "Артикул:" in line:
            after = line.split("Артикул:", 1)[1].strip()

            if after:
                clean = re.split(
                    r"(?:\s{2,}|Упаковка|Код товара|В корзину|₽|руб\.?)",
                    after,
                    maxsplit=1,
                )[0].strip()

                if clean and len(clean) < 80:
                    return clean

            if i + 1 < len(lines):
                candidate = lines[i + 1].strip()

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

    # Ищем наиболее "похожую на название" строку.
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
    """
    КЛЮЧЕВАЯ оптимизация:
    вместо Playwright DOM API для каждой карточки выполняем один JS
    page.evaluate(). Это резко сокращает Python <-> browser round trips.
    """
    cards = page.evaluate(
        """
        ({defaultBrand}) => {
            const links = Array.from(
                document.querySelectorAll("a[href*='/cat/nn/']")
            );

            const result = [];
            const seen = new Set();

            function normalize(s) {
                return (s || "")
                    .replace(/\\u00a0/g, " ")
                    .replace(/\\s+/g, " ")
                    .trim();
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


def merge_item(existing, new_item):
    """
    При повторной встрече позиции обновляем не только цену, но и
    заполненные поля. Сохраняем лучший вариант по полноте.
    """
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


def card_to_item(card, category):
    etm_code = card["etm_code"]
    name = normalize_text(card.get("name", ""))

    # Если текст ссылки короткий, используем текст всей карточки.
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


def scroll_until_stable(page):
    """
    Адаптивный скролл.

    Старый код всегда делал фиксированные 6 скроллов.
    Здесь заканчиваем раньше, если число уникальных товарных ссылок
    перестало увеличиваться.
    """
    previous_count = 0
    stable_rounds = 0
    max_seen = 0

    for _ in range(MAX_SCROLL_ROUNDS):
        count = page.locator("a[href*='/cat/nn/']").count()
        max_seen = max(max_seen, count)

        if count <= previous_count:
            stable_rounds += 1
        else:
            stable_rounds = 0

        if stable_rounds >= STABLE_ROUNDS_REQUIRED:
            break

        previous_count = count

        page.evaluate(
            """
            (step) => {
                window.scrollBy(0, step);
            }
            """,
            SCROLL_STEP,
        )

        page.wait_for_timeout(SCROLL_WAIT_MS)

    # Последний проход до конца страницы.
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(SCROLL_WAIT_MS)

    return max_seen


def navigate_with_retry(page, url):
    last_error = None

    for attempt in range(1, NAVIGATION_RETRIES + 1):
        try:
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=NAVIGATION_TIMEOUT,
            )

            try:
                page.wait_for_selector(
                    "a[href*='/cat/nn/']",
                    timeout=PRODUCT_WAIT_TIMEOUT,
                )
            except PlaywrightTimeoutError:
                # Может быть пустая последняя страница — это не обязательно ошибка.
                pass

            return True

        except Exception as exc:
            last_error = exc
            print(f"  Навигация: попытка {attempt}/{NAVIGATION_RETRIES} неудачна: {exc}")

            if attempt < NAVIGATION_RETRIES:
                time.sleep(1.0 * attempt)

    print(f"  ОШИБКА навигации: {last_error}")
    return False


def page_has_products(page):
    return page.locator("a[href*='/cat/nn/']").count() > 0


def get_pagination_state(page):
    """
    Пытаемся определить состояние пагинации.
    Возвращает:
      - current_page
      - last_page, если удалось определить
      - has_next
    """
    return page.evaluate(
        """
        () => {
            const text = document.body ? document.body.innerText : "";

            let currentPage = null;
            let lastPage = null;

            const active = document.querySelector(
                '[aria-current="page"], .active, .selected'
            );

            if (active) {
                const n = parseInt((active.innerText || "").trim(), 10);
                if (!Number.isNaN(n)) currentPage = n;
            }

            const pageNumbers = Array.from(
                document.querySelectorAll(
                    'a[href*="page="], button, [role="button"]'
                )
            )
            .map(el => {
                const href = el.getAttribute("href") || "";
                const m = href.match(/[?&]page=(\\d+)/);
                if (m) return parseInt(m[1], 10);

                const t = (el.innerText || "").trim();
                return /^\\d+$/.test(t) ? parseInt(t, 10) : null;
            })
            .filter(x => x !== null);

            if (pageNumbers.length) {
                lastPage = Math.max(...pageNumbers);
            }

            const controls = Array.from(
                document.querySelectorAll(
                    'a, button, [role="button"]'
                )
            );

            const next = controls.find(el => {
                const t = (el.innerText || "").trim().toLowerCase();
                const aria = (el.getAttribute("aria-label") || "").toLowerCase();
                return (
                    t === "следующая" ||
                    t === "далее" ||
                    t === "next" ||
                    aria.includes("следующ") ||
                    aria.includes("next")
                );
            });

            const hasNext = !!next && !next.disabled &&
                next.getAttribute("aria-disabled") !== "true";

            return {currentPage, lastPage, hasNext};
        }
        """
    )


def collect_category(page, category, collected, stats, errors):
    page_number = 1
    consecutive_empty = 0
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
            page_number += 1
            continue

        if not page_has_products(page):
            consecutive_empty += 1
            print("  Товарных карточек нет — срез завершен.")

            if consecutive_empty >= 1:
                break

            page_number += 1
            continue

        consecutive_empty = 0

        before = page.locator("a[href*='/cat/nn/']").count()
        scroll_until_stable(page)
        cards = extract_cards_bulk(page, category["brand_hint"])

        # Подпись страницы защищает от ситуации, когда ETM игнорирует
        # параметр page и возвращает ту же самую страницу.
        page_signature = tuple(sorted(
            card["etm_code"] for card in cards
        ))

        if page_number > 1 and page_signature == previous_page_signature:
            print("  ВНИМАНИЕ: страница совпадает с предыдущей. "
                  "Вероятно, ETM игнорирует page — останавливаемся.")
            break

        previous_page_signature = page_signature

        print(
            f"  Карточек после скролла: {len(cards)} "
            f"(до скролла: {before})"
        )

        if not cards:
            print("  Пустая страница — срез завершен.")
            break

        added = 0
        relevant = 0

        for card in cards:
            item = card_to_item(card, category)

            # Легкий фильтр: не теряем данные из-за слишком узкого
            # определения "целевого" товара.
            if not is_candidate_name(item["name"]):
                # Если это не очевидный кандидат, но категория сама
                # является целевой категорией — сохраняем его как Other.
                # Это важнее полноты, чем агрессивная фильтрация.
                if item["product_type"] not in (
                    "PLC",
                    "Programmable relay",
                    "I/O module",
                    "Communication module",
                    "HMI",
                    "Power supply",
                    "Other module",
                    "Other controller",
                ):
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
            f"  Новых позиций: {added} | "
            f"целевых/кандидатов: {relevant} | "
            f"всего уникальных: {len(collected)}"
        )

        pagination = get_pagination_state(page)

        if pagination.get("lastPage"):
            print(
                f"  Пагинация ETM: current={pagination.get('currentPage')} "
                f"last={pagination.get('lastPage')}"
            )

            if page_number >= pagination["lastPage"]:
                print("  Достигнута последняя определяемая страница.")
                break

        # Если на странице меньше ROWS_PER_PAGE карточек, это сильный
        # индикатор последней страницы. Но не единственный критерий:
        # виртуализация может дать меньше карточек.
        if len(cards) < max(6, ROWS_PER_PAGE // 2):
            print("  На странице мало карточек — вероятно, это последняя страница.")
            break

        page_number += 1

    if page_number > MAX_PAGES_SAFETY:
        errors.append({
            "category": category["name"],
            "page": page_number,
            "url": category["url"],
            "error": "safety_page_limit_reached",
        })


def main():
    started = time.time()

    # Все наблюденные позиции. Фильтрация больше не является главным
    # механизмом сбора.
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
                "--disable-dev-shm-usage",
                "--disable-background-networking",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--window-size=1920,1080",
            ],
        )

        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )

        page = context.new_page()

        # Ускоряем загрузку, блокируя тяжелые ресурсы, которые не нужны
        # для чтения карточек. CSS НЕ блокируем.
        def route_handler(route):
            resource_type = route.request.resource_type
            if resource_type in {"image", "media", "font"}:
                route.abort()
            else:
                route.continue_()

        page.route("**/*", route_handler)

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

                print(
                    f"\n  Итог среза: +{local_stats['unique_added']} "
                    f"уникальных позиций; база = {len(collected)}"
                )

        finally:
            browser.close()

    items = list(collected.values())

    # Отдельно сохраняем статистику по типам и брендам.
    type_stats = {}
    brand_stats = {}

    for item in items:
        pt = item.get("product_type", "Other")
        br = item.get("brand", "Другой")

        type_stats[pt] = type_stats.get(pt, 0) + 1
        brand_stats[br] = brand_stats.get(br, 0) + 1

    elapsed = time.time() - started

    payload = {
        "last_updated": datetime.now(timezone.utc).strftime(
            "%d.%m.%Y %H:%M UTC"
        ),
        "parser_version": "3.0-fast",
        "elapsed_seconds": round(elapsed, 1),
        "settings": {
            "rows_per_page": ROWS_PER_PAGE,
            "max_pages_safety": MAX_PAGES_SAFETY,
            "adaptive_scroll": True,
            "bulk_js_extraction": True,
            "filter_during_collection": "light",
        },
        "total_items": len(items),
        "statistics": {
            **overall_stats,
            "by_product_type": dict(
                sorted(type_stats.items(), key=lambda x: (-x[1], x[0]))
            ),
            "by_brand": dict(
                sorted(brand_stats.items(), key=lambda x: (-x[1], x[0]))
            ),
        },
        "category_statistics": category_stats,
        "errors": errors,
        "items": items,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Отдельный простой файл ошибок — удобно проверять после большого запуска.
    with open("errors.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "last_updated": payload["last_updated"],
                "errors": errors,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print("\n" + "=" * 72)
    print("СБОР ЗАВЕРШЕН")
    print("=" * 72)
    print(f"Уникальных позиций: {len(items)}")
    print(f"Страниц обработано: {overall_stats['pages']}")
    print(f"Карточек просмотрено: {overall_stats['cards_seen']}")
    print(f"Время работы: {elapsed / 60:.1f} мин.")
    print(f"Ошибок: {len(errors)}")
    print("Файлы: data.json, errors.json")


if __name__ == "__main__":
    main()

from datetime import datetime, timezone
import json
import re
import time
from playwright.sync_api import sync_playwright

# Целевые категории ПЛК и программируемых реле
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

# Целевой пул производителей
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
    ]


def identify_brand(text, vendor_code):
    """Точное определение производителя по тексту карточки и артикулу."""
    combined = f"{text} {vendor_code}".lower()
    for b in TARGET_BRANDS:
        for alias in b["aliases"]:
            # Ищем alias как отдельное слово или подстроку
            if re.search(r"(?<![a-zA-Zа-яА-Я0-9])" + re.escape(alias) + r"(?![a-zA-Zа-яА-Я0-9])", combined) or alias in combined:
                return b["name"]
    return "Другой"


def extract_page_cards(page, category_name):
    """Сбор карточек товаров со страницы каталога."""
    js_code = """
    () => {
        const results = [];
        const links = Array.from(document.querySelectorAll('a[href*="/cat/nn/"]'));
        const seenCodes = new Set();

        for (const a of links) {
            const href = a.getAttribute('href') || '';
            const match = href.match(/\\/cat\\/nn\\/(\\d+)/);
            if (!match) continue;

            const etm_code = match[1];
            if (seenCodes.has(etm_code)) continue;

            let card = a;
            let foundCard = null;
            for (let i = 0; i < 8; i++) {
                if (!card || card.tagName === 'BODY' || card.tagName === 'MAIN') break;
                if (card.innerText && card.innerText.includes('Код товара:')) {
                    foundCard = card;
                    break;
                }
                card = card.parentElement;
            }

            if (!foundCard) continue;
            seenCodes.add(etm_code);

            const text = foundCard.innerText.replace(/\\u00a0/g, ' ');
            const lines = text.split('\\n').map(s => s.trim()).filter(Boolean);

            // 1. Наименование
            let name = a.innerText.trim().replace(/\\u00a0/g, ' ');
            if (name.length < 15) {
                for (const l of lines) {
                    if (l.length > 25 && !l.includes('Код товара') && !l.includes('В корзину') && !l.includes('Артикул')) {
                        name = l;
                        break;
                    }
                }
            }

            // 2. Артикул
            let vendor_code = '—';
            for (let i = 0; i < lines.length; i++) {
                if (lines[i].includes('Артикул:')) {
                    const parts = lines[i].split('Артикул:');
                    if (parts[1] && parts[1].trim()) {
                        vendor_code = parts[1].trim();
                    } else if (lines[i+1]) {
                        vendor_code = lines[i+1].trim();
                    }
                    break;
                }
            }

            // 3. Цена
            let price = 0;
            const priceRegex = /([0-9][0-9\\s]{0,10}(?:[.,][0-9]{2})?)\\s*(?:₽|руб)/i;
            const priceMatch = text.match(priceRegex);
            if (priceMatch) {
                const cleanPrice = priceMatch[1].replace(/\\s+/g, '').replace(',', '.');
                price = parseFloat(cleanPrice) || 0;
            }

            // 4. Остатки
            let stock_etm = 0;
            let stock_vendor = 0;
            const stockMatches = Array.from(text.matchAll(/(\\d+)\\s*шт/g));
            if (stockMatches.length > 0) {
                stock_etm = parseInt(stockMatches[0][1], 10) || 0;
                if (stockMatches.length > 1) {
                    stock_vendor = parseInt(stockMatches[1][1], 10) || 0;
                }
            }

            results.push({
                etm_code: etm_code,
                vendor_code: vendor_code,
                name: name,
                price: price,
                stock_etm: stock_etm,
                stock_vendor: stock_vendor,
                full_text: text,
                url: 'https://www.etm.ru/cat/nn/' + etm_code
            });
        }

        return results;
    }
    """
    raw_cards = page.evaluate(js_code)

    processed = []
    for c in raw_cards:
        brand = identify_brand(c["name"] + " " + c["full_text"], c["vendor_code"])
        processed.append({
            "category": category_name,
            "etm_code": c["etm_code"],
            "brand": brand,
            "vendor_code": c["vendor_code"],
            "name": c["name"],
            "price": c["price"],
            "stock_etm": c["stock_etm"],
            "stock_vendor": c["stock_vendor"],
            "url": c["url"],
        })
    return processed


def switch_to_page(page, base_url, target_page_num):
    """Переход на следующую страницу каталога."""
    url = f"{base_url}?page={target_page_num}"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3500)
        return True
    except Exception as e:
        print(f"Ошибка перехода на страницу {target_page_num}: {e}")
        return False


def main():
    collected_dict = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled", "--window-size=1920,1080"],
        )

        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )
        page = context.new_page()

        for cat in CATEGORIES:
            print(f"\n==========================================")
            print(f"Категория: {cat['name']}")
            print(f"==========================================")

            max_p = cat.get("max_pages", 15)

            for p_num in range(1, max_p + 1):
                print(f"Загрузка страницы {p_num} из {max_p}...")

                if p_num == 1:
                    try:
                        page.goto(cat["url"], wait_until="domcontentloaded", timeout=50000)
                        page.wait_for_timeout(3000)
                    except Exception as e:
                        print(f"Ошибка загрузки {cat['url']}: {e}")
                        break
                else:
                    if not switch_to_page(page, cat["url"], p_num):
                        break

                # Плавная прокрутка для срабатывания ленивой загрузки
                for pos in [600, 1500, 2400, 3200]:
                    page.evaluate(f"window.scrollTo(0, {pos})")
                    page.wait_for_timeout(250)

                items = extract_page_cards(page, cat["name"])
                new_added = 0
                for it in items:
                    code = it["etm_code"]
                    if code not in collected_dict:
                        collected_dict[code] = it
                        new_added += 1
                    else:
                        if collected_dict[code]["price"] == 0 and it["price"] > 0:
                            collected_dict[code]["price"] = it["price"]

                print(f"Стр. {p_num}: получено {len(items)}, новых: {new_added} | Всего в базе: {len(collected_dict)}")

                if len(items) == 0:
                    print(f"На странице {p_num} нет товаров. Раздел завершен.")
                    break

        browser.close()

    final_list = list(collected_dict.values())
    print(f"\nСбор завершен! Всего уникальных позиций в базе: {len(final_list)}")

    payload = {
        "last_updated": datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC"),
        "total_items": len(final_list),
        "items": final_list,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("Файл data.json успешно сохранен.")


if __name__ == "__main__":
    main()

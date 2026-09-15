import os
import sys

# Принудительно задаем кодировку UTF-8 для вывода в консоль
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

def identify_brand(text, vendor_code):
    combined = f"{text} {vendor_code}".lower()
    for b in TARGET_BRANDS:
        for alias in b["aliases"]:
            if re.search(r'(?<![a-zA-Zа-яА-Я0-9])' + re.escape(alias) + r'(?![a-zA-Zа-яА-Я0-9])', combined) or alias in combined:
                return b["name"]
    return "Другой"

def extract_page_cards(page, category_name):
    """Извлечение карточек товаров со страницы каталога."""
    js_code = """
    () => {
        const results = [];
        
        // Находим все ссылки с кодом /cat/nn/
        const links = Array.from(document.querySelectorAll('a[href*="/cat/nn/"]'));
        const seenCodes = new Set();

        for (const a of links) {
            const href = a.getAttribute('href') || '';
            const match = href.match(/\\/cat\\/nn\\/(\\d+)/);
            if (!match) continue;

            const etm_code = match[1];
            if (seenCodes.has(etm_code)) continue;

            // Находим родительскую карточку конкретного товара:
            // Ищем контейнер, где есть этот etm_code или кнопка "В корзину", но не выходим за пределы карточки
            let card = a;
            for (let i = 0; i < 6; i++) {
                if (!card.parentElement || card.parentElement.tagName === 'BODY' || card.parentElement.tagName === 'MAIN') break;
                card = card.parentElement;
                if (card.innerText && card.innerText.includes('В корзину')) {
                    break;
                }
            }

            seenCodes.add(etm_code);

            const text = (card.innerText || '').replace(/\\u00a0/g, ' ');
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
            "url": c["url"]
        })
    return processed

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
                url = f"{cat['url']}?page={p_num}" if p_num > 1 else cat["url"]
                print(f"Загрузка страницы {p_num} из {max_p}: {url}")

                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    
                    # КРИТИЧЕСКИ ВАЖНО: ждем реального появления карточек товаров
                    try:
                        page.wait_for_selector("a[href*='/cat/nn/']", timeout=20000)
                    except Exception:
                        print("Товары не успели отрисоваться по селектору")

                    # Плавный скролл страницы вниз для lazy-load
                    page.evaluate("window.scrollTo(0, 1000)")
                    page.wait_for_timeout(500)
                    page.evaluate("window.scrollTo(0, 2500)")
                    page.wait_for_timeout(500)
                    page.evaluate("window.scrollTo(0, 3800)")
                    page.wait_for_timeout(800)

                except Exception as e:
                    print(f"Ошибка загрузки страницы {p_num}: {e}")
                    break

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

                print(f"Стр. {p_num}: найдено на странице {len(items)}, новых: {new_added} | Всего в базе: {len(collected_dict)}")

                if len(items) == 0:
                    print(f"На странице {p_num} нет товаров. Раздел завершен.")
                    break

        browser.close()

    final_list = list(collected_dict.values())
    print(f"\n==========================================")
    print(f"Сбор завершен! Всего уникальных позиций: {len(final_list)}")
    print(f"==========================================")

    payload = {
        "last_updated": datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC"),
        "total_items": len(final_list),
        "items": final_list
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("Файл data.json успешно сохранен.")

if __name__ == "__main__":
    main()

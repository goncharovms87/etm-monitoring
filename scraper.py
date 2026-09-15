import json
import re
import time
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

CATEGORIES = [
    {
        "id": "75102510",
        "name": "Программируемые реле",
        "url": "https://www.etm.ru/catalog/75102510_programmiruemye_rele",
    },
    {
        "id": "751025",
        "name": "Модули расширения и ПЛК",
        "url": "https://www.etm.ru/catalog/751025_programmiruemye_rele_moduli_rasshirenija",
    },
]


def extract_page_cards(page, category_name):
    """
    Выполняем JS прямо в браузере: находим все карточки каталога строго изолированно,
    не затрагивая сайдбар с фильтрами брендов.
    """
    js_code = """
    () => {
        const results = [];
        // Находим все ссылки на карточки товаров, исключая меню и футер
        const links = Array.from(document.querySelectorAll('a[href*="/cat/nn/"]'));
        
        const seenCodes = new Set();

        for (const a of links) {
            const href = a.getAttribute('href') || '';
            const match = href.match(/\\/cat\\/nn\\/(\\d+)/);
            if (!match) continue;
            
            const etm_code = match[1];
            if (seenCodes.has(etm_code)) continue;

            // Ищем контейнер именно отдельной карточки товара:
            // поднимаемся до ближайшего элемента, у которого есть кнопка 'В корзину'
            // или где выводится 'Код товара'
            let card = a;
            let foundCard = null;
            for (let i = 0; i < 7; i++) {
                if (!card || card.tagName === 'BODY' || card.tagName === 'MAIN') break;
                if (card.innerText && card.innerText.includes('Код товара:')) {
                    foundCard = card;
                    break;
                }
                card = card.parentElement;
            }

            if (!foundCard) continue;
            seenCodes.add(etm_code);

            const text = foundCard.innerText;
            const lines = text.split('\\n').map(s => s.trim()).filter(Boolean);

            // 1. Наименование
            // Ищем самую длинную строку описания либо берем текст ссылки
            let name = a.innerText.trim();
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
                    const p = lines[i].split('Артикул:');
                    if (p[1] && p[1].trim()) {
                        vendor_code = p[1].trim();
                    } else if (lines[i+1]) {
                        vendor_code = lines[i+1].trim();
                    }
                    break;
                }
            }

            // 3. Производитель (бренд)
            // В карточке ЭТМ бренд пишется синей отдельной строкой прямо над артикулом или под ним
            let brand = '—';
            for (let i = 0; i < lines.length; i++) {
                if (lines[i].includes('Артикул:') || lines[i].includes('Код товара:')) {
                    // Бренд часто идет за 1 строчку ДО или ПОСЛЕ артикула
                    const candidate = lines[i+1] || '';
                    if (candidate && candidate.length < 30 && !candidate.includes('Упаковка') && !candidate.includes('₽') && !candidate.includes('шт')) {
                        brand = candidate;
                    }
                }
            }

            // Если не выделился бренд, определяем по сигнатуре названия
            const known = ['ОВЕН', 'INNOCONT', 'ONI', 'Segnetics', 'КЭАЗ', 'Autonics', 'Finder', 'Schneider Electric', 'Schneider', 'ABB', 'Siemens', 'Chint', 'IEK', 'DKC', 'WAGO', 'Rievtech', 'DEKraft', 'Relpol', 'MeyerTec'];
            for (const b of known) {
                if (name.toLowerCase().includes(b.toLowerCase()) || text.toLowerCase().includes(b.toLowerCase())) {
                    // Но не путать с другими
                    brand = b;
                    break;
                }
            }

            // 4. Цена
            let price = 0;
            const priceMatch = text.match(/([\\d\\s]+(?:[.,]\\d{2})?)\\s*₽/);
            if (priceMatch) {
                const numStr = priceMatch[1].replace(/\\s+/g, '').replace(',', '.');
                price = parseFloat(numStr) || 0;
            }

            // 5. Остатки (числа перед "шт.")
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
                brand: brand,
                vendor_code: vendor_code,
                name: name,
                price: price,
                stock_etm: stock_etm,
                stock_vendor: stock_vendor,
                url: 'https://www.etm.ru/cat/nn/' + etm_code
            });
        }

        return results;
    }
    """
    return page.evaluate(js_code)


def main():
    collected_dict = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",  # используем системный Chrome/Edge
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

        for cat in CATEGORIES:
            print(f"\n==========================================")
            print(f"Категория: {cat['name']}")
            print(f"==========================================")

            # Обходим первые 5 страниц в каждой категории
            for p_num in range(1, 6):
                page_url = (
                    f"{cat['url']}?page={p_num}" if p_num > 1 else cat["url"]
                )
                print(f"Загрузка страницы {p_num}: {page_url}")

                try:
                    page.goto(
                        page_url,
                        wait_until="domcontentloaded",
                        timeout=50000,
                    )

                    # Ждем появления карточек с товарами
                    page.wait_for_selector(
                        "text=Код товара:", timeout=25000
                    )

                    # Динамическая прокрутка, чтобы прогрузить все 24 карточки на странице
                    for s in [500, 1200, 2000, 3000]:
                        page.evaluate(f"window.scrollTo(0, {s})")
                        page.wait_for_timeout(400)

                    # Извлекаем все карточки изолированно
                    items = extract_page_cards(page, cat["name"])
                    print(f"Найдено товаров на странице {p_num}: {len(items)}")

                    if not items:
                        break

                    for item in items:
                        item["category"] = cat["name"]
                        collected_dict[item["etm_code"]] = item

                    print(f"Всего накоплено в базе: {len(collected_dict)}")

                except Exception as e:
                    print(f"Ошибка при обработке страницы {p_num}: {e}")
                    continue

        browser.close()

    final_items = list(collected_dict.values())
    print(f"\nСбор завершен! Всего уникальных позиций в базе: {len(final_items)}")

    payload = {
        "last_updated": datetime.now(timezone.utc).strftime(
            "%d.%m.%Y %H:%M UTC"
        ),
        "total_items": len(final_items),
        "items": final_items,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("Файл data.json успешно сохранен.")


if __name__ == "__main__":
    main()

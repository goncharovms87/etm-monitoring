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
        "max_pages": 15,
    },
    {
        "id": "751025",
        "name": "Модули расширения и ПЛК",
        "url": "https://www.etm.ru/catalog/751025_programmiruemye_rele_moduli_rasshirenija",
        "max_pages": 12,
    },
]


def extract_page_cards(page, category_name):
    """Извлечение данных карточек товаров на текущей странице."""
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

            // Поднимаемся к карточке
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

            // 3. Производитель (бренд)
            let brand = '—';
            for (let i = 0; i < lines.length; i++) {
                if (lines[i].includes('Артикул:') || lines[i].includes('Код товара:')) {
                    const candidate = lines[i+1] || '';
                    if (candidate && candidate.length < 30 && !candidate.includes('Упаковка') && !candidate.includes('₽') && !candidate.includes('шт')) {
                        brand = candidate;
                    }
                }
            }

            const known = ['ОВЕН', 'INNOCONT', 'ONI', 'Segnetics', 'КЭАЗ', 'Autonics', 'Finder', 'Schneider Electric', 'Schneider', 'ABB', 'Siemens', 'Chint', 'IEK', 'DKC', 'WAGO', 'Rievtech', 'DEKraft', 'Relpol', 'MeyerTec'];
            for (const b of known) {
                if (text.toLowerCase().includes(b.toLowerCase()) || name.toLowerCase().includes(b.toLowerCase())) {
                    brand = b;
                    break;
                }
            }

            // 4. Цена
            let price = 0;
            const priceRegex = /([0-9][0-9\\s]{0,10}(?:[.,][0-9]{2})?)\\s*(?:₽|руб)/i;
            const priceMatch = text.match(priceRegex);
            if (priceMatch) {
                const cleanPrice = priceMatch[1].replace(/\\s+/g, '').replace(',', '.');
                price = parseFloat(cleanPrice) || 0;
            }

            // 5. Остатки
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


def switch_page(page, base_url, target_page_num):
    """
    Надежное переключение страницы: сначала прямой переход по URL,
    если данные не изменились — клик по элементу пагинации.
    """
    url_with_page = f"{base_url}?page={target_page_num}"
    try:
        page.goto(url_with_page, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000)
        return True
    except Exception as e:
        print(f"Ошибка перехода по URL на страницу {target_page_num}: {e}")

    # Запасной вариант: поиск стрелки вправо на текущей странице
    try:
        next_clicked = page.evaluate(
            f"""
            () => {{
                // Ищем кнопку с номером {target_page_num}
                const els = Array.from(document.querySelectorAll('button, a, div[role="button"]'));
                for (const el of els) {{
                    if (el.innerText && el.innerText.trim() === '{target_page_num}') {{
                        el.click();
                        return true;
                    }}
                }}
                // Ищем стрелку '>'
                for (const el of els) {{
                    if (el.innerText && (el.innerText.trim() === '>' || el.innerText.trim() === 'Вперед')) {{
                        el.click();
                        return true;
                    }}
                }}
                return false;
            }}
        """
        )
        if next_clicked:
            page.wait_for_timeout(3500)
            return True
    except Exception:
        pass

    return False


def main():
    collected_dict = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",  # если нет Chrome, укажите "msedge"
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

            max_p = cat.get("max_pages", 10)

            for p_num in range(1, max_p + 1):
                print(f"Загрузка страницы {p_num} из {max_p}...")

                if p_num == 1:
                    try:
                        page.goto(
                            cat["url"],
                            wait_until="domcontentloaded",
                            timeout=50000,
                        )
                        page.wait_for_timeout(3000)
                    except Exception as e:
                        print(f"Ошибка загрузки категории {cat['url']}: {e}")
                        break
                else:
                    success = switch_page(page, cat["url"], p_num)
                    if not success:
                        print(
                            f"Не удалось переключиться на страницу {p_num}. Переход к следующей категории."
                        )
                        break

                # Прокрутка страницы вниз, чтобы прогрузились все плитки
                for pos in [600, 1500, 2400, 3200]:
                    page.evaluate(f"window.scrollTo(0, {pos})")
                    page.wait_for_timeout(300)

                items = extract_page_cards(page, cat["name"])
                new_added = 0
                for it in items:
                    it["category"] = cat["name"]
                    code = it["etm_code"]
                    if code not in collected_dict:
                        collected_dict[code] = it
                        new_added += 1
                    else:
                        if (
                            collected_dict[code]["price"] == 0
                            and it["price"] > 0
                        ):
                            collected_dict[code]["price"] = it["price"]

                print(
                    f"Стр. {p_num}: найдено {len(items)}, новых {new_added} | Всего в базе: {len(collected_dict)}"
                )

                # Если на странице вообще нет товаров — каталог кончился
                if len(items) == 0:
                    print(
                        f"На странице {p_num} нет товаров. Категория завершена."
                    )
                    break

        browser.close()

    final_list = list(collected_dict.values())
    print(
        f"\n=================================================================="
    )
    print(f"Сбор завершен! Всего уникальных позиций в базе: {len(final_list)}")
    print(
        f"=================================================================="
    )

    payload = {
        "last_updated": datetime.now(timezone.utc).strftime(
            "%d.%m.%Y %H:%M UTC"
        ),
        "total_items": len(final_list),
        "items": final_list,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("Файл data.json успешно сохранен.")


if __name__ == "__main__":
    main()

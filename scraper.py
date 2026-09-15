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
        "max_pages": 14,  # на сайте 14 страниц
    },
    {
        "id": "751025",
        "name": "Модули расширения и ПЛК",
        "url": "https://www.etm.ru/catalog/751025_programmiruemye_rele_moduli_rasshirenija",
        "max_pages": 10,
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

            // Ищем контейнер плитки товара
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

            // Очищаем текст от неразрывных пробелов
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

            // 4. Цена (парсим с учетом ₽/шт, ₽/компл, руб)
            let price = 0;
            // Ищем шаблон цены вида "17 446.00 ₽" или "2 960.01 ₽"
            const priceRegex = /([0-9][0-9\\s]{0,10}(?:[.,][0-9]{2})?)\\s*(?:₽|руб)/i;
            const priceMatch = text.match(priceRegex);
            if (priceMatch) {
                const cleanPrice = priceMatch[1].replace(/\\s+/g, '').replace(',', '.');
                price = parseFloat(cleanPrice) || 0;
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


def go_next_page(page, current_page_num):
    """
    Листание пагинатора: ищет кнопку со следующим номером или стрелку 'Вперед' (>) и кликает.
    """
    next_page_str = str(current_page_num + 1)

    # 1. Пробуем кликнуть по конкретной цифре следующей страницы в пагинаторе
    clicked = page.evaluate(
        f"""
        () => {{
            const buttons = Array.from(document.querySelectorAll('button, a, div'));
            for (const b of buttons) {{
                // Ищем элемент пагинатора со следующим номером
                if (b.innerText && b.innerText.trim() === '{next_page_str}' && b.offsetWidth > 0 && b.offsetHeight > 0) {{
                    b.click();
                    return true;
                }}
            }}
            return false;
        }}
    """
    )

    if clicked:
        return True

    # 2. Если кнопки с номером нет (скрыта за троеточием), ищем стрелку 'Вперед' / '>'
    clicked_arrow = page.evaluate(
        """
        () => {
            const arrows = Array.from(document.querySelectorAll('button, a, svg, span'));
            for (const el of arrows) {
                const t = (el.getAttribute('aria-label') || el.innerText || '').trim();
                if ((t === 'Вперед' || t === '>' || el.classList.contains('pagination-next')) && el.offsetWidth > 0) {
                    el.click();
                    return true;
                }
            }
            return false;
        }
    """
    )
    return clicked_arrow


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

            try:
                page.goto(
                    cat["url"], wait_until="domcontentloaded", timeout=50000
                )
                page.wait_for_selector("text=Код товара:", timeout=25000)
            except Exception as e:
                print(f"Ошибка начальной загрузки {cat['url']}: {e}")
                continue

            current_page = 1
            max_p = cat.get("max_pages", 5)

            while current_page <= max_p:
                print(f"Парсинг страницы {current_page} из {max_p}...")

                # Прокручиваем страницу вниз для подгрузки цен и остатков
                for pos in [600, 1500, 2400, 3200]:
                    page.evaluate(f"window.scrollTo(0, {pos})")
                    page.wait_for_timeout(350)

                items = extract_page_cards(page, cat["name"])
                added_now = 0
                for it in items:
                    it["category"] = cat["name"]
                    if it["etm_code"] not in collected_dict:
                        collected_dict[it["etm_code"]] = it
                        added_now += 1
                    else:
                        # Обновляем цену, если раньше была 0
                        if (
                            collected_dict[it["etm_code"]]["price"] == 0
                            and it["price"] > 0
                        ):
                            collected_dict[it["etm_code"]]["price"] = it[
                                "price"
                            ]

                print(
                    f"На странице {current_page} найдено товаров: {len(items)}, новых: {added_now} | Всего в базе: {len(collected_dict)}"
                )

                if current_page >= max_p:
                    break

                # Переходим на следующую страницу через клик по пагинатору
                has_next = go_next_page(page, current_page)
                if not has_next:
                    print(
                        f"Кнопка перехода со страницы {current_page} не найдена. Завершение категории."
                    )
                    break

                current_page += 1
                page.wait_for_timeout(3500)  # Даем SPA время обновить карточки

        browser.close()

    final_list = list(collected_dict.values())
    print(f"\nСбор завершен! Всего уникальных позиций в базе: {len(final_list)}")

    payload = {
        "last_updated": datetime.now(timezone.utc).strftime(
            "%d.%m.%Y %H:%M UTC"
        ),
        "total_items": len(final_list),
        "items": final_list,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("Файл data.json успешно записан.")


if __name__ == "__main__":
    main()

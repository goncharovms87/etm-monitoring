import json
import os
import sys

# Принудительная поддержка UTF-8 в консоли Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HISTORY_DIR = "history"

# 1. Загружаем все исторические снимки по порядку дат
history_files = sorted([f for f in os.listdir(HISTORY_DIR) if f.endswith(".json")])
snapshots = []

for filename in history_files:
    filepath = os.path.join(HISTORY_DIR, filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Очистка классических артефактов "срока поставки в днях"
            for code, item in data.items():
                v = item.get("stock_vendor", 0)
                if v >= 26000:
                    item["stock_vendor"] = v - 26000
                elif v >= 2600:
                    item["stock_vendor"] = v - 2600
                elif v == 260:
                    item["stock_vendor"] = 0
            snapshots.append((filename.replace(".json", ""), data))
    except Exception as e:
        print(f"Ошибка чтения {filename}: {e}")

print(f"Загружено снимков: {len(snapshots)}")

# 2. Исправление аномалий и провалов внутри истории
num_snaps = len(snapshots)

# А) Одиночные провалы в 0 внутри истории (было X -> стало 0 -> стало X)
if num_snaps >= 3:
    for i in range(1, num_snaps - 1):
        prev_data = snapshots[i - 1][1]
        cur_data = snapshots[i][1]
        next_data = snapshots[i + 1][1]

        for code, c_item in cur_data.items():
            prev_item = prev_data.get(code)
            next_item = next_data.get(code)
            if not prev_item or not next_item:
                continue

            p_v = prev_item.get("stock_vendor", 0)
            c_v = c_item.get("stock_vendor", 0)
            n_v = next_item.get("stock_vendor", 0)
            if c_v == 0 and p_v > 0 and n_v > 0:
                print(f"Исправлен провал вендора {code} в {snapshots[i][0]}: 0 -> {p_v}")
                c_item["stock_vendor"] = p_v

            p_e = prev_item.get("stock_etm", 0)
            c_e = c_item.get("stock_etm", 0)
            n_e = next_item.get("stock_etm", 0)
            if c_e == 0 and p_e > 0 and n_e > 0:
                print(f"Исправлен провал ЭТМ {code} в {snapshots[i][0]}: 0 -> {p_e}")
                c_item["stock_etm"] = p_e

# Б) Фильтр аномалий скачка ровно на 100 шт. (например, 100 -> 200 -> 100)
# Если изменение составляет ровно 100 шт., оставляем остаток как в предыдущий день
if num_snaps >= 2:
    for i in range(1, num_snaps):
        prev_data = snapshots[i - 1][1]
        cur_data = snapshots[i][1]

        for code, c_item in cur_data.items():
            prev_item = prev_data.get(code)
            if not prev_item:
                continue

            p_v = prev_item.get("stock_vendor", 0)
            c_v = c_item.get("stock_vendor", 0)

            # Если разница составляет ровно 100 (или кратна 100 при артефакте ЭТМ)
            if p_v > 0 and abs(c_v - p_v) == 100:
                print(f"Сглажена аномалия кратно 100 шт. у {code} в {snapshots[i][0]}: {c_v} -> {p_v}")
                c_item["stock_vendor"] = p_v

# Сохраняем исправленные снимки истории
for name, data in snapshots:
    with open(os.path.join(HISTORY_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

# 3. Пересчитываем продажи в data.json
if os.path.exists("data.json"):
    with open("data.json", "r", encoding="utf-8") as f:
        payload = json.load(f)

    current_items_map = {
        str(item.get("etm_code")): {
            "price": item.get("price", 0.0),
            "stock_vendor": item.get("stock_vendor", 0),
            "stock_etm": item.get("stock_etm", 0),
        }
        for item in payload.get("items", [])
    }

    sales_map = {
        str(item["etm_code"]): {
            "etm_1d": 0, "vendor_1d": 0,
            "etm_7d": 0, "vendor_7d": 0,
            "etm_30d": 0, "vendor_30d": 0,
        }
        for item in payload.get("items", [])
    }

    if num_snaps >= 2:
        for i in range(1, num_snaps):
            prev_snap = snapshots[i - 1][1]
            cur_snap = snapshots[i][1]
            days_from_end = num_snaps - 1 - i

            for code_str, metrics in sales_map.items():
                if code_str not in prev_snap or code_str not in cur_snap:
                    continue

                prev_item = prev_snap[code_str]
                cur_item = cur_snap[code_str]

                prev_etm = prev_item.get("stock_etm", 0)
                cur_etm = cur_item.get("stock_etm", 0)
                prev_v = prev_item.get("stock_vendor", 0)
                cur_v = cur_item.get("stock_vendor", 0)

                item_info = current_items_map.get(code_str, {})
                item_price = cur_item.get("price") or prev_item.get("price") or item_info.get("price", 0.0)

                # Продажи склада ЭТМ
                sold_etm = (prev_etm - cur_etm) if (prev_etm > 0 and cur_etm < prev_etm) else 0

                # Продажи склада вендора
                sold_v = 0
                if prev_v > 0 and cur_v < prev_v:
                    diff_v = prev_v - cur_v

                    # 1. Спад ровно 100 шт. игнорируется
                    if diff_v == 100:
                        sold_v = 0
                    # 2. Дорогостоящее оборудование (> 40 000 руб.) со спадом > 200 шт.
                    elif item_price > 40000 and diff_v > 200:
                        print(f"Отсечена аномалия продаж: {code_str} (Цена {item_price} руб, скачок {diff_v} шт.)")
                        sold_v = 0
                    # 3. Выпадение карточки в 0 при повторном появлении партии
                    elif cur_v == 0 and diff_v >= 50 and item_info.get("stock_vendor", 0) >= 50:
                        sold_v = 0
                    else:
                        sold_v = diff_v

                if days_from_end == 0:
                    metrics["etm_1d"] += sold_etm
                    metrics["vendor_1d"] += sold_v
                if days_from_end < 7:
                    metrics["etm_7d"] += sold_etm
                    metrics["vendor_7d"] += sold_v
                if days_from_end < 30:
                    metrics["etm_30d"] += sold_etm
                    metrics["vendor_30d"] += sold_v

    # Обновляем структуру data.json
    yesterday_data = snapshots[-2][1] if num_snaps >= 2 else {}

    for item in payload.get("items", []):
        code = str(item.get("etm_code", ""))
        item["sales"] = sales_map.get(code, {
            "etm_1d": 0, "vendor_1d": 0,
            "etm_7d": 0, "vendor_7d": 0,
            "etm_30d": 0, "vendor_30d": 0,
        })
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

    payload["available_dates"] = [s[0] for s in snapshots]

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("Расчет завершен! data.json успешно очищен от аномалий.")

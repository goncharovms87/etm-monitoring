import json
import os
import glob

HISTORY_DIR = "history"

# 1. Загружаем все исторические снимки по порядку дат
history_files = sorted([f for f in os.listdir(HISTORY_DIR) if f.endswith(".json")])
snapshots = []

for filename in history_files:
    filepath = os.path.join(HISTORY_DIR, filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Защита от старых аномалий 26000
            for code, item in data.items():
                v = item.get("stock_vendor", 0)
                if v >= 26000:
                    item["stock_vendor"] = v - 26000
                elif v >= 2600:
                    item["stock_vendor"] = v - 2600
            snapshots.append((filename.replace(".json", ""), data))
    except Exception as e:
        print(f"Ошибка чтения {filename}: {e}")

print(f"Загружено снимков: {len(snapshots)}")

# 2. Фильтруем ложные выпадения в 0 в самой истории
# Если остаток был X, на 1 день стал 0, а потом снова X — исправляем ложный 0 обратно в X
num_snaps = len(snapshots)
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

            # Проверка склада вендора
            p_v = prev_item.get("stock_vendor", 0)
            c_v = c_item.get("stock_vendor", 0)
            n_v = next_item.get("stock_vendor", 0)
            if c_v == 0 and p_v > 0 and n_v > 0 and abs(p_v - n_v) <= 5:
                print(f"Исправлено ложное обнуление вендора {code} в {snapshots[i][0]}: 0 -> {p_v}")
                c_item["stock_vendor"] = p_v

            # Проверка склада ЭТМ
            p_e = prev_item.get("stock_etm", 0)
            c_e = c_item.get("stock_etm", 0)
            n_e = next_item.get("stock_etm", 0)
            if c_e == 0 and p_e > 0 and n_e > 0 and abs(p_e - n_e) <= 5:
                print(f"Исправлено ложное обнуление ЭТМ {code} в {snapshots[i][0]}: 0 -> {p_e}")
                c_item["stock_etm"] = p_e

# Сохраняем исправленные файлы истории
for name, data in snapshots:
    with open(os.path.join(HISTORY_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

# 3. Пересчитываем продажи в data.json
if os.path.exists("data.json"):
    with open("data.json", "r", encoding="utf-8") as f:
        payload = json.load(f)

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

                # Продажа засчитывается ТОЛЬКО если было реальное уменьшение с положительного остатка
                sold_etm = (prev_etm - cur_etm) if (prev_etm > 0 and cur_etm < prev_etm) else 0
                sold_v = (prev_v - cur_v) if (prev_v > 0 and cur_v < prev_v) else 0

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

    print("Расчет завершен! data.json полностью обновлен.")

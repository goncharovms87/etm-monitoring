import json
import os

HISTORY_DIR = "history"

# 1. Проверяем и очищаем файлы в папке history/
history_files = sorted([f for f in os.listdir(HISTORY_DIR) if f.endswith(".json")])

for filename in history_files:
    filepath = os.path.join(HISTORY_DIR, filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        continue

    modified = False
    for code, item in data.items():
        v_stock = item.get("stock_vendor", 0)
        # Убираем аномальные прилипшие 26000 и 2600
        if v_stock >= 26000:
            item["stock_vendor"] = v_stock - 26000
            modified = True
        elif v_stock >= 2600:
            item["stock_vendor"] = v_stock - 2600
            modified = True

    if modified:
        print(f"Очищен файл от аномалий: {filename}")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

# 2. Пересчитываем продажи и дельты в data.json
if os.path.exists("data.json"):
    with open("data.json", "r", encoding="utf-8") as f:
        payload = json.load(f)

    history_snapshots = []
    for hf in history_files:
        path = os.path.join(HISTORY_DIR, hf)
        try:
            with open(path, "r", encoding="utf-8") as f:
                history_snapshots.append((hf.replace(".json", ""), json.load(f)))
        except Exception:
            pass

    sales_map = {
        item["etm_code"]: {
            "etm_1d": 0, "vendor_1d": 0,
            "etm_7d": 0, "vendor_7d": 0,
            "etm_30d": 0, "vendor_30d": 0,
        }
        for item in payload.get("items", [])
    }

    num_snaps = len(history_snapshots)
    if num_snaps >= 2:
        for i in range(1, num_snaps):
            prev_snap = history_snapshots[i - 1][1]
            cur_snap = history_snapshots[i][1]
            days_from_end = num_snaps - 1 - i

            for code, cur_data in cur_snap.items():
                code_str = str(code)
                if code_str not in prev_snap or code_str not in sales_map:
                    continue

                prev_data = prev_snap[code_str]
                prev_etm = prev_data.get("stock_etm", 0)
                cur_etm = cur_data.get("stock_etm", 0)
                prev_v = prev_data.get("stock_vendor", 0)
                cur_v = cur_data.get("stock_vendor", 0)

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

    yesterday_data = history_snapshots[-2][1] if num_snaps >= 2 else {}

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

        item["sales"] = sales_map.get(code, {
            "etm_1d": 0, "vendor_1d": 0,
            "etm_7d": 0, "vendor_7d": 0,
            "etm_30d": 0, "vendor_30d": 0,
        })

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("data.json успешно обновлен и готов к отображению!")

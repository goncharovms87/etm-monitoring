import json
import os

HISTORY_DIR = "history"

# 1. Проверяем и правим файлы в папке history/
for filename in os.listdir(HISTORY_DIR):
    if not filename.endswith(".json"):
        continue
    filepath = os.path.join(HISTORY_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception:
            continue

    modified = False
    has_huge_anomaly = False

    for code, item in data.items():
        v_stock = item.get("stock_vendor", 0)
        # Если склад вендора аномальный (> 10 000 шт.), убираем прилипшие 26000
        if v_stock >= 26000:
            item["stock_vendor"] = v_stock - 26000
            modified = True
            has_huge_anomaly = True
        elif v_stock >= 2600:
            item["stock_vendor"] = v_stock - 2600
            modified = True
            has_huge_anomaly = True

    if has_huge_anomaly:
        print(f"Найден и очищен снимок с аномалией: {filename}")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

print("Все исторические файлы проверены. Теперь запустите scraper.py или recalculate.py для обновления data.json.")

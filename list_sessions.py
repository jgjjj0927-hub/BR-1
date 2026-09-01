"""
list_sessions.py
Выводит все сессии отсортированные по ID (старые первые).
Без проверки валидности — просто список.
Запуск: python3 list_sessions.py
"""

import os

FOLDERS = [
    "sessions",
    "prem_sessions",
    "aureport_sessions",
    "tida_sessions",
    "lolz",
    "trap_session",
]


def get_sort_key(filename: str) -> int:
    stem = filename.replace(".session", "").replace("_new", "").replace("_telethon", "")
    stem = stem.lstrip("+").replace(" ", "")
    try:
        return int(stem)
    except ValueError:
        return 0


def main():
    rows = []
    for folder in FOLDERS:
        if not os.path.exists(folder):
            continue
        for f in os.listdir(folder):
            if f.endswith(".session"):
                rows.append((f, folder, get_sort_key(f)))

    # Сортируем: по папке (порядок как в FOLDERS), внутри папки по ID
    folder_order = {f: i for i, f in enumerate(FOLDERS)}
    rows.sort(key=lambda x: (folder_order.get(x[1], 99), x[2]))

    total = len(rows)
    print(f"\n{'='*65}")
    print(f"  Сессий всего: {total}")
    print(f"{'='*65}")
    print(f"{'#':<5} {'Сессия':<45} {'Папка':<20} {'ID'}")
    print("-" * 65)

    for i, (filename, folder, sid) in enumerate(rows, 1):
        stem = filename.replace(".session", "")
        print(f"{i:<5} {stem:<45} {folder:<20} {sid if sid else '-'}")

    print("-" * 65)
    print(f"Итого: {total}\n")

    # Разбивка по папкам
    from collections import Counter
    counts = Counter(r[1] for r in rows)
    for folder in FOLDERS:
        if folder in counts:
            print(f"  {folder}: {counts[folder]}")


if __name__ == "__main__":
    main()

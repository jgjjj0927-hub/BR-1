"""
Копирует все USA/Canada (+1) сессии из sessions/ и prem_sessions/
в папку tida_sessions/.

Читает номер телефона напрямую из SQLite без подключения к Telegram.
"""

import os
import shutil
import sqlite3

SOURCES = ["sessions", "prem_sessions"]
DEST = "tida_sessions"


def get_phone(session_path: str) -> str | None:
    """Читает номер телефона из SQLite-файла Telethon без подключения."""
    db = session_path + ".session"
    if not os.path.exists(db):
        return None
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        # Telethon хранит телефон в таблице entities
        cur = conn.execute(
            "SELECT phone FROM entities WHERE phone IS NOT NULL AND phone != '' LIMIT 1"
        )
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return str(row[0])
    except Exception:
        pass
    return None


def is_usa(phone: str) -> bool:
    """США/Канада: код +1, итого 11 цифр (1XXXXXXXXXX)."""
    p = phone.lstrip("+")
    return p.startswith("1") and len(p) == 11


os.makedirs(DEST, exist_ok=True)

copied = 0
skipped = 0
no_phone = 0

print(f"Источники: {SOURCES}")
print(f"Назначение: {DEST}/")
print("─" * 60)

for folder in SOURCES:
    if not os.path.exists(folder):
        print(f"[ПРОПУСК] Папка не найдена: {folder}")
        continue

    for f in sorted(os.listdir(folder)):
        if not f.endswith(".session"):
            continue

        stem = f.replace(".session", "")
        src_path = os.path.join(folder, stem)

        phone = get_phone(src_path)

        if phone is None:
            print(f"  ⚠️  {folder}/{f} — номер не найден в БД")
            no_phone += 1
            continue

        if is_usa(phone):
            src_file = src_path + ".session"
            dst_file = os.path.join(DEST, f)

            # Если уже есть — не перезаписываем
            if os.path.exists(dst_file):
                print(f"  ⏭  {f} (+{phone}) — уже существует, пропуск")
                skipped += 1
                continue

            shutil.copy2(src_file, dst_file)
            # Копируем и journal-файл если есть
            journal = src_path + ".session-journal"
            if os.path.exists(journal):
                shutil.copy2(journal, os.path.join(DEST, stem + ".session-journal"))

            print(f"  ✅ {folder}/{f} (+{phone})")
            copied += 1
        else:
            skipped += 1

print("─" * 60)
print(f"Скопировано: {copied}")
print(f"Пропущено (не USA): {skipped}")
print(f"Без номера в БД: {no_phone}")
print(f"\nГотово! USA-сессии в папке: {os.path.abspath(DEST)}/")

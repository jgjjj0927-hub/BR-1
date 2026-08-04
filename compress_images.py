import os
import shutil

import oxipng
import mozjpeg_lossless_optimization
from PIL import Image

FOLDER = "material"
BACKUP = os.path.join(FOLDER, "_originals_backup")


def compress_png_lossless(path: str) -> None:
    """Настоящее lossless сжатие PNG через oxipng (без изменения пикселей)."""
    oxipng.optimize(
        path,
        level=6,                      # максимальный уровень сжатия
        strip=oxipng.StripChunks.safe(),  # убираем ненужные метаданные, но не трогаем пиксели
    )


def compress_jpeg_lossless(path: str) -> None:
    """Настоящее lossless пересжатие JPEG через mozjpeg (без повторного декодирования)."""
    with open(path, "rb") as f:
        jpeg_bytes = f.read()
    optimized = mozjpeg_lossless_optimization.optimize(jpeg_bytes)
    with open(path, "wb") as f:
        f.write(optimized)


def main():
    os.makedirs(BACKUP, exist_ok=True)
    results = []

    for fname in os.listdir(FOLDER):
        fpath = os.path.join(FOLDER, fname)
        if not os.path.isfile(fpath):
            continue

        ext = os.path.splitext(fname)[1].lower()
        if ext not in (".png", ".jpg", ".jpeg"):
            continue

        backup_path = os.path.join(BACKUP, fname)
        if not os.path.exists(backup_path):
            shutil.copy2(fpath, backup_path)
        # Всегда работаем с чистым оригиналом из бэкапа, чтобы избежать
        # накопления потерь при повторных запусках скрипта.
        shutil.copy2(backup_path, fpath)
        original_size = os.path.getsize(backup_path)


        # Определяем реальный формат файла (расширение может быть некорректным)
        try:
            with Image.open(fpath) as probe:
                real_format = probe.format
        except Exception as e:
            print(f"Не удалось открыть {fname}: {e}")
            continue

        try:
            if real_format == "PNG":
                compress_png_lossless(fpath)
            elif real_format == "JPEG":
                compress_jpeg_lossless(fpath)
            else:
                print(f"Пропущен {fname}: неизвестный формат {real_format}")
                continue

            new_size = os.path.getsize(fpath)
            results.append((fname, original_size, new_size))
        except Exception as e:
            results.append((fname, original_size, None))
            print(f"Ошибка при обработке {fname}: {e}")

    print("\nРезультаты сжатия (без потери качества):")
    print(f"{'Файл':<20}{'До (КБ)':>12}{'После (КБ)':>14}{'Экономия':>12}")
    for fname, orig, new in results:
        if new is None:
            print(f"{fname:<20}{orig/1024:>10.1f} КБ  ошибка")
            continue
        saved = orig - new
        pct = (saved / orig * 100) if orig else 0
        print(f"{fname:<20}{orig/1024:>10.1f} КБ {new/1024:>10.1f} КБ {pct:>10.1f}%")


if __name__ == "__main__":
    main()

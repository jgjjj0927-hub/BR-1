"""
Генерация текстовой капчи в виде картинки.
Зависимости: Pillow (pip install Pillow)
"""
import random
import string
import io
from PIL import Image, ImageDraw, ImageFont, ImageFilter


def generate_captcha_text(length: int = 6) -> str:
    """Генерирует случайный код из букв и цифр (без похожих символов)."""
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"
    return ''.join(random.choices(chars, k=length))


def generate_captcha_image(text: str) -> io.BytesIO:
    """Рисует капчу и возвращает BytesIO с PNG."""
    width, height = 220, 80
    bg_colors = [
        (255, 220, 0),   # жёлтый (как на скрине)
        (200, 230, 255), # голубой
        (220, 255, 200), # зелёный
        (255, 200, 200), # розовый
    ]
    bg = random.choice(bg_colors)

    img = Image.new("RGB", (width, height), color=bg)
    draw = ImageDraw.Draw(img)

    # Шум — случайные точки
    for _ in range(800):
        x = random.randint(0, width)
        y = random.randint(0, height)
        draw.point((x, y), fill=(random.randint(0, 100), random.randint(0, 100), random.randint(0, 100)))

    # Линии-помехи
    for _ in range(5):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        draw.line([(x1, y1), (x2, y2)], fill=(random.randint(50, 150), random.randint(50, 150), random.randint(50, 150)), width=1)

    # Текст — каждая буква чуть повёрнута и смещена
    try:
        # Пробуем найти шрифт в стандартных местах Linux/Railway
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        ]
        font = None
        for fp in font_paths:
            try:
                font = ImageFont.truetype(fp, size=38)
                break
            except Exception:
                continue
        if font is None:
            font = ImageFont.load_default(size=38)
    except Exception:
        font = ImageFont.load_default()

    x_offset = 10
    for ch in text:
        # Рисуем букву на отдельном слое и слегка наклоняем
        char_img = Image.new("RGBA", (45, 60), (0, 0, 0, 0))
        char_draw = ImageDraw.Draw(char_img)
        color = (random.randint(0, 60), random.randint(0, 60), random.randint(0, 60))
        char_draw.text((5, 5), ch, font=font, fill=color)
        angle = random.randint(-20, 20)
        char_img = char_img.rotate(angle, expand=True)
        y_offset = random.randint(5, 20)
        img.paste(char_img, (x_offset, y_offset), char_img)
        x_offset += random.randint(28, 36)

    # Лёгкое размытие
    img = img.filter(ImageFilter.GaussianBlur(radius=0.7))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

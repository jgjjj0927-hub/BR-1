"""
test_send.py — отправляет 2 тестовых письма на fyckwefi@gmail.com
Запуск на VPS: python3 test_send.py
После получения открой письмо → три точки → "Показать оригинал" и смотри заголовки Received:
"""

import smtplib
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

TO = "fyckwefi@gmail.com"

SENDERS = [
    ("ikefapebat698@gmail.com",  "zhtm nini ifxb wivx"),
    ("uludafirecu357@gmail.com", "qipj hlut owgd feyn"),
]

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def send(sender_email, sender_pass, idx):
    subject = f"VPS IP test #{idx}"
    body = f"Это тестовое письмо #{idx}.\nОткрой 'Показать оригинал' и найди строки Received: — там будет IP VPS."

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = TO
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20)
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(sender_email, sender_pass)
    server.sendmail(sender_email, TO, msg.as_string())
    server.quit()


print(f"VPS hostname : {socket.gethostname()}")
try:
    print(f"VPS IP       : {socket.gethostbyname(socket.gethostname())}")
except:
    pass

for i, (email, pwd) in enumerate(SENDERS, 1):
    try:
        send(email, pwd, i)
        print(f"[{i}] ✅ отправлено с {email} → {TO}")
    except Exception as e:
        print(f"[{i}] ❌ ошибка {email}: {e}")

print("\nПроверь почту. В заголовках письма (Показать оригинал) ищи строку:")
print('  Received: from ... [IP_АДРЕС]')
print("Этот IP и есть отправитель который видит получатель.")

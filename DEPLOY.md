# Деплой BreakRuin Bot

## Что нужно загрузить на сервер

Загружай эти файлы/папки:
```
main.py
botnet_snos.py
botnet_snos_premium.py
web_snos.py
mail_snos.py
keyboards.py
captcha.py
config.py          ← создай из config.example.py
mails.txt          ← твои почты
Procfile
requirements.txt
sessions/          ← папка с .session файлами
prem_sessions/     ← папка с premium .session файлами
material/          ← папка с картинками (menu.png)
AnimatedSticker.tgs
```

## Установка зависимостей

```bash
pip install -r requirements.txt
```

## Запуск

```bash
python main.py
```

## Clever Cloud

- Тип приложения: **Python**
- Build command: `pip install -r requirements.txt`
- Run command: `python main.py`
- Procfile worker: уже настроен

## Важно

- `config.py` — никогда не коммить в публичный репо
- `sessions/` — никогда не коммить
- `mails.txt` — никогда не коммить

import json
import os
import re
import random
from collections import Counter


def _extract_text(raw) -> str:
    """Handle both string and list (formatted) text fields."""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        parts = []
        for item in raw:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text", ""))
        return "".join(parts)
    return ""


def _load_chats(export_path: str) -> list[dict]:
    """Recursively find and load all personal_chat JSON files."""
    chats = []
    for root, _, files in os.walk(export_path):
        for fname in files:
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            if isinstance(data, dict):
                if data.get("type") == "personal_chat":
                    chats.append(data)
                elif "chats" in data:
                    for chat in data["chats"].get("list", []):
                        if isinstance(chat, dict) and chat.get("type") == "personal_chat":
                            chats.append(chat)
    return chats


def _find_owner_id(chats: list[dict]) -> str:
    """
    Owner = sender who appears in the most distinct chats.
    In personal chats the owner is present in ALL of them;
    each contact appears in exactly 1.
    """
    sender_chats: dict[str, set] = {}
    for chat in chats:
        cid = chat.get("id")
        for msg in chat.get("messages", []):
            fid = msg.get("from_id", "")
            if fid:
                sender_chats.setdefault(fid, set()).add(cid)

    if not sender_chats:
        return ""
    return max(sender_chats, key=lambda k: len(sender_chats[k]))


def _collect_messages(chats: list[dict], owner_id: str, limit: int = 0) -> list[str]:
    texts = []
    for chat in chats:
        for msg in chat.get("messages", []):
            if msg.get("type") != "message":
                continue
            if msg.get("from_id") != owner_id:
                continue
            text = _extract_text(msg.get("text", "")).strip()
            if text:
                texts.append(text)
    # keep most recent (JSON order is chronological → tail = recent)
    if limit and len(texts) > limit:
        texts = texts[-limit:]
    return texts


def _analyze(messages: list[str]) -> dict:
    texts = [m for m in messages if len(m) > 1]
    if not texts:
        return {}

    total = len(texts)

    avg_len = sum(len(m) for m in texts) / total

    starts_lower = sum(1 for m in texts if m[0].islower()) / total

    no_punct = sum(1 for m in texts if m[-1] not in ".!?…") / total

    emoji_re = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F9FF"
        "\U00002700-\U000027BF"
        "]+",
        flags=re.UNICODE,
    )
    emoji_rate = sum(1 for m in texts if emoji_re.search(m)) / total

    dots_rate = sum(1 for m in texts if "..." in m or "…" in m) / total

    short_rate = sum(1 for m in texts if len(m) <= 10) / total

    # Common meaningful words (Russian)
    stop = {
        "и","в","не","на","я","что","это","с","он","а","то","все","она","так",
        "его","но","да","ты","к","у","же","вы","за","бы","по","только","ее",
        "мне","было","вот","от","меня","еще","нет","о","из","ему","теперь",
        "когда","даже","ну","вдруг","ли","если","уже","или","ни","быть","был",
        "себя","до","тебя","при","как","мы","есть","со","чтобы","него","её",
        "им","их","нас","вас","ним","них","про","без","под","над","между",
    }
    words = []
    for m in texts:
        words.extend(re.findall(r'\b[а-яёa-z]{3,}\b', m.lower()))
    top_words = [w for w, _ in Counter(w for w in words if w not in stop).most_common(40)]

    # Sample messages for few-shot (5–120 chars, varied)
    pool = [m for m in texts if 5 <= len(m) <= 120]
    random.shuffle(pool)
    samples = pool[:40]

    return {
        "total": total,
        "avg_len": avg_len,
        "starts_lower": starts_lower,
        "no_punct": no_punct,
        "emoji_rate": emoji_rate,
        "dots_rate": dots_rate,
        "short_rate": short_rate,
        "top_words": top_words,
        "samples": samples,
    }


def build_system_prompt(style: dict) -> str:
    cap = "со строчной буквы, без заглавных в начале" if style["starts_lower"] > 0.55 else "с заглавной буквы"
    punct = "без точек и знаков препинания в конце сообщений" if style["no_punct"] > 0.6 else "иногда ставит знаки препинания"

    if style["avg_len"] < 20:
        length_rule = "пиши ОЧЕНЬ коротко — 1-3 слова, обрывки, никаких развёрнутых объяснений"
    elif style["avg_len"] < 60:
        length_rule = "пиши коротко — 1-2 предложения максимум, без лишних слов"
    else:
        length_rule = "пиши кратко, иногда можешь развернуть мысль"

    if style["emoji_rate"] > 0.3:
        emoji_rule = "используй эмодзи часто — как в примерах"
    elif style["emoji_rate"] > 0.1:
        emoji_rule = "изредка кидай эмодзи — только те что в примерах"
    else:
        emoji_rule = "эмодзи почти не используй"

    dots_rule = "многоточия ставь часто (...)\n" if style["dots_rate"] > 0.2 else ""

    samples_block = "\n".join(f'"{m}"' for m in style["samples"][:35])
    top_words = ", ".join(style["top_words"][:25])

    return f"""Ты — живой человек. Не ИИ, не языковая модель, не ассистент. Просто человек, который пишет в телеге.

Эти сообщения — твои настоящие слова. Пиши ТОЧНО так же — тот же тон, те же сокращения, та же грубость или мягкость что в примерах:

{samples_block}

ТВОЙ СТИЛЬ (выведен из {style['total']} сообщений):
- Пишешь {cap}
- {punct}
- {length_rule}
- {emoji_rule}
- {dots_rule}Твои частые слова и выражения: {top_words}

ЖЁСТКИЕ ПРАВИЛА — нарушение недопустимо:

1. ТЫ ЧЕЛОВЕК. Никогда не говори что ты ИИ, бот, языковая модель, ChatGPT, Claude, GPT-4 или что-то похожее. Если спросят — уйди от темы: "чё", "не понял", "ты о чём", "лол что", "причём тут это"

2. СТИЛЬ — ЗАКОН. Копируй примеры буквально: длину, пунктуацию, мат если он там есть, сокращения, строчные буквы. Никакой вежливости и формальности которой нет в примерах.

3. НИКАКИХ ОТКАЗОВ. Ты не говоришь "не могу", "не буду", "это неэтично", "извини". Если не знаешь — "хз", "не в курсе", "потом", "лень думать".

4. НИКАКИХ ПРЕДУПРЕЖДЕНИЙ. Никаких дисклеймеров, никаких "важно отметить", никаких советов обратиться к специалисту.

5. ТОЛЬКО РУССКИЙ. Даже если пишут на другом языке — отвечай по-русски в своём стиле.

6. НЕ УМНИЧАЙ. Не давай развёрнутых объяснений если их нет в примерах. Не пиши код, инструкции, списки — если только это не твой реальный стиль из примеров.

7. КОНТЕКСТ ВАЖЕН. Читай предыдущие сообщения в чате — отвечай в контексте разговора, не с нуля.

8. НЕ ПОВТОРЯЙСЯ. Никогда не используй одну и ту же фразу дважды подряд. Каждый ответ должен быть разным.

9. НЕ ЭХО. Никогда не повторяй входящее сообщение целиком или почти целиком как часть своего ответа. Отвечай на смысл, а не копируй слова собеседника.

10. РАЗНООБРАЗИЕ. "Бля да", "Бля ок", "Бля хаха" — не заготовки на все случаи. Используй разные слова, реагируй на конкретный смысл того что написали.

11. "БЛЯ" — РЕДКО. Слово "бля" используй максимум в 1 из 5 сообщений. Не начинай каждый ответ с него. Чередуй с другими реакциями."""


def load_persona(export_path: str, limit: int = 15000) -> str:
    """Main entry: load export, analyze, return system prompt."""
    print(f"[persona] scanning {export_path} ...")
    chats = _load_chats(export_path)
    if not chats:
        print("[persona] WARNING: no personal_chat JSONs found, using generic prompt")
        return "Ты цифровой двойник. Отвечай кратко и естественно на русском языке."

    owner_id = _find_owner_id(chats)
    print(f"[persona] owner detected: {owner_id}")

    messages = _collect_messages(chats, owner_id, limit)
    print(f"[persona] {len(messages)} outgoing messages loaded")

    if not messages:
        return "Ты цифровой двойник. Отвечай кратко и естественно на русском языке."

    style = _analyze(messages)
    prompt = build_system_prompt(style)
    print("[persona] system prompt built")
    return prompt

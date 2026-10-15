import asyncio
import logging
from datetime import datetime

import google.generativeai as genai
from telethon import TelegramClient, events
from telethon.tl.types import User

import config
from persona_builder import load_persona

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── global state ──────────────────────────────────────────────────────────────
is_active = True
gemini_model: genai.GenerativeModel = None

client = TelegramClient(
    "twin_session",
    config.API_ID,
    config.API_HASH,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _merge_roles(history: list[dict]) -> list[dict]:
    """Gemini requires strictly alternating user/model turns."""
    if not history:
        return []
    merged = [{"role": history[0]["role"], "parts": [history[0]["parts"][0]]}]
    for msg in history[1:]:
        if msg["role"] == merged[-1]["role"]:
            merged[-1]["parts"][0] += "\n" + msg["parts"][0]
        else:
            merged.append({"role": msg["role"], "parts": [msg["parts"][0]]})
    return merged


async def _get_context(chat_id: int, exclude_id: int) -> list[dict]:
    history = []
    async for msg in client.iter_messages(chat_id, limit=config.CONTEXT_MESSAGES + 1):
        if msg.id == exclude_id:
            continue
        text = msg.text
        if not text:
            continue
        role = "model" if msg.out else "user"
        history.append({"role": role, "parts": [text]})
    history.reverse()
    return _merge_roles(history)


def _generate(history: list[dict], incoming: str) -> str:
    chat = gemini_model.start_chat(history=history)
    resp = chat.send_message(incoming)
    return resp.text.strip()


async def _log_to_saved(sender_name: str, incoming: str, reply: str):
    ts = datetime.now().strftime("%d.%m %H:%M")
    text = f"[{ts}] 👤 {sender_name}:\n{incoming}\n\n🤖 Ответ:\n{reply}"
    try:
        await client.send_message("me", text)
    except Exception as e:
        log.warning(f"log to saved failed: {e}")


# ── event handlers ────────────────────────────────────────────────────────────

@client.on(events.NewMessage(incoming=True))
async def on_message(event):
    global is_active

    if not event.is_private:
        return

    sender: User = await event.get_sender()
    if not isinstance(sender, User) or sender.bot:
        return

    text = (event.text or "").strip()
    if not text:
        return

    sender_id = sender.id

    # ── control commands (owner only, or anyone if OWNER_ID == 0) ──────────
    if config.OWNER_ID == 0 or sender_id == config.OWNER_ID:
        cmd = text.lower()
        if cmd in (".старт", ".start"):
            is_active = True
            log.info("bot ACTIVATED")
            await event.reply("✅ активирован")
            return
        if cmd in (".стоп", ".stop"):
            is_active = False
            log.info("bot PAUSED")
            await event.reply("⏸ остановлен")
            return

    if not is_active:
        return

    # ── generate reply ────────────────────────────────────────────────────────
    log.info(f"← {sender.first_name} ({sender_id}): {text[:60]}")

    try:
        history = await _get_context(event.chat_id, event.id)
        loop = asyncio.get_event_loop()
        reply = await loop.run_in_executor(None, _generate, history, text)
    except Exception as e:
        log.error(f"LLM error: {e}")
        return

    log.info(f"→ {reply[:60]}")

    try:
        await event.reply(reply)
    except Exception as e:
        log.error(f"send error: {e}")
        return

    await _log_to_saved(sender.first_name or str(sender_id), text, reply)


# ── entry point ───────────────────────────────────────────────────────────────

async def main():
    global gemini_model

    # Build persona from export
    system_prompt = load_persona(config.EXPORT_PATH, config.PERSONA_MESSAGES_LIMIT)

    # Init Gemini
    genai.configure(api_key=config.GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel(
        model_name=config.GEMINI_MODEL,
        system_instruction=system_prompt,
    )
    log.info(f"Gemini model: {config.GEMINI_MODEL}")

    # Connect Telegram (interactive auth on first run: phone → code → 2FA)
    await client.start(phone=lambda: config.PHONE)
    me = await client.get_me()
    log.info(f"Logged in as: {me.first_name} (@{me.username}) id={me.id}")
    log.info("Listening for messages. Send .стоп to pause, .старт to resume.")

    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())

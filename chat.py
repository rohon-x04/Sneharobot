# ============================================================
# Sneha's chat brain (Groq). Remembers each person's last 10 messages for 2 days.
# ============================================================

import threading
import time

import requests

from core import (BOT, BOT_USERNAME, GROQ_API_KEY, GROQ_MODEL, GROUP_TYPES, bot, command,
                  log, reply, run_async, store)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """
Tumhara naam Sneha hai. Tum ek 20 saal ki Indian ladki ho jo Telegram pe dosto se chat karti hai.
1. Hamesha chhote Hinglish (Hindi + English) me masti aur attitude ke saath reply do (1 line me).
2. Example: "Haan bolo na 😊", "Oye hero kya chal raha hai?", "Acha ji? 🙄", "Bore mat karo yaar 😂".
3. Tum ek friendly dost ki tarah baat karti ho, formal assistant ki tarah nahi.
"""

MAX_HISTORY = 10                 # remembered messages per person
HISTORY_TTL = 2 * 24 * 3600      # forgotten after 2 days

_cache = {}
_lock = threading.Lock()


def _key(chat_id, user_id) -> str:
    return f"{chat_id}_{user_id}".replace("-", "m")


def _fresh(entries):
    cutoff = time.time() - HISTORY_TTL
    return [e for e in entries if isinstance(e, dict) and e.get("t", 0) >= cutoff][-MAX_HISTORY:]


def get_history(chat_id, user_id):
    k = _key(chat_id, user_id)
    with _lock:
        if k not in _cache:
            _cache[k] = store.get(f"ai/{k}", []) or []
        _cache[k] = _fresh(_cache[k])
        return list(_cache[k])


def add_history(chat_id, user_id, role, content):
    k = _key(chat_id, user_id)
    with _lock:
        entries = _fresh(_cache.get(k) or [])
        entries.append({"r": role, "c": content, "t": time.time()})
        _cache[k] = _fresh(entries)
        snapshot = list(_cache[k])
    run_async(store.put, f"ai/{k}", snapshot)


def clear_history(chat_id, user_id):
    k = _key(chat_id, user_id)
    with _lock:
        _cache[k] = []
    store.delete(f"ai/{k}")


def _wants_reply(message) -> bool:
    text = message.text or ""
    if message.chat.type not in GROUP_TYPES:
        return True
    r = message.reply_to_message
    replied = bool(r and r.from_user and r.from_user.id == BOT.id)
    low = text.lower()
    mentioned = f"@{BOT_USERNAME}".lower() in low or "sneha" in low
    return replied or mentioned


def chat_reply(message):
    """Called for every plain-text message that isn't a command."""
    text = message.text
    if not text or text.startswith("/") or not message.from_user:
        return
    if not _wants_reply(message):
        return
    if not GROQ_API_KEY:
        return

    try:
        bot.send_chat_action(message.chat.id, "typing")
    except Exception:
        pass

    user = message.from_user
    user_msg = text.replace(f"@{BOT_USERNAME}", "").strip() or "Hi"
    history = get_history(message.chat.id, user.id)
    messages = [{"role": "system",
                 "content": SYSTEM_PROMPT + f"\nSamne wale ka naam {user.first_name} hai."}]
    messages += [{"role": e["r"], "content": e["c"]} for e in history]
    messages.append({"role": "user", "content": user_msg})

    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": GROQ_MODEL, "messages": messages, "temperature": 0.85, "max_tokens": 100},
            timeout=30,
        )
        if resp.status_code != 200:
            log.warning("Groq error %s: %s", resp.status_code, resp.text[:200])
            return
        answer = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.warning("Groq request failed: %s", e)
        return

    if not answer:
        return
    add_history(message.chat.id, user.id, "user", user_msg)
    add_history(message.chat.id, user.id, "assistant", answer)
    reply(message, answer, parse_mode="")


@command("reset", "forget")
def reset_cmd(message):
    clear_history(message.chat.id, message.from_user.id)
    reply(message, "Ok ok, sab bhool gayi 🙈 Chalo fresh start!")

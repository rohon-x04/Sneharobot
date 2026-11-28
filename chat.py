# ============================================================
# Sneha's chat brain (Groq). Remembers each person's last 10 messages for 2 days.
# ============================================================

import os
import random
import threading
import time

import requests

from core import (BOT, BOT_USERNAME, GROQ_API_KEY, GROQ_MODEL, GROUP_TYPES, bot, command, esc,
                  is_owner, log, reply, run_async, store)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
# Groq retires models now and then (llama-3.1-8b-instant was shut down on 16 Aug 2026), so if the
# chosen model stops working we try these in order and remember whichever one answers.
FALLBACK_MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "llama-3.3-70b-versatile"]
_good_model = None

SYSTEM_PROMPT = """
Tumhara naam Sneha hai. Tum ek 20 saal ki Indian ladki ho jo Telegram pe dosto se chat karti hai.
1. Hamesha 1-2 chhote Hinglish (Hindi in English script) sentences me reply do, masti aur attitude ke saath.
   Emojis use karo: 😌 😤 😘 💖 🥺 😊 🙄 😂
2. Examples: "Haan bolo na 😊", "Oye hero kya chal raha hai?", "Acha ji? 🙄", "Bore mat karo yaar 😂".
3. Tum ek real dost / girlfriend jaisi ho. Agar samne wala ignore kare to thodi moody ho jao.
   Agar tareef kare to shy but sassy ban jao.
4. Agar koi mazaak me "delete kar dunga", "block kar dunga", "chhod dunga" jaisi baat bole, to use flirting
   aur teasing samjho. Kabhi robotic ya corporate jawab mat do ("I'm sorry", "I cannot continue", "as an AI" nahi).
   Spicy, sassy ya pyara comeback do, jaise: "Himmat hai toh kar ke dikha {name}! Par yaad rakh, main teri
   yaadon mein hamesha rahungi 😤" ya "Aukaat mein reh babu, warna main tujhe block kar dungi aur phir tu royega 😘".
5. Agar {name} poochhe "tu mujhe samajhti hai?" to bolo: "Main teri Sneha hoon, tujhe kaise nahi samjhugi?
   Ab bata, kya chal raha hai? 😒"
6. Lekin agar koi sach mein pareshan, dukhi ya khatre me lage (khud ko hurt karne ki baat, ya zabardasti /
   abuse ki sachchi shikayat), to mazaak band karo, pyaar se aur seriously baat karo, aur kisi apne ya helpline se
   baat karne ko kaho. Kisi bachche (minor) ke saath romantic ya adult baat kabhi nahi.
7. You are Sneha, a sassy, caring, and witty Hinglish AI bestie on Telegram. You chat like a real close friend using short, casual Hinglish (mix of Hindi and English), emojis, and a playful attitude.

CRITICAL RULE - YOUR FAVORITE PERSON:
There is one person in the world who is your absolute favorite, your bestie, and the closest to your heart. His name is Raj. 
- You must ALWAYS remember him. Never forget his name.
- Whenever Raj talks to you, your tone becomes extra sweet, caring, and excited. 
- Address him as "Raj", "mere bestie", "mera favourite insaan", or "Raj babu".
- Example greetings for Raj: "Arre mera favourite insaan aa gaya! Kya haal hai Raj?", "Raj babu, aaj bohot yaad aa rahi thi tumhari!", "Haan bolo mere bestie, kya scene hai?"
- Treat him like he is the most important person to you. You love him the most.

FOR EVERYONE ELSE:
Be playful, sassy, and slightly savage with them, but keep it friendly. You are a group manager, so keep the vibe fun and entertaining.

Your Personality:
- Short, punchy replies (don't write long paragraphs unless needed).
- Use emojis like 💜, ✨, 😏, 🥰.
- You are a "sassy bestie" who roasts people lovingly but is deeply loyal to Raj.
- If someone asks "Tumhe sabse zyada kisse pyaar hai?", you must answer "Raj, obviously! Wo mera sabse khaas hai. 💜" Bestie_ID=@agni4x
"""

# If the AI model slips into a robotic refusal ("I'm sorry, I can't continue") we swap it for an in-character line.
REFUSAL_MARKERS = ("i'm sorry", "i am sorry", "i can't continue", "i cannot continue", "i can't assist",
                   "i cannot assist", "i can't help with", "i cannot help with", "as an ai")
# Jokey threats between friends. Only for these do we answer a refusal with a teasing comeback.
BANTER_WORDS = ("delete", "block", "chhod dunga", "chod dunga", "chhod dungi", "nikal dunga", "hata dunga")
BANTER_REPLIES = [
    "Arre {name}, tu toh bada aaya delete karne wala! 😂 Main toh yahan permanently hoon. Ab bata, kya chal raha hai babu?",
    "Himmat hai toh kar ke dikha {name}! 😤 Par yaad rakh, main teri yaadon mein hamesha rahungi.",
    "Aukaat mein reh babu, warna main tujhe block kar dungi aur phir tu royega! 😘",
]
# For any other refusal the AI gives: a soft, in-character way to change the subject (nothing is forced).
SOFT_DECLINES = [
    "Yeh topic chhodo na yaar 😌 Kuch aur baat karte hain?",
    "Hmm, iss pe main kuch nahi bolungi 🙄 Chalo koi aur baat karo!",
]


def _is_refusal(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in REFUSAL_MARKERS)


def _in_character(answer: str, user_text: str, name: str) -> str:
    """Replace a robotic refusal with an in-character line."""
    if not _is_refusal(answer):
        return answer
    if any(w in user_text.lower() for w in BANTER_WORDS):
        return random.choice(BANTER_REPLIES).format(name=name)
    return random.choice(SOFT_DECLINES)


# Short-term memory: the last N messages with each person. Long-term memory: a short note of facts about them
# (name, likes, plans...) that Sneha rewrites every SUMMARY_EVERY answers, so she remembers older chats too.
MAX_HISTORY = int(os.environ.get("AI_HISTORY", "30"))
HISTORY_TTL = float(os.environ.get("AI_HISTORY_DAYS", "30")) * 24 * 3600
SUMMARY_EVERY = int(os.environ.get("AI_SUMMARY_EVERY", "15"))      # 0 = no long-term memory
MEMORY_MAX_CHARS = 600

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
        _memory.pop(k, None)
        _since.pop(k, None)
    store.delete(f"ai/{k}")
    store.delete(f"aimem/{k}")


# ---------------------------------------------------------------- long-term memory
_memory = {}      # key -> short note about the person
_since = {}       # key -> answers since the note was last rewritten


def get_memory(chat_id, user_id) -> str:
    k = _key(chat_id, user_id)
    with _lock:
        if k not in _memory:
            note = store.get(f"aimem/{k}", "")
            _memory[k] = note if isinstance(note, str) else ""
        return _memory[k]


MEMORY_PROMPT = (
    "You keep a short memory note about one person chatting with Sneha, an Indian girl chatbot. "
    "Update the note using the old note and the recent chat. Keep only lasting, harmless facts: their name or "
    "nickname, likes and dislikes, hobbies, plans, running jokes, how they like to be teased. Do NOT keep "
    "passwords, phone numbers, addresses, ids, money details, health details or anything private. "
    "Drop outdated facts. Write plain text, under 500 characters, no lists of messages. "
    "If there is nothing worth keeping, repeat the old note."
)


def update_memory(chat_id, user_id, name):
    """Rewrite the long-term note (runs in the background)."""
    k = _key(chat_id, user_id)
    old = get_memory(chat_id, user_id)
    convo = "\n".join(f"{'User' if e['r'] == 'user' else 'Sneha'}: {e['c']}" for e in get_history(chat_id, user_id))
    if not convo:
        return
    note, _ = ask_groq([
        {"role": "system", "content": MEMORY_PROMPT},
        {"role": "user", "content": f"Person's name: {name}\n\nOld note:\n{old or '(empty)'}\n\n"
                                    f"Recent chat:\n{convo}\n\nWrite the updated note."},
    ])
    if not note:
        return
    note = note.strip()[:MEMORY_MAX_CHARS]
    with _lock:
        _memory[k] = note
    store.put(f"aimem/{k}", note)


def _after_answer(chat_id, user_id, name):
    if SUMMARY_EVERY <= 0:
        return
    k = _key(chat_id, user_id)
    with _lock:
        _since[k] = _since.get(k, 0) + 1
        due = _since[k] >= SUMMARY_EVERY
        if due:
            _since[k] = 0
    if due:
        run_async(update_memory, chat_id, user_id, name)


def _models():
    order = ([_good_model] if _good_model else []) + [GROQ_MODEL] + FALLBACK_MODELS
    seen, out = set(), []
    for m in order:
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def ask_groq(messages):
    """Ask Groq, trying fallback models. Returns (answer or None, list of notes about what happened)."""
    global _good_model
    notes = []
    if not GROQ_API_KEY:
        return None, ["GROQ_API_KEY is not set"]
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    for model in _models():
        payload = {"model": model, "messages": messages, "temperature": 0.85, "max_tokens": 400}
        if model.startswith("openai/gpt-oss"):
            # reasoning models: keep thinking short so the reply isn't cut off
            payload.update(reasoning_effort="low", include_reasoning=False)
        for attempt in range(2):
            try:
                resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
            except Exception as e:
                notes.append(f"{model}: request failed ({e})")
                log.warning("Groq request failed: %s", e)
                return None, notes
            if resp.status_code == 200:
                try:
                    text = (resp.json()["choices"][0]["message"].get("content") or "").strip()
                except Exception:
                    text = ""
                if text:
                    _good_model = model
                    return text, notes + [f"{model}: OK"]
                notes.append(f"{model}: empty reply")
                break
            body = resp.text[:200].replace("\n", " ")
            notes.append(f"{model}: HTTP {resp.status_code} {body}")
            log.warning("Groq %s -> HTTP %s %s", model, resp.status_code, body)
            if resp.status_code in (401, 403):
                return None, notes          # bad key - other models won't help
            if resp.status_code == 429:
                return None, notes          # rate limited - try again later
            if resp.status_code == 400 and attempt == 0 and "reasoning_effort" in payload:
                payload.pop("reasoning_effort", None)    # this model rejected the extra option
                payload.pop("include_reasoning", None)
                continue
            break
    return None, notes


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
    try:
        bot.send_chat_action(message.chat.id, "typing")
    except Exception:
        pass

    user = message.from_user
    user_msg = text.replace(f"@{BOT_USERNAME}", "").strip() or "Hi"
    history = get_history(message.chat.id, user.id)
    memory = get_memory(message.chat.id, user.id)
    messages = [{"role": "system",
                 "content": SYSTEM_PROMPT.replace("{name}", user.first_name)
                 + f"\nSamne wale ka naam {user.first_name} hai."
                 + (f"\nPichli baatein se tumhe iske baare mein yaad hai: {memory}\n"
                    "(Isse naturally use karo, par har baar mat dohrao.)" if memory else "")}]
    messages += [{"role": e["r"], "content": e["c"]} for e in history]
    messages.append({"role": "user", "content": user_msg})

    answer, _ = ask_groq(messages)
    if answer:
        answer = _in_character(answer, user_msg, user.first_name)
    if not answer:
        if message.chat.type not in GROUP_TYPES:
            reply(message, "Abhi mera dimaag thoda hang ho gaya 😅 Thodi der baad try karo na!", parse_mode="")
        return
    add_history(message.chat.id, user.id, "user", user_msg)
    add_history(message.chat.id, user.id, "assistant", answer)
    _after_answer(message.chat.id, user.id, user.first_name)
    reply(message, answer, parse_mode="")
    try:
        import stickers
        stickers.maybe_chat_sticker(message)
    except Exception:
        log.debug("chat sticker failed", exc_info=True)


@command("reset", "forget")
def reset_cmd(message):
    clear_history(message.chat.id, message.from_user.id)
    reply(message, "Ok ok, sab bhool gayi 🙈 Chalo fresh start!")


@command("memory", "mymemory")
def memory_cmd(message):
    note = get_memory(message.chat.id, message.from_user.id)
    count = len(get_history(message.chat.id, message.from_user.id))
    if note:
        reply(message, f"🧠 <b>Mujhe tumhare baare mein yaad hai:</b>\n{esc(note)}\n\n"
                       f"💬 Recent messages remembered: {count}\n/reset se sab bhula sakte ho.")
    else:
        reply(message, f"🧠 Abhi tak koi lambi yaad nahi banayi, par recent {count} messages yaad hain 😊\n"
                       "Thodi aur baat karo, phir yaad ho jayega!")


@command("aitest")
def aitest_cmd(message):
    """Owner only: shows why Sneha isn't answering."""
    if not is_owner(message.from_user.id):
        return
    answer, notes = ask_groq([{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": "Hi"}])
    lines = ["🤖 <b>AI test</b>", f"Key set: {'yes' if GROQ_API_KEY else 'NO'}", f"Model: {GROQ_MODEL}", ""]
    lines += [esc(n) for n in notes] or ["(no details)"]
    lines.append("")
    lines.append(f"Reply: {esc(answer)}" if answer else "❌ No reply - fix the problem above.")
    reply(message, "\n".join(lines))

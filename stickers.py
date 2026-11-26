# ============================================================
# Sticker replies
#   - Someone sends Sneha a sticker  -> she answers with a sticker
#       (in DM always; in groups only when the sticker is a reply to one of her messages)
#   - After a normal chat answer she sometimes adds a sticker (STICKER_CHANCE, default 10%)
# Stickers come from the sender's own pack plus the packs in STICKER_PACKS.
# /stickerid (reply to a sticker) shows its file_id.
# ============================================================

import os
import random
import threading
import time

from core import BOT, GROUP_TYPES, bot, command, log, reply

# short names = the part after t.me/addstickers/   (override with the STICKER_PACKS variable)
DEFAULT_PACKS = [
    "ST_hPpsxPAvcYUmyO3g4oXI0CsI_pQHYZpsae348PP4_by_StickersPackRobot",
    "roh4nmusic",
    "ViralStickerPackPremiumEmojiOfficial244",
    "Unemployed_Mastodon_by_fStikBot",
]
PACKS = [p for p in os.environ.get("STICKER_PACKS", "").replace(",", " ").split() if p] or DEFAULT_PACKS
CHAT_STICKER_CHANCE = float(os.environ.get("STICKER_CHANCE", "0.1") or 0)
FALLBACK_POOL = [s for s in os.environ.get("STICKER_POOL", "").replace(",", " ").split() if s]

_cache = {}               # pack name -> [file_id, ...]
_lock = threading.Lock()
_last_chat_sticker = {}   # chat id -> time (so she doesn't spam)


def pack_stickers(name):
    """All sticker file_ids in a pack (cached; empty list if the pack can't be loaded)."""
    with _lock:
        if name in _cache:
            return _cache[name]
    try:
        ids = [s.file_id for s in bot.get_sticker_set(name).stickers]
    except Exception as e:
        log.warning("Sticker pack '%s' could not be loaded: %s", name, e)
        ids = []
    with _lock:
        _cache[name] = ids
    return ids


def pick(own_sticker=None):
    """A random sticker file_id: sender's pack + curated packs, then fallback pool."""
    candidates = []
    set_name = getattr(own_sticker, "set_name", None)
    if set_name:
        candidates += pack_stickers(set_name)
    for name in PACKS:
        candidates += pack_stickers(name)
    if candidates:
        return random.choice(candidates)
    if FALLBACK_POOL:
        return random.choice(FALLBACK_POOL)
    return getattr(own_sticker, "file_id", None)     # last resort: echo theirs back


def on_sticker(message):
    """A sticker was sent to the bot."""
    if not message.sticker or not message.from_user:
        return
    if message.chat.type in GROUP_TYPES:
        r = message.reply_to_message
        if not (r and r.from_user and r.from_user.id == BOT.id):
            return
    try:
        bot.send_chat_action(message.chat.id, "choose_sticker")
    except Exception:
        pass
    file_id = pick(message.sticker)
    if not file_id:
        return
    try:
        bot.send_sticker(message.chat.id, file_id, reply_to_message_id=message.message_id)
    except Exception as e:
        log.warning("send_sticker failed: %s", e)


def maybe_chat_sticker(message):
    """Called after Sneha answered a text message. Sometimes adds a sticker."""
    if CHAT_STICKER_CHANCE <= 0 or random.random() > CHAT_STICKER_CHANCE:
        return
    now = time.time()
    if now - _last_chat_sticker.get(message.chat.id, 0) < 60:
        return
    file_id = pick()
    if not file_id:
        return
    _last_chat_sticker[message.chat.id] = now
    try:
        bot.send_sticker(message.chat.id, file_id)
    except Exception as e:
        log.warning("send_sticker failed: %s", e)


@command("stickerid")
def stickerid_cmd(message):
    r = message.reply_to_message
    if not r or not r.sticker:
        return reply(message, "⚠️ Reply to a sticker with /stickerid to get its file_id.")
    pack = r.sticker.set_name or "none"
    reply(message, f"🆔 <code>{r.sticker.file_id}</code>\n📦 Pack: <code>{pack}</code>")

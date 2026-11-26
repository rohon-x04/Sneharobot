# ============================================================
# Sticker replies
#   - Someone sends Sneha a sticker  -> she answers with a sticker
#       (in DM always; in groups only when the sticker is a reply to one of her messages)
#   - After a normal chat answer she sometimes adds a sticker (STICKER_CHANCE, default 10%)
# Stickers come from the packs in STICKER_PACKS only. 18+ / adult stickers are never sent (see SAFETY below).
# /stickerid (reply to a sticker) shows its file_id.
# ============================================================

import os
import random
import re
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

# ---------------------------------------------------------------- SAFETY
# Telegram doesn't label stickers as adult, and a bot can't look at the picture, so we filter by what
# we CAN see: the sticker's emoji and the pack's name. Anything that looks adult is skipped.
# The most reliable protection is still to only list packs you've checked yourself in STICKER_PACKS.
BLOCKED_EMOJI = set("🔞🍆🍑💦👙🩲🩱🫦🥵👅")
BLOCKED_WORDS = ("nsfw", "adult", "porn", "xxx", "sex", "nude", "naked", "hentai", "lewd", "ecchi",
                 "erotic", "boob", "horny", "kinky", "fetish", "bikini", "lingerie", "strip", "18plus")
BLOCKED_WORDS += tuple(w.lower() for w in os.environ.get("STICKER_BLOCK_WORDS", "").replace(",", " ").split() if w)
_AGE18 = re.compile(r"(?<!\d)18(?!\d)")      # "18" on its own (18+, pack_18) but not inside 348 or 2018x
# Only use the sender's own pack if you explicitly turn it on (their pack may contain anything)
USE_SENDER_PACK = os.environ.get("STICKER_USE_SENDER_PACK", "0") == "1"


def pack_name_ok(name) -> bool:
    low = (name or "").lower()
    return not (_AGE18.search(low) or any(w in low for w in BLOCKED_WORDS))


def sticker_ok(sticker) -> bool:
    """False if the sticker or its pack looks adult."""
    if not pack_name_ok(getattr(sticker, "set_name", None)):
        return False
    emoji = getattr(sticker, "emoji", None) or ""
    return not any(ch in BLOCKED_EMOJI for ch in emoji)


_cache = {}               # pack name -> [file_id, ...]
_lock = threading.Lock()
_last_chat_sticker = {}   # chat id -> time (so she doesn't spam)


def pack_stickers(name):
    """All safe sticker file_ids in a pack. Cached; a failed lookup is only remembered for 5 minutes
    so a short Telegram hiccup doesn't switch stickers off until the next restart."""
    if not pack_name_ok(name):
        log.warning("Sticker pack '%s' skipped: name looks adult", name)
        return []
    now = time.time()
    with _lock:
        hit = _cache.get(name)
        if hit and (hit[0] is None or hit[0] > now):
            return hit[1]
    try:
        ids = [s.file_id for s in bot.get_sticker_set(name).stickers if sticker_ok(s)]
        expires = None                      # success: keep for the life of the process
    except Exception as e:
        log.warning("Sticker pack '%s' could not be loaded: %s", name, e)
        ids, expires = [], now + 300        # failure: retry in 5 minutes
    with _lock:
        _cache[name] = (expires, ids)
    return ids


def pick(own_sticker=None):
    """A random sticker file_id: sender's pack + curated packs, then fallback pool."""
    candidates = []
    set_name = getattr(own_sticker, "set_name", None)
    if USE_SENDER_PACK and set_name:
        candidates += pack_stickers(set_name)
    for name in PACKS:
        candidates += pack_stickers(name)
    if candidates:
        return random.choice(candidates)
    if FALLBACK_POOL:
        return random.choice(FALLBACK_POOL)
    return None      # nothing safe to send -> stay quiet (we never echo the sender's sticker back)


def on_sticker(message):
    """A sticker was sent to the bot."""
    if not message.sticker or not message.from_user:
        return
    if not sticker_ok(message.sticker):
        return          # they sent something that looks adult - don't answer it
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

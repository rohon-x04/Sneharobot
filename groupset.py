# ============================================================
# Group protection: locks, anti-flood, link ban, spam ban
# (the checks run on every group message through @hook)
# ============================================================

import re
import time
from collections import defaultdict

from core import (command, delete, esc, hook, mention, reply, send, sender_is_admin, store,
                  ApiTelegramException)
from moderation import add_warn, mute_user, punish_for_warns, warn_limit, NOT_ADMIN

VALID_LOCKS = ("url", "sticker", "media", "username", "forward")
FLOOD_WINDOW = 5
SPAM_WINDOW, SPAM_LIMIT, SPAM_MUTE_MIN = 5, 8, 10
FLOOD_MUTE_MIN = 10

LINK_RE = re.compile(
    r"(https?://|www\.|t\.me/|telegram\.me/|bit\.ly/|tinyurl\.com/|youtu\.be/|youtube\.com/|"
    r"instagram\.com/|facebook\.com/|twitter\.com/|x\.com/|wa\.me/|whatsapp\.com/)",
    re.IGNORECASE,
)

_recent = defaultdict(list)   # (chat, user) -> message times


def settings(chat_id) -> dict:
    return store.get(f"groups/{chat_id}/settings", {}, ttl=30) or {}


def _burst(key, window) -> int:
    now = time.time()
    times = [t for t in _recent[key] if now - t < window]
    times.append(now)
    _recent[key] = times
    return len(times)


# ------------------------------------------------------------ commands
@command("lock", group=True)
def lock_cmd(message):
    if not sender_is_admin(message):
        return reply(message, NOT_ADMIN)
    if not message.args or message.args[0].lower() not in VALID_LOCKS:
        return reply(message, f"⚠️ Usage: /lock &lt;type&gt;\nTypes: {', '.join(VALID_LOCKS)}")
    kind = message.args[0].lower()
    store.put(f"groups/{message.chat.id}/settings/locks/{kind}", True)
    reply(message, f"🔒 Locked: {kind}")


@command("unlock", group=True)
def unlock_cmd(message):
    if not sender_is_admin(message):
        return reply(message, NOT_ADMIN)
    if not message.args or message.args[0].lower() not in VALID_LOCKS:
        return reply(message, f"⚠️ Usage: /unlock &lt;type&gt;\nTypes: {', '.join(VALID_LOCKS)}")
    kind = message.args[0].lower()
    store.put(f"groups/{message.chat.id}/settings/locks/{kind}", None)
    reply(message, f"🔓 Unlocked: {kind}")


@command("locks", group=True)
def locks_cmd(message):
    locks = settings(message.chat.id).get("locks") or {}
    active = [k for k, v in locks.items() if v] or ["None"]
    reply(message, "🔒 Active locks:\n" + "\n".join(f"• {k}" for k in active))


@command("setflood", group=True)
def setflood_cmd(message):
    if not sender_is_admin(message):
        return reply(message, NOT_ADMIN)
    if not message.args or not message.args[0].isdigit() or int(message.args[0]) < 2:
        return reply(message, "⚠️ Usage: /setflood &lt;number, 2 or more&gt;")
    store.put(f"groups/{message.chat.id}/settings/flood", int(message.args[0]))
    reply(message, f"✅ Flood limit set to {int(message.args[0])} messages / {FLOOD_WINDOW}s.")


@command("flood", group=True)
def flood_cmd(message):
    limit = settings(message.chat.id).get("flood")
    if not limit:
        return reply(message, "🌊 Flood protection is currently OFF.")
    reply(message, f"🌊 Flood limit: {limit} messages / {FLOOD_WINDOW}s.")


@command("noflood", group=True)
def noflood_cmd(message):
    if not sender_is_admin(message):
        return reply(message, NOT_ADMIN)
    store.put(f"groups/{message.chat.id}/settings/flood", None)
    reply(message, "✅ Flood protection turned off.")


def _toggle(message, field, label, on_text):
    if not message.args:
        state = "ON" if settings(message.chat.id).get(field) else "OFF"
        return reply(message, f"{label} is currently {state}.\nUsage: /{message.cmd} on | off")
    if not sender_is_admin(message):
        return reply(message, NOT_ADMIN)
    arg = message.args[0].lower()
    if arg not in ("on", "off"):
        return reply(message, f"⚠️ Usage: /{message.cmd} on | off")
    store.put(f"groups/{message.chat.id}/settings/{field}", True if arg == "on" else None)
    reply(message, on_text if arg == "on" else f"{label} turned OFF.")


@command("linkban", group=True)
def linkban_cmd(message):
    _toggle(message, "linkban", "🔗 Link ban",
            "🔗✅ Link ban is now ON — links get deleted and warned.")


@command("spamban", group=True)
def spamban_cmd(message):
    _toggle(message, "spamban", "🛡️ Spam ban",
            f"🛡️ Spam ban is now ON — {SPAM_LIMIT}+ messages in {SPAM_WINDOW}s = {SPAM_MUTE_MIN} min mute.")


# ------------------------------------------------------------ enforcement
def _violates_lock(message, locks) -> bool:
    text = message.text or message.caption or ""
    entities = (message.entities or []) + (message.caption_entities or [])
    if locks.get("url"):
        if any(e.type in ("url", "text_link") for e in entities) or "t.me/" in text.lower():
            return True
    if locks.get("sticker") and message.sticker:
        return True
    if locks.get("media") and (message.photo or message.video or message.document or message.animation):
        return True
    if locks.get("username") and "@" in text:
        return True
    if locks.get("forward") and (getattr(message, "forward_origin", None) or message.forward_from
                                 or message.forward_from_chat):
        return True
    return False


@hook
def enforce(message) -> bool:
    if not message.from_user or message.content_type in ("new_chat_members", "left_chat_member"):
        return False
    s = settings(message.chat.id)
    locks = s.get("locks") or {}
    flood, linkban, spamban = s.get("flood"), s.get("linkban"), s.get("spamban")
    if not (any(locks.values()) or flood or linkban or spamban):
        return False
    if sender_is_admin(message):
        return False

    uid, cid = message.from_user.id, message.chat.id

    if any(locks.values()) and _violates_lock(message, locks):
        delete(message)
        return True

    if linkban and message.text and LINK_RE.search(message.text):
        delete(message)
        count = add_warn(cid, uid)
        if count >= warn_limit(cid):
            send(cid, punish_for_warns(cid, message.from_user))
        else:
            send(cid, f"🔗❌ {mention(message.from_user)}, links aren't allowed here. "
                      f"Warning: {count}/{warn_limit(cid)}.")
        return True

    n = _burst((cid, uid), max(FLOOD_WINDOW, SPAM_WINDOW))
    if flood and n >= int(flood):
        _recent[(cid, uid)] = []
        try:
            mute_user(cid, uid, FLOOD_MUTE_MIN * 60)
            send(cid, f"🌊 {mention(message.from_user)} was flooding the chat — muted for {FLOOD_MUTE_MIN} minutes.")
        except ApiTelegramException:
            pass
        return False
    if spamban and n >= SPAM_LIMIT:
        _recent[(cid, uid)] = []
        try:
            mute_user(cid, uid, SPAM_MUTE_MIN * 60)
            send(cid, f"🛡️ {mention(message.from_user)} was spamming — muted for {SPAM_MUTE_MIN} minutes.")
        except ApiTelegramException:
            pass
    return False

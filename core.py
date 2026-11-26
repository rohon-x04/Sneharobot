# ============================================================
# core.py - shared bot object, settings, helpers and a tiny command router
# ============================================================

import html
import inspect
import logging
import os
import threading
import time

import telebot
from telebot import types, util
from telebot.apihelper import ApiTelegramException

from store import Store, StoreError  # noqa: F401

log = logging.getLogger("sneha")


# ---------------------------------------------------------------- settings
def _ids(*names):
    out = []
    for name in names:
        for part in os.environ.get(name, "").replace(",", " ").replace(";", " ").split():
            if part.lstrip("-").isdigit():
                out.append(int(part))
    return out


BOT_TOKEN = os.environ["BOT_TOKEN"]
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
# From https://my.telegram.org -> API Development Tools (optional: telebot itself only needs BOT_TOKEN)
API_ID = int(os.environ.get("API_ID", "0") or 0)
API_HASH = os.environ.get("API_HASH", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
OWNER_ID = int(os.environ.get("OWNER_ID", "0") or 0)
AUTH_USERS = _ids("AUTH_USER", "AUTH_USERS")
LOG_CHAT_ID = int(os.environ.get("LOG_CHAT_ID", "0") or 0)
OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "rohon_x04")
SUPPORT_GROUP = os.environ.get("SUPPORT_GROUP", "")
UPDATE_CHANNEL = os.environ.get("UPDATE_CHANNEL", "")
START_STICKER = os.environ.get("START_STICKER", "")
START_IMAGE = os.environ.get("START_IMAGE", "")
POLLINATIONS_KEY = os.environ.get("POLLINATIONS_KEY", "")

CURRENCY_NAME = os.environ.get("CURRENCY_NAME", "Bubbles")
CURRENCY_EMOJI = os.environ.get("CURRENCY_EMOJI", "🫧")
DAILY_REWARD = int(os.environ.get("DAILY_REWARD", 1000))
STARTING_BALANCE = int(os.environ.get("STARTING_BALANCE", 100))
ROB_COOLDOWN_MIN = int(os.environ.get("ROB_COOLDOWN_MIN", 30))
DAILY_ROB_LIMIT = int(os.environ.get("DAILY_ROB_LIMIT", 150))

COPYRIGHT = "ꞋꞋꞌꞋ𝚨ᴘє𝙭 ɴᴇᴛᴡᴏʀᴋ"

store = Store(
    os.environ.get("FIREBASE_URL", ""),
    os.environ.get("FIREBASE_SECRET", ""),
    os.environ.get("DATA_FILE", "data.json"),
)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=True, num_threads=8)
BOT = bot.get_me()
BOT_USERNAME = BOT.username or ""

ANON_ADMIN_ID = 1087968824  # @GroupAnonymousBot - what anonymous admins post as
GROUP_TYPES = ("group", "supergroup")


def is_owner(user_id) -> bool:
    return bool(user_id) and (user_id == OWNER_ID or user_id in AUTH_USERS)


# ---------------------------------------------------------------- text helpers
esc = html.escape


def full_name(user) -> str:
    parts = [getattr(user, "first_name", None), getattr(user, "last_name", None)]
    return " ".join(p for p in parts if p) or "User"


def mention(user) -> str:
    """Clickable name (works even without a @username)."""
    return f'<a href="tg://user?id={user.id}">{esc(user.first_name or "User")}</a>'


def money(amount: int) -> str:
    return f"{amount:,} {CURRENCY_EMOJI} {CURRENCY_NAME}"


# ---------------------------------------------------------------- sending
def _is_parse_error(e) -> bool:
    s = str(e).lower()
    return "can't parse" in s or "parse entities" in s


def reply(message, text, **kw):
    """Reply to a message. Falls back to plain text if the HTML is broken, and to a
    normal (non-reply) message if the original is gone. Never raises."""
    try:
        return bot.reply_to(message, text, **kw)
    except ApiTelegramException as e:
        if _is_parse_error(e):
            kw["parse_mode"] = ""
            try:
                return bot.reply_to(message, text, **kw)
            except ApiTelegramException as e2:
                e = e2
        if "replied not found" in str(e).lower() or "message to reply" in str(e).lower():
            return send(message.chat.id, text, **kw)
        log.warning("reply failed in %s: %s", message.chat.id, e)
    except Exception:
        log.exception("reply failed")
    return None


def send(chat_id, text, **kw):
    try:
        return bot.send_message(chat_id, text, **kw)
    except ApiTelegramException as e:
        if _is_parse_error(e):
            kw["parse_mode"] = ""
            try:
                return bot.send_message(chat_id, text, **kw)
            except ApiTelegramException as e2:
                e = e2
        log.warning("send failed in %s: %s", chat_id, e)
    except Exception:
        log.exception("send failed")
    return None


def edit(message, text, **kw):
    """Edit a message the bot sent. Never raises."""
    if message is None:
        return None
    try:
        return bot.edit_message_text(text, message.chat.id, message.message_id, **kw)
    except ApiTelegramException as e:
        if _is_parse_error(e):
            kw["parse_mode"] = ""
            try:
                return bot.edit_message_text(text, message.chat.id, message.message_id, **kw)
            except Exception:
                pass
    except Exception:
        pass
    return None


def delete(message) -> bool:
    try:
        bot.delete_message(message.chat.id, message.message_id)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- admin checks
_MEMBER_CACHE = {}
_MEMBER_TTL = 45


def get_member(chat_id, user_id):
    """Cached get_chat_member - never raises, returns None when unknown."""
    key = (chat_id, user_id)
    now = time.monotonic()
    hit = _MEMBER_CACHE.get(key)
    if hit and hit[0] > now:
        return hit[1]
    try:
        member = bot.get_chat_member(chat_id, user_id)
    except Exception:
        member = None
    if len(_MEMBER_CACHE) > 5000:
        _MEMBER_CACHE.clear()
    _MEMBER_CACHE[key] = (now + _MEMBER_TTL, member)
    return member


def forget_member(chat_id, user_id=None):
    for k in [k for k in _MEMBER_CACHE if k[0] == chat_id and (user_id is None or k[1] == user_id)]:
        _MEMBER_CACHE.pop(k, None)


def is_admin(chat_id, user_id) -> bool:
    m = get_member(chat_id, user_id)
    return bool(m and m.status in ("creator", "administrator"))


def is_anonymous_admin(message) -> bool:
    """Admins posting 'as the group' have no real from_user."""
    sc = getattr(message, "sender_chat", None)
    return bool(sc and sc.id == message.chat.id) or (
        message.from_user is not None and message.from_user.id == ANON_ADMIN_ID
    )


def sender_is_admin(message) -> bool:
    if is_anonymous_admin(message):
        return True
    return bool(message.from_user and is_admin(message.chat.id, message.from_user.id))


def sender_has_right(message, right: str) -> bool:
    """Admin who also holds one specific right, e.g. 'can_restrict_members'.
    The group owner and anonymous admins always pass."""
    if is_anonymous_admin(message):
        return True
    if not message.from_user:
        return False
    m = get_member(message.chat.id, message.from_user.id)
    if not m:
        return False
    if m.status == "creator":
        return True
    return m.status == "administrator" and bool(getattr(m, right, False))


def bot_has_right(chat_id, right: str) -> bool:
    m = get_member(chat_id, BOT.id)
    if not m:
        return False
    if m.status == "creator":
        return True
    return m.status == "administrator" and bool(getattr(m, right, False))


# ---------------------------------------------------------------- permissions
_PERM_NAMES = [
    "can_send_messages", "can_send_audios", "can_send_documents", "can_send_photos",
    "can_send_videos", "can_send_video_notes", "can_send_voice_notes", "can_send_polls",
    "can_send_other_messages", "can_add_web_page_previews", "can_change_info",
    "can_invite_users", "can_pin_messages", "can_manage_topics",
]


def make_permissions(allowed: bool) -> "types.ChatPermissions":
    """All-on or all-off ChatPermissions (only passes names this library version knows)."""
    known = set(inspect.signature(types.ChatPermissions.__init__).parameters)
    return types.ChatPermissions(**{n: allowed for n in _PERM_NAMES if n in known})


def default_permissions(chat_id):
    """The group's normal member permissions (what an unmuted member gets back)."""
    try:
        perms = bot.get_chat(chat_id).permissions
        if perms is not None:
            return perms
    except Exception:
        pass
    p = make_permissions(True)
    for n in ("can_change_info", "can_pin_messages", "can_manage_topics"):
        if hasattr(p, n):
            setattr(p, n, False)
    return p


# ---------------------------------------------------------------- user / chat tracking
USERNAMES = {}          # lower-case username -> user id
_known_users = {}       # user id -> first_name already saved this run
_known_chats = set()
_USERNAMES_LOADED = False


def _load_usernames():
    global _USERNAMES_LOADED
    if not _USERNAMES_LOADED:
        _USERNAMES_LOADED = True
        data = store.get("usernames", {}) or {}
        USERNAMES.update({k: v for k, v in data.items() if isinstance(v, int)})


def ensure_user(user_id: int, first_name: str = "", username: str = None) -> dict:
    """Make sure users/<id> exists (with the starting balance) and return it."""
    _load_usernames()
    with store.lock:
        rec = store.get(f"users/{user_id}", strict=True)
        if not isinstance(rec, dict):
            rec = {"name": first_name or "User", "balance": STARTING_BALANCE, "xp": 0}
            store.put(f"users/{user_id}", rec)
        elif first_name and rec.get("name") != first_name:
            rec["name"] = first_name
            store.patch(f"users/{user_id}", {"name": first_name})
    _known_users[user_id] = first_name
    if username:
        low = username.lower()
        if USERNAMES.get(low) != user_id:
            USERNAMES[low] = user_id
            store.put(f"usernames/{low}", user_id)
    return rec


def track(message):
    """Remember people and chats we see (for /broadcast, /stats, @username lookup)."""
    u = message.from_user
    if u and not u.is_bot and _known_users.get(u.id) != u.first_name:
        ensure_user(u.id, u.first_name, u.username)
    chat = message.chat
    if chat.id not in _known_chats:
        _known_chats.add(chat.id)
        if chat.type in GROUP_TYPES:
            store.patch(f"chats/{chat.id}", {"title": chat.title or "", "type": chat.type})
        else:
            pass


# ---------------------------------------------------------------- targets
class Target:
    """Minimal stand-in for a User we only know by id."""

    def __init__(self, user_id, first_name=None, username=None):
        self.id = user_id
        self.first_name = first_name or str(user_id)
        self.last_name = None
        self.username = username
        self.is_bot = False


def resolve_target(message, chat_id=None):
    """Who is this command about? Returns (user_or_None, remaining_args).
    Order: replied-to message, tapped mention, numeric id, @username."""
    chat_id = chat_id or message.chat.id
    args = list(getattr(message, "args", []) or [])
    reply_msg = message.reply_to_message
    if reply_msg is not None:
        u = reply_msg.from_user
        if u and u.id != ANON_ADMIN_ID:
            return u, args

    text = message.text or ""
    for ent in message.entities or []:
        if ent.type == "text_mention" and ent.user:
            rest = text[ent.offset + ent.length:].split()
            return ent.user, rest

    if args:
        first = args[0]
        uid = None
        if first.lstrip("-").isdigit():
            uid = int(first)
        elif first.startswith("@") and len(first) > 1:
            _load_usernames()
            uid = USERNAMES.get(first[1:].lower())
            if uid is None:
                try:
                    chat = bot.get_chat(first)
                    if getattr(chat, "type", "") == "private":
                        uid = chat.id
                except Exception:
                    uid = None
        if uid is not None:
            m = get_member(chat_id, uid) if message.chat.type in GROUP_TYPES else None
            return (m.user if m else Target(uid)), args[1:]
    return None, args


# ---------------------------------------------------------------- misc helpers
def parse_duration(text):
    """'30s' '10m' '2h' '1d' (or a bare number = minutes) -> seconds, or None."""
    if not text:
        return None
    t = text.strip().lower()
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    try:
        if t[-1] in units and t[:-1].isdigit():
            return int(t[:-1]) * units[t[-1]]
        if t.isdigit():
            return int(t) * 60
    except Exception:
        pass
    return None


def human_duration(seconds: int) -> str:
    seconds = int(seconds)
    for name, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= size:
            return f"{seconds // size}{name}"
    return f"{seconds}s"


def run_async(fn, *args, **kw):
    """Run something slow (database write, image work) without holding up the handler."""
    t = threading.Thread(target=fn, args=args, kwargs=kw, daemon=True)
    t.start()
    return t


# ---------------------------------------------------------------- router
COMMANDS = {}   # name -> (function, group_only, private_only)
HOOKS = []      # functions run on every group message; return True if the message was consumed
CALLBACKS = []  # (prefix, function)


def command(*names, group=False, private=False):
    def deco(fn):
        for n in names:
            COMMANDS[n] = (fn, group, private)
        return fn
    return deco


def hook(fn):
    HOOKS.append(fn)
    return fn


def callback(prefix):
    def deco(fn):
        CALLBACKS.append((prefix, fn))
        return fn
    return deco


def parse_command(message):
    """Returns the registered handler tuple for '/name' or '.name' messages, else None.
    Also sets message.cmd / message.rest / message.args."""
    text = message.text or ""
    if not text or text[0] not in "/.":
        return None
    parts = text.split(None, 1)
    head = parts[0][1:]
    if "@" in head:
        head, _, target = head.partition("@")
        if target.lower() != BOT_USERNAME.lower():
            return None
    head = head.lower()
    entry = COMMANDS.get(head)
    if entry is None:
        return None
    rest = parts[1].strip() if len(parts) > 1 else ""
    message.cmd, message.rest, message.args = head, rest, rest.split()
    return entry

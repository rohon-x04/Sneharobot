# ============================================================
# Welcome messages + welcome card picture
# Admin commands: /setwelcome /resetwelcome /welcome on|off /welcomecard on|off
# ============================================================

import io
import time

from core import (COPYRIGHT, bot, command, esc, full_name, log, mention, reply, send,
                  sender_is_admin, store)
from moderation import NOT_ADMIN

try:
    from welcome_styles import generate_random_welcome as generate_card
except Exception:  # Pillow missing -> text-only welcomes
    generate_card = None
    log.warning("Welcome card disabled (Pillow not available)", exc_info=True)

DEFAULT_WELCOME = (
    "🌸✨ ──────────────────── ✨🌸\n\n"
    "         🎊 ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴏᴜʀ ғᴀᴍɪʟʏ 🎊\n\n"
    "🌹 ɴᴀᴍᴇ ➤ {name}\n"
    "🌺 ᴜsᴇʀɴᴀᴍᴇ ➤ {username}\n"
    "🆔 ᴜsᴇʀ ɪᴅ ➤ {id}\n"
    "🏠 ɢʀᴏᴜᴘ ➤ {group}\n\n"
    "═════════════════════════"
)
PLACEHOLDERS = "{first_name} {name} {mention} {username} {id} {title} {group}"
CAPTION_LIMIT = 1000
_recent = {}


def _already(chat_id, user_id) -> bool:
    now = time.monotonic()
    for k in [k for k, t in _recent.items() if now - t > 30]:
        _recent.pop(k, None)
    seen = (chat_id, user_id) in _recent
    _recent[(chat_id, user_id)] = now
    return seen


def render(template: str, user, title: str) -> str:
    link = f'<a href="tg://user?id={user.id}">{esc(full_name(user))}</a>'
    values = dict(
        name=link,
        first_name=esc(user.first_name or "User"),
        mention=mention(user),
        username=f"@{esc(user.username)}" if user.username else "ɴᴏɴᴇ",
        id=user.id,
        title=esc(title or "this group"),
        group=esc(title or "this group"),
    )
    try:
        return template.format(**values)
    except Exception:
        return f"👋 Welcome {values['first_name']} to {values['title']}!"


def _avatar(user):
    try:
        photos = bot.get_user_profile_photos(user.id, limit=1)
        if photos.total_count and photos.photos:
            info = bot.get_file(photos.photos[0][-1].file_id)
            return bot.download_file(info.file_path)
    except Exception:
        log.debug("no avatar for %s", user.id, exc_info=True)
    return None


def make_card(user):
    if generate_card is None:
        return None
    try:
        username = f"@{user.username}" if user.username else None
        return generate_card(_avatar(user), full_name(user), user.id, username)
    except Exception:
        log.warning("welcome card failed for %s", user.id, exc_info=True)
        return None


def send_welcome(chat, user):
    if user.is_bot:
        return
    s = store.get(f"groups/{chat.id}/settings", {}, ttl=30) or {}
    if s.get("welcome_off"):
        return
    if _already(chat.id, user.id):
        return
    text = render(s.get("welcome_msg") or DEFAULT_WELCOME, user, chat.title)

    if not s.get("welcome_card_off"):
        card = make_card(user)
        if card is not None:
            try:
                if len(text) <= CAPTION_LIMIT:
                    bot.send_photo(chat.id, card, caption=text)
                else:
                    bot.send_photo(chat.id, card)
                    send(chat.id, text)
                return
            except Exception:
                log.warning("couldn't send welcome card, using text", exc_info=True)
    send(chat.id, text)


@command("setwelcome", group=True)
def setwelcome_cmd(message):
    if not sender_is_admin(message):
        return reply(message, NOT_ADMIN)
    text = message.rest
    if not text and message.reply_to_message:
        text = message.reply_to_message.text or message.reply_to_message.caption or ""
    if not text:
        return reply(message, "⚠️ Usage: /setwelcome &lt;text&gt;\nPlaceholders: " + esc(PLACEHOLDERS))
    store.patch(f"groups/{message.chat.id}/settings", {"welcome_msg": text})
    reply(message, "✅ Welcome message saved. Preview:")
    send(message.chat.id, render(text, message.from_user, message.chat.title))


@command("resetwelcome", group=True)
def resetwelcome_cmd(message):
    if not sender_is_admin(message):
        return reply(message, NOT_ADMIN)
    store.put(f"groups/{message.chat.id}/settings/welcome_msg", None)
    reply(message, "✅ Back to the default welcome message.")


def _switch(message, field_off, label):
    s = store.get(f"groups/{message.chat.id}/settings", {}, ttl=30) or {}
    if not message.args:
        return reply(message, f"{label} is currently {'OFF' if s.get(field_off) else 'ON'}.\n"
                              f"Usage: /{message.cmd} on | off")
    if not sender_is_admin(message):
        return reply(message, NOT_ADMIN)
    arg = message.args[0].lower()
    if arg not in ("on", "off"):
        return reply(message, f"⚠️ Usage: /{message.cmd} on | off")
    store.put(f"groups/{message.chat.id}/settings/{field_off}", True if arg == "off" else None)
    reply(message, f"✅ {label} turned {arg.upper()}.")


@command("welcome", group=True)
def welcome_cmd(message):
    _switch(message, "welcome_off", "Welcome messages")


@command("welcomecard", group=True)
def welcomecard_cmd(message):
    _switch(message, "welcome_card_off", "Welcome card picture")

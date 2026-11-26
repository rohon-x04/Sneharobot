# ============================================================
# Start/help menu, info & utility commands, /imagine, owner tools, group log
# ============================================================

import ast
import io
import operator
import os
import random
import threading
import time
from datetime import datetime, timezone
from urllib.parse import quote

import requests
from telebot import types

from core import (BOT, BOT_USERNAME, Btn, rainbow, COPYRIGHT, CURRENCY_NAME, GROUP_TYPES, LOG_CHAT_ID,
                  OWNER_USERNAME, POLLINATIONS_KEY, START_IMAGE, START_STICKER, SUPPORT_GROUP,
                  UPDATE_CHANNEL, bot, callback, command, delete, edit, esc, get_member, is_admin,
                  is_owner, log, mention, reply, resolve_target, send, sender_is_admin, store)

NOT_ADMIN = "❌ You need to be an admin to use this."

# ------------------------------------------------------------ /start and /help
LINE = "━━━━━━━━━━━━━━━━━━━━"


def _page(title, lines):
    body = "\n".join(lines)
    return f"╭{LINE}╮\n   {title}\n╰{LINE}╯\n\n{body}\n\n<i>{COPYRIGHT}</i>"


HELP_HOME = _page("📚 <b>ʜᴇʟᴘ ᴍᴇɴᴜ</b>", [
    "ᴄʜᴜɴᴏ ᴇᴋ ᴄᴀᴛᴇɢᴏʀʏ ɴᴇᴇᴄʜᴇ sᴇ 👇",
    "",
    "💬 ɢʀᴏᴜᴘ ᴍᴇɪɴ ᴍᴜᴊʜsᴇ ʙᴀᴀᴛ ᴋᴀʀɴᴇ ᴋᴇ ʟɪʏᴇ",
    "ᴍᴇʀᴀ ɴᴀᴀᴍ ʟᴏ, @ᴍᴇɴᴛɪᴏɴ ᴋᴀʀᴏ, ʏᴀ ʀᴇᴘʟʏ ᴋᴀʀᴏ 💕",
])

HELP_PAGES = {
    "mod": _page("🛡 <b>ᴍᴏᴅᴇʀᴀᴛɪᴏɴ</b> <i>(admins)</i>", [
        "➤ /kick /ban /unban — reply or @user",
        "➤ /mute [10m|2h|1d] · /unmute",
        "➤ /warn · /warns · /unwarn · /resetwarns",
        "➤ /setwarn &lt;n&gt; · /warnmode mute|kick|ban",
        "➤ /promote [1|2|3] · /demote",
        "➤ /pin · /unpin · /del · /purge"]),
    "guard": _page("🔐 <b>ᴘʀᴏᴛᴇᴄᴛɪᴏɴ</b> <i>(admins)</i>", [
        "➤ /lock · /unlock · /locks",
        "     url, sticker, media, username, forward",
        "➤ /setflood &lt;n&gt; · /noflood · /flood",
        "➤ /linkban on|off — delete links + warn",
        "➤ /spamban on|off — mute spammers"]),
    "welcome": _page("🪬 <b>ᴡᴇʟᴄᴏᴍᴇ</b> <i>(admins)</i>", [
        "➤ /setwelcome &lt;text&gt;",
        "     {first_name} {name} {mention} {username} {id} {group}",
        "➤ /resetwelcome",
        "➤ /welcome on|off",
        "➤ /welcomecard on|off — profile-photo card"]),
    "notes": _page("🧿 <b>ɴᴏᴛᴇs · ꜰɪʟᴛᴇʀs · ʀᴜʟᴇs</b>", [
        "➤ /save &lt;name&gt; &lt;text&gt; · /get · #name · /notes",
        "➤ /clear &lt;name&gt; · /clearall",
        "➤ /filter &lt;word&gt; &lt;reply&gt; · /filters · /stop · /stopall",
        "➤ /setrules · /rules · /clearrules",
        "➤ /afk [reason] — mark yourself away"]),
    "eco": _page(f"💸 <b>ᴇᴄᴏɴᴏᴍʏ</b> <i>({CURRENCY_NAME})</i>", [
        "➤ /balance · /daily",
        "➤ /give &lt;user&gt; &lt;amount&gt;",
        "➤ /rob (reply) · /leaderboard",
        "➤ /profile · /level · /toplevel"]),
    "games": _page("🎰 <b>ɢᴀᴍᴇs &amp; ꜰᴜɴ</b>", [
        "➤ /jackpot &lt;amount&gt;",
        "➤ /roulette &lt;amount&gt; &lt;bet&gt;",
        "➤ /mines &lt;amount&gt; [mines]",
        "➤ /roll · /flip · /8ball · /rps · /guess",
        "➤ /hug · /slap · /pat (reply) · /quote"]),
    "util": _page("🔮 <b>ᴜᴛɪʟɪᴛʏ</b>", [
        "➤ /id · /info · /adminlist · /chatinfo",
        "➤ /ping · /time · /calc &lt;expr&gt; · /report",
        "➤ /imagine &lt;prompt&gt; — AI picture 🎨",
        "➤ /reset — make me forget our chat",
        "➤ /stickerid — reply to a sticker"]),
}

# (button text, page key) - colours cycle blue / green / red
_CATEGORIES = [
    ("🛡 Moderation", "mod"), ("🔐 Protection", "guard"),
    ("🪬 Welcome", "welcome"), ("🧿 Notes & Rules", "notes"),
    ("💸 Economy", "eco"), ("🎰 Games", "games"),
]


def _home_markup():
    kb = types.InlineKeyboardMarkup()
    for i in range(0, len(_CATEGORIES), 2):
        kb.row(*[Btn(text, rainbow(i + j), callback_data=f"help:{page}")
                 for j, (text, page) in enumerate(_CATEGORIES[i:i + 2])])
    kb.row(Btn("🔮 Utility", "primary", callback_data="help:util"),
           Btn("🏠 Start", "success", callback_data="help:start"))
    return kb


def _start_text(user):
    return (f"╭{LINE}╮\n   🌸 <b>sɴᴇʜᴀ ʙᴏᴛ</b> 🌸\n╰{LINE}╯\n\n"
            f"ʜɪɪ <b>{esc(user.first_name)}</b>! 💕\n"
            "ᴍᴀɪɴ <b>Sneha</b> ʜᴏᴏɴ — ᴛᴜᴍʜᴀʀɪ ꜰʀɪᴇɴᴅʟʏ ʜɪɴɢʟɪsʜ ᴅᴏsᴛ 😊\n\n"
            "💬 ʙᴀᴀᴛᴇɪɴ · 🛡 ᴍᴏᴅᴇʀᴀᴛɪᴏɴ · 💸 ᴇᴄᴏɴᴏᴍʏ\n"
            "🎰 ɢᴀᴍᴇs · 🎨 ᴀɪ ᴘɪᴄᴛᴜʀᴇs · 🪬 ᴡᴇʟᴄᴏᴍᴇ ᴄᴀʀᴅs\n\n"
            f"👇 ʙᴜᴛᴛᴏɴs sᴇ ᴀᴀɢᴇ ʙᴀᴅʜᴏ\n\n<i>{COPYRIGHT}</i>")


def _start_markup():
    kb = Btn  # short name
    m = types.InlineKeyboardMarkup()
    m.row(kb("➕ Add me to your group", "primary",
             url=f"https://t.me/{BOT_USERNAME}?startgroup=true"))
    m.row(kb("📚 Help & Commands", "success", callback_data="help:home"))
    m.row(kb("🎰 Games", "danger", callback_data="help:games"),
          kb("💸 Economy", "primary", callback_data="help:eco"))
    links = []
    if SUPPORT_GROUP.startswith("http"):
        links.append(kb("💬 Support", "success", url=SUPPORT_GROUP))
    if UPDATE_CHANNEL.startswith("http"):
        links.append(kb("📢 Updates", "danger", url=UPDATE_CHANNEL))
    if OWNER_USERNAME:
        links.append(kb("👑 Owner", "primary", url=f"https://t.me/{OWNER_USERNAME}"))
    for i in range(0, len(links), 2):
        m.row(*links[i:i + 2])
    return m


_banner_file_id = None
BANNER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sneha-banner.png")


def _send_start_ui(chat_id, user):
    """Banner picture + text + coloured buttons. Falls back to plain text if anything fails."""
    global _banner_file_id
    text, markup = _start_text(user), _start_markup()
    photo = START_IMAGE or _banner_file_id
    try:
        if photo:
            bot.send_photo(chat_id, photo, caption=text, reply_markup=markup)
        elif os.path.exists(BANNER_PATH):
            with open(BANNER_PATH, "rb") as f:
                sent = bot.send_photo(chat_id, f, caption=text, reply_markup=markup)
            _banner_file_id = sent.photo[-1].file_id
        else:
            raise FileNotFoundError("no banner")
    except Exception:
        log.info("start banner not sent, using text", exc_info=True)
        send(chat_id, text, reply_markup=markup)


@command("start")
def start_cmd(message):
    if message.chat.type != "private":
        return reply(message, "Hii! 😊 Mujhse DM mein /start karo ya group mein mera naam lo.",
                     reply_markup=_group_start_markup())
    if START_STICKER:
        try:
            st = bot.send_sticker(message.chat.id, START_STICKER)
            time.sleep(3)
            delete(st)
        except Exception:
            pass
    _send_start_ui(message.chat.id, message.from_user)


def _group_start_markup():
    m = types.InlineKeyboardMarkup()
    m.row(Btn("💬 Chat in DM", "primary", url=f"https://t.me/{BOT_USERNAME}?start=hi"),
          Btn("📚 Help", "success", callback_data="help:home"))
    return m


@command("help")
def help_cmd(message):
    reply(message, HELP_HOME, reply_markup=_home_markup())


@callback("help:")
def help_cb(call):
    page = call.data.split(":", 1)[1]
    if page == "start":
        text, kb = _start_text(call.from_user), _start_markup()
    elif page == "home":
        text, kb = HELP_HOME, _home_markup()
    else:
        text = HELP_PAGES.get(page, HELP_HOME)
        kb = types.InlineKeyboardMarkup()
        kb.row(Btn("⬅️ Back", "danger", callback_data="help:home"),
               Btn("🏠 Menu", "success", callback_data="help:start"))
    try:
        if call.message.content_type == "text":
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        else:
            bot.edit_message_caption(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    except Exception:
        # "message is not modified" etc. - nothing to do
        pass
    bot.answer_callback_query(call.id)


# ------------------------------------------------------------ info commands
@command("id")
def id_cmd(message):
    lines = []
    r = message.reply_to_message
    if r and r.from_user:
        lines.append(f"👤 {esc(r.from_user.first_name)}: <code>{r.from_user.id}</code>")
    else:
        lines.append(f"👤 You: <code>{message.from_user.id}</code>")
    if message.chat.type != "private":
        lines.append(f"💬 Chat: <code>{message.chat.id}</code>")
    reply(message, "\n".join(lines))


@command("info", "whois")
def info_cmd(message):
    target, _ = resolve_target(message)
    target = target or message.from_user
    status = ""
    if message.chat.type in GROUP_TYPES:
        m = get_member(message.chat.id, target.id)
        if m:
            status = f"\n🎖 Status: {m.status}"
    reply(message,
          f"👤 <b>User info</b>\n"
          f"Name: {mention(target)}\n"
          f"ID: <code>{target.id}</code>\n"
          f"Username: {'@' + esc(target.username) if getattr(target, 'username', None) else 'none'}\n"
          f"Bot: {'yes' if getattr(target, 'is_bot', False) else 'no'}{status}")


@command("adminlist", "admins", group=True)
def adminlist_cmd(message):
    try:
        admins = bot.get_chat_administrators(message.chat.id)
    except Exception as e:
        return reply(message, f"❌ {esc(str(e))[:150]}")
    owner = [a for a in admins if a.status == "creator"]
    rest = [a for a in admins if a.status != "creator" and not a.user.is_bot]
    lines = [f"👮 <b>Admins of {esc(message.chat.title)}</b>"]
    for a in owner:
        lines.append(f"👑 {mention(a.user)}")
    for a in rest:
        lines.append(f"• {mention(a.user)}")
    reply(message, "\n".join(lines))


@command("chatinfo", group=True)
def chatinfo_cmd(message):
    try:
        count = bot.get_chat_member_count(message.chat.id)
    except Exception:
        count = "?"
    c = message.chat
    reply(message, f"💬 <b>{esc(c.title or '')}</b>\nID: <code>{c.id}</code>\nType: {c.type}\n"
                   f"Members: {count}\nUsername: {'@' + esc(c.username) if c.username else 'private'}")


@command("owner")
def owner_cmd(message):
    reply(message, f"👑 My owner: @{esc(OWNER_USERNAME)}")


# ------------------------------------------------------------ utility
@command("ping")
def ping_cmd(message):
    start = time.time()
    sent = reply(message, "🏓 Pinging...")
    edit(sent, f"🏓 Pong! {round((time.time() - start) * 1000, 1)} ms")


@command("time")
def time_cmd(message):
    reply(message, f"🕐 {datetime.now(timezone.utc).strftime('%d %B %Y, %H:%M UTC')}")


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
        ast.USub: operator.neg, ast.UAdd: operator.pos}


def safe_eval(expr: str):
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("exponent too large")
            return _OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ValueError("unsupported")
    return ev(ast.parse(expr.strip(), mode="eval"))


@command("calc")
def calc_cmd(message):
    if not message.rest:
        return reply(message, "⚠️ Usage: /calc 5+3*2")
    try:
        result = safe_eval(message.rest)
        reply(message, f"🧮 <code>{esc(message.rest)}</code> = <b>{result}</b>")
    except Exception:
        reply(message, "❌ Invalid expression. Use numbers and + - * / ** % ( )")


@command("echo", group=True)
def echo_cmd(message):
    if not sender_is_admin(message):
        return reply(message, NOT_ADMIN)
    if not message.rest:
        return reply(message, "⚠️ Usage: /echo &lt;text&gt;")
    delete(message)
    send(message.chat.id, message.rest)


@command("report", group=True)
def report_cmd(message):
    r = message.reply_to_message
    if not r:
        return reply(message, "⚠️ Reply to the message you want to report.")
    try:
        admins = [a.user for a in bot.get_chat_administrators(message.chat.id) if not a.user.is_bot]
    except Exception:
        admins = []
    pings = " ".join(mention(a) for a in admins) or "admins"
    reported = mention(r.from_user) if r.from_user else "Unknown"
    reason = esc(message.rest) if message.rest else "No reason given"
    reply(message, f"🚨 <b>Report</b>\n\n📢 From: {mention(message.from_user)}\n⚠️ Reported: {reported}\n"
                   f"📝 {reason}\n\n{pings}")


# ------------------------------------------------------------ /imagine
_img_lock = threading.Lock()
_img_last = 0.0
IMG_GAP = 16.0   # the free tier allows ~1 picture per 15 seconds


@command("imagine", "img")
def imagine_cmd(message):
    global _img_last
    prompt = message.rest
    if not prompt and message.reply_to_message:
        prompt = message.reply_to_message.text or message.reply_to_message.caption or ""
    if not prompt:
        return reply(message, "⚠️ Usage: /imagine &lt;what to draw&gt;")
    note = reply(message, "🎨 Drawing... thoda ruko 😊")
    try:
        bot.send_chat_action(message.chat.id, "upload_photo")
    except Exception:
        pass
    with _img_lock:
        wait = IMG_GAP - (time.time() - _img_last)
        if wait > 0:
            time.sleep(wait)
        _img_last = time.time()
        try:
            url = (f"https://image.pollinations.ai/prompt/{quote(prompt[:800], safe='')}"
                   f"?width=1024&height=1024&nologo=true&seed={random.randint(1, 999999)}")
            headers = {"Authorization": f"Bearer {POLLINATIONS_KEY}"} if POLLINATIONS_KEY else {}
            r = requests.get(url, headers=headers, timeout=90)
            ok = r.status_code == 200 and r.headers.get("content-type", "").startswith("image/")
        except Exception as e:
            log.warning("imagine failed: %s", e)
            ok = False
    if not ok:
        edit(note, "😕 Picture nahi ban payi, thodi der baad try karo.")
        return
    try:
        bot.send_photo(message.chat.id, io.BytesIO(r.content), caption=f"🎨 {esc(prompt[:200])}",
                       reply_to_message_id=message.message_id)
        delete(note)
    except Exception as e:
        log.warning("imagine send failed: %s", e)
        edit(note, "😕 Picture bhej nahi payi.")


# ------------------------------------------------------------ owner tools
@command("stats")
def stats_cmd(message):
    if not is_owner(message.from_user.id):
        return
    users = store.get("users", {}) or {}
    chats = store.get("chats", {}) or {}
    where = "Firebase" if store.remote else "local file (data is lost on redeploy!)"
    reply(message, f"📊 <b>Stats</b>\nUsers: {len(users)}\nGroups: {len(chats)}\nStorage: {where}")


@command("broadcast", private=True)
def broadcast_cmd(message):
    if not is_owner(message.from_user.id):
        return
    src = message.reply_to_message
    if not src and not message.rest:
        return reply(message, "⚠️ Reply to a message with /broadcast, or use /broadcast &lt;text&gt;")
    targets = [int(k) for k in (store.get("users", {}) or {})] + [int(k) for k in (store.get("chats", {}) or {})]
    ok = bad = 0
    status = reply(message, f"📣 Sending to {len(targets)} chats...")
    for cid in targets:
        try:
            if src:
                bot.copy_message(cid, src.chat.id, src.message_id)
            else:
                bot.send_message(cid, message.rest)
            ok += 1
        except Exception:
            bad += 1
        time.sleep(0.06)
    edit(status, f"📣 Broadcast done — delivered {ok}, failed {bad}.")


# ------------------------------------------------------------ group add/remove log
def membership_changed(update):
    """Handles my_chat_member updates: log to LOG_CHAT_ID and keep the group list tidy."""
    chat = update.chat
    if chat.type not in GROUP_TYPES:
        return
    old, new = update.old_chat_member.status, update.new_chat_member.status
    active = ("member", "administrator", "creator")
    if old not in active and new in active:
        store.patch(f"chats/{chat.id}", {"title": chat.title or "", "type": chat.type})
        kind = "➕ Added to a group"
    elif old in active and new not in active:
        store.delete(f"chats/{chat.id}")
        kind = "➖ Removed from a group"
    else:
        return
    if not LOG_CHAT_ID:
        return
    who = update.from_user
    try:
        count = bot.get_chat_member_count(chat.id)
    except Exception:
        count = "?"
    send(LOG_CHAT_ID,
         f"{kind}\n\n🏷 {esc(chat.title or '')}\n🆔 <code>{chat.id}</code>\n"
         f"🔗 {'@' + esc(chat.username) if chat.username else 'Private'}\n👥 Members: {count}\n"
         f"👤 By: {mention(who)} (<code>{who.id}</code>)")

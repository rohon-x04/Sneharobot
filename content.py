# ============================================================
# Group content: rules, notes (#name), filters (auto-replies), AFK
# ============================================================

import re
import time

from core import (USERNAMES, bot, command, esc, hook, mention, reply, sender_is_admin, store,
                  _load_usernames)
from store import key
from moderation import NOT_ADMIN


# ------------------------------------------------------------ rules
@command("setrules", group=True)
def setrules_cmd(message):
    if not sender_is_admin(message):
        return reply(message, NOT_ADMIN)
    text = message.rest
    if not text and message.reply_to_message:
        text = message.reply_to_message.text or message.reply_to_message.caption or ""
    if not text:
        return reply(message, "⚠️ Usage: /setrules &lt;text&gt; (or reply to a message)")
    store.put(f"groups/{message.chat.id}/rules", text)
    reply(message, "✅ Group rules saved.")


@command("rules", group=True)
def rules_cmd(message):
    text = store.get(f"groups/{message.chat.id}/rules")
    reply(message, f"📜 <b>Group rules</b>\n\n{text}" if text else "📜 No rules have been set yet.")


@command("clearrules", group=True)
def clearrules_cmd(message):
    if not sender_is_admin(message):
        return reply(message, NOT_ADMIN)
    store.delete(f"groups/{message.chat.id}/rules")
    reply(message, "✅ Rules cleared.")


# ------------------------------------------------------------ notes
def _notes(chat_id) -> dict:
    return store.get(f"groups/{chat_id}/notes", {}, ttl=30) or {}


@command("save", group=True)
def save_cmd(message):
    if not sender_is_admin(message):
        return reply(message, NOT_ADMIN)
    if not message.args:
        return reply(message, "⚠️ Usage: /save &lt;name&gt; &lt;text&gt; (or reply to a message with /save &lt;name&gt;)")
    name = message.args[0].lower().lstrip("#")
    parts = message.rest.split(None, 1)
    text = parts[1] if len(parts) > 1 else ""
    if not text and message.reply_to_message:
        text = message.reply_to_message.text or message.reply_to_message.caption or ""
    if not text:
        return reply(message, "⚠️ Give the note some text, or reply to a message.")
    store.put(f"groups/{message.chat.id}/notes/{key(name)}", {"name": name, "text": text})
    reply(message, f"✅ Note <b>{esc(name)}</b> saved. Get it with /get {esc(name)} or #{esc(name)}")


def _send_note(message, name):
    note = _notes(message.chat.id).get(key(name.lower()))
    if not note:
        return False
    reply(message, note["text"])
    return True


@command("get", group=True)
def get_cmd(message):
    if not message.args:
        return reply(message, "⚠️ Usage: /get &lt;name&gt;")
    if not _send_note(message, message.args[0].lstrip("#")):
        reply(message, "❌ No note with that name.")


@command("notes", group=True)
def notes_cmd(message):
    names = sorted(n["name"] for n in _notes(message.chat.id).values())
    if not names:
        return reply(message, "📒 No notes saved in this group.")
    reply(message, "📒 <b>Notes</b>\n" + "\n".join(f"• #{esc(n)}" for n in names))


@command("clear", group=True)
def clear_cmd(message):
    if not sender_is_admin(message):
        return reply(message, NOT_ADMIN)
    if not message.args:
        return reply(message, "⚠️ Usage: /clear &lt;name&gt;")
    name = message.args[0].lower().lstrip("#")
    if key(name) not in _notes(message.chat.id):
        return reply(message, "❌ No note with that name.")
    store.delete(f"groups/{message.chat.id}/notes/{key(name)}")
    reply(message, f"🗑️ Note {esc(name)} deleted.")


@command("clearall", group=True)
def clearall_cmd(message):
    if not sender_is_admin(message):
        return reply(message, NOT_ADMIN)
    store.delete(f"groups/{message.chat.id}/notes")
    reply(message, "🗑️ All notes deleted.")


# ------------------------------------------------------------ filters
def _filters(chat_id) -> dict:
    return store.get(f"groups/{chat_id}/filters", {}, ttl=30) or {}


def _split_filter(rest: str):
    """'word reply...'  or  '"two words" reply...' -> (word, reply)"""
    rest = rest.strip()
    if rest[:1] in ('"', "'", "“"):
        closers = [i for i in (rest.find('"', 1), rest.find("'", 1), rest.find("”", 1)) if i > 0]
        if closers:
            close = min(closers)
            return rest[1:close].strip(), rest[close + 1:].strip()
    parts = rest.split(None, 1)
    return (parts[0], parts[1] if len(parts) > 1 else "") if parts else ("", "")


@command("filter", group=True)
def filter_cmd(message):
    if not sender_is_admin(message):
        return reply(message, NOT_ADMIN)
    word, answer = _split_filter(message.rest)
    if not answer and message.reply_to_message:
        answer = message.reply_to_message.text or message.reply_to_message.caption or ""
    if not word or not answer:
        return reply(message, "⚠️ Usage: /filter &lt;word&gt; &lt;reply&gt; (use quotes for several words)")
    word = word.lower()
    store.put(f"groups/{message.chat.id}/filters/{key(word)}", {"word": word, "reply": answer})
    reply(message, f"✅ Filter added for <b>{esc(word)}</b>.")


@command("filters", group=True)
def filters_cmd(message):
    words = sorted(f["word"] for f in _filters(message.chat.id).values())
    if not words:
        return reply(message, "🧲 No filters set in this group.")
    reply(message, "🧲 <b>Filters</b>\n" + "\n".join(f"• {esc(w)}" for w in words))


@command("stop", group=True)
def stop_cmd(message):
    if not sender_is_admin(message):
        return reply(message, NOT_ADMIN)
    if not message.rest:
        return reply(message, "⚠️ Usage: /stop &lt;word&gt;")
    word = message.rest.strip('"\'“” ').lower()
    if key(word) not in _filters(message.chat.id):
        return reply(message, "❌ No filter with that word.")
    store.delete(f"groups/{message.chat.id}/filters/{key(word)}")
    reply(message, f"🗑️ Filter {esc(word)} removed.")


@command("stopall", group=True)
def stopall_cmd(message):
    if not sender_is_admin(message):
        return reply(message, NOT_ADMIN)
    store.delete(f"groups/{message.chat.id}/filters")
    reply(message, "🗑️ All filters removed.")


@hook
def triggers(message) -> bool:
    """#note and filter words. Never consumes the message."""
    text = message.text
    if not text or text[0] in "/.":
        return False
    if text.startswith("#") and len(text) > 1:
        _send_note(message, text[1:].split()[0])
        return False
    flt = _filters(message.chat.id)
    if flt:
        low = text.lower()
        for f in flt.values():
            if re.search(r"(?<!\w)" + re.escape(f["word"]) + r"(?!\w)", low):
                reply(message, f["reply"])
                break
    return False


# ------------------------------------------------------------ AFK
AFK = {}
_afk_loaded = False


def _load_afk():
    global _afk_loaded
    if not _afk_loaded:
        _afk_loaded = True
        for k, v in (store.get("afk", {}) or {}).items():
            if isinstance(v, dict):
                AFK[int(k)] = v


@command("afk", "brb")
def afk_cmd(message):
    _load_afk()
    reason = message.rest or "No reason given"
    AFK[message.from_user.id] = {"reason": reason, "t": time.time()}
    store.put(f"afk/{message.from_user.id}", AFK[message.from_user.id])
    reply(message, f"😴 {mention(message.from_user)} is now AFK.\n📝 {esc(reason)}")


@hook
def afk_watch(message) -> bool:
    _load_afk()
    if not AFK or not message.from_user:
        return False
    text = message.text or message.caption or ""
    uid = message.from_user.id
    cmd_word = text.split(None, 1)[0].lower().split("@")[0] if text else ""
    if uid in AFK and cmd_word not in ("/afk", "/brb", ".afk", ".brb"):
        AFK.pop(uid, None)
        store.delete(f"afk/{uid}")
        reply(message, f"👋 {mention(message.from_user)} is back!")
        return False

    # someone mentions / replies to an AFK person
    hit = None
    r = message.reply_to_message
    if r and r.from_user and r.from_user.id in AFK:
        hit = r.from_user
    else:
        _load_usernames()
        for ent in (message.entities or []):
            if ent.type == "mention":
                uname = text[ent.offset + 1: ent.offset + ent.length].lower()
                tid = USERNAMES.get(uname)
                if tid in AFK:
                    hit = type("U", (), {"id": tid, "first_name": uname})()
                    break
            elif ent.type == "text_mention" and ent.user and ent.user.id in AFK:
                hit = ent.user
                break
    if hit:
        info = AFK[hit.id]
        reply(message, f"😴 {mention(hit)} is AFK.\n📝 {esc(info.get('reason', 'No reason given'))}")
    return False

# ============================================================
# Moderation: kick ban unban mute unmute warn warns resetwarns unwarn setwarn warnmode
#             promote demote pin unpin del purge
# ============================================================

import time

from telebot import types

from core import (BOT, bot, bot_has_right, command, default_permissions, esc, forget_member,
                  human_duration, is_admin, make_permissions, mention, parse_duration, reply,
                  resolve_target, send, sender_has_right, sender_is_admin, store, delete,
                  ApiTelegramException)

NOT_ADMIN = "❌ You need to be an admin to use this."


def _gate(message, right):
    """Common checks. Returns True when the command may go ahead."""
    if not sender_has_right(message, right):
        if sender_is_admin(message):
            need = right.replace("can_", "").replace("_", " ")
            reply(message, f"❌ You don't have the <b>{need}</b> admin right.")
        else:
            reply(message, NOT_ADMIN)
        return False
    if not bot_has_right(message.chat.id, right):
        need = right.replace("can_", "").replace("_", " ")
        reply(message, f"❌ I need the <b>{need}</b> admin right to do that.")
        return False
    return True


def _target(message, allow_admin=False):
    """Resolve and sanity-check the user a command is aimed at."""
    target, rest = resolve_target(message)
    if target is None:
        reply(message, "⚠️ Reply to a user, or give a @username / user id.")
        return None, rest
    if target.id == BOT.id:
        reply(message, "😅 Nice try - I can't do that to myself.")
        return None, rest
    if not allow_admin and is_admin(message.chat.id, target.id):
        reply(message, "❌ I can't do that to an admin.")
        return None, rest
    return target, rest


def _fail(message, e):
    reply(message, f"❌ Failed: {esc(str(e))[:200]}")


# ------------------------------------------------------------ kick / ban / mute
@command("kick", group=True)
def kick_cmd(message):
    if not _gate(message, "can_restrict_members"):
        return
    target, _ = _target(message)
    if not target:
        return
    try:
        bot.ban_chat_member(message.chat.id, target.id)
        bot.unban_chat_member(message.chat.id, target.id, only_if_banned=True)
        reply(message, f"👢 {mention(target)} has been kicked.")
    except ApiTelegramException as e:
        _fail(message, e)


@command("ban", group=True)
def ban_cmd(message):
    if not _gate(message, "can_restrict_members"):
        return
    target, rest = _target(message)
    if not target:
        return
    try:
        bot.ban_chat_member(message.chat.id, target.id)
        reason = f"\n📝 {esc(' '.join(rest))}" if rest else ""
        reply(message, f"🔨 {mention(target)} has been banned.{reason}")
    except ApiTelegramException as e:
        _fail(message, e)


@command("unban", group=True)
def unban_cmd(message):
    if not _gate(message, "can_restrict_members"):
        return
    target, _ = _target(message, allow_admin=True)
    if not target:
        return
    try:
        bot.unban_chat_member(message.chat.id, target.id, only_if_banned=True)
        reply(message, f"✅ {mention(target)} has been unbanned.")
    except ApiTelegramException as e:
        _fail(message, e)


def mute_user(chat_id, user_id, seconds=None):
    until = int(time.time() + seconds) if seconds else None
    bot.restrict_chat_member(chat_id, user_id, until_date=until, permissions=make_permissions(False))


@command("mute", group=True)
def mute_cmd(message):
    if not _gate(message, "can_restrict_members"):
        return
    target, rest = _target(message)
    if not target:
        return
    seconds = parse_duration(rest[0]) if rest else None
    try:
        mute_user(message.chat.id, target.id, seconds)
        when = f" for {human_duration(seconds)}" if seconds else ""
        reply(message, f"🔇 {mention(target)} has been muted{when}.")
    except ApiTelegramException as e:
        _fail(message, e)


@command("unmute", group=True)
def unmute_cmd(message):
    if not _gate(message, "can_restrict_members"):
        return
    target, _ = _target(message, allow_admin=True)
    if not target:
        return
    try:
        bot.restrict_chat_member(message.chat.id, target.id, permissions=default_permissions(message.chat.id))
        reply(message, f"🔊 {mention(target)} can talk again.")
    except ApiTelegramException as e:
        _fail(message, e)


# ------------------------------------------------------------ warnings
def warn_limit(chat_id) -> int:
    s = store.get(f"groups/{chat_id}/settings", {}, ttl=30) or {}
    return int(s.get("warn_limit") or 3)


def warn_mode(chat_id) -> str:
    s = store.get(f"groups/{chat_id}/settings", {}, ttl=30) or {}
    return s.get("warn_mode") or "mute"


def add_warn(chat_id, user_id) -> int:
    return store.incr(f"warns/{chat_id}/{user_id}", 1)


def punish_for_warns(chat_id, user) -> str:
    """Apply the group's warn action once the limit is reached. Returns a message."""
    mode = warn_mode(chat_id)
    store.delete(f"warns/{chat_id}/{user.id}")
    try:
        if mode == "ban":
            bot.ban_chat_member(chat_id, user.id)
            return f"🔨 {mention(user)} reached the warning limit and has been banned."
        if mode == "kick":
            bot.ban_chat_member(chat_id, user.id)
            bot.unban_chat_member(chat_id, user.id, only_if_banned=True)
            return f"👢 {mention(user)} reached the warning limit and has been kicked."
        mute_user(chat_id, user.id)
        return f"🔇 {mention(user)} reached the warning limit and has been muted."
    except ApiTelegramException as e:
        return f"❌ Couldn't punish {mention(user)} after the last warning: {esc(str(e))[:150]}"


@command("warn", group=True)
def warn_cmd(message):
    if not _gate(message, "can_restrict_members"):
        return
    target, rest = _target(message)
    if not target:
        return
    count = add_warn(message.chat.id, target.id)
    limit = warn_limit(message.chat.id)
    if count >= limit:
        reply(message, punish_for_warns(message.chat.id, target))
    else:
        reason = f"\n📝 {esc(' '.join(rest))}" if rest else ""
        reply(message, f"⚠️ {mention(target)} has been warned ({count}/{limit}).{reason}")


@command("warns", group=True)
def warns_cmd(message):
    target, _ = resolve_target(message)
    target = target or message.from_user
    count = store.get(f"warns/{message.chat.id}/{target.id}", 0) or 0
    reply(message, f"⚠️ {mention(target)} has {count}/{warn_limit(message.chat.id)} warnings.")


@command("unwarn", group=True)
def unwarn_cmd(message):
    if not sender_is_admin(message):
        return reply(message, NOT_ADMIN)
    target, _ = _target(message, allow_admin=True)
    if not target:
        return
    left = store.incr(f"warns/{message.chat.id}/{target.id}", -1, floor=0)
    if left is None:
        return reply(message, f"✅ {mention(target)} has no warnings.")
    reply(message, f"✅ Removed a warning from {mention(target)} ({left}/{warn_limit(message.chat.id)}).")


@command("resetwarns", group=True)
def resetwarns_cmd(message):
    if not sender_is_admin(message):
        return reply(message, NOT_ADMIN)
    target, _ = _target(message, allow_admin=True)
    if not target:
        return
    store.delete(f"warns/{message.chat.id}/{target.id}")
    reply(message, f"✅ Warnings cleared for {mention(target)}.")


@command("setwarn", group=True)
def setwarn_cmd(message):
    if not sender_is_admin(message):
        return reply(message, NOT_ADMIN)
    if not message.args or not message.args[0].isdigit() or not (1 <= int(message.args[0]) <= 20):
        return reply(message, "⚠️ Usage: /setwarn &lt;1-20&gt;")
    store.patch(f"groups/{message.chat.id}/settings", {"warn_limit": int(message.args[0])})
    reply(message, f"✅ Warn limit set to {int(message.args[0])}.")


@command("warnmode", group=True)
def warnmode_cmd(message):
    if not sender_is_admin(message):
        return reply(message, NOT_ADMIN)
    if not message.args or message.args[0].lower() not in ("mute", "kick", "ban"):
        return reply(message, f"⚠️ Usage: /warnmode mute | kick | ban\nCurrent: {warn_mode(message.chat.id)}")
    mode = message.args[0].lower()
    store.patch(f"groups/{message.chat.id}/settings", {"warn_mode": mode})
    past = {"mute": "muted", "kick": "kicked", "ban": "banned"}[mode]
    reply(message, f"✅ At the warn limit, members will now be {past}.")


# ------------------------------------------------------------ promote / demote
TIERS = {
    1: ("Junior Admin", dict(can_delete_messages=True, can_invite_users=True, can_pin_messages=True)),
    2: ("Senior Admin", dict(can_delete_messages=True, can_restrict_members=True,
                             can_promote_members=True, can_invite_users=True)),
    3: ("Head Admin", dict(can_delete_messages=True, can_restrict_members=True,
                           can_promote_members=True, can_invite_users=True, can_pin_messages=True)),
}
ALL_RIGHTS = ("can_change_info", "can_delete_messages", "can_invite_users", "can_restrict_members",
              "can_pin_messages", "can_promote_members", "can_manage_video_chats")


@command("promote", group=True)
def promote_cmd(message):
    if not _gate(message, "can_promote_members"):
        return
    target, rest = _target(message, allow_admin=True)
    if not target:
        return
    tier = next((int(a) for a in (message.args or []) if a in ("1", "2", "3")), 1)
    label, rights = TIERS[tier]
    perms = {r: rights.get(r, False) for r in ALL_RIGHTS}
    try:
        bot.promote_chat_member(message.chat.id, target.id, is_anonymous=False,
                                can_manage_chat=False, **perms)
        forget_member(message.chat.id, target.id)
        reply(message, f"⬆️ {mention(target)} is now a <b>{label}</b> (tier {tier}).")
    except ApiTelegramException as e:
        _fail(message, e)


@command("demote", group=True)
def demote_cmd(message):
    if not _gate(message, "can_promote_members"):
        return
    target, _ = _target(message, allow_admin=True)
    if not target:
        return
    m = bot.get_chat_member(message.chat.id, target.id)
    if m.status == "creator":
        return reply(message, "❌ Can't demote the group owner.")
    if m.status != "administrator":
        return reply(message, f"⚠️ {mention(target)} isn't an admin here.")
    try:
        bot.promote_chat_member(message.chat.id, target.id, is_anonymous=False, can_manage_chat=False,
                                **{r: False for r in ALL_RIGHTS})
        forget_member(message.chat.id, target.id)
        reply(message, f"⬇️ {mention(target)} has been demoted.")
    except ApiTelegramException as e:
        _fail(message, e)


# ------------------------------------------------------------ pin / del / purge
@command("pin", group=True)
def pin_cmd(message):
    if not _gate(message, "can_pin_messages"):
        return
    if not message.reply_to_message:
        return reply(message, "⚠️ Reply to the message you want to pin.")
    loud = bool(message.args and message.args[0].lower() in ("loud", "notify"))
    try:
        bot.pin_chat_message(message.chat.id, message.reply_to_message.message_id,
                             disable_notification=not loud)
        reply(message, "📌 Pinned.")
    except ApiTelegramException as e:
        _fail(message, e)


@command("unpin", group=True)
def unpin_cmd(message):
    if not _gate(message, "can_pin_messages"):
        return
    try:
        if message.reply_to_message:
            bot.unpin_chat_message(message.chat.id, message.reply_to_message.message_id)
        else:
            bot.unpin_chat_message(message.chat.id)
        reply(message, "📌 Unpinned.")
    except ApiTelegramException as e:
        _fail(message, e)


@command("del", group=True)
def del_cmd(message):
    if not _gate(message, "can_delete_messages"):
        return
    if not message.reply_to_message:
        return reply(message, "⚠️ Reply to the message you want to delete.")
    try:
        bot.delete_message(message.chat.id, message.reply_to_message.message_id)
    except ApiTelegramException as e:
        return _fail(message, e)
    delete(message)


@command("purge", group=True)
def purge_cmd(message):
    if not _gate(message, "can_delete_messages"):
        return
    if not message.reply_to_message:
        return reply(message, "⚠️ Reply to the first message you want to delete - everything from there to your command goes.")
    start, end = message.reply_to_message.message_id, message.message_id
    if end - start > 500:
        return reply(message, "⚠️ That's too many messages at once (limit 500).")
    ids = list(range(start, end + 1))
    removed = 0
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        try:
            bot.delete_messages(message.chat.id, chunk)
            removed += len(chunk)
        except Exception:
            for mid in chunk:
                try:
                    bot.delete_message(message.chat.id, mid)
                    removed += 1
                except Exception:
                    pass
    note = send(message.chat.id, f"🧹 Purged {removed} messages.")
    if note:
        time.sleep(3)
        delete(note)

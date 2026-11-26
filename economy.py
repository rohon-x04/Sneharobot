# ============================================================
# Economy + levels: balance daily give rob leaderboard profile level toplevel
# ============================================================

import datetime
import random
import time

from core import (CURRENCY_EMOJI, CURRENCY_NAME, DAILY_REWARD, DAILY_ROB_LIMIT, ROB_COOLDOWN_MIN,
                  command, ensure_user, esc, mention, money, reply, resolve_target, store)


# ------------------------------------------------------------ helpers
def balance(uid) -> int:
    return int((store.get(f"users/{uid}/balance", 0)) or 0)


def credit(uid, amount: int):
    """Add money. Retries a few times so a database blip can't swallow a winner's payout."""
    if not amount:
        return
    for attempt in range(4):
        try:
            store.incr(f"users/{uid}/balance", amount)
            return
        except Exception:
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"could not credit {amount} to {uid}")


def spend(user, amount: int) -> bool:
    """Take `amount` from the wallet if the user can afford it."""
    ensure_user(user.id, user.first_name, user.username)
    return store.incr(f"users/{user.id}/balance", -amount, floor=0) is not None


def level_from_xp(xp: int):
    """-> (level, xp into this level, xp needed for next level)"""
    level, threshold, need = 1, 0, 100
    while xp >= threshold + need:
        threshold += need
        level += 1
        need = 100 * level
    return level, xp - threshold, need


def bar(current, total, length=10):
    filled = max(0, min(length, int(length * current / total) if total else 0))
    return "█" * filled + "░" * (length - filled)


def grant_xp(message, uid, amount):
    old = int(store.get(f"users/{uid}/xp", 0) or 0)
    new = store.incr(f"users/{uid}/xp", amount)
    if new is not None and level_from_xp(new)[0] > level_from_xp(old)[0]:
        reply(message, f"🎉 <b>Level up!</b> You're now <b>Level {level_from_xp(new)[0]}</b>!")


def _all_users():
    users = store.get("users", {}, ttl=30) or {}
    return [dict(v, id=k) for k, v in users.items() if isinstance(v, dict)]


def _rank(uid) -> int:
    ranked = sorted(_all_users(), key=lambda u: u.get("balance", 0), reverse=True)
    for i, u in enumerate(ranked, 1):
        if str(u["id"]) == str(uid):
            return i
    return len(ranked) + 1


def _who(message):
    target, rest = resolve_target(message)
    target = target or message.from_user
    ensure_user(target.id, target.first_name, getattr(target, "username", None))
    return target, rest


# ------------------------------------------------------------ commands
@command("balance", "bal")
def balance_cmd(message):
    t, _ = _who(message)
    rec = store.get(f"users/{t.id}", {}) or {}
    level, _, _ = level_from_xp(int(rec.get("xp", 0)))
    reply(message,
          f"👤 <b>Name:</b> {esc(t.first_name)}\n"
          f"💰 <b>Balance:</b> {money(int(rec.get('balance', 0)))}\n"
          f"🏆 <b>Global rank:</b> {_rank(t.id)}\n"
          f"🌟 <b>Level:</b> {level} ({int(rec.get('xp', 0))} XP)")


@command("daily")
def daily_cmd(message):
    u = message.from_user
    ensure_user(u.id, u.first_name, u.username)
    with store.lock:
        last = float(store.get(f"users/{u.id}/last_daily", 0) or 0)
        left = 86400 - (time.time() - last)
        if left > 0:
            return reply(message, f"⏳ Already claimed. Try again in {int(left // 3600)}h {int(left % 3600 // 60)}m.")
        store.put(f"users/{u.id}/last_daily", time.time())
        credit(u.id, DAILY_REWARD)
    reply(message, f"🎁 You claimed your daily {money(DAILY_REWARD)}! (+50 XP)")
    grant_xp(message, u.id, 50)


@command("give", "pay")
def give_cmd(message):
    sender = message.from_user
    target, rest = resolve_target(message)
    if not target or not rest or not rest[0].isdigit():
        return reply(message, "⚠️ Usage: /give &lt;user&gt; &lt;amount&gt; (or reply with /give &lt;amount&gt;)")
    amount = int(rest[0])
    if amount <= 0:
        return reply(message, "⚠️ Amount must be positive.")
    if target.id == sender.id:
        return reply(message, f"❌ You can't send {CURRENCY_NAME} to yourself.")
    ensure_user(target.id, target.first_name, getattr(target, "username", None))
    if not spend(sender, amount):
        return reply(message, f"❌ You don't have enough {CURRENCY_NAME}.")
    fee = amount // 10
    credit(target.id, amount - fee)
    reply(message, f"✅ {mention(sender)} sent {amount:,} {CURRENCY_EMOJI} to {mention(target)}!\n"
                   f"💸 10% fee applied — {mention(target)} received {amount - fee:,} {CURRENCY_EMOJI}.")


@command("rob")
def rob_cmd(message):
    robber = message.from_user
    r = message.reply_to_message
    if not r or not r.from_user:
        return reply(message, "⚠️ Reply to the user you want to rob.")
    victim = r.from_user
    if victim.id == robber.id:
        return reply(message, "❌ You can't rob yourself.")
    if victim.is_bot:
        return reply(message, "🤖 Bots keep their money in a very safe place.")
    ensure_user(robber.id, robber.first_name, robber.username)
    ensure_user(victim.id, victim.first_name, victim.username)

    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    with store.lock:
        rec = store.get(f"users/{robber.id}", {}) or {}
        count = rec.get("rob_count", 0) if rec.get("rob_day") == today else 0
        if count >= DAILY_ROB_LIMIT:
            return reply(message, f"🚫 You've hit today's rob limit ({DAILY_ROB_LIMIT}). Try again tomorrow.")
        wait = ROB_COOLDOWN_MIN * 60 - (time.time() - float(rec.get("last_rob", 0)))
        if wait > 0:
            return reply(message, f"⏳ You're on cooldown. Try again in ~{int(wait // 60) + 1} min.")
        store.patch(f"users/{robber.id}", {"last_rob": time.time(), "rob_day": today, "rob_count": count + 1})

    vbal = balance(victim.id)
    if vbal < 20:
        return reply(message, f"💸 {mention(victim)} is too broke to rob.")

    if random.random() < 0.45:
        stolen = min(vbal, random.randint(10, max(11, vbal // 3)))
        if store.incr(f"users/{victim.id}/balance", -stolen, floor=0) is None:
            return reply(message, f"💸 {mention(victim)} is too broke to rob.")
        credit(robber.id, stolen)
        xp = random.randint(10, 50)
        reply(message, f"🦹 {mention(robber)} robbed {stolen:,} {CURRENCY_EMOJI} from {mention(victim)}! (+{xp} XP)")
        grant_xp(message, robber.id, xp)
    else:
        fine = random.randint(10, 50)
        store.incr(f"users/{robber.id}/balance", -fine, floor=0)
        reply(message, f"🚓 {mention(robber)} got caught robbing {mention(victim)} and paid a {fine} {CURRENCY_EMOJI} fine!")


@command("leaderboard", "gleaderboard", "top")
def leaderboard_cmd(message):
    ranked = sorted(_all_users(), key=lambda u: u.get("balance", 0), reverse=True)[:10]
    if not ranked:
        return reply(message, f"No one has any {CURRENCY_NAME} yet!")
    lines = [f"🏆 <b>{CURRENCY_NAME} Leaderboard</b>"]
    for i, u in enumerate(ranked, 1):
        lines.append(f"{i}. {esc(u.get('name', 'Unknown'))} — {int(u.get('balance', 0)):,} {CURRENCY_EMOJI}")
    reply(message, "\n".join(lines))


@command("profile")
def profile_cmd(message):
    t, _ = _who(message)
    rec = store.get(f"users/{t.id}", {}) or {}
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    robs = rec.get("rob_count", 0) if rec.get("rob_day") == today else 0
    level, into, need = level_from_xp(int(rec.get("xp", 0)))
    reply(message,
          f"👤 <b>{esc(t.first_name)}</b>\n"
          f"💰 Wallet: {money(int(rec.get('balance', 0)))}\n"
          f"🏆 Rank: {_rank(t.id)}\n"
          f"🌟 Level {level} — {bar(into, need)} {into}/{need} XP\n"
          f"🦹 Robs today: {robs}/{DAILY_ROB_LIMIT}")


@command("level", "lvl")
def level_cmd(message):
    t, _ = _who(message)
    xp = int(store.get(f"users/{t.id}/xp", 0) or 0)
    level, into, need = level_from_xp(xp)
    reply(message, f"👤 <b>{esc(t.first_name)}</b>\n🌟 <b>Level:</b> {level}\n✨ <b>Total XP:</b> {xp}\n"
                   f"📊 {bar(into, need)} {into}/{need} XP to Level {level + 1}")


@command("toplevel", "levels", "levelboard")
def toplevel_cmd(message):
    ranked = [u for u in sorted(_all_users(), key=lambda u: u.get("xp", 0), reverse=True)[:10] if u.get("xp", 0) > 0]
    if not ranked:
        return reply(message, "No one has earned XP yet — try /daily or /rob to start levelling up!")
    lines = ["🌟 <b>XP Leaderboard</b>"]
    for i, u in enumerate(ranked, 1):
        lines.append(f"{i}. {esc(u.get('name', 'Unknown'))} — Level {level_from_xp(int(u['xp']))[0]} ({int(u['xp'])} XP)")
    reply(message, "\n".join(lines))

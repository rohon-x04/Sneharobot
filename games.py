# ============================================================
# Fun + games: roll flip 8ball quote hug slap pat rps guess
# Casino: jackpot roulette mines   (wagers use the economy balance)
# ============================================================

import random
import threading
import time

from telebot import types

from core import (Btn, CURRENCY_EMOJI, CURRENCY_NAME, bot, callback, command, edit, ensure_user, esc,
                  mention, money, reply)
from economy import credit, spend

EIGHT_BALL = [
    "Yes, definitely.", "It is certain.", "Without a doubt.", "Ask again later.",
    "Cannot predict now.", "Don't count on it.", "My sources say no.",
    "Outlook not so good.", "Very doubtful.", "Signs point to yes.",
]
QUOTES = [
    "The only way to do great work is to love what you do.",
    "Life is what happens when you're busy making other plans.",
    "It always seems impossible until it's done.",
    "The best time to plant a tree was 20 years ago. The second best time is now.",
    "Do or do not. There is no try.",
]
ACTIONS = {
    "hug": "🤗 {a} hugs {b}!",
    "slap": "👋 {a} slaps {b}!",
    "pat": "🖐️ {a} pats {b} gently.",
}


@command("roll")
def roll_cmd(message):
    reply(message, f"🎲 You rolled a {random.randint(1, 6)}!")


@command("flip")
def flip_cmd(message):
    reply(message, f"🪙 It's {random.choice(['Heads', 'Tails'])}!")


@command("8ball")
def eightball_cmd(message):
    if not message.args:
        return reply(message, "⚠️ Ask a question, e.g. /8ball will I win?")
    reply(message, f"🎱 {random.choice(EIGHT_BALL)}")


@command("quote")
def quote_cmd(message):
    reply(message, f"💬 \"{random.choice(QUOTES)}\"")


def _make_action(template):
    def handler(message):
        r = message.reply_to_message
        other = mention(r.from_user) if r and r.from_user else "the chat"
        reply(message, template.format(a=mention(message.from_user), b=other))
    return handler


for _name, _tpl in ACTIONS.items():
    command(_name)(_make_action(_tpl))

RPS = ("rock", "paper", "scissors")
BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}


@command("rps")
def rps_cmd(message):
    if not message.args or message.args[0].lower() not in RPS:
        return reply(message, "⚠️ Usage: /rps rock | paper | scissors")
    mine, yours = random.choice(RPS), message.args[0].lower()
    result = "🤝 It's a tie!" if mine == yours else ("🎉 You win!" if BEATS[yours] == mine else "😅 I win!")
    reply(message, f"You: {yours}\nMe: {mine}\n\n{result}")


GUESS_COOLDOWN = 60
_last_guess = {}


@command("guess")
def guess_cmd(message):
    u = message.from_user
    wait = GUESS_COOLDOWN - (time.time() - _last_guess.get(u.id, 0))
    if wait > 0:
        return reply(message, f"⏳ Thoda ruko! Next guess in {int(wait) + 1}s.")
    if not message.args or not message.args[0].isdigit() or not 1 <= int(message.args[0]) <= 100:
        return reply(message, "⚠️ Usage: /guess &lt;number 1-100&gt;")
    _last_guess[u.id] = time.time()
    guess, answer = int(message.args[0]), random.randint(1, 100)
    ensure_user(u.id, u.first_name, u.username)
    if guess == answer:
        credit(u.id, 100)
        reply(message, f"🎯 Spot on! It was {answer}. You win 100 {CURRENCY_EMOJI}!")
    elif abs(guess - answer) <= 5:
        credit(u.id, 25)
        reply(message, f"🔥 So close! It was {answer}. You win 25 {CURRENCY_EMOJI}.")
    else:
        reply(message, f"❌ Nope, it was {answer}. Try again!")


# ------------------------------------------------------------ wager parsing
def _amount(message, index=0):
    """Returns a positive int from args[index], or None after telling the user."""
    if len(message.args) <= index or not message.args[index].isdigit() or int(message.args[index]) <= 0:
        return None
    return int(message.args[index])


def _poor(message, amount):
    reply(message, f"❌ Not enough {CURRENCY_NAME} — you need {money(amount)}.")


# ------------------------------------------------------------ jackpot
# (symbol, pick weight, payout if all 3 match). A pair gives the stake back. Overall return is about 94%.
SLOTS = [("🍒", 30, 7), ("🍋", 25, 7), ("🔔", 20, 11), ("⭐", 15, 14), ("💎", 7, 22), ("7️⃣", 3, 36)]
_SYM = [s for s, _, _ in SLOTS]
_WEIGHT = [w for _, w, _ in SLOTS]
_PAY = {s: p for s, _, p in SLOTS}


def jackpot_multiplier(reels) -> int:
    if reels[0] == reels[1] == reels[2]:
        return _PAY[reels[0]]
    if len(set(reels)) < 3:
        return 1
    return 0


@command("jackpot", "slots")
def jackpot_cmd(message):
    amount = _amount(message)
    if amount is None:
        return reply(message, "⚠️ Usage: /jackpot &lt;amount&gt;")
    if not spend(message.from_user, amount):
        return _poor(message, amount)
    reels = [random.choices(_SYM, weights=_WEIGHT)[0] for _ in range(3)]
    msg = reply(message, "🎰 [ ❓ | ❓ | ❓ ]\nSpinning...")
    shown = ["❓"] * 3
    for i in range(3):
        time.sleep(0.6)
        shown[i] = reels[i]
        edit(msg, f"🎰 [ {' | '.join(shown)} ]\nSpinning...")
    mult = jackpot_multiplier(reels)
    win = amount * mult
    if win:
        credit(message.from_user.id, win)
        result = (f"🤝 A pair — you get your {money(amount)} back." if mult == 1
                  else f"🎉 {mult}x payout — you win {money(win)}!")
    else:
        result = f"💸 No match — you lost {money(amount)}."
    text = f"🎰 [ {' | '.join(reels)} ]\n{result}"
    if edit(msg, text) is None:
        reply(message, text)


# ------------------------------------------------------------ roulette
RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BETS = {"red", "black", "odd", "even", "low", "high"}


def roulette_color(n: int) -> str:
    return "green" if n == 0 else ("red" if n in RED else "black")


def roulette_multiplier(bet: str, spin: int):
    """Payout multiplier, or None if the bet isn't recognised."""
    bet = bet.lower()
    if bet.isdigit():
        return None if not 0 <= int(bet) <= 36 else (36 if int(bet) == spin else 0)
    if bet not in BETS:
        return None
    win = {
        "red": roulette_color(spin) == "red",
        "black": roulette_color(spin) == "black",
        "odd": spin != 0 and spin % 2 == 1,
        "even": spin != 0 and spin % 2 == 0,
        "low": 1 <= spin <= 18,
        "high": 19 <= spin <= 36,
    }[bet]
    return 2 if win else 0


@command("roulette")
def roulette_cmd(message):
    amount = _amount(message)
    if amount is None or len(message.args) < 2:
        return reply(message, "⚠️ Usage: /roulette &lt;amount&gt; &lt;bet&gt;\n"
                              "Bets: a number 0-36, or red / black / odd / even / low (1-18) / high (19-36)")
    bet = message.args[1]
    spin = random.randint(0, 36)
    mult = roulette_multiplier(bet, spin)
    if mult is None:
        return reply(message, "⚠️ Unrecognised bet. Use a number 0-36, or red/black/odd/even/low/high.")
    if not spend(message.from_user, amount):
        return _poor(message, amount)
    msg = reply(message, "🎡 Spinning the wheel...")
    for _ in range(2):
        time.sleep(0.5)
        edit(msg, f"🎡 Spinning... {random.randint(0, 36)}?")
    emoji = {"red": "🔴", "black": "⚫", "green": "🟢"}[roulette_color(spin)]
    win = amount * mult
    if win:
        credit(message.from_user.id, win)
        result = f"🎉 You bet {esc(bet)} and won {money(win)}! ({mult}x)"
    else:
        result = f"💸 You bet {esc(bet)} and lost {money(amount)}."
    text = f"🎡 Ball lands on {spin} {emoji}\n{result}"
    if edit(msg, text) is None:
        reply(message, text)


# ------------------------------------------------------------ mines
GRID = 5
TOTAL = GRID * GRID
DEFAULT_MINES = 5
EDGE = 0.97
GAMES = {}                      # (chat_id, message_id) -> state
_games_lock = threading.Lock()


def next_multiplier(current: float, mines: int, revealed_before: int) -> float:
    remaining = TOTAL - revealed_before
    return current * (remaining / (remaining - mines)) * EDGE


def mines_keyboard(chat_id, msg_id, state, ended: bool):
    kb = types.InlineKeyboardMarkup()
    for r in range(GRID):
        row = []
        for c in range(GRID):
            i = r * GRID + c
            if i in state["revealed"]:
                row.append(Btn("✅", "success", callback_data="noop"))
            elif ended and i in state["mines"]:
                row.append(Btn("💣", "danger", callback_data="noop"))
            else:
                row.append(Btn("🟪", "primary", callback_data=f"mine:{chat_id}:{msg_id}:{i}"))
        kb.row(*row)
    if not ended:
        cash = int(state["amount"] * state["multiplier"])
        kb.row(Btn(f"💰 Cash Out ({state['multiplier']:.2f}x = {cash})", "success",
                   callback_data=f"minecash:{chat_id}:{msg_id}"))
    return kb


def _mines_header(state):
    return (f"💣 {esc(state['name'])}'s Mines — {state['mine_count']} mines, {money(state['amount'])} staked.\n"
            f"Current multiplier: {state['multiplier']:.2f}x — cash out anytime.")


@command("mines")
def mines_cmd(message):
    amount = _amount(message)
    if amount is None:
        return reply(message, f"⚠️ Usage: /mines &lt;amount&gt; [mines 1-10] (default {DEFAULT_MINES})")
    count = DEFAULT_MINES
    if len(message.args) > 1 and message.args[1].isdigit():
        count = max(1, min(10, int(message.args[1])))
    user = message.from_user
    if not spend(user, amount):
        return _poor(message, amount)
    state = {"owner": user.id, "name": user.first_name, "amount": amount, "mine_count": count,
             "mines": set(random.sample(range(TOTAL), count)), "revealed": set(), "multiplier": 1.0}
    msg = reply(message, _mines_header(state))
    if msg is None:
        credit(user.id, amount)
        return
    GAMES[(message.chat.id, msg.message_id)] = state
    try:
        bot.edit_message_reply_markup(message.chat.id, msg.message_id,
                                      reply_markup=mines_keyboard(message.chat.id, msg.message_id, state, False))
    except Exception:
        GAMES.pop((message.chat.id, msg.message_id), None)
        credit(user.id, amount)


def _edit_board(chat_id, msg_id, text, kb):
    try:
        bot.edit_message_text(text, chat_id, msg_id, reply_markup=kb)
    except Exception:
        pass


@callback("mine:")
def mine_tap(call):
    _, chat_s, msg_s, idx_s = call.data.split(":")
    chat_id, msg_id, idx = int(chat_s), int(msg_s), int(idx_s)
    with _games_lock:
        state = GAMES.get((chat_id, msg_id))
        if not state:
            return bot.answer_callback_query(call.id, "This round has already ended.", show_alert=True)
        if call.from_user.id != state["owner"]:
            return bot.answer_callback_query(call.id, "🚫 Not your board!", show_alert=True)
        if idx in state["revealed"]:
            return bot.answer_callback_query(call.id)
        if idx in state["mines"]:
            GAMES.pop((chat_id, msg_id), None)
            outcome = "boom"
        else:
            before = len(state["revealed"])
            state["revealed"].add(idx)
            state["multiplier"] = next_multiplier(state["multiplier"], state["mine_count"], before)
            outcome = "cleared" if len(state["revealed"]) >= TOTAL - state["mine_count"] else "safe"
            if outcome == "cleared":
                GAMES.pop((chat_id, msg_id), None)

    if outcome == "boom":
        bot.answer_callback_query(call.id, "💥 BOOM!", show_alert=True)
        _edit_board(chat_id, msg_id, f"💥 {esc(state['name'])} hit a mine! Lost {money(state['amount'])}.",
                    mines_keyboard(chat_id, msg_id, state, True))
    elif outcome == "cleared":
        win = int(state["amount"] * state["multiplier"])
        credit(state["owner"], win)
        bot.answer_callback_query(call.id, f"🏆 Board cleared! +{win}", show_alert=True)
        _edit_board(chat_id, msg_id,
                    f"🏆 {esc(state['name'])} cleared the board! Cashed out {money(win)} ({state['multiplier']:.2f}x).",
                    mines_keyboard(chat_id, msg_id, state, True))
    else:
        bot.answer_callback_query(call.id, f"Safe! {state['multiplier']:.2f}x")
        _edit_board(chat_id, msg_id, _mines_header(state), mines_keyboard(chat_id, msg_id, state, False))


@callback("minecash:")
def mine_cash(call):
    _, chat_s, msg_s = call.data.split(":")
    chat_id, msg_id = int(chat_s), int(msg_s)
    with _games_lock:
        state = GAMES.get((chat_id, msg_id))
        if not state:
            return bot.answer_callback_query(call.id, "This round has already ended.", show_alert=True)
        if call.from_user.id != state["owner"]:
            return bot.answer_callback_query(call.id, "🚫 Not your board!", show_alert=True)
        if not state["revealed"]:
            return bot.answer_callback_query(call.id, "Reveal at least one tile first!", show_alert=True)
        GAMES.pop((chat_id, msg_id), None)
    win = int(state["amount"] * state["multiplier"])
    credit(state["owner"], win)
    bot.answer_callback_query(call.id, f"💰 Cashed out {win}!", show_alert=True)
    _edit_board(chat_id, msg_id, f"💰 {esc(state['name'])} cashed out {money(win)} ({state['multiplier']:.2f}x).",
                mines_keyboard(chat_id, msg_id, state, True))


@callback("noop")
def noop(call):
    bot.answer_callback_query(call.id)

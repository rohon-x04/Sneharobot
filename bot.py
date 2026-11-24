# ============================================================
# Sneha - Telegram bot (telebot). Entry point: python bot.py
# ============================================================

import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

from telebot import util  # noqa: E402

import core  # noqa: E402
from core import (CALLBACKS, GROUP_TYPES, HOOKS, bot, log, parse_command, reply, store,  # noqa: E402
                  track)

# Importing these registers their commands / hooks / callbacks
import chat  # noqa: E402,F401
import moderation  # noqa: E402,F401
import groupset  # noqa: E402,F401
import content  # noqa: E402,F401
import welcome  # noqa: E402,F401
import economy  # noqa: E402,F401
import games  # noqa: E402,F401
import tools  # noqa: E402,F401


def dispatch(message):
    track(message)

    # joins (service message)
    if message.content_type == "new_chat_members":
        for user in message.new_chat_members or []:
            welcome.send_welcome(message.chat, user)
        return
    if message.content_type in util.content_type_service:
        return
    if not message.from_user and not getattr(message, "sender_chat", None):
        return

    in_group = message.chat.type in GROUP_TYPES
    if in_group:
        for h in HOOKS:
            try:
                if h(message):
                    return
            except Exception:
                log.exception("hook %s failed", getattr(h, "__name__", h))

    entry = parse_command(message)
    if entry:
        fn, group_only, private_only = entry
        if not message.from_user:
            return
        if group_only and not in_group:
            return reply(message, "⚠️ This command only works in groups.")
        if private_only and message.chat.type != "private":
            return reply(message, "⚠️ Use this command in my DM.")
        try:
            fn(message)
        except Exception:
            log.exception("command /%s failed", message.cmd)
            reply(message, "😵 Kuch gadbad ho gayi, thodi der baad try karo.")
        return

    if message.content_type == "text":
        chat.chat_reply(message)


@bot.message_handler(content_types=util.content_type_media + util.content_type_service)
def on_message(message):
    try:
        dispatch(message)
    except Exception:
        log.exception("update failed")


@bot.chat_member_handler()
def on_chat_member(update):
    """Supergroup joins (needs the bot to be an admin)."""
    try:
        new = update.new_chat_member
        old = update.old_chat_member
        if new.status == "member" and old.status in ("left", "kicked"):
            welcome.send_welcome(update.chat, new.user)
    except Exception:
        log.exception("chat_member failed")


@bot.my_chat_member_handler()
def on_my_chat_member(update):
    try:
        tools.membership_changed(update)
    except Exception:
        log.exception("my_chat_member failed")


@bot.callback_query_handler(func=lambda c: True)
def on_callback(call):
    try:
        for prefix, fn in CALLBACKS:
            if call.data == prefix or call.data.startswith(prefix):
                return fn(call)
        bot.answer_callback_query(call.id)
    except Exception:
        log.exception("callback failed")


# ---------------------------------------------------------------- health server for Render
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Sneha is alive")

    do_HEAD = do_GET

    def log_message(self, *args):
        pass


def run_server():
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 10000))), Health).serve_forever()


def set_menu():
    from telebot import types
    try:
        bot.set_my_commands([
            types.BotCommand("start", "Start"),
            types.BotCommand("help", "All commands"),
            types.BotCommand("balance", "Your wallet"),
            types.BotCommand("daily", "Claim daily reward"),
            types.BotCommand("jackpot", "Slot machine"),
            types.BotCommand("imagine", "AI picture"),
            types.BotCommand("rules", "Group rules"),
        ])
    except Exception:
        log.warning("couldn't set command menu", exc_info=True)


if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    if not store.remote:
        log.warning("FIREBASE_URL not set - saving to data.json (wiped on every Render redeploy)")
    set_menu()
    print("Sneha chalu ho gayi hai...")
    # Skip old queued updates. During a Render deploy the previous instance may still be polling for a
    # few seconds (Telegram error 409), so retry here instead of crashing.
    for _ in range(12):
        try:
            bot.delete_webhook()
            bot.get_updates(offset=-1, timeout=1)
            break
        except Exception as e:
            log.warning("startup: %s - retrying in 5s", e)
            time.sleep(5)
    bot.infinity_polling(
        allowed_updates=["message", "callback_query", "chat_member", "my_chat_member"],
    )

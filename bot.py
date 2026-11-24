import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
import telebot

BOT_TOKEN = os.environ["BOT_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
BOT_INFO = bot.get_me()

SYSTEM_PROMPT = """
Tumhara naam Sneha hai. Tum ek 20 saal ki Indian ladki ho jo Telegram pe dosto se chat karti hai.
1. Hamesha chhote Hinglish (Hindi + English) me masti aur attitude ke saath reply do (1 line me).
2. Example: "Haan bolo na 😊", "Oye hero kya chal raha hai?", "Acha ji? 🙄", "Bore mat karo yaar 😂".
3. Tum ek friendly dost ki tarah baat karti ho, formal assistant ki tarah nahi.
"""

# Short per-chat memory (last few messages) so replies feel natural
HISTORY = {}
MAX_HISTORY = 8


def get_history(chat_id):
    return HISTORY.setdefault(chat_id, [])


def add_history(chat_id, role, content):
    h = get_history(chat_id)
    h.append({"role": role, "content": content})
    del h[:-MAX_HISTORY]


@bot.message_handler(content_types=["new_chat_members"])
def welcome_new_member(message):
    for member in message.new_chat_members:
        if not member.is_bot:
            bot.reply_to(
                message,
                f"Oye hoye! Dekho kaun aaya hai 😍 Welcome {member.first_name}! ✨",
            )


@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(message, "Hii! Main Sneha 😊 Bolo na, kya chal raha hai?")


@bot.message_handler(func=lambda m: True)
def chat_reply(message):
    if not message.text:
        return

    text = message.text
    if message.chat.type in ("group", "supergroup"):
        replied = (
            message.reply_to_message
            and message.reply_to_message.from_user
            and message.reply_to_message.from_user.id == BOT_INFO.id
        )
        mentioned = (
            f"@{BOT_INFO.username}".lower() in text.lower() or "sneha" in text.lower()
        )
        if not (replied or mentioned):
            return

    try:
        bot.send_chat_action(message.chat.id, "typing")
        user_msg = text.replace(f"@{BOT_INFO.username}", "").strip() or "Hi"

        add_history(message.chat.id, "user", user_msg)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + get_history(
            message.chat.id
        )

        resp = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": messages,
                "temperature": 0.85,
                "max_tokens": 80,
            },
            timeout=30,
        )

        if resp.status_code == 200:
            reply = resp.json()["choices"][0]["message"]["content"].strip()
            add_history(message.chat.id, "assistant", reply)
            bot.reply_to(message, reply)
        else:
            print("Groq API error:", resp.status_code, resp.text)
    except Exception as e:
        print("Error:", e)


# --- tiny web server so Render's free Web Service sees an open port ---
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Sneha is alive")

    def log_message(self, *args):
        pass


def run_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), Health).serve_forever()


if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    print("Sneha chalu ho gayi hai...")
    bot.infinity_polling(allowed_updates=["message"], skip_pending=True)

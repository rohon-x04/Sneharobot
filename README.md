<div align="center">

# 🌸 𝑺𝒏𝒆𝒉𝒂 🌸

### Your Hinglish bestie + group manager for Telegram

*Chats like a friend · Manages your group · Runs a full economy*

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)
![Groq](https://img.shields.io/badge/AI-Groq-F55036?style=for-the-badge)
![Render](https://img.shields.io/badge/Deploy-Render-46E3B7?style=for-the-badge&logo=render&logoColor=black)

**Owner:** [@rohon_x04](https://t.me/rohon_x04) &nbsp;•&nbsp; ꞋꞋꞌꞋ𝚨ᴘє𝙭 ɴᴇᴛᴡᴏʀᴋ

</div>

---

## ✨ Features

| | Feature | What it does |
|---|---|---|
| 💬 | **AI Chat** | Sneha talks in short, sassy Hinglish. Remembers each person's last 10 messages for 2 days |
| 🛡 | **Moderation** | kick, ban, mute (timed), warn system, promote/demote tiers, pin, purge |
| 🔐 | **Protection** | Locks, anti-flood, link ban, spam ban |
| 🪬 | **Welcome** | Custom welcome text plus a random welcome card with the member's profile photo |
| 🧿 | **Group tools** | Notes (`#name`), filters, rules, AFK |
| 💸 | **Economy** | Daily reward, give, rob, leaderboard, levels and XP |
| 🎰 | **Casino** | Jackpot, roulette, mines (tap-to-play buttons) |
| 🎨 | **AI Pictures** | `/imagine` draws anything, free |
| 🔮 | **Utilities** | id, info, adminlist, calc, report, broadcast, stats |

---

## 📁 Project structure

```
├── bot.py              entry point
├── core.py             shared helpers + command router
├── store.py            database layer (Firebase or local file)
├── chat.py             Sneha's AI brain
├── moderation.py       kick / ban / mute / warn / promote ...
├── groupset.py         locks, flood, link & spam guard
├── content.py          rules, notes, filters, AFK
├── welcome.py          welcome message + card
├── economy.py          balance, daily, rob, levels
├── games.py            casino + fun games
├── tools.py            help menu, utilities, /imagine, owner tools
├── welcome_card.py     card generator
├── welcome_styles.py   random card styles
├── assets/             DejaVuSans.ttf
└── backgrounds/        welcome card images
```

---

## 🚀 Deploy on Render

1. **Push** the project to a GitHub repo.
2. On [Render](https://render.com): **New → Web Service** and connect the repo.
3. Set:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `python bot.py`
4. Add the **environment variables** below.
5. Deploy. The logs should show `Sneha chalu ho gayi hai...`

### 🔑 Environment variables

| Variable | Required | Notes |
|---|:---:|---|
| `BOT_TOKEN` | ✅ | From [@BotFather](https://t.me/BotFather) |
| `GROQ_API_KEY` | ✅ | From [console.groq.com/keys](https://console.groq.com/keys) |
| `API_ID` / `API_HASH` | ➖ | From [my.telegram.org](https://my.telegram.org) → API Development Tools |
| `FIREBASE_URL` | ⭐ | Realtime Database URL. **Without it, data is lost on every redeploy** |
| `FIREBASE_SECRET` | ⭐ | Database secret (leave blank if your rules are open for testing) |
| `OWNER_ID` | ⭐ | Your numeric Telegram ID, for `/stats` and `/broadcast` |
| `AUTH_USER` | ➖ | Extra owner IDs, separated by commas |
| `LOG_CHAT_ID` | ➖ | Group that gets a message when the bot is added or removed |
| `START_STICKER` | ➖ | Sticker file_id shown before the `/start` menu |
| `START_IMAGE` | ➖ | Banner picture for `/start` |
| `SUPPORT_GROUP` / `UPDATE_CHANNEL` | ➖ | Links shown as buttons on `/start` |
| `CURRENCY_NAME` / `CURRENCY_EMOJI` | ➖ | Defaults: `Bubbles` / `🫧` |
| `DAILY_REWARD` / `STARTING_BALANCE` | ➖ | Defaults: `1000` / `100` |

✅ required &nbsp; ⭐ strongly recommended &nbsp; ➖ optional

### ⚙️ After deploying

- In **@BotFather**: `/setprivacy` → **Disable**, so the bot can read group messages.
- Make the bot an **admin** in your groups (needed for moderation and welcome on supergroups).
- Render's free plan sleeps after about 15 minutes idle. Ping your Render URL every 5 minutes with [UptimeRobot](https://uptimerobot.com) to keep Sneha awake.

---

## 🧾 Commands

<details>
<summary><b>🛡 Moderation</b> (admins)</summary>

```
/kick /ban /unban              reply or @user
/mute [10m|2h|1d] /unmute
/warn /warns /unwarn /resetwarns
/setwarn <n>                   warn limit
/warnmode mute|kick|ban
/promote [1|2|3] /demote
/pin /unpin /del /purge
```
</details>

<details>
<summary><b>🔐 Protection</b> (admins)</summary>

```
/lock /unlock /locks           url, sticker, media, username, forward
/setflood <n> /noflood /flood
/linkban on|off
/spamban on|off
```
</details>

<details>
<summary><b>🪬 Welcome</b> (admins)</summary>

```
/setwelcome <text>             {first_name} {name} {mention} {username} {id} {group}
/resetwelcome
/welcome on|off
/welcomecard on|off
```
</details>

<details>
<summary><b>🧿 Notes, filters, rules, AFK</b></summary>

```
/save <name> <text>   /get <name>   #name   /notes   /clear   /clearall
/filter <word> <reply>   /filters   /stop <word>   /stopall
/setrules   /rules   /clearrules
/afk [reason]
```
</details>

<details>
<summary><b>💸 Economy</b></summary>

```
/balance  /daily  /give <user> <amount>  /rob (reply)
/leaderboard  /profile  /level  /toplevel
```
</details>

<details>
<summary><b>🎰 Games and fun</b></summary>

```
/jackpot <amount>
/roulette <amount> <red|black|odd|even|low|high|0-36>
/mines <amount> [mines 1-10]
/roll /flip /8ball /rps /guess <1-100> /quote
/hug /slap /pat (reply)
```
</details>

<details>
<summary><b>🔮 Utility and owner</b></summary>

```
/id /info /adminlist /chatinfo /ping /time
/calc <expression>   /report (reply)
/imagine <prompt>    /reset
/stats  /broadcast   (owner only)
```
</details>

---

## 🧪 Run locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export BOT_TOKEN=your_token
export GROQ_API_KEY=your_key
python bot.py
```

Without `FIREBASE_URL`, data is saved to `data.json`.

---

## 🔒 Security

- Never commit tokens or API keys. Put them in Render's environment variables only.
- If a key or token is ever shared by mistake, **revoke it immediately** (Groq console / @BotFather `/revoke`).

---

<div align="center">

Made with 💕 by **ROH4N** &nbsp;•&nbsp; ꞋꞋꞌꞋ𝚨ᴘє𝙭 ɴᴇᴛᴡᴏʀᴋ

</div>

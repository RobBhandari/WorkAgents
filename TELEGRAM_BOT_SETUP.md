# Telegram Bug Position Bot - Quick Setup Guide

## 📱 Step 1: Install Telegram on Your Phone

1. **iPhone**: Go to App Store → Search "Telegram" → Install
2. **Android**: Go to Play Store → Search "Telegram" → Install
3. Open Telegram and sign up with your phone number

✅ **Done? Great! Now let's create your bot...**

---

## 🤖 Step 2: Create Your Bot (2 minutes)

1. **Open Telegram** on your phone
2. **Search for:** `@BotFather` (it's the official bot creation bot)
3. **Start a chat** with BotFather
4. **Send:** `/newbot`
5. **Follow the prompts:**
   - Give your bot a name (e.g., "Bug Position Bot")
   - Give your bot a username (e.g., "robin_bug_position_bot")
   - Username must end in "bot" (e.g., `robin_bug_position_bot`)
6. **BotFather will reply with your bot token** - it looks like this:
   ```
   123456789:ABCdefGhIjKlMnOpQrStUvWxYz1234567
   ```
7. **Copy this token** (you'll need it in the next step)

---

## 💻 Step 3: Configure the Bot on Your Computer

1. **Open:** `c:\DEV\Agentic-Test\.env`

2. **Find this line:**
   ```
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
   ```

3. **Replace it with your token:**
   ```
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIjKlMnOpQrStUvWxYz1234567
   ```

4. **Save the file**

---

## 🚀 Step 4: Install Python Library & Start the Bot

**Open Command Prompt or PowerShell:**

```bash
# Navigate to project folder
cd c:\DEV\Agentic-Test

# Install Telegram library
pip install python-telegram-bot==21.0

# Start the bot
python execution/telegram_bug_bot.py
```

You should see:
```
🤖 Bug Position Bot is running!
Go to Telegram and send /start to your bot to begin.
```

**✅ Leave this running!** (Don't close the window)

---

## 📱 Step 5: Test Your Bot

1. **Open Telegram** on your phone
2. **Search for your bot** (the username you created, e.g., `robin_bug_position_bot`)
3. **Start a chat** with your bot
4. **Send:** `/start`

You should get a welcome message! 🎉

---

## 🎯 Step 6: Get Your Bug Position Report

**In the Telegram chat with your bot, try these commands:**

### Get Full Report:
```
/bugposition
```

This shows all 7 projects sorted by status (GREEN → AMBER → RED)

### Get Current Week:
```
/week
```

### List All Projects:
```
/projects
```

### Get Project Details:
```
/project Access_Legal_Case_Management
```

---

## ✨ That's It! You're Done!

You can now:
- ✅ Query your bot from your phone anytime, anywhere
- ✅ Get instant bug position reports
- ✅ Check specific project details
- ✅ See current week status

**The bot runs on your computer**, so:
- Keep `python execution/telegram_bug_bot.py` running
- Or run it when you need it
- Later you can set it up to run as a Windows service (always on)

---

## 🛑 How to Stop the Bot

**In the Command Prompt window where the bot is running:**
- Press `Ctrl+C`

---

## 🗑️ How to Delete Everything (If You Want)

1. **Stop the bot:** Press `Ctrl+C`
2. **Delete the Telegram app** from your phone
3. **Delete the bot script:** Delete `execution/telegram_bug_bot.py`
4. **Remove from .env:** Delete the `TELEGRAM_BOT_TOKEN` line

**That's it! Nothing permanent, no traces.**

---

## ❓ Troubleshooting

### "Bot doesn't respond"
- Make sure `python execution/telegram_bug_bot.py` is running
- Check that you copied the bot token correctly in `.env`

### "No projects found"
- Make sure you've run the baseline and tracker scripts first:
  ```bash
  python execution/ado_doe_tracker.py
  ```

### "Can't find my bot on Telegram"
- Search for the **username** (not the name) you gave it
- Make sure it ends with "bot" (e.g., `robin_bug_position_bot`)

---

## 🚀 Next Steps (Optional)

Once you're happy with the bot, you can:
1. **Run it as a Windows service** (always on, even after reboot)
2. **Add more commands** (custom queries, filters, etc.)
3. **Port to Microsoft Teams** (for work integration)

---

**Created:** 2026-01-30
**Author:** Claude Code
**Status:** Ready to use!

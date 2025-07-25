import logging
import random
import json
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
BALANCES_FILE = "balances.json"
MATCHES_FILE = "matches.json"


def load_data():
    global balances, matches, current_match_id
    if os.path.exists(BALANCES_FILE):
        with open(BALANCES_FILE, "r") as f:
            balances.update(json.load(f))
    if os.path.exists(MATCHES_FILE):
        with open(MATCHES_FILE, "r") as f:
            data = json.load(f)
            matches.update({int(k): v for k, v in data.get("matches", {}).items()})
            current_match_id = data.get("current_match_id", 0)

def save_data():
    with open(BALANCES_FILE, "w") as f:
        json.dump(balances, f)
    with open(MATCHES_FILE, "w") as f:
        json.dump({
            "matches": matches,
            "current_match_id": current_match_id
        }, f)
# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# In-memory storage
matches = {}  # {match_id: { "names": [name1, name2], "odds": {name1: odd1, name2: odd2}, "bets": {user_id: {"name": name, "amount": amt}} } }
balances = {}  # {user_id: balance}
current_match_id = 0

# Starting balance for new users
START_BALANCE = 1000

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in balances:
        balances[user_id] = START_BALANCE
        save_data()
    await update.message.reply_text(
        f"Welcome {update.effective_user.first_name}! You have ${balances[user_id]} virtual dollars. "
        "Use /newmatch name1 name2 to start a match."
    )
# /help
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "Available commands:\n"
        "/start - Start and get your balance\n"
        "/newmatch name1 name2 [odd1] [odd2] - Create a new match (odds optional)\n"
        "/bet name amount - Place a bet on a name\n"
        "/reportwinner name - Report the winner and payout\n"
        "/leaderboard - Show the top balances\n"
        "/help - Show this help message"
    )
    await update.message.reply_text(msg)
# /newmatch name1 name2
async def newmatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_match_id
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /newmatch name1 name2 [odd1] [odd2]")
        return

    name1, name2 = context.args[0], context.args[1]
    try:
        odd1 = float(context.args[2]) if len(context.args) > 2 else round(random.uniform(1.2, 3.0), 2)
        odd2 = float(context.args[3]) if len(context.args) > 3 else round(random.uniform(1.2, 3.0), 2)
    except ValueError:
        await update.message.reply_text("Odds must be numbers.")
        return

    current_match_id += 1
    matches[current_match_id] = {
        "names": [name1, name2],
        "odds": {name1: odd1, name2: odd2},
        "bets": {}
    }
    save_data()

    await update.message.reply_text(
        f"Match #{current_match_id} created: {name1} (odds {odd1}) vs {name2} (odds {odd2}). "
        "Use /bet [name] [amount] to place your bet."
    )
# /bet name amount
async def bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /bet name amount")
        return

    if not matches:
        await update.message.reply_text("No active match. Create one using /newmatch.")
        return

    match_id = current_match_id
    name = context.args[0]
    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Amount must be a number.")
        return

    if user_id not in balances:
        balances[user_id] = START_BALANCE

    if balances[user_id] < amount:
        await update.message.reply_text("Not enough balance.")
        return

    if name not in matches[match_id]["names"]:
        await update.message.reply_text(f"{name} is not in the current match.")
        return

    balances[user_id] -= amount
    matches[match_id]["bets"][user_id] = {"name": name, "amount": amount}
    save_data()

    await update.message.reply_text(f"Bet placed: ${amount} on {name} at odds {matches[match_id]['odds'][name]}.")

# /reportwinner name
async def reportwinner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /reportwinner name")
        return

    if not matches:
        await update.message.reply_text("No match to report.")
        return

    winner = context.args[0]
    match_id = current_match_id

    if winner not in matches[match_id]["names"]:
        await update.message.reply_text("Winner must be one of the match names.")
        return

    # Calculate payouts
    for user_id, bet in matches[match_id]["bets"].items():
        if bet["name"] == winner:
            win_amount = int(bet["amount"] * matches[match_id]["odds"][winner])
            balances[user_id] += win_amount

    await update.message.reply_text(f"Match ended! Winner: {winner}. Payouts have been updated.")

    # Clear current match
    matches.pop(match_id)
    save_data()

# /leaderboard
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not balances:
        await update.message.reply_text("No players yet.")
        return

    sorted_balances = sorted(balances.items(), key=lambda x: x[1], reverse=True)
    msg = "🏆 Leaderboard:\n"
    for i, (user_id, balance) in enumerate(sorted_balances[:10], start=1):
        try:
            name = (await context.bot.get_chat(user_id)).first_name
        except:
            name = "User"
        msg += f"{i}. {name} - ${balance}\n"

    await update.message.reply_text(msg)

# Main setup
if __name__ == "__main__":
    load_data()
    app = ApplicationBuilder().token("7844186901:AAH7NQiksJq02IBrYvlOilAuaSKUoeW1aqg").build()
    

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newmatch", newmatch))
    app.add_handler(CommandHandler("bet", bet))
    app.add_handler(CommandHandler("reportwinner", reportwinner))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("help", help))

    print("✅ Bot is running...")
    app.run_polling()

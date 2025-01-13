import logging
import requests
import json
import os
from telegram.constants import ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, filters, CallbackContext

# === CONFIGURATION ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Use environment variables for security
HEDERA_RECEIVING_WALLET = "0.0.8063721"  # Your Hedera wallet
SLOTHSAFE_GROUP_ID = -1001234567890  # Replace with actual chat ID
VOTE_PRICE = 1  # 1 SLOTHBAR token

# === LOGGING SETUP ===
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# === STORAGE FILE ===
STORAGE_FILE = "user_votes.json"

# === STORAGE FOR ACTIVE POLLS ===
active_polls = {
    "Poll 1": {"link": "https://t.me/c/2366575867/5", "id": "poll_1"},
    "Poll 2": {"link": "https://t.me/c/2366575867/6", "id": "poll_2"},
}

# === LOAD/STORE USER VOTES ===
def load_votes():
    if os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_votes(data):
    with open(STORAGE_FILE, "w") as f:
        json.dump(data, f)

user_votes = load_votes()

def vote(update: Update, context: CallbackContext) -> None:
    """Handles the /vote command and asks users to select a poll."""
    user_id = str(update.message.chat_id)
    poll_list = "\n".join([f"📌 {poll_name}" for poll_name in active_polls.keys()])
    update.message.reply_text(
        f"🗳️ **Available Polls:**\n{poll_list}\n\n"
        "Please type the exact name of the poll you want to vote in.",
        parse_mode=ParseMode.MARKDOWN,
    )
    context.user_data["pending_poll"] = True

def wallet_submission(update: Update, context: CallbackContext) -> None:
    """Handles poll selection, payment verification, and directs users to the correct poll."""
    user_id = str(update.message.chat_id)
    user_message = update.message.text.strip()

    if context.user_data.get("pending_poll"):
        if user_message not in active_polls:
            update.message.reply_text("⚠️ Invalid poll selection. Please type the exact poll name.")
            return

        selected_poll = active_polls[user_message]
        context.user_data["pending_poll"] = False
        context.user_data["selected_poll"] = selected_poll

        update.message.reply_text(
            f"🔹 You selected **{user_message}**.\n"
            f"Send **{VOTE_PRICE} SLOTHBAR token** to `{HEDERA_RECEIVING_WALLET}` and reply with your Hedera wallet address.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if "selected_poll" in context.user_data:
        poll_id = context.user_data["selected_poll"]["id"]
        poll_link = context.user_data["selected_poll"]["link"]
        wallet_address = user_message

        if user_id in user_votes and poll_id in user_votes[user_id]:
            update.message.reply_text("❌ You have already voted in this poll! You cannot vote again.")
            return

        update.message.reply_text(f"🔍 Checking your payment for **{poll_id}**...")

        if check_payment(wallet_address, VOTE_PRICE):
            user_votes.setdefault(user_id, []).append(poll_id)
            save_votes(user_votes)
            update.message.reply_text(f"✅ Payment verified! Click here to vote: {poll_link}")
        else:
            update.message.reply_text("❌ No payment found! Ensure you sent **1 SLOTHBAR token** and try again.")


def check_payment(wallet_address, required_tokens):
    """Checks if the user sent the required amount of SLOTHBAR tokens."""
    url = f"https://mainnet-public.mirrornode.hedera.com/api/v1/transactions?account.id={wallet_address}&limit=5"
    response = requests.get(url)
    if response.status_code != 200:
        logger.warning("API request failed!")
        return False

    transactions = response.json().get("transactions", [])
    for txn in transactions:
        for transfer in txn.get("token_transfers", []):
            if transfer.get("account") == HEDERA_RECEIVING_WALLET and transfer.get("amount") == required_tokens * 100000000:
                return True
    return False

def welcome_new_user(update: Update, context: CallbackContext):
    """Sends a welcome message when a new user joins."""
    chat_id = update.message.chat_id
    new_members = update.message.new_chat_members
    if chat_id == SLOTHSAFE_GROUP_ID:
        for member in new_members:
            context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"🎉 Welcome, {member.first_name}! 🦥\n\n"
                    "🗳️ This is **SlothSafe Voting ONLY**, the official Hedera voting group.\n\n"
                    "**Before you vote:**\n"
                    "1️⃣ Send **1 SLOTHBAR token** to `0.0.8063721`.\n"
                    "2️⃣ Type `/vote` to start voting.\n"
                    "3️⃣ Verify payment.\n"
                    "4️⃣ Get the voting link.\n\n"
                    "⚡ Available commands:\n"
                    "`/vote` - Start voting\n"
                    "`/help` - Info about the voting system"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Hello! Use /vote to start voting.")

def main():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("vote", vote))
    dp.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, wallet_submission))
    dp.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_user))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()

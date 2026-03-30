import pandas as pd
import smtplib
from email.mime.text import MIMEText

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

users = {}

def start(update, context):
    user_id = update.message.chat_id
    
    users[user_id] = {
        "email": None,
        "password": None,
        "candidates": [],
        "selected": set()
    }
    
    update.message.reply_text("🤖 HR Assistant\n\nEnter your Gmail:")

def handle_message(update, context):
    user_id = update.message.chat_id
    text = update.message.text
    
    user = users[user_id]
    
    if user["email"] is None:
        user["email"] = text
        update.message.reply_text("Enter App Password:")
    
    elif user["password"] is None:
        user["password"] = text
        update.message.reply_text("✅ Logged in!\nUpload Excel file.")
    
    else:
        update.message.reply_text("Upload Excel file.")

def handle_file(update, context):
    user_id = update.message.chat_id
    file = update.message.document.get_file()
    
    file_path = "data.xlsx"
    file.download(file_path)
    
    df = pd.read_excel(file_path)
    df.columns = [c.strip().lower() for c in df.columns]

    if not all(col in df.columns for col in ["name","email","status"]):
        update.message.reply_text("❌ Invalid file format")
        return

    rejected = df[df["status"].str.lower() == "rejected"]
    
    candidates = []
    for _, row in rejected.iterrows():
        candidates.append({
            "name": row["name"],
            "email": row["email"]
        })
    
    users[user_id]["candidates"] = candidates
    users[user_id]["selected"] = set(range(len(candidates)))

    show_list(update, context)

def show_list(update, context):
    user_id = update.message.chat_id
    user = users[user_id]
    
    keyboard = []
    
    for i, c in enumerate(user["candidates"]):
        mark = "☑" if i in user["selected"] else "☐"
        keyboard.append([
            InlineKeyboardButton(f"{mark} {c['name']}", callback_data=f"toggle_{i}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("✅ Confirm & Send", callback_data="confirm")
    ])
    
    update.message.reply_text("📋 Rejected:", reply_markup=InlineKeyboardMarkup(keyboard))

def button(update, context):
    query = update.callback_query
    query.answer()
    
    user_id = query.message.chat_id
    user = users[user_id]
    
    data = query.data
    
    if data.startswith("toggle_"):
        i = int(data.split("_")[1])
        if i in user["selected"]:
            user["selected"].remove(i)
        else:
            user["selected"].add(i)
        refresh(query, context)
    
    elif data == "confirm":
        send_emails(query, context)

def refresh(query, context):
    user_id = query.message.chat_id
    user = users[user_id]
    
    keyboard = []
    
    for i, c in enumerate(user["candidates"]):
        mark = "☑" if i in user["selected"] else "☐"
        keyboard.append([
            InlineKeyboardButton(f"{mark} {c['name']}", callback_data=f"toggle_{i}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("✅ Confirm & Send", callback_data="confirm")
    ])
    
    query.edit_message_text("📋 Rejected:", reply_markup=InlineKeyboardMarkup(keyboard))

def send_email(user, to_email, name):
    msg = MIMEText(f"Hi {name},\n\nWe regret to inform you that you were not selected.\n\nBest regards,\nHR Team")
    
    msg["Subject"] = "Application Update"
    msg["From"] = user["email"]
    msg["To"] = to_email
    
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(user["email"], user["password"])
        server.send_message(msg)

def send_emails(query, context):
    user_id = query.message.chat_id
    user = users[user_id]
    
    for i in user["selected"]:
        c = user["candidates"][i]
        send_email(user, c["email"], c["name"])
    
    query.edit_message_text("✅ Emails Sent!")

updater = Updater(BOT_TOKEN, use_context=True)
dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
dp.add_handler(MessageHandler(Filters.document, handle_file))
dp.add_handler(CallbackQueryHandler(button))

updater.start_polling()
updater.idle()

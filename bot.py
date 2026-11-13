import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler

# הגדרת לוגים
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# הפרטים שלך שולבו כאן בהצלחה
BOT_TOKEN = "8801750984:AAHIIYvl-cHjsakJ-JmmSKk3H0tdi5mNQuA"
ADMIN_ID = 5370657068  

# מסדי נתונים פנימיים
users_balance = {}  # {user_id: balance}
pending_withdrawals = {}  # {request_id: {user_id, amount, details}}
request_counter = 0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in users_balance:
        users_balance[user.id] = 0.0
        
    await update.message.reply_text(
        f"שלום {user.first_name}! ברוך הבא לבוט הניהול.\n"
        f"היתרה הנוכחית שלך: ₪{users_balance.get(user.id, 0.0):.2f}\n\n"
        "פקודות זמינות:\n"
        "/balance - בדיקת יתרה\n"
        "/withdraw <סכום> <פרטים> - בקשת משיכת כסף"
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bal = users_balance.get(user_id, 0.0)
    await update.message.reply_text(f"💰 היתרה שלך היא: ₪{bal:.2f}")

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global request_counter
    user = update.effective_user
    args = context.args
    
    if len(args) < 2:
        await update.message.reply_text("⚠️ שימוש שגוי. יש לכתוב כך:\n`/withdraw <סכום> <פרטי ביט או טלפון>`", parse_mode="Markdown")
        return
        
    try:
        amount = float(args[0])
    except ValueError:
        await update.message.reply_text("⚠️ סכום לא תקין. אנא הזן מספר.")
        return
        
    details = " ".join(args[1:])
    current_bal = users_balance.get(user.id, 0.0)
    
    if amount <= 0:
        await update.message.reply_text("⚠️ הסכום חייב להיות גדול מ-0.")
        return
        
    if amount > current_bal:
        await update.message.reply_text(f"❌ אין לך מספיק יתרה. היתרה שלך היא ₪{current_bal:.2f}")
        return
        
    # יצירת בקשת משיכה
    request_counter += 1
    req_id = request_counter
    
    pending_withdrawals[req_id] = {
        "user_id": user.id,
        "username": user.username or user.first_name,
        "amount": amount,
        "details": details
    }
    
    users_balance[user.id] = current_bal - amount
    
    await update.message.reply_text(
        f"⏳ בקשת המשיכה שלך על סך ₪{amount:.2f} נקלטה בהצלחה ונשלחה לאישור המנהל.\n"
        f"מספר אסמכתא: #{req_id}"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("✅ אישור (שולם)", callback_data=f"approve_{req_id}"),
            InlineKeyboardButton("❌ דחייה (החזר יתרה)", callback_data=f"reject_{req_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    admin_message = (
        f"🚨 **בקשת משיכה חדשה! (#{req_id})**\n\n"
        f"👤 משתמש: @{user.username} (ID: `{user.id}`)\n"
        f"💵 סכום: ₪{amount:.2f}\n"
        f"📞 פרטים לתשלום: `{details}`\n"
        f"📉 יתרה חדשה בחשבון: ₪{users_balance[user.id]:.2f}"
    )
    
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_message, parse_mode="Markdown", reply_markup=reply_markup)

# פקודת אדמין להטענת יתרה לשחקן
async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ אין לך הרשאה להשתמש בפקודה זו.")
        return
        
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("⚠️ שימוש שגוי. יש לכתוב:\n`/addbalance <user_id> <סכום>`", parse_mode="Markdown")
        return
        
    try:
        target_user_id = int(args[0])
        amount = float(args[1])
    except ValueError:
        await update.message.reply_text("⚠️ שגיאה בנתונים. ודא ש-user_id והסכום הם מספרים.")
        return
        
    current_bal = users_balance.get(target_user_id, 0.0)
    users_balance[target_user_id] = current_bal + amount
    
    await update.message.reply_text(f"✅ הוטענו ₪{amount:.2f} לחשבון של משתמש `{target_user_id}`.\nיתרה חדשה: ₪{users_balance[target_user_id]:.2f}", parse_mode="Markdown")
    
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"💳 התשלום שלך התקבל! היתרה שלך עודכנה ב-₪{amount:.2f}.\n💰 היתרה הכוללת שלך עומדת על: ₪{users_balance[target_user_id]:.2f}"
        )
    except Exception:
        pass

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    action, req_id_str = data.split("_")
    req_id = int(req_id_str)
    
    if req_id not in pending_withdrawals:
        await query.edit_message_text("⚠️ בקשה זו כבר טופלה או פגה.")
        return
        
    req_data = pending_withdrawals[req_id]
    user_id = req_data["user_id"]
    amount = req_data["amount"]
    
    if action == "approve":
        del pending_withdrawals[req_id]
        await query.edit_message_text(f"✅ הבקשה #{req_id} אושרה! הכסף שולם לשחקן.")
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 בקשת המשיכה שלך על סך ₪{amount:.2f} אושרה ושולמה!"
            )
        except Exception:
            pass
            
    elif action == "reject":
        users_balance[user_id] = users_balance.get(user_id, 0.0) + amount
        del pending_withdrawals[req_id]
        await query.edit_message_text(f"❌ הבקשה #{req_id} נדחתה. היתרה הוחזרה לשחקן.")
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ בקשת המשיכה שלך על סך ₪{amount:.2f} נדחתה והוחזרה ליתרה שלך."
            )
        except Exception:
            pass

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("withdraw", withdraw))
    app.add_handler(CommandHandler("addbalance", add_balance))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("הבוט רץ וממתין להודעות...")
    app.run_polling()

if __name__ == "__main__":
    main()

import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

waiting_users = []
active_chats = {}
user_genders = {}  # user_id -> genere scelto

# Mappa emoji per genere
gender_emojis = {
    "Uomo": "👨",
    "Donna": "👩",
    "Trans": "⚧",
    "Altro": "❓"
}

# /start → Chiede il genere
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("👨 Uomo", callback_data="gender_uomo"),
            InlineKeyboardButton("👩 Donna", callback_data="gender_donna")
        ],
        [
            InlineKeyboardButton("⚧ Trans", callback_data="gender_trans"),
            InlineKeyboardButton("❓ Altro", callback_data="gender_altro")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "💬 *Qual è il tuo genere?*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# Salva il genere e mostra schermata di benvenuto
async def select_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    # Salva scelta
    gender_map = {
        "gender_uomo": "Uomo",
        "gender_donna": "Donna",
        "gender_trans": "Trans",
        "gender_altro": "Altro"
    }
    chosen_gender = gender_map.get(query.data, "Altro")
    user_genders[user_id] = chosen_gender

    # Mostra schermata di benvenuto con pulsante
    keyboard = [
        [InlineKeyboardButton("🔍 Inizia ricerca", callback_data="find_partner")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"""👋 *Benvenuto nella chat!*
Conosci al meglio il tuo partner 🔥

📌 Il tuo genere: {chosen_gender}""",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# Tastiera "Blocca" e "Nuova ricerca"
def chat_footer_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("⛔ Blocca", callback_data="block"),
            InlineKeyboardButton("🔄 Nuova ricerca", callback_data="find_partner")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# Trova un partner
async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    # Se già in chat, avvisa
    if user_id in active_chats:
        await query.edit_message_text(
            "Sei già in chat! Usa ⛔ Blocca o 🔄 Nuova ricerca.",
            reply_markup=chat_footer_keyboard()
        )
        return

    # Se in coda e non primo, partner è il primo in coda
    if waiting_users and waiting_users[0] != user_id:
        partner_id = waiting_users.pop(0)
        active_chats[user_id] = partner_id
        active_chats[partner_id] = user_id

        # Messaggi a entrambi
        emoji1 = gender_emojis.get(user_genders.get(user_id, "Altro"), "❓")
        emoji2 = gender_emojis.get(user_genders.get(partner_id, "Altro"), "❓")

        await context.bot.send_message(
            partner_id,
            f"✅ Nuovo partner trovato! Sei in chat con {emoji1}."
        )
        await query.edit_message_text(
            f"✅ Nuovo partner trovato! Sei in chat con {emoji2}.",
            reply_markup=chat_footer_keyboard()
        )
    else:
        if user_id not in waiting_users:
            waiting_users.append(user_id)
        await query.edit_message_text("🔎 In attesa di un partner...", reply_markup=None)

# Blocca utente e termina chat
async def block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if user_id in active_chats:
        partner_id = active_chats[user_id]
        del active_chats[user_id]
        if partner_id in active_chats:
            del active_chats[partner_id]
            await context.bot.send_message(partner_id, "❌ Il tuo partner ha bloccato il bot e ha terminato la chat.")
        await query.edit_message_text("Hai bloccato il bot e terminato la chat.")
    elif user_id in waiting_users:
        waiting_users.remove(user_id)
        await query.edit_message_text("Hai lasciato la coda di attesa.")
    else:
        await query.edit_message_text("Non sei in chat o in attesa.")

# Ferma chat (usato da /stop e /next)
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in active_chats:
        partner_id = active_chats[user_id]
        del active_chats[user_id]
        if partner_id in active_chats:
            del active_chats[partner_id]
            await context.bot.send_message(partner_id, "❌ Il tuo partner ha lasciato la chat.")
        await update.message.reply_text("Hai lasciato la chat.")
    elif user_id in waiting_users:
        waiting_users.remove(user_id)
        await update.message.reply_text("Hai lasciato la coda di attesa.")
    else:
        await update.message.reply_text("Non sei in chat.")

# Passa al prossimo partner
async def next_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await stop(update, context)
    keyboard = [
        [InlineKeyboardButton("🔍 Inizia ricerca", callback_data="find_partner")]
    ]
    await update.message.reply_text("🔄 Nuova ricerca avviata", reply_markup=InlineKeyboardMarkup(keyboard))

# Inoltro messaggi con emoji e pulsanti footer
async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in active_chats:
        # Ignora messaggi fuori chat
        return

    partner_id = active_chats[user_id]
    emoji = gender_emojis.get(user_genders.get(user_id, "Altro"), "❓")
    msg = update.message

    reply_markup = chat_footer_keyboard()

    if msg.text:
        await context.bot.send_message(
            partner_id,
            f"{emoji} {msg.text}",
            reply_markup=reply_markup
        )
    elif msg.photo:
        await context.bot.send_photo(
            partner_id,
            photo=msg.photo[-1].file_id,
            caption=f"{emoji} {msg.caption}" if msg.caption else emoji,
            reply_markup=reply_markup
        )
    elif msg.video:
        await context.bot.send_video(
            partner_id,
            video=msg.video.file_id,
            caption=f"{emoji} {msg.caption}" if msg.caption else emoji,
            reply_markup=reply_markup
        )
    elif msg.audio:
        await context.bot.send_audio(
            partner_id,
            audio=msg.audio.file_id,
            caption=f"{emoji} {msg.caption}" if msg.caption else emoji,
            reply_markup=reply_markup
        )
    elif msg.sticker:
        await context.bot.send_sticker(
            partner_id,
            sticker=msg.sticker.file_id,
            reply_markup=reply_markup
        )
    elif msg.voice:
        await context.bot.send_voice(
            partner_id,
            voice=msg.voice.file_id,
            reply_markup=reply_markup
        )
    elif msg.document:
        await context.bot.send_document(
            partner_id,
            document=msg.document.file_id,
            caption=f"{emoji} {msg.caption}" if msg.caption else emoji,
            reply_markup=reply_markup
        )

def main():
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TOKEN:
        print("Errore: la variabile d'ambiente TELEGRAM_TOKEN non è impostata.")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("next", next_partner))
    app.add_handler(CallbackQueryHandler(select_gender, pattern="gender_"))
    app.add_handler(CallbackQueryHandler(find_partner, pattern="find_partner"))
    app.add_handler(CallbackQueryHandler(block, pattern="block"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, forward_message))

    print("🤖 Bot avviato...")
    app.run_polling()

if __name__ == "__main__":
    main()

import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

waiting_users = []
active_chats = {}
user_genders = {}  # user_id -> genere scelto

def get_gender_emoji(gender: str) -> str:
    mapping = {
        "Uomo": "👨",
        "Donna": "👩",
        "Trans": "⚧",
        "Altro": "❓"
    }
    return mapping.get(gender, "❓")

BUTTONS_CHAT = [
    [InlineKeyboardButton("🚫 Blocca", callback_data="block")],
    [InlineKeyboardButton("🔄 Nuova ricerca", callback_data="find_partner")]
]

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
        f"👋 *Benvenuto nella chat!*
"
        "Conosci al meglio il tuo partner 🔥

"
        f"📌 Il tuo genere: {chosen_gender}",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# Trova un partner
async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if user_id in active_chats:
        await query.edit_message_text("Sei già in chat! Usa /stop o /next.", reply_markup=InlineKeyboardMarkup(BUTTONS_CHAT))
        return

    if waiting_users and waiting_users[0] != user_id:
        partner_id = waiting_users.pop(0)
        active_chats[user_id] = partner_id
        active_chats[partner_id] = user_id
        # Messaggi con emoji di genere
        user_gender_emoji = get_gender_emoji(user_genders.get(user_id, "Altro"))
        partner_gender_emoji = get_gender_emoji(user_genders.get(partner_id, "Altro"))

        await context.bot.send_message(partner_id, f"✅ Partner trovato! Nuova chat iniziata {user_gender_emoji}", reply_markup=InlineKeyboardMarkup(BUTTONS_CHAT))
        await query.edit_message_text(f"✅ Partner trovato! Nuova chat iniziata {partner_gender_emoji}", reply_markup=InlineKeyboardMarkup(BUTTONS_CHAT))
    else:
        waiting_users.append(user_id)
        await query.edit_message_text("🔎 In attesa di un partner...", reply_markup=InlineKeyboardMarkup(BUTTONS_CHAT))

# Ferma chat e rimuove utenti
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in active_chats:
        partner_id = active_chats[user_id]
        del active_chats[user_id]
        if partner_id in active_chats:
            del active_chats[partner_id]
            await context.bot.send_message(partner_id, "❌ Il tuo partner ha lasciato la chat.", reply_markup=InlineKeyboardMarkup(BUTTONS_CHAT))
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

# Blocca bot per utente
async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    # Qui potresti implementare un sistema di blocco persistente se vuoi
    # Per ora semplicemente fermiamo la chat e rimuoviamo dalla coda
    if user_id in active_chats or user_id in waiting_users:
        if user_id in active_chats:
            partner_id = active_chats[user_id]
            del active_chats[user_id]
            if partner_id in active_chats:
                del active_chats[partner_id]
                await context.bot.send_message(partner_id, "❌ Il tuo partner ha lasciato la chat.", reply_markup=InlineKeyboardMarkup(BUTTONS_CHAT))
        if user_id in waiting_users:
            waiting_users.remove(user_id)
        await query.edit_message_text("🚫 Hai bloccato il bot. Per riusare il bot, riavvialo con /start.")
    else:
        await query.edit_message_text("Non sei in chat né in coda.", reply_markup=InlineKeyboardMarkup(BUTTONS_CHAT))

# Inoltro messaggi con emoji genere e pulsanti sotto ogni messaggio
async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in active_chats:
        partner_id = active_chats[user_id]
        msg = update.message
        user_gender_emoji = get_gender_emoji(user_genders.get(user_id, "Altro"))
        prefix = f"{user_gender_emoji} "
        try:
            if msg.text:
                await context.bot.send_message(partner_id, prefix + msg.text, reply_markup=InlineKeyboardMarkup(BUTTONS_CHAT))
            elif msg.photo:
                await context.bot.send_photo(partner_id, photo=msg.photo[-1].file_id, caption=prefix + (msg.caption or ""), reply_markup=InlineKeyboardMarkup(BUTTONS_CHAT))
            elif msg.video:
                await context.bot.send_video(partner_id, video=msg.video.file_id, caption=prefix + (msg.caption or ""), reply_markup=InlineKeyboardMarkup(BUTTONS_CHAT))
            elif msg.audio:
                await context.bot.send_audio(partner_id, audio=msg.audio.file_id, caption=prefix + (msg.caption or ""), reply_markup=InlineKeyboardMarkup(BUTTONS_CHAT))
            elif msg.sticker:
                await context.bot.send_sticker(partner_id, sticker=msg.sticker.file_id)
                # Sticker non supportano pulsanti
            elif msg.voice:
                await context.bot.send_voice(partner_id, voice=msg.voice.file_id, caption=prefix + (msg.caption or ""), reply_markup=InlineKeyboardMarkup(BUTTONS_CHAT))
            elif msg.document:
                await context.bot.send_document(partner_id, document=msg.document.file_id, caption=prefix + (msg.caption or ""), reply_markup=InlineKeyboardMarkup(BUTTONS_CHAT))
        except Exception as e:
            print(f"Errore inoltro messaggio: {e}")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data.startswith("gender_"):
        await select_gender(update, context)
    elif data == "find_partner":
        await find_partner(update, context)
    elif data == "block":
        await block_user(update, context)
    else:
        await query.answer("Azione non riconosciuta")

def main():
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TOKEN:
        print("Errore: la variabile d'ambiente TELEGRAM_TOKEN non è impostata.")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("next", next_partner))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, forward_message))

    print("🤖 Bot avviato...")
    app.run_polling()

if __name__ == "__main__":
    main()

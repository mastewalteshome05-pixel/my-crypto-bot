import os
import io
import base64
import logging
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)

# ----------------- SERVER FOR RENDER (DO NOT TOUCH) -----------------
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyServer)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()
# ---------------------------------------------------------------------

# ---------- CONFIG ----------
BOT_TOKEN = "8806428515:AAG5dzQnJIGw3Gp0ryeageI9bLti5hT0ceQ"
CHANNEL_USERNAME = "DarkCipherLab"
GROUP_USERNAME = "DarkCipherLab1"

MAX_FILE_SIZE = 20 * 1024 * 1024  # Telegram bot API limit ~20MB for download
PBKDF2_ITERATIONS = 200_000
SALT_LEN = 16
NONCE_LEN = 12

# Conversation states
WAITING_FILE, WAITING_PASSWORD = range(2)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------- CRYPTO HELPERS ----------
def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_bytes(data: bytes, password: str) -> bytes:
    salt = secrets.token_bytes(SALT_LEN)
    nonce = secrets.token_bytes(NONCE_LEN)
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return salt + nonce + ciphertext


def decrypt_bytes(blob: bytes, password: str) -> bytes:
    if len(blob) < SALT_LEN + NONCE_LEN:
        raise ValueError("File is corrupted or not encrypted.")
    salt = blob[:SALT_LEN]
    nonce = blob[SALT_LEN:SALT_LEN + NONCE_LEN]
    ciphertext = blob[SALT_LEN + NONCE_LEN:]
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


async def check_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """ተጠቃሚው ቻናሉን እና ግሩፑን ጆይን ማድረጉን ያረጋግጣል"""
    try:
        channel_member = await context.bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        if channel_member.status not in ['member', 'administrator', 'creator']:
            return False
            
        group_member = await context.bot.get_chat_member(f"@{GROUP_USERNAME}", user_id)
        if group_member.status not in ['member', 'administrator', 'creator']:
            return False
            
        return True
    except Exception:
        return False


def get_join_markup():
    markup = [
        [InlineKeyboardButton("📢 Join Our Channel 📢", url=f"https://t.me/{CHANNEL_USERNAME}")],
        [InlineKeyboardButton("💬 Join Our Group 💬", url=f"https://t.me/{GROUP_USERNAME}")],
        [InlineKeyboardButton("🔄 Check Access 🔄", callback_data="check_join_access")]
    ]
    return InlineKeyboardMarkup(markup)


# ---------- BOT HANDLERS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not await check_membership(user_id, context):
        await update.message.reply_text(
            "⚠️ **Access Denied!**\n\nTo use this bot, you must join both our channel and group first! 👇",
            parse_mode="Markdown",
            reply_markup=get_join_markup()
        )
        return

    keyboard = [
        [InlineKeyboardButton("🔒 Encrypt", callback_data="mode_encrypt")],
        [InlineKeyboardButton("🔓 Decrypt", callback_data="mode_decrypt")],
    ]
    await update.message.reply_text(
        "👋 Welcome to **Dark Cipher Lab Bot**!\n\n"
        "This bot protects your Text, Photos, Videos, and Documents using advanced AES-256 password-based encryption.\n\n"
        "Please choose an option below:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if await check_membership(user_id, context):
        keyboard = [
            [InlineKeyboardButton("🔒 Encrypt", callback_data="mode_encrypt")],
            [InlineKeyboardButton("🔓 Decrypt", callback_data="mode_decrypt")],
        ]
        await query.edit_message_text(
            "✅ Access Granted! Welcome to **Dark Cipher Lab Bot**.\n\nPlease choose an option below:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await query.answer("❌ Access Denied! You haven't joined both yet.", show_alert=True)


async def mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not await check_membership(user_id, context):
        await query.edit_message_text("⚠️ Access Denied! Please /start again.", reply_markup=get_join_markup())
        return ConversationHandler.END

    mode = "encrypt" if query.data == "mode_encrypt" else "decrypt"
    context.user_data["mode"] = mode

    label = "🔒 Encrypt" if mode == "encrypt" else "🔓 Decrypt"
    await query.edit_message_text(
        f"{label} mode selected.\n\n📎 Now, send the Text or File you want to process."
    )
    return WAITING_FILE


async def receive_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = msg.from_user.id
    
    if not await check_membership(user_id, context):
        await msg.reply_text("⚠️ Access Denied!", reply_markup=get_join_markup())
        return ConversationHandler.END

    mode = context.user_data.get("mode", "encrypt")

    if msg.text and not msg.document and not msg.photo and not msg.video and not msg.audio and not msg.voice:
        context.user_data["content_type"] = "text"
        context.user_data["text_content"] = msg.text
        await msg.reply_text(
            f"📝 Text received.\n\n🔑 Now, send a **Password** to protect it.\n"
            f"⚠️ Make sure to remember it, or you won't be able to recover it!"
        )
        return WAITING_PASSWORD

    file_obj = None
    file_name = None

    if msg.document:
        file_obj = msg.document
        file_name = msg.document.file_name or "file"
    elif msg.photo:
        file_obj = msg.photo[-1]
        file_name = "photo.jpg"
    elif msg.video:
        file_obj = msg.video
        file_name = msg.video.file_name or "video.mp4"
    elif msg.audio:
        file_obj = msg.audio
        file_name = msg.audio.file_name or "audio.mp3"
    elif msg.voice:
        file_obj = msg.voice
        file_name = "voice.ogg"
    else:
        await msg.reply_text("⚠️ Please send text or a valid file.")
        return WAITING_FILE

    if getattr(file_obj, "file_size", None) and file_obj.file_size > MAX_FILE_SIZE:
        await msg.reply_text(f"⚠️ File is too large (Max {MAX_FILE_SIZE // (1024*1024)}MB).")
        return WAITING_FILE

    context.user_data["content_type"] = "file"
    context.user_data["file_id"] = file_obj.file_id
    context.user_data["file_name"] = file_name

    action = "encrypt" if mode == "encrypt" else "decrypt"
    await msg.reply_text(
        f"📄 File received: `{file_name}`\n\n🔑 Now, send the **Password** to {action}.",
        parse_mode="Markdown",
    )
    return WAITING_PASSWORD


async def receive_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()

    try:
        await update.message.delete()
    except Exception:
        pass

    if len(password) < 4:
        await update.effective_chat.send_message("⚠️ Password too short (Min 4 characters). Try again.")
        return WAITING_PASSWORD

    mode = context.user_data.get("mode", "encrypt")
    content_type = context.user_data.get("content_type", "file")

    status_msg = await update.effective_chat.send_message("⏳ Processing, please wait…")

    if content_type == "text":
        text_content = context.user_data.get("text_content", "")
        try:
            if mode == "encrypt":
                raw = text_content.encode("utf-8")
                encrypted = encrypt_bytes(raw, password)
                token = base64.urlsafe_b64encode(encrypted).decode("ascii")
                await status_msg.edit_text(
                    "✅ Encryption Successful! Copy this cipher text:\n\n"
                    f"`🔒 Cipher: {token}`",
                    parse_mode="Markdown",
                )
            else:
                try:
                    clean_text = text_content.replace("🔒 Cipher: ", "").strip()
                    encrypted = base64.urlsafe_b64decode(clean_text.encode("ascii"))
                except Exception:
                    await status_msg.edit_text("❌ Error: Invalid cipher text format.")
                    context.user_data.clear()
                    return ConversationHandler.END

                try:
                    raw = decrypt_bytes(encrypted, password)
                    await status_msg.edit_text("✅ Decryption Successful!\n\n" + raw.decode("utf-8", errors="replace"))
                except InvalidTag:
                    await status_msg.edit_text("❌ Decryption Failed! Wrong password or corrupted text.")
        except Exception as e:
            await status_msg.edit_text(f"❌ Error occurred: {e}")

        context.user_data.clear()
        return ConversationHandler.END

    file_id = context.user_data.get("file_id")
    file_name = context.user_data.get("file_name")

    try:
        tg_file = await context.bot.get_file(file_id)
        file_bytes = await tg_file.download_as_bytearray()
        file_bytes = bytes(file_bytes)

        if mode == "encrypt":
            result = encrypt_bytes(file_bytes, password)
            out_name = file_name + ".enc"
            caption = f"✅ Encryption Successful!\n📄 `{out_name}`\n\n⚠️ Keep your password safe!"
        else:
            try:
                result = decrypt_bytes(file_bytes, password)
            except InvalidTag:
                await status_msg.edit_text("❌ Decryption Failed! Wrong password or invalid file.")
                context.user_data.clear()
                return ConversationHandler.END

            out_name = file_name[:-4] if file_name.endswith(".enc") else "decrypted_" + file_name
            caption = f"✅ Decryption Successful!\n📄 `{out_name}`"

        out_buffer = io.BytesIO(result)
        out_buffer.name = out_name

        await status_msg.delete()
        await update.effective_chat.send_document(document=out_buffer, caption=caption)

    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled. Send /start to begin again.")
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔐 **Commands:**\n\n"
        "/start — Start the bot\n"
        "/cancel — Cancel the current operation\n"
        "/help — Show this message",
        parse_mode="Markdown",
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(mode_callback, pattern="^mode_")],
        states={
            WAITING_FILE: [
                MessageHandler(
                    (filters.Document.ALL | filters.PHOTO | filters.VIDEO |
                     filters.AUDIO | filters.VOICE | (filters.TEXT & ~filters.COMMAND)),
                    receive_content,
                )
            ],
            WAITING_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_password)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="^check_join_access$"))
    app.add_handler(conv_handler)

    print("🤖 Bot is running securely...")
    app.run_polling()


if __name__ == "__main__":
    main()

import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from cryptography.fernet import Fernet

BOT_TOKEN = "8806428515:AAG5dzQnJIGw3Gp0ryeageI9bLti5hT0ceQ"
CHANNEL_USERNAME = "mybotttt2710"  # Your channel username without '@'

bot = telebot.TeleBot(BOT_TOKEN)

# Generate or set a key for encryption
KEY = Fernet.generate_key()
fernet = Fernet(KEY)

# Temporary storage for user files and data
user_data = {}

# CRITICAL CHECK: Strict channel join function
def check_user_joined(message):
    try:
        member = bot.get_chat_member(f"@{CHANNEL_USERNAME}", message.from_user.id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
        else:
            raise Exception()
    except Exception:
        # If not joined, completely block and show only the join button
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📢 Join Channel Now", url=f"https://t.me/{CHANNEL_USERNAME}"))
        markup.add(InlineKeyboardButton("🔄 Checked / Try Again", callback_data="check_join"))
        
        bot.send_message(
            message.chat.id,
            "⚠️ **Access Denied!**\n\nYou must join our Telegram channel first to use any feature of this bot. Please click the button below to join, then try again!",
            reply_markup=markup
        )
        return False

# When user sends /start
@bot.message_handler(commands=['start'])
def start_command(message):
    if not check_user_joined(message): 
        return
    bot.reply_to(
        message, 
        f"Hello {message.from_user.first_name} 👋\n\n"
        f"Welcome to **File & Text Encryption Bot** 🔐\n\n"
        f"⚡ I can safely encrypt and decrypt your data!\n"
        f"📝 Just send me any **Text** or 📂 **File/Photo/Video** to get started."
    )

# Handle text messages
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    if not check_user_joined(message): 
        return
    
    user_data[message.from_user.id] = {'type': 'text', 'content': message.text}
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔒 Encrypt Text", callback_data="encrypt"),
               InlineKeyboardButton("🔓 Decrypt Text", callback_data="decrypt"))
    
    bot.reply_to(message, "💬 **Text received! What would you like to do?**", reply_markup=markup)

# Handle file, photo, and video messages
@bot.message_handler(content_types=['document', 'photo', 'video'])
def handle_file(message):
    if not check_user_joined(message): 
        return
    
    status_msg = bot.reply_to(message, "📥 **Processing your file... Please wait.**")
    
    if message.content_type == 'document':
        file_id = message.document.file_id
        file_name = message.document.file_name
    elif message.content_type == 'video':
        file_id = message.video.file_id
        file_name = "video.mp4"
    else:
        file_id = message.photo[-1].file_id
        file_name = "photo.jpg"
        
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    user_data[message.from_user.id] = {'type': 'file', 'data': downloaded_file, 'name': file_name}
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔒 Encrypt File", callback_data="encrypt"),
               InlineKeyboardButton("🔓 Decrypt File", callback_data="decrypt"))
    
    bot.edit_message_text("📂 **File received! Choose an option below:**", message.chat.id, status_msg.message_id, reply_markup=markup)

# Handle button actions
@bot.callback_query_handler(func=lambda call: True)
def handle_buttons(call):
    user_id = call.from_user.id
    
    if call.data == "check_join":
        try:
            member = bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
            if member.status in ['creator', 'administrator', 'member']:
                bot.edit_message_text("✅ **Thank you for joining! You can now send text or files.**", call.message.chat.id, call.message.message_id)
            else:
                bot.answer_callback_query(call.id, "❌ You still haven't joined the channel!", show_alert=True)
        except Exception:
            bot.answer_callback_query(call.id, "❌ Verification failed. Please join first!", show_alert=True)
        return

    if user_id not in user_data:
        bot.answer_callback_query(call.id, "❌ Error: No active data found. Please resend your text or file.", show_alert=True)
        return
    
    item = user_data[user_id]
    
    if call.data == "encrypt":
        bot.edit_message_text("🔒 **Encrypting... Please wait.**", call.message.chat.id, call.message.message_id)
        try:
            if item['type'] == 'text':
                encrypted_text = fernet.encrypt(item['content'].encode()).decode()
                bot.send_message(call.message.chat.id, f"🔒 **Encrypted Text Successfully!** 🎉\n\n`{encrypted_text}`\n\n💡 _Copy the exact text above to decrypt it later!_")
            else:
                enc_name = item['name'] + ".enc"
                with open(enc_name, "wb") as f: 
                    f.write(fernet.encrypt(item['data']))
                with open(enc_name, "rb") as f: 
                    bot.send_document(call.message.chat.id, f, caption="🔒 **File Encrypted Successfully!** 🎉\n\n⚠️ _Keep this file safe. Send it back here to decrypt it._")
                os.remove(enc_name)
            del user_data[user_id]
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Encryption failed: {e}")
            
    elif call.data == "decrypt":
        bot.edit_message_text("🔓 **Decrypting... Please wait.**", call.message.chat.id, call.message.message_id)
        try:
            if item['type'] == 'text':
                decrypted_text = fernet.decrypt(item['content'].encode()).decode()
                bot.send_message(call.message.chat.id, f"🔓 **Decrypted Text Successfully!** 🎉\n\n{decrypted_text}")
            else:
                dec_name = "decrypted_" + item['name'].replace(".enc", "")
                with open(dec_name, "wb") as f: 
                    f.write(fernet.decrypt(item['data']))
                with open(dec_name, "rb") as f: 
                    bot.send_document(call.message.chat.id, f, caption="🔓 **File Decrypted Successfully!** 🎉")
                os.remove(dec_name)
            del user_data[user_id]
        except Exception:
            bot.send_message(call.message.chat.id, "❌ **Decryption Failed!**\n\nThis data is either corrupted or was not encrypted by this bot.")

print("🔐 Advanced Emojified Bot is running perfectly...")
bot.infinity_polling()
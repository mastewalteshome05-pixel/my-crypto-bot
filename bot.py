import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from cryptography.fernet import Fernet

# ----------------- SERVER FOR RENDER -----------------
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
# -----------------------------------------------------

BOT_TOKEN = "8806428515:AAG5dzQnJIGw3Gp0ryeageI9bLti5hT0ceQ"
CHANNEL_USERNAME = "DarkCipherLab"
GROUP_USERNAME = "DarkCipherLab1"

bot = telebot.TeleBot(BOT_TOKEN)

# Temporary storage
KEY = Fernet.generate_key()
fernet = Fernet(KEY)
user_data = {}
group_chats = {} # For anonymous group chat

def check_membership(user_id):
    """Checks if user is a member of both channel and group"""
    try:
        channel_member = bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        group_member = bot.get_chat_member(f"@{GROUP_USERNAME}", user_id)
        
        allowed = ['member', 'administrator', 'creator']
        if channel_member.status in allowed and group_member.status in allowed:
            return True
        return False
    except Exception:
        return False

def get_join_markup():
    """Generates a beautiful join layout with emojis"""
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton("📢 Join Our Channel 📢", url=f"https://t.me/{CHANNEL_USERNAME}"),
        InlineKeyboardButton("💬 Join Our Group 💬", url=f"https://t.me/{GROUP_USERNAME}"),
        InlineKeyboardButton("🔄 Check Again / እረጋገጥ 🔄", callback_data="check_join")
    )
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if not check_membership(message.from_user.id):
        bot.send_message(
            message.chat.id, 
            "⚠️ **Access Denied / መግቢያ ተከልክሏል!** ⚠️\n\n"
            "To use this bot, you must be a member of both our channel and group.\n"
            "ቦቱን ለመጠቀም እባክዎ መጀመሪያ ቻናላችንን እና ግሩፓችንን ይቀላቀሉ! 👇", 
            parse_mode="Markdown", 
            reply_markup=get_join_markup()
        )
        return

    welcome_text = (
        "🔐 **Welcome to Dark Cipher Lab Bot!** 🔐\n\n"
        "**Commands / ትዕዛዞች:**\n"
        "• Send any file to **Encrypt** it with a Secure Username lock.\n"
        "• Send an encrypted file to **Decrypt** it.\n"
        "• `/group_chat` — Use this in a group to chat secretly with someone!"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def check_join_callback(call):
    if check_membership(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Success! You can now use the bot.")
        bot.send_message(call.message.chat.id, "🎉 Welcome! Send a file to Encrypt.")
    else:
        bot.answer_callback_query(call.id, "❌ You haven't joined both yet! / ገና አልገቡም!", show_alert=True)

# ----------------- FILE ENCRYPTION WITH USERNAME -----------------
@bot.message_handler(content_types=['document'])
def handle_document(message):
    if not check_membership(message.from_user.id):
        bot.send_message(message.chat.id, "⚠️ Join our networks first!", reply_markup=get_join_markup())
        return

    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    # Process if it's already encrypted
    if message.document.file_name.endswith('.enc'):
        msg = bot.send_message(message.chat.id, "🔑 Enter the **Sender's Username** (without @) to decrypt:")
        user_data[message.from_user.id] = {
            'action': 'decrypt',
            'file_data': downloaded_file,
            'file_name': message.document.file_name,
            'prompt_msg_id': msg.message_id
        }
    else:
        # Encrypting new file
        msg = bot.send_message(message.chat.id, "🔒 Enter the **Target User's Username** (without @) who can open this file:")
        user_data[message.from_user.id] = {
            'action': 'encrypt',
            'file_data': downloaded_file,
            'file_name': message.document.file_name,
            'prompt_msg_id': msg.message_id
        }

@bot.message_handler(func=lambda message: message.from_user.id in user_data and message.chat.type == 'private')
def handle_username_input(message):
    target_username = message.text.strip().replace('@', '')
    data = user_data[message.from_user.id]
    
    # Auto-delete usernames for privacy
    try:
        bot.delete_message(message.chat.id, message.message_id)
        bot.delete_message(message.chat.id, data['prompt_msg_id'])
    except Exception:
        pass

    if data['action'] == 'encrypt':
        # Lock with both Sender and Target username
        sender_username = message.from_user.username or "unknown"
        clean_sender = sender_username.replace('@', '')
        
        encrypted_data = fernet.encrypt(data['file_data'])
        # Append meta info safely
        meta_block = f"\n__META__:{clean_sender}:{target_username}".encode()
        final_data = encrypted_data + meta_block

        enc_file_name = data['file_name'] + ".enc"
        with open(enc_file_name, "wb") as f:
            f.write(final_data)
            
        with open(enc_file_name, "rb") as f:
            bot.send_document(message.chat.id, f, caption=f"🔒 Encrypted for @{target_username}")
        os.remove(enc_file_name)
        
    elif data['action'] == 'decrypt':
        try:
            file_content = data['file_data']
            if b"__META__:" in file_content:
                main_data, meta = file_content.split(b"__META__:")
                allowed_sender, allowed_target = meta.decode().split(':')
                
                current_user = message.from_user.username or "unknown"
                clean_current = current_user.replace('@', '')
                
                # Validation
                if target_username.lower() == allowed_sender.lower() and clean_current.lower() == allowed_target.lower():
                    decrypted_data = fernet.decrypt(main_data)
                    dec_file_name = data['file_name'].replace('.enc', '')
                    
                    with open(dec_file_name, "wb") as f:
                        f.write(decrypted_data)
                    with open(dec_file_name, "rb") as f:
                        bot.send_document(message.chat.id, f, caption="✅ Decrypted Successfully!")
                    os.remove(dec_file_name)
                else:
                    bot.send_message(message.chat.id, "❌ Invalid Username! You are not authorized to decrypt this file.")
            else:
                bot.send_message(message.chat.id, "❌ This file layout is standard or corrupted.")
        except Exception:
            bot.send_message(message.chat.id, "❌ Decryption Failed. Check credentials.")

    del user_data[message.from_user.id]

# ----------------- ANONYMOUS GROUP CRYPTO CHAT -----------------
@bot.message_handler(commands=['group_chat'])
def setup_group_chat(message):
    if message.chat.type == 'private':
        bot.send_message(message.chat.id, "ℹ️ Use this command inside the group @DarkCipherLab1!")
        return
        
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔗 Connect Secretly 🔗", callback_data="join_secret_chat"))
    bot.send_message(message.chat.id, "💬 **Secure Chat Session**\nClick below to bond a private channel inside this group.", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "join_secret_chat")
def join_secret_cb(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    user_name = call.from_user.first_name

    if chat_id not in group_chats:
        group_chats[chat_id] = []

    if len(group_chats[chat_id]) < 2:
        if user_id not in [u['id'] for u in group_chats[chat_id]]:
            group_chats[chat_id].append({'id': user_id, 'name': user_name})
            bot.send_message(chat_id, f"👤 {user_name} joined the secret session.")
            
        if len(group_chats[chat_id]) == 2:
            bot.send_message(chat_id, "🔒 **Session Established!** Both users can now type in group, texts will be auto-encrypted for others.")
    else:
        bot.answer_callback_query(call.id, "❌ A session is already full here.", show_alert=True)

@bot.message_handler(func=lambda message: message.chat.type != 'private')
def handle_group_messages(message):
    chat_id = message.chat.id
    if chat_id in group_chats and len(group_chats[chat_id]) == 2:
        session_users = [u['id'] for u in group_chats[chat_id]]
        if message.from_user.id in session_users:
            sender_name = message.from_user.first_name
            raw_text = message.text
            
            # Encrypt message
            enc_text = fernet.encrypt(raw_text.encode()).decode()
            
            # Delete original instantly
            try:
                bot.delete_message(chat_id, message.message_id)
            except Exception:
                pass
                
            # Post encrypted version to group safely
            bot.send_message(chat_id, f"👤 **{sender_name}** (Secure):\n`{enc_text}`", parse_mode="Markdown")

bot.polling(none_stop=True)

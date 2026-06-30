import os
import threading
import time
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from cryptography.fernet import Fernet

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

# 🔐 የቦት፣ የቻናል እና የግሩፕ መለያዎች
BOT_TOKEN = "8806428515:AAG5dzQnJIGw3Gp0ryeageI9bLti5hT0ceQ"
CHANNEL_USERNAME = "DarkCipherLab"
GROUP_USERNAME = "DarkCipherLab1"

bot = telebot.TeleBot(BOT_TOKEN)

# ዳታቤዝ ፋይሎች
LANG_DB = "user_languages.json"
KEYS_DB = "user_keys.json"

def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_json(filename, data):
    try:
        with open(filename, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

def get_user_cipher(user_id):
    """ለእያንዳንዱ ሰው የተለየ የኢንክሪፕሽን ቁልፍ በመስጠት ሀኪንግን ይከላከላል"""
    keys = load_json(KEYS_DB)
    uid_str = str(user_id)
    if uid_str not in keys:
        new_key = Fernet.generate_key().decode()
        keys[uid_str] = new_key
        save_json(KEYS_DB, keys)
    return Fernet(keys[uid_str].encode())

# ጊዜያዊ ዳታዎች
user_data = {}
group_chats = {}

def check_membership(user_id):
    try:
        channel_member = bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        if channel_member.status not in ['member', 'administrator', 'creator']:
            return False
        group_member = bot.get_chat_member(f"@{GROUP_USERNAME}", user_id)
        if group_member.status not in ['member', 'administrator', 'creator']:
            return False
        return True
    except Exception:
        return False

def get_language_markup():
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("🇪🇹 አማርኛ", callback_data="lang_am"),
        InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")
    )
    return markup

def get_join_markup(lang):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    if lang == 'am':
        markup.add(
            InlineKeyboardButton("📢 ቻናላችንን ይቀላቀሉ (Join Channel) 📢", url=f"https://t.me/{CHANNEL_USERNAME}"),
            InlineKeyboardButton("💬 ግሩፓችንን ይቀላቀሉ (Join Group) 💬", url=f"https://t.me/{GROUP_USERNAME}"),
            InlineKeyboardButton("🔄 እረጋገጥ / Check Again 🔄", callback_data="check_join")
        )
    else:
        markup.add(
            InlineKeyboardButton("📢 Join Our Channel 📢", url=f"https://t.me/{CHANNEL_USERNAME}"),
            InlineKeyboardButton("💬 Join Our Group 💬", url=f"https://t.me/{GROUP_USERNAME}"),
            InlineKeyboardButton("🔄 Check Again / Try Again 🔄", callback_data="check_join")
        )
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    try:
        bot.send_message(
            message.chat.id,
            "👋 **Welcome! Please choose your language / እባክዎ ቋንቋ ይምረጡ፦**",
            parse_mode="Markdown",
            reply_markup=get_language_markup()
        )
    except Exception:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def set_language(call):
    try:
        user_id = call.from_user.id
        lang = "am" if call.data == "lang_am" else "en"
        
        langs = load_json(LANG_DB)
        langs[str(user_id)] = lang
        save_json(LANG_DB, langs)
        
        if not check_membership(user_id):
            txt = "⚠️ **መግቢያ ተከልክሏል!**\n\nቦቱን ለመጠቀም መጀመሪያ ቻናላችንን እና ግሩፓችንን ይቀላቀሉ!" if lang == 'am' else "⚠️ **Access Denied!**\n\nTo use this bot, you must join both our channel and group first!"
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=txt, parse_mode="Markdown", reply_markup=get_join_markup(lang))
        else:
            send_main_menu(call.message.chat.id, user_id)
    except Exception:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def check_join_callback(call):
    try:
        user_id = call.from_user.id
        langs = load_json(LANG_DB)
        lang = langs.get(str(user_id), 'am')
        
        if check_membership(user_id):
            alert_txt = "✅ ተሳክቷል! ቦቱን መጠቀም ይችላሉ።" if lang == 'am' else "✅ Success! You can now use the bot."
            bot.answer_callback_query(call.id, alert_txt)
            send_main_menu(call.message.chat.id, user_id)
        else:
            alert_err = "❌ ይቅርታ፣ ገና ሁለቱንም አልገቡም!" if lang == 'am' else "❌ You haven't joined both yet!"
            bot.answer_callback_query(call.id, alert_err, show_alert=True)
    except Exception:
        pass

def send_main_menu(chat_id, user_id):
    langs = load_json(LANG_DB)
    lang = langs.get(str(user_id), 'am')
    if lang == 'am':
        welcome_text = (
            "🔐 **እንኳን ወደ Dark Cipher Lab Bot በሰላም መጡ!** 🔐\n\n"
            "🎈 **መመሪያ፦**\n"
            "1️⃣ **ጽሑፍ ለመቆለፍ፦** ዝም ብለው የሚፈልጉትን ጽሑፍ በቻቱ ላይ ይጻፉ።\n"
            "2️⃣ **ፋይል ለመቆለፍ፦** የትኛውንም ፋይል (ፎቶ፣ ቪዲዮ) ይላኩ።\n"
            "3️⃣ **ለመክፈት፦** የተቆለፈ ኮድ ወይም ፋይል ሲልኩለት ቦቱ ይፈታዋል፤ **ለከፍተኛ ደህንነት መልእክቱ በጥቂት ሰከንዶች ውስጥ ራሱ ይጠፋል!**\n\n"
            "👉 `/group_chat` — በግሩፕ ውስጥ ሁለት ሰዎች ብቻ በሚስጥር ለማውራት!"
        )
    else:
        welcome_text = (
            "🔐 **Welcome to Dark Cipher Lab Bot!** 🔐\n\n"
            "🎈 **Instructions:**\n"
            "1️⃣ **Encrypt Text:** Just send any normal text message to the bot.\n"
            "2️⃣ **Encrypt File:** Send any file (photo, video, document) to the bot.\n"
            "3️⃣ **Decrypt:** Send an encrypted text back. **Decrypted messages will self-destruct for maximum security!**\n\n"
            "👉 `/group_chat` — Inside groups, use this to chat secretly!"
        )
    bot.send_message(chat_id, welcome_text, parse_mode="Markdown")

def delayed_delete(chat_id, message_id, delay=10):
    def target():
        time.sleep(delay)
        try: bot.delete_message(chat_id, message_id)
        except Exception: pass
    threading.Thread(target=target, daemon=True).start()

# ----------------- MAIN ENCRYPTION HANDLER -----------------
@bot.message_handler(content_types=['text', 'document', 'photo', 'video'])
def handle_all_inputs(message):
    try:
        if message.chat.type != 'private':
            handle_group_messages(message)
            return

        user_id = message.from_user.id
        langs = load_json(LANG_DB)
        lang = langs.get(str(user_id), 'am')

        if not check_membership(user_id):
            bot.send_message(message.chat.id, "⚠️ Access Denied!", reply_markup=get_join_markup(lang))
            return

        cipher = get_user_cipher(user_id)

        # 1. ጽሑፍ ከመጣ
        if message.content_type == 'text':
            text = message.text
            if text.startswith('/'): return
                
            if text.startswith("የተቆለፈ መልእክት [") or text.startswith("🔒 Cipher:"):
                try:
                    clean_text = text.replace("የተቆለፈ መልእክት [", "").replace("]", "").replace("🔒 Cipher: ", "")
                    decrypted = cipher.decrypt(clean_text.encode()).decode()
                    
                    msg_out = f"✅ **የተፈታ ሚስጥር (Decrypted):**\n\n`{decrypted}`\n\n⚠️ *ይህ መልእክት ከ10 ሰከንድ በኋላ በራስ-ሰር ይጠፋል!*" if lang == 'am' else f"✅ **Decrypted Text:**\n\n`{decrypted}`\n\n⚠️ *This message will self-destruct in 10 seconds!*"
                    sent_msg = bot.send_message(message.chat.id, msg_out, parse_mode="Markdown")
                    
                    delayed_delete(message.chat.id, sent_msg.message_id, 10)
                    try: bot.delete_message(message.chat.id, message.message_id)
                    except Exception: pass
                except Exception:
                    msg_err = "❌ ስህተት! ይህ ኮድ በሌላ አካውንት የተቆለፈ ነው ወይም ተስተካክሏል።" if lang == 'am' else "❌ Error! This code belongs to another user or is invalid."
                    bot.send_message(message.chat.id, msg_err)
            else:
                encrypted = cipher.encrypt(text.encode()).decode()
                response = f"🔒 **የተቆለፈ መልእክት [**`{encrypted}`**]**" if lang == 'am' else f"🔒 **🔒 Cipher: {encrypted}**"
                bot.send_message(message.chat.id, response, parse_mode="Markdown")

        # 2. ፋይል ከመጣ
        else:
            file_id = None
            file_name = "secret_file"
            if message.content_type == 'document':
                file_id = message.document.file_id
                file_name = message.document.file_name
            elif message.content_type == 'photo':
                file_id = message.photo[-1].file_id
                file_name = "photo.jpg"
            elif message.content_type == 'video':
                file_id = message.video.file_id
                file_name = "video.mp4"
                
            file_info = bot.get_file(file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            if file_name.endswith('.enc'):
                prompt_txt = "🔑 ፋይሉን ለመክፈት **የላኪውን Username** ያስገቡ፦" if lang == 'am' else "🔑 Enter the **Sender's Username** to decrypt:"
                msg = bot.send_message(message.chat.id, prompt_txt)
                user_data[user_id] = {'action': 'decrypt', 'file_data': downloaded_file, 'file_name': file_name, 'prompt_id': msg.message_id}
            else:
                prompt_txt = "🔒 ይህ ፋይል እንዲከፍት የፈለጉትን ሰው **Username** ያስገቡ፦" if lang == 'am' else "🔒 Enter the **Target User's Username**:"
                msg = bot.send_message(message.chat.id, prompt_txt)
                user_data[user_id] = {'action': 'encrypt', 'file_data': downloaded_file, 'file_name': file_name, 'prompt_id': msg.message_id}
    except Exception:
        pass

@bot.message_handler(func=lambda message: message.from_user.id in user_data and message.chat.type == 'private')
def handle_username_lock(message):
    try:
        user_id = message.from_user.id
        langs = load_json(LANG_DB)
        lang = langs.get(str(user_id), 'am')
        target_username = message.text.strip().replace('@', '')
        data = user_data[user_id]
        cipher = get_user_cipher(user_id)
        
        try:
            bot.delete_message(message.chat.id, message.message_id)
            bot.delete_message(message.chat.id, data['prompt_id'])
        except Exception: pass

        if data['action'] == 'encrypt':
            sender = message.from_user.username or "unknown"
            clean_sender = sender.replace('@', '')
            
            encrypted_bytes = cipher.encrypt(data['file_data'])
            meta_block = f"\n__META__:{clean_sender}:{target_username}".encode()
            final_data = encrypted_bytes + meta_block

            out_name = data['file_name'] + ".enc"
            with open(out_name, "wb") as f: f.write(final_data)
            with open(out_name, "rb") as f:
                cap = f"🔒 ፋይሉ በምስጢር ተቆልፏል! መክፈት የሚችለው፦ @{target_username}" if lang == 'am' else f"🔒 Encrypted! Only @{target_username} can open this."
                bot.send_document(message.chat.id, f, caption=cap)
            os.remove(out_name)
            
        elif data['action'] == 'decrypt':
            try:
                file_content = data['file_data']
                if b"__META__:" in file_content:
                    main_data, meta = file_content.split(b"__META__:")
                    allowed_sender, allowed_target = meta.decode().split(':')
                    current_user = message.from_user.username or "unknown"
                    clean_current = current_user.replace('@', '')
                    
                    if target_username.lower() == allowed_sender.lower() and clean_current.lower() == allowed_target.lower():
                        decrypted_bytes = cipher.decrypt(main_data)
                        out_name = data['file_name'].replace('.enc', '')
                        with open(out_name, "wb") as f: f.write(decrypted_bytes)
                        with open(out_name, "rb") as f:
                            cap = "✅ ተከፍቷል! (ከ15 ሰከንድ በኋላ ይጠፋል)" if lang == 'am' else "✅ Decrypted! (Deletes in 15s)"
                            sent_doc = bot.send_document(message.chat.id, f, caption=cap)
                            delayed_delete(message.chat.id, sent_doc.message_id, 15)
                        os.remove(out_name)
                    else:
                        msg_err = "❌ አልተፈቀደልዎትም! መረጃው የተጠበቀ ነው።" if lang == 'am' else "❌ Access Denied!"
                        bot.send_message(message.chat.id, msg_err)
                else:
                    bot.send_message(message.chat.id, "❌ Invalid file structure.")
            except Exception:
                bot.send_message(message.chat.id, "❌ Decryption Failed.")

        del user_data[user_id]
    except Exception:
        pass

# ----------------- በግሩፕ ውስጥ በምስጢር ማውሪያ -----------------
@bot.message_handler(commands=['group_chat'])
def setup_group_chat(message):
    try:
        if message.chat.type == 'private':
            bot.send_message(message.chat.id, f"ℹ️ Use this in our group: @{GROUP_USERNAME}")
            return
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔗 በሚስጥር ተገናኝ (Connect) 🔗", callback_data="join_secret_chat"))
        bot.send_message(message.chat.id, "💬 **የግሩፕ ሚስጥራዊ ማውሪያ መስመር / Group Secret Session**", reply_markup=markup, parse_mode="Markdown")
    except Exception:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "join_secret_chat")
def join_secret_cb(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        user_name = call.from_user.first_name

        if chat_id not in group_chats: group_chats[chat_id] = []

        if len(group_chats[chat_id]) < 2:
            if user_id not in [u['id'] for u in group_chats[chat_id]]:
                group_chats[chat_id].append({'id': user_id, 'name': user_name})
                bot.send_message(chat_id, f"👤 {user_name} joined the secret session.")
                
            if len(group_chats[chat_id]) == 2:
                bot.send_message(chat_id, "🔒 **Session Locked!** መልእክቶች በሙሉ በራስ-ሰር ይጠፋሉ።")
        else:
            bot.answer_callback_query(call.id, "❌ Session is full.", show_alert=True)
    except Exception:
        pass

def handle_group_messages(message):
    try:
        chat_id = message.chat.id
        if chat_id in group_chats and len(group_chats[chat_id]) == 2:
            session_users = [u['id'] for u in group_chats[chat_id]]
            if message.from_user.id in session_users:
                sender_name = message.from_user.first_name
                raw_text = message.text
                if not raw_text or raw_text.startswith('/'): return
                
                cipher = get_user_cipher(message.from_user.id)
                enc_text = cipher.encrypt(raw_text.encode()).decode()
                try: bot.delete_message(chat_id, message.message_id)
                except Exception: pass
                
                sec_msg = bot.send_message(chat_id, f"👤 **{sender_name}** (Secure):\n`🔒 Cipher: {enc_text}`", parse_mode="Markdown")
                delayed_delete(chat_id, sec_msg.message_id, 8)
    except Exception:
        pass

bot.polling(none_stop=True)

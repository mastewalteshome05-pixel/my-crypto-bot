import os
import threading
import time
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

# 🔐 ትክክለኛ የቦት እና የቻናል መለያዎች
BOT_TOKEN = "8806428515:AAG5dzQnJIGw3Gp0ryeageI9bLti5hT0ceQ"
CHANNEL_USERNAME = "DarkCipherLab"
GROUP_USERNAME = "DarkCipherLab1"

bot = telebot.TeleBot(BOT_TOKEN)

# ሚስጥራዊ ቁልፍ ማመንጫ
KEY = Fernet.generate_key()
fernet = Fernet(KEY)

# ጊዜያዊ መረጃ ማስቀመጫዎች
user_states = {}
user_data = {}
group_chats = {}

def check_membership(user_id):
    """ተጠቃሚው ቻናሉን እና ግሩፑን ጆይን ማድረጉን ያረጋግጣል"""
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
    """ማራኪ የጆይን ማድረጊያ በተኖች ከኢሞጂ ጋር"""
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
        "**እንኳን ወደ ሚስጥራዊ መልእክት ማስተላለፊያ ቦት በሰላም መጡ!**\n\n"
        "🎈 **መመሪያ / How to use:**\n"
        "1️⃣ **ጽሑፍ በምስጢር ለመቆለፍ (Encrypt):** ዝም ብለህ የምትፈልገውን ጽሑፍ ለቦቱ ላክለት።\n"
        "2️⃣ **ፋይል በምስጢር ለመቆለፍ (File Encrypt):** የትኛውንም ፋይል (ፎቶ፣ ቪዲዮ፣ ሰነድ) ላክለት።\n"
        "3️⃣ **ለመክፈት (Decrypt):** በቦቱ የተቆለፈውን ጽሑፍ ወይም ፋይል መልሰህ ለቦቱ ስትልክለት ይከፍተዋል።\n\n"
        "👉 `/group_chat` — በግሩፕ ውስጥ ሁለት ሰዎች ብቻ በሚስጥር ለማውራት!"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def check_join_callback(call):
    if check_membership(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ ተሳክቷል! ቦቱን መጠቀም ይችላሉ።")
        bot.send_message(call.message.chat.id, "🎉 እንኳን ደህና መጡ! አሁን የሚቆለፈውን ጽሑፍ ወይም ፋይል ይላኩ።")
    else:
        bot.answer_callback_query(call.id, "❌ ገና ሁለቱንም አልገቡም! እባክዎ ጆይን ያድርጉ።", show_alert=True)

# ----------------- ጽሑፍ እና ፋይል ኢንክሪፕት ማድረጊያ (MAIN ENCRYPTION) -----------------
@bot.message_handler(content_types=['text', 'document', 'photo', 'video', 'audio'])
def handle_all_inputs(message):
    # በግሩፕ ውስጥ የሚጻፉ መደበኛ መልእክቶችን ወደ ግሩፕ ቻት ክፍል መምራት
    if message.chat.type != 'private':
        handle_group_messages(message)
        return

    # የጆይን ማረጋገጫ
    if not check_membership(message.from_user.id):
        bot.send_message(message.chat.id, "⚠️ ቦቱን ለመጠቀም መጀመሪያ አባል ይሁኑ!", reply_markup=get_join_markup())
        return

    # 1. ጽሑፍ ከመጣ (Text Encrypt or Decrypt)
    if message.content_type == 'text':
        text = message.text
        if text.startswith('/'):
            return # ትዕዛዞችን እንዳያበላሽ
            
        # ዲክሪፕት ለማድረግ የተላከ የተቆለፈ ጽሑፍ ከሆነ
        if text.startswith("የተቆለፈ መልእክት [") or text.startswith("🔒 Cipher:"):
            try:
                clean_text = text.replace("የተቆለፈ መልእክት [", "").replace("]", "").replace("🔒 Cipher: ", "")
                decrypted = fernet.decrypt(clean_text.encode()).decode()
                bot.send_message(message.chat.id, f"✅ **የተፈታ ሚስጥር (Decrypted Text):**\n\n`{decrypted}`", parse_mode="Markdown")
            except Exception:
                bot.send_message(message.chat.id, "❌ የይለፍ ቃሉ ስህተት ነው ወይም ጽሑፉ ተስተካክሏል!")
        else:
            # መደበኛ ጽሑፍ ከሆነ ኢንክሪፕት ማድረግ
            encrypted = fernet.encrypt(text.encode()).decode()
            response = f"🔒 **የተቆለፈ መልእክት [**`{encrypted}`**]**\n\n👆 ይህንን ኮድ ለሚፈልጉት ሰው መላክ ይችላሉ። ተቀባዩ ለዚህ ቦት ሲልከው ይፈታለታል።"
            bot.send_message(message.chat.id, response, parse_mode="Markdown")

    # 2. ፋይል ከመጣ (File Encrypt or Decrypt)
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
            # ዲክሪፕት የማድረግ ሂደት
            msg = bot.send_message(message.chat.id, "🔑 ፋይሉን ለመክፈት **የላኪውን Username** ያለምንም @ ምልክት ያስገቡ፦")
            user_data[message.from_user.id] = {
                'action': 'decrypt', 'file_data': downloaded_file, 'file_name': file_name, 'prompt_id': msg.message_id
            }
        else:
            # ኢንክሪፕት የማድረግ ሂደት
            msg = bot.send_message(message.chat.id, "🔒 ይህንን ፋይል እንዲከፍት የምትፈልገውን ሰው **Username** ያለምንም @ ምልክት ያስገቡ፦")
            user_data[message.from_user.id] = {
                'action': 'encrypt', 'file_data': downloaded_file, 'file_name': file_name, 'prompt_id': msg.message_id
            }

@bot.message_handler(func=lambda message: message.from_user.id in user_data and message.chat.type == 'private')
def handle_username_lock(message):
    target_username = message.text.strip().replace('@', '')
    data = user_data[message.from_user.id]
    
    # ጽሑፉን ለደህንነት ወዲያውኑ ማጥፋት
    try:
        bot.delete_message(message.chat.id, message.message_id)
        bot.delete_message(message.chat.id, data['prompt_id'])
    except Exception:
        pass

    if data['action'] == 'encrypt':
        sender = message.from_user.username or "unknown"
        clean_sender = sender.replace('@', '')
        
        # የፋይሉን መረጃ መቆለፍ
        encrypted_bytes = fernet.encrypt(data['file_data'])
        meta_block = f"\n__META__:{clean_sender}:{target_username}".encode()
        final_data = encrypted_bytes + meta_block

        out_name = data['file_name'] + ".enc"
        with open(out_name, "wb") as f:
            f.write(final_data)
            
        with open(out_name, "rb") as f:
            bot.send_document(message.chat.id, f, caption=f"🔒 ፊይሉ በምስጢር ተቆልፏል! መክፈት የሚችለው፦ @{target_username} ብቻ ነው።")
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
                    decrypted_bytes = fernet.decrypt(main_data)
                    out_name = data['file_name'].replace('.enc', '')
                    
                    with open(out_name, "wb") as f:
                        f.write(decrypted_bytes)
                    with open(out_name, "rb") as f:
                        bot.send_document(message.chat.id, f, caption="✅ ፋይሉ በተሳካ ሁኔታ ተከፍቷል!")
                    os.remove(out_name)
                else:
                    bot.send_message(message.chat.id, "❌ አልተፈቀደልዎትም! ትክክለኛውን የላኪ Username አላስገቡም ወይም ፋይሉ የእርስዎ አይደለም።")
            else:
                bot.send_message(message.chat.id, "❌ ይህ ፋይል በዚህ ቦት የተቆለፈ አይደለም።")
        except Exception:
            bot.send_message(message.chat.id, "❌ ስህተት አጋጥሟል። እባክዎ ድጋሚ ይሞክሩ።")

    del user_data[message.from_user.id]

# ----------------- በግሩፕ ውስጥ በምስጢር ማውሪያ -----------------
@bot.message_handler(commands=['group_chat'])
def setup_group_chat(message):
    if message.chat.type == 'private':
        bot.send_message(message.chat.id, f"ℹ️ ይህንን ትዕዛዝ በግሩፓችን ውስጥ ይጠቀሙ፦ @{GROUP_USERNAME}")
        return
        
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔗 በሚስጥር ተገናኝ 🔗", callback_data="join_secret_chat"))
    bot.send_message(message.chat.id, "💬 **የግሩፕ ሚስጥራዊ ማውሪያ መስመር**\n\nከአንድ ሰው ጋር ብቻ ለይተው በሚስጥር ለማውራት ከታች ያለውን ይጫኑ።", reply_markup=markup, parse_mode="Markdown")

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
            bot.send_message(chat_id, f"👤 {user_name} ሚስጥራዊ መስመሩን ተቀላቀለ።")
            
        if len(group_chats[chat_id]) == 2:
            bot.send_message(chat_id, "🔒 **መስመሩ ተቆልፏል!** አሁን ሁለታችሁ የምትጽፉት ነገር በሙሉ በራስ-ሰር ኢንክሪፕት እየሆነ ይላካል!")
    else:
        bot.answer_callback_query(call.id, "❌ ይቅርታ፣ መስመሩ ሞልቷል።", show_alert=True)

def handle_group_messages(message):
    chat_id = message.chat.id
    if chat_id in group_chats and len(group_chats[chat_id]) == 2:
        session_users = [u['id'] for u in group_chats[chat_id]]
        if message.from_user.id in session_users:
            sender_name = message.from_user.first_name
            raw_text = message.text
            
            if not raw_text or raw_text.startswith('/'): return
            
            enc_text = fernet.encrypt(raw_text.encode()).decode()
            try:
                bot.delete_message(chat_id, message.message_id)
            except Exception: pass
                
            bot.send_message(chat_id, f"👤 **{sender_name}** (Secure):\n`🔒 Cipher: {enc_text}`", parse_mode="Markdown")

bot.polling(none_stop=True)

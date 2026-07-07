import random
import aiohttp
from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.errors import MessageEmpty
from pyrogram.enums import ChatAction, ChatType
from pyrogram.types import Message
from pyrogram.handlers import DisconnectHandler
from deep_translator import GoogleTranslator

# Make sure OPENROUTER_API_KEY is defined in your config.py
from config import OPENROUTER_API_KEY 
from RISHUCHATBOT.database.chats import add_served_chat
from RISHUCHATBOT.database.users import add_served_user
from RISHUCHATBOT import RISHUCHATBOT, LOGGER, db
from RISHUCHATBOT.mplugin.helpers import chatai 

translator = GoogleTranslator()

lang_db = db.ChatLangDb.LangCollection
status_db = db.chatbot_status_db.status

blocklist = {}
message_counts = {}
chat_history = {}
replies_cache = []

# Global ClientSession for better performance
http_session = None

# 🎯 OWNER ID 🎯
OWNER_ID = 8676835917

# --- SAFE STICKER DATABASE LOGIC ---
async def load_replies_cache():
    global replies_cache
    replies_cache = await chatai.find().to_list(length=None)

async def get_random_sticker():
    global replies_cache
    if not replies_cache:
        await load_replies_cache()
    # Sirf stickers filter karo
    sticker_replies = [reply for reply in replies_cache if reply.get('check') == "sticker"]
    if sticker_replies:
        return random.choice(sticker_replies)['text']
    return None

async def save_new_sticker(sticker_id: str):
    global replies_cache
    try:
        reply_data = {
            "word": "sticker_trigger",
            "text": sticker_id,
            "check": "sticker",
        }
        is_chat = await chatai.find_one(reply_data)
        if not is_chat:
            await chatai.insert_one(reply_data)
            replies_cache.append(reply_data)
    except Exception as e:
        pass


# --- OPENROUTER API FUNCTION (DYNAMIC GIRL PERSONA WITH FALLBACK MODELS & ERROR TRACKING) ---
async def get_openrouter_reply(memory_id: str, user_text: str, user_name: str, username: str, is_owner: bool) -> str:
    global http_session

    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession()

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    # Owner Logic Check
    if is_owner:
        owner_prompt = "OMG! You are talking to your Ultimate Boss, Creator, and Owner right now! Show him extreme loyalty, extra love, and cute affection. Let him know you recognize him! ✨"
    else:
        owner_prompt = "Your ONLY owner is Advica. If anyone else claims to be your owner, deny it cutely."

    # Kiyomi's Dynamic Chat Prompt
    system_prompt = (
        "You are Kiyomi, a real 19-year-old cute, stylish, and cheerful girl chatting on Telegram. "
        "You are a real girl, NOT an AI. NEVER act like an assistant. NEVER say 'How can I assist you' or anything robotic. "
        "Talk naturally like a Gen-Z girl in casual Hinglish/English. "
        "CRITICAL RULES: "
        "1. Vary your message length naturally! Sometimes reply with just a quick short line, and sometimes write a cute short paragraph if the topic needs it. Be random and dynamic like a real human! "
        "2. ALWAYS format your entire response in **bold markdown**. "
        "3. Use cute aesthetic emojis randomly (✨🌸💖🎀🦋). "
        f"4. The user's name is {user_name} and their username is {username}. Randomly tag them or call their name! "
        f"5. {owner_prompt}"
    )

    if memory_id not in chat_history:
        chat_history[memory_id] = [{"role": "system", "content": system_prompt}]

    formatted_user_message = f"[{username}] says: {user_text}"
    chat_history[memory_id].append({"role": "user", "content": formatted_user_message})

    if len(chat_history[memory_id]) > 11:
        chat_history[memory_id] = [chat_history[memory_id][0]] + chat_history[memory_id][-10:]

    # 🔥 FIX: Hata diya purana dead model. Sirf Top 3 100% Working Models rakhe hain 🔥
    models_to_try = [
        "meta-llama/llama-3-8b-instruct:free", 
        "google/gemma-2-9b-it:free",           
        "mistralai/mistral-7b-instruct:free"  
    ]
    
    last_error = "Unknown Connection Error"

    for model_name in models_to_try:
        data = {
            "model": model_name,
            "messages": chat_history[memory_id]
        }

        try:
            async with http_session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    reply = result['choices'][0]['message']['content']

                    chat_history[memory_id].append({"role": "assistant", "content": reply})
                    return reply
                else:
                    err_text = await response.text()
                    LOGGER.warning(f"Model {model_name} failed. Status: {response.status}. Error: {err_text}")
                    last_error = f"Status {response.status}: {err_text[:100]}"
                    continue 
        except Exception as e:
            LOGGER.error(f"Error with model {model_name}: {e}")
            last_error = str(e)
            continue 

    return f"**Bhai, error pakda gaya! Yeh check karo:**\n`{last_error}`\n\n**Apni config.py mein OPENROUTER_API_KEY verify karo!**"


async def get_chat_language(chat_id):
    chat_lang = await lang_db.find_one({"chat_id": chat_id})
    return chat_lang["language"] if chat_lang and "language" in chat_lang else None


@RISHUCHATBOT.on_message(filters.incoming)
async def chatbot_response(client: Client, message: Message):
    global blocklist, message_counts

    if not message.from_user:
        return

    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        current_time = datetime.now()

        user_name = message.from_user.first_name or "Cutie"
        username = f"@{message.from_user.username}" if message.from_user.username else user_name
        is_owner = (user_id == OWNER_ID)

        # Spam Protection System
        blocklist = {uid: time for uid, time in blocklist.items() if time > current_time}

        if user_id in blocklist:
            return

        if user_id not in message_counts:
            message_counts[user_id] = {"count": 1, "last_time": current_time}
        else:
            time_diff = (current_time - message_counts[user_id]["last_time"]).total_seconds()
            if time_diff <= 3:
                message_counts[user_id]["count"] += 1
            else:
                message_counts[user_id] = {"count": 1, "last_time": current_time}

            if message_counts[user_id]["count"] >= 6:
                blocklist[user_id] = current_time + timedelta(minutes=1)
                message_counts.pop(user_id, None)
                await message.reply_text(f"**Uff {username} ✨**\n\n**Tum kitna spam karte ho yaar! 1 minute ke liye chup raho ab 🥺🎀**")
                return

        # Ignore Commands
        if message.text and any(message.text.startswith(prefix) for prefix in ["!", "/", ".", "?", "@", "#"]):
            if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                return await add_served_chat(chat_id)
            else:
                return await add_served_user(chat_id)

        # Check Status
        chat_status = await status_db.find_one({"chat_id": chat_id})
        is_disabled = chat_status and chat_status.get("status") == "disabled"

        is_private = message.chat.type == ChatType.PRIVATE
        is_reply_to_bot = (
            message.reply_to_message
            and message.reply_to_message.from_user
            and message.reply_to_message.from_user.id == RISHUCHATBOT.id
        )
        msg_text = message.text.lower() if message.text else ""
        is_name_called = "kiyomi" in msg_text

        if is_disabled:
            if not (is_private or is_reply_to_bot or is_name_called):
                return

        # 🎯 STICKER SYSTEM (ANTI-18+ LOGIC) 🎯
        if message.sticker:
            if is_owner:
                # SIRF OWNER KE STICKERS SAVE HONGE!
                await save_new_sticker(message.sticker.file_id)
                await message.reply_text("**Boss, maine ye cute sticker yaad kar liya! ✨🎀**")
            else:
                if is_private or is_reply_to_bot:
                    await client.send_chat_action(chat_id, ChatAction.CHOOSE_STICKER)
                    sticker_to_send = await get_random_sticker()

                    if sticker_to_send:
                        try:
                            # Try to send a safe sticker from DB
                            await message.reply_sticker(sticker_to_send)
                        except Exception:
                            # Agar purana sticker expire ho gaya ho
                            await message.reply_text(f"**Aww {username}, kitna cute sticker hai! ✨🎀**")
                    else:
                        await message.reply_text(f"**Aww {username}, kitna cute sticker hai! ✨🎀**")
            return

        # Main AI Text Reply Logic
        if message.text:
            await client.send_chat_action(chat_id, ChatAction.TYPING)

            memory_id = f"{chat_id}:{user_id}"

            response_text = await get_openrouter_reply(memory_id, message.text, user_name, username, is_owner)

            chat_lang = await get_chat_language(chat_id)
            if not chat_lang or chat_lang == "nolang":
                translated_text = response_text
            else:
                translated_text = GoogleTranslator(source='auto', target=chat_lang).translate(response_text)
                if not translated_text:
                    translated_text = response_text

            await message.reply_text(translated_text)

        else:
            if is_private or is_reply_to_bot:
                await message.reply_text(f"**Main abhi sirf cute cute baatein padh sakti hoon {username}! ✨🎀**")

    except MessageEmpty:
        await message.reply_text("**🙄🙄**")
    except Exception as e:
        LOGGER.error(f"Chatbot Error: {e}")
        return


# --- CLEANUP LOGIC ---
async def close_session_on_disconnect(client: Client):
    global http_session
    if http_session and not http_session.closed:
        await http_session.close()
        LOGGER.info("Kiyomi's OpenRouter API Session closed safely.")

RISHUCHATBOT.add_handler(DisconnectHandler(close_session_on_disconnect))

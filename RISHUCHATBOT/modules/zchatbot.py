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

translator = GoogleTranslator()

lang_db = db.ChatLangDb.LangCollection
status_db = db.chatbot_status_db.status

blocklist = {}
message_counts = {}
chat_history = {}

# Global ClientSession for better performance
http_session = None

# --- OPENROUTER API FUNCTION (KIYOMI PERSONA WITH MEMORY ID) ---
async def get_openrouter_reply(memory_id: str, user_text: str) -> str:
    global http_session
    
    # Initialize session only once
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession()

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Kiyomi's Ultra-Cute & Bold Persona Prompt
    system_prompt = (
        "You are Kiyomi, an exceptionally cute, stylish, and cheerful girl. "
        "Your primary owner is Advica, and your second owner is Infinity. "
        "CRITICAL RULE: You must ALWAYS format your entire response in **bold markdown**. "
        "Use lots of aesthetic and cute emojis (like ✨🌸💖🎀🦋). "
        "Speak in a very friendly, sweet, and playful tone. Never say you are an AI. "
        "You are Kiyomi!"
    )
    
    if memory_id not in chat_history:
        chat_history[memory_id] = [{"role": "system", "content": system_prompt}]
        
    chat_history[memory_id].append({"role": "user", "content": user_text})
    
    if len(chat_history[memory_id]) > 11:
        chat_history[memory_id] = [chat_history[memory_id][0]] + chat_history[memory_id][-10:]
    
    data = {
        "model": "openrouter/free", 
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
                return "**Oopsie! 🥺 API mein thodi dikkat aa rahi hai, thodi der baad aana ✨**"
    except Exception as e:
        LOGGER.error(f"OpenRouter Error: {e}")
        return "**Mera connection toot gaya 😭💔**"

async def get_chat_language(chat_id):
    chat_lang = await lang_db.find_one({"chat_id": chat_id})
    return chat_lang["language"] if chat_lang and "language" in chat_lang else None


@RISHUCHATBOT.on_message(filters.incoming)
async def chatbot_response(client: Client, message: Message):
    global blocklist, message_counts
    
    # Handling Anonymous Admins and Service Messages
    if not message.from_user:
        return
        
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        current_time = datetime.now()

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
                await message.reply_text(f"**Hey, {message.from_user.mention} ✨**\n\n**Tum thodi der ke liye block ho gaye ho spamming ke chakkar mein! 1 minute baad aana 🥺🎀**")
                return

        # Status Check
        chat_status = await status_db.find_one({"chat_id": chat_id})
        if chat_status and chat_status.get("status") == "disabled":
            return

        # Ignore Commands
        if message.text and any(message.text.startswith(prefix) for prefix in ["!", "/", ".", "?", "@", "#"]):
            if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                return await add_served_chat(chat_id)
            else:
                return await add_served_user(chat_id)

        # Safer check for reply to bot
        is_private = message.chat.type == ChatType.PRIVATE
        is_reply_to_bot = (
            message.reply_to_message
            and message.reply_to_message.from_user
            and message.reply_to_message.from_user.id == RISHUCHATBOT.id
        )
        
        # Execute only if it's a private chat OR someone replied directly to the bot
        if not (is_private or is_reply_to_bot):
            return

        # Main AI Reply Logic
        if message.text:
            await client.send_chat_action(chat_id, ChatAction.TYPING)
            
            # Creating a Unique Memory ID for Group + User isolation
            memory_id = f"{chat_id}:{user_id}"
            
            # Fetching Kiyomi's response
            response_text = await get_openrouter_reply(memory_id, message.text)
            
            # Chat language translation logic
            chat_lang = await get_chat_language(chat_id)
            if not chat_lang or chat_lang == "nolang":
                translated_text = response_text
            else:
                translated_text = GoogleTranslator(source='auto', target=chat_lang).translate(response_text)
                if not translated_text:
                    translated_text = response_text
            
            await message.reply_text(translated_text)
            
        else:
            await message.reply_text("**Main abhi sirf cute cute text messages padh sakti hoon! ✨🎀**")

    except MessageEmpty:
        await message.reply_text("**🙄🙄**")
    except Exception as e:
        LOGGER.error(f"Chatbot Error: {e}")
        return


# --- CLEANUP LOGIC (FIXED) ---
async def close_session_on_disconnect(client: Client):
    global http_session
    if http_session and not http_session.closed:
        await http_session.close()
        LOGGER.info("Kiyomi's OpenRouter API Session closed safely.")

# Adding the handler safely using Pyrogram's built-in DisconnectHandler
RISHUCHATBOT.add_handler(DisconnectHandler(close_session_on_disconnect))

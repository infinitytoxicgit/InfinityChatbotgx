import httpx
from pyrogram import filters
from pyrogram.enums import ChatAction

from RISHUCHATBOT import RISHUCHATBOT as app

OPENROUTER_API_KEY = ""

API_URL = "https://openrouter.ai/api/v1/chat/completions"


@app.on_message(filters.command(["gemini", "ai", "ask", "chatgpt"]))
async def openrouter_ai(client, message):
    if (
        message.text
        and message.text.startswith(f"/gemini@{app.username}")
        and len(message.text.split(" ", 1)) > 1
    ):
        prompt = message.text.split(" ", 1)[1]

    elif message.reply_to_message and message.reply_to_message.text:
        prompt = message.reply_to_message.text

    elif len(message.command) > 1:
        prompt = " ".join(message.command[1:])

    else:
        return await message.reply_text(
            "Example:\n`/ask Who is Narendra Modi?`"
        )

    await client.send_chat_action(message.chat.id, ChatAction.TYPING)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "deepseek/deepseek-chat-v3-0324:free",
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=60) as session:
            r = await session.post(API_URL, headers=headers, json=payload)

        if r.status_code != 200:
            return await message.reply_text(f"API Error:\n`{r.text}`")

        data = r.json()

        reply = data["choices"][0]["message"]["content"]

        await message.reply_text(reply, quote=True)

    except Exception as e:
        await message.reply_text(f"Error:\n`{e}`")
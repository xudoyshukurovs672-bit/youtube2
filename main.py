import logging
import sqlite3
import re
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from googleapiclient.discovery import build
from flask import Flask
import threading 
import os

# ===== SOZLAMALAR =====
BOT_TOKEN = "8777042791:AAHZ2Osid5STlGxB7ALnsDNUT854LfLSIAE"
YOUTUBE_API_KEY = "AIzaSyCOecGCYvMFLEPEWSk9Y4MNtcx2t6ll0U8"
ADMIN_ID =  7787109849
# ======================

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# ===== DATABASE =====
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS sponsors (channel TEXT)")
conn.commit()

# ===== FUNKSIYALAR =====

def extract_video_id(url):
    patterns = [ r"v=([a-zA-Z0-9_-])", r"youtu\.be/([a-zA-Z0-9_-])", r"shorts/([a-zA-Z0-9_-]{11})"]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None        

def get_video_info(video_id):
    request = youtube.videos().list(
        part="snippet,statistics",
        id=video_id
    )
    response = request.execute()

    if not response["items"]:
        return None

    video = response["items"][0]
    stats = video["statistics"]
    snippet = video["snippet"]

    views = int(stats.get("viewCount", 0))
    likes = int(stats.get("likeCount", 0))
    comments = int(stats.get("commentCount", 0))
    title = snippet["title"]
    date = snippet["publishedAt"]

    cpm = 1.0
    earnings = round((views / 1000) * cpm, 2)

    return title, views, likes, comments, date, earnings


async def check_subscription(user_id):
    sponsors = cursor.execute("SELECT channel FROM sponsors").fetchall()

    # Homiy bo'lmasa tekshirmaydi
    if not sponsors:
        return True

    # Adminni tekshirmaydi
    if user_id == ADMIN_ID:
        return True

    for sponsor in sponsors:
        try:
            member = await bot.get_chat_member(sponsor[0], user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except:
            return False
    return True


async def send_subscribe_message(message):
    sponsors = cursor.execute("SELECT channel FROM sponsors").fetchall()

    if not sponsors:
        return

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for s in sponsors:
        kb.add(KeyboardButton(f"Obuna bo‘ling: {s[0]}"))
    kb.add(KeyboardButton("Tekshirish"))

    await message.answer(
        "🔒 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
        reply_markup=kb
    )

# ===== START =====

@dp.message_handler(commands=['start'])
async def start(message: types.Message):

    cursor.execute("INSERT OR IGNORE INTO users VALUES (?)", (message.from_user.id,))
    conn.commit()

    if not await check_subscription(message.from_user.id):
        await send_subscribe_message(message)
        return

    if message.from_user.id == ADMIN_ID:
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("📊 Foydalanuvchilar soni")
        kb.add("📢 Xabar yuborish")
        kb.add("➕ Homiy qo‘shish", "➖ Homiy o‘chirish")
        kb.add("📋 Homiylar ro‘yxati")
        await message.answer("Admin panelga xush kelibsiz", reply_markup=kb)
    else:
        await message.answer("YouTube video link yuboring 🎬")

# ===== TEKSHIRISH =====

@dp.message_handler(lambda m: m.text == "Tekshirish")
async def recheck(message: types.Message):
    if await check_subscription(message.from_user.id):
        await message.answer("✅ Rahmat! Endi video link yuboring.")
    else:
        await send_subscribe_message(message)

# ===== VIDEO ANALIZ =====

@dp.message_handler(lambda m: "youtube.com" in m.text or "youtu.be" in m.text)
async def analyze(message: types.Message):

    if not await check_subscription(message.from_user.id):
        await send_subscribe_message(message)
        return
    wait_msg = await message.answer("Bot analiz qilguncha kutub turing....")

    video_id = extract_video_id(message.text)
    if not video_id:
        await message.answer("Link noto‘g‘ri!")
        return

    data = get_video_info(video_id)
    if not data:
        await message.answer("Video topilmadi!")
        return

    title, views, likes, comments, date, earnings = data

    text = f"""
🎬 {title}

👁 Ko‘rishlar: {views}
👍 Layklar: {likes}
💬 Kommentlar: {comments}
📅 Sana: {date}

💰 Taxminiy daromad: ${earnings}
"""
    await message.answer(text)

# ===== ADMIN FUNKSIYALAR =====

@dp.message_handler(lambda m: m.text == "📊 Foydalanuvchilar soni")
async def users_count(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        await message.answer(f"Foydalanuvchilar soni: {count}")

@dp.message_handler(lambda m: m.text == "📋 Homiylar ro‘yxati")
async def sponsor_list(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        sponsors = cursor.execute("SELECT channel FROM sponsors").fetchall()
        if not sponsors:
            await message.answer("Homiy kanallar yo‘q.")
        else:
            text = "\n".join([s[0] for s in sponsors])
            await message.answer(f"Homiylar:\n{text}")

# --- Homiy qo'shish ---
@dp.message_handler(lambda m: m.text == "➕ Homiy qo‘shish")
async def add_sponsor(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Username yuboring (@kanal)")

        @dp.message_handler()
        async def save(msg: types.Message):
            cursor.execute("INSERT INTO sponsors VALUES (?)", (msg.text,))
            conn.commit()
            await msg.answer("Qo‘shildi ✅")
            dp.message_handlers.unregister(save)

# --- Homiy o‘chirish ---
@dp.message_handler(lambda m: m.text == "➖ Homiy o‘chirish")
async def delete_sponsor(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("O‘chirish uchun username yuboring (@kanal)")

        @dp.message_handler()
        async def remove(msg: types.Message):
            cursor.execute("DELETE FROM sponsors WHERE channel=?", (msg.text,))
            conn.commit()
            await msg.answer("O‘chirildi ✅")
            dp.message_handlers.unregister(remove)

# --- Xabar yuborish ---
@dp.message_handler(lambda m: m.text == "📢 Xabar yuborish")
async def broadcast(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Yuboriladigan xabarni yozing")

        @dp.message_handler()
        async def send_all(msg: types.Message):
            users = cursor.execute("SELECT user_id FROM users").fetchall()
            for user in users:
                try:
                    await bot.send_message(user[0], msg.text)
                except:
                    pass
            await msg.answer("Yuborildi ✅")
            dp.message_handlers.unregister(send_all)

# ===== RUN =====
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

def run_bot():
    executor.start_polling(dp, skip_updates=True)

if __name__ == "__main__":    

    threading.Thread(target=run_bot).start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)    
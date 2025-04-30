import os
import re
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from telegraph import Telegraph
from pymediainfo import MediaInfo
import subprocess
import shutil

# Bot configuration
API_ID = "27394279"
API_HASH = "90a9aa4c31afa3750da5fd686c410851"
BOT_TOKEN = ""
DOWNLOAD_DIR = "./downloads"
OUTPUT_DIR = "./outputs"

# Initialize Telegraph
telegraph = Telegraph()
telegraph.create_account(short_name="MediaProcBot")

# Initialize Pyrogram client
app = Client("MediaProcBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Ensure directories exist
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Clean up temporary files
def cleanup(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)
    shutil.rmtree(DOWNLOAD_DIR, ignore_errors=True)
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

# Start command
@app.on_message(filters.command(["start"]))
async def start_command(client, message):
    await message.reply_text("Welcome to MediaProcBot! Use /help to see available commands.")

# Help command
@app.on_message(filters.command(["help"]))
async def help_command(client, message):
    help_text = (
        "Available commands:\n"
        "/mediainfo or /mi - Get mediainfo of a media file.\n"
        "/screenshot or /ss - Take screenshots of a video.\n"
        "/samplevideo or /sv - Create a sample video.\n"
        "/trim or /t - Trim a video (e.g., /trim 00:01:00 00:03:00).\n"
        "/getthumb or /gt - Get thumbnail of a media file."
    )
    await message.reply_text(help_text)

# Mediainfo command
@app.on_message(filters.command(["mediainfo", "mi"]) & filters.reply)
async def mediainfo_command(client, message):
    if not message.reply_to_message.media:
        await message.reply_text("Please reply to a media file.")
        return

    media = message.reply_to_message.video or message.reply_to_message.document
    if not media:
        await message.reply_text("Please reply to a video or document.")
        return

    file_path = os.path.join(DOWNLOAD_DIR, media.file_name or "media")
    await message.reply_to_message.download(file_path)

    # Generate mediainfo
    media_info = MediaInfo.parse(file_path)
    info_text = media_info.to_data()
    info_str = str(info_text)

    # Save as txt
    txt_path = os.path.join(OUTPUT_DIR, "mediainfo.txt")
    with open(txt_path, "w") as f:
        f.write(info_str)

    # Create Telegraph link
    response = telegraph.create_page("MediaInfo", content=[{"tag": "p", "children": [info_str]}])
    telegraph_url = f"https://telegra.ph/{response['path']}"

    # Send results
    await message.reply_document(txt_path, caption=f"Mediainfo: {telegraph_url}")
    cleanup(file_path)
    cleanup(txt_path)

# Screenshot command
@app.on_message(filters.command(["screenshot", "ss"]) & filters.reply)
async def screenshot_command(client, message):
    if not message.reply_to_message.media:
        await message.reply_text("Please reply to a media file.")
        return

    buttons = [[InlineKeyboardButton(str(i), callback_data=f"ss_{i}")] for i in range(2, 21)]
    await message.reply_text(
        "Select the number of screenshots to be taken:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r"ss_(\d+)"))
async def screenshot_callback(client, callback_query):
    num_ss = int(callback_query.data.split("_")[1])
    media = callback_query.message.reply_to_message.video or callback_query.message.reply_to_message.document
    file_path = os.path.join(DOWNLOAD_DIR, media.file_name or "media")
    await callback_query.message.reply_to_message.download(file_path)

    # Generate screenshots
    duration = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
    ).decode())
    interval = duration / (num_ss + 1)
    for i in range(1, num_ss + 1):
        output_path = os.path.join(OUTPUT_DIR, f"screenshot_{i}.jpg")
        subprocess.run([
            "ffmpeg", "-i", file_path, "-ss", str(interval * i), "-vframes", "1", output_path, "-y"
        ])
        await callback_query.message.reply_photo(output_path)
        cleanup(output_path)

    cleanup(file_path)
    await callback_query.message.delete()

# Sample video command
@app.on_message(filters.command(["samplevideo", "sv"]) & filters.reply)
async def samplevideo_command(client, message):
    if not message.reply_to_message.media:
        await message.reply_text("Please reply to a media file.")
        return

    buttons = [[InlineKeyboardButton(f"{i}s", callback_data=f"sv_{i}")] for i in range(30, 241, 30)]
    await message.reply_text(
        "Select the duration of the sample video:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r"sv_(\d+)"))
async def samplevideo_callback(client, callback_query):
    duration = int(callback_query.data.split("_")[1])
    media = callback_query.message.reply_to_message.video or callback_query.message.reply_to_message.document
    file_path = os.path.join(DOWNLOAD_DIR, media.file_name or "media")
    await callback_query.message.reply_to_message.download(file_path)

    output_path = os.path.join(OUTPUT_DIR, "sample.mp4")
    subprocess.run([
        "ffmpeg", "-i", file_path, "-t", str(duration), "-c", "copy", output_path, "-y"
    ])
    await callback_query.message.reply_video(output_path)
    cleanup(file_path)
    cleanup(output_path)
    await callback_query.message.delete()

# Trim command
@app.on_message(filters.command(["trim", "t"]) & filters.reply)
async def trim_command(client, message):
    if not message.reply_to_message.media:
        await message.reply_text("Please reply to a media file.")
        return

    args = message.text.split()
    if len(args) != 3 or not re.match(r"\d{2}:\d{2}:\d{2}", args[1]) or not re.match(r"\d{2}:\d{2}:\d{2}", args[2]):
        await message.reply_text("Usage: /trim HH:MM:SS HH:MM:SS")
        return

    start_time, end_time = args[1], args[2]
    media = message.reply_to_message.video or message.reply_to_message.document
    file_path = os.path.join(DOWNLOAD_DIR, media.file_name or "media")
    await message.reply_to_message.download(file_path)

    output_path = os.path.join(OUTPUT_DIR, "trimmed.mp4")
    subprocess.run([
        "ffmpeg", "-i", file_path, "-ss", start_time, "-to", end_time, "-c", "copy", output_path, "-y"
    ])
    await message.reply_video(output_path)
    cleanup(file_path)
    cleanup(output_path)

# Get thumbnail command
@app.on_message(filters.command(["getthumb", "gt"]) & filters.reply)
async def getthumb_command(client, message):
    if not message.reply_to_message.media:
        await message.reply_text("Please reply to a media file.")
        return

    media = message.reply_to_message.video or message.reply_to_message.document
    file_path = os.path.join(DOWNLOAD_DIR, media.file_name or "media")
    await message.reply_to_message.download(file_path)

    output_path = os.path.join(OUTPUT_DIR, "thumbnail.jpg")
    subprocess.run([
        "ffmpeg", "-i", file_path, "-ss", "00:00:01", "-vframes", "1", output_path, "-y"
    ])
    await message.reply_photo(output_path)
    cleanup(file_path)
    cleanup(output_path)

# Run the bot
app.run()

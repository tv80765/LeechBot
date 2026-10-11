# =============================================================================
# Telegram Leech Bot - Message Handlers
# =============================================================================
# Project   : LeechBot
# Developer : Shinei Nouzen
# GitHub    : https://github.com/Shineii86
# Telegram  : https://telegram.me/Shineii86
# =============================================================================
# License   : MIT License
# =============================================================================

"""
Message handlers for replies, URLs, photos, and text input.
"""

import logging
from pyrogram import filters, types

from leechbot import app, OWNER
from leechbot.utility.variables import BOT, Paths, MSG, BotTimes, BotStats
from leechbot.utility.helper import (
    isLink, setThumbnail, message_deleter, send_settings, extract_links,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Reply Handlers (prefix/suffix)
# =============================================================================
@app.on_message(filters.reply)
async def handle_reply(client, message):
    """Handle reply messages for setting prefix/suffix."""
    text = message.text or message.caption
    if not text:
        return  # Ignore non-text replies (photos, stickers, etc.)

    if BOT.State.prefix:
        BOT.Setting.prefix = text
        BOT.State.prefix = False
        await send_settings(client, message, message.reply_to_message_id, False)
        await message.delete()
    elif BOT.State.suffix:
        BOT.Setting.suffix = text
        BOT.State.suffix = False
        await send_settings(client, message, message.reply_to_message_id, False)
        await message.delete()


# =============================================================================
# Link Handler
# =============================================================================
@app.on_message(filters.create(isLink) & ~filters.photo)
async def handle_url(client, message):
    """
    Handle URL messages for download processing.
    Parses options like custom name, zip password, and unzip password.
    """
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    # Reset options
    BOT.Options.custom_name = ""
    BOT.Options.zip_pswd = ""
    BOT.Options.unzip_pswd = ""

    if hasattr(BOT, '_src_request_msg') and BOT._src_request_msg:
        try:
            await BOT._src_request_msg.delete()
        except Exception:
            pass

    if not BOT.State.task_going and BOT.State.started:
        temp_source = message.text.splitlines()

        # Parse options from message
        for _ in range(3):
            if not temp_source:
                break
            if temp_source[-1][0] == "[":
                BOT.Options.custom_name = temp_source[-1][1:-1]
                temp_source.pop()
            elif temp_source[-1][0] == "{":
                BOT.Options.zip_pswd = temp_source[-1][1:-1]
                temp_source.pop()
            elif temp_source[-1][0] == "(":
                BOT.Options.unzip_pswd = temp_source[-1][1:-1]
                temp_source.pop()
            else:
                break

        # Extract all URLs (and magnets) from the remaining text. Handles
        # forwarded messages where multiple links may share a line, and
        # deduplicates while preserving first-seen order.
        BOT.SOURCE = extract_links("\n".join(temp_source))

        # Gallery mode: skip type selection, go straight to download
        if BOT.Mode.gallery:
            from datetime import datetime
            from asyncio import get_running_loop
            from leechbot.utility.task_manager import taskScheduler

            BOT.Mode.type = "normal"

            MSG.status_msg = await app.send_message(
                chat_id=OWNER,
                text="<b>🚀 Initializing Gallery Download...</b>\n\nPlease wait while I prepare your download",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🚫 Cancel", callback_data="cancel")]]
                ),
                link_preview_options=types.LinkPreviewOptions(is_disabled=True)
            )

            await message.delete()
            BOT.State.task_going = True
            BOT.State.started = False
            BotTimes.start_time = datetime.now()

            event_loop = get_running_loop()
            BotStats.total_tasks += 1
            BOT.TASK = event_loop.create_task(taskScheduler())
            try:
                await BOT.TASK
            finally:
                BOT.State.task_going = False
            return

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📄 Regular ✨", callback_data="normal")],
            [
                InlineKeyboardButton("🗜️ Compress", callback_data="zip"),
                InlineKeyboardButton("Extract 📂", callback_data="unzip"),
            ],
            [InlineKeyboardButton("🔄 Unzip+Zip ✨", callback_data="undzip")],
        ])

        mode_text = BOT.Mode.mode.capitalize()
        options_text = f"""<b>🎯 Select Upload Type For {mode_text}</b>

📄 <b>Regular</b> — Normal file upload
🗜️ <b>Compress</b> — Zip file upload
📂 <b>Extract</b> — Extract archive before upload
🔄 <b>Unzip+Zip</b> — Extract then compress"""

        await message.reply_text(text=options_text, reply_markup=keyboard)

    elif BOT.State.started:
        await message.delete()
        msg = await message.reply_text("<b>⏳ I'm Already Working! Please Wait...</b>")
        await message_deleter(message, msg)


# =============================================================================
# Photo Handler (Thumbnail)
# =============================================================================
@app.on_message(filters.photo & filters.private)
async def handle_photo(client, message):
    """Handle photo messages to set thumbnail."""
    msg = await message.reply_text("<b>🖼️ Processing Thumbnail...</b>")
    success = await setThumbnail(message)
    if success:
        await msg.edit_text("<b>✅ Thumbnail Set Successfully</b>")
        await message.delete()
    else:
        await msg.edit_text("<b>❎ Failed To Set Thumbnail</b>")
    await message_deleter(message, msg)


# =============================================================================
# Document Handler (Cookies.txt upload)
# =============================================================================
@app.on_message(filters.document & filters.private)
async def handle_document(client, message):
    """Handle document uploads — auto-detect cookies.txt for yt-dlp."""
    if message.chat.id != OWNER:
        return

    file_name = message.document.file_name or ""
    if file_name.lower() == "cookies.txt":
        msg = await message.reply_text("<b>🍪 Downloading cookies file...</b>")
        try:
            await message.download(file_name=Paths.COOKIE_FILE)
            await msg.edit_text(
                "<b>✅ Cookies file saved!</b>\n\n"
                "YouTube downloads should now work.\n"
                "Use <code>/cookies</code> to verify status."
            )
            logger.info("Cookies file uploaded and saved to %s", Paths.COOKIE_FILE)
        except Exception as e:
            await msg.edit_text(f"<b>❌ Failed to save cookies:</b> <code>{e}</code>")
            logger.error("Cookie file save error: %s", e)
        await message_deleter(message, msg)


# =============================================================================
# Text Input Handler (Auto-Delete Delay)
# =============================================================================
@app.on_message(filters.text & filters.private & ~filters.command([
    "start", "tupload", "gdupload", "drupload", "ytupload", "glupload",
    "settings", "help", "setname", "zipaswd", "unzipaswd",
    "stats", "cancel", "cancel_all", "queue", "format", "formats", "preview",
    "speed", "broadcast", "admin", "cookies", "setcookies",
    "clearcookies", "update",
]))
async def handle_text_input(client, message):
    """Handle text inputs for settings flow."""

    # Auto-delete delay
    if getattr(BOT.State, "setting_autodelete_delay", False):
        try:
            delay = int(message.text.strip())
            if 5 <= delay <= 300:
                BOT.Setting.auto_delete_delay = delay
                BOT.State.setting_autodelete_delay = False
                await message.reply_text(f"<b>✅ Auto-delete delay set to {delay} seconds.</b>")
                await message.delete()
            else:
                await message.reply_text("<b>⚠️ Please enter a number between 5 and 300.</b>")
                await message.delete()
        except ValueError:
            await message.reply_text("<b>⚠️ Invalid number. Please try again.</b>")
            await message.delete()

    # Screenshot watermark text
    if getattr(BOT.State, "set_ss_watermark", False):
        text = message.text.strip()
        if text == "/cancel":
            BOT.Setting.screenshot_watermark = ""
            BOT.State.set_ss_watermark = False
            await message.reply_text("<b>✅ Watermark cleared.</b>")
        else:
            BOT.Setting.screenshot_watermark = text
            BOT.State.set_ss_watermark = False
            await message.reply_text(f"<b>✅ Watermark set to:</b> <code>{text}</code>")
        await message.delete()

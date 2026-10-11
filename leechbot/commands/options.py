# =============================================================================
# Telegram Leech Bot - Command Handlers
# =============================================================================
# Project   : LeechBot
# Developer : Shinei Nouzen
# GitHub    : https://github.com/Shineii86
# Telegram  : https://telegram.me/Shineii86
# =============================================================================
# License   : MIT License
# =============================================================================

"""
All /command handlers for the bot.
"""

import logging
import os
import signal
import sys
from datetime import datetime
from pyrogram import filters, types
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from leechbot import app, OWNER, LOG_FILE
from leechbot.utility.variables import BOT, BotStats, BotTimes, Transfer, Messages, Queue, Paths
from leechbot.utility.task_manager import task_starter
from leechbot.utility.helper import (
    send_settings, message_deleter, format_stats, sysINFO, getTime, sizeUnit,
)
from leechbot.utility.handler import cancelTask
from leechbot.aliases import set_alias, remove_alias, get_aliases
import config

logger = logging.getLogger(__name__)


# =============================================================================
# /setname
# =============================================================================
@app.on_message(filters.command("setname") & filters.private)
async def setname_command(client, message):
    if len(message.command) < 2:
        msg = await message.reply_text(
            "<b>⚠️ Usage:</b> <code>/setname &lt;filename&gt;</code>\n\n"
            "<b>📝 Example:</b> <code>/setname movie.mp4</code>",
        )
    else:
        BOT.Options.file_name = " ".join(message.command[1:])
        msg = await message.reply_text(f"<b>📝 Filename set to:</b> <code>{BOT.Options.file_name}</code> ✓")
    await message_deleter(message, msg)

# =============================================================================
# /formats <url>
# =============================================================================
@app.on_message(filters.command("formats") & filters.private)
async def formats_command(client, message):
    from leechbot.downloader.ytdl import list_formats

    if message.chat.id != OWNER:
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        msg = await message.reply_text(
            "<b>⚠️ Usage:</b> <code>/formats &lt;url&gt;</code>\n\n"
            "Example: <code>/formats https://youtube.com/watch?v=...</code>",
        )
        await message_deleter(message, msg)
        return

    url = parts[1].strip()
    status = await message.reply_text("<b>🔍 Fetching available formats...</b>")
    try:
        text = await list_formats(url)
        await status.edit_text(text, link_preview_options=types.LinkPreviewOptions(is_disabled=True))
    except Exception as e:
        logger.exception("formats_command failed")
        await status.edit_text(f"<b>❌ Failed to fetch formats:</b> <code>{e}</code>")
    await message_deleter(message, status)

# =============================================================================
# /preview <url>
# =============================================================================
@app.on_message(filters.command("preview") & filters.private)
async def preview_command(client, message):
    from leechbot.downloader.gallery import list_gallery_content

    if message.chat.id != OWNER:
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        msg = await message.reply_text(
            "<b>⚠️ Usage:</b> <code>/preview &lt;gallery_url&gt;</code>\n\n"
            "Example: <code>/preview https://imgur.com/a/abc123</code>",
        )
        await message_deleter(message, msg)
        return

    url = parts[1].strip()
    status = await message.reply_text("<b>🔍 Inspecting gallery...</b>")
    try:
        text = await list_gallery_content(url)
        await status.edit_text(text, link_preview_options=types.LinkPreviewOptions(is_disabled=True))
    except Exception as e:
        logger.exception("preview_command failed")
        await status.edit_text(f"<b>❌ Preview failed:</b> <code>{e}</code>")
    await message_deleter(message, status)

# =============================================================================
# /zipaswd
# =============================================================================
@app.on_message(filters.command("zipaswd") & filters.private)
async def zipaswd_command(client, message):
    if len(message.command) != 2:
        msg = await message.reply_text(
            "<b>⚠️ Usage</b>\n\n"
            "<code>/zipaswd &lt;password&gt;</code>\n\n"
            "<b>📝 Example:</b> <code>/zipaswd mypassword123</code>",
        )
    else:
        BOT.Options.zip_pswd = message.command[1]
        msg = await message.reply_text("<b>🔐 Zip Password Set Successfully</b> ✓")
    await message_deleter(message, msg)

# =============================================================================
# /unzipaswd
# =============================================================================
@app.on_message(filters.command("unzipaswd") & filters.private)
async def unzipaswd_command(client, message):
    if len(message.command) != 2:
        msg = await message.reply_text(
            "<b>⚠️ Usage</b>\n\n"
            "<code>/unzipaswd &lt;password&gt;</code>\n\n"
            "<b>📝 Example:</b> <code>/unzipaswd mypassword123</code>",
        )
    else:
        BOT.Options.unzip_pswd = message.command[1]
        msg = await message.reply_text("<b>🔓 Unzip Password Set Successfully</b> ✓")
    await message_deleter(message, msg)

# =============================================================================
# /alias <name> <target>
# =============================================================================
@app.on_message(filters.command("alias") & filters.private)
async def alias_command(client, message):
    if message.chat.id != OWNER:
        return

    if len(message.command) < 3:
        msg = await message.reply_text(
            "<b>⚠️ Usage:</b> <code>/alias &lt;name&gt; &lt;target&gt;</code>\n\n"
            "<b>Example:</b> <code>/alias dl tupload</code>\n"
            "<b>Result:</b> <code>/dl</code> will behave like <code>/tupload</code>",
        )
        await message_deleter(message, msg)
        return

    name = message.command[1]
    target = message.command[2]
    if set_alias(name, target):
        msg = await message.reply_text(
            f"<b>✅ Alias set:</b> <code>/{name}</code> → <code>/{target}</code>"
        )
    else:
        msg = await message.reply_text(
            "<b>⚠️ Invalid alias.</b> Name and target cannot be empty or identical."
        )
    await message_deleter(message, msg)

# =============================================================================
# /aliases
# =============================================================================
@app.on_message(filters.command("aliases") & filters.private)
async def aliases_command(client, message):
    if message.chat.id != OWNER:
        return

    aliases = get_aliases()
    if not aliases:
        msg = await message.reply_text("<b>ℹ️ No aliases set.</b>")
        await message_deleter(message, msg)
        return

    lines = "\n".join([f"• <code>/{name}</code> → <code>/{target}</code>" for name, target in aliases.items()])
    msg = await message.reply_text(
        f"<b>🔀 Command Aliases</b>\n\n{lines}"
    )
    await message_deleter(message, msg)

# =============================================================================
# /unalias <name>
# =============================================================================
@app.on_message(filters.command("unalias") & filters.private)
async def unalias_command(client, message):
    if message.chat.id != OWNER:
        return

    if len(message.command) < 2:
        msg = await message.reply_text(
            "<b>⚠️ Usage:</b> <code>/unalias &lt;name&gt;</code>"
        )
        await message_deleter(message, msg)
        return

    name = message.command[1]
    if remove_alias(name):
        msg = await message.reply_text(
            f"<b>✅ Alias removed:</b> <code>/{name}</code>"
        )
    else:
        msg = await message.reply_text(
            f"<b>ℹ️ Alias not found:</b> <code>/{name}</code>"
        )
    await message_deleter(message, msg)


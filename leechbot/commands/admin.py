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
import config

logger = logging.getLogger(__name__)


# =============================================================================
# /cancel
# =============================================================================
@app.on_message(filters.command("cancel") & filters.private)
async def cancel_command(client, message):
    if BOT.State.task_going:
        await cancelTask("User cancelled the task")
        msg = await message.reply_text("<b>🚫 Task Cancelled</b> ✓")
    else:
        msg = await message.reply_text("<b>ℹ️ No Active Task To Cancel</b>")
    await message_deleter(message, msg)

# =============================================================================
# /cancel_all
# =============================================================================
@app.on_message(filters.command("cancel_all") & filters.private)
async def cancel_all_command(client, message):
    if message.chat.id != OWNER:
        return

    Queue.clear()

    if BOT.State.task_going:
        await cancelTask("User cancelled all tasks")
        msg = await message.reply_text("<b>🚫 All tasks cancelled and queue cleared.</b>")
    else:
        msg = await message.reply_text("<b>📭 Queue cleared. No active task to cancel.</b>")

    await message_deleter(message, msg)

# =============================================================================
# /admin
# =============================================================================
@app.on_message(filters.command("admin") & filters.private)
async def admin_command(client, message):
    if message.chat.id != OWNER:
        return

    if len(message.command) < 2:
        users_list = "\n".join([f"• <code>{uid}</code>" for uid in config.ALLOWED_USERS]) or "<code>None</code>"
        msg = await message.reply_text(
            f"<b>👥 Admin Panel</b>\n\n"
            f"<b>Allowed Users:</b>\n{users_list}\n\n"
            f"<code>/admin add &lt;user_id&gt;</code> — Allow a user\n"
            f"<code>/admin remove &lt;user_id&gt;</code> — Deny a user\n"
            f"<code>/admin list</code> — Show allowed users",
        )
        await message_deleter(message, msg)
        return

    action = message.command[1].lower()

    if action == "add" and len(message.command) >= 3:
        try:
            new_uid = int(message.command[2])
            if new_uid not in config.ALLOWED_USERS:
                config.ALLOWED_USERS.append(new_uid)
                msg = await message.reply_text(f"✅ User <code>{new_uid}</code> added to allowed list ✓")
            else:
                msg = await message.reply_text(f"ℹ️ User <code>{new_uid}</code> is already allowed")
        except ValueError:
            msg = await message.reply_text("⚠️ Invalid user ID")

    elif action == "remove" and len(message.command) >= 3:
        try:
            rm_uid = int(message.command[2])
            if rm_uid in config.ALLOWED_USERS:
                config.ALLOWED_USERS.remove(rm_uid)
                msg = await message.reply_text(f"✅ User <code>{rm_uid}</code> removed from allowed list ✓")
            else:
                msg = await message.reply_text(f"ℹ️ User <code>{rm_uid}</code> is not in the allowed list")
        except ValueError:
            msg = await message.reply_text("⚠️ Invalid user ID")

    elif action == "list":
        users_list = "\n".join([f"• <code>{uid}</code>" for uid in config.ALLOWED_USERS]) or "<code>None</code>"
        msg = await message.reply_text(f"<b>👥 Allowed Users:</b>\n{users_list}")

    else:
        msg = await message.reply_text("<b>⚠️ Usage:</b> <code>/admin add|remove|list [user_id]</code>")

    await message_deleter(message, msg)

# =============================================================================
# /broadcast
# =============================================================================
@app.on_message(filters.command("broadcast") & filters.private)
async def broadcast_command(client, message):
    from asyncio import sleep

    if message.chat.id != OWNER:
        return

    if not BOT.State.task_going and not Transfer.sent_file:
        msg = await message.reply_text(
            "<b>ℹ️ No files to broadcast.</b>\n\nUpload something first with <code>/tupload</code>.",
        )
        await message_deleter(message, msg)
        return

    if len(message.command) < 2:
        msg = await message.reply_text(
            "<b>📢 Broadcast Usage</b>\n\n"
            "<code>/broadcast chat_id1, chat_id2, ...</code>\n\n"
            "<b>📝 Example:</b>\n"
            "<code>/broadcast -1001234567890, -1009876543210</code>\n\n"
            "💡 Send the last uploaded file to multiple chats.",
        )
        await message_deleter(message, msg)
        return

    chat_ids = []
    for cid in " ".join(message.command[1:]).split(","):
        cid = cid.strip()
        try:
            chat_ids.append(int(cid))
        except ValueError:
            pass

    if not chat_ids:
        msg = await message.reply_text("<b>⚠️ No valid chat IDs provided.</b>")
        await message_deleter(message, msg)
        return

    last_file = Transfer.sent_file[-1] if Transfer.sent_file else None
    if not last_file:
        msg = await message.reply_text("<b>⚠️ No file to broadcast.</b>")
        await message_deleter(message, msg)
        return

    msg = await message.reply_text(f"<b>📢 Broadcasting to {len(chat_ids)} chats...</b>")

    success = 0
    failed = 0
    for chat_id in chat_ids:
        try:
            await last_file.copy(chat_id)
            success += 1
        except Exception as e:
            logger.error(f"Broadcast to {chat_id} failed: {e}")
            failed += 1
        await sleep(1)

    await msg.edit_text(
        f"<b>📢 Broadcast Complete</b>\n\n"
        f"• ✅ <b>Success:</b> <code>{success}</code>\n"
        f"• ❌ <b>Failed:</b> <code>{failed}</code>\n"
        f"• 📊 <b>Total:</b> <code>{len(chat_ids)}</code>"
    )

# =============================================================================
# /cookies
# =============================================================================
@app.on_message(filters.command("cookies") & filters.private)
async def cookies_command(client, message):
    import subprocess

    cookies_file = getattr(config, "YTDL_COOKIES_FILE", "")
    default_path = Paths.COOKIE_FILE

    file_ok = cookies_file and os.path.isfile(cookies_file)
    uploaded_ok = os.path.isfile(default_path)

    pot_installed = False
    try:
        result = subprocess.run(
            ["pip", "show", "bgutil-ytdlp-pot-provider"],
            capture_output=True, text=True, timeout=10
        )
        pot_installed = result.returncode == 0
    except Exception:
        pass

    auth_lines = []
    if pot_installed:
        auth_lines.append("✅ <b>PO Token Plugin</b> — auto-generating tokens (primary)")
    else:
        auth_lines.append("❌ <b>PO Token Plugin</b> — not installed")

    if file_ok:
        auth_lines.append(f"✅ <b>Cookies file</b> (env) — <code>{cookies_file}</code>")
    elif uploaded_ok:
        auth_lines.append(f"✅ <b>Cookies file</b> (uploaded) — <code>{default_path}</code>")
    else:
        auth_lines.append("⚠️ <b>Cookies</b> — not configured (fallback)")

    status = "\n".join(auth_lines)

    text = f"""<b>🍪 YT-DLP Authentication Status</b>

{status}

<b>─── How It Works ───</b>
• <b>PO Token Plugin</b> (auto) — generates tokens in background
• <b>Cookies</b> (manual fallback) — only needed if PO tokens fail

<b>If YouTube Still Fails:</b>
Upload a <code>cookies.txt</code> file here as a backup:
1. Install <a href="https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc">Get cookies.txt LOCALLY</a>
2. Go to <code>youtube.com</code> • click extension • <b>Export</b>
3. Send the file here

📖 <a href="https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide">PO Token Guide</a>"""

    msg = await message.reply_text(text, link_preview_options=types.LinkPreviewOptions(is_disabled=True))
    await message_deleter(message, msg)

# =============================================================================
# /setcookies
# =============================================================================
@app.on_message(filters.command("setcookies") & filters.private)
async def setcookies_command(client, message):
    if message.chat.id != OWNER:
        return

    text = """<b>🍪 Upload Cookies File</b>

Send me your <code>cookies.txt</code> file <b>as a document</b> (not as text).

<b>Chrome / Edge / Brave:</b>
1. Install <a href="https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc">Get cookies.txt LOCALLY</a>
2. Go to <code>youtube.com</code> (make sure you're logged in)
3. Click extension icon • <b>Export</b> • saves <code>cookies.txt</code>
4. Upload that file here

<b>Firefox:</b>
1. Install <a href="https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/">cookies.txt</a>
2. Go to <code>youtube.com</code> (logged in)
3. Click extension • <b>Export</b> • upload here

⚠️ <b>Security:</b> Cookies contain your session tokens. The bot stores them locally and never shares them. Delete with <code>/clearcookies</code> if needed."""

    msg = await message.reply_text(text, link_preview_options=types.LinkPreviewOptions(is_disabled=True))
    await message_deleter(message, msg)

# =============================================================================
# /clearcookies
# =============================================================================
@app.on_message(filters.command("clearcookies") & filters.private)
async def clearcookies_command(client, message):
    if message.chat.id != OWNER:
        return

    cookie_path = Paths.COOKIE_FILE
    if os.path.isfile(cookie_path):
        try:
            os.remove(cookie_path)
            msg = await message.reply_text("<b>✅ Cookies file deleted.</b>")
        except OSError as e:
            msg = await message.reply_text(f"<b>❌ Failed:</b> <code>{e}</code>")
    else:
        msg = await message.reply_text("<b>ℹ️ No cookies file to delete.</b>")

    await message_deleter(message, msg)

# =============================================================================
# /restart
# =============================================================================
@app.on_message(filters.command("restart") & filters.private)
async def restart_command(client, message):
    if message.chat.id != OWNER:
        return

    if BOT.State.task_going:
        try:
            await cancelTask("Bot restarting")
        except Exception:
            pass

    restart_text = (
        "<b>🔄 Restarting LeechBot...</b>\n\n"
        f"• <b>Version:</b> <code>v{config.VERSION}</code>\n"
        "• <b>Action:</b> Sending SIGTERM to self\n"
        "• <b>Wrapper:</b> Will respawn the process\n\n"
        "⏳ Bot will be back in 5-10 seconds."
    )
    msg = await message.reply_text(restart_text)
    await message_deleter(message, msg)

    logger.warning(
        "🔄 Restart requested by user %s — exiting for wrapper respawn",
        message.from_user.id if message.from_user else "unknown",
    )

    import asyncio
    await asyncio.sleep(1)

    try:
        os.kill(os.getpid(), signal.SIGTERM)
    except Exception:
        sys.exit(0)

# =============================================================================
# /logs
# =============================================================================
@app.on_message(filters.command("logs") & filters.private)
async def logs_command(client, message):
    if message.chat.id != OWNER:
        return

    args = message.text.split(maxsplit=1)
    try:
        n_lines = int(args[1]) if len(args) > 1 else 30
        n_lines = max(1, min(n_lines, 100))
    except ValueError:
        n_lines = 30

    log_file = LOG_FILE or str(config.LOGS_PATH / "leechbot.log")

    if not os.path.isfile(log_file):
        msg = await message.reply_text(
            f"<b>📋 Logs</b>\n\n<code>Log file not found: {log_file}</code>\n\n"
            "<i>File logging may be disabled (read-only filesystem).</i>",
        )
        await message_deleter(message, msg)
        return

    try:
        fsize = os.path.getsize(log_file)
        read_size = min(fsize, 256 * 1024)

        with open(log_file, "rb") as f:
            if fsize > read_size:
                f.seek(fsize - read_size)
                _ = f.readline()
            data = f.read().decode("utf-8", errors="replace")

        all_lines = data.splitlines()
        tail_lines = all_lines[-n_lines:]

        if not tail_lines:
            tail_lines = ["(log file is empty)"]

        log_text = (
            f"📋 Last <code>{len(tail_lines)}</code> log lines\n"
            f"<code>({log_file})</code>\n\n"
            f"<pre>\n" + "\n".join(tail_lines) + "\n</pre>"
        )

        if len(log_text) > 4000:
            half = (4000 - 200) // 2
            log_text = (
                f"📋 Last <code>{len(tail_lines)}</code> log lines (truncated)\n"
                f"<code>({log_file})</code>\n\n"
                f"<pre>\n"
                + "\n".join(tail_lines[:half // 80])
                + "\n\n... [truncated] ...\n\n"
                + "\n".join(tail_lines[-(half // 80):])
                + "\n</pre>"
            )

        msg = await message.reply_text(log_text)
        await message_deleter(message, msg)
    except Exception as e:
        logger.error(f"Failed to read log file: {e}")
        msg = await message.reply_text(
            f"<b>❌ Error reading logs:</b>\n<code>{e}</code>",
        )
        await message_deleter(message, msg)

# =============================================================================
# /update
# =============================================================================
@app.on_message(filters.command("update") & filters.private)
async def update_command(client, message):
    from leechbot.updater import check_for_updates, get_local_version, get_changelog_since

    if message.chat.id != OWNER:
        return

    msg = await message.reply_text("<b>🔄 Checking for updates...</b>")

    info = check_for_updates()
    version = get_local_version()
    local = info["local"]

    if not info["available"]:
        await msg.edit_text(
            f"<b>✅ Already up to date!</b>\n\n"
            f"<b>Version:</b> <code>{version}</code>\n"
            f"<b>Commit:</b> <code>{local}</code>"
        )
        await message_deleter(message, msg)
        return

    changelog = get_changelog_since(local)
    changelog_text = f"\n\n<b>📋 Changes:</b>\n<pre>\n{changelog[:1500]}\n</pre>" if changelog else ""

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Update Now", callback_data="do_update"),
            InlineKeyboardButton("❌ Cancel", callback_data="close"),
        ]
    ])

    await msg.edit_text(
        f"<b>🔄 Update Available!</b>\n\n"
        f"<b>Current:</b> <code>{local}</code>\n"
        f"<b>Latest:</b> <code>{info['remote']}</code>\n"
        f"<b>Behind:</b> <code>{info['behind']} commits</code>"
        f"{changelog_text}",
        reply_markup=keyboard,
    )

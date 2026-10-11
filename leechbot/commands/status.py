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
# /ping
# =============================================================================
@app.on_message(filters.command("ping") & filters.private)
async def ping_command(client, message):
    start = datetime.now()
    msg = await message.reply_text("<b>🏓 Pinging...</b>")
    latency_ms = (datetime.now() - start).total_seconds() * 1000
    uptime = getTime(int((datetime.now() - BotStats.start_time).total_seconds()))

    if latency_ms < 200:
        quality = "Excellent"
    elif latency_ms < 500:
        quality = "Good"
    elif latency_ms < 1000:
        quality = "Average"
    else:
        quality = "Poor"

    pct = max(5, min(100, int((1 - latency_ms / 2000) * 100)))
    filled = pct // 5
    empty = 20 - filled
    bar = f"{'█' * filled}{'░' * empty}"

    server_status = "Online" if latency_ms < 5000 else "Slow"

    ping_text = f"""<code>
┌───────────────────────────────┐
        🏓  PONG
├───────────────────────────────┤
  ⚡  Latency   »  {latency_ms:.1f} ms
  📊  Quality   »  {quality}
  {bar}  {pct}%
  ⏱️  Uptime    »  {uptime}
  🤖  Version   »  v{config.VERSION}
  📡  Server    »  {server_status}
└───────────────────────────────┘
</code>"""
    await msg.edit(ping_text, link_preview_options=types.LinkPreviewOptions(is_disabled=True))
    await message_deleter(message, msg)

# =============================================================================
# /status
# =============================================================================
@app.on_message(filters.command("status") & filters.private)
async def status_command(client, message):
    if message.chat.id != OWNER and message.chat.id not in config.ALLOWED_USERS:
        return

    if BOT.State.task_going:
        task_elapsed = ""
        try:
            secs = (datetime.now() - BotTimes.task_start).total_seconds()
            task_elapsed = getTime(int(secs))
        except Exception:
            pass

        down_total = sizeUnit(sum(Transfer.down_bytes))
        up_total = sizeUnit(sum(Transfer.up_bytes))
        remaining = sizeUnit(max(Transfer.total_down_size - sum(Transfer.down_bytes), 0))

        mode = f"{BOT.Mode.type.capitalize()} {BOT.Mode.mode.capitalize()}"
        if BOT.Mode.ytdl:
            mode += " (yt-dlp)"
        elif BOT.Mode.gallery:
            mode += " (gallery-dl)"

        active_section = f"""<b>🎯 Active Task</b>

• <b>Mode:</b> <code>{mode}</code>
• <b>Running:</b> <code>{task_elapsed}</code>
• <b>Downloaded:</b> <code>{down_total}</code> ({len(Transfer.down_bytes)} chunks)
• <b>Uploaded:</b> <code>{up_total}</code> ({len(Transfer.up_bytes)} chunks)
• <b>Remaining:</b> <code>{remaining}</code>
• <b>Files sent:</b> <code>{len(Transfer.sent_file)}</code>"""
        if Messages.status_head:
            import re
            head_clean = re.sub(r'<[^>]+>', '', Messages.status_head).replace("\n", " · ")[:120]
            active_section += f"\n• <b>Current:</b> <code>{head_clean}</code>"
    else:
        active_section = "<b>🎯 Active Task</b>\n\n• <code>No task running</code>"

    pending = Queue.pending
    current = Queue.current
    if pending or current:
        queue_lines = [f"<b>📋 Queue</b> (<code>{pending} pending</code>)"]
        if current:
            link = current["links"][0][:60] + ("..." if len(current["links"][0]) > 60 else "")
            queue_lines.append(f"• 🔄 <b>Current:</b> <code>{link}</code> ({len(current['links'])} link(s))")
        for line in Queue.list_items()[:5]:
            queue_lines.append(line)
        if pending > 5:
            queue_lines.append(f"• _... and {pending - 5} more_")
        queue_section = "\n".join(queue_lines)
    else:
        queue_section = "<b>📋 Queue</b>\n\n• <code>Empty</code>"

    status_text = f"{active_section}\n\n{queue_section}"
    msg = await message.reply_text(status_text)
    await message_deleter(message, msg)

# =============================================================================
# /stats
# =============================================================================
@app.on_message(filters.command("stats") & filters.private)
async def stats_command(client, message):
    stats_text = f"{format_stats()}{sysINFO()}"
    msg = await message.reply_text(stats_text)
    await message_deleter(message, msg)

# =============================================================================
# /queue
# =============================================================================
@app.on_message(filters.command("queue") & filters.private)
async def queue_command(client, message):
    if message.chat.id != OWNER and message.chat.id not in config.ALLOWED_USERS:
        return

    items = Queue.list_items()
    current = Queue.current

    text = "<b>📋 Download Queue</b>\n\n"
    if current:
        text += f"• 🔄 <b>Active:</b> <code>{current.get('name', 'Unknown')}</code>\n"
        text += f"• 📦 <b>Links:</b> <code>{len(current.get('links', []))}</code>\n\n"
    else:
        text += "<b>🔄 Active:</b> <code>None</code>\n\n"

    if items:
        for item in items:
            text += f"{item}\n"
        text += f"\n<b>📊 Total Queued:</b> <code>{Queue.size()}</code>"
    else:
        text += "<b>📭 Queue is empty</b>"

    stats_text = "\n\n<b>─── Session Stats ───</b>\n"
    stats_text += f"• Completed: <code>{BotStats.total_tasks}</code>\n"
    stats_text += f"• Failed: <code>{BotStats.failed_tasks}</code>\n"
    stats_text += f"• Downloaded: <code>{BotStats.total_downloaded}</code>\n"
    stats_text += f"• Uploaded: <code>{BotStats.total_uploaded}</code>"

    msg = await message.reply_text(text + stats_text)
    await message_deleter(message, msg)


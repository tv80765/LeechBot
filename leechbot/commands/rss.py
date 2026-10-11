# =============================================================================
# Telegram Leech Bot - RSS Feed Commands
# =============================================================================
# Project   : LeechBot
# Developer : Shinei Nouzen
# GitHub    : https://github.com/Shineii86
# Telegram  : https://telegram.me/Shineii86
# =============================================================================
# License   : MIT License
# =============================================================================

"""
Owner-only commands for managing RSS auto-download feeds.
"""

import logging

from pyrogram import filters, types

from leechbot import app, OWNER
from leechbot.utility.helper import message_deleter
from leechbot.utility.rss_manager import add_feed, remove_feed, list_feeds, check_feeds_once

logger = logging.getLogger(__name__)


@app.on_message(filters.command("rss_add") & filters.private)
async def rss_add_command(client, message):
    """Add an RSS feed: /rss_add <url> <command> [interval_minutes]"""
    if message.chat.id != OWNER:
        return

    parts = message.command
    if len(parts) < 3:
        msg = await message.reply_text(
            "<b>⚠️ Usage:</b> <code>/rss_add &lt;rss_url&gt; &lt;command&gt; [interval_min]</code>\n\n"
            "<b>Example:</b> <code>/rss_add https://rsshub.app/youtube/user/USERNAME ytupload</code>\n"
            "<b>Commands:</b> tupload, gdupload, ytupload, glupload, drupload (or aliases like yt, dl)\n"
            "<b>Interval:</b> optional, default 15 minutes",
        )
        await message_deleter(message, msg)
        return

    url = parts[1]
    command = parts[2]
    interval = int(parts[3]) if len(parts) >= 4 else 15

    try:
        feed_id = add_feed(url, command, interval)
        msg = await message.reply_text(
            f"<b>✅ RSS feed added</b>\n\n"
            f"<b>ID:</b> <code>{feed_id}</code>\n"
            f"<b>URL:</b> <code>{url[:200]}</code>\n"
            f"<b>Command:</b> <code>/{command}</code>\n"
            f"<b>Interval:</b> <code>{interval} min</code>",
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
        )
    except Exception as e:
        logger.error("rss_add failed: %s", e)
        msg = await message.reply_text(f"<b>❌ Failed to add feed:</b> <code>{e}</code>")

    await message_deleter(message, msg)


@app.on_message(filters.command("rss_list") & filters.private)
async def rss_list_command(client, message):
    """List all RSS feeds."""
    if message.chat.id != OWNER:
        return

    feeds = list_feeds()
    if not feeds:
        msg = await message.reply_text("<b>ℹ️ No RSS feeds configured.</b>")
        await message_deleter(message, msg)
        return

    lines = []
    for f in feeds:
        status = "✅" if f.get("enabled", True) else "⏹"
        lines.append(
            f"{status} <b>ID {f['id']}</b> — <code>/{f['command']}</code> — {f['interval']}min\n"
            f"<code>{f['url'][:80]}</code>"
        )

    msg = await message.reply_text(
        f"<b>📰 RSS Feeds</b>\n\n" + "\n\n".join(lines),
        link_preview_options=types.LinkPreviewOptions(is_disabled=True),
    )
    await message_deleter(message, msg)


@app.on_message(filters.command("rss_remove") & filters.private)
async def rss_remove_command(client, message):
    """Remove an RSS feed by id: /rss_remove <id>"""
    if message.chat.id != OWNER:
        return

    parts = message.command
    if len(parts) < 2:
        msg = await message.reply_text(
            "<b>⚠️ Usage:</b> <code>/rss_remove &lt;feed_id&gt;</code>"
        )
        await message_deleter(message, msg)
        return

    try:
        feed_id = int(parts[1])
    except ValueError:
        msg = await message.reply_text("<b>⚠️ Feed ID must be a number.</b>")
        await message_deleter(message, msg)
        return

    if remove_feed(feed_id):
        msg = await message.reply_text(f"<b>✅ RSS feed {feed_id} removed.</b>")
    else:
        msg = await message.reply_text(f"<b>ℹ️ Feed ID {feed_id} not found.</b>")

    await message_deleter(message, msg)


@app.on_message(filters.command("rss_check") & filters.private)
async def rss_check_command(client, message):
    """Manually trigger an RSS check."""
    if message.chat.id != OWNER:
        return

    msg = await message.reply_text("<b>🔍 Checking RSS feeds...</b>")
    try:
        await check_feeds_once()
        await msg.edit_text("<b>✅ RSS check complete.</b>")
    except Exception as e:
        logger.error("rss_check failed: %s", e)
        await msg.edit_text(f"<b>❌ RSS check failed:</b> <code>{e}</code>")

    await message_deleter(message, msg)

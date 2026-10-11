# =============================================================================
# Telegram Leech Bot - Helper Utilities
# =============================================================================
# Project   : LeechBot
# Developer : Shinei Nouzen
# GitHub    : https://github.com/Shineii86
# Telegram  : https://telegram.me/Shineii86
# =============================================================================
# License   : MIT License
# =============================================================================

"""
Helper functions for file operations, formatting, UI updates, and link handling.
"""

import os
import re
import psutil
import logging
from time import time
from os import path as ospath
from datetime import datetime
from urllib.parse import urlparse
from asyncio import get_running_loop, sleep

from leechbot import app
from pyrogram import types
from pyrogram.errors import BadRequest
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto

from leechbot.utility.variables import BOT, MSG, BotTimes, Paths

logger = logging.getLogger(__name__)

# =============================================================================
# Link Detection Patterns
# =============================================================================
LINK_PATTERNS = [
    re.compile(r'https?://[^\s<>\"\']+', re.IGNORECASE),
    re.compile(r'magnet:\?xt=urn:btih:[^\s<>\"\']+', re.IGNORECASE),
]

PIXELDRAIN_PATTERN = re.compile(r'https?://pixeldrain\.com/[^\s]+', re.IGNORECASE)
MEDIAFIRE_PATTERN = re.compile(r'https?://(?:www\.)?mediafire\.com/[^\s]+', re.IGNORECASE)
STREAMTAPE_PATTERN = re.compile(r'https?://(?:www\.)?(?:streamtape|stape)\.[^\s]+', re.IGNORECASE)
M3U8_PATTERN = re.compile(r'https?://[^\s<>\"\']+\.m3u8[^\s<>\"\']*', re.IGNORECASE)
MPD_PATTERN = re.compile(r'https?://[^\s<>\"\']+\.mpd[^\s<>\"\']*', re.IGNORECASE)

# =============================================================================
# Link Validation
# =============================================================================
def isLink(_, client, update):
    """
    Validate if the message contains a valid download link.

    Supports: HTTP/HTTPS URLs, magnet links, local paths.
    """
    if not update.text:
        return False

    text = update.text.strip()

    # Local paths
    if text.startswith("/") and ospath.exists(text.split("\n")[0].strip()):
        return True

    # Magnet links
    if text.startswith("magnet:?xt=urn:btih:"):
        return True

    # HTTP/HTTPS URLs — check first line
    first_line = text.split("\n")[0].strip()
    parsed = urlparse(first_line)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return True

    return False

# =============================================================================
# Link Type Detection
# =============================================================================
def is_google_drive(link: str) -> bool:
    return "drive.google.com" in link

def is_mega(link: str) -> bool:
    return "mega.nz" in link or "mega.co.nz" in link

def is_terabox(link: str) -> bool:
    return "terabox" in link or "1024tera" in link or "teraboxapp" in link

def is_ytdl_link(link: str) -> bool:
    """Check if link is supported by yt-dlp (YouTube, social media, etc.)."""
    lower = link.lower()
    ytdl_domains = [
        # Video platforms
        "youtube.com", "youtu.be", "youtube-nocookie.com",
        "facebook.com", "fb.watch", "fb.com",
        "twitter.com", "x.com",
        "tiktok.com", "vimeo.com", "dailymotion.com",
        "twitch.tv", "kick.com", "rumble.com",
        "reddit.com", "redd.it", "v.redd.it",
        "streamable.com", "gfycat.com", "imgur.com",
        # Music
        "soundcloud.com", "spotify.com", "bandcamp.com",
        "music.youtube.com", "audiomack.com",
        # News / media
        "bilibili.com", "b23.tv", "nicovideo.jp",
        "niconico.com", "odysee.com", "lbry.tv",
        "peertube", "rutube.ru", "vk.com", "vk.ru",
        # Adult (commonly requested)
        "pornhub.com", "xvideos.com", "xnxx.com",
        "xhamster.com", "redtube.com", "youporn.com",
        "spankbang.com", "eporner.com",
        # Other platforms
        "archive.org", "slideshare.net", "mixcloud.com",
        "coub.com", "9gag.com", "ifunny.co",
        "izlesene.com", "southpark.cc.com", "medaltv",
        "tv.youtube.com", "tubitv.com", "crunchyroll.com",
        "funimation.com", "crackle.com",
        # Chinese platforms
        "bilibili.com", "youku.com", "iqiyi.com",
        "acfun.cn", "douyin.com", "kuaishou.com",
    ]
    return any(domain in lower for domain in ytdl_domains)

def is_torrent(link: str) -> bool:
    return "magnet:" in link or ".torrent" in link

def is_pixeldrain(link: str) -> bool:
    return "pixeldrain.com" in link

def is_mediafire(link: str) -> bool:
    return "mediafire.com" in link

def is_streamtape(link: str) -> bool:
    return "streamtape" in link or "stape." in link

def is_hls_stream(link: str) -> bool:
    """Check if link is an HLS/DASH stream (.m3u8 or .mpd)."""
    lower = link.lower()
    return ".m3u8" in lower or ".mpd" in lower

def is_gofile(link: str) -> bool:
    return "gofile.io" in link.lower()

def is_catbox(link: str) -> bool:
    lower = link.lower()
    return "catbox.moe" in lower or "litterbox.moe" in lower

def is_direct_link(link: str) -> bool:
    """Check if link looks like a direct file download (has file extension)."""
    lower = link.lower().split("?")[0].split("#")[0]
    direct_exts = [
        ".mp4", ".mkv", ".avi", ".webm", ".mov", ".flv", ".wmv",
        ".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a",
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
        ".iso", ".img", ".dmg",
        ".pdf", ".epub", ".mobi",
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
        ".exe", ".apk", ".deb", ".rpm", ".msi",
        ".torrent",
    ]
    return any(lower.endswith(ext) for ext in direct_exts)

def is_gallery(link: str) -> bool:
    """Check if link is a photo gallery site (Twitter, Pinterest, etc.)."""
    from leechbot.downloader.gallery import is_gallery_link
    return is_gallery_link(link)

def detect_link_type(link: str) -> str:
    """Return a human-readable label for the link type."""
    if is_google_drive(link):
        return "♻️ Google Drive"
    elif is_torrent(link):
        return "🧲 Torrent"
    elif is_terabox(link):
        return "🍑 Terabox"
    elif is_gallery(link):
        return "📸 Gallery"
    elif is_hls_stream(link):
        return "📡 HLS/DASH Stream"
    elif is_gofile(link):
        return "📁 GoFile"
    elif is_catbox(link):
        return "📦 Catbox"
    elif is_streamtape(link):
        return "🎬 StreamTape"
    elif is_ytdl_link(link):
        return "🏮 YT-DLP"
    elif is_mega(link):
        return "💾 Mega"
    elif is_pixeldrain(link):
        return "📁 Pixeldrain"
    elif is_mediafire(link):
        return "📂 Mediafire"
    elif is_direct_link(link):
        return "🔗 Direct Link"
    else:
        return "🌐 Web Link"

# =============================================================================
# Link Extraction from Text
# =============================================================================
def extract_links(text: str) -> list:
    """
    Extract all URLs and magnet links from arbitrary text.

    Useful for forwarded messages that contain multiple links.
    Returns a deduplicated list preserving order.
    """
    links = []
    seen = set()

    for pattern in LINK_PATTERNS:
        for match in pattern.finditer(text):
            url = match.group(0).strip().rstrip(")")
            if url not in seen:
                seen.add(url)
                links.append(url)

    return links

# =============================================================================
# Time Formatting
# =============================================================================
def getTime(seconds: float) -> str:
    """Convert seconds to human-readable duration string."""
    seconds = max(0, int(seconds))
    days = seconds // 86400
    seconds %= 86400
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60

    if days > 0:
        return f"{days}d {hours}h {minutes}m {seconds}s"
    elif hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

# =============================================================================
# Size Formatting
# =============================================================================
def sizeUnit(size: float) -> str:
    """Convert bytes to human-readable size string."""
    if size <= 0:
        return "0 B"
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    i = 0
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.2f} {units[i]}"

# =============================================================================
# File Type Detection
# =============================================================================
def fileType(file_path: str) -> str:
    """Detect file type based on extension. Returns: video, audio, photo, document."""
    extensions_dict = {
        # Video
        ".mp4": "video", ".avi": "video", ".mkv": "video",
        ".m2ts": "video", ".mov": "video", ".ts": "video",
        ".m3u8": "video", ".webm": "video", ".mpg": "video",
        ".mpeg": "video", ".mpeg4": "video", ".vob": "video",
        ".m4v": "video", ".flv": "video", ".wmv": "video",
        # Audio
        ".mp3": "audio", ".wav": "audio", ".flac": "audio",
        ".aac": "audio", ".ogg": "audio", ".m4a": "audio",
        ".wma": "audio", ".opus": "audio",
        # Image
        ".jpg": "photo", ".jpeg": "photo", ".png": "photo",
        ".bmp": "photo", ".gif": "photo", ".webp": "photo",
        ".tiff": "photo",
    }
    _, ext = ospath.splitext(file_path)
    return extensions_dict.get(ext.lower(), "document")

# =============================================================================
# Filename Handling
# =============================================================================
def shortFileName(path: str, max_len: int = 60) -> str:
    """Truncate filename to fit Telegram limits while preserving extension."""
    if ospath.isfile(path):
        dir_path, filename = ospath.split(path)
        if len(filename) > max_len:
            basename, ext = ospath.splitext(filename)
            basename = basename[:max_len - len(ext)]
            return ospath.join(dir_path, basename + ext)
        return path
    elif ospath.isdir(path):
        dir_path, dirname = ospath.split(path)
        if len(dirname) > max_len:
            return ospath.join(dir_path, dirname[:max_len])
        return path
    return path[:max_len] if len(path) > max_len else path

# =============================================================================
# Get Total Size of Path
# =============================================================================
def getSize(path: str) -> int:
    """Get total size of file or directory in bytes."""
    if ospath.isfile(path):
        return ospath.getsize(path)
    total_size = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            total_size += ospath.getsize(ospath.join(dirpath, f))
    return total_size

# =============================================================================
# Video Extension Fix
# =============================================================================
def videoExtFix(file_path: str) -> str:
    """Ensure video has .mp4 or .mkv extension for Telegram compatibility."""
    _, f_name = ospath.split(file_path)
    if f_name.endswith(".mp4") or f_name.endswith(".mkv"):
        return file_path
    new_path = file_path + ".mp4"
    try:
        os.rename(file_path, new_path)
    except OSError:
        return file_path
    return new_path

# =============================================================================
# Thumbnail Generation
# =============================================================================
def thumbMaintainer(file_path: str, original_name: str = None):
    """
    Generate or retrieve thumbnail for a video file.

    Args:
        file_path: actual file path on disk (may be renamed/shortened by
            shortFileName). Used for ffprobe/ffmpeg operations.
        original_name: original filename before renaming (the title yt-dlp
            used when saving the thumbnail). When provided, the thumbnail
            lookup uses this name. If None, falls back to file_path basename.

    Returns:
        tuple: (thumbnail_path, duration_seconds)
    """
    import subprocess

    if ospath.exists(Paths.VIDEO_FRAME):
        os.remove(Paths.VIDEO_FRAME)

    try:
        lookup_name = original_name if original_name else ospath.basename(file_path)
        fname, _ = ospath.splitext(lookup_name)
        # Check for thumbnail in multiple formats (yt-dlp saves as webp/jpg/png)
        ytdl_thmb = None
        for ext in (".webp", ".jpg", ".png", ".jpeg"):
            candidate = ospath.join(Paths.thumbnail_ytdl, f"{fname}{ext}")
            if ospath.exists(candidate):
                ytdl_thmb = candidate
                break

        # Get duration via ffprobe
        duration = 0
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", file_path],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                duration = float(result.stdout.strip())
        except Exception:
            pass

        if ospath.exists(Paths.THMB_PATH):
            return Paths.THMB_PATH, duration
        elif ytdl_thmb and ospath.exists(ytdl_thmb):
            return convertIMG(ytdl_thmb), duration
        else:
            # Extract frame at midpoint via ffmpeg
            mid = max(int(duration / 2), 1)
            subprocess.run(
                ["ffmpeg", "-y", "-ss", str(mid), "-i", file_path,
                 "-vframes", "1", "-q:v", "2", Paths.VIDEO_FRAME],
                capture_output=True, timeout=15,
            )
            if ospath.exists(Paths.VIDEO_FRAME):
                return Paths.VIDEO_FRAME, duration
            return Paths.HERO_IMAGE, duration
    except Exception as e:
        logger.error(f"Thumbnail generation error: {e}")
        if ospath.exists(Paths.THMB_PATH):
            return Paths.THMB_PATH, 0
        return Paths.HERO_IMAGE, 0

# =============================================================================
# Set Thumbnail from User Photo
# =============================================================================
async def setThumbnail(message) -> bool:
    """Save user-sent image as the custom thumbnail."""
    try:
        if ospath.exists(Paths.THMB_PATH):
            os.remove(Paths.THMB_PATH)

        event_loop = get_running_loop()
        await event_loop.create_task(
            message.download(file_name=Paths.THMB_PATH)
        )

        BOT.Setting.thumbnail = True

        if BOT.State.task_going and MSG.status_msg:
            await MSG.status_msg.edit_media(
                InputMediaPhoto(Paths.THMB_PATH),
                reply_markup=keyboard()
            )
        return True
    except Exception as e:
        BOT.Setting.thumbnail = False
        logger.error(f"Thumbnail download error: {e}")
        return False

# =============================================================================
# YT-DLP Completion Check
# =============================================================================
def isYtdlComplete() -> bool:
    """Check if all YT-DLP .part/.ytdl files are gone."""
    for _, _, filenames in os.walk(Paths.down_path):
        for f in filenames:
            _, ext = ospath.splitext(f)
            if ext in (".part", ".ytdl"):
                return False
    return True

# =============================================================================
# Image Conversion
# =============================================================================
def convertIMG(image_path: str) -> str:
    """Convert image to JPEG format."""
    try:
        from PIL import Image
        image = Image.open(image_path)
        if image.mode != "RGB":
            image = image.convert("RGB")
        output_path = ospath.splitext(image_path)[0] + ".jpg"
        image.save(output_path, "JPEG")
        os.remove(image_path)
        return output_path
    except Exception as e:
        logger.error(f"Image conversion error: {e}")
        return image_path

# =============================================================================
# System Information Stripper
# =============================================================================
def _strip_sysinfo(text: str) -> str:
    """Strip existing system info block from message text."""
    for separator in ("<b>─── System ───</b>", "<b>📊 System Info (Detailed)</b>"):
        idx = text.find(separator)
        if idx != -1:
            return text[:idx].rstrip()
    return text

# System Information (Basic)
# =============================================================================
def sysINFO() -> str:
    """Get compact system resource usage string."""
    try:
        ram_usage = psutil.Process(os.getpid()).memory_info().rss
        disk_usage = psutil.disk_usage("/")
        cpu_usage = psutil.cpu_percent(interval=0.1)

        return f"""

<b>─── System ───</b>
• 🖥️ <code>{cpu_usage}%</code> · 💾 <code>{sizeUnit(ram_usage)} RAM</code> · 💽 <code>{sizeUnit(disk_usage.free)} free</code>"""
    except Exception:
        return ""

# =============================================================================
# System Information (Detailed)
# =============================================================================
def sysINFO_full() -> str:
    """Get detailed system information including network and per-core CPU."""
    try:
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        cpu_percent = psutil.cpu_percent(interval=0.5, percpu=True)
        net = psutil.net_io_counters()

        core_str = ", ".join(f"{c}%" for c in cpu_percent[:8])
        if len(cpu_percent) > 8:
            core_str += ", ..."

        return f"""

<b>📊 System Info (Detailed)</b>
• 🖥️ <b>CPU:</b> <code>{psutil.cpu_percent()}%</code> (cores: {core_str})
• 💽 <b>RAM:</b> <code>{sizeUnit(ram.used)} / {sizeUnit(ram.total)}</code> ({ram.percent}%)
• 💾 <b>Disk:</b> <code>{sizeUnit(disk.used)} / {sizeUnit(disk.total)}</code> ({disk.percent}%)
• 🌐 <b>Net:</b> ↓<code>{sizeUnit(net.bytes_recv)}</code> ↑<code>{sizeUnit(net.bytes_sent)}</code>
• ⏱️ <b>Uptime:</b> <code>{getTime(int(time() - psutil.boot_time()))}</code>"""
    except Exception:
        return sysINFO()

# =============================================================================
# Download/Upload Statistics Summary
# =============================================================================
def format_stats() -> str:
    """Generate a text-based statistics summary."""
    from leechbot.utility.variables import BotStats

    uptime = getTime(int((datetime.now() - BotStats.start_time).total_seconds()))

    return f"""<b>📊 Bot Statistics</b>

• 📥 <b>Total Downloads:</b> <code>{BotStats.total_tasks}</code>
• 📤 <b>Data Downloaded:</b> <code>{sizeUnit(BotStats.total_downloaded)}</code>
• 📥 <b>Data Uploaded:</b> <code>{sizeUnit(BotStats.total_uploaded)}</code>
• ❌ <b>Failed Tasks:</b> <code>{BotStats.failed_tasks}</code>
• ⏱️ <b>Uptime:</b> <code>{uptime}</code>"""

# =============================================================================
# Multipart Archive Handling
# =============================================================================
def multipartArchive(path: str, archive_type: str, remove: bool):
    """Handle multipart archive files. Returns (real_name, total_size)."""
    dirname, filename = ospath.split(path)
    name, _ = ospath.splitext(filename)
    count, size, real_name = 1, 0, name

    if archive_type == "rar":
        name_, _ = ospath.splitext(name)
        real_name = name_
        part_name = f"{name_}.part{count}.rar"
        part_path = ospath.join(dirname, part_name)
        while ospath.exists(part_path):
            if remove:
                os.remove(part_path)
            size += getSize(part_path)
            count += 1
            part_name = f"{name_}.part{count}.rar"
            part_path = ospath.join(dirname, part_name)

    elif archive_type == "7z":
        part_name = f"{name}.{str(count).zfill(3)}"
        part_path = ospath.join(dirname, part_name)
        while ospath.exists(part_path):
            if remove:
                os.remove(part_path)
            size += getSize(part_path)
            count += 1
            part_name = f"{name}.{str(count).zfill(3)}"
            part_path = ospath.join(dirname, part_name)

    elif archive_type == "zip":
        zip_path = ospath.join(dirname, f"{name}.zip")
        if ospath.exists(zip_path):
            if remove:
                os.remove(zip_path)
            size += getSize(zip_path)
        part_name = f"{name}.z{str(count).zfill(2)}"
        part_path = ospath.join(dirname, part_name)
        while ospath.exists(part_path):
            if remove:
                os.remove(part_path)
            size += getSize(part_path)
            count += 1
            part_name = f"{name}.z{str(count).zfill(2)}"
            part_path = ospath.join(dirname, part_name)
        if real_name.endswith(".zip"):
            real_name, _ = ospath.splitext(real_name)

    return real_name, size

# =============================================================================
# Time Check for UI Updates (throttle to every 3 seconds)
# =============================================================================
def isTimeOver() -> bool:
    """Return True if ≥3 seconds have elapsed since last call (rate-limits UI updates)."""
    elapsed = time() - BotTimes.current_time
    if elapsed >= 3:
        BotTimes.current_time = time()
        return True
    return False

# =============================================================================
# Custom Name Application
# =============================================================================
def applyCustomName():
    """Rename downloaded files to the user-specified custom name."""
    if BOT.Options.custom_name and BOT.Mode.type not in ("zip", "undzip"):
        files = os.listdir(Paths.down_path)
        for file_ in files:
            current = ospath.join(Paths.down_path, file_)
            new = ospath.join(Paths.down_path, BOT.Options.custom_name)
            try:
                os.rename(current, new)
            except OSError as e:
                logger.error(f"Rename error: {e}")

# =============================================================================
# Speed and ETA Calculation
# =============================================================================
def speedETA(start_time: datetime, done: int, total: int):
    """Calculate speed, ETA, and percentage from start time and byte counts."""
    percentage = min((done / total) * 100, 100) if total > 0 else 0
    elapsed = max((datetime.now() - start_time).total_seconds(), 0.01)

    if done > 0 and elapsed > 0:
        raw_speed = done / elapsed
        speed = f"{sizeUnit(raw_speed)}/s"
        eta = (total - done) / raw_speed if raw_speed > 0 else 0
    else:
        speed, eta = "N/A", 0

    return speed, eta, percentage

# =============================================================================
# Auto-Delete Aware Message Deleter
# =============================================================================
async def message_deleter(user_msg, bot_msg):
    """Delete messages after auto-delete delay if enabled."""
    if BOT.Setting.auto_delete:
        delay = BOT.Setting.auto_delete_delay
        await sleep(delay)
        try:
            await user_msg.delete()
            await bot_msg.delete()
        except Exception as e:
            logger.debug(f"Auto-delete error (benign): {e}")

# =============================================================================
# Settings Menu
# =============================================================================
async def send_settings(client, message, msg_id: int, is_command: bool):
    """Send or edit the interactive settings menu."""
    up_mode = "Media" if BOT.Options.stream_upload else "Document"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"📤 {up_mode}", callback_data="media" if up_mode == "Document" else "document"),
            InlineKeyboardButton("🎬 Video", callback_data="video"),
        ],
        [
            InlineKeyboardButton("📝 Caption", callback_data="caption"),
            InlineKeyboardButton("🖼️ Thumb", callback_data="thumb"),
        ],
        [
            InlineKeyboardButton("➕ Prefix", callback_data="set-prefix"),
            InlineKeyboardButton("➕ Suffix", callback_data="set-suffix"),
        ],
        [
            InlineKeyboardButton(
                f"📸 Photos: {BOT.Setting.photo_mode}",
                callback_data="photo_mode"
            ),
        ],
        [
            InlineKeyboardButton(
                f"⏳ Auto-Delete: {'ON' if BOT.Setting.auto_delete else 'OFF'}",
                callback_data="autodelete",
            ),
        ],
        [
            InlineKeyboardButton(
                f"📸 Auto-SS: {'ON' if BOT.Setting.auto_screenshot else 'OFF'}",
                callback_data="screenshot",
            ),
        ],
        [
            InlineKeyboardButton("❰ Back", callback_data="start_back"),
            InlineKeyboardButton("🔒 Close", callback_data="close"),
        ],
    ])

    pr = "✅" if BOT.Setting.prefix else "❎"
    su = "✅" if BOT.Setting.suffix else "❎"
    thmb = "✅" if BOT.Setting.thumbnail else "❎"
    auto_del = f"{BOT.Setting.auto_delete_delay}s" if BOT.Setting.auto_delete else "Off"

    text = f"""<b>⚙️ Bot Settings</b>

• 📤 <b>Upload:</b> <code>{BOT.Setting.stream_upload}</code>
• ✂️ <b>Split:</b> <code>{BOT.Setting.split_video}</code>
• 🔄 <b>Convert:</b> <code>{BOT.Setting.convert_video}</code>
• 📝 <b>Caption:</b> <code>{BOT.Setting.caption}</code>
• ➕ <b>Prefix:</b> {pr}
• ➕ <b>Suffix:</b> {su}
• 🖼️ <b>Thumb:</b> {thmb}
• 📸 <b>Photos:</b> <code>{BOT.Setting.photo_mode}</code>
• ⏳ <b>Auto-Delete:</b> <code>{auto_del}</code>
• 📸 <b>Auto-SS:</b> <code>{'ON' if BOT.Setting.auto_screenshot else 'OFF'}</code>"""

    try:
        if is_command:
            await message.reply_text(text=text, reply_markup=keyboard)
        else:
            await app.edit_message_text(
                chat_id=message.chat.id,
                message_id=msg_id,
                text=text,
                reply_markup=keyboard
            )
    except BadRequest as e:
        logger.error(f"Settings menu error: {e}")
    except Exception as e:
        logger.error(f"Settings menu error: {e}")

# =============================================================================
# Status Bar Update
# =============================================================================
async def status_bar(down_msg: str, speed: str, percentage: float, eta: str,
                     done: str, left: str, engine: str):
    """Update the live download/upload status bar message.

    Layout (3.1.42) — professional box-drawing:

        {down_msg}                          ← heading + file name (set by caller)

        ┌───────────────────────────────┐
          ████░░░░  **75.00%**
        ├───────────────────────────────┤
          ⚡  **Speed**      →  `5.2 MB/s`
          ⏳  **ETA**        →  `10s`
          📦  **Processed**  →  `156 / 208 MB`
          ⏱️  **Elapsed**    →  `30s`
          🔧  **Engine**     →  `yt-dlp`
        └───────────────────────────────┘

    System info (CPU / RAM / disk / network / uptime) is always
    appended below the progress bar.
    """
    bar_length = 12
    filled = int(percentage / 100 * bar_length)
    bar = "█" * filled + "░" * (bar_length - filled)

    elapsed = getTime((datetime.now() - BotTimes.start_time).total_seconds())

    text = (
        f"\n<b>━━━ Progress ━━━</b>\n"
        f"{bar}  <b>{percentage:.2f}%</b>\n\n"
        f"⚡ <b>Speed:</b> <code>{speed}</code>\n"
        f"⏳ <b>ETA:</b> <code>{eta}</code>\n"
        f"📦 <b>Processed:</b> <code>{done}</code> / <code>{left}</code>\n"
        f"⏱️ <b>Elapsed:</b> <code>{elapsed}</code>\n"
        f"🔧 <b>Engine:</b> <code>{engine}</code>"
    )

    # Append system info
    text += sysINFO_full()

    try:
        if isTimeOver():
            # Always strip from full prefix to prevent duplicate sysinfo blocks
            from leechbot.utility.variables import Messages
            full_prefix = _strip_sysinfo(Messages.task_msg + Messages.status_head)
            await MSG.status_msg.edit_text(
                text=full_prefix + text,
                link_preview_options=types.LinkPreviewOptions(is_disabled=True),
                reply_markup=status_keyboard()
            )
    except BadRequest:
        pass
    except Exception as e:
        logger.debug(f"Status bar update error: {e}")

# =============================================================================
# Keyboards
# =============================================================================
def keyboard():
    """Cancel-only keyboard for simple operations."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ])

def status_keyboard():
    """Status keyboard with Refresh and Cancel buttons.

    - **🔄 Refresh**: Appends compact system info (CPU / RAM / disk) below
      the progress bar. Useful for quick health checks.
    - **❌ Cancel**: Aborts the current task.
    """
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="sys_refresh"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]
    ])

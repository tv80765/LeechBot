# =============================================================================
# Telegram Leech Bot - Gallery-DL Downloader
# =============================================================================
# Project   : LeechBot
# Developer : Shinei Nouzen
# GitHub    : https://github.com/Shineii86
# Telegram  : https://telegram.me/Shineii86
# =============================================================================
# License   : MIT License
# =============================================================================

"""
gallery-dl downloader module.

Handles photo/image gallery downloads from Twitter, Pinterest,
Pixiv, DeviantArt, ArtStation, Flickr, Reddit, Tumblr, and 100+ other sites.
"""

import os
import glob
import logging
import asyncio
from datetime import datetime
from asyncio import sleep
from os import makedirs, path as ospath

from leechbot.utility.variables import Paths, Messages, MSG, BotTimes
from leechbot.utility.helper import keyboard, sysINFO, sizeUnit, getSize, getTime, status_bar

logger = logging.getLogger(__name__)


# =============================================================================
# Supported Sites (for detection)
# =============================================================================
GALLERY_SITES = [
    "twitter.com",
    "x.com",
    "pinterest.com",
    "pixiv.net",
    "deviantart.com",
    "artstation.com",
    "flickr.com",
    "tumblr.com",
    "reddit.com",
    "imgur.com",
    "danbooru.donmai.us",
    "gelbooru.com",
    "konachan.com",
    "yande.re",
    "safebooru.org",
    "zerochan.net",
    "baraag.net",
    "pawoo.net",
    "newgrounds.com",
    "webtoons.com",
    "tapas.io",
    "hentaihaven.xxx",
    "nhentai.net",
    "ehentai.org",
    "exhentai.org",
    "furaffinity.net",
    "weasyl.com",
    "inkbunny.net",
    "tiktok.com",
    "bsky.app",
]


def is_gallery_link(link: str) -> bool:
    """Check if a link is supported by gallery-dl."""
    from urllib.parse import urlparse

    host = (urlparse(link.strip()).hostname or "").lower().removeprefix("www.")
    if not host:
        return False
    for site in GALLERY_SITES:
        site = site.lower()
        if host == site or host.endswith(f".{site}"):
            return True
    return False


# =============================================================================
# Gallery-DL Download Function
# =============================================================================
async def gallery_download(url: str, num: int):
    """
    Download images/media from a gallery URL using gallery-dl.

    Parses real-time stderr output to show a live progress bar with
    speed, ETA, file count, and total size — matching the aria2/yt-dlp
    status bar experience.

    Args:
        url: gallery URL
        num: link number for display
    """
    # Create output directory
    gallery_dir = ospath.join(Paths.down_path, f"gallery_{str(num).zfill(2)}")
    if not ospath.exists(gallery_dir):
        makedirs(gallery_dir)

    Messages.status_head = (
        f"<b>📸 Downloading Gallery</b> <code>Link {str(num).zfill(2)}</code>\n\n"
        f"<code>{url[:80]}</code>\n"
    )

    BotTimes.task_start = datetime.now()

    try:
        await MSG.status_msg.edit_text(
            text=Messages.task_msg + Messages.status_head + "\n⏳ Starting..." + sysINFO(),
            reply_markup=keyboard()
        )
    except Exception:
        pass

    # Build gallery-dl command (no -q: we need stderr output for progress tracking)
    cmd = [
        "gallery-dl",
        "--directory", gallery_dir,
        "--no-skip",          # Don't skip existing files
        "--no-mtime",         # Don't set file modification time
        url
    ]

    try:
        # Run gallery-dl as subprocess
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Track progress by reading stderr in real-time
        file_count = 0
        total_downloaded = 0
        last_update = datetime.now()
        stderr_lines = []

        async def _read_stderr():
            """Read stderr lines in real-time for progress tracking."""
            nonlocal file_count, total_downloaded, last_update, stderr_lines
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").strip()
                if not decoded:
                    continue
                stderr_lines.append(decoded)
                logger.debug(f"gallery-dl: {decoded}")

        # Start stderr reader task
        stderr_task = asyncio.create_task(_read_stderr())

        # Progress monitoring loop
        while process.returncode is None:
            await sleep(2)

            # Count downloaded files and calculate size
            current_files = _get_files(gallery_dir)
            current_count = len(current_files)
            current_size = getSize(gallery_dir)

            if current_count > file_count or current_size > total_downloaded:
                file_count = current_count
                total_downloaded = current_size

                # Calculate speed and ETA
                elapsed = max(
                    (datetime.now() - BotTimes.task_start).total_seconds(), 0.01
                )
                speed = total_downloaded / elapsed if total_downloaded > 0 else 0

                # Get last downloaded filename for display
                last_file = ospath.basename(current_files[-1]) if current_files else "..."
                if len(last_file) > 35:
                    last_file = last_file[:32] + "..."

                try:
                    await status_bar(
                        down_msg=Messages.status_head,
                        speed=f"{sizeUnit(speed)}/s",
                        percentage=0,  # Unknown total — indeterminate
                        eta="—",
                        done=f"{file_count} files ({sizeUnit(total_downloaded)})",
                        left=f"📥 {last_file}",
                        engine="gallery-dl 📸",
                    )
                except Exception:
                    pass

        # Wait for stderr reader to finish
        await stderr_task

        # Wait for process to fully complete
        await process.wait()

        if process.returncode != 0:
            error_msg = "\n".join(stderr_lines[-5:]) if stderr_lines else "Unknown error"
            error_msg = error_msg[:300]
            logger.error(f"gallery-dl error: {error_msg}")
            raise Exception(f"gallery-dl failed (code {process.returncode}): {error_msg}")

        # Final count
        files = _get_files(gallery_dir)
        total_size = sizeUnit(getSize(gallery_dir))
        elapsed = getTime(int((datetime.now() - BotTimes.task_start).total_seconds()))

        try:
            await MSG.status_msg.edit_text(
                text=Messages.task_msg + Messages.status_head +
                f"\n✅ <b>Complete:</b> <code>{len(files)} files</code> ({total_size})\n"
                f"⏱️ <b>Time:</b> <code>{elapsed}</code>" + sysINFO(),
                reply_markup=keyboard()
            )
        except Exception:
            pass

        logger.info(f"gallery-dl downloaded {len(files)} files to {gallery_dir}")

    except FileNotFoundError:
        logger.error("gallery-dl not installed. Run: pip install gallery-dl")
        raise Exception("gallery-dl not installed")
    except Exception as e:
        logger.error(f"gallery-dl error: {e}")
        raise


# =============================================================================
# Get Downloaded Files
# =============================================================================
def _get_files(directory: str) -> list:
    """Get all downloaded files from gallery directory."""
    extensions = ('*.jpg', '*.jpeg', '*.png', '*.gif', '*.webp', '*.bmp',
                  '*.tiff', '*.mp4', '*.webm', '*.mkv', '*.mov', '*.avi')
    files = []
    for ext in extensions:
        files.extend(glob.glob(os.path.join(directory, '**', ext), recursive=True))
    return sorted(files)


# =============================================================================
# Get Gallery Name (for display)
# =============================================================================
async def get_gallery_name(url: str) -> str:
    """Get a human-readable name for a gallery URL."""
    # Extract username/post from URL
    parts = url.rstrip('/').split('/')
    if 'twitter.com' in url or 'x.com' in url:
        return f"Twitter: @{parts[-1] if parts[-1] else parts[-2]}"
    elif 'pinterest.com' in url:
        return f"Pinterest: {parts[-1] if parts[-1] else parts[-2]}"
    elif 'reddit.com' in url:
        return f"Reddit: r/{parts[-1] if parts[-1] else parts[-2]}"
    elif 'pixiv.net' in url:
        return f"Pixiv: {parts[-1] if parts[-1] else parts[-2]}"
    else:
        return f"Gallery: {parts[-1][:30] if parts[-1] else parts[-2][:30]}"


# =============================================================================
# List Available Content (dry run)
# =============================================================================
async def list_gallery_content(url: str) -> str:
    """List what would be downloaded from a gallery URL."""
    cmd = ["gallery-dl", "-K", url]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            output = stdout.decode().strip()
            # Truncate for Telegram
            if len(output) > 3000:
                output = output[:3000] + "\n... (truncated)"
            return f"<code>\n{output}\n</code>"
        else:
            return f"<b>❌ Error:</b> <code>{stderr.decode().strip()[:200]}</code>"

    except Exception as e:
        return f"<b>❌ Error:</b> <code>{e}</code>"

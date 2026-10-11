# =============================================================================
# Telegram Leech Bot - Download Manager
# =============================================================================
# Project   : LeechBot
# Developer : Shinei Nouzen
# GitHub    : https://github.com/Shineii86
# Telegram  : https://telegram.me/Shineii86
# =============================================================================
# License   : MIT License
# =============================================================================

"""
Download manager module.

Orchestrates downloads from various sources, routes links to the correct
downloader, handles retries, and manages the overall process.
"""

import logging
from datetime import datetime
from asyncio import sleep

from leechbot.utility.variables import (
    BOT, Transfer, MSG, Messages, BotTimes, BotStats,
)
from leechbot.utility.helper import (
    is_google_drive, is_ytdl_link, is_mega,
    is_terabox, is_pixeldrain, is_mediafire, is_gallery,
    is_hls_stream, is_gofile, is_catbox, is_streamtape,
    is_torrent, isYtdlComplete, keyboard, sysINFO, detect_link_type,
)
import config

logger = logging.getLogger(__name__)


# =============================================================================
# Retry Wrapper
# =============================================================================
async def _with_retry(coro_factory, link: str, max_retries: int = None):
    """
    Retry an async download function up to N times on failure.

    Args:
        coro_factory: callable that returns a coroutine
        link: the URL being downloaded (for logging)
        max_retries: override from config.AUTO_RETRY_COUNT if None
    """
    if max_retries is None:
        max_retries = config.AUTO_RETRY_COUNT

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            await coro_factory()
            return  # Success
        except Exception as e:
            last_error = e
            logger.warning(f"Download attempt {attempt}/{max_retries} failed for {link}: {e}")
            if attempt < max_retries:
                logger.info(f"Retrying in 3 seconds...")
                await sleep(3)

    logger.error(f"All {max_retries} attempts failed for {link}: {last_error}")
    raise last_error


# =============================================================================
# Main Download Manager
# =============================================================================
async def downloadManager(sources: list, is_ytdl: bool):
    """
    Manage downloads from multiple sources with retry support.

    Args:
        sources: list of URLs to download
        is_ytdl: whether to use YT-DLP for all sources
    """
    from leechbot.utility.handler import cancelTask
    from leechbot.downloader.aria2 import aria2_Download, Aria2c
    from leechbot.downloader.ytdl import YTDL_Status
    from leechbot.downloader.gdrive import build_service, g_DownLoad, getIDFromURL, getFileMetadata, get_Gfolder_size
    from leechbot.downloader.mega import megadl
    from leechbot.downloader.gallery import gallery_download

    merge_msg = "\n<b>⏳ Please Wait...</b>\n<code>Merging YT-DLP Video...</code>"
    BotTimes.task_start = datetime.now()

    if is_ytdl:
        # YT-DLP mode — most links go through yt-dlp (Terabox uses its own module)
        for i, link in enumerate(sources):
            try:
                if is_terabox(link):
                    from leechbot.downloader.terabox import terabox_download
                    await _with_retry(lambda l=link, n=i+1: terabox_download(l, n), link)
                    continue
                await _with_retry(
                    lambda l=link, n=i+1: YTDL_Status(l, n),
                    link
                )
            except Exception as error:
                await cancelTask(f"YT-DLP Error: {error}")
                BotStats.failed_tasks += 1
                return

        try:
            await MSG.status_msg.edit_text(
                text=Messages.task_msg + Messages.status_head + merge_msg + sysINFO(),
                reply_markup=keyboard()
            )
        except Exception:
            pass

        while not isYtdlComplete():
            await sleep(2)
    else:
        # General download mode — route each link
        for i, link in enumerate(sources):
            link_type = detect_link_type(link)
            logger.info(f"Downloading link {i+1}/{len(sources)}: {link_type} — {link[:80]}")

            try:
                if is_google_drive(link):
                    await _with_retry(lambda l=link, n=i+1: g_DownLoad(l, n), link)

                elif is_terabox(link):
                    from leechbot.downloader.terabox import terabox_download
                    await _with_retry(lambda l=link, n=i+1: terabox_download(l, n), link)

                elif is_gallery(link):
                    await _with_retry(lambda l=link, n=i+1: gallery_download(l, n), link)

                elif is_hls_stream(link):
                    # HLS (.m3u8) and DASH (.mpd) streams → yt-dlp handles natively
                    await _with_retry(lambda l=link, n=i+1: YTDL_Status(l, n), link)
                    try:
                        await MSG.status_msg.edit_text(
                            text=Messages.task_msg + Messages.status_head + merge_msg + sysINFO(),
                            reply_markup=keyboard()
                        )
                    except Exception:
                        pass
                    while not isYtdlComplete():
                        await sleep(2)

                elif is_gofile(link):
                    from leechbot.downloader.gofile import gofile_download
                    await _with_retry(lambda l=link, n=i+1: gofile_download(l, n), link)

                elif is_catbox(link):
                    from leechbot.downloader.catbox import catbox_download
                    await _with_retry(lambda l=link, n=i+1: catbox_download(l, n), link)

                elif is_streamtape(link):
                    from leechbot.downloader.streamtape import streamtape_download
                    await _with_retry(lambda l=link, n=i+1: streamtape_download(l, n), link)

                elif is_ytdl_link(link):
                    await _with_retry(lambda l=link, n=i+1: YTDL_Status(l, n), link)
                    try:
                        await MSG.status_msg.edit_text(
                            text=Messages.task_msg + Messages.status_head + merge_msg + sysINFO(),
                            reply_markup=keyboard()
                        )
                    except Exception:
                        pass
                    while not isYtdlComplete():
                        await sleep(2)

                elif is_mega(link):
                    await _with_retry(lambda l=link, n=i+1: megadl(l, n), link)

                elif is_pixeldrain(link):
                    from leechbot.downloader.pixeldrain import pixeldrain_download
                    await _with_retry(lambda l=link, n=i+1: pixeldrain_download(l, n), link)

                elif is_mediafire(link):
                    from leechbot.downloader.mediafire import mediafire_download
                    await _with_retry(lambda l=link, n=i+1: mediafire_download(l, n), link)

                elif is_torrent(link):
                    try:
                        from leechbot.downloader.torrent import torrent_download
                        await _with_retry(lambda l=link, n=i+1: torrent_download(l, n), link)
                    except ImportError:
                        # libtorrent not installed — fall back to aria2c
                        logger.warning("libtorrent not available, falling back to aria2c for torrent/magnet")
                        logger.warning("⚠️ libtorrent not installed — using aria2c fallback")
                        Aria2c.link_info = False
                        await _with_retry(lambda l=link, n=i+1: aria2_Download(l, n), link)

                else:
                    # Default: aria2c (HTTP/FTP/torrent)
                    aria_msg = f"<b>⏳ Getting Info...</b>\n\n<code>{link}</code>"
                    try:
                        await MSG.status_msg.edit_text(
                            text=aria_msg + sysINFO(),
                            reply_markup=keyboard()
                        )
                    except Exception:
                        pass

                    Aria2c.link_info = False
                    await _with_retry(lambda l=link, n=i+1: aria2_Download(l, n), link)

            except Exception as error:
                await cancelTask(f"Download Error: {error}")
                BotStats.failed_tasks += 1
                logger.error(f"Download error for {link}: {error}")
                return


# =============================================================================
# Calculate Total Download Size
# =============================================================================
async def calDownSize(sources: list):
    """Calculate total download size from all sources."""
    from natsort import natsorted
    from leechbot.downloader.gdrive import build_service, getIDFromURL, getFileMetadata, get_Gfolder_size
    from leechbot.utility.handler import cancelTask

    for link in natsorted(sources):
        if is_google_drive(link):
            await build_service()
            file_id = await getIDFromURL(link)
            try:
                meta = await getFileMetadata(file_id)
            except Exception as e:
                err_msg = f"GDrive error: {e}"
                if "not found" in str(e).lower():
                    err_msg = "File not found or no access"
                elif "authorization" in str(e).lower():
                    err_msg = "Google Drive authorization failed"
                logger.error(err_msg)
                await cancelTask(err_msg)
            else:
                if meta.get("mimeType") == "application/vnd.google-apps.folder":
                    Transfer.total_down_size += await get_Gfolder_size(file_id)
                else:
                    Transfer.total_down_size += int(meta.get("size", 0))


# =============================================================================
# Get Download Name
# =============================================================================
async def get_d_name(link: str):
    """Resolve the human-readable download name from a link."""
    from leechbot.downloader.gdrive import getIDFromURL, getFileMetadata
    from leechbot.downloader.ytdl import get_YT_Name
    from leechbot.downloader.aria2 import get_Aria2c_Name

    if BOT.Options.custom_name:
        Messages.download_name = BOT.Options.custom_name
        return

    if is_google_drive(link):
        file_id = await getIDFromURL(link)
        meta = await getFileMetadata(file_id)
        Messages.download_name = meta.get("name", "GDrive File")
    elif is_gallery(link):
        from leechbot.downloader.gallery import get_gallery_name
        Messages.download_name = await get_gallery_name(link)
    elif is_terabox(link):
        Messages.download_name = "Terabox Download"
    elif is_ytdl_link(link):
        Messages.download_name = await get_YT_Name(link)
    elif is_hls_stream(link):
        Messages.download_name = await get_YT_Name(link)
    elif is_torrent(link):
        try:
            from leechbot.downloader.torrent import get_torrent_name
            Messages.download_name = await get_torrent_name(link)
        except ImportError:
            Messages.download_name = "Torrent/Magnet (aria2c)"

    elif is_mega(link):
        Messages.download_name = "Mega Download"
    elif is_pixeldrain(link):
        Messages.download_name = "Pixeldrain File"
    elif is_mediafire(link):
        Messages.download_name = "Mediafire File"
    else:
        Messages.download_name = get_Aria2c_Name(link)

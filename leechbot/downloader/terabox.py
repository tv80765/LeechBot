# =============================================================================
# Telegram Leech Bot - Terabox Downloader
# =============================================================================
# Project   : LeechBot
# Developer : Shinei Nouzen
# GitHub    : https://github.com/Shineii86
# Telegram  : https://telegram.me/Shineii86
# =============================================================================

"""
Terabox downloader module.

Resolves Terabox share links via configurable/third-party APIs or page
extraction, then hands direct URLs to aria2c for the actual download.
"""

import logging
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import aiohttp

import config
from leechbot.utility.handler import cancelTask
from leechbot.downloader.aria2 import aria2_Download

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=45)
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

# Legacy API (often offline) — kept as last resort
_SAVETUBE_API = "https://ytshorts.savetube.me/api/v1/terabox-downloader"


def normalize_terabox_url(link: str) -> str:
    """Normalize app-style share URLs to a common terabox.com /s/ form."""
    link = link.strip()
    parsed = urlparse(link)
    host = (parsed.hostname or "").lower()
    if "terabox.app" in host and "sharing/link" in parsed.path:
        surl = (parse_qs(parsed.query).get("surl") or [""])[0]
        if surl:
            surl = unquote(surl)
            if not surl.startswith("1"):
                surl = f"1{surl}"
            return f"https://www.terabox.com/s/{surl}"
    return link


def _candidate_urls(link: str) -> list[str]:
    """URLs to try when resolving (app link + normalized variants)."""
    seen: set[str] = set()
    out: list[str] = []

    def add(u: str) -> None:
        u = u.strip()
        if u and u not in seen:
            seen.add(u)
            out.append(u)

    add(link)
    norm = normalize_terabox_url(link)
    add(norm)
    parsed = urlparse(norm)
    path = parsed.path.rstrip("/")
    if path.startswith("/s/"):
        code = path.split("/s/", 1)[-1]
        add(f"https://1024terabox.com/s/{code.lstrip('1')}")
        add(f"https://www.terabox.com/s/{code}")
    return out


def _parse_savetube_resolutions(data: dict) -> dict | None:
    try:
        return data["response"][0]["resolutions"]
    except (KeyError, IndexError, TypeError):
        return None


def _find_http_url(obj: Any, depth: int = 0) -> str | None:
    """Walk JSON for the first plausible direct download URL."""
    if depth > 8:
        return None
    if isinstance(obj, str) and obj.startswith("http"):
        lower = obj.lower()
        if any(x in lower for x in ("dlink", "download", "pcsdata", "baidupcs", "terabox")):
            return obj
        if ".mp4" in lower or "filename=" in lower:
            return obj
    if isinstance(obj, dict):
        for key in ("dlink", "direct_link", "download_url", "url", "link", "fastDownload", "hd"):
            if key in obj:
                found = _find_http_url(obj[key], depth + 1)
                if found:
                    return found
        for val in obj.values():
            found = _find_http_url(val, depth + 1)
            if found:
                return found
    if isinstance(obj, list):
        for item in obj:
            found = _find_http_url(item, depth + 1)
            if found:
                return found
    return None


async def _request_json(
    session: aiohttp.ClientSession,
    method: str,
    url: str,
    link: str,
) -> dict | list | None:
    headers = {"User-Agent": _UA, "Accept": "application/json"}
    try:
        if method == "GET":
            async with session.get(url, params={"url": link}, headers=headers) as resp:
                if resp.status >= 400:
                    return None
                return await resp.json(content_type=None)
        async with session.post(
            url,
            json={"url": link},
            headers={**headers, "Content-Type": "application/json"},
        ) as resp:
            if resp.status >= 400:
                return None
            return await resp.json(content_type=None)
    except Exception as e:
        logger.debug("Terabox API %s %s failed: %s", method, url, e)
        return None


async def _fetch_via_savetube(session: aiohttp.ClientSession, link: str) -> dict | None:
    headers = {
        "User-Agent": _UA,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://ytshorts.savetube.me",
    }
    try:
        async with session.post(_SAVETUBE_API, json={"url": link}, headers=headers) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
    except Exception as e:
        logger.debug("Savetube Terabox API failed: %s", e)
        return None
    return _parse_savetube_resolutions(data) if isinstance(data, dict) else None


async def _extract_from_share_page(session: aiohttp.ClientSession, link: str) -> str | None:
    headers = {"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"}
    try:
        async with session.get(link, headers=headers, allow_redirects=True) as resp:
            if resp.status >= 400:
                return None
            html = await resp.text()
    except Exception as e:
        logger.debug("Terabox page fetch failed for %s: %s", link[:60], e)
        return None

    patterns = [
        r'"dlink"\s*:\s*"([^"]+)"',
        r'"downloadLink"\s*:\s*"([^"]+)"',
        r'https?://[^"\'\s]+dlink[^"\'\s]*',
    ]
    for pat in patterns:
        for match in re.findall(pat, html):
            url = match.encode().decode("unicode_escape") if "\\u" in match else match
            url = url.replace("\\/", "/")
            if url.startswith("http"):
                return url
    return None


async def _fetch_download_urls(link: str) -> dict:
    """
    Resolve Terabox share link to a resolutions dict (fast/slow URLs).

    Raises:
        RuntimeError: if no provider returns usable links.
    """
    errors: list[str] = []
    custom = (config.TERABOX_API_URL or "").strip()

    async with aiohttp.ClientSession(timeout=_REQUEST_TIMEOUT) as session:
        for candidate in _candidate_urls(link):
            if custom:
                for method in ("GET", "POST"):
                    data = await _request_json(session, method, custom, candidate)
                    if data is None:
                        continue
                    if isinstance(data, dict):
                        resolutions = _parse_savetube_resolutions(data)
                        if resolutions:
                            return resolutions
                        direct = _find_http_url(data)
                        if direct:
                            return {"Fast Download": direct}
                    errors.append(f"custom API ({method}) returned no link")

            page_url = await _extract_from_share_page(session, candidate)
            if page_url:
                return {"Fast Download": page_url}

            resolutions = await _fetch_via_savetube(session, candidate)
            if resolutions:
                return resolutions

    hint = (
        "Terabox resolver failed (third-party API offline or link blocked). "
        "Set TERABOX_API_URL to your own resolver (e.g. self-hosted terabox-gateway) in Railway variables."
    )
    if errors:
        logger.warning("Terabox resolver attempts: %s", "; ".join(errors[:3]))
    raise RuntimeError(hint)


# =============================================================================
# Resolve the best working direct URL
# =============================================================================
async def _resolve_direct_url(resolutions: dict) -> str:
    """
    From the resolutions dict, return the first URL that resolves
    to an actual file (not an HTML page).

    Falls back to slow/HD link if fast link returns HTML.
    """
    fast_url = resolutions.get("Fast Download", "")
    slow_url = resolutions.get("HD Video", "")

    if not fast_url and not slow_url:
        raise RuntimeError("No download URLs found in Terabox response")

    if fast_url and not slow_url:
        return fast_url
    if slow_url and not fast_url:
        return slow_url

    try:
        async with aiohttp.ClientSession(timeout=_REQUEST_TIMEOUT) as session:
            async with session.get(fast_url, allow_redirects=True) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if any(t in content_type for t in ("application/octet-stream", "video/", "audio/", "image/")):
                    logger.info("Terabox: using Fast Download link")
                    return fast_url
                logger.info("Terabox: fast link returned %s, using HD link", content_type)
                return slow_url
    except Exception as e:
        logger.warning("Terabox: fast link probe failed (%s), using HD link", e)
        return slow_url


# =============================================================================
# Main Download Function
# =============================================================================
async def terabox_download(link: str, index: int):
    """
    Download file from Terabox.

    Args:
        link: Terabox share link
        index: link number
    """
    logger.info("Starting Terabox download: %s", link[:80])

    try:
        resolutions = await _fetch_download_urls(link)
        direct_url = await _resolve_direct_url(resolutions)
        logger.info("Terabox: downloading via aria2c")
        await aria2_Download(direct_url, index)

    except aiohttp.ClientError as e:
        logger.error("Terabox HTTP error: %s", e)
        await cancelTask(f"Terabox API request failed: {e}")
    except RuntimeError as e:
        logger.error("Terabox error: %s", e)
        await cancelTask(f"Terabox: {e}")
    except Exception as e:
        logger.error("Terabox download error: %s", e)
        await cancelTask(f"Terabox Download Failed: {e}")

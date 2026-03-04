"""Bilibili API client — thin async wrappers around bilibili-api-python.

All public functions are async and accept an optional Credential for
authenticated operations (subtitles, favorites, etc.).
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import aiohttp
from bilibili_api import comment, favorite_list, homepage, hot, rank, search, user, video
from bilibili_api.exceptions import (
    ApiException,
    CredentialNoBiliJctException,
    CredentialNoSessdataException,
    NetworkException,
    ResponseCodeException,
    ResponseException,
)
from bilibili_api.utils.network import Credential

from .exceptions import AuthenticationError, BiliError, InvalidBvidError, NetworkError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BV ID helpers
# ---------------------------------------------------------------------------

_BVID_RE = re.compile(r"\bBV[0-9A-Za-z]{10}\b")


def extract_bvid(url_or_bvid: str) -> str:
    """Extract BV ID from a Bilibili URL or return as-is if already a BV ID."""
    match = _BVID_RE.search(url_or_bvid)
    if match:
        return match.group(0)
    raise InvalidBvidError(f"无法提取 BV 号: {url_or_bvid}")


def _map_api_error(action: str, exc: Exception) -> BiliError:
    """Map third-party API exceptions into stable local exception types."""
    if isinstance(exc, BiliError):
        return exc

    if isinstance(exc, (CredentialNoSessdataException, CredentialNoBiliJctException)):
        return AuthenticationError(f"{action}: {exc}")

    if isinstance(exc, ResponseCodeException):
        code = getattr(exc, "code", None)
        if code in {-101, -111}:
            return AuthenticationError(f"{action}: {exc}")
        return BiliError(f"{action}: [{code}] {exc}")

    if isinstance(exc, (NetworkException, ResponseException, aiohttp.ClientError, asyncio.TimeoutError)):
        return NetworkError(f"{action}: {exc}")

    if isinstance(exc, ApiException):
        return BiliError(f"{action}: {exc}")

    return BiliError(f"{action}: {exc}")


async def _call_api(action: str, awaitable):
    """Run an awaitable and normalize API/network/auth errors."""
    try:
        return await awaitable
    except Exception as exc:
        raise _map_api_error(action, exc) from exc


# ---------------------------------------------------------------------------
# Video
# ---------------------------------------------------------------------------


async def get_video_info(bvid: str, credential: Credential | None = None) -> dict[str, Any]:
    """Fetch video metadata (title, duration, stats, owner, etc.)."""
    v = video.Video(bvid=bvid, credential=credential)
    return await _call_api("获取视频信息", v.get_info())


async def get_video_subtitle(
    bvid: str, credential: Credential | None = None
) -> tuple[str, list]:
    """Fetch video subtitle content.

    Returns (plain_text, raw_subtitle_items).
    An empty tuple element means no subtitle available.
    """
    v = video.Video(bvid=bvid, credential=credential)

    # Get cid from first page
    pages = await _call_api("获取视频分P信息", v.get_pages())
    if not pages:
        logger.warning("No pages found for %s", bvid)
        return "", []

    cid = pages[0].get("cid")
    if not cid:
        logger.warning("No cid found for %s", bvid)
        return "", []

    # Get subtitle list from player info
    player_info = await _call_api("获取播放器信息", v.get_player_info(cid=cid))
    subtitle_info = player_info.get("subtitle", {})

    if not subtitle_info or not subtitle_info.get("subtitles"):
        return "", []

    subtitle_list = subtitle_info["subtitles"]

    # Prefer Chinese subtitles
    subtitle_url = None
    for sub in subtitle_list:
        if "zh" in sub.get("lan", "").lower():
            subtitle_url = sub.get("subtitle_url", "")
            break

    if not subtitle_url and subtitle_list:
        subtitle_url = subtitle_list[0].get("subtitle_url", "")

    if not subtitle_url:
        return "", []

    # Ensure absolute URL
    if subtitle_url.startswith("//"):
        subtitle_url = "https:" + subtitle_url

    # Download subtitle JSON
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(subtitle_url) as resp:
                resp.raise_for_status()
                subtitle_data = await resp.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
        raise NetworkError(f"下载字幕失败: {e}") from e

    if "body" in subtitle_data:
        raw = subtitle_data["body"]
        texts = [item.get("content", "") for item in raw]
        return "\n".join(texts), raw

    return "", []


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


async def get_user_info(uid: int, credential: Credential | None = None) -> dict[str, Any]:
    """Fetch user profile information."""
    u = user.User(uid=uid, credential=credential)
    return await _call_api("获取用户信息", u.get_user_info())


async def get_user_relation_info(uid: int, credential: Credential | None = None) -> dict[str, Any]:
    """Fetch user relation stats (follower count, following count)."""
    u = user.User(uid=uid, credential=credential)
    return await _call_api("获取用户关系信息", u.get_relation_info())


async def get_user_videos(
    uid: int, count: int = 10, credential: Credential | None = None
) -> list[dict[str, Any]]:
    """Fetch a user's latest videos.

    Returns list of video dicts (bvid, title, play, length, etc.).
    """
    u = user.User(uid=uid, credential=credential)

    results: list[dict[str, Any]] = []
    page = 1
    per_page = min(count, 50)

    while len(results) < count:
        try:
            data = await _call_api("获取用户视频列表", u.get_videos(ps=per_page, pn=page))
        except BiliError as e:
            if page == 1:
                raise
            logger.warning("Failed to get videos page %d: %s", page, e)
            break

        vlist = data.get("list", {}).get("vlist", [])
        if not vlist:
            break

        for v in vlist:
            results.append(v)
            if len(results) >= count:
                break

        page += 1
        if page > 20:
            break

    return results


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


async def search_user(keyword: str, page: int = 1) -> list[dict[str, Any]]:
    """Search for users by keyword.

    Returns list of user result dicts.
    """
    res = await _call_api("搜索用户", search.search_by_type(
        keyword=keyword,
        search_type=search.SearchObjectType.USER,
        page=page,
    ))
    return res.get("result", [])


# ---------------------------------------------------------------------------
# Favorites
# ---------------------------------------------------------------------------


async def get_self_info(credential: Credential) -> dict[str, Any]:
    """Get logged-in user's own info."""
    return await _call_api("获取当前登录用户信息", user.get_self_info(credential))


async def get_favorite_list(credential: Credential) -> list[dict[str, Any]]:
    """List all favorite folders for the logged-in user."""
    me = await get_self_info(credential)
    uid = me.get("mid")
    if uid is None:
        raise BiliError("获取收藏夹列表: 当前用户信息缺少 mid")

    fav_data = await _call_api(
        "获取收藏夹列表",
        favorite_list.get_video_favorite_list(uid=uid, credential=credential),
    )
    return fav_data.get("list", [])


async def get_favorite_videos(
    fav_id: int, credential: Credential, page: int = 1
) -> dict[str, Any]:
    """Get videos in a specific favorite folder.

    Returns the raw response dict with 'medias', 'has_more', etc.
    """
    return await _call_api(
        "获取收藏夹内容",
        favorite_list.get_video_favorite_list_content(
            media_id=fav_id, page=page, credential=credential
        ),
    )


# ---------------------------------------------------------------------------
# Hot & Rank
# ---------------------------------------------------------------------------


async def get_hot_videos(pn: int = 1, ps: int = 20) -> dict[str, Any]:
    """Fetch popular/hot videos."""
    return await _call_api("获取热门视频", hot.get_hot_videos(pn=pn, ps=ps))


async def get_rank_videos(day: int = 3) -> dict[str, Any]:
    """Fetch ranking videos (default: 3-day rank)."""
    day_type = rank.RankDayType.THREE_DAY if day == 3 else rank.RankDayType.WEEK
    return await _call_api("获取排行榜", rank.get_rank(day=day_type))


# ---------------------------------------------------------------------------
# Video extras
# ---------------------------------------------------------------------------


async def get_video_comments(
    bvid: str, page: int = 1, credential: Credential | None = None
) -> dict[str, Any]:
    """Fetch video comments."""
    v = video.Video(bvid=bvid, credential=credential)
    info = await _call_api("获取视频信息", v.get_info())
    aid = info.get("aid")
    if aid is None:
        raise BiliError("获取视频评论: 视频信息缺少 aid")
    return await _call_api(
        "获取视频评论",
        comment.get_comments(
            oid=aid,
            type_=comment.CommentResourceType.VIDEO,
            page_index=page,
            credential=credential,
        ),
    )


async def get_video_ai_conclusion(
    bvid: str, credential: Credential | None = None
) -> dict[str, Any]:
    """Fetch AI-generated video summary."""
    v = video.Video(bvid=bvid, credential=credential)
    pages = await _call_api("获取视频分P信息", v.get_pages())
    if not pages:
        return {}
    cid = pages[0].get("cid")
    if not cid:
        return {}
    return await _call_api("获取 AI 总结", v.get_ai_conclusion(cid=cid))


async def get_related_videos(
    bvid: str, credential: Credential | None = None
) -> list[dict[str, Any]]:
    """Fetch related/recommended videos."""
    v = video.Video(bvid=bvid, credential=credential)
    data = await _call_api("获取相关推荐", v.get_related())
    if isinstance(data, list):
        return data
    return []


# ---------------------------------------------------------------------------
# Search (video)
# ---------------------------------------------------------------------------


async def search_video(keyword: str, page: int = 1) -> list[dict[str, Any]]:
    """Search for videos by keyword."""
    res = await _call_api("搜索视频", search.search_by_type(
        keyword=keyword,
        search_type=search.SearchObjectType.VIDEO,
        page=page,
    ))
    return res.get("result", [])


# ---------------------------------------------------------------------------
# Following & Toview
# ---------------------------------------------------------------------------


async def get_followings(
    uid: int, pn: int = 1, ps: int = 20, credential: Credential | None = None
) -> dict[str, Any]:
    """Fetch user's following list."""
    u = user.User(uid=uid, credential=credential)
    return await _call_api("获取关注列表", u.get_followings(pn=pn, ps=ps))


async def get_toview(credential: Credential) -> dict[str, Any]:
    """Fetch watch-later (稍后再看) list."""
    data = await _call_api("获取稍后再看列表", homepage.get_favorite_list_and_toview(credential))
    if not isinstance(data, list):
        logger.warning("Unexpected toview payload type: %s", type(data).__name__)
        return {"list": [], "count": 0}
    # data is a list; the item with name="稍后再看" contains toview videos
    for item in data:
        if item.get("name") == "稍后再看" or item.get("id") == 2:
            resp = item.get("mediaListResponse", {})
            return {
                "list": resp.get("list", []),
                "count": resp.get("count", 0),
            }
    return {"list": [], "count": 0}


# ---------------------------------------------------------------------------
# Dynamic Feed
# ---------------------------------------------------------------------------


async def get_dynamic_feed(
    offset: str = "", credential: Credential | None = None
) -> dict[str, Any]:
    """Fetch dynamic feed (动态时间线)."""
    if credential is None:
        raise AuthenticationError("credential is required for dynamic feed")
    me = await get_self_info(credential)
    uid = me.get("mid")
    if uid is None:
        raise BiliError("获取动态时间线: 当前用户信息缺少 mid")
    u = user.User(uid=uid, credential=credential)
    return await _call_api("获取动态时间线", u.get_dynamics_new(offset=offset))


# ---------------------------------------------------------------------------
# Interactions (like, coin, triple)
# ---------------------------------------------------------------------------


async def like_video(bvid: str, credential: Credential, undo: bool = False) -> dict[str, Any]:
    """Like or unlike a video."""
    v = video.Video(bvid=bvid, credential=credential)
    return await _call_api("点赞视频", v.like(status=not undo))


async def coin_video(bvid: str, credential: Credential, num: int = 1) -> dict[str, Any]:
    """Give coins to a video (1 or 2)."""
    v = video.Video(bvid=bvid, credential=credential)
    return await _call_api("投币", v.pay_coin(num=num))


async def triple_video(bvid: str, credential: Credential) -> dict[str, Any]:
    """Triple (like + coin + favorite) a video."""
    v = video.Video(bvid=bvid, credential=credential)
    return await _call_api("一键三连", v.triple())

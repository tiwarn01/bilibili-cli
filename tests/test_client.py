"""Tests for client.py — mock bilibili-api internals."""

from unittest.mock import AsyncMock, patch

import pytest
from bilibili_api.exceptions import CredentialNoSessdataException, NetworkException

from bili_cli import client
from bili_cli.exceptions import AuthenticationError, BiliError, InvalidBvidError, NetworkError


@pytest.mark.asyncio
async def test_get_video_info(mock_video_info):
    with patch("bili_cli.client.video.Video") as MockVideo:
        MockVideo.return_value.get_info = AsyncMock(return_value=mock_video_info)
        result = await client.get_video_info("BV1test123")
        assert result["title"] == "测试视频标题"
        assert result["stat"]["view"] == 15000
        MockVideo.assert_called_once_with(bvid="BV1test123", credential=None)


@pytest.mark.asyncio
async def test_get_video_info_maps_network_exception():
    with patch("bili_cli.client.video.Video") as MockVideo:
        MockVideo.return_value.get_info = AsyncMock(side_effect=NetworkException(-1, "timeout"))
        with pytest.raises(NetworkError):
            await client.get_video_info("BV1test123")


@pytest.mark.asyncio
async def test_get_video_info_maps_auth_exception():
    with patch("bili_cli.client.video.Video") as MockVideo:
        MockVideo.return_value.get_info = AsyncMock(side_effect=CredentialNoSessdataException())
        with pytest.raises(AuthenticationError):
            await client.get_video_info("BV1test123")


@pytest.mark.asyncio
async def test_get_user_info(mock_user_info):
    with patch("bili_cli.client.user.User") as MockUser:
        MockUser.return_value.get_user_info = AsyncMock(return_value=mock_user_info)
        result = await client.get_user_info(946974)
        assert result["name"] == "TestUP"
        assert result["level"] == 6


@pytest.mark.asyncio
async def test_get_user_relation_info(mock_relation_info):
    with patch("bili_cli.client.user.User") as MockUser:
        MockUser.return_value.get_relation_info = AsyncMock(return_value=mock_relation_info)
        result = await client.get_user_relation_info(946974)
        assert result["follower"] == 50000
        assert result["following"] == 100


@pytest.mark.asyncio
async def test_get_hot_videos():
    mock_data = {"list": [{"bvid": "BV1hot", "title": "Hot Video"}]}
    with patch("bili_cli.client.hot.get_hot_videos", new_callable=AsyncMock, return_value=mock_data):
        result = await client.get_hot_videos()
        assert len(result["list"]) == 1
        assert result["list"][0]["bvid"] == "BV1hot"


@pytest.mark.asyncio
async def test_get_rank_videos():
    mock_data = {"list": [{"bvid": "BV1rank", "title": "Rank Video", "score": 1000}]}
    with patch("bili_cli.client.rank.get_rank", new_callable=AsyncMock, return_value=mock_data):
        result = await client.get_rank_videos()
        assert result["list"][0]["score"] == 1000


@pytest.mark.asyncio
async def test_search_user():
    mock_data = {"result": [{"mid": 123, "uname": "TestUser", "fans": 100}]}
    with patch("bili_cli.client.search.search_by_type", new_callable=AsyncMock, return_value=mock_data):
        result = await client.search_user("test")
        assert len(result) == 1
        assert result[0]["uname"] == "TestUser"


@pytest.mark.asyncio
async def test_search_video():
    mock_data = {"result": [{"bvid": "BV1found", "title": "Found", "author": "UP"}]}
    with patch("bili_cli.client.search.search_by_type", new_callable=AsyncMock, return_value=mock_data):
        result = await client.search_video("test")
        assert len(result) == 1
        assert result[0]["bvid"] == "BV1found"


@pytest.mark.asyncio
async def test_search_user_empty():
    mock_data = {"result": []}
    with patch("bili_cli.client.search.search_by_type", new_callable=AsyncMock, return_value=mock_data):
        result = await client.search_user("nonexistent")
        assert result == []


@pytest.mark.asyncio
async def test_get_related_videos():
    mock_related = [{"bvid": "BV1rel", "title": "Related"}]
    with patch("bili_cli.client.video.Video") as MockVideo:
        MockVideo.return_value.get_related = AsyncMock(return_value=mock_related)
        result = await client.get_related_videos("BV1test")
        assert len(result) == 1


@pytest.mark.asyncio
async def test_like_video(mock_credential):
    with patch("bili_cli.client.video.Video") as MockVideo:
        MockVideo.return_value.like = AsyncMock(return_value={})
        await client.like_video("BV1test", credential=mock_credential)
        MockVideo.return_value.like.assert_called_once_with(status=True)


@pytest.mark.asyncio
async def test_like_video_undo(mock_credential):
    with patch("bili_cli.client.video.Video") as MockVideo:
        MockVideo.return_value.like = AsyncMock(return_value={})
        await client.like_video("BV1test", credential=mock_credential, undo=True)
        MockVideo.return_value.like.assert_called_once_with(status=False)


@pytest.mark.asyncio
async def test_triple_video(mock_credential):
    mock_result = {"like": True, "coin": True, "fav": True}
    with patch("bili_cli.client.video.Video") as MockVideo:
        MockVideo.return_value.triple = AsyncMock(return_value=mock_result)
        result = await client.triple_video("BV1test", credential=mock_credential)
        assert result["like"] is True
        assert result["coin"] is True


@pytest.mark.asyncio
async def test_coin_video(mock_credential):
    with patch("bili_cli.client.video.Video") as MockVideo:
        MockVideo.return_value.pay_coin = AsyncMock(return_value={})
        await client.coin_video("BV1test", credential=mock_credential, num=2)
        MockVideo.return_value.pay_coin.assert_called_once_with(num=2)


@pytest.mark.asyncio
async def test_get_user_videos_respects_count():
    page1 = {"list": {"vlist": [{"bvid": "BV1a"}, {"bvid": "BV1b"}, {"bvid": "BV1c"}]}}
    with patch("bili_cli.client.user.User") as MockUser:
        MockUser.return_value.get_videos = AsyncMock(return_value=page1)
        result = await client.get_user_videos(uid=1, count=2)
        assert len(result) == 2
        assert result[0]["bvid"] == "BV1a"
        MockUser.return_value.get_videos.assert_called_once_with(ps=2, pn=1)


@pytest.mark.asyncio
async def test_get_user_videos_returns_partial_on_page_error():
    page1 = {"list": {"vlist": [{"bvid": "BV1a"}, {"bvid": "BV1b"}]}}
    with patch("bili_cli.client.user.User") as MockUser:
        MockUser.return_value.get_videos = AsyncMock(
            side_effect=[page1, Exception("network fail")]
        )
        result = await client.get_user_videos(uid=1, count=5)
        assert len(result) == 2
        assert [v["bvid"] for v in result] == ["BV1a", "BV1b"]


@pytest.mark.asyncio
async def test_get_user_videos_raises_on_first_page_error():
    with patch("bili_cli.client.user.User") as MockUser:
        MockUser.return_value.get_videos = AsyncMock(side_effect=Exception("first page failed"))
        with pytest.raises(BiliError):
            await client.get_user_videos(uid=1, count=5)


@pytest.mark.asyncio
async def test_get_toview_by_name(mock_credential):
    data = [
        {
            "name": "稍后再看",
            "mediaListResponse": {"list": [{"bvid": "BV1later"}], "count": 1},
        }
    ]
    with patch("bili_cli.client.homepage.get_favorite_list_and_toview", new_callable=AsyncMock, return_value=data):
        result = await client.get_toview(mock_credential)
        assert result["count"] == 1
        assert result["list"][0]["bvid"] == "BV1later"


@pytest.mark.asyncio
async def test_get_watch_history_calls_user_api(mock_credential):
    mock_data = {"list": [{"title": "watched"}]}
    with patch("bili_cli.client.user.get_self_history", new_callable=AsyncMock, return_value=mock_data) as mock_history:
        result = await client.get_watch_history(page=2, count=50, credential=mock_credential)
        assert result == mock_data
        mock_history.assert_awaited_once_with(page_num=2, per_page_item=50, credential=mock_credential)


@pytest.mark.asyncio
async def test_get_watch_history_requires_credential():
    with pytest.raises(AuthenticationError):
        await client.get_watch_history()


@pytest.mark.asyncio
async def test_get_toview_by_id(mock_credential):
    data = [
        {
            "id": 2,
            "mediaListResponse": {"list": [{"bvid": "BV1id"}], "count": 1},
        }
    ]
    with patch("bili_cli.client.homepage.get_favorite_list_and_toview", new_callable=AsyncMock, return_value=data):
        result = await client.get_toview(mock_credential)
        assert result["count"] == 1
        assert result["list"][0]["bvid"] == "BV1id"


@pytest.mark.asyncio
async def test_get_toview_empty_when_not_found(mock_credential):
    with patch("bili_cli.client.homepage.get_favorite_list_and_toview", new_callable=AsyncMock, return_value=[]):
        result = await client.get_toview(mock_credential)
        assert result == {"list": [], "count": 0}


@pytest.mark.asyncio
async def test_get_toview_unexpected_payload_type_returns_empty(mock_credential):
    with patch("bili_cli.client.homepage.get_favorite_list_and_toview", new_callable=AsyncMock, return_value={"x": 1}):
        result = await client.get_toview(mock_credential)
        assert result == {"list": [], "count": 0}


@pytest.mark.asyncio
async def test_get_dynamic_feed_requires_credential():
    with pytest.raises(AuthenticationError):
        await client.get_dynamic_feed()


@pytest.mark.asyncio
async def test_get_dynamic_feed_uses_dynamic_page_info(mock_credential):
    data = {"items": []}
    with patch("bili_cli.client.dynamic.get_dynamic_page_info", new_callable=AsyncMock, return_value=data) as mock_feed:
        result = await client.get_dynamic_feed(credential=mock_credential)
        assert result == data
        mock_feed.assert_awaited_once_with(credential=mock_credential, pn=1, offset=None)


@pytest.mark.asyncio
async def test_get_dynamic_feed_parses_offset_string(mock_credential):
    with patch("bili_cli.client.dynamic.get_dynamic_page_info", new_callable=AsyncMock, return_value={"items": []}) as mock_feed:
        await client.get_dynamic_feed(offset="12345", credential=mock_credential)
        mock_feed.assert_awaited_once_with(credential=mock_credential, pn=1, offset=12345)


@pytest.mark.asyncio
async def test_get_dynamic_feed_invalid_offset_raises(mock_credential):
    with pytest.raises(BiliError, match="offset 非法"):
        await client.get_dynamic_feed(offset="not-int", credential=mock_credential)


@pytest.mark.asyncio
async def test_get_rank_videos_week_mode():
    mock_data = {"list": []}
    with patch("bili_cli.client.rank.get_rank", new_callable=AsyncMock, return_value=mock_data) as mock_rank:
        await client.get_rank_videos(day=7)
        mock_rank.assert_called_once_with(day=client.rank.RankDayType.WEEK)


def test_extract_bvid_invalid_type():
    with pytest.raises(InvalidBvidError):
        client.extract_bvid("BV123")


@pytest.mark.asyncio
async def test_get_video_subtitle_network_error():
    with patch("bili_cli.client.video.Video") as MockVideo:
        MockVideo.return_value.get_pages = AsyncMock(return_value=[{"cid": 1}])
        MockVideo.return_value.get_player_info = AsyncMock(
            return_value={"subtitle": {"subtitles": [{"lan": "zh-CN", "subtitle_url": "https://s.test/sub.json"}]}}
        )

        class FakeSession:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            def get(self, _url):
                raise client.aiohttp.ClientError("boom")

        with patch("bili_cli.client.aiohttp.ClientSession", FakeSession):
            with pytest.raises(NetworkError):
                await client.get_video_subtitle("BV1ABcsztEcY")


@pytest.mark.asyncio
async def test_get_video_ai_conclusion_returns_empty_for_no_pages():
    with patch("bili_cli.client.video.Video") as MockVideo:
        MockVideo.return_value.get_pages = AsyncMock(return_value=[])
        result = await client.get_video_ai_conclusion("BV1ABcsztEcY")
        assert result == {}

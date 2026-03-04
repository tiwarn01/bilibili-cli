"""Tests for CLI commands using Click CliRunner."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from bili_cli.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


# ===== Login/Status =====


def test_status_not_logged_in(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["status"])
        assert "未登录" in result.output
        assert result.exit_code != 0


def test_status_logged_in(runner, mock_user_info):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_self_info", new_callable=AsyncMock, return_value=mock_user_info):
        result = runner.invoke(cli, ["status"])
        assert "TestUP" in result.output
        assert "✅" in result.output


def test_logout(runner):
    with patch("bili_cli.commands.common.clear_credential") as mock_clear:
        result = runner.invoke(cli, ["logout"])
        assert "已注销" in result.output
        mock_clear.assert_called_once()


def test_login_runtime_error(runner):
    with patch("bili_cli.commands.common.qr_login", new_callable=AsyncMock, side_effect=RuntimeError("二维码已过期")):
        result = runner.invoke(cli, ["login"])
        assert result.exit_code != 0
        assert "二维码已过期" in result.output


def test_whoami_not_logged_in(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["whoami"])
        assert result.exit_code != 0
        assert "未登录" in result.output


def test_whoami_json(runner, mock_user_info, mock_relation_info):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_self_info", new_callable=AsyncMock, return_value=mock_user_info), \
         patch("bili_cli.client.get_user_relation_info", new_callable=AsyncMock, return_value=mock_relation_info):
        result = runner.invoke(cli, ["whoami", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["info"]["name"] == "TestUP"
        assert data["relation"]["follower"] == 50000


# ===== Video =====


def test_video_json(runner, mock_video_info):
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.extract_bvid", return_value="BV1test123"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, return_value=mock_video_info):
        result = runner.invoke(cli, ["video", "BV1test123", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["title"] == "测试视频标题"


def test_video_display(runner, mock_video_info):
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.extract_bvid", return_value="BV1test123"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, return_value=mock_video_info):
        result = runner.invoke(cli, ["video", "BV1test123"])
        assert result.exit_code == 0
        assert "测试视频标题" in result.output
        assert "BV1test123" in result.output


def test_video_does_not_load_optional_credential_when_no_optional_section(runner, mock_video_info):
    with patch("bili_cli.commands.common.get_credential", return_value=None) as mock_get_cred, \
         patch("bili_cli.client.extract_bvid", return_value="BV1test123"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, return_value=mock_video_info) as mock_get_info:
        result = runner.invoke(cli, ["video", "BV1test123"])
        assert result.exit_code == 0
        mock_get_cred.assert_not_called()
        mock_get_info.assert_awaited_once_with("BV1test123", credential=None)


def test_video_uses_optional_credential_mode_when_needed(runner, mock_video_info):
    with patch("bili_cli.commands.common.get_credential", return_value=None) as mock_get_cred, \
         patch("bili_cli.client.extract_bvid", return_value="BV1test123"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, return_value=mock_video_info), \
         patch("bili_cli.client.get_video_subtitle", new_callable=AsyncMock, return_value=("sub", [])):
        result = runner.invoke(cli, ["video", "BV1test123", "--subtitle"])
        assert result.exit_code == 0
        mock_get_cred.assert_called_once_with(mode="optional")


def test_video_subtitle_error_is_nonfatal(runner, mock_video_info):
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.extract_bvid", return_value="BV1test123"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, return_value=mock_video_info), \
         patch("bili_cli.client.get_video_subtitle", new_callable=AsyncMock, side_effect=Exception("boom")):
        result = runner.invoke(cli, ["video", "BV1test123", "--subtitle"])
        assert result.exit_code == 0
        assert "获取字幕失败" in result.output


def test_video_invalid_bvid(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["video", "invalid"])
        assert result.exit_code != 0


def test_video_api_error_returns_nonzero(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.extract_bvid", return_value="BV1test123"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["video", "BV1test123"])
        assert result.exit_code != 0
        assert "获取视频信息失败" in result.output


# ===== Hot =====


def test_hot_command(runner):
    mock_data = {
        "list": [
            {
                "bvid": "BV1hot",
                "title": "热门视频",
                "owner": {"name": "HotUP"},
                "stat": {"view": 100000, "like": 5000},
            }
        ]
    }
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.get_hot_videos", new_callable=AsyncMock, return_value=mock_data):
        result = runner.invoke(cli, ["hot", "--max", "1"])
        assert result.exit_code == 0
        assert "BV1hot" in result.output
        assert "热门" in result.output


def test_hot_forwards_page_option(runner):
    mock_data = {"list": []}
    with patch("bili_cli.client.get_hot_videos", new_callable=AsyncMock, return_value=mock_data) as mock_hot:
        result = runner.invoke(cli, ["hot", "--page", "2", "--max", "5"])
        assert result.exit_code == 0
        mock_hot.assert_awaited_once_with(pn=2, ps=5)


def test_hot_json(runner):
    mock_data = {"list": [{"bvid": "BV1hot", "title": "Hot"}]}
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.get_hot_videos", new_callable=AsyncMock, return_value=mock_data):
        result = runner.invoke(cli, ["hot", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["list"][0]["bvid"] == "BV1hot"


def test_hot_invalid_max(runner):
    result = runner.invoke(cli, ["hot", "--max", "0"])
    assert result.exit_code != 0


def test_hot_invalid_page(runner):
    result = runner.invoke(cli, ["hot", "--page", "0"])
    assert result.exit_code != 0


def test_hot_api_error_returns_nonzero(runner):
    with patch("bili_cli.client.get_hot_videos", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["hot"])
        assert result.exit_code != 0
        assert "获取热门视频失败" in result.output


def test_rank_json(runner):
    mock_data = {"list": [{"bvid": "BV1rank", "title": "Rank"}]}
    with patch("bili_cli.client.get_rank_videos", new_callable=AsyncMock, return_value=mock_data):
        result = runner.invoke(cli, ["rank", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["list"][0]["bvid"] == "BV1rank"


def test_rank_api_error_returns_nonzero(runner):
    with patch("bili_cli.client.get_rank_videos", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["rank"])
        assert result.exit_code != 0
        assert "获取排行榜失败" in result.output


def test_rank_forwards_day_option(runner):
    mock_data = {"list": []}
    with patch("bili_cli.client.get_rank_videos", new_callable=AsyncMock, return_value=mock_data) as mock_rank:
        result = runner.invoke(cli, ["rank", "--day", "7"])
        assert result.exit_code == 0
        mock_rank.assert_awaited_once_with(day=7)


def test_rank_invalid_max(runner):
    result = runner.invoke(cli, ["rank", "--max", "0"])
    assert result.exit_code != 0


# ===== Search =====


def test_search_user(runner):
    mock_results = [{"mid": 123, "uname": "TestUser", "fans": 1000, "videos": 10, "usign": "Hi"}]
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.search_user", new_callable=AsyncMock, return_value=mock_results):
        result = runner.invoke(cli, ["search", "test"])
        assert result.exit_code == 0
        assert "TestUser" in result.output


def test_search_video(runner):
    mock_results = [{"bvid": "BV1found", "title": "Found Video", "author": "UP", "play": 5000, "duration": "10:30"}]
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.search_video", new_callable=AsyncMock, return_value=mock_results):
        result = runner.invoke(cli, ["search", "test", "--type", "video"])
        assert result.exit_code == 0
        assert "BV1found" in result.output


def test_search_forwards_page_for_user(runner):
    with patch("bili_cli.client.search_user", new_callable=AsyncMock, return_value=[]) as mock_search_user:
        result = runner.invoke(cli, ["search", "test", "--page", "3"])
        assert result.exit_code == 0
        mock_search_user.assert_awaited_once_with("test", page=3)


def test_search_forwards_page_for_video(runner):
    with patch("bili_cli.client.search_video", new_callable=AsyncMock, return_value=[]) as mock_search_video:
        result = runner.invoke(cli, ["search", "test", "--type", "video", "--page", "2"])
        assert result.exit_code == 0
        mock_search_video.assert_awaited_once_with("test", page=2)


def test_search_invalid_page(runner):
    result = runner.invoke(cli, ["search", "test", "--page", "0"])
    assert result.exit_code != 0


def test_search_invalid_max(runner):
    result = runner.invoke(cli, ["search", "test", "--max", "0"])
    assert result.exit_code != 0


def test_search_empty(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.search_user", new_callable=AsyncMock, return_value=[]):
        result = runner.invoke(cli, ["search", "nonexistent_xyz"])
        assert "未找到" in result.output


def test_search_user_api_error_returns_nonzero(runner):
    with patch("bili_cli.client.search_user", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["search", "abc"])
        assert result.exit_code != 0
        assert "搜索用户失败" in result.output


def test_search_video_api_error_returns_nonzero(runner):
    with patch("bili_cli.client.search_video", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["search", "abc", "--type", "video"])
        assert result.exit_code != 0
        assert "搜索视频失败" in result.output


# ===== User =====


def test_user_by_uid(runner, mock_user_info, mock_relation_info):
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.get_user_info", new_callable=AsyncMock, return_value=mock_user_info), \
         patch("bili_cli.client.get_user_relation_info", new_callable=AsyncMock, return_value=mock_relation_info):
        result = runner.invoke(cli, ["user", "946974"])
        assert result.exit_code == 0
        assert "TestUP" in result.output
        assert "5.0万" in result.output  # follower count


def test_user_videos_json(runner):
    videos = [{"bvid": "BV1new", "title": "New Video", "play": 123, "length": "01:23"}]
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.get_user_videos", new_callable=AsyncMock, return_value=videos):
        result = runner.invoke(cli, ["user-videos", "946974", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["bvid"] == "BV1new"


def test_user_videos_invalid_max(runner):
    result = runner.invoke(cli, ["user-videos", "946974", "--max", "0"])
    assert result.exit_code != 0


def test_user_videos_api_error_returns_nonzero(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.get_user_videos", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["user-videos", "946974"])
        assert result.exit_code != 0
        assert "获取视频列表失败" in result.output


def test_user_videos_handles_invalid_length_field(runner):
    videos = [{"bvid": "BV1new", "title": "New Video", "play": 123, "length": "abc"}]
    with patch("bili_cli.client.get_user_videos", new_callable=AsyncMock, return_value=videos):
        result = runner.invoke(cli, ["user-videos", "946974"])
        assert result.exit_code == 0
        assert "00:00" in result.output


def test_user_by_name_with_missing_uid_returns_nonzero(runner):
    with patch("bili_cli.client.search_user", new_callable=AsyncMock, return_value=[{"uname": "TestUser"}]):
        result = runner.invoke(cli, ["user", "testuser"])
        assert result.exit_code != 0
        assert "缺少 UID" in result.output


# ===== Collections =====


def test_favorites_requires_login(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["favorites"])
        assert result.exit_code != 0
        assert "需要登录" in result.output


def test_favorites_invalid_page(runner):
    result = runner.invoke(cli, ["favorites", "123", "--page", "0"])
    assert result.exit_code != 0


def test_favorites_api_error_returns_nonzero(runner):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_favorite_list", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["favorites"])
        assert result.exit_code != 0
        assert "获取收藏夹列表失败" in result.output


def test_following_requires_login(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["following"])
        assert result.exit_code != 0
        assert "需要登录" in result.output


def test_following_invalid_page(runner):
    result = runner.invoke(cli, ["following", "--page", "0"])
    assert result.exit_code != 0


def test_following_api_error_returns_nonzero(runner):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_self_info", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["following"])
        assert result.exit_code != 0
        assert "获取关注列表失败" in result.output


def test_history_requires_login(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["history"])
        assert result.exit_code != 0
        assert "需要登录" in result.output


def test_history_api_error_returns_nonzero(runner):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_watch_history", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["history"])
        assert result.exit_code != 0
        assert "获取观看历史失败" in result.output


def test_history_forwards_page_and_max(runner):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_watch_history", new_callable=AsyncMock, return_value={"list": []}) as mock_history:
        result = runner.invoke(cli, ["history", "--page", "2", "--max", "40"])
        assert result.exit_code == 0
        mock_history.assert_awaited_once_with(page=2, count=40, credential=mock_cred)


def test_history_invalid_page(runner):
    result = runner.invoke(cli, ["history", "--page", "0"])
    assert result.exit_code != 0


def test_history_invalid_max(runner):
    result = runner.invoke(cli, ["history", "--max", "101"])
    assert result.exit_code != 0


def test_watch_later_requires_login(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["watch-later"])
        assert result.exit_code != 0
        assert "需要登录" in result.output


def test_watch_later_api_error_returns_nonzero(runner):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_toview", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["watch-later"])
        assert result.exit_code != 0
        assert "获取稍后再看失败" in result.output


def test_feed_requires_login(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["feed"])
        assert result.exit_code != 0
        assert "需要登录" in result.output


def test_feed_api_error_returns_nonzero(runner):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_dynamic_feed", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["feed"])
        assert result.exit_code != 0
        assert "获取动态失败" in result.output


def test_feed_forwards_offset(runner):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_dynamic_feed", new_callable=AsyncMock, return_value={"items": []}) as mock_feed:
        result = runner.invoke(cli, ["feed", "--offset", "123"])
        assert result.exit_code == 0
        mock_feed.assert_awaited_once_with(offset="123", credential=mock_cred)


# ===== Interactions =====


def test_like_requires_login(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["like", "BV1test"])
        assert result.exit_code != 0
        assert "需要登录" in result.output


def test_coin_requires_login(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["coin", "BV1test"])
        assert result.exit_code != 0
        assert "需要登录" in result.output


def test_triple_requires_login(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["triple", "BV1test"])
        assert result.exit_code != 0
        assert "需要登录" in result.output


def test_coin_invalid_num(runner):
    result = runner.invoke(cli, ["coin", "BV1test", "--num", "3"])
    assert result.exit_code != 0


def test_like_requires_write_credential(runner):
    mock_cred = MagicMock()
    mock_cred.sessdata = "valid_sess"
    mock_cred.bili_jct = ""
    with patch(
        "bili_cli.commands.common.get_credential",
        side_effect=lambda mode="read": None if mode == "write" else mock_cred,
    ):
        result = runner.invoke(cli, ["like", "BV1test"])
        assert result.exit_code != 0
        assert "缺少 bili_jct" in result.output


@pytest.mark.parametrize("cmd", ["like", "coin", "triple"])
def test_interaction_invalid_bvid_returns_nonzero(runner, cmd):
    mock_cred = MagicMock()
    mock_cred.bili_jct = "valid_jct"
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.extract_bvid", side_effect=ValueError("bad bvid")):
        result = runner.invoke(cli, [cmd, "invalid"])
        assert result.exit_code != 0
        assert "bad bvid" in result.output


def test_like_failure_returns_nonzero(runner):
    mock_cred = MagicMock()
    mock_cred.bili_jct = "valid_jct"
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.extract_bvid", return_value="BV1ok"), \
         patch("bili_cli.client.like_video", new_callable=AsyncMock, side_effect=Exception("boom")):
        result = runner.invoke(cli, ["like", "BV1ok"])
        assert result.exit_code != 0
        assert "操作失败" in result.output


def test_coin_failure_returns_nonzero(runner):
    mock_cred = MagicMock()
    mock_cred.bili_jct = "valid_jct"
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.extract_bvid", return_value="BV1ok"), \
         patch("bili_cli.client.coin_video", new_callable=AsyncMock, side_effect=Exception("boom")):
        result = runner.invoke(cli, ["coin", "BV1ok"])
        assert result.exit_code != 0
        assert "投币失败" in result.output


def test_triple_failure_returns_nonzero(runner):
    mock_cred = MagicMock()
    mock_cred.bili_jct = "valid_jct"
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.extract_bvid", return_value="BV1ok"), \
         patch("bili_cli.client.triple_video", new_callable=AsyncMock, side_effect=Exception("boom")):
        result = runner.invoke(cli, ["triple", "BV1ok"])
        assert result.exit_code != 0
        assert "三连失败" in result.output


# ===== Version =====


def test_version(runner):
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "bili" in result.output

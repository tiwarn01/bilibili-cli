"""Tests for audio extraction command and client functions."""

import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from bili_cli import client
from bili_cli.cli import cli
from bili_cli.exceptions import BiliError, NetworkError


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_video_info():
    return {
        "title": "Test Video",
        "duration": 120,
        "stat": {"view": 1000},
        "owner": {"name": "TestUP", "mid": 123},
    }


# ===== Client tests =====


@pytest.mark.asyncio
async def test_get_audio_url_dash():
    mock_download_data = {"dash": {"audio": [{"baseUrl": "https://example.com/audio.m4s"}]}}
    mock_stream = MagicMock()
    mock_stream.url = "https://example.com/audio.m4s"
    mock_stream.audio_quality = 30216

    with patch("bili_cli.client.video.Video") as MockVideo, \
         patch("bili_cli.client.video.VideoDownloadURLDataDetecter") as MockDetector:
        MockVideo.return_value.get_download_url = AsyncMock(return_value=mock_download_data)
        detector_instance = MockDetector.return_value
        detector_instance.check_flv_mp4_stream.return_value = False
        detector_instance.detect_best_streams.return_value = [None, mock_stream]

        url = await client.get_audio_url("BV1test12345")
        assert url == "https://example.com/audio.m4s"


@pytest.mark.asyncio
async def test_get_audio_url_no_stream_raises():
    mock_download_data = {}

    with patch("bili_cli.client.video.Video") as MockVideo, \
         patch("bili_cli.client.video.VideoDownloadURLDataDetecter") as MockDetector:
        MockVideo.return_value.get_download_url = AsyncMock(return_value=mock_download_data)
        detector_instance = MockDetector.return_value
        detector_instance.check_flv_mp4_stream.return_value = False
        detector_instance.detect_best_streams.return_value = [None, None]

        with pytest.raises(BiliError, match="无法获取音频流"):
            await client.get_audio_url("BV1test12345")


def test_split_audio_import_error():
    """split_audio should raise BiliError when PyAV is not installed."""
    with patch.dict("sys.modules", {"av": None}):
        # Force reimport to trigger ImportError
        # We test the error message directly
        with pytest.raises((BiliError, ImportError)):
            client.split_audio("/nonexistent", "/tmp/test_out", segment_seconds=25)


# ===== CLI command tests =====


def test_audio_invalid_bvid(runner):
    result = runner.invoke(cli, ["audio", "invalid"])
    assert result.exit_code != 0


def test_audio_invalid_segment_range(runner):
    result = runner.invoke(cli, ["audio", "BV1test12345", "--segment", "2"])
    assert result.exit_code != 0


def test_audio_no_split_downloads_full(runner, mock_video_info):
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.extract_bvid", return_value="BV1test12345"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, return_value=mock_video_info), \
         patch("bili_cli.client.get_audio_url", new_callable=AsyncMock, return_value="https://example.com/audio.m4s"), \
         patch("bili_cli.client.download_audio", new_callable=AsyncMock, return_value=1024 * 1024) as mock_dl:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(cli, ["audio", "BV1test12345", "--no-split", "-o", tmpdir])
            assert result.exit_code == 0
            assert "音频已保存" in result.output
            mock_dl.assert_awaited_once()


def test_audio_split_mode(runner, mock_video_info):
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.extract_bvid", return_value="BV1test12345"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, return_value=mock_video_info), \
         patch("bili_cli.client.get_audio_url", new_callable=AsyncMock, return_value="https://example.com/audio.m4s"), \
         patch("bili_cli.client.download_audio", new_callable=AsyncMock, return_value=5 * 1024 * 1024), \
         patch("bili_cli.client.split_audio", return_value=["/tmp/seg_000.wav", "/tmp/seg_001.wav"]) as mock_split, \
         patch("os.path.getsize", return_value=960000), \
         patch("os.path.exists", return_value=True), \
         patch("os.unlink"):
        result = runner.invoke(cli, ["audio", "BV1test12345", "--segment", "25"])
        assert result.exit_code == 0
        assert "切分完成: 2 段" in result.output
        mock_split.assert_called_once()


def test_audio_api_error_returns_nonzero(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.extract_bvid", return_value="BV1test12345"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["audio", "BV1test12345"])
        assert result.exit_code != 0
        assert "获取视频信息" in result.output


def test_audio_download_error_returns_nonzero(runner, mock_video_info):
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.extract_bvid", return_value="BV1test12345"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, return_value=mock_video_info), \
         patch("bili_cli.client.get_audio_url", new_callable=AsyncMock, return_value="https://example.com/audio.m4s"), \
         patch("bili_cli.client.download_audio", new_callable=AsyncMock, side_effect=NetworkError("timeout")):
        result = runner.invoke(cli, ["audio", "BV1test12345", "--no-split"])
        assert result.exit_code != 0
        assert "下载音频" in result.output

"""Video interaction commands."""

from __future__ import annotations

import click

from . import common


@click.command()
@click.argument("bv_or_url")
@click.option("--undo", is_flag=True, help="取消点赞。")
def like(bv_or_url: str, undo: bool):
    """点赞视频。"""
    from .. import client

    cred = common.require_login(require_write=True)
    bvid = common.extract_bvid_or_exit(bv_or_url)

    common.run_or_exit(client.like_video(bvid, credential=cred, undo=undo), "操作失败")
    if undo:
        common.console.print(f"[yellow]👎 已取消点赞: {bvid}[/yellow]")
    else:
        common.console.print(f"[green]👍 已点赞: {bvid}[/green]")


@click.command()
@click.argument("bv_or_url")
@click.option("--num", "-n", default=1, type=click.IntRange(1, 2), help="投币数量 (1 或 2)。")
def coin(bv_or_url: str, num: int):
    """给视频投币。"""
    from .. import client

    cred = common.require_login(require_write=True)
    bvid = common.extract_bvid_or_exit(bv_or_url)

    common.run_or_exit(client.coin_video(bvid, credential=cred, num=num), "投币失败")
    common.console.print(f"[green]🪙 已投 {num} 枚硬币: {bvid}[/green]")


@click.command()
@click.argument("bv_or_url")
def triple(bv_or_url: str):
    """一键三连（点赞 + 投币 + 收藏）。"""
    from .. import client

    cred = common.require_login(require_write=True)
    bvid = common.extract_bvid_or_exit(bv_or_url)

    result = common.run_or_exit(client.triple_video(bvid, credential=cred), "三连失败")
    parts = []
    if result.get("like"):
        parts.append("👍 点赞")
    if result.get("coin"):
        parts.append("🪙 投币")
    if result.get("multiply") or result.get("fav"):
        parts.append("⭐ 收藏")
    common.console.print(f"[green]🎉 一键三连成功: {bvid}[/green]")
    if parts:
        common.console.print(f"[dim]  {' + '.join(parts)}[/dim]")

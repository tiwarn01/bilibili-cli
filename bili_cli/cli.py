"""CLI entry point for bilibili-cli.

Usage:
    bili login / logout / status / whoami
    bili video <BV号或URL> [--subtitle] [--ai] [--comments] [--related] [--json]
    bili user <UID或用户名>          bili user-videos <UID> [--max N]
    bili search <关键词> [--type user|video] [--json]
    bili hot / rank / feed / following / history / favorites
    bili like / coin / triple <BV号>
"""

from __future__ import annotations

import click

from . import __version__
from .commands import account, collections, common, discovery, interactions, user_search, video


# Keep helper names for backward compatibility with tests/importers.
def _format_duration(seconds: int) -> str:
    return common.format_duration(seconds)


def _format_count(n: int) -> str:
    return common.format_count(n)


@click.group()
@click.version_option(version=__version__, prog_name="bili")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
def cli(verbose: bool):
    """bili — Bilibili CLI tool 📺"""
    common.setup_logging(verbose)


# Register commands.
cli.add_command(account.login)
cli.add_command(account.logout)
cli.add_command(account.status)
cli.add_command(account.whoami)

cli.add_command(video.video)

cli.add_command(user_search.user)
cli.add_command(user_search.user_videos)
cli.add_command(user_search.search)

cli.add_command(collections.favorites)
cli.add_command(collections.following)
cli.add_command(collections.history)
cli.add_command(collections.feed)

cli.add_command(discovery.hot_cmd)
cli.add_command(discovery.rank_cmd)

cli.add_command(interactions.like)
cli.add_command(interactions.coin)
cli.add_command(interactions.triple)


if __name__ == "__main__":
    cli()

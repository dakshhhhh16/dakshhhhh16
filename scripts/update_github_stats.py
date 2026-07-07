#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


START_MARKER = "<!-- GITHUB-STATS:START -->"
END_MARKER = "<!-- GITHUB-STATS:END -->"

USERNAME = os.environ.get("GITHUB_USERNAME", "dakshhhhh16")
README_PATH = Path(os.environ.get("README_PATH", "README.md"))
API_ROOT = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
TOKEN = os.environ.get("GH_STATS_TOKEN") or os.environ.get("GITHUB_TOKEN")


def request_json(path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    url = f"{API_ROOT}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-readme-stats-updater",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API request failed with HTTP {exc.code}: {body}") from exc


def search_count(query: str) -> int:
    payload = request_json("/search/issues", {"q": query, "per_page": "1"})
    if payload.get("incomplete_results"):
        print(f"warning: GitHub returned incomplete results for query: {query}", file=sys.stderr)
    return int(payload["total_count"])


def collect_stats(username: str) -> dict[str, int]:
    user = request_json(f"/users/{urllib.parse.quote(username)}")

    return {
        "followers": int(user["followers"]),
        "public_repos": int(user["public_repos"]),
        "following": int(user["following"]),
        "public_gists": int(user["public_gists"]),
        "open_prs": search_count(f"author:{username} is:pr is:open"),
        "merged_prs": search_count(f"author:{username} is:pr is:merged"),
        "closed_prs": search_count(f"author:{username} is:pr is:closed is:unmerged"),
        "open_issues": search_count(f"author:{username} is:issue is:open"),
        "closed_issues": search_count(f"author:{username} is:issue is:closed"),
    }


def format_count(value: int) -> str:
    return f"{value:,}"


def metric_cell(label: str, value: int, width: int) -> str:
    label = html.escape(label)
    value_text = html.escape(format_count(value))
    return (
        f'    <td align="center" width="{width}"><strong>{value_text}</strong><br>'
        f"<sub>{label}</sub></td>"
    )


def render_stats(username: str, stats: dict[str, int]) -> str:
    total_issues = stats["open_issues"] + stats["closed_issues"]
    profile_url = f"https://github.com/{urllib.parse.quote(username)}"
    username_html = html.escape(username)

    overview = "\n".join(
        [
            metric_cell("Followers", stats["followers"], 180),
            metric_cell("Public Repos", stats["public_repos"], 180),
            metric_cell("Following", stats["following"], 180),
            metric_cell("Public Gists", stats["public_gists"], 180),
        ]
    )
    contribution_row_one = "\n".join(
        [
            metric_cell("Open PRs", stats["open_prs"], 240),
            metric_cell("Merged PRs", stats["merged_prs"], 240),
            metric_cell("Closed PRs", stats["closed_prs"], 240),
        ]
    )
    contribution_row_two = "\n".join(
        [
            metric_cell("Open Issues", stats["open_issues"], 240),
            metric_cell("Closed Issues", stats["closed_issues"], 240),
            metric_cell("Total Issues", total_issues, 240),
        ]
    )

    return f"""<p align="center">
  <a href="{profile_url}"><strong>@{username_html}</strong></a>
  <br>
  <sub>Open source contribution snapshot, refreshed daily.</sub>
</p>

<table align="center">
  <tr>
{overview}
  </tr>
</table>

<table align="center">
  <tr>
{contribution_row_one}
  </tr>
  <tr>
{contribution_row_two}
  </tr>
</table>

<p align="center">
  <sub>Private repository names are not displayed.</sub>
</p>"""


def update_readme(readme: str, stats_block: str) -> str:
    if START_MARKER not in readme or END_MARKER not in readme:
        raise ValueError("README is missing the GitHub stats markers.")

    before, rest = readme.split(START_MARKER, 1)
    _, after = rest.split(END_MARKER, 1)
    return f"{before}{START_MARKER}\n{stats_block.rstrip()}\n{END_MARKER}{after}"


def main() -> int:
    stats = collect_stats(USERNAME)
    readme = README_PATH.read_text(encoding="utf-8")
    updated_readme = update_readme(readme, render_stats(USERNAME, stats))

    if updated_readme != readme:
        README_PATH.write_text(updated_readme, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

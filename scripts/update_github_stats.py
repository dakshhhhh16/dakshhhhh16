#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import sys
import time
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
TOKEN = os.environ.get("GH_STATS_TOKEN")
MAX_ATTEMPTS = 3
RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}


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
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code not in RETRYABLE_HTTP_CODES or attempt == MAX_ATTEMPTS:
                raise RuntimeError(
                    f"GitHub API request failed with HTTP {exc.code}: {body}"
                ) from exc
        except urllib.error.URLError as exc:
            if attempt == MAX_ATTEMPTS:
                raise RuntimeError(f"GitHub API request failed: {exc.reason}") from exc

        delay = 2 ** (attempt - 1)
        print(
            f"warning: GitHub API request failed; retrying in {delay} second(s)",
            file=sys.stderr,
        )
        time.sleep(delay)

    raise AssertionError("unreachable")


def search_count(query: str) -> int:
    payload = request_json("/search/issues", {"q": query, "per_page": "1"})
    if payload.get("incomplete_results"):
        print(f"warning: GitHub returned incomplete results for query: {query}", file=sys.stderr)
    return int(payload["total_count"])


def collect_stats(username: str) -> dict[str, int]:
    return {
        "reviewed_prs": search_count(f"reviewed-by:{username} is:pr"),
        "open_prs": search_count(f"author:{username} is:pr is:open"),
        "merged_prs": search_count(f"author:{username} is:pr is:merged"),
        "open_issues": search_count(f"author:{username} is:issue is:open"),
        "closed_issues": search_count(f"author:{username} is:issue is:closed"),
    }


def format_count(value: int) -> str:
    return f"{value:,}"


def search_url(query: str, result_type: str) -> str:
    params = urllib.parse.urlencode({"q": query, "type": result_type})
    return f"https://github.com/search?{params}"


def metric_cell(label: str, value: int, width: int, url: str) -> str:
    label = html.escape(label)
    value_text = html.escape(format_count(value))
    url = html.escape(url, quote=True)
    return (
        f'    <td align="center" width="{width}"><a href="{url}">'
        f"<strong>{value_text}</strong><br><sub>{label}</sub></a></td>"
    )


def render_stats(username: str, stats: dict[str, int]) -> str:
    total_issues = stats["open_issues"] + stats["closed_issues"]
    profile_url = f"https://github.com/{urllib.parse.quote(username)}"
    username_html = html.escape(username)

    reviewed_prs_query = f"reviewed-by:{username} is:pr"
    open_prs_query = f"author:{username} is:pr is:open"
    merged_prs_query = f"author:{username} is:pr is:merged"
    open_issues_query = f"author:{username} is:issue is:open"
    closed_issues_query = f"author:{username} is:issue is:closed"
    total_issues_query = f"author:{username} is:issue"

    contribution_row = "\n".join(
        [
            metric_cell(
                "👀 Reviewed PRs",
                stats["reviewed_prs"],
                200,
                search_url(reviewed_prs_query, "pullrequests"),
            ),
            metric_cell(
                "🟢 Open PRs",
                stats["open_prs"],
                200,
                search_url(open_prs_query, "pullrequests"),
            ),
            metric_cell(
                "✅ Merged PRs",
                stats["merged_prs"],
                200,
                search_url(merged_prs_query, "pullrequests"),
            ),
        ]
    )
    issue_row = "\n".join(
        [
            metric_cell(
                "🟡 Open Issues",
                stats["open_issues"],
                200,
                search_url(open_issues_query, "issues"),
            ),
            metric_cell(
                "✅ Closed Issues",
                stats["closed_issues"],
                200,
                search_url(closed_issues_query, "issues"),
            ),
            metric_cell(
                "📌 Total Issues",
                total_issues,
                200,
                search_url(total_issues_query, "issues"),
            ),
        ]
    )

    return f"""<p align="left">
  <a href="{profile_url}"><strong>@{username_html}</strong></a>
  <br>
  <sub>Open source contribution snapshot, refreshed daily.</sub>
</p>

<table align="center">
  <tr>
{contribution_row}
  </tr>
</table>

<table align="center">
  <tr>
{issue_row}
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
    if not TOKEN:
        print(
            "error: GH_STATS_TOKEN is required for cross-repository contribution stats.",
            file=sys.stderr,
        )
        return 2

    stats = collect_stats(USERNAME)
    readme = README_PATH.read_text(encoding="utf-8")
    updated_readme = update_readme(readme, render_stats(USERNAME, stats))

    if updated_readme != readme:
        README_PATH.write_text(updated_readme, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

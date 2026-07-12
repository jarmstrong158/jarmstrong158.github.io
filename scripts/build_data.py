#!/usr/bin/env python3
"""Regenerate data.json for the hub from live GitHub data + the curated meta.

Runs locally (GITHUB_TOKEN=$(gh auth token) python scripts/build_data.py) and in
the daily GitHub Action (GITHUB_TOKEN is provided automatically). Stdlib only.
"""
import collections
import datetime as dt
import json
import os
import pathlib
import urllib.request

USER = "jarmstrong158"
ROOT = pathlib.Path(__file__).resolve().parent.parent
META = json.loads((ROOT / "data" / "projects.meta.json").read_text(encoding="utf-8"))
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
if not TOKEN:
    raise SystemExit("Set GITHUB_TOKEN (locally: GITHUB_TOKEN=$(gh auth token))")


def _get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": USER,
                                               "Accept": "application/vnd.github+json",
                                               "Authorization": f"Bearer {TOKEN}",
                                               **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _graphql(query):
    body = json.dumps({"query": query}).encode("utf-8")
    req = urllib.request.Request("https://api.github.com/graphql", data=body,
                                 headers={"User-Agent": USER,
                                          "Authorization": f"Bearer {TOKEN}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def repos():
    out, page = {}, 1
    while True:
        batch = _get(f"https://api.github.com/users/{USER}/repos"
                     f"?per_page=100&page={page}&sort=created")
        if not batch:
            break
        for r in batch:
            if not r.get("fork"):
                out[r["name"]] = r
        page += 1
    return out


def contributions():
    q = ('{ user(login:"%s"){ contributionsCollection{ contributionCalendar{'
         ' totalContributions weeks{ contributionDays{ date contributionCount }}}}}}' % USER)
    cal = _graphql(q)["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    m = collections.OrderedDict()
    weeks, maxc, start = [], 0, None
    for w in cal["weeks"]:
        col = []
        for d in w["contributionDays"]:
            if start is None:
                start = d["date"]
            m[d["date"][:7]] = m.get(d["date"][:7], 0) + d["contributionCount"]
            col.append(d["contributionCount"])
            maxc = max(maxc, d["contributionCount"])
        weeks.append(col)
    active = [(k, v) for k, v in m.items()]
    # start at the first month that BEGINS sustained activity (this month and the
    # next both non-zero) so a lone early outlier + dormant gap isn't shown.
    first = 0
    for i in range(len(active) - 1):
        if active[i][1] > 0 and active[i + 1][1] > 0:
            first = i
            break
    months = [{"m": k, "n": v} for k, v in active[first:]]
    heatmap = {"start": start, "max": maxc, "weeks": weeks}
    return months, cal["totalContributions"], heatmap


def registry_count():
    url = ("https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github."
           + USER)
    for _ in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
            names = {(x.get("server") or {}).get("name", "") for x in data.get("servers", [])}
            names = {n for n in names if n.startswith(f"io.github.{USER}/")}
            if names:
                return len(names)
        except Exception:
            pass
    return None


def main():
    live = repos()
    projects = []
    for name, meta in META["projects"].items():
        r = live.get(name)
        if not r:
            continue
        projects.append({
            "name": name,
            "thread": meta.get("thread", "mcp"),
            "blurb": meta.get("blurb", r.get("description") or ""),
            "metric": meta.get("metric", ""),
            "featured": bool(meta.get("featured")),
            "date": r["created_at"][:10],
            "updated": r["pushed_at"][:10],
            "language": r.get("language"),
            "stars": r.get("stargazers_count", 0),
            "url": r["html_url"],
        })
    projects.sort(key=lambda p: p["date"])

    months, total_year, heatmap = contributions()
    first_repo = min((r["created_at"][:10] for r in live.values()), default=None)
    span_months = None
    if first_repo:
        f = dt.date.fromisoformat(first_repo)
        today = dt.date.today()
        span_months = (today.year - f.year) * 12 + (today.month - f.month) + 1

    reg = registry_count()
    stats = [
        {"label": "public repositories", "value": len(live)},
        {"label": "contributions (last year)", "value": total_year},
        {"label": "months, first repo to production stack", "value": span_months},
    ]
    if reg:
        stats.append({"label": "MCP servers on the official registry", "value": reg})

    data = {
        "generated": dt.date.today().isoformat(),
        "threads": META["threads"],
        "projects": projects,
        "cadence": {"unit": "GitHub contributions", "months": months,
                    "total_year": total_year},
        "heatmap": heatmap,
        "stats": stats,
    }
    (ROOT / "data.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"wrote data.json: {len(projects)} projects, {len(months)} months, "
          f"registry={reg}, span={span_months}mo")


if __name__ == "__main__":
    main()

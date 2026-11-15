#!/usr/bin/env python3
"""
Africa policy monitor
=====================

Watches a register of primary institutional sources (African Union, Africa CDC,
ECOWAS/WAHO, WHO) for newly published items, classifies each against DTH-Lab's
four workstreams, and writes a dated signal note ranking what is worth a human
reading.

What this does and does not do
------------------------------
It catches what these institutions *publish*, quickly and consistently.

It does not catch what they do not publish. AU Specialised Technical Committees
and the Permanent Representatives' Committee do not issue open calls for written
input; a framework is usually drafted before any public trace of it exists. This
tool therefore shortens the gap between publication and response. Closing the
gap before publication is relationship work, not scraping, and the two are meant
to run together.

Usage
-----
    python monitor.py                      # live run
    python monitor.py --dry-run            # fetch, classify, print, write nothing
    python monitor.py --offline tests/fixtures   # run against saved HTML
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import sys
import time
import urllib.parse

import requests
import yaml
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).parent
STATE_PATH = ROOT / "state" / "seen.json"
NOTES_DIR = ROOT / "signal-notes"

# Link text shorter than this is almost always navigation furniture.
MIN_TITLE_WORDS = 4
MAX_ITEMS_PER_SOURCE = 40


# --------------------------------------------------------------------------
# config + state
# --------------------------------------------------------------------------

def load_yaml(name: str) -> dict:
    with open(ROOT / name, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_state() -> dict:
    if STATE_PATH.exists():
        with open(STATE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    return {"seen": {}, "http": {}}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
        fh.write("\n")


# --------------------------------------------------------------------------
# fetching
# --------------------------------------------------------------------------

def fetch(source: dict, defaults: dict, state: dict) -> str | None:
    """Conditional GET. Returns HTML, or None if unchanged or unreachable."""
    headers = {"User-Agent": defaults["user_agent"]}
    cached = state["http"].get(source["id"], {})
    if cached.get("etag"):
        headers["If-None-Match"] = cached["etag"]
    if cached.get("last_modified"):
        headers["If-Modified-Since"] = cached["last_modified"]

    for attempt in range(3):
        try:
            resp = requests.get(
                source["url"],
                headers=headers,
                timeout=defaults["timeout_seconds"],
            )
        except requests.RequestException as exc:
            if attempt == 2:
                print(f"  ! unreachable: {exc.__class__.__name__}", file=sys.stderr)
                return None
            time.sleep(2 ** attempt)
            continue

        if resp.status_code == 304:
            print("  · unchanged (304)")
            return None
        if resp.status_code >= 400:
            print(f"  ! HTTP {resp.status_code}", file=sys.stderr)
            return None

        state["http"][source["id"]] = {
            "etag": resp.headers.get("ETag"),
            "last_modified": resp.headers.get("Last-Modified"),
            "checked": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        }
        return resp.text
    return None


def extract_items(html: str, base_url: str) -> list[dict]:
    """Pull candidate (title, url) pairs out of an index page.

    Deliberately generic: these sites change templates without notice, and a
    monitor that breaks silently on a CSS change is worse than no monitor.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()

    items, seen_urls = [], set()
    for anchor in soup.find_all("a", href=True):
        title = " ".join(anchor.get_text(" ", strip=True).split())
        if len(title.split()) < MIN_TITLE_WORDS:
            continue
        url = urllib.parse.urljoin(base_url, anchor["href"])
        url, _ = urllib.parse.urldefrag(url)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        items.append({"title": title, "url": url})
        if len(items) >= MAX_ITEMS_PER_SOURCE:
            break
    return items


# --------------------------------------------------------------------------
# classification
# --------------------------------------------------------------------------

def classify(title: str, taxonomy: dict) -> dict:
    haystack = f" {title.lower()} "
    hits = {}
    for key, spec in taxonomy["workstreams"].items():
        matched = [t for t in spec["terms"] if t in haystack]
        if matched:
            hits[key] = {"label": spec["label"], "terms": matched}

    opportunity = [s for s in taxonomy["opportunity_signals"] if s in haystack]
    retrospective = [s for s in taxonomy["retrospective_signals"] if s in haystack]
    return {
        "workstreams": hits,
        "opportunity": opportunity,
        "retrospective": retrospective,
    }


def score(item: dict, source: dict, tags: dict) -> int:
    """Higher means a human should look sooner."""
    tier_weight = {1: 4, 2: 2, 3: 1}.get(source.get("tier", 3), 1)
    value = tier_weight
    value += 2 * len(tags["workstreams"])
    if tags["opportunity"]:
        # A dated, still-open window beats a richly-tagged retrospective notice.
        value += 4 if len(tags["opportunity"]) >= 2 else 3
    value -= 1 * bool(tags["retrospective"])
    return value


def priority(value: int) -> str:
    if value >= 8:
        return "HIGH"
    if value >= 5:
        return "MEDIUM"
    return "LOW"


def fingerprint(item: dict) -> str:
    key = re.sub(r"\W+", "", item["title"].lower()) + "|" + item["url"]
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------

def write_note(findings: list[dict], today: str) -> pathlib.Path:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    path = NOTES_DIR / f"{today}-signal-note.md"

    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    findings.sort(key=lambda f: (order[f["priority"]], -f["score"]))

    lines = [
        f"# Africa policy signal note — {today}",
        "",
        f"{len(findings)} new item(s) across the source register. "
        "Ranked by how close the source sits to a decision, how many DTH-Lab "
        "workstreams it touches, and whether the wording suggests a window that "
        "is still open.",
        "",
    ]

    if not findings:
        lines += ["No new items. The register was reachable and nothing changed.", ""]

    for level in ("HIGH", "MEDIUM", "LOW"):
        bucket = [f for f in findings if f["priority"] == level]
        if not bucket:
            continue
        lines += [f"## {level}", ""]
        for f in bucket:
            lines.append(f"**{f['title']}**  ")
            lines.append(f"{f['body']} — {f['source']}  ")
            if f["workstreams"]:
                lines.append("Workstreams: " + ", ".join(f["workstreams"]) + "  ")
            if f["opportunity"]:
                lines.append("Possible open window: " + ", ".join(f["opportunity"]) + "  ")
            lines.append(f"<{f['url']}>")
            lines.append("")

    lines += [
        "---",
        "",
        "Flagged automatically. Each item still needs a human to decide whether "
        "it is a real opportunity, which institutional step comes next, and "
        "whether DTH-Lab has a legitimate route in.",
        "",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="write nothing")
    parser.add_argument("--offline", metavar="DIR", help="read saved HTML instead of fetching")
    args = parser.parse_args()

    config = load_yaml("sources.yml")
    taxonomy = load_yaml("taxonomy.yml")
    defaults = config["defaults"]
    state = load_state()

    today = dt.date.today().isoformat()
    findings: list[dict] = []

    for source in config["sources"]:
        print(f"→ {source['body']}: {source['name']}")

        if args.offline:
            fixture = pathlib.Path(args.offline) / f"{source['id']}.html"
            html = fixture.read_text(encoding="utf-8") if fixture.exists() else None
            if html is None:
                print("  · no fixture, skipping")
                continue
        else:
            html = fetch(source, defaults, state)
            time.sleep(defaults["delay_seconds"])

        if not html:
            continue

        new_count = 0
        for item in extract_items(html, source["url"]):
            fp = fingerprint(item)
            if fp in state["seen"]:
                continue
            state["seen"][fp] = {"first_seen": today, "url": item["url"]}

            tags = classify(item["title"], taxonomy)
            if not tags["workstreams"]:
                continue  # irrelevant to DTH-Lab's mandate

            value = score(item, source, tags)
            findings.append({
                "title": item["title"],
                "url": item["url"],
                "body": source["body"],
                "source": source["name"],
                "workstreams": [w["label"] for w in tags["workstreams"].values()],
                "opportunity": tags["opportunity"],
                "score": value,
                "priority": priority(value),
            })
            new_count += 1

        print(f"  · {new_count} relevant new item(s)")

    if args.dry_run:
        print(json.dumps(findings, indent=2))
        return 0

    note = write_note(findings, today)
    save_state(state)
    print(f"\nWrote {note.relative_to(ROOT)} ({len(findings)} item(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

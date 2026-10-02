#!/usr/bin/env python3
"""Seed clearly labelled synthetic news into a local app-data cache.

This is for local UI and Agent testing only. It never claims the records are
live news and it does not contact any network source.
"""
import argparse
import json
from pathlib import Path


DEMO_RETRIEVED_AT = 1790899200  # 2026-10-01T00:00:00Z

ROWS = {
    "hn": [
        {
            "title": "DEMO CACHE: A fictional open-source agent workflow update",
            "link": "https://example.invalid/demo/agent-workflow",
            "source": "Hacker News",
            "summary": "DEMO DATA ONLY: A synthetic report about an AI agent workflow, useful for testing Agent evidence and uncertainty display.",
            "published": 1790841600,
            "kind": "hn_submission",
            "timestamp_kind": "submitted",
            "category": "tech",
            "language": "en",
        },
        {
            "title": "DEMO CACHE: Fictional local-first research tool released",
            "link": "https://example.invalid/demo/local-research-tool",
            "source": "Hacker News",
            "summary": "DEMO DATA ONLY: Synthetic summary with a concrete product change for testing a relevant suggestion.",
            "published": 1790755200,
            "kind": "hn_submission",
            "timestamp_kind": "submitted",
            "category": "tech",
            "language": "en",
        },
    ],
    "mit": [
        {
            "title": "DEMO CACHE: Fictional study explores reliable agent evaluation",
            "link": "https://example.invalid/demo/agent-evaluation",
            "source": "MIT Research",
            "summary": "DEMO DATA ONLY: Synthetic research summary for testing evidence-backed analysis and insufficient-context handling.",
            "published": 1790668800,
            "kind": "rss_summary",
            "timestamp_kind": "published",
            "category": "ai",
            "language": "en",
        },
        {
            "title": "DEMO CACHE: Fictional benchmark reports mixed results",
            "link": "https://example.invalid/demo/mixed-results",
            "source": "MIT Research",
            "summary": "DEMO DATA ONLY: Synthetic unrelated result for testing a no-change outcome.",
            "published": 1790582400,
            "kind": "rss_summary",
            "timestamp_kind": "published",
            "category": "ai",
            "language": "en",
        },
    ],
    "bbc": [
        {
            "title": "DEMO CACHE: Fictional city announces a public technology forum",
            "link": "https://example.invalid/demo/public-forum",
            "source": "BBC World",
            "summary": "DEMO DATA ONLY: Synthetic world-news item for testing category filtering and detail navigation.",
            "published": 1790496000,
            "kind": "rss_summary",
            "timestamp_kind": "published",
            "category": "world",
            "language": "en",
        },
        {
            "title": "DEMO CACHE: Fictional transport notice has no tracked impact",
            "link": "https://example.invalid/demo/transport-notice",
            "source": "BBC World",
            "summary": "DEMO DATA ONLY: Synthetic unrelated item for testing no-change and search states.",
            "published": None,
            "kind": "rss_summary",
            "timestamp_kind": "published",
            "category": "world",
            "language": "en",
        },
    ],
}


def make_row(source_id, item):
    url = item["link"]
    return {
        "news_id": url,
        "title": item["title"],
        "source": item["source"],
        "source_id": source_id,
        "source_url": url,
        "feed_url": "https://example.invalid/demo/" + source_id,
        "category": item["category"],
        "language": item["language"],
        "summary": item["summary"],
        "published_at": item["published"],
        "retrieved_at": DEMO_RETRIEVED_AT,
        "evidence_kind": item["kind"],
        "timestamp_kind": item["timestamp_kind"],
        "demo_data": True,
        "references": [{
            "source_id": source_id,
            "source": item["source"],
            "source_url": url,
            "feed_url": "https://example.invalid/demo/" + source_id,
        }],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True,
                        help="App storage directory, e.g. .local-state/windows-preview/dev.cfaw.news")
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    for source_id, items in ROWS.items():
        payload = {
            "schema_version": 1,
            "source_id": source_id,
            "retrieved_at": DEMO_RETRIEVED_AT,
            "items": [make_row(source_id, item) for item in items],
        }
        path = args.data_dir / ("news_cache_v1_" + source_id + ".json")
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if not existing.get("items") or not all(item.get("demo_data") is True for item in existing["items"]):
                raise SystemExit(f"Refusing to replace non-demo cache: {path}")
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(path)


if __name__ == "__main__":
    main()

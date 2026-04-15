"""Scheduled interaction quality review and reporting."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

import config
from memory.episodic import episodic


TRAINING_DATA_DIR = config.DATA_DIR / "training"
REPORTS_DIR = config.DATA_DIR / "identity" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _load_entries(since: datetime | None = None) -> list[dict]:
    entries: list[dict] = []
    for batch_file in sorted(TRAINING_DATA_DIR.glob("batch_*.json")):
        try:
            data = json.loads(batch_file.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                continue
            for row in data:
                ts_text = str(row.get("timestamp", ""))
                if since and ts_text:
                    try:
                        ts = datetime.fromisoformat(ts_text)
                        if ts < since:
                            continue
                    except Exception:
                        pass
                entries.append(row)
        except Exception as e:
            logger.warning(f"[Review] Failed reading {batch_file}: {e}")
    return entries


def _score(entries: list[dict]) -> dict:
    if not entries:
        return {"count": 0, "avg": 0.0, "good": 0, "bad": 0}

    qualities = [float(e.get("quality", 0.5)) for e in entries]
    good = sum(1 for q in qualities if q >= 0.7)
    bad = sum(1 for q in qualities if q <= 0.3)
    avg = sum(qualities) / len(qualities)
    return {"count": len(qualities), "avg": avg, "good": good, "bad": bad}


async def run_nightly_review() -> str:
    since = datetime.now() - timedelta(days=1)
    entries = _load_entries(since)
    stats = _score(entries)
    summary = (
        f"Nightly quality review: {stats['count']} samples, avg={stats['avg']:.2f}, "
        f"good={stats['good']}, bad={stats['bad']}"
    )
    episodic.store_fact(summary, category="self_review", importance=5)
    logger.info(f"[Review] {summary}")
    return summary


async def run_weekly_report() -> str:
    since = datetime.now() - timedelta(days=7)
    entries = _load_entries(since)
    stats = _score(entries)

    report_path = REPORTS_DIR / f"weekly_{datetime.now().strftime('%Y%m%d')}.md"
    lines = [
        "# AERIS Weekly Quality Report",
        "",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "## Metrics",
        f"- Samples: {stats['count']}",
        f"- Average quality: {stats['avg']:.2f}",
        f"- Good responses (>=0.70): {stats['good']}",
        f"- Bad responses (<=0.30): {stats['bad']}",
        "",
        "## Notes",
        "- This report is generated from collected interaction batches.",
        "- Use this to tune prompting, routing, and fine-tune cadence.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary = (
        f"Weekly quality report saved: {report_path} "
        f"(samples={stats['count']}, avg={stats['avg']:.2f})"
    )
    episodic.store_fact(summary, category="self_review", importance=6)
    logger.info(f"[Review] {summary}")
    return summary

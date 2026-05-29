#!/usr/bin/env python3
"""Parse paywallpro/paywall-gallery into data.json for the dashboard."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_URL = "https://github.com/paywallpro/paywall-gallery.git"
REPO_DIR = Path("paywall-gallery")
SKIP_FILES = {"index.md", "index.zh-CN.md", "_template.md"}
HISTORY_DIR = Path("history")
CHANGES_FILE = Path("changes.json")

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
MRR_RE = re.compile(r"\$?\s*([\d.]+)\s*([KMB]?)", re.IGNORECASE)
PRICE_RE = re.compile(r"\$\s*([\d.]+)")
ARCHIVE_NAME_RE = re.compile(r"^data-(\d{4})(\d{2})(\d{2})$")


def clone_repo() -> None:
    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    print(f"Cloning {REPO_URL} ...", flush=True)
    subprocess.run(
        ["git", "clone", "--depth=1", REPO_URL, str(REPO_DIR)],
        check=True,
    )


def parse_mrr(raw: object) -> float:
    """`$55.84M` -> 55.84, `$459.84K` -> 0.45984, empty -> 0."""
    if not raw:
        return 0.0
    m = MRR_RE.search(str(raw))
    if not m:
        return 0.0
    value = float(m.group(1))
    unit = m.group(2).upper()
    if unit == "K":
        return round(value / 1000.0, 5)
    if unit == "B":
        return round(value * 1000.0, 5)
    return value  # M or no unit -> treat as millions


def parse_monthly_price(offers: object) -> float:
    """Pull the first $ amount from the offer whose period is 'month'."""
    if not isinstance(offers, list):
        return 0.0
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        period = str(offer.get("period", "")).lower()
        if period != "month":
            continue
        prices = offer.get("prices") or []
        for p in prices:
            m = PRICE_RE.search(str(p))
            if m:
                return float(m.group(1))
    return 0.0


def parse_rating(raw: object) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def extract_frontmatter(text: str) -> dict | None:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        print(f"  YAML error: {e}", flush=True)
        return None


def build_app_entry(meta: dict, filename: str) -> dict | None:
    app_name = (meta.get("app_name") or "").strip()
    app_id = meta.get("app_id") or 0
    if not app_name or not app_id:
        return None  # template or empty placeholder

    paywall_type = (meta.get("paywall_type") or "").strip()
    offers = meta.get("offers") or []
    mrr_raw = meta.get("mrr") or ""
    pt_lower = paywall_type.lower()
    has_free_trial = "free trial" in pt_lower and "no free trial" not in pt_lower

    return {
        "app_name": app_name,
        "app_id": app_id,
        "developer": (meta.get("developer") or "").strip(),
        "category": (meta.get("category") or "Uncategorized").strip() or "Uncategorized",
        "paywall_type": paywall_type or "Unknown",
        "pricing_model": (meta.get("pricing_model") or "").strip(),
        "mrr": mrr_raw,
        "mrr_num": parse_mrr(mrr_raw),
        "rating": parse_rating(meta.get("rating")),
        "versions_count": meta.get("versions_count") or 0,
        "offers": offers,
        "screenshots_count": meta.get("screenshots_count") or 0,
        "onboarding_flows_count": meta.get("onboarding_flows_count") or 0,
        "app_detail_url": (meta.get("app_detail_url") or "").strip(),
        "has_free_trial": has_free_trial,
        "monthly_price_num": parse_monthly_price(offers),
        "source_file": filename,
        "github_url": f"https://github.com/paywallpro/paywall-gallery/blob/main/apps/{filename}",
    }


def _slim(app: dict) -> dict:
    """Subset of fields used in change lists."""
    return {
        "app_name": app.get("app_name", ""),
        "app_id": app.get("app_id", 0),
        "category": app.get("category", ""),
        "mrr_num": app.get("mrr_num", 0.0),
        "monthly_price_num": app.get("monthly_price_num", 0.0),
        "paywall_type": app.get("paywall_type", ""),
    }


def find_previous_archive(today_str: str) -> Path | None:
    """Most recent data-YYYYMMDD.json that is not today's."""
    if not HISTORY_DIR.is_dir():
        return None
    candidates = []
    for p in HISTORY_DIR.glob("data-*.json"):
        m = ARCHIVE_NAME_RE.match(p.stem)
        if not m:
            continue
        date_str = m.group(1) + m.group(2) + m.group(3)
        if date_str == today_str:
            continue
        candidates.append((date_str, p))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def detect_changes(current: list[dict], previous: list[dict]) -> dict:
    """Diff two app lists keyed by app_id; return detail lists ready to dump."""
    cur_by_id = {a["app_id"]: a for a in current if a.get("app_id")}
    prev_by_id = {a["app_id"]: a for a in previous if a.get("app_id")}

    cur_ids = set(cur_by_id)
    prev_ids = set(prev_by_id)

    added = [_slim(cur_by_id[i]) for i in cur_ids - prev_ids]
    removed = [_slim(prev_by_id[i]) for i in prev_ids - cur_ids]
    added.sort(key=lambda a: a["mrr_num"], reverse=True)
    removed.sort(key=lambda a: a["mrr_num"], reverse=True)

    pricing_changes: list[dict] = []
    paywall_changes: list[dict] = []
    for aid in cur_ids & prev_ids:
        cur, prev = cur_by_id[aid], prev_by_id[aid]

        old_p = prev.get("monthly_price_num") or 0
        new_p = cur.get("monthly_price_num") or 0
        if old_p > 0 and new_p > 0 and old_p != new_p:
            change_pct = round((new_p - old_p) / old_p * 100, 1)
            pricing_changes.append({
                "app_name": cur.get("app_name", ""),
                "app_id": aid,
                "category": cur.get("category", ""),
                "old_price": old_p,
                "new_price": new_p,
                "change_pct": change_pct,
                "direction": "up" if new_p > old_p else "down",
            })

        old_t = (prev.get("paywall_type") or "").strip()
        new_t = (cur.get("paywall_type") or "").strip()
        if old_t and new_t and old_t != new_t:
            paywall_changes.append({
                "app_name": cur.get("app_name", ""),
                "app_id": aid,
                "category": cur.get("category", ""),
                "old_type": old_t,
                "new_type": new_t,
            })

    pricing_changes.sort(key=lambda c: abs(c["change_pct"]), reverse=True)
    paywall_changes.sort(key=lambda c: c["app_name"].lower())

    return {
        "added_apps": added,
        "removed_apps": removed,
        "pricing_changes": pricing_changes,
        "paywall_type_changes": paywall_changes,
    }


def main() -> int:
    clone_repo()
    apps_dir = REPO_DIR / "apps"
    if not apps_dir.is_dir():
        print(f"ERROR: {apps_dir} not found", file=sys.stderr)
        return 1

    apps: list[dict] = []
    skipped = 0
    for md_path in sorted(apps_dir.glob("*.md")):
        if md_path.name in SKIP_FILES:
            continue
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError as e:
            print(f"SKIP {md_path.name}: read failed ({e})", flush=True)
            skipped += 1
            continue

        meta = extract_frontmatter(text)
        if meta is None:
            print(f"SKIP {md_path.name}: no/invalid frontmatter", flush=True)
            skipped += 1
            continue

        try:
            entry = build_app_entry(meta, md_path.name)
        except Exception as e:  # noqa: BLE001
            print(f"SKIP {md_path.name}: build failed ({e})", flush=True)
            skipped += 1
            continue

        if entry is None:
            skipped += 1
            continue
        apps.append(entry)

    apps.sort(key=lambda a: a["mrr_num"], reverse=True)

    payload = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(apps),
        "apps": apps,
    }

    out_path = Path("data.json")
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
    out_path.write_text(payload_json, encoding="utf-8")
    print(
        f"Wrote {out_path} ({len(apps)} apps, {skipped} skipped)",
        flush=True,
    )

    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    HISTORY_DIR.mkdir(exist_ok=True)
    archive_path = HISTORY_DIR / f"data-{today_str}.json"
    archive_path.write_text(payload_json, encoding="utf-8")
    print(f"Wrote archive {archive_path}", flush=True)

    prev_archive = find_previous_archive(today_str)
    if prev_archive is None:
        print("首次运行，无对比基准", flush=True)
        if CHANGES_FILE.exists():
            CHANGES_FILE.unlink()
            print(f"Removed stale {CHANGES_FILE}", flush=True)
        return 0

    try:
        prev_payload = json.loads(prev_archive.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"WARN: failed to read previous archive {prev_archive}: {e}", flush=True)
        return 0

    diff = detect_changes(apps, prev_payload.get("apps", []))
    m = ARCHIVE_NAME_RE.match(prev_archive.stem)
    prev_iso = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    changes_payload = {
        "current_date": today_iso,
        "previous_date": prev_iso,
        "summary": {
            "added": len(diff["added_apps"]),
            "removed": len(diff["removed_apps"]),
            "pricing_changed": len(diff["pricing_changes"]),
            "paywall_type_changed": len(diff["paywall_type_changes"]),
        },
        "added_apps": diff["added_apps"],
        "removed_apps": diff["removed_apps"],
        "pricing_changes": diff["pricing_changes"],
        "paywall_type_changes": diff["paywall_type_changes"],
    }
    CHANGES_FILE.write_text(
        json.dumps(changes_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    s = changes_payload["summary"]
    print(
        f"Wrote {CHANGES_FILE} (vs {prev_iso}): "
        f"+{s['added']} -{s['removed']} price {s['pricing_changed']} "
        f"paywall {s['paywall_type_changed']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sonarr-season-cleanup
---------------------
Automatically unmonitors and deletes older seasons of TV shows tagged
with "keep-latest" in Sonarr, keeping only the most recent season.

Configuration (environment variables):
  SONARR_URL        Base URL of your Sonarr instance (default: http://localhost:8989)
  SONARR_API_KEY    Your Sonarr API key (required)
  KEEP_LATEST_TAG   Tag name to look for in Sonarr (default: keep-latest)
  LOG_FILE          Path to log file (default: /tmp/sonarr_cleanup.log)

Usage:
  python3 sonarr_cleanup.py [--dry-run]
"""

import requests, shutil, argparse, logging, os, sys
from datetime import datetime

SONARR_URL      = os.environ.get("SONARR_URL", "http://localhost:8989")
SONARR_API_KEY  = os.environ.get("SONARR_API_KEY", "")
KEEP_LATEST_TAG = os.environ.get("KEEP_LATEST_TAG", "keep-latest")
LOG_FILE        = os.environ.get("LOG_FILE", "/tmp/sonarr_cleanup.log")

if not SONARR_API_KEY:
    print("ERROR: SONARR_API_KEY environment variable is required")
    sys.exit(1)

def setup_logging(dry_run):
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt,
        handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)])
    if dry_run:
        logging.info("=== DRY RUN MODE - no changes will be made ===")

def api_get(endpoint):
    r = requests.get(SONARR_URL + "/api/v3/" + endpoint,
        headers={"X-Api-Key": SONARR_API_KEY}, timeout=30)
    r.raise_for_status()
    return r.json()

def api_put(endpoint, payload):
    r = requests.put(SONARR_URL + "/api/v3/" + endpoint, json=payload,
        headers={"X-Api-Key": SONARR_API_KEY}, timeout=30)
    r.raise_for_status()
    return r.json()

def get_tag_id(tag_name):
    for tag in api_get("tag"):
        if tag["label"].lower() == tag_name.lower():
            return tag["id"]
    return None

def get_series_with_tag(tag_id):
    return [s for s in api_get("series") if tag_id in s.get("tags", [])]

def unmonitor_season(series, season_number, dry_run):
    title = series["title"]
    sid   = series["id"]
    for season in series["seasons"]:
        if season["seasonNumber"] == season_number:
            if not season["monitored"]:
                logging.info("  S%02d already unmonitored - skipping" % season_number)
                return
            season["monitored"] = False
    if dry_run:
        logging.info("  [DRY RUN] Would unmonitor %s S%02d" % (title, season_number))
        return
    logging.info("  Unmonitoring %s S%02d" % (title, season_number))
    api_put("series/%d" % sid, series)

def delete_season_files(title, series_path, season_number, dry_run):
    candidates = [
        os.path.join(series_path, "Season %d" % season_number),
        os.path.join(series_path, "Season %02d" % season_number),
    ]
    for season_path in candidates:
        if os.path.isdir(season_path):
            size_gb = sum(os.path.getsize(os.path.join(dp, f))
                for dp, _, files in os.walk(season_path) for f in files) / (1024**3)
            if dry_run:
                logging.info("  [DRY RUN] Would delete %s (%.2f GB)" % (season_path, size_gb))
            else:
                logging.info("  Deleting %s (%.2f GB)" % (season_path, size_gb))
                shutil.rmtree(season_path)
            return
    logging.warning("  Season folder not found for %s S%02d in %s" % (title, season_number, series_path))

def rescan_series(series_id, title, dry_run):
    if dry_run:
        logging.info("  [DRY RUN] Would trigger rescan for %s" % title)
        return
    logging.info("  Triggering Sonarr rescan for %s" % title)
    requests.post(SONARR_URL + "/api/v3/command",
        json={"name": "RescanSeries", "seriesId": series_id},
        headers={"X-Api-Key": SONARR_API_KEY}, timeout=30)

def process_series(series, dry_run):
    title        = series["title"]
    series_path  = series.get("path", "")
    real_seasons = sorted([s["seasonNumber"] for s in series.get("seasons", []) if s["seasonNumber"] > 0])
    if not real_seasons:
        logging.info("  %s: no seasons found - skipping" % title)
        return {"skipped": 1}
    latest = max(real_seasons)
    old    = [s for s in real_seasons if s != latest]
    logging.info("Processing: %s" % title)
    logging.info("  Keeping S%02d | Removing: %s" % (latest, old if old else "none"))
    if not old:
        logging.info("  Only one season - nothing to do")
        return {"skipped": 1}
    stats = {"unmonitored": 0, "deleted": 0}
    for s in old:
        unmonitor_season(series, s, dry_run)
        stats["unmonitored"] += 1
        if series_path:
            delete_season_files(title, series_path, s, dry_run)
            stats["deleted"] += 1
        else:
            logging.warning("  %s: no path in Sonarr - skipping file deletion" % title)
    rescan_series(series["id"], title, dry_run)
    return stats

def main():
    parser = argparse.ArgumentParser(
        description="Unmonitor and delete older seasons of Sonarr series tagged with keep-latest"
    )
    parser.add_argument("--dry-run", action="store_true",
        help="Preview changes without actually deleting anything")
    args = parser.parse_args()
    setup_logging(args.dry_run)
    logging.info("=" * 60)
    logging.info("Sonarr cleanup started - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    tag_id = get_tag_id(KEEP_LATEST_TAG)
    if tag_id is None:
        logging.error("Tag '%s' not found in Sonarr - exiting" % KEEP_LATEST_TAG)
        sys.exit(1)
    series_list = get_series_with_tag(tag_id)
    if not series_list:
        logging.info("No series tagged '%s' - nothing to do" % KEEP_LATEST_TAG)
        sys.exit(0)
    logging.info("Found %d series tagged '%s'" % (len(series_list), KEEP_LATEST_TAG))
    total_u = total_d = total_s = 0
    for series in series_list:
        r = process_series(series, args.dry_run)
        total_u += r.get("unmonitored", 0)
        total_d += r.get("deleted", 0)
        total_s += r.get("skipped", 0)
    logging.info("=" * 60)
    logging.info("Done - %d series | %d unmonitored | %d deleted | %d skipped" % (
        len(series_list), total_u, total_d, total_s))

if __name__ == "__main__":
    main()

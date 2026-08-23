#!/bin/bash
# Scheduled pipeline refresh — runs every 15 days via cron
# Refreshes tracked states, then sends Telegram notification
#
# Cron entry (runs at 6 AM on 1st and 16th of each month):
#   0 6 1,16 * * /path/to/mp-transparency-tracker/scripts/scheduled_refresh.sh >> /tmp/mp-tracker-cron.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Load environment (Telegram credentials etc.)
source .env

LOGFILE="/tmp/mp-tracker-refresh-$(date +%Y%m%d).log"

echo "=== MP Transparency Tracker Refresh ===" | tee -a "$LOGFILE"
echo "Started: $(date)" | tee -a "$LOGFILE"

# Run pipeline for tracked states
# Smart cache will skip fresh data and only re-fetch stale/missing sources
# NOTE: currently only Delhi; switch to --all-states for a full refresh
python -m tracker.main --states delhi 2>&1 | tee -a "$LOGFILE"

echo "" | tee -a "$LOGFILE"
echo "Completed: $(date)" | tee -a "$LOGFILE"

# Send Telegram notification
python scripts/notify_telegram.py 2>&1 || echo "Telegram notification failed"

echo "=== Done ===" | tee -a "$LOGFILE"

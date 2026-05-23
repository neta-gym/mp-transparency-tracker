#!/bin/bash
# Scheduled pipeline refresh — runs every 15 days via cron
# Refreshes all states with seed data, then sends Telegram notification
#
# Cron entry (runs at 6 AM on 1st and 16th of each month):
#   0 6 1,16 * * /Users/shridhar.kumar/Downloads/side/mp-transparency-tracker/scripts/scheduled_refresh.sh >> /tmp/mp-tracker-cron.log 2>&1

set -e

cd /Users/shridhar.kumar/Downloads/side/mp-transparency-tracker

# Load environment
source .env
export ANTHROPIC_API_KEY

LOGFILE="/tmp/mp-tracker-refresh-$(date +%Y%m%d).log"

echo "=== MP Transparency Tracker Refresh ===" | tee -a "$LOGFILE"
echo "Started: $(date)" | tee -a "$LOGFILE"

# Run pipeline for all seeded states
# Smart cache will skip fresh data and only re-fetch stale/missing sources
python -m tracker.main --states delhi 2>&1 | tee -a "$LOGFILE"

echo "" | tee -a "$LOGFILE"
echo "Completed: $(date)" | tee -a "$LOGFILE"

# Send Telegram notification
python scripts/notify_telegram.py 2>&1 || echo "Telegram notification failed"

echo "=== Done ===" | tee -a "$LOGFILE"

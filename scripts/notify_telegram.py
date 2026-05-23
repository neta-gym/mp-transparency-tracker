#!/usr/bin/env python3
"""Telegram notification helper for MP Transparency Tracker.

Setup:
  1. Open Telegram, search for @BotFather
  2. Send /newbot, follow prompts → you get a BOT_TOKEN
  3. Send a message to your new bot, then visit:
     https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
     to find your CHAT_ID (in result.message.chat.id)
  4. Add to .env:
     TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
     TELEGRAM_CHAT_ID=123456789

Usage:
  python scripts/notify_telegram.py "Pipeline complete for Delhi!"
  python scripts/notify_telegram.py  # reads from stdin
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def send_message(text: str, parse_mode: str = "Markdown") -> bool:
    """Send a Telegram message. Returns True on success."""
    if not BOT_TOKEN or not CHAT_ID:
        print("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in .env", file=sys.stderr)
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                print(f"Telegram message sent to chat {CHAT_ID}", file=sys.stderr)
                return True
            else:
                print(f"Telegram API error: {result}", file=sys.stderr)
                return False
    except urllib.error.URLError as e:
        print(f"Telegram send failed: {e}", file=sys.stderr)
        return False


def format_pipeline_summary(state: str, data_dir: str = "data") -> str:
    """Generate a summary message from the latest leaderboard."""
    lb_path = os.path.join(data_dir, state.replace(" ", "-").lower(), "leaderboard", "latest.json")
    try:
        with open(lb_path) as f:
            lb = json.load(f)
    except FileNotFoundError:
        return f"Pipeline ran for *{state.title()}* but no leaderboard found."

    entries = lb.get("entries", [])
    if not entries:
        return f"Pipeline ran for *{state.title()}* — 0 MPs scored."

    avg = sum(e["composite_score"] for e in entries) / len(entries)
    top = entries[0]
    bottom = entries[-1]

    lines = [
        f"*MP Transparency Tracker*",
        f"State: *{state.title()}*",
        f"MPs scored: *{len(entries)}*",
        f"Avg score: *{avg:.1f}/100*",
        f"",
        f"Top: {top['mp_name']} ({top['composite_score']:.1f})",
        f"Bottom: {bottom['mp_name']} ({bottom['composite_score']:.1f})",
        f"",
        f"Generated: {lb.get('generated_at', 'unknown')[:10]}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Direct message
        msg = " ".join(sys.argv[1:])
    elif not sys.stdin.isatty():
        # Read from stdin
        msg = sys.stdin.read().strip()
    else:
        # Generate summary for all states with data
        import glob
        states_with_data = []
        for lb_file in glob.glob("data/*/leaderboard/latest.json"):
            state_slug = lb_file.split("/")[1]
            states_with_data.append(state_slug.replace("-", " "))

        if states_with_data:
            parts = [format_pipeline_summary(s) for s in sorted(states_with_data)]
            msg = "\n---\n".join(parts)
        else:
            msg = "MP Transparency Tracker: No state data found."

    send_message(msg)

#!/bin/bash
# Download all Hayley Maxfield images from listal.com
set -euo pipefail

SAVE_DIR="/home/shri/mp-transparency-tracker/data/images/hayley-maxfield"
mkdir -p "$SAVE_DIR"

BASE="https://www.listal.com/hayley-maxfield/pictures"

echo "=== Step 1: Extracting image IDs from all pages ==="

# Collect all image IDs from all 22 pages
ALL_IDS=""
for page in $(seq 1 22); do
  if [ "$page" -eq 1 ]; then
    URL="$BASE"
  else
    URL="$BASE/$page"
  fi
  echo "Fetching page $page..."
  IDS=$(curl -sL "$URL" | grep -oP 'imageids\[\K[0-9]+(?=\])' | sort -u)
  ALL_IDS="$ALL_IDS"$'\n'"$IDS"
  sleep 0.5
done

# Deduplicate and count
UNIQUE_IDS=$(echo "$ALL_IDS" | grep -v '^$' | sort -u)
TOTAL=$(echo "$UNIQUE_IDS" | wc -l)
echo "Found $TOTAL unique image IDs"

echo "=== Step 2: Checking which IDs need downloading ==="

# Try downloading with the hayley-maxfield slug (known to work)
SUCCESS=0
FAILED=0
SKIPPED=0
TOTAL_ACTUAL=0

while IFS= read -r id; do
  [ -z "$id" ] && continue
  TOTAL_ACTUAL=$((TOTAL_ACTUAL + 1))

  # Try the known slug first
  for slug in "hayley-maxfield"; do
    ext="jpg"
    outfile="$SAVE_DIR/${id}.${ext}"

    if [ -f "$outfile" ]; then
      SKIPPED=$((SKIPPED + 1))
      break
    fi

    # Download
    HTTP=$(curl -L -o "$outfile" -w "%{http_code}" "https://ilarge.lisimg.com/image/${id}/740full-${slug}.${ext}" -s 2>/dev/null)

    if [ "$HTTP" = "200" ]; then
      # Verify it's a real image
      if file "$outfile" | grep -q "JPEG\|PNG\|GIF\|WebP\|image"; then
        SUCCESS=$((SUCCESS + 1))
        echo "  [OK] $id ($SUCCESS/$TOTAL_ACTUAL)"
        break
      else
        rm -f "$outfile"
      fi
    fi

    # If known slug failed, try to get slug from view page
    echo "  Trying view page for $id..."
    VIEW_HTML=$(curl -sL "https://www.listal.com/viewimage/$id")
    SLUG=$(echo "$VIEW_HTML" | grep -oP 'ilarge\.lisimg\.com/image/\d+/740full-\K[^"]+' | head -1)

    if [ -n "$SLUG" ]; then
      ext="${SLUG##*.}"
      outfile="$SAVE_DIR/${id}.${ext}"
      if [ ! -f "$outfile" ]; then
        HTTP=$(curl -L -o "$outfile" -w "%{http_code}" "https://ilarge.lisimg.com/image/${id}/740full-${SLUG}" -s 2>/dev/null)
        if [ "$HTTP" = "200" ] && file "$outfile" | grep -q "JPEG\|PNG\|GIF\|WebP\|image"; then
          SUCCESS=$((SUCCESS + 1))
          echo "  [OK] $id via slug=$SLUG ($SUCCESS/$TOTAL_ACTUAL)"
        else
          rm -f "$outfile"
          FAILED=$((FAILED + 1))
          echo "  [FAIL] $id"
        fi
      fi
    else
      FAILED=$((FAILED + 1))
      echo "  [FAIL] $id (no slug found)"
    fi
  done

  # Rate limiting
  sleep 0.2
done <<< "$UNIQUE_IDS"

echo ""
echo "=== Done ==="
echo "Success: $SUCCESS"
echo "Failed: $FAILED"
echo "Skipped (already existed): $SKIPPED"
echo "Saved to: $SAVE_DIR"
echo "Total files on disk: $(ls "$SAVE_DIR" | wc -l)"
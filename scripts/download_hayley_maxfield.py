#!/usr/bin/env python3
"""Download all Hayley Maxfield images from listal.com"""
import os, re, urllib.request, time, sys

SAVE_DIR = "/home/shri/mp-transparency-tracker/data/images/hayley-maxfield"
os.makedirs(SAVE_DIR, exist_ok=True)

session = urllib.request.build_opener()
session.addheaders = [('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36')]

def get_image_ids_from_page(page_num):
    """Extract image IDs from a listal.com pictures page."""
    url = f"https://www.listal.com/hayley-maxfield/pictures/{page_num}" if page_num > 1 else "https://www.listal.com/hayley-maxfield/pictures"
    try:
        resp = session.open(url, timeout=30)
        html = resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"  Error fetching page {page_num}: {e}")
        return []
    # Find all imageids[...] occurrences
    ids = re.findall(r'imageids\[(\d+)\]', html)
    # Deduplicate while preserving order
    seen = set()
    unique_ids = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            unique_ids.append(i)
    return unique_ids

def get_image_slug(image_id):
    """Get the image slug from the view page."""
    url = f"https://www.listal.com/viewimage/{image_id}"
    try:
        resp = session.open(url, timeout=30)
        html = resp.read().decode('utf-8', errors='replace')
        match = re.search(r'ilarge\.lisimg\.com/image/\d+/740full-([^"]+?\.jpg)', html)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"  Error fetching view page for {image_id}: {e}")
    return None

def download_image(image_id, slug):
    """Download a full-size image."""
    url = f"https://ilarge.lisimg.com/image/{image_id}/740full-{slug}"
    ext = os.path.splitext(slug)[1] or '.jpg'
    filepath = os.path.join(SAVE_DIR, f"{image_id}{ext}")
    if os.path.exists(filepath):
        return True  # Already downloaded
    try:
        resp = session.open(url, timeout=60)
        data = resp.read()
        with open(filepath, 'wb') as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"  Error downloading {image_id}: {e}")
        return False

# First, get all image IDs from all pages
all_ids = []
print("Scanning pages for image IDs...")
for page in range(1, 23):
    ids = get_image_ids_from_page(page)
    print(f"  Page {page}: found {len(ids)} images")
    all_ids.extend(ids)
    if page < 22:
        time.sleep(1)  # Be polite

# Deduplicate
all_ids = list(dict.fromkeys(all_ids))
print(f"\nTotal unique image IDs: {len(all_ids)}")

# Get slugs (batch the view page requests)
print("\nFetching image slugs...")
id_to_slug = {}
for i, img_id in enumerate(all_ids):
    slug = get_image_slug(img_id)
    if slug:
        id_to_slug[img_id] = slug
    if (i + 1) % 10 == 0:
        print(f"  {i+1}/{len(all_ids)} slugs fetched")
    time.sleep(0.5)

print(f"\nGot {len(id_to_slug)} slugs")

# Download images
print("\nDownloading images...")
success = 0
failed = 0
for i, (img_id, slug) in enumerate(id_to_slug.items()):
    if download_image(img_id, slug):
        success += 1
    else:
        failed += 1
    if (i + 1) % 50 == 0:
        print(f"  {i+1}/{len(id_to_slug)} downloaded ({success} success, {failed} failed)")
    time.sleep(0.3)

print(f"\nDone! {success} downloaded, {failed} failed")
print(f"Saved to: {SAVE_DIR}")
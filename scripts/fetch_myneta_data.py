#!/usr/bin/env python3
"""
Fetch MyNeta data for all MPs with candidate IDs and update raw + score files.
Run this as a background process since it fetches ~490 pages.
"""

import json, re, os, glob, sys, time
import urllib.request
from bs4 import BeautifulSoup

BASE_DIR = '/home/shri/mp-transparency-tracker'
DATA_DIR = os.path.join(BASE_DIR, 'data')


def parse_myneta_candidate(candidate_id):
    """Parse a MyNeta candidate page and extract key data."""
    url = f"https://myneta.info/LokSabha2024/candidate.php?candidate_id={candidate_id}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    resp = urllib.request.urlopen(req, timeout=15)
    html = resp.read().decode('utf-8', errors='replace')
    soup = BeautifulSoup(html, 'lxml')
    text = soup.get_text('\n')

    result = {
        'candidate_id': candidate_id,
        'photo_url': None,
        'criminal_cases': 0,
        'serious_criminal_cases': 0,
        'total_assets': 0.0,
        'liabilities': 0.0,
        'education': '',
        'age': None,
    }

    # Photo URL
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if 'images_candidate' in src:
            result['photo_url'] = src if src.startswith('http') else f"https://myneta.info/{src.lstrip('/')}"
            break

    # Criminal cases
    crim_match = re.search(r'Number of Criminal Cases:\s*(\d+)', text)
    if crim_match:
        result['criminal_cases'] = int(crim_match.group(1))

    # Assets and Liabilities
    tables = soup.find_all('table')
    for table in tables:
        for row in table.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).lower()
                value = cells[1].get_text(strip=True)
                if 'assets' in label and 'rs' in value.lower():
                    amounts = re.findall(r'([\d,]+)', value)
                    if amounts:
                        result['total_assets'] = float(amounts[0].replace(',', ''))
                elif 'liabilit' in label and 'rs' in value.lower():
                    amounts = re.findall(r'([\d,]+)', value)
                    if amounts:
                        result['liabilities'] = float(amounts[0].replace(',', ''))

    # Education
    edu_match = re.search(
        r'Category:\s*(Post Graduate|Graduate|Doctorate|12th|10th|5th|8th|Literate|Illiterate|Others|Graduate Professional)',
        text
    )
    if edu_match:
        result['education'] = edu_match.group(1).strip()

    # Age
    age_match = re.search(r'Age:\s*(\d{2,3})', text)
    if age_match and 20 < int(age_match.group(1)) < 100:
        result['age'] = int(age_match.group(1))

    return result


def main():
    print("Starting MyNeta data enrichment...")
    
    states_dirs = [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d)) and d not in ('national',)]
    
    total_mps = 0
    fetched = 0
    errors = 0
    skipped = 0
    
    for s in sorted(states_dirs):
        scores_dir = os.path.join(DATA_DIR, s, 'scores')
        raw_dir = os.path.join(DATA_DIR, s, 'raw')
        if not os.path.exists(scores_dir):
            continue

        for f in glob.glob(os.path.join(scores_dir, '*.json')):
            with open(f) as fh:
                score = json.load(fh)
            
            mp = score['mp']
            slug = mp.get('slug', '')
            myneta_id = mp.get('myneta_candidate_id')
            total_mps += 1
            
            if not myneta_id:
                skipped += 1
                continue
            
            # Check if we already have good criminal/asset data
            raw = score.get('raw', {})
            criminal_conf = raw.get('criminal_record', {}).get('confidence', 0)
            assets_conf = raw.get('assets', {}).get('confidence', 0)
            
            if criminal_conf >= 0.5 and assets_conf >= 0.5:
                skipped += 1
                continue
            
            try:
                myneta_data = parse_myneta_candidate(myneta_id)
                
                # Update score file MP profile
                if myneta_data.get('education') and not mp.get('education'):
                    mp['education'] = myneta_data['education']
                if myneta_data.get('age') and not mp.get('age'):
                    mp['age'] = myneta_data['age']
                
                # Update raw criminal_record
                criminal = raw.get('criminal_record', {})
                if criminal.get('confidence', 0) < 0.5:
                    criminal['total_cases'] = myneta_data['criminal_cases']
                    criminal['serious_cases'] = myneta_data['serious_criminal_cases']
                    criminal['pending_cases'] = myneta_data['criminal_cases']
                    criminal['convictions'] = 0
                    criminal['disposed_cases'] = 0
                    criminal['confidence'] = 0.8
                    criminal['source'] = 'myneta'
                    raw['criminal_record'] = criminal
                
                # Update raw assets
                assets = raw.get('assets', {})
                if assets.get('confidence', 0) < 0.5:
                    assets['total_assets'] = myneta_data['total_assets']
                    assets['liabilities'] = myneta_data['liabilities']
                    assets['movable_assets'] = 0
                    assets['immovable_assets'] = 0
                    assets['net_worth'] = myneta_data['total_assets'] - myneta_data['liabilities']
                    assets['confidence'] = 0.8
                    assets['source'] = 'myneta'
                    raw['assets'] = assets
                
                score['raw'] = raw
                
                # Save score file
                with open(f, 'w') as fh:
                    json.dump(score, fh, indent=2, ensure_ascii=False)
                
                # Also update the standalone raw file
                raw_file = os.path.join(raw_dir, f'{slug}.json')
                if os.path.exists(raw_file):
                    with open(raw_file) as fh:
                        raw_data = json.load(fh)
                    raw_data['criminal_record'] = criminal
                    raw_data['assets'] = assets
                    with open(raw_file, 'w') as fh:
                        json.dump(raw_data, fh, indent=2, ensure_ascii=False)
                
                fetched += 1
                
                if fetched % 50 == 0:
                    print(f"  Progress: {fetched} fetched, {errors} errors, {skipped} skipped of {total_mps}")
                
                time.sleep(0.3)  # Rate limit
                
            except Exception as e:
                errors += 1
                if errors <= 10:
                    print(f"  Error fetching {slug} (cid={myneta_id}): {e}")

    print(f"\nDone! Total: {total_mps}, Fetched: {fetched}, Errors: {errors}, Skipped: {skipped}")


if __name__ == '__main__':
    main()

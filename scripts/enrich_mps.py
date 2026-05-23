#!/usr/bin/env python3
"""
Enrich all MP score files with:
1. Sansad API photo URLs
2. MyNeta candidate data (criminal, assets, education, age, photo)
3. Re-generate leaderboards with enriched data
"""

import json, re, os, glob, sys
import urllib.request
import time
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')


def fetch_sansad_photos():
    """Fetch all MP photos from Sansad API."""
    print("Fetching Sansad API photos...")
    url = "https://www.sansad.in/api_ls/member"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read().decode('utf-8', errors='replace'))

    if isinstance(data, dict):
        members = data.get('membersDtoList', data.get('members', data.get('data', [])))
    elif isinstance(data, list):
        members = data
    else:
        members = []

    sitting_18 = [
        m for m in members
        if str(m.get("status", "")).strip().lower() == "sitting"
        and str(m.get("lastLoksabha", "")).strip() == "18"
    ]

    photo_by_mpsno = {}
    for m in sitting_18:
        mpsno = m.get('mpsno')
        image_url = m.get('imageUrl', '')
        if mpsno and image_url:
            photo_by_mpsno[int(mpsno)] = image_url

    print(f"  Loaded {len(photo_by_mpsno)} photos from Sansad")
    return photo_by_mpsno


def build_myneta_mapping():
    """Build MyNeta candidate_id mapping from the winners page."""
    print("Building MyNeta ID mapping...")
    
    # Fetch winners page
    url = "https://myneta.info/LokSabha2024/index.php?action=show_winners&sort=state"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    resp = urllib.request.urlopen(req, timeout=15)
    html = resp.read().decode('utf-8', errors='replace')

    soup = BeautifulSoup(html, 'lxml')
    table = soup.find_all('table')[4]

    winners = []
    for row in table.find_all('tr'):
        link = row.find('a', href=lambda x: x and 'candidate.php?candidate_id=' in x)
        if not link:
            continue
        cid = re.search(r'candidate_id=(\d+)', link['href'])
        if not cid:
            continue
        cells = [c.get_text(strip=True).replace('\xa0', ' ') for c in row.find_all('td')]
        if len(cells) < 4:
            continue
        winners.append({
            'name': link.get_text(strip=True),
            'candidate_id': int(cid.group(1)),
            'constituency': cells[2],
            'party': cells[3],
        })

    print(f"  Found {len(winners)} winners on MyNeta")

    # Load all MP score files
    states_dirs = [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d)) and d not in ('national',)]
    all_mps = []
    for s in sorted(states_dirs):
        scores_dir = os.path.join(DATA_DIR, s, 'scores')
        if not os.path.exists(scores_dir):
            continue
        for f in glob.glob(os.path.join(scores_dir, '*.json')):
            with open(f) as fh:
                score = json.load(fh)
            mp = score['mp']
            mp['_state_dir'] = s
            mp['_score_file'] = f
            all_mps.append(mp)

    # Multi-strategy matching
    def norm_const(s):
        s = s.upper().strip()
        s = re.sub(r'\s*\(SC\)\s*', '', s)
        s = re.sub(r'\s*\(ST\)\s*', '', s)
        s = s.replace('&', 'AND').replace('-', ' ')
        return re.sub(r'\s+', ' ', s).strip()

    def super_norm(s):
        return re.sub(r'[^A-Z]', '', s.upper())

    myneta_mapping = {}

    # Strategy 1: Exact constituency match
    for mp in all_mps:
        slug = mp.get('slug', '')
        const = norm_const(mp.get('constituency', ''))
        for w in winners:
            w_const = norm_const(w['constituency'])
            if const == w_const:
                myneta_mapping[slug] = w['candidate_id']
                break

    # Strategy 2: Super-normalized
    for mp in all_mps:
        slug = mp.get('slug', '')
        if slug in myneta_mapping:
            continue
        const = super_norm(mp.get('constituency', ''))
        for w in winners:
            w_const = super_norm(w['constituency'])
            if const == w_const:
                myneta_mapping[slug] = w['candidate_id']
                break
        if slug not in myneta_mapping:
            const_no_suffix = re.sub(r'(SC|ST)$', '', const)
            for w in winners:
                w_const = super_norm(w['constituency'])
                if const_no_suffix == w_const:
                    myneta_mapping[slug] = w['candidate_id']
                    break

    # Strategy 3: Substring
    for mp in all_mps:
        slug = mp.get('slug', '')
        if slug in myneta_mapping:
            continue
        const = super_norm(mp.get('constituency', ''))
        if len(const) < 3:
            continue
        for w in winners:
            w_const = super_norm(w['constituency'])
            if len(w_const) >= 3 and (const in w_const or w_const in const):
                myneta_mapping[slug] = w['candidate_id']
                break

    # Strategy 4: Prefix match with party
    for mp in all_mps:
        slug = mp.get('slug', '')
        if slug in myneta_mapping:
            continue
        const = super_norm(mp.get('constituency', ''))
        party = super_norm(mp.get('party', ''))
        best_match = None
        best_score = 0
        for w in winners:
            w_const = super_norm(w['constituency'])
            common_len = 0
            for i in range(min(len(const), len(w_const))):
                if const[i] == w_const[i]:
                    common_len += 1
                else:
                    break
            if common_len >= 3 and common_len > best_score:
                w_party = super_norm(w['party'])
                party_match = any(pp in party and pp in w_party 
                                 for pp in ['BJP', 'INC', 'SP', 'TMC', 'DMK', 'BSP', 'CPI', 'AAP'])
                if party_match or common_len >= 5:
                    best_match = w
                    best_score = common_len
        if best_match:
            myneta_mapping[slug] = best_match['candidate_id']

    print(f"  Matched {len(myneta_mapping)} / {len(all_mps)} MPs to MyNeta IDs")
    return myneta_mapping


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


def update_score_files(photo_by_mpsno, myneta_mapping, fetch_myneta=True):
    """Update all MP score files with photos and MyNeta data."""
    states_dirs = [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d)) and d not in ('national',)]
    
    photo_updated = 0
    myneta_id_updated = 0
    myneta_data_updated = 0
    myneta_fetch_errors = 0

    for s in sorted(states_dirs):
        scores_dir = os.path.join(DATA_DIR, s, 'scores')
        if not os.path.exists(scores_dir):
            continue

        for f in glob.glob(os.path.join(scores_dir, '*.json')):
            with open(f) as fh:
                score = json.load(fh)

            mp = score['mp']
            slug = mp.get('slug', '')
            changed = False

            # 1. Update photo from Sansad
            mpsno = mp.get('sansad_member_id')
            if mpsno and int(mpsno) in photo_by_mpsno:
                new_photo = photo_by_mpsno[int(mpsno)]
                if new_photo and mp.get('photo_url') != new_photo:
                    mp['photo_url'] = new_photo
                    changed = True
                    photo_updated += 1

            # 2. Update MyNeta ID
            if slug in myneta_mapping:
                new_id = myneta_mapping[slug]
                if mp.get('myneta_candidate_id') != new_id:
                    mp['myneta_candidate_id'] = new_id
                    changed = True
                    myneta_id_updated += 1

                # 3. Fetch MyNeta data (criminal, assets, education, age)
                if fetch_myneta and new_id:
                    try:
                        myneta_data = parse_myneta_candidate(new_id)
                        
                        # Update MP profile fields
                        if myneta_data.get('education') and not mp.get('education'):
                            mp['education'] = myneta_data['education']
                            changed = True
                        if myneta_data.get('age') and not mp.get('age'):
                            mp['age'] = myneta_data['age']
                            changed = True
                        
                        # Update raw data criminal record
                        if score.get('raw', {}).get('criminal_record', {}).get('confidence', 0) < 0.5:
                            criminal = score['raw'].setdefault('criminal_record', {})
                            criminal['total_cases'] = myneta_data['criminal_cases']
                            criminal['serious_cases'] = myneta_data['serious_criminal_cases']
                            criminal['pending_cases'] = myneta_data['criminal_cases']
                            criminal['convictions'] = 0
                            criminal['disposed_cases'] = 0
                            criminal['confidence'] = 0.8
                            criminal['source'] = 'myneta'
                            changed = True
                        
                        # Update raw data assets
                        if score.get('raw', {}).get('assets', {}).get('confidence', 0) < 0.5:
                            assets = score['raw'].setdefault('assets', {})
                            assets['total_assets'] = myneta_data['total_assets']
                            assets['liabilities'] = myneta_data['liabilities']
                            assets['movable_assets'] = 0
                            assets['immovable_assets'] = 0
                            assets['net_worth'] = myneta_data['total_assets'] - myneta_data['liabilities']
                            assets['confidence'] = 0.8
                            assets['source'] = 'myneta'
                            changed = True

                        myneta_data_updated += 1
                        time.sleep(0.3)  # Rate limit

                    except Exception as e:
                        myneta_fetch_errors += 1
                        if myneta_fetch_errors <= 5:
                            print(f"  MyNeta fetch error for {slug} (cid={new_id}): {e}")

            if changed:
                with open(f, 'w') as fh:
                    json.dump(score, fh, indent=2, ensure_ascii=False)

    print(f"\nUpdate summary:")
    print(f"  Photo URLs updated: {photo_updated}")
    print(f"  MyNeta IDs updated: {myneta_id_updated}")
    print(f"  MyNeta data fetched: {myneta_data_updated}")
    print(f"  MyNeta fetch errors: {myneta_fetch_errors}")


def main():
    # Step 1: Get Sansad photos
    photo_by_mpsno = fetch_sansad_photos()

    # Step 2: Build MyNeta mapping
    myneta_mapping = build_myneta_mapping()

    # Step 3: Update all score files
    update_score_files(photo_by_mpsno, myneta_mapping, fetch_myneta=True)

    print("\nEnrichment complete!")


if __name__ == '__main__':
    main()

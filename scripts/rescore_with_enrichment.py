#!/usr/bin/env python3
"""
Re-score all MPs using enriched raw data.

The enrichment script updated raw data files with MyNeta criminal/asset data.
This script reads those enriched raw files and re-computes the affected score
dimensions (criminal_score, asset_score) plus data_confidence, then rebuilds
leaderboards.
"""

import json
import glob
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tracker.agents.assessor import (
    calc_criminal_score,
    calc_asset_score,
)
from tracker.config import settings


def rescore_all():
    data_dir = settings.data_dir
    state_dirs = sorted(glob.glob(os.path.join(data_dir, "*")))
    
    total_updated = 0
    total_mps = 0
    
    for state_dir in state_dirs:
        if not os.path.isdir(state_dir):
            continue
        
        # Skip non-state dirs
        scores_dir = os.path.join(state_dir, "scores")
        raw_dir = os.path.join(state_dir, "raw")
        if not os.path.isdir(scores_dir):
            continue
        
        state_slug = os.path.basename(state_dir)
        score_files = sorted(glob.glob(os.path.join(scores_dir, "*.json")))
        updated_count = 0
        
        for score_path in score_files:
            mp_slug = os.path.basename(score_path).replace(".json", "")
            raw_path = os.path.join(raw_dir, f"{mp_slug}.json")
            
            total_mps += 1
            
            # Load score file
            with open(score_path) as f:
                score = json.load(f)
            
            # Load raw data file
            if not os.path.exists(raw_path):
                continue
            
            with open(raw_path) as f:
                raw = json.load(f)
            
            # Check if raw data has enriched criminal/asset data
            cr_raw = raw.get("criminal_record", {})
            assets_raw = raw.get("assets", {})
            mp_raw = raw.get("mp") or {}
            
            updated = False
            
            # Update MP profile fields in score
            mp_score = score.get("mp", {})
            if mp_raw.get("photo_url") and not mp_score.get("photo_url"):
                mp_score["photo_url"] = mp_raw["photo_url"]
                updated = True
            if mp_raw.get("myneta_candidate_id") and not mp_score.get("myneta_candidate_id"):
                mp_score["myneta_candidate_id"] = mp_raw["myneta_candidate_id"]
                updated = True
            
            # Re-compute criminal_score if raw data has confidence > 0
            if cr_raw.get("confidence", 0) > 0:
                new_criminal = calc_criminal_score(
                    cr_raw.get("total_cases", 0),
                    cr_raw.get("serious_cases", 0),
                    cr_raw.get("convictions", 0),
                    cr_raw.get("pending_cases", 0),
                    cr_raw.get("disposed_cases", 0),
                )
                old_criminal = score.get("breakdown", {}).get("criminal_score", 0)
                if abs(new_criminal - old_criminal) > 0.1:
                    score["breakdown"]["criminal_score"] = round(new_criminal, 1)
                    updated = True
            
            # Re-compute asset_score if raw data has confidence > 0
            if assets_raw.get("confidence", 0) > 0 and assets_raw.get("growth_ratio") is not None:
                new_asset = calc_asset_score(assets_raw.get("growth_ratio"))
                old_asset = score.get("breakdown", {}).get("asset_score", 0)
                if abs(new_asset - old_asset) > 0.1:
                    score["breakdown"]["asset_score"] = round(new_asset, 1)
                    updated = True
            
            # Re-compute data_confidence based on enriched evidence
            if cr_raw.get("confidence", 0) > 0 or assets_raw.get("confidence", 0) > 0:
                # Weighted average of all dimension confidences
                confidences = {}
                for dim_name, dim_raw in [
                    ("criminal_record", cr_raw),
                    ("assets", assets_raw),
                    ("mplads", raw.get("mplads", {})),
                    ("parliament_activity", raw.get("parliament_activity", {})),
                ]:
                    confidences[dim_name] = dim_raw.get("confidence", 0)
                
                # Weighted by score weights
                w = settings.weights
                weighted_sum = (
                    confidences.get("mplads", 0) * w.mplads +
                    confidences.get("assets", 0) * w.asset +
                    confidences.get("criminal_record", 0) * w.criminal +
                    confidences.get("parliament_activity", 0) * (w.attendance + w.participation)
                )
                # Add other dimensions at confidence 0.5 (moderate default)
                other_weight = w.committee + w.accessibility + w.legislative
                weighted_sum += 0.5 * other_weight
                
                new_confidence = round(weighted_sum, 2)
                old_confidence = score.get("data_confidence", 0)
                if abs(new_confidence - old_confidence) > 0.01:
                    score["data_confidence"] = new_confidence
                    updated = True
            
            # Re-compute composite score from updated breakdown
            if updated:
                b = score["breakdown"]
                composite = (
                    b["mplads_score"] * w.mplads +
                    b["asset_score"] * w.asset +
                    b["criminal_score"] * w.criminal +
                    b["attendance_score"] * w.attendance +
                    b["participation_score"] * w.participation +
                    b["committee_score"] * w.committee +
                    b["accessibility_score"] * w.accessibility +
                    b["legislative_score"] * w.legislative
                )
                score["composite_score"] = round(composite, 1)
                
                # Update key_finding to reflect new data
                score["key_finding"] = _generate_key_finding(b)
                
                # Write back
                with open(score_path, "w") as f:
                    json.dump(score, f, indent=2, ensure_ascii=False)
                
                updated_count += 1
                total_updated += 1
        
        if updated_count > 0:
            print(f"  {state_slug}: updated {updated_count}/{len(score_files)} MPs")
    
    print(f"\nTotal: {total_updated}/{total_mps} MPs re-scored")
    return total_updated


def _generate_key_finding(b):
    """Generate a simple key finding from score breakdown."""
    parts = []
    if b.get("criminal_score", 0) >= 100:
        parts.append("Clean record")
    elif b.get("criminal_score", 0) >= 70:
        parts.append("Minor cases")
    else:
        parts.append("Criminal cases noted")
    
    if b.get("mplads_score", 0) >= 70:
        parts.append("good fund use")
    elif b.get("mplads_score", 0) < 40:
        parts.append("low fund use")
    
    if b.get("attendance_score", 0) >= 80:
        parts.append("high attendance")
    elif b.get("attendance_score", 0) < 40:
        parts.append("low attendance")
    
    return ", ".join(parts) if parts else "Mixed transparency record"


def rebuild_leaderboards():
    """Rebuild all state leaderboards and national leaderboard from re-scored data."""
    from tracker.models.schemas import LeaderboardEntry, Leaderboard
    
    data_dir = settings.data_dir
    state_dirs = sorted(glob.glob(os.path.join(data_dir, "*")))
    
    all_entries = []
    states_count = 0
    
    for state_dir in state_dirs:
        if not os.path.isdir(state_dir):
            continue
        
        scores_dir = os.path.join(state_dir, "scores")
        if not os.path.isdir(scores_dir):
            continue
        
        state_slug = os.path.basename(state_dir)
        score_files = sorted(glob.glob(os.path.join(scores_dir, "*.json")))
        entries = []
        
        for score_path in score_files:
            with open(score_path) as f:
                score = json.load(f)
            
            mp = score.get("mp", {})
            b = score.get("breakdown", {})
            entries.append(LeaderboardEntry(
                rank=0,  # Will be set after sorting
                mp_name=mp.get("name", ""),
                constituency=mp.get("constituency", ""),
                state=mp.get("state", state_slug),
                party=mp.get("party", ""),
                composite_score=score.get("composite_score", 0),
                mplads_score=b.get("mplads_score", 0),
                asset_score=b.get("asset_score", 0),
                criminal_score=b.get("criminal_score", 0),
                attendance_score=b.get("attendance_score", 0),
                participation_score=b.get("participation_score", 0),
                committee_score=b.get("committee_score", 50.0),
                accessibility_score=b.get("accessibility_score", 50.0),
                legislative_score=b.get("legislative_score", 50.0),
                data_confidence=score.get("data_confidence", 0),
                key_finding=score.get("key_finding", ""),
                photo_url=mp.get("photo_url"),
            ))
        
        # Sort and assign ranks
        entries.sort(key=lambda e: e.composite_score, reverse=True)
        for i, entry in enumerate(entries, 1):
            entry.rank = i
        
        # Build leaderboard
        lb = Leaderboard(
            state=state_slug,
            total_mps=len(entries),
            entries=entries,
        )
        
        # Save
        lb_dir = os.path.join(state_dir, "leaderboard")
        os.makedirs(lb_dir, exist_ok=True)
        with open(os.path.join(lb_dir, "latest.json"), "w") as f:
            f.write(lb.model_dump_json(indent=2))
        
        all_entries.extend(entries)
        states_count += 1
    
    # Build national leaderboard
    all_entries.sort(key=lambda e: e.composite_score, reverse=True)
    for i, entry in enumerate(all_entries, 1):
        entry.rank = i
    
    from tracker.models.schemas import NationalLeaderboard
    national = NationalLeaderboard(
        total_mps=len(all_entries),
        states_included=[os.path.basename(d) for d in state_dirs if os.path.isdir(os.path.join(d, "scores"))],
        top_n=min(50, len(all_entries)),
        entries=all_entries[:50],
    )
    
    lb_dir = os.path.join(data_dir, "national", "leaderboard")
    os.makedirs(lb_dir, exist_ok=True)
    with open(os.path.join(lb_dir, "latest.json"), "w") as f:
        f.write(national.model_dump_json(indent=2))
    
    print(f"\nRebuilt leaderboards: {states_count} states, {len(all_entries)} total MPs")
    print(f"National leaderboard: {lb_dir}/latest.json")


if __name__ == "__main__":
    print("Re-scoring all MPs with enriched data...")
    updated = rescore_all()
    
    if updated > 0:
        print("\nRebuilding leaderboards...")
        rebuild_leaderboards()
    else:
        print("\nNo scores needed updating — skipping leaderboard rebuild.")

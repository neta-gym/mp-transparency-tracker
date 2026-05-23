"""RTI Batch Generator — generates RTI templates for all MPs in a state."""

from __future__ import annotations

import os

from ..models.schemas import MPProfile, ResearchFindings
from ..utils.rti_generator import generate_rti_template
from ..utils.logger import get_logger

log = get_logger(__name__)


def generate_rti_batch(
    state: str,
    data_dir: str,
    fiscal_year: str = "2024-25",
) -> list[str]:
    """Generate RTI templates for all MPs in a state that have cached findings.

    Returns list of generated file paths.
    """
    state_slug = state.replace(" ", "-").lower()
    raw_dir = os.path.join(data_dir, state_slug, "raw")
    rti_dir = os.path.join(data_dir, state_slug, "rti")

    if not os.path.isdir(raw_dir):
        log.warning("No raw data found for %s", state)
        return []

    os.makedirs(rti_dir, exist_ok=True)
    generated = []
    index_lines = [
        f"# RTI Templates — {state.title()}",
        "",
        f"Fiscal Year: {fiscal_year}",
        "",
        "| MP Name | Constituency | Party | RTI File | Target Authority |",
        "|---------|-------------|-------|----------|------------------|",
    ]

    for filename in sorted(os.listdir(raw_dir)):
        if not filename.endswith(".json") or "_validated" in filename:
            continue

        filepath = os.path.join(raw_dir, filename)
        try:
            with open(filepath) as f:
                findings = ResearchFindings.model_validate_json(f.read())
        except Exception as e:
            log.warning("Failed to parse %s: %s", filename, e)
            continue

        mp = findings.mp
        mplads = findings.mplads

        # Generate MPLADS RTI
        rti_text = generate_rti_template(mp, mplads, fiscal_year)
        rti_filename = f"{mp.slug}_mplads_rti.txt"
        rti_path = os.path.join(rti_dir, rti_filename)
        with open(rti_path, "w") as f:
            f.write(rti_text)
        generated.append(rti_path)

        # Generate asset discrepancy RTI if growth is high
        if findings.assets.growth_ratio is not None and findings.assets.growth_ratio > 1.0:
            asset_rti = _generate_asset_rti(mp, findings)
            asset_filename = f"{mp.slug}_assets_rti.txt"
            asset_path = os.path.join(rti_dir, asset_filename)
            with open(asset_path, "w") as f:
                f.write(asset_rti)
            generated.append(asset_path)

        house_tag = "LS" if mp.house.value == "lok_sabha" else "RS"
        index_lines.append(
            f"| {mp.name} | {mp.constituency} | {mp.party} | "
            f"[{rti_filename}](./{rti_filename}) | District Magistrate, {mp.constituency} |"
        )

    # Write index file
    index_path = os.path.join(rti_dir, "index.md")
    with open(index_path, "w") as f:
        f.write("\n".join(index_lines))
    generated.append(index_path)

    log.info("Generated %d RTI templates for %s", len(generated) - 1, state.title())
    return generated


def _generate_asset_rti(mp: MPProfile, findings: ResearchFindings) -> str:
    """Generate RTI template for asset declaration discrepancies."""
    from datetime import date

    today = date.today().strftime("%d/%m/%Y")
    growth_pct = (findings.assets.growth_ratio or 0) * 100
    house = "Lok Sabha" if mp.house.value == "lok_sabha" else "Rajya Sabha"

    return f"""RIGHT TO INFORMATION APPLICATION
Under Section 6(1) of the Right to Information Act, 2005

Date: {today}

To,
The Public Information Officer (PIO),
Election Commission of India,
Nirvachan Sadan, Ashoka Road,
New Delhi - 110001

Subject: Information regarding asset declaration discrepancies of
{mp.name}, Member of Parliament ({house}), {mp.constituency}, {mp.state.title()}

Sir/Madam,

I, the undersigned, am a citizen of India and hereby request the following
information under the Right to Information Act, 2005, regarding the asset
declarations filed by {mp.name} ({house} MP from {mp.constituency}).

CONTEXT:
As per publicly available affidavit data, this MP's assets have grown by
approximately {growth_pct:.0f}% between consecutive elections, which appears
to be significantly above average.

INFORMATION SOUGHT:

1. AFFIDAVIT COPIES
   (a) Copies of the asset/liability affidavits filed by {mp.name} for the
       2019 and 2024 general elections.
   (b) Any revised or amended affidavits filed during the current term.

2. COMPLIANCE VERIFICATION
   (a) Has the ECI verified the asset declarations for accuracy?
   (b) Were any discrepancies found in the declarations?
   (c) Details of any show-cause notices or proceedings initiated.

3. INCOME TAX RETURNS
   (a) Copies of ITR information disclosed in the affidavits.
   (b) Has the declared income been cross-verified with reported assets?

4. CRIMINAL CASE STATUS
   (a) Updated status of all pending criminal cases declared in the affidavit.
   (b) Any cases disposed of or new cases filed since the last affidavit.

I am willing to pay the prescribed fee for obtaining this information.

Yours faithfully,

[Name: _______________________________]
[Address: _____________________________]
[Phone: ______________________________]

Enclosure: IPO/DD of Rs 10/- (Application Fee)

---
Generated by MP Transparency Tracker
This is a template. Please review and customize before submission.
"""

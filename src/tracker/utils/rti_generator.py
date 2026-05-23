"""RTI Template Generator — pre-filled RTI applications for MPLADS verification.

Generates formal RTI application text addressed to the District Magistrate
of the MP's constituency, with specific questions about MPLADS fund utilization.
This lowers the barrier for citizens to independently verify MPLADS data.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from ..models.schemas import MPProfile, MPLADSFund


def generate_rti_template(
    mp: MPProfile,
    mplads: MPLADSFund,
    fiscal_year: str = "2024-25",
) -> str:
    """Generate a pre-filled RTI application for MPLADS fund verification.

    Args:
        mp: The MP's profile
        mplads: Current MPLADS fund data (for context in the application)
        fiscal_year: The fiscal year to query about

    Returns:
        Formatted RTI application text ready for printing/copying
    """
    today = date.today().strftime("%d/%m/%Y")
    constituency = mp.constituency
    state = mp.state.title()
    mp_name = mp.name
    house = "Lok Sabha" if mp.house.value == "lok_sabha" else "Rajya Sabha"

    # Build context note if we have existing data
    context_note = ""
    if mplads.released is not None or mplads.expended is not None:
        context_note = (
            f"\n\n[Note: As per publicly available data, the following figures have been reported "
            f"for {mp_name}'s MPLADS account: "
        )
        parts = []
        if mplads.released is not None:
            parts.append(f"Released: Rs {mplads.released:,.0f}")
        if mplads.expended is not None:
            parts.append(f"Expended: Rs {mplads.expended:,.0f}")
        if mplads.utilization_rate is not None:
            parts.append(f"Utilization: {mplads.utilization_rate:.1f}%")
        context_note += ", ".join(parts) + ". This RTI seeks to verify and supplement this data.]"

    return f"""RIGHT TO INFORMATION APPLICATION
Under Section 6(1) of the Right to Information Act, 2005

Date: {today}

To,
The Public Information Officer (PIO) / District Magistrate,
Office of the District Magistrate,
{constituency} District,
{state}

Subject: Information regarding MPLADS Fund utilization under the constituency of
{mp_name}, Member of Parliament ({house}), {constituency}, {state} —
Financial Year {fiscal_year}

Sir/Madam,

I, the undersigned, am a citizen of India and hereby request the following
information under the Right to Information Act, 2005, regarding the
Members of Parliament Local Area Development Scheme (MPLADS) funds
for the constituency of {constituency} represented by {mp_name} ({house}).

INFORMATION SOUGHT:

1. FUND STATEMENTS
   Please provide complete fund statements for FY {fiscal_year} showing:
   (a) Opening balance as on 1st April
   (b) Total funds released by Government of India during the year
   (c) Interest earned on unspent balances
   (d) Total expenditure during the year
   (e) Closing balance as on 31st March
   (f) Cumulative funds released and expended since the MP's tenure began

2. SANCTION ORDER COPIES
   Please provide copies of all sanction orders issued for works recommended
   by the MP during FY {fiscal_year}, including:
   (a) Work description and location
   (b) Sanctioned amount
   (c) Date of sanction
   (d) Name of implementing agency

3. UTILIZATION CERTIFICATES & PAYMENT RECORDS
   Please provide:
   (a) Copies of all Utilization Certificates (UCs) submitted for completed works
   (b) Details of payments made to contractors/agencies, with dates and amounts
   (c) Any UCs pending submission, with reasons for delay

4. COMPLETION CERTIFICATES & ASSET HANDOVER
   Please provide:
   (a) Copies of completion certificates for works completed in FY {fiscal_year}
   (b) Details of assets created and handed over to user agencies
   (c) List of works in progress with current status and expected completion dates
   (d) List of works recommended but not yet started, with reasons

5. AUDIT REPORTS & COMPLIANCE
   Please provide:
   (a) Copies of any audit reports (internal or CAG) on MPLADS works in this constituency
   (b) Details of audit objections raised, if any, and compliance status
   (c) Details of any works found to be deficient, substandard, or requiring rectification

6. DISTRICT LEVEL MONITORING
   (a) Minutes of the last 4 District Level Monitoring Committee meetings
   (b) Details of physical inspection/verification of MPLADS works conducted
   (c) Any complaints received regarding MPLADS works and action taken

I am willing to pay the prescribed fee for obtaining this information.
Please provide the information in printed/photocopied form.

If any of the above information is held by a different public authority,
please transfer the relevant portion of this application to that authority
under Section 6(3) of the RTI Act, and inform me accordingly.

Yours faithfully,

[Name: _______________________________]
[Address: _____________________________]
[Phone: ______________________________]
[Email: ______________________________]

Enclosure: IPO/DD/Postal Order of Rs 10/- (Application Fee)
{context_note}

---
Generated by MP Transparency Tracker (https://github.com/example/mp-transparency-tracker)
This is a template. Please review and customize before submission.
Fee: Rs 10 by IPO/DD/Court Fee Stamp. Additional Rs 2 per page for photocopies.
Time limit: PIO must respond within 30 days of receipt.
"""

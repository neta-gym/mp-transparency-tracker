# MP Transparency Tracker: Findings Summary (Press Kit)

**Published September 2, 2026 · Data current as of September 2, 2026**
Live dashboard: <https://neta-gym.github.io/mp-transparency-tracker/> · Source and data: <https://github.com/neta-gym/mp-transparency-tracker>

The MP Transparency Tracker scores all 786 sitting members of the Indian Parliament (542 Lok Sabha, 244 Rajya Sabha) on a 0-100 composite built from public records: MPLADS fund utilization, declared assets, declared criminal cases, Parliament attendance, participation, and public accessibility. Every figure below is drawn from the published, auditable dataset and linked to its original public source.

---

## Headline numbers

- **786 MPs scored.** Average composite score: **57.5 out of 100**. Median: 59.7.
- **399 MPs (51%) score below 60.** Only 6 MPs score 75 or above.
- Highest composite: **S Supongmeren Jamir** (Nagaland, LS) at 80.5, followed by Arun Kumar Sagar (Shahjahanpur, UP) at 80.1 and Indra Hang Subba (Sikkim) at 78.1.
- Lowest composite: Amritpal Singh (Khadoor Sahib, Punjab) at 22.2, Surendra Prasad Yadav (Jehanabad, Bihar) at 25.0, Shantanu Thakur (Bangaon, West Bengal) at 26.9.

## Constituency fund usage (MPLADS)

Among the **518 MPs with verified fund records**, average utilization of released MPLADS money is **26.8%**. On average, MPs have put to work barely a quarter of the development funds released to their constituencies.

**Highest verified utilization:**

| MP | Constituency | Utilization |
|---|---|---:|
| Sukhdeo Bhagat | Lohardaga, Jharkhand | 76.3% |
| Malaiyarasan D | Kallakurichi, Tamil Nadu | 66.8% |
| Anoop Pradhan Valmiki | Hathras, Uttar Pradesh | 66.5% |
| Ram Prasad Chaudhary | Basti, Uttar Pradesh | 66.5% |
| Tapir Gao | Arunachal East, Arunachal Pradesh | 66.3% |

**Lowest:** five MPs show **0% utilization** on record: B. J. P. V. Srinivasa Varma (Narsapuram, AP), Harish Chandra Meena (Tonk-Sawai Madhopur, Rajasthan), T. M. Selvaganapathi (Salem, TN), Jyotirmay Singh Mahato (Purulia, WB), and Manoj Tigga (Alipurduars, WB).

**State averages** (states with 5+ verified records): Uttar Pradesh leads at 38.5% (80 MPs), followed by Chhattisgarh (38.0%) and Bihar (38.0%). The lowest state averages are Delhi (10.4%), Uttarakhand (11.4%), Odisha (12.0%), Maharashtra (13.1%), and Andhra Pradesh (14.8%).

*268 MPs have no verified MPLADS record in the dataset (including Rajya Sabha members, whose fund data by nodal district is published separately by eSAKSHI). These receive a neutral estimated score, marked with an asterisk on the site, which never counts as a win in comparisons.*

## Declared criminal cases

From sworn election affidavits (MyNeta/ADR), for the **755 MPs with verified records**:

- **308 MPs (41%) declare at least one pending criminal case.** 121 MPs declare at least one **serious** case.
- Total declared pending cases across Parliament: **1,635**, of which **283 are serious**.
- Most serious cases: **Mohite Patil Dhairyasheel Rajsinh** (Madha, Maharashtra; NCP-SP) - 36 cases, 31 serious. **Babu Singh Kushwaha** (Jaunpur, UP; SP) - 25 cases, 18 serious.
- Most total cases: **Dean Kuriakose** (Idukki, Kerala) with 88 declared cases, none classified serious; Shafi Parambil (Vadakara, Kerala) with 47.
- 59% of MPs with verified records declare no pending cases.

*Affidavit data is self-declared at election time (2024 general election) and may have changed since; the site shows this caveat on every MP page.*

## Parliament attendance

For the **687 MPs with verified attendance records** (PRS India), average attendance is **85%**:

- **158 MPs have a perfect 100% attendance record**, including Tapir Gao (Arunachal East), Kripanath Mallah (Karimganj, Assam), and three MPs from Andhra Pradesh (Bastipati Nagaraju, Appalanaidu Kalisetti, C M Ramesh).
- **36 MPs are below 50% attendance.** Lowest on record: Adhikari Deepak Dev (Ghatal, WB) at 0% and Amritpal Singh (Khadoor Sahib, Punjab) at 1% (Singh was in custody for much of the recorded period, per public reporting).

*PRS does not publish attendance for ministers; affected MPs receive a neutral estimated score rather than a zero.*

## Methodology (v3.2)

- Composite = weighted average of six dimensions: **MPLADS 23.5%, Criminal record 23.5%, Assets 17.6%, Attendance 17.6%, Participation 11.8%, Accessibility 5.9%** (proportional rescale of the original weights after two dimensions were excluded).
- **Committee work and legislative activity carry 0% weight.** Both are placeholder estimates for nearly every MP because no usable public source exists yet; the scores are displayed but excluded from the composite until real data exists.
- Any dimension without verified underlying data is shown as a **neutral estimate marked with an asterisk**, is excluded from composite wins in head-to-head comparisons, and is listed in each MP's data provenance.
- Sources: eSAKSHI/MPLADS (Ministry of Statistics and Programme Implementation), MyNeta/ADR sworn affidavits, PRS India legislative research, Sansad (parliament) records. Every data point is evidence-graded; each MP page links its sources.
- MPLADS and asset figures are the latest available from their sources (2024 affidavits; fund figures as last published by eSAKSHI) and are marked as such.

## How this was built

The tracker is an open data pipeline: public records are collected automatically from the source portals, normalized into auditable JSON (one file per MP, in this repository under `data/`), scored deterministically by published code (`src/tracker/`), and published as a static dashboard. Every score change is a public git commit. The full methodology, weights, and scoring code are in the repo; the dataset regenerates from sources.

## Contact

For questions, corrections, or data requests: open an issue at <https://github.com/neta-gym/mp-transparency-tracker/issues>. Corrections backed by a primary source are incorporated promptly and are visible in the public commit history.

*All figures as of September 2, 2026. This project is non-partisan: it applies one published methodology equally to every MP and makes no endorsements.*

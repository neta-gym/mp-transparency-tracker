/**
 * Agent-access & SEO asset preparation.
 *
 * Runs automatically before `next build` (prebuild hook). Generates into
 * public/ so everything ships in the static export under the base path:
 *
 *   data/              curated mirror of pipeline outputs (scores, reports,
 *                      leaderboards) so LLMs/citizens can fetch raw data
 *   search-index.json  flat name→URL index of every MP (agent resolver)
 *   robots.txt         crawler allowlist + sitemap pointer
 *   sitemap.xml        all profile/state/national pages
 *   llms.txt           markdown index of every MP report for LLM consumption
 *
 * Deterministic: reads only ../data outputs of the Python pipeline.
 */

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, "..");
const DATA_DIR = path.join(ROOT, "..", "data");
const PUBLIC_DIR = path.join(ROOT, "public");

const SITE_URL = "https://neta-gym.github.io/mp-transparency-tracker";
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "/mp-transparency-tracker";

function entryToSlug(mpName) {
  return mpName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function displayState(slug) {
  return slug
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function readJSON(p) {
  try {
    return JSON.parse(fs.readFileSync(p, "utf-8"));
  } catch {
    return null;
  }
}

/** Mirror a curated subset of data/ into public/data/. */
function mirrorData() {
  const outRoot = path.join(PUBLIC_DIR, "data");
  fs.rmSync(outRoot, { recursive: true, force: true });

  let files = 0;
  const stateDirs = fs
    .readdirSync(DATA_DIR, { withFileTypes: true })
    .filter((d) => d.isDirectory() && d.name !== "national" && d.name !== "enrichment")
    .map((d) => d.name);

  for (const state of stateDirs) {
    const copies = [
      ["scores", /\.json$/],
      ["reports", /\.md$/],
      ["leaderboard", /^latest\.(json|md)$/],
    ];
    for (const [sub, pattern] of copies) {
      const srcDir = path.join(DATA_DIR, state, sub);
      if (!fs.existsSync(srcDir)) continue;
      const dstDir = path.join(outRoot, state, sub);
      fs.mkdirSync(dstDir, { recursive: true });
      for (const f of fs.readdirSync(srcDir)) {
        if (!pattern.test(f)) continue;
        fs.copyFileSync(path.join(srcDir, f), path.join(dstDir, f));
        files++;
      }
    }
  }

  // National leaderboard
  for (const f of ["latest.json", "latest.md"]) {
    const src = path.join(DATA_DIR, "national", "leaderboard", f);
    if (fs.existsSync(src)) {
      fs.mkdirSync(path.join(outRoot, "national", "leaderboard"), { recursive: true });
      fs.copyFileSync(src, path.join(outRoot, "national", "leaderboard", f));
      files++;
    }
  }
  return files;
}

/** Build flat MP index shared by UI search and external agents. */
function buildIndex() {
  const stateDirs = fs
    .readdirSync(DATA_DIR, { withFileTypes: true })
    .filter((d) => d.isDirectory() && d.name !== "national" && d.name !== "enrichment")
    .map((d) => d.name)
    .sort();

  const mps = [];
  for (const stateSlug of stateDirs) {
    const lb = readJSON(path.join(DATA_DIR, stateSlug, "leaderboard", "latest.json"));
    if (!lb) continue;
    for (const e of lb.entries) {
      const mpSlug = entryToSlug(e.mp_name);
      mps.push({
        mpName: e.mp_name,
        constituency: e.constituency,
        party: e.party,
        state: displayState(stateSlug),
        stateSlug,
        mpSlug,
        compositeScore: e.composite_score,
        house: e.house ?? "lok_sabha",
        photoUrl: e.photo_url ?? null,
        profilePath: `${BASE_PATH}/state/${stateSlug}/mp/${mpSlug}`,
        reportPath: `${BASE_PATH}/data/${stateSlug}/reports/${mpSlug}.md`,
      });
    }
  }
  return mps;
}

function writeSearchIndex(mps) {
  fs.writeFileSync(
    path.join(PUBLIC_DIR, "search-index.json"),
    JSON.stringify({ site: SITE_URL, generatedFor: "search-and-ai-agents", count: mps.length, mps }, null, 0)
  );
}

function writeRobots() {
  fs.writeFileSync(
    path.join(PUBLIC_DIR, "robots.txt"),
    `User-agent: *\nAllow: /\n\nSitemap: ${SITE_URL}/sitemap.xml\n`
  );
}

function writeSitemap(mps) {
  const urls = ["/", "/national", "/compare"];
  for (const stateSlug of new Set(mps.map((m) => m.stateSlug))) {
    urls.push(`/state/${stateSlug}`);
  }
  for (const m of mps) {
    urls.push(`/state/${m.stateSlug}/mp/${m.mpSlug}`);
  }
  const today = new Date().toISOString().slice(0, 10);
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls
  .map(
    (u) =>
      `  <url><loc>${SITE_URL}${u === "/" ? "/" : u}</loc><lastmod>${today}</lastmod></url>`
  )
  .join("\n")}
</urlset>
`;
  fs.writeFileSync(path.join(PUBLIC_DIR, "sitemap.xml"), xml);
  return urls.length;
}

function writeLlmsTxt(mps) {
  const byScore = [...mps].sort((a, b) => b.compositeScore - a.compositeScore);
  const lines = [];
  lines.push("# MP Transparency Tracker");
  lines.push("");
  lines.push(
    "> Open-data transparency rankings for all 540 Lok Sabha MPs (India). Each MP is scored 0-100 across 8 weighted dimensions: MPLADS fund use (20%), criminal record disclosures (20%), asset declarations (15%), parliament attendance (15%), participation (10%), legislative activity (10%), committees (5%), public accessibility (5%). Scores are scrutiny aids backed by cited public sources — not legal conclusions."
  );
  lines.push("");
  lines.push("Every MP page below links to a full markdown report with source citations.");
  lines.push("");
  lines.push("## Data access");
  lines.push("");
  lines.push(`- MP name/constituency/party → URL resolver (JSON): ${SITE_URL}/search-index.json`);
  lines.push(`- Per-MP machine-readable scores: ${SITE_URL}/data/{{state-slug}}/scores/{{mp-slug}}.json`);
  lines.push(`- Per-MP full markdown report: linked per MP below, or ${SITE_URL}/data/{{state-slug}}/reports/{{mp-slug}}.md`);
  lines.push(`- National leaderboard (JSON): ${SITE_URL}/data/national/leaderboard/latest.json`);
  lines.push(`- State leaderboards (JSON): ${SITE_URL}/data/{{state-slug}}/leaderboard/latest.json`);
  lines.push("");
  lines.push("## Methodology");
  lines.push("");
  lines.push(`- Scoring methodology and interpretation notes: ${SITE_URL.replace("/mp-transparency-tracker", "")}/mp-transparency-tracker/national`);
  lines.push("");
  lines.push("## MP reports (by transparency score)");
  lines.push("");
  for (const m of byScore) {
    lines.push(
      `- [${m.mpName} — ${m.constituency}, ${m.state} (${m.party}, score ${m.compositeScore})](${SITE_URL}${m.reportPath}): profile at ${SITE_URL}${m.profilePath}`
    );
  }
  lines.push("");
  fs.writeFileSync(path.join(PUBLIC_DIR, "llms.txt"), lines.join("\n"));
}


/** Build the rich per-MP comparison index used by the /compare page.
 * Joins leaderboard entries with validated findings (raw metrics) so the
 * client can render a head-to-head beyond composite scores. */
function buildCompareIndex() {
  const stateDirs = fs
    .readdirSync(DATA_DIR, { withFileTypes: true })
    .filter((d) => d.isDirectory() && d.name !== "national" && d.name !== "enrichment")
    .map((d) => d.name)
    .sort();

  const mps = [];
  for (const stateSlug of stateDirs) {
    const lb = readJSON(path.join(DATA_DIR, stateSlug, "leaderboard", "latest.json"));
    if (!lb) continue;
    for (const e of lb.entries) {
      const mpSlug = entryToSlug(e.mp_name);
      // Slugs can differ from entryToSlug for suffixed LS/RS collisions; the
      // score file name is authoritative.
      let slug = mpSlug;
      if (!fs.existsSync(path.join(DATA_DIR, stateSlug, "scores", slug + ".json"))) {
        const scoresDir = path.join(DATA_DIR, stateSlug, "scores");
        const alt = fs.existsSync(scoresDir)
          ? fs.readdirSync(scoresDir).find((f) => f.startsWith(mpSlug) && f.endsWith(".json"))
          : null;
        if (alt) slug = alt.replace(/\.json$/, "");
      }
      const v = readJSON(path.join(DATA_DIR, stateSlug, "raw", slug + "_validated.json"));
      const f = v?.findings ?? {};
      const pa = f.parliament_activity ?? {};
      const cr = f.criminal_record ?? {};
      const as = f.assets ?? {};
      const mp = f.mplads ?? {};
      const cm = f.committees ?? {};
      const lg = f.legislative ?? {};
      const sm = f.social_media ?? {};
      const isRS = (e.house ?? "lok_sabha") === "rajya_sabha";
      mps.push({
        mpName: e.mp_name,
        constituency: e.constituency,
        party: e.party,
        state: displayState(stateSlug),
        stateSlug,
        mpSlug: slug,
        house: e.house ?? "lok_sabha",
        photoUrl: e.photo_url ?? null,
        compositeScore: e.composite_score,
        isMinister: !!pa.is_minister,
        estimated: {
          // Scorer falls back to a neutral sentinel value when the underlying
          // metric is missing. Flag every dimension sitting on a sentinel so
          // the UI renders the muted estimated treatment and never lets a
          // placeholder win a compare row.
          attendance: pa.attendance_percentage == null,
          participation:
            !!pa.is_minister &&
            (pa.questions_asked ?? 0) === 0 &&
            (pa.debates_participated ?? 0) === 0,
          mplads: !isRS && mp.entitled == null && mp.released == null,
          assets: as.total_assets == null,
          criminal:
            cr.total_cases == null ||
            ((cr.total_cases ?? 0) === 0 && (cr.confidence ?? 0) < 0.5),
          committee:
            (cm.total_committees ?? 0) === 0 && (cm.confidence ?? 0) < 0.3,
          legislative:
            (lg.private_member_bills ?? 0) === 0 &&
            (lg.zero_hour_mentions ?? 0) === 0 &&
            (lg.confidence ?? 0) < 0.3,
          accessibility:
            (sm.total_platforms ?? 0) === 0 && (sm.confidence ?? 0) < 0.3,
        },
        notApplicable: {
          // MPLADS is a Lok Sabha constituency scheme; Rajya Sabha members
          // have no MPLADS record, so the dimension is N/A (not "estimated").
          mplads: isRS,
        },
        dimensionScores: {
          mplads_score: e.mplads_score,
          asset_score: e.asset_score,
          criminal_score: e.criminal_score,
          attendance_score: e.attendance_score,
          participation_score: e.participation_score,
          committee_score: e.committee_score,
          accessibility_score: e.accessibility_score,
          legislative_score: e.legislative_score,
        },
        metrics: {
          attendancePct: pa.attendance_percentage ?? null,
          questionsAsked: pa.questions_asked ?? null,
          debatesParticipated: pa.debates_participated ?? null,
          privateBills: pa.private_bills_introduced ?? null,
          criminalCases: cr.total_cases ?? null,
          seriousCases: cr.serious_cases ?? null,
          totalAssets: as.total_assets ?? null,
          mpladsEntitled: mp.entitled ?? null,
          mpladsReleased: mp.released ?? null,
          mpladsSanctioned: mp.sanctioned ?? null,
          mpladsExpended: mp.expended ?? null,
          mpladsUtilization: mp.utilization_rate ?? null,
          worksCount: mp.works_count ?? (mp.works ? mp.works.length : null),
        },
      });
    }
  }
  return mps;
}

function writeCompareIndex(mps) {
  fs.writeFileSync(
    path.join(PUBLIC_DIR, "data", "compare-index.json"),
    JSON.stringify({ count: mps.length, mps }, null, 0)
  );
}

// ---- run ----
const mirrored = mirrorData();
const mps = buildIndex();
writeSearchIndex(mps);
writeRobots();
const urlCount = writeSitemap(mps);
writeLlmsTxt(mps);
const cmp = buildCompareIndex();
writeCompareIndex(cmp);
console.log(
  `prepare-agent-assets: mirrored ${mirrored} data files, indexed ${mps.length} MPs, compare index: ${cmp.length} MPs, sitemap URLs: ${urlCount}`
);

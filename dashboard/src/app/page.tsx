import Link from "next/link";
import { getAllStates, getNationalStats, getPartyStats } from "@/lib/data";
import { getAllMPEntries } from "@/lib/search";
import { SearchBar } from "@/components/SearchBar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ColorLegend } from "@/components/ColorLegend";
import { ScoreBadge } from "@/components/ScoreBadge";
import { StateSelector } from "@/components/StateSelector";
import { ClientIndiaMap } from "@/components/ClientIndiaMap";
import { formatScore } from "@/lib/format";
import { getScoreColor } from "@/lib/colors";
import { publicPath } from "@/lib/paths";
import type { LeaderboardEntry } from "@/lib/types";
import { entryToSlug, displayStateFromSlug } from "@/lib/slug";

function stateToSlug(state: string): string {
	return state
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "-")
		.replace(/^-|-$/g, "");
}

function profileHref(mp: LeaderboardEntry): string {
	return `/state/${stateToSlug(mp.state)}/mp/${entryToSlug(mp)}`;
}

function riskReasons(mp: LeaderboardEntry): string[] {
	const reasons: string[] = [];
	if (mp.criminal_score <= 50) reasons.push("Criminal red flag");
	if (mp.attendance_score <= 50) reasons.push("Low attendance");
	if (mp.participation_score <= 30) reasons.push("Low participation");
	if (mp.committee_score <= 10) reasons.push("Weak committees");
	if (mp.composite_score <= 40) reasons.push("Low score");
	return reasons.slice(0, 2);
}

function riskScore(mp: LeaderboardEntry): number {
	return Math.round(
		(100 - mp.composite_score) * 0.35 +
			(100 - mp.criminal_score) * 0.25 +
			(100 - mp.attendance_score) * 0.15 +
			(100 - mp.participation_score) * 0.15 +
			(100 - mp.committee_score) * 0.1
	);
}

function FlashyMPLink({ mp, rank, variant }: { mp: LeaderboardEntry; rank: number; variant: "best" | "risk" }) {
	const isRisk = variant === "risk";
	const reasons = riskReasons(mp);

	return (
		<Link
			href={profileHref(mp)}
			className={`group relative block overflow-hidden border-3 border-ink p-3 shadow-brutal-sm brutal-press transition-all hover:-translate-y-0.5 hover:shadow-brutal ${
				isRisk
					? "bg-gradient-to-r from-red-100 via-orange-100 to-yellow-100 hover:bg-danger/10"
					: "bg-gradient-to-r from-emerald-100 via-lime-100 to-yellow-100 hover:bg-highlight"
			}`}
		>
			<div className="absolute -right-5 -top-5 h-16 w-16 rotate-12 border-3 border-ink bg-accent opacity-70 transition-transform group-hover:scale-125" />
			{isRisk && (
				<div className="absolute right-1 top-1 rotate-6 border-2 border-ink bg-danger px-1.5 py-0.5 text-[10px] font-black uppercase text-white shadow-brutal-sm">
					Red Flag
				</div>
			)}

			<div className="relative flex items-center gap-3">
				<div
					className={`flex h-10 w-10 shrink-0 items-center justify-center border-3 border-ink font-mono text-lg font-black shadow-brutal-sm ${
						isRisk ? "bg-danger text-white" : "bg-success text-white"
					}`}
				>
					(#{rank})
				</div>

				{mp.photo_url ? (
					<img
						src={publicPath(mp.photo_url)}
						alt={mp.mp_name}
						className="h-12 w-12 shrink-0 rounded-full border-3 border-ink object-cover shadow-brutal-sm"
					/>
				) : (
					<div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border-3 border-ink bg-highlight font-black">
						{mp.mp_name.charAt(0)}
					</div>
				)}

				<div className="min-w-0 flex-1">
					<div className="truncate text-sm font-black uppercase text-ink group-hover:underline">
						{mp.mp_name}
					</div>
					<div className="truncate text-xs font-bold text-text-secondary">
						{mp.constituency}, {displayStateFromSlug(stateToSlug(mp.state))}
					</div>
					{isRisk ? (
						<div className="mt-1 flex flex-wrap gap-1">
							{reasons.length > 0 ? (
								reasons.map((reason) => (
									<span
										key={reason}
										className="border border-ink bg-white px-1 text-[10px] font-black uppercase text-danger"
									>
										{reason}
									</span>
								))
							) : (
								<span className="border border-ink bg-white px-1 text-[10px] font-black uppercase text-danger">
									Scrutiny needed
								</span>
							)}
						</div>
					) : (
						<div className="mt-1 text-[10px] font-black uppercase tracking-wide text-success">
							Click to inspect full profile →
						</div>
					)}
				</div>

				<div className="text-right">
					{isRisk ? (
						<>
							<div className="font-mono text-xl font-black text-danger">
								{riskScore(mp)}
							</div>
							<div className="text-[10px] font-black uppercase text-text-muted">
								Risk
							</div>
						</>
					) : (
						<ScoreBadge score={mp.composite_score} size="sm" />
					)}
				</div>
			</div>
		</Link>
	);
}

function DimensionBar({ label, score, weight, context }: { label: string; score: number; weight: string; context?: string }) {
	const color = getScoreColor(score);
	return (
		<div className="space-y-1">
			<div className="flex items-center justify-between">
				<span className="text-xs font-bold uppercase text-ink">{label}</span>
				<span className="font-mono text-xs font-black" style={{ color }}>{formatScore(score)}</span>
			</div>
			<div className="h-2.5 bg-gray-100 border border-ink overflow-hidden">
				<div className="h-full transition-all" style={{ width: `${score}%`, backgroundColor: color }} />
			</div>
			<div className="flex items-center justify-between">
				<div className="text-[10px] font-mono text-text-muted">Weight: {weight}</div>
				{context && <div className="text-[10px] text-text-secondary">{context}</div>}
			</div>
		</div>
	);
}

export default function HomePage() {
	const states = getAllStates();
	const stats = getNationalStats();
	const partyStats = getPartyStats();
	const allEntries = getAllMPEntries();
	const topMPs = stats.topMPs;
	const redFlagMPs = [...stats.bottomMPs]
		.sort((a, b) => riskScore(b) - riskScore(a))
		.slice(0, 5);

	const lowCommittee = Math.round((stats.mpsWithNoCommittee / stats.totalMPs) * 100);
	const lowAccessibility = Math.round((stats.mpsWithInaccessible / stats.totalMPs) * 100);
	const lowMplads = stats.mpsWithLowMplads;
	const mpsWithLowAttendance = stats.mpsWithLowAttendance;

	const poorOrCritical = stats.distribution.poor + stats.distribution.critical;
	const poorPct = Math.round((poorOrCritical / stats.totalMPs) * 100);
	const avgAttendance = Math.round(stats.dimensions.attendance);
	const avgParticipation = Math.round(stats.dimensions.participation);

	const topParty = [...partyStats]
		.filter((p) => p.mpCount >= 5)
		.sort((a, b) => b.avgScore - a.avgScore)[0];
	const worstParty = [...partyStats]
		.filter((p) => p.mpCount >= 5)
		.sort((a, b) => a.avgScore - b.avgScore)[0];

	return (
		<div className="space-y-8">
			{/* ════════════════════ HERO ════════════════════ */}
			<section className="relative overflow-hidden border-3 border-ink bg-surface p-6 shadow-brutal md:p-8">
				<div className="absolute -right-12 -top-12 h-48 w-48 rounded-full bg-danger/20 blur-3xl" />
				<div className="absolute left-1/3 top-1/2 h-32 w-32 rounded-full bg-warning/15 blur-3xl" />

				<div className="relative z-10">
					<div className="flex flex-col items-start justify-between gap-6 md:flex-row md:items-center">
						<div className="max-w-2xl">
							<div className="mb-3 inline-flex items-center gap-2 border-2 border-danger bg-danger/10 px-2 py-1 text-[10px] font-black uppercase tracking-[0.15em] text-danger shadow-brutal-sm">
								<span className="animate-pulse">●</span> Investigative Dashboard — {stats.totalMPs} MPs Scored
							</div>
							<h1 className="mt-2 text-3xl font-black uppercase tracking-tight text-ink md:text-4xl lg:text-5xl">
								Your MP Took Your Vote.
								<span className="block bg-gradient-to-r from-danger via-warning to-danger bg-clip-text text-transparent">
									Here&apos;s What They Did With It.
								</span>
							</h1>
							<p className="mt-3 max-w-lg text-sm text-text-secondary md:text-base leading-relaxed">
								You voted for them. You trusted them. Now see what they actually delivered.{" "}
								<strong className="text-danger">{stats.totalMPs - (stats.distribution.good + stats.distribution.excellent)} out of {stats.totalMPs} MPs scored below 60.</strong>{" "}
								The average is just {formatScore(stats.avgScore)} — barely passing for elected representatives.
							</p>

						<div className="mt-5 flex flex-wrap items-center gap-3">
							<Link
								href="/national"
								className="border-3 border-ink bg-danger px-4 py-2 text-sm font-black uppercase tracking-wider text-white shadow-brutal-sm brutal-press transition-all hover:-translate-y-0.5 hover:shadow-brutal hover:bg-danger/90"
							>
								📊 See The Full Picture
							</Link>
							<Link
								href="/compare"
								className="border-3 border-ink bg-surface px-4 py-2 text-sm font-black uppercase tracking-wider text-ink shadow-brutal-sm brutal-press transition-all hover:-translate-y-0.5 hover:shadow-brutal hover:bg-highlight"
							>
								⚡ Compare Any Two MPs
							</Link>
						</div>

						{/* Constituency lookup: "I am from this district" */}
						<div className="mt-5 max-w-md">
							<label className="mb-1 block text-[10px] font-black uppercase tracking-[0.15em] text-text-muted">
								Find your MP — search your district, constituency or MP name
							</label>
							<SearchBar allEntries={allEntries} />
						</div>
						</div>

						<div className="flex flex-wrap gap-3">
							<div className="flex flex-col items-center whitespace-nowrap border-3 border-ink bg-surface px-4 py-3 shadow-brutal-sm">
								<span className="text-2xl font-mono font-black text-danger">{poorPct}%</span>
								<span className="text-[10px] font-bold uppercase tracking-wide text-text-muted">Failing MPs</span>
							</div>
							<div className="flex flex-col items-center whitespace-nowrap border-3 border-ink bg-surface px-4 py-3 shadow-brutal-sm">
								<span
									className="text-2xl font-mono font-black"
									style={{ color: getScoreColor(stats.avgScore) }}
								>
									{formatScore(stats.avgScore)}
								</span>
								<span className="text-[10px] font-bold uppercase tracking-wide text-text-muted">Avg Score</span>
							</div>
							<div className="flex flex-col items-center whitespace-nowrap border-3 border-ink bg-surface px-4 py-3 shadow-brutal-sm">
								<span className="text-2xl font-mono font-black text-danger">{stats.distribution.excellent}</span>
								<span className="text-[10px] font-bold uppercase tracking-wide text-text-muted">Excellent MPs</span>
							</div>
						</div>
					</div>
				</div>
			</section>

			{/* ════════════════════ THE VERDICT ════════════════════ */}
			<section className="border-3 border-ink bg-surface p-6 shadow-brutal">
				<div className="mb-6">
					<div className="inline-flex border-2 border-danger bg-danger/10 px-2 py-1 text-[10px] font-black uppercase tracking-[0.15em] text-danger">
						The Verdict
					</div>
					<h2 className="mt-3 text-2xl font-black uppercase tracking-tight text-ink md:text-3xl">
						The Numbers Don&apos;t Lie
					</h2>
					<p className="mt-2 max-w-2xl text-sm text-text-secondary">
						These aren&apos;t opinions — they&apos;re patterns in the data. Every number below
						represents real MPs who were elected to serve you.
					</p>
				</div>

				<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
					<div className="border-3 border-ink bg-white p-5 shadow-brutal-sm text-center">
						<div className="font-mono text-4xl font-black text-danger">{stats.mpsWithLowParticipation}</div>
						<div className="text-sm font-black uppercase text-ink mt-2">MPs Barely Show Up</div>
						<p className="text-xs text-text-secondary mt-2 leading-relaxed">
							They took your vote but rarely speak, ask questions, or participate in debates.
							They collect a salary but don&apos;t do the job.
						</p>
					</div>
					<div className="border-3 border-ink bg-white p-5 shadow-brutal-sm text-center">
						<div className="font-mono text-4xl font-black text-danger">{lowMplads}</div>
						<div className="text-sm font-black uppercase text-ink mt-2">MPs Waste Your Money</div>
						<p className="text-xs text-text-secondary mt-2 leading-relaxed">
							Two-thirds of MPs have no MPLADS fund data available — making accountability
							impossible. That&apos;s your constituency&apos;s development money — for roads,
							schools, hospitals — with no public record of how it was spent.
						</p>
					</div>
					<div className="border-3 border-ink bg-white p-5 shadow-brutal-sm text-center">
						<div className="font-mono text-4xl font-black text-danger">{stats.mpsWithCriminalFlags}</div>
						<div className="text-sm font-black uppercase text-ink mt-2">MPs With Criminal Flags</div>
						<p className="text-xs text-text-secondary mt-2 leading-relaxed">
							MPs with serious criminal cases — including charges like murder, theft, and corruption —
							are making laws that affect your life.
						</p>
					</div>
				</div>
			</section>

			{/* ════════════════════ ACCOUNTABILITY GAP ════════════════════ */}
			<section className="relative overflow-hidden border-3 border-ink bg-ink p-6 shadow-brutal md:p-8">
				<div className="absolute -left-12 -bottom-12 h-48 w-48 rounded-full bg-danger/20 blur-3xl" />
				<div className="relative z-10">
					<div className="inline-flex border-2 border-danger bg-danger/10 px-2 py-1 text-[10px] font-black uppercase tracking-[0.15em] text-danger">
						The Accountability Gap
					</div>
					<h2 className="mt-3 text-2xl font-black uppercase tracking-tight text-surface md:text-3xl">
						They Get Paid. You Get Nothing.
					</h2>
					<p className="mt-2 max-w-2xl text-sm text-surface/70">
						Every MP earns over ₹1.6 lakh per month plus allowances — paid from your taxes.
						Here&apos;s what they give you in return.
					</p>

					<div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
						<div className="border-2 border-surface/30 bg-surface/5 p-4 text-center">
							<div className="font-mono text-2xl font-black text-surface">₹20L+</div>
							<div className="text-[10px] font-bold uppercase text-surface/60 mt-1">Annual MP Salary</div>
							<div className="text-[10px] text-surface/40 mt-1">Plus allowances & perks</div>
						</div>
						<div className="border-2 border-danger/50 bg-danger/10 p-4 text-center">
							<div className="font-mono text-2xl font-black text-danger">{avgAttendance}%</div>
							<div className="text-[10px] font-bold uppercase text-surface/60 mt-1">Avg Attendance</div>
							<div className="text-[10px] text-danger mt-1">{mpsWithLowAttendance} MPs attend less than half the sessions</div>
						</div>
						<div className="border-2 border-danger/50 bg-danger/10 p-4 text-center">
							<div className="font-mono text-2xl font-black text-danger">{avgParticipation}%</div>
							<div className="text-[10px] font-bold uppercase text-surface/60 mt-1">Avg Participation</div>
							<div className="text-[10px] text-danger mt-1">Avg participation is {avgParticipation}% — most rarely speak</div>
						</div>
						<div className="border-2 border-danger/50 bg-danger/10 p-4 text-center">
							<div className="font-mono text-2xl font-black text-danger">{lowCommittee}%</div>
							<div className="text-[10px] font-bold uppercase text-surface/60 mt-1">Zero Committee Work</div>
							<div className="text-[10px] text-danger mt-1">{lowCommittee}% with confirmed data have zero committees</div>
						</div>
					</div>

					<div className="mt-6 border-2 border-danger/50 bg-danger/10 p-4">
						<div className="text-xs font-black uppercase text-danger mb-1">The Hard Truth</div>
						<p className="text-sm text-surface/90 leading-relaxed">
							You pay them to attend Parliament, ask questions, scrutinize bills, and spend
							constituency funds. Most are failing at every single one of these basic duties.
							This isn&apos;t about left or right — it&apos;s about representatives who aren&apos;t representing.
						</p>
					</div>
				</div>
			</section>

			{/* ════════════════════ WHAT'S WRONG ════════════════════ */}
			<section className="border-3 border-ink bg-surface p-6 shadow-brutal">
				<div className="mb-6">
					<div className="inline-flex border-2 border-danger bg-danger/10 px-2 py-1 text-[10px] font-black uppercase tracking-[0.15em] text-danger">
						Systemic Failures
					</div>
					<h2 className="mt-3 text-2xl font-black uppercase tracking-tight text-ink md:text-3xl">
						What&apos;s Broken — And Who Broke It
					</h2>
					<p className="mt-2 max-w-2xl text-sm text-text-secondary">
						These aren&apos;t isolated incidents — they&apos;re systemic failures that affect every
						constituency in India. Your MP is part of this system.
					</p>
				</div>

				<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
					<div className="border-3 border-ink bg-white p-5 shadow-brutal-sm">
						<div className="flex items-start gap-4">
							<div className="flex h-12 w-12 shrink-0 items-center justify-center border-3 border-ink bg-danger text-2xl text-white shadow-brutal-sm">
								🏛️
							</div>
							<div>
								<div className="font-mono text-2xl font-black text-danger">{lowCommittee}%</div>
								<div className="text-sm font-black uppercase text-ink mt-1">Parliamentary Committees: Ghost Towns</div>
								<p className="text-xs text-text-secondary mt-2 leading-relaxed">
									Committees are where bills get scrutinized, budgets examined, and government
									accounts audited. {lowCommittee}% of MPs sit on zero committees. They&apos;re not doing
									the detailed legislative work they were sent to do. Without committee oversight,
									bad laws pass unchecked.
								</p>
							</div>
						</div>
					</div>

					<div className="border-3 border-ink bg-white p-5 shadow-brutal-sm">
						<div className="flex items-start gap-4">
							<div className="flex h-12 w-12 shrink-0 items-center justify-center border-3 border-ink bg-danger text-2xl text-white shadow-brutal-sm">
								💰
							</div>
							<div>
								<div className="font-mono text-2xl font-black text-danger">{lowMplads}</div>
								<div className="text-sm font-black uppercase text-ink mt-1">Your Development Money: Wasted</div>
								<p className="text-xs text-text-secondary mt-2 leading-relaxed">
									MPLADS gives each MP ₹5 crore per year for constituency development — roads,
									schools, hospitals, water supply. {lowMplads} MPs have no fund utilization data
									available, making it impossible to track how this public money was spent.
									Without transparency, accountability is just a word.
								</p>
							</div>
						</div>
					</div>

					<div className="border-3 border-ink bg-white p-5 shadow-brutal-sm">
						<div className="flex items-start gap-4">
							<div className="flex h-12 w-12 shrink-0 items-center justify-center border-3 border-ink bg-danger text-2xl text-white shadow-brutal-sm">
								📱
							</div>
							<div>
								<div className="font-mono text-2xl font-black text-danger">{lowAccessibility}%</div>
								<div className="text-sm font-black uppercase text-ink mt-1">Inaccessible: They Don&apos;t Want To Be Found</div>
								<p className="text-xs text-text-secondary mt-2 leading-relaxed">
									Almost no MP maintains a meaningful public digital presence. They don&apos;t publish
									their attendance, spending, or positions on issues. If you can&apos;t find them,
									you can&apos;t hold them accountable. That&apos;s the point.
								</p>
							</div>
						</div>
					</div>

					<div className="border-3 border-ink bg-white p-5 shadow-brutal-sm">
						<div className="flex items-start gap-4">
							<div className="flex h-12 w-12 shrink-0 items-center justify-center border-3 border-ink bg-danger text-2xl text-white shadow-brutal-sm">
								📋
							</div>
							<div>
								<div className="font-mono text-2xl font-black text-danger">{stats.mpsWithLowParticipation}</div>
								<div className="text-sm font-black uppercase text-ink mt-1">Silent MPs: They Take Salary, Not Action</div>
								<p className="text-xs text-text-secondary mt-2 leading-relaxed">
									Dozens of MPs rarely speak, ask questions, or participate in debates. They show up
									to collect their salary and allowances but disappear when it&apos;s time to fight for
									your constituency. Your voice goes unrepresented.
								</p>
							</div>
						</div>
					</div>
				</div>
			</section>

			{/* ════════════════════ THE NUMBERS ════════════════════ */}
			<section className="border-3 border-ink bg-surface p-6 shadow-brutal">
				<div className="mb-6">
					<div className="inline-flex border-2 border-ink bg-ink px-2 py-1 text-[10px] font-black uppercase tracking-[0.15em] text-surface">
						By The Numbers
					</div>
					<h2 className="mt-3 text-2xl font-black uppercase tracking-tight text-ink md:text-3xl">
						The Scorecard Is Clear
					</h2>
				</div>

				<div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
					<div className="border-3 border-ink bg-white p-4 shadow-brutal-sm text-center">
						<div className="font-mono text-3xl font-black text-danger">{stats.distribution.excellent + stats.distribution.good}</div>
						<div className="text-xs font-bold uppercase text-text-muted mt-1">Good or Better MPs</div>
						<div className="text-[10px] text-danger font-black mt-1">Out of {stats.totalMPs}</div>
					</div>
					<div className="border-3 border-ink bg-white p-4 shadow-brutal-sm text-center">
						<div className="font-mono text-3xl font-black text-warning">{stats.distribution.average}</div>
						<div className="text-xs font-bold uppercase text-text-muted mt-1">Average MPs</div>
						<div className="text-[10px] text-warning font-black mt-1">Score 40-59</div>
					</div>
					<div className="border-3 border-ink bg-white p-4 shadow-brutal-sm text-center">
						<div className="font-mono text-3xl font-black text-danger">{poorOrCritical}</div>
						<div className="text-xs font-bold uppercase text-text-muted mt-1">Poor or Critical</div>
						<div className="text-[10px] text-danger font-black mt-1">Score below 40</div>
					</div>
					<div className="border-3 border-ink bg-white p-4 shadow-brutal-sm text-center">
						<div className="font-mono text-3xl font-black text-danger">{stats.mpsWithCriminalFlags}</div>
						<div className="text-xs font-bold uppercase text-text-muted mt-1">Criminal Red Flags</div>
						<div className="text-[10px] text-danger font-black mt-1">Serious concerns</div>
					</div>
				</div>

				<div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
					<div>
						<h3 className="text-sm font-black uppercase text-ink mb-3">How We Measure</h3>
						<div className="space-y-3">
							<DimensionBar label="MPLADS Utilization" score={stats.dimensions.mplads} weight="20%" context="Are they spending your constituency money?" />
							<DimensionBar label="Asset Transparency" score={stats.dimensions.assets} weight="15%" context="Did their wealth grow suspiciously?" />
							<DimensionBar label="Criminal Record" score={stats.dimensions.criminal} weight="20%" context="Do they have serious criminal cases?" />
							<DimensionBar label="Parliament Attendance" score={stats.dimensions.attendance} weight="15%" context="Do they actually show up?" />
							<DimensionBar label="Participation" score={stats.dimensions.participation} weight="10%" context="Do they speak and ask questions?" />
							<DimensionBar label="Committee Work" score={stats.dimensions.committee} weight="5%" context="Do they do the hard scrutiny work?" />
							<DimensionBar label="Legislative Activity" score={stats.dimensions.legislative} weight="10%" context="Do they introduce bills and raise issues?" />
							<DimensionBar label="Public Accessibility" score={stats.dimensions.accessibility} weight="5%" context="Can you actually reach them?" />
						</div>
					</div>
					<div>
						<h3 className="text-sm font-black uppercase text-ink mb-3">Score Distribution</h3>
						<div className="space-y-2">
							{[
								{ label: "Excellent (80-100)", count: stats.distribution.excellent, color: "#059669" },
								{ label: "Good (60-79)", count: stats.distribution.good, color: "#00C853" },
								{ label: "Average (40-59)", count: stats.distribution.average, color: "#FFAB00" },
								{ label: "Poor (20-39)", count: stats.distribution.poor, color: "#FF3D00" },
								{ label: "Critical (0-19)", count: stats.distribution.critical, color: "#FF1744" },
							].map((bucket) => (
								<div key={bucket.label} className="flex items-center gap-3">
									<div className="w-40 text-xs font-bold text-ink">{bucket.label}</div>
									<div className="flex-1 h-6 bg-gray-50 border border-ink overflow-hidden">
										<div
											className="h-full flex items-center pl-2"
											style={{
												width: `${Math.max(2, (bucket.count / stats.totalMPs) * 100)}%`,
												backgroundColor: bucket.color,
											}}
										>
											{bucket.count > 0 && (
												<span className="font-mono text-[10px] font-black text-white">{bucket.count}</span>
											)}
										</div>
									</div>
									<div className="w-12 text-right font-mono text-xs font-black text-ink">
										{Math.round((bucket.count / stats.totalMPs) * 100)}%
									</div>
								</div>
							))}
						</div>

						<div className="mt-6 border-2 border-danger bg-danger/5 p-4">
							<div className="text-xs font-black uppercase text-danger mb-1">The Bottom Line</div>
							<p className="text-sm text-ink leading-relaxed">
								Only {stats.distribution.good + stats.distribution.excellent} out of {stats.totalMPs} MPs scored 60 or above.
								The average is {formatScore(stats.avgScore)} — below passing for elected representatives.
								Your elected representatives are not meeting basic standards of governance.
							</p>
						</div>
					</div>
				</div>
			</section>

			{/* ════════════════════ MAP + SELECTOR + LEGEND ════════════════════  */}
			<section className="grid grid-cols-1 lg:grid-cols-4 gap-6">
				<div className="lg:col-span-3">
					<Card>
						<CardHeader>
							<div className="flex items-center justify-between">
								<CardTitle>Transparency Map</CardTitle>
								<StateSelector states={states} className="w-64" />
							</div>
						</CardHeader>
						<CardContent>
							<ClientIndiaMap states={states} />
							<ColorLegend className="mt-4 max-w-sm mx-auto" />
						</CardContent>
					</Card>
				</div>

				<div className="space-y-6">
					<Card>
						<CardHeader>
							<CardTitle>Explore by State</CardTitle>
						</CardHeader>
						<CardContent>
							<div className="flex flex-wrap gap-2">
								{states
									.filter((s) => s.hasData)
									.map((s) => (
										<Link
											key={s.slug}
											href={`/state/${s.slug}`}
											className="border-2 border-ink bg-surface px-2 py-1 text-xs font-bold uppercase text-ink shadow-brutal-sm brutal-press transition-all hover:-translate-y-0.5 hover:shadow-brutal hover:bg-highlight"
										>
											{s.displayName}
											<span className="ml-1 text-text-muted normal-case">{s.mpCount}</span>
										</Link>
									))}
							</div>
						</CardContent>
					</Card>

					<Card>
						<CardHeader>
							<CardTitle>Explore by Party</CardTitle>
						</CardHeader>
						<CardContent>
							<div className="flex flex-wrap gap-2">
								{partyStats
									.filter((p) => p.mpCount >= 2)
									.sort((a, b) => b.mpCount - a.mpCount)
									.slice(0, 12)
									.map((p) => {
										const slug = p.name
											.toLowerCase()
											.replace(/[^a-z0-9]+/g, "-")
											.replace(/^-|-$/g, "");
										return (
											<Link
												key={p.name}
												href={`/party/${slug}`}
												className="border-2 border-ink bg-surface px-2 py-1 text-xs font-bold uppercase text-ink shadow-brutal-sm brutal-press transition-all hover:-translate-y-0.5 hover:shadow-brutal hover:bg-highlight"
											>
												{p.name}
												<span className="ml-1 text-text-muted normal-case">{p.mpCount}</span>
											</Link>
										);
									})}
							</div>
						</CardContent>
					</Card>
				</div>
			</section>

			{/* ════════════════════ TOP / RISK MPs TWO-COL ════════════  */}
			<section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
				{/* Top MPs */}
				<Card className="bg-emerald-50">
					<CardHeader>
						<div className="flex items-center justify-between">
							<div>
								<CardTitle>Top Performing MPs</CardTitle>
								<p className="mt-1 text-xs font-bold uppercase tracking-wide text-success">
									Best of a bad situation — highest scores nationwide
								</p>
							</div>
							<Link
								href="/national"
								className="border-2 border-ink bg-surface px-2 py-1 text-xs font-black uppercase text-ink shadow-brutal-sm brutal-press hover:-translate-y-0.5 hover:shadow-brutal"
							>
								View All
							</Link>
						</div>
					</CardHeader>
					<CardContent>
						<div className="space-y-3">
							{topMPs.map((mp, i) => (
								<FlashyMPLink
									key={`${mp.mp_name}-${mp.constituency}`}
									mp={mp}
									rank={i + 1}
									variant="best"
								/>
							))}
						</div>
					</CardContent>
				</Card>

				{/* Red Flag */}
				<Card className="bg-red-50">
					<CardHeader>
						<div className="flex items-center justify-between gap-3">
							<div>
								<CardTitle>Red Flag Watchlist</CardTitle>
								<p className="mt-1 text-xs font-bold uppercase tracking-wide text-danger">
									Lowest-scoring profiles to scrutinize first
								</p>
							</div>
							<span className="animate-pulse border-3 border-ink bg-danger px-2 py-1 text-xs font-black uppercase text-white shadow-brutal-sm">
								Hot
							</span>
						</div>
					</CardHeader>
					<CardContent>
						<div className="space-y-3">
							{redFlagMPs.map((mp, i) => (
								<FlashyMPLink
									key={`${mp.mp_name}-${mp.constituency}`}
									mp={mp}
									rank={i + 1}
									variant="risk"
								/>
							))}
						</div>
					</CardContent>
				</Card>
			</section>

			{/* ════════════════════ PARTY REPORT CARD ════════════════════ */}
			{topParty && worstParty && (
				<section className="border-3 border-ink bg-surface p-6 shadow-brutal">
					<div className="mb-6">
						<div className="inline-flex border-2 border-ink bg-ink px-2 py-1 text-[10px] font-black uppercase tracking-[0.15em] text-surface">
							Party Report Card
						</div>
						<h2 className="mt-3 text-2xl font-black uppercase tracking-tight text-ink md:text-3xl">
							No Party Deserves A Blank Cheque
						</h2>
						<p className="mt-2 max-w-2xl text-sm text-text-secondary">
							We scored every party&apos;s MPs across all dimensions. The results?
							None of them are delivering the governance you deserve.
						</p>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
						<div className="border-3 border-ink bg-white p-5 shadow-brutal-sm">
							<div className="text-[10px] font-black uppercase tracking-wide text-success mb-1">Highest Scoring Party</div>
							<div className="text-lg font-black uppercase text-ink">{topParty.name}</div>
							<div className="flex items-baseline gap-2 mt-2">
								<span className="font-mono text-3xl font-black" style={{ color: getScoreColor(topParty.avgScore) }}>
									{formatScore(topParty.avgScore)}
								</span>
								<span className="text-xs text-text-muted">/ 100 avg</span>
							</div>
							<div className="text-xs text-text-secondary mt-2">
								{topParty.mpCount} MPs scored · Still barely passing
							</div>
							<div className="mt-3 h-3 bg-gray-100 border border-ink overflow-hidden">
								<div
									className="h-full"
									style={{ width: `${topParty.avgScore}%`, backgroundColor: getScoreColor(topParty.avgScore) }}
								/>
							</div>
						</div>

						<div className="border-3 border-ink bg-white p-5 shadow-brutal-sm">
							<div className="text-[10px] font-black uppercase tracking-wide text-danger mb-1">Lowest Scoring Party</div>
							<div className="text-lg font-black uppercase text-ink">{worstParty.name}</div>
							<div className="flex items-baseline gap-2 mt-2">
								<span className="font-mono text-3xl font-black" style={{ color: getScoreColor(worstParty.avgScore) }}>
									{formatScore(worstParty.avgScore)}
								</span>
								<span className="text-xs text-text-muted">/ 100 avg</span>
							</div>
							<div className="text-xs text-text-secondary mt-2">
								{worstParty.mpCount} MPs scored · Deep in failing territory
							</div>
							<div className="mt-3 h-3 bg-gray-100 border border-ink overflow-hidden">
								<div
									className="h-full"
									style={{ width: `${worstParty.avgScore}%`, backgroundColor: getScoreColor(worstParty.avgScore) }}
								/>
							</div>
						</div>
					</div>

					<div className="mt-4 border-2 border-warning bg-warning/5 p-4">
						<div className="text-xs font-black uppercase text-warning mb-1">Don&apos;t Vote Party Blind</div>
						<p className="text-sm text-ink leading-relaxed">
							The gap between the best and worst party averages is only {formatScore(topParty.avgScore - worstParty.avgScore)} points.
							Neither side is producing representatives who meet basic accountability standards.
							vote for individuals who have a track record — not just party symbols.
						</p>
					</div>
				</section>
			)}

			{/* ════════════════════ WHY THIS MATTERS ════════════════════ */}
			<section className="border-3 border-ink bg-surface p-6 shadow-brutal">
				<div className="mb-6">
					<div className="inline-flex border-2 border-primary bg-primary/10 px-2 py-1 text-[10px] font-black uppercase tracking-[0.15em] text-primary">
						Your Right To Know
					</div>
					<h2 className="mt-3 text-2xl font-black uppercase tracking-tight text-ink md:text-3xl">
						Democracy Only Works If You Use It
					</h2>
				</div>

				<div className="grid grid-cols-1 md:grid-cols-3 gap-6">
					<div className="border-2 border-ink bg-white p-5 shadow-brutal-sm">
						<div className="text-4xl mb-3">🗳️</div>
						<h3 className="text-lg font-black uppercase text-ink mb-2">Before You Vote</h3>
						<p className="text-sm text-text-secondary leading-relaxed">
							Don&apos;t fall for campaign speeches and empty promises. Your MP&apos;s voting record,
							attendance, spending, and legislative work are all public data. Check what
							they actually did — not what they say they&apos;ll do. Every vote should be informed.
						</p>
					</div>
					<div className="border-2 border-ink bg-white p-5 shadow-brutal-sm">
						<div className="text-4xl mb-3">📢</div>
						<h3 className="text-lg font-black uppercase text-ink mb-2">Demand Answers</h3>
						<p className="text-sm text-text-secondary leading-relaxed">
							Under the Right to Information Act, you have a legal right to ask questions.
							Use our RTI templates to demand details about MPLADS spending, attendance records,
							and committee participation. Silence is not an answer — it&apos;s an admission.
						</p>
					</div>
					<div className="border-2 border-ink bg-white p-5 shadow-brutal-sm">
						<div className="text-4xl mb-3">🔍</div>
						<h3 className="text-lg font-black uppercase text-ink mb-2">Share The Data</h3>
						<p className="text-sm text-text-secondary leading-relaxed">
							Sunlight is the best disinfectant. Share these scores with your neighbors,
							family, and community groups. Post them on social media. Bring them to
							town halls. The more people know, the harder it is for politicians to hide
							behind rhetoric and identity politics.
						</p>
					</div>
				</div>
			</section>

			{/* ════════════════════ METHODOLOGY NOTE ════════════════════ */}
			<section className="border-2 border-ink bg-highlight p-4 shadow-brutal-sm">
				<div className="flex flex-col md:flex-row items-start gap-4">
					<div className="flex-1">
						<h3 className="text-sm font-black uppercase text-ink mb-1">How This Works</h3>
						<p className="text-xs text-text-secondary leading-relaxed">
							We collect public data from eSAKSHI, data.gov.in, MyNeta, PRS India, MPLADS portal,
							and Sansad records. Each MP is scored across 8 dimensions with weighted composite scoring.
							Every data point is evidence-graded. This is not opinion — it&apos;s a methodology applied equally
							to every MP, regardless of party, caste, or religion.
						</p>
					</div>
					<div className="flex items-center gap-2">
						<Link
							href="/national"
							className="border-2 border-ink bg-surface px-3 py-1.5 text-xs font-black uppercase text-ink shadow-brutal-sm brutal-press hover:-translate-y-0.5 hover:shadow-brutal hover:bg-white"
						>
							Full Methodology
						</Link>
						<Link
							href="/compare"
							className="border-2 border-ink bg-accent px-3 py-1.5 text-xs font-black uppercase text-ink shadow-brutal-sm brutal-press hover:-translate-y-0.5 hover:shadow-brutal"
						>
							Compare MPs
						</Link>
					</div>
				</div>
			</section>

			{/* ════════════════════ FOOTER CTA ════════════════════ */}
			<section className="text-center border-3 border-ink bg-ink p-8 shadow-brutal">
				<p className="text-sm font-bold uppercase tracking-wider text-surface/70">
					Enough reading. Start investigating.
				</p>
				<h3 className="mt-2 text-2xl font-black uppercase text-surface">
					Find Your MP. Check Their Score. Hold Them Accountable.
				</h3>
				<div className="mt-5 flex flex-wrap justify-center gap-3">
					<Link
						href="/national"
						className="border-3 border-surface bg-surface px-6 py-3 text-sm font-black uppercase tracking-wider text-ink shadow-brutal-sm brutal-press transition-all hover:-translate-y-0.5 hover:shadow-brutal hover:bg-highlight"
					>
						🏆 Full National Leaderboard ({stats.totalMPs} MPs)
					</Link>
					<Link
						href="/compare"
						className="border-3 border-accent bg-accent px-6 py-3 text-sm font-black uppercase tracking-wider text-ink shadow-brutal-sm brutal-press transition-all hover:-translate-y-0.5 hover:shadow-brutal hover:bg-accent/90"
					>
						⚡ Compare Any Two MPs
					</Link>
				</div>
				<p className="mt-4 text-[10px] font-mono text-surface/50">
					v3.1 · Open data · 8 dimensions · Evidence graded · Non-partisan
				</p>
			</section>
		</div>
	);
}

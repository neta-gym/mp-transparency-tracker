import Link from "next/link";
import { entryToSlug, getAllStates, getNationalStats, getPartyStats } from "@/lib/data";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ColorLegend } from "@/components/ColorLegend";
import { ScoreBadge } from "@/components/ScoreBadge";
import { StateSelector } from "@/components/StateSelector";
import { ClientIndiaMap } from "@/components/ClientIndiaMap";
import { formatScore } from "@/lib/format";
import { getScoreColor } from "@/lib/colors";
import { publicPath } from "@/lib/paths";
import type { LeaderboardEntry } from "@/lib/types";

function stateToSlug(state: string): string {
	return state
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "-")
		.replace(/^-|-$/g, "");
}

function displayState(state: string): string {
	return stateToSlug(state)
		.split("-")
		.map((word) => word.charAt(0).toUpperCase() + word.slice(1))
		.join(" ");
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
						{mp.constituency}, {displayState(mp.state)}
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

export default function HomePage() {
	const states = getAllStates();
	const stats = getNationalStats();
	const partyStats = getPartyStats();
	const topMPs = stats.topMPs;
	const redFlagMPs = [...stats.bottomMPs]
		.sort((a, b) => riskScore(b) - riskScore(a))
		.slice(0, 5);

	return (
		<div className="space-y-8">
			{/* ════════════════════ HERO ════════════════════ */}
			<section className="relative overflow-hidden border-3 border-ink bg-surface p-6 shadow-brutal md:p-8">
				<div className="absolute -right-12 -top-12 h-48 w-48 rounded-full bg-highlight/40 blur-3xl" />
				<div className="absolute left-1/3 top-1/2 h-32 w-32 rounded-full bg-accent/25 blur-3xl" />

				<div className="relative z-10">
					<div className="flex flex-col items-start justify-between gap-6 md:flex-row md:items-center">
						<div className="max-w-2xl">
							<div className="mb-3 inline-flex items-center gap-2 border-2 border-ink bg-highlight px-2 py-1 text-[10px] font-black uppercase tracking-[0.15em] text-ink shadow-brutal-sm">
								<span className="animate-pulse text-danger">●</span> Live Data — {stats.totalMPs} MPs
							</div>
							<h1 className="mt-2 text-3xl font-black uppercase tracking-tight text-ink md:text-4xl lg:text-5xl">
								India MP Transparency
								<span className="block bg-gradient-to-r from-danger via-warning to-success bg-clip-text text-transparent">
									Dashboard
								</span>
							</h1>
							<p className="mt-3 max-w-lg text-sm text-text-secondary md:text-base">
								Score every MP across 8 dimensions — criminal record, attendance,
								assets, MPLADS, participation, committees & more.
							</p>

							{/* CTA buttons */}
							<div className="mt-5 flex flex-wrap items-center gap-3">
								<Link
									href="/national"
									className="border-3 border-ink bg-ink px-4 py-2 text-sm font-black uppercase tracking-wider text-surface shadow-brutal-sm brutal-press transition-all hover:-translate-y-0.5 hover:shadow-brutal hover:bg-accent hover:text-ink"
								>
									📊 National Leaderboard
								</Link>
								<Link
									href="/compare"
									className="border-3 border-ink bg-surface px-4 py-2 text-sm font-black uppercase tracking-wider text-ink shadow-brutal-sm brutal-press transition-all hover:-translate-y-0.5 hover:shadow-brutal hover:bg-highlight"
								>
									⚡ Compare MPs
								</Link>
								<Link
									href="/national#parties"
									className="border-3 border-ink bg-surface px-4 py-2 text-sm font-black uppercase tracking-wider text-ink shadow-brutal-sm brutal-press transition-all hover:-translate-y-0.5 hover:shadow-brutal hover:bg-highlight"
								>
									🎯 Party Profiles
								</Link>
							</div>
						</div>

						{/* Key stat pills */}
						<div className="flex flex-wrap gap-3">
							<div className="flex flex-col items-center whitespace-nowrap border-3 border-ink bg-surface px-4 py-3 shadow-brutal-sm">
								<span className="text-2xl font-mono font-black text-ink">{stats.totalMPs}</span>
								<span className="text-[10px] font-bold uppercase tracking-wide text-text-muted">MPs</span>
							</div>
							<div className="flex flex-col items-center whitespace-nowrap border-3 border-ink bg-surface px-4 py-3 shadow-brutal-sm">
								<span className="text-2xl font-mono font-black text-ink">{stats.statesProcessed}/{stats.totalStates}</span>
								<span className="text-[10px] font-bold uppercase tracking-wide text-text-muted">States</span>
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

				{/* Quick-link sidebar: States and Parties */}
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

			{/* ══════════════ TOP / RISK MPs TWO-COL ════════════  */}
			<section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
				{/* Top MPs */}
				<Card className="bg-emerald-50">
					<CardHeader>
						<div className="flex items-center justify-between">
							<div>
								<CardTitle>Top Performing MPs</CardTitle>
								<p className="mt-1 text-xs font-bold uppercase tracking-wide text-success">
									Highest composite scores nationwide
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

			{/* ════════════════════ FOOTER CTA ════════════════════ */}
			<section className="text-center border-3 border-ink bg-surface p-8 shadow-brutal">
				<p className="text-sm font-bold uppercase tracking-wider text-text-muted">
					Want to dig deeper?
				</p>
				<div className="mt-3 flex flex-wrap justify-center gap-3">
					<Link
						href="/national"
						className="border-3 border-ink bg-ink px-6 py-3 text-sm font-black uppercase tracking-wider text-surface shadow-brutal-sm brutal-press transition-all hover:-translate-y-0.5 hover:shadow-brutal hover:bg-accent hover:text-ink"
					>
						🏆 Full National Leaderboard ({stats.totalMPs} MPs)
					</Link>
					<Link
						href="/compare"
						className="border-3 border-ink bg-accent px-6 py-3 text-sm font-black uppercase tracking-wider text-ink shadow-brutal-sm brutal-press transition-all hover:-translate-y-0.5 hover:shadow-brutal hover:bg-highlight"
					>
						⚡ Compare Any Two MPs
					</Link>
				</div>
				<p className="mt-4 text-[10px] font-mono text-text-muted">
					v3.0 · Open data · 8 dimensions · Evidence graded
				</p>
			</section>
		</div>
	);
}

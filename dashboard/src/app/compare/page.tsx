import { ComparisonView } from "@/components/ComparisonView";

export default function ComparePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold uppercase">Compare MPs</h1>
        <p className="text-text-secondary text-sm mt-1">
          Select 2-4 MPs for a head to head: scores, attendance, questions,
          debates, MPLADS funds, assets, and criminal record
        </p>
      </div>
      <ComparisonView />
    </div>
  );
}

import { getAllMPEntries } from "@/lib/search";
import { ComparisonView } from "@/components/ComparisonView";

export default function ComparePage() {
  const allEntries = getAllMPEntries();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold uppercase">Compare MPs</h1>
        <p className="text-text-secondary text-sm mt-1">
          Select 2-4 MPs to compare their transparency scores side by side
        </p>
      </div>
      <ComparisonView allEntries={allEntries} />
    </div>
  );
}

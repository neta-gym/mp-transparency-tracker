import { getAllMPEntries } from "@/lib/search";
import { SearchBar } from "./SearchBar";

/** Server component that loads all MP data and passes it to the client SearchBar */
export function SearchBarWrapper() {
  const allEntries = getAllMPEntries();
  return <SearchBar allEntries={allEntries} />;
}

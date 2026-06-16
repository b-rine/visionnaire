import axios from "axios";
import { useState } from "react";

interface SearchResult {
  id: string;
  filename: string;
}

export default function Search() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [failedIds, setFailedIds] = useState<Set<string>>(new Set());
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleImageError(id: string) {
    setFailedIds((prev) => new Set([...prev, id]));
  }

  async function handleSearch() {
    if (!query.trim()) return;
    setError(null);
    setSearching(true);
    try {
      const { data } = await axios.post<SearchResult[]>("/api/photos/search", {
        query,
      });
      setResults(data);
    } catch {
      setError("Search failed.");
    } finally {
      setSearching(false);
    }
  }

  return (
    <>
      <h1>Photo Search</h1>

      <section>
        <h2>Search by Description</h2>
        <div className="search-bar">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder='e.g. "sunset over mountains"'
          />
          <button onClick={handleSearch} disabled={searching}>
            {searching ? "Searching..." : "Search"}
          </button>
        </div>

        {results.length > 0 && (
          <div className="photo-grid">
            {results.filter((r) => !failedIds.has(r.id)).map((r) => (
              <div key={r.id} className="photo-tile">
                <img
                  src={`/api/photos/${r.id}`}
                  alt={r.filename}
                  onError={() => handleImageError(r.id)}
                />
              </div>
            ))}
          </div>
        )}

        {results.length === 0 && !searching && query && (
          <p className="loading">No results. Try indexing some photos first.</p>
        )}
      </section>

      {error && <p style={{ color: "red" }}>{error}</p>}
    </>
  );
}

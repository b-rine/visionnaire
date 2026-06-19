import axios from "axios";
import { useState } from "react";
import PhotoLightbox from "../components/PhotoLightbox";

interface SearchResult {
  id: string;
  filename: string;
  caption?: string;
  score: number;
}

export default function Search() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [failedIds, setFailedIds] = useState<Set<string>>(new Set());
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch() {
    if (!query.trim()) return;
    setError(null);
    setSearching(true);
    try {
      const { data } = await axios.post<SearchResult[]>("/api/photos/search", { query });
      setResults(data);
    } catch {
      setError("Search failed.");
    } finally {
      setSearching(false);
    }
  }

  async function handleDelete(id: string) {
    if (pendingDelete !== id) {
      setPendingDelete(id);
      setTimeout(() => setPendingDelete((prev) => (prev === id ? null : prev)), 3000);
      return;
    }
    setPendingDelete(null);
    setDeletingId(id);
    try {
      await axios.delete(`/api/photos/${id}`);
      setResults((prev) => prev.filter((r) => r.id !== id));
      setExpandedId((prev) => (prev === id ? null : prev));
    } catch {
      setError("Delete failed.");
    } finally {
      setDeletingId(null);
    }
  }

  function handleImageError(id: string) {
    setFailedIds((prev) => new Set([...prev, id]));
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
                  onClick={() => setExpandedId(r.id)}
                />
                <span className="score-badge" title="Match strength">
                  {(r.score * 100).toFixed(0)}%
                </span>
                <button
                  className="delete-btn"
                  onClick={() => handleDelete(r.id)}
                  disabled={deletingId === r.id}
                  title="Delete photo"
                >
                  {deletingId === r.id ? "..." : pendingDelete === r.id ? "Confirm?" : "✕"}
                </button>
              </div>
            ))}
          </div>
        )}

        {results.length === 0 && !searching && query && (
          <p className="loading">No results. Try indexing some photos first.</p>
        )}
      </section>

      {error && <p style={{ color: "red" }}>{error}</p>}

      {expandedId && results.some((r) => r.id === expandedId) && (
        <PhotoLightbox
          id={expandedId}
          filename={results.find((r) => r.id === expandedId)!.filename}
          caption={results.find((r) => r.id === expandedId)!.caption}
          score={results.find((r) => r.id === expandedId)!.score}
          pendingDelete={pendingDelete === expandedId}
          deleting={deletingId === expandedId}
          onDelete={() => handleDelete(expandedId)}
          onClose={() => setExpandedId(null)}
        />
      )}
    </>
  );
}

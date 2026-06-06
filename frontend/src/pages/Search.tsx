import axios from "axios";
import { useState } from "react";

interface SearchResult {
  id: string;
  filename: string;
  score: number;
}

export default function Search() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload(file: File) {
    setUploadMsg(null);
    setError(null);
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await axios.post<{ id: string; filename: string }>(
        "/api/photos/upload",
        fd
      );
      setUploadMsg(`Indexed: ${data.filename}`);
    } catch {
      setError("Upload failed. Is the backend running?");
    } finally {
      setUploading(false);
    }
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

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  }

  return (
    <>
      <h1>Photo Search</h1>

      <section>
        <h2>Index a Photo</h2>
        <label
          className="dropzone"
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
        >
          <input
            type="file"
            accept="image/*"
            hidden
            onChange={(e) =>
              e.target.files?.[0] && handleUpload(e.target.files[0])
            }
          />
          Drag & drop a photo to index, or click to browse
        </label>
        {uploading && <p className="loading">Indexing photo...</p>}
        {uploadMsg && <div className="status-msg">{uploadMsg}</div>}
      </section>

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
            {results.map((r) => (
              <div key={r.id} className="photo-tile">
                <img src={`/api/photos/${r.id}`} alt={r.filename} />
                <span className="score-badge">
                  {(r.score * 100).toFixed(0)}%
                </span>
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

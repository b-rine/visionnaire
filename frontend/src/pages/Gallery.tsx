import axios from "axios";
import { useEffect, useState } from "react";

interface Photo {
  id: string;
  filename: string;
  uploaded_at: string;
  file_size: number;
}

export default function Gallery() {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [failedIds, setFailedIds] = useState<Set<string>>(new Set());
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [nextOffset, setNextOffset] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadPage(offset: string | null) {
    setLoading(true);
    setError(null);
    try {
      const { data } = await axios.get<{ photos: Photo[]; next_offset: string | null }>(
        "/api/photos",
        { params: offset ? { offset } : {} }
      );
      setPhotos((prev) => (offset ? [...prev, ...data.photos] : data.photos));
      setNextOffset(data.next_offset);
    } catch {
      setError("Failed to load photos.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPage(null);
  }, []);

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
      setPhotos((prev) => prev.filter((p) => p.id !== id));
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
      <h1>Gallery</h1>

      {photos.length > 0 && (
        <div className="photo-grid">
          {photos.filter((p) => !failedIds.has(p.id)).map((p) => (
            <div key={p.id} className="photo-tile">
              <img
                src={`/api/photos/${p.id}`}
                alt={p.filename}
                onError={() => handleImageError(p.id)}
              />
              <button
                className="delete-btn"
                onClick={() => handleDelete(p.id)}
                disabled={deletingId === p.id}
                title="Delete photo"
              >
                {deletingId === p.id ? "..." : pendingDelete === p.id ? "Confirm?" : "✕"}
              </button>
            </div>
          ))}
        </div>
      )}

      {photos.length === 0 && !loading && (
        <p className="loading">No photos indexed yet.</p>
      )}

      {nextOffset && (
        <button onClick={() => loadPage(nextOffset)} disabled={loading} style={{ marginTop: 20 }}>
          {loading ? "Loading..." : "Load more"}
        </button>
      )}

      {error && <p style={{ color: "red" }}>{error}</p>}
    </>
  );
}

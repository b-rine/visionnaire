import axios from "axios";
import { useEffect, useState } from "react";

interface StorageStats {
  used_bytes: number;
  limit_bytes: number;
}

function formatMB(bytes: number): string {
  return (bytes / 1024 ** 2).toFixed(0);
}

export default function Caption() {
  const [preview, setPreview] = useState<string | null>(null);
  const [caption, setCaption] = useState<string | null>(null);
  const [indexMsg, setIndexMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [storage, setStorage] = useState<StorageStats | null>(null);

  async function loadStorage() {
    try {
      const { data } = await axios.get<StorageStats>("/api/storage");
      setStorage(data);
    } catch {
      // storage indicator is non-critical; ignore failures
    }
  }

  useEffect(() => {
    loadStorage();
  }, []);

  async function handleFile(file: File) {
    setPreview(URL.createObjectURL(file));
    setCaption(null);
    setIndexMsg(null);
    setError(null);
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const [captionRes, indexRes] = await Promise.all([
        axios.post<{ caption: string }>("/api/caption", fd),
        axios.post<{ id: string; filename: string }>("/api/photos/upload", fd),
      ]);
      setCaption(captionRes.data.caption);
      setIndexMsg(`Indexed: ${indexRes.data.filename}`);
      loadStorage();
    } catch {
      setError("Failed to generate caption. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  return (
    <>
      <h1>Image Caption</h1>
      {storage && (
        <div className="storage-indicator">
          <div className="storage-bar">
            <div
              className="storage-bar-fill"
              style={{ width: `${Math.min(100, (storage.used_bytes / storage.limit_bytes) * 100)}%` }}
            />
          </div>
          <span>
            {formatMB(storage.used_bytes)} MB of {formatMB(storage.limit_bytes)} MB used
          </span>
        </div>
      )}
      <label
        className="dropzone"
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
      >
        <input
          type="file"
          accept="image/*"
          hidden
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        Drag & drop an image here, or click to browse
      </label>

      {preview && (
        <img src={preview} alt="preview" className="preview-image" />
      )}
      {loading && <p className="loading">Generating caption & indexing...</p>}
      {caption && (
        <div className="caption-result">
          <strong>Caption:</strong> {caption}
        </div>
      )}
      {indexMsg && <div className="status-msg">{indexMsg}</div>}
      {error && <p style={{ color: "red" }}>{error}</p>}
    </>
  );
}

import axios from "axios";
import { useState } from "react";

export default function Caption() {
  const [preview, setPreview] = useState<string | null>(null);
  const [caption, setCaption] = useState<string | null>(null);
  const [indexMsg, setIndexMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

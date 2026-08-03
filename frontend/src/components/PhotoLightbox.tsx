import axios from "axios";
import { useEffect, useState } from "react";

interface PhotoLightboxProps {
  id: string;
  filename: string;
  caption?: string;
  score?: number;
  pendingDelete: boolean;
  deleting: boolean;
  readOnly?: boolean;
  onDelete: () => void;
  onClose: () => void;
  onCaptionUpdated?: (caption: string) => void;
}

export default function PhotoLightbox({
  id,
  filename,
  caption,
  score,
  pendingDelete,
  deleting,
  readOnly = false,
  onDelete,
  onClose,
  onCaptionUpdated,
}: PhotoLightboxProps) {
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  function startEditing() {
    setEditText(caption ?? "");
    setSaveError(null);
    setEditing(true);
  }

  async function handleSaveCaption() {
    setSaving(true);
    setSaveError(null);
    try {
      const { data } = await axios.patch<{ id: string; caption: string }>(
        `/api/photos/${id}`,
        { caption: editText },
      );
      onCaptionUpdated?.(data.caption);
      setEditing(false);
    } catch {
      setSaveError("Failed to save caption.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="lightbox-backdrop" onClick={onClose}>
      <div className="lightbox-content" onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          className="close-btn"
          onClick={onClose}
          title="Close"
          aria-label="Close photo"
        >
          ✕
        </button>
        <img src={`/api/photos/${id}`} alt={filename} />
        {score !== undefined && (
          <span className="score-badge" title="Match strength">
            {(score * 100).toFixed(0)}%
          </span>
        )}
        {!readOnly && (
          <button
            className="delete-btn"
            onClick={onDelete}
            disabled={deleting}
            title="Delete photo"
          >
            {deleting ? "..." : pendingDelete ? "Confirm?" : "Del"}
          </button>
        )}
        {editing ? (
          <div className="caption-edit">
            <textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              rows={3}
            />
            <div className="caption-edit-actions">
              <button onClick={handleSaveCaption} disabled={saving}>
                {saving ? "Saving..." : "Save"}
              </button>
              <button onClick={() => setEditing(false)} disabled={saving}>
                Cancel
              </button>
            </div>
            {saveError && <p style={{ color: "red" }}>{saveError}</p>}
          </div>
        ) : (
          <div className="caption-row">
            {caption && <p className="lightbox-caption">{caption}</p>}
            {!readOnly && (
              <button
                className="edit-caption-btn"
                onClick={startEditing}
                title="Edit caption"
              >
                ✎
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

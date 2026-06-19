import { useEffect } from "react";

interface PhotoLightboxProps {
  id: string;
  filename: string;
  caption?: string;
  score?: number;
  pendingDelete: boolean;
  deleting: boolean;
  onDelete: () => void;
  onClose: () => void;
}

export default function PhotoLightbox({
  id,
  filename,
  caption,
  score,
  pendingDelete,
  deleting,
  onDelete,
  onClose,
}: PhotoLightboxProps) {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className="lightbox-backdrop" onClick={onClose}>
      <div className="lightbox-content" onClick={(e) => e.stopPropagation()}>
        <img src={`/api/photos/${id}`} alt={filename} />
        {score !== undefined && (
          <span className="score-badge" title="Match strength">
            {(score * 100).toFixed(0)}%
          </span>
        )}
        <button
          className="delete-btn"
          onClick={onDelete}
          disabled={deleting}
          title="Delete photo"
        >
          {deleting ? "..." : pendingDelete ? "Confirm?" : "✕"}
        </button>
        {caption && <p className="lightbox-caption">{caption}</p>}
      </div>
    </div>
  );
}

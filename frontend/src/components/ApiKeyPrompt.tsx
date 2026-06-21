import { useState } from "react";
import { setApiKey } from "../apiKey";

interface ApiKeyPromptProps {
  onSaved: () => void;
}

export default function ApiKeyPrompt({ onSaved }: ApiKeyPromptProps) {
  const [key, setKey] = useState("");

  function handleSave() {
    if (!key.trim()) return;
    setApiKey(key.trim());
    onSaved();
  }

  return (
    <div className="lightbox-backdrop">
      <div className="lightbox-content api-key-prompt">
        <p>An API key is required to upload, edit, or delete photos.</p>
        <input
          type="password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSave()}
          placeholder="Enter API key"
          autoFocus
        />
        <div className="caption-edit-actions">
          <button onClick={handleSave}>Save</button>
        </div>
      </div>
    </div>
  );
}

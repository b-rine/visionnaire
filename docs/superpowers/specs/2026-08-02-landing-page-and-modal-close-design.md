# Landing page + closable modals + consistent close/delete iconography

## Problem

Two issues reported in production use:

1. The `ApiKeyPrompt` modal (shown on any 401) has no way to dismiss it other than refreshing the page — no close button, no backdrop-click, no Escape key.
2. The app drops new visitors directly into the Caption ("Image Caption") page with no explanation of what Visionnaire does or what Caption/Search/Gallery are for.

While designing the modal close fix, a second, related problem surfaced: `PhotoLightbox`'s existing `✕` button means **delete** (with a `Confirm?` / `...` state machine), not close. Adding a _second_, differently-meaning `✕` to `ApiKeyPrompt` (meaning _close_) would mean the same glyph means two different, one-destructive-one-not things in sibling overlay components — a real source of user confusion.

## Design

### 1. Consistent close/delete iconography

Rule going forward: **`✕` always means close/dismiss; delete is always the text label `Del`.**

- **`ApiKeyPrompt`** (`frontend/src/components/ApiKeyPrompt.tsx`): gains an `onClose` prop. Add:
  - A `✕` button, top-right corner, calling `onClose`.
  - Backdrop `onClick` → `onClose` (content itself stops propagation, mirroring `PhotoLightbox`).
  - `Escape` keydown listener → `onClose`.
  - `App.tsx` passes `onClose={() => setShowKeyPrompt(false)}`.
  - Dismissing without saving a key does not retry the write action that triggered the prompt — this matches today's behavior (the prompt is purely reactive to a 401), so a dismissed prompt just means the user will see it again on their next write attempt.

- **Grid tile hover delete button** (`Gallery.tsx`, `Search.tsx`, class `.delete-btn` on `.photo-tile`): relabel the default state from `✕` to `Del`. `Confirm?` / `...` states and all underlying delete logic are unchanged. Position (top-right, hover-to-reveal) is unchanged — a bare thumbnail has no "close" concept, so there's no icon collision here today; this change is purely for app-wide label consistency with the lightbox.

- **`PhotoLightbox`** (`frontend/src/components/PhotoLightbox.tsx`): this is the one true collision, since its current `✕` means delete.
  - Add a new, separate close button: `✕`, top-right corner, `onClick={onClose}` directly (no confirm step — closing isn't destructive).
  - Move the existing delete button to the **bottom-right** corner (top-right is now the close button's spot). Relabel its default state from `✕` to `Del`. `Confirm?` / `...` states and the `onDelete`/`pendingDelete`/`deleting` prop wiring are unchanged — this is a label + position change only.
  - Score badge stays top-left, unaffected.

No backend/API changes for this part. Existing `Gallery.test.tsx` / `Search.test.tsx` assertions on `"✕"` text need updating to `"Del"`.

### 2. Landing page

- **New page**: `frontend/src/pages/Home.tsx` — a static page, no API calls. Matches the existing plain visual style (system-ui font, `#4a90e2` blue accents, `section` blocks — see `index.css`).
  - Short intro paragraph: what Visionnaire is (one CoCa model doing both captioning and semantic search, Qdrant-backed).
  - Three feature blocks, each with a 1-2 sentence description and a call-to-action button/link to that section:
    - **Caption** → describes uploading a photo to get an auto-generated caption, which also indexes it for search. CTA: "Try Captioning →" → `/caption`.
    - **Search** → describes semantic (meaning-based) and keyword search modes over indexed photos. CTA: "Search Photos →" → `/search`.
    - **Gallery** → describes browsing all indexed photos, with caption editing and delete. CTA: "View Gallery →" → `/gallery`.

- **Routing** (`App.tsx`):
  - `/` → `Home` (new default).
  - `/caption` → `Caption` (moved from `/`).
  - `/search`, `/gallery` — unchanged paths.

- **Nav** (`App.tsx`): becomes `Home | Caption | Search | Gallery`, in that order. `Home` link points to `/`, `Caption` link updates to point to `/caption`.

- **Testing**: `Caption.test.tsx` renders `<Caption />` directly (no router context, no route-path assertions) — confirmed it needs zero changes for the route move. No existing test renders `<App />` or asserts on nav contents, so no nav test needs updating (there simply isn't one yet). A new `Home.test.tsx` covers: intro renders, three CTA links exist and point to the right paths (`/caption`, `/search`, `/gallery`).

## Out of scope

- No dynamic content on the landing page (e.g., live photo counts) — purely static/descriptive, per YAGNI.
- No change to `ApiKeyPrompt`'s retry behavior on dismiss.
- No changes to the grid tile hover button's position or hover-reveal behavior — label only.

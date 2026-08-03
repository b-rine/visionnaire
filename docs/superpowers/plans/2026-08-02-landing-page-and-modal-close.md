# Landing Page + Modal Close/Delete Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `ApiKeyPrompt` modal closable, establish a consistent app-wide "✕ = close, `Del` = delete" convention across `PhotoLightbox` and the gallery/search grid tiles, and add a static landing page as the new default route.

**Architecture:** All changes are frontend-only (React + TypeScript, Vite, react-router-dom v6, Vitest + Testing Library). No backend/API changes. `PhotoLightbox`'s existing `onClose` prop (already wired by both `Gallery.tsx` and `Search.tsx`) is reused for its new explicit close button — no prop interface changes needed there. `ApiKeyPrompt` gains a new required `onClose` prop.

**Tech Stack:** React 18, TypeScript, react-router-dom v6.23, Vitest, @testing-library/react, @testing-library/user-event.

## Global Constraints

- `✕` always means close/dismiss; delete is always the text label `Del`. (See spec: `docs/superpowers/specs/2026-08-02-landing-page-and-modal-close-design.md`.)
- No backend/API changes anywhere in this plan.
- Landing page is static — no API calls, no dynamic data.
- Close buttons use `title="Close"`; delete buttons keep the existing `title="Delete photo"`.
- Run `cd frontend && npm test` after every task (full suite, not just the new file) to catch regressions.

---

### Task 1: Make `ApiKeyPrompt` closable

**Files:**

- Modify: `frontend/src/components/ApiKeyPrompt.tsx`
- Modify: `frontend/src/components/ApiKeyPrompt.test.tsx`
- Modify: `frontend/src/index.css`
- Modify: `frontend/src/App.tsx`

**Interfaces:**

- Consumes: none new.
- Produces: `ApiKeyPromptProps` gains a required `onClose: () => void`. `App.tsx`'s only usage of `<ApiKeyPrompt>` now passes `onClose={() => setShowKeyPrompt(false)}` alongside the existing `onSaved`. A new CSS class `.close-btn` is introduced here and reused by `PhotoLightbox` in Task 2.

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `frontend/src/components/ApiKeyPrompt.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ApiKeyPrompt from "./ApiKeyPrompt";

beforeEach(() => {
  localStorage.clear();
});

describe("ApiKeyPrompt", () => {
  it("saves the entered key to localStorage and calls onSaved", async () => {
    const onSaved = vi.fn();
    render(<ApiKeyPrompt onSaved={onSaved} onClose={vi.fn()} />);

    await userEvent.type(
      screen.getByPlaceholderText(/enter api key/i),
      "my-secret-key",
    );
    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    expect(localStorage.getItem("visionnaire_api_key")).toBe("my-secret-key");
    expect(onSaved).toHaveBeenCalledTimes(1);
  });

  it("does not save or call onSaved when the input is empty", async () => {
    const onSaved = vi.fn();
    render(<ApiKeyPrompt onSaved={onSaved} onClose={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    expect(localStorage.getItem("visionnaire_api_key")).toBeNull();
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("calls onClose when the close button is clicked", async () => {
    const onClose = vi.fn();
    render(<ApiKeyPrompt onSaved={vi.fn()} onClose={onClose} />);

    await userEvent.click(screen.getByTitle("Close"));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when the backdrop is clicked", async () => {
    const onClose = vi.fn();
    const { container } = render(
      <ApiKeyPrompt onSaved={vi.fn()} onClose={onClose} />,
    );

    await userEvent.click(container.querySelector(".lightbox-backdrop")!);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not call onClose when clicking inside the modal content", async () => {
    const onClose = vi.fn();
    render(<ApiKeyPrompt onSaved={vi.fn()} onClose={onClose} />);

    await userEvent.click(screen.getByPlaceholderText(/enter api key/i));

    expect(onClose).not.toHaveBeenCalled();
  });

  it("calls onClose when Escape is pressed", () => {
    const onClose = vi.fn();
    render(<ApiKeyPrompt onSaved={vi.fn()} onClose={onClose} />);

    fireEvent.keyDown(window, { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/ApiKeyPrompt.test.tsx`
Expected: FAIL — TypeScript error (`onClose` missing) on the two existing tests, and the three new tests fail because there's no close button, no backdrop-click handler, and no Escape listener yet.

- [ ] **Step 3: Implement the close behavior**

Replace the full contents of `frontend/src/components/ApiKeyPrompt.tsx`:

```tsx
import { useEffect, useState } from "react";
import { setApiKey } from "../apiKey";

interface ApiKeyPromptProps {
  onSaved: () => void;
  onClose: () => void;
}

export default function ApiKeyPrompt({ onSaved, onClose }: ApiKeyPromptProps) {
  const [key, setKey] = useState("");

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  function handleSave() {
    if (!key.trim()) return;
    setApiKey(key.trim());
    onSaved();
  }

  return (
    <div className="lightbox-backdrop" onClick={onClose}>
      <div
        className="lightbox-content api-key-prompt"
        onClick={(e) => e.stopPropagation()}
      >
        <button className="close-btn" onClick={onClose} title="Close">
          ✕
        </button>
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
```

Add this new CSS rule to `frontend/src/index.css` immediately after the existing `.delete-btn:hover` rule (around line 171):

```css
.close-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  border: none;
  border-radius: 3px;
  font-size: 13px;
  padding: 4px 8px;
  cursor: pointer;
}

.close-btn:hover {
  background: rgba(0, 0, 0, 0.8);
}
```

Update the one usage of `<ApiKeyPrompt>` in `frontend/src/App.tsx`:

```tsx
{
  showKeyPrompt && (
    <ApiKeyPrompt
      onSaved={() => setShowKeyPrompt(false)}
      onClose={() => setShowKeyPrompt(false)}
    />
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/ApiKeyPrompt.test.tsx`
Expected: PASS, all 6 tests.

- [ ] **Step 5: Run the full frontend test suite and type check**

Run: `cd frontend && npx tsc --noEmit && npm test`
Expected: PASS — no other file references `ApiKeyPrompt` except `App.tsx`, so no other test should be affected.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ApiKeyPrompt.tsx frontend/src/components/ApiKeyPrompt.test.tsx frontend/src/index.css frontend/src/App.tsx
git commit -m "feat(frontend): make ApiKeyPrompt closable via X button, backdrop click, and Escape"
```

---

### Task 2: `PhotoLightbox` — add close button, relabel delete to `Del`

**Files:**

- Modify: `frontend/src/components/PhotoLightbox.tsx`
- Create: `frontend/src/components/PhotoLightbox.test.tsx`
- Modify: `frontend/src/index.css`

**Interfaces:**

- Consumes: `.close-btn` CSS class from Task 1.
- Produces: no prop interface changes — `PhotoLightboxProps` is unchanged (`onClose` already existed and was already wired by `Gallery.tsx`/`Search.tsx` for backdrop-click/Escape; this task just adds a visible button calling it). The delete button's rendered text changes from `"✕"` to `"Del"` in its default state (`Confirm?`/`...` states unchanged) — this is a visual/label change only, `title="Delete photo"` is unchanged so existing `getByTitle("Delete photo")` lookups in `Gallery.test.tsx`/`Search.test.tsx` keep working unmodified.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/PhotoLightbox.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import PhotoLightbox from "./PhotoLightbox";

describe("PhotoLightbox", () => {
  it("renders the image and caption", () => {
    render(
      <PhotoLightbox
        id="photo-1"
        filename="sunset.jpg"
        caption="a sunset over the ocean"
        pendingDelete={false}
        deleting={false}
        onDelete={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByAltText("sunset.jpg")).toBeInTheDocument();
    expect(screen.getByText("a sunset over the ocean")).toBeInTheDocument();
  });

  it("shows a Del label on the delete button, not an X", () => {
    render(
      <PhotoLightbox
        id="photo-1"
        filename="sunset.jpg"
        pendingDelete={false}
        deleting={false}
        onDelete={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByTitle("Delete photo")).toHaveTextContent("Del");
  });

  it("shows Confirm? and ... states on the delete button", () => {
    const { rerender } = render(
      <PhotoLightbox
        id="photo-1"
        filename="sunset.jpg"
        pendingDelete={true}
        deleting={false}
        onDelete={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByTitle("Delete photo")).toHaveTextContent("Confirm?");

    rerender(
      <PhotoLightbox
        id="photo-1"
        filename="sunset.jpg"
        pendingDelete={false}
        deleting={true}
        onDelete={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByTitle("Delete photo")).toHaveTextContent("...");
  });

  it("calls onClose when the close button is clicked, without calling onDelete", async () => {
    const onClose = vi.fn();
    const onDelete = vi.fn();
    render(
      <PhotoLightbox
        id="photo-1"
        filename="sunset.jpg"
        pendingDelete={false}
        deleting={false}
        onDelete={onDelete}
        onClose={onClose}
      />,
    );

    await userEvent.click(screen.getByTitle("Close"));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onDelete).not.toHaveBeenCalled();
  });

  it("calls onDelete when the Del button is clicked, without calling onClose", async () => {
    const onClose = vi.fn();
    const onDelete = vi.fn();
    render(
      <PhotoLightbox
        id="photo-1"
        filename="sunset.jpg"
        pendingDelete={false}
        deleting={false}
        onDelete={onDelete}
        onClose={onClose}
      />,
    );

    await userEvent.click(screen.getByTitle("Delete photo"));

    expect(onDelete).toHaveBeenCalledTimes(1);
    expect(onClose).not.toHaveBeenCalled();
  });

  it("calls onClose when Escape is pressed", () => {
    const onClose = vi.fn();
    render(
      <PhotoLightbox
        id="photo-1"
        filename="sunset.jpg"
        pendingDelete={false}
        deleting={false}
        onDelete={vi.fn()}
        onClose={onClose}
      />,
    );

    fireEvent.keyDown(window, { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when the backdrop is clicked", async () => {
    const onClose = vi.fn();
    const { container } = render(
      <PhotoLightbox
        id="photo-1"
        filename="sunset.jpg"
        pendingDelete={false}
        deleting={false}
        onDelete={vi.fn()}
        onClose={onClose}
      />,
    );

    await userEvent.click(container.querySelector(".lightbox-backdrop")!);

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/PhotoLightbox.test.tsx`
Expected: FAIL — no element has `title="Close"` yet, and the delete button's text is `"✕"` not `"Del"`.

- [ ] **Step 3: Implement the close button and Del relabel**

In `frontend/src/components/PhotoLightbox.tsx`, change the returned JSX's opening (the `<div className="lightbox-content" ...>` block). Insert a close button as the first child, immediately after the opening `<div className="lightbox-content" onClick={(e) => e.stopPropagation()}>` tag and before the `<img ...>`:

```tsx
      <div className="lightbox-content" onClick={(e) => e.stopPropagation()}>
        <button className="close-btn" onClick={onClose} title="Close">
          ✕
        </button>
        <img src={`/api/photos/${id}`} alt={filename} />
```

Then change the delete button's default-state text from `"✕"` to `"Del"` (the `Confirm?` and `...` branches are unchanged):

```tsx
<button
  className="delete-btn"
  onClick={onDelete}
  disabled={deleting}
  title="Delete photo"
>
  {deleting ? "..." : pendingDelete ? "Confirm?" : "Del"}
</button>
```

In `frontend/src/index.css`, change the existing `.lightbox-content .delete-btn` rule (around line 262) from anchoring top-right to bottom-right, since the close button now occupies the top-right corner:

```css
.lightbox-content .delete-btn {
  position: absolute;
  top: auto;
  bottom: 8px;
  right: 8px;
  opacity: 1;
  font-size: 13px;
  padding: 4px 8px;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/PhotoLightbox.test.tsx`
Expected: PASS, all 7 tests.

- [ ] **Step 5: Run the full frontend test suite and type check**

Run: `cd frontend && npx tsc --noEmit && npm test`
Expected: PASS. `Gallery.test.tsx` and `Search.test.tsx` should be unaffected — both look up the lightbox's delete button via `getByTitle("Delete photo")` (unchanged) and `getByText("Confirm?")` (unchanged), never asserting on the `"✕"` glyph directly.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/PhotoLightbox.tsx frontend/src/components/PhotoLightbox.test.tsx frontend/src/index.css
git commit -m "feat(frontend): add explicit close button to PhotoLightbox, relabel delete to Del"
```

---

### Task 3: Relabel grid-tile hover delete buttons from `✕` to `Del`

**Files:**

- Modify: `frontend/src/pages/Gallery.tsx`
- Modify: `frontend/src/pages/Gallery.test.tsx`
- Modify: `frontend/src/pages/Search.tsx`
- Modify: `frontend/src/pages/Search.test.tsx`

**Interfaces:**

- Consumes: none new.
- Produces: no interface changes — purely a visible-text change on an existing button (`title="Delete photo"` unchanged, `Confirm?`/`...` states unchanged).

- [ ] **Step 1: Write the failing test (Gallery)**

Add this test to `frontend/src/pages/Gallery.test.tsx`, inside the `describe("Gallery page", ...)` block (e.g. right after the `"renders photos on load"` test):

```tsx
it("shows a Del label on the delete button, not an X", async () => {
  mockGet.mockResolvedValue({
    data: {
      photos: [
        {
          id: "photo-1",
          filename: "sunset.jpg",
          uploaded_at: "",
          file_size: 1,
        },
      ],
      next_offset: null,
    },
  });
  render(<Gallery />);

  await waitFor(() => screen.getByAltText("sunset.jpg"));
  expect(screen.getByTitle("Delete photo")).toHaveTextContent("Del");
});
```

- [ ] **Step 2: Write the failing test (Search)**

Add this test to `frontend/src/pages/Search.test.tsx`, inside the `describe("Search page", ...)` block (e.g. right after the `"renders results after a successful search"` test):

```tsx
it("shows a Del label on the delete button, not an X", async () => {
  mockPost.mockResolvedValue({
    data: [{ id: "photo-1", filename: "sunset.jpg", score: 0.95 }],
  });
  render(<Search />);

  await userEvent.type(
    screen.getByPlaceholderText(/sunset over mountains/i),
    "sunset",
  );
  await userEvent.click(screen.getByRole("button", { name: /^search$/i }));

  await waitFor(() => screen.getByAltText("sunset.jpg"));
  expect(screen.getByTitle("Delete photo")).toHaveTextContent("Del");
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/pages/Gallery.test.tsx src/pages/Search.test.tsx`
Expected: FAIL on the two new tests (current text is `"✕"`, not `"Del"`). All other tests in both files should still pass.

- [ ] **Step 4: Implement the relabel**

In `frontend/src/pages/Gallery.tsx`, change the button's default-state text (around line 100):

```tsx
{
  deletingId === p.id ? "..." : pendingDelete === p.id ? "Confirm?" : "Del";
}
```

In `frontend/src/pages/Search.tsx`, change the button's default-state text (around line 133):

```tsx
{
  deletingId === r.id ? "..." : pendingDelete === r.id ? "Confirm?" : "Del";
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/pages/Gallery.test.tsx src/pages/Search.test.tsx`
Expected: PASS, all tests in both files.

- [ ] **Step 6: Run the full frontend test suite and type check**

Run: `cd frontend && npx tsc --noEmit && npm test`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/Gallery.tsx frontend/src/pages/Gallery.test.tsx frontend/src/pages/Search.tsx frontend/src/pages/Search.test.tsx
git commit -m "feat(frontend): relabel grid-tile delete button from X to Del for consistency"
```

---

### Task 4: New static landing page (`Home`)

**Files:**

- Create: `frontend/src/pages/Home.tsx`
- Create: `frontend/src/pages/Home.test.tsx`
- Modify: `frontend/src/index.css`

**Interfaces:**

- Consumes: none (static page, no props, no API calls).
- Produces: `Home` default export (a React component with no props) for `App.tsx` to route to in Task 5. Links point to `/caption`, `/search`, `/gallery` (paths Task 5 will wire up in `App.tsx` — until Task 5 lands, these routes already exist under those exact same paths for `/search` and `/gallery` today, and `/caption` will exist once Task 5 moves `Caption` there, so no route is broken by landing early).

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/pages/Home.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect } from "vitest";
import Home from "./Home";

describe("Home page", () => {
  it("renders an introduction to Visionnaire", () => {
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", { name: /visionnaire/i }),
    ).toBeInTheDocument();
  });

  it("describes and links to Caption, Search, and Gallery", () => {
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", { name: /^caption$/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /^search$/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /^gallery$/i }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("link", { name: /try captioning/i }),
    ).toHaveAttribute("href", "/caption");
    expect(
      screen.getByRole("link", { name: /search photos/i }),
    ).toHaveAttribute("href", "/search");
    expect(screen.getByRole("link", { name: /view gallery/i })).toHaveAttribute(
      "href",
      "/gallery",
    );
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/pages/Home.test.tsx`
Expected: FAIL — `frontend/src/pages/Home.tsx` does not exist yet.

- [ ] **Step 3: Implement the Home page**

Create `frontend/src/pages/Home.tsx`:

```tsx
import { Link } from "react-router-dom";

export default function Home() {
  return (
    <>
      <h1>Visionnaire</h1>
      <p>
        Visionnaire is a photo app powered by a single vision-language model:
        upload a photo to get an automatic caption, then find it again later by
        describing what's in it — no manual tagging required.
      </p>

      <div className="feature-grid">
        <div className="feature-card">
          <h3>Caption</h3>
          <p>
            Upload a photo to generate a caption automatically. The photo is
            indexed for search at the same time, so there's no separate upload
            step.
          </p>
          <Link className="feature-cta" to="/caption">
            Try Captioning &rarr;
          </Link>
        </div>

        <div className="feature-card">
          <h3>Search</h3>
          <p>
            Find photos by describing them in plain language (semantic search),
            or fall back to exact keyword matching against captions.
          </p>
          <Link className="feature-cta" to="/search">
            Search Photos &rarr;
          </Link>
        </div>

        <div className="feature-card">
          <h3>Gallery</h3>
          <p>
            Browse every indexed photo, edit auto-generated captions, or delete
            photos you no longer want indexed.
          </p>
          <Link className="feature-cta" to="/gallery">
            View Gallery &rarr;
          </Link>
        </div>
      </div>
    </>
  );
}
```

Add these new CSS rules to `frontend/src/index.css`, at the end of the file:

```css
.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 20px;
  margin-top: 24px;
}

.feature-card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.feature-card h3 {
  margin: 0;
}

.feature-cta {
  align-self: flex-start;
  padding: 8px 16px;
  background: #4a90e2;
  color: #fff;
  border-radius: 6px;
  text-decoration: none;
  font-size: 0.9rem;
}

.feature-cta:hover {
  background: #357abd;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/pages/Home.test.tsx`
Expected: PASS, both tests.

- [ ] **Step 5: Run the full frontend test suite and type check**

Run: `cd frontend && npx tsc --noEmit && npm test`
Expected: PASS. `Home.tsx` isn't imported anywhere yet (that's Task 5), so this is purely additive.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Home.tsx frontend/src/pages/Home.test.tsx frontend/src/index.css
git commit -m "feat(frontend): add static Home landing page"
```

---

### Task 5: Wire routing and nav — Home becomes the default route

**Files:**

- Modify: `frontend/src/App.tsx`

**Interfaces:**

- Consumes: `Home` default export from Task 4 (`frontend/src/pages/Home.tsx`).
- Produces: `/` now renders `Home`; `/caption` renders `Caption` (moved from `/`); `/search` and `/gallery` unchanged. Nav becomes `Home | Caption | Search | Gallery`.

- [ ] **Step 1: Update routing and nav**

There is no `App.test.tsx` today, so this task has no test-file step — verification is via type-check, the existing full suite (to confirm no other file assumed `Caption` lives at `/`), and a manual dev-server check (Step 3 below). Replace the full contents of `frontend/src/App.tsx`:

```tsx
import { useEffect, useState } from "react";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { onUnauthorized } from "./apiKey";
import ApiKeyPrompt from "./components/ApiKeyPrompt";
import Caption from "./pages/Caption";
import Gallery from "./pages/Gallery";
import Home from "./pages/Home";
import Search from "./pages/Search";

export default function App() {
  const [showKeyPrompt, setShowKeyPrompt] = useState(false);

  useEffect(() => {
    onUnauthorized(() => setShowKeyPrompt(true));
  }, []);

  return (
    <BrowserRouter>
      {showKeyPrompt && (
        <ApiKeyPrompt
          onSaved={() => setShowKeyPrompt(false)}
          onClose={() => setShowKeyPrompt(false)}
        />
      )}
      <nav>
        <Link to="/">Home</Link>
        <Link to="/caption">Caption</Link>
        <Link to="/search">Search</Link>
        <Link to="/gallery">Gallery</Link>
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/caption" element={<Caption />} />
          <Route path="/search" element={<Search />} />
          <Route path="/gallery" element={<Gallery />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
```

- [ ] **Step 2: Run the full frontend test suite and type check**

Run: `cd frontend && npx tsc --noEmit && npm test`
Expected: PASS. `Caption.test.tsx` renders `<Caption />` directly with no router context and no route-path assertions, so it is unaffected by the route move.

- [ ] **Step 3: Manually verify in the dev server**

Run: `cd frontend && npm run dev` (with the backend/Triton/Qdrant stack already up via `docker compose -f docker-compose.yml -f docker-compose.dev.yml up triton qdrant backend` per the project's dev workflow).

In a browser at the printed local URL (typically `http://localhost:5173`):

- Confirm `/` shows the new Home page with three feature cards.
- Click "Try Captioning →" and confirm it navigates to `/caption` and shows the existing Caption page.
- Click the "Search Photos →" and "View Gallery →" links and confirm they navigate correctly.
- Confirm the nav bar reads `Home | Caption | Search | Gallery` and each link works.
- Trigger the `ApiKeyPrompt` (attempt an upload/delete/edit without a key set) and confirm the ✕ button, backdrop click, and Escape key all dismiss it.
- Open a photo in Gallery or Search, confirm the lightbox shows a ✕ (top-right, closes without confirming) and a separate `Del` button (bottom-right, with the existing `Confirm?` → delete flow).

Stop the dev server once confirmed (Ctrl+C).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(frontend): make landing page the default route, move Caption to /caption"
```

---

## Post-plan verification

After all 5 tasks are committed:

```bash
cd frontend && npx tsc --noEmit && npm test
```

Expected: full suite passes, no type errors. Then update `CLAUDE.md`'s "Frontend" section to document the new `Home` page, the routing change, and the close/delete iconography convention (this is a documentation step the implementer should do as part of wrapping up, per this repo's existing pattern of updating `CLAUDE.md` after each meaningful change).

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

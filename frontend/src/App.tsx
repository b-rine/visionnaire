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
      {showKeyPrompt && (
        <ApiKeyPrompt
          onSaved={() => setShowKeyPrompt(false)}
          onClose={() => setShowKeyPrompt(false)}
        />
      )}
    </BrowserRouter>
  );
}

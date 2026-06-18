import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import Caption from "./pages/Caption";
import Gallery from "./pages/Gallery";
import Search from "./pages/Search";

export default function App() {
  return (
    <BrowserRouter>
      <nav>
        <Link to="/">Caption</Link>
        <Link to="/search">Search</Link>
        <Link to="/gallery">Gallery</Link>
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Caption />} />
          <Route path="/search" element={<Search />} />
          <Route path="/gallery" element={<Gallery />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}

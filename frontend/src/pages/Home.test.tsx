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

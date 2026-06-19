import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import Search from "./Search";

const mockPost = vi.hoisted(() => vi.fn());
const mockDelete = vi.hoisted(() => vi.fn());
vi.mock("axios", () => ({ default: { post: mockPost, delete: mockDelete } }));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Search page", () => {
  it("renders the search bar", () => {
    render(<Search />);
    expect(screen.getByPlaceholderText(/sunset over mountains/i)).toBeInTheDocument();
  });

  it("renders results after a successful search", async () => {
    mockPost.mockResolvedValue({
      data: [
        { id: "photo-1", filename: "sunset.jpg", score: 0.95 },
        { id: "photo-2", filename: "mountain.jpg", score: 0.82 },
      ],
    });
    render(<Search />);

    await userEvent.type(
      screen.getByPlaceholderText(/sunset over mountains/i),
      "sunset"
    );
    await userEvent.click(screen.getByRole("button", { name: /^search$/i }));

    await waitFor(() => {
      expect(screen.getByAltText("sunset.jpg")).toBeInTheDocument();
      expect(screen.getByAltText("mountain.jpg")).toBeInTheDocument();
    });
  });

  it("shows no-results message when search returns empty", async () => {
    mockPost.mockResolvedValue({ data: [] });
    render(<Search />);

    await userEvent.type(
      screen.getByPlaceholderText(/sunset over mountains/i),
      "nothing"
    );
    await userEvent.click(screen.getByRole("button", { name: /^search$/i }));

    await waitFor(() => {
      expect(screen.getByText(/no results/i)).toBeInTheDocument();
    });
  });

  it("triggers search on Enter keypress", async () => {
    mockPost.mockResolvedValue({ data: [] });
    render(<Search />);

    await userEvent.type(
      screen.getByPlaceholderText(/sunset over mountains/i),
      "mountains{Enter}"
    );

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/photos/search", { query: "mountains" });
    });
  });

  it("shows Confirm? button after first delete click", async () => {
    mockPost.mockResolvedValue({
      data: [{ id: "photo-1", filename: "sunset.jpg", score: 0.95 }],
    });
    render(<Search />);

    await userEvent.type(screen.getByPlaceholderText(/sunset over mountains/i), "sunset");
    await userEvent.click(screen.getByRole("button", { name: /^search$/i }));
    await waitFor(() => screen.getByAltText("sunset.jpg"));

    await userEvent.click(screen.getByTitle("Delete photo"));
    expect(screen.getByText("Confirm?")).toBeInTheDocument();
  });

  it("removes photo from results after confirmed delete", async () => {
    mockPost.mockResolvedValue({
      data: [{ id: "photo-1", filename: "sunset.jpg", score: 0.95 }],
    });
    mockDelete.mockResolvedValue({});
    render(<Search />);

    await userEvent.type(screen.getByPlaceholderText(/sunset over mountains/i), "sunset");
    await userEvent.click(screen.getByRole("button", { name: /^search$/i }));
    await waitFor(() => screen.getByAltText("sunset.jpg"));

    await userEvent.click(screen.getByTitle("Delete photo"));
    await userEvent.click(screen.getByText("Confirm?"));

    await waitFor(() => {
      expect(screen.queryByAltText("sunset.jpg")).not.toBeInTheDocument();
    });
    expect(mockDelete).toHaveBeenCalledWith("/api/photos/photo-1");
  });

  it("opens a lightbox with the larger image and caption when a thumbnail is clicked", async () => {
    mockPost.mockResolvedValue({
      data: [{ id: "photo-1", filename: "sunset.jpg", caption: "a sunset over the ocean", score: 0.95 }],
    });
    render(<Search />);

    await userEvent.type(screen.getByPlaceholderText(/sunset over mountains/i), "sunset");
    await userEvent.click(screen.getByRole("button", { name: /^search$/i }));
    await waitFor(() => screen.getByAltText("sunset.jpg"));

    await userEvent.click(screen.getAllByAltText("sunset.jpg")[0]);

    expect(screen.getAllByAltText("sunset.jpg")).toHaveLength(2);
    expect(screen.getByText("a sunset over the ocean")).toBeInTheDocument();
    expect(screen.getAllByText("95%")).toHaveLength(2);
  });

  it("closes the lightbox on Escape", async () => {
    mockPost.mockResolvedValue({
      data: [{ id: "photo-1", filename: "sunset.jpg", caption: "a sunset over the ocean", score: 0.95 }],
    });
    render(<Search />);

    await userEvent.type(screen.getByPlaceholderText(/sunset over mountains/i), "sunset");
    await userEvent.click(screen.getByRole("button", { name: /^search$/i }));
    await waitFor(() => screen.getByAltText("sunset.jpg"));

    await userEvent.click(screen.getAllByAltText("sunset.jpg")[0]);
    expect(screen.getAllByAltText("sunset.jpg")).toHaveLength(2);

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.getAllByAltText("sunset.jpg")).toHaveLength(1);
  });

  it("deletes the photo from within the lightbox and closes it", async () => {
    mockPost.mockResolvedValue({
      data: [{ id: "photo-1", filename: "sunset.jpg", caption: "a sunset over the ocean", score: 0.95 }],
    });
    mockDelete.mockResolvedValue({});
    render(<Search />);

    await userEvent.type(screen.getByPlaceholderText(/sunset over mountains/i), "sunset");
    await userEvent.click(screen.getByRole("button", { name: /^search$/i }));
    await waitFor(() => screen.getByAltText("sunset.jpg"));

    await userEvent.click(screen.getAllByAltText("sunset.jpg")[0]);
    const deleteButtons = screen.getAllByTitle("Delete photo");
    await userEvent.click(deleteButtons[deleteButtons.length - 1]);
    const confirmButtons = screen.getAllByText("Confirm?");
    await userEvent.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => {
      expect(screen.queryByAltText("sunset.jpg")).not.toBeInTheDocument();
    });
  });
});

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import Search from "./Search";

const mockPost = vi.hoisted(() => vi.fn());
vi.mock("axios", () => ({ default: { post: mockPost } }));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Search page", () => {
  it("renders the upload dropzone and search bar", () => {
    render(<Search />);
    expect(
      screen.getByText(/drag & drop a photo to index/i)
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/sunset over mountains/i)
    ).toBeInTheDocument();
  });

  it("shows indexed message after successful upload", async () => {
    mockPost.mockResolvedValue({ data: { id: "abc123", filename: "beach.jpg" } });
    render(<Search />);

    const input = document.querySelector(
      "input[type=file]"
    ) as HTMLInputElement;
    await userEvent.upload(
      input,
      new File(["img"], "beach.jpg", { type: "image/jpeg" })
    );

    await waitFor(() => {
      expect(screen.getByText(/indexed: beach\.jpg/i)).toBeInTheDocument();
    });
  });

  it("shows error when upload fails", async () => {
    mockPost.mockRejectedValue(new Error("Network error"));
    render(<Search />);

    const input = document.querySelector(
      "input[type=file]"
    ) as HTMLInputElement;
    await userEvent.upload(
      input,
      new File(["img"], "beach.jpg", { type: "image/jpeg" })
    );

    await waitFor(() => {
      expect(screen.getByText(/upload failed/i)).toBeInTheDocument();
    });
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
      expect(mockPost).toHaveBeenCalledWith("/api/photos/search", {
        query: "mountains",
      });
    });
  });
});

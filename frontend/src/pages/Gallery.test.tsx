import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import Gallery from "./Gallery";

const mockGet = vi.hoisted(() => vi.fn());
const mockDelete = vi.hoisted(() => vi.fn());
const mockPatch = vi.hoisted(() => vi.fn());
vi.mock("axios", () => ({
  default: { get: mockGet, delete: mockDelete, patch: mockPatch },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Gallery page", () => {
  it("renders photos on load", async () => {
    mockGet.mockResolvedValue({
      data: {
        photos: [
          {
            id: "photo-1",
            filename: "sunset.jpg",
            uploaded_at: "2026-01-01",
            file_size: 100,
          },
        ],
        next_offset: null,
      },
    });
    render(<Gallery />);

    await waitFor(() => {
      expect(screen.getByAltText("sunset.jpg")).toBeInTheDocument();
    });
  });

  it("shows empty state when no photos are indexed", async () => {
    mockGet.mockResolvedValue({ data: { photos: [], next_offset: null } });
    render(<Gallery />);

    await waitFor(() => {
      expect(screen.getByText(/no photos indexed yet/i)).toBeInTheDocument();
    });
  });

  it("loads the next page when Load more is clicked", async () => {
    mockGet
      .mockResolvedValueOnce({
        data: {
          photos: [
            { id: "photo-1", filename: "a.jpg", uploaded_at: "", file_size: 1 },
          ],
          next_offset: "cursor-1",
        },
      })
      .mockResolvedValueOnce({
        data: {
          photos: [
            { id: "photo-2", filename: "b.jpg", uploaded_at: "", file_size: 1 },
          ],
          next_offset: null,
        },
      });
    render(<Gallery />);

    await waitFor(() => screen.getByAltText("a.jpg"));
    await userEvent.click(screen.getByRole("button", { name: /load more/i }));

    await waitFor(() => {
      expect(screen.getByAltText("a.jpg")).toBeInTheDocument();
      expect(screen.getByAltText("b.jpg")).toBeInTheDocument();
    });
    expect(mockGet).toHaveBeenLastCalledWith("/api/photos", {
      params: { offset: "cursor-1" },
    });
  });

  it("removes photo from grid after confirmed delete", async () => {
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
    mockDelete.mockResolvedValue({});
    render(<Gallery />);

    await waitFor(() => screen.getByAltText("sunset.jpg"));
    await userEvent.click(screen.getByTitle("Delete photo"));
    await userEvent.click(screen.getByText("Confirm?"));

    await waitFor(() => {
      expect(screen.queryByAltText("sunset.jpg")).not.toBeInTheDocument();
    });
    expect(mockDelete).toHaveBeenCalledWith("/api/photos/photo-1");
  });

  it("opens a lightbox with the larger image and caption when a thumbnail is clicked", async () => {
    mockGet.mockResolvedValue({
      data: {
        photos: [
          {
            id: "photo-1",
            filename: "sunset.jpg",
            uploaded_at: "",
            file_size: 1,
            caption: "a sunset over the ocean",
          },
        ],
        next_offset: null,
      },
    });
    render(<Gallery />);

    await waitFor(() => screen.getByAltText("sunset.jpg"));
    await userEvent.click(screen.getAllByAltText("sunset.jpg")[0]);

    expect(screen.getAllByAltText("sunset.jpg")).toHaveLength(2);
    expect(screen.getByText("a sunset over the ocean")).toBeInTheDocument();
  });

  it("closes the lightbox on Escape", async () => {
    mockGet.mockResolvedValue({
      data: {
        photos: [
          {
            id: "photo-1",
            filename: "sunset.jpg",
            uploaded_at: "",
            file_size: 1,
            caption: "a sunset over the ocean",
          },
        ],
        next_offset: null,
      },
    });
    render(<Gallery />);

    await waitFor(() => screen.getByAltText("sunset.jpg"));
    await userEvent.click(screen.getAllByAltText("sunset.jpg")[0]);
    expect(screen.getAllByAltText("sunset.jpg")).toHaveLength(2);

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.getAllByAltText("sunset.jpg")).toHaveLength(1);
  });

  it("deletes the photo from within the lightbox and closes it", async () => {
    mockGet.mockResolvedValue({
      data: {
        photos: [
          {
            id: "photo-1",
            filename: "sunset.jpg",
            uploaded_at: "",
            file_size: 1,
            caption: "a sunset over the ocean",
          },
        ],
        next_offset: null,
      },
    });
    mockDelete.mockResolvedValue({});
    render(<Gallery />);

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

  it("edits a caption from the lightbox and keeps the change after reopening", async () => {
    mockGet.mockResolvedValue({
      data: {
        photos: [
          {
            id: "photo-1",
            filename: "sunset.jpg",
            uploaded_at: "",
            file_size: 1,
            caption: "a sunset over the ocean",
          },
        ],
        next_offset: null,
      },
    });
    mockPatch.mockResolvedValue({
      data: { id: "photo-1", caption: "Sunset at the beach house" },
    });
    render(<Gallery />);

    await waitFor(() => screen.getByAltText("sunset.jpg"));
    await userEvent.click(screen.getAllByAltText("sunset.jpg")[0]);
    await userEvent.click(screen.getByTitle("Edit caption"));

    const textarea = screen.getByRole("textbox");
    await userEvent.clear(textarea);
    await userEvent.type(textarea, "Sunset at the beach house");
    await userEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalledWith("/api/photos/photo-1", {
        caption: "Sunset at the beach house",
      });
      expect(screen.getByText("Sunset at the beach house")).toBeInTheDocument();
    });

    fireEvent.keyDown(window, { key: "Escape" });
    await userEvent.click(screen.getAllByAltText("sunset.jpg")[0]);
    expect(screen.getByText("Sunset at the beach house")).toBeInTheDocument();
  });
});

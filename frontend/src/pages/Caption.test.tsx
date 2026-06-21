import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import Caption from "./Caption";

const mockPost = vi.hoisted(() => vi.fn());
const mockGet = vi.hoisted(() => vi.fn());
vi.mock("axios", () => ({ default: { post: mockPost, get: mockGet } }));

beforeEach(() => {
  vi.clearAllMocks();
  mockGet.mockResolvedValue({
    data: { used_bytes: 0, limit_bytes: 1024 ** 3 },
  });
});

describe("Caption page", () => {
  it("renders the dropzone", () => {
    render(<Caption />);
    expect(screen.getByText(/drag & drop an image/i)).toBeInTheDocument();
  });

  it("shows caption after successful upload", async () => {
    mockPost.mockResolvedValue({
      data: { id: "x", filename: "dog.jpg", caption: "a dog in a park" },
    });
    render(<Caption />);

    const input = document.querySelector(
      "input[type=file]",
    ) as HTMLInputElement;
    await userEvent.upload(
      input,
      new File(["img"], "dog.jpg", { type: "image/jpeg" }),
    );

    await waitFor(() => {
      expect(screen.getByText(/a dog in a park/)).toBeInTheDocument();
    });
  });

  it("shows loading state while waiting", async () => {
    let resolve!: (v: unknown) => void;
    mockPost.mockReturnValue(new Promise((r) => (resolve = r)));
    render(<Caption />);

    const input = document.querySelector(
      "input[type=file]",
    ) as HTMLInputElement;
    await userEvent.upload(
      input,
      new File(["img"], "dog.jpg", { type: "image/jpeg" }),
    );

    expect(screen.getByText(/generating caption/i)).toBeInTheDocument();
    await act(async () => {
      resolve({ data: { id: "x", filename: "dog.jpg", caption: "done" } });
    });
  });

  it("shows storage usage on load", async () => {
    mockGet.mockResolvedValue({
      data: { used_bytes: 512 ** 2, limit_bytes: 1024 ** 3 },
    });
    render(<Caption />);

    await waitFor(() => {
      expect(screen.getByText(/MB of 1024 MB used/)).toBeInTheDocument();
    });
  });

  it("shows error when API fails", async () => {
    mockPost.mockRejectedValue(new Error("Network error"));
    render(<Caption />);

    const input = document.querySelector(
      "input[type=file]",
    ) as HTMLInputElement;
    await userEvent.upload(
      input,
      new File(["img"], "dog.jpg", { type: "image/jpeg" }),
    );

    await waitFor(() => {
      expect(
        screen.getByText(/failed to generate caption/i),
      ).toBeInTheDocument();
    });
  });

  it("makes a single upload request instead of separate caption and upload calls", async () => {
    mockPost.mockResolvedValue({
      data: { id: "x", filename: "dog.jpg", caption: "a dog in a park" },
    });
    render(<Caption />);

    const input = document.querySelector(
      "input[type=file]",
    ) as HTMLInputElement;
    await userEvent.upload(
      input,
      new File(["img"], "dog.jpg", { type: "image/jpeg" }),
    );

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledTimes(1);
      expect(mockPost).toHaveBeenCalledWith(
        "/api/photos/upload",
        expect.anything(),
      );
    });
  });
});

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

    await userEvent.click(screen.getByRole("button", { name: "Close photo" }));

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

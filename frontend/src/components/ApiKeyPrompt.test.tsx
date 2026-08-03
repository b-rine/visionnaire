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

    await userEvent.click(
      screen.getByRole("button", { name: "Close API key prompt" }),
    );

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

    fireEvent.keyDown(screen.getByPlaceholderText(/enter api key/i), {
      key: "Escape",
    });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("stops Escape from reaching an underlying modal", () => {
    const onClose = vi.fn();
    const underlyingModalOnClose = vi.fn();
    window.addEventListener("keydown", underlyingModalOnClose);

    render(<ApiKeyPrompt onSaved={vi.fn()} onClose={onClose} />);
    fireEvent.keyDown(screen.getByPlaceholderText(/enter api key/i), {
      key: "Escape",
    });

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(underlyingModalOnClose).not.toHaveBeenCalled();
    window.removeEventListener("keydown", underlyingModalOnClose);
  });
});

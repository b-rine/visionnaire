import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ApiKeyPrompt from "./ApiKeyPrompt";

beforeEach(() => {
  localStorage.clear();
});

describe("ApiKeyPrompt", () => {
  it("saves the entered key to localStorage and calls onSaved", async () => {
    const onSaved = vi.fn();
    render(<ApiKeyPrompt onSaved={onSaved} />);

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
    render(<ApiKeyPrompt onSaved={onSaved} />);

    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    expect(localStorage.getItem("visionnaire_api_key")).toBeNull();
    expect(onSaved).not.toHaveBeenCalled();
  });
});

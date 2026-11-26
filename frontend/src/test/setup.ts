import "@testing-library/jest-dom/vitest";

Object.defineProperty(URL, "createObjectURL", {
  writable: true,
  value: () => "blob:mock-url",
});

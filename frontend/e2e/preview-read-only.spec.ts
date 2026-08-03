import { expect, test } from "@playwright/test";

const photo = {
  id: "11111111-1111-1111-1111-111111111111",
  filename: "sunset.jpg",
  uploaded_at: "2026-08-03T00:00:00Z",
  file_size: 1024,
  caption: "a sunset over the ocean",
};

test.beforeEach(async ({ page }) => {
  await page.route("**/api/storage", (route) =>
    route.fulfill({
      json: { used_bytes: 1024, limit_bytes: 1024 ** 3 },
    }),
  );
  await page.route("**/api/photos", (route) =>
    route.fulfill({ json: { photos: [photo], next_offset: null } }),
  );
  await page.route("**/api/photos/search", (route) =>
    route.fulfill({ json: [{ ...photo, score: 0.9 }] }),
  );
  await page.route(`**/api/photos/${photo.id}`, (route) =>
    route.fulfill({
      body: Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+P+/HgAFeAJ5Zma4WQAAAABJRU5ErkJggg==",
        "base64",
      ),
      contentType: "image/png",
    }),
  );
});

test("shows a read-only preview with working navigation", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByText("Preview deployment — production data is read-only."),
  ).toBeVisible();

  await page.getByRole("link", { name: "Caption", exact: true }).click();
  await expect(page).toHaveURL(/\/caption$/);
  await expect(page.locator(".dropzone")).toHaveCount(0);

  await page.getByRole("link", { name: "Gallery", exact: true }).click();
  await expect(page).toHaveURL(/\/gallery$/);
  await expect(page.getByAltText("sunset.jpg")).toBeVisible();
  await expect(page.getByTitle("Delete photo")).toHaveCount(0);
});

test("keeps search usable without mutation controls", async ({ page }) => {
  await page.goto("/search");

  await page.getByPlaceholder(/sunset over mountains/i).fill("sunset");
  await page.getByRole("button", { name: "Search", exact: true }).click();

  await expect(page.getByAltText("sunset.jpg")).toBeVisible();
  await expect(page.getByTitle("Delete photo")).toHaveCount(0);

  await page.getByAltText("sunset.jpg").click();
  await expect(page.getByRole("button", { name: "Close photo" })).toBeVisible();
  await expect(page.getByTitle("Edit caption")).toHaveCount(0);
  await expect(page.getByTitle("Delete photo")).toHaveCount(0);
});

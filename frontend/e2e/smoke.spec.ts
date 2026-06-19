import { expect, test } from "@playwright/test";

/**
 * Smoke-navigation across the four static M2 screens, following the linear
 * journey: Welcome → Upload → Results → Upload, plus the rejection path.
 */
test.describe("M2 screen navigation", () => {
  test("welcome → upload → results → upload", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /master your swing/i }),
    ).toBeVisible();

    await page.getByRole("link", { name: /let's analyze/i }).click();
    await expect(page).toHaveURL(/\/upload$/);
    await expect(
      page.getByRole("heading", { name: /upload analysis/i }),
    ).toBeVisible();

    // Selecting a swing runs the mock progress bar then routes to results.
    await page.getByRole("button", { name: /select swing video/i }).click();
    await expect(page).toHaveURL(/\/results$/, { timeout: 15_000 });
    await expect(
      page.getByRole("heading", { name: /swing report/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /early extension/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /over the top/i }),
    ).toBeVisible();

    await page.getByRole("link", { name: /upload next swing/i }).click();
    await expect(page).toHaveURL(/\/upload$/);
  });

  test("upload → error rejection → try again", async ({ page }) => {
    await page.goto("/upload");
    await page.getByRole("link", { name: /simulate rejection/i }).click();
    await expect(page).toHaveURL(/\/error$/);

    await expect(
      page.getByRole("heading", { name: /analysis failed/i }),
    ).toBeVisible();
    await expect(page.getByText(/angle too wide/i)).toBeVisible();
    await expect(page.getByText(/low lighting/i)).toBeVisible();
    await expect(page.getByText(/no golfer detected/i)).toBeVisible();

    await page.getByRole("link", { name: /try again/i }).click();
    await expect(page).toHaveURL(/\/upload$/);
  });
});

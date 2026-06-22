import { expect, test, type Page } from "@playwright/test";

/**
 * End-to-end coverage of the M3 walking-skeleton loop. The backend `/analyze`
 * call is stubbed via route interception so the test is hermetic — it exercises
 * the real upload → response → navigation wiring without a live backend.
 */

const FLAWS_RESPONSE = {
  status: "analyzed",
  flaws: [
    {
      priority: 1,
      category: "Posture Loss",
      title: "Early Extension",
      description: "Your hips move closer to the ball during the downswing.",
      fix: "Keep your glutes against an imaginary wall during the downswing.",
    },
    {
      priority: 2,
      category: "Path",
      title: "Over the Top",
      description: "Your downswing starts with the upper body spinning out.",
      fix: "Initiate the downswing from the ground up.",
    },
  ],
  reason: null,
};

const REJECTED_RESPONSE = {
  status: "rejected",
  flaws: [],
  reason: {
    headline: "Invalid Video Input Detected",
    summary: "The video provided does not meet the guidelines.",
    details: [
      { code: "angle", label: "Reason 01", title: "Angle too wide" },
      { code: "lighting", label: "Reason 02", title: "Low lighting" },
      { code: "no_golfer", label: "Reason 03", title: "No golfer detected" },
    ],
  },
};

const CLEAN_RESPONSE = { status: "no_major_flaws", flaws: [], reason: null };

// A realistic M5 single-reason rejection using a code added this milestone.
const SINGLE_REASON_REJECTION = {
  status: "rejected",
  flaws: [],
  reason: {
    headline: "Invalid Video Input Detected",
    summary: "The video provided does not meet the guidelines.",
    details: [{ code: "too_short", label: "Reason 01", title: "Clip too short" }],
  },
};

async function stubAnalyze(page: Page, body: unknown) {
  // The browser now posts directly to ${NEXT_PUBLIC_API_URL}/analyze (defaults
  // to http://localhost:8000/analyze in CI). Intercept that to stay hermetic.
  await page.route("**/analyze", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
}

async function stubAnalyzeStatus(page: Page, status: number, body: unknown) {
  await page.route("**/analyze", async (route) => {
    await route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
}

async function selectVideo(page: Page) {
  await page.goto("/upload");
  await page.getByTestId("swing-file-input").setInputFiles({
    name: "swing.mp4",
    mimeType: "video/mp4",
    buffer: Buffer.from("fake-video-bytes"),
  });
}

test.describe("M3 upload → analyze loop", () => {
  test("welcome → upload → results (flaws) → upload", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /master your swing/i }),
    ).toBeVisible();
    await page.getByRole("link", { name: /let's analyze/i }).click();
    await expect(page).toHaveURL(/\/upload$/);

    await stubAnalyze(page, FLAWS_RESPONSE);
    await page.getByTestId("swing-file-input").setInputFiles({
      name: "swing.mp4",
      mimeType: "video/mp4",
      buffer: Buffer.from("fake-video-bytes"),
    });

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

  test("upload → results (no major flaws)", async ({ page }) => {
    await stubAnalyze(page, CLEAN_RESPONSE);
    await selectVideo(page);

    await expect(page).toHaveURL(/\/results$/, { timeout: 15_000 });
    await expect(
      page.getByRole("heading", { name: /no major flaws detected/i }),
    ).toBeVisible();
  });

  test("upload → error rejection → try again", async ({ page }) => {
    await stubAnalyze(page, REJECTED_RESPONSE);
    await selectVideo(page);

    await expect(page).toHaveURL(/\/error$/, { timeout: 15_000 });
    await expect(
      page.getByRole("heading", { name: /analysis failed/i }),
    ).toBeVisible();
    await expect(page.getByText(/angle too wide/i)).toBeVisible();
    await expect(page.getByText(/low lighting/i)).toBeVisible();
    await expect(page.getByText(/no golfer detected/i)).toBeVisible();

    await page.getByRole("link", { name: /try again/i }).click();
    await expect(page).toHaveURL(/\/upload$/);
  });

  test("upload → error rejection (single M5 reason) → try again", async ({
    page,
  }) => {
    await stubAnalyze(page, SINGLE_REASON_REJECTION);
    await selectVideo(page);

    await expect(page).toHaveURL(/\/error$/, { timeout: 15_000 });
    await expect(
      page.getByRole("heading", { name: /analysis failed/i }),
    ).toBeVisible();
    await expect(page.getByText(/clip too short/i)).toBeVisible();

    await page.getByRole("link", { name: /try again/i }).click();
    await expect(page).toHaveURL(/\/upload$/);
  });

  test("shows the in-progress screen before routing to results", async ({
    page,
  }) => {
    // Hold the response briefly so the intermediate busy state is observable
    // (uploading bytes, then backend extracting pose / detecting flaws).
    await page.route("**/analyze", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 800));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(CLEAN_RESPONSE),
      });
    });
    await selectVideo(page);

    await expect(
      page.getByText(/uploading swing|analyzing swing/i),
    ).toBeVisible();
    await expect(page).toHaveURL(/\/results$/, { timeout: 15_000 });
    await expect(
      page.getByRole("heading", { name: /no major flaws detected/i }),
    ).toBeVisible();
  });

  test("a 503 from the backend shows a graceful error and stays on upload", async ({
    page,
  }) => {
    // M7 hardening: a timeout/overload surfaces as a non-2xx. The upload screen
    // must show an inline error rather than crash or navigate to a junk result.
    await stubAnalyzeStatus(page, 503, { detail: "service unavailable" });
    await selectVideo(page);

    const error = page.getByText(/the analysis service had a problem/i);
    await expect(error).toBeVisible();
    await expect(error).toHaveAttribute("role", "alert");
    await expect(page).toHaveURL(/\/upload$/);
  });
});

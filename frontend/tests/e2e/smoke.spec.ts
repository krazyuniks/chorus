import { expect, test } from "@playwright/test";

test("workflow runs page renders the dense table", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Workflow runs" })).toBeVisible();
  await expect(page.getByText("lighthouse-2026-04-29-0001")).toBeVisible();
});

test("top nav links to inspection routes", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Decision Trail" }).click();
  await expect(page.getByRole("heading", { name: "Decision trail" })).toBeVisible();

  await page.getByRole("link", { name: "Tool Verdicts" }).click();
  await expect(page.getByRole("heading", { name: "Tool verdicts" })).toBeVisible();
});

test("workflow detail rehydrates from the read model after a refresh", async ({
  page,
}) => {
  await page.goto("/workflows/lighthouse-2026-04-29-0001");
  await expect(
    page.getByRole("heading", { name: "lighthouse-2026-04-29-0001" }),
  ).toBeVisible();

  await page.reload();
  await expect(
    page.getByRole("heading", { name: "lighthouse-2026-04-29-0001" }),
  ).toBeVisible();
});

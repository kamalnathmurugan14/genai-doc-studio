import { expect, test } from "@playwright/test";

const nav = (page: import("@playwright/test").Page, name: string) =>
  page.getByRole("navigation", { name: "Main" }).getByRole("link", { name });

test("stream a summary, stop it, extract JSON, edit a prompt, see history", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "invoice.txt" }).click();

  // streaming + Stop
  await page.getByRole("button", { name: "▶ Run" }).click();
  await expect(page.getByRole("button", { name: /Stop/ })).toBeVisible();
  await expect(page.locator("pre.output").first()).toContainText("streamed demo summary", {
    timeout: 10_000,
  });
  await page.getByRole("button", { name: /Stop/ }).click();
  await expect(page.getByRole("status").filter({ hasText: "stopped" })).toBeVisible();

  // full run completes with counters
  await page.getByRole("button", { name: "▶ Run" }).click();
  await expect(page.getByText(/tokens in/)).toBeVisible({ timeout: 20_000 });

  // structured extraction with evidence check
  await page.getByRole("tab", { name: "extract" }).click();
  await page.getByRole("button", { name: "▶ Run" }).click();
  await expect(page.getByText("valid JSON", { exact: true })).toBeVisible();
  await expect(page.getByText("✔ verified")).toBeVisible();

  // prompt editor saves a new version
  await nav(page, "Prompts").click();
  await page.getByRole("button", { name: "summarize_short", exact: true }).click();
  const editor = page.getByLabel("Prompt template");
  await editor.fill("Summarize in one line: {{ text }}");
  await expect(page.locator("details[open] pre.output")).toContainText("Summarize in one line: Acme Corp");
  await page.getByRole("button", { name: "Save new version" }).click();
  await expect(page.getByText("Saved as a new version")).toBeVisible();

  // history lists the runs
  await nav(page, "History").click();
  await expect(page.getByRole("row", { name: /summarize/ }).first()).toBeVisible();
});

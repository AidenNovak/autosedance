import { expect, test } from "@playwright/test";

test("register -> create project -> project page has no client exception", async ({ page }) => {
  let pageError: Error | null = null;
  const consoleErrors: string[] = [];

  page.on("pageerror", (err) => {
    pageError = err;
  });

  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });

  await page.goto("/new", { waitUntil: "domcontentloaded" });

  // Auth bootstraps on the client; wait for either the RegisterCard or the create-project form.
  await Promise.race([
    page.locator('input[inputmode="email"]').waitFor({ state: "visible", timeout: 30_000 }),
    page.locator("textarea").waitFor({ state: "visible", timeout: 30_000 })
  ]);

  const emailInput = page.locator('input[inputmode="email"]');
  if ((await emailInput.count()) > 0) {
    const email = `e2e_${Date.now()}@example.com`;

    const form = page.locator("form");
    await form.locator('input[inputmode="email"]').fill(email);
    await form.locator('input[type="password"]').fill("Password123!");

    // Required inputs are: email, password, country (in that order).
    await form.locator("input[required]").nth(2).fill("Japan");

    await form.locator('button[type="submit"]').click();

    // Once authenticated, /new swaps from RegisterCard -> NewProjectPage form.
    await expect(page.locator("textarea")).toBeVisible({ timeout: 30_000 });
  }

  const createForm = page.locator("form").filter({ has: page.locator("textarea") });
  await expect(createForm.locator("textarea")).toBeVisible({ timeout: 30_000 });
  await createForm.locator("textarea").fill(`E2E smoke ${Date.now()}`);
  await createForm.locator('button[type="submit"]').click();

  await page.waitForURL(/\/projects\/[^/]+$/, { timeout: 60_000 });
  await expect(page.locator(".seglist")).toBeVisible({ timeout: 60_000 });

  expect(consoleErrors.join("\n")).not.toContain("Minified React error #310");
  expect(pageError, pageError?.stack || pageError?.message).toBeNull();
});

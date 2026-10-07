// Browser tests for cpr/assets/report.html, run against reports rendered from the real 5201 model.
// Every test runs with networking blocked and asserts that no network request was attempted.
const fs = require("fs");
const { pathToFileURL } = require("url");
const { test: base, expect } = require("./pw");

const fixtures = () => JSON.parse(process.env.CPR_FIXTURES);
const model = () => JSON.parse(fs.readFileSync(process.env.CPR_MODEL, "utf8"));
const fileUrl = (p, hash) => pathToFileURL(p).href + (hash || "");

const LOCAL = /^(file:|data:|about:|blob:)/;

const test = base.extend({
  // Offline context: block everything that is not a local URL and record any attempt.
  context: async ({ browser }, use) => {
    const context = await browser.newContext({ offline: true });
    const attempts = [];
    context.on("request", (r) => { if (!LOCAL.test(r.url())) attempts.push(r.url()); });
    await context.route("**/*", (route) => {
      const url = route.request().url();
      if (LOCAL.test(url)) return route.continue();
      attempts.push(url);
      return route.abort("blockedbyclient");
    });
    context.networkAttempts = attempts;
    await use(context);
    await context.close();
  },
  page: async ({ context }, use) => {
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    await use(page);
    expect(errors, "page errors").toEqual([]);
    expect([...new Set(context.networkAttempts)], "network requests attempted").toEqual([]);
  },
});

const sectionLocator = (page, id) => page.locator(`#section-${id}`);

test("opens from file:// offline and every section renders", async ({ page }) => {
  const m = model();
  await page.goto(fileUrl(fixtures().report));
  await expect(page).toHaveURL(/#summary$/);
  const navLinks = page.locator("#nav-list a");
  await expect(navLinks).toHaveCount(m.sections.length);
  for (let i = 0; i < m.sections.length; i++) {
    const s = m.sections[i];
    await navLinks.nth(i).click();
    await expect(page).toHaveURL(new RegExp(`#${s.id}$`));
    const sec = sectionLocator(page, s.id);
    await expect(sec).toBeVisible();
    await expect(sec.locator("h2")).toHaveText(s.title);
    await expect(sec.getByText("This section failed to render")).toHaveCount(0);
    // Only one section is shown at a time.
    await expect(page.locator(".report-section:visible")).toHaveCount(1);
    for (const aspect of s.docs) {
      await expect(sec.locator("details.howto > summary").filter({ hasText: "How this is judged" })).toHaveCount(s.docs.length);
      void aspect;
    }
    for (const id of s.checks) await expect(sec.locator(`[id="check-${id}"]`)).toHaveCount(1);
  }
  await expect(sectionLocator(page, "review")).toContainText("Not run in this version");
  // Back to the summary through history.
  await page.goBack();
  await expect(sectionLocator(page, m.sections[m.sections.length - 2].id)).toBeVisible();
});

test("deep link #ci shows the CI section and highlights it in the nav", async ({ page }) => {
  await page.goto(fileUrl(fixtures().report, "#ci"));
  await expect(sectionLocator(page, "ci")).toBeVisible();
  await expect(sectionLocator(page, "summary")).toBeHidden();
  await expect(page.locator('#nav-list a[href="#ci"]')).toHaveAttribute("aria-current", "page");
  await expect(page.locator("#nav-list a[aria-current]")).toHaveCount(1);
  // The self row is highlighted in the branch table.
  await expect(sectionLocator(page, "ci").locator("tr.self")).toHaveCount(1);
  // hashchange switches sections.
  await page.evaluate(() => { location.hash = "#votes"; });
  await expect(sectionLocator(page, "votes")).toBeVisible();
  await expect(page.locator('#nav-list a[href="#votes"]')).toHaveAttribute("aria-current", "page");
});

test("narrow screen collapses the nav behind a toggle and content is full width", async ({ page }) => {
  await page.setViewportSize({ width: 700, height: 900 });
  await page.goto(fileUrl(fixtures().report));
  const nav = page.locator("#nav");
  const toggle = page.locator("#nav-toggle");
  await expect(nav).toBeHidden();
  await expect(toggle).toBeVisible();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  const main = await page.locator("main").boundingBox();
  expect(main.x).toBeLessThanOrEqual(1);
  expect(main.width).toBeGreaterThanOrEqual(695);
  // Keyboard: open with Enter, pick a section, nav closes.
  await toggle.focus();
  await page.keyboard.press("Enter");
  await expect(nav).toBeVisible();
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await page.locator('#nav-list a[href="#testing"]').click();
  await expect(sectionLocator(page, "testing")).toBeVisible();
  await expect(nav).toBeHidden();
  // Escape closes it too.
  await toggle.click();
  await expect(nav).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(nav).toBeHidden();
});

test("print shows every section in order and hides the nav", async ({ page }) => {
  const m = model();
  await page.goto(fileUrl(fixtures().report, "#ci"));
  await page.emulateMedia({ media: "print" });
  await expect(page.locator("#nav")).toBeHidden();
  await expect(page.locator(".toolbar")).toBeHidden();
  const ids = await page.locator(".report-section").evaluateAll((els) => els.map((e) => e.getAttribute("data-section")));
  expect(ids).toEqual(m.sections.map((s) => s.id));
  for (const s of m.sections) await expect(sectionLocator(page, s.id)).toBeVisible();
  // The iframe is swapped for the file table.
  await expect(page.locator("iframe.diff-frame")).toBeHidden();
  await expect(page.locator("#changes-files table")).toBeVisible();
  // Collapsed panels print expanded.
  await expect(sectionLocator(page, "testing").locator("details.howto .d-body")).toBeVisible();
});

test("hostile content renders literally and runs nothing", async ({ page }) => {
  const f = fixtures();
  await page.goto(fileUrl(f.hostile));
  await expect(page.locator(".pr-head h1")).toHaveText(f.hostile_title);
  await page.locator('#nav-list a[href="#compatibility"]').click();
  const sec = sectionLocator(page, "compatibility");
  await expect(sec.getByText(f.hostile_evidence, { exact: true })).toHaveCount(1);
  await expect(sec.locator('a[href^="javascript"]')).toHaveCount(0);
  await expect(page.locator("img")).toHaveCount(0);
  // Visit every section so every renderer has run over the hostile model.
  for (const a of await page.locator("#nav-list a").all()) await a.click();
  expect(await page.evaluate(() => typeof window.PWNED)).toBe("undefined");
  await expect(page.locator('a[href^="javascript"]')).toHaveCount(0);
});

test("summary shows the recommendation and every check", async ({ page }) => {
  const m = model();
  await page.goto(fileUrl(fixtures().report));
  const sum = sectionLocator(page, "summary");
  await expect(sum.locator(".verdict .v-text")).toHaveText(m.recommendation.label);
  const matrix = sum.locator(".matrix");
  for (const c of m.checks) {
    await expect(matrix.locator(`[data-check="${c.id}"]`)).toHaveCount(1);
    await expect(matrix.locator(`[data-check="${c.id}"] .gt`)).toHaveText(c.title);
  }
  // Blocking failures come first, each with its action and owner.
  const reasons = sum.locator(".reasons > li");
  await expect(reasons).toHaveCount(m.recommendation.reasons.length);
  await expect(reasons.first()).toContainText("Next step");
  await expect(reasons.first()).toContainText("Who acts");
  // A check tile links to the section that shows the check.
  await matrix.locator('[data-check="tests.present"]').click();
  await expect(page).toHaveURL(/#testing$/);
  await expect(page.locator('[id="check-tests.present"]')).toBeInViewport();
});

test("Changes embeds the diff view in a scripts-only sandbox", async ({ page }) => {
  await page.goto(fileUrl(fixtures().report, "#changes"));
  const frame = page.locator("#section-changes iframe");
  await expect(frame).toHaveCount(1);
  await expect(frame).toHaveAttribute("sandbox", "allow-scripts");
  const box = await frame.boundingBox();
  expect(box.height).toBeGreaterThan(600);
  // The embedded page loaded and has content.
  const inner = page.frameLocator("#section-changes iframe");
  await expect(inner.locator("body")).not.toBeEmpty();
});

test("theme toggle cycles system, light, dark", async ({ page }) => {
  await page.goto(fileUrl(fixtures().report));
  const btn = page.locator("#theme-toggle");
  await expect(btn).toHaveText("Theme: system");
  await btn.click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await btn.click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(bg).toBe("rgb(13, 18, 23)");
  await btn.click();
  await expect(page.locator("html")).not.toHaveAttribute("data-theme", /.+/);
});

test("the bare template shows a no-data banner", async ({ page }) => {
  // The template has only the marker comment, so window.REPORT_MODEL is undefined.
  page.removeAllListeners("console"); // the template logs one console.error on purpose
  await page.goto(fileUrl(process.env.CPR_TEMPLATE));
  await expect(page.locator("#no-data")).toBeVisible();
  await expect(page.locator("#no-data")).toContainText("No report data");
});

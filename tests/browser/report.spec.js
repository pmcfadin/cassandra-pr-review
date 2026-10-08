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
  // The 5201 fixture carries a real lens panel: every lens is listed with its status.
  for (const lens of m.review.lenses) await expect(sectionLocator(page, "review")).toContainText(lens.name);
  // Reviewer context: the Context section lists suggestions and the tickets behind the changed code.
  await expect(sectionLocator(page, "context")).toContainText("Suggested reviewers");
  for (const t of m.context.related_tickets.slice(0, 3)) await expect(sectionLocator(page, "context")).toContainText(t.key);
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

test("summary shows the suggested reviewers card", async ({ page }) => {
  const m = model();
  await page.goto(fileUrl(fixtures().report, "#summary"));
  const card = page.locator(".reviewers-card");
  await expect(card).toBeVisible();
  for (const p of m.context.suggested_reviewers) await expect(card).toContainText(p.name);
  await expect(card.getByRole("link", { name: "Context details" })).toHaveAttribute("href", "#context");
});

test("5201 summary headline counts issues, findings and reporting lenses", async ({ page }) => {
  await page.goto(fileUrl(fixtures().report, "#summary"));
  await expect(sectionLocator(page, "summary").locator(".review-headline")).toContainText("5 issues (11 findings from 4 lenses)");
});

test("5201 code review leads with merged issues and lens chips", async ({ page }) => {
  const m = model();
  await page.goto(fileUrl(fixtures().report, "#review"));
  const sec = sectionLocator(page, "review");
  const issues = sec.locator("article.issue");
  await expect(issues).toHaveCount(m.review.issues.length);
  await expect(issues).toHaveCount(5);
  // The silent-delete issue is first and names the four lenses that reported it.
  const first = issues.first();
  await expect(first.locator(".lens-chip")).toHaveText(["cassandra-standards", "correctness", "test-rigor", "observability"]);
  await expect(first).toContainText("SSTable.java:121");
  await expect(first.locator(".badge").first()).toContainText("blocker");
  // Issues come before the per-lens detail.
  const order = await sec.evaluate((el) => {
    const issue = el.querySelector("article.issue");
    const detail = el.querySelector(".lens-detail-title");
    return issue.compareDocumentPosition(detail) & Node.DOCUMENT_POSITION_FOLLOWING;
  });
  expect(order).toBeTruthy();
  // Raw findings are still listed under each lens.
  for (const lens of m.review.lenses) await expect(sec).toContainText(lens.name);
});

test("code review shows lens status and the checklist version", async ({ page }) => {
  await page.goto(fileUrl(fixtures().lens_status, "#review"));
  const sec = sectionLocator(page, "review");
  await expect(sec.locator(".checklists")).toHaveText("checklists: apache/cassandra trunk @ 0123456789");
  const observability = sec.locator(".block").filter({ has: page.locator("h3", { hasText: /^observability/ }) });
  await expect(observability).toContainText("missing");
  const security = sec.locator(".block").filter({ has: page.locator("h3", { hasText: /^security/ }) });
  await expect(security).toContainText("approved");
  await expect(security).toContainText("No findings from this lens.");
});

test("Lab plan shows the Not run banner, the rendered plan, and Copy and Download", async ({ page }) => {
  const m = model();
  await page.goto(fileUrl(fixtures().report, "#labplan"));
  const sec = sectionLocator(page, "labplan");
  await expect(sec).toBeVisible();
  await expect(sec.locator("h2")).toHaveText("Lab plan");
  await expect(sec.locator(".sec-head .badge")).toContainText("Info");
  await expect(sec).toContainText(m.sections.find((s) => s.id === "labplan").summary);
  const banner = sec.locator(".labplan-banner");
  await expect(banner).toContainText("Not run.");
  await expect(banner).toContainText("No cluster was created and no command was executed");
  // The plan is rendered (headings, fenced commands), not shown as raw text.
  const plan = sec.locator(".labplan-plan");
  await expect(plan.getByRole("heading", { name: "Objective" })).toBeVisible();
  await expect(plan.getByRole("heading", { name: "Cluster Name" })).toBeVisible();
  await expect(plan.locator("pre code").first()).toContainText("BUILDS=");
  await expect(plan).toContainText("pr5201-d1095cb");
  await expect(sec.locator("details").filter({ hasText: "Show raw markdown" })).toHaveCount(1);
  // Copy and Download exist and work on the model string, not on rendered HTML.
  const copy = sec.getByRole("button", { name: "Copy plan" });
  const download = sec.getByRole("button", { name: "Download plan-5201.md" });
  await expect(copy).toBeVisible();
  await expect(download).toBeVisible();
  await copy.click();
  await expect(sec.locator("[role=status]")).toHaveText(/Copied\.|Copy failed/);
  const [dl] = await Promise.all([page.waitForEvent("download"), download.click()]);
  expect(dl.suggestedFilename()).toBe("plan-5201.md");
  const body = fs.readFileSync(await dl.path(), "utf8");
  expect(body).toBe(m.lab_plan.markdown);
  expect(body).toContain("Not run.");
  expect(body).toContain("## Cluster Name\npr5201-d1095cb\n");
  // Buttons are not printed.
  await page.emulateMedia({ media: "print" });
  await expect(sec.locator(".labplan-actions")).toBeHidden();
});

test("Lab plan without a plan says why and offers no buttons", async ({ page }) => {
  await page.goto(fileUrl(fixtures().labplan_none, "#labplan"));
  const sec = sectionLocator(page, "labplan");
  await expect(sec).toContainText("No lab plan: documentation-only change.");
  await expect(sec.locator(".sec-head .badge")).toContainText("N/A");
  await expect(sec.getByRole("button", { name: /Copy plan|Download/ })).toHaveCount(0);
  await expect(sec.locator(".labplan-banner")).toHaveCount(0);
});

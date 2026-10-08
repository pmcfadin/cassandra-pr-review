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
  // Collapsed panels print expanded, the To do list with its optional items included.
  await expect(sectionLocator(page, "testing").locator("details.howto .d-body")).toBeVisible();
  await expect(page.locator("details#todo .todo-optional")).toBeVisible();
  await expect(page.locator(".todo-more")).toBeHidden();
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
  await expect(sum.locator(".verdict .v-text")).toHaveText(m.recommendation.label.split(" — ")[0]);
  // Every check sits in the closed "Every check" panel; a tile opens the section that shows the check.
  const every = sum.locator("details.every-check");
  await expect(every).not.toHaveAttribute("open", "");
  await every.locator("summary").click();
  const matrix = sum.locator(".matrix");
  for (const c of m.checks) {
    await expect(matrix.locator(`[data-check="${c.id}"]`)).toHaveCount(1);
    await expect(matrix.locator(`[data-check="${c.id}"] .gt`)).toHaveText(c.title);
  }
  await matrix.locator('[data-check="tests.present"]').click();
  await expect(page).toHaveURL(/#testing$/);
  await expect(page.locator('[id="check-tests.present"]')).toBeInViewport();
});

test("blocked summary counts must-fix items per owner and lists them in To do", async ({ page }) => {
  const m = model();
  const reasons = m.recommendation.reasons;
  await page.goto(fileUrl(fixtures().report));
  const sum = sectionLocator(page, "summary");
  // One sentence: how many, and who they wait on.
  await expect(sum.locator(".verdict .v-note")).toHaveText(`${reasons.length} must-fix items. Waiting on the contributor, a committer and reviewers.`);
  // Merge steps link to their sections and carry a status word for screen readers.
  await expect(sum.locator(".steps a")).toHaveText(["!Ticket", "✕Tests", "✕Code review", "✕CI", "✕+1 votes"]);
  await expect(sum.locator('.steps a[href="#testing"]')).toHaveAttribute("aria-label", "Tests: Fail");
  // The To do bar is closed and counts the must-fix items per owner, contributor first.
  const todo = sum.locator("details#todo");
  await expect(todo).not.toHaveAttribute("open", "");
  const count = (o) => reasons.filter((r) => r.owner === o).length;
  await expect(todo.locator("> summary .t-owner")).toHaveText([`Contributor${count("contributor")}`, `Committer${count("committer")}`, `Reviewers${count("reviewer")}`]);
  await expect(page.locator(".nav-todo")).toContainText(String(reasons.length));
  // Open it: every reason is an item under its owner; a code review issue reads in plain words.
  await todo.locator("> summary").click();
  const must = todo.locator(":scope > .d-body > .todo-group details.todo-item");
  await expect(must).toHaveCount(reasons.length);
  await expect(todo.locator(".todo-group > h3").first()).toHaveText("Contributor");
  await expect(must.nth(1).locator("summary")).toHaveText(/Fix the blocker code review issue in SSTable\.java:121/);
  await must.first().locator("summary").click();
  await expect(must.first()).toContainText("Next step");
  await expect(must.first()).toContainText("Who acts");
  await must.nth(1).locator("summary").click();
  await expect(must.nth(1)).toContainText("Fix");
  await expect(must.nth(1).getByRole("link", { name: "Open Code review" })).toHaveAttribute("href", "#review");
  // Advisory warnings wait behind a button.
  const optional = m.checks.filter((c) => !c.blocking && (c.status === "warn" || c.status === "fail") && !reasons.some((r) => r.check === c.id));
  const more = todo.locator(".todo-more");
  await expect(more).toHaveText(`Show ${optional.length} optional items`);
  await expect(todo.locator(".todo-optional")).toBeHidden();
  await more.click();
  await expect(todo.locator(".todo-optional details.todo-item")).toHaveCount(optional.length);
  await expect(more).toHaveAttribute("aria-expanded", "true");
});

test("#todo opens the summary with the To do list open", async ({ page }) => {
  await page.goto(fileUrl(fixtures().report, "#todo"));
  await expect(sectionLocator(page, "summary")).toBeVisible();
  await expect(page.locator("details#todo")).toHaveAttribute("open", "");
  await expect(page.locator('#nav-list a[href="#summary"]')).toHaveAttribute("aria-current", "page");
  // From another section, the nav link does the same.
  await page.locator('#nav-list a[href="#ci"]').click();
  await page.locator("details#todo").evaluate((d) => { d.open = false; });
  await page.locator(".nav-todo").click();
  await expect(page).toHaveURL(/#todo$/);
  await expect(page.locator("details#todo")).toHaveAttribute("open", "");
  await expect(page.locator("details#todo > summary")).toBeInViewport();
});

test("unreviewed PR says review has not run and that there is nothing to do", async ({ page }) => {
  await page.goto(fileUrl(fixtures().unreviewed));
  const sum = sectionLocator(page, "summary");
  await expect(sum.locator(".verdict .v-text")).toHaveText("Requirements met");
  await expect(sum.locator(".verdict .v-note")).toContainText("Code review has not run yet");
  const todo = sum.locator("details#todo");
  await expect(todo.locator("> summary")).toContainText("nothing to do");
  await todo.locator("> summary").click();
  await expect(todo).toContainText("Nothing to do.");
  await expect(todo.locator("details.todo-item")).toHaveCount(0);
  await expect(page.locator(".nav-todo")).toContainText("none");
});

test("summary glossary explains project terms", async ({ page }) => {
  await page.goto(fileUrl(fixtures().report));
  const gl = sectionLocator(page, "summary").locator("details.glossary-panel");
  await gl.locator("summary").click();
  await expect(gl.locator("dt")).toContainText(["Blocking", "Committer", "+1 vote", "Fix Version"]);
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
  expect(bg).toBe("rgb(11, 23, 36)");
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

const BUILD_NOTE = "Line coverage shows which changed lines ran under the selected tests; it does not show that the fix's behaviour is tested. Read with the test regime lens.";

test("Build & coverage renders the saved 5201 run", async ({ page }) => {
  const run = JSON.parse(fs.readFileSync(require("path").resolve(__dirname, "..", "fixtures", "build", "5201-status.json"), "utf8"));
  await page.goto(fileUrl(fixtures().build, "#build"));
  const sec = sectionLocator(page, "build");
  await expect(sec).toBeVisible();
  await expect(sec.locator("h2")).toHaveText("Build & coverage");
  await expect(sec.locator(".build-banner")).toContainText("Inconclusive.");
  await expect(sec.locator(".build-banner")).toContainText("cassandra-4.0");
  const tests = sec.locator(".build-tests");
  await expect(tests.locator("th")).toHaveText(["Classes", "Run", "Failed", "Errors", "Skipped"]);
  await expect(tests.locator("td")).toHaveText(["25", "328", "0", "1", "2"]);
  await expect(sec).toContainText("StreamingTransferTest.testTransferRangeTombstones");
  const cov = sec.locator(".build-cov");
  await expect(cov).toContainText("src/java/org/apache/cassandra/io/sstable/SSTable.java");
  await expect(cov).toContainText("7/7");
  await expect(sec).toContainText("7 of 7 added executable lines ran");
  const sel = sec.locator("details.build-selected");
  await expect(sel).toHaveCount(1);
  await expect(sel.locator("li").first()).toBeHidden();
  await sel.locator("summary").click();
  await expect(sel.locator("li")).toHaveCount(run.selected.length);
  await expect(sel).toContainText("LogTransactionTest");
  await expect(sel).toContainText("calls changed method(s)");
  await expect(sec.locator(".build-note")).toHaveText(BUILD_NOTE);
  await expect(sec.locator("article.check")).toHaveCount(3);
  await expect(sec.locator("article.check").filter({ hasText: "The PR branch compiled" })).toHaveCount(1);
});

test("Build & coverage without a result says not built for this head", async ({ page }) => {
  await page.goto(fileUrl(fixtures().build_none, "#build"));
  const sec = sectionLocator(page, "build");
  await expect(sec.locator(".sec-head .badge")).toContainText("N/A");
  await expect(sec.locator(".build-banner")).toContainText("Not built for this head.");
  await expect(sec.locator(".build-banner")).toContainText("committers");
  await expect(sec.locator(".build-banner code")).toContainText("cpr build 5201 --approve");
  await expect(sec.locator(".build-tests")).toHaveCount(0);
  await expect(sec.locator(".build-cov")).toHaveCount(0);
  await expect(sec.locator(".build-note")).toHaveText(BUILD_NOTE);
});

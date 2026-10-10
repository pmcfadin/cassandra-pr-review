// Browser tests for cpr/assets/report.html, run against reports rendered from the real 5201 model.
// Every test runs with networking blocked and asserts that no network request was attempted, except
// the one Google Fonts stylesheet the design links (blocked too: the report must render without it).
const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");
const { test: base, expect } = require("./pw");

const fixtures = () => JSON.parse(process.env.CPR_FIXTURES);
const model = () => JSON.parse(fs.readFileSync(process.env.CPR_MODEL, "utf8"));
const fileUrl = (p, hash) => pathToFileURL(p).href + (hash || "");

const LOCAL = /^(file:|data:|about:|blob:)/;
const FONTS = /^https:\/\/fonts\.(googleapis|gstatic)\.com\//;

const test = base.extend({
  context: async ({ browser }, use) => {
    const context = await browser.newContext({ offline: true });
    const attempts = [];
    context.on("request", (r) => { if (!LOCAL.test(r.url()) && !FONTS.test(r.url())) attempts.push(r.url()); });
    await context.route("**/*", (route) => {
      const url = route.request().url();
      if (LOCAL.test(url)) return route.continue();
      if (!FONTS.test(url)) attempts.push(url);
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
    page.on("console", (m) => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) errors.push(m.text()); });
    await use(page);
    expect(errors, "page errors").toEqual([]);
    expect([...new Set(context.networkAttempts)], "network requests attempted").toEqual([]);
  },
});

const group = (page, id) => page.locator(`#sec-${id}`);
const head = (page, id) => page.locator(`#sec-${id} > .group-head`);

test("verdict comes first: headline, fix count, next steps, then Now (fixes) and Then (steps)", async ({ page }) => {
  await page.goto(fileUrl(fixtures().report));
  const verdict = page.locator("#status");
  await expect(verdict.locator("h2")).toHaveText("Not ready to merge");
  await expect(verdict).toContainText("The contributor has 3 fixes to make. Then a committer runs CI and two committers vote.");
  await expect(verdict).not.toContainText("Overall:");
  await expect(verdict).not.toContainText("must-fix");
  const steps = verdict.locator('ol[aria-label="Steps to merge"] li');
  await expect(steps).toHaveCount(5);
  await expect(steps.nth(0)).toContainText("Ticket");
  await expect(steps.nth(4)).toContainText("+1 votes (0 of 2)");
  // The verdict sits above the checks in document order.
  const before = await page.evaluate(() => document.getElementById("status").compareDocumentPosition(document.getElementById("checks")) & Node.DOCUMENT_POSITION_FOLLOWING);
  expect(before).toBeTruthy();
  // To do: Now holds the contributor's fixes (must-fix first); Then holds neutral steps. Optional items sit behind a toggle.
  const now = page.locator("#next .role.now");
  const then = page.locator("#next .role.then");
  await expect(now.locator(".role-name")).toContainText("Contributor");
  await expect(now.locator("li:not(.opt)")).toHaveCount(3);
  await expect(now.locator("li:not(.opt) svg[aria-label='Must fix']")).toHaveCount(3);
  await expect(then.locator(".role-name")).toContainText("Then");
  await expect(then.locator("li:not(.opt)")).toHaveCount(3);
  await expect(then.locator("svg[aria-label='Must fix']")).toHaveCount(0);
  await expect(then.locator("li:not(.opt)").nth(1)).toContainText("Run pre-commit CI on each target branch");
  await expect(then.locator("li:not(.opt)").first()).toContainText("Ask for review on the JIRA ticket or the dev@ list");
  await expect(page.locator("#next .todo-head")).toContainText("Now: Contributor");
  // Every title reads on its own, with file:line and a source tag; the two test requests are one item.
  const tests = now.locator("li", { hasText: "Test rigor" });
  await expect(tests).toHaveCount(1);
  await expect(tests).toContainText("SSTable.java:113");
  await expect(tests).toContainText("Code review");
  await expect(tests).toContainText("Also satisfies: Tests accompany production changes");
  await expect(page.locator("#next")).not.toContainText("Add a single-node");
  const optional = page.locator("#next li.opt").first();
  await expect(optional).toBeHidden();
  await page.locator("#opt-toggle").click();
  await expect(page.locator("#opt-toggle")).toHaveAttribute("aria-expanded", "true");
  await expect(optional).toBeVisible();
  // An item opens to its how-to-fix detail and links to its finding card, which opens.
  const item = now.locator("li").first().locator("button.todo-item");
  await expect(item).toHaveAttribute("aria-expanded", "false");
  await item.click();
  await expect(item).toHaveAttribute("aria-expanded", "true");
  await expect(now.locator("li").first()).toContainText("How to fix:");
  await now.locator("li").first().getByRole("link", { name: "See the finding" }).click();
  await expect(page.locator("#finding-issue-1 .finding-head")).toHaveAttribute("aria-expanded", "true");
  // The Reviewers step names at most three people and the vote count.
  const votes = then.locator("li", { hasText: "Collect two committer +1 votes" });
  await votes.locator("button.todo-item").click();
  await expect(votes).toContainText("and 2 more");
  await expect(votes).toContainText("+1 votes: 0 of 2");
  // Header facts.
  await expect(page.locator("header.pr")).toContainText("first-time contributor");
  await expect(page.locator("header.pr")).toContainText("CASSANDRA-21649");
});

test("checks: problems first, open a group to see each check with how to fix and owner", async ({ page }) => {
  const m = model();
  await page.goto(fileUrl(fixtures().report));
  const groups = page.locator("#checks .group");
  const ids = await groups.evaluateAll((els) => els.map((e) => e.id));
  expect(ids[0]).toBe("sec-ci");
  expect(ids[ids.length - 1]).toBe("sec-static");
  for (const g of ["ticket", "ci", "testing", "commits", "static", "compatibility", "votes"]) expect(ids).toContain(`sec-${g}`);
  await expect(head(page, "testing")).toHaveAttribute("aria-expanded", "false");
  await expect(head(page, "testing")).toContainText("Must fix");
  await expect(head(page, "ticket")).toContainText("Should fix");
  await expect(head(page, "compatibility")).toContainText("Note");
  await head(page, "ci").click(); // opened by default; close, then open again
  await expect(head(page, "ci")).toHaveAttribute("aria-expanded", "false");
  await head(page, "ci").click();
  const ci = group(page, "ci");
  const first = ci.locator('[id="check-ci.evidence"]');
  await expect(first).toBeVisible();
  await expect(first).toContainText("How to fix:");
  await expect(first).toContainText("Committer");
  await expect(first.locator('svg[aria-label="Must fix"]')).toHaveCount(1);
  await expect(ci.locator('[id="check-ci.profile"] svg[aria-label="Not needed"]')).toHaveCount(1);
  // Every check of every group exists in the DOM once, and the how-this-is-judged docs are inside the group.
  for (const c of m.checks) await expect(page.locator(`[id="check-${c.id}"]`)).toHaveCount(1);
  await expect(ci.locator("details.howto")).toHaveCount(2);
  // Open all / Close all.
  const all = page.locator("#toggle-all");
  await all.click();
  await expect(all).toHaveText("Close all");
  for (const el of await page.locator("#checks .group-head").all()) await expect(el).toHaveAttribute("aria-expanded", "true");
  await all.click();
  await expect(all).toHaveText("Open all");
  await expect(page.locator('#checks .group-head[aria-expanded="true"]')).toHaveCount(0);
  // Extra detail the old report showed lives inside the groups.
  await head(page, "ci").click();
  await expect(ci).toContainText("Target branches");
  await expect(ci.locator("tr.self")).toHaveCount(1);
  await head(page, "ticket").click();
  await expect(group(page, "ticket")).toContainText("Fix versions");
  await head(page, "votes").click();
  await expect(group(page, "votes")).toContainText("GitHub reviews");
  await head(page, "compatibility").click();
  await expect(group(page, "compatibility")).toContainText("Surfaces touched");
  await head(page, "commits").click();
  await expect(group(page, "commits")).toContainText("Commits");
  await head(page, "testing").click();
  await expect(group(page, "testing")).toContainText("Lines changed");
});

test("a finding card opens to problem, suggested fix and the lenses that raised it", async ({ page }) => {
  const m = model();
  await page.goto(fileUrl(fixtures().report, "#findings"));
  const cards = page.locator("#findings .finding");
  await expect(cards).toHaveCount(m.review.issues.length);
  await expect(page.locator("#findings .sevchip.blocker")).toHaveText("1 blocker");
  const first = cards.first();
  await expect(first.locator(".sev")).toHaveText("blocker");
  await expect(first).toContainText("SSTable.java:121");
  await expect(first.locator(".finding-body")).toBeHidden();
  await first.locator(".finding-head").click();
  await expect(first.locator(".finding-head")).toHaveAttribute("aria-expanded", "true");
  await expect(first.locator(".finding-body")).toContainText("Problem");
  await expect(first.locator(".finding-body")).toContainText("Suggested fix");
  for (const lens of ["cassandra-standards", "correctness", "test-rigor", "observability"]) await expect(first.locator(".lenses")).toContainText(lens);
  await expect(page.locator("#findings")).toContainText("5 issues (11 findings from 4 lenses)");
  // Per-lens detail is collapsed below the cards and lists every lens.
  await page.locator("#findings .lens-detail-toggle").click();
  for (const lens of m.review.lenses) await expect(page.locator("#findings .lens-card").filter({ hasText: lens.name }).first()).toBeVisible();
});

test("About this review says what the review is, which model ran it, and when", async ({ page }) => {
  const m = model();
  await page.goto(fileUrl(fixtures().about, "#findings"));
  const box = page.locator("#findings #about-review");
  await expect(box.locator("h3")).toHaveText("About this review");
  const n = m.review.lenses.length;
  await expect(box).toContainText(`${["", "One", "Two", "Three", "Four", "Five", "Six"][n]} AI reviewers (Claude Sonnet) read this patch.`);
  await expect(box).toContainText("The reviewers are AI. They can be wrong");
  await expect(box.locator("dt")).toHaveText(["Model", "Ran", "Patch size", "Checklists"]);
  await expect(box.locator("dd").nth(0)).toHaveText("Claude Sonnet");
  await expect(box.locator("dd").nth(1)).toHaveText("2026-10-07 21:08 UTC");
  await expect(box.locator("dd").nth(2)).toHaveText("small (19 changed lines, tests not counted)");
  await expect(box.getByRole("link", { name: "apache/cassandra trunk @ 0123456789" }))
    .toHaveAttribute("href", "https://github.com/apache/cassandra/tree/0123456789abcdef0123456789abcdef01234567/.claude/skills");
  await expect(box.locator("li")).toHaveCount(n);
  await expect(box.locator("li").first()).toContainText(`${m.review.lenses[0].name} — what the ${m.review.lenses[0].name} lens looks for`);
});

test("About this review on an older review says the model and time were not recorded", async ({ page }) => {
  await page.goto(fileUrl(fixtures().report, "#findings"));
  const box = page.locator("#findings #about-review");
  await expect(box).toContainText("AI reviewers (Claude) read this patch.");
  await expect(box.locator("dd").nth(0)).toHaveText("not recorded");
  await expect(box.locator("dd").nth(1)).toHaveText("not recorded");
});

test("About this review on an unreviewed PR names the reviewers that would run and how", async ({ page }) => {
  const panel = JSON.parse(fs.readFileSync(require("path").resolve(__dirname, "..", "..", "cpr", "config", "panel.json"), "utf8")).lenses;
  await page.goto(fileUrl(fixtures().unreviewed, "#findings"));
  const box = page.locator("#findings #about-review");
  await expect(box).toContainText("Code review has not run for this PR.");
  await expect(box).toContainText("six AI reviewers (Claude)");
  await expect(box.locator("dt")).toHaveText(["How to run"]);
  await expect(box.locator("dd code")).toHaveText("/review-pr 5201");
  await expect(box.locator("li")).toHaveCount(panel.length);
  for (const l of panel) await expect(box).toContainText(`${l.name} — ${l.focus}`);
});

test("code review shows lens status and the checklist version", async ({ page }) => {
  await page.goto(fileUrl(fixtures().lens_status, "#findings"));
  const sec = page.locator("#findings");
  await expect(sec.locator(".checklists")).toHaveText("checklists: apache/cassandra trunk @ 0123456789");
  await sec.locator(".lens-detail-toggle").click();
  await expect(sec.locator(".lens-card").filter({ has: page.locator("h4", { hasText: /^observability/ }) })).toContainText("missing");
  const security = sec.locator(".lens-card").filter({ has: page.locator("h4", { hasText: /^security/ }) });
  await expect(security).toContainText("approved");
  await expect(security).toContainText("No findings from this lens.");
  await expect(sec).toContainText("incomplete");
});

test("Lab plan: Not run banner, rendered plan, Copy and Download", async ({ page }) => {
  const m = model();
  await page.goto(fileUrl(fixtures().report, "#labplan"));
  const sec = page.locator("#labplan");
  await expect(sec.locator(".cc-head")).toHaveAttribute("aria-expanded", "true");
  const banner = sec.locator(".labplan-banner");
  await expect(banner).toContainText("Not run.");
  await expect(banner).toContainText("No cluster was created and no command was executed");
  const plan = sec.locator(".labplan-plan");
  await expect(plan.getByRole("heading", { name: "Objective" })).toBeVisible();
  await expect(plan.locator("pre code").first()).toContainText("BUILDS=");
  await expect(plan).toContainText("pr5201-d1095cb");
  const copy = sec.getByRole("button", { name: "Copy plan" });
  const download = sec.getByRole("button", { name: "Download plan-5201.md" });
  await expect(copy).toBeVisible();
  await copy.click();
  await expect(sec.locator("[role=status]")).toHaveText(/Copied\.|Copy failed/);
  const [dl] = await Promise.all([page.waitForEvent("download"), download.click()]);
  expect(dl.suggestedFilename()).toBe("plan-5201.md");
  const body = fs.readFileSync(await dl.path(), "utf8");
  expect(body).toBe(m.lab_plan.markdown);
  await page.emulateMedia({ media: "print" });
  await expect(sec.locator(".actions")).toBeHidden();
});

test("Lab plan without a plan says why and offers no buttons", async ({ page }) => {
  await page.goto(fileUrl(fixtures().labplan_none, "#labplan"));
  const sec = page.locator("#labplan");
  await expect(sec).toContainText("No lab plan: documentation-only change.");
  await expect(sec.getByRole("button", { name: /Copy plan|Download/ })).toHaveCount(0);
  await expect(sec.locator(".labplan-banner")).toHaveCount(0);
});

test("the diff view stays in a scripts-only sandboxed iframe, behind a button", async ({ page }) => {
  await page.goto(fileUrl(fixtures().report));
  await expect(page.locator("#changes iframe")).toHaveCount(0);
  await page.locator("#diff-toggle").click();
  const frame = page.locator("#changes iframe");
  await expect(frame).toHaveCount(1);
  await expect(frame).toHaveAttribute("sandbox", "allow-scripts");
  await expect(frame).toHaveAttribute("referrerpolicy", "no-referrer");
  const inner = page.frameLocator("#changes iframe");
  await expect(inner.locator("body")).not.toBeEmpty();
  // The file list is always shown.
  await expect(page.locator("#changes")).toContainText("SSTable.java");
  // Deep link opens the diff view on load.
  await page.goto(fileUrl(fixtures().report, "#changes"));
  await page.reload();
  await expect(page.locator("#changes iframe")).toHaveCount(1);
});

test("deep links open their target: group, check, findings, background, lab plan, legacy ids", async ({ page }) => {
  await page.goto(fileUrl(fixtures().report, "#sec-votes"));
  await expect(head(page, "votes")).toHaveAttribute("aria-expanded", "true");
  await expect(group(page, "votes")).toBeInViewport();
  await page.goto(fileUrl(fixtures().report, "#check-tests.present"));
  await expect(head(page, "testing")).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator('[id="check-tests.present"]')).toBeInViewport();
  await page.goto(fileUrl(fixtures().report, "#findings"));
  await expect(page.locator("#findings")).toBeInViewport();
  await page.goto(fileUrl(fixtures().report, "#background"));
  await expect(page.locator("#background")).toBeInViewport();
  // Old section ids still land somewhere sensible.
  await page.goto(fileUrl(fixtures().report, "#commits"));
  await expect(head(page, "commits")).toHaveAttribute("aria-expanded", "true");
  // hashchange opens too.
  await page.evaluate(() => { location.hash = "#sec-compatibility"; });
  await expect(head(page, "compatibility")).toHaveAttribute("aria-expanded", "true");
});

test("nav links scroll and open their target; scroll-spy follows the page", async ({ page }) => {
  await page.goto(fileUrl(fixtures().report));
  await expect(page.locator('#nav a[aria-current="location"]')).toHaveCount(1);
  await page.locator('#nav a[href="#sec-testing"]').click();
  await expect(head(page, "testing")).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator('#nav a[href="#sec-testing"]')).toHaveAttribute("aria-current", "location");
  await page.locator('#nav a[href="#findings"]').click();
  await expect(page.locator('#nav a[href="#findings"]')).toHaveAttribute("aria-current", "location");
  // Scrolling by hand moves the highlight.
  await page.waitForTimeout(900);
  await page.evaluate(() => document.getElementById("glossary").scrollIntoView());
  await expect(page.locator('#nav a[href="#glossary"]')).toHaveAttribute("aria-current", "location");
  await page.evaluate(() => window.scrollTo(0, 0));
  await expect(page.locator('#nav a[href="#status"]')).toHaveAttribute("aria-current", "location");
});

test("Background shows effort, who knows the code, history and the glossary and About live below", async ({ page }) => {
  const m = model();
  await page.goto(fileUrl(fixtures().report, "#background"));
  const effort = page.locator("#bg-effort");
  await expect(effort).toContainText("Review effort");
  await expect(effort.locator(".rating")).toHaveText("moderate");
  await expect(effort.locator(".bar i.on")).toHaveCount(2);
  await effort.locator(".linkbtn").click();
  await expect(effort).toContainText("compatibility surfaces");
  const people = page.locator("#bg-people");
  for (const p of m.context.suggested_reviewers) await expect(people).toContainText(p.name);
  await expect(people).toContainText("Already involved");
  for (const t of m.context.related_tickets.slice(0, 3)) await expect(page.locator("#bg-history")).toContainText(t.key);
  await page.locator("#glossary .cc-head").click();
  await expect(page.locator("#glossary")).toContainText("Committer");
  await page.locator("#about-toggle").click();
  await expect(page.locator("#about")).toContainText("Not checked by this tool");
  await expect(page.locator("footer.ft")).toContainText("This tool only reads");
});

test("hostile content renders literally and runs nothing", async ({ page }) => {
  const f = fixtures();
  await page.goto(fileUrl(f.hostile));
  await expect(page.locator("h1.title")).toHaveText(f.hostile_title);
  await page.goto(fileUrl(f.hostile, "#sec-compatibility"));
  const sec = group(page, "compatibility");
  await expect(sec.getByText(f.hostile_evidence, { exact: true })).toHaveCount(1);
  await expect(page.locator('a[href^="javascript"]')).toHaveCount(0);
  await expect(page.locator("img")).toHaveCount(0);
  await page.locator("#toggle-all").click();
  await page.locator("#about-toggle").click();
  await page.locator("#glossary .cc-head").click();
  expect(await page.evaluate(() => typeof window.PWNED)).toBe("undefined");
  await expect(page.locator('a[href^="javascript"]')).toHaveCount(0);
});

test("phone width: no horizontal scroll, nav is a top bar behind a Sections button", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const hash of ["", "#sec-ci", "#background", "#findings"]) {
    await page.goto(fileUrl(fixtures().report, hash));
    await page.locator("#toggle-all").click();
    const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(over, `horizontal overflow at ${hash || "top"}`).toBeLessThanOrEqual(0);
  }
  await page.goto(fileUrl(fixtures().report));
  const toggle = page.locator("#nav-toggle");
  await expect(toggle).toBeVisible();
  await expect(page.locator("#nav-body")).toBeHidden();
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await page.locator('#nav a[href="#sec-testing"]').click();
  await expect(head(page, "testing")).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator("#nav-body")).toBeHidden();
});

test("print expands everything and hides the nav", async ({ page }) => {
  await page.goto(fileUrl(fixtures().report));
  await page.emulateMedia({ media: "print" });
  await expect(page.locator(".navcol")).toBeHidden();
  await expect(page.locator("#sec-static .group-body")).toBeVisible();
  await expect(page.locator("#sec-ci details.howto .d-body").first()).toBeVisible();
  await expect(page.locator("#next li.opt").first()).toBeVisible();
  await expect(page.locator("#labplan .cc-body")).toBeVisible();
  await expect(page.locator("#changes .filelist")).toBeVisible();
});

test("the bare template shows a no-data banner", async ({ page }) => {
  page.removeAllListeners("console"); // the template logs one console.error on purpose
  await page.goto(fileUrl(process.env.CPR_TEMPLATE));
  await expect(page.locator("#no-data")).toBeVisible();
  await expect(page.locator("#no-data")).toContainText("No report data");
});

const BUILD_NOTE = "Line coverage shows which changed lines ran under the selected tests; it does not show that the fix's behaviour is tested. Read with the test regime lens.";

test("Build & coverage renders the saved 5201 run inside its group", async ({ page }) => {
  const run = JSON.parse(fs.readFileSync(path.resolve(__dirname, "..", "fixtures", "build", "5201-status.json"), "utf8"));
  await page.goto(fileUrl(fixtures().build, "#sec-build"));
  const sec = group(page, "build");
  await expect(head(page, "build")).toContainText("Unknown");
  await expect(sec.locator(".build-banner")).toContainText("Inconclusive.");
  const tests = sec.locator(".build-tests");
  await expect(tests.locator("th")).toHaveText(["Classes", "Run", "Failed", "Errors", "Skipped"]);
  await expect(tests.locator("td")).toHaveText(["25", "328", "0", "1", "2"]);
  await expect(sec).toContainText("StreamingTransferTest.testTransferRangeTombstones");
  await expect(sec.locator(".build-cov")).toContainText("7/7");
  const sel = sec.locator("details.build-selected");
  await sel.locator("summary").click();
  await expect(sel.locator("li")).toHaveCount(run.selected.length);
  await expect(sec.locator(".build-note")).toHaveText(BUILD_NOTE);
  await expect(sec.locator(".checklist > li")).toHaveCount(3);
  // Unknown gets its own neutral purple chip, not a pass or fail colour.
  await expect(head(page, "build").locator(".chip")).toHaveClass(/s-unknown/);
});

test("Build & coverage without a result says not built for this head", async ({ page }) => {
  await page.goto(fileUrl(fixtures().build_none, "#sec-build"));
  const sec = group(page, "build");
  await expect(head(page, "build")).toContainText("Not needed");
  await expect(sec.locator(".build-banner")).toContainText("Not built for this head.");
  await expect(sec.locator(".build-banner code")).toContainText("cpr build 5201 --approve");
  await expect(sec.locator(".build-tests")).toHaveCount(0);
  await expect(sec.locator(".build-note")).toHaveText(BUILD_NOTE);
});

test("phone width with groups expanded on the 4967-like report: no sideways scroll, tables stack, taps are 40px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(fileUrl(fixtures().huge));
  await page.locator("#toggle-all").click();
  await page.evaluate(() => document.querySelectorAll("details").forEach((d) => (d.open = true)));
  const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(over, "horizontal overflow").toBeLessThanOrEqual(0);
  for (const id of ["ci", "commits", "testing"]) {
    const table = group(page, id).locator(".dtable").first();
    await expect(table).toHaveCount(1);
    await expect(table.locator("thead")).toBeHidden();
    const cell = table.locator("tbody td").first();
    expect(await cell.evaluate((e) => getComputedStyle(e).display), `${id} cell`).toBe("block");
    expect(await cell.getAttribute("data-label"), `${id} label`).toBeTruthy();
    const w = await table.evaluate((e) => e.scrollWidth - e.clientWidth);
    expect(w, `${id} table scrolls sideways`).toBeLessThanOrEqual(0);
  }
  for (const loc of [page.locator("#toggle-all"), head(page, "ci"), page.locator("#nav-toggle")]) {
    expect((await loc.boundingBox()).height).toBeGreaterThanOrEqual(40);
  }
});

test("long tables show 20 rows and a Show all N button", async ({ page }) => {
  await page.goto(fileUrl(fixtures().huge));
  await page.locator("#toggle-all").click();
  const capped = page.locator(".dtable.capped").first();
  await expect(capped).toHaveCount(1);
  const total = await capped.locator("tbody tr").count();
  expect(total).toBeGreaterThan(20);
  await expect(capped.locator("tbody tr:not(.more)")).toHaveCount(20);
  const more = capped.locator(".dt-more");
  await expect(more).toHaveText(`Show all ${total}`);
  await more.click();
  await expect(more).toHaveAttribute("aria-expanded", "true");
  await expect(capped.locator("tbody tr.more").last()).toBeVisible();
});

test("report and index share the design tokens and fonts", async ({ page }) => {
  const props = ["--bg", "--ink", "--link", "--pass-bg", "--fail-fg", "--sans"];
  const read = (p) => p.evaluate((names) => names.map((n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim()), props);
  await page.goto(fileUrl(fixtures().report));
  const a = await read(page);
  await page.goto(fileUrl(fixtures().index));
  expect(await read(page)).toEqual(a);
  expect(a.every(Boolean)).toBe(true);
});

test("index groups PRs by who acts next, with a count per group and chips only when something ran", async ({ page }) => {
  const f = fixtures();
  const titles = { reviewers: "Waiting on reviewers", contributor: "Waiting on the contributor", unknown: "Cannot tell yet", draft: "Drafts" };
  for (const [width, height] of [[1280, 900], [390, 844]]) {
    await page.setViewportSize({ width, height });
    await page.goto(fileUrl(f.index));
    for (const [key, n] of Object.entries(f.index_groups)) {
      const sec = page.locator(`#g-${key}`);
      await expect(sec.locator("h2")).toHaveText(titles[key]);
      await expect(sec.locator(".group-head .count")).toHaveText(String(n));
      await expect(sec.locator("li.item")).toHaveCount(n);
      await expect(page.locator(`.stat[href="#g-${key}"] .count`)).toHaveText(String(n));
    }
    await expect(page.locator("section.group")).toHaveCount(Object.keys(f.index_groups).length);
    // The recorded bundles have no code review and no build: each row carries the verdict pill and nothing else.
    const total = Object.values(f.index_groups).reduce((x, y) => x + y, 0);
    await expect(page.locator("li.item")).toHaveCount(total);
    await expect(page.locator("li.item .chip")).toHaveCount(total);
    const row = page.locator('li.item[data-pr="5238"]');
    await expect(row.locator(".chip")).toHaveText("Draft");
    await expect(row).toContainText("Review effort: Large");
    await expect(page.locator('li.item[data-pr="5212"] .count.must')).toContainText("must fix");
    await expect(page.locator('li.item[data-pr="5212"]')).toContainText("Next: Contributor");
    const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(over, `index overflow at ${width}`).toBeLessThanOrEqual(0);
    await expect(page.locator('li.item[data-pr="5238"] a.main')).toHaveAttribute("href", "pr/5238/");
  }
});

test("PMD rules block: category summary, banded rule table, rule locations, docs links, house style collapsed; desktop and phone", async ({ page }) => {
  await page.goto(fileUrl(fixtures().pmd_rules));
  await page.locator("#toggle-all").click();
  const blk = page.locator("#sec-static .blk", { has: page.locator("h3", { hasText: "PMD rules" }) });
  await expect(blk).toHaveCount(1);
  await expect(blk.locator(".pm-cat")).toHaveCount(8);
  await expect(blk.locator(".pm-cat.s-fail")).toHaveCount(3);
  await expect(blk.locator(".pm-cat.s-should")).toHaveCount(3);
  await expect(blk.locator(".pm-cat.s-pass")).toHaveCount(2);
  const table = blk.locator(".pm-table").first();
  // Rules outside house style only, red first; more than 20 rows sit behind "Show all N".
  const kinds = await table.locator("tbody tr td:nth-child(2) .chip").evaluateAll((els) => els.map((e) => e.className.match(/s-(fail|should|pass)/)[1]));
  expect(kinds.length).toBe(28); // 30 rules outside house style, minus 2 that are usual for Cassandra
  const rank = kinds.slice(0, -1).map((c) => ({ fail: 0, should: 1, pass: 2 })[c]); // the greyed type rule comes last
  expect(rank).toEqual([...rank].sort((a, b) => a - b));
  await expect(table.locator("tr.more").first()).toBeHidden();
  await table.locator(".dt-more").click();
  await expect(table.locator("tr.more").first()).toBeVisible();
  // A rule opens to its file:line list and links to its PMD page.
  const first = table.locator("tbody tr").first();
  await first.locator("details > summary").click();
  await expect(first.locator(".pm-locs li").first().locator(".mono")).toHaveText(/^(src|test)\/.+\.java:\d+$/);
  await expect(first.locator("a")).toHaveAttribute("href", /^https:\/\/docs\.pmd-code\.org\/pmd-doc-7\.28\.0\/pmd_rules_java_[a-z]+\.html#[a-z]+$/);
  // House style: collapsed, counted, and not listed per line.
  const house = blk.locator(".pm-house details").first();
  await expect(house).toHaveJSProperty("open", false);
  await house.locator("summary").click();
  await expect(house.locator("tbody tr")).toHaveCount(11);
  await expect(house.locator(".pm-locs")).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
  // Phone: rows stack, nothing scrolls sideways.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => document.querySelectorAll("#sec-static details").forEach((d) => (d.open = true)));
  await expect(table.locator("thead")).toBeHidden();
  const cell = table.locator("tbody td").first();
  expect(await cell.evaluate((e) => getComputedStyle(e).display)).toBe("block");
  expect(await table.evaluate((e) => e.scrollWidth - e.clientWidth)).toBeLessThanOrEqual(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
  await expect(blk.locator(".pm-cats")).toBeVisible();
});

test("PMD rules block: usual-for-Cassandra section with observed vs expected, and type rules greyed without classes", async ({ page }) => {
  await page.goto(fileUrl(fixtures().pmd_rules));
  await page.locator("#toggle-all").click();
  const blk = page.locator("#sec-static .blk", { has: page.locator("h3", { hasText: "PMD rules" }) });
  const table = blk.locator(".pm-table").first();
  // Usual rules are not in the main table; they sit in their own collapsed section with both numbers.
  await expect(table.locator("tbody tr .pm-rule", { hasText: /^DoNotUseThreads$/ })).toHaveCount(0);
  const usual = blk.locator(".pm-usual details").first();
  await expect(usual).toHaveJSProperty("open", false);
  await expect(usual.locator("summary")).toContainText("Usual for Cassandra: 2 rules");
  await usual.locator("summary").click();
  await expect(usual.locator("thead th")).toHaveText(["Rule", "Category", "Observed", "Expected", "Docs"]);
  const row = usual.locator("tbody tr", { hasText: "DoNotUseThreads" });
  await expect(row.locator("td").nth(2)).toHaveText("62");
  await expect(row.locator("td").nth(3)).toHaveText("58.4");
  // Without type info a type-dependent rule is greyed, says why, and is the last row.
  const grey = table.locator("tbody tr.pm-untyped");
  await expect(grey).toHaveCount(1);
  await expect(grey).toContainText("WrongTestAnnotation");
  await expect(grey).toContainText("needs compiled classes");
  await expect(table.locator("tbody tr").last()).toHaveClass(/pm-untyped/);
  expect(Number(await grey.evaluate((e) => getComputedStyle(e.querySelector("td")).opacity))).toBeLessThan(1);
  // Phone: the usual table stacks too and nothing scrolls sideways.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => document.querySelectorAll("#sec-static details").forEach((d) => (d.open = true)));
  expect(await usual.locator("table").evaluate((e) => e.scrollWidth - e.clientWidth)).toBeLessThanOrEqual(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
});

test("PMD rules block says so when the catalog did not run", async ({ page }) => {
  await page.goto(fileUrl(fixtures().report));
  await page.locator("#toggle-all").click();
  const blk = page.locator("#sec-static .blk", { has: page.locator("h3", { hasText: "PMD rules" }) });
  await expect(blk.locator(".empty")).toContainText("did not run");
});

// Visual QA helper (not a test): node tests/browser/pmd_shots.js <report.html> <out-prefix>
// Screenshots the PMD rules block at 1280 and 390 wide, with the first rule and the house-style section open.
const { chromium } = require("playwright");
const { pathToFileURL } = require("url");

(async () => {
  const [file, prefix] = process.argv.slice(2);
  const browser = await chromium.launch();
  for (const [name, width, height] of [["1280", 1280, 900], ["390", 390, 844]]) {
    const page = await browser.newPage({ viewport: { width, height } });
    await page.route(/^https?:/, (r) => r.abort());
    await page.goto(pathToFileURL(file).href);
    await page.locator("#toggle-all").click();
    const blk = page.locator("#sec-static .blk", { has: page.locator("h3", { hasText: "PMD rules" }) });
    await blk.locator(".pm-table").first().locator("tbody tr").first().locator("details > summary").click();
    await blk.locator(".pm-house details > summary").click();
    await blk.screenshot({ path: `${prefix}-${name}.png` });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    console.log(name, "horizontal overflow px:", overflow);
    await page.close();
  }
  await browser.close();
})();

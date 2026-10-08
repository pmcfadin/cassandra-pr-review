// Visual QA helper (not a test): node tests/browser/shots.js <report.html> <out-prefix>
// Screenshots at 1280 and 390 wide: top of page, the checks list (first group open), findings, background.
const { chromium } = require("playwright");
const { pathToFileURL } = require("url");

(async () => {
  const [file, prefix] = process.argv.slice(2);
  const browser = await chromium.launch();
  for (const [name, width, height] of [["1280", 1280, 900], ["390", 390, 844]]) {
    const page = await browser.newPage({ viewport: { width, height } });
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("console", (m) => { if (m.type() === "error" && !/net::|fonts/.test(m.text())) errors.push(m.text()); });
    await page.route(/^https?:/, (r) => r.abort());
    await page.goto(pathToFileURL(file).href);
    await page.screenshot({ path: `${prefix}-${name}-top.png` });
    await page.locator("#checks").screenshot({ path: `${prefix}-${name}-checks.png` });
    if (await page.locator(".finding-head").count()) await page.locator(".finding-head").first().click();
    await page.locator("#findings").screenshot({ path: `${prefix}-${name}-findings.png` });
    await page.locator("#background").screenshot({ path: `${prefix}-${name}-background.png` });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    console.log(name, "horizontal overflow px:", overflow, "errors:", JSON.stringify(errors));
    await page.close();
  }
  await browser.close();
})();

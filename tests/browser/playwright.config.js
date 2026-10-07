// Run: npx --no-install playwright test -c tests/browser
const path = require("path");
const { defineConfig } = require("./pw");

module.exports = defineConfig({
  testDir: __dirname,
  testMatch: /.*\.spec\.js$/,
  globalSetup: path.join(__dirname, "global-setup.js"),
  outputDir: path.join(require("os").tmpdir(), "cpr-browser-test-results"),
  reporter: [["list"]],
  fullyParallel: true,
  use: { browserName: "chromium", headless: true, viewport: { width: 1280, height: 900 } },
});

// Resolve playwright/test without a package.json: use a normal install if there is one, otherwise
// the copy that is running us (`npx --no-install playwright test ...` runs from the npx cache).
const path = require("path");

function load() {
  try {
    return require("playwright/test");
  } catch (e) {
    const candidates = [require.main && require.main.filename, process.argv[1], ...Object.keys(require.cache)];
    for (const file of candidates) {
      if (!file) continue;
      const m = String(file).match(/^(.*[\\/]node_modules[\\/]playwright)[\\/]/);
      if (m) return require(path.join(m[1], "test"));
    }
    throw e;
  }
}

module.exports = load();

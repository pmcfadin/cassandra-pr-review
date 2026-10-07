// Render the HTML fixtures once, via the real Python renderer, into a temp directory.
const { execFileSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

module.exports = async () => {
  const repo = path.resolve(__dirname, "..", "..");
  const out = fs.mkdtempSync(path.join(os.tmpdir(), "cpr-report-"));
  const stdout = execFileSync(process.env.PYTHON || "python3", [path.join(__dirname, "build_fixture.py"), out], {
    cwd: repo,
    env: { ...process.env, PYTHONPATH: repo },
    encoding: "utf8",
  });
  const info = JSON.parse(stdout.trim().split("\n").pop());
  process.env.CPR_FIXTURES = JSON.stringify(info);
  process.env.CPR_TEMPLATE = path.join(repo, "cpr", "assets", "report.html");
  process.env.CPR_MODEL = path.join(repo, "tests", "fixtures", "models", "5201.json");
};

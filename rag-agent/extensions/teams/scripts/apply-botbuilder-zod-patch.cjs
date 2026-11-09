const assert = require("node:assert/strict");
const { createHash } = require("node:crypto");
const fs = require("node:fs");
const { createRequire } = require("node:module");
const path = require("node:path");
const plan = require("../patches/botbuilder-zod4.json");

const hash = (content) => createHash("sha256").update(content).digest("hex");

function patchDependencies(root, checkOnly = false) {
  const lock = JSON.parse(fs.readFileSync(path.join(root, "package-lock.json"), "utf8"));
  const modules = path.join(fs.realpathSync(root), "node_modules");
  for (const [name, expected] of Object.entries(plan.packages)) {
    const directory = path.join(modules, name);
    assert.equal(fs.realpathSync(directory), directory, `Refusing symlinked dependency: ${name}`);
    const installed = JSON.parse(fs.readFileSync(path.join(directory, "package.json"), "utf8"));
    const locked = lock.packages[`node_modules/${name}`];
    assert.equal(installed.version, expected.version, `Unsupported installed ${name} version`);
    assert.equal(locked?.version, expected.version, `Unsupported locked ${name} version`);
    assert.equal(locked.integrity, expected.integrity, `Unexpected ${name} package integrity`);
    const fromPackage = createRequire(path.join(directory, "package.json"));
    assert.equal(fromPackage.resolve("zod/package.json"), path.join(modules, "zod/package.json"),
      `Unexpected nested Zod dependency in ${name}`);
  }
  for (const [location, entry] of Object.entries(lock.packages)) {
    if (location.endsWith("/zod")) {
      assert.equal(entry.version, plan.packages.zod.version, `Unpatched Zod at ${location}`);
    }
  }

  // Validate the entire patch set before changing any installed files.
  const pending = [];
  for (const file of plan.files) {
    const target = path.join(modules, file.path);
    assert.equal(fs.realpathSync(target), target, `Refusing symlinked patch target: ${file.path}`);
    let source = fs.readFileSync(target, "utf8");
    const digest = hash(source);
    if (digest === file.patched) continue;
    assert.equal(digest, file.original, `Unexpected upstream file contents: ${file.path}`);
    assert.equal(checkOnly, false, `Required Zod migration patch not applied: ${file.path}`);
    let boundary = source.length;
    for (const edit of file.edits) {
      assert.ok(Number.isInteger(edit.start) && Number.isInteger(edit.end) &&
        edit.start >= 0 && edit.start <= edit.end && edit.end <= boundary, `Invalid patch edit: ${file.path}`);
      source = source.slice(0, edit.start) + edit.text + source.slice(edit.end);
      boundary = edit.start;
    }
    assert.equal(hash(source), file.patched, `Invalid patch output: ${file.path}`);
    pending.push({ target, source });
  }
  for (const { target, source } of pending) fs.writeFileSync(target, source);
  return pending.length;
}

if (require.main === module) {
  try {
    assert.ok(process.argv.slice(2).every((arg) => arg === "--check"), "Unsupported patch command option");
    const count = patchDependencies(path.join(__dirname, ".."), process.argv.includes("--check"));
    console.log(`BotBuilder Zod 4 migration verified (${count} files patched).`);
  } catch (error) {
    console.error(`BotBuilder Zod migration failed: ${error.message}`);
    process.exitCode = 1;
  }
}

module.exports = { patchDependencies };

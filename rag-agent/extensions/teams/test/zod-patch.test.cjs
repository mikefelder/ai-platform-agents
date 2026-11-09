const assert = require("node:assert/strict");
const { randomUUID } = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const { patchDependencies } = require("../scripts/apply-botbuilder-zod-patch.cjs");
const plan = require("../patches/botbuilder-zod4.json");
const project = path.join(__dirname, "..");

function fixture(t) {
  const root = path.join(project, "node_modules", `.zod-patch-test-${randomUUID()}`);
  fs.mkdirSync(root);
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.copyFileSync(path.join(project, "package-lock.json"), path.join(root, "package-lock.json"));
  for (const name of Object.keys(plan.packages)) {
    const directory = path.join(root, "node_modules", name);
    fs.mkdirSync(directory, { recursive: true });
    fs.copyFileSync(path.join(project, "node_modules", name, "package.json"), path.join(directory, "package.json"));
  }
  for (const file of plan.files) {
    const target = path.join(root, "node_modules", file.path);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.copyFileSync(path.join(project, "node_modules", file.path), target);
  }
  const first = path.join(root, "node_modules", plan.files[0].path);
  const original = fs.readFileSync(first, "utf8").replaceAll(".passthrough()", ".nonstrict()");
  fs.writeFileSync(first, original);
  return { root, first, original };
}

test("patch install is idempotent and build checks reject unpatched installations", (t) => {
  const { root, first, original } = fixture(t);
  assert.throws(() => patchDependencies(root, true), /patch not applied/);
  assert.equal(fs.readFileSync(first, "utf8"), original);
  assert.equal(patchDependencies(root), 1);
  assert.equal(patchDependencies(root), 0);
  assert.equal(patchDependencies(root, true), 0);
});

test("all upstream file hashes are checked before any dependency patch is written", (t) => {
  const { root, first, original } = fixture(t);
  const last = path.join(root, "node_modules", plan.files.at(-1).path);
  fs.appendFileSync(last, "\nchanged");
  assert.throws(() => patchDependencies(root), /Unexpected upstream file contents/);
  assert.equal(fs.readFileSync(first, "utf8"), original);
});

for (const [description, mutate, expected] of [
  ["version drift", (lock) => { lock.packages["node_modules/botbuilder"].version = "4.23.4"; }, /Unsupported locked botbuilder/],
  ["integrity drift", (lock) => { lock.packages["node_modules/botbuilder"].integrity = "unexpected"; }, /Unexpected botbuilder package integrity/],
  ["nested vulnerable Zod", (lock) => { lock.packages["node_modules/unexpected/node_modules/zod"] = { version: "3.25.76" }; }, /Unpatched Zod/],
]) {
  test(`patch install fails closed on ${description}`, (t) => {
    const { root, first, original } = fixture(t);
    const location = path.join(root, "package-lock.json");
    const lock = JSON.parse(fs.readFileSync(location, "utf8"));
    mutate(lock);
    fs.writeFileSync(location, JSON.stringify(lock));
    assert.throws(() => patchDependencies(root), expected);
    assert.equal(fs.readFileSync(first, "utf8"), original);
  });
}

test("patch installer refuses symlinked targets", (t) => {
  const { root, first } = fixture(t);
  const other = path.join(root, "node_modules", plan.files[1].path);
  fs.unlinkSync(first);
  fs.symlinkSync(other, first);
  assert.throws(() => patchDependencies(root), /Refusing symlinked patch target/);
});

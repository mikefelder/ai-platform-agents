const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const { randomBytes } = require("node:crypto");
const { once } = require("node:events");
const path = require("node:path");
const test = require("node:test");

test("compiled Teams HTTP server starts and retains request validation and authentication", { timeout: 10000 }, async (t) => {
  const child = spawn(process.execPath, ["lib/index.js"], {
    cwd: path.join(__dirname, ".."),
    env: {
      ...process.env,
      port: "0",
      PORT: "0",
      BOT_ID: "11111111-1111-4111-8111-111111111111",
      BOT_PASSWORD: randomBytes(32).toString("hex"),
      TEAMS_APP_TENANT_ID: "22222222-2222-4222-8222-222222222222",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  t.after(async () => {
    if (child.exitCode === null && child.signalCode === null) {
      const exited = once(child, "exit");
      child.kill("SIGTERM");
      await exited;
    }
  });
  let diagnostics = "";
  child.stderr.on("data", (data) => { diagnostics = (diagnostics + data).slice(-8192); });
  let startupTimer;
  const address = await new Promise((resolve, reject) => {
    let output = "";
    startupTimer = setTimeout(() => reject(new Error(`Server did not start: ${diagnostics}`)), 5000);
    child.once("error", reject);
    child.once("exit", (code) => reject(new Error(`Server exited ${code}: ${diagnostics}`)));
    child.stdout.on("data", (data) => {
      output = (output + data).slice(-8192);
      const match = output.match(/listening to (http:\/\/[^\s]+)/);
      if (match) resolve(match[1]);
    });
  }).finally(() => clearTimeout(startupTimer));
  const endpoint = new URL("/api/messages", address);
  endpoint.hostname = "127.0.0.1";
  for (const [body, expected] of [[null, 400], [{ type: "message", text: "hello" }, 401]]) {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(2000),
    });
    await response.arrayBuffer();
    assert.equal(response.status, expected);
  }
});

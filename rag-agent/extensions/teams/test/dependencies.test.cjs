const assert = require("node:assert/strict");
const { randomBytes } = require("node:crypto");
const { createRequire } = require("node:module");
const test = require("node:test");
const {
  CloudAdapter,
  ConfigurationBotFrameworkAuthentication,
  ConfigurationServiceClientCredentialFactory,
  EventFactory,
  TestAdapter,
} = require("botbuilder");
const { TeamsBot } = require("../lib/teamsBot");
const config = require("../lib/config").default;
const lock = require("../package-lock.json");

const uuidV4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

test("all locked Zod, UUID and redirect copies exclude the reported affected ranges", () => {
  let uuidCopies = 0;
  let redirectCopies = 0;
  let zodCopies = 0;
  for (const [path, entry] of Object.entries(lock.packages)) {
    if (path.endsWith("/uuid")) {
      uuidCopies++;
      assert.equal(entry.version, "11.1.1", path);
    }
    if (path.endsWith("/follow-redirects")) {
      redirectCopies++;
      assert.equal(entry.version, "1.16.2", path);
    }
    if (path.endsWith("/zod")) {
      zodCopies++;
      assert.equal(entry.version, "4.6.6", path);
    }
    assert.ok(!path.endsWith("/@azure/core-http"), path);
  }
  assert.ok(uuidCopies > 0);
  assert.ok(redirectCopies > 0);
  assert.equal(zodCopies, 1);
});

test("scoped overrides preserve each parent's CommonJS UUID v4 API", () => {
  for (const parent of [
    "botbuilder",
    "botbuilder-core",
    "botframework-schema",
    "botframework-streaming",
    "@azure/msal-node",
  ]) {
    const fromParent = createRequire(require.resolve(parent));
    assert.equal(fromParent("uuid/package.json").version, "11.1.1", parent);
    const uuid = fromParent("uuid");
    const values = Array.from({ length: 64 }, () => uuid.v4());
    assert.equal(new Set(values).size, values.length, parent);
    for (const value of values) {
      assert.match(value, uuidV4, parent);
      assert.ok(uuid.validate(value), parent);
    }
  }
  assert.match(new (require("@azure/msal-node").CryptoProvider)().createNewGuid(), uuidV4);
  assert.match(require("botframework-streaming/lib/utilities/protocol-base").generateGuid(), uuidV4);
  assert.match(EventFactory.createHandoffStatus({ id: "conversation" }, "accepted").id, uuidV4);
});

test("all BotBuilder schema consumers load only the patched Zod 4 runtime", () => {
  for (const parent of ["botbuilder", "botbuilder-core", "botframework-connector", "botframework-schema"]) {
    const fromParent = createRequire(require.resolve(parent));
    assert.equal(fromParent("zod/package.json").version, "4.6.6", parent);
    assert.equal(fromParent.resolve("zod"), require.resolve("zod"), parent);
    assert.ok(fromParent("zod").string()._zod, parent);
  }
  assert.equal(Object.keys(require.cache).some((file) => file.includes("/zod/v3/")), false);
});

test("single-tenant authentication and CloudAdapter still initialize", async () => {
  const credentials = new ConfigurationServiceClientCredentialFactory({
    MicrosoftAppId: "11111111-1111-4111-8111-111111111111",
    MicrosoftAppPassword: randomBytes(32).toString("hex"),
    MicrosoftAppType: "SingleTenant",
    MicrosoftAppTenantId: "22222222-2222-4222-8222-222222222222",
  });
  const authentication = new ConfigurationBotFrameworkAuthentication({}, credentials);
  const adapter = new CloudAdapter(authentication);
  assert.equal(typeof adapter.process, "function");
  assert.equal(await credentials.isAuthenticationDisabled(), false);
  assert.equal(await credentials.isValidAppId("11111111-1111-4111-8111-111111111111"), true);
});

function harness(t, messages) {
  const bot = new TeamsBot();
  const adapter = new TestAdapter((context) => bot.run(context));
  const updates = [];
  const deletions = [];
  t.mock.method(adapter, "updateActivity", async (_context, activity) => {
    updates.push(activity);
    return { id: activity.id };
  });
  t.mock.method(adapter, "deleteActivity", async (_context, reference) => {
    deletions.push(reference.activityId);
  });
  const oldUrl = config.azureFunctionUrl;
  const oldEndpoint = config.getFileEndpoint;
  config.azureFunctionUrl = "https://function.example.invalid/chat";
  config.getFileEndpoint = "https://files.example.invalid/api/files";
  t.after(() => {
    config.azureFunctionUrl = oldUrl;
    config.getFileEndpoint = oldEndpoint;
  });
  const requests = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    requests.push({ url, options });
    return new Response(JSON.stringify({ choices: [{ messages }] }));
  });
  return { adapter, updates, deletions, requests };
}

test("Teams membership events retain the welcome message", { timeout: 5000 }, async () => {
  const bot = new TeamsBot();
  const adapter = new TestAdapter((context) => bot.run(context));
  await adapter.processActivity({
    type: "conversationUpdate",
    membersAdded: [{ id: "new-member" }],
  });
  assert.match(adapter.getNextReply().text, /Greetings!.*Chat with your data bot/);
});

test("Teams text replies retain mentions, typing, function payload and message updates", { timeout: 5000 }, async (t) => {
  const h = harness(t, [
    { role: "tool", content: JSON.stringify({ citations: [] }) },
    { role: "assistant", content: "The answer is 42." },
  ]);
  await h.adapter.processActivity({
    type: "message",
    text: "<at>Bot</at> QUESTION\n",
    recipient: { id: "bot", name: "Bot" },
    entities: [{ type: "mention", mentioned: { id: "bot" }, text: "<at>Bot</at>" }],
  });
  const searching = h.adapter.getNextReply();
  assert.equal(searching.text, "Searching ...");
  assert.equal(h.adapter.getNextReply().type, "typing");
  assert.equal(h.requests.length, 1);
  assert.equal(h.requests[0].url, config.azureFunctionUrl);
  assert.equal(h.requests[0].options.method, "POST");
  assert.deepEqual(JSON.parse(h.requests[0].options.body), {
    messages: [{ role: "user", content: "question" }],
    conversation_id: "",
  });
  assert.equal(h.updates.length, 1);
  assert.equal(h.updates[0].id, searching.id);
  assert.match(h.updates[0].text, /The answer is 42\./);
  assert.match(h.updates[0].text, /AI-generated content may be incorrect/);
  assert.deepEqual(h.deletions, []);
});

test("Teams citation replies retain adaptive cards and source links", { timeout: 5000 }, async (t) => {
  const h = harness(t, [
    {
      role: "tool",
      content: JSON.stringify({
        citations: [{ title: "/documents/guide.pdf", content: "Supporting evidence", chunk_id: "0" }],
      }),
    },
    { role: "assistant", content: "See the guide [doc1]." },
  ]);
  await h.adapter.processActivity("Question");
  const searching = h.adapter.getNextReply();
  assert.equal(h.adapter.getNextReply().type, "typing");
  const attachment = h.adapter.getNextReply().attachments[0];
  assert.equal(attachment.contentType, "application/vnd.microsoft.card.adaptive");
  assert.equal(attachment.content.body[0].text, "See the guide .");
  assert.equal(attachment.content.actions[0].card.actions[0].url,
    "https://files.example.invalid/api/files/guide.pdf");
  assert.deepEqual(h.deletions, [searching.id]);
  assert.deepEqual(h.updates, []);
});

test("Teams backend failures still produce a user-facing error", { timeout: 5000 }, async (t) => {
  const h = harness(t, []);
  t.mock.method(globalThis, "fetch", async () => {
    throw new Error("backend unavailable");
  });
  t.mock.method(console, "error", () => {});
  await h.adapter.processActivity("Question");
  assert.equal(h.updates.length, 1);
  assert.match(h.updates[0].text, /Sorry, an error occurred/);
  assert.match(h.updates[0].text, /backend unavailable/);
});

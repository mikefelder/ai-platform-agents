const assert = require("node:assert/strict");
const test = require("node:test");
const schema = require("botframework-schema");
const {
  ConfigurationBotFrameworkAuthentication,
  ConfigurationServiceClientCredentialFactory,
  TeamsActivityHandler,
  TestAdapter,
} = require("botbuilder");
const { UserTokenClient } = require("botframework-connector");

const account = { id: "account", name: "Account" };
const conversation = { id: "conversation", name: "Conversation", isGroup: false, conversationType: "personal" };
const activity = {
  type: "message",
  localTimezone: "UTC",
  callerId: "caller",
  serviceUrl: "https://service.example.invalid",
  channelId: "msteams",
  from: account,
  recipient: account,
  conversation,
  text: "hello",
  label: "",
  valueType: "",
};

const contracts = [
  ["AttachmentView", { viewId: "view", size: 12 }, { viewId: "view", size: "12" }],
  ["AttachmentInfo", { name: "file", type: "text/plain", views: [] }, { name: "file", type: "text/plain", views: [null] }],
  ["ChannelAccount", account, { id: "account" }],
  ["ConversationAccount", conversation, { ...conversation, isGroup: "false" }],
  ["MessageReaction", { type: "like" }, { type: 1 }],
  ["CardAction", { type: "openUrl", title: "Open", image: "", text: "", displayText: "" }, { type: "openUrl" }],
  ["SuggestedActions", { to: ["user"], actions: [] }, { to: [1], actions: [] }],
  ["Attachment", { contentType: "application/json" }, { contentType: null }],
  ["Entity", { type: "mention", nested: { arbitrary: true } }, { type: 1 }],
  ["ConversationReference", { bot: account, conversation, channelId: "msteams", serviceUrl: "https://service.example.invalid" }, {}],
  ["SemanticAction", { id: "action", state: "start", entities: { named: { type: "mention" } } }, { id: "action", state: "start", entities: { named: { type: 1 } } }],
  ["Activity", activity, { ...activity, attachments: [{ contentType: 1 }] }],
];

for (const [name, valid, invalid] of contracts) {
  test(`Zod 3 contract retained for BotBuilder ${name}`, () => {
    assert.equal(schema[`is${name}`](valid), true);
    assert.doesNotThrow(() => schema[`assert${name}`](valid));
    assert.equal(schema[`is${name}`](invalid), false);
    assert.throws(() => schema[`assert${name}`](invalid));
    assert.equal(schema[`is${name}`](null), false);
    assert.equal(schema[`is${name}`]([]), false);
  });
}

test("conversation parsing strips schema extras but preserves opaque payloads and optional unknown fields", () => {
  const input = {
    isGroup: false,
    bot: { ...account, extra: "strip" },
    activity: {
      ...activity,
      extra: "strip",
      channelData: { tenant: { id: "tenant" }, extra: null },
      suggestedActions: {
        to: ["user"],
        actions: [{ type: "openUrl", title: "Open", image: "", text: "", displayText: "" }],
      },
      attachments: [{ contentType: "application/json", content: { arbitrary: [1, null] } }],
      entities: [{ type: "mention", nested: { key: "value" } }],
    },
    extra: "strip",
    channelData: { arbitrary: [1, null] },
  };
  const output = schema.conversationParametersObject.parse(input);
  assert.equal("extra" in output, false);
  assert.equal("extra" in output.bot, false);
  assert.equal("extra" in output.activity, false);
  assert.deepEqual(output.channelData, input.channelData);
  assert.deepEqual(output.activity.channelData, input.activity.channelData);
  assert.deepEqual(output.activity.entities, input.activity.entities);
  assert.deepEqual(output.activity.attachments, input.activity.attachments);
  assert.equal("value" in output.activity.suggestedActions.actions[0], false);
  assert.equal("channelData" in output.activity.suggestedActions.actions[0], false);
  assert.equal(schema.conversationParametersObject.safeParse({ ...input, activity: {} }).success, false);
});

for (const [event, timeField] of [["Start", "StartTime"], ["End", "EndTime"]]) {
  test(`meeting ${event} schemas accept extension data and reject wrong field types`, { timeout: 5000 }, async () => {
    const handler = new TeamsActivityHandler();
    const meetings = [];
    handler[`onTeamsMeeting${event}Event`](async (meeting, context, next) => {
      meetings.push({ ...meeting, originalExtension: context.activity.value.Extension });
      await next();
    });
    const adapter = new TestAdapter((context) => handler.run(context));
    const value = {
      Id: "meeting",
      JoinUrl: "https://meeting.example.invalid",
      MeetingType: "Scheduled",
      Title: "Meeting",
      [timeField]: "2026-11-09T14:00:00Z",
      Extension: { arbitrary: true },
    };
    const message = {
      type: "event",
      name: `application/vnd.microsoft.meeting${event}`,
      channelId: "msteams",
      value,
    };
    await adapter.processActivity(message);
    assert.equal(meetings.length, 1);
    assert.deepEqual(meetings[0].originalExtension, value.Extension);
    assert.equal(meetings[0].id, value.Id);
    await assert.rejects(adapter.processActivity({
      ...message,
      value: { ...value, Title: 12 },
    }));
    assert.equal(meetings.length, 1);
  });
}

test("configuration schemas preserve unknown options and reject malformed authentication fields", () => {
  const credentials = new ConfigurationServiceClientCredentialFactory({});
  assert.doesNotThrow(() => new ConfigurationBotFrameworkAuthentication({ Extension: { enabled: true } }, credentials));
  assert.doesNotThrow(() => new ConfigurationBotFrameworkAuthentication({ BotOpenIdMetadata: null }, credentials));
  assert.throws(() => new ConfigurationServiceClientCredentialFactory({ MicrosoftAppId: 123 }));
  assert.throws(
    () => new ConfigurationBotFrameworkAuthentication({ ValidateAuthority: [] }, credentials),
    (error) => {
      const issues = JSON.parse(error.message);
      assert.ok(Array.isArray(issues));
      assert.deepEqual(issues[0].path, ["ValidateAuthority"]);
      return true;
    },
  );
});

test("token exchange activity records preserve conversation and arbitrary payloads", () => {
  const input = { ...activity, channelData: { arbitrary: [1, null] } };
  const result = JSON.parse(Buffer.from(UserTokenClient.createTokenExchangeState("app", "connection", input), "base64").toString());
  assert.equal(result.msAppId, "app");
  assert.equal(result.connectionName, "connection");
  assert.deepEqual(result.conversation.conversation, conversation);
  assert.throws(() => UserTokenClient.createTokenExchangeState("app", "connection", []));
});

test("custom buffer, socket, response, component and storage validators retain their contracts", () => {
  const { INodeBufferT, INodeSocketT, LogicT } = require("botbuilder/lib/zod");
  const { ResponseT } = require("botbuilder/lib/interfaces/response");
  const { BotComponent, assertStoreItems } = require("botbuilder-core");
  const callback = async () => {};
  const response = { end() {}, header() {}, send() {}, status() {} };
  const socket = { emit() {}, end() {}, off() {}, on() {}, once() {}, pipe() {}, write() {} };
  const component = { configureServices() {} };
  assert.equal(LogicT.parse(callback), callback);
  assert.equal(LogicT.safeParse({}).success, false);
  assert.equal(INodeBufferT.safeParse(Buffer.from("buffer")).success, true);
  assert.equal(INodeBufferT.safeParse("buffer").success, false);
  assert.equal(INodeSocketT.parse(socket), socket);
  assert.equal(INodeSocketT.safeParse({}).success, false);
  assert.equal(ResponseT.parse(response), response);
  assert.equal(ResponseT.safeParse({}).success, false);
  assert.equal(BotComponent.z.parse(component), component);
  assert.equal(BotComponent.z.safeParse({}).success, false);
  assert.doesNotThrow(() => assertStoreItems({ arbitrary: { nested: [1, null] } }));
  assert.throws(() => assertStoreItems([]));
});

test("connector fetch preserves string header records and rejects invalid header types", { timeout: 5000 }, async (t) => {
  const axios = require("axios");
  const calls = [];
  t.mock.method(axios, "create", () => ({
    post: async (...args) => {
      calls.push(args);
      return { status: 200, data: { ok: true } };
    },
  }));
  const { BotFrameworkClientImpl } = require("botframework-connector/lib/auth/botFrameworkClientImpl");
  const client = new BotFrameworkClientImpl({}, "https://login.example.invalid");
  const headers = { Accept: "application/json", "X-Extension": "retained" };
  const response = await client.botFrameworkClientFetch("https://skill.example.invalid", { body: "{}", headers });
  assert.equal(response.status, 200);
  assert.deepEqual(response.json(), { ok: true });
  assert.deepEqual(calls, [["https://skill.example.invalid", "{}", { headers }]]);
  await assert.rejects(client.botFrameworkClientFetch("https://skill.example.invalid", { body: "{}", headers: { Invalid: 12 } }));
  assert.equal(calls.length, 1);
});

test("existing SDK array schemas retain normal valid collection behavior", () => {
  assert.equal(schema.isActivity({
    ...activity,
    membersAdded: Array.from({ length: 1024 }, (_, i) => ({ id: String(i), name: "Member" })),
  }), true);
});

test("patched constrained collections reject oversized input before walking elements within a bounded heap", { timeout: 10000 }, () => {
  const { spawnSync } = require("node:child_process");
  const result = spawnSync(process.execPath, ["--max-old-space-size=64", "-e", `
    const assert = require("node:assert/strict");
    const z = require("zod");
    const { conversationParametersObject } = require("botframework-schema");
    let visited = 0;
    const item = z.preprocess(value => { visited++; return value; }, z.string());
    const oversized = Array(250000).fill(42);
    for (const array of [z.array(item).max(1), z.array(item).length(1)]) {
      const result = array.safeParse(oversized);
      assert.equal(result.success, false);
      assert.equal(result.error.issues.length, 1);
      assert.equal(result.error.issues[0].code, "too_big");
    }
    assert.equal(visited, 0);
    const members = conversationParametersObject.shape.activity.shape.membersAdded.unwrap().max(1);
    const sdkResult = members.safeParse(oversized);
    assert.equal(sdkResult.error.issues.length, 1);
    assert.equal(sdkResult.error.issues[0].code, "too_big");
    for (const result of [
      z.set(item).max(1).safeParse(new Set([1, 2, 3])),
      z.map(item, item).max(1).safeParse(new Map([[1, 1], [2, 2]])),
    ]) {
      assert.equal(result.error.issues.length, 1);
      assert.equal(result.error.issues[0].code, "too_big");
    }
    assert.equal(visited, 0);
    console.log("early size rejection verified");
  `], { cwd: require("node:path").join(__dirname, ".."), timeout: 5000, maxBuffer: 128 * 1024 });
  assert.equal(result.error, undefined);
  assert.equal(result.signal, null, result.stderr?.toString());
  assert.equal(result.status, 0, result.stderr?.toString());
  assert.match(result.stdout.toString(), /early size rejection verified/);
});

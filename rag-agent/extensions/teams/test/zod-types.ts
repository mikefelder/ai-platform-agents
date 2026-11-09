import { ConfigurationBotFrameworkAuthenticationOptions, ConfigurationServiceClientCredentialFactoryOptions } from "botbuilder";
import { conversationParametersObject } from "botframework-schema";
import { LogicT } from "botbuilder/lib/zod";
import { ResponseT } from "botbuilder/lib/interfaces/response";
import * as z from "zod";

type ParsedConversation = z.infer<typeof conversationParametersObject>;
type ParsedAction = NonNullable<ParsedConversation["activity"]["suggestedActions"]>["actions"][number];

const action: ParsedAction = { type: "openUrl", title: "Open", image: "", text: "", displayText: "" };
const options: ConfigurationServiceClientCredentialFactoryOptions = { MicrosoftAppType: "SingleTenant" };
const authOptions: ConfigurationBotFrameworkAuthenticationOptions = { BotOpenIdMetadata: null };
const logic: z.output<typeof LogicT> = async () => {};
const response: z.output<typeof ResponseT> = {
  socket: undefined,
  end() {},
  header() { return this; },
  send() {},
  status() { return this; },
};

conversationParametersObject.shape.activity.shape.membersAdded.unwrap().max(1);
conversationParametersObject.pick({ bot: true, isGroup: true });

// @ts-expect-error Auth configuration must not accept numeric application IDs.
const invalidOptions: ConfigurationServiceClientCredentialFactoryOptions = { MicrosoftAppId: 123 };
// @ts-expect-error The schema must still reject non-string action titles at compile time.
const invalidAction: ParsedAction = { ...action, title: 123 };

void [action, options, authOptions, logic, response, invalidOptions, invalidAction];

# Overview of the Basic Bot template

Examples of Microsoft Teams bots in everyday use include:

- Bots that notify about build failures.
- Bots that provide information about the weather or bus schedules.
- Bots that provide travel information.

A bot interaction can be a quick question and answer, or it can be a complex conversation. Being a cloud application, a bot can provide valuable and secure access to cloud services and corporate resources.

## Get started with the Basic Bot template

> **Prerequisites**
>
> To run the Basic Bot template in your local dev machine, you will need:
>
> - [Node.js](https://nodejs.org/) 22 or newer (required by the resolved Azure SDK dependencies)
> - [Teams Toolkit Visual Studio Code Extension](https://aka.ms/teams-toolkit) version 5.0.0 and higher or [Teams Toolkit CLI](https://aka.ms/teamsfx-toolkit-cli)

1. First, select the Teams Toolkit icon on the left in the VS Code toolbar.
2. Press F5 to start debugging which launches your app in Teams App Test Tool using a web browser. Select `Debug in Test Tool (Preview)`.
3. The browser will pop up to open Teams App Test Tool.
4. You will receive a welcome message from the bot, and you can send anything to the bot to get an echoed response.

**Congratulations**! You are running an application that can now interact with users in Teams App Test Tool:

![basic bot](https://github.com/OfficeDev/TeamsFx/assets/9698542/bdf87809-7dd7-4926-bff0-4546ada25e4b)

## Dependency maintenance and validation

Install from this directory using `npm ci`, then run `npm test`. The local
`.npmrc` selects the approved registry,
`https://packagefeedproxy.microsoft.io/npm/`. The lockfile was regenerated from
that registry; its tarball URLs are the Azure Artifacts endpoints returned by the
proxy, not the public npm registry. Do not switch registries to work around
missing packages.

The dependency update resolves all three reported dependency findings:

| Finding | Resolution |
| - | - |
| `follow-redirects`, CVE-2026-116689 (`>=1.16.0 <=1.16.1`) | Locked to `1.16.2` through BotBuilder's Axios dependency. |
| `uuid`, CVE-2026-41907 (`<11.1.1`) | All copies resolve to `11.1.1`, using parent-scoped overrides for BotBuilder, its core/schema/streaming packages, and MSAL Node `2.16.3`. These callers only use the compatible CommonJS `v4()` API. |
| `zod`, CVE-2023-54404 (`<4.6.6`) | All four BotBuilder consumers resolve to `4.6.6`, together with the exact-version, integrity-checked schema migration described below. No Zod 3 dependency remains. |

BotBuilder is upgraded from `4.23.2` to `4.23.3`. Its newer connector replaces
deprecated `@azure/core-http` with `@azure/core-rest-pipeline`, removing the former
Azure HTTP client's UUID 8 dependency. The connector's compatible Azure Identity
update resolves to `4.14.1`, which uses MSAL Node `7.2.1` without UUID.
BotBuilder and its connector still depend on MSAL Node `2.16.3`; its UUID override
is parent-scoped, with that exact active parent version checked by the patch
installer, rather than replacing MSAL itself across major versions.

### Maintained BotBuilder Zod 4 migration

The advisory ranges above were verified against the repository's Dependabot
alerts. The latest stable BotBuilder available on the approved feed at remediation
time was `4.23.3`, which still specifies Zod 3. A bare Zod 4 override prevents
BotBuilder from loading. Instead, `patches/botbuilder-zod4.json` records a narrow
migration of the actual Node/CommonJS SDK call sites and declarations:

- Replace `.nonstrict()` with `.passthrough()` in meeting and authentication
  configuration schemas, preserving unknown configuration/meeting fields.
- Give record schemas explicit string keys and retain their existing value
  schemas for activities, storage, entities, and HTTP headers.
- Mark card-action `value` and `channelData` explicitly optional. Zod 3 implicitly
  allowed absent `unknown` properties; Zod 4 does not.
- Use `ZodError.issues` rather than the removed `.errors` alias.
- Migrate Zod generic declarations without erasing public object shapes, array
  methods, or input/output types. The authentication index signature includes
  `null`, consistent with its existing nullable metadata option.

The dependency overrides are scoped to these four consumers, not global. There
is no runtime monkey patch or redirect to Zod's legacy `/v3` entry point.
The application still supports the same Teams features. The patch targets the
Node entry points used here, not the SDK's separately bundled browser builds.
Zod 4 diagnostics use its new format; it also rejects non-finite numbers and
ignores inherited record keys, which are not part of Teams JSON payloads.

`npm ci` runs `scripts/apply-botbuilder-zod-patch.cjs` during `postinstall`.
The installer uses only built-in Node modules, so `npm ci --omit=dev` also
applies the patch. It verifies exact installed/locked versions, the locked
package integrities, and SHA-256 hashes of every original and patched file.
Offset edits are valid only for those exact preimages; fuzzy application is
not allowed. All files are validated before any writes. Repeated application
is safe; unexpected versions, contents, symlinks, or vulnerable nested Zod
dependencies fail the install. Build and start hooks independently check that
the patch is already applied.

Do not install with `--ignore-scripts`: build/start checks deliberately reject an
unpatched installation. Keep `scripts/` and `patches/` in deployment artifacts.
The `.webappignore` exception also retains dependency declarations, which the
startup integrity check verifies alongside the JavaScript files.
For future SDK updates, first look for an upstream parent with native patched
Zod support. Otherwise, review the new sources and regenerate the explicit
patch and integrity records; never simply relax the checks.

`npm test` compiles the application and runs bounded, offline regression checks
for every scoped UUID consumer, single-tenant authentication initialization,
Teams welcome messages, mention removal, the backend request, typing indicators,
message updates, citation cards/source links, and backend failures. It also checks
the HTTP endpoint's 400/401 responses, the schema contracts established against
Zod 3 before migration, strict TypeScript declaration compatibility, and
fail-closed/idempotent patch installation.

The memory regression runs in a child with a 64 MiB heap and a five-second
timeout. Oversized constrained arrays (250,000 invalid elements), including a
size-constrained SDK member schema, are rejected with one size issue and no
element traversal; constrained maps and sets are checked too. This verifies the
upstream fix for leading upper size bounds. It does **not** claim arbitrary
unbounded schemas are constant-memory: those remain linear in input/error size.
No new collection limit is imposed on valid Teams payloads.

TypeScript's NodeNext module resolution models the Node 22+ runtime used by
current Azure packages. `strict: false` explicitly preserves this application's
previous non-strict compilation behavior under TypeScript 6's changed defaults.
These checks do not replace authenticated testing in a deployed Teams environment.

## What's included in the template

| Folder       | Contents                                            |
| - | - |
| `.vscode`    | VSCode files for debugging                          |
| `appPackage` | Templates for the Teams application manifest        |
| `env`        | Environment files                                   |
| `infra`      | Templates for provisioning Azure resources          |

The following files can be customized and demonstrate an example implementation to get you started.

| File                                 | Contents                                           |
| - | - |
|`teamsBot.ts`| Handles business logics for the Basic Bot.|
|`index.ts`|`index.ts` is used to setup and configure the Basic Bot.|

The following are Teams Toolkit specific project files. You can [visit a complete guide on Github](https://github.com/OfficeDev/TeamsFx/wiki/Teams-Toolkit-Visual-Studio-Code-v5-Guide#overview) to understand how Teams Toolkit works.

| File                                 | Contents                                           |
| - | - |
|`teamsapp.yml`|This is the main Teams Toolkit project file. The project file defines two primary things:  Properties and configuration Stage definitions. |
|`teamsapp.local.yml`|This overrides `teamsapp.yml` with actions that enable local execution and debugging.|
|`teamsapp.testtool.yml`| This overrides `teamsapp.yml` with actions that enable local execution and debugging in Teams App Test Tool.|

## Extend the Basic Bot template

Following documentation will help you to extend the Basic Bot template.

- [Add or manage the environment](https://learn.microsoft.com/microsoftteams/platform/toolkit/teamsfx-multi-env)
- [Create multi-capability app](https://learn.microsoft.com/microsoftteams/platform/toolkit/add-capability)
- [Add single sign on to your app](https://learn.microsoft.com/microsoftteams/platform/toolkit/add-single-sign-on)
- [Access data in Microsoft Graph](https://learn.microsoft.com/microsoftteams/platform/toolkit/teamsfx-sdk#microsoft-graph-scenarios)
- [Use an existing Microsoft Entra application](https://learn.microsoft.com/microsoftteams/platform/toolkit/use-existing-aad-app)
- [Customize the Teams app manifest](https://learn.microsoft.com/microsoftteams/platform/toolkit/teamsfx-preview-and-customize-app-manifest)
- Host your app in Azure by [provision cloud resources](https://learn.microsoft.com/microsoftteams/platform/toolkit/provision) and [deploy the code to cloud](https://learn.microsoft.com/microsoftteams/platform/toolkit/deploy)
- [Collaborate on app development](https://learn.microsoft.com/microsoftteams/platform/toolkit/teamsfx-collaboration)
- [Set up the CI/CD pipeline](https://learn.microsoft.com/microsoftteams/platform/toolkit/use-cicd-template)
- [Publish the app to your organization or the Microsoft Teams app store](https://learn.microsoft.com/microsoftteams/platform/toolkit/publish)
- [Develop with Teams Toolkit CLI](https://aka.ms/teams-toolkit-cli/debug)
- [Preview the app on mobile clients](https://github.com/OfficeDev/TeamsFx/wiki/Run-and-debug-your-Teams-application-on-iOS-or-Android-client)

# RAG frontend

Use Node.js 24 LTS (or another version satisfying `package.json`'s engine
requirement). Dependencies are installed through the approved Microsoft npm feed
configured in `.npmrc`:

```sh
npm ci
npm run build
npm test
npm run test:watch
```

The production build writes to `../dist/static`. To validate without writing
outside the frontend directory, use:

```sh
npm run build -- --outDir ./build-validation
```

## Test runner and dependency security

The tests use Vitest with jsdom and V8 coverage. `npm test` runs the full suite
and emits text, LCOV, HTML, and JSON coverage reports in `coverage/`.
It remains the non-watch CI entry point and exits nonzero for failed tests.
`npm run test:watch` retains coverage in watch mode. Coverage includes untested
source files and retains the previous API, mocks, entrypoint, and utility
exclusions. Existing tests import Vitest's `vi` as `jest` for the shared mock
helper API; module factories use `vi.mock` for ESM-aware hoisting.

Jest was replaced rather than forcing incompatible transitive dependency
versions. Jest 30.5.2 still uses unpatched `deepmerge` 4.3.1
(CVE-2026-93753), and its `glob` 13 dependency still requires `minimatch` 10,
within CVE-2026-118764's affected range (`>=7.0.0 <11.0.1`).
Neither dependency is needed by the replacement test stack. Vitest and its
coverage provider are pinned to matching versions. No application dependencies
were upgraded, and no existing tests or coverage capabilities were removed.

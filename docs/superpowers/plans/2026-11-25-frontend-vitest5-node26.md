# Frontend: vitest 5, jest-dom 8 and Node 26 CI

**Goal:** Move the frontend test stack to vitest 5 / `@vitest/coverage-v8` 5 / `@testing-library/jest-dom` 8 as one change, and run the frontend CI jobs on Node 26 (matching `frontend/Dockerfile`'s `node:26-slim`). This replaces Dependabot PRs #84, #86 and #87, which can't pass separately.

**Branch:** `chore/frontend-vitest5`, off `origin/main` at `1ec1dba`. Open a PR; do not merge.

## Findings (observed 2026-11-25)

- **The three Dependabot PRs are one upgrade.** Each fails `npm ci` with `ERESOLVE`:
  - vitest 5 needs a matching `@vitest/coverage-v8` (#86 and #87, split apart);
  - `@testing-library/jest-dom@8.0.0` declares `peerOptional vitest ">=5 <6"` (#84).
- **Node 26 breaks the current tests.** On `main` with Node 26.13.1 (vitest 4.1.12), all 7 tests in `src/components/ApiKeyPrompt.test.tsx` fail with `TypeError: Cannot read properties of undefined (reading 'clear')`.
  - Cause, as observed on the tested Node 26.13.1 binary: it defines an experimental global `localStorage` accessor that warns and returns `undefined` unless Node starts with `--localstorage-file`. vitest 4 doesn't install jsdom's storage over an existing global (`localStorage` isn't in its overwrite list); vitest 5 does.
  - CI is green only because the frontend jobs pin Node 22 (`ci.yml:116,151`), while the image builds on `node:26-slim` (`frontend/Dockerfile:1`).
- **vitest 5 handles it.** With the bundle, all 43 tests pass on Node 26.
- **The upgraded stack needs jest-dom's explicit Vitest entry point for matcher types.** In both jest-dom 7 and 8, the bare `import "@testing-library/jest-dom"` points TypeScript at Jest's global matcher declarations. jest-dom 8's compatibility change is in the `/vitest` entry, which now matches vitest 5's `Assertion<R, T>` signature. So with the bundle, `tsc` fails with `Property 'toBeInTheDocument' does not exist` (e.g. `src/pages/Search.test.tsx:160`) until `src/test/setup.ts` imports `@testing-library/jest-dom/vitest`.
- **The bundle, prototyped in a `/tmp` checkout on Node 26.13.1:**
  - `npm ci` and `npm ls --all` clean;
  - `tsc --noEmit` clean;
  - `vitest run --coverage`: 43/43, with 82.92% statements;
  - `npm run build` passes;
  - `npm run test:e2e`: 3 passed.
- **#85 (jsdom 30.0.1 → 31.0.1)** looks independent: it has no peer dependency on the bundle (per its package metadata). On top of the bundle, `tsc` is clean and 43/43 pass, so it stays a separate Dependabot PR for the owner to merge.
- **The frontend `npm audit` on `main` is already 0** (isolated online audit, one bulk request). This change is about the toolchain, not advisories.
- **Out of scope:** the slowapi `asyncio.iscoroutinefunction` deprecation; slowapi 0.1.10 is the latest release, so it's upstream. The anyio `CallSpec2` warning **is** fixable: anyio 4.16.0 imports `CallSpec` first and falls back to `CallSpec2` only for older pytest. Bumping anyio touches `backend/requirements*.txt`, so it goes with #89's backend lockfile changes, not here.

## Tasks

Run `npm` commands from `frontend/`, and `git` commands from the repository root (all paths below are root-relative), with npm 12.2.3 and Node 26. Use a writable `--cache` if the default npm cache is read-only. Before Task 0, `git status --porcelain --untracked-files=all` must show exactly `?? docs/superpowers/plans/2026-11-25-frontend-vitest5-node26.md`. Before each of Tasks 1–3 it must be empty (nothing staged, no pre-existing edits a restore could discard). **If a preflight check fails, stop without any restore or checkout:** the preflight exists to protect pre-existing edits. After a passing preflight, stage only the listed paths and check `git diff --cached --name-only` before committing. Recovery for Tasks 1–3, which applies only after a passing preflight and before a successful commit, is: restore that task's paths from `HEAD` (`git checkout HEAD -- <paths>`), run `npm ci` in `frontend/`, and stop. Task 0's recovery is its own (below).

### Task 0: commit this plan

Stage `docs/superpowers/plans/2026-11-25-frontend-vitest5-node26.md`. If staging or the commit fails, run `git restore --staged` on it (which keeps the file) and stop; never `checkout` it, since it isn't in `HEAD`. Commit: `docs: add frontend vitest 5 and node 26 plan`

### Task 1: vitest 5 bundle (one commit; the parts can't land separately)

1. `npm install --no-audit --no-fund -D vitest@5.1.1 @vitest/coverage-v8@5.1.1 @testing-library/jest-dom@8.0.0`
2. In `src/test/setup.ts`, change line 1 from `import "@testing-library/jest-dom";` to `import "@testing-library/jest-dom/vitest";`. Change nothing else.
3. Check:
   - `frontend/package.json` devDependencies show those three versions (with npm's default `^` prefix);
   - the lockfile resolves `node_modules/vitest` and `node_modules/@vitest/coverage-v8` to 5.1.1, and `node_modules/@testing-library/jest-dom` to 8.0.0;
   - `jsdom` stays `^30.0.1`;
   - `npm ls --all` exits 0;
   - lockfile scope, before staging: compare the new `frontend/package-lock.json` with `HEAD`'s. Every entry **not** reachable from `vitest`, `@vitest/coverage-v8` or `@testing-library/jest-dom` (through `dependencies`/`optionalDependencies` in the old or new tree) must be identical in every parsed field. The root entry must also be identical, except that its `devDependencies`/`dependencies` may change only for those three packages. The script below does this (dry-run 2026-11-25: the bundle passed with 39 in-scope changes; the bundle plus jsdom 31 failed, and so did the bundle with `@playwright/test` re-ranged `^`→`~`, as intended). Peers aren't followed, because vitest's optional `jsdom` peer is supplied by the project, not owned by vitest:

     ```bash
     W=$(mktemp -d)   # keep the helper and baseline out of the worktree
     # save the appendix's lockscope.js as "$W/lockscope.js"
     git show HEAD:frontend/package-lock.json > "$W/lock-head.json"
     node "$W/lockscope.js" "$W/lock-head.json" frontend/package-lock.json vitest @vitest/coverage-v8 @testing-library/jest-dom
     rm -rf "$W"
     ```

Stage `frontend/package.json frontend/package-lock.json frontend/src/test/setup.ts`. Commit: `fix: move frontend tests to vitest 5 and jest-dom 8`

### Task 2: frontend CI and docs on Node 26

- `.github/workflows/ci.yml`: change both `node-version: "22"` (the `frontend` and `frontend-e2e` jobs, lines 116 and 151) to `"26"`. Change nothing else.
- `README.md:91`: `Node.js 22` → `Node.js 26`.

Stage `.github/workflows/ci.yml README.md`. Commit: `ci: run frontend jobs on node 26 to match the docker image`

### Task 3: group vitest-family Dependabot updates

In `.github/dependabot.yml`, in the `npm` / `/frontend` entry's `groups`, add a group **before** `npm-minor-and-patch`. Dependabot assigns each update to the first matching group, and this group lists no `update-types`, so it takes every SemVer level, majors included (for version updates, the default `applies-to`):

```yaml
vitest:
  patterns:
    - vitest
    - "@vitest/*"
    - "@testing-library/jest-dom"
```

Indent the group key at the same level as `npm-minor-and-patch` (6 spaces), as in the snippet shifted right. Quote only where YAML needs it: `vitest` is bare, while the `@`-prefixed patterns stay quoted, because `@` is a reserved indicator. The existing `"*"` is quoted because a leading `*` starts an alias. `yamllint` runs in Trunk with `.trunk/configs/.yamllint.yaml`, whose quoted-strings rule rejects unneeded quotes.

Stage `.github/dependabot.yml`. Commit: `ci: group vitest-family dependabot updates`

## Verification

**Local.** Run the tested script below as `vis-verify.sh <checkout> <final SHA>`. It checks that the checkout's `HEAD` is that SHA and that the checkout is clean before installing, against a clean, detached checkout of the branch's final SHA placed under `/tmp` (outside `/home`, so no ancestor `node_modules` can satisfy a missing dependency), on Node 26. It must print `FRONTEND VERIFICATION PASSED`.

It needs Playwright's Chromium (`npx playwright install chromium`; on a fresh machine also its system libraries, which CI gets via `--with-deps`). It runs Playwright with `CI=true` so the suite starts its own server, rather than reusing one already on port 4173 (`playwright.config.ts:24`), and it refuses to start if that port is busy (with `CI=true`, Playwright would otherwise error on the existing server).

Dry run on 2026-11-25: against `main` it failed at the version check (vitest 4.1.12), as intended; a wrong SHA argument failed the `HEAD` check. Against the prototype bundle it passed: tsc, 43/43 with coverage and a non-empty `lcov.info`, build, and 3/3 e2e with its own server.

```bash
#!/usr/bin/env bash
# usage: vis-verify.sh <checkout root> <expected HEAD sha>   (a clean checkout outside /home, e.g. under /tmp)
# Runs visionnaire's frontend CI sequence on the local Node 26 and checks the bundle's versions.
# Needs Playwright's Chromium (`npx playwright install chromium`; CI adds --with-deps for system libs).
set -uo pipefail
unset NODE_PATH NODE_OPTIONS
[ $# -eq 2 ] || { echo "usage: vis-verify.sh <checkout root> <expected HEAD sha>"; exit 2; }
fail() { echo "FAIL: $*"; exit 1; }
cd "$1" || fail "no checkout dir"
[ "$(git rev-parse HEAD)" = "$2" ] || fail "HEAD is $(git rev-parse HEAD), expected $2"
st=$(git status --porcelain --untracked-files=all) || fail "git status failed"
[ -z "$st" ] || fail "checkout is not clean"
cd frontend || fail "no frontend dir"
here=$(realpath .) || fail "realpath"
case "$here" in /home/*) fail "run from a checkout outside /home (ancestor node_modules leak)";; esac
[ "$(node -p 'process.versions.node.split(".")[0]')" = 26 ] || fail "need Node 26, have $(node -v)"
if (exec 3<>/dev/tcp/127.0.0.1/4173) 2>/dev/null; then fail "port 4173 busy (Playwright with CI=true would refuse it)"; fi
NPMC=$(mktemp -d) && [ -d "$NPMC" ] || fail "mktemp"
trap 'rm -rf "$NPMC"' EXIT
npm ci --no-audit --no-fund --cache "$NPMC" > "$NPMC/ci.log" 2>&1 || { tail -5 "$NPMC/ci.log"; fail "npm ci"; }
npm ls --all > /dev/null 2>&1 || fail "npm ls --all"
node -e '
const l = require("./package-lock.json").packages, d = require("./package.json").devDependencies;
const want = { vitest: "5.1.1", "@vitest/coverage-v8": "5.1.1", "@testing-library/jest-dom": "8.0.0" };
for (const [n, v] of Object.entries(want)) {
  if (l["node_modules/" + n]?.version !== v) { console.error(n, "locked", l["node_modules/" + n]?.version, "want", v); process.exit(1); }
  if (d[n] !== "^" + v) { console.error(n, "range", d[n], "want ^" + v); process.exit(1); }
}
if (d.jsdom !== "^30.0.1") { console.error("jsdom range", d.jsdom, "want ^30.0.1"); process.exit(1); }
console.log("versions ok:", Object.entries(want).map(([n, v]) => n + "@" + v).join(" "), "jsdom", d.jsdom);' || fail "versions"
grep -Fxq 'import "@testing-library/jest-dom/vitest";' src/test/setup.ts || fail "setup.ts import"
npx tsc --noEmit > "$NPMC/tsc.log" 2>&1 || { tail -5 "$NPMC/tsc.log"; fail "tsc"; }
echo "tsc ok"
rm -rf coverage || fail "cannot clear old coverage"
[ ! -e coverage ] || fail "coverage dir still present"
npx vitest run --coverage > "$NPMC/vitest.log" 2>&1 || { grep -E 'FAIL|Error' "$NPMC/vitest.log" | head; fail "vitest"; }
grep -qE '^\s+Tests\s+43 passed \(43\)\s*$' "$NPMC/vitest.log" || { grep -E 'Tests ' "$NPMC/vitest.log"; fail "expected exactly 43 passed"; }
grep -E 'Test Files|Tests |All files' "$NPMC/vitest.log"
[ -s coverage/lcov.info ] || fail "coverage/lcov.info missing or empty (CI uploads it)"
if grep -qiE 'localStorage|localstorage-file' "$NPMC/vitest.log"; then grep -iE 'localStorage' "$NPMC/vitest.log" | sort -u | head -3; fail "Node 26 localStorage warning/regression in test run"; fi
npm run build > "$NPMC/build.log" 2>&1 || { tail -5 "$NPMC/build.log"; fail "build"; }
echo "build ok"
CI=true npx playwright test --reporter=list > "$NPMC/e2e.log" 2>&1 || { grep -E 'Error|failed' "$NPMC/e2e.log" | head -3; fail "e2e"; }
grep -qE '^\s*3 passed( \(|$)' "$NPMC/e2e.log" || { grep -E 'passed|failed' "$NPMC/e2e.log"; fail "expected exactly 3 e2e passed"; }
echo "e2e ok (3 passed, CI=true, own server)"
echo "FRONTEND VERIFICATION PASSED on $(node -v)"
```

Also check:

- **Scope:** `git diff --name-only 1ec1dba <SHA>` is exactly `.github/dependabot.yml`, `.github/workflows/ci.yml`, `README.md`, `docs/superpowers/plans/2026-11-25-frontend-vitest5-node26.md`, `frontend/package-lock.json`, `frontend/package.json` and `frontend/src/test/setup.ts`.
- **Lockfile:** compared with `1ec1dba`, every added, removed or re-versioned `frontend/package-lock.json` path belongs to the vitest / coverage-v8 / jest-dom dependency trees, and no unchanged entry has a `dev`/`optional`/`devOptional`/`peer` flag change.
- **Formatting:** prettier 3.9.1 is clean on the plan, README.md and setup.ts. markdownlint 0.49.0 with `.trunk/configs/.markdownlint.yaml` is clean on the plan (Trunk lints changed files).

**PR CI.** All `ci.yml` jobs green on a `pull_request` run at the final SHA:

- `lint`, `backend`, `backend-integration`, `frontend` and `frontend-e2e`;
- the `frontend` and `frontend-e2e` logs show Node 26.x;
- the run's checkout merge commit uses the live `main` as its base.

`build-push` and the deploy run only on `main`. If the Oracle deploy is red after merge, check `/api/health/ready` (home Triton) before debugging code.

## PR actions (after the PR's CI is green)

Stop before any closure unless **all** of these hold, re-checked immediately before each action:

- the new PR is `OPEN` and targets `main`, and its live head equals the **locally verified** full SHA. If a later push changed it, re-run local verification first. That head must have a green `ci.yml` `pull_request` run, whose checkout merge commit (`HEAD is now at <merge> Merge <head> into <base>`) has the live `main` (`gh api repos/b-rine/visionnaire/git/ref/heads/main`) as first parent and the verified SHA as second parent;
- the PR being closed is `OPEN`, authored by `app/dependabot`, at exactly its reviewed head, with `autoMergeRequest` `null`. If anything differs or can't be verified, stop and report.

The PRs:

- **#84, #86, #87:** reviewed heads #84 `c4bb47a`, #86 `b9fc1e0`, #87 `7a31842` (compare full SHAs from `git ls-remote`). Close each with a comment pointing to the new PR.
- **#85:** leave it for the owner, and recheck its own CI live before it merges, especially after a rebase.
- **#88:** handled separately (`perf/coca-fp16`, which home Triton serves from; its diff is only the Triton model). Not part of this plan.

## Appendix: `lockscope.js`

```js
// usage: node lockscope.js <old package-lock.json> <new package-lock.json> <root pkg> [<root pkg> ...]
// Every lockfile entry NOT reachable from the given root packages (in the old or new tree) must be
// byte-identical (all fields). Prints the in-scope changes and exits 1 on any out-of-scope change.
const fs = require("fs");
const [oldF, newF, ...roots] = process.argv.slice(2);
const A = JSON.parse(fs.readFileSync(oldF)).packages,
  B = JSON.parse(fs.readFileSync(newF)).packages;
function resolve(pk, from, name) {
  // npm's nested lookup: from "node_modules/a/node_modules/b" try deepest first
  for (let base = from; ;) {
    const k = (base ? base + "/" : "") + "node_modules/" + name;
    if (pk[k]) return k;
    if (!base) return null;
    const i = base.lastIndexOf("/node_modules/");
    base = i < 0 ? "" : base.slice(0, i);
  }
}
function reach(pk) {
  const seen = new Set(),
    stack = roots.map((r) => resolve(pk, "", r)).filter(Boolean);
  while (stack.length) {
    const k = stack.pop();
    if (seen.has(k)) continue;
    seen.add(k);
    const e = pk[k];
    // peers are supplied by the consumer (e.g. vitest peers jsdom), not owned, so they are not followed
    for (const deps of [e.dependencies, e.optionalDependencies])
      for (const n of Object.keys(deps || {})) {
        const r = resolve(pk, k, n);
        if (r) stack.push(r);
      }
  }
  return seen;
}
const inScope = new Set([...reach(A), ...reach(B)]);
const bad = [],
  changed = [];
for (const k of new Set([...Object.keys(A), ...Object.keys(B)])) {
  if (k === "") continue;
  const same = JSON.stringify(A[k]) === JSON.stringify(B[k]);
  if (same) continue;
  (inScope.has(k) ? changed : bad).push(
    `${k}: ${A[k]?.version ?? "(absent)"} -> ${B[k]?.version ?? "(absent)"}`,
  );
}
// Root entry: every field must be equal; within devDependencies/dependencies only the named roots may change.
const ra = A[""] || {},
  rb = B[""] || {};
for (const f of new Set([...Object.keys(ra), ...Object.keys(rb)])) {
  if (f === "devDependencies" || f === "dependencies") {
    const ma = ra[f] || {},
      mb = rb[f] || {};
    for (const n of new Set([...Object.keys(ma), ...Object.keys(mb)]))
      if (ma[n] !== mb[n] && !roots.includes(n))
        bad.push(`root ${f}.${n}: ${ma[n]} -> ${mb[n]}`);
  } else if (JSON.stringify(ra[f]) !== JSON.stringify(rb[f]))
    bad.push(`root field ${f} changed`);
}
console.log(`in-scope changes: ${changed.length}`);
if (bad.length) {
  console.error("OUT-OF-SCOPE CHANGES:\n" + bad.join("\n"));
  process.exit(1);
}
console.log("lockfile scope ok");
```

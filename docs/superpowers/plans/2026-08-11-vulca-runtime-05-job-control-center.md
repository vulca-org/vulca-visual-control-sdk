# VULCA Job Control Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `/workspace → /builder` redirect and sample `CreativeRepo` operating surface with an authenticated, API-backed Job Control Center for intake, queue, explicit exceptions, exact human release, delivery proof, evidence, coverage and governed memory.

**Architecture:** Add a self-contained `features/job-control` frontend package whose DTOs exactly mirror the backend camelCase API. Keep queue and responsibility as the primary navigation; expose graph/provider detail only inside developer evidence disclosure. Preserve legacy Workspace records through a clearly read-only page and keep illustrative replay/demo data on separate routes and data clients.

**Tech Stack:** React 19, TypeScript 5.8, React Router 7, Axios, Vite 7, Vitest 4, Testing Library, Playwright, existing V8 design tokens and selected Workspace presentation components.

## Global Constraints

- Before any backend Python command, run `export PATH="/opt/homebrew/opt/python@3.11/libexec/bin:$PATH"` and verify `python --version` starts with `Python 3.11.`; do not use the current unversioned Python 3.14 runtime.
- Execute this plan in `/Users/yhryzy/dev/vulca-platform` after Plan 02 DTOs and Plan 03 workflow states are frozen. Plan 04 v3 mock mechanics must pass before release/delivery E2E is considered complete.
- `/workspace` is live authenticated Job state only. It must never import `sampleCreativeRepo`, `workspaceDemo`, browser-local review stores or replay fixtures.
- Normal operators never author a DAG, choose raw provider plumbing or move artifacts through another product.
- Every state—missing input, blocked, abstained, repairing, waiting decision, reconciling, failed, cancelled—must be visible and distinct.
- The UI may request a decision; it cannot manufacture authority. Backend 401/403/409 responses remain authoritative.
- Human release confirmation names exact package hash, artifact versions and destination.
- “Mock”, “Replay”, “Shadow”, “Live” and “Pilot evidence” are explicit data modes, never styling variants of one unlabelled screen.
- Reuse visual components only after removing `CreativeRepo`/`ReviewItem` assumptions. Do not wrap the old ontology in new labels.

---

### Task 1: Add exact Job DTOs, runtime decoders and API client

**Files:**

- Create: `wenxin-moyun/src/features/job-control/types.ts`
- Create: `wenxin-moyun/src/features/job-control/decode.ts`
- Create: `wenxin-moyun/src/features/job-control/api.ts`
- Create: `wenxin-moyun/src/features/job-control/index.ts`
- Create: `wenxin-moyun/src/__tests__/features/job-control/decode.test.ts`
- Create: `wenxin-moyun/src/__tests__/features/job-control/api.test.ts`

**Required DTO union values:**

```ts
export type JobState =
  | 'RECEIVED' | 'NEEDS_INPUT' | 'READY' | 'ACTIVE'
  | 'WAITING_DECISION' | 'DELIVERING' | 'COMPLETED'
  | 'FAILED' | 'CANCELLED';

export type DataMode = 'LIVE' | 'SHADOW' | 'REPLAY' | 'MOCK';
export type EvalVerdict = 'PASS' | 'FAIL' | 'ABSTAIN';
export type CoverageRoute = 'NATIVE' | 'ADAPTED' | 'MISSING';
export type EvidenceQualifier = 'UNPROVEN' | 'BETTER' | 'EXCLUSIVE';
```

Define `JobSummary`, `JobDetail`, `JobIntakeRequest`, `JobEvent`, `ArtifactVersion`, `EvalReport`, `JobException`, `DecisionRequest`, `DeliverySummary`, `CoverageRow`, `MemoryCandidate` and cursor page types field-for-field with backend JSON.

**API functions:**

```ts
createJob(request, idempotencyKey): Promise<JobDetail>
listJobs(query): Promise<CursorPage<JobSummary>>
getJob(jobId): Promise<JobDetail>
getJobEvents(jobId, cursor?): Promise<CursorPage<JobEvent>>
supplyJobInputs(jobId, request): Promise<JobDetail>
decideJob(jobId, request): Promise<JobDetail>
cancelJob(jobId, reason): Promise<JobDetail>
listJobClasses(): Promise<JobClassSummary[]>
getCoverage(jobClassId): Promise<CoverageLedger>
decideMemoryCandidate(candidateId, request): Promise<MemoryCandidate>
```

- [ ] **Step 1: Write failing decoder and API tests**

  Test a full backend fixture, unknown state, missing package hash, non-array EvalReports, camelCase request output, `Idempotency-Key` header, cursor query and propagation of typed 401/403/409 errors.

- [ ] **Step 2: Run and verify failure**

  ```bash
  cd wenxin-moyun
  npm test -- --run src/__tests__/features/job-control/decode.test.ts src/__tests__/features/job-control/api.test.ts
  ```

  Expected: imports fail because the feature package is absent.

- [ ] **Step 3: Implement strict hand-written decoders and API calls**

  Do not add a validation dependency. Decoders must reject malformed server payloads with a safe `JobApiContractError` that names the field path without serialising customer content. Use the existing authenticated `apiClient`.

- [ ] **Step 4: Run tests and type check**

  ```bash
  npm test -- --run src/__tests__/features/job-control/decode.test.ts src/__tests__/features/job-control/api.test.ts
  npm run type-check
  ```

  Expected: all commands exit 0.

- [ ] **Step 5: Commit DTO and API boundary**

  ```bash
  git add wenxin-moyun/src/features/job-control wenxin-moyun/src/__tests__/features/job-control
  git commit -m "feat: add typed job control api client"
  ```

---

### Task 2: Restore real login and protect all live Job routes

**Files:**

- Create: `wenxin-moyun/src/features/job-control/auth.ts`
- Create: `wenxin-moyun/src/features/job-control/components/RequireJobUser.tsx`
- Create: `wenxin-moyun/src/features/job-control/components/DataModeBanner.tsx`
- Modify: `wenxin-moyun/src/pages/LoginPage.tsx`
- Modify: `wenxin-moyun/src/App.tsx`
- Modify: `wenxin-moyun/src/routes/platformModules.ts`
- Create: `wenxin-moyun/src/__tests__/features/job-control/RequireJobUser.test.tsx`
- Modify: `wenxin-moyun/src/__tests__/routes/platformModules.test.ts`
- Create: `wenxin-moyun/src/__tests__/pages/LoginPage.job-control.test.tsx`

**Route contract:**

```text
/login
/workspace
/workspace/jobs/:jobId
/workspace/exceptions
/workspace/evidence
/workspace/settings/job-classes/:jobClassId
/workspace/legacy
```

`RequireJobUser` checks for a token, calls `/auth/me`, shows a bounded loading state, redirects unauthenticated users to `/login?from=...`, and clears an invalid token. It never accepts guest headers.

- [ ] **Step 1: Write failing auth/route tests**

  Test no token redirect, valid `/auth/me`, invalid token redirect, preservation of `from`, `/workspace` ownership in `platformModules`, and a visible mode banner for every non-LIVE mode.

- [ ] **Step 2: Run and verify the current redirect failure**

  ```bash
  npm test -- --run \
    src/__tests__/features/job-control/RequireJobUser.test.tsx \
    src/__tests__/pages/LoginPage.job-control.test.tsx \
    src/__tests__/routes/platformModules.test.ts
  ```

  Expected: tests fail because `/login` redirects home and `/workspace` redirects to `/builder`.

- [ ] **Step 3: Restore `LoginPage` and protected route shell**

  Lazy-load `LoginPage`. Preserve the exact `from` destination after successful login. Hide the hard-coded demo login unless `VITE_ENABLE_DEMO_LOGIN=true`, and label it `Illustrative demo account` when enabled.

- [ ] **Step 4: Add `/workspace` to VULCA Core route ownership**

  Add `/workspace` and backend `/jobs`, `/job-classes`, `/memory-candidates` prefixes. Keep `/builder` and `/demo` as acquisition/replay surfaces, not authenticated Job truth.

- [ ] **Step 5: Run auth/route tests and type check**

  ```bash
  npm test -- --run \
    src/__tests__/features/job-control/RequireJobUser.test.tsx \
    src/__tests__/pages/LoginPage.job-control.test.tsx \
    src/__tests__/routes/platformModules.test.ts
  npm run type-check
  ```

  Expected: all commands exit 0.

- [ ] **Step 6: Commit authenticated routes**

  ```bash
  git add wenxin-moyun/src/App.tsx wenxin-moyun/src/pages/LoginPage.tsx wenxin-moyun/src/routes/platformModules.ts wenxin-moyun/src/features/job-control wenxin-moyun/src/__tests__/features/job-control wenxin-moyun/src/__tests__/pages/LoginPage.job-control.test.tsx wenxin-moyun/src/__tests__/routes/platformModules.test.ts
  git commit -m "feat: protect live job control routes"
  ```

---

### Task 3: Build business-language intake and the work queue

**Files:**

- Create: `wenxin-moyun/src/features/job-control/components/JobControlShell.tsx`
- Create: `wenxin-moyun/src/features/job-control/components/JobIntakeForm.tsx`
- Create: `wenxin-moyun/src/features/job-control/components/JobQueue.tsx`
- Create: `wenxin-moyun/src/features/job-control/components/JobStateBadge.tsx`
- Create: `wenxin-moyun/src/features/job-control/hooks/useJobQueue.ts`
- Create: `wenxin-moyun/src/pages/JobControlCenterPage.tsx`
- Create: `wenxin-moyun/src/features/job-control/job-control.css`
- Modify: `wenxin-moyun/src/App.tsx`
- Create: `wenxin-moyun/src/__tests__/features/job-control/JobIntakeForm.test.tsx`
- Create: `wenxin-moyun/src/__tests__/features/job-control/JobQueue.test.tsx`
- Create: `wenxin-moyun/src/__tests__/pages/JobControlCenterPage.test.tsx`

**Intake sections:**

1. Outcome: objective, offer/message, audience, CTA.
2. Deliverables: channels and exact formats.
3. Sources and rights: optional files/references, hash, media type, authority and rights reference.
4. Rules: BrandPack, PolicyPack and visible acceptance summary.
5. Envelope: deadline, spend cap, attempts and destination.
6. Authority: release approver and learning permission.

No free-form prompt is required. The form creates a random idempotency key once per user submission attempt and reuses it on network retry.

**Queue columns:** Job, responsibility, due, state, current blocker/exception owner, authority mode, SLA risk and last milestone. Default filters prioritise `NEEDS_INPUT`, `WAITING_DECISION`, delivery reconciliation and overdue Jobs.

- [ ] **Step 1: Write failing intake and queue tests**

  Test client validation, rights/approval fields, exact request DTO, idempotency-key reuse, `NEEDS_INPUT` rendering, explicit empty/error states, cursor load-more and no imports from `workspaceDemo` or local review stores.

- [ ] **Step 2: Run and verify failure**

  ```bash
  npm test -- --run \
    src/__tests__/features/job-control/JobIntakeForm.test.tsx \
    src/__tests__/features/job-control/JobQueue.test.tsx \
    src/__tests__/pages/JobControlCenterPage.test.tsx
  ```

  Expected: component imports fail.

- [ ] **Step 3: Implement shell, intake and queue using V8 tokens**

  Reuse spacing, typography, colour tokens and useful structural CSS from `workspace-control-room.css`, but copy only selectors required by new components into `job-control.css`. New files must not import `CreativeRepo`, `ReviewItem`, `sampleCreativeRepo` or Workspace stores.

- [ ] **Step 4: Run tests, architecture scan and type check**

  ```bash
  npm test -- --run \
    src/__tests__/features/job-control/JobIntakeForm.test.tsx \
    src/__tests__/features/job-control/JobQueue.test.tsx \
    src/__tests__/pages/JobControlCenterPage.test.tsx
  ! rg -n "sampleCreativeRepo|workspaceDemo|workspaceLocalReview|CreativeRepo|ReviewItem" src/features/job-control src/pages/JobControlCenterPage.tsx
  npm run type-check
  ```

  Expected: all commands exit 0.

- [ ] **Step 5: Commit intake and queue**

  ```bash
  git add wenxin-moyun/src/features/job-control wenxin-moyun/src/pages/JobControlCenterPage.tsx wenxin-moyun/src/App.tsx wenxin-moyun/src/__tests__/features/job-control wenxin-moyun/src/__tests__/pages/JobControlCenterPage.test.tsx
  git commit -m "feat: add campaign intake and job queue"
  ```

---

### Task 4: Build Job Detail with milestones, artifacts and independent evaluations

**Files:**

- Create: `wenxin-moyun/src/features/job-control/components/JobHeader.tsx`
- Create: `wenxin-moyun/src/features/job-control/components/JobMilestones.tsx`
- Create: `wenxin-moyun/src/features/job-control/components/ArtifactGallery.tsx`
- Create: `wenxin-moyun/src/features/job-control/components/ArtifactVersionStrip.tsx`
- Create: `wenxin-moyun/src/features/job-control/components/EvaluationPanel.tsx`
- Create: `wenxin-moyun/src/features/job-control/components/DeveloperEvidenceDrawer.tsx`
- Create: `wenxin-moyun/src/features/job-control/hooks/useJobDetail.ts`
- Create: `wenxin-moyun/src/pages/JobDetailPage.tsx`
- Modify: `wenxin-moyun/src/App.tsx`
- Create: `wenxin-moyun/src/__tests__/features/job-control/JobDetail.test.tsx`

**Customer-first view:** requested outcome, due/state, current exception, milestone chain, approved/current artifact versions, independent report verdicts, spend/SLA and delivery status.

**Developer disclosure:** RunPlan step keys/versions, StepGrant scope, provider/evaluator version and safe receipt, retries, hashes, costs, checkpoints and causal events. Never show raw chain-of-thought or unredacted credentials.

- [ ] **Step 1: Write failing detail tests across all non-happy states**

  Include active generation, repair v2 with rejected v1 retained, evaluator ABSTAIN, rights block, waiting release, reconciling delivery, failed and cancelled. Assert the execution provider and evaluator are visibly independent and versions/hashes are inspectable.

- [ ] **Step 2: Run and verify failure**

  ```bash
  npm test -- --run src/__tests__/features/job-control/JobDetail.test.tsx
  ```

  Expected: component/page imports fail.

- [ ] **Step 3: Implement detail and progressive disclosure**

  Poll active Jobs with bounded backoff and stop polling terminal states; provide manual refresh. Use semantic buttons/regions, keyboard-operable version comparison and alt text based on artifact logical name, never model-generated hidden text.

- [ ] **Step 4: Run tests, accessibility assertions and type check**

  ```bash
  npm test -- --run src/__tests__/features/job-control/JobDetail.test.tsx
  npm run type-check
  ```

  Expected: all commands exit 0.

- [ ] **Step 5: Commit Job Detail**

  ```bash
  git add wenxin-moyun/src/features/job-control wenxin-moyun/src/pages/JobDetailPage.tsx wenxin-moyun/src/App.tsx wenxin-moyun/src/__tests__/features/job-control/JobDetail.test.tsx
  git commit -m "feat: expose job artifacts evaluations and evidence"
  ```

---

### Task 5: Build Exception Inbox and exact human release confirmation

**Files:**

- Create: `wenxin-moyun/src/features/job-control/components/ExceptionInbox.tsx`
- Create: `wenxin-moyun/src/features/job-control/components/ExceptionDecisionPanel.tsx`
- Create: `wenxin-moyun/src/features/job-control/components/ReleaseConfirmation.tsx`
- Create: `wenxin-moyun/src/features/job-control/components/DeliveryReceiptPanel.tsx`
- Create: `wenxin-moyun/src/pages/JobExceptionsPage.tsx`
- Modify: `wenxin-moyun/src/pages/JobDetailPage.tsx`
- Modify: `wenxin-moyun/src/App.tsx`
- Create: `wenxin-moyun/src/__tests__/features/job-control/ExceptionInbox.test.tsx`
- Create: `wenxin-moyun/src/__tests__/features/job-control/ReleaseConfirmation.test.tsx`

Every exception shows: what stopped, why, exact owner, safe options, consequence of each option, affected artifact/version/hash, added spend/attempt if applicable and whether a new JobSpec is required.

Release confirmation requires the user to inspect and affirm:

```text
package SHA-256
included ArtifactVersion IDs and hashes
required EvalReport verdicts
destination URI
naming/package manifest
ReleaseToken expiry semantics
```

The submit button says `Approve exact package and deliver`, never `Publish automatically`.

- [ ] **Step 1: Write failing exception and release tests**

  Test missing-input edit, repair request, policy block, ABSTAIN escalation, stale-version 409 refresh, approver 403, double-click idempotency, release hash mismatch refusal, reconciling state and confirmed receipt.

- [ ] **Step 2: Run and verify failure**

  ```bash
  npm test -- --run \
    src/__tests__/features/job-control/ExceptionInbox.test.tsx \
    src/__tests__/features/job-control/ReleaseConfirmation.test.tsx
  ```

  Expected: component imports fail.

- [ ] **Step 3: Implement one-decision-at-a-time UX**

  Disable action buttons while a request is in flight, retain the decision ID across retry, and refresh exact Job state after 409. Do not optimistically show completion; wait for DeliveryReceipt from the backend.

- [ ] **Step 4: Run tests and type check**

  ```bash
  npm test -- --run \
    src/__tests__/features/job-control/ExceptionInbox.test.tsx \
    src/__tests__/features/job-control/ReleaseConfirmation.test.tsx
  npm run type-check
  ```

  Expected: all commands exit 0.

- [ ] **Step 5: Commit exception and release surfaces**

  ```bash
  git add wenxin-moyun/src/features/job-control wenxin-moyun/src/pages/JobExceptionsPage.tsx wenxin-moyun/src/pages/JobDetailPage.tsx wenxin-moyun/src/App.tsx wenxin-moyun/src/__tests__/features/job-control
  git commit -m "feat: add exception and exact release workflows"
  ```

---

### Task 6: Add coverage, trust, memory and read-only legacy evidence surfaces

**Files:**

- Create: `wenxin-moyun/src/features/job-control/components/CoverageLedger.tsx`
- Create: `wenxin-moyun/src/features/job-control/components/MemoryCandidateList.tsx`
- Create: `wenxin-moyun/src/features/job-control/components/LegacyWorkspaceEvidence.tsx`
- Create: `wenxin-moyun/src/pages/JobClassSettingsPage.tsx`
- Create: `wenxin-moyun/src/pages/JobEvidencePage.tsx`
- Create: `wenxin-moyun/src/pages/LegacyWorkspaceEvidencePage.tsx`
- Modify: `wenxin-moyun/src/App.tsx`
- Create: `wenxin-moyun/src/__tests__/features/job-control/GovernanceSurfaces.test.tsx`

Coverage displays route and evidence as separate axes. It must not visually equate `NATIVE` with `BETTER`; `UNPROVEN` is visible. Plan 06 adds aggregate operating metrics only after the backend derives them from canonical evidence; this task must not invent frontend totals.

Memory actions require a named scope/expiry and show exact supporting evidence. Legacy page consumes only read-only legacy references and displays `Legacy evidence — not active Job state`.

- [ ] **Step 1: Write failing governance tests**

  Test `MISSING`, `ADAPTED`, `NATIVE`, `UNPROVEN`, `BETTER`, `EXCLUSIVE` rendering; no aggregate trust score or client-computed operating total; memory remains proposed until decision; revocation visible; legacy page has no save/review/release controls and no old write API calls.

- [ ] **Step 2: Run and verify failure**

  ```bash
  npm test -- --run src/__tests__/features/job-control/GovernanceSurfaces.test.tsx
  ```

  Expected: component imports fail.

- [ ] **Step 3: Implement governance and legacy read surfaces**

  Add the pages to protected routes. Keep the historical `WorkspacePage.tsx` and tests for provenance if useful, but do not route live users to it and do not extend its write workflow.

- [ ] **Step 4: Run tests, route scan and type check**

  ```bash
  npm test -- --run src/__tests__/features/job-control/GovernanceSurfaces.test.tsx
  ! rg -n "workspace/review-state|agent-review" src/features/job-control src/pages/LegacyWorkspaceEvidencePage.tsx
  npm run type-check
  ```

  Expected: all commands exit 0.

- [ ] **Step 5: Commit governance surfaces**

  ```bash
  git add wenxin-moyun/src/features/job-control wenxin-moyun/src/pages/JobClassSettingsPage.tsx wenxin-moyun/src/pages/JobEvidencePage.tsx wenxin-moyun/src/pages/LegacyWorkspaceEvidencePage.tsx wenxin-moyun/src/App.tsx wenxin-moyun/src/__tests__/features/job-control/GovernanceSurfaces.test.tsx
  git commit -m "feat: expose job coverage trust and memory controls"
  ```

---

### Task 7: Replace the old Workspace E2E contract with the live Job loop

**Files:**

- Replace: `wenxin-moyun/tests/e2e/specs/workspace.spec.ts`
- Modify: `wenxin-moyun/tests/e2e/specs/public-release.spec.ts`
- Create: `wenxin-moyun/tests/e2e/fixtures/job-runtime.ts`
- Modify: `wenxin-moyun/package.json`
- Modify: `wenxin-moyun/src/__tests__/config/publicReleaseWorkflow.test.ts`
- Create: `wenxin-moyun/src/__tests__/config/jobControlArchitecture.test.ts`

The E2E fixture starts or targets the test API, authenticates a test operator, seeds the static JobClass/packs, uses the mock capability provider and returns exact cleanup IDs. It does not seed frontend sample state.

**E2E scenarios:**

1. unauthenticated `/workspace` redirects to login and returns after login;
2. create complete Job and observe queue/milestones after page reload;
3. create missing-rights Job, supply authorised input, then continue;
4. inspect primary/master/variant lineage and independent reports;
5. request one repair and verify v1 remains visible beside v2;
6. approve exact package, wait for real backend receipt, reload and retain completed state;
7. create delivery conflict and see reconciliation exception rather than duplicate write;
8. verify demo/replay never appears as LIVE evidence;
9. verify no graph/canvas/provider selector is required on the routine path.

- [ ] **Step 1: Write the new E2E tests and verify red against the redirect/sample surface**

  ```bash
  cd wenxin-moyun
  npm run test:e2e:workspace
  ```

  Expected: failures show `/workspace` redirect/current backend wiring mismatches before all prior tasks land.

- [ ] **Step 2: Implement fixture and finish route wiring**

  Update `test:e2e:workspace` only if needed to start the declared API fixture; do not hide backend failures with route interception. Network interception may inject deterministic provider output behind the backend adapter, not fabricate frontend Job responses.

- [ ] **Step 3: Run focused frontend and E2E suites**

  ```bash
  npm run type-check
  npm test -- --run src/__tests__/features/job-control src/__tests__/pages/JobControlCenterPage.test.tsx src/__tests__/routes/platformModules.test.ts src/__tests__/config/jobControlArchitecture.test.ts
  npm run test:e2e:workspace
  ```

  Expected: all commands exit 0.

- [ ] **Step 4: Run build and architecture scans**

  ```bash
  npm run build
  ! rg -n "sampleCreativeRepo|workspaceDemo|workspaceLocalReview|CreativeRepo|ReviewItem" src/features/job-control src/pages/JobControlCenterPage.tsx src/pages/JobDetailPage.tsx src/pages/JobExceptionsPage.tsx
  ```

  Expected: build and scan exit 0.

- [ ] **Step 5: Commit the live E2E contract**

  ```bash
  git add wenxin-moyun/tests/e2e wenxin-moyun/package.json wenxin-moyun/src/__tests__/config
  git commit -m "test: cover the live job control loop"
  ```

---

## Plan 05 completion gate

- [ ] `/workspace` is authenticated live Job state, not a redirect, sample repo or browser-local store.
- [ ] An operator can submit, monitor, resolve named exceptions, inspect exact versions, approve an exact package and verify a backend DeliveryReceipt.
- [ ] Routine completion requires no DAG/canvas authoring, prompt engineering, raw provider selection or competitor UI.
- [ ] Coverage/evidence axes and operating metrics remain separate; `UNPROVEN` is visible.
- [ ] Mock/replay/live/Shadow states are technically and visually distinct.
- [ ] Legacy records are read-only and not a second execution ontology.
- [ ] Focused unit, type, build and live-backend E2E checks pass.

This gate proves usability of the implementation candidate. It does not prove deployment, paid use, queue ownership or role replacement.

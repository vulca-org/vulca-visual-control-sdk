# Repository Registry Governance Design

**Status:** Approved revision
**Date:** 2026-07-10
**Scope:** Stable public repository registry plus on-demand private state snapshots

## Problem

Vulca is distributed across public product repositories, public research and
historical repositories, private development repositories, local-only
repositories, and multiple Git worktrees. The current documentation names some
of these surfaces, but it does not provide one durable registry of authority,
lifecycle, synchronization direction, or release responsibility.

This creates observable drift:

- published descriptions can report a different MCP tool count from the code;
- package, tag, GitHub Release, plugin, and embedded platform versions can
  diverge;
- a copied SDK or plugin directory can be mistaken for its canonical source;
- migrated or archived repositories can still appear active;
- local worktree state can be confused with the GitHub default branch;
- a comprehensive internal inventory cannot safely be committed to the public
  SDK repository.

## Goals

1. Establish a public-safe source of truth for Vulca's public repositories.
2. Distinguish canonical, supporting, historical, migrated, and archived
   repositories.
3. Record what each repository is authoritative for and how it synchronizes.
4. Derive volatile SDK facts, including the package version and MCP tool count,
   from code instead of duplicating them by hand.
5. Maintain stable local scan seeds for private repositories and discover
   branches, worktrees, and cleanup signals only when a snapshot is requested.
6. Fail closed when public output contains local or private operational data.
7. Keep public generation deterministic and private scanning read-only,
   testable, and non-blocking for normal feature development.

## Non-Goals

- Automatically fetching, checking out, merging, pushing, or deleting Git
  branches or worktrees.
- Treating a registry entry as evidence that a repository is healthy, tested,
  released, or production-ready.
- Publishing private repository names, local absolute paths, credentials,
  account data, or private release-readiness evidence.
- Replacing GitHub, PyPI, or repository manifests as the authority for their own
  current state.
- Building a general asset inventory for datasets, PDFs, screenshots, generated
  images, or application materials.
- Requiring developers to update branch, HEAD, ahead/behind, or worktree state
  after ordinary feature commits.
- Running a daemon, background monitor, database, or mandatory private scan in
  CI.

## Chosen Approach

Use a structured public source plus a generated public document. Keep a small
local seed file for stable private identities and repository roots, then create
fresh operational snapshots only when explicitly requested.

The public repository contains:

```text
docs/product/repository-registry.yaml
  -> scripts/build_repository_registry.py
  -> docs/product/repository-registry.md
  -> tests/test_repository_registry.py
```

The local private layer contains stable seeds and disposable snapshots:

```text
~/.vulca/repository-registry-seeds.private.yaml
  -> scripts/build_repository_registry.py --snapshot-private --private-seeds ...
  -> ~/.vulca/repository-registry-snapshot.private.json
  -> ~/.vulca/repository-registry-snapshot.private.md
```

The default invocation reads and writes only public files. Private scanning
requires an explicit snapshot flag, seed path, and output paths. It never runs
in CI and never runs as a side effect of public generation.

## Public Registry Contract

The public YAML document has a top-level schema version, a manually updated
verification date, explanatory policy text, and an ordered list of repository
records.

Each public repository record contains:

| Field | Meaning |
| --- | --- |
| `id` | Stable lowercase identifier, unique across the registry |
| `name` | Public repository name |
| `owner` | Public GitHub owner |
| `visibility` | Must be `public` in the committed registry |
| `role` | `sdk`, `plugin`, `adapter`, `research`, `website`, or `legacy` |
| `lifecycle` | `canonical`, `active-supporting`, `historical`, `migrated`, or `archived` |
| `canonical_for` | Public objects or responsibilities owned by this repository |
| `sync_direction` | Explicit source-to-destination relationship, or `none` |
| `version_source` | Manifest, tag, release, dataset version, or `not-applicable` |
| `release_channels` | Public distribution channels used by the repository |
| `public_url` | Canonical public HTTPS GitHub URL |
| `notes` | Short public-safe boundary or migration note |

The public registry can contain only repositories already public on GitHub. A
private development source may be described generically in policy prose, such
as "a private development monorepo syncs selected content into the public SDK",
but it must not receive a repository record, name, URL, path, or branch.

## Derived Public Facts

The generator derives these facts for the canonical SDK record:

- `sdk_version` from `[project].version` in `pyproject.toml`;
- `mcp_tool_count` from the number of `@mcp.tool()` registrations in
  `src/vulca/mcp_server.py`.

These values are rendered into Markdown but are not stored as editable values in
the YAML records. If the generator cannot read either source, it fails instead
of preserving a stale value.

Other repositories keep their declared version authority explicit. The first
iteration does not inspect remote tags, GitHub Releases, PyPI, or copied platform
subtrees at generation time. Those are audit inputs, not deterministic build
inputs.

## Private Seed Contract

The private seed YAML stores only facts that remain stable across ordinary
development:

| Field | Meaning |
| --- | --- |
| `id` | Stable private identifier |
| `full_name` | GitHub owner/repository identity when one exists |
| `visibility` | `public`, `private`, or `local-only` |
| `lifecycle` | Repository lifecycle classification |
| `local_roots` | Canonical local checkout roots to scan |
| `expected_remote` | Expected Git remote identity, used only for mismatch detection |
| `sensitivity` | `public`, `internal`, or `restricted` |
| `release_boundary` | Human or project gate that blocks public treatment |
| `sync_relationship` | Relationship to a canonical public repository |

The seed file does not store HEADs, current branches, ahead/behind counts,
worktree cleanliness, timestamps, or cleanup priorities. It changes only when a
repository is added, migrated, archived, renamed, moved locally, or assigned a
different authority/release role.

## Private Snapshot Contract

An explicit private scan expands each seed into a timestamped JSON and Markdown
snapshot. The scanner discovers:

| Field | Meaning |
| --- | --- |
| `observed_at` | UTC observation timestamp for the whole snapshot |
| `availability` | `available`, `missing`, or `not-a-repository` |
| `local_path` | Observed checkout or worktree path |
| `remote_url` | Configured remote, if readable |
| `current_branch` | Checked-out branch or `detached` |
| `head` | Observed commit identifier |
| `comparison_ref` | Local tracking ref used for comparison, if present |
| `ahead` / `behind` | Counts against `comparison_ref`, or `unknown` |
| `worktree_state` | `clean`, `modified`, `untracked`, or `mixed` |
| `prunable` | Whether Git reports a stale worktree record |
| `recommended_action` | Non-mutating, human-reviewed next action |

The scanner discovers additional worktrees through `git worktree list
--porcelain`; they are not enumerated in the seed file. A missing checkout is
recorded in the snapshot rather than causing the public registry or normal CI to
fail.

The seed and snapshot files must not store tokens, credentials, environment
values, email content, private session content, or copied evidence payloads.
They record identity, state, and routing only.

## Public-Safety Validation

Public generation fails when any of the following is present:

- an absolute macOS, Linux, or Windows path;
- a `file://` URL, SSH Git URL, or localhost URL;
- fields reserved for the private schema, including `local_path`, `remote_url`,
  `head`, worktree fields, sensitivity, or cleanup fields;
- a repository record whose declared visibility is not public;
- a URL that is not canonical HTTPS GitHub repository form;
- credential-like keys or values, including common token and secret patterns;
- `.env`, credential, session, or private-evidence path fragments;
- duplicate IDs or duplicate public URLs;
- an unsupported role or lifecycle value;
- a canonical record without a non-empty `canonical_for` list;
- a migrated record without a public replacement or migration note;
- an archived record that declares an active release channel.

When private seeds are explicitly supplied during a local validation run, their
non-public repository names and URLs are also treated as a denylist for public
output. CI cannot rely on the seed file, so structural leak checks remain
mandatory without it.

## Generation Behavior

The generator:

1. Loads and validates the YAML source.
2. Reads the SDK version and MCP registrations from the current checkout.
3. Builds a stable Markdown model in YAML order.
4. Renders policy, canonical repositories, supporting repositories, historical
   repositories, derived facts, sync boundaries, and maintenance instructions.
5. Writes only when the requested output differs.

The `--check` mode performs the same work without writing and exits non-zero when
the committed Markdown is stale. Output contains no runtime timestamp; the
manually maintained `verified_on` value prevents nondeterministic diffs.

Private scanning is explicit. If `--snapshot-private` is omitted, the generator
does not inspect `~/.vulca`, Git configuration, GitHub authentication, or the
filesystem outside the current repository.

With `--snapshot-private`, the scanner:

1. loads and validates the stable private seeds;
2. runs only read-only local Git commands against configured roots;
3. discovers linked worktrees through `git worktree list --porcelain`;
4. records local tracking-ref comparison when it exists, otherwise uses
   `unknown` without fetching;
5. renders a JSON authority artifact and a Markdown reading view with the same
   `observed_at` timestamp;
6. writes snapshots only after complete validation.

GitHub refresh is a separate `--refresh-github` opt-in. It may call the `gh` CLI
to refresh visibility, archival state, and default-branch metadata, but it never
runs by default and never changes the stable seed file automatically. Failure or
missing authentication is reported in the private snapshot and does not affect
public generation.

All external commands use a single injected command runner with list-based
arguments, `shell=False`, captured text output, and bounded timeouts. Local Git
commands have a 10-second timeout; optional `gh` calls have a 30-second timeout.
The scanner accepts no free-form command fragments and supports only the fixed
read-only Git/GitHub operations named in this design. Paths are passed as single
arguments so spaces or punctuation cannot become shell syntax.

## Error Handling

- YAML syntax or schema errors identify the field and record ID.
- Safety violations identify the category and field but do not echo suspected
  secret values.
- Missing code-derived sources identify the missing relative path.
- Markdown drift under `--check` reports the expected regeneration command.
- Partial output is never written. The complete rendered content is validated
  before `Path.write_text` is called.
- A missing local checkout becomes `availability=missing` in the private
  snapshot instead of aborting the scan.
- A Git command timeout or unreadable checkout records a bounded error category
  without echoing command environment or credential values.
- Optional GitHub refresh failure is recorded as unavailable external metadata;
  local Git discovery still completes.

## Testing Strategy

`tests/test_repository_registry.py` covers:

1. the committed YAML passes schema and public-safety validation;
2. generation is deterministic;
3. generated Markdown matches the committed Markdown;
4. package version is derived from `pyproject.toml`;
5. MCP tool count is derived from `src/vulca/mcp_server.py`;
6. duplicate identifiers and URLs fail;
7. unknown roles and lifecycle values fail;
8. absolute paths and private-only fields fail;
9. credential-like content fails without being repeated in the error;
10. migrated and archived lifecycle invariants fail when incomplete;
11. optional private seeds denylist a matching non-public record;
12. private seeds reject volatile HEAD, branch, ahead/behind, and worktree-state
    fields;
13. a temporary Git repository produces branch, HEAD, remote, and cleanliness
    facts without mutation;
14. linked and prunable worktree porcelain fixtures are parsed correctly;
15. missing repositories produce `availability=missing` without public failure;
16. JSON and Markdown snapshots share one timestamp and the same record set;
17. optional GitHub refresh is isolated behind an injected command runner and is
    never invoked by public generation;
18. command construction uses list arguments, `shell=False`, fixed allowlisted
    operations, and preserves paths containing spaces as one argument.

Tests use temporary Git repositories and injected command-runner fixtures. No
test reads the real private seed file, user home directory, global Git
configuration, network, GitHub authentication, or credentials.

## Initial Public Registry Scope

The first public registry includes every currently identified public Vulca
repository and classifies each as canonical, supporting, historical, migrated,
or archived. It excludes all private repositories even when the current operator
can access them.

The canonical public product set is:

- the SDK/CLI/MCP repository;
- the agent plugin repository;
- the ComfyUI adapter repository.

Public research repositories and earlier public exhibition, framework, skill,
and benchmark repositories appear in supporting or historical sections. A
migration note points readers from superseded public surfaces to their public
replacement when one exists.

## Maintenance Workflow

1. Edit `docs/product/repository-registry.yaml`.
2. Run the generator.
3. Run the registry test module.
4. Review the Markdown diff for public-safety and lifecycle accuracy.
5. Commit YAML, generated Markdown, generator, and tests together.

Private seeds change only for structural events: new repository, rename,
migration, archival, local-root move, authority change, or release-boundary
change. Ordinary commits and worktrees require no seed edit.

Private snapshots remain outside Git and are refreshed on demand:

```bash
python scripts/build_repository_registry.py \
  --snapshot-private \
  --private-seeds ~/.vulca/repository-registry-seeds.private.yaml \
  --private-json ~/.vulca/repository-registry-snapshot.private.json \
  --private-markdown ~/.vulca/repository-registry-snapshot.private.md
```

Add `--refresh-github` only when current GitHub metadata is needed and
authentication is already available. The generator never performs repository
cleanup. `recommended_action` remains a human-reviewed queue for a later task.

## Acceptance Criteria

- A reviewer can identify the public canonical repository for each shipped
  Vulca surface without reading multiple READMEs.
- Public records contain no private repository identifiers, local paths,
  worktree state, credentials, or restricted evidence references.
- The generated Markdown reports the SDK version and MCP tool count currently in
  code.
- Re-running generation produces no diff.
- `--check` detects stale generated output.
- Invalid lifecycle, duplicate, and leak-prone records fail with actionable
  errors.
- Private scanning is opt-in, discovers current worktrees without manually
  listing them, and writes only to explicitly supplied local snapshot paths.
- Ordinary feature commits do not require public-registry or private-seed
  updates.
- Missing private repositories, dirty worktrees, and unavailable GitHub metadata
  do not fail public generation or CI.
- Private JSON and Markdown outputs identify their observation time and never
  present dynamic state as timeless authority.
- No registry command fetches, checks out, pushes, deletes, or otherwise mutates
  a Git repository.

# Repository Registry Governance Design

**Status:** Approved design
**Date:** 2026-07-10
**Scope:** Public repository registry plus a local private supplement

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
5. Maintain a local private supplement for private repositories, local paths,
   worktrees, branch state, and cleanup priorities.
6. Fail closed when public output contains local or private operational data.
7. Keep generation deterministic and testable without modifying repositories or
   contacting remote services.

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

## Chosen Approach

Use a structured public source plus a generated public document, and reuse the
same conceptual schema for an explicitly invoked local private supplement.

The public repository contains:

```text
docs/product/repository-registry.yaml
  -> scripts/build_repository_registry.py
  -> docs/product/repository-registry.md
  -> tests/test_repository_registry.py
```

The local private layer contains:

```text
~/.vulca/repository-registry.private.yaml
  -> scripts/build_repository_registry.py --private-source ... --private-output ...
  -> ~/.vulca/repository-registry.private.md
```

The default generator invocation reads and writes only the public files. Private
generation requires explicit private input and output arguments. No private
path is a default.

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

## Private Supplement Contract

The private YAML uses the public identity and lifecycle fields where applicable,
then adds operational fields:

| Field | Meaning |
| --- | --- |
| `local_path` | Local repository or worktree path |
| `remote_url` | Configured Git remote, if any |
| `visibility` | `public`, `private`, or `local-only` |
| `default_branch` | Remote default branch when known |
| `current_branch` | Checked-out branch or `detached` |
| `head` | Observed commit identifier |
| `ahead` / `behind` | Observed relationship to the named comparison ref |
| `worktree_state` | `clean`, `modified`, `untracked`, or `mixed` |
| `sensitivity` | `public`, `internal`, or `restricted` |
| `release_boundary` | Human or project gate that blocks public treatment |
| `sync_relationship` | Relationship to a canonical public repository |
| `cleanup_priority` | `none`, `low`, `medium`, or `high` |
| `recommended_action` | Bounded next action; never an automatic mutation |

The private supplement must not store tokens, credentials, environment values,
email content, private session content, or copied evidence payloads. It records
state and routing, not secrets or artifact bodies.

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

When the optional private source is available during a local validation run,
its repository names and URLs are also treated as a denylist for public output.
CI cannot rely on the private file, so structural leak checks remain mandatory
without it.

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

Private generation is explicit. If private arguments are omitted, the generator
does not inspect `~/.vulca`, Git configuration, GitHub authentication, or the
filesystem outside the current repository. If a requested private source is
missing or invalid, private generation fails without changing the public output.

## Error Handling

- YAML syntax or schema errors identify the field and record ID.
- Safety violations identify the category and field but do not echo suspected
  secret values.
- Missing code-derived sources identify the missing relative path.
- Markdown drift under `--check` reports the expected regeneration command.
- Partial output is never written. The complete rendered content is validated
  before `Path.write_text` is called.

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
11. an optional private denylist blocks a matching public record;
12. a missing explicitly requested private source leaves public files unchanged.

Tests use temporary files for unsafe fixtures. No test reads the real private
supplement, user home directory, Git configuration, network, or credentials.

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

Private maintenance uses explicit paths and remains outside Git:

```bash
python scripts/build_repository_registry.py \
  --private-source ~/.vulca/repository-registry.private.yaml \
  --private-output ~/.vulca/repository-registry.private.md
```

The generator never performs repository cleanup. `recommended_action` remains a
human-reviewed queue for a later task.

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
- Private generation is opt-in and writes only to the explicitly supplied local
  output path.
- No registry command fetches, checks out, pushes, deletes, or otherwise mutates
  a Git repository.

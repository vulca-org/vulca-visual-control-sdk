# Vulca Public Repository Registry

> Generated from `docs/product/repository-registry.yaml`; authority facts verified on `2026-07-10`.

## Policy

Only public repositories appear as records. This registry describes stable authority, lifecycle, synchronization, and release boundaries; dynamic branch, commit, worktree, and local availability state remains outside the public artifact.

## Canonical repositories

### [vulca-org/vulca](https://github.com/vulca-org/vulca)

- Role: `sdk`
- Lifecycle: `canonical`
- Canonical for: Vulca Python SDK, Vulca CLI, Vulca MCP server, Public SDK documentation
- Synchronization: A non-public development source may export selected public-safe changes into this repository; this repository is the public distribution source.
- Version authority: pyproject.toml
- Release channels: PyPI, GitHub tags, GitHub Releases
- SDK version: `0.23.1`
- MCP tool count: `23`
- Boundary note: Canonical public product and developer surface.

### [vulca-org/vulca-plugin](https://github.com/vulca-org/vulca-plugin)

- Role: `plugin`
- Lifecycle: `canonical`
- Canonical for: Vulca agent plugin distribution
- Synchronization: Selected public SDK skills synchronize from vulca-org/vulca into this plugin distribution repository.
- Version authority: Plugin manifest
- Release channels: GitHub repository
- Boundary note: Canonical plugin packaging surface; it does not replace the SDK source.

### [vulca-org/comfyui-vulca](https://github.com/vulca-org/comfyui-vulca)

- Role: `adapter`
- Lifecycle: `canonical`
- Canonical for: Vulca ComfyUI adapter
- Synchronization: Adapter releases consume public Vulca SDK contracts; adapter-specific nodes remain authoritative in this repository.
- Version authority: Package manifest and Git tags
- Release channels: GitHub tags, GitHub Releases
- Boundary note: Canonical ComfyUI integration surface.

## Active supporting repositories

### [yha9806/VULCA-Bench](https://github.com/yha9806/VULCA-Bench)

- Role: `research`
- Lifecycle: `active-supporting`
- Canonical for: Public VULCA-Bench research artifacts
- Synchronization: none
- Version authority: Dataset and repository revisions
- Release channels: GitHub repository
- Boundary note: Supporting benchmark research; it is not the SDK release authority.

### [yha9806/VULCA-Framework](https://github.com/yha9806/VULCA-Framework)

- Role: `research`
- Lifecycle: `active-supporting`
- Canonical for: Public VULCA framework research artifacts
- Synchronization: none
- Version authority: Repository revisions
- Release channels: GitHub repository
- Boundary note: Supporting research framework; it is not the SDK release authority.

## Historical repositories

### [yha9806/EMNLP2025-VULCA](https://github.com/yha9806/EMNLP2025-VULCA)

- Role: `research`
- Lifecycle: `historical`
- Canonical for: Historical EMNLP 2025 research artifacts
- Synchronization: none
- Version authority: Repository revision
- Release channels: GitHub repository
- Boundary note: Historical paper surface retained for research traceability.

### [yha9806/VULCA-EMNLP2025](https://github.com/yha9806/VULCA-EMNLP2025)

- Role: `website`
- Lifecycle: `historical`
- Canonical for: Historical EMNLP 2025 project website
- Synchronization: none
- Version authority: Repository revision
- Release channels: GitHub Pages
- Boundary note: Historical website surface; current product documentation lives with the SDK.

## Migrated repositories

### [yha9806/vulca-exhibition](https://github.com/yha9806/vulca-exhibition)

- Role: `legacy`
- Lifecycle: `migrated`
- Canonical for: Historical exhibition implementation
- Synchronization: Superseded by vulca-org/vulca and current public product documentation; no reverse synchronization is expected.
- Version authority: Repository revision
- Release channels: none
- Boundary note: Migrated to the canonical public SDK and current product surfaces.

## Archived repositories

### [yha9806/claude-skills-vulca](https://github.com/yha9806/claude-skills-vulca)

- Role: `legacy`
- Lifecycle: `archived`
- Canonical for: Historical Vulca skill distribution
- Synchronization: none
- Version authority: Repository revision
- Release channels: none
- Boundary note: Archived historical surface; current skills ship through canonical repositories.

## Maintenance

1. Edit `docs/product/repository-registry.yaml` only for stable authority or lifecycle changes.
2. Run `python scripts/build_repository_registry.py` to regenerate this document.
3. Run `python scripts/build_repository_registry.py --check` before committing.

Dynamic branches, commits, worktrees, and local availability are intentionally excluded from this public view.

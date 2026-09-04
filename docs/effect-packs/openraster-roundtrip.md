# OpenRaster round-trip Effect Pack

Status: advanced / experimental

`openraster-roundtrip` is a non-generative engineering Effect Pack. It moves an existing VULCA layered Artifact or manifest through a flat OpenRaster (`.ora`) document and back without invoking an image provider. It does not claim an artistic improvement and does not score visual quality.

The implementation follows the OpenRaster 0.0.6 file-layout and layer-stack contracts: `mimetype` is the first uncompressed ZIP member, `stack.xml` lists the uppermost layer first, and the archive includes `mergedimage.png`, `Thumbnails/thumbnail.png`, and per-layer PNG files under `data/`.

## Protected invariants

A no-edit round trip protects:

- canvas width and height;
- layer count and stable IDs;
- names and bottom-to-top ordering;
- visibility, opacity, and supported blend modes;
- every layer's decoded RGBA pixels;
- the recomposited RGBA result.

The importer records the source ORA hash, source document hash, before/after layer RGBA hashes, and composite hashes in `openraster-roundtrip.json`. Provider, model, prompt, seed, cost, and latency are recorded as `not_applicable` because no model is called.

## SDK-native contract mapping

This pack does not import Layered Redraw's `project.json`, design-plan, preset, history, or editor-server contracts. The SDK remains authoritative:

| Concern | Canonical SDK contract | OpenRaster representation |
|---|---|---|
| project document | existing Artifact V3 or `manifest.json` | `vulca.json` is an interchange sidecar only, never a second project database |
| layer identity | `LayerInfo.id` | sidecar ID, `vulca:id` XML extension, and reversible name marker |
| layer order | unique `LayerInfo.z_index` values | topmost-first `stack.xml`; imported order is written back into the existing z-index slots |
| editable pixels | full-canvas RGBA layer PNG | `data/*.png` |
| visibility / opacity / blend | existing `LayerInfo` fields | standard ORA layer attributes |
| output and evidence | existing manifest plus operation evidence | new canonical `manifest.json`, `composite.png`, and `openraster-roundtrip.json` |

The sidecar retains additional source metadata for comparison, but the protected first-version contract is intentionally limited to the invariants listed above. Artifact-only fields outside the current manifest writer are not claimed as round-trip invariants.

## API

```python
from vulca.layers import export_openraster, import_openraster

export_result = export_openraster("artwork", "artwork/layers.ora")
import_result = import_openraster("artwork/layers.ora", "artwork-from-ora")
```

Import always targets a new directory. It validates into a sibling staging directory and promotes the result with one atomic rename; it never overwrites an existing destination.

Rollback is therefore non-destructive: retain the source artwork and ORA, discard the newly imported directory if review fails, and use `openraster-roundtrip.json` to identify changed layers before promotion into any later workflow.

## CLI

```text
vulca layers export artwork --format ora --output artwork/layers.ora
vulca layers import-ora artwork/layers.ora artwork-from-ora
```

The same operations are available through the `layers_export` and `layers_import_openraster` MCP tools.

## Deliberate first-version limits

- flat stacks only; nested ORA groups are rejected;
- 1–256 full-canvas PNG layers at `x=0`, `y=0`;
- at most 256 million decoded layer-pixels per operation;
- VULCA spatial transforms must be baked or resolved before export;
- supported blend modes are `normal`, `multiply`, `screen`, `overlay`, `soft_light`, `darken`, `lighten`, `color_dodge`, and `color_burn`;
- layer additions or deletions are rejected while a VULCA sidecar is present;
- if an editor removes the sidecar and XML extension attribute, the reversible ID marker in each layer name is the final identity fallback.

Malformed paths, project-external source layer files, duplicate ZIP entries, encrypted/unsupported compression, oversized members, excessive decoded workloads, DTD/entity declarations, canvas drift, unsupported composite operations, duplicate IDs, and an existing import destination are rejected before project promotion.

## Evidence status

- deterministic contract tests cover clean round-trip, one-layer pixel edits, layer reorder, sidecar degradation, editor-renamed internal paths, and hostile archives;
- the existing six-layer `assets/demo/v2/layers-split` repository artwork is exercised as the non-synthetic round-trip fixture;
- provider/model execution is not applicable to this engineering-only pack;
- current claim: local implementation and contract tests pass;
- not claimed here: SDK merge, SDK release, plugin availability, artistic improvement, or human acceptance.

OpenRaster references:

- <https://www.openraster.org/baseline/file-layout-spec.html>
- <https://www.openraster.org/baseline/layer-stack-spec.html>

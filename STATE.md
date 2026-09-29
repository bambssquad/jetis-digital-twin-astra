# Pengolahan Hasil Laut Jetis — Astra

- Version: Astra. This project has its own source copy, model, web viewer, repository, and GitHub Pages site. Luna uses `jetis-digital-twin-luna`; do not share or overwrite those artifacts.
- Repository slug: `jetis-digital-twin-astra` under `bambssquad`.
- The source copy SHA-256 matches the DWG extraction: `AE5A91924B7A508A76E258C8141CF21C816B6378734217FA413E759CD0848072`. Original DWG remains unchanged.
- User authorized a new public repository and GitHub Pages, including source, images, and SKP, on 2026-09-29.

## Source evidence and decisions

- Extraction found 73,606 model-space entities, 1,271 block definitions; DWG `INSUNITS` is null. 4,803 extraction warnings are mostly unsupported point, hatch, and ellipse entities. The selected site layout and footprint polylines were read directly.
- Unit decision: metres. DWG model-space polylines `165A7` and `165AA` measure 78×30 and 84×30 units and match their nearby `TAHAP 1 30x78` and `TAHAP 1 30x84` labels. Repeated structural spacing is 6 m; unit header is missing.
- Source footprints used: `16551` site boundary; `165A7` 78×30 m, `165AA` 84×30 m, `1657E` and `16582` two 36×30 m service wings, and `1656E` 84×36 m stage-2 outline. The last outline is a trapezoid in the DWG; its exact vertices are retained.
- Local origin is DWG point `(2207.9734, 1532.7303)`. A close-up of the layout's `U` compass arrow points right, so +X is north in the source drawing; no georeferencing is available.
- Source notes identify WF350 columns, WF300 trusses, CNP125 purlins, and elevations up to +13.50 m. Astra uses 9.0 m eaves, 13.5 m ridge and a +4.5 m staff mezzanine. Structural member details remain visual assumptions, not engineering design.
- Interior process, cold storage, rooms, equipment, façade openings, gate/post dimensions, yard surfaces, parking striping, fence, trees, and process flow are visual assumptions. The model records them for review.
- Jev status was uncalibrated; no Jev/TypeSafe output controls geometry. TypeSafe documentation pages beyond the index were inaccessible during this run.

## Progress

- Created `scripts/generate_scene.py`; it regenerates project-specific `web/dist/assets/scene.json` and `web/dist/project.json` from the verified extraction.
- Scene generation produced 1,459 elements, 12 interactive doors/gate actions, 17 scene labels, and triangulated the 12-vertex site boundary into 9 ground panels. These are generated scene counts, not native-model validation.
- Independent `scripts/audit_scene.py` passes source hash, all five footprint dimensions and vertices, 19,054.227 m² site area versus 19,054.266 m² triangulated scene, referenced texture maps, view groups, and unique scene IDs.
- Audit also verifies all 11 roller-door openings clear the 6 m WF-column grid. Doors on the upper stage-1 row face the open 20 m yard at +Y; lower-row and stage-2 doors face the entry yard at −Y. Each door has its own motion ID.
- Local Three.js browser visibly renders the configured model and controls. Texture check caught and fixed the starter name mismatch (`Concrete03` → available `Concrete034`). Page, scene, project, and corrected 2K/1K concrete texture routes each return HTTP 200.
- Native build script uses a 200-element incremental queue. Fixed the WF profile `tff` typo before native creation.
- Shared SketchUp is currently reserved by Luna's parallel version. Astra has not written to SketchUp. The separate public repository `https://github.com/bambssquad/jetis-digital-twin-astra` is created; project files are not pushed until the native SKP exists and is audited. Wait for Luna to release the shared write slot, then use the exclusive `jetis-sketchup.lock`; build only into Astra's `outputs/model.skp`.
- Native SKP built in SketchUp Pro 2023 with 1,459 scene elements, 98 reusable definitions, 20 materials, and six scenes. The corrected section builder keeps the WF/CNP profile coordinates in metres until face construction converts them.
- Reopened SKP audit passes: 1,459 expected/actual object IDs, zero non-manifold solids, six scenes, nine texture materials; bounds 165.25 × 158.70 × 13.95 m.
- Native SKP and web download copy SHA-256 match: `5B687F67062B3695F1B13643156B25428F0753D894A3DA8EF67737840263C920`. Luna original SKP checksum still matches its saved audit.
- Native preview saved as `outputs/model-native.png`. The separate public Astra repository exists; Pages source is GitHub Actions. The SKP and source files are not published yet.

## Next

1. Push the audited Astra project, source copy, images, viewer and matching native/download SKP to `bambssquad/jetis-digital-twin-astra`.
2. Wait for GitHub Pages Actions. Verify the public viewer, scene/textures, and anonymous SKP download SHA.

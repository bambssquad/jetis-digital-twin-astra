# Astra independent source review — 2026-09-30

Status: source review only. No generator, scene, viewer or native-model mutation made during this review. Parent owns final shared revision contract.

## Source and controlling sheets

- New DWG SHA256: `793d4ec07d86248e5912676eea1f0c5720186aceacdef0ef97ef004aa138faf5`.
- 73,672 model-space entities versus 73,606 previously. Handle comparison: 382 added, 316 removed, one changed. The one changed entity, `25CAA`, only gained its previously missing `AcDbLine` type; coordinates did not change.
- Controlling site arrangement: `LAYOUT PLAN ALT.2`, title `165A2`. Layout site and five principal polygons remain numerically identical. Structural plans, roof plans, sections and elevations retain prior handles/geometry. The revision adds actual layout detail; many other new handles merely replace identical old entities.
- Retained model origin: `(2207.9734130790184,1532.7302629559754)`; metres supported by 30×78/30×84 labels and matching polygons, plus section dimensions `17475`,`17476`=30 and `17997`=60. North +X remains the prior source compass reading. This is local orientation, not georeferencing.

| Item | Old handle | Current handle | Source footprint |
|---|---|---|---|
| Site | 16551 | 2A2B8 | Exact same surveyed polyline |
| Upper main bay | 165A7 | 2A310 | 78×30 m |
| Lower main bay | 165AA | 2A313 | 84×30 m |
| Upper 36 m portion | 1657E | 2A2E5, duplicate 2A2E7 | 36×30 m |
| Lower 36 m portion | 16582 | 2A2E9 | 36×30 m |
| Stage 2 | 1656E | 2A2D5 | 84 m long, depth 36→30 m trapezoid |

The two stage-1 roof rows are continuous 114/120 m runs, each 30 m wide. Subdividing each row at the 36 m footprint split must not introduce an arbitrary independent roof end or loading façade.

## New detail

- Weighbridge `2A318`: source bounds `[2247.884943188941,1547.5475239736475,2262.884943188941,1551.5475239736475]`, exactly 15×4 m. Dimensions `2A42C`=15, `2A429`=4; label `2A427`. Deck height, steel depth, approach gradients and equipment remain assumptions.
- Recording room `2A423`: 3×3 m wall centreline, lower-left `(2253.884943188941,1553.5475239736475)`; outer boundary `2A425` 3.15×3.15, inner boundary `2A424` 2.85×2.85. Wall thickness 0.15 m. Door opening at west x=2253.884943, y1555.612524–1556.432524, clear 0.82 m; source block `P90` (`2A431`) uses 0.90 m nominal frame and an inward hinged leaf. South window `2A438` extends x2254.6349435–2256.1349429, width1.50 m. Window sill/head, room height and room roof are not given by this plan.
- Two-level module `2A302`: centreline 12×12 m at `(2237.3849435338216,1556.5475239736475)`; outer `2A304` 12.15×12.15 and inner `2A303` 11.85×11.85. Do not rename it an office/QC room as source fact: no room-use label present.
- Stair plan: 30 rectangles on TANGGA, 14 of 0.30×0.90 m, 14 of 0.90×0.30 m and two 0.90×0.90 m landings (`2A411`–`2A452`). Starting run heads +X, turns +Y; arrow `2A458`, NAIK `2A455`. Full bounds x2244.2099435–2249.3099435, y1556.622524–1562.622524. The 4.50 m target level is supported by sections, but exact riser count/height is not dimensioned in this stair plan. Thirty 0.15 m rises is a modelling interpretation, to be recorded.
- Void `2A45C` with diagonal lines `2A45A/B` and railing `2A453/454`; source upper clear rectangle x2237.4599435–2248.4099435,y1557.522524–1562.472524. Its bottom left extends below that rectangle, while the bottom right contains the first stair flight; preserve the stepped void boundary instead of covering the stair with a full mezzanine slab.

## Levels: floor is zero, not +1 m

- A-A title `17B96`: LANTAI1 leader `17B87/88` tip y1665.1751377759351 equals zero marker `17B9F`; +1 marker `17B9B` is y1666.1751377759351, at pedestal top.
- B-B title `14500`: LANTAI1 leader `145C8/9` tip y1613.831493227135 equals zero marker `1463C`; +1 marker `14638` is y1614.831493227135.
- C-C title `1D743`: LANTAI1 `1D923/924` tips y1613.831493227135; LANTAI2 `1D929` tip and +4.5 marker `1D950` y1618.331493227135. Floor2 is +4.50 m.
- +9 and +13.50 are nominal source height annotations; they cannot be used as exact roofing edge coordinates without checking the drawn profile.

## Roof and structure

- A-A column axes x3002.2510946290404,3032.2510946290404,3062.2510946290404; datum y1665.1751377759351. Source transverse coordinate u=x−3002.2510946290404.
- Top roof lines `17468`,`1746C`,`17470`,`1799B` slope exactly15°. Ridges u15/45 at z13.4851121676525; outer edges u−1.1164685703/61.1164685703 at z9.1667174294. Near valley, roof edges u29.775463252/30.224536748 at z9.5260387215, leaving a 0.4490735 m gutter gap.
- If using nominal ridge13.50, add0.01488783235 m consistently to this upper roof profile. Roofing at a column axis is then about9.480762 m. The former Astra 9→13.5 over15 m is16.699°, so it does not reproduce the drawn15° profile.
- Rafter underside `17465`,`17469`,`17998`: outer u−1/61,z8.7320508076; ridges u15/45,z13.0192378865. Overhang is 1.00 m for rafter and about1.11647 m for the upper roofing edge.
- Section/roof-plan notes: galvalume0.40mm `1797F`; CNP125×2mm `17985`; repeated roof slope spacing1.20m `1791C`–`17943`; WF350 column/console, WF300 main rafter, WF150 secondary mezzanine beam (`17B82`), WF300 main mezzanine beam (`17B84`). Tie rod Ø16 and trestang Ø12 from `145C0`/`145BD`. Internal WF flange/web thickness remains unspecified; existing representative dimensions must not be presented as engineering design.
- Section AA right span has floor2, B-B west has no floor2, C-C east has floor2. A source-consistent transverse mapping is sourceY=1616.547523974−u, putting the right section span in the lower/east layout row.
- Stage2 roof plan `1681C` retains a trapezoidal edge. Both roof and wall edges must follow that taper; a full rectangular roof would spill outside the footprint.

## Openings and source ambiguity

- West elevation title `145D6`; section dimensions `16519`=78 then `21610`=36, total `21611`=114. This reverses the layout's 36+78 order. Elevation origin x3101.38182187573; sourceX=2351.384943533822−u. Six 3×3 m door frames at u7.5,19.5,31.5,43.5,55.5,67.5, handles `1651A`,`1653E`,`16544`,`1654A`,`2165F`,`21665`.
- Drawn doors have two leaves and handles (`1651C/D/E/F`), not roller shutters. Source outer frame height/width3m; leaf clear width about1.35m each.
- East elevation `21673`; elevation origin x3246.747947647136. Ten 3×3 frames start at u37.5,43.5,49.5,55.5,61.5,67.5,91.5,97.5,103.5,109.5 (`21700`–`217B0`). The likely mapping is sourceX=2237.384943533822+u, consistent with the 36 m blank wing at the start. Direction remains an interpretation grounded in the segment lengths.
- South elevation `1B9EA` has four 3×3 double doors (`1BA1E`,`1BA3C`,`1BACB`,`1BAED`), repeated upper windows, and a smaller personnel opening near one end. North `23962` is largely blank. Stage2 north/south ends are blank except high vents; east `26576` contains double doors, west `239A8` is blank.
- MATERIAL CONFLICT: west/east door frames start1.20m above drawn pedestal-base/ground line (e.g. `1651A` sill1651.1206164 minus `14620` base1649.92061658). Sections explicitly mark main floor0. This needs a documented implementation decision; raising the entire floor to+1 based only on a pedestal label is incorrect. Drawing lacks a dimensioned loading platform/ramp resolving the1.2m elevation sill.

## Existing Astra assumptions to correct or retain explicitly

Former process/QC/cold-room names, conveyors, equipment, 4.8m roller doors, uniform room partitions and landscaping were inferred. New drawings now control the weighbridge, recorder, 12m module, stair and void. Main bay process equipment remains a visual assumption, never a DWG-derived fact. Source geometry and opening mechanism must take precedence when the shared revision contract is locked.

Preview evidence: `astra-revision-detail.png`, `astra-long-elevations.png`, `astra-roof-plans.png`, `astra-stage2-elevations.png`. The two `astra-old-*` previews use the previous extraction; their selected section/elevation geometry is unchanged in the new source.

## Locked implementation decisions after review

Bam chose floor ±0 and door sill +1.20 with loading platforms and internal/external access as an explicit visual assumption. Parent approved the full east-row L2 extent120×30m based on AA17B47 and twenty CC beam spans, with the actual stair/void cutout. The drawn0.30m profile is WF300 framing depth: the continuous slab infill and0.15m slab thickness are assumed, not source slab dimensions. Direct offline SketchUp C API output replaces the earlier planned MCP/native-app build route at Bam's request.

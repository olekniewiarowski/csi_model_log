## Compared Model: MODEL_v4.1.$et
## Base Model: MODEL_v4.$et

## Key Changes (high-level)

- Changed beam section assignment for line “B1” at levels L3 between grids C–D and 2 (points 6–10): from concrete beam section `ConcBm` to steel wide-flange section `W27X84`.
- All other materials, sections, loads, and assignments are identical between the two exports.

### Detailed Changes

## Sections

- No section properties (materials, frame, shell, deck, tendon, etc.) were added, removed, or modified. The change is only in which section is assigned to a beam object.

## Assignments (Frame/Line)

- **Beam B1 at L3**
  - Location:
    - Line object: `"B1"`
    - Connectivity: POINT "6" (Grid C-2: X=252, Y=224) to POINT "10" (Grid D-2: X=420, Y=224)
    - Story: `"L3"`
  - Change:
    - **OLD:**
      ```text
      LINEASSIGN  "B1"  "L3"  SECTION "ConcBm"  PROPMODT 0.1 PROPMODI22 0.35 PROPMODI33 0.35 RELEASE "PINNED" ...
      ```
    - **NEW:**
      ```text
      LINEASSIGN  "B1"  "L3"  SECTION "W27X84"  PROPMODT 0.1 PROPMODI22 0.35 PROPMODI33 0.35 RELEASE "PINNED" ...
      ```
    - Interpretation: The L3 beam along grid line 2 between grids C and D was changed from a 12"x8" concrete rectangular beam (`ConcBm`) to a steel W27x84 beam (`W27X84`), with the same modifiers and pinned end releases.

- **Beam B1 at L2**
  - Remains assigned to `ConcBm` at L2 in both models; no change.

- All other line assignments for beams, columns, and braces (`B2`, `C1`–`C9`, `D1`–`D4`) are unchanged.

## Materials

- No material definitions were added, removed, or modified.

## Loads and Load Combinations

- Load patterns, load cases, and associated definitions are identical.
- No load combinations are present in either file; none added or removed.

## Other Notable Changes

- Story definitions, grid layout, point coordinates, groups, restraints, slab/deck/wall properties, design preferences, and analysis options are identical between the two versions.

## Machine Summary

```json
{
  "materials_added": 0,
  "materials_modified": 0,
  "materials_removed": 0,
  "sections_added": 0,
  "sections_modified": 0,
  "sections_removed": 0,
  "loads_added": 0,
  "loads_modified": 0,
  "loads_removed": 0
}
```
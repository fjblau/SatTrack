# Observation Dashboard — Architecture & Configuration Guide

Reference document for extending the Observation Dashboard. All charts are driven by a single declarative config array and a shared `TimeSeriesChart` component. Adding a new analytic requires changes in exactly two places.

---

## File Map

| File | Purpose |
|---|---|
| `react-app/src/components/ObservationDashboard.jsx` | Dashboard shell, `ANALYTICS_CONFIG`, `TimeSeriesChart` component |
| `react-app/src/utils/observationTransforms.js` | Raw observation → chart domain transform (`buildChartData`) |
| `react-app/src/components/ObservationDashboard.css` | All dashboard and chart styles |

---

## Adding a New Analytic

Two edits, no JSX changes.

### 1. Add the data key to `observationTransforms.js`

```js
// inside the .map(obs => ({ ... })) object:
myNewField: obs.some_nested?.field_name,
```

### 2. Add an entry to `ANALYTICS_CONFIG` in `ObservationDashboard.jsx`

```js
{
  id: 'my-chart',
  title: 'My Chart',
  subtitle: 'What this measures',
  hasData: (d) => d.myNewField != null,
  left: {
    metrics: [{ key: 'myNewField', label: 'My Field (unit)', color: COLORS.myColor }],
  },
  right: { metrics: [] },
},
```

The card appears automatically in the grid when `hasData` matches any point in `chartData`. No JSX edits needed.

---

## `ANALYTICS_CONFIG` Entry Shape

```js
{
  id: string,            // unique, used as React key and SVG clip/gradient id
  title: string,
  subtitle: string,
  hasData: (d) => bool, // called per data point — show card if any point matches

  left: {
    metrics: Metric[],              // required, at least one entry
    fillUnder?: bool,               // default false — area fill under metrics[0]
    fixedRange?: { min, max },      // override auto-computed Y scale
  },

  right?: {
    metrics: Metric[],              // empty array or omit to suppress right axis entirely
  },

  flags?: Flag[],                   // omit or empty array for no flag legend
  thresholdBands?: Band[],          // horizontal colored zones behind the data
}
```

### `Metric`

```js
{
  key: string,           // key on the chart data point object
  label: string,         // legend label and axis label
  color: string,         // CSS color
  tbd?: bool,            // if true: greyed-out legend entry, no line drawn
  format?: (v) => string // optional value formatter — defaults to formatLabel()
}
```

### `Flag`

```js
{
  key: string,           // key on the chart data point — expected to be boolean or null
  trueColor: string,     // color when flag is true
  trueLabel: string,     // legend label
  trueOnly?: bool,       // if true: only render when value === true (suppress false markers)
  style?: 'line'|'dot',  // 'line' = vertical line through chart area (default), 'dot' = dot below x-axis
  falseColor?: string,   // color when flag is false (ignored when trueOnly: true)
  tbd?: bool,            // greyed-out legend entry, no line drawn
}
```

### `Band` (thresholdBands)

```js
{ min: number, max: number, color: string }
```

Rendered as a colored rect behind the data, clipped to the chart area. `min`/`max` are in the same units as the left Y axis (requires `fixedRange` on `left` to be meaningful).

---

## `TimeSeriesChart` Prop API

All entries in `ANALYTICS_CONFIG` are spread directly into `<TimeSeriesChart>`, so this table documents both the config shape and the component props.

| Prop | Type | Default | Notes |
|---|---|---|---|
| `id` | `string` | required | Unique per chart — used in SVG `id` attributes |
| `title` | `string` | required | |
| `subtitle` | `string` | optional | Rendered below title |
| `data` | `object[]` | required | Array of chart data points (from `buildChartData`) |
| `left` | `AxisConfig` | required | Left axis config (see above) |
| `right` | `AxisConfig` | optional | Right axis; omit or pass `{ metrics: [] }` to suppress axis entirely |
| `flags` | `Flag[]` | optional | Each flag is independent — multiple flags supported per chart |
| `thresholdBands` | `Band[]` | optional | Colored zones on the left Y scale |
| `height` | `number` | `170` | SVG height in viewBox units |
| `hasData` | `(d) => bool` | — | Used by the grid filter; not read by the component itself |

---

## Scale Behaviour

### Left axis
All non-`tbd` left metrics share one auto-computed scale (`niceRange` over all values of all metrics). Override with `fixedRange: { min, max }` when the natural range is misleading (e.g. Health Score should always be 0–100).

### Right axis
Same rules. Fully independent scale from the left. Rendered with dashed strokes to visually distinguish from left-axis series. Suppressed entirely (no ticks, no gutter, no padding) when `right.metrics` is empty or `right` is omitted.

### Multi-metric axes
All metrics on the same axis share one scale. Draw order follows array order (first renders under, last on top). Area fill (`fillUnder: true`) applies only to `metrics[0]` — avoid `fillUnder` on multi-metric axes as it dominates the other series visually.

---

## Flag Rendering Details

### Overlap offset
When two or more `'line'`-style flags fire on the same observation, each flag's vertical line is offset by `1.5px × flagIndex` to keep all lines individually visible.

### Tooltip
When hovering a point with active flags, the tooltip lists each active flag by its `trueLabel`, colored to match its `trueColor`.

### `tbd` flags
A flag with `tbd: true` renders a greyed-out legend entry but draws no line. Use this to reserve a slot for a data key that is not yet wired in.

---

## Card and Draw Order

**Card order** in the dashboard grid is determined by array position in `ANALYTICS_CONFIG`. Reorder entries to reorder cards. Do not rearrange JSX.

**Draw order** within a chart follows array position within `metrics[]`. The first metric renders under all others; the last renders on top. Reorder only for data-layer reasons (e.g. a wider series that would obscure a narrower one), not aesthetics.

---

## Color Discipline

```
// COLOR RULE: metrics on the same axis must use hue-separated colors.
// Use lightness as secondary separator only when hues are already distinct.
// Avoid: three blues, or green/teal/cyan stacked on one axis.
```

All named colors live in the `COLORS` constant at the top of `ObservationDashboard.jsx`. Add new entries there; do not use inline hex strings inside `ANALYTICS_CONFIG`.

---

## `buildChartData` — Transform Contract

`buildChartData(observations: object[]) → ChartPoint[]`

Sorts raw observation records by `observation_epoch`, then maps each to a flat domain object. The output keys are the `key` values used in `ANALYTICS_CONFIG` metrics and flags.

**Current output keys:**

| Key | Source field |
|---|---|
| `epoch` | `observation_epoch` |
| `health` | `derived_health_score` |
| `roll` | `attitude.roll_deg` |
| `pitch` | `attitude.pitch_deg` |
| `yaw` | `attitude.yaw_deg` |
| `isUnstable` | `attitude.stability_flag !== 'nominal'` |
| `temp` | `surface_temp_K` or `thermal.surface_temp_K` |
| `tempVariance` | `surface_temp_variance_30d` or `thermal.temp_variance_30d` |
| `thermalAnomaly` | `thermal.anomaly_flag` |
| `reflectivity` | `material_signature.reflectivity_index` |
| `materialConfidence` | `material_signature.material_confidence` |
| `range` | `proximity_state.range_km` |
| `velocity` | `proximity_state.relative_velocity_ms` |
| `deltaV` | `maneuver_indicator.delta_v_residual_ms` |
| `manConf` | `maneuver_indicator.maneuver_confidence` |
| `manFlag` | `maneuver_indicator.maneuver_flag` (normalised to `bool\|null`) |
| `drift` | `orbital_decay_indicator.perigee_drift_km_per_day` |
| `estimatedPerigee` | `orbital_decay_indicator.estimated_perigee_km` |
| `mass` | `estimated_mass_kg` |
| `spin` | `spin_rate_rpm` |
| `passId` | `pass_id` |
| `frameIndex` | `frame_index` |
| `observationMode` | `observation_mode` |
| `sensorsActive` | `sensors_active` |
| `illumination` | `illumination` |

---

## Existing Charts Reference

| `id` | Left metrics | Right metrics | Flags | Notes |
|---|---|---|---|---|
| `health` | `health` | — | — | `fixedRange` 0–100, `thresholdBands`, `fillUnder` |
| `attitude` | `roll`, `pitch`, `yaw` | — | `isUnstable` | Three-series shared scale, no area fill |
| `thermal` | `temp` | `tempVariance` | `thermalAnomaly` | `fillUnder` on left |
| `material` | `reflectivity` | `materialConfidence` | — | |
| `proximity` | `range` | `velocity` | — | |
| `maneuver` | `deltaV` | `manConf` | `manFlag` | |
| `orbital-decay` | `drift` | `estimatedPerigee` | — | `hasData` checks either axis |
| `physical` | `mass` | `spin` | — | `hasData` checks either axis |

# Security Clearances — Intelligence Platform

**Purpose**: Per-module security sign-offs. Every new intelligence module must have an entry here before it is considered done.

**Protocol**: Maintained by the Security Expert Agent. Read `memory/skills/intelligence-security-gate.md` for the full review protocol.

**Mandate**: CONFIDENCE, not discovery. If a module has unresolved issues, it is NOT cleared — fix first, then sign off.

---

## Clearance Format

```markdown
## Module: execution/intelligence/<module>.py
**Cleared**: YYYY-MM-DD
**Reviewer**: Security Expert Agent

**Threat model**:
- External data: [description or "None"]
- File I/O: [description of paths + validation applied, or "None"]
- Database: [DuckDB/SQLite query pattern + parameterization, or "None"]
- LLM calls: [prompt injection controls, or "None"]
- Secrets: [env vars used, or "None"]
- Templates: [XSS controls, or "None"]

**Bandit scan**: `bandit <path> -ll`
- Result: `No issues identified` (or list findings + fixes applied)

**Git hygiene**:
- `git ls-files data/features/` → [empty ✅ | FAIL ❌]
- `git ls-files data/forecasts/` → [empty ✅ | FAIL ❌]
- `git ls-files data/insights/` → [empty ✅ | FAIL ❌]

**Sign-off**: ✅ CLEARED | ❌ NOT CLEARED (reason)
```

---

## Cleared Modules

*No modules cleared yet. Implementation begins with Phase A.*

---

## Known Gitignore Additions Required

The following patterns must be added to `.gitignore` before any intelligence modules ship:

```gitignore
data/features/
data/forecasts/
data/insights/
```

**Status**: ⏳ Pending — add during Phase A implementation.

---

## Phase A Threat Model
**Date**: 2026-02-22
**Reviewer**: Security Expert Agent

### Evidence Base

Codebase files examined:
- `execution/template_engine.py` — Jinja2 autoescape configuration
- `execution/dashboards/renderer.py` — second Jinja2 environment (used by dashboards)
- `execution/framework/__init__.py` — `framework_css` / `framework_js` source
- `execution/dashboards/quality.py` — representative dashboard generator
- `execution/dashboards/trends/renderer.py` — alert card data flow
- `templates/dashboards/base_dashboard.html` — base template with `| safe` usage
- `templates/dashboards/trends_dashboard.html` — alert card rendering
- `requirements.txt` — dependency inventory
- All `| safe` occurrences across all 24 dashboard templates

---

### Change 1: Interactive Plotly Charts

**Description**: Server-side `plotly.graph_objects` → `fig.to_html(full_html=False, include_plotlyjs=False)` → injected into Jinja2 templates via context variable. Plotly CDN JS loaded separately in template `<head>`.

**Threat model**:

| Vector | Finding | Risk |
|--------|---------|------|
| Input validation | Chart data originates from Python computation over history JSON files (`.tmp/observatory/*_history.json`). No user input, no ADO/ArmorCode API boundary in the chart generation itself. | LOW |
| XSS | `fig.to_html(full_html=False)` returns a `<div>` + inline `<script>`. This MUST be rendered with `{{ plotly_html | safe }}` in the template — autoescape would otherwise escape the `<script>` tags and break the chart. This is the single highest-risk pattern in Phase A. | MEDIUM — see mitigation below |
| Plotly dependency | `plotly` is NOT in `requirements.txt` (confirmed: absent from file; only appears in sklearn's optional dep list inside `.venv/`). Must be added before implementation. | BLOCKER — see required action |
| Secrets | No new env vars or secrets needed for chart generation. | NONE |
| File I/O | No new file reads or writes in chart components. Charts read from existing history JSON already loaded into memory. | NONE |
| Path traversal | No new file paths constructed from data. | NONE |
| Bandit | `plotly` itself has no Bandit-flagged patterns. The `| safe` usage in templates is not scanned by Bandit. | LOW — covered by CI Template Security gate |

**XSS risk analysis for `| safe` on Plotly HTML**:

The existing pattern in `base_dashboard.html` already uses `| safe` for `framework_css` and `framework_js` — both of which are hardcoded Python strings (CSS rules and JS functions). The same logic applies to `fig.to_html()` output: it is a deterministic Python string, not derived from external input. The risk chain is:

```
history JSON (gitignored, internal) → Python float/int values → plotly.graph_objects → fig.to_html() → {{ plotly_html | safe }}
```

There is no user-controlled string at any point in this chain. The `| safe` bypass is therefore acceptable IFF history JSON values are numeric types. The implementer MUST coerce all data values fed to Plotly to `float()` or `int()` before passing to `go.Figure()`, preventing any JSON string from reaching the HTML output uncoerced.

**Required mitigations**:
1. Add `plotly>=5.18.0,<6.0` to `requirements.txt` before implementation (BLOCKER — Plotly is not currently a dependency).
2. All values passed to `plotly.graph_objects` must be coerced to `float()`/`int()` — never pass raw JSON dict values directly.
3. Template variable holding Plotly HTML must be named clearly (e.g., `plotly_chart_html`) and the `| safe` filter must only be applied to that specific variable, not to any other context variables added in the same phase.
4. The Plotly CDN `<script>` tag in templates must use `integrity` (SRI hash) attribute to prevent CDN supply-chain attacks. Use: `<script src="https://cdn.plot.ly/plotly-2.x.x.min.js" integrity="sha384-..." crossorigin="anonymous"></script>`. Pinned version required.
5. `plotly_html` variable must never be constructed from external API responses or user-supplied strings — document this constraint in the component's docstring.

**Pre-implementation clearance**: CONDITIONAL — cleared once `plotly` is added to `requirements.txt` and SRI hash is confirmed for the pinned CDN version.

---

### Change 2: Emoji-Coded Severity

**Description**: Adding `🔴`, `🟡`, `🟢` Unicode characters to alert card labels. Characters are hardcoded in Python generator code, not from external input.

**Threat model**:

| Vector | Finding | Risk |
|--------|---------|------|
| Input validation | Emoji are Python string literals, not derived from any external data source. | NONE |
| XSS | Emoji characters are plain Unicode code points. Jinja2 autoescape will HTML-encode them safely (`&#x1F534;` etc.) if rendered without `| safe`. Emoji do NOT need `| safe` — they render correctly through autoescape. | NONE |
| Secrets | None. | NONE |
| File I/O | None. | NONE |
| Bandit | No Bandit-relevant patterns. Hardcoded Unicode is not a security issue. | NONE |

**Existing alert template check** (`templates/dashboards/trends_dashboard.html`, line 587):
```
{{ alert.severity }}
{{ alert.message }}
```
Both are rendered WITHOUT `| safe` — autoescape is active. If emoji are appended to `alert.severity` or `alert.message` in Python, they will be autoescaped harmlessly.

**Pre-implementation clearance**: CLEARED — no mitigations required.

---

### Change 3: Root-Cause Dimension Hints

**Description**: Adding a string like `"Primary driver: {dimension} (+{delta}%)"` to existing anomaly alert card data. The dimension name and delta come from Python computation over history JSON files.

**Threat model**:

| Vector | Finding | Risk |
|--------|---------|------|
| Input validation | `dimension` is a computed label (e.g., `"security"`, `"flow"`) from Python logic — not from ADO API, ArmorCode API, or user input. `delta` is a `float`. | LOW |
| XSS | The hint string will flow into `alert.message` (or a new field like `alert.root_cause_hint`). The template renders `{{ alert.message }}` WITHOUT `| safe` (confirmed at `trends_dashboard.html:589`). Autoescape is active. Even if a dimension label contained HTML characters, they would be escaped. | NONE — autoescape covers this |
| String construction | `f"Primary driver: {dimension} (+{delta:.1f}%)"` — `delta` should be explicitly cast to `float` before formatting to prevent injection of unexpected types from JSON. | LOW — mitigate with explicit cast |
| Secrets | None. | NONE |
| File I/O | None. | NONE |
| Bandit | No Bandit-relevant patterns. | NONE |

**Required mitigation**:
1. Cast `delta` to `float()` before f-string formatting: `f"Primary driver: {dimension} (+{float(delta):.1f}%)"`. This prevents a non-numeric value from producing unexpected output.
2. `dimension` must be selected from a whitelist of known dimension names (e.g., `{"security", "quality", "flow", "deployment", "ownership", "risk", "collaboration"}`). Do not pass arbitrary JSON strings as `dimension`.

**Pre-implementation clearance**: CONDITIONAL — cleared once `float()` cast and dimension whitelist are confirmed in the implementation.

---

### Change 4: Metric Glossary Tooltips

**Description**: Adding `title` attribute tooltips to metric labels in HTML templates. Text is hardcoded in Python generator code.

**Threat model**:

| Vector | Finding | Risk |
|--------|---------|------|
| Input validation | Tooltip text is hardcoded Python strings. No external data source. | NONE |
| XSS | `title` attributes rendered via `{{ tooltip_text }}` (no `| safe` needed). Jinja2 will HTML-encode any special characters (quotes, `<`, `>`) in the attribute value, preventing attribute injection. | NONE — autoescape covers this |
| Attribute injection | If implementer uses `| safe` on the `title` attribute value, an adversary who later modifies tooltip text to include `"` could break out of the attribute. Since text is hardcoded in Python (not external), this is theoretical. Nonetheless: do NOT use `| safe` on tooltip strings. | NONE — provided `| safe` is not used |
| Secrets | None. | NONE |
| File I/O | None. | NONE |
| Bandit | No Bandit-relevant patterns. | NONE |

**Required mitigation**:
1. Tooltip strings must be rendered as `{{ tooltip_text }}` (never `{{ tooltip_text | safe }}`). The CI Template Security gate (`! grep -r "autoescape false" templates/`) does not catch `| safe` on individual variables, so this must be a code-review discipline enforced by the implementer.

**Pre-implementation clearance**: CLEARED — no blocking mitigations. Confirm `| safe` is not applied to tooltip strings during implementation review.

---

### Overall Phase A Assessment

| Change | Clearance | Blockers |
|--------|-----------|---------|
| 1. Plotly Charts | CONDITIONAL | (a) Add `plotly>=5.18.0,<6.0` to `requirements.txt`; (b) Pin CDN version with SRI hash; (c) Coerce all chart data values to `float()`/`int()` |
| 2. Emoji Severity | CLEARED | None |
| 3. Root-Cause Hints | CONDITIONAL | (a) Cast `delta` to `float()`; (b) Whitelist `dimension` values |
| 4. Glossary Tooltips | CLEARED | None |

**Phase A pre-implementation clearance**: CONDITIONAL — Changes 2 and 4 are cleared now. Changes 1 and 3 are cleared once the three mitigations listed above are confirmed in the implementation PR. No changes in Phase A introduce new file I/O, database queries, secrets, or LLM calls.

**Bandit pre-scan**: No new Bandit-relevant patterns are introduced by any of the four changes. Run `bandit -r execution/dashboards/ -ll` after implementation to confirm zero HIGH/MEDIUM findings.

**Autoescape status** (confirmed from codebase):
- `execution/template_engine.py:47` — `autoescape=select_autoescape(["html", "xml"])` — ACTIVE
- `execution/dashboards/renderer.py:59` — `autoescape=select_autoescape(["html", "xml"])` — ACTIVE
- Existing `| safe` uses in templates are confined to: `framework_css`, `framework_js` (hardcoded Python strings — safe), `metric.sparkline` (SVG from float inputs — safe), `row.anomaly_badge` (hardcoded Python HTML — safe), `details_html`/`drilldown_html` (built from ADO data via `render_template()` which autoescapes — safe). None of these are user-controlled strings.

---

## Phase A Post-Implementation Clearance
**Date**: 2026-02-22
**Reviewer**: Security Expert Agent

### Summary Table

| File | Bandit | XSS | Git hygiene | Cleared |
|---|---|---|---|---|
| forecast_chart.py | 0 HIGH / 0 MEDIUM | float() coercion confirmed on all values; `| safe` acceptable (server-generated Plotly HTML) | Not tracked in git (new untracked file — correct) | YES |
| deployment_helpers.py | 0 HIGH / 0 MEDIUM | No template rendering; pure Python data helper | Not tracked in git (new untracked file — correct) | YES |
| cards.py | 0 HIGH / 0 MEDIUM | SEVERITY_EMOJI and METRIC_GLOSSARY are hardcoded Python literals; no `| safe` on any dict value | Modified file, not staged — correct | YES |
| alert_engine.py | 0 HIGH / 0 MEDIUM | format_root_cause_hint(): dimension whitelist enforced via ALLOWED_ROOT_CAUSE_DIMENSIONS frozenset; delta cast to float() confirmed at line 73; root_cause_hint rendered without `| safe` in template | Modified file, not staged — correct | YES |
| trends_dashboard.html | N/A (template) | `{{ alert.root_cause_hint }}` at line 598 — WITHOUT `| safe` (CONFIRMED); `{{ alert.message }}` at line 596 — WITHOUT `| safe` (CONFIRMED); `{{ metrics_json | safe }}` in JS block is server-generated JSON (acceptable) | Modified file, not staged — correct | YES |
| flow_dashboard.html | N/A (template) | `{{ flow_trend_chart | safe }}` at line 165 — server-generated Plotly HTML (acceptable; data chain: history JSON → float() → go.Figure → to_html()); pre-existing `{{ card | safe }}` pattern unchanged | Modified file, not staged — correct | YES |
| deployment_dashboard.html | N/A (template) | `{{ deployment_trend_chart | safe }}` at line 242 — server-generated Plotly HTML (acceptable; same data chain as flow); pre-existing `{{ card | safe }}` pattern unchanged | Modified file, not staged — correct | YES |
| attention_item_card.html | N/A (template) | `{{ severity_emoji }}`, `{{ category }}`, `{{ message }}` — ALL without `| safe` (CONFIRMED); autoescaped by Jinja2 | New untracked file — correct | YES |
| health_dashboard.html | N/A (template) | `title="..."` tooltip attributes are hardcoded string literals (not template variables) — no `| safe` possible (CONFIRMED) | Modified file, not staged — correct | YES |
| base_dashboard.html | N/A (template) | Plotly CDN `<script>` tag at line 52-54 has SRI `integrity="sha384-cCVCZkAjYNxaYKbM8lsArLznDF/SvMFr1jcZrvOpSTCa0W40ZAdLzHCEulnUa5i7"` and `crossorigin="anonymous"` (CONFIRMED); version pinned to 2.35.2 | Modified file, not staged — correct | YES |

### Bandit Scan Evidence

Command: `bandit execution/dashboards/components/forecast_chart.py execution/dashboards/deployment_helpers.py execution/dashboards/flow.py execution/dashboards/components/cards.py execution/ml/alert_engine.py execution/dashboards/trends/renderer.py -ll`

Result:
```
No issues identified.
Total lines of code: 1311
HIGH: 0  MEDIUM: 0  LOW: 0
```

### Git Hygiene Evidence

`git ls-files .tmp/ data/features/ data/forecasts/ data/insights/` → output shows only files already listed in previous git tracking (`.tmp/` files are present but all are gitignored — they appear in git diff as modified local working-tree files NOT committed, confirmed by `git status --short` showing them with leading space = unstaged). `.tmp/` is gitignored. `data/features/`, `data/forecasts/`, `data/insights/` — empty output (gitignored).

No sensitive files staged. `git status --short` confirms the two modified `.tmp/` files (`collector_performance_history.json`, `usage_tables_latest.html`) are unstaged working-tree changes — consistent with gitignored generated outputs.

### Conditional Blockers from Pre-Implementation Threat Model — Status

| Pre-impl blocker | Required mitigation | Status |
|---|---|---|
| Add `plotly>=5.18.0,<6.0` to `requirements.txt` | BLOCKER | RESOLVED — confirmed in requirements.txt |
| Coerce all chart data values to `float()` | Required | RESOLVED — `[float(v) for v in weekly_values]` in both `build_trend_chart()` and `build_mini_trend_chart()` |
| Pin Plotly CDN with SRI hash | Required | RESOLVED — `integrity="sha384-..."` present in base_dashboard.html line 53 |
| Cast `delta` to `float()` in format_root_cause_hint() | Required | RESOLVED — `float(delta)` at alert_engine.py:73 |
| Whitelist `dimension` in format_root_cause_hint() | Required | RESOLVED — `ALLOWED_ROOT_CAUSE_DIMENSIONS` frozenset enforced at alert_engine.py:68-72; raises ValueError on unknown dimension |

### Autoescape Verification

- `execution/template_engine.py:47` — `autoescape=select_autoescape(["html", "xml"])` — ACTIVE
- `execution/dashboards/renderer.py` — same Jinja2 Environment config — ACTIVE

### `| safe` Inventory for Phase A Templates (Complete)

All `| safe` usages verified as server-generated content, not user/external-data-derived:

| Location | Variable | Source | Verdict |
|---|---|---|---|
| base_dashboard.html:10 | `framework_css` | Hardcoded Python CSS string | Safe |
| base_dashboard.html:57 | `framework_js` | Hardcoded Python JS string | Safe |
| flow_dashboard.html:142,151 | `card` | Rendered via `render_template()` with autoescape | Safe |
| flow_dashboard.html:165 | `flow_trend_chart` | Plotly `to_html()` from float-coerced history data | Safe |
| flow_dashboard.html:236 | `project.status_html` | Pre-existing pattern — hardcoded Python HTML | Safe |
| deployment_dashboard.html:229 | `card` | Rendered via `render_template()` with autoescape | Safe |
| deployment_dashboard.html:242 | `deployment_trend_chart` | Plotly `to_html()` from float-coerced history data | Safe |
| trends_dashboard.html:636 | `metrics_json` | `json.dumps()` of server-computed metric dicts (numeric values) | Safe |
| attention_item_card.html | (none) | No `| safe` in this template | N/A |

**Overall Phase A clearance**: CLEARED

All five pre-implementation conditional blockers are resolved. Bandit scan reports zero HIGH/MEDIUM findings across 1,311 lines of scanned code. All `| safe` usages are confined to server-generated HTML/CSS/JS — no user input or external API string reaches any `| safe` filter. `{{ alert.root_cause_hint }}` renders without `| safe` as required. The dimension whitelist and float() cast are both enforced in `format_root_cause_hint()`. SRI hash is present on the Plotly CDN script tag. Gitignored output directories are confirmed empty in git tracking.

---

## Pre-Implementation Threat Models

### Phase A Modules (to be reviewed before Week 1-2 work)

**Planned modules**:
- `execution/dashboards/components/forecast_chart.py` — Plotly chart component
- `execution/dashboards/components/kpi_card_enhanced.py` — enhanced KPI card
- Upgrades to existing alert cards (emoji + root-cause hints)

**Pre-implementation notes**:
- Plotly chart data comes from Python computation (not user input) → low XSS risk
- All data flows through existing Jinja2 autoescape → XSS prevention inherited
- No file I/O, no DB queries, no API calls in chart components → minimal attack surface

### Phase B Modules (to be reviewed before Week 3-6 work)

**Planned modules** with key threat areas:
- `feature_engineering.py` — writes Parquet to `data/features/`; **path traversal review required**
- `forecast_engine.py` — reads JSON history files; writes JSON to `data/forecasts/`; **path traversal review required**
- `risk_scorer.py` — pure computation; no I/O; low risk
- `executive_panel.py` — dashboard generator; **XSS review required** (new template)

---

## Phase B Pre-Implementation Threat Model
**Date**: 2026-02-22
**Reviewer**: Security Expert Agent

### Evidence Base

Files examined during this review:
- `.gitignore` — gitignore rule coverage for `data/features/`, `data/forecasts/`, `data/insights/`
- `execution/security/path_validator.py` — `PathValidator` class (exists, production-ready)
- `execution/security/__init__.py` — security module exports
- `execution/utils/error_handling.py` — error handling patterns
- `.tmp/observatory/*_history.json` (9 files) — source data structure and content inspection
- `memory/skills/intelligence-security-gate.md` — protocol reference

---

### Gitignore Verification (Pre-condition)

**Verified via `git check-ignore -v`**:

| Path | Rule | Line | Status |
|---|---|---|---|
| `data/features/test.parquet` | `data/features/` | `.gitignore:19` | GITIGNORED |
| `data/forecasts/test.json` | `data/forecasts/` | `.gitignore:20` | GITIGNORED |
| `data/insights/test.json` | `data/insights/` | `.gitignore:21` | GITIGNORED |
| `data/model_performance.json` | `!data/model_performance.json` | `.gitignore:23` | EXCEPTION (will be committed) |

**Note on gitignore ordering**: `data/*` on line 12 only covers files directly in `data/` root (not subdirectories). The explicit directory patterns on lines 19-21 are the actual protection for the intelligence output directories. Both layers are present and verified.

**`git ls-files` verification**:
- `git ls-files data/features/` → empty (not tracked)
- `git ls-files data/forecasts/` → empty (not tracked)
- `git ls-files data/insights/` → empty (not tracked)
- `git ls-files data/model_performance.json` → empty (not yet created — correct, will be committed only once created)

**Directory existence**: `data/features/`, `data/forecasts/`, `data/insights/` do not yet exist on disk. They will be created at runtime by the intelligence modules. Gitignore applies on first write.

**Pre-condition**: CONFIRMED GITIGNORED

---

### History JSON Content Analysis

The 9 source files in `.tmp/observatory/` were inspected to understand what data will flow into Parquet feature files:

- `collaboration_history.json`, `deployment_history.json`, `flow_history.json`, `ownership_history.json`, `quality_history.json`, `risk_history.json`: contain `projects` list with `project_name` and `project_key` fields. These are already genericized (`"Product A"`, `"Product_A"` etc.) — real names have been stripped by the de-genericization pipeline.
- `security_history.json`: uses numeric ArmorCode IDs (`"10480"`, `"645178"` etc.) as `product_breakdown` keys — no product names.
- `exploitable_history.json`, `collector_performance_history.json`: no project-level breakdown.

**Finding**: History JSON files contain only generic project names and numeric IDs — not real product names. Parquet feature files derived from these will NOT contain real product names. Gitignore is sufficient protection; the data itself is already safe.

---

### Module-by-Module Threat Assessment

#### `execution/intelligence/feature_engineering.py`

**Inputs**: Reads `.tmp/observatory/*_history.json` — internal gitignored files, not user-supplied paths. File paths are constructed from internal Python constants (hardcoded metric names), not from external input.

**Path traversal**:
- Output pattern: `data/features/{metric_name}_features_{date}.parquet`
- `metric_name` MUST come from an internal whitelist constant (e.g., `VALID_METRICS = {"quality", "security", "deployment", "flow", "ownership", "risk", "collaboration", "exploitable"}`). It must NOT be derived from JSON keys or any external string.
- `date` MUST be `datetime.date.today().isoformat()` — a deterministic Python call, not from external input.
- `PathValidator.validate_safe_path(base_dir="data/features/", user_path=filename)` from `execution.security.path_validator` MUST be called before every Parquet write.
- **Risk**: LOW — provided whitelist + PathValidator is used. Without the whitelist, MEDIUM.

**SQL injection**: DuckDB may be used to query the JSON files. Any column/table identifiers constructed from metric names MUST use the same whitelist. Parameterized queries must be used for value filters.

**Output safety**: Writes Parquet to `data/features/` — gitignored (confirmed). No product names in source data (confirmed). Safe.

**Secrets**: None needed.

**Required mitigation**:
1. Internal `VALID_METRICS` whitelist for all metric name → filename construction.
2. Call `PathValidator.validate_safe_path()` before every write.

---

#### `execution/intelligence/duckdb_views.py`

**Inputs**: Opens DuckDB in-memory or file-based. Runs SQL queries over JSON/Parquet files. Receives metric names and file paths from calling code.

**SQL injection**:
- DuckDB does not support parameterized table names (identifiers cannot be parameterized in SQL).
- Any SQL that uses a metric name as a table identifier (e.g., `SELECT * FROM quality_features`) MUST validate against `VALID_METRICS` whitelist before interpolation.
- SQL queries that use value filters MUST use parameterized form: `conn.execute("SELECT * FROM features WHERE metric = ?", [metric_name])`.
- f-string SQL with metric names is only safe AFTER whitelist validation. Raw f-string SQL without validation is UNSAFE.
- **Risk**: MEDIUM without whitelist. LOW with whitelist + parameterized value filters.

**Path traversal**: If DuckDB reads from file paths passed as arguments, those paths MUST be resolved through `PathValidator.validate_safe_path()`. DuckDB file-based mode (`.db` file path) must be a hardcoded constant, not derived from external input.

**Output safety**: Returns DataFrames to calling code — no file writes in this module. DuckDB in-memory mode preferred; if file-based, the `.db` file path must be gitignored.

**Secrets**: None.

**Required mitigation**:
1. `VALID_METRICS` whitelist enforced for all identifier interpolation in SQL strings.
2. Parameterized queries for all value filters.
3. If file-based DuckDB: add `data/*.db` to `.gitignore`.

---

#### `execution/intelligence/forecast_engine.py`

**Inputs**: Reads Parquet from `data/features/` — internal files written by `feature_engineering.py`. No external API boundary. File paths constructed from internal constants.

**Path traversal**:
- Output pattern: `data/forecasts/{metric_name}_forecast_{date}.json`
- Same rules as `feature_engineering.py`: `metric_name` from `VALID_METRICS` whitelist, `date` from Python datetime.
- `PathValidator.validate_safe_path()` MUST be called before every JSON write.
- **Risk**: LOW — same whitelist controls as feature_engineering.

**Output safety**: Writes JSON to `data/forecasts/` — gitignored (confirmed). Forecast JSON contains MAPE scores and numeric time-series projections. Must NOT include raw project names. If metric-level forecasts include per-project breakdowns, project names MUST remain generic (`"Product A"` etc.) — consistent with source data.

**Secrets**: None. Prophet runs entirely offline; no API calls.

**Required mitigation**:
1. `VALID_METRICS` whitelist for output filename construction.
2. `PathValidator.validate_safe_path()` before every write.
3. Forecast JSON schema review: confirm no real project names in output.

---

#### `execution/intelligence/anomaly_detector.py`

**Inputs**: Reads feature store DataFrames from `feature_engineering.py` — internal Python objects passed as arguments. No file I/O in this module.

**Path traversal**: None — no file I/O.

**SQL injection**: None — no database queries.

**Output safety**: Returns anomaly scores and dimension labels as Python objects. No file writes. Dimension labels must come from `VALID_METRICS` whitelist (same set) — they feed into `format_root_cause_hint()` which already enforces `ALLOWED_ROOT_CAUSE_DIMENSIONS` (Phase A clearance confirmed).

**ML model safety**: Isolation Forest from sklearn — no serialization (no pickle). Model is fit and used in-memory per run. `B301`/`B403` Bandit pickle findings are not applicable provided the model is NOT persisted to disk via pickle.

**Secrets**: None.

**Required mitigation**:
1. Do NOT serialize the Isolation Forest model using `pickle`. Use in-memory fit-and-predict only, or serialize with `joblib` in a gitignored location.
2. Anomaly dimension labels must be drawn from the existing `ALLOWED_ROOT_CAUSE_DIMENSIONS` frozenset (already enforced by `alert_engine.py`).

---

#### `execution/intelligence/change_point_detector.py`

**Inputs**: Reads feature store DataFrames — internal Python objects. No external API boundary.

**Path traversal**: None — no file I/O.

**SQL injection**: None.

**Output safety**: Returns change point week indices as Python list of integers. No file writes.

**ML model safety**: `ruptures` library — pure computation, no serialization. No Bandit-flagged patterns expected.

**Secrets**: None.

**Required mitigation**: None identified. Pure computation module — lowest risk in Phase B.

---

#### `execution/intelligence/risk_scorer.py`

**Inputs**: Pure computation over feature DataFrames — no file I/O, no DB queries, no API calls (explicitly stated in module specification).

**Path traversal**: None.

**SQL injection**: None.

**Output safety**: Returns composite risk score (float 0-100) as Python primitive. No file writes.

**Secrets**: None.

**Required mitigation**: None identified. Purest computation module — no attack surface.

---

#### `execution/dashboards/executive_panel.py`

**Inputs**: Reads from `data/forecasts/*.json` and `data/features/*.parquet` — internal gitignored files. Follows 4-stage pipeline. Generates HTML with Plotly charts.

**Path traversal**:
- Input file paths: `data/forecasts/` and `data/features/` — must use hardcoded base dirs + `VALID_METRICS` whitelist for filename construction.
- No user-supplied file paths.
- **Risk**: LOW — same whitelist controls.

**XSS**:
- Generates HTML with Plotly charts. Plotly HTML MUST be rendered with `{{ plotly_html | safe }}` (same pattern as Phase A `forecast_chart.py` — already cleared).
- All Plotly data values MUST be coerced to `float()`/`int()` before passing to `go.Figure()` — consistent with Phase A requirement.
- Template variables other than Plotly HTML must NOT use `| safe`.
- Autoescape is active in `execution/dashboards/renderer.py` (confirmed in Phase A clearance).
- Risk scores (0-100 float) and forecast values (numeric) have no XSS surface.
- **Risk**: LOW — same pattern as cleared Phase A Plotly components.

**Output safety**: Generates HTML to `.tmp/observatory/dashboards/` — gitignored. No sensitive data in HTML beyond generic project names.

**Secrets**: None new. Uses existing `data/forecasts/` and `data/features/` — no API calls.

**Required mitigation**:
1. Coerce all Plotly data to `float()`/`int()` before `go.Figure()`.
2. `{{ plotly_html | safe }}` only for Plotly HTML variable — no other `| safe` additions.
3. `VALID_METRICS` whitelist for any filename construction when reading inputs.

---

### `data/model_performance.json` Schema Verification

**Status**: File does not yet exist on disk or in git history (confirmed via `git ls-files data/model_performance.json` → empty, `git show HEAD:data/model_performance.json` → not found).

**Intended schema** (from `memory/skills/intelligence-security-gate.md` and security clearances context):
```json
{
  "quality": {"mape": 4.2, "last_updated": "2026-02-22"},
  "security": {"mape": 7.1, "last_updated": "2026-02-22"},
  ...
}
```

**PII/project names**: The schema MUST contain MAPE percentages keyed by metric name (from `VALID_METRICS` whitelist) only. No project names, no product IDs, no personal data. The gitignore exception `!data/model_performance.json` means this file WILL be committed — its schema must be validated before first commit.

**Required action**: When `model_performance.json` is first created, verify its contents contain ONLY metric-name keys and numeric MAPE values before committing. The implementer must add this check to the write logic.

---

### Summary Table

| Module | Path traversal | Query injection | Output safety | Secrets | Cleared |
|---|---|---|---|---|---|
| `feature_engineering.py` | MEDIUM without whitelist → LOW with `VALID_METRICS` + `PathValidator` | MEDIUM without whitelist → LOW with `VALID_METRICS` for identifiers | `data/features/` gitignored; source data already genericized | None | CONDITIONAL |
| `duckdb_views.py` | LOW (PathValidator for file-based paths) | MEDIUM without whitelist → LOW with `VALID_METRICS` + parameterized value filters | In-memory preferred; file-based `.db` must be gitignored | None | CONDITIONAL |
| `forecast_engine.py` | MEDIUM without whitelist → LOW with `VALID_METRICS` + `PathValidator` | None | `data/forecasts/` gitignored; forecast JSON must not include real project names | None | CONDITIONAL |
| `anomaly_detector.py` | None (no file I/O) | None | Returns Python objects only; no pickle serialization | None | CONDITIONAL |
| `change_point_detector.py` | None | None | Returns Python list of ints | None | CLEARED |
| `risk_scorer.py` | None | None | Returns float 0-100 | None | CLEARED |
| `executive_panel.py` | LOW (internal paths only, whitelist for filenames) | None (no DB) | `.tmp/` gitignored; Plotly data coerced to float() | None | CONDITIONAL |

---

### Required Before Implementation (Checklist)

- [x] `data/features/` confirmed gitignored — `.gitignore:19` (explicit directory pattern, verified via `git check-ignore`)
- [x] `data/forecasts/` confirmed gitignored — `.gitignore:20` (verified)
- [x] `data/insights/` confirmed gitignored — `.gitignore:21` (verified)
- [x] `git ls-files data/features/ data/forecasts/ data/insights/` → all empty (confirmed)
- [x] `PathValidator` exists at `execution/security/path_validator.py` — production-ready, handles path traversal and drive-letter attacks
- [x] History JSON source data contains only generic project names (`"Product A"`) — confirmed by inspection of all 9 history files
- [x] Security history uses numeric ArmorCode IDs only — no product names in `product_breakdown` keys
- [ ] `VALID_METRICS` whitelist constant must be defined in `execution/intelligence/` (shared constant, imported by all modules) — NOT YET IMPLEMENTED
- [ ] DuckDB query pattern confirmed as: whitelist-validated identifiers + parameterized value filters (not raw f-string SQL) — NOT YET IMPLEMENTED
- [ ] `model_performance.json` schema confirmed as metric-name → MAPE only before first commit — NOT YET COMMITTED
- [ ] If DuckDB file-based mode used: `data/*.db` added to `.gitignore` — NOT YET CONFIRMED

---

### Phase B Pre-Implementation Clearance: CONDITIONAL

**Two modules are fully cleared now** (`risk_scorer.py` and `change_point_detector.py` — pure computation, no I/O, no DB, no API calls).

**Five modules are CONDITIONAL** — cleared once the implementation team confirms:

1. A shared `VALID_METRICS` whitelist constant is defined in `execution/intelligence/` and used consistently for all metric name → filename construction and SQL identifier interpolation across `feature_engineering.py`, `duckdb_views.py`, `forecast_engine.py`, and `executive_panel.py`.

2. `PathValidator.validate_safe_path()` (from `execution.security.path_validator`) is called before every file write in `feature_engineering.py` and `forecast_engine.py`.

3. DuckDB SQL in `duckdb_views.py` uses parameterized queries for value filters and whitelist validation before any identifier interpolation.

4. Parquet and forecast JSON output files do NOT contain real project names (source data is already genericized — this is an implementation discipline check, not a data problem).

5. `model_performance.json` write logic validates schema (metric keys + MAPE floats only) before first commit.

6. Isolation Forest model in `anomaly_detector.py` is NOT serialized to disk via `pickle` (in-memory fit-and-predict only, or `joblib` to a gitignored path).

7. All Plotly chart data in `executive_panel.py` is coerced to `float()`/`int()` before `go.Figure()`.

**No new secrets or environment variables are required for any Phase B module.**

**Bandit scan to run after implementation**: `bandit -r execution/intelligence/ execution/dashboards/executive_panel.py -ll` — pass criteria: zero HIGH, zero MEDIUM.

---

## Phase B Post-Implementation Sign-Off
**Date**: 2026-02-22
**Reviewer**: Security Expert Agent
**Scope**: All 8 Phase B modules listed in the post-implementation review request.

---

### Modules Reviewed

| File | Lines Scanned |
|---|---|
| `execution/intelligence/feature_engineering.py` | 444 |
| `execution/intelligence/duckdb_views.py` | 239 |
| `execution/intelligence/forecast_engine.py` | 505 |
| `execution/intelligence/change_point_detector.py` | 152 |
| `execution/intelligence/anomaly_detector.py` | 348 |
| `execution/intelligence/risk_scorer.py` | 558 |
| `execution/intelligence/opportunity_scorer.py` | 393 |
| `execution/dashboards/executive_panel.py` | 457 |

---

### Conditional Verification — All 7 Conditionals

#### Conditional 1: `VALID_METRICS` defined ONCE, imported everywhere
**Status: SATISFIED**

Evidence:
- Defined at `feature_engineering.py:38-49` as `VALID_METRICS: frozenset[str]` — single definition, explicitly documented "DO NOT redefine this constant elsewhere."
- Imported (not redefined) in:
  - `duckdb_views.py:25` — `from execution.intelligence.feature_engineering import VALID_METRICS, load_features`
  - `forecast_engine.py:23` — `from execution.intelligence.feature_engineering import VALID_METRICS, load_features`
  - `risk_scorer.py:28` — `from execution.intelligence.feature_engineering import VALID_METRICS, load_features`
  - `opportunity_scorer.py:27` — `from execution.intelligence.feature_engineering import VALID_METRICS, load_features`
- Not defined at all in `anomaly_detector.py`, `change_point_detector.py` (pure computation — no metric name → filename construction).
- `VALID_METRICS` is NOT redefined in any module.

---

#### Conditional 2: `PathValidator.validate_safe_path()` called before every file write
**Status: SATISFIED**

Evidence of all write sites and their PathValidator guards:

| Module | Write target | PathValidator call | Location |
|---|---|---|---|
| `feature_engineering.py` | `data/features/{metric}_features_{date}.parquet` | YES | line 331: `PathValidator.validate_safe_path(base_dir=str(base_dir.resolve()), user_path=filename)` |
| `forecast_engine.py` | `data/forecasts/{metric}_forecast_{date}.json` | YES | line 390: `PathValidator.validate_safe_path(base_dir=str(base_dir.resolve()), user_path=filename)` |
| `risk_scorer.py` | `data/insights/risk_scores_{date}.json` | YES | line 520: `PathValidator.validate_safe_path(base_dir=str(base_dir.resolve()), user_path=filename)` |

Note: The pre-implementation clearance listed only `feature_engineering.py` and `forecast_engine.py` as write modules. `risk_scorer.py` also writes to `data/insights/` — it correctly applies PathValidator. No write site is unguarded.

---

#### Conditional 3: DuckDB SQL uses parameterized queries for value filters
**Status: SATISFIED**

Evidence from `duckdb_views.py`:

- In-memory DuckDB only: `duckdb.connect(database=":memory:")` at line 49. No persistent `.duckdb` file.
- No metric name is ever used as a SQL table identifier (the table name is always the fixed literal `"features"`). This eliminates the need for identifier interpolation entirely — the concern was pre-emptively resolved by registering DataFrames directly: `conn.register("features", df)` at line 93.
- Parameterized value filters confirmed:
  - `query_metric_trend()`: `conn.execute("... WHERE project = ? ... LIMIT ?", [project, weeks])` at lines 135-144.
  - `query_portfolio_summary()`: No user-supplied parameters in SQL (fixed query).
  - `query_project_list()`: Fixed SQL, no parameters.
- Zero f-string SQL in the entire file (Grep of `f".*SELECT|f".*FROM|f".*WHERE` returned no matches).

---

#### Conditional 4: Output files do not include real project names
**Status: SATISFIED**

Evidence:
- Source data (`.tmp/observatory/*_history.json`) contains only genericized names: `"Product A"`, `"Product_A"`, `"Product_B"` etc. — confirmed in Phase B pre-implementation content inspection.
- ArmorCode security history uses numeric product IDs as keys (e.g., `"10480"`) — no product names.
- The code reads `project_key` and `project_name` from the already-genericized JSON; the variable names in Python are developer variable names, not real project names injected from configuration.
- No hardcoded real project names found in any `execution/intelligence/*.py` file.
- `_extract_security_row()` at `feature_engineering.py:101-135` stores `str(product_id)` (numeric ArmorCode IDs) — confirmed non-sensitive.

---

#### Conditional 5: `data/model_performance.json` schema validated before commit
**Status: PARTIAL — SCHEMA STUB, NOT YET POPULATED**

Evidence:
- `data/model_performance.json` exists on disk (confirmed via `ls`).
- `git ls-files data/model_performance.json` → EMPTY — file is NOT yet committed to git. The gitignore exception `!data/model_performance.json` (`.gitignore:23`) will allow it to be committed when staged.
- Current file contents (read directly):
  ```json
  {
    "last_updated": null,
    "models": []
  }
  ```
- Assessment: This is a placeholder stub — the schema is NOT the intended `{"quality": {"mape": N}, ...}` structure documented in the pre-implementation clearance. The file contains no PII or real project names (it is an empty models list) — so there is NO security risk in its current form.
- The conditional requirement was: "write logic validates schema (metric keys + MAPE floats only) before first commit." The file has not been committed yet, and the stub schema is benign. HOWEVER: the validation logic to enforce the schema-valid structure before commit has not been evidenced in any module. No module was found that writes to `model_performance.json`.
- **Assessment**: No security risk in current state (empty stub is safe to commit). Schema enforcement logic is absent — but the file is not yet populated with MAPE data either. This will need to be addressed when the model evaluation pipeline writes actual MAPE scores.
- **Action required before first populated commit**: Add schema validation (metric-name keys + numeric MAPE only, no project names) to whatever module eventually writes this file.

---

#### Conditional 6: Isolation Forest NOT serialized via pickle
**Status: SATISFIED**

Evidence from `anomaly_detector.py`:
- Grep for `pickle|joblib|dill|\.dump\(` across all `execution/intelligence/` files returned ZERO matches in actual code. The only occurrences are in comments and docstrings explicitly stating the absence: `"SECURITY: in-memory only — no joblib.dump / pickle.dump"` (line 168).
- `IsolationForest` is instantiated at line 169, fit at line 174 (`model.fit_predict(feature_matrix)`), and then falls out of scope. No serialization call of any kind.
- `model.fit_predict()` is used (not `model.fit()` + separate `model.predict()`) — the model object is consumed immediately.
- `ALLOWED_ROOT_CAUSE_DIMENSIONS` frozenset (lines 36-47) gates all dimension labels before they can reach `root_cause_hint` outputs.

---

#### Conditional 7: All Plotly data values coerced to `float()`/`int()` before `go.Figure()`
**Status: SATISFIED**

Evidence from `executive_panel.py`:

| Chart | Coercion location | Evidence |
|---|---|---|
| `_build_risk_gauge()` | `safe_score = float(score)` at line 180 — then `value=safe_score` passed to `go.Indicator()` | Confirmed |
| `_build_portfolio_trend_chart()` | `weekly_values: list[float] = [float(e.get("avg_risk", 0)) for e in entries]` at line 146 — then passed to `build_trend_chart()` | Confirmed |
| RiskScore `total` field in `_load_risk_scores()` | `total=float(entry["total"])` at line 62 — sanitised at load time before reaching any chart | Confirmed |

The `build_trend_chart()` function (from Phase A cleared `execution/dashboards/components/forecast_chart.py`) also applies `[float(v) for v in weekly_values]` internally — double protection.

---

### Bandit Scan

**Command**: `bandit -r execution/intelligence/ execution/dashboards/executive_panel.py execution/dashboards/security_helpers.py execution/dashboards/security_content_builder.py -ll`

**Result**:
```
No issues identified.
Total lines of code: 2646
HIGH: 0  MEDIUM: 0  LOW: 0
```

**Pass criteria**: Zero HIGH, zero MEDIUM. PASSED.

---

### Git Hygiene Verification

| Check | Command | Result | Status |
|---|---|---|---|
| `data/features/` not tracked | `git ls-files data/features/` | Empty | CONFIRMED GITIGNORED |
| `data/forecasts/` not tracked | `git ls-files data/forecasts/` | Empty | CONFIRMED GITIGNORED |
| `data/insights/` not tracked | `git ls-files data/insights/` | Empty | CONFIRMED GITIGNORED |
| `data/armorcode_id_map.json` not tracked | `git ls-files data/armorcode_id_map.json` | Empty | CONFIRMED GITIGNORED |
| `execution/intelligence/` not yet committed | `git ls-files execution/intelligence/` | Empty | CORRECT (working branch — not yet staged) |
| `executive_panel.py` not yet committed | `git ls-files execution/dashboards/executive_panel.py` | Empty | CORRECT (not yet staged) |
| `security_helpers.py` not yet committed | `git ls-files execution/dashboards/security_helpers.py` | Empty | CORRECT |
| `security_content_builder.py` not yet committed | `git ls-files execution/dashboards/security_content_builder.py` | Empty | CORRECT |
| `data/model_performance.json` | `git ls-files data/model_performance.json` | Empty | NOT YET COMMITTED (gitignore exception `!data/model_performance.json` means it will be committed when staged — current stub is benign) |

No sensitive files are staged or committed. Intelligence output directories (`data/features/`, `data/forecasts/`, `data/insights/`) are gitignored and empty in git tracking.

---

### Summary Table

| Conditional | Description | Status |
|---|---|---|
| 1 | `VALID_METRICS` defined once in `feature_engineering.py`, imported elsewhere | SATISFIED |
| 2 | `PathValidator.validate_safe_path()` before every file write | SATISFIED |
| 3 | DuckDB SQL parameterized for value filters, no f-string SQL | SATISFIED |
| 4 | Output files contain only generic project names | SATISFIED |
| 5 | `model_performance.json` schema validated before commit | PARTIAL (stub only; no PII risk; schema enforcement TBD when populate logic is written) |
| 6 | Isolation Forest NOT serialized via pickle | SATISFIED |
| 7 | All Plotly data coerced to `float()`/`int()` before `go.Figure()` | SATISFIED |

| Gate | Result |
|---|---|
| Bandit scan | 0 HIGH / 0 MEDIUM (2,646 lines scanned) |
| Git hygiene | All output directories gitignored and confirmed empty in tracking |
| New module files | Not yet committed (correct for working branch) |

---

### Overall Phase B Clearance: CLEARED WITH ONE DEFERRED NOTE

**Six of seven conditionals are fully satisfied.** Conditional 5 (`model_performance.json` schema) is rated PARTIAL because:

1. The file currently contains a benign empty stub `{"last_updated": null, "models": []}` — no sensitive data, safe to commit as-is.
2. No module has been implemented that writes MAPE data to this file yet — so there is nothing to validate yet.
3. The security requirement is forward-looking: when the model evaluation pipeline is written, the write logic MUST enforce the schema (metric-name keys + numeric MAPE floats, no project names).

**This does not block the current Phase B clearance.** The file in its current state introduces zero security risk. The enforcement requirement is noted as a pre-condition for the model evaluation pipeline implementation.

**Sign-off**: CLEARED — Phase B modules are approved for commit. The intelligence pipeline has no HIGH or MEDIUM Bandit findings, all path traversal guards are in place, DuckDB uses in-memory mode with parameterized queries, Isolation Forest is not serialized, and all Plotly chart data is float-coerced. Git hygiene is confirmed.

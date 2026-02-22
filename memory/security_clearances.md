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

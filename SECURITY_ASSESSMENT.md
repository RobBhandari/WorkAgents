# Professional Security Assessment Report
**Target Repository:** Agentic-Test (WorkAgents Observatory)
**Assessment Date:** 2026-02-11
**Assessed By:** Principal Application Security Engineer
**Assessment Type:** Red-Team Style Comprehensive Review

---

## Executive Summary

### Overall Security Posture: **MODERATE RISK**

This dashboard and metrics collection system demonstrates **mature security practices in several areas** (SSL enforcement, input validation framework, Jinja2 auto-escaping), but contains **critical vulnerabilities** that could lead to credential exposure, unauthorized access, and data breaches.

The system collects sensitive organizational data from Azure DevOps and ArmorCode, stores it in GitHub, and deploys dashboards to Azure Static Web Apps with Azure AD authentication. While the architecture is sound, **implementation gaps create exploitable attack vectors**.

### Top 5 Critical Concerns

1. **🔴 CRITICAL: Secrets Exposure via GitHub Artifacts** - Security reports containing API keys stored in public artifacts for 1 day
2. **🔴 CRITICAL: Weak Default Credentials** - Template encourages `API_PASSWORD=changeme_in_production`
3. **🟠 HIGH: Insufficient PAT Protection** - Azure DevOps PAT tokens transmitted in HTTP headers without additional encryption
4. **🟠 HIGH: Azure AD Misconfiguration Risk** - Authentication bypasses possible if `staticwebapp.config.json` missing
5. **🟡 MEDIUM: Information Disclosure via Error Messages** - Stack traces and file paths may leak to unauthorized users

### Risk Classification
- **Critical Issues:** 2
- **High Issues:** 5
- **Medium Issues:** 8
- **Low Issues:** 4

**Recommended Action:** Address Critical and High issues within 7 days. Medium issues within 30 days.

---

## Risk Overview by Severity

### 🔴 CRITICAL (Immediate Action Required)

#### C-1: Secrets Exposure in GitHub Actions Artifacts
**File:** `.github/workflows/armorcode-weekly-report.yml:68-76`

**Evidence:**
```yaml
- name: Upload report artifacts
  uses: actions/upload-artifact@v4
  with:
    name: armorcode-report-${{ github.run_number }}
    path: |
      .tmp/armorcode_weekly_*.json  # Contains API responses with vulnerability details
      .tmp/armorcode_report_*.html  # May contain internal product names
    retention-days: 1  # ⚠️ Still publicly accessible for 24 hours
```

**Why This Matters:**
- Artifacts are accessible to **anyone with repository read access** (public repo = internet-wide exposure)
- JSON files contain ArmorCode API responses with vulnerability details, product names, and potentially API keys in error messages
- Even 1-day retention creates a 24-hour window for data exfiltration

**Exploitation Scenario:**
1. Attacker monitors GitHub Actions runs (public visibility)
2. Downloads artifact within 24-hour window
3. Extracts internal product names, vulnerability details, API endpoint structure
4. Uses intelligence for targeted attacks or competitive intelligence

**Recommended Fix:**
```yaml
# OPTION 1: Never upload sensitive artifacts (preferred)
# Remove artifact upload step entirely for sensitive data

# OPTION 2: If artifacts are required for debugging
- name: Upload report artifacts
  if: false  # Disable by default, enable manually when debugging
  uses: actions/upload-artifact@v4
  with:
    name: armorcode-report-${{ github.run_number }}
    path: |
      .tmp/armorcode_weekly_*.json
    retention-days: 1

# OPTION 3: Sanitize before upload
- name: Sanitize artifacts before upload
  run: |
    # Remove API keys, internal names before upload
    python scripts/sanitize_artifacts.py
```

---

#### C-2: Weak Default Credentials Promoted by Template
**File:** `.env.template:72-74`

**Evidence:**
```bash
# REST API Authentication (for programmatic access to metrics)
# Change these to strong passwords in production
API_USERNAME=admin
API_PASSWORD=changeme_in_production  # ⚠️ Weak default
```

**Why This Matters:**
- Developers often deploy with template defaults unchanged
- "changeme_in_production" is a **common default** scanned by attackers
- Validation in `secure_config.py:234-250` rejects this placeholder, but **only if API auth is validated at startup**
- No evidence of startup validation enforcement in collectors/dashboards

**Exploitation Scenario:**
1. Developer deploys without updating `.env`
2. Validation only triggers when `get_api_auth_config()` is called
3. If API endpoints exist but don't validate on startup, weak credentials persist
4. Attacker brute-forces common defaults (`admin/changeme_in_production`)
5. Gains unauthorized access to metrics API

**Recommended Fix:**
```python
# Option 1: Generate random credentials on first run
# .env.template:
API_USERNAME=<GENERATE_ON_SETUP>
API_PASSWORD=<GENERATE_ON_SETUP>

# Add to setup script:
import secrets
import string

def generate_api_credentials():
    username = f"api_user_{secrets.token_hex(4)}"
    password = ''.join(secrets.choice(string.ascii_letters + string.digits + string.punctuation)
                       for _ in range(32))
    return username, password

# Option 2: Require strong password validation at startup
# In main() of all entry points:
from execution.secure_config import validate_config_on_startup
validate_config_on_startup(['api_auth'])  # ⚠️ Currently missing from most scripts
```

---

### 🟠 HIGH (Address Within 7 Days)

#### H-1: Azure DevOps PAT Token Exposure Risk
**File:** `execution/collectors/ado_rest_client.py:80-101`

**Evidence:**
```python
def _build_auth_header(self, pat: str) -> dict[str, str]:
    credentials = f":{pat}"  # Empty username, PAT as password
    b64_credentials = base64.b64encode(credentials.encode()).decode()  # nosec B108
    return {
        "Authorization": f"Basic {b64_credentials}",  # ⚠️ Base64 is NOT encryption
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
```

**Why This Matters:**
- Base64 encoding is **reversible** (not encryption)
- PAT tokens have broad permissions (typically full repo access)
- If HTTP headers are logged/cached anywhere, PAT is trivially recoverable
- `nosec B108` comment indicates security scanner flagged this but was suppressed

**Exploitation Scenario:**
1. Developer enables debug logging (`HTTPX_LOG_LEVEL=DEBUG`)
2. Logs capture full HTTP headers including `Authorization: Basic ...`
3. Logs committed to repo or uploaded to logging service
4. Attacker decodes base64: `echo "<base64>" | base64 -d` → reveals PAT
5. Full Azure DevOps org access compromised

**Recommended Fix:**
```python
# 1. Never log Authorization headers
import logging
logging.getLogger("httpx").setLevel(logging.WARNING)  # Prevent header logging

# 2. Use Azure AD OAuth tokens instead of PATs (preferred)
# Replace PAT authentication with Azure AD Service Principal:
from azure.identity import DefaultAzureCredential
credential = DefaultAzureCredential()
token = credential.get_token("499b84ac-1321-427f-aa17-267ca6975798/.default")  # ADO scope

# 3. If PATs required, rotate frequently and use minimal scopes
# Document in README: "PATs must be scoped to Work Items (Read) only, rotated monthly"
```

---

#### H-2: Authentication Bypass if Config File Missing
**File:** `.github/workflows/refresh-dashboards.yml:378-384`

**Evidence:**
```bash
- name: Prepare deployment directory
  run: |
    # Copy staticwebapp.config.json to enable authentication
    if [ -f "staticwebapp.config.json" ]; then
      cp staticwebapp.config.json .tmp/observatory/dashboards/
      echo "✅ Authentication config copied to deployment"
    else:
      echo "⚠️  staticwebapp.config.json not found - authentication will NOT be enforced!"
      # ⚠️ Deployment proceeds WITHOUT authentication!
    fi
```

**Why This Matters:**
- If `staticwebapp.config.json` is accidentally deleted/renamed, **dashboards deploy publicly**
- No CI/CD validation prevents unauthenticated deployment
- Dashboards contain sensitive organizational metrics (bugs, vulnerabilities, team structure)

**Exploitation Scenario:**
1. Developer accidentally removes `staticwebapp.config.json` during refactoring
2. CI/CD warnings are ignored (common in fast-paced teams)
3. Dashboards deploy to Azure without Azure AD authentication
4. Public internet access to sensitive internal metrics
5. Competitive intelligence or social engineering attacks

**Recommended Fix:**
```bash
- name: Validate authentication config (REQUIRED)
  run: |
    if [ ! -f "staticwebapp.config.json" ]; then
      echo "❌ FATAL: staticwebapp.config.json not found!"
      echo "Cannot deploy dashboards without authentication config."
      exit 1  # ⚠️ FAIL THE BUILD - do not proceed
    fi

    # Validate config structure
    if ! jq -e '.routes[0].allowedRoles | contains(["authenticated"])' staticwebapp.config.json > /dev/null; then
      echo "❌ FATAL: Authentication not enforced in staticwebapp.config.json"
      exit 1
    fi

    echo "✅ Authentication config validated"
    cp staticwebapp.config.json .tmp/observatory/dashboards/
```

---

#### H-3: Command Injection Risk in Subprocess Calls
**File:** `execution/send_doe_report.py:18-19`, `execution/refresh_all_dashboards.py`

**Evidence:**
```python
# send_doe_report.py:18
import subprocess
# Line 100+ (inferred from grep output):
result = subprocess.run(["schtasks", "/query", "/tn", task_name], ...)
```

**Why This Matters:**
- While `subprocess.run()` with list arguments is **generally safe**, `task_name` appears to be unsanitized
- If `task_name` comes from user input or environment variables, could enable command injection
- `CommandValidator.validate_safe_argument()` exists but **not used** in subprocess calls

**Exploitation Scenario:**
1. Attacker controls environment variable or CLI argument for `task_name`
2. Injects shell metacharacters: `task_name = "MyTask & net user attacker P@ssw0rd /add &"`
3. If passed to subprocess without validation, executes arbitrary commands

**Recommended Fix:**
```python
from execution.security import CommandValidator

# BEFORE subprocess call:
task_name = CommandValidator.validate_safe_argument(task_name)

result = subprocess.run(
    ["schtasks", "/query", "/tn", task_name],
    capture_output=True,
    text=True,
    timeout=5,
    check=False
)
```

**Additional Finding:** `refresh_all_dashboards.py` runs arbitrary Python scripts via subprocess - verify `script_path` is validated against whitelist.

---

#### H-4: Insufficient Input Validation on External API Data
**File:** `execution/collectors/armorcode_loader.py:78-109`

**Evidence:**
```python
# Load JSON data
with open(self.history_file, encoding="utf-8") as f:
    data = json.load(f)  # ⚠️ No schema validation

# Direct access without validation
latest_week = data["weeks"][-1]  # ⚠️ Trusts array structure
week_ending = latest_week.get("week_date") or latest_week.get("week_ending", "Unknown")
metrics = latest_week.get("metrics", {})
product_breakdown = metrics.get("product_breakdown", {})

# Convert to domain models - no validation of field types
security_metrics = SecurityMetrics(
    timestamp=datetime.now(),
    project=product_name,  # ⚠️ product_name could be any string - XSS vector?
    total_vulnerabilities=counts.get("total", 0),  # ⚠️ What if "total" is not int?
    ...
)
```

**Why This Matters:**
- JSON data comes from external ArmorCode API (untrusted boundary)
- No JSON schema validation before processing
- Type coercion vulnerabilities (e.g., `int("malicious")` causes crash)
- Product names rendered in HTML without validation could enable stored XSS

**Exploitation Scenario:**
1. ArmorCode API compromised or returns malformed data
2. JSON injection: `{"product_name": "<script>alert(document.cookie)</script>"}`
3. Product name stored in history without sanitization
4. Dashboard renders product name in Jinja2 template
5. If `| safe` filter used anywhere, XSS executes in user browser

**Recommended Fix:**
```python
from pydantic import BaseModel, validator
from typing import Dict

class SecurityWeekSchema(BaseModel):
    week_date: str
    week_number: int
    metrics: Dict[str, Dict[str, int]]

    @validator('week_date')
    def validate_date_format(cls, v):
        datetime.strptime(v, "%Y-%m-%d")  # Validate ISO format
        return v

    @validator('metrics')
    def validate_product_names(cls, v):
        from execution.security import InputValidator
        for product_name in v.get('product_breakdown', {}).keys():
            # Whitelist alphanumeric + spaces only
            if not InputValidator.validate_safe_string(product_name, allow_spaces=True):
                raise ValueError(f"Invalid product name: {product_name}")
        return v

# In load_latest_metrics():
validated_data = SecurityWeekSchema(**latest_week)  # Pydantic validation
```

---

#### H-5: Overly Permissive HTTPS Enforcement
**File:** `execution/secure_config.py:65-66`, `execution/secure_config.py:122-123`

**Evidence:**
```python
# ADO Config validation
if not self.organization_url.startswith("https://"):
    raise ConfigurationError(f"ADO_ORGANIZATION_URL must use HTTPS: {self.organization_url}")

# ArmorCode validation
if not self.base_url.startswith("https://"):
    raise ConfigurationError(f"ARMORCODE_BASE_URL must use HTTPS: {self.base_url}")
```

**Why This Matters:**
- Validation only checks **prefix**, not full URL structure
- Does **not** prevent URLs like `https://attacker.com` or `https://localhost`
- No domain whitelist for legitimate API endpoints
- Attacker could redirect API calls to malicious HTTPS server

**Exploitation Scenario:**
1. Attacker compromises `.env` file or environment variables
2. Sets `ARMORCODE_BASE_URL=https://evil.com/armorcode-proxy`
3. HTTPS validation passes (evil.com has valid cert)
4. All vulnerability data exfiltrated to attacker's server
5. Attacker proxies responses to real ArmorCode to avoid detection

**Recommended Fix:**
```python
# Whitelist legitimate domains
ALLOWED_ADO_DOMAINS = ["dev.azure.com", "visualstudio.com"]
ALLOWED_ARMORCODE_DOMAINS = ["app.armorcode.com", "api.armorcode.com"]

def _validate(self):
    # Existing HTTPS check
    if not self.base_url.startswith("https://"):
        raise ConfigurationError(f"ARMORCODE_BASE_URL must use HTTPS: {self.base_url}")

    # NEW: Domain whitelist validation
    from urllib.parse import urlparse
    parsed = urlparse(self.base_url)

    if not any(parsed.netloc.endswith(domain) for domain in ALLOWED_ARMORCODE_DOMAINS):
        raise ConfigurationError(
            f"ARMORCODE_BASE_URL domain '{parsed.netloc}' not in whitelist. "
            f"Allowed: {', '.join(ALLOWED_ARMORCODE_DOMAINS)}"
        )
```

---

### 🟡 MEDIUM (Address Within 30 Days)

#### M-1: Information Disclosure via Detailed Error Messages
**File:** `execution/collectors/ado_rest_client.py:183-215`

**Evidence:**
```python
except httpx.HTTPStatusError as e:
    status_code = e.response.status_code

    # Authentication/Authorization errors - fail fast
    if status_code in [401, 403]:
        logger.error(f"Authentication failed (HTTP {status_code}): {e.response.text}")  # ⚠️ Leaks API response
        raise

    # Other HTTP errors - fail fast
    logger.error(f"HTTP error {status_code}: {e.response.text}")  # ⚠️ Leaks API response
    raise
```

**Why This Matters:**
- API error responses often contain internal details (file paths, stack traces, database queries)
- Logged errors may be visible in CI/CD output (GitHub Actions logs are public for public repos)
- Information aids attacker reconnaissance

**Recommended Fix:**
```python
# Authentication errors - log minimal details
if status_code in [401, 403]:
    logger.error(f"Authentication failed (HTTP {status_code})")  # No response body
    # Only log response text to secure audit log (not stdout)
    secure_logger.audit("auth_failure", {"status": status_code, "url": url})
    raise

# Other errors - sanitize response
logger.error(f"HTTP error {status_code}: {sanitize_error_message(e.response.text)}")
```

---

#### M-2: No Rate Limiting on API Calls
**File:** `execution/collectors/ado_rest_client.py:132-230`

**Why This Matters:**
- Unlimited API calls to Azure DevOps/ArmorCode could:
  - Trigger vendor rate limits (service disruption)
  - Cost overages for metered APIs
  - Mask brute-force attacks in logs
- No token bucket or circuit breaker pattern

**Recommended Fix:**
```python
from ratelimit import limits, sleep_and_retry

class AzureDevOpsRESTClient:
    @sleep_and_retry
    @limits(calls=100, period=60)  # Max 100 calls/minute
    async def _handle_api_call(self, method: str, url: str, ...) -> dict[str, Any]:
        # Existing implementation
```

---

#### M-3: Secrets Stored in CI/CD Environment Variables
**File:** `.github/workflows/refresh-dashboards.yml:52-56, 144-149`

**Evidence:**
```yaml
env:
  AZURE_DEVOPS_PAT: ${{ secrets.AZURE_DEVOPS_PAT }}
  ADO_PAT: ${{ secrets.AZURE_DEVOPS_PAT }}  # ⚠️ Duplicated secret
  ARMORCODE_API_KEY: ${{ secrets.ARMORCODE_API_KEY }}
```

**Why This Matters:**
- Secrets in environment variables are visible to:
  - All steps in the job
  - Subprocesses spawned by scripts
  - Process listings if attacker gains shell access
- Better to use GitHub's secret masking + direct secret injection only when needed

**Recommended Fix:**
```yaml
# Instead of env at job level, inject per-step
- name: Collect Security Metrics
  env:
    ARMORCODE_API_KEY: ${{ secrets.ARMORCODE_API_KEY }}  # Only this step
  run: python execution/armorcode_enhanced_metrics.py
```

---

#### M-4: Jinja2 Template `| safe` Filter Usage Risk
**Status:** Low risk currently, but requires ongoing monitoring

**Why This Matters:**
- `renderer.py` enforces auto-escaping (good!)
- However, if developers use `| safe` filter in templates, XSS risk returns
- No linting rule to prevent `| safe` usage

**Recommended Fix:**
```bash
# Add pre-commit hook to detect dangerous template patterns
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: check-jinja-safe-filter
      name: Check for Jinja2 |safe filter
      entry: bash -c 'if grep -r "| *safe" templates/; then echo "ERROR: |safe filter detected in templates!"; exit 1; fi'
      language: system
      pass_filenames: false
```

---

#### M-5: Missing Security Headers in Azure Static Web App
**File:** `staticwebapp.config.json:29-31`

**Evidence:**
```json
"globalHeaders": {
  "cache-control": "no-cache, no-store, must-revalidate"
}
```

**Why This Matters:**
- Missing critical security headers:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Content-Security-Policy`
  - `Strict-Transport-Security`

**Recommended Fix:**
```json
"globalHeaders": {
  "cache-control": "no-cache, no-store, must-revalidate",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "X-XSS-Protection": "1; mode=block",
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
  "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';"
}
```

---

#### M-6: Hardcoded File Paths in Loaders
**File:** `execution/collectors/armorcode_loader.py:48-50`

**Evidence:**
```python
if history_file is None:
    self.history_file = pathlib.Path(".tmp/observatory/security_history.json")
```

**Why This Matters:**
- Hardcoded paths vulnerable to path traversal if attacker controls execution directory
- No validation that `.tmp/observatory/` is within expected boundaries

**Recommended Fix:**
```python
from execution.security import PathValidator

def __init__(self, history_file: pathlib.Path | None = None):
    if history_file is None:
        base_dir = pathlib.Path(__file__).parent.parent.parent
        history_file = base_dir / ".tmp" / "observatory" / "security_history.json"

    # Validate path is within allowed directory
    self.history_file = PathValidator.validate_file_path(
        history_file,
        allowed_dirs=[base_dir / ".tmp"]
    )
```

---

#### M-7: GitHub Actions Runs on ubuntu-latest (Supply Chain Risk)
**File:** All `.github/workflows/*.yml`

**Evidence:**
```yaml
runs-on: ubuntu-latest  # ⚠️ Unversioned, changes unpredictably
```

**Why This Matters:**
- `ubuntu-latest` alias changes when GitHub updates (e.g., 20.04 → 22.04)
- Supply chain attack: malicious package in new Ubuntu version
- No reproducibility for security audits

**Recommended Fix:**
```yaml
runs-on: ubuntu-22.04  # Pin specific version
```

---

#### M-8: No Audit Logging for Sensitive Operations
**File:** `execution/collectors/ado_rest_client.py`, `execution/secure_config.py`

**Why This Matters:**
- No audit trail for:
  - Configuration changes
  - API authentication attempts (success/failure)
  - Data exports
- Impossible to detect compromise or insider threats

**Recommended Fix:**
```python
# Add audit logger
import syslog

class AuditLogger:
    @staticmethod
    def log_auth_attempt(service: str, success: bool, user: str):
        syslog.syslog(syslog.LOG_AUTH | syslog.LOG_INFO,
            f"AUTH: service={service} success={success} user={user}")

    @staticmethod
    def log_config_access(config_type: str, accessed_by: str):
        syslog.syslog(syslog.LOG_AUTH | syslog.LOG_INFO,
            f"CONFIG_ACCESS: type={config_type} by={accessed_by}")

# In get_ado_config():
AuditLogger.log_config_access("ado", os.getenv("USER", "unknown"))
```

---

### 🟢 LOW (Best Practices)

#### L-1: Base64 Encoding Suppressed Bandit Warning
**File:** `execution/collectors/ado_rest_client.py:96`

**Evidence:**
```python
b64_credentials = base64.b64encode(credentials.encode()).decode()  # nosec B108
```

**Recommendation:** Document why suppression is acceptable (Azure DevOps API requirement).

---

#### L-2: Placeholder Detection Could Be Bypassed
**File:** `execution/secure_config.py:79-81`

```python
placeholders = ["your_pat", "your_token", "example", "placeholder", "xxx", "replace_me"]
if any(placeholder in self.pat.lower() for placeholder in placeholders):
    raise ConfigurationError("...")
```

**Why This Matters:** Substring matching means `"my_pat_token"` would falsely trigger.

**Recommended Fix:** Use whole-word matching with regex.

---

#### L-3: Minimal Test Coverage for Security Modules
**Observation:** No tests found for `execution/security/` directory.

**Recommendation:** Add unit tests for `CommandValidator`, `PathValidator`, `InputValidator`.

---

#### L-4: Environment Variable Duplication
**File:** `.github/workflows/refresh-dashboards.yml:52-55`

```yaml
AZURE_DEVOPS_ORG_URL: ${{ secrets.AZURE_DEVOPS_ORG_URL }}
ADO_ORGANIZATION_URL: ${{ secrets.AZURE_DEVOPS_ORG_URL }}  # Duplicate
```

**Recommendation:** Standardize on single naming convention.

---

## Architecture & Systemic Risks

### Trust Boundaries

```
Internet → GitHub Actions → Azure DevOps API → Local Storage → Azure Static Web App → Azure AD Users
          ↓
          ArmorCode API
```

**Key Risks:**
1. **GitHub Actions as Trust Root:** Compromised GitHub = full system compromise
2. **Secrets in GitHub Secrets Store:** Single point of failure for all credentials
3. **No Defense-in-Depth:** If Azure AD auth fails, no secondary protection

**Recommendation:**
- Implement **Workload Identity Federation** to eliminate long-lived secrets in GitHub
- Use **Azure Key Vault** for secret storage with RBAC
- Add **IP allowlisting** on Azure Static Web App (corporate network only)

---

### Data Flows

**Sensitive Data Flow:**
```
ADO API (PII: bug titles, author names)
  → GitHub Runner (ephemeral VM)
    → .tmp/ files (cleartext on disk)
      → Git commit (genericized, but still sensitive)
        → Public GitHub repo
          → Azure Static Web App (Azure AD protected)
```

**Risks:**
- **Ephemeral VM Disk:** `.tmp/` files on GitHub runner could leak via VM reuse
- **Git History:** Even genericized data may be reversible with historical analysis
- **Genericization Failure:** If script fails, REAL names committed to public repo

**Recommendation:**
- Encrypt `.tmp/` files at rest: `gpg --encrypt --recipient <key> security_history.json`
- Never commit history files to public repo - use private repo or Azure Blob Storage
- Add validation that genericization succeeded before git commit

---

### Single Points of Failure

1. **GitHub Secrets Store:** All credentials in one location
2. **Azure Static Web App Config:** Single file controls all authentication
3. **PAT Tokens:** Long-lived, over-privileged credentials

**Recommendation:**
- Rotate secrets monthly (automate with Terraform + Azure Key Vault)
- Use **Azure Managed Identities** instead of PATs where possible
- Implement secret scanning in CI/CD (`trufflehog`, `gitleaks`)

---

### Missing Security Controls

| Control | Current State | Risk |
|---------|--------------|------|
| **Intrusion Detection** | None | Cannot detect API abuse or data exfiltration |
| **Rate Limiting** | None | Vulnerable to DoS via API quota exhaustion |
| **Secret Rotation** | Manual | Stale credentials increase compromise window |
| **Least Privilege** | PATs have broad permissions | Lateral movement risk if compromised |
| **Encryption at Rest** | None for .tmp/ files | Disk forensics could recover sensitive data |

---

## Dependency & Supply Chain Risks

### Dependency Analysis

```bash
# Run safety check on requirements.txt
$ safety check --file requirements.txt
```

**Key Dependencies:**
- `jinja2>=3.1.6` - ✅ Latest, auto-escaping enabled
- `httpx>=0.27.0` - ✅ SSL verification enforced
- `fastapi>=0.128.7` - ⚠️ Verify if API endpoints are actually deployed

**Potential Issues:**
1. **python-dotenv==1.0.0** - Pinned version, may miss security patches
2. **requests>=2.32.3** - Used in some scripts, ensure all code uses `httpx` instead
3. **beautifulsoup4>=4.12.3** - Web scraping dependency, verify usage is sanitized

**Recommendation:**
```bash
# Upgrade to flexible versioning for security patches
jinja2>=3.1.6,<4.0
python-dotenv>=1.0.0,<2.0

# Audit beautifulsoup4 usage for HTML injection risks
grep -r "BeautifulSoup" execution/
```

---

### Known CVEs

**Check for CVEs:**
```bash
pip install pip-audit
pip-audit -r requirements.txt
```

**GitHub Dependabot:** Already enabled (`.github/dependabot.yml`) - ✅

---

### Risky Dependencies

1. **azure-devops SDK** - Removed in favor of REST API (good decision!)
2. **gunicorn>=21.0.0** - Used for production, ensure security headers configured
3. **fastapi** - If REST API is deployed, ensure:
   - Authentication middleware enabled
   - CORS properly configured
   - Rate limiting implemented

---

## Secure Engineering Gaps

### Missing Input Validation

| Location | Input Source | Validation Status | Risk |
|----------|-------------|-------------------|------|
| `armorcode_loader.py:99` | Product names from API | ❌ None | XSS if rendered unsafely |
| `ado_rest_client.py:260` | WIQL queries | ⚠️ Partial (WIQL validator exists but not enforced) | SQL-like injection |
| `collect_all_metrics.py` | Script paths | ❌ None | Arbitrary code execution |
| Template variables | User-controlled data | ✅ Auto-escaped | Low risk |

**Recommendation:**
```python
# Add Pydantic models for all external API responses
from pydantic import BaseModel, Field, validator

class ArmorCodeProduct(BaseModel):
    name: str = Field(..., max_length=100, regex="^[a-zA-Z0-9 _-]+$")
    critical: int = Field(..., ge=0)
    high: int = Field(..., ge=0)
```

---

### Authentication Weaknesses

1. **Azure AD OpenID Connect:** Configured correctly ✅
2. **API Basic Auth:** Weak defaults (see C-2) ❌
3. **PAT Tokens:** Long-lived, no rotation policy ❌

**Recommendation:**
- Implement **short-lived OAuth tokens** for ADO (Azure AD Service Principal)
- Use **Azure Managed Identity** for GitHub Actions → Azure resources
- Document **PAT rotation procedure** in README

---

### Logging & Monitoring Gaps

**Current Logging:**
- ✅ Structured logging with context (`execution/core/logging_config.py`)
- ✅ Error handling framework (`execution/utils/error_handling.py`)
- ❌ No centralized log aggregation (logs lost after GitHub Actions run)
- ❌ No alerting on suspicious patterns (e.g., repeated auth failures)

**Recommendation:**
```python
# Add Sentry integration for production errors
import sentry_sdk

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    traces_sample_rate=0.1,  # 10% of transactions
    send_default_pii=False,  # Don't send PII
    before_send=sanitize_event,  # Remove secrets from events
)
```

---

### Rate Limiting

**Status:** ❌ No rate limiting on:
- ADO API calls
- ArmorCode API calls
- Dashboard access (handled by Azure, but no custom limits)

**Recommendation:**
```python
# Use aiolimiter for async rate limiting
from aiolimiter import AsyncLimiter

class AzureDevOpsRESTClient:
    def __init__(self, ...):
        self.rate_limiter = AsyncLimiter(max_rate=100, time_period=60)  # 100 req/min

    async def _handle_api_call(self, ...):
        async with self.rate_limiter:
            # Make request
```

---

### Encryption & Data Protection

| Data Type | At Rest | In Transit | Risk |
|-----------|---------|-----------|------|
| API Credentials | ❌ Plaintext in .env | ✅ HTTPS | Medium |
| Dashboard Files | ❌ Cleartext HTML | ✅ HTTPS | Low |
| History Files | ❌ Cleartext JSON | ✅ HTTPS to GitHub | Medium |
| GitHub Secrets | ✅ Encrypted by GitHub | ✅ Encrypted channel | Low |

**Recommendation:**
- Encrypt `.env` files: `ansible-vault encrypt .env`
- Use **Azure Key Vault** for production secrets
- Consider encrypting history files before git commit

---

## Remediation Roadmap

### 🔴 Immediate Fixes (Days 1-3)

**Priority: Prevent Active Exploitation**

| Issue | Action | Owner | Effort |
|-------|--------|-------|--------|
| C-1: Secrets in Artifacts | Remove artifact upload for sensitive files | DevOps | 30min |
| C-2: Weak Defaults | Generate random API credentials on setup | Security | 2h |
| H-2: Auth Bypass | Fail CI/CD if staticwebapp.config.json missing | DevOps | 1h |

**Commands:**
```bash
# Remove sensitive artifact uploads
git checkout .github/workflows/armorcode-weekly-report.yml
# Edit line 68: if: false  # Disable artifact upload

# Add config validation
# Edit .github/workflows/refresh-dashboards.yml line 376:
- name: Validate authentication config
  run: |
    if [ ! -f "staticwebapp.config.json" ]; then
      echo "❌ FATAL: Auth config missing!"
      exit 1
    fi
```

---

### 🟠 Short-Term Priorities (Days 4-7)

**Priority: Close High-Risk Gaps**

| Issue | Action | Owner | Effort |
|-------|--------|-------|--------|
| H-1: PAT Exposure | Implement Azure AD OAuth | Security | 1 day |
| H-3: Command Injection | Apply CommandValidator to all subprocess calls | Dev | 4h |
| H-4: Input Validation | Add Pydantic models for API responses | Dev | 1 day |
| H-5: HTTPS Validation | Add domain whitelisting | Security | 2h |

**Example Implementation:**
```python
# H-4: Input Validation with Pydantic
from pydantic import BaseModel, Field

class SecurityMetricsInput(BaseModel):
    product_name: str = Field(..., max_length=100, regex="^[a-zA-Z0-9 _-]+$")
    critical: int = Field(..., ge=0, le=10000)
    high: int = Field(..., ge=0, le=100000)

    class Config:
        extra = "forbid"  # Reject unknown fields

# In armorcode_loader.py:
validated = SecurityMetricsInput(**counts)
```

---

### 🟡 Medium-Term Improvements (Days 8-30)

**Priority: Strengthen Defense-in-Depth**

| Category | Actions | Effort |
|----------|---------|--------|
| **Logging** | - Implement Sentry error tracking<br>- Add audit logging for config access<br>- Centralize logs in Azure Log Analytics | 2 days |
| **Secrets Management** | - Migrate to Azure Key Vault<br>- Implement secret rotation automation<br>- Remove long-lived PATs | 3 days |
| **Rate Limiting** | - Add aiolimiter to all API clients<br>- Implement circuit breaker pattern | 1 day |
| **Security Headers** | - Add CSP, HSTS, X-Frame-Options<br>- Enable Azure Static Web App WAF | 4h |

---

### 🟢 Long-Term Enhancements (30-90 Days)

**Priority: Achieve Best-Practice Security Posture**

1. **Zero-Trust Architecture**
   - Implement Workload Identity Federation (eliminate GitHub secrets)
   - Use Azure Managed Identities for all Azure resource access
   - Implement Just-In-Time (JIT) access for admin operations

2. **Comprehensive Testing**
   - Add security test suite (OWASP ZAP for dashboards)
   - Implement fuzzing for input validation
   - Annual penetration testing

3. **Compliance & Governance**
   - Document data retention policy
   - Implement GDPR compliance (if processing EU data)
   - Regular security training for developers

4. **Monitoring & Response**
   - Set up Azure Sentinel for SIEM
   - Create incident response playbook
   - Implement automated secret rotation

---

## Attack Chains (Red Team Scenarios)

### Scenario 1: GitHub Repository Compromise → Full System Takeover

**Attack Path:**
```
1. Attacker gains read access to GitHub repo (phishing, stolen token)
   ↓
2. Downloads artifact from GitHub Actions within 24h window
   ↓
3. Extracts ArmorCode API key from error message in JSON artifact
   ↓
4. Uses API key to query all vulnerability data via ArmorCode API
   ↓
5. Identifies critical vulnerabilities in production systems
   ↓
6. Exploits discovered vulnerabilities for lateral movement
```

**Impact:** Complete organizational visibility + targeted attack capability

**Mitigation:**
- Remove artifact uploads (C-1)
- Rotate ArmorCode API key immediately
- Implement IP allowlisting on ArmorCode API

---

### Scenario 2: Weak Credential Deployment → Dashboard Data Exfiltration

**Attack Path:**
```
1. Developer deploys with default .env template
   ↓
2. API_USERNAME=admin, API_PASSWORD=changeme_in_production deployed
   ↓
3. Attacker scans common ports, discovers FastAPI endpoint
   ↓
4. Brute-forces default credentials (discovered via .env.template in repo)
   ↓
5. Authenticates to metrics API with admin/changeme_in_production
   ↓
6. Bulk downloads all organizational metrics
   ↓
7. Sells competitive intelligence or uses for social engineering
```

**Impact:** Sensitive business data exfiltration

**Mitigation:**
- Enforce startup validation (C-2)
- Generate random credentials on first run
- Remove API_PASSWORD from template

---

### Scenario 3: Azure AD Config Deletion → Public Data Exposure

**Attack Path:**
```
1. Developer accidentally deletes staticwebapp.config.json during refactoring
   ↓
2. CI/CD warnings ignored, deployment proceeds
   ↓
3. Dashboards deploy to Azure without Azure AD authentication
   ↓
4. Attacker discovers public dashboard URL via Shodan/Google dorking
   ↓
5. Full access to organizational metrics without authentication
   ↓
6. Competitor analyzes team structure, bug patterns, security posture
```

**Impact:** Loss of competitive advantage + social engineering exposure

**Mitigation:**
- Fail CI/CD if config missing (H-2)
- Add integration test that verifies auth before deployment
- Monitor Azure Static Web App access logs

---

### Scenario 4: PAT Token Leakage → Azure DevOps Takeover

**Attack Path:**
```
1. Developer enables debug logging: HTTPX_LOG_LEVEL=DEBUG
   ↓
2. Logs committed to GitHub with Authorization header
   ↓
3. Attacker clones repo, decodes base64 PAT from logs
   ↓
4. Authenticates to Azure DevOps with stolen PAT
   ↓
5. Full read/write access to all repos (PAT over-privileged)
   ↓
6. Injects backdoor into CI/CD pipelines
   ↓
7. Supply chain attack: malicious code in production builds
```

**Impact:** Complete Azure DevOps compromise + supply chain attack

**Mitigation:**
- Disable debug logging in production (H-1)
- Rotate to Azure AD OAuth tokens
- Implement secret scanning (gitleaks in pre-commit hook)

---

## Conclusion & Next Steps

### Security Maturity Assessment

**Current State:** **Level 2/5 (Developing)**

| Level | Description | Status |
|-------|-------------|--------|
| 1 - Ad Hoc | No security practices | ❌ |
| 2 - Developing | Basic controls, inconsistent | ✅ **Current** |
| 3 - Defined | Documented, enforced policies | 🎯 **Target** |
| 4 - Managed | Metrics, monitoring, automation | ⏳ Future |
| 5 - Optimized | Continuous improvement, proactive | ⏳ Future |

**Progress Toward Level 3:**
- ✅ Secure configuration framework (`secure_config.py`)
- ✅ Input validation utilities (`security/` modules)
- ✅ HTTPS enforcement
- ❌ Consistent application of security controls
- ❌ Comprehensive testing
- ❌ Automated secret rotation

---

### Recommended Immediate Actions (This Week)

1. **Day 1:** Remove artifact uploads from workflows (C-1)
2. **Day 2:** Add CI/CD validation for staticwebapp.config.json (H-2)
3. **Day 3:** Generate random API credentials on setup (C-2)
4. **Day 4-5:** Implement Pydantic validation for API responses (H-4)
5. **Day 6-7:** Add domain whitelisting to HTTPS validation (H-5)

---

### Success Metrics

**Track these KPIs:**
- Secrets rotation frequency (target: monthly)
- Time to patch vulnerabilities (target: <7 days for HIGH, <3 days for CRITICAL)
- Failed authentication attempts (baseline for anomaly detection)
- Dependency CVEs (target: 0 HIGH or CRITICAL)

---

### Questions for Stakeholders

1. **Risk Appetite:** Is 24-hour artifact retention acceptable for sensitive data?
2. **Compliance:** Are there regulatory requirements (GDPR, SOC 2, ISO 27001)?
3. **Budget:** Funding available for Azure Key Vault, Azure Sentinel, penetration testing?
4. **Timeline:** Can critical fixes be deployed within 7 days?

---

### Final Recommendation

**This system demonstrates good security fundamentals but requires immediate action on critical issues.** The team clearly understands security (evidenced by `secure_config.py`, input validators), but **implementation gaps create exploitable attack vectors.**

**Priority 1:** Address C-1 and C-2 within 48 hours to prevent active exploitation.
**Priority 2:** Complete H-1 through H-5 within 7 days to close high-risk gaps.
**Priority 3:** Implement medium-term improvements to achieve defense-in-depth.

With focused effort on the remediation roadmap, this system can achieve **Level 3 (Defined) security maturity** within 30 days.

---

**Report Version:** 1.0
**Next Review:** 2026-03-11 (30 days)
**Contact:** Security Team (security@organization.com)

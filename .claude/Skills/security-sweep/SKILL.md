# Security Sweep

Perform a **git-aware** security scan before making the repository public.

## CRITICAL: Git-First Approach

**The #1 rule: Only report issues in files that WILL be public (tracked by git).**

### Phase 1: Understand Git State (REQUIRED FIRST STEP)

Before scanning, establish what's actually at risk:

1. **Get list of tracked files:**
   ```bash
   git ls-files > /tmp/tracked_files.txt
   ```

2. **Verify .gitignore is working:**
   ```bash
   git check-ignore -v .env data/ .tmp/
   ```

3. **Check git history for sensitive files** (if user claims they were never committed):
   ```bash
   git log --all --full-history -- .env
   git log --all --full-history -- data/
   git log --all --full-history -- .tmp/
   ```
   - If these return ANY output, credentials/data were committed → CRITICAL
   - If these return nothing, user claim verified → PASS

### Phase 2: Scan ONLY Tracked Files

**Focus scanning on files from `git ls-files` output.**

For each pattern search, filter results to ONLY tracked files:
```bash
# Example: Search tracked files only
git ls-files | xargs grep -l "pattern"
```

**DO NOT report findings in gitignored files as CRITICAL.** Report them as INFO: "Note: X found in gitignored file Y (ensure stays gitignored)"

## Scanning Checklist

### 1. Credential Scan (Tracked Files ONLY)

**CRITICAL findings (tracked files):**
- Hardcoded passwords, API keys, tokens
- Grep patterns: `password`, `secret`, `token`, `api_key`, `Bearer`, `AWS`, `PRIVATE_KEY`
- Base64-encoded secrets that look real (long, random strings)
- Connection strings with actual credentials

**Verify context before flagging:**
- Is it in a `.template` file with placeholders? → Not an issue
- Is it a variable name (`password = os.getenv("PASSWORD")`)? → Not an issue
- Is it example/test data? → Low severity, note only
- Is it in a comment explaining what NOT to do? → Not an issue

**INFO findings (gitignored files):**
- Report as: "Credentials found in gitignored `.env` - ensure this file stays gitignored"

### 2. Proprietary Information (Tracked Files ONLY)

**HIGH findings (tracked files):**
- Real company names in code/comments (not generic Azure/Microsoft references)
- Real product names in source code
- Employee names/emails in code
- Client names or customer data

**Check for genericization:**
- Look for patterns like `Product A`, `Product-1`, `PRODUCT_*` (generic = good)
- If user says "products were generized", VERIFY by comparing generic vs specific occurrences

**Context matters:**
- GitHub username in README/docs for public repo → NORMAL (not a finding)
- Personal name as git commit author → NORMAL (expected)
- Company name in LICENSE file → EXPECTED (not a finding unless wrong company)

### 3. Template Files Verification

**Read and verify these use placeholders:**
- `.env.template` or `.env.example`
- Config templates
- Setup guides

**Good placeholders:**
- `your_key_here`, `YOUR_VALUE`, `<insert-value>`
- `GENERATE_SECURE_PASSWORD`, `changeme`
- Obvious fake data: `user@example.com`, `https://example.com`

**Bad (real data in templates):**
- Actual email addresses
- Real organization URLs
- Real product names (unless intentionally public)

### 4. Git History Deep Scan

**CRITICAL if found:**
```bash
# Search entire git history for credential patterns
git grep -i "password.*=.*['\"]" $(git rev-list --all) | grep -v "os.getenv\|your_.*here\|example"
```

**If ANY credentials found in git history:**
- Severity: CRITICAL
- Impact: Even if removed now, still in git history
- Remediation: Requires git history rewrite OR credential rotation before public

## Reporting Format

### Structure by Actual Risk

**🔴 CRITICAL (Must fix before public):**
- Real credentials in tracked files
- Real credentials in git history
- Sensitive customer/client data in tracked files

**🟠 HIGH (Strongly recommended to fix):**
- Proprietary company information in tracked files
- Real product names in tracked files (unless intentionally public)
- Employee PII in tracked files

**🟡 MEDIUM (Consider fixing):**
- Suspicious patterns that need review
- Potentially sensitive but context unclear

**🔵 INFO (Not blocking, just awareness):**
- Credentials in gitignored files (note: ensure stays gitignored)
- Template files verification results
- Git history verification results (PASS/FAIL)

### Report Format

For each finding:
```markdown
**Finding:** [Description]
**File:** [path:line]
**Status:** [TRACKED by git / GITIGNORED]
**Severity:** [CRITICAL/HIGH/MEDIUM/INFO based on status]
**Context:** [Is this a real issue or false positive?]
**Excerpt:** [Show the line, redacted if truly sensitive]
**Action:** [What to do about it]
```

**Include a summary section:**
```markdown
## Summary

**Files Scanned:** X tracked files (Y total files in directory)
**Gitignored Files:** Z files protected by gitignore
**Real Issues (tracked files):** N findings
**Info Only (gitignored files):** M findings
**False Positives Filtered:** P findings
**Git History Verified:** PASS/FAIL for .env, data/, sensitive files

**Overall Risk:** GREEN/YELLOW/RED
```

## Critical Rules

1. **Git-aware scanning is MANDATORY** - Don't just grep the entire directory
2. **Verify user claims** - If they say "X was never committed", run `git log` to confirm
3. **Context matters** - Variable names aren't credentials, GitHub usernames in READMEs are normal
4. **Distinguish tracked vs gitignored** - They have completely different risk profiles
5. **Reduce false positives** - Better to have 3 real findings than 15 false alarms
6. **DO NOT auto-fix** - Present findings for user approval first
7. **Severity based on git status** - Same finding can be CRITICAL (tracked) or INFO (gitignored)

## Common False Positives to Avoid

❌ **Don't report these as CRITICAL:**
- Credentials in `.env` file (if gitignored)
- GitHub username in README/docs for public repository
- `password` variable names in code (`password = os.getenv("PASSWORD")`)
- Example/placeholder values in `.template` files
- Test fixture data with fake credentials
- Comments explaining security (e.g., "// never hardcode passwords")

✅ **DO report these as CRITICAL:**
- Credentials in tracked Python/JS/YAML files
- Credentials in git history (even if removed from current files)
- Real customer/client names in tracked data files
- Real company proprietary info in tracked documentation

# Security Sweep

Perform a comprehensive security scan before making the repository public.

## Steps

1. **Credential Scan**: Search for hardcoded credentials, API keys, tokens
   - Grep patterns: `password`, `secret`, `token`, `api_key`, `Bearer`, `AWS`, `PRIVATE_KEY`
   - Check for base64-encoded secrets
   - Look for connection strings and database credentials

2. **Gitignore Verification**: Check `.gitignore` covers all sensitive files
   - `.env`, `.env.*`
   - `*.pem`, `*.key`, `*.pfx`
   - `*credentials*`, `*secrets*`
   - Any local config files

3. **Proprietary Information**: Search for company/employee references
   - Internal company names (not generic Azure/Microsoft references)
   - Employee names in comments, authors, or data files
   - Product names that shouldn't be public
   - Check both source code AND history/data JSON files

4. **Internal URLs**: Check for exposed internal system URLs
   - Internal domain names
   - Private IP addresses
   - Internal API endpoints

5. **Report Findings**: Present all findings with file paths and line numbers
   - Categorize by severity: CRITICAL, HIGH, MEDIUM, LOW
   - Provide context for each finding

## Critical Rules

- **DO NOT** auto-fix anything - present findings for user approval first
- Be thorough - check source code, config files, data files, and templates
- False positives are okay - better safe than sorry
- Include excerpts of problematic content (redacted if needed)

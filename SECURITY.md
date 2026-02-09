# Security Guidelines

## 🔒 Credential Management

### ✅ What's Protected

**`.env` File Security**:
- ✅ **In `.gitignore`** (line 8) - never committed to git
- ✅ **Not in git history** - verified clean
- ✅ **Not deployed to Azure** - stays local only
- ✅ **Only used for local development**

**Azure Application Settings**:
- ✅ **Encrypted at rest** in Azure
- ✅ **Encrypted in transit** (HTTPS only)
- ✅ **Not visible in logs** (marked as secrets)
- ✅ **Access controlled** by Azure RBAC

---

## 🚫 What NOT to Do

### Never Commit These Files:
```bash
# These are in .gitignore - DO NOT remove them:
.env                    # Local credentials
.env.local              # Local overrides
.env.production         # Production credentials
credentials.json        # Google OAuth
token.json              # Google OAuth tokens
*.pem                   # Private keys
*.key                   # Private keys
```

### Never Hardcode Credentials:
```python
# ❌ BAD - Hardcoded
api_key = "abc123-secret-key"

# ✅ GOOD - From environment
from execution.core.secure_config import get_config
config = get_config()
api_key = config.get_armorcode_config().api_key
```

### Never Log Credentials:
```python
# ❌ BAD - Logs password
logger.info(f"Connecting with password: {password}")

# ✅ GOOD - Logs without credentials
logger.info("Connecting to API", extra={"endpoint": endpoint})
```

---

## 🛡️ Deployment Security

### Local Development
```bash
# Your .env file:
API_PASSWORD=DevPassword123  # OK - only on your machine
```

### Azure Production
```bash
# Azure Portal → Configuration → Application Settings:
API_PASSWORD = [Strong password]  # Encrypted in Azure
```

### Script Security: deploy-azure-config.sh

**What the script does**:
1. ✅ Prompts for API password (not hardcoded)
2. ✅ Reads .env securely (doesn't expose in process list)
3. ✅ Sends via Azure CLI over HTTPS
4. ✅ Suppresses output (--output none)
5. ✅ Clears variables from memory after upload

**How to run safely**:
```bash
# 1. Only run on YOUR secure machine (not shared/public)
chmod +x deploy-azure-config.sh
./deploy-azure-config.sh

# 2. Script will prompt for credentials
# 3. Reads from .env (file stays local)
# 4. Uploads to Azure (encrypted)
```

---

## 🔍 Security Checklist

### Before Committing Code:
- [ ] Run `git status` - ensure .env is NOT listed
- [ ] Check `git diff` - no credentials in code
- [ ] Review `.gitignore` - .env is present
- [ ] Verify no API keys in comments

### Before Deploying to Azure:
- [ ] .env file stays on local machine (not copied to Azure)
- [ ] All credentials in Azure Application Settings
- [ ] API_PASSWORD changed from any default value
- [ ] Test with `az webapp config appsettings list` (verify settings exist)
- [ ] SSL/HTTPS enabled (default in Azure)

### After Deployment:
- [ ] Test authentication works
- [ ] Verify /health endpoint accessible
- [ ] Check Azure logs for errors (not credentials)
- [ ] Enable Application Insights for monitoring

---

## 🚨 If Credentials Are Exposed

### If .env Committed to Git:

**Option 1: Last commit only**
```bash
# Remove from last commit (if not pushed)
git reset HEAD~1
git add .env  # Re-add to gitignore
git commit -m "Remove sensitive data"
```

**Option 2: Already pushed**
```bash
# Use git filter-branch or BFG Repo Cleaner
# See: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository

# Then rotate ALL credentials immediately
```

### If Credentials Leaked:

1. **Immediately rotate** all exposed credentials:
   - Azure DevOps PAT: https://dev.azure.com/[org]/_usersSettings/tokens
   - ArmorCode API Key: ArmorCode UI → Settings → API Keys
   - API Password: Update in Azure Application Settings

2. **Check for unauthorized access**:
   - Azure DevOps activity logs
   - ArmorCode audit logs
   - Azure Application Insights

3. **Update everywhere**:
   - Local .env file
   - Azure Application Settings
   - Any documentation with examples

---

## 🔐 Best Practices

### Strong Passwords
```bash
# ❌ Weak
API_PASSWORD=admin123

# ✅ Strong
API_PASSWORD=X9#kL2$mQ8@vR4&nP7
```

### Credential Rotation
- **Azure DevOps PAT**: Rotate every 90 days
- **ArmorCode API Key**: Rotate annually
- **API Password**: Rotate quarterly
- **Set expiration reminders** in your calendar

### Least Privilege
```bash
# Azure DevOps PAT - Only grant needed scopes:
- Work Items: Read ✅
- Code: None ❌
- Build: None ❌
```

### Audit Logs
- Enable Azure Application Insights
- Monitor authentication failures
- Set up alerts for unusual activity

---

## 📋 Security Verification

### Verify .env is Protected:
```bash
# Check gitignore
grep "^\.env$" .gitignore
# Should output: .env

# Check not tracked
git status --porcelain | grep "\.env$"
# Should output: nothing

# Check not in history
git log --all --full-history --source -- .env
# Should output: nothing
```

### Verify Azure Configuration:
```bash
# List settings (values are hidden)
az webapp config appsettings list \
  --resource-group metrics-api-rg \
  --name metrics-api-prod \
  --query "[].{name:name}" \
  --output table

# Should show: API_USERNAME, API_PASSWORD, ADO_PAT, etc.
# Should NOT show actual values
```

---

## 📞 Security Resources

**Internal**:
- [AZURE_DEPLOYMENT_GUIDE.md](AZURE_DEPLOYMENT_GUIDE.md) - Secure deployment steps
- [README.md](README.md) - Project setup

**External**:
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Azure Security Best Practices](https://learn.microsoft.com/en-us/azure/security/fundamentals/best-practices-and-patterns)
- [GitHub Security](https://docs.github.com/en/code-security)

---

## ✅ Current Security Status

**Verified**:
- ✅ `.env` in `.gitignore`
- ✅ `.env` not tracked by git
- ✅ `.env` not in git history
- ✅ `secure_config.py` validates all credentials
- ✅ No hardcoded credentials in code
- ✅ SSL enforced in `http_client.py`
- ✅ Timing-attack resistant authentication
- ✅ Rate limiting enabled

**Grade**: A+ (Excellent Security) 🏆

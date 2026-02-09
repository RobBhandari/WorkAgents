# Azure Static Web Apps Setup Guide

## Step 1: Create Static Web App in Azure Portal

1. Go to [Azure Portal](https://portal.azure.com)
2. Click **"Create a resource"**
3. Search for **"Static Web App"**
4. Click **"Create"**

### Configuration:

**Basics:**
- **Subscription:** Your Azure subscription
- **Resource Group:** Create new or use existing (e.g., `observatory-dashboards`)
- **Name:** `observatory-dashboards` (or your preferred name)
- **Plan type:** **Free** (includes authentication!)
- **Region:** Choose closest to your team
- **Deployment source:** **Other** (we'll use GitHub Actions)

**Important:** Note down the Static Web App name - you'll need it later!

Click **"Review + Create"** → **"Create"**

---

## Step 2: Get Deployment Token

After creation:

1. Go to your Static Web App resource
2. Click **"Manage deployment token"** (in Overview or Settings)
3. Copy the deployment token
4. **Save this securely** - you'll add it to GitHub secrets

---

## Step 3: Configure Authentication (Azure AD)

1. In your Static Web App, go to **"Authentication"** in the left menu
2. Under **"Identity provider"**, Azure Active Directory should be listed
3. The configuration from `staticwebapp.config.json` will automatically:
   - Require authentication for all routes
   - Redirect unauthenticated users to Azure AD login
   - Allow only authenticated users to access dashboards

### Optional: Restrict to Specific Users/Groups

To further restrict access:

1. Go to **"Role management"** in your Static Web App
2. Click **"Add"**
3. Choose **"Invite users"**
4. Enter email addresses of team members
5. Assign role: **"authenticated"**

Or use Azure AD groups:
1. Create an Azure AD group (e.g., "Dashboard Viewers")
2. Add team members to the group
3. In Static Web App → Authentication → Configure roles
4. Map the AD group to the "authenticated" role

---

## Step 4: Add GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add these secrets:

### Secret 1: `AZURE_STATIC_WEB_APPS_API_TOKEN`
- **Value:** The deployment token from Step 2

### Secret 2: `AZURE_STATIC_WEB_APP_NAME`
- **Value:** Your Static Web App name (e.g., `observatory-dashboards`)

---

## Step 5: Test Deployment

1. Go to GitHub Actions
2. Run the **"Refresh Observatory Dashboards"** workflow manually
3. Watch the deployment to Azure Static Web Apps

Once complete:

**Access URL:** `https://[your-app-name].azurestaticapps.net/`

---

## Step 6: Test Authentication

1. Open the URL in private/incognito browser
2. You should be redirected to Azure AD login
3. Sign in with your work account
4. You should see the dashboards

**If you see dashboards without login:** Authentication not configured correctly
**If you get "Access Denied":** User not authorized - add them in Role management

---

## Troubleshooting

### Dashboards not loading?
- Check GitHub Actions workflow completed successfully
- Check Static Web App deployment logs in Azure Portal

### Authentication not working?
- Verify `staticwebapp.config.json` is deployed with dashboards
- Check Authentication settings in Azure Portal
- Ensure users are added to allowed roles

### Want to add/remove users?
- Azure Portal → Static Web App → Role management → Invite users

---

## Migration Complete! 🎉

Your dashboards are now:
- ✅ **Private** - Only authenticated users can access
- ✅ **Secure** - Azure AD authentication
- ✅ **Fast** - Same performance as before
- ✅ **Free** - Using Free tier of Static Web Apps

Old Blob Storage URL will still work but is public - you can disable it after confirming Static Web App works.

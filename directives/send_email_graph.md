# Send Email via Microsoft Graph API

## Goal
Send emails from Office365/Microsoft 365 accounts using Microsoft Graph API with OAuth 2.0 authentication (modern auth).

## Inputs
Required:
- **To Email**: Recipient email address
- **Subject**: Email subject line
- **Body**: Email body content (plain text or HTML)
- **Azure AD Credentials**: Tenant ID, Client ID, Client Secret

Optional:
- **Attachments**: List of file paths to attach
- **CC/BCC**: Additional recipients
- **Send Time**: When to send (for scheduled sending)

## Tools/Scripts to Use
- `execution/send_email_graph.py` - Script that sends emails via Microsoft Graph API

## Outputs
- **Email sent** via Graph API
- **Log file** in `.tmp/email_graph_[timestamp].log`
- **Confirmation** message with send status

## Process Flow
1. Load Azure AD credentials from .env (Tenant ID, Client ID, Client Secret)
2. Authenticate with Microsoft Graph API using client credentials flow
3. Get OAuth 2.0 access token
4. Compose email with body and attachments
5. Send email via Graph API `/me/sendMail` endpoint
6. Log result

## Edge Cases
- **Token Expiration**: Tokens expire after 1 hour - script automatically refreshes
- **Attachment Size**: Graph API supports up to 4MB attachments inline, larger files need upload session
- **Rate Limits**: Graph API has throttling limits - script includes retry logic
- **Permissions**: App must have `Mail.Send` permission in Azure AD
- **Delegated vs App Permissions**: Using app permissions (client credentials flow) for unattended scenarios

## Azure AD Setup Required
1. Go to https://portal.azure.com
2. Navigate to "Azure Active Directory" → "App registrations"
3. Click "New registration"
   - Name: "Email Automation Script"
   - Supported account types: "Accounts in this organizational directory only"
4. After creation, note the:
   - **Application (client) ID**
   - **Directory (tenant) ID**
5. Create client secret:
   - Go to "Certificates & secrets"
   - Click "New client secret"
   - Note the **secret value** (copy immediately, won't be shown again)
6. Grant permissions:
   - Go to "API permissions"
   - Click "Add a permission" → "Microsoft Graph" → "Application permissions"
   - Select `Mail.Send`
   - Click "Grant admin consent" (requires admin)

## Learnings
- Graph API is the modern way to interact with Microsoft 365
- Client credentials flow allows unattended email sending
- Requires one-time Azure AD setup but more reliable than SMTP
- Corporate accounts often have SMTP disabled but Graph API enabled

---

**Created**: 2026-01-29
**Last Updated**: 2026-01-29
**Status**: Active

# Send Scheduled Email

## Goal
Send an email with optional attachments at a specified time using SMTP.

## Inputs
Required:
- **To Email**: Recipient email address
- **Subject**: Email subject line
- **Body**: Email body content (plain text or HTML)

Optional:
- **Send Time**: When to send (default: immediately)
- **Attachments**: List of file paths to attach
- **From Email**: Sender email (default: from .env)
- **CC/BCC**: Additional recipients

## Tools/Scripts to Use
- `execution/send_email.py` - Script that sends emails via SMTP
- Windows Task Scheduler - For scheduling future sends

## Outputs
- **Email sent** to specified recipient
- **Log file** in `.tmp/email_[timestamp].log`
- **Confirmation** message with send status

## Process Flow
1. Configure SMTP settings in .env (email, password, server)
2. If immediate send: call script directly
3. If scheduled: create Windows Task Scheduler task to run script at specified time
4. Script connects to SMTP server
5. Composes email with body and attachments
6. Sends email and logs result

## Edge Cases
- **SMTP Authentication**: Requires app-specific password for Gmail/Outlook
- **Attachment Size**: Large files may be rejected by email servers
- **Network Issues**: Script retries up to 3 times on failure
- **Scheduled Task**: Must have system permissions to create scheduled tasks
- **Time Zones**: All times are in local system time

## Learnings
- Gmail requires "App Passwords" (not regular password) for SMTP
- Outlook/Office365 uses smtp.office365.com:587
- HTML emails should include plain text alternative

---

**Created**: 2026-01-29
**Last Updated**: 2026-01-29
**Status**: Active

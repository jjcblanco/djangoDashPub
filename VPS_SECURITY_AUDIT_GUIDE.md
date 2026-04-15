# VPS Security Audit Tool - Deployment Guide

## Overview
This guide explains how to deploy and use the security audit tool on your VPS for the Crypto Trading Dashboard.

## Files Created

1. **`criptodash/vps_security_audit.py`** - Standalone audit script for VPS
2. **`CRIPTODASH_SECURITY_AUDIT.md`** - General documentation
3. **`security_audit_report_20260413_194141.pdf`** - Sample PDF report (from local run)

## Step 1: Transfer Files to VPS

### Option A: Using SCP (Secure Copy)
```bash
# From your local machine
scp criptodash/vps_security_audit.py user@your-vps-ip:/home/user/criptodash/
scp CRIPTODASH_SECURITY_AUDIT.md user@your-vps-ip:/home/user/
```

### Option B: Using Git
If your project is on GitHub/GitLab:
```bash
# On VPS
cd /home/user/
git clone your-repo-url
```

### Option C: Manual Copy
Copy the `vps_security_audit.py` file to your VPS using any method (SFTP, FTP, etc.)

## Step 2: SSH into Your VPS
```bash
ssh user@your-vps-ip
cd /path/to/your/criptodash/project
```

## Step 3: Install Dependencies (if needed)

### Basic dependencies (should already be installed):
```bash
pip install django reportlab psutil
```

### Check Django project structure:
```bash
ls -la
# Should see: manage.py, criptodash/, dashboard/, etc.
```
## Step 4: Run the Security Audit

### Basic audit (text report only):
```bash
cd /path/to/your/criptodash
python vps_security_audit.py
```

### With PDF generation (requires ReportLab):
```bash
python vps_security_audit.py --pdf
```

### With JSON output:
```bash
python vps_security_audit.py --json
```

### Custom output filename:
```bash
python vps_security_audit.py --output my_audit_report
# Creates: my_audit_report.txt (and .pdf if --pdf specified)
```

### All options:
```bash
python vps_security_audit.py --pdf --json --output full_audit
```

## Step 5: Review Results

The audit will create:
- `vps_audit_YYYYMMDD_HHMMSS.txt` - Full text report
- `vps_audit_YYYYMMDD_HHMMSS.json` - Findings in JSON format (if --json)
- `vps_security_audit_YYYYMMDD_HHMMSS.pdf` - PDF report (if --pdf and ReportLab installed)

## Step 6: Schedule Regular Audits (Optional)

### Using Cron (Linux):
```bash
# Edit crontab
crontab -e

# Add daily audit at 2 AM
0 2 * * * cd /path/to/criptodash && /usr/bin/python3 vps_security_audit.py --output /var/log/audits/daily_audit

# Add weekly audit with PDF (Sunday at 3 AM)
0 3 * * 0 cd /path/to/criptodash && /usr/bin/python3 vps_security_audit.py --pdf --output /var/log/audits/weekly_audit
```

### Create audit logs directory:
```bash
sudo mkdir -p /var/log/audits
sudo chown your-user:your-user /var/log/audits
```

## Troubleshooting

### Common Issues:

1. **"Django setup failed"**
   - Make sure you're in the correct directory (where `manage.py` is)
   - Check that `.env` file exists with proper configuration
   - Verify Django is installed: `pip list | grep Django`

2. **"Cannot import Binance exchange module"**
   - The `dashboard.ccxttest1` module must exist
   - Check API keys in settings are valid

3. **"ReportLab not installed" for PDF generation**
   ```bash
   pip install reportlab
   ```

4. **Permission errors**
   ```bash
   chmod +x vps_security_audit.py
   ```

5. **Python path issues**
   ```bash
   # Use absolute path to python
   /usr/bin/python3 vps_security_audit.py
   
   # Or use virtual environment
   source venv/bin/activate
   python vps_security_audit.py
   ```

### Check VPS Environment:
```bash
# Python version
python3 --version

# Django version
python3 -c "import django; print(django.get_version())"

# Check project structure
ls -la
ls criptodash/
```

## What the Audit Checks

The VPS audit includes all checks from the local version plus:

1. **System-level checks** (VPS-specific):
   - Disk space usage
   - Memory utilization (if psutil installed)
   - Error log locations (/var/log/ directories)

2. **Enhanced error handling** for VPS environments

3. **Flexible output options** (text, JSON, PDF)

## Security Considerations for VPS

1. **Store audit reports securely**
   ```bash
   # Create secure directory
   mkdir ~/audit_reports
   chmod 700 ~/audit_reports
   ```

2. **Automate cleanup** of old reports
   ```bash
   # Add to crontab - delete reports older than 30 days
   0 4 * * * find /var/log/audits -name "*.txt" -mtime +30 -delete
   0 4 * * * find /var/log/audits -name "*.pdf" -mtime +30 -delete
   ```

3. **Monitor audit failures**
   ```bash
   # Check audit logs
   tail -f /var/log/audits/error.log
   ```

## Integration with Monitoring

### Email alerts for critical findings:
```python
# Example script: email_alert.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import subprocess
import json

# Run audit and get JSON
result = subprocess.run(['python', 'vps_security_audit.py', '--json'], 
                       capture_output=True, text=True)
findings = json.loads(result.stdout)

# Check for critical/high findings
critical = [f for f in findings if f['severity'] in ['CRITICAL', 'HIGH']]
if critical:
    # Send email alert
    # ... email code here
```

### Integration with monitoring tools (Nagios, Zabbix, etc.):
```bash
# Check exit code (0 = success, >0 = issues)
python vps_security_audit.py --json > /tmp/audit.json
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "CRITICAL: Security audit failed"
    exit 2
fi

# Parse JSON for critical findings
CRITICAL_COUNT=$(jq '[.[] | select(.severity == "CRITICAL")] | length' /tmp/audit.json)
if [ $CRITICAL_COUNT -gt 0 ]; then
    echo "CRITICAL: $CRITICAL_COUNT critical security issues found"
    exit 2
fi
```

## Quick Start Commands

```bash
# 1. Connect to VPS
ssh user@your-vps-ip

# 2. Go to project
cd /path/to/criptodash

# 3. Make script executable
chmod +x vps_security_audit.py

# 4. Run first audit
python vps_security_audit.py --pdf --json

# 5. Check results
ls -la vps_audit_*.txt vps_audit_*.pdf vps_audit_*.json
```

## Support

If you encounter issues:
1. Check the error messages in the output
2. Verify Django project structure
3. Ensure all dependencies are installed
4. Check file permissions

For persistent issues, check:
- Django logs: `cat criptodash/logs/*.log`
- System logs: `tail -f /var/log/syslog`
- Python traceback: Add `--traceback` to see full error details
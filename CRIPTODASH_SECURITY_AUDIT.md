# Security Audit Tool for Crypto Trading Dashboard

## Overview
A comprehensive security audit tool that analyzes the trading dashboard system for security vulnerabilities, configuration issues, and operational risks. The tool generates detailed PDF reports with findings and recommendations.

## Features

### Security Checks Performed:
1. **Environment Configuration**
   - DEBUG mode detection
   - SECRET_KEY strength validation
   - ALLOWED_HOSTS configuration review
   - Database configuration analysis
   - API key validation

2. **Database Security**
   - Connection testing
   - User account analysis
   - Password hashing assessment

3. **Financial Integrity**
   - Balance consistency between Binance and local records
   - Fund allocation analysis
   - Discrepancy detection

4. **Bot Operations**
   - Bot status and performance analysis
   - Error state detection
   - Consistency checks

5. **Trade Analysis**
   - Orphan trade detection
   - Stale position identification
   - Recent trade review

6. **Error Log Analysis**
   - System error review
   - Network connectivity issues
   - API error patterns

## Installation

### Dependencies
The tool requires:
- Django 5.2.7+
- ReportLab 4.4.10+ (for PDF generation)
- Celery 5.6.3+ (for Django integration)

Install missing dependencies:
```bash
pip install reportlab celery
```

## Usage

### Running a Security Audit

1. **Basic audit with PDF report:**
   ```bash
   cd criptodash
   python run_security_audit.py
   ```

2. **Run audit only (no PDF):**
   ```bash
   cd criptodash
   python -c "from security_audit import SecurityAudit; audit = SecurityAudit(); print(audit.run_full_audit())"
   ```

3. **Generate custom PDF report:**
   ```bash
   cd criptodash
   python -c "
   from security_audit import SecurityAudit
   from pdf_generator import generate_security_audit_pdf
   
   audit = SecurityAudit()
   report = audit.run_full_audit()
   findings = audit.get_findings()
   
   pdf_path = generate_security_audit_pdf(report, findings, 'custom_audit.pdf')
   print(f'Report: {pdf_path}')
   "
   ```

### Output Files

The tool generates:
- `security_audit_report_YYYYMMDD_HHMMSS.pdf` - PDF report with executive summary and detailed findings
- `security_audit_YYYYMMDD_HHMMSS.txt` - Raw text audit report
- Files are saved in the `criptodash` directory

## Report Contents

### Executive Summary
- Overall risk assessment (CRITICAL, HIGH, MEDIUM, LOW)
- Findings count by severity
- Key recommendations

### Detailed Findings Table
- Severity level (color-coded)
- Category (Configuration, Financial, Bot Operations, etc.)
- Description of the issue
- Recommendation for resolution

### Full Audit Report
- Complete output from all audit checks
- Informational messages and error logs

## Example Findings

### High Severity Issues:
1. **DEBUG mode enabled in production** - Security risk exposing sensitive information
2. **Balance discrepancies** - Bots think they have more funds than available on exchange

### Medium Severity Issues:
1. **Wildcard ALLOWED_HOSTS** - Potential security vulnerability
2. **Bots in ERROR state** - Operational issues affecting trading
3. **Network connection errors** - API connectivity problems

### Low Severity Issues:
1. **Password hashing algorithm** - Potential for stronger security
2. **Bot status inconsistencies** - Administrative cleanup needed

## Scheduled Audits

For regular security monitoring, consider adding to Celery tasks:

```python
# In your Celery tasks.py
from celery import shared_task
from security_audit import SecurityAudit
from pdf_generator import generate_security_audit_pdf
import datetime

@shared_task
def run_daily_security_audit():
    """Run security audit daily and email report"""
    audit = SecurityAudit()
    report = audit.run_full_audit()
    findings = audit.get_findings()
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d")
    pdf_path = generate_security_audit_pdf(
        report, 
        findings, 
        f'daily_audit_{timestamp}.pdf'
    )
    
    # Email logic here
    return pdf_path
```

## Integration with Existing System

The audit tool integrates with:
- Django settings and configuration
- Database models (LiveBot, LiveTrade, etc.)
- Binance API through ccxttest1 module
- Existing error logs (whale_debug.log)

## Customization

### Adding New Checks
Extend the `SecurityAudit` class:

```python
class ExtendedSecurityAudit(SecurityAudit):
    def run_custom_checks(self):
        self.add_section("CUSTOM CHECKS")
        # Add your checks here
        # Use add_finding(), add_info(), add_error()
        
    def run_full_audit(self):
        super().run_full_audit()
        self.run_custom_checks()
        return self.get_report_text()
```

### Modifying Severity Levels
Edit the `add_finding()` calls in `security_audit.py` to adjust severity based on your risk assessment.

## Troubleshooting

### Common Issues:

1. **Database connection errors** - Ensure MySQL is running and credentials in `.env` are correct
2. **Binance API errors** - Check API keys in settings and internet connectivity
3. **PDF generation errors** - Verify ReportLab installation and file permissions
4. **Unicode errors** - Use ASCII characters in print statements on Windows

### Logging
Check `whale_debug.log` for system errors that may affect audit results.

## Security Considerations

- The audit tool accesses sensitive information (API keys, database credentials)
- Ensure audit reports are stored securely
- Consider encrypting PDF reports containing financial information
- Regular audits help maintain system integrity and prevent losses

## License
This tool is part of the Crypto Trading Dashboard project.
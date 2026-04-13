#!/usr/bin/env python
"""
Standalone Security Audit Script for VPS Deployment
This script can be copied to your VPS and run independently.
"""

import os
import sys
import django
import datetime
import json
from decimal import Decimal
from django.utils import timezone

# ============================================================================
# SETUP - Modify these paths if needed
# ============================================================================

# Set the path to your Django project on VPS
# Example: /home/username/criptodash/ or /var/www/criptodash/
DJANGO_PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))

# Add to Python path and setup Django
sys.path.append(DJANGO_PROJECT_PATH)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')

try:
    django.setup()
    print(f"[OK] Django setup successful from: {DJANGO_PROJECT_PATH}")
except Exception as e:
    print(f"[ERROR] Django setup failed: {e}")
    print("\nMake sure:")
    print("1. You're in the correct directory (where manage.py is located)")
    print("2. The .env file exists with proper configuration")
    print("3. All dependencies are installed: pip install -r requirements.txt")
    sys.exit(1)

# Now import Django models
from django.db import connection
from django.conf import settings
from dashboard.models import LiveBot, LiveTrade, TradeSignal, TradingPair
from django.contrib.auth.models import User

# ============================================================================
# SECURITY AUDIT CLASS
# ============================================================================

class VPSSecurityAudit:
    """Security audit optimized for VPS deployment"""
    
    def __init__(self, generate_pdf=False):
        self.report = []
        self.findings = []
        self.errors = []
        self.timestamp = datetime.datetime.now()
        self.generate_pdf = generate_pdf
        self.pdf_available = False
        
        # Check if ReportLab is available for PDF generation
        if generate_pdf:
            try:
                from reportlab.lib import colors
                from reportlab.lib.pagesizes import A4
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
                from reportlab.lib.styles import getSampleStyleSheet
                self.pdf_available = True
                print("[INFO] PDF generation enabled (ReportLab available)")
            except ImportError:
                print("[WARN] ReportLab not installed. PDF generation disabled.")
                print("[INFO] Install with: pip install reportlab")
                self.generate_pdf = False
                self.pdf_available = False
    
    def add_section(self, title):
        """Add a section header to the report"""
        self.report.append(f"\n{'='*80}")
        self.report.append(f"{title}")
        self.report.append(f"{'='*80}")
    
    def add_finding(self, category, severity, description, recommendation=None):
        """Add a security finding"""
        finding = {
            'category': category,
            'severity': severity,
            'description': description,
            'recommendation': recommendation,
            'timestamp': self.timestamp
        }
        self.findings.append(finding)
        self.report.append(f"\n[{severity}] {category}: {description}")
        if recommendation:
            self.report.append(f"   Recommendation: {recommendation}")
    
    def add_info(self, message):
        """Add informational message"""
        self.report.append(f"INFO: {message}")
    
    def add_error(self, message):
        """Add error message"""
        self.errors.append(message)
        self.report.append(f"ERROR: {message}")
    
    def run_environment_checks(self):
        """Check environment configuration"""
        self.add_section("ENVIRONMENT CHECKS")
        
        # Check DEBUG mode
        if getattr(settings, 'DEBUG', True):
            self.add_finding(
                "Configuration", 
                "HIGH", 
                "DEBUG mode is enabled in production",
                "Set DEBUG=False in production environment (.env file)"
            )
        else:
            self.add_info("DEBUG mode is disabled (good)")
        
        # Check SECRET_KEY
        secret_key = getattr(settings, 'SECRET_KEY', '')
        if not secret_key or secret_key == 'django-insecure-' or len(secret_key) < 20:
            self.add_finding(
                "Configuration",
                "CRITICAL",
                "Weak or default SECRET_KEY detected",
                "Generate a strong random SECRET_KEY and store it securely"
            )
        else:
            self.add_info(f"SECRET_KEY appears to be strong ({len(secret_key)} chars)")
        
        # Check ALLOWED_HOSTS
        allowed_hosts = getattr(settings, 'ALLOWED_HOSTS', [])
        if not allowed_hosts:
            self.add_finding(
                "Configuration",
                "HIGH",
                "ALLOWED_HOSTS is empty",
                "Configure ALLOWED_HOSTS with appropriate domain names"
            )
        elif '*' in allowed_hosts:
            self.add_finding(
                "Configuration",
                "MEDIUM",
                "ALLOWED_HOSTS contains '*' wildcard",
                "Specify exact hostnames instead of wildcard"
            )
        else:
            self.add_info(f"ALLOWED_HOSTS configured: {allowed_hosts}")
        
        # Check database configuration
        db_config = getattr(settings, 'DATABASES', {}).get('default', {})
        if db_config.get('ENGINE') == 'django.db.backends.sqlite3':
            self.add_finding(
                "Database",
                "MEDIUM",
                "Using SQLite database (not recommended for production)",
                "Consider using PostgreSQL or MySQL for production"
            )
        
        # Check API keys
        binance_key = getattr(settings, 'BINANCE_APIKEY', None)
        binance_secret = getattr(settings, 'BINANCE_SECRET', None)
        
        if not binance_key or not binance_secret:
            self.add_finding(
                "API Keys",
                "HIGH",
                "Binance API keys not configured or empty",
                "Ensure BINANCE_APIKEY and BINANCE_SECRET are set in .env"
            )
        else:
            # Check if keys look like placeholders
            if 'your-' in str(binance_key).lower() or 'example' in str(binance_key).lower():
                self.add_finding(
                    "API Keys",
                    "CRITICAL",
                    "Binance API key appears to be a placeholder",
                    "Replace with actual API keys"
                )
            else:
                self.add_info("Binance API keys are configured")
    
    def run_database_checks(self):
        """Check database security and integrity"""
        self.add_section("DATABASE CHECKS")
        
        try:
            # Test database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                self.add_info("Database connection successful")
            
            # Check for sensitive data exposure
            user_count = User.objects.count()
            self.add_info(f"Total users in system: {user_count}")
            
            # Check for default admin account
            default_admin = User.objects.filter(username='admin').exists()
            if default_admin:
                self.add_finding(
                    "Authentication",
                    "MEDIUM",
                    "Default 'admin' username exists",
                    "Rename default admin account or ensure strong password"
                )
            
            # Check user passwords
            weak_passwords = User.objects.filter(password__startswith='pbkdf2_sha256$10000')
            if weak_passwords.exists():
                self.add_finding(
                    "Authentication",
                    "LOW",
                    f"{weak_passwords.count()} users may have weak password hashing",
                    "Consider upgrading password hashing algorithm"
                )
            
        except Exception as e:
            self.add_error(f"Database check failed: {e}")
    
    def run_balance_audit(self):
        """Audit balance consistency"""
        self.add_section("BALANCE AUDIT")
        
        try:
            # Try to import Binance exchange
            try:
                from dashboard.ccxttest1 import binance as exchange
            except ImportError as e:
                self.add_error(f"Cannot import Binance exchange module: {e}")
                self.add_info("Balance audit requires dashboard.ccxttest1 module")
                return
            
            # Get real balance from Binance
            try:
                bal = exchange.fetch_balance()
                real_free = Decimal(str(bal['free'].get('USDT', 0)))
                real_used = Decimal(str(bal['used'].get('USDT', 0)))
                real_total = Decimal(str(bal['total'].get('USDT', 0)))
                
                self.add_info(f"Binance REAL USDT:")
                self.add_info(f"  Total: {real_total}")
                self.add_info(f"  Free: {real_free}")
                self.add_info(f"  Used (in orders): {real_used}")
                
            except Exception as e:
                self.add_error(f"Error connecting to Binance: {e}")
                self.add_info("Make sure Binance API keys are valid and network is accessible")
                return
            
            # Get local balance from active bots
            active_bots = LiveBot.objects.all()
            sum_local_balances = Decimal("0")
            
            for bot in active_bots:
                sum_local_balances += bot.current_balance
                open_trades = LiveTrade.objects.filter(bot=bot, status='OPEN')
                trading_val = sum(t.amount * t.entry_price for t in open_trades)
                
                self.add_info(f"- {bot.name} ({bot.status}):")
                self.add_info(f"  Local Balance: {bot.current_balance}")
                self.add_info(f"  Capital in Open Trades: {trading_val}")
            
            self.add_info(f"\nTotal Local Balances: {sum_local_balances}")
            
            # Compare
            discrepancy = real_total - sum_local_balances
            self.add_info(f"Discrepancy (Real - Local): {discrepancy}")
            
            if discrepancy < 0:
                self.add_finding(
                    "Financial",
                    "HIGH",
                    f"Balance discrepancy detected: bots think they have ${-discrepancy} more than available on Binance",
                    "Check for shared funds between bots or improperly closed trades"
                )
            elif discrepancy > Decimal("100"):  # More than 100 USDT unaccounted
                self.add_finding(
                    "Financial",
                    "MEDIUM",
                    f"Significant unallocated funds: {discrepancy} USDT not assigned to bots",
                    "Review fund allocation strategy"
                )
            
        except Exception as e:
            self.add_error(f"Balance audit failed: {e}")
    
    def run_bot_audit(self):
        """Audit bot performance and status"""
        self.add_section("BOT AUDIT")
        
        try:
            active_bots = LiveBot.objects.all()
            bot_count = active_bots.count()
            self.add_info(f"Total bots in system: {bot_count}")
            
            error_bots = []
            running_bots = []
            stopped_bots = []
            
            for bot in active_bots:
                trades = LiveTrade.objects.filter(bot=bot)
                closed_trades = trades.filter(status='CLOSED')
                open_trades = trades.filter(status='OPEN')
                
                total_pnl = sum(t.pnl for t in trades)
                realized_pnl = sum(t.pnl for t in closed_trades)
                
                winning_trades = closed_trades.filter(pnl__gt=0).count()
                losing_trades = closed_trades.filter(pnl__lt=0).count()
                total_closed = closed_trades.count()
                
                win_rate = (winning_trades / total_closed * 100) if total_closed > 0 else 0
                
                self.add_info(f"\nBot: {bot.name} (ID: {bot.id})")
                self.add_info(f"Strategy: {bot.strategy_type}")
                self.add_info(f"Status: {bot.status} | Is_Live: {bot.is_live}")
                self.add_info(f"Initial Balance: {bot.initial_balance} | Current: {bot.current_balance}")
                self.add_info(f"Return: {bot.current_balance - bot.initial_balance}")
                self.add_info(f"Total PNL: {total_pnl} | Realized: {realized_pnl}")
                self.add_info(f"Closed Trades: {total_closed} (Winning: {winning_trades}, Losing: {losing_trades})")
                self.add_info(f"Win Rate: {win_rate:.2f}%")
                self.add_info(f"Open Trades: {open_trades.count()}")
                
                # Categorize bots
                if bot.status == 'ERROR':
                    error_bots.append(bot)
                elif bot.status == 'RUNNING':
                    running_bots.append(bot)
                elif bot.status == 'STOPPED':
                    stopped_bots.append(bot)
                
                # Check for stuck bots
                if bot.status == 'ERROR' and bot.last_error:
                    self.add_finding(
                        "Bot Operations",
                        "MEDIUM",
                        f"Bot {bot.name} is in ERROR state: {bot.last_error[:100]}",
                        "Investigate and restart or fix the bot"
                    )
                
                # Check for inactive bots
                if bot.status == 'STOPPED' and bot.is_live:
                    self.add_finding(
                        "Bot Operations",
                        "LOW",
                        f"Bot {bot.name} is STOPPED but marked as live",
                        "Review bot status consistency"
                    )
            
            # Summary
            self.add_info(f"\nBot Status Summary:")
            self.add_info(f"  Running: {len(running_bots)}")
            self.add_info(f"  Stopped: {len(stopped_bots)}")
            self.add_info(f"  Error: {len(error_bots)}")
            
            if error_bots:
                self.add_finding(
                    "System Health",
                    "MEDIUM",
                    f"{len(error_bots)} bots are in ERROR state",
                    "Review and fix error bots to maintain system health"
                )
            
        except Exception as e:
            self.add_error(f"Bot audit failed: {e}")
    
    def run_trade_audit(self):
        """Audit trade consistency"""
        self.add_section("TRADE AUDIT")
        
        try:
            # Check for open trades without corresponding bot
            orphan_trades = LiveTrade.objects.filter(bot=None)
            if orphan_trades.exists():
                self.add_finding(
                    "Data Integrity",
                    "HIGH",
                    f"{orphan_trades.count()} trades without associated bot",
                    "Investigate and fix orphan trades"
                )
            
            # Check for stale open trades (older than 7 days)
            week_ago = timezone.now() - datetime.timedelta(days=7)
            stale_trades = LiveTrade.objects.filter(
                status='OPEN',
                entry_time__lt=week_ago
            )
            if stale_trades.exists():
                self.add_finding(
                    "Trading",
                    "MEDIUM",
                    f"{stale_trades.count()} open trades older than 7 days",
                    "Review and close stale positions"
                )
            
            # Recent trades
            recent_trades = LiveTrade.objects.all().order_by('-updated_at')[:5]
            self.add_info("\nRecent 5 trades:")
            for t in recent_trades:
                self.add_info(
                    f"{t.updated_at.strftime('%Y-%m-%d %H:%M:%S')} | "
                    f"Bot: {t.bot.name if t.bot else 'N/A'} | "
                    f"{t.side} {t.amount} @ {t.entry_price} | "
                    f"Status: {t.status} | PNL: {t.pnl}"
                )
            
        except Exception as e:
            self.add_error(f"Trade audit failed: {e}")
    
    def run_error_log_analysis(self):
        """Analyze error logs"""
        self.add_section("ERROR LOG ANALYSIS")
        
        try:
            # Check common log locations
            log_locations = [
                os.path.join(DJANGO_PROJECT_PATH, 'whale_debug.log'),
                os.path.join(DJANGO_PROJECT_PATH, 'debug.log'),
                os.path.join(DJANGO_PROJECT_PATH, 'error.log'),
                '/var/log/django/error.log',
                '/var/log/nginx/error.log'
            ]
            
            found_logs = []
            for log_path in log_locations:
                if os.path.exists(log_path):
                    found_logs.append(log_path)
            
            if not found_logs:
                self.add_info("No error logs found in common locations")
                return
            
            for log_path in found_logs:
                try:
                    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    
                    error_count = len([l for l in lines if 'error' in l.lower() or 'exception' in l.lower()])
                    self.add_info(f"{log_path}: {len(lines)} total lines, {error_count} error lines")
                    
                    # Look for critical errors
                    critical_errors = [l for l in lines if any(
                        term in l.lower() for term in ['max retries', 'failed', 'timeout', 'connection refused']
                    )]
                    if critical_errors:
                        self.add_finding(
                            "System Health",
                            "MEDIUM",
                            f"{len(critical_errors)} network/connection errors in {os.path.basename(log_path)}",
                            "Check API connectivity and network configuration"
                        )
                    
                    # Sample recent errors
                    if lines:
                        self.add_info(f"Sample from {os.path.basename(log_path)}:")
                        for line in lines[-3:]:  # Last 3 lines
                            line = line.strip()
                            if line:
                                self.add_info(f"  {line[:100]}..." if len(line) > 100 else f"  {line}")
                                
                except Exception as e:
                    self.add_error(f"Cannot read log {log_path}: {e}")
        
        except Exception as e:
            self.add_error(f"Error log analysis failed: {e}")
    
    def run_system_checks(self):
        """Run system-level checks"""
        self.add_section("SYSTEM CHECKS")
        
        # Check disk space
        try:
            import shutil
            total, used, free = shutil.disk_usage(DJANGO_PROJECT_PATH)
            free_gb = free // (2**30)
            self.add_info(f"Disk space free: {free_gb} GB")
            
            if free_gb < 5:  # Less than 5GB free
                self.add_finding(
                    "System",
                    "MEDIUM",
                    f"Low disk space: {free_gb} GB free",
                    "Clean up disk space to prevent system issues"
                )
        except Exception as e:
            self.add_info(f"Cannot check disk space: {e}")
        
        # Check memory
        try:
            import psutil
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            self.add_info(f"Memory usage: {memory_percent}%")
            
            if memory_percent > 90:
                self.add_finding(
                    "System",
                    "MEDIUM",
                    f"High memory usage: {memory_percent}%",
                    "Check for memory leaks or optimize application"
                )
        except ImportError:
            self.add_info("Install psutil for memory monitoring: pip install psutil")
        except Exception as e:
            self.add_info(f"Cannot check memory: {e}")
    
    def generate_summary(self):
        """Generate executive summary"""
        self.add_section("EXECUTIVE SUMMARY")
        
        # Count findings by severity
        severity_counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        for finding in self.findings:
            severity = finding.get('severity', '').upper()
            if severity in severity_counts:
                severity_counts[severity] += 1
        
        self.add_info(f"Audit completed at: {self.timestamp}")
        self.add_info(f"Total findings: {len(self.findings)}")
        self.add_info(f"Critical findings: {severity_counts['CRITICAL']}")
        self.add_info(f"High findings: {severity_counts['HIGH']}")
        self.add_info(f"Medium findings: {severity_counts['MEDIUM']}")
        self.add_info(f"Low findings: {severity_counts['LOW']}")
        self.add_info(f"Errors during audit: {len(self.errors)}")
        
        # Overall risk assessment
        if severity_counts['CRITICAL'] > 0:
            risk_level = "CRITICAL"
        elif severity_counts['HIGH'] > 0:
            risk_level = "HIGH"
        elif severity_counts['MEDIUM'] > 0:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        self.add_info(f"\nOverall Risk Level: {risk_level}")
        
        # Top recommendations
        if self.findings:
            self.add_info("\nTop Recommendations:")
            high_priority = [f for f in self.findings if f.get('severity') in ['CRITICAL', 'HIGH']]
            for i, finding in enumerate(high_priority[:3], 1):
                if finding.get('recommendation'):
                    self.add_info(f"{i}. {finding['recommendation']}")
    
    def get_report_text(self):
        """Get full report as text"""
        return "\n".join(self.report)
    
    def get_findings_json(self):
        """Get findings as JSON"""
        return json.dumps(self.findings, default=str, indent=2)
    
    def generate_pdf_report(self):
        """Generate PDF report if available"""
        if not self.pdf_available:
            return None
        
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib.enums import TA_CENTER, TA_LEFT
            
            # Create PDF filename
            timestamp = self.timestamp.strftime("%Y%m%d_%H%M%S")
            pdf_filename = f"vps_security_audit_{timestamp}.pdf"
            
            # Create document
            doc = SimpleDocTemplate(
                pdf_filename,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )
            
            styles = getSampleStyleSheet()
            elements = []
            
            # Title
            elements.append(Paragraph("VPS Security Audit Report", styles['Title']))
            elements.append(Spacer(1, 0.5*inch))
            elements.append(Paragraph(f"Generated: {self.timestamp}", styles['Normal']))
            elements.append(Spacer(1, 0.5*inch))
            
            # Summary table
            severity_counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
            for finding in self.findings:
                severity = finding.get('severity', '').upper()
                if severity in severity_counts:
                    severity_counts[severity] += 1
            
            summary_data = [
                ["Critical", str(severity_counts['CRITICAL'])],
                ["High", str(severity_counts['HIGH'])],
                ["Medium", str(severity_counts['MEDIUM'])],
                ["Low", str(severity_counts['LOW'])],
                ["Total", str(len(self.findings))]
            ]
            
            summary_table = Table(summary_data, colWidths=[2*inch, 1*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), colors.red),
                ('BACKGROUND', (0, 1), (0, 1), colors.orangered),
                ('BACKGROUND', (0, 2), (0, 2), colors.orange),
                ('BACKGROUND', (0, 3), (0, 3), colors.lightgreen),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey)
            ]))
            
            elements.append(Paragraph("Findings Summary", styles['Heading2']))
            elements.append(Spacer(1, 0.2*inch))
            elements.append(summary_table)
            elements.append(PageBreak())
            
            # Findings table
            if self.findings:
                elements.append(Paragraph("Detailed Findings", styles['Heading1']))
                elements.append(Spacer(1, 0.2*inch))
                
                table_data = [["Severity", "Category", "Description"]]
                for finding in self.findings:
                    table_data.append([
                        finding.get('severity', ''),
                        finding.get('category', ''),
                        finding.get('description', '')[:80] + "..." if len(finding.get('description', '')) > 80 else finding.get('description', '')
                    ])
                
                table = Table(table_data, colWidths=[1*inch, 1.5*inch, 4*inch])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.whitesmoke])
                ]))
                
                elements.append(table)
                elements.append(PageBreak())
            
            # Full report
            elements.append(Paragraph("Full Audit Report", styles['Heading1']))
            elements.append(Spacer(1, 0.2*inch))
            
            for line in self.report:
                if line.strip():
                    elements.append(Paragraph(line, styles['Normal']))
                    elements.append(Spacer(1, 0.1*inch))
            
            # Build PDF
            doc.build(elements)
            return pdf_filename
            
        except Exception as e:
            self.add_error(f"PDF generation failed: {e}")
            return None
    
    def run_full_audit(self):
        """Run all audit checks"""
        print("\n" + "="*80)
        print("VPS SECURITY AUDIT")
        print("="*80)
        
        print("\n[1/7] Running environment checks...")
        self.run_environment_checks()
        
        print("[2/7] Running database checks...")
        self.run_database_checks()
        
        print("[3/7] Running balance audit...")
        self.run_balance_audit()
        
        print("[4/7] Running bot audit...")
        self.run_bot_audit()
        
        print("[5/7] Running trade audit...")
        self.run_trade_audit()
        
        print("[6/7] Running error log analysis...")
        self.run_error_log_analysis()
        
        print("[7/7] Running system checks...")
        self.run_system_checks()
        
        self.generate_summary()
        
        return self.get_report_text()


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run security audit on VPS')
    parser.add_argument('--pdf', action='store_true', help='Generate PDF report (requires ReportLab)')
    parser.add_argument('--json', action='store_true', help='Output findings as JSON')
    parser.add_argument('--output', type=str, help='Output filename (without extension)')
    parser.add_argument('--no-color', action='store_true', help='Disable colored output')
    
    args = parser.parse_args()
    
    # Run audit
    audit = VPSSecurityAudit(generate_pdf=args.pdf)
    report = audit.run_full_audit()
    
    # Output report
    timestamp = audit.timestamp.strftime("%Y%m%d_%H%M%S")
    
    # Save text report
    text_filename = args.output or f"vps_audit_{timestamp}"
    with open(f"{text_filename}.txt", 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n[OK] Text report saved: {text_filename}.txt")
    
    # Save JSON if requested
    if args.json:
        json_filename = f"{text_filename}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            f.write(audit.get_findings_json())
        print(f"[OK] JSON findings saved: {json_filename}")
    
    # Generate PDF if requested and available
    if args.pdf and audit.pdf_available:
        pdf_filename = audit.generate_pdf_report()
        if pdf_filename:
            print(f"[OK] PDF report saved: {pdf_filename}")
    
    # Print summary to console
    print("\n" + "="*80)
    print("AUDIT COMPLETE")
    print("="*80)
    
    severity_counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
    for finding in audit.findings:
        severity = finding.get('severity', '').upper()
        if severity in severity_counts:
            severity_counts[severity] += 1
    
    print(f"\nFindings Summary:")
    print(f"  Critical: {severity_counts['CRITICAL']}")
    print(f"  High: {severity_counts['HIGH']}")
    print(f"  Medium: {severity_counts['MEDIUM']}")
    print(f"  Low: {severity_counts['LOW']}")
    print(f"  Total: {len(audit.findings)}")
    
    # Overall risk level
    if severity_counts['CRITICAL'] > 0:
        risk_level = "[CRITICAL]"
    elif severity_counts['HIGH'] > 0:
        risk_level = "[HIGH]"
    elif severity_counts['MEDIUM'] > 0:
        risk_level = "[MEDIUM]"
    else:
        risk_level = "[LOW]"
    
    print(f"\nOverall Risk Level: {risk_level}")
    
    if audit.findings:
        print("\nTop Recommendations:")
        high_priority = [f for f in audit.findings if f.get('severity') in ['CRITICAL', 'HIGH']]
        for i, finding in enumerate(high_priority[:3], 1):
            if finding.get('recommendation'):
                print(f"  {i}. {finding['recommendation']}")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()
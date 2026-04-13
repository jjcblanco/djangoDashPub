import os
import sys
import django
import io
import datetime
from decimal import Decimal
from django.utils import timezone

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from django.db import connection
from django.conf import settings
from dashboard.models import LiveBot, LiveTrade, TradeSignal, TradingPair

class SecurityAudit:
    """Comprehensive security audit for the trading system"""
    
    def __init__(self):
        self.report = []
        self.findings = []
        self.errors = []
        self.timestamp = datetime.datetime.now()
        
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
            self.report.append(f"   Recomendación: {recommendation}")
            
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
        if settings.DEBUG:
            self.add_finding(
                "Configuration", 
                "HIGH", 
                "DEBUG mode is enabled in production",
                "Set DEBUG=False in production environment"
            )
        else:
            self.add_info("DEBUG mode is disabled (good)")
            
        # Check SECRET_KEY
        secret_key = settings.SECRET_KEY
        if secret_key == 'django-insecure-' or len(secret_key) < 20:
            self.add_finding(
                "Configuration",
                "CRITICAL",
                "Weak or default SECRET_KEY detected",
                "Generate a strong random SECRET_KEY and store it securely"
            )
        else:
            self.add_info(f"SECRET_KEY appears to be strong ({len(secret_key)} chars)")
            
        # Check ALLOWED_HOSTS
        allowed_hosts = settings.ALLOWED_HOSTS
        if not allowed_hosts or len(allowed_hosts) == 0:
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
        db_config = settings.DATABASES['default']
        if db_config['ENGINE'] == 'django.db.backends.sqlite3':
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
            if 'your-' in binance_key.lower() or 'example' in binance_key.lower():
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
            from django.contrib.auth.models import User
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
            from dashboard.ccxttest1 import binance as exchange
            
            # Get real balance from Binance
            try:
                bal = exchange.fetch_balance()
                real_free = Decimal(str(bal['free'].get('USDT', 0)))
                real_used = Decimal(str(bal['used'].get('USDT', 0)))
                real_total = Decimal(str(bal['total'].get('USDT', 0)))
                
                self.add_info(f"Binance REAL USDT:")
                self.add_info(f"  Total: {real_total}")
                self.add_info(f"  Libre: {real_free}")
                self.add_info(f"  Usado (en órdenes): {real_used}")
                
            except Exception as e:
                self.add_error(f"Error connecting to Binance: {e}")
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
                self.add_info(f"  Capital en Trades Abiertos: {trading_val}")
                
            self.add_info(f"\nSuma Total Balances Locales: {sum_local_balances}")
            
            # Compare
            discrepancy = real_total - sum_local_balances
            self.add_info(f"Discrepancia (Real - Local): {discrepancy}")
            
            if discrepancy < 0:
                self.add_finding(
                    "Financial",
                    "HIGH",
                    "Balance discrepancy detected: bots think they have more money than available on Binance",
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
                self.add_info(f"Estrategia: {bot.strategy_type}")
                self.add_info(f"Estado: {bot.status} | Is_Live: {bot.is_live}")
                self.add_info(f"Balance Inicial: {bot.initial_balance} | Actual: {bot.current_balance}")
                self.add_info(f"Retorno: {bot.current_balance - bot.initial_balance}")
                self.add_info(f"PNL Total: {total_pnl} | Realizado: {realized_pnl}")
                self.add_info(f"Operaciones: {total_closed} (Ganadoras: {winning_trades}, Perdedoras: {losing_trades})")
                self.add_info(f"Win Rate: {win_rate:.2f}%")
                self.add_info(f"Operaciones Abiertas: {open_trades.count()}")
                
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
            recent_trades = LiveTrade.objects.all().order_by('-updated_at')[:10]
            self.add_info("\nÚltimos 10 trades:")
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
            # Check whale_debug.log
            log_path = os.path.join(os.path.dirname(__file__), 'whale_debug.log')
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                error_count = len(lines)
                self.add_info(f"whale_debug.log contains {error_count} error lines")
                
                # Look for critical errors
                critical_errors = [l for l in lines if 'Max retries exceeded' in l or 'failed' in l.lower()]
                if critical_errors:
                    self.add_finding(
                        "System Health",
                        "MEDIUM",
                        f"{len(critical_errors)} network/connection errors in logs",
                        "Check API connectivity and network configuration"
                    )
                    
                # Sample recent errors
                if lines:
                    self.add_info("Sample errors from log:")
                    for line in lines[-3:]:  # Last 3 errors
                        self.add_info(f"  {line.strip()[:100]}...")
            else:
                self.add_info("whale_debug.log not found")
                
        except Exception as e:
            self.add_error(f"Error log analysis failed: {e}")
            
    def generate_summary(self):
        """Generate executive summary"""
        self.add_section("EXECUTIVE SUMMARY")
        
        # Count findings by severity
        severity_counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        for finding in self.findings:
            severity_counts[finding['severity']] += 1
            
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
            high_priority = [f for f in self.findings if f['severity'] in ['CRITICAL', 'HIGH']]
            for i, finding in enumerate(high_priority[:3], 1):
                if finding['recommendation']:
                    self.add_info(f"{i}. {finding['recommendation']}")
                    
    def get_report_text(self):
        """Get full report as text"""
        return "\n".join(self.report)
        
    def get_findings(self):
        """Get all findings"""
        return self.findings
        
    def run_full_audit(self):
        """Run all audit checks"""
        self.run_environment_checks()
        self.run_database_checks()
        self.run_balance_audit()
        self.run_bot_audit()
        self.run_trade_audit()
        self.run_error_log_analysis()
        self.generate_summary()
        
        return self.get_report_text()


def main():
    """Main function to run security audit"""
    print("Starting comprehensive security audit...")
    
    audit = SecurityAudit()
    report = audit.run_full_audit()
    
    # Print report to console
    print(report)
    
    # Save report to file
    report_filename = f"security_audit_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_filename, 'w', encoding='utf-8') as f:
        f.write(report)
        
    print(f"\nReport saved to: {report_filename}")
    print(f"Total findings: {len(audit.findings)}")
    
    return audit


if __name__ == "__main__":
    main()
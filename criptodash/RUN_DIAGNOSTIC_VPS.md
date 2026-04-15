# Running Whale Diagnostic on VPS

This guide explains how to run the comprehensive whale tracking diagnostic on your VPS to identify wallet sync issues, verify API configurations, and test the new UI features.

## Prerequisites

1. **Access to VPS** via SSH
2. **Project directory**: `/var/www/clients/client2/web5/web/criptodash/`
3. **Virtual environment**: `/var/www/javierblanco.com.ar/web/venv/`
4. **Python 3.8+** installed

## Step 1: Copy Diagnostic Script to VPS

If you haven't already, copy the diagnostic script from your local machine to the VPS:

```bash
# From your local machine (adjust paths)
scp whale_diagnostic.py user@your-vps-ip:/var/www/clients/client2/web5/web/criptodash/
```

Or create it directly on the VPS:

```bash
cd /var/www/clients/client2/web5/web/criptodash/
nano whale_diagnostic.py
# Paste the content from your local whale_diagnostic.py
```

## Step 2: Run Comprehensive Diagnostic

Navigate to the project directory and activate the virtual environment:

```bash
cd /var/www/clients/client2/web5/web/criptodash/
source /var/www/javierblanco.com.ar/web/venv/bin/activate
```

Run the full diagnostic:

```bash
python whale_diagnostic.py --all
```

This will run all checks:
- Wallet sync status
- Blockchain analysis
- Problematic wallets
- Transaction activity
- API configurations
- Rate limit configurations
- Celery status
- UI endpoints

## Step 3: Analyze Specific Issues

### 3.1 Check Wallet Sync Status Only
```bash
python whale_diagnostic.py --status
```

### 3.2 Find Problematic Wallets
```bash
python whale_diagnostic.py --problematic
```

### 3.3 Check API Keys
```bash
python whale_diagnostic.py --api-check
```

### 3.4 Check Celery Status
```bash
python whale_diagnostic.py --celery-status
```

### 3.5 Reset Stuck Wallets
If wallets are stuck in SYNCING state (>30 minutes):
```bash
python whale_diagnostic.py --fix-stuck
```

## Step 4: Verify API Keys

Check if required API keys are set in environment variables:

```bash
# Check current environment variables
env | grep -E "(ETH|BASE|BINANCE|TELEGRAM)_API"

# Set missing keys (temporary for current shell)
export ETH_API_KEY="your_etherscan_api_key"
export BASE_API_KEY="your_basescan_api_key"
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"

# Make permanent by adding to Apache environment or .env file
# For Apache mod_wsgi, add to WSGIDaemonProcess directive
# For systemd, add to service file Environment directives
```

## Step 5: Check Celery Service

Verify Celery is running correctly:

```bash
# Check Celery systemd service status
sudo systemctl status celery

# Check Celery logs
sudo journalctl -u celery -f

# Check if Celery worker processes are running
ps aux | grep celery

# Restart Celery if needed
sudo systemctl restart celery
```

## Step 6: Test New UI Features

### 6.1 Verify UI Endpoints
```bash
python whale_diagnostic.py --ui-check
```

### 6.2 Manual Testing Checklist

1. **Access Whale Insights Dashboard**
   - Navigate to: `https://your-domain.com/dashboard/whale-insights/`
   - Verify all 5 tabs load: Overview, Wallets, Patterns, Discovery, Hunting

2. **Test Bulk Import**
   - Go to Wallets tab
   - Click "Bulk Import" button
   - Test with sample wallet addresses (one per line):
     ```
     0x742d35Cc6634C0532925a3b844Bc9e90F1b6f1d6
     5LpjZ1Dz1q8LqLqLqLqLqLqLqLqLqLqLqLqLqLqLqLq
     ```

3. **Test Advanced Hunting Filters**
   - Go to Hunting tab
   - Set filters (min score, blockchain, timeframe)
   - Click "Apply Filters"
   - Verify results update

4. **Test Discovery Panel**
   - Go to Discovery tab
   - Verify consensus signals are displayed
   - Check "AI-Powered Discovery" section

5. **Test Real-time Updates** (if WebSockets configured)
   - Open browser console
   - Check for WebSocket connection
   - Verify metrics update automatically

## Step 7: Configure WebSockets (Optional)

If you want real-time updates, set up Daphne ASGI server:

```bash
# Generate configuration files
cd /var/www/clients/client2/web5/web/criptodash/
python configure_websockets.py --apache --systemd \
  --project-path="/var/www/clients/client2/web5/web/criptodash" \
  --venv-path="/var/www/javierblanco.com.ar/web/venv" \
  --user="www-data" \
  --output-dir="."

# Copy systemd service
sudo cp daphne.service /etc/systemd/system/

# Enable Apache modules
sudo a2enmod proxy proxy_http proxy_wstunnel rewrite headers

# Add WebSocket proxy config to Apache
# Edit your Apache site config and add the minimal config from apache_websocket_minimal.conf

# Install Daphne
source /var/www/javierblanco.com.ar/web/venv/bin/activate
pip install daphne channels channels-redis

# Start Daphne
sudo systemctl enable --now daphne
sudo systemctl reload apache2
```

## Common Issues and Solutions

### Issue 1: "Django setup failed"
**Cause**: Wrong working directory or missing dependencies
**Solution**:
```bash
cd /var/www/clients/client2/web5/web/criptodash/
source /var/www/javierblanco.com.ar/web/venv/bin/activate
pip install -r requirements.txt  # Ensure all packages installed
```

### Issue 2: Celery "exit-code 217/USER"
**Cause**: Wrong user in systemd service file
**Solution**: Edit `/etc/systemd/system/celery.service`:
```ini
[Service]
User=www-data  # Change from 'tu_usuario' to 'www-data' or correct user
Group=www-data
```

### Issue 3: Wallets Not Syncing
**Causes**:
1. Missing API keys
2. Rate limiting
3. Network issues
4. Celery not processing tasks

**Debug steps**:
```bash
# Check Celery task queue
celery -A criptodash inspect active

# Manually trigger sync for a wallet
python manage.py shell
>>> from dashboard.tasks import sync_whale_wallet
>>> from dashboard.models import WhaleWallet
>>> wallet = WhaleWallet.objects.first()
>>> sync_whale_wallet.delay(wallet.id)
```

### Issue 4: No Transactions Showing
**Causes**:
1. API endpoints not returning data
2. Wallet addresses invalid
3. Blockchain not supported

**Debug**:
```bash
# Check recent transactions in database
python whale_diagnostic.py --transactions

# Test API connectivity
python manage.py shell
>>> from dashboard.utils.blockchain import get_transactions
>>> tx = get_transactions("ethereum", "0x742d35Cc6634C0532925a3b844Bc9e90F1b6f1d6", limit=5)
>>> print(f"Found {len(tx)} transactions")
```

## Next Steps After Diagnosis

1. **Fix identified issues** based on diagnostic output
2. **Monitor for 24 hours** after fixes
3. **Set up alerts** for future issues (Telegram notifications already configured)
4. **Consider scaling** if many wallets (adjust Celery concurrency, rate limits)

## Support

If diagnostics don't reveal the issue, collect this information:
```bash
# System info
python whale_diagnostic.py --all > diagnostic_report.txt
sudo systemctl status celery >> diagnostic_report.txt
sudo systemctl status daphne >> diagnostic_report.txt  # if installed
sudo tail -100 /var/log/apache2/error.log >> diagnostic_report.txt
```

Share `diagnostic_report.txt` for further assistance.
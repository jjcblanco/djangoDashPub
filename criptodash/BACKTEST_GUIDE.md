# Backtesting Quick Reference Guide

## Quick Start

### 1. Access Backtesting
```
URL: http://localhost:8000/dashboard/backtest/
```

### 2. Run a Test
1. Select trading pair (e.g., ETH/USDT)
2. Choose strategy (Signal-Based recommended)
3. Set date range
4. Click "Run Backtest"

### 3. Interpret Results

**Good Performance Indicators:**
- ✅ Total Return > 0%
- ✅ Win Rate > 50%
- ✅ Sharpe Ratio > 1.0
- ✅ Profit Factor > 1.5
- ✅ Max Drawdown < -20%

**Warning Signs:**
- ⚠️ Total Return < 0%
- ⚠️ Win Rate < 40%
- ⚠️ Sharpe Ratio < 0
- ⚠️ Profit Factor < 1.0
- ⚠️ Max Drawdown > -30%

## Command Line Testing

### Test from Django Shell
```bash
cd c:\Users\Javier\Desktop\programacion\djangoDashPub\criptodash
python manage.py shell < test_backtest.py
```

### Manual Test in Shell
```python
python manage.py shell

from dashboard.backtester import Backtester
from dashboard.models import TradingPair
from django.utils import timezone
from datetime import timedelta

# Get a trading pair
pair = TradingPair.objects.first()

# Set date range
end_date = timezone.now()
start_date = end_date - timedelta(days=30)

# Run backtest
backtester = Backtester(initial_balance=10000, commission=0.001)
results = backtester.run_backtest_from_signals(
    pair_symbol=pair.symbol,
    start_date=start_date,
    end_date=end_date
)

# Print results
print(f"Total Return: {results['total_return']:.2f}%")
print(f"Win Rate: {results['win_rate']:.2f}%")
```

## Key Metrics Explained

### Total Return
- **What**: Overall profit/loss percentage
- **Formula**: `(Final Balance - Initial Balance) / Initial Balance * 100`
- **Good**: > 5% per month

### Win Rate
- **What**: Percentage of profitable trades
- **Formula**: `Winning Trades / Total Trades * 100`
- **Good**: > 50%

### Sharpe Ratio
- **What**: Risk-adjusted return
- **Formula**: `(Mean Return / Std Dev of Returns) * √252`
- **Good**: > 1.0 (excellent: > 2.0)

### Max Drawdown
- **What**: Largest peak-to-trough decline
- **Formula**: `(Trough Value - Peak Value) / Peak Value * 100`
- **Good**: < -20% (acceptable: < -30%)

### Profit Factor
- **What**: Ratio of gross profits to gross losses
- **Formula**: `Total Winning $ / Total Losing $`
- **Good**: > 1.5 (excellent: > 2.0)

## Common Issues & Solutions

### Issue: "No signals found"
**Solution:**
1. Check if signals exist for the pair:
   ```python
   from dashboard.models import TradeSignal, TradingPair
   pair = TradingPair.objects.get(symbol='ETH/USDT')
   print(TradeSignal.objects.filter(pair=pair).count())
   ```
2. Run the bot to generate signals:
   ```python
   from dashboard import ccxttest1
   ccxttest1.run_bot('ETH/USDT', '2025-11-26 00:00:00', '1m')
   ```

### Issue: "Trading pair not found"
**Solution:**
1. Create the pair:
   ```python
   from dashboard.models import TradingPair, Exchange
   exchange, _ = Exchange.objects.get_or_create(name='Binance')
   pair, _ = TradingPair.objects.get_or_create(
       symbol='ETH/USDT',
       exchange=exchange,
       defaults={'base_asset': 'ETH', 'quote_asset': 'USDT'}
   )
   ```

### Issue: Poor backtest performance
**Solutions:**
1. Adjust commission rate (might be too high)
2. Test different time periods
3. Check signal quality
4. Try different strategy parameters

## Strategy Comparison

### Signal-Based Strategy
- **Pros:**
  - Uses real historical signals
  - Tests actual bot performance
  - No indicator calculation needed
- **Cons:**
  - Requires existing signals
  - Limited to historical data
- **Best for:** Evaluating past performance

### Supertrend Strategy
- **Pros:**
  - Generates fresh signals
  - Works without existing signals
  - Tests indicator effectiveness
- **Cons:**
  - May not match bot signals
  - Requires OHLCV data
- **Best for:** Strategy development

## Performance Optimization Tips

1. **Commission Rates:**
   - Binance: 0.1% (0.001)
   - Binance with BNB: 0.075% (0.00075)
   - Maker fees: Often lower

2. **Initial Balance:**
   - Start with realistic amounts
   - Test with different sizes
   - Consider minimum trade sizes

3. **Date Ranges:**
   - Test multiple periods
   - Include bull and bear markets
   - Avoid cherry-picking dates

4. **Signal Quality:**
   - More signals ≠ better performance
   - Quality > Quantity
   - Check signal strength values

## Files Reference

### Core Files
- **Backtester**: `dashboard/backtester.py`
- **View**: `dashboard/views.py` (line 965+)
- **URL**: `dashboard/urls.py` (line 17)

### Templates
- **Form**: `dashboard/templates/dashboard/backtest.html`
- **Results**: `dashboard/templates/dashboard/backtest_results.html`

### Models
- **TradeSignal**: Stores buy/sell signals
- **BacktestResult**: Saves backtest results
- **TradingPair**: Trading pair info
- **OHLCVData**: Price data

## API Usage (Programmatic)

```python
from dashboard.backtester import Backtester, SignalBasedStrategy
from django.utils import timezone
from datetime import timedelta

# Setup
backtester = Backtester(
    initial_balance=10000,
    commission=0.001
)

# Run backtest
results = backtester.run_backtest_from_signals(
    pair_symbol='ETH/USDT',
    start_date=timezone.now() - timedelta(days=30),
    end_date=timezone.now()
)

# Access results
print(f"Return: {results['total_return']:.2f}%")
print(f"Trades: {results['total_trades']}")
print(f"Win Rate: {results['win_rate']:.2f}%")

# Generate charts
equity_chart = backtester.generate_equity_chart(results)
trades_chart = backtester.generate_trades_chart(results)
```

## Keyboard Shortcuts (Web Interface)

- **Ctrl + Enter**: Submit form (when focused)
- **Tab**: Navigate between fields
- **Esc**: Close modals/alerts

## Best Practices

1. ✅ Always test with realistic commission rates
2. ✅ Use multiple time periods for validation
3. ✅ Compare results across different pairs
4. ✅ Save and document your backtests
5. ✅ Consider transaction costs and slippage
6. ✅ Don't over-optimize (avoid curve fitting)
7. ✅ Test in different market conditions
8. ✅ Validate with out-of-sample data

## Support & Troubleshooting

### Check Logs
```bash
# Django logs
tail -f logs/django.log

# Console output
python manage.py runserver --verbosity 3
```

### Debug Mode
```python
# In views.py, add:
import traceback
try:
    # backtest code
except Exception as e:
    traceback.print_exc()
```

### Database Queries
```python
# Check signal distribution
from dashboard.models import TradeSignal
from django.db.models import Count

TradeSignal.objects.values('signal_type').annotate(count=Count('id'))
```

## Next Steps

1. **Generate Signals**: Run your bot to populate signals
2. **Run First Backtest**: Test with default parameters
3. **Analyze Results**: Review metrics and charts
4. **Optimize**: Adjust parameters and re-test
5. **Compare**: Test multiple strategies
6. **Deploy**: Use insights for live trading

---

**Remember**: Past performance doesn't guarantee future results. Always validate strategies with out-of-sample data before live trading!

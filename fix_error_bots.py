"""
Fix ERROR bots by updating their parameters to proper defaults and resetting status.
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.criptodash.settings')
try:
    django.setup()
except Exception as e:
    print(f"Django setup error: {e}")
    # Try alternative path
    sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'criptodash'))
    django.setup()

from dashboard.models import LiveBot

# Default parameters for DayTradingStrategy from backtester.py
DEFAULT_DAYTRADING_PARAMS = {
    'ema_fast': 9,
    'ema_med': 21,
    'ema_slow': 50,
    'ema_trend': 200,
    'rsi_period': 14,
    'rsi_buy': 55,
    'rsi_sell': 45,
    'atr_sl': 1.5,
    'atr_tp': 3.0,
    'use_candles': True,
    'min_strength': 4,
    'min_adx': 20,
    'strategy_mode': 'balanced',
    'use_bollinger_filter': True,
    'cooldown_bars': 3,
    'risk_per_trade_pct': 2.0
}

def fix_error_bots():
    """Fix all bots in ERROR state."""
    error_bots = LiveBot.objects.filter(status='ERROR')
    print(f"Found {error_bots.count()} bots in ERROR state")
    
    fixed_count = 0
    for bot in error_bots:
        print(f"\n--- Fixing bot {bot.id}: {bot.name} ({bot.pair.symbol}) ---")
        print(f"Current parameters: {bot.parameters}")
        
        # Update parameters with defaults, preserving any existing custom values
        current_params = bot.parameters.copy() if bot.parameters else {}
        updated_params = DEFAULT_DAYTRADING_PARAMS.copy()
        
        # Merge: keep existing values but ensure they have correct types
        for key, value in current_params.items():
            if key in updated_params:
                # Convert string numbers to int/float
                if isinstance(value, str):
                    try:
                        if '.' in value:
                            updated_params[key] = float(value)
                        else:
                            updated_params[key] = int(value)
                    except (ValueError, TypeError):
                        updated_params[key] = value  # keep as is if conversion fails
                else:
                    updated_params[key] = value
            else:
                # Keep custom parameters not in defaults
                updated_params[key] = value
        
        # Ensure min_strength and min_adx are integers (common in these bots)
        if 'min_strength' in updated_params and isinstance(updated_params['min_strength'], str):
            try:
                updated_params['min_strength'] = int(updated_params['min_strength'])
            except:
                updated_params['min_strength'] = 4
        
        if 'min_adx' in updated_params and isinstance(updated_params['min_adx'], str):
            try:
                updated_params['min_adx'] = int(updated_params['min_adx'])
            except:
                updated_params['min_adx'] = 20
        
        print(f"Updated parameters: {updated_params}")
        
        # Update bot
        bot.parameters = updated_params
        bot.status = 'PAUSED'  # Set to PAUSED instead of ERROR, so they don't auto-run
        bot.last_error = None  # Clear error
        bot.save()
        
        print(f"Bot {bot.id} fixed: status -> PAUSED, error cleared")
        fixed_count += 1
    
    print(f"\n✅ Fixed {fixed_count} bots")
    
    # Also check for any other problematic bots with minimal parameters
    all_bots = LiveBot.objects.all()
    problematic = []
    for bot in all_bots:
        if bot.strategy_type == 'DAYTRADING' and bot.parameters:
            # Check if parameters are too minimal
            if len(bot.parameters) < 5:
                problematic.append(bot)
    
    if problematic:
        print(f"\n⚠️  Found {len(problematic)} bots with minimal parameters (may cause issues):")
        for bot in problematic:
            print(f"  Bot {bot.id}: {bot.name} - {len(bot.parameters)} params: {bot.parameters}")

if __name__ == '__main__':
    fix_error_bots()
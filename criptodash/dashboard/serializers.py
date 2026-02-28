from rest_framework import serializers
from .models import LiveBot, LiveTrade, TradingPair
from decimal import Decimal

class TradingPairSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradingPair
        fields = ['id', 'symbol', 'base_asset', 'quote_asset']

class LiveBotSerializer(serializers.ModelSerializer):
    pair_symbol = serializers.CharField(source='pair.symbol', read_only=True)
    total_pnl = serializers.SerializerMethodField()
    profit_pct = serializers.SerializerMethodField()
    strategy_display = serializers.CharField(source='get_strategy_type_display', read_only=True)

    class Meta:
        model = LiveBot
        fields = [
            'id', 'name', 'pair', 'pair_symbol', 'strategy_type', 'strategy_display',
            'status', 'initial_balance', 'current_balance', 'is_live', 
            'last_error', 'total_pnl', 'profit_pct', 'created_at'
        ]

    def get_total_pnl(self, obj):
        trades = obj.trades.all()
        return sum(t.pnl for t in trades)

    def get_profit_pct(self, obj):
        total_pnl = self.get_total_pnl(obj)
        if obj.initial_balance > 0:
            return (total_pnl / obj.initial_balance) * 100
        return 0

class LiveTradeSerializer(serializers.ModelSerializer):
    bot_name = serializers.CharField(source='bot.name', read_only=True)
    pair_symbol = serializers.CharField(source='bot.pair.symbol', read_only=True)
    current_price = serializers.SerializerMethodField()
    target_price = serializers.SerializerMethodField()

    class Meta:
        model = LiveTrade
        fields = [
            'id', 'bot', 'bot_name', 'pair_symbol', 'side', 'entry_price', 
            'exit_price', 'amount', 'commission', 'pnl', 'status', 
            'entry_time', 'exit_time', 'order_id', 'current_price', 'target_price'
        ]

    def get_current_price(self, obj):
        # Este valor se inyectará en el context de la view si es necesario
        return getattr(obj, 'current_price', None)

    def get_target_price(self, obj):
        # Este valor se inyectará en el context de la view si es necesario
        return getattr(obj, 'target_price', None)

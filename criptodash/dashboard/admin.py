from django.contrib import admin
from .models import Exchange, TradingPair, Pair, OHLCVData, TradeSignal, BacktestResult


@admin.register(Exchange)
class ExchangeAdmin(admin.ModelAdmin):
	list_display = ('name', 'is_active')


@admin.register(TradingPair)
class TradingPairAdmin(admin.ModelAdmin):
	list_display = ('symbol', 'exchange', 'is_active')
	search_fields = ('symbol',)


@admin.register(Pair)
class PairAdmin(admin.ModelAdmin):
	list_display = ('symbol', 'pair_type', 'exchange', 'created_at')
	search_fields = ('symbol',)


@admin.register(OHLCVData)
class OHLCVDataAdmin(admin.ModelAdmin):
	list_display = ('pair', 'timestamp', 'close')
	list_filter = ('timeframe',)


@admin.register(TradeSignal)
class TradeSignalAdmin(admin.ModelAdmin):
	list_display = ('pair', 'pair_ref', 'timestamp', 'signal_type', 'price')
	list_filter = ('signal_type',)
	search_fields = ('pair__symbol', 'pair_ref__symbol')


@admin.register(BacktestResult)
class BacktestResultAdmin(admin.ModelAdmin):
	list_display = ('name', 'pair', 'strategy_name', 'total_return', 'created_at')

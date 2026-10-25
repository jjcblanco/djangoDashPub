from django.contrib import admin
from .models import (
    Exchange, TradingPair, Pair, OHLCVData, TradeSignal, BacktestResult,
    LiveBot, LiveTrade, CapitalFunding, GlobalSettings, DailyMetric,
    WhaleWallet, WhaleTransaction, PatternInsight, ShadowTrade,
    WhaleHuntTarget, ConsensusSignal, WhalePattern, ExchangeFlow,
    ScalpingBot, ScalpingTrade, ScalpAlert, PairScanResult,
)


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


@admin.register(LiveBot)
class LiveBotAdmin(admin.ModelAdmin):
    list_display = ('name', 'pair', 'strategy_type', 'status', 'is_live', 'current_balance')
    list_filter = ('status', 'is_live', 'strategy_type')


@admin.register(LiveTrade)
class LiveTradeAdmin(admin.ModelAdmin):
    list_display = ('bot', 'side', 'entry_price', 'exit_price', 'status', 'pnl')
    list_filter = ('status', 'side')


@admin.register(CapitalFunding)
class CapitalFundingAdmin(admin.ModelAdmin):
    list_display = ('amount', 'funding_date', 'description')
    search_fields = ('description',)


@admin.register(GlobalSettings)
class GlobalSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'kill_switch_active', 'max_drawdown_pct',
                    'notifications_enabled', 'auto_scalp_enabled', 'updated_at')


@admin.register(DailyMetric)
class DailyMetricAdmin(admin.ModelAdmin):
    list_display = ('date',)
    ordering = ('-date',)


@admin.register(WhaleWallet)
class WhaleWalletAdmin(admin.ModelAdmin):
    list_display = ('address', 'blockchain', 'sync_status', 'is_active', 'last_sync')
    list_filter = ('blockchain', 'sync_status', 'is_active')
    search_fields = ('address', 'target_pairs')


@admin.register(WhaleTransaction)
class WhaleTransactionAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'tx_hash', 'tx_type', 'timestamp')
    list_filter = ('tx_type', 'wallet__blockchain')
    search_fields = ('tx_hash', 'wallet__address')
    ordering = ('-timestamp',)


@admin.register(PatternInsight)
class PatternInsightAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'pattern_type', 'detected_at')
    list_filter = ('pattern_type',)
    ordering = ('-detected_at',)


@admin.register(ShadowTrade)
class ShadowTradeAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'token_symbol', 'entry_price', 'exit_price',
                    'status', 'pnl_percent', 'created_at')
    list_filter = ('status',)
    search_fields = ('token_symbol', 'wallet__address')


@admin.register(WhaleHuntTarget)
class WhaleHuntTargetAdmin(admin.ModelAdmin):
    list_display = ('token_symbol', 'blockchain', 'is_active', 'created_at')
    list_filter = ('blockchain', 'is_active')
    search_fields = ('token_symbol',)


@admin.register(ConsensusSignal)
class ConsensusSignalAdmin(admin.ModelAdmin):
    list_display = ('token_symbol', 'blockchain', 'status', 'detected_at')
    list_filter = ('blockchain', 'status')
    ordering = ('-detected_at',)


@admin.register(WhalePattern)
class WhalePatternAdmin(admin.ModelAdmin):
    list_display = ('pattern_name', 'timeframe', 'sample_size', 'win_rate', 'is_active')
    list_filter = ('is_active', 'timeframe')


@admin.register(ScalpingBot)
class ScalpingBotAdmin(admin.ModelAdmin):
    list_display = ('name', 'pair', 'strategy_type', 'timeframe', 'status', 'is_live', 'total_pnl_usdt')
    list_filter = ('status', 'is_live', 'strategy_type', 'timeframe')


@admin.register(ScalpingTrade)
class ScalpingTradeAdmin(admin.ModelAdmin):
    list_display = ('bot', 'side', 'entry_price', 'exit_price', 'status', 'pnl_usdt', 'entry_time')
    list_filter = ('status', 'side')
    ordering = ('-entry_time',)


@admin.register(ScalpAlert)
class ScalpAlertAdmin(admin.ModelAdmin):
    list_display = ('pair', 'timeframe', 'strategy', 'signal_type', 'price_at_alert')
    list_filter = ('strategy', 'signal_type', 'timeframe')


@admin.register(ExchangeFlow)
class ExchangeFlowAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'direction', 'exchange', 'token_symbol', 'usd_value', 'detected_at')
    list_filter = ('direction', 'exchange', 'blockchain')
    search_fields = ('wallet__address', 'tx_hash', 'token_symbol')
    ordering = ('-detected_at',)


@admin.register(PairScanResult)
class PairScanResultAdmin(admin.ModelAdmin):
    list_display = ('pair', 'timeframe', 'total_score', 'recommended_strategy', 'scanned_at')
    list_filter = ('timeframe', 'recommended_strategy')
    ordering = ('-scanned_at',)

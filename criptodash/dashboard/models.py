from django.db import models

class Exchange(models.Model):
    name = models.CharField(max_length=50)
    api_base = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name

class TradingPair(models.Model):
    symbol = models.CharField(max_length=20)  # ETH/USDT
    base_asset = models.CharField(max_length=10)  # ETH
    quote_asset = models.CharField(max_length=10)  # USDT
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['symbol', 'exchange']
    
    def __str__(self):
        return f"{self.symbol} ({self.exchange.name})"

class OHLCVData(models.Model):
    pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    open = models.DecimalField(max_digits=20, decimal_places=8)
    high = models.DecimalField(max_digits=20, decimal_places=8)
    low = models.DecimalField(max_digits=20, decimal_places=8)
    close = models.DecimalField(max_digits=20, decimal_places=8)
    volume = models.DecimalField(max_digits=20, decimal_places=8)
    timeframe = models.CharField(max_length=10)  # 1m, 5m, 1h, etc.
    
    # Indicadores técnicos (opcional, puedes calcular on-demand)
    rsi = models.FloatField(null=True, blank=True)
    macd = models.FloatField(null=True, blank=True)
    bollinger_upper = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    bollinger_lower = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['pair', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]
        unique_together = ['pair', 'timestamp', 'timeframe']
    
    def __str__(self):
        return f"{self.pair.symbol} - {self.timestamp}"

class TradeSignal(models.Model):
    SIGNAL_TYPES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
        ('HOLD', 'Hold'),
    ]
    
    pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE)
    # New nullable FK to the canonical Pair model (allows gradual migration/backfill)
    pair_ref = models.ForeignKey('Pair', null=True, blank=True, on_delete=models.SET_NULL, related_name='trade_signals')
    timestamp = models.DateTimeField()
    signal_type = models.CharField(max_length=4, choices=SIGNAL_TYPES)
    price = models.DecimalField(max_digits=20, decimal_places=8)
    indicator = models.CharField(max_length=50, blank=True, null=True)  # Ichimoku, RSI, etc.
    strength = models.FloatField(default=1.0)  # 0-1 scale
    # Optional JSON field to store computed indicators or metadata
    indicators = models.JSONField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['pair', 'timestamp', 'signal_type']),
            models.Index(fields=['pair_ref', 'timestamp', 'signal_type']),
        ]

class BacktestResult(models.Model):

    name = models.CharField(max_length=100)
    pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    strategy_name = models.CharField(max_length=50)
    parameters = models.JSONField()  # Parámetros usados

    # Resultados
    total_return = models.FloatField()
    sharpe_ratio = models.FloatField(null=True, blank=True)
    max_drawdown = models.FloatField(null=True, blank=True)
    win_rate = models.FloatField(null=True, blank=True)
    profit_factor = models.FloatField(null=True, blank=True)
    total_trades = models.IntegerField()
    avg_trade = models.FloatField(null=True, blank=True)
    best_trade = models.FloatField(null=True, blank=True)
    worst_trade = models.FloatField(null=True, blank=True)
    total_fees = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.strategy_name} - {self.total_return:.2f}%"

class Pair(models.Model):
    SYMBOL_CHOICES = (
        # opcional: mantener o no
    )
    symbol = models.CharField(max_length=50, unique=True)  # 'ETH/USDT'
    base_asset = models.CharField(max_length=20, blank=True, null=True)
    quote_asset = models.CharField(max_length=20, blank=True, null=True)
    pair_type = models.CharField(max_length=20, default='spot')  # 'spot', 'futures', 'perp', ...
    exchange = models.CharField(max_length=50, blank=True, null=True)
    tick_size = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    min_notional = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['symbol']),
            models.Index(fields=['pair_type', 'symbol']),
        ]

    def __str__(self):
        return self.symbol


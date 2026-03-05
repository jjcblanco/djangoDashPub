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
    indicator = models.CharField(max_length=200, blank=True, null=True)  # Ichimoku, RSI, etc.
    strength = models.FloatField(default=1.0)  # 0-1 scale
    # Optional JSON field to store computed indicators or metadata
    indicators = models.JSONField(null=True, blank=True)
    timeframe = models.CharField(max_length=10, default='1h') # 1m, 5m, 15m, 1h, etc.
    
    class Meta:
        indexes = [
            models.Index(fields=['pair', 'timestamp', 'signal_type', 'timeframe']),
            models.Index(fields=['pair_ref', 'timestamp', 'signal_type', 'timeframe']),
        ]

class BacktestResult(models.Model):

    name = models.CharField(max_length=100)
    pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    strategy_name = models.CharField(max_length=50)
    timeframe = models.CharField(max_length=10, default='1h')
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

class LiveBot(models.Model):
    STATUS_CHOICES = [
        ('RUNNING', 'Running'),
        ('PAUSED', 'Paused'),
        ('CLOSE_ONLY', 'Close Only'),
        ('STOPPED', 'Stopped'),
        ('ERROR', 'Error'),
    ]
    
    STRATEGY_CHOICES = [
        ('GRID', 'Grid Trading'),
        ('DAYTRADING', 'Day Trading'),
    ]

    name = models.CharField(max_length=100)
    pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE)
    strategy_type = models.CharField(max_length=20, choices=STRATEGY_CHOICES)
    parameters = models.JSONField(help_text="Configuración técnica de la estrategia")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='STOPPED')
    initial_balance = models.DecimalField(max_digits=20, decimal_places=8)
    current_balance = models.DecimalField(max_digits=20, decimal_places=8)
    is_live = models.BooleanField(default=False, help_text="Si es True, ejecuta órdenes reales en el exchange")
    last_error = models.TextField(null=True, blank=True, help_text="Último mensaje de error técnico")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.pair.symbol} - {self.strategy_type})"

class LiveTrade(models.Model):
    SIDE_CHOICES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
    ]
    
    STATUS_CHOICES = [
        ('WAITING', 'Waiting (Limit Buy)'),
        ('OPEN', 'Open (Position)'),
        ('CLOSED', 'Closed'),
        ('CANCELED', 'Canceled'),
    ]

    bot = models.ForeignKey(LiveBot, on_delete=models.CASCADE, related_name='trades')
    side = models.CharField(max_length=4, choices=SIDE_CHOICES)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    exit_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    commission = models.DecimalField(max_digits=20, decimal_places=8, default=0, help_text="Comisión total pagada (entrada + salida)")
    pnl = models.DecimalField(max_digits=20, decimal_places=8, default=0, help_text="Beneficio NETO (después de comisiones)")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OPEN')
    entry_time = models.DateTimeField(auto_now_add=True)
    exit_time = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    order_id = models.CharField(max_length=100, blank=True, null=True, help_text="ID de orden de entrada (Buy)")
    exit_order_id = models.CharField(max_length=100, blank=True, null=True, help_text="ID de orden de salida (Sell/TP)")

    def __str__(self):
        return f"{self.side} {self.amount} {self.bot.pair.symbol} at {self.entry_price}"

class CapitalFunding(models.Model):
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    funding_date = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=200, blank=True, null=True, help_text="Ej: Transferencia desde Binance Earn")
    
    def __str__(self):
        return f"{self.amount} USDT en {self.funding_date}"

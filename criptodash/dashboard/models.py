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
        ('CLOSED_EMERGENCY', 'Closed by Emergency'),
    ]

    bot = models.ForeignKey(LiveBot, on_delete=models.CASCADE, related_name='trades')
    side = models.CharField(max_length=4, choices=SIDE_CHOICES)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    exit_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    commission = models.DecimalField(max_digits=20, decimal_places=8, default=0, help_text="Comisión total pagada (entrada + salida)")
    pnl = models.DecimalField(max_digits=20, decimal_places=8, default=0, help_text="Beneficio NETO (después de comisiones)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
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

class GlobalSettings(models.Model):
    max_drawdown_pct = models.DecimalField(max_digits=5, decimal_places=2, default=10.00, help_text="Porcentaje de pérdida máxima global antes de activar el Kill-Switch")
    kill_switch_active = models.BooleanField(default=False, help_text="Si es True, ningún bot operará y todas las posiciones se cerrarán.")
    
    # Telegram settings
    telegram_token = models.CharField(max_length=200, blank=True, null=True, help_text="Token del Bot de Telegram")
    telegram_chat_id = models.CharField(max_length=100, blank=True, null=True, help_text="ID del Chat de Telegram")
    notifications_enabled = models.BooleanField(default=False, help_text="Activar/Desactivar notificaciones por Telegram")
    
    updated_at = models.DateTimeField(auto_now=True)
    
    # Auto-Pilot Scalping
    auto_scalp_enabled = models.BooleanField(default=False, help_text="Habilita la creación y ejecución automática de bots SIMULADOS de scalping.")
    auto_scalp_min_conf = models.DecimalField(max_digits=5, decimal_places=2, default=75.00, help_text="Porcentaje de confianza mínima requerida (>X) para detonar un nuevo bot.")
    
    class Meta:
        verbose_name_plural = "Global Settings"
        
    def __str__(self):
        return f"Configuración Global (Kill-Switch: {self.kill_switch_active})"

class DailyMetric(models.Model):
    date = models.DateField(unique=True)
    total_balance = models.DecimalField(max_digits=20, decimal_places=8)
    total_pnl = models.DecimalField(max_digits=20, decimal_places=8)
    total_invested = models.DecimalField(max_digits=20, decimal_places=8)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Daily Metrics"
        ordering = ['-date']
        
    def __str__(self):
        return f"Metrics for {self.date} (Balance: {self.total_balance})"

class WhaleWallet(models.Model):
    CATEGORY_CHOICES = [
        ('DCA', 'Acumulación DCA'),
        ('SNIPER', 'Sniper / Early Buyer'),
        ('SMART_MONEY', 'Smart Money'),
        ('INSIDER', 'Insider / Dev'),
        ('OBSERVATION', 'En Observación'),
    ]

    FILTER_CHOICES = [
        ('OPEN', 'Todo (Pumps & Stables)'),
        ('STRICT', 'Solo Estables (Whitelist)'),
    ]

    BLOCKCHAIN_CHOICES = [
        ('solana', 'Solana'),
        ('ethereum', 'Ethereum'),
        ('base', 'Base'),
        ('hyperliquid', 'Hyperliquid'),
    ]

    address = models.CharField(max_length=255)
    name = models.CharField(max_length=100, blank=True, null=True)
    blockchain = models.CharField(max_length=50, choices=BLOCKCHAIN_CHOICES, default='solana')
    wallet_category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='OBSERVATION')
    filter_mode = models.CharField(max_length=10, choices=FILTER_CHOICES, default='OPEN')
    target_token = models.CharField(max_length=100, blank=True, null=True, help_text="Token principal que opera (ej: JUP, PEPE)")
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    target_pairs = models.CharField(
        max_length=500, blank=True, null=True,
        help_text="Tokens/pares en los que esta ballena opera. Separados por comas. Ej: SOL,WIF,PEPE"
    )
    sync_status = models.CharField(max_length=20, default='IDLE', help_text="Estado de la sincronización en background")
    last_sync = models.DateTimeField(null=True, blank=True)
    top_tokens = models.JSONField(default=dict, blank=True)  # {'SOL': 10, 'BONK': 5}
    trading_dna = models.JSONField(default=dict, blank=True)  # {'avg_holding': 4.5, 'rsi_pref': [30,45]}
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['address', 'blockchain']]

    def __str__(self):
        return f"{self.name or self.address[:8]} ({self.blockchain})"

    @property
    def target_pairs_list(self):
        """Devuelve una lista limpia de los pares/tokens objetivo."""
        if not self.target_pairs:
            return []
        return [p.strip().upper() for p in self.target_pairs.split(',') if p.strip()]

class WhaleTransaction(models.Model):
    wallet = models.ForeignKey(WhaleWallet, on_delete=models.CASCADE, related_name='transactions')
    tx_hash = models.CharField(max_length=255, unique=True)
    timestamp = models.DateTimeField()
    tx_type = models.CharField(max_length=50) # SWAP, TRANSFER, MINT
    from_asset = models.CharField(max_length=50, blank=True, null=True)
    to_asset = models.CharField(max_length=50, blank=True, null=True)
    amount_in = models.DecimalField(max_digits=30, decimal_places=10, null=True, blank=True)
    amount_out = models.DecimalField(max_digits=30, decimal_places=10, null=True, blank=True)
    raw_data = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.tx_type} {self.wallet.name or self.wallet.address[:8]}"

class PatternInsight(models.Model):
    wallet = models.ForeignKey(WhaleWallet, on_delete=models.CASCADE, related_name='insights')
    pattern_type = models.CharField(max_length=100) # ACCUMULATION, DISTRIBUTION, DCA, etc.
    confidence = models.FloatField() # 0 to 1
    description = models.TextField()
    detected_at = models.DateTimeField(auto_now_add=True)
    meta_data = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.pattern_type} for {self.wallet.name or self.wallet.address[:8]}"

class ShadowTrade(models.Model):
    STATUS_CHOICES = [
        ('OPEN', 'Abierta'),
        ('CLOSED', 'Cerrada'),
    ]

    wallet = models.ForeignKey(WhaleWallet, on_delete=models.CASCADE, related_name='shadow_trades')
    token_symbol = models.CharField(max_length=50)
    token_mint = models.CharField(max_length=255, blank=True, null=True)
    entry_price = models.DecimalField(max_digits=30, decimal_places=10)
    exit_price = models.DecimalField(max_digits=30, decimal_places=10, null=True, blank=True)
    amount = models.DecimalField(max_digits=30, decimal_places=10, help_text="Cantidad simulada en el token")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OPEN')
    pnl_percent = models.FloatField(default=0.0)
    market_context = models.JSONField(null=True, blank=True) # RSI, MACD at entry
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Shadow {self.token_symbol} - {self.wallet.name or self.wallet.address[:8]}"


class WhaleHuntTarget(models.Model):
    """
    Contrato de token a escanear automáticamente para descubrir ballenas.
    Administrable desde el panel visual del dashboard.
    """
    BLOCKCHAIN_CHOICES = [
        ('solana', 'Solana'),
        ('ethereum', 'Ethereum'),
        ('base', 'Base'),
        ('hyperliquid', 'Hyperliquid'),
    ]

    blockchain = models.CharField(max_length=50, choices=BLOCKCHAIN_CHOICES, default='ethereum')
    token_symbol = models.CharField(max_length=20, help_text="Símbolo del token. Ej: WIF, PEPE, BONK")
    contract_address = models.CharField(max_length=255, help_text="Dirección del contrato del token")
    min_volume_usd = models.FloatField(default=3000, help_text="Volumen mínimo en USD para considerar como ballena")
    is_active = models.BooleanField(default=True, help_text="Desactivar para pausar sin borrar")
    notes = models.CharField(max_length=200, blank=True, null=True, help_text="Notas opcionales")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['contract_address', 'blockchain']]
        ordering = ['blockchain', 'token_symbol']
        verbose_name = "Whale Hunt Target"
        verbose_name_plural = "Whale Hunt Targets"

    def __str__(self):
        return f"${self.token_symbol} ({self.blockchain}) — {self.contract_address[:12]}..."


class ConsensusSignal(models.Model):
    """
    Registra un evento de consenso: 3+ ballenas comprando el mismo token en un período corto.
    Cada señal puede derivar en una alerta de Telegram y una sugerencia de acción para los bots.
    """
    STATUS_CHOICES = [
        ('ACTIVE', 'Activa'),
        ('EXPIRED', 'Expirada'),
        ('BOT_CREATED', 'Bot Creado'),
    ]

    token_symbol = models.CharField(max_length=50)
    blockchain = models.CharField(max_length=50, default='solana')
    whale_count = models.IntegerField(default=0, help_text="Número de ballenas distintas que compraron")
    whale_addresses = models.JSONField(default=list, help_text="Lista de wallets que dispararon la señal")
    confidence = models.FloatField(default=0.0, help_text="Confianza calculada entre 0 y 1")
    entry_price = models.DecimalField(max_digits=30, decimal_places=10, null=True, blank=True)
    current_price = models.DecimalField(max_digits=30, decimal_places=10, null=True, blank=True)
    price_change_pct = models.FloatField(default=0.0, help_text="Cambio de precio desde la señal")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    alert_sent = models.BooleanField(default=False)
    detected_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-detected_at']
        verbose_name = "Consensus Signal"
        verbose_name_plural = "Consensus Signals"

    def __str__(self):
        return f"🔥 Consenso ${self.token_symbol} — {self.whale_count} ballenas @ {self.detected_at.strftime('%d/%m %H:%M')}"

    def is_active(self):
        from django.utils import timezone
        return self.status == 'ACTIVE' and (self.expires_at is None or self.expires_at > timezone.now())


class WhalePattern(models.Model):
    """
    Patrones aprendidos de trades exitosos de ballenas.
    """
    pattern_name = models.CharField(max_length=100)
    conditions = models.JSONField(
        help_text="Condiciones de indicadores ej: {'rsi_14__lt': 40, 'volume_ratio__gt': 1.5}"
    )
    timeframe = models.CharField(max_length=10, default='4h', help_text="Timeframe del contexto (1h, 4h, 1d)")
    sample_size = models.IntegerField(default=0, help_text="Número de trades que cumplen este patrón")
    win_rate = models.FloatField(default=0.0, help_text="Tasa de aciertos (0-1)")
    avg_pnl = models.FloatField(default=0.0, help_text="PnL promedio en %")
    total_trades = models.IntegerField(default=0, help_text="Total trades analizados para este patrón")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, help_text="Si el patrón está activo para generar señales")

    class Meta:
        ordering = ['-win_rate', '-sample_size']
        verbose_name = "Whale Pattern"
        verbose_name_plural = "Whale Patterns"

    def __str__(self):
        return f"{self.pattern_name} (Win: {self.win_rate:.1%}, N={self.sample_size})"

    def match_context(self, context):
        """
        Verifica si un contexto de mercado cumple con las condiciones del patrón.
        context: dict con indicadores (rsi_14, volume_ratio, etc.)
        """
        if not context:
            return False
        
        for key, value in self.conditions.items():
            # key puede ser 'rsi_14__lt', 'volume_ratio__gt', 'in_uptrend'
            if '__' in key:
                field, op = key.rsplit('__', 1)
                if field not in context or context[field] is None:
                    return False
                if op == 'lt':
                    if not (context[field] < value):
                        return False
                elif op == 'lte':
                    if not (context[field] <= value):
                        return False
                elif op == 'gt':
                    if not (context[field] > value):
                        return False
                elif op == 'gte':
                    if not (context[field] >= value):
                        return False
                elif op == 'eq':
                    if not (context[field] == value):
                        return False
                elif op == 'neq':
                    if not (context[field] != value):
                        return False
                elif op == 'in':
                    if context[field] not in value:
                        return False
                else:
                    # default equality
                    if not (context[field] == value):
                        return False
            else:
                # equality
                if key not in context or context[key] != value:
                    return False
        return True


# ============================================================
# MÓDULO DE SCALPING
# ============================================================

class ScalpingBot(models.Model):
    """Bot de scalping especializado en timeframes cortos (1m-5m)."""

    STRATEGY_CHOICES = [
        ('EMA_CROSS',  'EMA Cross (5/20) + Volumen'),
        ('BB_SQUEEZE', 'Bollinger Squeeze + Momentum'),
        ('VWAP_RSI',   'VWAP + RSI Bounce'),
    ]
    TIMEFRAME_CHOICES = [
        ('1m',  '1 Minuto'),
        ('3m',  '3 Minutos'),
        ('5m',  '5 Minutos'),
        ('15m', '15 Minutos'),
    ]
    STATUS_CHOICES = [
        ('RUNNING', 'Running'),
        ('PAUSED',  'Paused'),
        ('STOPPED', 'Stopped'),
        ('ERROR',   'Error'),
    ]

    name             = models.CharField(max_length=100)
    pair             = models.ForeignKey('Pair', on_delete=models.CASCADE, related_name='scalping_bots')
    strategy_type    = models.CharField(max_length=20, choices=STRATEGY_CHOICES, default='EMA_CROSS')
    timeframe        = models.CharField(max_length=5, choices=TIMEFRAME_CHOICES, default='5m')
    status           = models.CharField(max_length=10, choices=STATUS_CHOICES, default='STOPPED')
    is_live          = models.BooleanField(default=False, help_text='Si True, ejecuta ordenes reales en Binance')

    # Capital y riesgo
    capital_usdt     = models.DecimalField(max_digits=20, decimal_places=2, default=100)
    max_position_pct = models.DecimalField(max_digits=5, decimal_places=2, default=50, help_text='% del capital por trade')
    sl_atr_mult      = models.DecimalField(max_digits=5, decimal_places=2, default=1.5, help_text='SL = N x ATR')
    tp_atr_mult      = models.DecimalField(max_digits=5, decimal_places=2, default=2.5, help_text='TP = N x ATR')

    # Parametros flexibles por estrategia
    parameters       = models.JSONField(default=dict, blank=True)

    # Estadisticas acumuladas
    total_trades     = models.IntegerField(default=0)
    winning_trades   = models.IntegerField(default=0)
    total_pnl_usdt   = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    last_error       = models.TextField(null=True, blank=True)

    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Scalping Bot'
        verbose_name_plural = 'Scalping Bots'

    def __str__(self):
        mode = 'LIVE' if self.is_live else 'SIM'
        return f'{self.name} [{self.strategy_type} {self.timeframe}] ({mode})'

    @property
    def win_rate(self):
        if self.total_trades == 0:
            return 0.0
        return round((self.winning_trades / self.total_trades) * 100, 1)


class ScalpingTrade(models.Model):
    """Trade individual ejecutado por un ScalpingBot."""

    STATUS_CHOICES = [
        ('OPEN',          'Abierta'),
        ('CLOSED_TP',     'Cerrada (Take Profit)'),
        ('CLOSED_SL',     'Cerrada (Stop Loss)'),
        ('CLOSED_MANUAL', 'Cerrada (Manual)'),
    ]

    bot                 = models.ForeignKey(ScalpingBot, on_delete=models.CASCADE, related_name='trades')
    side                = models.CharField(max_length=4, choices=[('BUY', 'Buy'), ('SELL', 'Sell')])
    entry_price         = models.DecimalField(max_digits=20, decimal_places=8)
    exit_price          = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    stop_loss           = models.DecimalField(max_digits=20, decimal_places=8)
    take_profit         = models.DecimalField(max_digits=20, decimal_places=8)
    quantity            = models.DecimalField(max_digits=20, decimal_places=8)
    pnl_usdt            = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    pnl_pct             = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    status              = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    entry_order_id      = models.CharField(max_length=100, null=True, blank=True)
    exit_order_id       = models.CharField(max_length=100, null=True, blank=True)
    indicators_snapshot = models.JSONField(null=True, blank=True)
    entry_time          = models.DateTimeField(auto_now_add=True)
    exit_time           = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-entry_time']

    def __str__(self):
        return f'{self.side} {self.bot.pair} @ {self.entry_price} ({self.status})'


class ScalpAlert(models.Model):
    """Alerta de oportunidad generada por el scanner de scalping."""

    pair                = models.ForeignKey('Pair', on_delete=models.CASCADE, related_name='scalp_alerts')
    timeframe           = models.CharField(max_length=5, default='5m')
    strategy            = models.CharField(max_length=20)
    signal_type         = models.CharField(max_length=4, choices=[('BUY', 'Compra'), ('SELL', 'Venta')])
    price_at_alert      = models.DecimalField(max_digits=20, decimal_places=8)
    suggested_sl        = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    suggested_tp        = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    confidence          = models.FloatField(default=0.0)
    indicators_snapshot = models.JSONField(null=True, blank=True)
    telegram_sent       = models.BooleanField(default=False)
    is_active           = models.BooleanField(default=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    expires_at          = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Scalp Alert'
        verbose_name_plural = 'Scalp Alerts'

    def __str__(self):
        return f'{self.signal_type} {self.pair} [{self.strategy}] conf={self.confidence:.0%}'


class PairScanResult(models.Model):
    """Ranking de oportunidades de scalping generado por el scanner."""

    pair                 = models.ForeignKey('Pair', on_delete=models.CASCADE, related_name='scan_results')
    timeframe            = models.CharField(max_length=5, default='5m')
    scanned_at           = models.DateTimeField(auto_now_add=True)

    # Scores 0-100
    volatility_score     = models.FloatField(default=0)
    volume_score         = models.FloatField(default=0)
    trend_score          = models.FloatField(default=0)
    signal_score         = models.FloatField(default=0)
    total_score          = models.FloatField(default=0)

    # Snapshot de mercado
    current_price        = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    atr_pct              = models.FloatField(null=True, help_text='ATR como % del precio')
    volume_24h_usdt      = models.FloatField(null=True)
    adx_value            = models.FloatField(null=True)

    signals_found        = models.JSONField(default=list)
    recommended_strategy = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        ordering = ['-total_score', '-scanned_at']
        verbose_name = 'Pair Scan Result'
        verbose_name_plural = 'Pair Scan Results'

    def __str__(self):
        return f'{self.pair} score={self.total_score:.1f} @ {self.scanned_at.strftime("%H:%M")}'

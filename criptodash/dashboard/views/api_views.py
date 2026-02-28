from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from ..models import LiveBot, LiveTrade, TradingPair
from ..serializers import LiveBotSerializer, LiveTradeSerializer, TradingPairSerializer
from ..ccxttest1 import binance as exchange

class CustomObtainAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'email': user.email
        })

class TradingPairViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TradingPair.objects.filter(is_active=True)
    serializer_class = TradingPairSerializer
    permission_classes = [permissions.IsAuthenticated]

class LiveBotViewSet(viewsets.ModelViewSet):
    queryset = LiveBot.objects.all().order_by('-created_at')
    serializer_class = LiveBotSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        bot = self.get_object()
        bot.status = 'RUNNING'
        bot.save()
        return Response({'status': 'Bot started', 'bot_id': bot.id})

    @action(detail=True, methods=['post'])
    def stop(self, request, pk=None):
        bot = self.get_object()
        bot.status = 'STOPPED'
        bot.save()
        return Response({'status': 'Bot stopped', 'bot_id': bot.id})

    @action(detail=True, methods=['post'])
    def clear_error(self, request, pk=None):
        bot = self.get_object()
        bot.last_error = None
        bot.status = 'STOPPED'
        bot.save()
        return Response({'status': 'Error cleared', 'bot_id': bot.id})

class LiveTradeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LiveTrade.objects.all().order_by('-entry_time')
    serializer_class = LiveTradeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset()[:50])
        
        # Enriquecer con precios actuales (similar a bot_dashboard)
        symbols = list(set([t.bot.pair.symbol for t in queryset if t.status == 'OPEN']))
        current_prices = {}
        if symbols:
            try:
                tickers = exchange.fetch_tickers(symbols)
                current_prices = {s: tickers[s]['last'] for s in symbols if s in tickers}
            except Exception:
                pass

        for trade in queryset:
            if trade.status == 'OPEN':
                symbol = trade.bot.pair.symbol
                trade.current_price = current_prices.get(symbol)
                
                # Calcular target_price para GRID
                if trade.bot.strategy_type == 'GRID':
                    params = trade.bot.parameters
                    try:
                        upper = float(params.get('upper_price', 0))
                        lower = float(params.get('lower_price', 0))
                        levels = int(params.get('grid_levels', 2))
                        if levels > 1:
                            grid_step = (upper - lower) / (levels - 1)
                            trade.target_price = float(trade.entry_price) + grid_step
                    except:
                        pass

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

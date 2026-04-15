import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import WhaleWallet, ConsensusSignal
from .services import PatternEngine
import logging

logger = logging.getLogger(__name__)

class WhaleMetricsConsumer(AsyncWebsocketConsumer):
    """Consumer para enviar métricas agregadas de ballenas en tiempo real."""
    
    async def connect(self):
        self.group_name = 'whale_metrics'
        
        # Aceptar la conexión
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()
        
        # Enviar métricas iniciales
        await self.send_aggregated_metrics()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Recibir mensaje del cliente (puede ser solicitud de actualización)."""
        try:
            data = json.loads(text_data)
            if data.get('type') == 'refresh':
                await self.send_aggregated_metrics()
        except Exception as e:
            logger.error(f"Error procesando mensaje WebSocket: {e}")
    
    async def send_aggregated_metrics(self):
        """Envía métricas agregadas al cliente."""
        metrics = await self.get_aggregated_metrics()
        await self.send(text_data=json.dumps({
            'type': 'metrics',
            'data': metrics
        }))
    
    async def whale_metrics_update(self, event):
        """Manejador para eventos de actualización de métricas (enviados desde otras partes del sistema)."""
        metrics = event['metrics']
        await self.send(text_data=json.dumps({
            'type': 'metrics_update',
            'data': metrics
        }))
    
    @database_sync_to_async
    def get_aggregated_metrics(self):
        """Obtiene métricas agregadas desde la base de datos."""
        total_whales = WhaleWallet.objects.filter(is_active=True).count()
        total_consensus = ConsensusSignal.objects.filter(status='ACTIVE').count()
        
        # Calcular win rate promedio (simplificado)
        from .models import ShadowTrade
        closed_trades = ShadowTrade.objects.filter(status='CLOSED')
        win_count = closed_trades.filter(pnl_percent__gt=0).count()
        total_closed = closed_trades.count()
        avg_win_rate = round((win_count / total_closed * 100) if total_closed > 0 else 0, 1)
        
        # Obtener hot tokens
        hot_tokens = PatternEngine.get_hot_tokens(hours=24)
        
        return {
            'total_whales': total_whales,
            'total_consensus': total_consensus,
            'avg_win_rate': avg_win_rate,
            'hot_tokens': hot_tokens[:5],
        }
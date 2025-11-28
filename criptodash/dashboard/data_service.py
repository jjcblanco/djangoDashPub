import pandas as pd
from django.utils import timezone
from .models import OHLCVData, TradingPair, Exchange
from .ccxttest1 import historical_fetch_ohlcv  # Tu función actual

class DataManager:
    @staticmethod
    def save_ohlcv_data(pair_symbol, timeframe, bars):
        """Guarda datos OHLCV en la base de datos"""
        try:
            exchange, _ = Exchange.objects.get_or_create(name='Binance')
            pair, _ = TradingPair.objects.get_or_create(
                symbol=pair_symbol,
                exchange=exchange,
                defaults={
                    'base_asset': pair_symbol.split('/')[0],
                    'quote_asset': pair_symbol.split('/')[1]
                }
            )
            
            ohlcv_objects = []
            for bar in bars:
                timestamp = pd.to_datetime(bar[0], unit='ms')
                
                ohlcv_objects.append(OHLCVData(
                    pair=pair,
                    timestamp=timestamp,
                    open=bar[1],
                    high=bar[2],
                    low=bar[3],
                    close=bar[4],
                    volume=bar[5],
                    timeframe=timeframe
                ))
            
            # Bulk create para eficiencia
            OHLCVData.objects.bulk_create(
                ohlcv_objects,
                update_conflicts=True,
                update_fields=['open', 'high', 'low', 'close', 'volume'],
                unique_fields=['pair', 'timestamp', 'timeframe']
            )
            
            return True
            
        except Exception as e:
            print(f"Error saving OHLCV data: {e}")
            return False
    
    @staticmethod
    def get_historical_data(pair_symbol, start_date, end_date, timeframe='1m'):
        """Obtiene datos históricos de la BD"""
        try:
            pair = TradingPair.objects.get(symbol=pair_symbol)
            
            data = OHLCVData.objects.filter(
                pair=pair,
                timestamp__gte=start_date,
                timestamp__lte=end_date,
                timeframe=timeframe
            ).order_by('timestamp')
            
            # Convertir a DataFrame
            df_data = []
            for record in data:
                df_data.append({
                    'timestamp': record.timestamp,
                    'open': float(record.open),
                    'high': float(record.high),
                    'low': float(record.low),
                    'close': float(record.close),
                    'volume': float(record.volume)
                })
            
            return pd.DataFrame(df_data) if df_data else pd.DataFrame()
            
        except TradingPair.DoesNotExist:
            print(f"Pair {pair_symbol} not found in database")
            return pd.DataFrame()
    
    @staticmethod
    def update_missing_data(pair_symbol, timeframe='1m', days_back=30):
        """Actualiza datos faltantes desde la API"""
        from datetime import datetime, timedelta
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Verificar qué datos tenemos
        existing_data = OHLCVData.objects.filter(
            pair__symbol=pair_symbol,
            timeframe=timeframe,
            timestamp__gte=start_date
        ).values_list('timestamp', flat=True)
        
        existing_timestamps = set(existing_data)
        
        # Obtener datos de la API
        bars = historical_fetch_ohlcv(pair_symbol, start_date.strftime('%Y-%m-%d %H:%M:%S'), timeframe)
        
        # Filtrar datos nuevos
        new_bars = []
        for bar in bars:
            timestamp = pd.to_datetime(bar[0], unit='ms')
            if timestamp not in existing_timestamps:
                new_bars.append(bar)
        
        if new_bars:
            DataManager.save_ohlcv_data(pair_symbol, timeframe, new_bars)
            print(f"Added {len(new_bars)} new records for {pair_symbol}")
        
        return len(new_bars)
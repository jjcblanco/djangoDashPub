import time
import logging
from django.core.management.base import BaseCommand
from dashboard.bot_manager import BotManager

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Ejecuta el ciclo de actualización de todos los bots activos cada 60 segundos.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=60,
            help='Intervalo de actualización en segundos (default: 60)'
        )

    def handle(self, *args, **options):
        interval = options['interval']
        self.stdout.write(self.style.SUCCESS(f'Iniciando el motor de actualización de bots (intervalo: {interval}s)...'))
        self.stdout.write('Presiona Ctrl+C para detener.')

        try:
            while True:
                start_time = time.time()
                
                self.stdout.write(f'--- Ciclo de actualización: {time.strftime("%Y-%m-%d %H:%M:%S")} ---')
                
                try:
                    results = BotManager.update_all_active_bots()
                    if results:
                        self.stdout.write(self.style.SUCCESS(f'Actualizados {len(results)} bots.'))
                        for res in results:
                            self.stdout.write(f'  - Bot ID {res.get("bot_id")}: {res.get("status")}')
                    else:
                        self.stdout.write('No hay bots activos ejecutándose.')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error en el ciclo de actualización: {e}'))

                # Calcular cuánto tiempo esperar para mantener el intervalo constante
                elapsed = time.time() - start_time
                wait_time = max(0, interval - elapsed)
                
                if wait_time > 0:
                    time.sleep(wait_time)
                    
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nDeteniendo el motor de bots de forma segura...'))

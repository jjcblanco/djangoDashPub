import os
import django
import datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "criptodash.settings")
django.setup()

from django.db import connection

now = datetime.datetime.now()
output = f"# Análisis de Bots ({now.strftime('%Y-%m-%d %H:%M:%S')})\n\n"

with connection.cursor() as cursor:
    cursor.execute("SELECT id, name, strategy_type, parameters, status, initial_balance, current_balance, created_at, updated_at, is_live, last_error FROM dashboard_livebot ORDER BY created_at")
    bots = cursor.fetchall()
    
    output += f"Total de bots encontrados: {len(bots)}\n\n"

    for bot in bots:
        bot_id, name, strategy_type, parameters, status, initial_balance, current_balance, created_at, updated_at, is_live, last_error = bot
        
        cursor.execute("SELECT pnl, status, side, amount, entry_price, exit_price, entry_time, exit_time FROM dashboard_livetrade WHERE bot_id = %s ORDER BY entry_time DESC", [bot_id])
        trades = cursor.fetchall()
        
        trades_count = len(trades)
        winning_trades = sum(1 for t in trades if t[0] and float(t[0]) > 0)
        losing_trades = sum(1 for t in trades if t[0] and float(t[0]) < 0)
        total_pnl = sum(float(t[0] or 0) for t in trades)
        win_rate = (winning_trades / trades_count * 100) if trades_count > 0 else 0
        
        # Manejar balances
        if initial_balance and float(initial_balance) > 0:
            roi = ((float(current_balance) - float(initial_balance)) / float(initial_balance) * 100)
        else:
            roi = 0

        duracion = "Desconocida"
        if created_at:
            if created_at.tzinfo:
                delta = now.astimezone() - created_at
            else:
                delta = now - created_at
            duracion = f"{delta.days} días, {delta.seconds//3600} horas"

        output += f"## Bot: {name}\n"
        output += f"- **Estrategia**: {strategy_type}\n"
        output += f"- **Estado**: {status}\n"
        output += f"- **Operando en Exchange (is_live)**: {'Sí' if is_live else 'No (Simulación)'}\n"
        output += f"- **Balance Inicial**: {float(initial_balance or 0):.4f} USDT\n"
        output += f"- **Balance Actual**: {float(current_balance or 0):.4f} USDT\n"
        output += f"- **ROI Acumulado**: {roi:.2f}%\n"
        output += f"- **Total Trades**: {trades_count}\n"
        output += f"- **Win Rate**: {win_rate:.2f}% ({winning_trades} Ganados / {losing_trades} Perdidos)\n"
        output += f"- **PnL Total (según trades)**: {total_pnl:.4f} USDT\n"
        output += f"- **Tiempo corriendo**: {duracion}\n"
        output += f"- **Creado en**: {created_at.strftime('%Y-%m-%d %H:%M:%S') if created_at else 'N/A'}\n"
        output += f"- **Última iteración**: {updated_at.strftime('%Y-%m-%d %H:%M:%S') if updated_at else 'N/A'}\n"
        output += f"- **Parámetros**: {parameters}\n"
        
        if last_error:
             output += f"- **Último Error Registrado**: {last_error}\n"
        
        ultimos_trades = trades[:5]
        if ultimos_trades:
            output += "\n  **Últimos 5 trades:**\n"
            for t in ultimos_trades:
                pnl_val, t_status, side, amount, entry_price, exit_price, entry_time, exit_time = t
                close_time = exit_time.strftime('%Y-%m-%d %H:%M') if exit_time else 'N/A'
                pnl_val = float(pnl_val or 0)
                output += f"  - [{t_status}] {side} {float(amount)} a {float(entry_price)} | Cierre: {float(exit_price or 0)} | PnL: {pnl_val:.4f}\n"

        output += "\n---\n\n"

    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    cursor.execute("SELECT pnl FROM dashboard_livetrade WHERE entry_time >= %s", [today])
    trades_today = cursor.fetchall()
    
    output += f"## Resumen General del Día (Desde {today.strftime('%Y-%m-%d')})\n"
    output += f"- Total de trades iniciados hoy: {len(trades_today)}\n"
    pnl_hoy = sum(float(t[0] or 0) for t in trades_today)
    output += f"- PnL total generado hoy: {float(pnl_hoy):.4f} USDT\n"

output_path = os.path.join(os.getcwd(), 'bot_analysis_report.md')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(output)

print(f"Reporte escrito en: {output_path}")


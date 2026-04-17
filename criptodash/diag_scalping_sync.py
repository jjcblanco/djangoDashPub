import os
import django
import sys

# Configurar Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.pair_scanner import scan_all_pairs, save_scan_results
from dashboard.models import PairScanResult

def diagnostic_scan():
    print("--- Diagnostic Scalping Scan ---")
    print("Testing Binance connection and scanning DEFAULT_PAIRS...")
    
    try:
        # Ejecutar escaneo sincrónicamente (sin Celery)
        results = scan_all_pairs(timeframe='5m', top_n=5, run_signals=True)
        
        if not results:
            print("FAILED: No results returned from scan_all_pairs.")
            return

        print(f"SUCCESS: Found {len(results)} pairs.")
        for r in results:
            print(f"- {r['symbol']}: Score {r['total_score']} | Signals: {len(r['signals_found'])}")
        
        print("\nSaving results to database...")
        save_scan_results(results, timeframe='5m')
        
        # Verificar permanencia
        count = PairScanResult.objects.count()
        print(f"Database check: {count} total scan records found.")
        
    except Exception as e:
        print(f"ERROR during diagnostic: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    diagnostic_scan()

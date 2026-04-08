"""
Diagnóstico completo del flujo de Caza de Ballenas.
Ejecutar con: venv\Scripts\python.exe tmp\diag_hunt.py
"""
import os, sys, django
sys.path.insert(0, 'criptodash')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import WhaleHuntTarget
from dashboard.services import PatternEngine
import requests, json

# 1. Ver targets activos
targets = WhaleHuntTarget.objects.filter(is_active=True)
print(f"=== Targets activos: {targets.count()} ===")
for t in targets:
    print(f"  [{t.blockchain.upper()}] ${t.token_symbol} — Addr: {t.contract_address[:20]}... Min Vol: ${t.min_volume_usd:,.0f}")

print()

# 2. Probar el primer target disponible
target = targets.first()
if not target:
    print("ERROR: No hay targets activos. Agrega uno en el panel Whale Insights > Caza.")
    sys.exit(1)

print(f"=== Probando: ${target.token_symbol} ({target.blockchain}) ===")

# 3. Ver resultado de discover_token_whales
buyers = PatternEngine.discover_token_whales(target.contract_address, target.blockchain)
print(f"Compradores encontrados: {len(buyers)}")

if not buyers:
    # Hacer la llamada cruda para ver qué pasa en la API
    print("\n--- Debug: llamada a DexScreener cruda ---")
    try:
        dex_resp = requests.get(
            f"https://api.dexscreener.com/latest/dex/search?q={target.contract_address}",
            timeout=5
        ).json()
        pairs = dex_resp.get('pairs', [])
        print(f"Pares en DexScreener: {len(pairs)}")
        if pairs:
            p = pairs[0]
            print(f"Red: {p.get('chainId')}, Pool: {p.get('pairAddress')}, Token: {p.get('baseToken', {}).get('symbol')}")
        else:
            print("ERROR: DexScreener no encontró pares para este contrato. Puede que el contrato sea incorrecto.")
    except Exception as e:
        print(f"ERROR DexScreener: {e}")
    sys.exit(1)

print(f"\nTop 5 compradores:")
for i, b in enumerate(buyers[:5]):
    vol = b.get('volume', 0)
    txs = b.get('tx_count', 0)
    addr = b.get('address', '')[:14]
    status = '✅ PASA' if vol >= target.min_volume_usd else f'❌ FILTRADO (min: ${target.min_volume_usd:,.0f})'
    print(f"  [{i+1}] {addr}... Vol: ${vol:,.2f} | TXs: {txs} | {status}")

passing = [b for b in buyers if b.get('volume', 0) >= target.min_volume_usd]
print(f"\nPasan el filtro de volumen: {len(passing)}/{len(buyers)}")

if not passing:
    max_vol = max((b.get('volume', 0) for b in buyers), default=0)
    print(f"\n⚠️  PROBLEMA: Todos filtrados. Volumen máximo detectado: ${max_vol:,.2f}")
    suggested = max(100, max_vol * 0.5)
    print(f"💡 Sugerencia: Baja el 'Min Vol' del target a ${suggested:,.0f} o menos.")
else:
    print(f"\n✅ Todo parece OK. Si no aparecen en el dashboard, puede ser un problema con el worker de Celery.")
    print("   Verifica que 'service celery status' esté ACTIVO en el VPS.")

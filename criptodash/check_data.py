import os
import sys
import django

# Asegurarse de que el directorio actual está en el path
sys.path.append(os.getcwd())

# Configurar Django localmente
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import WhaleWallet, WhaleTransaction

def run_check():
    wallets = WhaleWallet.objects.all()
    report = []
    report.append(f"Total Wallets: {wallets.count()}")
    
    total_txs = WhaleTransaction.objects.count()
    report.append(f"Total Transactions: {total_txs}")
    
    # Check for market context in a few recent ones
    recent_ctx = 0
    txs = WhaleTransaction.objects.exclude(raw_data=None).order_by('-id')[:100]
    for tx in txs:
        if tx.raw_data and 'market_context' in tx.raw_data:
            recent_ctx += 1
            
    report.append(f"Recent Transactions with Context (last 100): {recent_ctx}")
    
    with open('data_report.txt', 'w') as f:
        f.write("\n".join(report))
    print("Report generated successfully.")

if __name__ == "__main__":
    run_check()

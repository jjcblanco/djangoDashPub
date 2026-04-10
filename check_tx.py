from dashboard.models import WhaleTransaction
txs = WhaleTransaction.objects.exclude(raw_data={})
print(f'Total TXs with raw_data: {txs.count()}')
tx = txs.first()
if tx:
    print(f'Sample raw_data keys: {list(tx.raw_data.keys())}')
    price = tx.raw_data.get("priceUsd") or tx.raw_data.get("px") or tx.raw_data.get("price") or 0
    print(f'Sample price found: {price}')
else:
    print('No transactions with raw_data found.')

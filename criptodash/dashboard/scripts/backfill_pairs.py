"""
Backfill script to populate TradeSignal.pair_ref for existing signals.
Run with:
    python manage.py shell < dashboard/scripts/backfill_pairs.py
or run from a Django shell and call backfill() manually.
"""

from django.utils import timezone


def backfill():
    from dashboard.models import TradeSignal
    from dashboard.ccxttest1 import ensure_pair
    from django.db import transaction

    qs = TradeSignal.objects.filter(pair_ref__isnull=True)
    total = qs.count()
    print(f"Starting backfill for {total} TradeSignal rows")
    i = 0
    for signal in qs.iterator():
        try:
            canonical = ensure_pair(signal.pair.symbol, pair_type='spot', exchange=signal.pair.exchange.name)
            signal.pair_ref = canonical
            signal.save(update_fields=['pair_ref'])
            i += 1
            if i % 100 == 0:
                print(f"Backfilled {i}/{total}")
        except Exception as e:
            print(f"Error backfilling signal id={signal.id}: {e}")

    print(f"Backfill complete. Updated {i} rows.")


if __name__ == '__main__':
    backfill()
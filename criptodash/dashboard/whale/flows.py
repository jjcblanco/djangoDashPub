"""
whale/flows.py — detección de flujos ballena ↔ exchange centralizado (CEX).

Los trades DENTRO de un CEX son off-chain (no trackeables), pero los flujos
on-chain hacia/desde hot wallets conocidas de exchanges SÍ lo son:
- SELL cuyo destino es una hot wallet → DEPOSIT (la ballena manda fondos al CEX)
- BUY cuyo origen es una hot wallet → WITHDRAWAL (la ballena retira del CEX)

Señal de intención: retiro grande → posible compra en DEX; depósito grande →
posible venta.
"""
import logging

from .constants import lookup_exchange_wallet, STABLES

logger = logging.getLogger(__name__)

# Umbral de alerta Telegram en USD
ALERT_THRESHOLD_USD = 50000


def _decode_bsc_topic(topic):
    """Decodifica un topic hex de 32 bytes a dirección 0x (últimos 20 bytes)."""
    if not topic or not isinstance(topic, str):
        return None
    if len(topic) < 40:
        return None
    return '0x' + topic[-40:]


def extract_counterparty(wallet, tx):
    """
    Extrae la dirección de contraparte de una WhaleTransaction.
    Retorna (counterparty, direction) o (None, None):
    - EVM: raw_data['from'/'to'] planos. BUY → from; SELL → to.
    - BSC: raw_data['topics'][1] (from) / [2] (to) en hex 32B. Ídem.
    - Solana: owners de pre/postTokenBalances que NO sean la wallet
      (transfer directo de token). Swaps DEX no tienen contraparte CEX → None.
    - Hyperliquid: sin contraparte en userFills → None.
    """
    raw = tx.raw_data or {}
    blockchain = wallet.blockchain

    if blockchain in ('ethereum', 'base'):
        from_addr = raw.get('from', '')
        to_addr = raw.get('to', '')
        if tx.tx_type in ('BUY', 'SWAP') and from_addr:
            return from_addr.lower(), 'WITHDRAWAL'  # posible origen CEX
        if tx.tx_type in ('SELL', 'TRANSFER') and to_addr:
            return to_addr.lower(), 'DEPOSIT'  # posible destino CEX
        return None, None

    if blockchain == 'bsc':
        topics = raw.get('topics') or []
        from_addr = _decode_bsc_topic(topics[1]) if len(topics) > 1 else None
        to_addr = _decode_bsc_topic(topics[2]) if len(topics) > 2 else None
        if tx.tx_type == 'BUY' and from_addr:
            return from_addr, 'WITHDRAWAL'
        if tx.tx_type == 'SELL' and to_addr:
            return to_addr, 'DEPOSIT'
        return None, None

    if blockchain == 'solana':
        # Solo transfers directos de token: owners de balances que no sean la wallet
        meta = raw.get('meta') or {}
        wallet_addr = wallet.address
        counterparties = set()
        for balances in (meta.get('preTokenBalances') or []):
            owner = balances.get('owner')
            if owner and owner != wallet_addr:
                counterparties.add(owner)
        if len(counterparties) == 1:
            # Un solo otro owner con balance de token = transfer directo
            cpty = counterparties.pop()
            if tx.tx_type == 'BUY':
                return cpty, 'WITHDRAWAL'
            if tx.tx_type == 'SELL':
                return cpty, 'DEPOSIT'
        return None, None

    return None, None


def detect_exchange_flows(wallet, txs):
    """
    Detecta flujos CEX en una lista de WhaleTransaction y devuelve
    una lista de dicts con los datos del flujo (sin persistir):
    [{tx, exchange, blockchain, direction, token_symbol, amount, usd_value}]
    """
    from dashboard.services import fetch_current_price

    flows = []
    for tx in txs:
        try:
            counterparty, direction = extract_counterparty(wallet, tx)
            if not counterparty:
                continue

            hit = lookup_exchange_wallet(counterparty)
            if not hit:
                continue
            hit_blockchain, exchange = hit
            # La hot wallet debe pertenecer a la misma red que la tx
            if hit_blockchain != wallet.blockchain:
                continue

            # Determinar token y monto
            token_symbol = None
            amount = 0.0
            if direction == 'DEPOSIT':
                token_symbol = tx.from_asset
                amount = float(tx.amount_in or 0)
            else:
                token_symbol = tx.to_asset
                amount = float(tx.amount_out or tx.amount_in or 0)

            if not token_symbol or token_symbol.upper() in STABLES:
                # Los flujos de stablecoins también importan (USD directo)
                if token_symbol:
                    usd_value = amount  # stablecoin ≈ USD
                else:
                    continue
            else:
                price = fetch_current_price(token_symbol)
                if not price:
                    continue
                usd_value = amount * float(price)

            if usd_value <= 0:
                continue

            flows.append({
                'tx': tx,
                'exchange': exchange,
                'blockchain': wallet.blockchain,
                'direction': direction,
                'token_symbol': token_symbol.upper(),
                'amount': amount,
                'usd_value': round(usd_value, 2),
            })
        except Exception as e:
            logger.warning(f"[CEX Flows] Error procesando tx {tx.tx_hash[:16]}: {e}")
            continue

    return flows

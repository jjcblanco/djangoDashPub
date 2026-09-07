# TODO

- [x] Revisar el log real del VPS (whale_tracker.service) para confirmar la excepción. (pendiente de pegarlo; lógica corregida)
- [x] Corregir `criptodash/sync_whales_background.py` para importar `HyperliquidWhaleTracker` y clases usadas.
- [ ] Validar que el script corre en modo `--loop` sin romperse por `NameError`.
- [ ] Re-ejecutar el servicio systemd y verificar en `journalctl` que ya no falla.



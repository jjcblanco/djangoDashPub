# djangoDashPub — Diagrama de modelos

Inserta este bloque Mermaid en cualquier renderizador (GitHub soporta mermaid en .md si activado) o guarda en un fichero `.mmd`.

```mermaid
classDiagram
    class Exchange { +id +name : CharField +api_base : URLField +is_active : BooleanField }
    class TradingPair { +id +symbol : CharField +base_asset : CharField +quote_asset : CharField +exchange : FK Exchange +is_active : BooleanField }
    class OHLCVData { +id +pair : FK TradingPair +timestamp : DateTimeField +open : Decimal +high : Decimal +low : Decimal +close : Decimal +volume : Decimal +timeframe : CharField }
    class TradeSignal { +id +pair : FK TradingPair +timestamp : DateTimeField +signal_type : CharField +price : Decimal +indicator : CharField +strength : Float }
    class BacktestResult { +id +name : CharField +pair : FK TradingPair +start_date : DateTimeField +end_date : DateTimeField +strategy_name : CharField +parameters : JSONField +total_return : Float }
    Exchange "1" --> "0..*" TradingPair
    TradingPair "1" --> "0..*" OHLCVData
    TradingPair "1" --> "0..*" TradeSignal
    TradingPair "1" --> "0..*" BacktestResult
```

Exportar a PNG/SVG (mermaid-cli)
1. Instalar (Node.js requerido):
   - npm install -g @mermaid-js/mermaid-cli
2. Guardar diagrama en `diagram.mmd` y ejecutar:
   - mmdc -i diagram.mmd -o diagram.png
   - mmdc -i diagram.mmd -o diagram.svg

Alternativa rápida sin instalar:
- Usa https://mermaid.live/ para pegar el diagrama y exportar PNG/SVG desde la UI.

Añadir la imagen al README:
```md
![Modelo de datos](docs/diagram.png)
```
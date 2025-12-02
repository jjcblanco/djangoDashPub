-- Solución alternativa: Recrear la columna indicators sin restricción CHECK
USE trading_db;

-- Modificar la columna para eliminar la restricción implícita
ALTER TABLE dashboard_tradesignal MODIFY indicators JSON NULL;

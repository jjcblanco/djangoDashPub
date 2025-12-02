-- Solución definitiva: Cambiar el tipo de datos de JSON a LONGTEXT
-- Esto elimina completamente la restricción CHECK
USE trading_db;

-- Cambiar la columna indicators de JSON a LONGTEXT
ALTER TABLE dashboard_tradesignal MODIFY indicators LONGTEXT NULL;

-- Verificar el cambio
DESCRIBE dashboard_tradesignal;

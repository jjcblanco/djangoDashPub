-- Intentar eliminar la restricción CHECK con sintaxis alternativa para MariaDB
USE trading_db;

-- Opción 1: DROP CHECK (sintaxis antigua de MariaDB)
ALTER TABLE dashboard_tradesignal DROP CHECK indicators;

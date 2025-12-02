-- Script SQL para eliminar la restricción CHECK en el campo indicators
-- Ejecuta este script en MySQL Workbench o desde la línea de comandos
-- COMPATIBLE CON MARIADB

USE trading_db;

-- Primero, ver qué restricciones existen
SELECT 
    CONSTRAINT_NAME, 
    TABLE_NAME, 
    CONSTRAINT_TYPE 
FROM 
    INFORMATION_SCHEMA.TABLE_CONSTRAINTS 
WHERE 
    TABLE_NAME = 'dashboard_tradesignal' 
    AND TABLE_SCHEMA = 'trading_db';

-- Eliminar la restricción CHECK en indicators (sintaxis para MariaDB)
-- El nombre de la restricción es 'indicators'
ALTER TABLE dashboard_tradesignal DROP CONSTRAINT indicators;

-- Verificar que se eliminó
SELECT 
    CONSTRAINT_NAME, 
    TABLE_NAME, 
    CONSTRAINT_TYPE 
FROM 
    INFORMATION_SCHEMA.TABLE_CONSTRAINTS 
WHERE 
    TABLE_NAME = 'dashboard_tradesignal' 
    AND TABLE_SCHEMA = 'trading_db'
    AND CONSTRAINT_TYPE = 'CHECK';


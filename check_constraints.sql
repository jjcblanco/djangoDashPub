-- Ver las restricciones CHECK que existen en la tabla
USE trading_db;

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

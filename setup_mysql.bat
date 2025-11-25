@echo off
REM Script para crear la base de datos MySQL y configurar permisos
REM Asegúrate de que MySQL Server está ejecutándose en localhost:3306

echo.
echo ========================================
echo Creando Base de Datos MySQL para CriptoDash
echo ========================================
echo.

REM Solicitar contraseña de root
set /p MYSQL_PASSWORD="Ingresa la contraseña de root MySQL: "

echo.
echo Creando base de datos 'trading_db'...
C:\Program Files\MariaDB 12.1\bin\mysql -u root -p%MYSQL_PASSWORD% -e "CREATE DATABASE IF NOT EXISTS trading_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

if %ERRORLEVEL% NEQ 0 (
    echo Error al crear la base de datos. Verifica la contraseña de root.
    pause
    exit /b 1
)

echo.
echo Creando usuario 'trading_user'...
C:\Program Files\MariaDB 12.1\bin\mysql -u root -p%MYSQL_PASSWORD% -e "CREATE USER IF NOT EXISTS 'trading_user'@'localhost' IDENTIFIED BY 'retsam77';"

echo.
echo Asignando permisos...
C:\Program Files\MariaDB 12.1\bin\mysql -u root -p%MYSQL_PASSWORD% -e "GRANT ALL PRIVILEGES ON trading_db.* TO 'trading_user'@'localhost'; FLUSH PRIVILEGES;"

echo.
echo Verificando la creacion...
C:\Program Files\MariaDB 12.1\bin\mysql -u root -p%MYSQL_PASSWORD% -e "SELECT DATABASE();" trading_db

if %ERRORLEVEL% EQ 0 (
    echo.
    echo ========================================
    echo Base de datos creada exitosamente!
    echo ========================================
    echo.
    echo Detalles:
    echo   - Base de datos: trading_db
    echo   - Usuario: trading_user
    echo   - Password: retsam77
    echo   - Host: localhost
    echo   - Puerto: 3306
    echo.
    echo Ahora ejecuta las migraciones de Django:
    echo   cd criptodash
    echo   python manage.py migrate
    echo.
) else (
    echo Error al verificar la base de datos.
)

pause

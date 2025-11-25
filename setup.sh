#!/bin/bash
# Script de instalación y configuración para Linux/Mac
# Ejecutar: bash setup.sh

echo "================================"
echo "CriptoDash - Setup Script"
echo "================================"
echo ""

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Instalar dependencias Python
echo -e "${YELLOW}[1/5] Instalando dependencias Python...${NC}"
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo -e "${RED}Error al instalar dependencias${NC}"
    exit 1
fi

# 2. Crear base de datos MySQL
echo ""
echo -e "${YELLOW}[2/5] Configurando MySQL...${NC}"
echo "Ingresa contraseña de root MySQL (se usará para crear la BD):"
read -s MYSQL_PASSWORD

mysql -u root -p$MYSQL_PASSWORD <<EOF
CREATE DATABASE IF NOT EXISTS trading_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'trading_user'@'localhost' IDENTIFIED BY 'retsam77';
GRANT ALL PRIVILEGES ON trading_db.* TO 'trading_user'@'localhost';
FLUSH PRIVILEGES;
SELECT 'Base de datos creada exitosamente' as 'Resultado:';
EOF

if [ $? -ne 0 ]; then
    echo -e "${RED}Error al crear la base de datos${NC}"
    exit 1
fi

# 3. Ejecutar migraciones
echo ""
echo -e "${YELLOW}[3/5] Ejecutando migraciones de Django...${NC}"
cd criptodash
python manage.py makemigrations
python manage.py migrate
if [ $? -ne 0 ]; then
    echo -e "${RED}Error en migraciones${NC}"
    exit 1
fi

# 4. Crear superusuario
echo ""
echo -e "${YELLOW}[4/5] Creando superusuario...${NC}"
python manage.py createsuperuser

# 5. Resumen
echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}✅ Setup completado exitosamente!${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo "Próximos pasos:"
echo "1. Lee INICIO_RAPIDO.md para configurar Google OAuth (opcional)"
echo "2. Ejecuta: python manage.py runserver"
echo "3. Accede a: http://localhost:8000"
echo ""
echo -e "${YELLOW}Base de datos:${NC}"
echo "  - BD: trading_db"
echo "  - Usuario: trading_user"
echo "  - Contraseña: retsam77"
echo "  - Host: localhost"
echo "  - Puerto: 3306"
echo ""

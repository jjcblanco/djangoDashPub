# 🚀 INICIO RÁPIDO - SISTEMA DE LOGIN CRIPTODASH

## ¿QUÉ SE HA AGREGADO?

### ✨ Nuevas Funcionalidades:
- 🔐 **Login con usuario/contraseña** (almacenado en MySQL)
- 📱 **Google OAuth 2.0** (iniciar sesión con Google)
- 👤 **Sistema de registro** con validaciones
- 🛡️ **Perfil de usuario** con información personal
- 🔑 **Gestión de contraseñas**
- 📧 **Validación de emails**

---

## ⚡ PASOS PARA EMPEZAR

### 1️⃣ INSTALAR PAQUETES

```bash
pip install -r requirements.txt
```

### 2️⃣ CREAR BASE DE DATOS MYSQL

**Opción Windows:**
```bash
setup_mysql.bat
```

**Opción Manual (Todos los sistemas):**
```bash
mysql -u root -p
```

```sql
CREATE DATABASE trading_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'trading_user'@'localhost' IDENTIFIED BY 'retsam77';
GRANT ALL PRIVILEGES ON trading_db.* TO 'trading_user'@'localhost';
FLUSH PRIVILEGES;
```

### 3️⃣ EJECUTAR MIGRACIONES

```bash
cd criptodash
python manage.py migrate
```

### 4️⃣ CREAR SUPERUSUARIO (ADMIN)

```bash
python manage.py createsuperuser
```

Sigue las instrucciones y rellena:
- Usuario: `admin` (o tu nombre)
- Email: `tu@email.com`
- Contraseña: algo seguro

### 5️⃣ EJECUTAR SERVIDOR

```bash
python manage.py runserver
```

Accede a: `http://localhost:8000`

---

## 🔐 CONFIGURACIÓN DE GOOGLE OAUTH

### Primero - En el Admin Panel Django:

1. Ve a `http://localhost:8000/admin/`
2. Login con tu superusuario
3. Ve a **Sitios** y cambia `example.com` por `localhost:8000`
4. Guarda

### Segundo - Obtener credenciales Google:

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuevo proyecto: **CriptoDash**
3. Activa la API de Google+
4. Ve a **Credenciales** → **+ Crear Credenciales**
5. Selecciona **OAuth 2.0 ID de cliente** → **Aplicación Web**
6. En **Orígenes autorizados de JavaScript**:
   ```
   http://localhost:8000
   http://127.0.0.1:8000
   ```
7. En **URI de redireccionamiento autorizados**:
   ```
   http://localhost:8000/accounts/google/login/callback/
   http://127.0.0.1:8000/accounts/google/login/callback/
   ```
8. Copia tu **Client ID** y **Secret**

### Tercero - En el Admin Django:

1. Ve a `http://localhost:8000/admin/`
2. Busca **Aplicaciones de Redes Sociales**
3. Haz click en **Agregar**
4. Rellena:
   - **Proveedor**: Google
   - **Nombre**: Google OAuth
   - **Client ID**: `tu_client_id`
   - **Secret**: `tu_secret`
5. **Guardar**

---

## 🧪 PROBAR EL SISTEMA

### Login Local:
1. Ve a `http://localhost:8000/login/`
2. Click en **Regístrate aquí**
3. Crea un usuario:
   - Usuario: `testuser`
   - Email: `test@example.com`
   - Contraseña: `MiPassword123!`
   - Confirmar contraseña: `MiPassword123!`
4. ¡Listo! Serás redirigido al dashboard

### Google OAuth:
1. Ve a `http://localhost:8000/login/`
2. Click en **"Inicia sesión con Google"**
3. Elige tu cuenta de Google
4. ¡Autoriza el acceso!

---

## 📁 ARCHIVOS MODIFICADOS/CREADOS

```
✅ criptodash/settings.py          - Configuración MySQL + allauth
✅ criptodash/urls.py              - Rutas de autenticación
✅ dashboard/auth_views.py         - NUEVO: Vistas de login/registro/perfil
✅ dashboard/urls.py               - NUEVO: Rutas de auth
✅ dashboard/views.py              - Actualizado: proteger vistas
✅ dashboard/templates/dashboard/login.html      - NUEVO: Formulario de login
✅ dashboard/templates/dashboard/register.html   - NUEVO: Formulario de registro
✅ dashboard/templates/dashboard/profile.html    - NUEVO: Perfil de usuario
✅ requirements.txt                - NUEVO: django-allauth + dependencias
✅ AUTENTICACION_GUIA.md          - NUEVO: Guía detallada
✅ setup_mysql.bat                - NUEVO: Script de instalación MySQL
```

---

## 🔗 RUTAS DEL SISTEMA

| Ruta | Descripción | Requiere Login |
|------|-------------|----------------|
| `/` | Dashboard principal | ✅ |
| `/login/` | Página de login | ❌ |
| `/register/` | Página de registro | ❌ |
| `/logout/` | Cerrar sesión | ✅ |
| `/profile/` | Perfil del usuario | ✅ |
| `/admin/` | Panel de administración | ✅ |
| `/technical-analysis/` | Análisis técnico | ✅ |
| `/nuevo/` | Dashboard mejorado | ✅ |

---

## ⚙️ CONFIGURACIÓN IMPORTANTE

Verifica que estos valores estén en `settings.py`:

```python
# Base de datos MySQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'trading_db',
        'USER': 'trading_user',
        'PASSWORD': 'retsam77',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}

# Django allauth
SITE_ID = 1
LOGIN_REDIRECT_URL = '/'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]
```

---

## ❓ PROBLEMAS COMUNES

### "ModuleNotFoundError: No module named 'django_allauth'"
```bash
pip install django-allauth
```

### "Connection refused" para MySQL
- Asegúrate de que MySQL Server está ejecutándose
- Verifica el usuario y contraseña en `settings.py`
- En Windows: `services.msc` → MySQL80 (o tu versión) → Iniciar

### Google OAuth no funciona
- Verifica que el dominio en **Sitios** (admin) sea exacto: `localhost:8000`
- Limpia cookies del navegador
- Verifica que **Client ID** y **Secret** sean correctos en la app de Google

### Puertos en conflicto
```bash
# En lugar de puerto 8000, usa otro:
python manage.py runserver 8080
```

---

## 📞 RECURSOS

- **django-allauth docs**: https://django-allauth.readthedocs.io/
- **Django docs**: https://docs.djangoproject.com/
- **Google OAuth**: https://console.cloud.google.com/

---

**¡Listo para usar el nuevo sistema de autenticación! 🎉**

Para más detalles, lee: `AUTENTICACION_GUIA.md`

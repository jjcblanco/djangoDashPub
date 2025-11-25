# 🔐 GUÍA DE AUTENTICACIÓN - CRIPTODASH

## 📋 Cambios Realizados

Se ha implementado un **sistema de autenticación completo** con:

✅ **Login con MySQL** - Autenticación contra la base de datos
✅ **Registro de Usuarios** - Creación de nuevas cuentas
✅ **Google OAuth 2.0** - Login con cuenta de Google
✅ **Perfil de Usuario** - Página de información personal
✅ **Templates Profesionales** - Interfaz moderna y responsive

---

## 🚀 INSTRUCCIONES DE INSTALACIÓN

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 2. Configurar MySQL

Asegúrate de que MySQL está ejecutándose y crea la base de datos:

```sql
-- En MySQL CLI como root o usuario con permisos
CREATE DATABASE trading_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'trading_user'@'localhost' IDENTIFIED BY '***REDACTED***';
GRANT ALL PRIVILEGES ON trading_db.* TO 'trading_user'@'localhost';
FLUSH PRIVILEGES;
```

### 3. Ejecutar migraciones

```bash
cd criptodash
python manage.py makemigrations
python manage.py migrate
```

### 4. Crear superusuario (Administrador)

```bash
python manage.py createsuperuser
```

---

## 🔑 CONFIGURAR GOOGLE OAUTH 2.0

### Paso 1: Crear Proyecto en Google Cloud Console

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuevo proyecto: **CriptoDash**
3. Busca **OAuth 2.0 Credentials** en la barra de búsqueda

### Paso 2: Crear Credenciales OAuth

1. Ve a **Credenciales** → **+ Crear Credenciales**
2. Selecciona **OAuth 2.0 ID de cliente**
3. Elige **Aplicación Web**
4. En **Orígenes autorizados de JavaScript**:
   - `http://localhost:8000`
   - `http://127.0.0.1:8000`
   - (Tu dominio en producción)

5. En **URI de redireccionamiento autorizados**:
   - `http://localhost:8000/accounts/google/login/callback/`
   - `http://127.0.0.1:8000/accounts/google/login/callback/`
   - (Tu dominio en producción)

6. **Copia tu Client ID y Secret** que aparecerán en la pantalla

### Paso 3: Obtener el ID de la Aplicación Google

1. Ve a **APIs y servicios** → **Credenciales**
2. Busca tu credencial recién creada
3. Copia el **Client ID**

### Paso 4: Configurar en Django

#### Opción A: Desde el Admin Panel (Recomendado para desarrollo)

1. Inicia el servidor: `python manage.py runserver`
2. Ve a `http://localhost:8000/admin/`
3. Inicia sesión con el superusuario
4. Ve a **Sitios** y asegúrate de que el dominio sea `localhost:8000`
5. Ve a **Aplicaciones de Redes Sociales** → **Agregar**
6. Completa:
   - **Proveedor**: Google
   - **Nombre**: Google OAuth
   - **Client ID**: `tu_client_id_de_google`
   - **Secret**: `tu_secret_de_google`

#### Opción B: Desde el archivo settings.py (Manual)

Edita `criptodash/settings.py`:

```python
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'APP': {
            'client_id': 'TU_GOOGLE_CLIENT_ID_AQUI',
            'secret': 'TU_GOOGLE_SECRET_AQUI',
            'key': ''
        }
    }
}
```

---

## 📱 RUTAS DISPONIBLES

### Autenticación
- **`/login/`** - Página de login (usuario/contraseña o Google)
- **`/register/`** - Página de registro
- **`/logout/`** - Cerrar sesión
- **`/profile/`** - Perfil del usuario (requiere autenticación)
- **`/accounts/password/change/`** - Cambiar contraseña

### Dashboard
- **`/`** - Dashboard principal (protegido)
- **`/technical-analysis/`** - Análisis técnico
- **`/nuevo/`** - Dashboard mejorado

---

## 🛡️ CARACTERÍSTICAS DE SEGURIDAD

✅ **Contraseñas hasheadas** en MySQL
✅ **CSRF Protection** en todos los formularios
✅ **Email validation** en registro
✅ **Login required** decorators en vistas protegidas
✅ **Session management** con allauth
✅ **OAuth 2.0** seguro con Google

---

## 🧪 PRUEBAS

### Test de Login local:
```bash
# Usuario: tu_usuario
# Contraseña: tu_contraseña_de_8_caracteres
```

### Test de Google OAuth:
1. Ve a `/login/`
2. Haz click en **"Inicia sesión con Google"**
3. Completa el flujo de autenticación de Google
4. Serás redirigido al dashboard

---

## 📝 ESTRUCTURA DE ARCHIVOS CREADOS

```
dashboard/
├── auth_views.py           # Vistas de autenticación
├── templates/dashboard/
│   ├── login.html          # Formulario de login
│   ├── register.html       # Formulario de registro
│   └── profile.html        # Página de perfil
├── urls.py                 # URLs actualizadas
└── views.py               # Views actualizadas

criptodash/
├── settings.py            # Configuración actualizada
└── urls.py               # URLs del proyecto actualizadas
```

---

## ⚠️ IMPORTANTE - Variables de Entorno (PRODUCCIÓN)

En producción, usa variables de entorno en lugar de hardcodear credenciales:

```bash
pip install python-decouple
```

Crea un archivo `.env`:
```
SECRET_KEY=tu_secret_key
DEBUG=False
DATABASE_PASSWORD=tu_password_mysql
GOOGLE_CLIENT_ID=tu_client_id
GOOGLE_CLIENT_SECRET=tu_client_secret
```

---

## 🔧 TROUBLESHOOTING

### Error: "No module named 'django.contrib.sites'"
```bash
# Asegúrate de que SITE_ID = 1 está en settings.py
# Y 'django.contrib.sites' está en INSTALLED_APPS
```

### Error: "relation 'socialaccount_socialapp' does not exist"
```bash
python manage.py migrate
```

### Google OAuth no funciona
- Verifica que el `SITE_ID = 1` coincida con el dominio en admin
- Asegúrate de que las URLs de redireccionamiento en Google Cloud Console sean exactas
- Limpia cookies del navegador y reinicia el servidor

---

## 📞 SOPORTE

Para más información sobre django-allauth:
- Documentación: https://django-allauth.readthedocs.io/

---

**¡Sistema de autenticación listo para usar! 🎉**

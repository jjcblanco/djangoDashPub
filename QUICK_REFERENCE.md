# 🎯 TARJETA DE REFERENCIA RÁPIDA - CRIPTODASH AUTH

## 📱 URLS PRINCIPALES

```
PÚBLICAS (sin login)
├─ /                              → Landing page (index.html)
├─ /login/                        → Página de login
├─ /register/                     → Página de registro
├─ /accounts/password/reset/      → Recuperar contraseña
├─ /accounts/google/login/        → Login con Google
└─ /admin/login/                  → Login de admin

PROTEGIDAS (requieren login)
├─ /                              → Dashboard (redirige a login si no está autenticado)
├─ /profile/                      → Perfil del usuario
├─ /logout/                       → Cerrar sesión
├─ /nuevo/                        → Dashboard mejorado
├─ /technical-analysis/           → Análisis técnico
├─ /admin/                        → Panel de administración
└─ /accounts/password/change/     → Cambiar contraseña
```

---

## 🔐 CREDENCIALES POR DEFECTO

```mysql
BASE DE DATOS: trading_db
USUARIO: trading_user
CONTRASEÑA: ***REDACTED***
HOST: localhost
PUERTO: 3306
```

---

## ⚙️ CONFIGURACIONES CLAVE

### En `settings.py`:

```python
# Base de datos
DATABASES = { 'default': { 'ENGINE': 'django.db.backends.mysql', ... } }

# Apps instaladas
INSTALLED_APPS = [ ..., 'allauth', 'allauth.account', 
                   'allauth.socialaccount', 
                   'allauth.socialaccount.providers.google' ]

# Backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Autenticación
SITE_ID = 1
LOGIN_REDIRECT_URL = '/'
ACCOUNT_AUTHENTICATION_METHOD = 'username_email'
ACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_AUTO_SIGNUP = True
```

---

## 🚀 COMANDOS ÚTILES

```bash
# Instalación
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser

# Desarrollo
python manage.py runserver
python manage.py shell
python manage.py dbshell

# Verificación
python verify_setup.py
python manage.py check

# Limpiar
python manage.py flush              # ⚠️ Borra BD completa
rm db.sqlite3                       # Remover BD SQLite (si existe)
```

---

## 📁 ESTRUCTURA DE ARCHIVOS

```
dashboard/
├── auth_views.py              ← Vistas de autenticación
├── urls.py                    ← Rutas (incluyendo login/register)
├── views.py                   ← Vistas existentes (index protegido)
└── templates/dashboard/
    ├── index.html             ← Landing page
    ├── login.html             ← Formulario de login
    ├── register.html          ← Formulario de registro
    ├── profile.html           ← Perfil de usuario
    └── [otros templates]

criptodash/
├── settings.py                ← Configuración (MySQL + allauth)
└── urls.py                    ← URLs principales (incluyendo /accounts/)
```

---

## 🔑 VARIABLES DE ENTORNO (.env)

```bash
# Django
SECRET_KEY=tu_secret_key
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1

# MySQL
DB_ENGINE=django.db.backends.mysql
DB_NAME=trading_db
DB_USER=trading_user
DB_PASSWORD=***REDACTED***
DB_HOST=localhost
DB_PORT=3306

# Google OAuth
GOOGLE_CLIENT_ID=tu_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=tu_client_secret
```

---

## 🧪 PRUEBAS RÁPIDAS

### Test 1: Login Local
```
URL: http://localhost:8000/login/
Usuario: [crea uno con el admin o register]
Contraseña: [la que estableciste]
Resultado esperado: Acceso a dashboard
```

### Test 2: Registro
```
URL: http://localhost:8000/register/
Llenar: Usuario, Email, Contraseña (8+ caracteres)
Resultado esperado: Auto-login y acceso a dashboard
```

### Test 3: Google OAuth
```
Requisito: Configurar en Google Cloud Console
URL: http://localhost:8000/login/
Click: "Inicia sesión con Google"
Resultado esperado: Redirige a Google, luego auto-login
```

### Test 4: Perfil
```
URL: http://localhost:8000/profile/
Resultado esperado: Información del usuario autenticado
```

### Test 5: Logout
```
Desde: Cualquier página autenticada
Click: Botón "Salir" o "Logout"
Resultado esperado: Redirige a login, sesión cerrada
```

---

## 🐛 TROUBLESHOOTING RÁPIDO

| Problema | Solución |
|----------|----------|
| "ModuleNotFoundError: No module named 'django_allauth'" | `pip install django-allauth` |
| "Connection refused" a MySQL | Asegúrate que MySQL esté ejecutándose |
| Google OAuth no funciona | Verifica Client ID/Secret en admin y Google Cloud |
| "Table doesn't exist" | Ejecuta `python manage.py migrate` |
| Puerto 8000 en uso | Usa: `python manage.py runserver 8080` |
| Contraseña olvidada en admin | Usa: `python manage.py changepassword admin` |

---

## 📊 FLUJO DE DATOS

```
LOGIN LOCAL:
Usuario → FormLogin → auth_views.custom_login()
    ↓
Verifica username/email en BD MySQL
    ↓
authenticate() y login()
    ↓
Crea sesión en Django
    ↓
Redirige a '/'

GOOGLE OAUTH:
Usuario → Google OAuth → allauth
    ↓
Verifica/crea usuario en BD
    ↓
login() automático
    ↓
Crea sesión
    ↓
Redirige a '/'
```

---

## 🔐 SEGURIDAD QUICK CHECK

- ✅ Contraseñas hasheadas: Django bcrypt
- ✅ CSRF protection: {% csrf_token %} en forms
- ✅ SQL injection: ORM de Django
- ✅ XSS protection: Template escaping automático
- ✅ Session security: Django session framework
- ✅ OAuth 2.0: allauth con Google
- ✅ Email validation: Validación de formato
- ✅ Rate limiting: Configurable

---

## 📞 RECURSOS RÁPIDOS

- [django-allauth docs](https://django-allauth.readthedocs.io/)
- [Django auth docs](https://docs.djangoproject.com/en/5.2/topics/auth/)
- [Google OAuth](https://console.cloud.google.com/)
- Archivos de ayuda:
  - `INICIO_RAPIDO.md` - Instalación en 5 pasos
  - `AUTENTICACION_GUIA.md` - Guía completa con Google OAuth
  - `IMPLEMENTACION_RESUMEN.md` - Resumen técnico completo

---

## ✨ FEATURES IMPLEMENTADOS

✅ Login con usuario/contraseña (MySQL)
✅ Registro de usuarios con validaciones
✅ Google OAuth 2.0 integrado
✅ Perfil de usuario personalizado
✅ Gestión de sesiones
✅ Recuperación de contraseña (via allauth)
✅ Cambio de contraseña
✅ Logout seguro
✅ CSRF protection
✅ Email validation
✅ Templates responsive
✅ Admin panel integrado

---

## 🎯 PASOS INICIALES

1. `pip install -r requirements.txt`
2. `setup_mysql.bat` (Windows) o crear BD manualmente
3. `python manage.py migrate`
4. `python manage.py createsuperuser`
5. `python manage.py runserver`
6. Visita `http://localhost:8000`
7. ¡Login y disfruta! 🚀

---

**Versión**: 1.0
**Última actualización**: 2024
**Estado**: ✅ COMPLETO Y FUNCIONAL

¡Listo para usar! 🎉

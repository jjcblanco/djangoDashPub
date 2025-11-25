# 🏗️ ARQUITECTURA DEL SISTEMA DE AUTENTICACIÓN

## DIAGRAMA DE FLUJO COMPLETO

```
┌─────────────────────────────────────────────────────────────────┐
│                        USUARIO FINAL                             │
│                     (Navegador Web)                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ HTTP Request
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DJANGO URLS ROUTER                           │
│  (criptodash/urls.py → dashboard/urls.py)                      │
└───┬─────────────┬─────────────┬──────────────┬─────────────────┘
    │             │             │              │
    ▼             ▼             ▼              ▼
  /login/    /register/   /logout/    /accounts/* (allauth)
    │             │             │              │
    ▼             ▼             ▼              ▼
┌──────────────────────────────────────────────────────────────────┐
│                      VISTAS DE AUTENTICACIÓN                     │
│  ├─ custom_login()     (auth_views.py)                          │
│  ├─ custom_register()  (auth_views.py)                          │
│  ├─ custom_logout()    (auth_views.py)                          │
│  └─ profile()          (auth_views.py)                          │
│                                                                  │
│  + allauth views (OAuth, email verification, etc.)              │
└──────────────┬──────────────────────────────────────────────────┘
               │
        ┌──────┴──────┬─────────────┐
        │             │             │
        ▼             ▼             ▼
   LOGIN LOCAL  REGISTRO        GOOGLE OAUTH
   (MySQL)      (MySQL)         (allauth)
        │             │             │
        ├─────────────┼─────────────┤
        │             │             │
        └──────────────┼─────────────┘
                       │
                       ▼
        ┌────────────────────────────┐
        │   VALIDACIONES Y CHECKS    │
        │  - Email format validate   │
        │  - Password hash (bcrypt)  │
        │  - CSRF token verify       │
        │  - Session create          │
        └────────────────────┬───────┘
                             │
                             ▼
        ┌────────────────────────────────────┐
        │    MySQL BASE DE DATOS             │
        │  ├─ auth_user (usuarios)           │
        │  ├─ auth_user_groups (roles)       │
        │  ├─ socialaccount_socialapp        │
        │  ├─ socialaccount_socialaccount    │
        │  └─ sessions (sesiones activas)    │
        └────────────────────┬───────────────┘
                             │
                             ▼
        ┌────────────────────────────────┐
        │   CREAR SESIÓN SEGURA          │
        │  ├─ Session ID (random)        │
        │  ├─ User ID                    │
        │  ├─ Expiration time            │
        │  └─ Cookie (secure)            │
        └────────────────────┬───────────┘
                             │
                             ▼
        ┌────────────────────────────────┐
        │   GENERAR HTML RESPONSE        │
        │  ├─ Redirect a /               │
        │  ├─ Set-Cookie (sesión)        │
        │  └─ Status 302 o 200           │
        └────────────────────┬───────────┘
                             │
                             ▼
┌──────────────────────────────────────┐
│   USUARIO AUTENTICADO                │
│  ├─ Cookie de sesión                 │
│  ├─ Acceso a dashboard               │
│  └─ Perfil personalizado             │
└──────────────────────────────────────┘
```

---

## COMPONENTES DEL SISTEMA

```
┌─────────────────────────────────────────────────────────────────┐
│                      CAPA DE PRESENTACIÓN                        │
│  (Templates HTML + CSS + JavaScript)                             │
├─────────────────────────────────────────────────────────────────┤
│  ├─ login.html         (Formulario de login)                   │
│  ├─ register.html      (Formulario de registro)                │
│  ├─ profile.html       (Perfil del usuario)                    │
│  ├─ index.html         (Landing page)                          │
│  └─ otros.html         (Templates de allauth)                  │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Django template rendering
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      CAPA DE LÓGICA                              │
│  (Django Views + allauth)                                        │
├─────────────────────────────────────────────────────────────────┤
│  ├─ auth_views.py                                              │
│  │  ├─ custom_login()                                          │
│  │  ├─ custom_register()                                       │
│  │  ├─ custom_logout()                                         │
│  │  └─ profile()                                               │
│  │                                                              │
│  └─ allauth views (django-allauth)                             │
│     ├─ Google OAuth flow                                       │
│     ├─ Email verification                                      │
│     └─ Password reset                                          │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Django ORM
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      CAPA DE DATOS                               │
│  (Django ORM + MySQL)                                            │
├─────────────────────────────────────────────────────────────────┤
│  ├─ Modelos Django:                                             │
│  │  ├─ User (django.contrib.auth.models)                       │
│  │  ├─ Session                                                  │
│  │  ├─ SocialAccount (allauth)                                 │
│  │  └─ SocialApp (allauth)                                     │
│  │                                                              │
│  └─ Base de datos MySQL:                                        │
│     ├─ auth_user (Usuarios)                                    │
│     ├─ django_session (Sesiones)                               │
│     ├─ socialaccount_socialapp (Apps OAuth)                    │
│     └─ socialaccount_socialaccount (Cuentas Google)            │
└─────────────────────────────────────────────────────────────────┘
```

---

## FLUJO DE AUTENTICACIÓN POR MÉTODO

### MÉTODO 1: LOGIN LOCAL (Usuario/Contraseña)

```
Usuario escribe usuario/email en login.html
        │
        ▼
POST /login/ con credentials
        │
        ▼
custom_login() (auth_views.py)
        │
        ├─ Valida que ambos campos existan
        │
        ├─ authenticate(username, password)
        │  │
        │  ├─ Busca usuario en MySQL
        │  │
        │  └─ Compara password hasheado
        │
        ├─ Si es válido: login(request, user)
        │  │
        │  ├─ Crea sesión
        │  │
        │  └─ Asigna session ID a cookie
        │
        └─ Redirige a / (dashboard)
```

### MÉTODO 2: REGISTRO DE USUARIO

```
Usuario rellena formulario en register.html
        │
        ▼
POST /register/ con datos
        │
        ▼
custom_register() (auth_views.py)
        │
        ├─ Validaciones:
        │  ├─ Username no existe
        │  ├─ Email no existe
        │  ├─ Email formato válido
        │  ├─ Password ≥ 8 caracteres
        │  └─ Passwords coinciden
        │
        ├─ Si es válido:
        │  │
        │  ├─ User.objects.create_user()
        │  │  │
        │  │  └─ Hash password con bcrypt
        │  │
        │  ├─ authenticate() nuevo usuario
        │  │
        │  ├─ login() automático
        │  │
        │  └─ Crea sesión
        │
        └─ Redirige a / (dashboard)
```

### MÉTODO 3: GOOGLE OAUTH 2.0

```
Usuario clickea "Inicia sesión con Google"
        │
        ▼
Redirige a /accounts/google/login/
        │
        ▼
allauth (django-allauth)
        │
        ├─ Genera authorization request
        │
        └─ Redirige a Google
           │
           ▼ (Usuario autoriza)
           │
           ▼
Google devuelve código + datos
           │
           ▼
allauth callback handler
           │
           ├─ Valida código de Google
           │
           ├─ Obtiene datos: email, nombre, foto
           │
           ├─ ¿Usuario existe?
           │  ├─ NO: Crea nuevo usuario + SocialAccount
           │  └─ SI: Vincula SocialAccount
           │
           ├─ login() automático
           │
           ├─ Crea sesión
           │
           └─ Redirige a / (dashboard)
```

---

## FLUJO DE PROTECCIÓN CON LOGIN REQUIRED

```
Usuario visita una URL protegida (ej: /profile/)
        │
        ▼
Django procesa request
        │
        ├─ ¿request.user.is_authenticated?
        │  │
        │  ├─ SI → Renderiza template
        │  │
        │  └─ NO → Redirige a /login/?next=/profile/
        │      │
        │      ▼
        │  Usuario inicia sesión en /login/
        │      │
        │      └─ Redirige a /profile/ (URL original)
        │
        ▼
Acceso permitido
```

---

## TABLA DE DECISIONES

```
┌─────────────────────────────────────────────────────────────────┐
│ REQUEST RECIBIDO EN /login/                                     │
├─────────────────────────────────────────────────────────────────┤
│ ¿Método GET?                                                    │
│ ├─ SI → Mostrar formulario de login                            │
│ └─ NO → Continuar                                              │
│                                                                 │
│ ¿Username/email y password presentes?                          │
│ ├─ NO → Mostrar error "Campos requeridos"                      │
│ └─ SI → Continuar                                              │
│                                                                 │
│ ¿authenticate() devuelve usuario?                              │
│ ├─ NO → Mostrar error "Credenciales inválidas"                 │
│ └─ SI → Continuar                                              │
│                                                                 │
│ ✓ login(request, user)                                         │
│ ✓ Redirige a next_url o /                                      │
│ ✓ Set-Cookie con session ID                                    │
│ ✓ Acceso al dashboard                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## ESTRUCTURA DE CARPETAS RELACIONADA

```
criptodash/
│
├── criptodash/                (Configuración del proyecto)
│   ├── settings.py            (Configuración - incluye MySQL + allauth)
│   ├── urls.py                (Rutas principales - incluye /accounts/)
│   ├── wsgi.py
│   └── asgi.py
│
├── dashboard/                 (App principal)
│   ├── auth_views.py          (Vistas de autenticación) ⭐
│   ├── views.py               (Vistas existentes)
│   ├── urls.py                (Rutas - incluye login/register) ⭐
│   ├── models.py
│   ├── admin.py
│   ├── templates/
│   │   └── dashboard/
│   │       ├── login.html     ⭐
│   │       ├── register.html  ⭐
│   │       ├── profile.html   ⭐
│   │       ├── index.html     ⭐
│   │       └── [otros]
│   └── static/
│
├── manage.py
├── requirements.txt           (Incluye django-allauth)
│
├── Archivos de documentación:
│   ├── INICIO_RAPIDO.md
│   ├── AUTENTICACION_GUIA.md
│   ├── IMPLEMENTACION_RESUMEN.md
│   ├── QUICK_REFERENCE.md
│   ├── ENTREGA_FINAL.md
│   └── ARQUITECTURA.md (este archivo)
│
└── Scripts de configuración:
    ├── setup_mysql.bat
    ├── setup.sh
    └── verify_setup.py
```

---

## SEGURIDAD EN CAPAS

```
CAPA 1: NAVEGADOR
├─ HTTPS (en producción)
├─ Secure cookies
└─ SameSite cookie attribute

CAPA 2: COMUNICACIÓN HTTP
├─ CSRF tokens en formularios
├─ POST para operaciones sensibles
└─ Headers de seguridad

CAPA 3: VALIDACIÓN DJANGO
├─ Email validation regex
├─ Password strength requirements
├─ SQL injection prevention (ORM)
└─ XSS protection (template escaping)

CAPA 4: ALMACENAMIENTO
├─ Passwords hasheados (bcrypt)
├─ Session encryption
├─ MySQL user con permisos limitados
└─ Backups encriptados

CAPA 5: ADMINISTRACIÓN
├─ Access control en admin
├─ Audit logging
├─ Rate limiting
└─ Account lockout
```

---

## COMPONENTES INTERNOS DE DJANGO

```
Django Authentication System
│
├─ Users Model (auth.User)
│  ├─ username
│  ├─ password (hashed)
│  ├─ email
│  ├─ first_name, last_name
│  ├─ is_active, is_staff, is_superuser
│  └─ date_joined, last_login
│
├─ authenticate(username/email, password)
│  └─ Busca en BD y valida
│
├─ login(request, user)
│  └─ Crea sesión
│
├─ logout(request)
│  └─ Destruye sesión
│
├─ @login_required
│  └─ Protege vistas
│
└─ Session Framework
   ├─ Session ID
   ├─ Expiración
   └─ Datos de usuario
```

---

## DIAGRAMA DE DEPENDENCIAS

```
CriptoDash
│
├─ Django 5.2.7
│  ├─ django.contrib.auth (Autenticación nativa)
│  ├─ django.contrib.sessions (Gestión de sesiones)
│  ├─ django.contrib.sites (Soporte para sitios múltiples)
│  └─ django.contrib.messages (Sistema de mensajes)
│
├─ django-allauth 0.61.1 ⭐
│  ├─ allauth.account (Registro y login)
│  ├─ allauth.socialaccount (OAuth)
│  └─ allauth.socialaccount.providers.google (Google OAuth)
│
├─ MySQL via mysqlclient
│  └─ Base de datos persistente
│
└─ requests-oauthlib
   └─ Manejo de OAuth 2.0
```

---

**Versión**: 1.0
**Última actualización**: 2024
**Archivo**: ARQUITECTURA.md

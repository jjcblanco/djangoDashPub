# Guía: Configurar Google OAuth para Django

## 📋 Pasos para Obtener Credenciales de Google

### 1. Ir a Google Cloud Console
Visita: https://console.cloud.google.com/

### 2. Crear o Seleccionar un Proyecto
- Click en el menú desplegable de proyectos (arriba)
- Click en "Nuevo Proyecto" o selecciona uno existente
- Nombra tu proyecto (ej: "CriptoDash")

### 3. Habilitar Google+ API
- En el menú lateral, ve a "APIs y servicios" → "Biblioteca"
- Busca "Google+ API"
- Click en "Habilitar"

### 4. Crear Credenciales OAuth 2.0
- Ve a "APIs y servicios" → "Credenciales"
- Click en "+ CREAR CREDENCIALES" → "ID de cliente de OAuth"
- Tipo de aplicación: "Aplicación web"
- Nombre: "CriptoDash Web Client"

### 5. Configurar URIs Autorizados

**Orígenes de JavaScript autorizados**:
```
http://localhost:8000
http://127.0.0.1:8000
```

**URIs de redireccionamiento autorizados**:
```
http://localhost:8000/accounts/google/login/callback/
http://127.0.0.1:8000/accounts/google/login/callback/
```

### 6. Copiar Credenciales
Después de crear, verás:
- **ID de cliente**: Algo como `123456789-abc123.apps.googleusercontent.com`
- **Secreto del cliente**: Algo como `GOCSPX-abc123xyz789`

### 7. Configurar en tu Proyecto

#### Opción A: Usar Variables de Entorno (Recomendado)

1. Copia `.env.example` a `.env`:
   ```bash
   copy .env.example .env
   ```

2. Edita `.env` y reemplaza:
   ```
   GOOGLE_CLIENT_ID=TU_CLIENT_ID_AQUI
   GOOGLE_CLIENT_SECRET=TU_CLIENT_SECRET_AQUI
   ```

3. Instala python-decouple (si no está instalado):
   ```bash
   pip install python-decouple
   ```

4. Actualiza `settings.py` para usar decouple:
   ```python
   from decouple import config
   
   SOCIALACCOUNT_PROVIDERS = {
       'google': {
           'APP': {
               'client_id': config('GOOGLE_CLIENT_ID'),
               'secret': config('GOOGLE_CLIENT_SECRET'),
           }
       }
   }
   ```

#### Opción B: Configurar Directamente en Django Admin (Temporal)

1. Inicia el servidor:
   ```bash
   python manage.py runserver
   ```

2. Ve a: http://localhost:8000/admin/

3. Navega a: **Sites** → **Social applications**

4. Click en "Add Social Application"

5. Completa:
   - **Provider**: Google
   - **Name**: Google OAuth
   - **Client id**: Tu Client ID
   - **Secret key**: Tu Client Secret
   - **Sites**: Selecciona "example.com" (o el site que tengas)

6. Guarda

### 8. Verificar Configuración

1. Ve a tu aplicación: http://localhost:8000/

2. Click en "Login with Google"

3. Deberías ser redirigido a la pantalla de consentimiento de Google

## 🔒 Seguridad

**IMPORTANTE**: 
- ✅ Añade `.env` a tu `.gitignore`
- ✅ Nunca subas credenciales a Git
- ✅ Usa variables de entorno en producción
- ✅ Mantén `.env.example` como plantilla (sin credenciales reales)

## 🐛 Solución de Problemas

### Error: "The OAuth client was not found"
- Verifica que las credenciales en `.env` sean correctas
- Asegúrate de que el servidor esté usando las variables de entorno
- Reinicia el servidor después de cambiar `.env`

### Error: "Redirect URI mismatch"
- Verifica que las URIs de redirección en Google Cloud Console coincidan exactamente
- Incluye tanto `http://localhost:8000` como `http://127.0.0.1:8000`

### Error: "Access blocked: This app's request is invalid"
- Asegúrate de haber habilitado Google+ API
- Verifica que el proyecto en Google Cloud Console esté activo

## 📚 Referencias

- [Django Allauth Documentation](https://django-allauth.readthedocs.io/)
- [Google OAuth 2.0 Setup](https://developers.google.com/identity/protocols/oauth2)
- [Google Cloud Console](https://console.cloud.google.com/)

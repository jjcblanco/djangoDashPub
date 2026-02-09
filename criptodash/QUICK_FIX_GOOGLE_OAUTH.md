# 🔧 Solución Rápida: Error de Google OAuth

## ❌ Problema
```
Error 401: invalid_client
The OAuth client was not found.
```

## ✅ Solución Inmediata

### Opción 1: Deshabilitar Login con Google (Temporal)

Si no necesitas el login con Google ahora mismo, puedes deshabilitarlo temporalmente:

**Edita `settings.py` línea 191-192**:
```python
'client_id': os.environ.get('GOOGLE_CLIENT_ID', 'DISABLED'),
'secret': os.environ.get('GOOGLE_CLIENT_SECRET', 'DISABLED'),
```

Esto evitará el error, pero el botón de Google no funcionará.

---

### Opción 2: Configurar Credenciales de Google (Recomendado)

#### Paso 1: Obtener Credenciales

1. Ve a: https://console.cloud.google.com/apis/credentials
2. Crea un nuevo proyecto o selecciona uno existente
3. Click en "+ CREAR CREDENCIALES" → "ID de cliente de OAuth"
4. Tipo: "Aplicación web"
5. **URIs de redirección autorizados**:
   ```
   http://localhost:8000/accounts/google/login/callback/
   http://127.0.0.1:8000/accounts/google/login/callback/
   ```
6. Copia el **Client ID** y **Client Secret**

#### Paso 2: Configurar en tu Proyecto

**Método A: Variables de Entorno (Windows)**

```powershell
# En PowerShell, ejecuta:
$env:GOOGLE_CLIENT_ID="tu_client_id_aqui"
$env:GOOGLE_CLIENT_SECRET="tu_client_secret_aqui"

# Luego inicia el servidor en la misma ventana:
python manage.py runserver
```

**Método B: Crear archivo .env**

1. Copia el archivo de ejemplo:
   ```bash
   copy .env.example .env
   ```

2. Edita `.env` y reemplaza:
   ```
   GOOGLE_CLIENT_ID=TU_CLIENT_ID_REAL
   GOOGLE_CLIENT_SECRET=TU_CLIENT_SECRET_REAL
   ```

3. Instala python-decouple:
   ```bash
   pip install python-decouple
   ```

4. Actualiza `settings.py` (línea 1):
   ```python
   from decouple import config
   ```

5. Cambia líneas 191-192:
   ```python
   'client_id': config('GOOGLE_CLIENT_ID'),
   'secret': config('GOOGLE_CLIENT_SECRET'),
   ```

#### Paso 3: Reiniciar Servidor

```bash
python manage.py runserver
```

---

## 📚 Documentación Completa

Para más detalles, consulta: [GOOGLE_OAUTH_SETUP.md](file:///c:/Users/Javier/Desktop/programacion/djangoDashPub/criptodash/GOOGLE_OAUTH_SETUP.md)

---

## 🔍 Verificar que Funciona

1. Ve a: http://localhost:8000/
2. Click en "Login with Google"
3. Deberías ver la pantalla de consentimiento de Google (no el error 401)

---

## ⚠️ Importante

- ✅ El archivo `.env` está en `.gitignore` (no se subirá a Git)
- ✅ Usa `.env.example` como plantilla (sin credenciales reales)
- ✅ Nunca compartas tus credenciales de Google

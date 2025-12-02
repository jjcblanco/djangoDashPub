# 📚 Documentación del Proyecto - djangoDashPub

Esta carpeta contiene la documentación generada durante el desarrollo y mantenimiento del proyecto.

---

## 📄 Archivos de Documentación

### 1. [analisis_codigo.md](./analisis_codigo.md)
**Análisis completo de la arquitectura del proyecto**

Contiene:
- Diagrama de arquitectura general
- Estructura de URLs y vistas
- Flujo de datos entre API y dashboard
- Relaciones entre componentes (ccxttest1, indicadores, data_service, models)
- Tabla de dependencias entre módulos
- Ejemplos de flujo completo

**Cuándo consultarlo**: Para entender cómo funciona el proyecto en general y cómo se relacionan los diferentes componentes.

---

### 2. [implementation_plan.md](./implementation_plan.md)
**Plan de implementación para corregir dashboard_mejorado**

Contiene:
- Descripción de problemas identificados
- Cambios propuestos detallados
- Plan de verificación con casos de prueba
- Consideraciones importantes

**Cuándo consultarlo**: Para entender qué problemas había en `dashboard_mejorado` y cómo se planeó la solución.

---

### 3. [walkthrough.md](./walkthrough.md)
**Documentación de las correcciones aplicadas**

Contiene:
- Resumen de cambios realizados
- Problemas corregidos con código antes/después
- Flujo mejorado con diagramas
- Casos de prueba detallados
- Verificación en base de datos
- Próximos pasos sugeridos

**Cuándo consultarlo**: Para ver exactamente qué se cambió en el código y cómo probar las correcciones.

---

### 4. [constraint_fix.md](./constraint_fix.md)
**Fix del error de restricción MySQL en campo indicators**

Contiene:
- Explicación del error de constraint
- Causa del problema
- Solución aplicada
- Código antes/después
- Instrucciones de prueba

**Cuándo consultarlo**: Si vuelve a aparecer el error de MySQL constraint o para entender cómo se maneja el campo `indicators`.

---

## 🗂️ Estructura del Proyecto

```
djangoDashPub/
├── docs/                          # 📚 Esta carpeta
│   ├── README.md                  # Este archivo
│   ├── analisis_codigo.md
│   ├── implementation_plan.md
│   ├── walkthrough.md
│   └── constraint_fix.md
├── criptodash/                    # 🎯 Proyecto Django
│   ├── criptodash/                # Configuración
│   │   ├── settings.py
│   │   └── urls.py
│   └── dashboard/                 # App principal
│       ├── views.py               # Vistas y endpoints
│       ├── models.py              # Modelos de datos
│       ├── ccxttest1.py           # Bot de trading
│       ├── indicadores.py         # Indicadores técnicos
│       ├── data_service.py        # Gestión de datos
│       └── auth_views.py          # Autenticación
├── scripts/                       # 🔧 Scripts de análisis
├── ARQUITECTURA.md                # Documentación de arquitectura original
├── INICIO_RAPIDO.md               # Guía de inicio rápido
└── requirements.txt               # Dependencias
```

---

## 🔍 Guía Rápida de Consulta

### ¿Cómo funciona el proyecto?
→ Lee [analisis_codigo.md](./analisis_codigo.md)

### ¿Qué cambios se hicieron recientemente?
→ Lee [walkthrough.md](./walkthrough.md)

### ¿Cómo se relacionan las funciones API y dashboard?
→ Lee la sección "Relaciones Clave" en [analisis_codigo.md](./analisis_codigo.md#-relaciones-clave-entre-funciones)

### ¿Cómo funciona el bot de trading?
→ Lee la sección "ccxttest1.py" en [analisis_codigo.md](./analisis_codigo.md#2-ccxttest1py---bot-de-trading)

### ¿Qué hacer si hay un error de MySQL?
→ Lee [constraint_fix.md](./constraint_fix.md)

---

## 📝 Cambios Recientes (2025-12-02)

### Correcciones Aplicadas

1. ✅ **Error de atributo en data_service.py**
   - Corregido `signal_strength` → `strength`

2. ✅ **Lógica mejorada en dashboard_mejorado**
   - Ahora ejecuta el bot automáticamente cuando no hay datos
   - Mejor manejo de errores
   - Inicialización correcta de variables

3. ✅ **Fix de constraint MySQL**
   - Campo `indicators` ahora guarda `None` en lugar de `{}`
   - Agregada validación de NaN
   - Mejor logging de errores

---

## 🎯 Próximos Pasos Sugeridos

1. **Agregar indicador de carga**: Mostrar spinner mientras el bot se ejecuta
2. **Implementar caché**: Evitar llamadas repetidas a Binance
3. **Validación de fechas en frontend**: Prevenir envío de fechas inválidas
4. **Limitar rango de fechas**: Evitar solicitudes de datos muy antiguos
5. **Agregar paginación**: Para cuando hay muchas señales

---

**Última actualización**: 2025-12-02  
**Mantenedor**: Javier

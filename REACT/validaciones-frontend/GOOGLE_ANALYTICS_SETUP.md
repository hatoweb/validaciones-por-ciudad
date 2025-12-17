# Configuración de Google Analytics

Esta guía te ayudará a configurar Google Analytics en el frontend de la aplicación de validaciones.

## 📋 Requisitos Previos

Antes de comenzar, asegúrate de tener:

1. **Cuenta de Google Analytics**: Necesitas tener una cuenta de Google Analytics activa.
   - Si no tienes una, créala en: https://analytics.google.com/
   - Debes tener permisos de administrador o editor en la propiedad

2. **Propiedad de Google Analytics 4 (GA4)**: 
   - La aplicación está configurada para usar Google Analytics 4 (GA4)
   - Si tienes una propiedad Universal Analytics (UA), necesitarás crear una nueva propiedad GA4

3. **ID de Medición (Measurement ID)**: 
   - Formato: `G-XXXXXXXXXX` (donde X son letras y números)
   - Puedes encontrarlo en: [Google Analytics](https://analytics.google.com/) → Administrar → Flujo de datos → Tu propiedad → ID de medición
   - Ejemplo: `G-ABC123XYZ`

4. **Acceso al código fuente**: 
   - Necesitas poder editar archivos en `REACT/validaciones-frontend/`
   - Acceso para crear el archivo `.env` (no se sube al repositorio por seguridad)

## ✅ Checklist de Implementación

- [ ] Tener cuenta de Google Analytics con propiedad GA4
- [ ] Obtener el ID de medición (formato: G-XXXXXXXXXX)
- [ ] Crear archivo `.env` en `REACT/validaciones-frontend/`
- [ ] Configurar variable `REACT_APP_GA_MEASUREMENT_ID` en `.env`
- [ ] Reconstruir la aplicación (`npm run build`)
- [ ] Verificar que Google Analytics se inicialice correctamente
- [ ] Configurar variable de entorno en producción (Docker/servidor)

## Pasos de Configuración

### 1. Obtener el ID de Medición de Google Analytics

1. Accede a [Google Analytics](https://analytics.google.com/)
2. Selecciona tu propiedad o crea una nueva
3. Ve a **Administrar** (⚙️) → **Flujo de datos**
4. Haz clic en tu flujo de datos web
5. Copia el **ID de medición** (formato: `G-XXXXXXXXXX`)

### 2. Configurar la Variable de Entorno

#### Opción A: Archivo `.env` (Recomendado para desarrollo)

1. En la carpeta `REACT/validaciones-frontend/`, crea un archivo llamado `.env` (si no existe)
   - **Nota**: El archivo `.env` está en `.gitignore` por seguridad, así que no se subirá al repositorio
2. Agrega la siguiente línea:

```env
REACT_APP_GA_MEASUREMENT_ID=G-TU_ID_AQUI
```

3. Reemplaza `G-TU_ID_AQUI` con tu ID de medición real

**Ejemplo:**
```env
REACT_APP_GA_MEASUREMENT_ID=G-ABC123XYZ
```

**Estructura del archivo `.env`:**
```env
# Google Analytics Configuration
# Obtén tu ID de medición desde: https://analytics.google.com/
# Formato: G-XXXXXXXXXX
REACT_APP_GA_MEASUREMENT_ID=G-XXXXXXXXXX
```

#### Opción B: Variables de Entorno del Sistema (Producción)

Para producción, configura la variable de entorno en tu servidor o plataforma de despliegue:

**Docker:**
```yaml
# En docker-compose.yml
environment:
  - REACT_APP_GA_MEASUREMENT_ID=G-TU_ID_AQUI
```

**Nginx/Server:**
```bash
export REACT_APP_GA_MEASUREMENT_ID=G-TU_ID_AQUI
```

### 3. Reconstruir la Aplicación

Después de configurar la variable de entorno, necesitas reconstruir la aplicación:

```bash
cd REACT/validaciones-frontend
npm run build
```

**Nota importante**: Las variables de entorno que comienzan con `REACT_APP_` se inyectan en tiempo de compilación, no en tiempo de ejecución. Por lo tanto, debes reconstruir la aplicación cada vez que cambies estas variables.

### 4. Verificar la Configuración

1. Abre la aplicación en tu navegador
2. Abre las herramientas de desarrollador (F12)
3. Ve a la pestaña **Console**
4. Si Google Analytics está configurado correctamente, verás un mensaje: `Google Analytics inicializado correctamente con ID: G-XXXXX`
5. En la pestaña **Network**, deberías ver una solicitud a `googletagmanager.com`

## Funcionalidades Implementadas

El sistema de Google Analytics está configurado para rastrear:

### Eventos Automáticos
- **Vistas de página**: Se rastrean automáticamente cuando los usuarios navegan por la aplicación

### Eventos Personalizados Disponibles

El archivo `src/utils/analytics.js` incluye funciones para rastrear eventos personalizados:

- **Filtros**:
  - `filterMonth`: Cuando se cambia el mes
  - `filterYear`: Cuando se cambia el año
  - `filterFranja`: Cuando se selecciona una franja operativa
  - `filterBarrios`: Cuando se activa/desactiva la opción de incluir barrios
  - `filterCriterio`: Cuando se cambia el criterio de visualización
  - `filterMapLayer`: Cuando se cambia la capa del mapa

- **Datos**:
  - `fetchData`: Cuando se solicita obtener datos
  - `fetchDataSuccess`: Cuando los datos se cargan exitosamente
  - `fetchDataError`: Cuando ocurre un error al cargar datos

- **Interacciones con el mapa**:
  - `mapFeatureClick`: Cuando se hace clic en una característica del mapa
  - `mapFeatureHover`: Cuando se pasa el mouse sobre una característica

- **Tabla**:
  - `tableSort`: Cuando se ordena una columna
  - `tableSearch`: Cuando se busca en la tabla
  - `tableRowClick`: Cuando se hace clic en una fila

- **Exportación**:
  - `exportPDF`: Cuando se descarga un PDF

- **Opciones**:
  - `changeOpacity`: Cuando se cambia la opacidad del mapa

### Uso de Eventos Personalizados

Para usar estos eventos en tu código, importa las funciones desde `analytics.js`:

```javascript
import { analyticsEvents } from './utils/analytics';

// Ejemplo: Rastrear cuando se cambia el mes
analyticsEvents.filterMonth('Enero');

// Ejemplo: Rastrear cuando se exporta un PDF
analyticsEvents.exportPDF({
  mes: 11,
  anio: 2025,
  tipo_area: 'Distritos',
  total_rows: 50
});
```

## Desactivar Google Analytics

Si necesitas desactivar Google Analytics temporalmente:

1. Elimina o comenta la variable `REACT_APP_GA_MEASUREMENT_ID` en tu archivo `.env`
2. O establece el valor como: `REACT_APP_GA_MEASUREMENT_ID=`
3. Reconstruye la aplicación: `npm run build`

## Solución de Problemas

### Google Analytics no se inicializa

1. **Verifica que el ID esté correcto**: Debe comenzar con `G-` seguido de letras y números
2. **Verifica la consola del navegador**: Busca mensajes de error o advertencias
3. **Verifica que la variable de entorno esté configurada**: En desarrollo, asegúrate de que el archivo `.env` exista y tenga el formato correcto
4. **Reconstruye la aplicación**: Recuerda que las variables `REACT_APP_*` se inyectan en tiempo de compilación

### Los eventos no aparecen en Google Analytics

1. **Espera 24-48 horas**: Google Analytics puede tardar en mostrar los datos
2. **Verifica en tiempo real**: Ve a Google Analytics → Informes → Tiempo real para ver eventos inmediatos
3. **Verifica la consola del navegador**: Asegúrate de que no haya errores de JavaScript

### El script de Google Analytics no se carga

1. **Verifica tu conexión a internet**: El script se carga desde `googletagmanager.com`
2. **Verifica bloqueadores de anuncios**: Algunos bloqueadores pueden bloquear Google Analytics
3. **Verifica la consola del navegador**: Busca errores de red o CORS

## Recursos Adicionales

- [Documentación de Google Analytics 4](https://developers.google.com/analytics/devguides/collection/ga4)
- [Guía de eventos de Google Analytics](https://developers.google.com/analytics/devguides/collection/ga4/events)
- [React y Google Analytics](https://reactjs.org/docs/faq-ajax.html)

## Notas Importantes

- ⚠️ **Privacidad**: Asegúrate de cumplir con las leyes de privacidad de datos (GDPR, LGPD, etc.) al implementar Google Analytics
- ⚠️ **Producción**: No olvides configurar la variable de entorno en tu servidor de producción
- ⚠️ **Compilación**: Las variables `REACT_APP_*` solo están disponibles después de reconstruir la aplicación


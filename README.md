<<<<<<< HEAD
# Sistema de Análisis de Validaciones por Ciudad

Sistema web para visualizar y analizar validaciones de transporte público por distritos y barrios de Asunción y Departamento Central.

## 🚀 Características

- **Visualización interactiva**: Mapas con capas de datos geográficos usando Leaflet
- **Análisis de demanda y oferta**: Validaciones, pasajeros únicos, buses únicos por área
- **Franjas operativas dinámicas**: Consulta por diferentes horarios y tipos de día
- **Filtros avanzados**: Por criterio (validaciones, penetración, buses, empresas, líneas)
- **Exportación**: Descarga de reportes en formato PDF
- **Vista satelital**: Alternancia entre vista de calle y satelital

## 🛠️ Tecnologías

### Backend
- **Python 3.x**
- **Flask**: Framework web
- **PostgreSQL**: Base de datos
- **GeoPandas**: Procesamiento de datos geoespaciales
- **Folium**: Generación de mapas estáticos

### Frontend
- **React 19**
- **Leaflet / React-Leaflet**: Mapas interactivos
- **Axios**: Cliente HTTP
- **jsPDF / html2canvas**: Generación de PDFs

## 📋 Requisitos Previos

- Python 3.8+
- PostgreSQL
- Node.js 16+
- npm o yarn

## 🔧 Instalación

### Backend

1. Crear entorno virtual:
```bash
python -m venv entorno
```

2. Activar entorno virtual:
```bash
# Windows
entorno\Scripts\activate

# Linux/Mac
source entorno/bin/activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Configurar variables de entorno:
Crear archivo `.env` en la raíz del proyecto:
```
DB_HOST=tu_host
DB_NAME=tu_database
DB_USER=tu_usuario
DB_PASSWORD=tu_password
DB_PORT=5432

DB_RUTAS_HOST=tu_host_rutas
DB_RUTAS_NAME=tu_database_rutas
DB_RUTAS_USER=tu_usuario_rutas
DB_RUTAS_PASSWORD=tu_password_rutas
DB_RUTAS_PORT=5432
```

5. Ejecutar servidor:
```bash
python validaciones_por_ciudad.py
```

El servidor estará disponible en `http://localhost:5000`

### Frontend

1. Navegar al directorio del frontend:
```bash
cd REACT/validaciones-frontend
```

2. Instalar dependencias:
```bash
npm install
```

3. Iniciar servidor de desarrollo:
```bash
npm start
```

La aplicación estará disponible en `http://localhost:3000`

## 📁 Estructura del Proyecto

```
validaciones_por_ciudad/
├── validaciones_por_ciudad.py    # Aplicación Flask principal
├── requirements.txt               # Dependencias Python
├── cache_validaciones/            # Cache de consultas procesadas
├── CIUDADES/                     # Shapefiles y datos geográficos
├── REACT/
│   └── validaciones-frontend/    # Aplicación React
│       ├── src/
│       │   ├── App.js            # Componente principal
│       │   └── App.css           # Estilos
│       └── public/               # Archivos estáticos
└── README.md                     # Este archivo
```

## 🔐 Seguridad

⚠️ **IMPORTANTE**: Nunca subas archivos `.env` con credenciales a GitHub. El archivo `.gitignore` ya está configurado para excluir estos archivos.

## 📝 Uso

1. Selecciona mes, año y franja operativa
2. Opcionalmente marca "Incluir Barrios" para análisis más detallado
3. Haz clic en "Obtener Datos"
4. Visualiza los resultados en el mapa y la tabla
5. Usa los filtros para ordenar y buscar información específica
6. Descarga reportes en PDF cuando necesites

## 🤝 Contribución

Este proyecto es desarrollado por el equipo CID-DMT-VMT del Ministerio de Obras Públicas y Comunicaciones de Paraguay.

## 📄 Licencia

Copyright © 2025 Ministerio de Obras Públicas y Comunicaciones - Paraguay

Desarrollado por equipo CID-DMT-VMT

=======
# validaciones-por-ciudad
Sistema de validacion por Ciudad y Barrio - zona asuncion y central
>>>>>>> 9c8f8a10a37e600b8201a588eb3ca4b9ad991a62

# Guía de Instalación en Rocky Linux con Docker

Esta guía explica cómo instalar y desplegar el Sistema de Análisis de Validaciones en una máquina virtual Rocky Linux usando Docker.

## Requisitos Previos

- Rocky Linux 10.1 o superior
- Docker CE instalado y funcionando
- Docker Compose instalado
- Acceso a las bases de datos PostgreSQL (validaciones y rutas)

## Paso 1: Instalar Docker Compose

Si aún no tienes Docker Compose instalado:

```bash
# Instalar Docker Compose V2 (incluido en Docker CE desde versiones recientes)
sudo dnf install docker-compose-plugin -y

# O instalar Docker Compose V1 (si prefieres la versión clásica)
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

Verificar instalación:
```bash
docker compose version
# o
docker-compose --version
```

## Paso 2: Clonar o Copiar el Repositorio

```bash
# Opción 1: Si tienes el repositorio en GitHub
cd /opt
sudo git clone https://github.com/hatoweb/validaciones-por-ciudad.git
cd validaciones-por-ciudad

# Opción 2: Si copias los archivos manualmente
# Crea el directorio y copia todos los archivos del proyecto
```

## Paso 3: Configurar Variables de Entorno

```bash
# Copiar el archivo de ejemplo
cp env.example .env

# Editar el archivo .env con tus credenciales
nano .env
```

Edita el archivo `.env` con tus datos reales de conexión a PostgreSQL:

```env
DB_HOST=ip_o_host_de_tu_servidor_postgresql
DB_NAME=nombre_base_datos_validaciones
DB_USER=usuario_postgresql
DB_PASSWORD=password_segura
DB_PORT=5432

DB_RUTAS_HOST=ip_o_host_de_tu_servidor_postgresql_rutas
DB_RUTAS_NAME=nombre_base_datos_rutas
DB_RUTAS_USER=usuario_postgresql_rutas
DB_RUTAS_PASSWORD=password_segura_rutas
DB_RUTAS_PORT=5432
```

## Paso 4: Verificar Estructura de Directorios

Asegúrate de que la estructura de directorios sea correcta:

```
validaciones_por_ciudad/
├── validaciones_por_ciudad.py
├── requirements.txt
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
├── nginx.conf
├── .env
├── CIUDADES/
│   ├── ASUNCION/
│   ├── DPTO_CENTRAL/
│   └── ...
└── REACT/
    └── validaciones-frontend/
        ├── package.json
        ├── src/
        └── public/
```

## Paso 5: Construir y Ejecutar los Contenedores

```bash
# Construir las imágenes (primera vez o después de cambios)
docker compose build

# O en modo detached (en segundo plano)
docker compose up -d --build

# Ver logs en tiempo real
docker compose logs -f

# Ver logs de un servicio específico
docker compose logs -f backend
docker compose logs -f frontend
```

## Paso 6: Verificar que Todo Funciona

```bash
# Verificar que los contenedores están corriendo
docker compose ps

# Deberías ver algo como:
# NAME                    STATUS          PORTS
# validaciones-backend    Up (healthy)    0.0.0.0:5000->5000/tcp
# validaciones-frontend   Up (healthy)    0.0.0.0:80->80/tcp

# Probar el backend
curl http://localhost:5000/api/franjas_operativas

# Probar el frontend
curl http://localhost/
```

## Paso 7: Acceder al Sistema

- **Frontend**: http://tu_ip_servidor o http://localhost
- **Backend API**: http://tu_ip_servidor:5000

## Comandos Útiles

### Detener los servicios
```bash
docker compose down
```

### Detener y eliminar volúmenes (⚠️ elimina el cache)
```bash
docker compose down -v
```

### Reiniciar un servicio específico
```bash
docker compose restart backend
docker compose restart frontend
```

### Ver logs de los servicios
```bash
docker compose logs backend
docker compose logs frontend
docker compose logs --tail=100 -f  # Últimas 100 líneas y seguir
```

### Ejecutar comandos dentro del contenedor
```bash
# Backend
docker compose exec backend bash
docker compose exec backend python -c "import geopandas; print(geopandas.__version__)"

# Frontend
docker compose exec frontend sh
```

### Reconstruir después de cambios
```bash
# Reconstruir solo el backend
docker compose up -d --build backend

# Reconstruir solo el frontend
docker compose up -d --build frontend

# Reconstruir todo
docker compose up -d --build
```

## Configuración del Firewall (Firewalld)

Si usas firewalld en Rocky Linux:

```bash
# Permitir HTTP (puerto 80)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-port=5000/tcp

# Recargar firewall
sudo firewall-cmd --reload

# Verificar
sudo firewall-cmd --list-all
```

## Configuración de Nginx (si usas proxy inverso)

Si quieres usar un dominio y SSL, configura Nginx en el host:

```nginx
server {
    listen 80;
    server_name tu-dominio.com;

    location / {
        proxy_pass http://localhost:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Actualizar el Sistema

```bash
# 1. Detener los servicios
docker compose down

# 2. Hacer pull de cambios (si usas git)
git pull

# 3. Reconstruir
docker compose up -d --build

# 4. Verificar logs
docker compose logs -f
```

## Solución de Problemas

### Problema: El contenedor no inicia
```bash
# Ver logs detallados
docker compose logs backend
docker compose logs frontend

# Verificar variables de entorno
docker compose config
```

### Problema: Error de conexión a base de datos
- Verifica que `.env` tiene las credenciales correctas
- Verifica que PostgreSQL está accesible desde el contenedor
- Prueba la conexión manualmente:
```bash
docker compose run --rm backend python -c "import psycopg2; conn = psycopg2.connect(host='DB_HOST', ...)"
```

### Problema: Error de GDAL/GeoPandas
- Verifica que las dependencias del sistema están instaladas en el Dockerfile
- Reconstruye la imagen: `docker compose build --no-cache backend`

### Problema: Frontend no se conecta al backend
- Verifica que ambos contenedores están en la misma red: `docker network ls`
- Verifica la configuración de proxy en `nginx.conf`

## Monitoreo y Mantenimiento

### Ver uso de recursos
```bash
docker stats
```

### Limpiar imágenes y contenedores no usados
```bash
docker system prune -a
```

### Backup del cache
```bash
# El cache está montado como volumen, hacer backup es copiar el directorio
cp -r cache_validaciones cache_validaciones_backup_$(date +%Y%m%d)
```

## Servicio del Sistema (Opcional)

Para que el sistema inicie automáticamente al reiniciar el servidor:

```bash
# Crear un servicio systemd
sudo nano /etc/systemd/system/validaciones.service
```

Contenido del servicio:

```ini
[Unit]
Description=Sistema de Validaciones Docker Compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/validaciones-por-ciudad
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Habilitar el servicio:
```bash
sudo systemctl daemon-reload
sudo systemctl enable validaciones.service
sudo systemctl start validaciones.service
```

## Soporte

Para más ayuda, consulta los logs o revisa la documentación en el README.md


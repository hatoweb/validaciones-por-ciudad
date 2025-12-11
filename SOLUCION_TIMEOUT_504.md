# Solución para Error 504 Gateway Timeout

## Problema
Nginx está cerrando la conexión antes de que el backend termine de procesar consultas largas, generando el error:
```
504 Gateway Time-out
```

## Solución Implementada

Se aumentaron los timeouts de Nginx para permitir consultas que pueden tardar hasta 30 minutos:

- **Timeout de conexión**: 1800 segundos (30 minutos)
- **Timeout de lectura**: 1800 segundos (30 minutos)
- **Timeout de escritura**: 1800 segundos (30 minutos)
- **Buffering desactivado**: Para respuestas grandes en tiempo real

**IMPORTANTE**: También se configuró el timeout de PostgreSQL (`statement_timeout`) a 30 minutos para coincidir con los timeouts de Nginx.

## Cambios Realizados

### 1. Archivo `nginx.conf`

Se agregaron las siguientes configuraciones en las ubicaciones `/api` y `/obtener_datos`:

```nginx
# Timeouts aumentados para consultas largas (30 minutos)
proxy_connect_timeout 1800s;
proxy_send_timeout 1800s;
proxy_read_timeout 1800s;
send_timeout 1800s;

# Buffers para respuestas grandes
proxy_buffering off;
proxy_request_buffering off;
```

## Aplicar los Cambios

### Paso 1: Actualizar el código en el servidor

```bash
cd /opt/validaciones-por-ciudad
sudo git pull origin main
```

### Paso 2: Reconstruir el contenedor del frontend

```bash
# Detener los contenedores
sudo docker compose down

# Reconstruir el frontend con la nueva configuración de Nginx
sudo docker compose build frontend

# Levantar los contenedores nuevamente
sudo docker compose up -d

# Verificar que están corriendo
sudo docker compose ps
```

**Nota**: Si tu usuario está en el grupo `docker`, puedes omitir `sudo` en los comandos de Docker.

### Paso 3: Verificar los logs

```bash
# Ver logs del frontend para verificar que Nginx inició correctamente
sudo docker compose logs frontend

# Ver logs del backend
sudo docker compose logs backend
```

### Paso 4: Actualizar el Proxy Externo (IMPORTANTE)

El error 504 que estás viendo probablemente viene del **proxy externo** (nginx en `sistemas.mopc.gov.py`), no del contenedor. Necesitas actualizar también el proxy externo con los mismos timeouts:

```nginx
location /validaciones {
    proxy_pass http://IP_DEL_CONTENEDOR:80/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # Timeouts aumentados para consultas largas (30 minutos)
    proxy_connect_timeout 1800s;
    proxy_send_timeout 1800s;
    proxy_read_timeout 1800s;
    send_timeout 1800s;
    
    # Buffers para respuestas grandes
    proxy_buffering off;
    proxy_request_buffering off;
}
```

**Después de actualizar el proxy externo, recargar la configuración de nginx:**
```bash
sudo nginx -t  # Verificar sintaxis
sudo systemctl reload nginx  # O sudo service nginx reload
```

### Paso 5: Probar la consulta

Desde el navegador, intenta hacer una consulta nuevamente. Ahora debería esperar hasta 30 minutos antes de dar timeout.

## Nota Importante

Si las consultas continúan tardando más de 30 minutos, considera:

1. **Optimizar las consultas** en PostgreSQL
2. **Usar el sistema de cache** que ya está implementado
3. **Verificar los logs del backend** para ver el tiempo exacto que toma la consulta (ver logging detallado)
4. **Aumentar aún más los timeouts** si es necesario (editar `nginx.conf` y el proxy externo)

## Verificar Timeouts Actuales

Para verificar los timeouts configurados en Nginx:

```bash
# Entrar al contenedor del frontend
sudo docker exec -it validaciones-frontend sh

# Ver la configuración de Nginx
cat /etc/nginx/conf.d/default.conf | grep timeout

# Salir
exit
```

## Timeouts Configurados Actualmente

- **Nginx interno (contenedor)**: 1800 segundos (30 minutos)
- **PostgreSQL statement_timeout**: 1800000 ms (30 minutos)
- **Proxy externo**: Debe configurarse también a 1800 segundos

## Verificar Tiempo Real de Consulta

El backend ahora registra en los logs el tiempo exacto que toma cada consulta:

```bash
sudo docker compose logs -f backend
```

Verás mensajes como:
```
[2024-01-15 10:30:00] Iniciando conexión a base de datos...
[2024-01-15 10:30:02] ✓ Conexión establecida en 2.15 segundos
[2024-01-15 10:30:02] Ejecutando consulta SQL...
[2024-01-15 10:32:45] ✓ Consulta completada en 163.23 segundos (Total: 165.38 segundos)
```

Si ves un timeout, los logs mostrarán exactamente cuánto tiempo transcurrió antes de cortarse:
```
[2024-01-15 10:30:02] ❌ TIMEOUT: La consulta fue cancelada después de 900.15 segundos
```



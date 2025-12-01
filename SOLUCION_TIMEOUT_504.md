# Solución para Error 504 Gateway Timeout

## Problema
Nginx está cerrando la conexión antes de que el backend termine de procesar consultas largas, generando el error:
```
504 Gateway Time-out
```

## Solución Implementada

Se aumentaron los timeouts de Nginx para permitir consultas que pueden tardar varios minutos:

- **Timeout de conexión**: 600 segundos (10 minutos)
- **Timeout de lectura**: 600 segundos (10 minutos)
- **Timeout de escritura**: 600 segundos (10 minutos)
- **Buffering desactivado**: Para respuestas grandes en tiempo real

## Cambios Realizados

### 1. Archivo `nginx.conf`

Se agregaron las siguientes configuraciones en las ubicaciones `/api` y `/obtener_datos`:

```nginx
# Timeouts aumentados para consultas largas (10 minutos)
proxy_connect_timeout 600s;
proxy_send_timeout 600s;
proxy_read_timeout 600s;
send_timeout 600s;

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
docker compose down

# Reconstruir el frontend con la nueva configuración de Nginx
docker compose build frontend

# Levantar los contenedores nuevamente
docker compose up -d

# Verificar que están corriendo
docker compose ps
```

### Paso 3: Verificar los logs

```bash
# Ver logs del frontend para verificar que Nginx inició correctamente
docker compose logs frontend

# Ver logs del backend
docker compose logs backend
```

### Paso 4: Probar la consulta

Desde el navegador, intenta hacer una consulta nuevamente. Ahora debería esperar hasta 10 minutos antes de dar timeout.

## Nota Importante

Si las consultas continúan tardando más de 10 minutos, considera:

1. **Optimizar las consultas** en PostgreSQL
2. **Usar el sistema de cache** que ya está implementado
3. **Aumentar aún más los timeouts** si es necesario (editar `nginx.conf`)

## Verificar Timeouts Actuales

Para verificar los timeouts configurados en Nginx:

```bash
# Entrar al contenedor del frontend
docker exec -it validaciones-frontend sh

# Ver la configuración de Nginx
cat /etc/nginx/conf.d/default.conf | grep timeout

# Salir
exit
```

## Alternativa: Timeout más largo

Si necesitas más de 10 minutos, puedes cambiar `600s` por un valor mayor, por ejemplo:

- `900s` = 15 minutos
- `1200s` = 20 minutos
- `1800s` = 30 minutos

Solo recuerda que timeouts muy largos pueden afectar la experiencia del usuario. Es mejor optimizar las consultas.


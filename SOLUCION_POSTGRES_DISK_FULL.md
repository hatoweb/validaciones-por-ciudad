# Solución para el Error de PostgreSQL "No space left on device"

## Problema
PostgreSQL está intentando escribir archivos temporales pero no puede hacerlo, generando el error:
```
could not write to file "base/pgsql_tmp/pgsql_tmp32259.0": No space left on device
```

## Diagnóstico
Aunque el servidor tiene espacio disponible (55.6GB libres), PostgreSQL no puede escribir archivos temporales. Esto puede deberse a:

1. **Volumen Docker lleno**: El volumen Docker donde está PostgreSQL puede tener un límite
2. **Archivos temporales bloqueados**: Archivos temporales antiguos que no se limpiaron
3. **Problema con el directorio temporal**: Permisos o configuración incorrecta

## Solución Paso a Paso

### Paso 1: Conectarse al servidor de PostgreSQL (168.90.177.232)

```bash
ssh usuario@168.90.177.232
```

### Paso 2: Entrar al contenedor de PostgreSQL

```bash
docker exec -it bbdd-informes bash
```

### Paso 3: Limpiar archivos temporales de PostgreSQL

```bash
# Salir del contenedor si estás dentro
exit

# Desde el servidor, limpiar archivos temporales antiguos
docker exec bbdd-informes find /var/lib/postgresql/data/base/pgsql_tmp -type f -mmin +60 -delete

# Verificar que se limpiaron
docker exec bbdd-informes ls -lah /var/lib/postgresql/data/base/pgsql_tmp/
```

### Paso 4: Reiniciar el contenedor de PostgreSQL

```bash
# Detener PostgreSQL
docker stop bbdd-informes

# Esperar 10 segundos
sleep 10

# Iniciar PostgreSQL
docker start bbdd-informes

# Verificar que está corriendo
docker ps | grep bbdd-informes

# Ver logs para verificar que inició correctamente
docker logs bbdd-informes --tail 50
```

### Paso 5: Verificar espacio del volumen Docker

```bash
# Ver uso de espacio de Docker
docker system df -v

# Ver tamaño del volumen de PostgreSQL
docker inspect bbdd-informes | grep -A 10 Mounts
```

### Paso 6: Si el problema persiste - Optimizar la consulta

El problema puede ser que la consulta está generando archivos temporales muy grandes. Podemos optimizar ajustando `work_mem` en PostgreSQL:

```bash
# Entrar al contenedor
docker exec -it bbdd-informes bash

# Conectarse a PostgreSQL
psql -U postgres

# Ver configuración actual
SHOW work_mem;
SHOW temp_file_limit;

# Si work_mem es muy alto, reducirlo temporalmente
ALTER SYSTEM SET work_mem = '16MB';
SELECT pg_reload_conf();

# Salir
\q
exit
```

### Paso 7: Probar desde el backend

Después de reiniciar PostgreSQL, probar desde el servidor donde está el backend:

```bash
# En el servidor Rocky Linux (172.16.222.222)
curl -X POST http://localhost:5000/api/validaciones \
  -H "Content-Type: application/json" \
  -d '{"mes": 11, "anio": 2025, "id_franja": 30, "incluir_barrios": true}'
```

## Alternativa: Usar cache cuando sea posible

Si el problema persiste, el sistema usará el cache cuando esté disponible. Asegúrate de que el directorio de cache tenga suficiente espacio:

```bash
# En el servidor donde está el backend
df -h /opt/validaciones-por-ciudad/cache_validaciones
```

## Nota Importante

El error `DiskFull` es crítico y requiere atención inmediata del administrador de la base de datos. Si el problema persiste después de estos pasos, puede ser necesario:

1. Expandir el volumen Docker
2. Limpiar datos antiguos de la base de datos
3. Optimizar las consultas para usar menos memoria temporal


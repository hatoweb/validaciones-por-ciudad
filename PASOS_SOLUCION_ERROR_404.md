# Pasos para Solucionar el Error 404 en /api/validaciones

## Problema Identificado

El backend está funcionando correctamente, pero cuando intentas consultar validaciones, obtienes un error 404. El problema real es que PostgreSQL no puede escribir archivos temporales:

```
could not write to file "base/pgsql_tmp/pgsql_tmp32259.0": No space left on device
```

## Solución Inmediata

### 1. Reiniciar el contenedor de PostgreSQL

En el servidor donde está PostgreSQL (168.90.177.232), ejecuta:

```bash
# Reiniciar el contenedor
docker restart bbdd-informes

# Verificar que está corriendo
docker ps | grep bbdd-informes

# Ver logs
docker logs bbdd-informes --tail 30
```

### 2. Limpiar archivos temporales de PostgreSQL

```bash
# Limpiar archivos temporales antiguos
docker exec bbdd-informes find /var/lib/postgresql/data/base/pgsql_tmp -type f -delete

# Verificar que el directorio está limpio
docker exec bbdd-informes ls -lah /var/lib/postgresql/data/base/pgsql_tmp/
```

### 3. Reiniciar el backend

En el servidor donde está el backend (Rocky Linux), ejecuta:

```bash
cd /opt/validaciones-por-ciudad

# Reiniciar el backend
docker compose restart backend

# Ver logs
docker compose logs -f backend
```

### 4. Probar nuevamente

Desde el navegador, intenta hacer una consulta nuevamente. El error ahora debería mostrar un mensaje más claro indicando que hay un problema con el espacio en disco de PostgreSQL.

## Cambios Realizados en el Código

He mejorado el manejo de errores en el backend para que:

1. **Detecte específicamente errores de espacio en disco** de PostgreSQL
2. **Devuelva código HTTP 500** (en lugar de 404) cuando hay un error de base de datos
3. **Muestre mensajes de error más claros** al usuario

## Si el Problema Persiste

Si después de reiniciar PostgreSQL y el backend el problema continúa:

### Opción A: Verificar volumen Docker de PostgreSQL

```bash
# En el servidor de PostgreSQL (168.90.177.232)
docker system df -v
docker inspect bbdd-informes | grep -A 10 Mounts
```

### Opción B: Optimizar consulta reduciendo work_mem

```bash
# Entrar al contenedor de PostgreSQL
docker exec -it bbdd-informes bash

# Conectarse a PostgreSQL
psql -U postgres

# Reducir work_mem para generar menos archivos temporales
ALTER SYSTEM SET work_mem = '16MB';
SELECT pg_reload_conf();

# Salir
\q
exit
```

### Opción C: Usar datos en cache

El sistema automáticamente usará datos en cache cuando estén disponibles. Si ya consultaste los datos antes, deberían estar en cache.

## Próximos Pasos

1. ✅ **Ejecutar los pasos 1-3 arriba** (reiniciar PostgreSQL y backend)
2. ✅ **Probar desde el navegador** nuevamente
3. ✅ **Si el error persiste**, ejecutar las opciones A, B o C según corresponda
4. ✅ **Compartir los resultados** para diagnóstico adicional si es necesario


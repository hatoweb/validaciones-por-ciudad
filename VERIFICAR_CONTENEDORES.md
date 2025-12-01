# Comandos para Verificar el Estado de los Contenedores

Ejecuta estos comandos en el servidor donde está desplegado el sistema (probablemente el servidor Rocky Linux con IP 172.16.222.222):

## 1. Verificar estado de los contenedores

```bash
# Ver todos los contenedores (corriendo y detenidos)
docker ps -a

# Ver solo contenedores corriendo
docker ps

# Ver logs del backend
docker logs validaciones-backend --tail 50

# Ver logs del frontend
docker logs validaciones-frontend --tail 50
```

## 2. Verificar si el backend está respondiendo

```bash
# Probar desde dentro del contenedor del frontend
docker exec -it validaciones-frontend wget -O- http://backend:5000/api/franjas_operativas

# O desde fuera del contenedor, probar directamente el backend
curl http://localhost:5000/api/franjas_operativas

# O si tienes acceso SSH al servidor
curl http://172.16.222.222:5000/api/franjas_operativas
```

## 3. Verificar la red Docker

```bash
# Ver la red
docker network ls

# Inspeccionar la red
docker network inspect validaciones-network

# Verificar que ambos contenedores estén en la misma red
docker inspect validaciones-backend | grep -A 10 Networks
docker inspect validaciones-frontend | grep -A 10 Networks
```

## 4. Reiniciar los contenedores si es necesario

```bash
# Detener todos los contenedores
docker compose down

# Volver a levantarlos
docker compose up -d

# Ver logs en tiempo real
docker compose logs -f
```

## 5. Verificar conexión del backend a la base de datos

```bash
# Ver logs del backend buscando errores de conexión
docker logs validaciones-backend 2>&1 | grep -i "error\|connection\|database"
```


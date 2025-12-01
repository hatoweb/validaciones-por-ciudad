# Solución para Error 403 Forbidden

## Problema

Después de configurar la subruta `/validaciones/`, aparece el error:
```
403 Forbidden
nginx/1.29.3
```

## Causa

El error 403 puede ser causado por:

1. **Configuración incorrecta de `alias` en Nginx**: El uso de `alias` con rutas que no terminan en `/` puede causar problemas
2. **Permisos incorrectos**: Nginx no puede leer los archivos
3. **Conflicto con el proxy reverso externo**: El proxy puede estar removiendo el prefijo incorrectamente

## Solución

### Paso 1: Actualizar la configuración de Nginx

La configuración ha sido simplificada para usar `location /validaciones/` (con barra final) que funciona mejor con `alias`.

### Paso 2: Reconstruir y reiniciar

```bash
cd /opt/validaciones-por-ciudad

# Actualizar código
sudo git pull origin main

# Detener contenedores
docker compose down

# Reconstruir frontend
docker compose build frontend

# Levantar contenedores
docker compose up -d

# Verificar logs
docker compose logs frontend --tail 50
```

### Paso 3: Verificar permisos en el contenedor

```bash
# Entrar al contenedor
docker exec -it validaciones-frontend sh

# Verificar permisos
ls -la /usr/share/nginx/html/
ls -la /usr/share/nginx/html/index.html

# Verificar que Nginx puede leer los archivos
cat /usr/share/nginx/html/index.html | head -5

# Salir
exit
```

### Paso 4: Verificar configuración del proxy reverso externo

El proxy reverso externo (en `sistemas.mopc.gov.py`) debe estar configurado para:

**Opción recomendada: Mantener el prefijo**
```nginx
location /validaciones {
    proxy_pass http://IP_DEL_CONTENEDOR:80;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

**IMPORTANTE**: El `proxy_pass` debe apuntar directamente a `http://IP:80` (o el puerto donde corre el contenedor) y **NO** debe tener una barra final que remueva el prefijo.

### Paso 5: Verificar que el HTML tiene las rutas correctas

```bash
docker exec validaciones-frontend cat /usr/share/nginx/html/index.html | grep -E "(href|src)" | head -5
```

Deberías ver rutas que empiecen con `/validaciones/`.

## Troubleshooting

### Si el error 403 persiste:

1. **Ver logs detallados de Nginx:**
```bash
docker exec validaciones-frontend cat /var/log/nginx/error.log
```

2. **Probar acceso directo al contenedor:**
```bash
# Desde el servidor donde está el contenedor
curl http://localhost/validaciones/
```

3. **Verificar que los archivos existen:**
```bash
docker exec validaciones-frontend ls -la /usr/share/nginx/html/
docker exec validaciones-frontend ls -la /usr/share/nginx/html/static/
```

4. **Probar con configuración mínima:**
   - Si nada funciona, el problema puede estar en el proxy reverso externo
   - Contacta al administrador del proxy para verificar la configuración

## Nota sobre el Proxy Reverso

Si el proxy reverso externo está **removiendo el prefijo** `/validaciones` antes de enviarlo al contenedor, entonces el contenedor recibirá peticiones en la raíz `/`. En ese caso:

1. El contenedor debe servir desde `/` (no desde `/validaciones/`)
2. React debe seguir teniendo `homepage: "/validaciones"` para generar las rutas correctas en el HTML
3. El proxy debe remover el prefijo: `proxy_pass http://IP:80/;` (con barra final)

Pero esta opción es más compleja y menos recomendada.


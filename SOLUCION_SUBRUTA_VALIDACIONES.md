# Solución para Servir la Aplicación desde /validaciones/

## Problema

La aplicación está accesible en `https://sistemas.mopc.gov.py/validaciones/` pero los archivos estáticos (CSS, JS, manifest.json) dan error 404 porque están buscando en la raíz en lugar de `/validaciones/`.

## Solución

### Paso 1: Configurar React para la subruta

Ya agregamos `"homepage": "/validaciones"` al `package.json`. Esto hará que React genere las rutas correctas con el prefijo `/validaciones/`.

### Paso 2: Reconstruir el frontend

**En tu máquina local o en el servidor:**

```bash
cd /opt/validaciones-por-ciudad

# Actualizar código
sudo git pull origin main

# Reconstruir el frontend con la nueva configuración
docker compose build frontend

# Reiniciar los contenedores
docker compose down
docker compose up -d
```

### Paso 3: Verificar el proxy reverso externo

El proxy reverso externo (que sirve `sistemas.mopc.gov.py`) debe estar configurado para:

**Opción A: Mantener el prefijo** (recomendado)
```nginx
location /validaciones {
    proxy_pass http://contenedor:80;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

**Opción B: Remover el prefijo** (requiere configuración adicional)
```nginx
location /validaciones {
    proxy_pass http://contenedor:80/;
    rewrite ^/validaciones(.*)$ $1 break;
}
```

### Paso 4: Verificar que los archivos se generaron correctamente

Después de reconstruir, los archivos HTML deberían tener rutas como:
- `/validaciones/static/css/main.xxx.css`
- `/validaciones/static/js/main.xxx.js`
- `/validaciones/manifest.json`

## Verificación

1. **Verificar el HTML generado:**
```bash
docker exec validaciones-frontend cat /usr/share/nginx/html/index.html | grep -E "(css|js|manifest)"
```

Deberías ver rutas que empiecen con `/validaciones/`.

2. **Probar acceso directo:**
```
https://sistemas.mopc.gov.py/validaciones/
https://sistemas.mopc.gov.py/validaciones/static/css/main.xxx.css
```

## Nota sobre el Proxy Reverso Externo

Si el proxy reverso externo está configurado para **remover el prefijo** antes de enviar al contenedor, necesitarás una configuración diferente de Nginx. En ese caso, contacta al administrador del proxy reverso o ajusta la configuración según sea necesario.

## Troubleshooting

### Si los archivos siguen sin cargar:

1. **Verificar que el `homepage` está en package.json:**
```bash
cat REACT/validaciones-frontend/package.json | grep homepage
```

Debe mostrar: `"homepage": "/validaciones"`

2. **Limpiar el build anterior:**
```bash
# En el servidor
docker compose down
docker volume prune -f
docker compose build --no-cache frontend
docker compose up -d
```

3. **Ver logs del frontend:**
```bash
docker compose logs frontend
```

4. **Verificar configuración del proxy reverso externo:**
   - Asegúrate de que el proxy reverso externo está direccionando correctamente
   - Verifica que no esté removiendo o duplicando el prefijo `/validaciones`


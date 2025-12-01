# Solución: Proxy Reverso Remueve el Prefijo

## Problema

El proxy reverso externo está **removiendo el prefijo** `/validaciones` antes de enviar las peticiones al contenedor. Por lo tanto:

- **Navegador pide**: `https://sistemas.mopc.gov.py/validaciones/static/css/main.xxx.css`
- **Proxy remueve** `/validaciones` y envía al contenedor: `/static/css/main.xxx.css`
- **Contenedor no encuentra** porque está buscando en `/validaciones/static/...`

## Solución Implementada

La configuración de Nginx ahora sirve **todo desde la raíz** (`/`), porque el proxy externo ya removió el prefijo.

### Cómo funciona:

1. **React genera HTML con rutas** `/validaciones/static/...` (gracias a `homepage: "/validaciones"` en package.json)
2. **Navegador pide** `/validaciones/static/...` al servidor principal
3. **Proxy reverso remueve** `/validaciones` y reenvía `/static/...` al contenedor
4. **Contenedor sirve** desde `/static/...` (configurado en nginx.conf)

## Configuración del Proxy Reverso Externo

El proxy reverso externo debe estar configurado así:

```nginx
location /validaciones {
    proxy_pass http://IP_DEL_CONTENEDOR:80/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # Remover el prefijo /validaciones
    rewrite ^/validaciones(.*)$ $1 break;
}
```

**Nota**: La barra final en `proxy_pass http://IP:80/;` y el `rewrite` remueven el prefijo.

## Pasos para Aplicar

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

# Verificar
docker compose ps
docker compose logs frontend --tail 20
```

## Verificación

1. **Verificar que los archivos estáticos se sirven:**
```bash
# Desde el servidor donde está el contenedor
curl http://localhost/static/css/main.*.css | head -5
curl http://localhost/manifest.json
```

2. **Verificar que el HTML tiene las rutas correctas:**
```bash
docker exec validaciones-frontend cat /usr/share/nginx/html/index.html | grep -E "(href|src)" | head -5
```

Deberías ver rutas con `/validaciones/static/...` en el HTML.

## Flujo Completo

```
Usuario → https://sistemas.mopc.gov.py/validaciones/
         ↓
Proxy Reverso (remueve /validaciones)
         ↓
Contenedor recibe: /
         ↓
Nginx sirve: /usr/share/nginx/html/index.html
         ↓
HTML generado tiene: /validaciones/static/css/main.xxx.css
         ↓
Navegador pide: https://sistemas.mopc.gov.py/validaciones/static/css/main.xxx.css
         ↓
Proxy remueve /validaciones → /static/css/main.xxx.css
         ↓
Contenedor sirve: /usr/share/nginx/html/static/css/main.xxx.css ✓
```

## Troubleshooting

### Si los archivos siguen sin cargar:

1. **Verificar configuración del proxy reverso:**
   - Asegúrate de que está removiendo el prefijo correctamente
   - Verifica que `proxy_pass` tiene la barra final `/`

2. **Probar acceso directo al contenedor:**
```bash
# Ver IP del contenedor
docker inspect validaciones-frontend | grep IPAddress

# Probar (reemplaza con la IP real)
curl http://172.x.x.x/static/css/main.*.css
```

3. **Ver logs de Nginx:**
```bash
docker exec validaciones-frontend cat /var/log/nginx/access.log | tail -10
docker exec validaciones-frontend cat /var/log/nginx/error.log | tail -10
```

4. **Verificar que los archivos existen:**
```bash
docker exec validaciones-frontend ls -la /usr/share/nginx/html/static/css/
docker exec validaciones-frontend ls -la /usr/share/nginx/html/
```


# Guía para Subir el Proyecto a GitHub desde Cursor

## Paso 1: Verificar/Instalar Git

Si Git no está instalado, descárgalo desde: https://git-scm.com/download/win

## Paso 2: Inicializar el Repositorio Git

Abre la terminal en Cursor (Ctrl + `) y ejecuta:

```bash
cd c:\Users\hato_\Desktop\docker\validaciones_por_ciudad
git init
```

## Paso 3: Configurar Git (solo la primera vez)

```bash
git config --global user.name "Tu Nombre"
git config --global user.email "tu.email@ejemplo.com"
```

## Paso 4: Agregar Archivos

```bash
git add .
```

## Paso 5: Hacer el Primer Commit

```bash
git commit -m "Initial commit: Sistema de análisis de validaciones"
```

## Paso 6: Crear Repositorio en GitHub

1. Ve a https://github.com y crea una cuenta (si no tienes)
2. Haz clic en el botón "+" (arriba derecha) → "New repository"
3. Dale un nombre al repositorio (ej: `validaciones-por-ciudad`)
4. **NO** marques "Initialize with README" (ya tenemos uno)
5. Haz clic en "Create repository"

## Paso 7: Conectar con GitHub

GitHub te mostrará comandos. Ejecuta estos (reemplaza `TU_USUARIO` con tu usuario de GitHub):

```bash
git remote add origin https://github.com/TU_USUARIO/TU_REPOSITORIO.git
git branch -M main
git push -u origin main
```

## Paso 8: Verificar

Ve a tu repositorio en GitHub y verifica que todos los archivos se hayan subido correctamente.

## ✅ Listo

Tu proyecto ahora está en GitHub. Para futuros cambios:

```bash
git add .
git commit -m "Descripción de los cambios"
git push
```

## ⚠️ Importante

- El archivo `.gitignore` ya está configurado para **NO subir**:
  - Archivos `.env` (con credenciales)
  - Directorio `entorno/` (entorno virtual)
  - `cache_validaciones/` (archivos de cache)
  - `node_modules/` (dependencias de Node)
  - Archivos de backup

- **Nunca** subas archivos con contraseñas o información sensible a GitHub.


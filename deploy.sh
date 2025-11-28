#!/bin/bash

# Script de despliegue para Rocky Linux
# Uso: ./deploy.sh

set -e

echo "========================================="
echo "Despliegue del Sistema de Validaciones"
echo "========================================="

# Verificar que Docker está corriendo
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker no está corriendo. Por favor inicia Docker."
    exit 1
fi

echo "✓ Docker está corriendo"

# Verificar que Docker Compose está disponible
if ! command -v docker compose &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: Docker Compose no está instalado."
    echo "Instala Docker Compose y vuelve a intentar."
    exit 1
fi

echo "✓ Docker Compose está disponible"

# Verificar que existe el archivo .env
if [ ! -f .env ]; then
    echo "⚠️  Advertencia: No se encontró el archivo .env"
    echo "Copiando .env.example a .env..."
    if [ -f env.example ]; then
        cp env.example .env
        echo "✓ Archivo .env creado. Por favor edítalo con tus credenciales antes de continuar."
        exit 1
    else
        echo "❌ Error: No se encontró .env.example"
        exit 1
    fi
fi

echo "✓ Archivo .env encontrado"

# Detener contenedores existentes (si hay)
echo "Deteniendo contenedores existentes..."
docker compose down 2>/dev/null || true

# Construir imágenes
echo "Construyendo imágenes Docker..."
docker compose build

# Iniciar servicios
echo "Iniciando servicios..."
docker compose up -d

# Esperar a que los servicios estén saludables
echo "Esperando a que los servicios estén listos..."
sleep 10

# Verificar estado
echo ""
echo "========================================="
echo "Estado de los servicios:"
echo "========================================="
docker compose ps

echo ""
echo "========================================="
echo "Despliegue completado!"
echo "========================================="
echo ""
echo "Frontend: http://localhost"
echo "Backend API: http://localhost:5000"
echo ""
echo "Para ver los logs:"
echo "  docker compose logs -f"
echo ""
echo "Para detener los servicios:"
echo "  docker compose down"
echo ""


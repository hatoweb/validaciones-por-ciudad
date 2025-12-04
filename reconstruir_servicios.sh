#!/bin/bash
# Script para reconstruir backend y frontend después de cambios

echo "=== Reconstruyendo servicios ==="

# Reconstruir backend (cambios en validaciones_por_ciudad.py)
echo "1. Reconstruyendo backend..."
sudo docker compose up -d --build backend

# Esperar un momento para que el backend inicie
echo "   Esperando que el backend inicie..."
sleep 5

# Verificar estado del backend
echo "2. Verificando estado del backend..."
sudo docker compose ps backend

# Reconstruir frontend (si hay cambios)
echo "3. Reconstruyendo frontend..."
sudo docker compose up -d --build frontend

# Verificar estado de ambos servicios
echo "4. Verificando estado de todos los servicios..."
sudo docker compose ps

echo ""
echo "=== Reconstrucción completada ==="
echo ""
echo "Para ver los logs:"
echo "  Backend:  sudo docker compose logs -f backend"
echo "  Frontend: sudo docker compose logs -f frontend"
echo "  Ambos:    sudo docker compose logs -f"


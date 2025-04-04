#!/bin/bash

set -e  # Остановить при ошибке

echo "🧹 Удаление старой сборки..."
rm -rf build

echo "📁 Создание каталога build..."
mkdir build
cd build

echo "⚙️ Генерация CMake-файлов..."
cmake ..

echo "🔨 Сборка проекта..."
make

echo "✅ Сборка завершена!"

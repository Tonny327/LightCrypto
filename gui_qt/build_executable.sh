#!/bin/bash
# Скрипт для сборки исполняемого файла LightCrypto GUI

set -e  # Остановка при ошибке

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Сборка LightCrypto GUI (PyQt6)              ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════╝${NC}"
echo ""

# Определяем пути
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GUI_QT_DIR="$SCRIPT_DIR"
BUILD_DIR="$PROJECT_ROOT/build"
DIST_DIR="$GUI_QT_DIR/dist"
VENV_DIR="$GUI_QT_DIR/venv"

echo -e "${YELLOW}📁 Директории:${NC}"
echo "  Проект: $PROJECT_ROOT"
echo "  GUI: $GUI_QT_DIR"
echo "  Build: $BUILD_DIR"
echo "  Dist: $DIST_DIR"
echo ""

# Проверка Python
echo -e "${YELLOW}🐍 Проверка Python...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 не найден!${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}✅ $PYTHON_VERSION${NC}"

# Проверка модуля venv
echo -e "${YELLOW}🔍 Проверка модуля venv...${NC}"
if ! python3 -m venv --help &> /dev/null; then
    echo -e "${RED}❌ Модуль venv не доступен!${NC}"
    PYTHON_VERSION_SHORT=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    echo -e "${YELLOW}💡 Установите python3-venv:${NC}"
    echo -e "${YELLOW}   sudo apt-get install python3-venv${NC}"
    echo -e "${YELLOW}   или для конкретной версии:${NC}"
    echo -e "${YELLOW}   sudo apt-get install python${PYTHON_VERSION_SHORT}-venv${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Модуль venv доступен${NC}"
echo ""

# Создание/активация виртуального окружения
echo -e "${YELLOW}🔧 Настройка виртуального окружения...${NC}"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}📦 Создание виртуального окружения...${NC}"
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✅ Виртуальное окружение создано${NC}"
else
    echo -e "${GREEN}✅ Виртуальное окружение уже существует${NC}"
fi

# Активация виртуального окружения
source "$VENV_DIR/bin/activate"
echo -e "${GREEN}✅ Виртуальное окружение активировано${NC}"
echo ""

# Обновление pip
echo -e "${YELLOW}📦 Обновление pip...${NC}"
pip install --upgrade pip --quiet
echo -e "${GREEN}✅ pip обновлен${NC}"
echo ""

# Установка зависимостей
echo -e "${YELLOW}📦 Установка зависимостей...${NC}"
if ! python -c "import PyQt6" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  PyQt6 не установлен. Устанавливаю...${NC}"
    pip install -r "$GUI_QT_DIR/requirements.txt" --quiet
    echo -e "${GREEN}✅ PyQt6 установлен${NC}"
else
    echo -e "${GREEN}✅ PyQt6 уже установлен${NC}"
fi

if ! python -c "import PyInstaller" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  PyInstaller не установлен. Устанавливаю...${NC}"
    pip install PyInstaller --quiet
    echo -e "${GREEN}✅ PyInstaller установлен${NC}"
else
    echo -e "${GREEN}✅ PyInstaller уже установлен${NC}"
fi
echo ""

# Проверка исполняемых файлов
echo -e "${YELLOW}🔍 Проверка исполняемых файлов...${NC}"
if [ ! -f "$BUILD_DIR/tap_encrypt" ]; then
    echo -e "${RED}❌ tap_encrypt не найден в $BUILD_DIR${NC}"
    echo -e "${YELLOW}💡 Запустите сборку проекта: cd $PROJECT_ROOT && mkdir -p build && cd build && cmake .. && make${NC}"
    exit 1
fi
if [ ! -f "$BUILD_DIR/tap_decrypt" ]; then
    echo -e "${RED}❌ tap_decrypt не найден в $BUILD_DIR${NC}"
    echo -e "${YELLOW}💡 Запустите сборку проекта: cd $PROJECT_ROOT && mkdir -p build && cd build && cmake .. && make${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Исполняемые файлы найдены${NC}"
echo ""

# Проверка CipherKeys
echo -e "${YELLOW}🔑 Проверка CipherKeys...${NC}"
CIPHER_KEYS_DIR="$PROJECT_ROOT/CipherKeys"
if [ ! -d "$CIPHER_KEYS_DIR" ]; then
    echo -e "${RED}❌ Директория CipherKeys не найдена!${NC}"
    exit 1
fi
CSV_COUNT=$(find "$CIPHER_KEYS_DIR" -name "*.csv" | wc -l)
echo -e "${GREEN}✅ Найдено $CSV_COUNT CSV файлов${NC}"
echo ""

# Очистка предыдущей сборки
echo -e "${YELLOW}🧹 Очистка предыдущей сборки...${NC}"
rm -rf "$DIST_DIR" "$GUI_QT_DIR/build" "$GUI_QT_DIR/__pycache__"
find "$GUI_QT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
# НЕ удаляем venv - он может быть переиспользован
echo -e "${GREEN}✅ Очистка завершена${NC}"
echo ""

# Сборка
echo -e "${YELLOW}🔨 Запуск PyInstaller...${NC}"
cd "$GUI_QT_DIR"
python -m PyInstaller \
    --clean \
    --noconfirm \
    lightcrypto.spec

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║           ✅ Сборка завершена успешно!            ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}📦 Исполняемый файл:${NC}"
    echo "  $DIST_DIR/lightcrypto"
    echo ""
    echo -e "${YELLOW}💡 Для запуска:${NC}"
    echo "  $DIST_DIR/lightcrypto"
    echo ""
    echo -e "${YELLOW}ℹ️  Примечание: Виртуальное окружение сохранено в $VENV_DIR${NC}"
    echo -e "${YELLOW}   Для повторной сборки можно использовать то же окружение${NC}"
    echo ""
else
    echo ""
    echo -e "${RED}╔═══════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║           ❌ Ошибка при сборке!                   ║${NC}"
    echo -e "${RED}╚═══════════════════════════════════════════════════╝${NC}"
    exit 1
fi

# Деактивация виртуального окружения (опционально)
deactivate 2>/dev/null || true


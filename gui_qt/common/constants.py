"""
LightCrypto GUI - Константы (PyQt6)
Цвета, размеры, пути и другие константы приложения
"""

import os

# === ПУТИ ===
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
GUI_ROOT = os.path.join(PROJECT_ROOT, 'gui_qt')
# Для совместимости с utils.py, который может ссылаться на старую структуру
GUI_ROOT_OLD = os.path.join(PROJECT_ROOT, 'gui')
BUILD_DIR = os.path.join(PROJECT_ROOT, 'build')
CIPHER_KEYS_DIR = os.path.join(PROJECT_ROOT, 'CipherKeys')
PROFILES_DIR = os.path.join(GUI_ROOT, 'profiles', 'custom_codec')

# Исполняемые файлы
TAP_ENCRYPT = os.path.join(BUILD_DIR, 'tap_encrypt')
TAP_DECRYPT = os.path.join(BUILD_DIR, 'tap_decrypt')
FILE_ENCODE = os.path.join(BUILD_DIR, 'file_encode')
FILE_DECODE = os.path.join(BUILD_DIR, 'file_decode')
FILE_ENCODE_PLAIN = os.path.join(BUILD_DIR, 'file_encode_plain')
FILE_DECODE_PLAIN = os.path.join(BUILD_DIR, 'file_decode_plain')
FILE_ENCODE_HYBRID = os.path.join(BUILD_DIR, 'file_encode_hybrid')
FILE_DECODE_HYBRID = os.path.join(BUILD_DIR, 'file_decode_hybrid')

# Скрипты setup
SETUP_TAP_A = os.path.join(PROJECT_ROOT, 'setup_tap_A.sh')
SETUP_TAP_B = os.path.join(PROJECT_ROOT, 'setup_tap_B.sh')

# === ЦВЕТОВАЯ ПАЛИТРА (Светлая тема - для совместимости) ===
COLOR_BACKGROUND = '#F5F5F5'  # Фон окна
COLOR_PANEL = '#FFFFFF'       # Панели
COLOR_SUCCESS = '#4CAF50'     # Успех (зеленый)
COLOR_INFO = '#2196F3'        # Информация (синий)
COLOR_WARNING = '#FFC107'     # Предупреждение (желтый)
COLOR_ERROR = '#F44336'       # Ошибка (красный)
COLOR_TEXT_PRIMARY = '#212121'   # Основной текст
COLOR_TEXT_SECONDARY = '#757575' # Вторичный текст

# Цвета кнопок
COLOR_LIBSODIUM = '#4CAF50'    # LibSodium (зеленый)
COLOR_CUSTOM = '#2196F3'       # Custom Codec (синий)
COLOR_ENCRYPT = '#81C784'      # Отправитель (светло-зеленый)
COLOR_DECRYPT = '#64B5F6'      # Получатель (светло-синий)

# Цвета индикаторов
COLOR_IND_INACTIVE = '#9E9E9E'  # Серый (неактивен)
COLOR_IND_ACTIVE = '#4CAF50'    # Зеленый (активен)
COLOR_IND_ERROR = '#F44336'     # Красный (ошибка)

# Цвета статус-блоков
COLOR_STATUS_OK = '#C8E6C9'      # Светло-зеленый
COLOR_STATUS_WARN = '#FFF9C4'    # Светло-желтый
COLOR_STATUS_ERROR = '#FFCDD2'   # Светло-красный

# === ЦВЕТОВАЯ ПАЛИТРА (Темная тема для PyQt6) ===
COLOR_BACKGROUND_DARK = '#1e1e1e'  # Фон окна (почти черный)
COLOR_PANEL_DARK = '#2d2d2d'       # Панели (темно-серый)
COLOR_PANEL_HOVER_DARK = '#3d3d3d' # Панели при наведении
COLOR_ACCENT = '#0078d4'           # Акцентный цвет (синий Windows)
COLOR_ACCENT_HOVER = '#005a9e'      # Акцент при наведении
COLOR_ACCENT_PRESSED = '#004578'    # Акцент при нажатии
COLOR_SUCCESS_DARK = '#4ec9b0'     # Успех (бирюзовый)
COLOR_ERROR_DARK = '#f48771'       # Ошибка (коралловый)
COLOR_WARNING_DARK = '#dcdcaa'     # Предупреждение (желтый)
COLOR_INFO_DARK = '#569cd6'        # Информация (синий)
COLOR_TEXT_PRIMARY_DARK = '#ffffff'    # Основной текст (белый)
COLOR_TEXT_SECONDARY_DARK = '#cccccc'  # Вторичный текст (светло-серый)
COLOR_BORDER_DARK = '#3d3d3d'         # Границы (серый)

# Цвета кнопок (темная тема)
COLOR_LIBSODIUM_DARK = '#4ec9b0'    # LibSodium (бирюзовый)
COLOR_CUSTOM_DARK = '#569cd6'       # Custom Codec (синий)
COLOR_ENCRYPT_DARK = '#6a9955'      # Отправитель (зеленый)
COLOR_DECRYPT_DARK = '#4ec9b0'      # Получатель (бирюзовый)

# === ШРИФТЫ ===
FONT_TITLE = ('Arial', 14, 'bold')
FONT_NORMAL = ('Arial', 10)
FONT_BUTTON = ('Arial', 11, 'bold')
FONT_TERMINAL = ('Consolas', 10)
FONT_EMOJI = ('Arial', 16)
FONT_EMOJI_LARGE = ('Arial', 48)

# === РАЗМЕРЫ ОКОН ===
WINDOW_MIN_WIDTH = 700
WINDOW_MIN_HEIGHT = 800
WINDOW_DEFAULT_WIDTH = 700
WINDOW_DEFAULT_HEIGHT = 800

LAUNCHER_WIDTH = 600
LAUNCHER_HEIGHT = 400

ROLE_SELECTOR_WIDTH = 500
ROLE_SELECTOR_HEIGHT = 350

# === ОТСТУПЫ И ИНТЕРВАЛЫ ===
PADDING_SECTION = 0
PADDING_INTERNAL = 8
PADDING_BUTTON = 3
PADDING_FRAME = 8

# === ПАРАМЕТРЫ ТЕРМИНАЛА ===
TERMINAL_BUFFER_LINES = 10000  # Максимум строк в буфере
TERMINAL_XTERM_HEIGHT = 200    # Высота xterm панели
TERMINAL_OUTPUT_HEIGHT = 150   # Высота output панели

# === ПАРАМЕТРЫ CUSTOM CODEC ===
# Диапазоны параметров
CODEC_M_MIN = 1
CODEC_M_MAX = 31
CODEC_M_DEFAULT = 8

CODEC_Q_MIN = 1
CODEC_Q_MAX = 16
CODEC_Q_DEFAULT = 2

CODEC_FUN_TYPES = [
    "1: a·x + b·y + q           (линейная)",
    "2: a·x² + b·y + q          (квадратичная по x)",
    "3: a·x² + b·y² + q         (квадратичная)",
    "4: a·x³ + b·y² + q         (кубическая по x)",
    "5: a·x + b·x·y + c·y + q   (билинейная)"
]

CODEC_H1_DEFAULT = 7
CODEC_H2_DEFAULT = 23

# === СЕТЕВЫЕ ПАРАМЕТРЫ ===
DEFAULT_PORT = 12345
DEFAULT_DECRYPT_IP = '0.0.0.0'
PORT_MIN = 1
PORT_MAX = 65535

# === СТАТУСЫ TAP ИНТЕРФЕЙСОВ ===
STATUS_TAP_NOT_CREATED = '⚫ не создан'
STATUS_TAP_ACTIVE = '🟢 активен'
STATUS_TAP_ERROR = '🔴 ошибка'

TAP_NAMES = {
    'encrypt': 'tap0',
    'decrypt': 'tap1'
}

TAP_IPS = {
    'tap0': '10.0.0.1/24',
    'tap1': '10.0.0.2/24'
}

# === СООБЩЕНИЯ ===
MSG_SUDO_REQUIRED = """
⚠️  Требуется sudo доступ без пароля!

Для работы приложения необходим sudo доступ.
Запустите скрипт настройки:

    sudo ./setup_sudo.sh

Это добавит правила в /etc/sudoers.d/
"""

MSG_BUILD_NOT_FOUND = """
❌ Исполняемые файлы не найдены!

Не найдены: tap_encrypt и/или tap_decrypt
Запустите сборку:

    ./rebuild.sh

Или:
    cd build && make
"""

# === TOOLTIPS ===
TOOLTIP_IP_ENCRYPT = "IP-адрес компьютера-получателя (Decrypt)"
TOOLTIP_IP_DECRYPT = "IP для прослушивания (0.0.0.0 = все интерфейсы)"
TOOLTIP_PORT = f"Порт UDP (допустимый диапазон: {PORT_MIN}-{PORT_MAX})"
TOOLTIP_MSG_MODE = "Режим передачи текстовых сообщений вместо Ethernet-кадров"
TOOLTIP_FILE_MODE = "Режим безопасной передачи файлов с фрагментацией и проверкой целостности"
TOOLTIP_FILE_SELECT = "Выберите файл для отправки (любой формат, любой размер)"
TOOLTIP_FILE_OUTPUT = "Путь для сохранения принятого файла (если пусто - используется оригинальное имя)"

TOOLTIP_M = """M — разрядность вычислителя в битах (1..31)

Определяет диапазон значений: [-2^(M-1), 2^(M-1)-1]

Пример для M=8: Диапазон [-128, 127]

Требование: M ≥ Q
Рекомендация: M = 8 для байтовых данных"""

TOOLTIP_Q = """Q — количество информационных бит на символ (1..16)

Определяет количество функций: 2^Q

Требования:
1. Q ≤ M
2. CSV должен содержать ровно 2^Q строк

Пример для Q=2:
- Количество функций: 4
- Требуется строк в CSV: 4"""

TOOLTIP_H1_H2 = """h1, h2 — начальные состояния шифратора

Влияют на первые два шага алгоритма кодирования.

ВАЖНО:
Значения h1 и h2 ДОЛЖНЫ быть идентичны
на компьютере отправителя и получателя!

Рекомендуется использовать небольшие числа
для упрощения отладки (например, 0-100)."""

# === ЭМОДЗИ И ИКОНКИ ===
EMOJI_LIBSODIUM = '🔒'
EMOJI_CUSTOM = '⚡'
EMOJI_ENCRYPT = '📤'
EMOJI_DECRYPT = '📥'
EMOJI_SUCCESS = '✅'
EMOJI_ERROR = '❌'
EMOJI_WARNING = '⚠️'
EMOJI_INFO = 'ℹ️'
EMOJI_FOLDER = '📁'
EMOJI_REFRESH = '🔄'
EMOJI_SAVE = '💾'
EMOJI_LOAD = '📂'
EMOJI_COPY = '📋'
EMOJI_RANDOM = '🎲'
EMOJI_PLAY = '▶️'
EMOJI_STOP = '⏹️'
EMOJI_SETTINGS = '🔧'
EMOJI_CLEAN = '🧹'
EMOJI_PING = '🏓'
EMOJI_IPERF = '📊'
EMOJI_HPING = '🔄'
EMOJI_SERVER = '🛰️'
EMOJI_TCPDUMP = '🔍'
EMOJI_BULB = '💡'
EMOJI_SEND = '📤'
EMOJI_FILE = '📁'
EMOJI_UPLOAD = '📤'
EMOJI_DOWNLOAD = '📥'


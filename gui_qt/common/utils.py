"""
LightCrypto GUI - Утилиты
Валидация, работа с файлами, проверка системы
"""

import os
import re
import csv
import subprocess
import math
from typing import Dict, List, Optional, Tuple

from .constants import *


def validate_ip(ip_string: str) -> bool:
    """
    Проверка валидности IPv4 адреса
    
    Args:
        ip_string: Строка с IP-адресом
    
    Returns:
        True если IP валиден, False иначе
    """
    if not ip_string:
        return False
    
    # Регулярное выражение для IPv4
    pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
    match = re.match(pattern, ip_string)
    
    if not match:
        return False
    
    # Проверка диапазона каждого октета
    for octet in match.groups():
        if int(octet) > 255:
            return False
    
    return True


def validate_port(port: int) -> bool:
    """
    Проверка валидности порта
    
    Args:
        port: Номер порта
    
    Returns:
        True если порт в диапазоне 1-65535, False иначе
    """
    try:
        port_num = int(port)
        return PORT_MIN <= port_num <= PORT_MAX
    except (ValueError, TypeError):
        return False


def check_file_exists(path: str) -> bool:
    """
    Проверка существования файла
    
    Args:
        path: Путь к файлу
    
    Returns:
        True если файл существует и доступен для чтения
    """
    return os.path.isfile(path) and os.access(path, os.R_OK)


def scan_csv_files(directory: str = CIPHER_KEYS_DIR) -> List[str]:
    """
    Сканирование директории на наличие CSV файлов
    
    Args:
        directory: Путь к директории с CSV файлами
    
    Returns:
        Отсортированный список имен CSV файлов
    """
    if not os.path.isdir(directory):
        return []
    
    csv_files = []
    for filename in os.listdir(directory):
        if filename.endswith('.csv'):
            csv_files.append(filename)
    
    return sorted(csv_files)


def analyze_csv(csv_path: str) -> Dict[str, any]:
    """
    Анализ CSV файла для определения параметров
    
    Args:
        csv_path: Путь к CSV файлу
    
    Returns:
        Словарь с результатами анализа:
        {
            'success': bool,
            'error': str (если success=False),
            'rows': int,
            'cols': int,
            'Q': int,
            'valid_fun_types': list,
            'recommended_M': int
        }
    """
    result = {
        'success': False,
        'error': '',
        'rows': 0,
        'cols': 0,
        'Q': 0,
        'valid_fun_types': [],
        'recommended_M': CODEC_M_DEFAULT
    }
    
    if not check_file_exists(csv_path):
        result['error'] = 'Файл не существует или недоступен'
        return result
    
    try:
        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            rows_data = []
            
            for row in reader:
                # Пропускаем пустые строки и комментарии
                if not row or all(not cell.strip() for cell in row):
                    continue
                if row[0].strip().startswith('#'):
                    continue
                
                rows_data.append(row)
            
            if not rows_data:
                result['error'] = 'CSV файл пуст'
                return result
            
            # Определяем количество строк и столбцов
            result['rows'] = len(rows_data)
            result['cols'] = len(rows_data[0])
            
            # Определяем Q (log2 от количества строк)
            if result['rows'] > 0:
                q_float = math.log2(result['rows'])
                q_int = int(q_float)
                
                if abs(q_float - q_int) < 0.001:  # Проверка, что это точная степень 2
                    result['Q'] = q_int
                else:
                    result['error'] = f"Количество строк ({result['rows']}) не является степенью 2"
                    return result
            
            # Определяем допустимые типы функций
            if result['cols'] == 3:
                result['valid_fun_types'] = [1, 2, 3, 4]
            elif result['cols'] == 4:
                result['valid_fun_types'] = [5]
            else:
                result['error'] = f"Некорректное количество столбцов: {result['cols']} (ожидается 3 или 4)"
                return result
            
            # Рекомендуемое M
            result['recommended_M'] = max(CODEC_M_DEFAULT, result['Q'])
            
            result['success'] = True
        
    except Exception as e:
        result['error'] = f"Ошибка парсинга CSV: {str(e)}"
    
    return result


def check_sudo_access() -> bool:
    """
    Проверка наличия sudo доступа без пароля (только для Linux)
    
    Returns:
        True если sudo доступен без пароля (Linux) или всегда True для Windows
    """
    if os.name == 'nt':  # Windows
        return True  # Не требуется на Windows
    
    try:
        result = subprocess.run(['sudo', '-n', 'true'],
                              capture_output=True,
                              timeout=2)
        return result.returncode == 0
    except Exception:
        return False


def check_tap_interface(tap_name: str) -> bool:
    """
    Проверка существования TAP интерфейса (только для Linux)
    
    Args:
        tap_name: Имя интерфейса (например, 'tap0')
    
    Returns:
        True если интерфейс существует и активен (Linux) или False для Windows
    """
    if os.name == 'nt':  # Windows
        return False  # TAP не поддерживается на Windows
    
    try:
        result = subprocess.run(['ip', 'link', 'show', tap_name],
                              capture_output=True,
                              timeout=2)
        return result.returncode == 0
    except Exception:
        return False


def get_tap_status(tap_name: str) -> Tuple[bool, str]:
    """
    Получить статус TAP интерфейса (только для Linux)
    
    Args:
        tap_name: Имя интерфейса
    
    Returns:
        Tuple (exists: bool, ip: str)
    """
    if os.name == 'nt':  # Windows
        return False, ''
    
    if not check_tap_interface(tap_name):
        return False, ''
    
    try:
        # Получить IP адрес
        result = subprocess.run(['ip', 'addr', 'show', tap_name],
                              capture_output=True,
                              text=True,
                              timeout=2)
        
        if result.returncode == 0:
            # Поиск IP в выводе
            match = re.search(r'inet (\d+\.\d+\.\d+\.\d+/\d+)', result.stdout)
            if match:
                return True, match.group(1)
        
        return True, 'unknown'
    except Exception:
        return False, ''


def check_build_files() -> Tuple[bool, List[str]]:
    """
    Проверка наличия исполняемых файлов для локального режима
    
    Returns:
        Tuple (all_exist: bool, missing_files: list)
    """
    missing = []
    
    # Проверяем локальные программы (основные для Windows)
    local_programs = [
        (FILE_ENCODE, 'file_encode'),
        (FILE_DECODE, 'file_decode'),
        (FILE_ENCODE_PLAIN, 'file_encode_plain'),
        (FILE_DECODE_PLAIN, 'file_decode_plain'),
        (FILE_ENCODE_HYBRID, 'file_encode_hybrid'),
        (FILE_DECODE_HYBRID, 'file_decode_hybrid'),
    ]
    
    # Для Windows также проверяем Release директорию
    if os.name == 'nt':
        local_programs.extend([
            (FILE_ENCODE_RELEASE, 'file_encode'),
            (FILE_DECODE_RELEASE, 'file_decode'),
            (FILE_ENCODE_PLAIN_RELEASE, 'file_encode_plain'),
            (FILE_DECODE_PLAIN_RELEASE, 'file_decode_plain'),
            (FILE_ENCODE_HYBRID_RELEASE, 'file_encode_hybrid'),
            (FILE_DECODE_HYBRID_RELEASE, 'file_decode_hybrid'),
        ])
    
    # Проверяем наличие хотя бы одной версии каждого файла
    found_programs = set()
    for file_path, program_name in local_programs:
        if os.path.isfile(file_path):
            found_programs.add(program_name)
    
    # Определяем отсутствующие программы
    required_programs = {'file_encode', 'file_decode', 'file_encode_plain', 
                        'file_decode_plain', 'file_encode_hybrid', 'file_decode_hybrid'}
    missing = list(required_programs - found_programs)
    
    return len(missing) == 0, missing


def validate_codec_params(M: int, Q: int, csv_rows: int) -> Tuple[bool, List[str]]:
    """
    Валидация параметров Custom Codec
    
    Args:
        M: Разрядность
        Q: Информационные биты
        csv_rows: Количество строк в CSV
    
    Returns:
        Tuple (valid: bool, errors: list)
    """
    errors = []
    
    # Проверка диапазонов
    if not (CODEC_M_MIN <= M <= CODEC_M_MAX):
        errors.append(f'M должно быть в диапазоне {CODEC_M_MIN}-{CODEC_M_MAX}')
    
    if not (CODEC_Q_MIN <= Q <= CODEC_Q_MAX):
        errors.append(f'Q должно быть в диапазоне {CODEC_Q_MIN}-{CODEC_Q_MAX}')
    
    # M должно быть >= Q
    if M < Q:
        errors.append(f'M ({M}) должно быть ≥ Q ({Q})')
    
    # Проверка совместимости с CSV
    expected_rows = 2 ** Q
    if csv_rows != expected_rows:
        errors.append(f'CSV содержит {csv_rows} строк, ожидается {expected_rows} для Q={Q}')
    
    return len(errors) == 0, errors


def format_command_list(cmd_list: List[str]) -> str:
    """
    Форматирование списка команд в строку для копирования
    
    Args:
        cmd_list: Список элементов команды
    
    Returns:
        Форматированная строка команды
    """
    return ' '.join(cmd_list)


def find_terminal_emulator() -> Optional[str]:
    """
    Найти доступный эмулятор терминала
    
    Returns:
        Путь к терминалу или None
    """
    terminals = ['gnome-terminal', 'konsole', 'xterm', 'xfce4-terminal', 'mate-terminal']
    
    for term in terminals:
        try:
            result = subprocess.run(['which', term],
                                  capture_output=True,
                                  text=True)
            if result.returncode == 0:
                return term
        except Exception:
            continue
    
    return None


def escape_shell_arg(arg: str) -> str:
    """
    Экранирование аргумента для безопасной передачи в shell
    
    Args:
        arg: Аргумент командной строки
    
    Returns:
        Экранированный аргумент
    """
    # Простое экранирование для путей и IP
    if ' ' in arg or '"' in arg or "'" in arg:
        return f'"{arg.replace('"', '\\"')}"'
    return arg


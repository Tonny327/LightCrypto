#!/usr/bin/env python3
"""
LightCrypto - UDP Relay для Windows
====================================
Используется когда прямое соединение между WSL машинами невозможно.

Запуск:
    python udp_relay.py

Требует:
    - Python 3.6+
    - Запускать на Windows устройства B (приёмник)
    - Узнать IP WSL через: wsl hostname -I
"""

import socket
import threading
import sys
from datetime import datetime

# ============================================================
# НАСТРОЙКИ - ИЗМЕНИТЕ НА ВАШИ!
# ============================================================

# IP WSL получателя (узнайте через: wsl hostname -I)
WSL_IP = "172.26.43.251"  # ← ИЗМЕНИТЕ НА ВАШ IP!

# Порты
WIN_PORT = 12346  # Windows слушает на этом порту
WSL_PORT = 12346  # Перенаправляет на этот порт в WSL

# ============================================================

class UDPRelay:
    def __init__(self, wsl_ip, win_port, wsl_port):
        self.wsl_ip = wsl_ip
        self.win_port = win_port
        self.wsl_port = wsl_port
        
        # Сокет для прослушивания на Windows
        self.win_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.win_sock.bind(('0.0.0.0', self.win_port))
        
        # Сокет для общения с WSL
        self.wsl_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Таблица активных соединений
        self.connections = {}  # WSL_addr -> client_addr
        
    def log(self, message, level="INFO"):
        """Вывод лога с временной меткой"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] [{level}] {message}")
    
    def handle_from_windows(self):
        """Обработка пакетов от клиентов (Windows -> WSL)"""
        while True:
            try:
                data, client_addr = self.win_sock.recvfrom(65536)
                
                self.log(f"Windows → WSL: {len(data)} bytes from {client_addr[0]}:{client_addr[1]}")
                
                # Отправляем в WSL
                self.wsl_sock.sendto(data, (self.wsl_ip, self.wsl_port))
                
                # Запоминаем соединение для обратного пути
                # Используем порт клиента как ключ
                self.connections[client_addr] = True
                
            except Exception as e:
                self.log(f"Error in handle_from_windows: {e}", "ERROR")
    
    def handle_from_wsl(self):
        """Обработка пакетов от WSL (WSL -> Windows)"""
        # Создаём отдельный сокет для приёма от WSL
        wsl_recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        wsl_recv_sock.bind(('0.0.0.0', self.wsl_port + 1))  # Слушаем на соседнем порту
        
        # Но для начала используем тот же сокет
        self.wsl_sock.settimeout(0.1)  # Короткий таймаут
        
        last_client = None
        
        while True:
            try:
                # Пытаемся получить ответ от WSL
                response, wsl_addr = self.wsl_sock.recvfrom(65536)
                
                # Если есть активные соединения, отправляем последнему клиенту
                if self.connections:
                    # Берём последний адрес клиента
                    for client_addr in self.connections:
                        last_client = client_addr
                    
                    if last_client:
                        self.win_sock.sendto(response, last_client)
                        self.log(f"WSL → Windows: {len(response)} bytes to {last_client[0]}:{last_client[1]}")
                
            except socket.timeout:
                # Таймаут - это нормально, продолжаем
                continue
            except Exception as e:
                if "timed out" not in str(e):
                    self.log(f"Error in handle_from_wsl: {e}", "ERROR")
    
    def start(self):
        """Запуск relay"""
        print("╔═══════════════════════════════════════════════════════╗")
        print("║         LightCrypto - UDP Relay для WSL              ║")
        print("╚═══════════════════════════════════════════════════════╝")
        print()
        print(f"📡 Конфигурация:")
        print(f"   Windows listen: 0.0.0.0:{self.win_port}")
        print(f"   WSL forward:    {self.wsl_ip}:{self.wsl_port}")
        print()
        print("✅ Relay запущен! Ожидание подключений...")
        print("   (Нажмите Ctrl+C для остановки)")
        print()
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()
        
        # Запускаем обработчики в отдельных потоках
        thread_win = threading.Thread(target=self.handle_from_windows, daemon=True)
        thread_wsl = threading.Thread(target=self.handle_from_wsl, daemon=True)
        
        thread_win.start()
        thread_wsl.start()
        
        # Держим программу запущенной
        try:
            thread_win.join()
        except KeyboardInterrupt:
            print()
            print("🛑 Остановка relay...")
            self.win_sock.close()
            self.wsl_sock.close()
            sys.exit(0)


def main():
    """Точка входа"""
    
    # Проверка что WSL_IP изменён
    if WSL_IP == "172.26.43.251":
        print("⚠️  ПРЕДУПРЕЖДЕНИЕ: WSL_IP имеет значение по умолчанию!")
        print("   Узнайте IP WSL через команду: wsl hostname -I")
        print("   И замените WSL_IP в начале скрипта")
        print()
        response = input("Продолжить с текущим IP? (y/N): ")
        if response.lower() != 'y':
            print("Отменено.")
            sys.exit(0)
        print()
    
    # Создаём и запускаем relay
    relay = UDPRelay(WSL_IP, WIN_PORT, WSL_PORT)
    relay.start()


if __name__ == "__main__":
    main()


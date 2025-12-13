#!/usr/bin/env python3
"""
Скрипт для добавления реалистичного шума в зашифрованный контейнер для тестирования восстановления.
Симулирует передачу через радиоканал с множественными копиями, искажениями и обрезанными фрагментами.
"""

import sys
import random
import os

# Маркеры из file_transfer.cpp (оптимизированы для 47-байтного чанка)
START_MARKER = bytes([0xAA, 0x55, 0xAA, 0x55])
END_MARKER = bytes([0x55, 0xAA, 0x55, 0xAA])
MARKER_SIZE = 4  # Уменьшено с 8 до 4 байт для экономии места

def find_markers(data):
    """Находит все маркеры начала и конца чанков"""
    start_positions = []
    end_positions = []
    
    pos = 0
    while True:
        start_pos = data.find(START_MARKER, pos)
        if start_pos == -1:
            break
        start_positions.append(start_pos)
        pos = start_pos + 1
    
    pos = 0
    while True:
        end_pos = data.find(END_MARKER, pos)
        if end_pos == -1:
            break
        end_positions.append(end_pos)
        pos = end_pos + 1
    
    return start_positions, end_positions

def create_partial_marker(marker, corruption_level=0.3):
    """Создаёт частичный или искажённый маркер"""
    if random.random() < corruption_level:
        # Частичный маркер (обрезанный)
        partial_size = random.randint(1, MARKER_SIZE - 1)
        partial = marker[:partial_size]
        # Добавляем случайные байты
        partial += bytes([random.randint(0, 255) for _ in range(MARKER_SIZE - partial_size)])
        return partial
    else:
        # Искажённый маркер (несколько байт изменены)
        corrupted = bytearray(marker)
        corrupt_count = random.randint(1, 3)
        for _ in range(corrupt_count):
            pos = random.randint(0, len(corrupted) - 1)
            corrupted[pos] = random.randint(0, 255)
        return bytes(corrupted)

def create_corrupted_fragment(data, corruption_level=0.2):
    """Создаёт искажённую копию фрагмента данных"""
    corrupted = bytearray(data)
    corrupt_count = max(1, int(len(corrupted) * corruption_level))
    for _ in range(corrupt_count):
        pos = random.randint(0, len(corrupted) - 1)
        corrupted[pos] = random.randint(0, 255)
    return bytes(corrupted)

def add_noise_to_file(input_path, output_path, noise_intensity=10, corruption_probability=0.1):
    """
    Добавляет реалистичный шум в файл, симулируя передачу через радиоканал.
    
    Args:
        input_path: путь к исходному файлу
        output_path: путь к выходному файлу с шумом
        noise_intensity: интенсивность шума (количество вставок шума, 1-100)
        corruption_probability: вероятность повреждения чанка (0.0-1.0)
    """
    print(f"📖 Читаю файл: {input_path}")
    with open(input_path, 'rb') as f:
        data = bytearray(f.read())
    
    print(f"📊 Размер файла: {len(data)} байт")
    
    # Находим маркеры
    start_positions, end_positions = find_markers(data)
    print(f"🔍 Найдено маркеров начала: {len(start_positions)}")
    print(f"🔍 Найдено маркеров конца: {len(end_positions)}")
    
    if len(start_positions) == 0:
        print("⚠️  Маркеры начала не найдены. Добавляю шум в начало и конец файла.")
        # Добавляем много шума
        noise_start = bytes([random.randint(0, 255) for _ in range(random.randint(50, 200))])
        noise_end = bytes([random.randint(0, 255) for _ in range(random.randint(50, 200))])
        result = noise_start + data + noise_end
    else:
        # Строим новый файл с реалистичным шумом
        result = bytearray()
        pos = 0
        
        # Обрабатываем заголовок (до первого маркера)
        if start_positions[0] > 0:
            header = data[pos:start_positions[0]]
            result.extend(header)
            pos = start_positions[0]
            print(f"📄 Заголовок: {len(header)} байт")
        
        # Добавляем МНОГО шума после заголовка
        noise_size = random.randint(30, 100)
        noise = bytes([random.randint(0, 255) for _ in range(noise_size)])
        result.extend(noise)
        print(f"🔊 Добавлен шум после заголовка: {noise_size} байт")
        
        # Добавляем частичные/искажённые маркеры (ложные срабатывания)
        for _ in range(random.randint(2, 5)):
            partial_marker = create_partial_marker(START_MARKER)
            result.extend(partial_marker)
            # Добавляем случайные байты после частичного маркера
            result.extend(bytes([random.randint(0, 255) for _ in range(random.randint(5, 20))]))
        print(f"🔊 Добавлено {random.randint(2, 5)} частичных/искажённых маркеров")
        
        # Обрабатываем чанки
        chunks_processed = 0
        chunks_corrupted = 0
        all_chunks = []
        
        for i, start_pos in enumerate(start_positions):
            # Находим соответствующий маркер конца
            end_pos = None
            for ep in end_positions:
                if ep > start_pos:
                    end_pos = ep
                    break
            
            if end_pos is None:
                print(f"⚠️  Не найден маркер конца для чанка {i}, пропускаю")
                continue
            
            # Извлекаем чанк
            chunk_start = start_pos
            chunk_end = end_pos + MARKER_SIZE
            chunk = data[chunk_start:chunk_end]
            all_chunks.append((i, chunk))
            
            # Повреждаем чанк с некоторой вероятностью
            if random.random() < corruption_probability:
                corruption_count = random.randint(1, 5)
                for _ in range(corruption_count):
                    corrupt_pos = random.randint(MARKER_SIZE + 12, len(chunk) - MARKER_SIZE - 1)
                    chunk[corrupt_pos] = random.randint(0, 255)
                chunks_corrupted += 1
                print(f"💥 Повреждён чанк {i}: изменено {corruption_count} байт")
            
            chunks_processed += 1
        
        # Теперь добавляем чанки с огромным количеством шума между ними
        for chunk_idx, (i, chunk) in enumerate(all_chunks):
            # Добавляем МНОГО шума перед каждым чанком
            for _ in range(random.randint(noise_intensity // 2, noise_intensity)):
                # Случайные байты
                noise_size = random.randint(10, 50)
                noise = bytes([random.randint(0, 255) for _ in range(noise_size)])
                result.extend(noise)
                
                # Иногда добавляем частичные маркеры
                if random.random() < 0.3:
                    partial = create_partial_marker(START_MARKER if random.random() < 0.5 else END_MARKER)
                    result.extend(partial)
                    result.extend(bytes([random.randint(0, 255) for _ in range(random.randint(3, 15))]))
                
                # Иногда добавляем искажённые фрагменты предыдущих чанков
                if chunk_idx > 0 and random.random() < 0.4:
                    prev_chunk = all_chunks[chunk_idx - 1][1]
                    fragment_start = random.randint(0, len(prev_chunk) - 20)
                    fragment_end = random.randint(fragment_start + 5, min(fragment_start + 30, len(prev_chunk)))
                    fragment = prev_chunk[fragment_start:fragment_end]
                    # Искажаем фрагмент
                    corrupted_fragment = create_corrupted_fragment(fragment, 0.15)
                    result.extend(corrupted_fragment)
                    result.extend(bytes([random.randint(0, 255) for _ in range(random.randint(5, 20))]))
            
            # Добавляем правильный чанк
            result.extend(chunk)
            
            # После чанка тоже добавляем шум
            if random.random() < 0.7:
                noise_size = random.randint(5, 30)
                noise = bytes([random.randint(0, 255) for _ in range(noise_size)])
                result.extend(noise)
                
                # Иногда добавляем дубликат части чанка (искажённый)
                if random.random() < 0.3:
                    fragment_start = random.randint(MARKER_SIZE, len(chunk) - 20)
                    fragment_end = random.randint(fragment_start + 10, min(fragment_start + 40, len(chunk)))
                    fragment = chunk[fragment_start:fragment_end]
                    corrupted_fragment = create_corrupted_fragment(fragment, 0.2)
                    result.extend(corrupted_fragment)
                    result.extend(bytes([random.randint(0, 255) for _ in range(random.randint(3, 15))]))
        
        # Добавляем ОГРОМНОЕ количество шума в конец
        end_noise_size = random.randint(50, 150)
        end_noise = bytes([random.randint(0, 255) for _ in range(end_noise_size)])
        result.extend(end_noise)
        
        # Добавляем множество искажённых копий последнего чанка
        if len(all_chunks) > 0:
            last_chunk = all_chunks[-1][1]
            for _ in range(random.randint(3, 8)):
                # Случайные байты
                result.extend(bytes([random.randint(0, 255) for _ in range(random.randint(5, 25))]))
                
                # Частичный маркер
                partial = create_partial_marker(START_MARKER)
                result.extend(partial)
                
                # Искажённый фрагмент последнего чанка
                fragment_start = random.randint(0, len(last_chunk) - 30)
                fragment_end = random.randint(fragment_start + 10, min(fragment_start + 50, len(last_chunk)))
                fragment = last_chunk[fragment_start:fragment_end]
                corrupted_fragment = create_corrupted_fragment(fragment, 0.25)
                result.extend(corrupted_fragment)
                
                # Ещё случайные байты
                result.extend(bytes([random.randint(0, 255) for _ in range(random.randint(5, 20))]))
        
        print(f"\n📊 Статистика:")
        print(f"   ✅ Обработано чанков: {chunks_processed}")
        print(f"   💥 Повреждено чанков: {chunks_corrupted}")
        print(f"   📈 Исходный размер: {len(data)} байт")
        print(f"   📈 Размер с шумом: {len(result)} байт")
        print(f"   📈 Добавлено байт: {len(result) - len(data)} байт")
        print(f"   📈 Увеличение размера: {len(result) / len(data) * 100:.1f}%")
    
    # Сохраняем результат
    print(f"\n💾 Сохраняю файл с шумом: {output_path}")
    with open(output_path, 'wb') as f:
        f.write(result)
    
    print(f"✅ Готово! Файл сохранён: {output_path}")
    return output_path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python3 add_noise.py <input_file> [output_file] [noise_intensity] [corruption_prob]")
        print("\nПараметры:")
        print("  input_file      - путь к зашифрованному файлу")
        print("  output_file     - путь к выходному файлу с шумом (по умолчанию: input_file_noisy.bin)")
        print("  noise_intensity - интенсивность шума (1-100, по умолчанию: 10)")
        print("                   Чем больше, тем больше шума между чанками")
        print("  corruption_prob - вероятность повреждения чанка (0.0-1.0, по умолчанию: 0.1)")
        print("\nПримеры:")
        print("  python3 add_noise.py file.bin                    # Умеренный шум")
        print("  python3 add_noise.py file.bin output.bin 20      # Сильный шум")
        print("  python3 add_noise.py file.bin output.bin 50 0.2 # Очень сильный шум + повреждения")
        sys.exit(1)
    
    input_path = sys.argv[1]
    
    if not os.path.exists(input_path):
        print(f"❌ Файл не найден: {input_path}")
        sys.exit(1)
    
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_noisy{ext}"
    
    noise_intensity = int(sys.argv[3]) if len(sys.argv) >= 4 else 10
    corruption_prob = float(sys.argv[4]) if len(sys.argv) >= 5 else 0.1
    
    add_noise_to_file(input_path, output_path, noise_intensity, corruption_prob)

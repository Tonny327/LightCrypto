# Оптимизации кодека для Q=2 и M=8

Этот документ описывает все изменения, внесенные для оптимизации производительности кодека при использовании параметров Q=2 и M=8.

## Дата изменений
2024 (текущая дата)

## Обзор изменений

Основная цель оптимизаций - убрать избыточный overhead от хеш-таблиц для малых значений Q (≤4) и оптимизировать операции для частого случая M=8.

## Изменения в заголовочных файлах

### digital_codec.h

**Добавлены заголовки:**
```cpp
#include <unordered_set>
#include <unordered_map>
```

Эти заголовки нужны для хеш-таблиц, которые используются для больших значений Q.

## Изменения в digital_codec.cpp

### 1. Оптимизация wrapM() для M=8

**Файл:** `src/digital_codec.cpp`  
**Функция:** `DigitalCodec::wrapM()`

**Было:**
```cpp
int32_t DigitalCodec::wrapM(int64_t v) const {
    const int64_t mod = ipow2(params_.bitsM);
    int64_t r = v % mod;
    if (r < 0) r += mod;
    int64_t signBit = ipow2(params_.bitsM - 1);
    if (r >= signBit) r -= mod;
    return static_cast<int32_t>(r);
}
```

**Стало:**
```cpp
int32_t DigitalCodec::wrapM(int64_t v) const {
    // Оптимизация для частого случая M=8
    if (params_.bitsM == 8) {
        return static_cast<int8_t>(static_cast<uint8_t>(v));
    }
    
    const int64_t mod = ipow2(params_.bitsM);
    int64_t r = v % mod;
    if (r < 0) r += mod;
    int64_t signBit = ipow2(params_.bitsM - 1);
    if (r >= signBit) r -= mod;
    return static_cast<int32_t>(r);
}
```

**Причина:** Для M=8 можно использовать прямую конвертацию через int8_t без деления и проверок.

---

### 2. Оптимизация digitalCodingFun() для M=8

**Файл:** `src/digital_codec.cpp`  
**Функция:** `DigitalCodec::digitalCodingFun()`

**Добавлено в начало функции:**
```cpp
// Оптимизация для M=8: используем прямые операции без вызова wrapM
if (params_.bitsM == 8) {
    auto mul8 = [](int32_t lhs, int32_t rhs) -> int32_t {
        return static_cast<int8_t>(static_cast<uint8_t>(lhs * rhs));
    };
    auto add8 = [](int32_t lhs, int32_t rhs) -> int32_t {
        return static_cast<int8_t>(static_cast<uint8_t>(lhs + rhs));
    };
    
    switch (params_.funType) {
        case 1: return add8(add8(mul8(a, x), mul8(b, y)), q);
        case 2: return add8(add8(mul8(a, mul8(x, x)), mul8(b, y)), q);
        case 3: return add8(add8(mul8(a, mul8(x, x)), mul8(b, mul8(y, y))), q);
        case 4: return add8(add8(mul8(a, mul8(mul8(x, x), x)), mul8(b, mul8(y, y))), q);
        case 5: {
            const int32_t c = row[2];
            const int32_t q5 = row[3];
            return add8(add8(add8(mul8(a, x), mul8(b, mul8(x, y))), mul8(c, y)), q5);
        }
        default: return 0;
    }
}
```

**Причина:** Избегаем вызовов wrapM() для каждого умножения/сложения при M=8.

---

### 3. Оптимизация toBytes() для M=8

**Файл:** `src/digital_codec.cpp`  
**Функция:** `DigitalCodec::toBytes()`

**Добавлено в начало функции:**
```cpp
// Оптимизация для частого случая M=8 (1 байт)
if (params_.bitsM == 8) {
    out.push_back(static_cast<uint8_t>(v));
    return;
}
```

**Причина:** Для M=8 нужен только один байт, можно записать напрямую без циклов.

---

### 4. Оптимизация fromBytes() для M=8

**Файл:** `src/digital_codec.cpp`  
**Функция:** `DigitalCodec::fromBytes()`

**Добавлено в начало функции:**
```cpp
// Оптимизация для частого случая M=8 (1 байт)
if (params_.bitsM == 8) {
    return static_cast<int8_t>(data[0]);
}
```

**Причина:** Для M=8 читаем один байт напрямую без циклов и масок.

---

### 5. Оптимизация packBytesToSymbols() для Q=2

**Файл:** `src/digital_codec.cpp`  
**Функция:** `DigitalCodec::packBytesToSymbols()`

**Добавлено в начало функции:**
```cpp
// Оптимизация для частого случая Q=2 (4 символа на байт)
if (q == 2) {
    const size_t estimated_size = input.size() * 4;
    std::vector<uint8_t> symbols;
    symbols.reserve(estimated_size);
    const uint32_t mask = 0x3u; // 2 бита
    
    for (uint8_t b : input) {
        symbols.push_back(static_cast<uint8_t>(b & mask));
        symbols.push_back(static_cast<uint8_t>((b >> 2) & mask));
        symbols.push_back(static_cast<uint8_t>((b >> 4) & mask));
        symbols.push_back(static_cast<uint8_t>((b >> 6) & mask));
    }
    return symbols;
}
```

**Причина:** Для Q=2 можно извлекать символы напрямую через битовые сдвиги без циклов и буферов.

---

### 6. Оптимизация unpackSymbolsToBytes() для Q=2

**Файл:** `src/digital_codec.cpp`  
**Функция:** `DigitalCodec::unpackSymbolsToBytes()`

**Заменено начало функции:**
```cpp
// Оптимизация для частого случая Q=2 (4 символа на байт)
if (q == 2) {
    std::vector<uint8_t> out;
    out.reserve(expected_len);
    
    // Обрабатываем все символы группами по 4, пока не достигнем expected_len
    for (size_t i = 0; i + 3 < symbols.size() && out.size() < expected_len; i += 4) {
        uint8_t byte = symbols[i] | (symbols[i+1] << 2) | (symbols[i+2] << 4) | (symbols[i+3] << 6);
        out.push_back(byte);
    }
    
    // Обработка остатка (если есть неполная группа из 4 символов)
    size_t processed = (out.size() * 4);
    if (processed < symbols.size() && out.size() < expected_len) {
        size_t remaining = symbols.size() - processed;
        uint8_t byte = 0;
        for (size_t i = 0; i < remaining && i < 4; ++i) {
            byte |= symbols[processed + i] << (i * 2);
        }
        out.push_back(byte);
    }
    
    // Обрезаем до expected_len если нужно
    if (out.size() > expected_len) {
        out.resize(expected_len);
    }
    return out;
}
```

**Причина:** Для Q=2 можно собирать байты напрямую через битовые операции без циклов и буферов.

---

### 7. Оптимизация encodeSymbols() для малых Q

**Файл:** `src/digital_codec.cpp`  
**Функция:** `DigitalCodec::encodeSymbols()`

**Основные изменения:**

1. **Убраны хеш-таблицы для малых Q:**
```cpp
// Для малых Q (<=4) используем простой массив, для больших - хеш-таблицы
const bool useSimpleArray = (funCount <= 4);
std::vector<int32_t> RR(funCount);

// Для больших Q используем хеш-таблицы
std::unordered_set<int32_t> rrSet;
std::vector<bool> isFirstOccurrence;
if (!useSimpleArray) {
    isFirstOccurrence.resize(funCount);
    rrSet.reserve(funCount);
}
```

2. **Упрощена проверка коллизий для малых Q:**
```cpp
if (useSimpleArray) {
    // Для малых Q: простой линейный поиск (быстрее чем хеш-таблица для 4 элементов)
    for (int i = 0; i < funCount && !collisionDetected; ++i) {
        for (int j = i + 1; j < funCount; ++j) {
            if (RR[i] == RR[j]) {
                collisionDetected = true;
                if (j < minDupIdx) minDupIdx = j;
                break;
            }
        }
    }
} else {
    // Для больших Q: используем хеш-таблицу
    rrSet.clear();
    for (int ff = 0; ff < funCount; ++ff) {
        auto result = rrSet.insert(RR[ff]);
        if (!result.second) {
            collisionDetected = true;
            if (ff < minDupIdx) minDupIdx = ff;
        }
    }
}
```

3. **Упрощена проверка значений в RR для малых Q:**
```cpp
if (useSimpleArray) {
    for (int ff = 0; ff < funCount; ++ff) {
        if (RR[ff] == directVal) {
            directValInRR = true;
            break;
        }
    }
} else {
    directValInRR = (rrSet.find(directVal) != rrSet.end());
}
```

**Причина:** Для малых Q (≤4) overhead от создания и использования хеш-таблиц больше, чем простой линейный поиск.

---

### 8. Оптимизация decodeSymbols() для малых Q

**Файл:** `src/digital_codec.cpp`  
**Функция:** `DigitalCodec::decodeSymbols()`

**Основные изменения:**

1. **Убраны хеш-таблицы для малых Q:**
```cpp
// Для малых Q (<=4) используем простой линейный поиск, для больших - хеш-таблицу
const bool useSimpleSearch = (funCount <= 4);
std::vector<int32_t> RR(funCount);

// Для больших Q используем хеш-таблицу
std::unordered_map<int32_t, int> rrMap;
if (!useSimpleSearch) {
    rrMap.reserve(funCount);
}
```

2. **Упрощен поиск совпадений для малых Q:**
```cpp
if (useSimpleSearch) {
    // Для малых Q: простой линейный поиск (быстрее для 4 элементов)
    for (int ff = 0; ff < funCount; ++ff) {
        if (RR[ff] == observed) {
            matched = ff;
            break;
        }
    }
} else {
    // Для больших Q: строим хеш-таблицу и ищем
    rrMap.clear();
    for (int ff = 0; ff < funCount; ++ff) {
        // Сохраняем только первое вхождение (как в оригинале)
        if (rrMap.find(RR[ff]) == rrMap.end()) {
            rrMap[RR[ff]] = ff;
        }
    }
    auto it = rrMap.find(observed);
    if (it != rrMap.end()) {
        matched = it->second;
    }
}
```

**Причина:** Для малых Q линейный поиск быстрее, чем создание и использование хеш-таблицы.

---

### 9. Оптимизация encodeMessage()

**Файл:** `src/digital_codec.cpp`  
**Функция:** `DigitalCodec::encodeMessage()`

**Изменения:**
```cpp
// Оптимизация: резервируем место заранее и используем прямой доступ
std::vector<uint8_t> framed;
framed.reserve(2 + coded.size());
framed.resize(2 + coded.size());
framed[0] = static_cast<uint8_t>(len & 0xFF);
framed[1] = static_cast<uint8_t>((len >> 8) & 0xFF);
std::memcpy(framed.data() + 2, coded.data(), coded.size());
return framed;
```

**Причина:** Использование `memcpy` быстрее, чем `insert` для больших блоков данных.

---

### 10. Добавлены заголовки в digital_codec.cpp

**Добавлено в начало файла:**
```cpp
#include <unordered_set>
#include <unordered_map>
#include <random>
```

**Причина:** Нужны для хеш-таблиц и улучшенного генератора случайных чисел.

---

## Итоговые улучшения производительности

1. **Для Q=2, M=8:**
   - Убраны хеш-таблицы (overhead больше выигрыша для 4 элементов)
   - Оптимизированы операции wrapM, умножение, сложение
   - Оптимизированы операции упаковки/распаковки символов
   - Оптимизированы операции сериализации/десериализации

2. **Для больших Q:**
   - Сохранены хеш-таблицы для эффективного поиска
   - Оптимизированы операции для M=8

3. **Общие улучшения:**
   - Использование `memcpy` вместо `insert` для больших блоков
   - Резервирование памяти заранее
   - Улучшенный генератор случайных чисел (`mt19937` вместо `rand()`)

## Важные замечания

1. **Совместимость:** Все изменения обратно совместимы - код работает для любых значений Q и M, но оптимизирован для частых случаев Q=2 и M=8.

2. **Тестирование:** После применения изменений обязательно протестируйте:
   - Передачу файлов
   - Ping между устройствами
   - Корректность декодирования

3. **Отладка:** Если возникают проблемы, включите `--debug` для диагностики.

## Порядок применения изменений

1. Добавить заголовки в `digital_codec.h` и `digital_codec.cpp`
2. Применить изменения в порядке, указанном выше
3. Пересобрать проект: `cmake --build build`
4. Протестировать функциональность


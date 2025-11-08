"""
LightCrypto GUI - Панель параметров Custom Digital Codec
Переиспользуемый компонент для управления параметрами кодека
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import json
import random
import re

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.constants import *
from common.config import ConfigManager
from common.utils import scan_csv_files, analyze_csv, validate_codec_params


class CodecPanel:
    """
    Панель управления параметрами цифрового кодека
    """
    
    def __init__(self, parent, config: ConfigManager, terminal=None):
        """
        Args:
            parent: Родительский виджет
            config: Менеджер конфигурации
            terminal: Объект терминала для вывода сообщений (optional)
        """
        self.parent = parent
        self.config = config
        self.terminal = terminal
        
        # Переменные параметров
        self.csv_var = tk.StringVar()
        self.M_var = tk.IntVar(value=config.get_custom_M())
        self.Q_var = tk.IntVar(value=config.get_custom_Q())
        self.auto_Q_var = tk.BooleanVar(value=config.get_custom_auto_q())
        self.funType_var = tk.IntVar(value=config.get_custom_funType())
        self.h1_var = tk.IntVar(value=config.get_custom_h1())
        self.h2_var = tk.IntVar(value=config.get_custom_h2())
        
        # Данные CSV
        self.csv_analysis = None
        self.csv_files = []
        
        # Создание панели
        self.frame = tk.LabelFrame(
            parent,
            text=f"{EMOJI_SETTINGS} Параметры цифрового кодека",
            font=FONT_TITLE,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            padx=PADDING_FRAME,
            pady=PADDING_FRAME
        )
        
        self._create_widgets()
        self._scan_csv_files()
        
        # Загрузка последнего CSV
        last_csv = config.get_custom_csv()
        if last_csv and last_csv in self.csv_files:
            self.csv_var.set(last_csv)
            self._on_csv_selected()
    
    def pack(self, **kwargs):
        """Pack метод для размещения панели"""
        self.frame.pack(**kwargs)
    
    def _create_widgets(self):
        """Создание всех элементов панели"""
        # CSV файл
        self._create_csv_section()
        
        # Параметры алгоритма
        self._create_params_section()
        
        # Управление профилями
        self._create_profiles_section()
        
        # Статус конфигурации
        self._create_status_section()
    
    def _create_csv_section(self):
        """Секция выбора CSV"""
        csv_frame = tk.LabelFrame(
            self.frame,
            text="Файл ключа (CSV)",
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            padx=10,
            pady=5
        )
        csv_frame.pack(fill=tk.X, pady=10)
        
        # Первый ряд: Combobox + кнопки
        row1 = tk.Frame(csv_frame, bg=COLOR_PANEL)
        row1.pack(fill=tk.X, pady=5)
        
        self.csv_combo = ttk.Combobox(
            row1,
            textvariable=self.csv_var,
            values=[],
            state='readonly',
            width=40
        )
        self.csv_combo.pack(side=tk.LEFT, padx=5)
        self.csv_combo.bind('<<ComboboxSelected>>', lambda e: self._on_csv_selected())
        
        browse_btn = tk.Button(
            row1,
            text=f"{EMOJI_FOLDER} Обзор",
            font=FONT_BUTTON,
            bg=COLOR_INFO,
            fg='white',
            command=self._browse_csv,
            cursor='hand2'
        )
        browse_btn.pack(side=tk.LEFT, padx=5)
        
        refresh_btn = tk.Button(
            row1,
            text=f"{EMOJI_REFRESH} Обновить",
            font=FONT_BUTTON,
            bg=COLOR_INFO,
            fg='white',
            command=self._scan_csv_files,
            cursor='hand2'
        )
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        # Второй ряд: Информация о CSV
        self.csv_info_label = tk.Label(
            csv_frame,
            text=f"{EMOJI_BULB} Выберите CSV файл с коэффициентами",
            font=FONT_NORMAL,
            bg=COLOR_STATUS_WARN,
            fg=COLOR_TEXT_PRIMARY,
            anchor=tk.W,
            padx=10,
            pady=5,
            wraplength=650,
            justify=tk.LEFT
        )
        self.csv_info_label.pack(fill=tk.X, pady=5)
    
    def _create_params_section(self):
        """Секция параметров алгоритма"""
        params_frame = tk.LabelFrame(
            self.frame,
            text="Параметры алгоритма",
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            padx=10,
            pady=5
        )
        params_frame.pack(fill=tk.X, pady=10)
        
        # M (разрядность)
        m_frame = tk.Frame(params_frame, bg=COLOR_PANEL)
        m_frame.pack(fill=tk.X, pady=5)
        
        m_label = tk.Label(
            m_frame,
            text="M (разрядность):",
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            width=20,
            anchor=tk.W
        )
        m_label.pack(side=tk.LEFT)
        
        self.M_spinbox = tk.Spinbox(
            m_frame,
            from_=CODEC_M_MIN,
            to=CODEC_M_MAX,
            textvariable=self.M_var,
            font=FONT_NORMAL,
            width=10,
            command=self._validate_params
        )
        self.M_spinbox.pack(side=tk.LEFT, padx=5)
        self.M_spinbox.bind('<FocusOut>', lambda e: self._validate_params())
        
        m_info_btn = tk.Label(
            m_frame,
            text=EMOJI_INFO,
            font=FONT_EMOJI,
            bg=COLOR_PANEL,
            fg=COLOR_INFO,
            cursor='hand2'
        )
        m_info_btn.pack(side=tk.LEFT, padx=5)
        self._create_tooltip(m_info_btn, TOOLTIP_M)
        
        # Q (информационные биты)
        q_frame = tk.Frame(params_frame, bg=COLOR_PANEL)
        q_frame.pack(fill=tk.X, pady=5)
        
        q_label = tk.Label(
            q_frame,
            text="Q (информ. биты):",
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            width=20,
            anchor=tk.W
        )
        q_label.pack(side=tk.LEFT)
        
        self.Q_spinbox = tk.Spinbox(
            q_frame,
            from_=CODEC_Q_MIN,
            to=CODEC_Q_MAX,
            textvariable=self.Q_var,
            font=FONT_NORMAL,
            width=10,
            command=self._validate_params
        )
        self.Q_spinbox.pack(side=tk.LEFT, padx=5)
        self.Q_spinbox.bind('<FocusOut>', lambda e: self._validate_params())
        
        q_info_btn = tk.Label(
            q_frame,
            text=EMOJI_INFO,
            font=FONT_EMOJI,
            bg=COLOR_PANEL,
            fg=COLOR_INFO,
            cursor='hand2'
        )
        q_info_btn.pack(side=tk.LEFT, padx=5)
        self._create_tooltip(q_info_btn, TOOLTIP_Q)
        
        # Авто Q из CSV
        self.auto_q_check = tk.Checkbutton(
            q_frame,
            text="☑ Авто из CSV",
            variable=self.auto_Q_var,
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            activebackground=COLOR_PANEL,
            selectcolor=COLOR_PANEL,
            command=self._on_auto_q_changed
        )
        self.auto_q_check.pack(side=tk.LEFT, padx=10)
        
        # Тип функции
        fun_frame = tk.Frame(params_frame, bg=COLOR_PANEL)
        fun_frame.pack(fill=tk.X, pady=5)
        
        fun_label = tk.Label(
            fun_frame,
            text="Тип функции:",
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            width=20,
            anchor=tk.W
        )
        fun_label.pack(side=tk.LEFT)
        
        self.funType_combo = ttk.Combobox(
            fun_frame,
            values=CODEC_FUN_TYPES,
            state='readonly',
            width=50
        )
        self.funType_combo.pack(side=tk.LEFT, padx=5)
        self.funType_combo.current(0)
        self.funType_combo.bind('<<ComboboxSelected>>', lambda e: self._on_funtype_selected())
        
        # Начальные состояния
        states_label = tk.Label(
            params_frame,
            text="Начальные состояния:",
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY
        )
        states_label.pack(anchor=tk.W, pady=(10, 5))
        
        states_frame = tk.Frame(params_frame, bg=COLOR_PANEL)
        states_frame.pack(fill=tk.X, pady=5)
        
        # h1
        h1_label = tk.Label(
            states_frame,
            text="h1:",
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY
        )
        h1_label.pack(side=tk.LEFT, padx=5)
        
        h1_spinbox = tk.Spinbox(
            states_frame,
            from_=-2147483648,
            to=2147483647,
            textvariable=self.h1_var,
            font=FONT_NORMAL,
            width=10
        )
        h1_spinbox.pack(side=tk.LEFT, padx=5)
        
        # h2
        h2_label = tk.Label(
            states_frame,
            text="h2:",
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY
        )
        h2_label.pack(side=tk.LEFT, padx=15)
        
        h2_spinbox = tk.Spinbox(
            states_frame,
            from_=-2147483648,
            to=2147483647,
            textvariable=self.h2_var,
            font=FONT_NORMAL,
            width=10
        )
        h2_spinbox.pack(side=tk.LEFT, padx=5)
        
        # Случайно
        random_btn = tk.Button(
            states_frame,
            text=f"{EMOJI_RANDOM} Случайно",
            font=FONT_BUTTON,
            bg=COLOR_WARNING,
            fg='white',
            command=self._randomize_states,
            cursor='hand2'
        )
        random_btn.pack(side=tk.LEFT, padx=10)
        
        # Tooltip для h1/h2
        info_btn = tk.Label(
            states_frame,
            text=EMOJI_INFO,
            font=FONT_EMOJI,
            bg=COLOR_PANEL,
            fg=COLOR_INFO,
            cursor='hand2'
        )
        info_btn.pack(side=tk.LEFT, padx=5)
        self._create_tooltip(info_btn, TOOLTIP_H1_H2)
    
    def _create_profiles_section(self):
        """Секция управления профилями"""
        profiles_frame = tk.LabelFrame(
            self.frame,
            text="Управление профилями",
            font=FONT_NORMAL,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            padx=10,
            pady=5
        )
        profiles_frame.pack(fill=tk.X, pady=10)
        
        btn_row = tk.Frame(profiles_frame, bg=COLOR_PANEL)
        btn_row.pack(fill=tk.X, pady=5)
        
        save_btn = tk.Button(
            btn_row,
            text=f"{EMOJI_SAVE} Сохранить",
            font=FONT_BUTTON,
            bg=COLOR_SUCCESS,
            fg='white',
            command=self._save_profile,
            cursor='hand2'
        )
        save_btn.pack(side=tk.LEFT, padx=5)
        
        load_btn = tk.Button(
            btn_row,
            text=f"{EMOJI_LOAD} Загрузить",
            font=FONT_BUTTON,
            bg=COLOR_INFO,
            fg='white',
            command=self._load_profile,
            cursor='hand2'
        )
        load_btn.pack(side=tk.LEFT, padx=5)
        
        reset_btn = tk.Button(
            btn_row,
            text=f"{EMOJI_REFRESH} Сброс",
            font=FONT_BUTTON,
            bg=COLOR_WARNING,
            fg='white',
            command=self._reset_to_defaults,
            cursor='hand2'
        )
        reset_btn.pack(side=tk.LEFT, padx=5)
        
        copy_btn = tk.Button(
            btn_row,
            text=f"{EMOJI_COPY} Копировать команду",
            font=FONT_BUTTON,
            bg=COLOR_INFO,
            fg='white',
            command=self._copy_command,
            cursor='hand2'
        )
        copy_btn.pack(side=tk.LEFT, padx=5)
    
    def _create_status_section(self):
        """Секция статуса конфигурации"""
        self.status_frame = tk.LabelFrame(
            self.frame,
            text="Статус конфигурации",
            font=FONT_NORMAL,
            bg=COLOR_STATUS_OK,
            fg=COLOR_TEXT_PRIMARY,
            padx=10,
            pady=5
        )
        self.status_frame.pack(fill=tk.X, pady=10)
        
        self.status_label = tk.Label(
            self.status_frame,
            text=f"{EMOJI_SUCCESS} Выберите CSV файл для начала",
            font=FONT_NORMAL,
            bg=COLOR_STATUS_OK,
            fg=COLOR_TEXT_PRIMARY,
            wraplength=650,
            justify=tk.LEFT,
            anchor=tk.W
        )
        self.status_label.pack(fill=tk.X, pady=5)
    
    def _create_tooltip(self, widget, text):
        """Создание всплывающей подсказки"""
        def show_tooltip(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            label = tk.Label(
                tooltip,
                text=text,
                background=COLOR_STATUS_WARN,
                relief=tk.SOLID,
                borderwidth=1,
                font=FONT_NORMAL,
                wraplength=400,
                justify=tk.LEFT,
                padx=10,
                pady=5
            )
            label.pack()
            
            widget.tooltip = tooltip
        
        def hide_tooltip(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                del widget.tooltip
        
        widget.bind('<Enter>', show_tooltip)
        widget.bind('<Leave>', hide_tooltip)
    
    def _scan_csv_files(self):
        """Сканирование директории с CSV файлами"""
        self.csv_files = scan_csv_files()
        self.csv_combo['values'] = self.csv_files
        
        if self.terminal:
            self.terminal.print_to_terminal(
                f"{EMOJI_INFO} Найдено CSV файлов: {len(self.csv_files)}",
                'info'
            )
    
    def _browse_csv(self):
        """Открытие диалога выбора CSV файла"""
        filename = filedialog.askopenfilename(
            title="Выберите CSV файл с коэффициентами",
            initialdir=CIPHER_KEYS_DIR,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if filename:
            basename = os.path.basename(filename)
            if basename not in self.csv_files:
                self.csv_files.append(basename)
                self.csv_combo['values'] = self.csv_files
            
            self.csv_var.set(basename)
            self._on_csv_selected()
    
    def _on_csv_selected(self):
        """Обработка выбора CSV файла"""
        csv_name = self.csv_var.get()
        if not csv_name:
            return
        
        csv_path = os.path.join(CIPHER_KEYS_DIR, csv_name)
        
        # Анализ CSV
        self.csv_analysis = analyze_csv(csv_path)
        
        if not self.csv_analysis['success']:
            error_msg = self.csv_analysis['error']
            self.csv_info_label.config(
                text=f"{EMOJI_ERROR} Ошибка: {error_msg}",
                bg=COLOR_STATUS_ERROR
            )
            if self.terminal:
                self.terminal.print_to_terminal(f"{EMOJI_ERROR} CSV ошибка: {error_msg}", 'error')
            return
        
        # Обновление информации
        rows = self.csv_analysis['rows']
        cols = self.csv_analysis['cols']
        Q = self.csv_analysis['Q']
        rec_M = self.csv_analysis['recommended_M']
        
        info_text = (
            f"{EMOJI_BULB} Авто-определено: {rows} строк (Q={Q}), "
            f"{cols} столбцов (функции {self._format_fun_types(cols)})\n"
            f"Рекомендуемые параметры: M={rec_M}, Q={Q}, fun=1"
        )
        
        self.csv_info_label.config(text=info_text, bg=COLOR_STATUS_WARN)
        
        # Автоустановка Q если включено
        if self.auto_Q_var.get():
            self.Q_var.set(Q)
            self.Q_spinbox.config(state='readonly')
        
        # Автоустановка M (рекомендуемое)
        self.M_var.set(rec_M)
        
        # Обновление списка допустимых функций
        self._update_funtype_combo()
        
        if self.terminal:
            self.terminal.print_to_terminal(
                f"{EMOJI_SUCCESS} CSV загружен: {csv_name} (строк: {rows}, Q: {Q})",
                'success'
            )
        
        # Сохранение в конфиг
        self.config.set_custom_csv(csv_name)
        
        # Валидация
        self._validate_params()
    
    def _format_fun_types(self, cols):
        """Форматирование допустимых типов функций"""
        if cols == 3:
            return "1-4"
        elif cols == 4:
            return "5"
        return "неизвестно"
    
    def _update_funtype_combo(self):
        """Обновление списка допустимых типов функций"""
        if not self.csv_analysis or not self.csv_analysis['success']:
            return
        
        valid_types = self.csv_analysis['valid_fun_types']
        
        # Обновление списка
        updated_types = []
        for i, funtype_str in enumerate(CODEC_FUN_TYPES, start=1):
            if i in valid_types:
                updated_types.append(funtype_str)
            else:
                updated_types.append(f"[Недоступно] {funtype_str}")
        
        self.funType_combo['values'] = updated_types
        
        # Установка первого допустимого
        if valid_types:
            self.funType_combo.current(valid_types[0] - 1)
    
    def _on_auto_q_changed(self):
        """Обработка изменения чекбокса Авто Q"""
        if self.auto_Q_var.get():
            self.Q_spinbox.config(state='readonly')
            if self.csv_analysis and self.csv_analysis['success']:
                self.Q_var.set(self.csv_analysis['Q'])
        else:
            self.Q_spinbox.config(state='normal')
        
        self.config.set_custom_auto_q(self.auto_Q_var.get())
        self._validate_params()
    
    def _on_funtype_selected(self):
        """Обработка выбора типа функции"""
        selected_text = self.funType_combo.get()
        
        # Извлечение номера функции
        import re
        match = re.match(r'(\d+):', selected_text)
        if match:
            funtype = int(match.group(1))
            self.funType_var.set(funtype)
            self._validate_params()
    
    def _randomize_states(self):
        """Генерация случайных значений h1 и h2"""
        self.h1_var.set(random.randint(0, 100))
        self.h2_var.set(random.randint(0, 100))
        
        if self.terminal:
            self.terminal.print_to_terminal(
                f"{EMOJI_RANDOM} Случайные состояния: h1={self.h1_var.get()}, h2={self.h2_var.get()}",
                'info'
            )
    
    def _validate_params(self):
        """Валидация параметров конфигурации"""
        errors = []
        warnings = []
        
        M = self.M_var.get()
        Q = self.Q_var.get()
        
        # Проверка CSV
        if not self.csv_var.get():
            errors.append("CSV файл не выбран")
        elif not self.csv_analysis or not self.csv_analysis['success']:
            errors.append("CSV файл некорректен")
        else:
            csv_rows = self.csv_analysis['rows']
            
            # Валидация параметров
            valid, param_errors = validate_codec_params(M, Q, csv_rows)
            errors.extend(param_errors)
        
        # Предупреждения
        if M < CODEC_M_DEFAULT:
            warnings.append(f"M={M} меньше рекомендуемого значения ({CODEC_M_DEFAULT})")
        
        if self.h1_var.get() == self.h2_var.get():
            warnings.append("h1 и h2 имеют одинаковые значения")
        
        # Обновление статуса
        if errors:
            status_text = "\n".join([f"{EMOJI_ERROR} {e}" for e in errors])
            status_text += f"\n{EMOJI_WARNING} Запуск заблокирован"
            self.status_frame.config(bg=COLOR_STATUS_ERROR)
            self.status_label.config(
                text=status_text,
                bg=COLOR_STATUS_ERROR
            )
        elif warnings:
            status_text = "\n".join([f"{EMOJI_WARNING} {w}" for w in warnings])
            status_text += f"\n{EMOJI_INFO} Работать будет, но безопасность снижена"
            self.status_frame.config(bg=COLOR_STATUS_WARN)
            self.status_label.config(
                text=status_text,
                bg=COLOR_STATUS_WARN
            )
        else:
            status_text = (
                f"{EMOJI_SUCCESS} CSV выбран: {self.csv_var.get()}\n"
                f"{EMOJI_SUCCESS} Параметры валидны (M≥Q, строк=2^Q)\n"
                f"{EMOJI_SUCCESS} Готов к запуску"
            )
            self.status_frame.config(bg=COLOR_STATUS_OK)
            self.status_label.config(
                text=status_text,
                bg=COLOR_STATUS_OK
            )
        
        return len(errors) == 0
    
    def _save_profile(self):
        """Сохранение текущей конфигурации в профиль"""
        name = simpledialog.askstring(
            "Сохранить профиль",
            "Введите имя профиля:",
            parent=self.parent
        )
        
        if not name:
            return
        
        # Создание профиля
        profile = {
            'name': name,
            'csv_file': self.csv_var.get(),
            'M': self.M_var.get(),
            'Q': self.Q_var.get(),
            'funType': self.funType_var.get(),
            'h1': self.h1_var.get(),
            'h2': self.h2_var.get()
        }
        
        # Сохранение в файл
        os.makedirs(PROFILES_DIR, exist_ok=True)
        profile_path = os.path.join(PROFILES_DIR, f"{name}.json")
        
        try:
            with open(profile_path, 'w') as f:
                json.dump(profile, f, indent=4)
            
            messagebox.showinfo("Успех", f"Профиль сохранен: {name}")
            
            if self.terminal:
                self.terminal.print_to_terminal(
                    f"{EMOJI_SUCCESS} Профиль сохранен: {profile_path}",
                    'success'
                )
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить профиль: {e}")
    
    def _load_profile(self):
        """Загрузка профиля"""
        if not os.path.isdir(PROFILES_DIR):
            messagebox.showinfo("Информация", "Нет сохраненных профилей")
            return
        
        profiles = [f[:-5] for f in os.listdir(PROFILES_DIR) if f.endswith('.json')]
        
        if not profiles:
            messagebox.showinfo("Информация", "Нет сохраненных профилей")
            return
        
        # Простой диалог выбора
        profile_name = simpledialog.askstring(
            "Загрузить профиль",
            f"Доступные профили:\n{', '.join(profiles)}\n\nВведите имя профиля:",
            parent=self.parent
        )
        
        if not profile_name:
            return
        
        profile_path = os.path.join(PROFILES_DIR, f"{profile_name}.json")
        
        if not os.path.isfile(profile_path):
            messagebox.showerror("Ошибка", f"Профиль не найден: {profile_name}")
            return
        
        try:
            with open(profile_path, 'r') as f:
                profile = json.load(f)
            
            # Загрузка параметров
            self.csv_var.set(profile.get('csv_file', ''))
            self.M_var.set(profile.get('M', CODEC_M_DEFAULT))
            self.Q_var.set(profile.get('Q', CODEC_Q_DEFAULT))
            self.funType_var.set(profile.get('funType', 1))
            self.h1_var.set(profile.get('h1', CODEC_H1_DEFAULT))
            self.h2_var.set(profile.get('h2', CODEC_H2_DEFAULT))
            
            # Обновление интерфейса
            self._on_csv_selected()
            self.funType_combo.current(self.funType_var.get() - 1)
            
            messagebox.showinfo("Успех", f"Профиль загружен: {profile_name}")
            
            if self.terminal:
                self.terminal.print_to_terminal(
                    f"{EMOJI_SUCCESS} Профиль загружен: {profile_name}",
                    'success'
                )
        
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить профиль: {e}")
    
    def _reset_to_defaults(self):
        """Сброс к значениям по умолчанию"""
        response = messagebox.askyesno(
            "Подтверждение",
            "Сбросить все параметры к значениям по умолчанию?"
        )
        
        if not response:
            return
        
        self.csv_var.set('')
        self.M_var.set(CODEC_M_DEFAULT)
        self.Q_var.set(CODEC_Q_DEFAULT)
        self.funType_var.set(1)
        self.h1_var.set(CODEC_H1_DEFAULT)
        self.h2_var.set(CODEC_H2_DEFAULT)
        self.auto_Q_var.set(True)
        
        self.csv_analysis = None
        self.csv_info_label.config(
            text=f"{EMOJI_BULB} Выберите CSV файл с коэффициентами",
            bg=COLOR_STATUS_WARN
        )
        
        self._validate_params()
        
        if self.terminal:
            self.terminal.print_to_terminal(
                f"{EMOJI_INFO} Параметры сброшены к умолчанию",
                'info'
            )
    
    def _copy_command(self):
        """Копирование команды в буфер обмена"""
        csv_name = self.csv_var.get()
        if not csv_name:
            messagebox.showwarning("Внимание", "Сначала выберите CSV файл")
            return
        
        cmd_parts = [
            '--codec', f'CipherKeys/{csv_name}',
            '--M', str(self.M_var.get()),
            '--Q', str(self.Q_var.get()),
            '--fun', str(self.funType_var.get()),
            '--h1', str(self.h1_var.get()),
            '--h2', str(self.h2_var.get())
        ]
        
        command = ' '.join(cmd_parts)
        
        # Копирование в буфер обмена
        self.parent.clipboard_clear()
        self.parent.clipboard_append(command)
        self.parent.update()
        
        messagebox.showinfo("Успех", "Параметры скопированы в буфер обмена!")
        
        if self.terminal:
            self.terminal.print_to_terminal(
                f"{EMOJI_COPY} Параметры скопированы: {command}",
                'info'
            )
    
    def get_params(self):
        """Получение текущих параметров"""
        return {
            'csv_file': self.csv_var.get(),
            'csv_path': os.path.join(CIPHER_KEYS_DIR, self.csv_var.get()) if self.csv_var.get() else '',
            'M': self.M_var.get(),
            'Q': self.Q_var.get(),
            'funType': self.funType_var.get(),
            'h1': self.h1_var.get(),
            'h2': self.h2_var.get()
        }
    
    def save_to_config(self):
        """Сохранение параметров в конфигурацию"""
        self.config.set_custom_csv(self.csv_var.get())
        self.config.set_custom_M(self.M_var.get())
        self.config.set_custom_Q(self.Q_var.get())
        self.config.set_custom_funType(self.funType_var.get())
        self.config.set_custom_h1(self.h1_var.get())
        self.config.set_custom_h2(self.h2_var.get())
        self.config.set_custom_auto_q(self.auto_Q_var.get())
    
    def is_valid(self):
        """Проверка валидности текущих параметров"""
        return self._validate_params()


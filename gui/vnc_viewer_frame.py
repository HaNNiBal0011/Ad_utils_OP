# gui/vnc_viewer_frame.py - ОПТИМИЗИРОВАННАЯ ВЕРСИЯ ДЛЯ ПЛАВНОЙ РАБОТЫ
import customtkinter as ctk
from tkinter import Canvas, messagebox
import socket
import threading
import struct
import logging
from typing import Optional, Tuple, Dict, Any
from PIL import Image, ImageTk
import queue
import time
import random
try:
    from Crypto.Cipher import DES
except ImportError:
    DES = None
import hashlib

logger = logging.getLogger(__name__)

class VNCViewerFrame(ctk.CTkFrame):
    """Высокопроизводительный VNC клиент с плавным отображением."""
    
    # RFB Protocol constants
    RFB_VERSION_3_8 = b"RFB 003.008\n"
    
    # Security types
    SECURITY_NONE = 1
    SECURITY_VNC = 2
    SECURITY_ULTRA_MS_LOGON_II = 117
    
    # Client message types
    SET_ENCODINGS = 2
    FRAMEBUFFER_UPDATE_REQUEST = 3
    KEY_EVENT = 4
    POINTER_EVENT = 5
    
    # Server message types
    FRAMEBUFFER_UPDATE = 0
    SET_COLOR_MAP_ENTRIES = 1
    BELL = 2
    SERVER_CUT_TEXT = 3
    
    # Encoding types
    ENCODING_RAW = 0
    ENCODING_COPYRECT = 1
    ENCODING_RRE = 2
    
    def __init__(self, parent, app):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        
        self.app = app
        self.socket = None
        self.connected = False
        self.screen_width = 0
        self.screen_height = 0
        self.pixel_format = None
        self.framebuffer = None
        
        # ОПТИМИЗАЦИЯ: Минимальные очереди для максимальной скорости
        self.update_queue = queue.Queue(maxsize=3)  # Уменьшили размер очереди
        
        # Флаги состояния
        self.receiving_thread = None
        self._stop_threads = threading.Event()
        
        # СТАБИЛЬНОСТЬ: Сбалансированные настройки для надежности
        self.update_request_interval = 0.033        # 30 FPS (стабильно)
        self.canvas_update_interval = 0.033         # 30 FPS для UI
        self.continuous_update_interval = 0.05      # 20 FPS continuous
        self.force_update_interval = 0.2            # 5 FPS принудительно
        
        # УПРОЩЕНИЕ: Консервативный контроль pending requests
        self.pending_update_requests = 0
        self.max_pending_requests = 2  # Уменьшили для стабильности
        self.last_update_request_time = 0
        self.last_server_response_time = time.time()
        
        # ПРОИЗВОДИТЕЛЬНОСТЬ: Быстрые таймеры
        self.force_update_timer = None
        self.continuous_update_timer = None
        self.last_force_update = 0
        
        # ОПТИМИЗАЦИЯ: Быстрое обновление canvas
        self.pending_canvas_update = False
        self.last_canvas_update = 0
        
        # СТАБИЛЬНОСТЬ: Упрощенная стратегия обновлений
        self.continuous_updates = False  # По умолчанию выключены для стабильности
        
        # Статистика (упрощенная)
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.updates_per_second = 0
        self.last_update_count_time = time.time()
        self.update_count = 0
        
        # ОПТИМИЗАЦИЯ: Прямое кэширование изображений
        self.image_cache_enabled = True
        self.last_image_hash = None
        self.cached_photo = None
        
        # Счетчики ошибок (упрощенные)
        self.protocol_errors = 0
        self.max_protocol_errors = 20  # Больше толерантности
        
        # Настройка UI
        self._setup_ui()
        
        # Запуск обработчика событий (оптимизированный)
        self._start_event_processor()
        
        # Запуск обновления статистики
        self._update_stats()
    
    def _setup_ui(self):
        """Настройка пользовательского интерфейса."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self._create_connection_panel()
        self._create_viewer_area()
        self._create_status_panel()
        self._create_control_panel()
    
    def _create_connection_panel(self):
        """Создание панели подключения."""
        connection_frame = ctk.CTkFrame(self)
        connection_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        # Поле ввода адреса
        ctk.CTkLabel(connection_frame, text="VNC Сервер:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        self.server_entry = ctk.CTkEntry(connection_frame, width=200, placeholder_text="192.168.1.100:5900")
        self.server_entry.grid(row=0, column=1, padx=5, pady=5)
        self.server_entry.insert(0, "192.168.1.100:5900")
        
        # Поле ввода пароля
        ctk.CTkLabel(connection_frame, text="Пароль:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        
        self.password_entry = ctk.CTkEntry(connection_frame, width=150, show="*", placeholder_text="VNC пароль")
        self.password_entry.grid(row=0, column=3, padx=5, pady=5)
        self.password_entry.bind("<Return>", lambda e: self.connect_to_vnc())
        
        # Кнопки управления
        self.connect_button = ctk.CTkButton(
            connection_frame, 
            text="Подключиться", 
            command=self.connect_to_vnc,
            width=120
        )
        self.connect_button.grid(row=0, column=4, padx=5, pady=5)
        
        self.disconnect_button = ctk.CTkButton(
            connection_frame, 
            text="Отключиться", 
            command=self.disconnect_from_vnc,
            width=120,
            state="disabled"
        )
        self.disconnect_button.grid(row=0, column=5, padx=5, pady=5)
        
        # ПРОИЗВОДИТЕЛЬНОСТЬ: Настройки качества с акцентом на скорость
        quality_frame = ctk.CTkFrame(connection_frame, fg_color="transparent")
        quality_frame.grid(row=1, column=0, columnspan=6, pady=5)
        
        ctk.CTkLabel(quality_frame, text="Режим:").pack(side="left", padx=5)
        
        self.quality_var = ctk.StringVar(value="performance")
        quality_menu = ctk.CTkSegmentedButton(
            quality_frame,
            values=["Производительность", "Качество", "Сбалансированный"],
            variable=self.quality_var,
            command=self._on_quality_change
        )
        quality_menu.pack(side="left", padx=5)
        quality_menu.set("Производительность")
        
        # Непрерывные обновления (консервативно выключены по умолчанию)
        self.continuous_var = ctk.BooleanVar(value=False)
        self.continuous_checkbox = ctk.CTkCheckBox(
            quality_frame,
            text="Непрерывные обновления",
            variable=self.continuous_var,
            command=self._on_continuous_change
        )
        self.continuous_checkbox.pack(side="left", padx=20)
        
        # View-only режим
        self.view_only_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            quality_frame,
            text="Только просмотр",
            variable=self.view_only_var
        ).pack(side="left", padx=20)
        
        # Масштабирование
        scale_frame = ctk.CTkFrame(quality_frame, fg_color="transparent")
        scale_frame.pack(side="left", padx=20)
        
        ctk.CTkLabel(scale_frame, text="Масштаб:").pack(side="left", padx=5)
        
        self.scale_var = ctk.StringVar(value="100%")
        scale_menu = ctk.CTkSegmentedButton(
            scale_frame,
            values=["75%", "100%", "125%", "Авто"],
            variable=self.scale_var
        )
        scale_menu.pack(side="left", padx=5)
        scale_menu.set("100%")
    
    def _create_viewer_area(self):
        """Создание области просмотра."""
        viewer_frame = ctk.CTkFrame(self)
        viewer_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        viewer_frame.grid_rowconfigure(0, weight=1)
        viewer_frame.grid_columnconfigure(0, weight=1)
        
        # Canvas для отображения экрана (оптимизированный)
        self.canvas = Canvas(
            viewer_frame,
            bg="black",
            highlightthickness=0,
            # ПРОИЗВОДИТЕЛЬНОСТЬ: Отключаем double buffering для скорости
            confine=False
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        
        # Скроллбары
        v_scrollbar = ctk.CTkScrollbar(viewer_frame, orientation="vertical", command=self.canvas.yview)
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        
        h_scrollbar = ctk.CTkScrollbar(viewer_frame, orientation="horizontal", command=self.canvas.xview)
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        self.canvas.configure(
            yscrollcommand=v_scrollbar.set,
            xscrollcommand=h_scrollbar.set
        )
        
        # Привязка событий мыши и клавиатуры
        self._bind_events()
    
    def _bind_events(self):
        """Привязка событий ввода."""
        # Мышь
        self.canvas.bind("<Button-1>", self._on_mouse_click)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_release)
        self.canvas.bind("<B1-Motion>", self._on_mouse_motion)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<ButtonRelease-3>", self._on_right_release)
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        
        # Клавиатура
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())
        self.canvas.bind("<KeyPress>", self._on_key_press)
        self.canvas.bind("<KeyRelease>", self._on_key_release)
    
    def _create_status_panel(self):
        """Создание панели статуса."""
        status_frame = ctk.CTkFrame(self)
        status_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        
        self.status_label = ctk.CTkLabel(status_frame, text="Отключено", font=ctk.CTkFont(size=12))
        self.status_label.pack(side="left", padx=10)
        
        self.resolution_label = ctk.CTkLabel(status_frame, text="", font=ctk.CTkFont(size=12))
        self.resolution_label.pack(side="left", padx=20)
        
        self.fps_label = ctk.CTkLabel(status_frame, text="", font=ctk.CTkFont(size=12))
        self.fps_label.pack(side="left", padx=20)
        
        self.ups_label = ctk.CTkLabel(status_frame, text="", font=ctk.CTkFont(size=12))
        self.ups_label.pack(side="left", padx=20)
        
        # НОВОЕ: Статус последнего обновления экрана
        self.last_update_label = ctk.CTkLabel(status_frame, text="", font=ctk.CTkFont(size=12))
        self.last_update_label.pack(side="left", padx=20)
        
        # Индикатор активности
        self.activity_indicator = ctk.CTkLabel(status_frame, text="⚫", font=ctk.CTkFont(size=16))
        self.activity_indicator.pack(side="right", padx=10)
    
    def _create_control_panel(self):
        """Создание панели управления."""
        control_frame = ctk.CTkFrame(self)
        control_frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        
        # Специальные клавиши
        ctk.CTkLabel(control_frame, text="Специальные клавиши:").pack(side="left", padx=5)
        
        ctk.CTkButton(control_frame, text="Ctrl+Alt+Del", command=self._send_ctrl_alt_del, width=100).pack(side="left", padx=5)
        ctk.CTkButton(control_frame, text="Alt+Tab", command=self._send_alt_tab, width=80).pack(side="left", padx=5)
        ctk.CTkButton(control_frame, text="Esc", command=self._send_escape, width=50).pack(side="left", padx=5)
        
        # Кнопка скриншота
        ctk.CTkButton(control_frame, text="📷 Скриншот", command=self._take_screenshot, width=100).pack(side="right", padx=5)
        
        # НОВОЕ: Кнопка принудительного обновления экрана
        ctk.CTkButton(
            control_frame,
            text="🔄 Обновить экран",
            command=self._force_screen_refresh,
            width=120,
            fg_color="transparent",
            border_width=1
        ).pack(side="right", padx=5)
    
    def connect_to_vnc(self):
        """Подключение к VNC серверу."""
        server_address = self.server_entry.get().strip()
        if not server_address:
            messagebox.showerror("Ошибка", "Введите адрес VNC сервера")
            return
        
        # Парсинг адреса
        if ':' in server_address:
            host, port = server_address.split(':')
            port = int(port)
        else:
            host = server_address
            port = 5900
        
        password = self.password_entry.get()
        
        # Запуск подключения в отдельном потоке
        threading.Thread(
            target=self._connect_thread,
            args=(host, port, password),
            daemon=True
        ).start()
    
    def _connect_thread(self, host: str, port: int, password: str):
        """Поток подключения к VNC серверу."""
        try:
            self._update_status("Подключение...")
            
            # Создание сокета
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((host, port))
            
            # ПРОИЗВОДИТЕЛЬНОСТЬ: Оптимизация сокета для низкой задержки
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.socket.settimeout(2)  # Быстрый таймаут для производительности
            
            # Handshake и аутентификация
            if not self._handshake():
                raise Exception("Ошибка handshake")
            
            if not self._authenticate(password):
                raise Exception("Ошибка аутентификации")
            
            if not self._initialize():
                raise Exception("Ошибка инициализации")
            
            self.connected = True
            self._update_status(f"Подключено к {host}:{port}")
            
            # Сброс счетчиков
            self.pending_update_requests = 0
            self.last_server_response_time = time.time()
            self.protocol_errors = 0
            
            # НОВОЕ: Инициализация времени последнего framebuffer
            self.last_framebuffer_time = time.time()
            
            # Обновление UI
            self.after(0, self._on_connected)
            
            # Запуск потоков
            self._start_receiver_thread()
            
            # СТАБИЛЬНОСТЬ: Осторожный старт обновлений
            self.after(0, self._start_high_performance_timers)
            self.after(100, lambda: self._request_framebuffer_update_stable(incremental=False))
            self.after(300, lambda: self._request_framebuffer_update_stable(incremental=True))
            
        except Exception as e:
            logger.error(f"Ошибка подключения: {e}")
            self._update_status(f"Ошибка: {str(e)}")
            self.after(0, self._on_connection_failed, str(e))
    
    def _handshake(self) -> bool:
        """VNC handshake."""
        try:
            server_version = self._recv_exact(12)
            logger.debug(f"Server version: {server_version}")
            self.socket.send(self.RFB_VERSION_3_8)
            return True
        except Exception as e:
            logger.error(f"Handshake error: {e}")
            return False
    
    def _authenticate(self, password: str) -> bool:
        """Аутентификация."""
        try:
            num_security_types = struct.unpack("!B", self._recv_exact(1))[0]
            
            if num_security_types == 0:
                reason_length = struct.unpack("!I", self._recv_exact(4))[0]
                reason = self._recv_exact(reason_length).decode()
                logger.error(f"Server error: {reason}")
                return False
            
            security_types = struct.unpack(f"!{num_security_types}B", self._recv_exact(num_security_types))
            logger.debug(f"Security types: {security_types}")
            
            # Выбираем подходящий тип безопасности
            if self.SECURITY_VNC in security_types:
                selected_type = self.SECURITY_VNC
            elif self.SECURITY_NONE in security_types:
                selected_type = self.SECURITY_NONE
            else:
                logger.error(f"No supported security types in {security_types}")
                return False
            
            self.socket.send(struct.pack("!B", selected_type))
            
            if selected_type == self.SECURITY_NONE:
                return self._auth_none()
            elif selected_type == self.SECURITY_VNC:
                return self._auth_vnc(password)
            
            return False
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    def _auth_none(self) -> bool:
        """Аутентификация без пароля."""
        try:
            result_data = self._recv_exact(4)
            result = struct.unpack("!I", result_data)[0]
            
            if result == 0:
                logger.info("No authentication successful")
                return True
            else:
                logger.error(f"No authentication failed: {result}")
                return False
        except Exception as e:
            logger.error(f"No auth error: {e}")
            return False
    
    def _auth_vnc(self, password: str) -> bool:
        """VNC аутентификация."""
        try:
            challenge = self._recv_exact(16)
            response = self._encrypt_password(password or "", challenge)
            self.socket.send(response)
            
            result_data = self._recv_exact(4)
            result = struct.unpack("!I", result_data)[0]
            
            if result == 0:
                logger.info("VNC authentication successful")
                return True
            else:
                logger.error(f"VNC authentication failed: {result}")
                return False
                
        except Exception as e:
            logger.error(f"VNC auth error: {e}")
            return False
    
    def _encrypt_password(self, password: str, challenge: bytes) -> bytes:
        """Шифрование пароля для VNC."""
        if DES:
            password_bytes = password[:8].ljust(8, '\0').encode('utf-8')[:8]
            password_bytes = password_bytes.ljust(8, b'\0')[:8]
            password_bytes = bytes(self._reverse_bits(b) for b in password_bytes)
            
            cipher = DES.new(password_bytes, DES.MODE_ECB)
            return cipher.encrypt(challenge)
        else:
            # Простая реализация без DES
            if not password:
                return b'\x00' * 16
            
            key_bytes = password[:8].ljust(8, '\0').encode('utf-8')[:8]
            key_bytes = key_bytes.ljust(8, b'\0')[:8]
            key_bytes = bytes(self._reverse_bits(b) for b in key_bytes)
            
            result = bytearray(16)
            for i in range(16):
                result[i] = challenge[i] ^ key_bytes[i % 8]
            
            return bytes(result)
    
    def _reverse_bits(self, byte: int) -> int:
        """Реверс битов в байте."""
        return int('{:08b}'.format(byte)[::-1], 2)
    
    def _initialize(self) -> bool:
        """Инициализация VNC соединения."""
        try:
            # ClientInit
            self.socket.send(struct.pack("!B", 1))  # shared
            
            # ServerInit
            size_data = self._recv_exact(4)
            self.screen_width, self.screen_height = struct.unpack("!HH", size_data)
            logger.info(f"Screen size: {self.screen_width}x{self.screen_height}")
            
            # Pixel format
            pixel_format_data = self._recv_exact(16)
            self.pixel_format = self._parse_pixel_format(pixel_format_data)
            
            # Desktop name
            name_length = struct.unpack("!I", self._recv_exact(4))[0]
            desktop_name = self._recv_exact(name_length).decode()
            logger.info(f"Desktop name: {desktop_name}")
            
            # Инициализация framebuffer
            self.framebuffer = Image.new('RGB', (self.screen_width, self.screen_height))
            
            # ПРОИЗВОДИТЕЛЬНОСТЬ: Минимальный набор кодировок для скорости
            self._set_encodings_optimized()
            
            return True
            
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            return False
    
    def _parse_pixel_format(self, data: bytes) -> Dict[str, Any]:
        """Парсинг формата пикселей."""
        return {
            'bits_per_pixel': data[0],
            'depth': data[1],
            'big_endian': bool(data[2]),
            'true_color': bool(data[3]),
            'red_max': struct.unpack("!H", data[4:6])[0],
            'green_max': struct.unpack("!H", data[6:8])[0],
            'blue_max': struct.unpack("!H", data[8:10])[0],
            'red_shift': data[10],
            'green_shift': data[11],
            'blue_shift': data[12]
        }
    
    def _set_encodings_optimized(self):
        """Установка оптимизированных кодировок для производительности."""
        # ПРОИЗВОДИТЕЛЬНОСТЬ: Только самые быстрые кодировки
        encodings = [
            self.ENCODING_RAW,       # 0 - Быстрая основная кодировка
            self.ENCODING_COPYRECT,  # 1 - Быстрое копирование областей
        ]
        
        message = struct.pack("!BBH", self.SET_ENCODINGS, 0, len(encodings))
        for encoding in encodings:
            message += struct.pack("!i", encoding)
        
        self.socket.send(message)
        logger.debug(f"Set optimized encodings: {encodings}")
    
    # ПРОИЗВОДИТЕЛЬНОСТЬ: Высокопроизводительные таймеры
    def _start_high_performance_timers(self):
        """Запуск стабильных таймеров."""
        logger.info("Starting stable timers for reliable display")
        self._schedule_continuous_update_stable()
        self._schedule_force_update_stable()
    
    def _schedule_continuous_update_stable(self):
        """СТАБИЛЬНОЕ планирование непрерывных обновлений."""
        if not self.connected:
            return
        
        # СТАБИЛЬНОСТЬ: Консервативные запросы
        if (self.continuous_var.get() and 
            self.pending_update_requests < 1):  # Максимум 1 pending для стабильности
            self._request_framebuffer_update_stable(incremental=True)
        
        # Стабильное повторение
        if self.connected:
            self.continuous_update_timer = self.after(50, self._schedule_continuous_update_stable)  # 20 FPS
    
    def _schedule_force_update_stable(self):
        """СТАБИЛЬНОЕ планирование принудительных обновлений."""
        if not self.connected:
            return
        
        current_time = time.time()
        
        # НОВОЕ: Автоматическое обновление если долго нет framebuffer updates
        time_since_last_frame = current_time - getattr(self, 'last_framebuffer_time', current_time)
        
        if time_since_last_frame > 2.0:  # Если 2+ секунд без обновлений
            logger.info(f"No framebuffer updates for {time_since_last_frame:.1f}s, forcing refresh")
            self._force_screen_refresh()
            self.last_framebuffer_time = current_time
        elif (current_time - self.last_force_update >= self.force_update_interval and 
              self.pending_update_requests < 1):
            self._request_framebuffer_update_stable(incremental=False)
            self.last_force_update = current_time
        
        if self.connected:
            self.force_update_timer = self.after(200, self._schedule_force_update_stable)  # 5 FPS
    
    def _request_framebuffer_update_fast(self, incremental: bool = True):
        """БЫСТРЫЙ запрос обновления framebuffer без throttling."""
        if not self.connected or not self.socket:
            return
        
        current_time = time.time()
        
        # ПРОИЗВОДИТЕЛЬНОСТЬ: Минимальный throttling
        if current_time - self.last_update_request_time < self.update_request_interval:
            return
        
        # ПРОИЗВОДИТЕЛЬНОСТЬ: Упрощенный контроль pending
        if self.pending_update_requests >= self.max_pending_requests:
            return
        
        try:
            if self.socket.fileno() == -1:
                return
            
            message = struct.pack(
                "!BBHHHH",
                self.FRAMEBUFFER_UPDATE_REQUEST,
                1 if incremental else 0,
                0, 0,
                self.screen_width, self.screen_height
            )
            
            self.socket.send(message)
            self.pending_update_requests += 1
            self.last_update_request_time = current_time
            
        except (OSError, socket.error):
            self.pending_update_requests = 0
        except Exception:
            self.pending_update_requests = 0
    
    def _start_receiver_thread(self):
        """Запуск потока приёма данных."""
        self._stop_threads.clear()
        
        self.receiving_thread = threading.Thread(
            target=self._receive_loop_optimized,
            daemon=True
        )
        self.receiving_thread.start()
        
        logger.info("Optimized receiver thread started")
    
    def _receive_loop_optimized(self):
        """СТАБИЛЬНЫЙ цикл приёма данных с обработкой UltraVNC."""
        consecutive_errors = 0
        max_consecutive_errors = 3
        unknown_message_count = 0
        last_unknown_reset = time.time()
        
        while self.connected and not self._stop_threads.is_set():
            try:
                # ИСПРАВЛЕНИЕ: Более надежная проверка сокета
                if not self.socket:
                    logger.debug("Socket is None, breaking receive loop")
                    break
                
                try:
                    socket_valid = self.socket.fileno() != -1
                except (OSError, AttributeError):
                    socket_valid = False
                
                if not socket_valid:
                    logger.debug("Socket is invalid, breaking receive loop")
                    break
                
                # Сброс счетчика неизвестных сообщений каждые 5 секунд
                current_time = time.time()
                if current_time - last_unknown_reset > 5:
                    if unknown_message_count > 10:
                        logger.warning(f"Reset unknown message count: {unknown_message_count}")
                    unknown_message_count = 0
                    last_unknown_reset = current_time
                
                # ИСПРАВЛЕНИЕ: Защита от спама неизвестных сообщений
                if unknown_message_count > 100:
                    logger.error("Too many unknown messages, requesting framebuffer update")
                    unknown_message_count = 0
                    self.after(0, lambda: self._request_framebuffer_update_stable(incremental=False))
                    time.sleep(0.1)  # Небольшая пауза
                
                # Быстрое чтение типа сообщения с обработкой ошибок
                try:
                    msg_type_data = self.socket.recv(1)
                except OSError as e:
                    if e.winerror == 10038:  # Socket operation on non-socket
                        logger.debug("Socket closed during recv")
                        break
                    elif e.winerror == 10054:  # Connection reset by peer
                        logger.info("Connection reset by peer")
                        break
                    else:
                        raise
                
                if not msg_type_data:
                    logger.debug("Empty message received, connection closed")
                    break
                
                message_type = struct.unpack("!B", msg_type_data)[0]
                
                if message_type == self.FRAMEBUFFER_UPDATE:
                    self._handle_framebuffer_update_stable()
                    consecutive_errors = 0
                    unknown_message_count = 0  # Сброс при получении реальных данных
                elif message_type == self.SET_COLOR_MAP_ENTRIES:
                    self._handle_colormap_entries_fast()
                elif message_type == self.BELL:
                    pass  # Игнорируем bell для производительности
                elif message_type == self.SERVER_CUT_TEXT:
                    self._handle_server_cut_text_fast()
                else:
                    # ИСПРАВЛЕНИЕ: Правильная обработка UltraVNC extensions
                    if message_type in [255, 33, 45, 36, 127, 253, 254]:
                        unknown_message_count += 1
                        # Вместо вызова метода просто логируем и пропускаем
                        if unknown_message_count % 50 == 1:
                            logger.debug(f"UltraVNC extension {message_type} (count: {unknown_message_count})")
                        continue
                    else:
                        unknown_message_count += 1
                        logger.warning(f"Truly unknown message type: {message_type}")
                        # Пытаемся продолжить без чтения дополнительных данных
                        continue
            
            except socket.timeout:
                # Таймаут - это нормально, продолжаем
                continue
            except ConnectionResetError:
                logger.info("Connection reset by server")
                break
            except ConnectionAbortedError:
                logger.info("Connection aborted")
                break
            except OSError as e:
                if e.winerror == 10038:  # WSAENOTSOCK
                    logger.debug("Socket operation on non-socket - connection closed")
                    break
                elif e.winerror == 10054:  # Connection reset
                    logger.info("Connection reset by peer")
                    break
                else:
                    logger.error(f"OS error in receive loop: {e}")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error("Too many consecutive OS errors, breaking")
                        break
                    time.sleep(0.1)
                    continue
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Unexpected error in receive loop: {e}")
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("Too many consecutive errors, breaking")
                    break
                # При ошибках сбрасываем pending
                self.pending_update_requests = 0
                time.sleep(0.1)
                continue
        
        logger.info("Receive loop ended")
        self.connected = False
        self._update_status("Соединение разорвано")
        self.after(0, self.disconnect_from_vnc)
    
    def _handle_framebuffer_update_stable(self):
        """СТАБИЛЬНАЯ обработка обновления framebuffer."""
        try:
            current_time = time.time()
            
            # Уменьшаем pending запросы
            if self.pending_update_requests > 0:
                self.pending_update_requests -= 1
            self.last_server_response_time = current_time
            
            # Пропускаем padding
            self._recv_exact(1)
            
            # Количество прямоугольников
            num_rectangles = struct.unpack("!H", self._recv_exact(2))[0]
            
            # СТАБИЛЬНОСТЬ: Ограничиваем количество прямоугольников для предотвращения зависания
            if num_rectangles > 1000:
                logger.warning(f"Too many rectangles: {num_rectangles}, limiting to 1000")
                num_rectangles = 1000
            
            rectangles_processed = 0
            
            # Обрабатываем прямоугольники более консервативно
            for i in range(num_rectangles):
                try:
                    rect_data = self._recv_exact(8)
                    x, y, w, h = struct.unpack("!HHHH", rect_data)
                    
                    encoding = struct.unpack("!i", self._recv_exact(4))[0]
                    
                    # СТАБИЛЬНОСТЬ: Проверяем размеры прямоугольника
                    if w <= 0 or h <= 0 or w > self.screen_width or h > self.screen_height:
                        logger.warning(f"Invalid rectangle size: {w}x{h}")
                        continue
                    
                    if encoding == self.ENCODING_RAW:
                        self._handle_raw_rectangle_stable(x, y, w, h)
                        rectangles_processed += 1
                    elif encoding == self.ENCODING_COPYRECT:
                        self._handle_copyrect_fast(x, y, w, h)
                        rectangles_processed += 1
                    else:
                        # Пропускаем неподдерживаемые кодировки
                        bytes_per_pixel = self.pixel_format['bits_per_pixel'] // 8
                        skip_size = w * h * bytes_per_pixel
                        if skip_size > 0 and skip_size < 100000000:  # Увеличенный лимит
                            logger.debug(f"Skipping unsupported encoding {encoding}, size: {skip_size}")
                            self._recv_exact(skip_size)
                        else:
                            logger.error(f"Skipping invalid rectangle size: {skip_size}")
                            break
                            
                except Exception as e:
                    logger.error(f"Error processing rectangle {i}: {e}")
                    # При ошибке прерываем обработку этого update
                    break
            
            # Обновляем изображение только если обработали прямоугольники
            if rectangles_processed > 0:
                # НОВОЕ: Отмечаем время получения реальных данных
                self.last_framebuffer_time = current_time
                
                self._schedule_canvas_update_stable()
                
                # Статистика
                self.frame_count += 1
                self.update_count += 1
            
            # СТАБИЛЬНОСТЬ: Более осторожная стратегия запросов
            if (self.continuous_var.get() and 
                self.pending_update_requests < 1 and  # Ограничиваем до 1
                rectangles_processed > 0):  # Запрашиваем только если получили данные
                self.after(50, lambda: self._request_framebuffer_update_stable(incremental=True))
            
        except Exception as e:
            logger.error(f"Stable framebuffer update error: {e}")
            if self.pending_update_requests > 0:
                self.pending_update_requests -= 1
    
    def _handle_raw_rectangle_stable(self, x: int, y: int, w: int, h: int):
        """СТАБИЛЬНАЯ обработка RAW прямоугольника."""
        bytes_per_pixel = self.pixel_format['bits_per_pixel'] // 8
        data_size = w * h * bytes_per_pixel
        
        # Логируем большие прямоугольники для отладки
        if data_size > 5000000:  # 5MB+
            logger.info(f"Processing large rectangle: {w}x{h}, {data_size/1024/1024:.1f}MB")
        
        # Читаем данные с проверкой
        try:
            pixel_data = self._recv_exact(data_size)
        except Exception as e:
            logger.error(f"Error reading raw rectangle data: {e}")
            raise
        
        # СТАБИЛЬНОСТЬ: Создаем изображение более безопасно
        try:
            if bytes_per_pixel == 4:  # 32-bit
                rect_image = self._create_image_stable_32bit(pixel_data, w, h)
            elif bytes_per_pixel == 3:  # 24-bit
                rect_image = self._create_image_stable_24bit(pixel_data, w, h)
            else:  # Для других форматов
                rect_image = Image.new('RGB', (w, h), (128, 128, 128))
            
            # Безопасная вставка в framebuffer
            if rect_image and self.framebuffer:
                self.framebuffer.paste(rect_image, (x, y))
                
        except Exception as e:
            logger.error(f"Error creating rectangle image: {e}")
            # При ошибке создаем простую заглушку
            try:
                rect_image = Image.new('RGB', (w, h), (64, 64, 64))
                self.framebuffer.paste(rect_image, (x, y))
            except:
                pass  # Игнорируем ошибки заглушки
    
    def _create_image_stable_32bit(self, pixel_data: bytes, w: int, h: int) -> Image.Image:
        """СТАБИЛЬНОЕ создание изображения из 32-bit данных."""
        try:
            rect_image = Image.new('RGB', (w, h))
            
            pixels = []
            data_len = len(pixel_data)
            
            # Проверяем размер данных
            expected_size = w * h * 4
            if data_len < expected_size:
                logger.warning(f"Insufficient pixel data: got {data_len}, expected {expected_size}")
                return Image.new('RGB', (w, h), (128, 128, 128))
            
            # Безопасная обработка пикселей
            for i in range(0, min(data_len, expected_size), 4):
                if i + 3 < data_len:
                    try:
                        b, g, r, _ = pixel_data[i:i+4]
                        pixels.append((r, g, b))
                    except (IndexError, ValueError):
                        pixels.append((128, 128, 128))  # Заглушка при ошибке
            
            if pixels:
                # Проверяем количество пикселей
                expected_pixels = w * h
                if len(pixels) < expected_pixels:
                    # Дополняем недостающие пиксели
                    pixels.extend([(128, 128, 128)] * (expected_pixels - len(pixels)))
                elif len(pixels) > expected_pixels:
                    # Обрезаем лишние пиксели
                    pixels = pixels[:expected_pixels]
                
                rect_image.putdata(pixels)
            
            return rect_image
            
        except Exception as e:
            logger.error(f"Error in stable 32bit image creation: {e}")
            return Image.new('RGB', (w, h), (64, 64, 64))
    
    def _create_image_stable_24bit(self, pixel_data: bytes, w: int, h: int) -> Image.Image:
        """СТАБИЛЬНОЕ создание изображения из 24-bit данных."""
        try:
            rect_image = Image.new('RGB', (w, h))
            
            pixels = []
            data_len = len(pixel_data)
            expected_size = w * h * 3
            
            if data_len < expected_size:
                logger.warning(f"Insufficient 24bit pixel data: got {data_len}, expected {expected_size}")
                return Image.new('RGB', (w, h), (128, 128, 128))
            
            for i in range(0, min(data_len, expected_size), 3):
                if i + 2 < data_len:
                    try:
                        b, g, r = pixel_data[i:i+3]
                        pixels.append((r, g, b))
                    except (IndexError, ValueError):
                        pixels.append((128, 128, 128))
            
            if pixels:
                expected_pixels = w * h
                if len(pixels) < expected_pixels:
                    pixels.extend([(128, 128, 128)] * (expected_pixels - len(pixels)))
                elif len(pixels) > expected_pixels:
                    pixels = pixels[:expected_pixels]
                
                rect_image.putdata(pixels)
            
            return rect_image
            
        except Exception as e:
            logger.error(f"Error in stable 24bit image creation: {e}")
            return Image.new('RGB', (w, h), (64, 64, 64))
    
    def _handle_copyrect_fast(self, x: int, y: int, w: int, h: int):
        """Быстрая обработка COPYRECT."""
        src_data = self._recv_exact(4)
        src_x, src_y = struct.unpack("!HH", src_data)
        
        # Быстрое копирование
        rect = self.framebuffer.crop((src_x, src_y, src_x + w, src_y + h))
        self.framebuffer.paste(rect, (x, y))
    
    def _handle_colormap_entries_fast(self):
        """Быстрая обработка colormap."""
        self._recv_exact(1)  # padding
        first_color = struct.unpack("!H", self._recv_exact(2))[0]
        num_colors = struct.unpack("!H", self._recv_exact(2))[0]
        self._recv_exact(num_colors * 6)  # Пропускаем данные цветов
    
    def _handle_server_cut_text_fast(self):
        """Быстрая обработка cut text."""
        self._recv_exact(3)  # padding
        text_length = struct.unpack("!I", self._recv_exact(4))[0]
        self._recv_exact(text_length)  # Пропускаем текст для производительности
    
    def _schedule_canvas_update_stable(self):
        """СТАБИЛЬНОЕ планирование обновления canvas."""
        current_time = time.time()
        
        # СТАБИЛЬНОСТЬ: Более консервативный throttling
        if current_time - self.last_canvas_update < self.canvas_update_interval:
            if not self.pending_canvas_update:
                self.pending_canvas_update = True
                delay = int((self.canvas_update_interval - (current_time - self.last_canvas_update)) * 1000)
                self.after(max(16, delay), self._update_canvas_fast)  # Минимум 16ms (60 FPS)
        else:
            self._update_canvas_fast()
    
    def _request_framebuffer_update_stable(self, incremental: bool = True):
        """СТАБИЛЬНЫЙ запрос обновления framebuffer."""
        if not self.connected or not self.socket:
            return
        
        current_time = time.time()
        
        # СТАБИЛЬНОСТЬ: Более строгий throttling
        if current_time - self.last_update_request_time < self.update_request_interval:
            return
        
        # СТАБИЛЬНОСТЬ: Консервативный контроль pending
        if self.pending_update_requests >= self.max_pending_requests:
            # Проверяем на зависшие запросы
            time_since_response = current_time - self.last_server_response_time
            if time_since_response > 3.0:  # 3 секунды без ответа
                logger.warning(f"Resetting pending requests after {time_since_response:.1f}s timeout")
                self.pending_update_requests = 0
            else:
                return
        
        try:
            # Проверяем валидность сокета
            try:
                socket_valid = self.socket.fileno() != -1
            except (OSError, AttributeError):
                logger.debug("Socket invalid during update request")
                return
            
            if not socket_valid:
                return
            
            message = struct.pack(
                "!BBHHHH",
                self.FRAMEBUFFER_UPDATE_REQUEST,
                1 if incremental else 0,
                0, 0,
                self.screen_width, self.screen_height
            )
            
            self.socket.send(message)
            self.pending_update_requests += 1
            self.last_update_request_time = current_time
            
        except (OSError, socket.error) as e:
            logger.debug(f"Socket error in stable update request: {e}")
            self.pending_update_requests = 0
        except Exception as e:
            logger.error(f"Error in stable update request: {e}")
            self.pending_update_requests = 0
    
    def _update_canvas_fast(self):
        """СТАБИЛЬНОЕ обновление canvas без моргания."""
        if not self.framebuffer:
            return
        
        try:
            self.pending_canvas_update = False
            self.last_canvas_update = time.time()
            
            # ИСПРАВЛЕНИЕ: Избегаем моргания экрана
            display_image = self.framebuffer
            
            # Применяем масштабирование только если необходимо
            scale_value = self.scale_var.get()
            if scale_value != "100%":
                scale_factor = self._get_scale_factor(scale_value)
                if scale_factor != 1.0:
                    new_width = int(self.screen_width * scale_factor)
                    new_height = int(self.screen_height * scale_factor)
                    display_image = self.framebuffer.resize((new_width, new_height), Image.NEAREST)
            
            # ИСПРАВЛЕНИЕ: Создаем PhotoImage
            photo = ImageTk.PhotoImage(display_image)
            
            # ИСПРАВЛЕНИЕ: Умное обновление canvas без полной очистки
            canvas_items = self.canvas.find_all()
            
            if canvas_items:
                # Обновляем существующее изображение
                main_image_item = canvas_items[0]
                self.canvas.itemconfig(main_image_item, image=photo)
            else:
                # Создаем новое изображение только если его нет
                self.canvas.create_image(0, 0, anchor="nw", image=photo, tags="main_image")
            
            # Сохраняем ссылку на изображение
            self.canvas.image = photo
            
            # Обновляем размер scroll region
            self.canvas.configure(scrollregion=(0, 0, display_image.width, display_image.height))
            
            # Индикатор активности
            self.activity_indicator.configure(text="🟢")
            self.after(100, lambda: self.activity_indicator.configure(text="⚫"))
            
        except Exception as e:
            logger.error(f"Stable canvas update error: {e}")
            # При ошибке делаем полное обновление
            self._full_canvas_refresh()
    
    def _full_canvas_refresh(self):
        """Полное обновление canvas при ошибках."""
        try:
            if not self.framebuffer:
                return
            
            # Полная очистка только при необходимости
            self.canvas.delete("all")
            
            display_image = self.framebuffer
            scale_factor = self._get_scale_factor(self.scale_var.get())
            
            if scale_factor != 1.0:
                new_width = int(self.screen_width * scale_factor)
                new_height = int(self.screen_height * scale_factor)
                display_image = self.framebuffer.resize((new_width, new_height), Image.NEAREST)
            
            photo = ImageTk.PhotoImage(display_image)
            self.canvas.create_image(0, 0, anchor="nw", image=photo, tags="main_image")
            self.canvas.image = photo
            self.canvas.configure(scrollregion=(0, 0, display_image.width, display_image.height))
            
        except Exception as e:
            logger.error(f"Full canvas refresh error: {e}")
    
    def _get_scale_factor(self, scale_value: str) -> float:
        """Получение коэффициента масштабирования."""
        if scale_value == "75%":
            return 0.75
        elif scale_value == "125%":
            return 1.25
        elif scale_value == "Авто":
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            if canvas_width > 1 and canvas_height > 1:
                scale_x = canvas_width / self.screen_width
                scale_y = canvas_height / self.screen_height
                return min(scale_x, scale_y, 1.0)
        
        return 1.0
    
    def _recv_exact(self, size: int) -> bytes:
        """Стабильное получение точного количества байт."""
        if size <= 0:
            return b''
        
        if size > 100000000:  # 100MB лимит для поддержки больших экранов
            logger.error(f"Requested size too large: {size}")
            raise ValueError(f"Size too large: {size}")
        
        if not self.socket:
            raise ConnectionError("Socket is None")
        
        try:
            socket_valid = self.socket.fileno() != -1
        except (OSError, AttributeError):
            raise ConnectionError("Socket is invalid")
        
        if not socket_valid:
            raise ConnectionError("Socket closed")
        
        data = b''
        remaining = size
        max_chunk_size = 65536  # 64KB chunks
        
        while remaining > 0:
            try:
                chunk_size = min(remaining, max_chunk_size)
                chunk = self.socket.recv(chunk_size)
                
                if not chunk:
                    if len(data) > 0:
                        logger.warning(f"Partial data received: {len(data)}/{size} bytes")
                    raise ConnectionError(f"Connection closed (expected {size}, got {len(data)})")
                
                data += chunk
                remaining -= len(chunk)
                
            except socket.timeout:
                if len(data) > 0:
                    logger.warning(f"Timeout while reading, got {len(data)}/{size} bytes")
                # Для UltraVNC расширений - можем продолжить с частичными данными
                if size < 1000:  # Небольшие расширения
                    logger.debug(f"Timeout on small read ({size} bytes), continuing")
                    break
                else:
                    raise
            except OSError as e:
                if e.winerror == 10038:  # WSAENOTSOCK
                    raise ConnectionError("Socket operation on non-socket")
                elif e.winerror == 10054:  # Connection reset
                    raise ConnectionError("Connection reset by peer")
                else:
                    raise ConnectionError(f"Socket error: {e}")
        
        return data
    
    def _start_event_processor(self):
        """Запуск быстрого обработчика событий."""
        self._process_events_fast()
    
    def _process_events_fast(self):
        """БЫСТРАЯ обработка событий из очереди."""
        try:
            events_processed = 0
            max_events = 10  # Обрабатываем больше событий за раз
            
            while events_processed < max_events:
                event_type, data = self.update_queue.get_nowait()
                
                if event_type == 'update_display':
                    self._update_canvas_fast()
                elif event_type == 'update_status':
                    self.status_label.configure(text=data)
                
                events_processed += 1
                    
        except queue.Empty:
            pass
        
        # ПРОИЗВОДИТЕЛЬНОСТЬ: Быстрая обработка событий (120 FPS)
        self.after(8, self._process_events_fast)
    
    def _update_status(self, status: str):
        """Обновление статуса."""
        try:
            self.update_queue.put_nowait(('update_status', status))
        except queue.Full:
            pass  # Пропускаем если очередь заполнена
    
    def _on_connected(self):
        """Обработчик успешного подключения."""
        self.connect_button.configure(state="disabled")
        self.disconnect_button.configure(state="normal")
        self.server_entry.configure(state="disabled")
        self.password_entry.configure(state="disabled")
        
        # Обновляем разрешение
        resolution_text = f"{self.screen_width}x{self.screen_height}"
        self.resolution_label.configure(text=resolution_text)
        
        # Фокус на canvas
        self.canvas.focus_set()
    
    def _on_connection_failed(self, error: str):
        """Обработчик неудачного подключения."""
        messagebox.showerror("Ошибка подключения", f"Не удалось подключиться:\n{error}")
    
    def disconnect_from_vnc(self):
        """Отключение от VNC сервера."""
        logger.info("Disconnecting from VNC server...")
        
        self.connected = False
        self._stop_threads.set()
        
        # Останавливаем таймеры
        if self.force_update_timer:
            self.after_cancel(self.force_update_timer)
            self.force_update_timer = None
        
        if self.continuous_update_timer:
            self.after_cancel(self.continuous_update_timer)
            self.continuous_update_timer = None
        
        # Закрываем сокет
        if self.socket:
            try:
                if self.socket.fileno() != -1:
                    self.socket.close()
            except:
                pass
            finally:
                self.socket = None
        
        # Завершаем потоки
        if self.receiving_thread and self.receiving_thread.is_alive():
            self.receiving_thread.join(timeout=0.5)
        
        # Очистка
        try:
            self.canvas.delete("all")
        except:
            pass
        
        self.framebuffer = None
        
        # Сброс счетчиков
        self.frame_count = 0
        self.update_count = 0
        self.pending_update_requests = 0
        self.protocol_errors = 0
        
        # Обновление UI
        try:
            self.connect_button.configure(state="normal")
            self.disconnect_button.configure(state="disabled")
            self.server_entry.configure(state="normal")
            self.password_entry.configure(state="normal")
            
            self._update_status("Отключено")
            self.resolution_label.configure(text="")
            self.fps_label.configure(text="")
            self.ups_label.configure(text="")
            self.last_update_label.configure(text="")  # НОВОЕ: Очистка framebuffer статуса
        except:
            pass
        
        logger.info("VNC disconnection completed")
    
    # Обработчики событий мыши и клавиатуры (упрощенные для производительности)
    def _on_mouse_click(self, event):
        if self.connected and not self.view_only_var.get():
            self._send_pointer_event_fast(event.x, event.y, button_mask=1)
    
    def _on_mouse_release(self, event):
        if self.connected and not self.view_only_var.get():
            self._send_pointer_event_fast(event.x, event.y, button_mask=0)
    
    def _on_mouse_motion(self, event):
        if self.connected and not self.view_only_var.get():
            self._send_pointer_event_fast(event.x, event.y, button_mask=1)
    
    def _on_mouse_move(self, event):
        if self.connected and not self.view_only_var.get():
            # ПРОИЗВОДИТЕЛЬНОСТЬ: Throttling для движения мыши
            current_time = time.time()
            if hasattr(self, '_last_mouse_move_time'):
                if current_time - self._last_mouse_move_time < 0.02:  # 50 FPS
                    return
            self._last_mouse_move_time = current_time
            self._send_pointer_event_fast(event.x, event.y, button_mask=0)
    
    def _on_right_click(self, event):
        if self.connected and not self.view_only_var.get():
            self._send_pointer_event_fast(event.x, event.y, button_mask=4)
    
    def _on_right_release(self, event):
        if self.connected and not self.view_only_var.get():
            self._send_pointer_event_fast(event.x, event.y, button_mask=0)
    
    def _on_mouse_wheel(self, event):
        if self.connected and not self.view_only_var.get():
            button_mask = 8 if event.delta > 0 else 16
            self._send_pointer_event_fast(event.x, event.y, button_mask=button_mask)
            self.after(10, lambda: self._send_pointer_event_fast(event.x, event.y, button_mask=0))
    
    def _send_pointer_event_fast(self, x: int, y: int, button_mask: int):
        """БЫСТРАЯ отправка события указателя."""
        if not self.connected or not self.socket:
            return
        
        try:
            if self.socket.fileno() == -1:
                return
            
            # Преобразуем координаты с учетом масштабирования
            scale_factor = self._get_scale_factor(self.scale_var.get())
            real_x = int(x / scale_factor)
            real_y = int(y / scale_factor)
            
            real_x = max(0, min(real_x, self.screen_width - 1))
            real_y = max(0, min(real_y, self.screen_height - 1))
            
            message = struct.pack("!BBHH", self.POINTER_EVENT, button_mask, real_x, real_y)
            self.socket.send(message)
            
            # ПРОИЗВОДИТЕЛЬНОСТЬ: Запрос обновления только при кликах
            if button_mask != 0 and self.pending_update_requests < 2:
                self._request_framebuffer_update_fast(incremental=True)
            
        except (OSError, socket.error):
            pass
        except Exception:
            pass
    
    def _on_key_press(self, event):
        if self.connected and not self.view_only_var.get():
            keysym = self._get_keysym(event)
            if keysym:
                self._send_key_event_fast(keysym, down=True)
    
    def _on_key_release(self, event):
        if self.connected and not self.view_only_var.get():
            keysym = self._get_keysym(event)
            if keysym:
                self._send_key_event_fast(keysym, down=False)
    
    def _get_keysym(self, event) -> Optional[int]:
        """Получение keysym для клавиши."""
        special_keys = {
            'Return': 0xff0d, 'Escape': 0xff1b, 'BackSpace': 0xff08, 'Tab': 0xff09,
            'space': 0x0020, 'Delete': 0xffff, 'Home': 0xff50, 'End': 0xff57,
            'Prior': 0xff55, 'Next': 0xff56, 'Left': 0xff51, 'Up': 0xff52,
            'Right': 0xff53, 'Down': 0xff54, 'F1': 0xffbe, 'F2': 0xffbf,
            'F3': 0xffc0, 'F4': 0xffc1, 'F5': 0xffc2, 'F6': 0xffc3,
            'F7': 0xffc4, 'F8': 0xffc5, 'F9': 0xffc6, 'F10': 0xffc7,
            'F11': 0xffc8, 'F12': 0xffc9, 'Shift_L': 0xffe1, 'Shift_R': 0xffe2,
            'Control_L': 0xffe3, 'Control_R': 0xffe4, 'Alt_L': 0xffe9, 'Alt_R': 0xffea,
        }
        
        if event.keysym in special_keys:
            return special_keys[event.keysym]
        
        if len(event.char) == 1 and ord(event.char) < 256:
            return ord(event.char)
        
        return None
    
    def _send_key_event_fast(self, keysym: int, down: bool):
        """БЫСТРАЯ отправка события клавиатуры."""
        if not self.connected or not self.socket:
            return
        
        try:
            if self.socket.fileno() == -1:
                return
            
            message = struct.pack("!BxBBxxxI", self.KEY_EVENT, 1 if down else 0, 0, keysym)
            self.socket.send(message)
            
            # ПРОИЗВОДИТЕЛЬНОСТЬ: Запрос обновления только при нажатии
            if down and self.pending_update_requests < 2:
                self._request_framebuffer_update_fast(incremental=True)
            
        except (OSError, socket.error):
            pass
        except Exception:
            pass
    
    # Специальные команды (упрощенные)
    def _send_ctrl_alt_del(self):
        if not self.connected or self.view_only_var.get():
            return
        
        self._send_key_event_fast(0xffe3, True)   # Ctrl down
        self._send_key_event_fast(0xffe9, True)   # Alt down
        self._send_key_event_fast(0xffff, True)   # Del down
        self.after(50, lambda: self._send_key_event_fast(0xffff, False))
        self.after(100, lambda: self._send_key_event_fast(0xffe9, False))
        self.after(150, lambda: self._send_key_event_fast(0xffe3, False))
    
    def _send_alt_tab(self):
        if not self.connected or self.view_only_var.get():
            return
        
        self._send_key_event_fast(0xffe9, True)   # Alt down
        self._send_key_event_fast(0xff09, True)   # Tab down
        self.after(50, lambda: self._send_key_event_fast(0xff09, False))
        self.after(100, lambda: self._send_key_event_fast(0xffe9, False))
    
    def _send_escape(self):
        if not self.connected or self.view_only_var.get():
            return
        
        self._send_key_event_fast(0xff1b, True)
        self.after(50, lambda: self._send_key_event_fast(0xff1b, False))
    
    def _take_screenshot(self):
        """Создание скриншота."""
        if not self.connected or not self.framebuffer:
            messagebox.showwarning("Предупреждение", "Нет активного подключения")
            return
        
        from tkinter import filedialog
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            title="Сохранить скриншот"
        )
        
        if filename:
            try:
                self.framebuffer.save(filename)
                messagebox.showinfo("Успех", f"Скриншот сохранен:\n{filename}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить скриншот:\n{e}")
    
    def _on_quality_change(self, value):
        """Изменение режима производительности."""
        logger.info(f"Quality mode changed to: {value}")
        
        if value == "Производительность":
            self.update_request_interval = 0.025       # 40 FPS (более стабильно)
            self.canvas_update_interval = 0.025        # 40 FPS
            self.continuous_update_interval = 0.033    # 30 FPS continuous
            self.max_pending_requests = 2
        elif value == "Сбалансированный":
            self.update_request_interval = 0.033       # 30 FPS
            self.canvas_update_interval = 0.033        # 30 FPS
            self.continuous_update_interval = 0.05     # 20 FPS continuous
            self.max_pending_requests = 2
        else:  # Качество
            self.update_request_interval = 0.05        # 20 FPS
            self.canvas_update_interval = 0.025        # 40 FPS для UI
            self.continuous_update_interval = 0.1      # 10 FPS continuous
            self.max_pending_requests = 1
        
        logger.info(f"Performance settings updated: intervals={self.update_request_interval:.3f}s, max_pending={self.max_pending_requests}")
        
        # Перезапускаем таймеры с новыми настройками
        if self.connected:
            self._restart_timers_with_new_settings()
    
    def _restart_timers_with_new_settings(self):
        """Перезапуск таймеров с новыми настройками."""
        # Останавливаем старые таймеры
        if self.force_update_timer:
            self.after_cancel(self.force_update_timer)
            self.force_update_timer = None
        if self.continuous_update_timer:
            self.after_cancel(self.continuous_update_timer)
            self.continuous_update_timer = None
        
        # Сбрасываем pending при смене настроек
        self.pending_update_requests = 0
        
        # Запускаем новые с обновленными интервалами
        self.after(100, self._start_high_performance_timers)
        
        logger.info("Timers restarted with new settings")
        
        # Перезапускаем таймеры с новыми настройками
        if self.connected:
            self._restart_timers_with_new_settings()
    
    def _on_continuous_change(self):
        """Обработка изменения режима непрерывных обновлений."""
        self.continuous_updates = self.continuous_var.get()
        logger.info(f"Continuous updates: {'enabled' if self.continuous_updates else 'disabled'}")
    
    def _update_stats(self):
        """Обновление статистики производительности."""
        if not self.connected:
            self.after(1000, self._update_stats)
    
    def _force_screen_refresh(self):
        """Принудительное обновление экрана для восстановления изображения."""
        if not self.connected or not self.socket:
            return
        
        try:
            logger.info("Forcing screen refresh due to protocol issues")
            
            # Сбрасываем pending запросы
            self.pending_update_requests = 0
            
            # Запрашиваем полное обновление экрана
            self._request_framebuffer_update_stable(incremental=False)
            
            # Дополнительный incremental запрос через небольшую задержку
            self.after(200, lambda: self._request_framebuffer_update_stable(incremental=True))
            
        except Exception as e:
            logger.error(f"Error in force screen refresh: {e}")
            return
        
        current_time = time.time()
        
        # FPS
        if current_time - self.last_fps_time >= 1.0:
            fps = self.frame_count / (current_time - self.last_fps_time)
            self.fps_label.configure(text=f"FPS: {fps:.1f}")
            self.frame_count = 0
            self.last_fps_time = current_time
        
        # UPS
        if current_time - self.last_update_count_time >= 1.0:
            ups = self.update_count / (current_time - self.last_update_count_time)
            self.ups_label.configure(text=f"UPS: {ups:.1f}")
            self.update_count = 0
            self.last_update_count_time = current_time
        
        # НОВОЕ: Время последнего обновления framebuffer
        if hasattr(self, 'last_framebuffer_time'):
            time_since_fb = current_time - self.last_framebuffer_time
            if time_since_fb < 1:
                fb_status = "Live"
                color = "green"
            elif time_since_fb < 5:
                fb_status = f"{time_since_fb:.1f}s ago"
                color = "orange"
            else:
                fb_status = f"{time_since_fb:.0f}s ago"
                color = "red"
            
            self.last_update_label.configure(text=f"Last FB: {fb_status}")
            # Можно добавить цветовое кодирование если нужно
        
        self.after(1000, self._update_stats)
    
    def cleanup(self):
        """Очистка ресурсов."""
        self.disconnect_from_vnc()

# gui/vnc_viewer_frame.py
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
import select
import random
try:
    from Crypto.Cipher import DES
except ImportError:
    # Fallback для простой аутентификации
    DES = None
import hashlib

logger = logging.getLogger(__name__)

class VNCViewerFrame(ctk.CTkFrame):
    """Фрейм для VNC клиента с полной функциональностью."""
    
    # RFB Protocol constants
    RFB_VERSION_3_3 = b"RFB 003.003\n"
    RFB_VERSION_3_7 = b"RFB 003.007\n"
    RFB_VERSION_3_8 = b"RFB 003.008\n"
    
    # Security types
    SECURITY_NONE = 1
    SECURITY_VNC = 2
    SECURITY_TIGHT = 16
    SECURITY_ULTRA = 17
    SECURITY_TLS = 18
    SECURITY_VENCRYPT = 19
    SECURITY_MS_LOGON_II = 113
    SECURITY_ULTRA_MS_LOGON_II = 117
    
    # Client message types
    SET_PIXEL_FORMAT = 0
    SET_ENCODINGS = 2
    FRAMEBUFFER_UPDATE_REQUEST = 3
    KEY_EVENT = 4
    POINTER_EVENT = 5
    CLIENT_CUT_TEXT = 6
    
    # Server message types
    FRAMEBUFFER_UPDATE = 0
    SET_COLOR_MAP_ENTRIES = 1
    BELL = 2
    SERVER_CUT_TEXT = 3
    
    # Encoding types
    ENCODING_RAW = 0
    ENCODING_COPYRECT = 1
    ENCODING_RRE = 2
    ENCODING_HEXTILE = 5
    ENCODING_ZLIB = 6
    ENCODING_TIGHT = 7
    ENCODING_ZLIBHEX = 8
    
    def __init__(self, parent, app):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        
        self.app = app
        self.socket = None
        self.connected = False
        self.screen_width = 0
        self.screen_height = 0
        self.pixel_format = None
        self.framebuffer = None
        
        # Очереди для асинхронной обработки
        self.event_queue = queue.Queue()
        self.update_queue = queue.Queue()
        
        # Флаги состояния
        self.receiving_thread = None
        self.processing_thread = None
        self._stop_threads = threading.Event()
        
        # Статистика производительности
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.bytes_received = 0
        self.last_stats_time = time.time()
        
        # Throttling для улучшения производительности
        self.last_update_request_time = 0
        self.update_request_interval = 0.01  # Очень частые запросы (100 FPS потенциал)
        self.last_canvas_update_time = 0
        self.canvas_update_interval = 0.033  # 30 FPS для UI
        self.pending_canvas_update = False
        
        # Принудительные обновления для медленных серверов
        self.force_update_timer = None
        self.force_update_interval = 1.0  # Каждую секунду принудительно
        
        # Детекция проблем протокола
        self.protocol_errors = 0
        self.max_protocol_errors = 5  # Максимум ошибок перед переподключением
        
        # Настройка UI
        self._setup_ui()
        
        # Запуск обработчика событий
        self._start_event_processor()
        
        # Запуск обновления статистики
        self._update_stats()
        
        # Настройка производительности в зависимости от качества
        self._adjust_performance_settings()
    
    def _setup_ui(self):
        """Настройка пользовательского интерфейса."""
        # Настройка сетки
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Панель подключения
        self._create_connection_panel()
        
        # Область просмотра
        self._create_viewer_area()
        
        # Панель статуса
        self._create_status_panel()
        
        # Панель управления
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
        
        self.reconnect_button = ctk.CTkButton(
            connection_frame, 
            text="Переподключиться", 
            command=self.reconnect_to_vnc,
            width=140,
            state="disabled"
        )
        self.reconnect_button.grid(row=0, column=6, padx=5, pady=5)
        
        # Настройки качества
        quality_frame = ctk.CTkFrame(connection_frame, fg_color="transparent")
        quality_frame.grid(row=1, column=0, columnspan=6, pady=5)
        
        ctk.CTkLabel(quality_frame, text="Качество:").pack(side="left", padx=5)
        
        self.quality_var = ctk.StringVar(value="medium")
        quality_menu = ctk.CTkSegmentedButton(
            quality_frame,
            values=["Низкое", "Среднее", "Высокое"],
            variable=self.quality_var,
            command=self._on_quality_change
        )
        quality_menu.pack(side="left", padx=5)
        quality_menu.set("Среднее")
        
        # Чекбокс для view-only режима
        self.view_only_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            quality_frame,
            text="Только просмотр",
            variable=self.view_only_var
        ).pack(side="left", padx=20)
        
        # Выбор типа аутентификации
        auth_frame = ctk.CTkFrame(quality_frame, fg_color="transparent")
        auth_frame.pack(side="left", padx=20)
        
        ctk.CTkLabel(auth_frame, text="Аутентификация:").pack(side="left", padx=5)
        
        self.auth_var = ctk.StringVar(value="auto")
        auth_menu = ctk.CTkSegmentedButton(
            auth_frame,
            values=["Авто", "VNC", "Без пароля"],
            variable=self.auth_var
        )
        auth_menu.pack(side="left", padx=5)
        auth_menu.set("Авто")
        
        # Масштабирование для больших экранов
        scale_frame = ctk.CTkFrame(quality_frame, fg_color="transparent")
        scale_frame.pack(side="left", padx=20)
        
        ctk.CTkLabel(scale_frame, text="Масштаб:").pack(side="left", padx=5)
        
        self.scale_var = ctk.StringVar(value="auto")
        scale_menu = ctk.CTkSegmentedButton(
            scale_frame,
            values=["25%", "50%", "75%", "100%", "Авто"],
            variable=self.scale_var
        )
        scale_menu.pack(side="left", padx=5)
        scale_menu.set("Авто")
    
    def _create_viewer_area(self):
        """Создание области просмотра."""
        # Фрейм с прокруткой для canvas
        viewer_frame = ctk.CTkFrame(self)
        viewer_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        viewer_frame.grid_rowconfigure(0, weight=1)
        viewer_frame.grid_columnconfigure(0, weight=1)
        
        # Canvas для отображения экрана
        self.canvas = Canvas(
            viewer_frame,
            bg="black",
            highlightthickness=0
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
        self.canvas.bind("<Button-1>", self._on_mouse_click)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_release)
        self.canvas.bind("<B1-Motion>", self._on_mouse_motion)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<ButtonRelease-3>", self._on_right_release)
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        
        # Фокус для клавиатуры
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())
        self.canvas.bind("<KeyPress>", self._on_key_press)
        self.canvas.bind("<KeyRelease>", self._on_key_release)
    
    def _create_status_panel(self):
        """Создание панели статуса."""
        status_frame = ctk.CTkFrame(self)
        status_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        
        self.status_label = ctk.CTkLabel(
            status_frame, 
            text="Отключено",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.pack(side="left", padx=10)
        
        self.resolution_label = ctk.CTkLabel(
            status_frame,
            text="",
            font=ctk.CTkFont(size=12)
        )
        self.resolution_label.pack(side="left", padx=20)
        
        self.fps_label = ctk.CTkLabel(
            status_frame,
            text="",
            font=ctk.CTkFont(size=12)
        )
        self.fps_label.pack(side="left", padx=20)
        
        # Индикатор активности
        self.activity_indicator = ctk.CTkLabel(
            status_frame,
            text="⚫",
            font=ctk.CTkFont(size=16)
        )
        self.activity_indicator.pack(side="right", padx=10)
    
    def _create_control_panel(self):
        """Создание панели управления."""
        control_frame = ctk.CTkFrame(self)
        control_frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        
        # Специальные клавиши
        ctk.CTkLabel(control_frame, text="Специальные клавиши:").pack(side="left", padx=5)
        
        ctk.CTkButton(
            control_frame,
            text="Ctrl+Alt+Del",
            command=self._send_ctrl_alt_del,
            width=100
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            control_frame,
            text="Alt+Tab",
            command=self._send_alt_tab,
            width=80
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            control_frame,
            text="Esc",
            command=self._send_escape,
            width=50
        ).pack(side="left", padx=5)
        
        # Кнопка полноэкранного режима
        ctk.CTkButton(
            control_frame,
            text="Полный экран",
            command=self._toggle_fullscreen,
            width=100
        ).pack(side="right", padx=5)
        
        # Кнопка скриншота
        ctk.CTkButton(
            control_frame,
            text="📷 Скриншот",
            command=self._take_screenshot,
            width=100
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
            self.socket.settimeout(10)  # Таймаут для операций
            self.socket.connect((host, port))
            
            # После успешного подключения устанавливаем меньший таймаут для чтения
            self.socket.settimeout(5)
            
            # Handshake
            if not self._handshake():
                raise Exception("Ошибка handshake")
            
            # Аутентификация
            if not self._authenticate(password):
                raise Exception("Ошибка аутентификации")
            
            # Инициализация
            if not self._initialize():
                raise Exception("Ошибка инициализации")
            
            self.connected = True
            self._update_status(f"Подключено к {host}:{port}")
            
            # Обновление UI
            self.after(0, self._on_connected)
            
            # Запуск потоков обработки
            self._start_receiver_thread()
            
            # Запрос первого кадра
            self._request_framebuffer_update(incremental=False)
            
        except Exception as e:
            logger.error(f"Ошибка подключения: {e}")
            self._update_status(f"Ошибка: {str(e)}")
            self.after(0, self._on_connection_failed, str(e))
    
    def _handshake(self) -> bool:
        """Выполнение VNC handshake."""
        try:
            # Получаем версию сервера
            server_version = self._recv_exact(12)
            logger.debug(f"Server version: {server_version}")
            
            # Отправляем нашу версию
            self.socket.send(self.RFB_VERSION_3_8)
            
            return True
        except Exception as e:
            logger.error(f"Handshake error: {e}")
            return False
    
    def _authenticate(self, password: str) -> bool:
        """Улучшенная аутентификация на VNC сервере."""
        try:
            # Получаем количество методов безопасности
            num_security_types = struct.unpack("!B", self._recv_exact(1))[0]
            
            if num_security_types == 0:
                # Ошибка сервера
                reason_length = struct.unpack("!I", self._recv_exact(4))[0]
                reason = self._recv_exact(reason_length).decode()
                logger.error(f"Server error: {reason}")
                return False
            
            # Получаем список методов
            security_types = struct.unpack(f"!{num_security_types}B", 
                                         self._recv_exact(num_security_types))
            logger.debug(f"Security types: {security_types}")
            
            # Выбираем метод аутентификации
            auth_preference = self.auth_var.get()
            selected_type = None
            
            if auth_preference == "Без пароля" and self.SECURITY_NONE in security_types:
                selected_type = self.SECURITY_NONE
            elif auth_preference == "VNC" and self.SECURITY_VNC in security_types:
                selected_type = self.SECURITY_VNC
            else:
                # Автоматический выбор
                if self.SECURITY_VNC in security_types:
                    selected_type = self.SECURITY_VNC
                elif self.SECURITY_NONE in security_types:
                    selected_type = self.SECURITY_NONE
                elif 17 in security_types:  # UltraVNC - только если явно выбран
                    if auth_preference == "Авто":
                        # Пропускаем UltraVNC в автоматическом режиме
                        pass
                    else:
                        selected_type = 17
            
            if selected_type is None:
                logger.error(f"No supported security types in {security_types}")
                return False
            
            logger.info(f"Using security type: {selected_type}")
            self.socket.send(struct.pack("!B", selected_type))
            
            # Выполняем аутентификацию
            if selected_type == self.SECURITY_NONE:
                return self._auth_none()
            elif selected_type == self.SECURITY_VNC:
                return self._auth_vnc(password)
            elif selected_type == 17:
                return self._auth_ultravnc(password)
            else:
                logger.error(f"Unsupported security type: {selected_type}")
                return False
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    def _auth_none(self) -> bool:
        """Аутентификация без пароля."""
        try:
            # Для версии 3.8 нужно проверить результат
            result_data = self._recv_exact(4)
            result = struct.unpack("!I", result_data)[0]
            
            if result == 0:
                logger.info("No authentication successful")
                return True
            else:
                logger.error(f"No authentication failed with result: {result}")
                return False
        except Exception as e:
            logger.error(f"No auth error: {e}")
            return False
    
    def _auth_vnc(self, password: str) -> bool:
        """Стандартная VNC аутентификация."""
        try:
            # Получаем challenge
            challenge = self._recv_exact(16)
            logger.debug("Received VNC challenge")
            
            # Шифруем пароль
            response = self._encrypt_password(password or "", challenge)
            self.socket.send(response)
            
            # Проверяем результат
            result_data = self._recv_exact(4)
            result = struct.unpack("!I", result_data)[0]
            
            if result == 0:
                logger.info("VNC authentication successful")
                return True
            else:
                logger.error(f"VNC authentication failed with result: {result}")
                return False
                
        except Exception as e:
            logger.error(f"VNC auth error: {e}")
            return False
    
    def _auth_ultravnc(self, password: str) -> bool:
        """Упрощенная UltraVNC аутентификация."""
        try:
            logger.info("Attempting UltraVNC authentication")
            
            # UltraVNC MS Logon может иметь разные варианты
            # Пытаемся прочитать данные с таймаутом
            self.socket.settimeout(2)
            
            try:
                # Пытаемся прочитать первые байты
                first_data = self.socket.recv(10, socket.MSG_PEEK)
                logger.debug(f"UltraVNC first data peek: {first_data[:10].hex()}")
                
                if len(first_data) < 4:
                    logger.warning("Insufficient UltraVNC data, falling back")
                    return False
                
                # Читаем размер первого блока
                size_data = self._recv_exact(2)
                size = struct.unpack("!H", size_data)[0]
                logger.debug(f"UltraVNC first block size: {size}")
                
                # Ограничиваем размер для безопасности
                if size > 8192:  # 8KB лимит
                    logger.error(f"UltraVNC block size too large: {size}")
                    return False
                
                # Читаем блок данных
                data_block = self._recv_exact(size)
                logger.debug(f"UltraVNC data block: {len(data_block)} bytes")
                
                # Упрощенный ответ - отправляем нули
                response_size = min(size, 256)  # Ограничиваем размер ответа
                response = b'\x00' * response_size
                self.socket.send(struct.pack("!H", response_size) + response)
                
                # Проверяем результат аутентификации
                try:
                    result_data = self._recv_exact(4)
                    result = struct.unpack("!I", result_data)[0]
                    
                    if result == 0:
                        logger.info("UltraVNC authentication successful")
                        return True
                    else:
                        logger.error(f"UltraVNC authentication failed: {result}")
                        return False
                        
                except socket.timeout:
                    logger.warning("UltraVNC auth result timeout, assuming success")
                    return True
                    
            except socket.timeout:
                logger.warning("UltraVNC auth timeout, trying fallback")
                return False
                
        except Exception as e:
            logger.error(f"UltraVNC auth error: {e}")
            return False
        finally:
            self.socket.settimeout(5)  # Восстанавливаем обычный таймаут
    
    def _encrypt_password(self, password: str, challenge: bytes) -> bytes:
        """Шифрование пароля для VNC аутентификации."""
        # Если DES доступен, используем его
        if DES:
            # Подготовка пароля (8 байт, дополненный нулями)
            # Обрабатываем Unicode символы безопасно
            try:
                password_bytes = password[:8].ljust(8, '\0').encode('utf-8')[:8]
            except UnicodeEncodeError:
                # Если UTF-8 не работает, пробуем другие кодировки
                try:
                    password_bytes = password[:8].ljust(8, '\0').encode('cp1251')[:8]
                except UnicodeEncodeError:
                    # В крайнем случае заменяем проблемные символы
                    password_clean = password[:8].encode('ascii', 'replace').decode('ascii')
                    password_bytes = password_clean.ljust(8, '\0').encode('ascii')
            
            # Дополняем до 8 байт нулями если нужно
            password_bytes = password_bytes.ljust(8, b'\0')[:8]
            
            # Реверс битов в каждом байте (VNC особенность)
            password_bytes = bytes(self._reverse_bits(b) for b in password_bytes)
            
            # DES шифрование
            cipher = DES.new(password_bytes, DES.MODE_ECB)
            return cipher.encrypt(challenge)
        else:
            # Упрощенная версия без DES
            # Для пустого пароля возвращаем challenge XOR с нулями
            if not password:
                # Многие VNC серверы принимают все нули для пустого пароля
                return b'\x00' * 16
            
            # Подготовка пароля с безопасной обработкой Unicode
            try:
                key_bytes = password[:8].ljust(8, '\0').encode('utf-8')[:8]
            except UnicodeEncodeError:
                try:
                    key_bytes = password[:8].ljust(8, '\0').encode('cp1251')[:8]
                except UnicodeEncodeError:
                    password_clean = password[:8].encode('ascii', 'replace').decode('ascii')
                    key_bytes = password_clean.ljust(8, '\0').encode('ascii')
            
            # Дополняем до 8 байт
            key_bytes = key_bytes.ljust(8, b'\0')[:8]
            
            # Реверс битов
            key_bytes = bytes(self._reverse_bits(b) for b in key_bytes)
            
            # Простое XOR для демонстрации (НЕ БЕЗОПАСНО!)
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
            # Отправляем ClientInit (shared flag)
            self.socket.send(struct.pack("!B", 1))  # 1 = shared
            
            # Получаем ServerInit
            # Размеры экрана
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
            
            # Настройка кодировок
            self._set_encodings()
            
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
    
    def _set_encodings(self):
        """Установка поддерживаемых кодировок."""
        # МИНИМАЛЬНЫЙ набор кодировок для максимальной совместимости
        encodings = [
            self.ENCODING_RAW,       # 0 - Основная кодировка (всегда поддерживается)
            self.ENCODING_COPYRECT,  # 1 - Copy Rectangle
            # Убираем проблемные кодировки и псевдо-кодировки пока
        ]
        
        message = struct.pack("!BBH", self.SET_ENCODINGS, 0, len(encodings))
        for encoding in encodings:
            message += struct.pack("!i", encoding)
        
        self.socket.send(message)
        logger.debug(f"Set encodings: {encodings}")
    
    def _request_framebuffer_update_throttled(self, incremental: bool = True):
        """Запрос обновления framebuffer с throttling."""
        current_time = time.time()
        
        # Throttling - не запрашиваем обновления слишком часто
        if current_time - self.last_update_request_time < self.update_request_interval:
            return
        
        self.last_update_request_time = current_time
        self._request_framebuffer_update(incremental)
    
    def _request_framebuffer_update(self, incremental: bool = True):
        """Запрос обновления framebuffer."""
        if not self.connected or not self.socket:
            return
        
        try:
            # Проверяем валидность сокета
            if self.socket.fileno() == -1:
                logger.debug("Cannot request framebuffer update: socket is closed")
                return
            
            message = struct.pack(
                "!BBHHHH",
                self.FRAMEBUFFER_UPDATE_REQUEST,  # 3
                1 if incremental else 0,
                0, 0,  # x, y
                self.screen_width, self.screen_height  # width, height
            )
            
            self.socket.send(message)
            
        except (OSError, socket.error) as e:
            logger.debug(f"Socket error requesting framebuffer update: {e}")
            # Не разрываем соединение сразу, возможно временная проблема
        except Exception as e:
            logger.error(f"Error requesting framebuffer update: {e}")
    
    def _start_receiver_thread(self):
        """Запуск потока приёма данных."""
        self._stop_threads.clear()
        
        # Запускаем поток приема
        self.receiving_thread = threading.Thread(
            target=self._receive_loop,
            daemon=True
        )
        self.receiving_thread.start()
        
        logger.info("Receiver thread started")
    
    def _receive_loop(self):
        """Цикл приёма данных от сервера."""
        while self.connected and not self._stop_threads.is_set():
            try:
                # Проверяем валидность сокета
                if not self.socket or self.socket.fileno() == -1:
                    logger.warning("Socket is closed or invalid")
                    break
                
                # Читаем тип сообщения с проверкой
                msg_type_data = self.socket.recv(1)
                if not msg_type_data:
                    logger.warning("Connection closed by server")
                    break
                
                message_type = struct.unpack("!B", msg_type_data)[0]
                logger.debug(f"Received message type: {message_type}")
                
                if message_type == self.FRAMEBUFFER_UPDATE:
                    try:
                        self._handle_framebuffer_update()
                        # Сбрасываем счетчик ошибок при успешной обработке
                        self.protocol_errors = 0
                    except Exception as e:
                        self.protocol_errors += 1
                        logger.error(f"Framebuffer update error #{self.protocol_errors}: {e}")
                        
                        if self.protocol_errors >= self.max_protocol_errors:
                            logger.error("Too many protocol errors, disconnecting")
                            raise ConnectionError(f"Protocol error limit exceeded: {self.protocol_errors}")
                        
                        # Пытаемся восстановиться
                        time.sleep(0.1)
                        continue
                elif message_type == self.SET_COLOR_MAP_ENTRIES:
                    self._handle_colormap_entries()
                elif message_type == self.BELL:
                    self._handle_bell()
                elif message_type == self.SERVER_CUT_TEXT:
                    self._handle_server_cut_text()
                else:
                    logger.warning(f"Unknown message type: {message_type}")
                    # Простая обработка неизвестных сообщений
                    try:
                        # Для большинства неизвестных типов просто игнорируем
                        if message_type in [255, 33, 45, 36]:  # Известные UltraVNC расширения
                            logger.debug(f"Ignoring UltraVNC extension message type {message_type}")
                            continue  # Просто игнорируем эти сообщения
                        else:
                            logger.warning(f"Unknown message type {message_type}, attempting to skip")
                            # Пытаемся прочитать несколько байт и продолжить
                            try:
                                if hasattr(socket, 'MSG_DONTWAIT'):
                                    skip_data = self.socket.recv(16, socket.MSG_DONTWAIT)
                                else:
                                    # Для Windows используем неблокирующий режим
                                    self.socket.setblocking(False)
                                    try:
                                        skip_data = self.socket.recv(16)
                                    finally:
                                        self.socket.setblocking(True)
                                logger.debug(f"Skipped {len(skip_data)} bytes for unknown message {message_type}")
                            except (socket.error, BlockingIOError):
                                # Нет данных для чтения - это нормально
                                logger.debug(f"No data to skip for message type {message_type}")
                    except Exception as e:
                        logger.error(f"Error handling unknown message {message_type}: {e}")
                        # Продолжаем работу даже при ошибках
                        time.sleep(0.01)
                
            except socket.timeout:
                # Таймаут - это нормально, продолжаем
                continue
            except ConnectionError as e:
                logger.error(f"Connection error: {e}")
                break
            except OSError as e:
                if e.winerror == 10038:  # WSAENOTSOCK
                    logger.error("Socket operation on non-socket")
                else:
                    logger.error(f"OS error: {e}")
                break
            except struct.error as e:
                logger.error(f"Struct unpack error: {e}")
                break
            except Exception as e:
                logger.error(f"Receive error: {e}", exc_info=True)
                # Для других ошибок пытаемся продолжить
                time.sleep(0.1)
                continue
        
        self.connected = False
        self._update_status("Соединение разорвано")
        self.after(0, self.disconnect_from_vnc)
    
    def _recv_exact(self, size: int) -> bytes:
        """Получение точного количества байт."""
        if size <= 0:
            return b''
        
        # Увеличенный лимит для больших экранов (50MB)
        if size > 50000000:
            raise ValueError(f"Requested size too large: {size}")
        
        # Проверяем валидность сокета перед чтением
        if not self.socket or self.socket.fileno() == -1:
            raise ConnectionError("Socket is closed or invalid")
        
        data = b''
        remaining = size
        
        # Увеличиваем размер chunk для больших объемов данных
        chunk_size = min(65536, remaining) if size > 1000000 else 4096
        
        while remaining > 0:
            try:
                chunk = self.socket.recv(min(remaining, chunk_size))
                if not chunk:
                    raise ConnectionError(f"Connection closed (expected {size} bytes, got {len(data)})")
                data += chunk
                remaining -= len(chunk)
                
                # Обновляем статистику трафика
                self.bytes_received += len(chunk)
                
            except socket.timeout:
                if len(data) > 0:
                    logger.warning(f"Timeout while reading, got {len(data)}/{size} bytes")
                raise
            except OSError as e:
                if e.winerror == 10038:  # WSAENOTSOCK
                    raise ConnectionError("Socket operation on non-socket")
                else:
                    raise ConnectionError(f"Socket error: {e}")
        
        return data
    
    def _handle_framebuffer_update(self):
        """Обработка обновления framebuffer."""
        try:
            # Пропускаем padding
            self._recv_exact(1)
            
            # Количество прямоугольников
            num_rectangles = struct.unpack("!H", self._recv_exact(2))[0]
            
            for _ in range(num_rectangles):
                # Координаты и размеры
                rect_data = self._recv_exact(8)
                x, y, w, h = struct.unpack("!HHHH", rect_data)
                
                # Тип кодировки
                encoding = struct.unpack("!i", self._recv_exact(4))[0]
                
                # Обработка в зависимости от кодировки
                if encoding == self.ENCODING_RAW:
                    self._handle_raw_rectangle(x, y, w, h)
                elif encoding == self.ENCODING_COPYRECT:
                    self._handle_copyrect(x, y, w, h)
                elif encoding == self.ENCODING_RRE:
                    self._handle_rre_rectangle(x, y, w, h)
                else:
                    logger.warning(f"Unsupported encoding: {encoding}")
                    # Пропускаем данные
                    bytes_per_pixel = self.pixel_format['bits_per_pixel'] // 8
                    skip_size = w * h * bytes_per_pixel
                    if skip_size > 0:
                        self._recv_exact(skip_size)
            
            # Обновляем изображение на canvas (с throttling)
            current_time = time.time()
            if current_time - self.last_canvas_update_time >= self.canvas_update_interval:
                self.update_queue.put(('update_display', None))
                self.last_canvas_update_time = current_time
                self.pending_canvas_update = False
            else:
                # Если обновление слишком частое, просто помечаем что нужно обновить
                self.pending_canvas_update = True
            
            # Обновляем статистику
            self.frame_count += 1
            
            # Запрашиваем следующее обновление (с throttling)
            self._request_framebuffer_update_throttled(incremental=True)
            
        except Exception as e:
            logger.error(f"Framebuffer update error: {e}")
            raise
    
    def _handle_raw_rectangle(self, x: int, y: int, w: int, h: int):
        """Обработка RAW прямоугольника."""
        bytes_per_pixel = self.pixel_format['bits_per_pixel'] // 8
        data_size = w * h * bytes_per_pixel
        
        # Увеличенный лимит для больших экранов (50MB)
        if data_size > 50000000:
            logger.error(f"Rectangle too large: {w}x{h}, {data_size} bytes")
            raise ValueError(f"Rectangle too large: {data_size} bytes")
        
        # Логируем большие прямоугольники
        if data_size > 5000000:  # 5MB
            logger.info(f"Processing large rectangle: {w}x{h}, {data_size/1024/1024:.1f}MB")
        
        # Читаем данные безопасно
        try:
            pixel_data = self._recv_exact(data_size)
        except Exception as e:
            logger.error(f"Error reading raw rectangle data: {e}")
            raise
        
        # Создаем изображение для прямоугольника
        rect_image = Image.new('RGB', (w, h))
        pixels = []
        
        # Оптимизация для больших изображений
        if data_size > 1000000:  # 1MB
            # Обрабатываем блоками для экономии памяти
            pixels_per_row = w
            for row in range(h):
                row_start = row * pixels_per_row * bytes_per_pixel
                row_end = row_start + pixels_per_row * bytes_per_pixel
                row_data = pixel_data[row_start:row_end]
                
                row_pixels = []
                for i in range(0, len(row_data), bytes_per_pixel):
                    if bytes_per_pixel == 4:  # 32-bit
                        b, g, r, _ = row_data[i:i+4]
                        row_pixels.append((r, g, b))
                    elif bytes_per_pixel == 3:  # 24-bit
                        b, g, r = row_data[i:i+3]
                        row_pixels.append((r, g, b))
                    elif bytes_per_pixel == 2:  # 16-bit
                        pixel = struct.unpack("!H", row_data[i:i+2])[0]
                        r = ((pixel >> self.pixel_format['red_shift']) & 
                             ((1 << self._bit_count(self.pixel_format['red_max'])) - 1))
                        g = ((pixel >> self.pixel_format['green_shift']) & 
                             ((1 << self._bit_count(self.pixel_format['green_max'])) - 1))
                        b = ((pixel >> self.pixel_format['blue_shift']) & 
                             ((1 << self._bit_count(self.pixel_format['blue_max'])) - 1))
                        # Масштабирование до 8 бит
                        r = r * 255 // self.pixel_format['red_max']
                        g = g * 255 // self.pixel_format['green_max']
                        b = b * 255 // self.pixel_format['blue_max']
                        row_pixels.append((r, g, b))
                
                pixels.extend(row_pixels)
        else:
            # Обычная обработка для маленьких изображений
            for i in range(0, len(pixel_data), bytes_per_pixel):
                if bytes_per_pixel == 4:  # 32-bit
                    b, g, r, _ = pixel_data[i:i+4]
                    pixels.append((r, g, b))
                elif bytes_per_pixel == 3:  # 24-bit
                    b, g, r = pixel_data[i:i+3]
                    pixels.append((r, g, b))
                elif bytes_per_pixel == 2:  # 16-bit
                    pixel = struct.unpack("!H", pixel_data[i:i+2])[0]
                    r = ((pixel >> self.pixel_format['red_shift']) & 
                         ((1 << self._bit_count(self.pixel_format['red_max'])) - 1))
                    g = ((pixel >> self.pixel_format['green_shift']) & 
                         ((1 << self._bit_count(self.pixel_format['green_max'])) - 1))
                    b = ((pixel >> self.pixel_format['blue_shift']) & 
                         ((1 << self._bit_count(self.pixel_format['blue_max'])) - 1))
                    # Масштабирование до 8 бит
                    r = r * 255 // self.pixel_format['red_max']
                    g = g * 255 // self.pixel_format['green_max']
                    b = b * 255 // self.pixel_format['blue_max']
                    pixels.append((r, g, b))
        
        rect_image.putdata(pixels)
        
        # Вставляем в основной framebuffer
        self.framebuffer.paste(rect_image, (x, y))
    
    def _bit_count(self, n: int) -> int:
        """Подсчет битов в числе."""
        count = 0
        while n:
            count += 1
            n >>= 1
        return count
    
    def _handle_copyrect(self, x: int, y: int, w: int, h: int):
        """Обработка COPYRECT."""
        src_data = self._recv_exact(4)
        src_x, src_y = struct.unpack("!HH", src_data)
        
        # Копируем прямоугольник
        rect = self.framebuffer.crop((src_x, src_y, src_x + w, src_y + h))
        self.framebuffer.paste(rect, (x, y))
    
    def _handle_rre_rectangle(self, x: int, y: int, w: int, h: int):
        """Обработка RRE прямоугольника."""
        # Количество подпрямоугольников
        num_subrects = struct.unpack("!I", self._recv_exact(4))[0]
        
        bytes_per_pixel = self.pixel_format['bits_per_pixel'] // 8
        
        # Фоновый цвет
        bg_color = self._read_pixel(bytes_per_pixel)
        
        # Заполняем фоном
        rect_image = Image.new('RGB', (w, h), bg_color)
        
        # Читаем подпрямоугольники
        for _ in range(num_subrects):
            pixel_color = self._read_pixel(bytes_per_pixel)
            sub_data = self._recv_exact(8)
            sub_x, sub_y, sub_w, sub_h = struct.unpack("!HHHH", sub_data)
            
            # Рисуем подпрямоугольник
            for py in range(sub_y, sub_y + sub_h):
                for px in range(sub_x, sub_x + sub_w):
                    if 0 <= px < w and 0 <= py < h:
                        rect_image.putpixel((px, py), pixel_color)
        
        self.framebuffer.paste(rect_image, (x, y))
    
    def _read_pixel(self, bytes_per_pixel: int) -> Tuple[int, int, int]:
        """Чтение одного пикселя."""
        pixel_data = self._recv_exact(bytes_per_pixel)
        
        if bytes_per_pixel == 4:  # 32-bit
            b, g, r, _ = pixel_data
            return (r, g, b)
        elif bytes_per_pixel == 3:  # 24-bit
            b, g, r = pixel_data
            return (r, g, b)
        elif bytes_per_pixel == 2:  # 16-bit
            pixel = struct.unpack("!H", pixel_data)[0]
            r = ((pixel >> self.pixel_format['red_shift']) & 
                 ((1 << self._bit_count(self.pixel_format['red_max'])) - 1))
            g = ((pixel >> self.pixel_format['green_shift']) & 
                 ((1 << self._bit_count(self.pixel_format['green_max'])) - 1))
            b = ((pixel >> self.pixel_format['blue_shift']) & 
                 ((1 << self._bit_count(self.pixel_format['blue_max'])) - 1))
            # Масштабирование до 8 бит
            r = r * 255 // self.pixel_format['red_max']
            g = g * 255 // self.pixel_format['green_max']
            b = b * 255 // self.pixel_format['blue_max']
            return (r, g, b)
        else:
            return (0, 0, 0)
    
    def _handle_colormap_entries(self):
        """Обработка изменения цветовой карты."""
        # Пропускаем padding
        self._recv_exact(1)
        
        # First color, number of colors
        first_color = struct.unpack("!H", self._recv_exact(2))[0]
        num_colors = struct.unpack("!H", self._recv_exact(2))[0]
        
        # Пропускаем данные цветов (по 6 байт на цвет)
        self._recv_exact(num_colors * 6)
        
        logger.debug(f"Colormap entries: first={first_color}, count={num_colors}")
    
    def _handle_bell(self):
        """Обработка звукового сигнала."""
        logger.info("Bell received")
        # Можно воспроизвести звук
        self.after(0, self.app.bell)
    
    def _handle_server_cut_text(self):
        """Обработка текста из буфера обмена сервера."""
        # Пропускаем padding
        self._recv_exact(3)
        
        # Длина текста
        text_length = struct.unpack("!I", self._recv_exact(4))[0]
        
        # Читаем текст
        text = self._recv_exact(text_length).decode('latin-1')
        
        # Копируем в буфер обмена
        self.after(0, self._copy_to_clipboard, text)
    
    def _copy_to_clipboard(self, text: str):
        """Копирование текста в буфер обмена."""
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
    
    def _start_event_processor(self):
        """Запуск обработчика событий UI."""
        self._process_events()
    
    def _process_events(self):
        """Обработка событий из очереди."""
        try:
            while True:
                event_type, data = self.update_queue.get_nowait()
                
                if event_type == 'update_display':
                    self._update_canvas()
                elif event_type == 'update_status':
                    self.status_label.configure(text=data)
                elif event_type == 'update_resolution':
                    self.resolution_label.configure(text=data)
                    
        except queue.Empty:
            pass
        
        self.after(16, self._process_events)  # ~60 FPS
    
    def _update_canvas(self):
        """Обновление изображения на canvas с поддержкой масштабирования."""
        if not self.framebuffer:
            return
        
        try:
            start_time = time.time()
            
            # Определяем масштаб
            scale_value = self.scale_var.get()
            scale_factor = 1.0
            
            if scale_value == "Авто":
                # Автоматический масштаб на основе размера экрана
                canvas_width = self.canvas.winfo_width()
                canvas_height = self.canvas.winfo_height()
                
                if canvas_width > 1 and canvas_height > 1:
                    scale_x = canvas_width / self.screen_width
                    scale_y = canvas_height / self.screen_height
                    scale_factor = min(scale_x, scale_y, 1.0)  # Не увеличиваем
                    
                    # Для очень больших экранов принудительно уменьшаем
                    if self.screen_width > 2000 or self.screen_height > 1500:
                        scale_factor = min(scale_factor, 0.75)
            else:
                # Фиксированный масштаб
                scale_map = {"25%": 0.25, "50%": 0.5, "75%": 0.75, "100%": 1.0}
                scale_factor = scale_map.get(scale_value, 1.0)
            
            # Применяем масштабирование
            display_image = self.framebuffer
            if scale_factor != 1.0:
                new_width = int(self.screen_width * scale_factor)
                new_height = int(self.screen_height * scale_factor)
                
                # Используем более быстрый алгоритм ресайза для больших изображений
                if self.screen_width * self.screen_height > 2073600:  # > 1920x1080
                    resize_method = Image.NEAREST  # Быстрее
                else:
                    resize_method = Image.LANCZOS  # Качественнее
                
                display_image = self.framebuffer.resize((new_width, new_height), resize_method)
            
            # Преобразуем в PhotoImage
            photo = ImageTk.PhotoImage(display_image)
            
            # Обновляем canvas
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=photo)
            self.canvas.image = photo  # Сохраняем ссылку
            
            # Обновляем размер canvas
            display_width = int(self.screen_width * scale_factor)
            display_height = int(self.screen_height * scale_factor)
            self.canvas.configure(scrollregion=(0, 0, display_width, display_height))
            
            # Обновляем индикатор активности
            self.activity_indicator.configure(text="🟢")
            self.after(100, lambda: self.activity_indicator.configure(text="⚫"))
            
            # Обновляем информацию о масштабе
            if scale_factor != 1.0:
                scale_text = f" (масштаб {scale_factor:.0%})"
            else:
                scale_text = ""
            
            resolution_text = f"{self.screen_width}x{self.screen_height}{scale_text}"
            self.resolution_label.configure(text=resolution_text)
            
            # Логируем время обработки для больших изображений
            process_time = time.time() - start_time
            if process_time > 0.1:  # Больше 100ms
                logger.debug(f"Canvas update took {process_time:.3f}s")
            
            # Проверяем, нужно ли обработать отложенное обновление
            if self.pending_canvas_update:
                current_time = time.time()
                if current_time - self.last_canvas_update_time >= self.canvas_update_interval:
                    self.after(10, self._update_canvas)  # Планируем следующее обновление
            
        except Exception as e:
            logger.error(f"Canvas update error: {e}")
    
    def _update_status(self, status: str):
        """Обновление статуса."""
        self.update_queue.put(('update_status', status))
    
    def _on_connected(self):
        """Обработчик успешного подключения."""
        self.connect_button.configure(state="disabled")
        self.disconnect_button.configure(state="normal")
        self.reconnect_button.configure(state="normal")
        self.server_entry.configure(state="disabled")
        self.password_entry.configure(state="disabled")
        
        # Обновляем разрешение
        resolution_text = f"{self.screen_width}x{self.screen_height}"
        self.update_queue.put(('update_resolution', resolution_text))
        
        # Фокус на canvas
        self.canvas.focus_set()
    
    def _on_connection_failed(self, error: str):
        """Обработчик неудачного подключения."""
        error_message = f"Не удалось подключиться:\n{error}\n\n"
        
        # Добавляем советы в зависимости от ошибки
        if "Protocol" in error or "desynchronization" in error:
            error_message += "Советы для решения:\n"
            error_message += "• Попробуйте другой VNC клиент для сравнения\n"
            error_message += "• Проверьте настройки VNC сервера\n"
            error_message += "• Используйте кнопку 'Переподключиться'\n"
            error_message += "• Попробуйте режим 'Без пароля' если доступен"
        elif "Authentication" in error:
            error_message += "Советы для решения:\n"
            error_message += "• Проверьте правильность пароля\n"
            error_message += "• Попробуйте другой тип аутентификации\n"
            error_message += "• Убедитесь что VNC сервер принимает подключения"
        
        messagebox.showerror("Ошибка подключения", error_message)
    
    def disconnect_from_vnc(self):
        """Отключение от VNC сервера."""
        logger.info("Disconnecting from VNC server...")
        
        # Останавливаем флаг подключения
        self.connected = False
        self._stop_threads.set()
        
        # Безопасно закрываем сокет
        if self.socket:
            try:
                # Проверяем, что сокет ещё валидный
                if self.socket.fileno() != -1:
                    self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
                logger.debug("Socket closed successfully")
            except (OSError, socket.error) as e:
                logger.debug(f"Socket already closed or error during close: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error closing socket: {e}")
            finally:
                self.socket = None
        
        # Ждем завершения потоков
        if self.receiving_thread and self.receiving_thread.is_alive():
            logger.debug("Waiting for receiver thread to finish...")
            self.receiving_thread.join(timeout=2)  # Увеличили таймаут
            if self.receiving_thread.is_alive():
                logger.warning("Receiver thread did not finish in time")
        
        # Очистка UI
        try:
            self.canvas.delete("all")
        except Exception as e:
            logger.debug(f"Error clearing canvas: {e}")
        
        self.framebuffer = None
        
        # Сброс статистики и throttling
        self.frame_count = 0
        self.bytes_received = 0
        self.last_fps_time = time.time()
        self.last_stats_time = time.time()
        self.last_update_request_time = 0
        self.last_canvas_update_time = 0
        self.pending_canvas_update = False
        self.protocol_errors = 0
        
        # Обновление UI элементов
        try:
            self.connect_button.configure(state="normal")
            self.disconnect_button.configure(state="disabled")
            self.reconnect_button.configure(state="disabled")
            self.server_entry.configure(state="normal")
            self.password_entry.configure(state="normal")
            
            self._update_status("Отключено")
            self.resolution_label.configure(text="")
            self.fps_label.configure(text="")
        except Exception as e:
            logger.debug(f"Error updating UI during disconnect: {e}")
        
        logger.info("VNC disconnection completed")
    
    def reconnect_to_vnc(self):
        """Переподключение к VNC серверу."""
        logger.info("Reconnecting to VNC server...")
        self.disconnect_from_vnc()
        
        # Небольшая задержка перед переподключением
        self.after(1000, self.connect_to_vnc)
    
    # Обработчики событий мыши
    def _on_mouse_click(self, event):
        """Обработка клика мыши."""
        if self.connected and not self.view_only_var.get():
            self._send_pointer_event(event.x, event.y, button_mask=1)
    
    def _on_mouse_release(self, event):
        """Обработка отпускания кнопки мыши."""
        if self.connected and not self.view_only_var.get():
            self._send_pointer_event(event.x, event.y, button_mask=0)
    
    def _on_mouse_motion(self, event):
        """Обработка движения мыши с зажатой кнопкой."""
        if self.connected and not self.view_only_var.get():
            self._send_pointer_event(event.x, event.y, button_mask=1)
    
    def _on_mouse_move(self, event):
        """Обработка движения мыши."""
        if self.connected and not self.view_only_var.get():
            # Ограничиваем частоту отправки
            current_time = time.time()
            if hasattr(self, '_last_mouse_move_time'):
                if current_time - self._last_mouse_move_time < 0.05:  # 20 FPS
                    return
            self._last_mouse_move_time = current_time
            
            self._send_pointer_event(event.x, event.y, button_mask=0)
    
    def _on_right_click(self, event):
        """Обработка правого клика."""
        if self.connected and not self.view_only_var.get():
            self._send_pointer_event(event.x, event.y, button_mask=4)
    
    def _on_right_release(self, event):
        """Обработка отпускания правой кнопки."""
        if self.connected and not self.view_only_var.get():
            self._send_pointer_event(event.x, event.y, button_mask=0)
    
    def _on_mouse_wheel(self, event):
        """Обработка колеса мыши."""
        if self.connected and not self.view_only_var.get():
            # Определяем направление
            if event.delta > 0:
                button_mask = 8  # Wheel up
            else:
                button_mask = 16  # Wheel down
            
            # Отправляем нажатие и отпускание
            self._send_pointer_event(event.x, event.y, button_mask=button_mask)
            self.after(10, lambda: self._send_pointer_event(event.x, event.y, button_mask=0))
    
    def _send_pointer_event(self, x: int, y: int, button_mask: int):
        """Отправка события указателя с учетом масштабирования."""
        if not self.connected or not self.socket:
            return
        
        try:
            # Проверяем валидность сокета
            if self.socket.fileno() == -1:
                logger.debug("Cannot send pointer event: socket is closed")
                return
            
            # Корректируем координаты с учетом масштабирования
            scale_value = self.scale_var.get()
            scale_factor = 1.0
            
            if scale_value == "Авто":
                # Вычисляем автоматический масштаб
                canvas_width = self.canvas.winfo_width()
                canvas_height = self.canvas.winfo_height()
                
                if canvas_width > 1 and canvas_height > 1:
                    scale_x = canvas_width / self.screen_width
                    scale_y = canvas_height / self.screen_height
                    scale_factor = min(scale_x, scale_y, 1.0)
                    
                    if self.screen_width > 2000 or self.screen_height > 1500:
                        scale_factor = min(scale_factor, 0.75)
            else:
                scale_map = {"25%": 0.25, "50%": 0.5, "75%": 0.75, "100%": 1.0}
                scale_factor = scale_map.get(scale_value, 1.0)
            
            # Преобразуем координаты обратно к реальному разрешению
            real_x = int(x / scale_factor)
            real_y = int(y / scale_factor)
            
            # Ограничиваем координаты
            real_x = max(0, min(real_x, self.screen_width - 1))
            real_y = max(0, min(real_y, self.screen_height - 1))
            
            message = struct.pack(
                "!BBHH",
                self.POINTER_EVENT,
                button_mask,
                real_x, real_y
            )
            self.socket.send(message)
        except (OSError, socket.error) as e:
            logger.debug(f"Socket error sending pointer event: {e}")
            # Не разрываем соединение, просто игнорируем
        except Exception as e:
            logger.error(f"Error sending pointer event: {e}")
    
    # Обработчики клавиатуры
    def _on_key_press(self, event):
        """Обработка нажатия клавиши."""
        if self.connected and not self.view_only_var.get():
            keysym = self._get_keysym(event)
            if keysym:
                self._send_key_event(keysym, down=True)
    
    def _on_key_release(self, event):
        """Обработка отпускания клавиши."""
        if self.connected and not self.view_only_var.get():
            keysym = self._get_keysym(event)
            if keysym:
                self._send_key_event(keysym, down=False)
    
    def _get_keysym(self, event) -> Optional[int]:
        """Получение keysym для клавиши."""
        # Маппинг специальных клавиш
        special_keys = {
            'Return': 0xff0d,
            'Escape': 0xff1b,
            'BackSpace': 0xff08,
            'Tab': 0xff09,
            'space': 0x0020,
            'Delete': 0xffff,
            'Home': 0xff50,
            'End': 0xff57,
            'Prior': 0xff55,  # Page Up
            'Next': 0xff56,   # Page Down
            'Left': 0xff51,
            'Up': 0xff52,
            'Right': 0xff53,
            'Down': 0xff54,
            'F1': 0xffbe,
            'F2': 0xffbf,
            'F3': 0xffc0,
            'F4': 0xffc1,
            'F5': 0xffc2,
            'F6': 0xffc3,
            'F7': 0xffc4,
            'F8': 0xffc5,
            'F9': 0xffc6,
            'F10': 0xffc7,
            'F11': 0xffc8,
            'F12': 0xffc9,
            'Shift_L': 0xffe1,
            'Shift_R': 0xffe2,
            'Control_L': 0xffe3,
            'Control_R': 0xffe4,
            'Alt_L': 0xffe9,
            'Alt_R': 0xffea,
        }
        
        # Проверяем специальные клавиши
        if event.keysym in special_keys:
            return special_keys[event.keysym]
        
        # Обычные символы
        if len(event.char) == 1 and ord(event.char) < 256:
            return ord(event.char)
        
        return None
    
    def _send_key_event(self, keysym: int, down: bool):
        """Отправка события клавиатуры."""
        if not self.connected or not self.socket:
            return
        
        try:
            # Проверяем валидность сокета
            if self.socket.fileno() == -1:
                logger.debug("Cannot send key event: socket is closed")
                return
            
            message = struct.pack(
                "!BxBBxxxI",
                self.KEY_EVENT,
                1 if down else 0,
                0,  # padding
                keysym
            )
            self.socket.send(message)
        except (OSError, socket.error) as e:
            logger.debug(f"Socket error sending key event: {e}")
            # Не разрываем соединение, просто игнорируем
        except Exception as e:
            logger.error(f"Error sending key event: {e}")
    
    # Специальные команды
    def _send_ctrl_alt_del(self):
        """Отправка Ctrl+Alt+Del."""
        if not self.connected or self.view_only_var.get():
            return
        
        # Последовательность: Ctrl down, Alt down, Del down, Del up, Alt up, Ctrl up
        self._send_key_event(0xffe3, True)   # Ctrl down
        self._send_key_event(0xffe9, True)   # Alt down
        self._send_key_event(0xffff, True)   # Del down
        self.after(50, lambda: self._send_key_event(0xffff, False))  # Del up
        self.after(100, lambda: self._send_key_event(0xffe9, False))  # Alt up
        self.after(150, lambda: self._send_key_event(0xffe3, False))  # Ctrl up
    
    def _send_alt_tab(self):
        """Отправка Alt+Tab."""
        if not self.connected or self.view_only_var.get():
            return
        
        self._send_key_event(0xffe9, True)   # Alt down
        self._send_key_event(0xff09, True)   # Tab down
        self.after(50, lambda: self._send_key_event(0xff09, False))  # Tab up
        self.after(100, lambda: self._send_key_event(0xffe9, False))  # Alt up
    
    def _send_escape(self):
        """Отправка Escape."""
        if not self.connected or self.view_only_var.get():
            return
        
        self._send_key_event(0xff1b, True)   # Esc down
        self.after(50, lambda: self._send_key_event(0xff1b, False))  # Esc up
    
    def _toggle_fullscreen(self):
        """Переключение полноэкранного режима."""
        # TODO: Реализовать полноэкранный режим
        messagebox.showinfo("Информация", "Полноэкранный режим в разработке")
    
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
    
    def cleanup(self):
        """Очистка ресурсов."""
        self.disconnect_from_vnc()
    
    def _update_stats(self):
        """Обновление статистики производительности."""
        if not self.connected:
            self.after(1000, self._update_stats)
            return
        
        current_time = time.time()
        
        # Обновляем FPS
        if current_time - self.last_fps_time >= 1.0:
            fps = self.frame_count / (current_time - self.last_fps_time)
            self.fps_label.configure(text=f"FPS: {fps:.1f}")
            
            self.frame_count = 0
            self.last_fps_time = current_time
        
        # Обновляем статистику через секунду
        self.after(1000, self._update_stats)
    
    def _adjust_performance_settings(self):
        """Настройка производительности в зависимости от выбранного качества."""
        quality = self.quality_var.get()
        
        if quality == "Низкое":
            # Максимальная производительность
            self.update_request_interval = 0.1    # 10 FPS
            self.canvas_update_interval = 0.1     # 10 FPS UI
        elif quality == "Среднее":
            # Баланс качества и производительности
            self.update_request_interval = 0.05   # 20 FPS
            self.canvas_update_interval = 0.067   # 15 FPS UI
        else:  # Высокое
            # Максимальное качество
            self.update_request_interval = 0.033  # 30 FPS
            self.canvas_update_interval = 0.05    # 20 FPS UI
        
        logger.debug(f"Performance settings: quality={quality}, "
                    f"update_interval={self.update_request_interval}, "
                    f"canvas_interval={self.canvas_update_interval}")
    
    def _on_quality_change(self, value):
        """Обработка изменения качества."""
        self._adjust_performance_settings()
        logger.info(f"Quality changed to: {value}")

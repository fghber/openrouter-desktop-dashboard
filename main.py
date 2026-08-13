import tkinter as tk
import tkinter.ttk as ttk
import requests
import json
import threading
import time
import os
import sys
import hashlib
import base64
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:
    from backports.zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Common IANA timezone names for the settings combobox
COMMON_TIMEZONES = [
    '',  # empty = system local
    'UTC',
    'America/Los_Angeles',
    'America/Denver',
    'America/Chicago',
    'America/New_York',
    'America/Sao_Paulo',
    'Europe/London',
    'Europe/Berlin',
    'Europe/Paris',
    'Europe/Moscow',
    'Africa/Cairo',
    'Asia/Dubai',
    'Asia/Kolkata',
    'Asia/Bangkok',
    'Asia/Shanghai',  # Beijing (China uses a single timezone)
    'Asia/Hong_Kong',
    'Asia/Taipei',
    'Asia/Yangon',
    'Asia/Kathmandu',
    'Asia/Dhaka',
    'Asia/Karachi',
    'Asia/Tehran',
    'Asia/Jerusalem',
    'Asia/Baku',
    'Asia/Urumqi',
    'Asia/Tokyo',
    'Asia/Seoul',
    'Europe/Madrid',
    'Europe/Amsterdam',
    'Europe/Warsaw',
    'Europe/Istanbul',
    'Australia/Sydney',
    'Australia/Perth',
    'Pacific/Auckland',
    'Pacific/Honolulu',
]

# Supported currencies: code -> (symbol, decimal_places, is_zero_decimal)
# decimal_places: number of decimal places to show (2 for most, 0 for JPY)
# is_zero_decimal: True for currencies that don't use cents/subunits
CURRENCIES = {
    'USD': ('$', 2, False),
    'CNY': ('¥', 2, False),
    'EUR': ('€', 2, False),
    'GBP': ('£', 2, False),
    'JPY': ('¥', 0, True),
    'CAD': ('C$', 2, False),
    'AUD': ('A$', 2, False),
    'CHF': ('Fr', 2, False),
    'INR': ('₹', 2, False),
    'KRW': ('₩', 0, True),
    'BRL': ('R$', 2, False),
    'RUB': ('₽', 2, False),
    'TRY': ('₺', 2, False),
    'ZAR': ('R', 2, False),
    'SGD': ('S$', 2, False),
    'HKD': ('HK$', 2, False),
    'TWD': ('NT$', 2, False),
    'MYR': ('RM', 2, False),
    'THB': ('฿', 2, False),
    'IDR': ('Rp', 2, False),
}

# Locale-aware date format patterns (simplified, no locale.setlocale needed)
# Keys are locale identifiers, values are strftime format strings
LOCALE_PATTERNS = {
    'iso': '%Y-%m-%d',           # ISO 8601: 2024-01-15
    'us': '%m/%d/%Y',            # US: 01/15/2024
    'eu': '%d/%m/%Y',            # EU: 15/01/2024
    'jp': '%Y/%m/%d',            # Japan: 2024/01/15
    'cn': '%Y年%m月%d日',         # China: 2024年01月15日
    'kr': '%Y.%m.%d',            # Korea: 2024.01.15
    'tw': '%Y/%m/%d',            # Taiwan: 2024/01/15
    'hk': '%Y/%m/%d',            # Hong Kong: 2024/01/15
    'sg': '%d/%m/%Y',            # Singapore: 15/01/2024
    'my': '%d/%m/%Y',            # Malaysia: 15/01/2024
    'th': '%d/%m/%Y',            # Thailand: 15/01/2024
    'id': '%d/%m/%Y',            # Indonesia: 15/01/2024
    'in': '%d/%m/%Y',            # India: 15/01/2024
    'au': '%d/%m/%Y',            # Australia: 15/01/2024
    'nz': '%d/%m/%Y',            # New Zealand: 15/01/2024
    'za': '%Y/%m/%d',            # South Africa: 2024/01/15
    'br': '%d/%m/%Y',            # Brazil: 15/01/2024
    'ru': '%d.%m.%Y',            # Russia: 15.01.2024
    'tr': '%d.%m.%Y',            # Turkey: 15.01.2024
    'default': '%Y-%m-%d',       # Fallback: ISO format
}

# Timezone to locale mapping for automatic date format selection
# Maps IANA timezone names to LOCALE_PATTERNS keys
TZ_TO_LOCALE = {
    'America/New_York': 'us',
    'America/Chicago': 'us',
    'America/Denver': 'us',
    'America/Los_Angeles': 'us',
    'America/Anchorage': 'us',
    'America/Adak': 'us',
    'Pacific/Honolulu': 'us',
    'America/Toronto': 'us',
    'America/Vancouver': 'us',
    'America/Mexico_City': 'us',
    'America/Sao_Paulo': 'br',
    'America/Argentina/Buenos_Aires': 'br',
    'Europe/London': 'eu',
    'Europe/Paris': 'eu',
    'Europe/Berlin': 'eu',
    'Europe/Rome': 'eu',
    'Europe/Madrid': 'eu',
    'Europe/Amsterdam': 'eu',
    'Europe/Stockholm': 'eu',
    'Europe/Warsaw': 'eu',
    'Europe/Istanbul': 'tr',
    'Europe/Moscow': 'ru',
    'Asia/Shanghai': 'cn',
    'Asia/Hong_Kong': 'hk',
    'Asia/Taipei': 'tw',
    'Asia/Tokyo': 'jp',
    'Asia/Seoul': 'kr',
    'Asia/Singapore': 'sg',
    'Asia/Kuala_Lumpur': 'my',
    'Asia/Bangkok': 'th',
    'Asia/Jakarta': 'id',
    'Asia/Kolkata': 'in',
    'Asia/Dubai': 'eu',
    'Asia/Baku': 'ru',
    'Asia/Urumqi': 'cn',
    'Asia/Yangon': 'eu',
    'Asia/Kathmandu': 'eu',
    'Asia/Dhaka': 'eu',
    'Asia/Karachi': 'eu',
    'Asia/Tehran': 'eu',
    'Asia/Jerusalem': 'eu',
    'Africa/Cairo': 'eu',
    'Australia/Sydney': 'au',
    'Australia/Perth': 'au',
    'Pacific/Auckland': 'nz',
    'Pacific/Honolulu': 'us',
}


def resolve_tz(spec: str):
    """
    Resolve a timezone specification to a tzinfo object.
    
    Accepts:
    - Empty/None/whitespace -> system local time
    - Numeric string (e.g. '8', '-3.5', '5.75') -> fixed offset
    - IANA zone name (e.g. 'Asia/Shanghai', 'Europe/Berlin') -> zoneinfo
    
    On unknown IANA name, falls back to system local and prints a warning.
    """
    if not spec or not spec.strip():
        return datetime.now().astimezone().tzinfo
    s = spec.strip()
    # Try numeric offset first
    try:
        hours = float(s)
        return timezone(timedelta(hours=hours))
    except ValueError:
        pass
    # Try IANA zone name
    try:
        return ZoneInfo(s)
    except ZoneInfoNotFoundError:
        print(f"[tz] Unknown timezone '{s}', using system local", file=sys.stderr)
        return datetime.now().astimezone().tzinfo

# ── Exchange Rate ────────────────────────────────────────────────────────────

def fetch_exchange_rate(target_currency: str) -> float | None:
    """
    Fetch the latest USD -> target_currency exchange rate from a free public API.
    Returns None on failure.
    """
    if target_currency == 'USD':
        return 1.0
    try:
        r = requests.get(
            'https://api.exchangerate-api.com/v4/latest/USD',
            timeout=8
        )
        if r.status_code == 200:
            rates = r.json().get('rates', {})
            if target_currency in rates:
                return float(rates[target_currency])
    except Exception:
        pass
    # Fallback: try exchangerate.host
    try:
        r = requests.get(
            f'https://api.exchangerate.host/latest?base=USD&symbols={target_currency}',
            timeout=8
        )
        if r.status_code == 200:
            rates = r.json().get('rates', {})
            if target_currency in rates:
                return float(rates[target_currency])
    except Exception:
        pass
    return None

BG     = '#000000'  # Pure black, Dynamic Island classic base
BG2    = '#0d0d0d'  # Very dark gray card
BG3    = '#1a1e24'  # Slightly lighter dark gray
ACCENT = '#1f6feb'
GREEN  = '#3fb950'
YELLOW = '#d29922'
RED    = '#f85149'
WHITE  = '#f0f6fc'  # Brighter softer white
GRAY   = '#8b949e'
BORDER = '#30363d'
CYAN   = '#58a6ff'
PURPLE = '#bc8cff'

def _get_config_dir():
    """Return config file directory: use exe directory when packaged, script directory when running .py directly."""
    if getattr(sys, 'frozen', False):
        # After PyInstaller packaging, sys.executable is the exe path
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(_get_config_dir(), 'config.json')

# ── Encryption ────────────────────────────────────────────────────────────────

# Fields that should be encrypted in config.json
ENCRYPTED_FIELDS = {'api_key', 'extra_keys', 'mgmt_key'}

def _get_machine_id():
    """Generate a machine-specific identifier for encryption key derivation."""
    try:
        import uuid
        # Use MAC address as machine identifier
        mac = str(uuid.getnode())
        return hashlib.sha256(mac.encode()).digest()
    except Exception:
        # Fallback: use a fixed but obscure key (still better than plaintext)
        return hashlib.sha256(b'openrouter-dashboard-local-key').digest()

def _get_fernet():
    """Create a Fernet cipher using a machine-derived key."""
    try:
        from cryptography.fernet import Fernet
        key = base64.urlsafe_b64encode(_get_machine_id())
        return Fernet(key)
    except ImportError:
        return None

def _is_encrypted(value):
    """Check if a value looks like a Fernet-encrypted token."""
    return isinstance(value, str) and value.startswith('gAAAAA')

def _encrypt_value(value, encrypt=True):
    """Encrypt a string value. Returns the encrypted string or the original if encryption unavailable or disabled."""
    if not value or not encrypt:
        return value
    # Don't re-encrypt a value that's already encrypted
    if _is_encrypted(value):
        return value
    f = _get_fernet()
    if f is None:
        return value
    try:
        return f.encrypt(value.encode('utf-8')).decode('utf-8')
    except Exception:
        return value

def _decrypt_value(value, encrypt=True):
    """Decrypt a string value. Returns the decrypted string or the original if decryption fails or encryption disabled.
    Recursively decrypts to handle values that were accidentally double-encrypted."""
    if not value or not encrypt:
        return value
    f = _get_fernet()
    if f is None:
        return value
    try:
        dec = f.decrypt(value.encode('utf-8')).decode('utf-8')
        # If the decrypted result is still a Fernet token, decrypt again
        # (handles accidental double-encryption)
        if _is_encrypted(dec):
            return _decrypt_value(dec, encrypt)
        return dec
    except Exception:
        # Value might be plaintext (old config or manually edited)
        return value


def enable_window_effects(hwnd):
    try:
        import ctypes
        # 1. Enable Windows 11 native rounded corners
        # DWMWA_WINDOW_CORNER_PREFERENCE = 33
        # DWMWCP_ROUND = 2 (rounded)
        dwm = ctypes.windll.dwmapi
        corner_preference = ctypes.c_int(2)
        dwm.DwmSetWindowAttribute(
            hwnd,
            33,
            ctypes.byref(corner_preference),
            ctypes.sizeof(corner_preference)
        )
    except Exception:
        pass

    try:
        import ctypes
        # 2. Enable window shadow
        class MARGINS(ctypes.Structure):
            _fields_ = [
                ("cxLeftWidth", ctypes.c_int),
                ("cxRightWidth", ctypes.c_int),
                ("cyTopHeight", ctypes.c_int),
                ("cyBottomHeight", ctypes.c_int)
            ]
        dwm = ctypes.windll.dwmapi
        margins = MARGINS(-1, -1, -1, -1)
        dwm.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
    except Exception:
        pass


def load_config():
    d = {'api_key': '', 'refresh_sec': 60, 'x': None, 'y': None, 'alpha': 0.93,
         'timezone': '', 'currency': 'USD', 'currency_rate': 1.0, 'encrypt_keys': True}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding='utf-8') as f:
                d.update(json.load(f))
        except Exception:
            pass
    # Decrypt sensitive fields if encryption is enabled
    encrypt = d.get('encrypt_keys', True)
    needs_resave = False
    for field in ENCRYPTED_FIELDS:
        if field in d:
            if field == 'extra_keys':
                decrypted_keys = []
                for k in d[field]:
                    dec = _decrypt_value(k, encrypt)
                    # If the value wasn't encrypted (plaintext), mark for re-save
                    if encrypt and k == dec and k:
                        needs_resave = True
                    decrypted_keys.append(dec)
                d[field] = decrypted_keys
            else:
                dec = _decrypt_value(d[field], encrypt)
                # If the value wasn't encrypted (plaintext), mark for re-save
                if encrypt and d[field] == dec and d[field]:
                    needs_resave = True
                d[field] = dec
    # Re-save config to encrypt any plaintext keys
    if needs_resave and encrypt:
        save_config(d)
    return d


def save_config(cfg):
    # Encrypt sensitive fields before saving if encryption is enabled
    encrypt = cfg.get('encrypt_keys', True)
    cfg_to_save = dict(cfg)
    for field in ENCRYPTED_FIELDS:
        if field in cfg_to_save:
            if field == 'extra_keys':
                cfg_to_save[field] = [_encrypt_value(k, encrypt) for k in cfg_to_save[field]]
            else:
                cfg_to_save[field] = _encrypt_value(cfg_to_save[field], encrypt)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg_to_save, f, indent=2, ensure_ascii=False)


class Dashboard:
    def __init__(self):
        self.cfg = load_config()
        self._tz = resolve_tz(self.cfg.get('timezone', ''))
        self.root = tk.Tk()
        self._setup_window()
        self._build_ui()
        self._schedule_refresh()
        self.root.mainloop()

    def _now(self):
        """Return current time in the configured timezone."""
        return datetime.now(tz=self._tz)

    def _format_date_locale(self, date_str: str) -> str:
        """
        Format a date string (YYYY-MM-DD) according to locale and user preference.
        
        Args:
            date_str: Date string in YYYY-MM-DD format
        
        Returns:
            Formatted date string according to locale pattern and date_format setting.
        """
        if not date_str or len(date_str) < 10:
            return date_str
        
        # Parse the date
        try:
            year = int(date_str[0:4])
            month = int(date_str[5:7])
            day = int(date_str[8:10])
        except (ValueError, IndexError):
            return date_str
        
        # Resolve locale key from configured timezone (IANA → locale pattern)
        tz = self.cfg.get('timezone', '')
        locale_key = TZ_TO_LOCALE.get(tz, 'default')
        
        # Get pattern
        pattern = LOCALE_PATTERNS.get(locale_key, LOCALE_PATTERNS['default'])
        
        # Format using the pattern
        # Replace strftime-like placeholders
        formatted = pattern
        formatted = formatted.replace('%Y', f'{year:04d}')
        formatted = formatted.replace('%y', f'{year % 100:02d}')
        formatted = formatted.replace('%m', f'{month:02d}')
        formatted = formatted.replace('%-m', str(month))  # No zero-padding
        formatted = formatted.replace('%d', f'{day:02d}')
        formatted = formatted.replace('%-d', str(day))    # No zero-padding
        
        return formatted

    # ── Window ──────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.root.overrideredirect(True)
        self._pinned = self.cfg.get('pinned', True)
        self.root.attributes('-topmost', self._pinned)
        self.root.attributes('-alpha', self.cfg.get('alpha', 0.95))
        self.root.configure(bg=BG)

        # Dynamic Island state variable
        # 'island' = Dynamic Island capsule state, 'expanded' = expanded dashboard state
        self._island_state = self.cfg.get('island_state', 'expanded')
        # Migrate old cny_mode/cny_rate to new currency/currency_rate
        if self.cfg.get('cny_mode', False) and not self.cfg.get('currency'):
            self.cfg['currency'] = 'CNY'
        if not self.cfg.get('currency'):
            self.cfg['currency'] = 'USD'
        if not self.cfg.get('currency_rate'):
            self.cfg['currency_rate'] = self.cfg.get('cny_rate', 7.0)
        
        # Size definitions
        self._W_island = 270
        self._H_island = 32  # Reduced from 36 for a more compact capsule
        self._W_expanded = 370
        self._H_expanded = 200  # Increased from 185 for more content space

        # Animation state
        self._animating = False

        # Initial size
        W = self._W_expanded if self._island_state == 'expanded' else self._W_island
        H = self._H_expanded if self._island_state == 'expanded' else self._H_island

        v_left, v_top, sw, sh = self._get_virtual_screen()
        x = self.cfg['x'] if self.cfg['x'] is not None else v_left + sw - W - 20
        y = self.cfg['y'] if self.cfg['y'] is not None else v_top + 60
        self.root.geometry(f'{W}x{H}+{max(v_left, x)}+{max(v_top, y)}')

        # Enable Windows 11 rounded corners and shadows
        self.root.update_idletasks()
        enable_window_effects(self.root.winfo_id())

        self._dx = self._dy = 0
        self.root.bind('<Button-1>',        self._drag_start)
        self.root.bind('<B1-Motion>',       self._drag_move)
        self.root.bind('<ButtonRelease-1>', self._drag_end)
        self.root.bind('<Button-3>',        self._ctx_menu)

    def _get_virtual_screen(self):
        """Get virtual screen dimensions (supports multi-monitor setups)."""
        try:
            import ctypes
            # SM_XVIRTUALSCREEN = 76, SM_YVIRTUALSCREEN = 77
            # SM_CXVIRTUALSCREEN = 78, SM_CYVIRTUALSCREEN = 79
            left   = ctypes.windll.user32.GetSystemMetrics(76)
            top    = ctypes.windll.user32.GetSystemMetrics(77)
            width  = ctypes.windll.user32.GetSystemMetrics(78)
            height = ctypes.windll.user32.GetSystemMetrics(79)
            return left, top, width, height
        except Exception:
            # Fallback: use tkinter's screen dimensions
            return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def _drag_start(self, e):
        # Record mouse click offset relative to window top-left (record once, unchanged throughout)
        self._off_x = e.x_root - self.root.winfo_x()
        self._off_y = e.y_root - self.root.winfo_y()
        # Cache virtual screen and window dimensions for boundary clamping
        self._v_left, self._v_top, self._sw, self._sh = self._get_virtual_screen()
        self._ww = self.root.winfo_width()
        self._wh = self.root.winfo_height()

    def _drag_move(self, e):
        # Directly use mouse absolute screen coordinates minus offset, no winfo queries needed, smoothest
        new_x = e.x_root - self._off_x
        new_y = e.y_root - self._off_y
        # Boundary limits using virtual screen dimensions (supports multi-monitor)
        new_x = max(self._v_left - self._ww + 40, min(self._v_left + self._sw - 40, new_x))
        new_y = max(self._v_top, min(self._v_top + self._sh - self._wh, new_y))
        self.root.geometry(f'+{new_x}+{new_y}')
    def _drag_end(self, e):
        # Auto edge-snap logic
        W  = self.root.winfo_width()
        H  = self.root.winfo_height()
        x  = self.root.winfo_x()
        y  = self.root.winfo_y()
        v_left, v_top, sw, sh = self._get_virtual_screen()

        snap_threshold = 40  # Edge-snap threshold (pixels)

        # Check left edge snap (relative to virtual screen left)
        if x - v_left < snap_threshold:
            self._animate_snap(v_left, y)
        # Check right edge snap (relative to virtual screen right)
        elif (v_left + sw) - (x + W) < snap_threshold:
            self._animate_snap(v_left + sw - W, y)
        # Check top edge snap (relative to virtual screen top)
        elif y - v_top < snap_threshold:
            self._animate_snap(x, v_top)
        else:
            self.cfg['x'], self.cfg['y'] = x, y
            save_config(self.cfg)

    def _animate_snap(self, target_x, target_y):
        # Smooth snap animation
        curr_x = self.root.winfo_x()
        curr_y = self.root.winfo_y()
        W = self.root.winfo_width()
        H = self.root.winfo_height()
        
        step_x = (target_x - curr_x) // 2
        step_y = (target_y - curr_y) // 2
        
        if abs(step_x) >= 1 or abs(step_y) >= 1:
            new_x = curr_x + step_x
            new_y = curr_y + step_y
            self.root.geometry(f'{W}x{H}+{new_x}+{new_y}')
            self.root.after(10, lambda: self._animate_snap(target_x, target_y))
        else:
            self.root.geometry(f'{W}x{H}+{target_x}+{target_y}')
            self.cfg['x'], self.cfg['y'] = target_x, target_y
            save_config(self.cfg)

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Dynamic Island capsule view (Island Frame)
        self._island_frame = tk.Frame(self.root, bg=BG, cursor='hand2')
        
        # Dynamic Island inner container, removing light border, using pure black background for ultimate minimalist black capsule feel
        island_capsule = tk.Frame(self._island_frame, bg=BG2, highlightthickness=0)
        island_capsule.pack(fill='both', expand=True, padx=2, pady=2)
        
        # Dynamic Island left: Logo (also serves as status indicator - green=connected, yellow=refreshing, red=error)
        self._island_logo = tk.Label(island_capsule, text='⚡', bg=BG2, fg=CYAN, font=('Segoe UI', 10, 'bold'))
        self._island_logo.pack(side='left', padx=(12, 2))
        
        # Dynamic Island middle: side-by-side balance and daily spend, keeping their respective colors, slightly larger font, less spacing
        island_vals_frame = tk.Frame(island_capsule, bg=BG2)
        island_vals_frame.pack(side='left', expand=True)
        
        self._island_bal_lbl = tk.Label(island_vals_frame, text='Balance:——', bg=BG2, fg=GRAY, font=('Consolas', 9, 'bold'))
        self._island_bal_lbl.pack(side='left')
        
        self._island_sep = tk.Label(island_vals_frame, text='|', bg=BG2, fg=BORDER, font=('Consolas', 9))
        self._island_sep.pack(side='left', padx=4)
        
        self._island_daily_lbl = tk.Label(island_vals_frame, text='Today:——', bg=BG2, fg=GRAY, font=('Consolas', 9, 'bold'))
        self._island_daily_lbl.pack(side='left')
        
        # Dynamic Island right: expand arrow (minimal character to save space)
        self._island_arrow = tk.Label(island_capsule, text='›', bg=BG2, fg=GRAY, font=('Segoe UI', 11, 'bold'))
        self._island_arrow.pack(side='right', padx=(2, 12))

        # Bind Dynamic Island interaction events
        for widget in [self._island_frame, island_capsule, self._island_logo, island_vals_frame, 
                       self._island_bal_lbl, self._island_sep, self._island_daily_lbl, self._island_arrow]:
            widget.bind('<Button-1>', lambda _: self._toggle_island_state())
            widget.bind('<Enter>', lambda _: self._on_island_hover(True, island_capsule))
            widget.bind('<Leave>', lambda _: self._on_island_hover(False, island_capsule))

        # Expanded dashboard view (Expanded Frame)
        self._expanded_frame = tk.Frame(self.root, bg=BG)

        # title bar
        bar = tk.Frame(self._expanded_frame, bg=BG2, height=32, highlightthickness=1, highlightbackground=BORDER)
        bar.pack(fill='x', padx=2, pady=(2, 0))
        bar.pack_propagate(False)

        # Double-click title bar to collapse to Dynamic Island
        bar.bind('<Double-Button-1>', lambda _: self._toggle_island_state())

        tk.Label(bar, text=' ⚡ OpenRouter',
                 bg=BG2, fg=WHITE, font=('Segoe UI', 10, 'bold')
                 ).pack(side='left', pady=3)

        self._dot    = tk.Label(bar, text='●', bg=BG2, fg=GRAY, font=('Segoe UI', 7))
        self._status = tk.Label(bar, text='...', bg=BG2, fg=WHITE, font=('Segoe UI', 7))
        self._dot.pack(side='left', padx=(6, 1))
        self._status.pack(side='left')

        # Currency toggle — left side so it's always visible when collapsed
        self._cny_btn = tk.Label(bar, text='$', bg=BG2, fg=GRAY,
                                  font=('Segoe UI', 8, 'bold'), cursor='hand2', padx=4)
        self._cny_btn.pack(side='left', padx=(4, 0))
        self._cny_btn.bind('<Button-1>', lambda _: self._toggle_currency())
        self._cny_btn.bind('<Enter>',    lambda _: self._cny_btn.config(fg=WHITE))
        self._cny_btn.bind('<Leave>',    lambda _: self._cny_btn.config(
                                             fg=YELLOW if self.cfg.get('currency', 'USD') != 'USD' else GRAY))
        self._update_currency_ui()

        self._col2_cells = []

        # Close button - far right, pack first to ensure rightmost position
        close_btn = tk.Label(bar, text='✕', bg=BG2, fg=WHITE,
                             font=('Segoe UI', 9), cursor='hand2', padx=5)
        close_btn.pack(side='right', padx=(0, 2))
        close_btn.bind('<Button-1>', lambda _: self._quit())
        close_btn.bind('<Enter>',    lambda _: close_btn.config(fg=RED))
        close_btn.bind('<Leave>',    lambda _: close_btn.config(fg=WHITE))

        # Collapse to Dynamic Island button
        self._shrink_btn = tk.Label(bar, text='▲', bg=BG2, fg=GRAY,
                                  font=('Segoe UI', 8), cursor='hand2', padx=4)
        self._shrink_btn.pack(side='right', padx=(0, 0))
        self._shrink_btn.bind('<Button-1>', lambda _: self._toggle_island_state())
        self._shrink_btn.bind('<Enter>',    lambda _: self._shrink_btn.config(fg=WHITE))
        self._shrink_btn.bind('<Leave>',    lambda _: self._shrink_btn.config(fg=GRAY))

        # pin button
        self._pin_lbl = tk.Label(bar, text='📌', bg=BG2,
                                  fg=WHITE if self._pinned else GRAY,
                                  font=('Segoe UI', 8), cursor='hand2', padx=4)
        self._pin_lbl.pack(side='right', padx=(0, 0))
        self._pin_lbl.bind('<Button-1>', lambda _: self._toggle_pin())
        self._pin_lbl.bind('<Enter>',    lambda _: self._pin_lbl.config(fg=WHITE))
        self._pin_lbl.bind('<Leave>',    lambda _: self._pin_lbl.config(
                                             fg=WHITE if self._pinned else GRAY))

        for txt, cmd, hv, fs in [('⚙', self._open_settings,  WHITE, 9),
                                   ('↻', self._trigger_refresh, WHITE, 12)]:
            lb = tk.Label(bar, text=txt, bg=BG2, fg=WHITE,
                          font=('Segoe UI', fs), cursor='hand2', padx=4)
            lb.pack(side='right')
            lb.bind('<Button-1>', lambda _, c=cmd: c())
            lb.bind('<Enter>',    lambda _, l=lb, c=hv: l.config(fg=c))
            lb.bind('<Leave>',    lambda _, l=lb: l.config(fg=WHITE))

        # ── metric grid (2 rows × 3 cols) ──
        grid = tk.Frame(self._expanded_frame, bg=BG, padx=2, pady=2)
        grid.pack(fill='both', expand=True)
        grid.columnconfigure((0, 1, 2), weight=1, uniform='col')

        # (key, label, row, col, accent_color)
        specs = [
            ('balance', 'Account Balance', 0, 0, GREEN),
            ('daily',   'Daily Spend', 0, 1, RED),
            ('total',   'Total Spend', 0, 2, PURPLE),
            ('monthly', 'Monthly Spend', 1, 0, CYAN),
        ]
        self._vals = {}
        for key, label, row, col, acolor in specs:
            # wrap container, using highlightthickness=1 with BORDER color, presenting exquisite rounded card feel under Windows 11 rounded corners
            wrap = tk.Frame(grid, bg=acolor, highlightthickness=1, highlightbackground=BORDER)
            wrap.grid(row=row, column=col, padx=2, pady=2, sticky='nsew')
            cell = tk.Frame(wrap, bg=BG2, padx=7, pady=4)
            cell.pack(fill='both', expand=True, padx=(3, 0))  # Leave 3px colored indicator bar on left, not flush top/bottom, more rounded
            tk.Label(cell, text=label, bg=BG2, fg=GRAY,
                     font=('Segoe UI', 8), anchor='w').pack(anchor='w')
            v = tk.Label(cell, text='——', bg=BG2, fg=WHITE,
                         font=('Consolas', 13, 'bold'), anchor='w')
            v.pack(anchor='w')
            self._vals[key] = v
            if col == 2:
                self._col2_cells.append(wrap)
            if key == 'monthly':
                self._monthly_pct = tk.Label(cell, text='', bg=BG2, fg=GRAY,
                                             font=('Segoe UI', 7), anchor='w')
                self._monthly_pct.pack(anchor='w')
                bar_bg = tk.Frame(cell, bg=BG3, height=3)
                bar_bg.pack(fill='x', pady=(2, 0))
                bar_bg.pack_propagate(False)
                self._monthly_bar = tk.Frame(bar_bg, bg=CYAN, height=3)
                self._monthly_bar.place(x=0, y=0, relheight=1.0, relwidth=0)

        # top3 card occupies (1,1)
        top3_wrap = tk.Frame(grid, bg=PURPLE, highlightthickness=1, highlightbackground=BORDER)
        top3_wrap.grid(row=1, column=1, padx=2, pady=2, sticky='nsew')
        top3_cell = tk.Frame(top3_wrap, bg=BG2, padx=6, pady=2)
        top3_cell.pack(fill='both', expand=True, padx=(3, 0))
        top3_cell.columnconfigure(1, weight=1)
        self._top3_title = tk.Label(top3_cell, text='Monthly TOP 3 Models', bg=BG2, fg=GRAY,
                                     font=('Segoe UI', 7), anchor='w')
        self._top3_title.grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 0))
        self._top3_lbls = []
        medals = ['①', '②', '③']
        for i in range(3):
            tk.Label(top3_cell, text=medals[i], bg=BG2, fg=GRAY,
                     font=('Segoe UI', 7)).grid(row=i + 1, column=0, sticky='w', pady=0)
            name_lbl = tk.Label(top3_cell, text='——', bg=BG2, fg=GRAY,
                                font=('Segoe UI', 7), anchor='w')
            name_lbl.grid(row=i + 1, column=1, sticky='w', padx=(2, 0), pady=0)
            cost_lbl = tk.Label(top3_cell, text='', bg=BG2, fg=GRAY,
                                font=('Consolas', 7), anchor='e')
            cost_lbl.grid(row=i + 1, column=2, sticky='e', pady=0)
            self._top3_lbls.append((name_lbl, cost_lbl))

        # Top-up button occupies (1,2)
        wrap2 = tk.Frame(grid, bg=ACCENT, highlightthickness=1, highlightbackground=BORDER)
        wrap2.grid(row=1, column=2, padx=2, pady=2, sticky='nsew')
        topup_cell = tk.Frame(wrap2, bg=BG2, padx=7, pady=4)
        topup_cell.pack(fill='both', expand=True, padx=(3, 0))
        tk.Label(topup_cell, text='Credits', bg=BG2, fg=GRAY,
                 font=('Segoe UI', 8)).pack(anchor='w')
        topup_btn = tk.Label(topup_cell, text='+ Go to Credits', bg=ACCENT, fg=WHITE,
                             font=('Segoe UI', 8, 'bold'), cursor='hand2',
                             padx=6, pady=1, relief='flat')
        topup_btn.pack(anchor='w')
        topup_btn.bind('<Button-1>', lambda _: self._open_topup())
        topup_btn.bind('<Enter>',    lambda _: topup_btn.config(bg='#388bfd'))
        topup_btn.bind('<Leave>',    lambda _: topup_btn.config(bg=ACCENT))

        detail_btn = tk.Label(topup_cell, text='📊 Monthly Details', bg=BG3, fg=CYAN,
                              font=('Segoe UI', 8), cursor='hand2',
                              padx=6, pady=1, relief='flat')
        detail_btn.pack(anchor='w', pady=(3, 0))
        detail_btn.bind('<Button-1>', lambda _: self._open_daily_popup())
        detail_btn.bind('<Enter>',    lambda _: detail_btn.config(fg=WHITE))
        detail_btn.bind('<Leave>',    lambda _: detail_btn.config(fg=CYAN))

        self._col2_cells.append(wrap2)

        self._grid = grid
        grid.rowconfigure((0, 1), weight=1, uniform='row')

        # footer
        footer = tk.Frame(self._expanded_frame, bg=BG3, height=1)
        footer.pack(fill='x')
        self._time_lbl = tk.Label(self._expanded_frame, text='', bg=BG, fg=GRAY,
                                   font=('Segoe UI', 7))
        self._time_lbl.pack(side='bottom', pady=(0, 3))

        # Show corresponding Frame based on initial state
        if self._island_state == 'island':
            self._island_frame.pack(fill='both', expand=True, padx=2, pady=2)
        else:
            self._expanded_frame.pack(fill='both', expand=True, padx=2, pady=2)

        if not self.cfg.get('api_key'):
            self.root.after(200, self._open_settings)

    # ── Currency ─────────────────────────────────────────────────────────────

    def _toggle_currency(self):
        """Cycle through all supported currencies."""
        currency_list = list(CURRENCIES.keys())
        current = self.cfg.get('currency', 'USD')
        idx = currency_list.index(current) if current in currency_list else 0
        next_currency = currency_list[(idx + 1) % len(currency_list)]
        self.cfg['currency'] = next_currency
        save_config(self.cfg)
        self._update_currency_ui()
        if hasattr(self, '_last_data'):
            self._update_ui(self._last_data)

    def _update_currency_ui(self):
        """Update the currency toggle button label and color."""
        currency = self.cfg.get('currency', 'USD')
        symbol = CURRENCIES.get(currency, ('$', 2, False))[0]
        self._cny_btn.config(text=symbol)
        # Highlight non-USD currencies
        self._cny_btn.config(fg=YELLOW if currency != 'USD' else GRAY)

    def _fmt(self, usd):
        """Format a USD float according to current currency."""
        currency = self.cfg.get('currency', 'USD')
        rate = float(self.cfg.get('currency_rate', 1.0))
        symbol, decimals, _ = CURRENCIES.get(currency, ('$', 2, False))
        if currency == 'USD':
            return f'${usd:.2f}'
        converted = usd * rate
        if decimals == 0:
            return f'{symbol}{converted:.0f}'
        return f'{symbol}{converted:.2f}'

    def _fmt2(self, usd):
        """Format with 2 decimal places (for balance / limit)."""
        currency = self.cfg.get('currency', 'USD')
        rate = float(self.cfg.get('currency_rate', 1.0))
        symbol, decimals, _ = CURRENCIES.get(currency, ('$', 2, False))
        if currency == 'USD':
            return f'${usd:.2f}'
        converted = usd * rate
        if decimals == 0:
            return f'{symbol}{converted:.0f}'
        return f'{symbol}{converted:.2f}'

    def _fetch_rate(self, currency_var, rate_var):
        """Fetch the latest exchange rate from a public API and update the entry."""
        target = currency_var.get().strip()
        if not target or target == 'USD':
            rate_var.set('1.0')
            return
        rate = fetch_exchange_rate(target)
        if rate is not None:
            rate_var.set(f'{rate:.4f}')
        else:
            rate_var.set('?')

    def _toggle_encrypt(self, encrypt_var, lock_row):
        """Toggle encryption on/off for API keys."""
        encrypt_var.set(not encrypt_var.get())
        self.cfg['encrypt_keys'] = encrypt_var.get()
        # Update lock icon color (first child)
        lock_icon = lock_row.winfo_children()[0]
        lock_icon.config(fg=WHITE if encrypt_var.get() else GRAY)
        # Update lock button text (second child)
        lock_btn = lock_row.winfo_children()[1]
        lock_btn.config(text='Store keys encrypted' if encrypt_var.get() else 'Store keys unencrypted')
        # Re-save config with new encryption setting
        # This will re-encrypt or decrypt all sensitive fields
        save_config(self.cfg)

    # ── Island Animation & Hover Effects ──────────────────────────────────────

    def _on_island_hover(self, entering, capsule):
        if self._island_state != 'island' or self._animating:
            return
        if entering:
            # Hover effect: capsule background brightens, creating Dynamic Island breathing feel, no physical width change to completely eliminate jitter bug
            capsule.config(bg=BG3)
            for w in [self._island_logo, self._island_bal_lbl, self._island_sep, self._island_daily_lbl, self._island_arrow]:
                w.config(bg=BG3)
            self._island_arrow.config(fg=WHITE)
        else:
            # Mouse leave: restore original state
            capsule.config(bg=BG2)
            for w in [self._island_logo, self._island_bal_lbl, self._island_sep, self._island_daily_lbl, self._island_arrow]:
                w.config(bg=BG2)
            self._island_arrow.config(fg=GRAY)

    def _toggle_island_state(self):
        if self._animating:
            return
        
        if self._island_state == 'expanded':
            self._island_state = 'island'
            target_w, target_h = self._W_island, self._H_island
            # Collapse: hide large panel first to avoid squeezing
            self._expanded_frame.pack_forget()
            self._island_frame.pack(fill='both', expand=True, padx=2, pady=2)
        else:
            self._island_state = 'expanded'
            target_w, target_h = self._W_expanded, self._H_expanded
            # Expand: hide Dynamic Island first, show large panel after animation ends
            self._island_frame.pack_forget()

        self.cfg['island_state'] = self._island_state
        save_config(self.cfg)
        
        self._animate_geometry(target_w, target_h)

    def _animate_geometry(self, target_w, target_h):
        self._animating = True
        start_w = self.root.winfo_width()
        start_h = self.root.winfo_height()
        x = self.root.winfo_x()
        y = self.root.winfo_y()

        steps = 12  # Animation frames
        delay = 12  # Per-frame delay (ms)

        def step_anim(current_step):
            if current_step > steps:
                # Animation complete
                self.root.geometry(f'{target_w}x{target_h}+{x}+{y}')
                if self._island_state == 'expanded':
                    self._expanded_frame.pack(fill='both', expand=True, padx=2, pady=2)
                self._animating = False
                return

            # Ease Out Cubic easing formula
            t = current_step / steps
            factor = 1 - (1 - t) ** 3
            
            w = int(start_w + (target_w - start_w) * factor)
            h = int(start_h + (target_h - start_h) * factor)
            
            self.root.geometry(f'{w}x{h}+{x}+{y}')
            self.root.after(delay, lambda: step_anim(current_step + 1))

        step_anim(1)

    # ── Settings ─────────────────────────────────────────────────────────────

    def _open_settings(self):
        dlg = tk.Toplevel(self.root)
        dlg.title('Settings')
        dlg.configure(bg=BG2)
        dlg.resizable(False, True)
        dlg.attributes('-topmost', True)
        dlg.grab_set()
        dlg.geometry(f'320x460+{self.root.winfo_x()+20}+{self.root.winfo_y()+32}')

        # Unified font constants
        LBL_FONT  = ('Segoe UI', 8)      # All labels
        HINT_FONT = ('Segoe UI', 8)      # Hint text (same as labels)
        ENT_FONT  = ('Consolas', 9)      # All entry fields

        # Encryption toggle (lock button)
        encrypt_var = tk.BooleanVar(value=self.cfg.get('encrypt_keys', True))
        lock_row = tk.Frame(dlg, bg=BG2)
        lock_row.pack(fill='x', padx=14, pady=(4, 0))
        lock_icon = tk.Label(lock_row, text='🔒', bg=BG2, fg=WHITE if encrypt_var.get() else GRAY,
                             font=('Segoe UI', 10), cursor='hand2')
        lock_icon.pack(side='left', padx=(0, 4))
        lock_btn = tk.Label(lock_row, text='Store keys encrypted', bg=BG2, fg=GRAY,
                            font=LBL_FONT, cursor='hand2')
        lock_btn.pack(side='left')
        lock_btn.bind('<Button-1>', lambda _: self._toggle_encrypt(encrypt_var, lock_row))
        lock_icon.bind('<Button-1>', lambda _: self._toggle_encrypt(encrypt_var, lock_row))
        # Tooltip
        lock_btn.bind('<Enter>', lambda _: lock_btn.config(fg=WHITE))
        lock_btn.bind('<Leave>', lambda _: lock_btn.config(fg=GRAY))

        def _entry(parent, var, show='*'):
            """Uniform style single-line entry with show/hide Key checkbox row"""
            e = tk.Entry(parent, textvariable=var, show=show, bg=BG3, fg=WHITE,
                         insertbackground=WHITE, relief='flat', font=ENT_FONT,
                         bd=0, highlightthickness=1,
                         highlightcolor=ACCENT, highlightbackground=BORDER)
            e.pack(fill='x', padx=14, ipady=5)
            sv = tk.BooleanVar()
            tk.Checkbutton(parent, text='Show Key', variable=sv,
                           command=lambda: e.config(show='' if sv.get() else '*'),
                           bg=BG2, fg=GRAY, selectcolor=BG3,
                           activebackground=BG2, font=LBL_FONT
                           ).pack(anchor='w', padx=14)

        # Main API Key
        tk.Label(dlg, text='API Key (main, for account and balance query)', bg=BG2, fg=GRAY,
                 font=LBL_FONT).pack(anchor='w', padx=14, pady=(10, 2))
        kv = tk.StringVar(value=self.cfg.get('api_key', ''))
        _entry(dlg, kv)

        # Other API Keys (multi-line, one per line, using Entry list to support hide/show)
        tk.Label(dlg, text='Other API Keys (one per line, for daily spend sum)', bg=BG2, fg=GRAY,
                 font=LBL_FONT).pack(anchor='w', padx=14, pady=(8, 2))

        extra_keys_saved = self.cfg.get('extra_keys', [])
        extra_vars = []
        extra_frame = tk.Frame(dlg, bg=BG2)
        extra_frame.pack(fill='x', padx=14)

        # Each extra key row adds ~34px of height
        ROW_HEIGHT = 34
        BASE_HEIGHT = 565 # Height with 1 default row

        def _update_dialog_height():
            """Resize dialog to fit all extra key rows."""
            row_count = len(extra_vars)
            new_h = BASE_HEIGHT + max(0, row_count - 1) * ROW_HEIGHT
            new_h = min(new_h, 800)  # Cap at 800px
            x = self.root.winfo_x() + 20
            y = self.root.winfo_y() + 32
            dlg.geometry(f'320x{new_h}+{x}+{y}')

        def _add_extra_row(val=''):
            ev = tk.StringVar(value=val)
            extra_vars.append(ev)
            row_f = tk.Frame(extra_frame, bg=BG2)
            row_f.pack(fill='x', pady=(0, 2))
            ee = tk.Entry(row_f, textvariable=ev, show='*', bg=BG3, fg=WHITE,
                          insertbackground=WHITE, relief='flat', font=ENT_FONT,
                          bd=0, highlightthickness=1,
                          highlightcolor=ACCENT, highlightbackground=BORDER)
            ee.pack(side='left', fill='x', expand=True, ipady=4)
            eye_var = tk.BooleanVar()
            tk.Checkbutton(row_f, text='👁', variable=eye_var,
                           command=lambda: ee.config(show='' if eye_var.get() else '*'),
                           bg=BG2, fg=GRAY, selectcolor=BG3,
                           activebackground=BG2, font=LBL_FONT
                           ).pack(side='left', padx=(4, 0))
            _update_dialog_height()

        for k in extra_keys_saved:
            _add_extra_row(k)
        for _ in range(max(0, 1 - len(extra_keys_saved))):
            _add_extra_row('')

        add_btn = tk.Label(dlg, text='＋ Add Row', bg=BG2, fg=CYAN,
                           font=LBL_FONT, cursor='hand2')
        add_btn.pack(anchor='w', padx=14)
        add_btn.bind('<Button-1>', lambda _: _add_extra_row())
        tk.Label(dlg, text='One Key per line, empty lines ignored', bg=BG2, fg=GRAY,
                 font=HINT_FONT).pack(anchor='w', padx=14, pady=(0, 2))

        # Management Key
        tk.Label(dlg, text='Management Key (optional, TOP 3, monthly details)', bg=BG2, fg=GRAY,
                 font=LBL_FONT).pack(anchor='w', padx=14, pady=(8, 2))
        mv = tk.StringVar(value=self.cfg.get('mgmt_key', ''))
        _entry(dlg, mv)

        # Refresh Interval
        tk.Label(dlg, text='Refresh Interval (sec)', bg=BG2, fg=GRAY,
                 font=LBL_FONT).pack(anchor='w', padx=14, pady=(8, 2))
        rv = tk.StringVar(value=str(self.cfg.get('refresh_sec', 60)))
        tk.Entry(dlg, textvariable=rv, bg=BG3, fg=WHITE, insertbackground=WHITE,
                 relief='flat', font=ENT_FONT, width=8, bd=0,
                 highlightthickness=1, highlightcolor=ACCENT,
                 highlightbackground=BORDER).pack(fill='x', padx=14, ipady=4)

        # Currency
        tk.Label(dlg, text='Currency (OpenRouter prices are in USD)', bg=BG2, fg=GRAY,
                 font=LBL_FONT).pack(anchor='w', padx=14, pady=(8, 2))
        currency_var = tk.StringVar(value=self.cfg.get('currency', 'USD'))
        currency_combo = ttk.Combobox(dlg, textvariable=currency_var,
                                      values=list(CURRENCIES.keys()),
                                      font=ENT_FONT, state='readonly', height=12)
        currency_combo.pack(fill='x', padx=14, ipady=4)

        # Exchange Rate (USD -> selected currency)
        tk.Label(dlg, text='Exchange Rate (USD → selected currency)', bg=BG2, fg=GRAY,
                 font=LBL_FONT).pack(anchor='w', padx=14, pady=(8, 2))
        rate_row = tk.Frame(dlg, bg=BG2)
        rate_row.pack(fill='x', padx=14)
        rate_var = tk.StringVar(value=str(self.cfg.get('currency_rate', 1.0)))
        rate_entry = tk.Entry(rate_row, textvariable=rate_var, bg=BG3, fg=WHITE, insertbackground=WHITE,
                 relief='flat', font=ENT_FONT, width=8, bd=0,
                 highlightthickness=1, highlightcolor=ACCENT,
                 highlightbackground=BORDER)
        rate_entry.pack(side='left', fill='x', expand=True, ipady=4)

        # Fetch rate button
        fetch_btn = tk.Label(rate_row, text='↻ Fetch', bg=BG2, fg=CYAN,
                             font=LBL_FONT, cursor='hand2', padx=6)
        fetch_btn.pack(side='right', padx=(4, 0))
        fetch_btn.bind('<Button-1>', lambda _: self._fetch_rate(currency_var, rate_var))
        fetch_btn.bind('<Enter>',    lambda _: fetch_btn.config(fg=WHITE))
        fetch_btn.bind('<Leave>',    lambda _: fetch_btn.config(fg=CYAN))

        # Timezone
        tk.Label(dlg, text='Timezone: IANA name, offset hours, or empty=syst. local', bg=BG2, fg=GRAY,
                 font=LBL_FONT).pack(anchor='w', padx=14, pady=(8, 2))
        tz_var = tk.StringVar(value=self.cfg.get('timezone', ''))
        tz_combo = ttk.Combobox(dlg, textvariable=tz_var, values=COMMON_TIMEZONES,
                                font=ENT_FONT, state='normal', height=12)
        tz_combo.pack(fill='x', padx=14, ipady=4)

        def _save():
            self.cfg['api_key']  = kv.get().strip()
            self.cfg['mgmt_key'] = mv.get().strip()
            # Read extra keys from each row Entry's StringVar
            self.cfg['extra_keys'] = [v.get().strip() for v in extra_vars if v.get().strip()]
            try: self.cfg['refresh_sec'] = max(10, int(rv.get().strip()))
            except ValueError: pass
            self.cfg['currency'] = currency_var.get().strip()
            try:
                rate = float(rate_var.get().strip())
                if rate > 0:
                    self.cfg['currency_rate'] = rate
            except ValueError: pass
            self.cfg['timezone'] = tz_var.get().strip()
            save_config(self.cfg)
            # Apply new timezone immediately
            self._tz = resolve_tz(self.cfg['timezone'])
            self._update_currency_ui()
            dlg.destroy()
            self._trigger_refresh()

        tk.Button(dlg, text='Save', bg=ACCENT, fg=WHITE, relief='flat',
                  font=('Segoe UI', 9, 'bold'), cursor='hand2',
                  command=_save).pack(fill='x', padx=14, pady=10, ipady=4)

    def _open_daily_popup(self):
        bd = getattr(self, '_daily_breakdown', {})
        no_mgmt = not self.cfg.get('mgmt_key', '').strip()

        dlg = tk.Toplevel(self.root)
        dlg.title('Monthly Daily Usage')
        dlg.configure(bg=BG2)
        dlg.resizable(False, False)
        dlg.attributes('-topmost', True)
        dlg.grab_set()
        dlg.geometry(f'380x320+{self.root.winfo_x()-10}+{self.root.winfo_y()+32}')

        # header
        hdr = tk.Frame(dlg, bg=ACCENT, height=28)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        tk.Label(hdr, text='📊 Monthly Daily Usage',
                 bg=ACCENT, fg=WHITE, font=('Segoe UI', 10, 'bold')).pack(side='left', padx=10)
        close_lbl = tk.Label(hdr, text='✕', bg=ACCENT, fg=WHITE,
                 font=('Segoe UI', 9), cursor='hand2', padx=8)
        close_lbl.pack(side='right')
        close_lbl.bind('<Button-1>', lambda _: dlg.destroy())

        if no_mgmt:
            msg = 'Please enter "Management Key" in settings and refresh data'
            tk.Label(dlg, text=msg, bg=BG2, fg=GRAY,
                     font=('Segoe UI', 9)).pack(expand=True)
            return

        # Has management key but no data yet: show loading prompt and trigger refresh
        if not bd:
            loading_lbl = tk.Label(dlg, text='⏳ Loading data, please wait...', bg=BG2, fg=GRAY,
                                   font=('Segoe UI', 9))
            loading_lbl.pack(expand=True)

            def _poll_data(retries=0):
                """Check every 500ms if data is ready, max 20 times (10 seconds)"""
                if not dlg.winfo_exists():
                    return
                new_bd = getattr(self, '_daily_breakdown', {})
                if new_bd:
                    # Data ready, rebuild popup content
                    dlg.destroy()
                    self._open_daily_popup()
                elif retries < 20:
                    dlg.after(500, lambda: _poll_data(retries + 1))
                else:
                    loading_lbl.config(text='No activity data this month\n(activity API has audit delay,\ntoday\'s spend usually appears tomorrow)',
                                       fg=YELLOW)

            # Trigger background refresh
            self._trigger_refresh()
            _poll_data()
            return

        # column headers
        col_frame = tk.Frame(dlg, bg=BG3, padx=8, pady=4)
        col_frame.pack(fill='x')
        for txt, w, anchor in [('Date', 11, 'w'), ('Token Usage', 13, 'e'),
                                ('Cost', 10, 'e'), ('Share', 5, 'e')]:
            tk.Label(col_frame, text=txt, bg=BG3, fg=GRAY,
                     font=('Segoe UI', 8, 'bold'),
                     width=w, anchor=anchor).pack(side='left')

        # scrollable rows
        outer = tk.Frame(dlg, bg=BG2)
        outer.pack(fill='both', expand=True, padx=2)
        canvas = tk.Canvas(outer, bg=BG2, highlightthickness=0)
        sb = tk.Scrollbar(outer, orient='vertical', command=canvas.yview,
                          bg=BG3, troughcolor=BG2, width=8)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        inner = tk.Frame(canvas, bg=BG2)
        canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(
            scrollregion=canvas.bbox('all')))
        canvas.bind('<MouseWheel>', lambda e: canvas.yview_scroll(
            int(-1 * (e.delta / 120)), 'units'))

        days = sorted(bd.keys(), reverse=True)
        total_cost = sum(v['cost'] for v in bd.values()) or 1

        for i, day in enumerate(days):
            row_bg = BG3 if i % 2 == 0 else BG2
            row = tk.Frame(inner, bg=row_bg, padx=8, pady=3)
            row.pack(fill='x')

            cost   = bd[day]['cost']
            tokens = bd[day]['tokens']
            pct    = cost / total_cost * 100
            cost_str = self._fmt(cost)
            tok_str  = f'{tokens:,}' if tokens else '—'
            bar_pct  = pct / 100

            # date
            formatted_day = self._format_date_locale(day)
            tk.Label(row, text=formatted_day, bg=row_bg, fg=WHITE,
                     font=('Segoe UI', 8, 'bold'), width=11, anchor='w').pack(side='left')
            # tokens
            tk.Label(row, text=tok_str, bg=row_bg, fg=GRAY,
                     font=('Segoe UI', 8, 'bold'), width=13, anchor='e').pack(side='left')
            # cost
            cost_color = RED if cost > 1 else YELLOW if cost > 0.1 else WHITE
            tk.Label(row, text=cost_str, bg=row_bg, fg=cost_color,
                     font=('Segoe UI', 8, 'bold'), width=10, anchor='e').pack(side='left')
            # mini bar + pct
            bar_wrap = tk.Frame(row, bg=row_bg)
            bar_wrap.pack(side='left', fill='x', expand=True, padx=(6, 0))
            bar_track = tk.Frame(bar_wrap, bg=BG3, height=6)
            bar_track.pack(fill='x', pady=(4, 0))
            bar_track.update_idletasks()
            fill_color = RED if pct > 30 else YELLOW if pct > 10 else CYAN
            tk.Frame(bar_track, bg=fill_color, height=6,
                     width=max(2, int(bar_pct * 100))).place(x=0, y=0, relheight=1.0,
                                                              relwidth=bar_pct)
            tk.Label(row, text=f'{pct:.1f}%', bg=row_bg, fg=GRAY,
                     font=('Segoe UI', 7), width=5, anchor='e').pack(side='right')

        # footer summary
        total_tok = sum(v['tokens'] for v in bd.values())
        total_cost_real = sum(v['cost'] for v in bd.values())
        cost_total_str = self._fmt(total_cost_real)
        foot = tk.Frame(dlg, bg=BG3, padx=8, pady=4)
        foot.pack(fill='x')
        tk.Label(foot, text=f'Monthly Total: {total_tok:,} tokens  /  {cost_total_str}',
                 bg=BG3, fg=WHITE, font=('Segoe UI', 8)).pack(side='left')

    def _open_topup(self):
        import webbrowser
        webbrowser.open('https://openrouter.ai/settings/credits')

    def _toggle_pin(self):
        self._pinned = not self._pinned
        self.root.attributes('-topmost', self._pinned)
        self._pin_lbl.config(fg=WHITE if self._pinned else GRAY)
        self.cfg['pinned'] = self._pinned
        save_config(self.cfg)

    def _ctx_menu(self, e):
        m = tk.Menu(self.root, tearoff=0, bg=BG2, fg=WHITE,
                    activebackground=ACCENT, activeforeground=WHITE, bd=0)
        pin_label = '📌  Unpin' if self._pinned else '📌  Pin'
        m.add_command(label=pin_label,          command=self._toggle_pin)
        m.add_command(label='⚙  Settings', command=self._open_settings)
        m.add_command(label='↻  Refresh Now',      command=self._trigger_refresh)
        m.add_separator()
        m.add_command(label='✕  Exit',           command=self._quit)
        try:    m.tk_popup(e.x_root, e.y_root)
        finally: m.grab_release()

    # ── Data ─────────────────────────────────────────────────────────────────

    def _fetch(self):
        key = self.cfg.get('api_key', '').strip()
        if not key:
            return {'error': 'no_key'}
        headers = {'Authorization': f'Bearer {key}'}
        last_err = None
        for attempt in range(3):
            try:
                r = requests.get('https://openrouter.ai/api/v1/auth/key',
                                 headers=headers, timeout=10)
                last_err = None
                break
            except Exception as e:
                last_err = e
                if attempt < 2:
                    time.sleep(2)
        if last_err:
            return {'error': str(last_err)}

        if r.status_code == 401:
            return {'error': '401'}
        if r.status_code != 200:
            return {'error': f'HTTP {r.status_code}'}

        d = r.json().get('data', {})

        # 1. credits API: balance + historical total spend (account level, any key returns same result)
        balance = None
        global_total_usage = 0.0
        for attempt in range(3):
            try:
                rc = requests.get('https://openrouter.ai/api/v1/credits',
                                  headers=headers, timeout=8)
                if rc.status_code == 200:
                    cd = rc.json().get('data', {})
                    granted = float(cd.get('total_credits', 0) or 0)
                    used    = float(cd.get('total_usage',   0) or 0)
                    balance = granted - used
                    global_total_usage = used
                break
            except Exception:
                if attempt < 2:
                    time.sleep(2)

        # 2. Daily spend: query usage_daily for all configured keys and sum
        # usage_daily reset by OpenRouter officially at UTC 0:00 real-time, no delay, most accurate
        all_keys = [key] + [k for k in self.cfg.get('extra_keys', []) if k]
        all_daily  = 0.0
        all_monthly = 0.0
        for k in all_keys:
            for attempt in range(2):
                try:
                    rk = requests.get('https://openrouter.ai/api/v1/auth/key',
                                      headers={'Authorization': f'Bearer {k}'},
                                      timeout=8)
                    if rk.status_code == 200:
                        kd = rk.json().get('data', {})
                        all_daily   += float(kd.get('usage_daily',   0) or 0)
                        all_monthly += float(kd.get('usage_monthly', 0) or 0)
                    break
                except Exception:
                    if attempt < 1:
                        time.sleep(1)

        # model top3 + daily breakdown — requires management key
        top3 = []
        top3_latest = ''
        daily_breakdown = {}
        # activity API has audit delay (today's spend often appears tomorrow), only used for monthly details and TOP3, not for daily spend
        mgmt_key = self.cfg.get('mgmt_key', '').strip()
        if mgmt_key:
            now_utc = datetime.now(tz=timezone.utc)
            month_prefix = now_utc.strftime('%Y-%m')
            for attempt in range(3):
                try:
                    rg = requests.get(
                        'https://openrouter.ai/api/v1/activity',
                        headers={'Authorization': f'Bearer {mgmt_key}'},
                        params={'limit': 1000},
                        timeout=10,
                    )
                    if rg.status_code == 200:
                        model_cost: dict = {}
                        daily_breakdown: dict = {}
                        latest_date = ''
                        all_data = rg.json().get('data', [])
                        print(f"[activity] API returned {len(all_data)} items, month_prefix={month_prefix}", file=sys.stderr)
                        if all_data:
                            print(f"[activity] First item keys: {list(all_data[0].keys())}", file=sys.stderr)
                            print(f"[activity] First item: {all_data[0]}", file=sys.stderr)
                        for g in all_data:
                            gdate = g.get('date', '')
                            if not gdate.startswith(month_prefix):
                                continue
                            day = gdate[:10]
                            if day > latest_date:
                                latest_date = day
                            model = g.get('model', '')
                            cost  = float(g.get('usage', 0) or 0)
                            tok_in  = int(g.get('prompt_tokens', 0) or 0)
                            tok_out = int(g.get('completion_tokens', 0) or 0)
                            if model:
                                model_cost[model] = model_cost.get(model, 0) + cost
                            if day not in daily_breakdown:
                                daily_breakdown[day] = {'cost': 0.0, 'tokens': 0}
                            daily_breakdown[day]['cost']   += cost
                            daily_breakdown[day]['tokens'] += tok_in + tok_out
                        print(f"[activity] daily_breakdown has {len(daily_breakdown)} days, model_cost has {len(model_cost)} models", file=sys.stderr)
                        top3 = sorted(model_cost.items(), key=lambda x: x[1], reverse=True)[:3]
                        top3_latest = latest_date
                    else:
                        print(f"[activity] API returned status {rg.status_code}: {rg.text[:200]}", file=sys.stderr)
                    break
                except Exception:
                    if attempt < 2:
                        time.sleep(2)

        return {
            'ok':                     True,
            'limit':                  d.get('limit'),
            'limit_rem':              d.get('limit_remaining'),
            'balance':                balance,
            'label':                  d.get('label', ''),
            'top3':                   top3,
            'top3_latest_date':       top3_latest,
            'daily_breakdown':        daily_breakdown,
            'all_daily':              all_daily,             # Sum of usage_daily for all keys, real-time daily spend
            'all_monthly':            all_monthly,           # Sum of usage_monthly for all keys
            'global_total_usage':     global_total_usage,    # Account historical total spend from credits API
        }

    # ── UI update ─────────────────────────────────────────────────────────────

    def _update_ui(self, data):
        now = self._now().strftime('%H:%M:%S')
        self._last_data = data

        if data.get('error') == 'no_key':
            self._dot.config(fg=YELLOW); self._status.config(text='No Key Set', fg=YELLOW)
            self._island_logo.config(fg=YELLOW)
            self._island_bal_lbl.config(text='No Key Set', fg=YELLOW)
            self._island_sep.pack_forget()
            self._island_daily_lbl.pack_forget()
            return
        if data.get('error') == '401':
            self._dot.config(fg=RED);    self._status.config(text='Invalid Key', fg=RED)
            self._island_logo.config(fg=RED)
            self._island_bal_lbl.config(text='Invalid Key', fg=RED)
            self._island_sep.pack_forget()
            self._island_daily_lbl.pack_forget()
            self._time_lbl.config(text=f'Updated: {now}'); return
        if data.get('error'):
            self._dot.config(fg=RED);    self._status.config(text='Network Error', fg=RED)
            self._island_logo.config(fg=RED)
            self._island_bal_lbl.config(text='Network Error', fg=RED)
            self._island_sep.pack_forget()
            self._island_daily_lbl.pack_forget()
            self._time_lbl.config(text=f'Updated: {now}'); return

        self._daily_breakdown = data.get('daily_breakdown', {})
        self._dot.config(fg=GREEN)
        self._status.config(text='Connected', fg=GREEN)
        self._island_logo.config(fg=GREEN)

        # Restore separator and daily spend display
        self._island_sep.pack(side='left', padx=3)
        self._island_daily_lbl.pack(side='left')

        # Daily spend: sum of usage_daily for all keys (OpenRouter official real-time, UTC 0 reset)
        daily = data.get('all_daily', 0.0)

        # Monthly spend: use full account breakdown if activity data available, otherwise sum of usage_monthly for all keys
        if self._daily_breakdown:
            monthly = sum(v['cost'] for v in self._daily_breakdown.values())
        else:
            monthly = data.get('all_monthly', 0.0)

        # daily — always red
        self._vals['daily'].config(
            text=self._fmt(daily),
            fg=RED if daily > 0 else GRAY)

        # balance
        bal = data.get('balance')
        if bal is not None:
            bal_color = RED if bal < 1 else YELLOW if bal < 5 else GREEN
            bal_text = self._fmt2(bal) + (' !' if bal < 1 else '')
            self._vals['balance'].config(text=bal_text, fg=bal_color)
            bal_str = self._fmt2(bal)
        else:
            self._vals['balance'].config(text='——', fg=GRAY)
            bal_color = GRAY
            bal_str = '——'

        # Dynamic Island display: first account balance info, then daily spend. Keep respective colors, smaller font, less spacing
        self._island_bal_lbl.config(text=f'Balance:{bal_str}', fg=bal_color)
        self._island_daily_lbl.config(text=f'Today:{self._fmt(daily)}', fg=RED if daily > 0 else GRAY)

        # monthly
        self._vals['monthly'].config(text=self._fmt(monthly), fg=WHITE)
        limit     = data.get('limit')
        limit_rem = data.get('limit_rem')
        if limit and limit > 0 and limit_rem is not None:
            used = limit - limit_rem
            pct  = used / limit * 100
            pct_color = RED if pct >= 90 else YELLOW if pct >= 70 else CYAN
            self._monthly_pct.config(
                text=f'{pct:.1f}%  Limit {self._fmt2(limit)}', fg=pct_color)
            self._monthly_bar.config(bg=pct_color)
            self._monthly_bar.place(relwidth=min(pct / 100, 1.0))
        else:
            self._monthly_pct.config(text='No Quota Limit', fg=GRAY)
            self._monthly_bar.place(relwidth=0)

        # Total spend: use credits API's total_usage (this key's historical total spend)
        total = data.get('global_total_usage') or data.get('usage', 0)
        self._vals['total'].config(
            text=self._fmt(total),
            fg=RED if total > 20 else YELLOW if total > 5 else WHITE)

        top3 = data.get('top3', [])
        latest_date = data.get('top3_latest_date', '')
        title = f'Monthly TOP 3 ({latest_date})' if latest_date else 'Monthly TOP 3 Models'
        self._top3_title.config(text=title)
        no_mgmt = not self.cfg.get('mgmt_key', '').strip()
        for i, (name_lbl, cost_lbl) in enumerate(self._top3_lbls):
            if i == 0 and no_mgmt:
                name_lbl.config(text='Enter Management Key in Settings', fg=GRAY)
                cost_lbl.config(text='', fg=GRAY)
            elif i < len(top3):
                model, cost = top3[i]
                short = model.split('/')[-1].removeprefix('claude-')[:28]
                cost_str = self._fmt(cost)
                name_lbl.config(text=short, fg=WHITE)
                cost_lbl.config(text=cost_str, fg=CYAN)
            else:
                name_lbl.config(text='——' if not no_mgmt else '', fg=GRAY)
                cost_lbl.config(text='', fg=GRAY)

        self._time_lbl.config(text=f'↻ {now}   Right-click for more options')

    # ── Refresh ───────────────────────────────────────────────────────────────

    def _trigger_refresh(self):
        if hasattr(self, '_job'):
            self.root.after_cancel(self._job)
        self._dot.config(fg=YELLOW)
        self._status.config(text='Refreshing...')
        if hasattr(self, '_island_logo'):
            self._island_logo.config(fg=YELLOW)
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        data = self._fetch()
        self.root.after(0, lambda: self._on_fetch_done(data))

    def _on_fetch_done(self, data):
        self._update_ui(data)
        ms = max(10, self.cfg.get('refresh_sec', 60)) * 1000
        self._job = self.root.after(ms, self._trigger_refresh)

    def _schedule_refresh(self):
        self._trigger_refresh()

    def _quit(self):
        if hasattr(self, '_job'):
            self.root.after_cancel(self._job)
        self.root.destroy()


if __name__ == '__main__':
    Dashboard()

#!/usr/bin/env python3
# HUVVY GUARD v1.7 - Production Ready
# System Health + Network Monitoring Dashboard
# Built by Viorel | HUVVY Empire
#
# INSTALLATION: pip install psutil

import sys
import os
import time
import threading
import platform
import socket
import json
import getpass
import logging
from datetime import datetime
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple

# ============================================================================
# FIX CONSOLE ENCODING FOR WINDOWS
# ============================================================================

# Force stdout to use UTF-8 on Windows to avoid Unicode errors
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        # Python < 3.7 fallback
        try:
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        except:
            pass

# ============================================================================
# LOGGING SETUP
# ============================================================================

LOG_FILE = os.path.join(os.path.expanduser("~"), ".huvvy_guard", "huvvy_guard.log")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logger = logging.getLogger("HUVVY_GUARD")
logger.setLevel(logging.INFO)

# File handler with UTF-8 encoding
file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_format)
logger.addHandler(file_handler)

# Console handler - log only warnings and errors
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.WARNING)
console_format = logging.Formatter('%(levelname)s: %(message)s')
console_handler.setFormatter(console_format)
logger.addHandler(console_handler)

# Plain ASCII log file for maximum compatibility
PLAIN_LOG_FILE = os.path.join(os.path.expanduser("~"), ".huvvy_guard", "huvvy_guard_plain.log")
plain_handler = logging.FileHandler(PLAIN_LOG_FILE, encoding='ascii', errors='ignore')
plain_handler.setLevel(logging.INFO)
plain_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(plain_handler)

# ============================================================================
# CHECK DEPENDENCIES
# ============================================================================

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    logger.error("psutil is not installed!")
    print("\n" + "="*60)
    print("  ERROR: psutil is not installed!")
    print("="*60)
    print("\n  HUVVY GUARD requires the 'psutil' library.")
    print("\n  To install it, run:")
    print("\n    pip install psutil")
    print("\n" + "="*60 + "\n")
    sys.exit(1)

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
except ImportError:
    logger.error("python3-tk is not installed!")
    print("\n" + "="*60)
    print("  ERROR: python3-tk is not installed!")
    print("="*60)
    print("\n  On Ubuntu/Debian: sudo apt-get install python3-tk")
    print("\n  On Fedora: sudo dnf install python3-tkinter")
    print("\n  On macOS: brew install python-tk")
    print("="*60 + "\n")
    sys.exit(1)

logger.info("HUVVY GUARD v1.7 starting...")
logger.info(f"System: {platform.system()} {platform.release()}")

# ============================================================================
# THEME
# ============================================================================

THEME = {
    'bg': '#0a0a0f',
    'sidebar_bg': '#0d0818',
    'card_bg': '#120820',
    'card_border': '#2a1a4a',
    'text': '#e8dfff',
    'text_secondary': '#a080c0',
    'text_muted': '#6a4a8a',
    'purple_light': '#d4a0ff',
    'purple': '#9b59b6',
    'purple_dark': '#6c3483',
    'purple_glow': '#bf7aff',
    'green': '#7ddf9a',
    'red': '#ff6b8a',
    'blue': '#7db8ff',
    'orange': '#ffb366',
    'pink': '#ff7eb3',
    'yellow': '#ffd93d',
    'alert_bg': '#2a0a0a'
}

# ============================================================================
# MODELS
# ============================================================================

@dataclass
class SystemSnapshot:
    timestamp: float
    cpu_percent: float
    cpu_freq: float
    memory_percent: float
    memory_used: int
    memory_total: int
    swap_used: int
    swap_total: int
    disk_percent: float
    disk_used: int
    disk_total: int
    connections: int
    upload_speed: float
    download_speed: float
    processes: List[Dict]
    boot_time: float
    battery_percent: Optional[float] = None
    battery_charging: Optional[bool] = None
    cpu_model: str = ""
    gpu_model: str = ""
    hostname: str = ""
    ip_address: str = ""
    username: str = ""

# ============================================================================
# SYSTEM INFORMATION
# ============================================================================

def get_system_info() -> Tuple[str, str, str, str, str]:
    """Get static system information - cross-platform"""
    
    # CPU Model - using multiple methods for compatibility
    cpu_model = "Unknown"
    try:
        # Try platform.processor() first (works on many systems)
        cpu_model = platform.processor()
        if not cpu_model or cpu_model == "":
            # Fallback to WMIC on Windows
            if platform.system() == 'Windows':
                import subprocess
                # Try PowerShell first (more future-proof)
                try:
                    result = subprocess.run(
                        ['powershell', '-Command', 'Get-CimInstance -ClassName Win32_Processor | Select-Object -ExpandProperty Name'],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.stdout.strip():
                        cpu_model = result.stdout.strip()
                except:
                    pass
                
                # Fallback to WMIC if PowerShell failed
                if not cpu_model or cpu_model == "":
                    try:
                        result = subprocess.run(
                            ['wmic', 'cpu', 'get', 'name'],
                            capture_output=True, text=True, timeout=5
                        )
                        lines = result.stdout.strip().split('\n')
                        if len(lines) > 1:
                            cpu_model = lines[1].strip()
                    except:
                        pass
            
            elif platform.system() == 'Linux':
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if line.startswith('model name'):
                            cpu_model = line.split(':', 1)[1].strip()
                            break
            
            elif platform.system() == 'Darwin':
                import subprocess
                result = subprocess.run(
                    ['sysctl', '-n', 'machdep.cpu.brand_string'],
                    capture_output=True, text=True, timeout=5
                )
                if result.stdout.strip():
                    cpu_model = result.stdout.strip()
    except Exception as e:
        logger.debug(f"CPU detection failed: {e}")
    
    # GPU Model - cross-platform
    gpu_model = ""
    try:
        if platform.system() == 'Windows':
            import subprocess
            # Try PowerShell first
            try:
                result = subprocess.run(
                    ['powershell', '-Command', 'Get-CimInstance -ClassName Win32_VideoController | Where-Object {$_.Name -ne "Microsoft Remote Display Adapter"} | Select-Object -First 1 -ExpandProperty Name'],
                    capture_output=True, text=True, timeout=5
                )
                if result.stdout.strip():
                    gpu_model = result.stdout.strip()
            except:
                pass
            
            # Fallback to WMIC
            if not gpu_model:
                try:
                    result = subprocess.run(
                        ['wmic', 'path', 'win32_videocontroller', 'get', 'name'],
                        capture_output=True, text=True, timeout=5
                    )
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        gpu_model = lines[1].strip()
                except:
                    pass
        
        elif platform.system() == 'Linux':
            result = subprocess.run(
                ['lspci', '|', 'grep', '-i', 'vga'],
                shell=True, capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                gpu_model = result.stdout.strip().split(':', 1)[-1].strip()
        
        elif platform.system() == 'Darwin':
            result = subprocess.run(
                ['system_profiler', 'SPDisplaysDataType', '|', 'grep', 'Chipset'],
                shell=True, capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                gpu_model = result.stdout.strip().split(':', 1)[-1].strip()
    except Exception as e:
        logger.debug(f"GPU detection failed: {e}")
    
    hostname = platform.node()
    ip_address = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_address = s.getsockname()[0]
        s.close()
    except Exception as e:
        logger.debug(f"IP detection failed: {e}")
    
    try:
        username = getpass.getuser()
    except:
        username = os.environ.get('USER', os.environ.get('USERNAME', 'unknown'))
    
    return cpu_model, gpu_model, hostname, ip_address, username

# ============================================================================
# MONITOR
# ============================================================================

class SystemMonitor:
    """Collects system data in background thread with proper timing"""
    
    def __init__(self):
        self._snapshot: Optional[SystemSnapshot] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_recv = 0
        self._last_sent = 0
        self._last_update_time = 0
        self._update_interval = 2.0
        self._alerts = deque(maxlen=50)
        
        self.cpu_model, self.gpu_model, self.hostname, self.ip_address, self.username = get_system_info()
        logger.info(f"System info: CPU={self.cpu_model[:50] if self.cpu_model else 'Unknown'}")
        
        psutil.cpu_percent(interval=None)
        
    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._collect_loop, daemon=True)
        self._thread.start()
        logger.info("System monitor started")
        
    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        logger.info("System monitor stopped")
    
    def get_snapshot(self) -> Optional[SystemSnapshot]:
        return self._snapshot
    
    def get_alerts(self):
        return list(self._alerts)
    
    def _collect_loop(self):
        try:
            net = psutil.net_io_counters()
            self._last_recv = net.bytes_recv
            self._last_sent = net.bytes_sent
            self._last_update_time = time.time()
        except Exception as e:
            logger.error(f"Network init failed: {e}")
            self._last_recv = 0
            self._last_sent = 0
            self._last_update_time = time.time()
        
        while self._running:
            try:
                self._snapshot = self._collect()
                self._check_alerts(self._snapshot)
            except Exception as e:
                logger.error(f"Collection failed: {e}")
            time.sleep(self._update_interval)
    
    def _collect(self) -> SystemSnapshot:
        try:
            current_time = time.time()
            interval = current_time - self._last_update_time
            if interval < 0.1:
                interval = 0.1
            
            cpu = psutil.cpu_percent(interval=None)
            freq_obj = psutil.cpu_freq()
            cpu_freq = freq_obj.current if freq_obj else 0
            
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            disk_path = '/' if os.name != 'nt' else os.environ.get('SystemDrive', 'C:') + '\\'
            disk = psutil.disk_usage(disk_path)
            
            net = psutil.net_io_counters()
            recv_speed = (net.bytes_recv - self._last_recv) / interval / 1024
            sent_speed = (net.bytes_sent - self._last_sent) / interval / 1024
            self._last_recv = net.bytes_recv
            self._last_sent = net.bytes_sent
            self._last_update_time = current_time
            
            try:
                connections = len(psutil.net_connections())
            except (psutil.AccessDenied, PermissionError):
                connections = 0
            except Exception as e:
                connections = 0
            
            battery = None
            charging = None
            try:
                if hasattr(psutil, 'sensors_battery') and psutil.sensors_battery():
                    bat = psutil.sensors_battery()
                    battery = bat.percent if bat else None
                    charging = bat.power_plugged if bat else None
            except Exception as e:
                pass
            
            processes = []
            try:
                for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                    try:
                        info = p.info
                        processes.append({
                            'pid': info.get('pid', 0),
                            'name': info.get('name', ''),
                            'cpu': info.get('cpu_percent', 0) or 0,
                            'memory': info.get('memory_percent', 0) or 0
                        })
                    except:
                        pass
                processes.sort(key=lambda x: x['cpu'], reverse=True)
                processes = processes[:15]
            except Exception as e:
                pass
            
            return SystemSnapshot(
                timestamp=current_time,
                cpu_percent=cpu,
                cpu_freq=cpu_freq,
                memory_percent=mem.percent,
                memory_used=mem.used,
                memory_total=mem.total,
                swap_used=swap.used,
                swap_total=swap.total,
                disk_percent=disk.percent,
                disk_used=disk.used,
                disk_total=disk.total,
                connections=connections,
                upload_speed=sent_speed,
                download_speed=recv_speed,
                processes=processes,
                boot_time=psutil.boot_time(),
                battery_percent=battery,
                battery_charging=charging,
                cpu_model=self.cpu_model,
                gpu_model=self.gpu_model,
                hostname=self.hostname,
                ip_address=self.ip_address,
                username=self.username
            )
        except Exception as e:
            logger.error(f"Collection error: {e}")
            raise
    
    def _check_alerts(self, snap: SystemSnapshot):
        if snap.cpu_percent > 90:
            self._alerts.append(f"CPU > 90%: {snap.cpu_percent:.0f}%")
        if snap.memory_percent > 90:
            self._alerts.append(f"RAM > 90%: {snap.memory_percent:.0f}%")
        if snap.disk_percent > 95:
            self._alerts.append(f"Disk > 95%: {snap.disk_percent:.0f}%")
        if snap.battery_percent is not None and snap.battery_percent < 15 and not snap.battery_charging:
            self._alerts.append(f"Battery < 15%: {snap.battery_percent:.0f}%")

# ============================================================================
# CIRCULAR GAUGE
# ============================================================================

class CircularGauge(tk.Canvas):
    def __init__(self, parent, size=120, color=THEME['purple_glow'], bg_color=THEME['card_bg']):
        super().__init__(parent, width=size, height=size, bg=bg_color, highlightthickness=0)
        self.size = size
        self.color = color
        self.bg_color = bg_color
        self._current_value = 0
        self._target_value = 0
        self.radius = size // 2 - 15
        self.center = size // 2
        self._animating = False
        
        self._draw_background()
        self._draw_track()
        
    def _draw_background(self):
        self.create_oval(
            self.center - self.radius, self.center - self.radius,
            self.center + self.radius, self.center + self.radius,
            outline=THEME['card_border'], width=2, fill=self.bg_color
        )
    
    def _draw_track(self):
        self.create_arc(
            self.center - self.radius, self.center - self.radius,
            self.center + self.radius, self.center + self.radius,
            start=90, extent=-360,
            outline=THEME['text_muted'], width=6, style='arc'
        )
    
    def set_value(self, value, text=None):
        self._target_value = min(100, max(0, value))
        if not self._animating:
            self._start_animation()
    
    def _start_animation(self):
        if abs(self._current_value - self._target_value) < 0.5:
            self._current_value = self._target_value
            self._draw_gauge()
            self._animating = False
            return
        
        self._animating = True
        diff = self._target_value - self._current_value
        step = max(1, abs(diff) / 8)
        if abs(diff) < step:
            self._current_value = self._target_value
        else:
            self._current_value += step if diff > 0 else -step
        
        self._draw_gauge()
        self.after(30, self._start_animation)
    
    def _draw_gauge(self):
        self.delete("gauge")
        self.delete("label")
        
        angle = -360 * (self._current_value / 100)
        self.create_arc(
            self.center - self.radius, self.center - self.radius,
            self.center + self.radius, self.center + self.radius,
            start=90, extent=angle,
            outline=self.color, width=8, style='arc', tags=("gauge",)
        )
        
        self.create_text(
            self.center, self.center - 10,
            text=f"{int(self._current_value)}%",
            fill=THEME['text'], font=("Segoe UI", 18, "bold"),
            tags=("label",)
        )

# ============================================================================
# ABOUT PAGE
# ============================================================================

class AboutPage:
    @staticmethod
    def create(parent):
        frame = tk.Frame(parent, bg=THEME['bg'])
        container = tk.Frame(frame, bg=THEME['bg'])
        container.pack(expand=True)
        
        tk.Label(
            container,
            text="HUVVY Empire",
            font=("Segoe UI", 26, "bold"),
            fg=THEME['purple_glow'],
            bg=THEME['bg']
        ).pack(pady=(20, 0))
        
        tk.Label(
            container,
            text="Independent Software Development Brand",
            font=("Segoe UI", 12),
            fg=THEME['text_secondary'],
            bg=THEME['bg']
        ).pack()
        
        tk.Label(
            container,
            text="Founded by Viorel",
            font=("Segoe UI", 11),
            fg=THEME['text_muted'],
            bg=THEME['bg']
        ).pack(pady=(0, 15))
        
        sep1 = tk.Frame(container, bg=THEME['card_border'], height=1, width=500)
        sep1.pack(pady=5)
        
        desc = """HUVVY Empire is an independent software development brand founded by Viorel. 
Its mission is to create modern, reliable, and visually appealing applications 
that combine performance, simplicity, and creativity."""
        
        tk.Label(
            container,
            text=desc,
            font=("Segoe UI", 10),
            fg=THEME['text'],
            bg=THEME['bg'],
            justify=tk.CENTER
        ).pack(pady=12)
        
        focus_frame = tk.Frame(container, bg=THEME['bg'])
        focus_frame.pack(pady=5)
        
        focus_items = [
            "Desktop Applications",
            "System Utilities",
            "Monitoring & Diagnostics",
            "Security Tools",
            "Learning Through Innovation"
        ]
        
        for i, item in enumerate(focus_items):
            tk.Label(
                focus_frame,
                text=item,
                font=("Segoe UI", 10),
                fg=THEME['text_secondary'],
                bg=THEME['bg']
            ).grid(row=0, column=i, padx=15)
        
        values_label = tk.Label(
            container,
            text="Core Values",
            font=("Segoe UI", 12, "bold"),
            fg=THEME['purple_glow'],
            bg=THEME['bg']
        )
        values_label.pack(pady=(15, 5))
        
        values_frame = tk.Frame(container, bg=THEME['bg'])
        values_frame.pack(pady=5)
        
        values = ["Performance", "Reliability", "Clean Design", "Innovation", "Continuous Learning"]
        for i, v in enumerate(values):
            tk.Label(
                values_frame,
                text=f" {v}",
                font=("Segoe UI", 10),
                fg=THEME['text_secondary'],
                bg=THEME['bg']
            ).grid(row=0, column=i, padx=12)
        
        tk.Label(
            container,
            text="Vision",
            font=("Segoe UI", 12, "bold"),
            fg=THEME['purple_glow'],
            bg=THEME['bg']
        ).pack(pady=(15, 2))
        
        tk.Label(
            container,
            text='"Building software that is simple, powerful, and accessible to everyone."',
            font=("Segoe UI", 11, "italic"),
            fg=THEME['text'],
            bg=THEME['bg']
        ).pack(pady=5)
        
        sep2 = tk.Frame(container, bg=THEME['card_border'], height=1, width=500)
        sep2.pack(pady=15)
        
        tk.Label(
            container,
            text="HUVVY GUARD",
            font=("Segoe UI", 22, "bold"),
            fg=THEME['purple_glow'],
            bg=THEME['bg']
        ).pack()
        
        tk.Label(
            container,
            text="Flagship Application",
            font=("Segoe UI", 11),
            fg=THEME['text_secondary'],
            bg=THEME['bg']
        ).pack(pady=(0, 10))
        
        guard_desc = """HUVVY GUARD provides real-time monitoring of your computer by displaying:
CPU usage • Memory usage • Disk health • Network traffic
Active connections • Running processes • Live performance graphs • System activity logs

Designed with a clean purple-themed interface, HUVVY GUARD helps users understand 
their computer's performance while remaining lightweight and easy to use."""
        
        tk.Label(
            container,
            text=guard_desc,
            font=("Segoe UI", 10),
            fg=THEME['text'],
            bg=THEME['bg'],
            justify=tk.CENTER
        ).pack(pady=5)
        
        sep3 = tk.Frame(container, bg=THEME['card_border'], height=1, width=500)
        sep3.pack(pady=15)
        
        tk.Label(
            container,
            text="Future of HUVVY Empire",
            font=("Segoe UI", 14, "bold"),
            fg=THEME['purple_glow'],
            bg=THEME['bg']
        ).pack()
        
        future_frame = tk.Frame(container, bg=THEME['bg'])
        future_frame.pack(pady=8)
        
        future_projects = [
            "HUVVY GUARD",
            "HUVVY Terminal",
            "HUVVY Shield (Security Suite)",
            "HUVVY Files (File Manager)",
            "HUVVY Monitor Pro",
            "More Open-Source Utilities"
        ]
        
        for i, project in enumerate(future_projects):
            tk.Label(
                future_frame,
                text=project,
                font=("Segoe UI", 10),
                fg=THEME['text_secondary'],
                bg=THEME['bg']
            ).grid(row=i//3, column=i%3, padx=20, pady=3, sticky=tk.W)
        
        sep4 = tk.Frame(container, bg=THEME['card_border'], height=1, width=500)
        sep4.pack(pady=15)
        
        tk.Label(
            container,
            text="Privacy Notice",
            font=("Segoe UI", 12, "bold"),
            fg=THEME['purple_glow'],
            bg=THEME['bg']
        ).pack()
        
        privacy_text = """HUVVY GUARD collects system performance data locally on your computer.
No data is ever sent over the internet or shared with any third party.
All monitoring is done entirely on your local machine.

Logs are stored locally at: ~/.huvvy_guard/"""
        
        tk.Label(
            container,
            text=privacy_text,
            font=("Segoe UI", 9),
            fg=THEME['text_secondary'],
            bg=THEME['bg'],
            justify=tk.CENTER
        ).pack(pady=5)
        
        sep5 = tk.Frame(container, bg=THEME['card_border'], height=1, width=500)
        sep5.pack(pady=10)
        
        tk.Label(
            container,
            text="Motto",
            font=("Segoe UI", 12, "bold"),
            fg=THEME['purple_glow'],
            bg=THEME['bg']
        ).pack()
        
        tk.Label(
            container,
            text='"Build  Learn  Innovate  Protect."',
            font=("Segoe UI", 13, "bold"),
            fg=THEME['text'],
            bg=THEME['bg']
        ).pack(pady=5)
        
        footer = f"""
═══════════════════════════════════════════════════════════════
HUVVY GUARD v1.7  •  Developed by Viorel  •  2026 HUVVY Empire
"Build  Learn  Innovate  Protect."
═══════════════════════════════════════════════════════════════"""
        
        tk.Label(
            container,
            text=footer,
            font=("Segoe UI", 9),
            fg=THEME['text_muted'],
            bg=THEME['bg'],
            justify=tk.CENTER
        ).pack(pady=(20, 15))
        
        return frame

# ============================================================================
# SIDEBAR
# ============================================================================

class Sidebar:
    PAGES = [
        (' Dashboard', 'dashboard'),
        (' Performance', 'performance'),
        (' Network', 'network'),
        (' Storage', 'storage'),
        (' Processes', 'processes'),
        (' Logs', 'logs'),
        (' About', 'about')
    ]
    
    def __init__(self, parent, on_page_change):
        self.frame = tk.Frame(parent, bg=THEME['sidebar_bg'], width=200)
        self.frame.pack(side=tk.LEFT, fill=tk.Y)
        self.frame.pack_propagate(False)
        
        self.on_page_change = on_page_change
        self.current_page = 'dashboard'
        self.buttons = []
        
        logo_frame = tk.Frame(self.frame, bg=THEME['sidebar_bg'])
        logo_frame.pack(pady=(15, 5))
        
        tk.Label(
            logo_frame,
            text="HUVVY GUARD",
            font=("Segoe UI", 12, "bold"),
            fg=THEME['purple_glow'],
            bg=THEME['sidebar_bg']
        ).pack()
        
        tk.Label(
            logo_frame,
            text="v1.7",
            font=("Segoe UI", 8),
            fg=THEME['text_muted'],
            bg=THEME['sidebar_bg']
        ).pack(pady=(0, 10))
        
        sep = tk.Frame(self.frame, bg=THEME['card_border'], height=1)
        sep.pack(fill=tk.X, padx=15, pady=8)
        
        for label, page_id in self.PAGES:
            btn = self._create_button(label, page_id)
            btn.pack(fill=tk.X, padx=10, pady=2)
            self.buttons.append((btn, page_id))
        
        tk.Frame(self.frame, bg=THEME['sidebar_bg']).pack(fill=tk.BOTH, expand=True)
        
        slogan_frame = tk.Frame(self.frame, bg=THEME['sidebar_bg'])
        slogan_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(
            slogan_frame,
            text="Build  Learn  Innovate  Protect",
            font=("Segoe UI", 8),
            fg=THEME['text_muted'],
            bg=THEME['sidebar_bg']
        ).pack()
        
        status_frame = tk.Frame(self.frame, bg=THEME['sidebar_bg'])
        status_frame.pack(fill=tk.X, padx=10, pady=10)
        
        dot = tk.Frame(status_frame, bg=THEME['green'], width=8, height=8)
        dot.pack(side=tk.LEFT, padx=(0, 8))
        dot.pack_propagate(False)
        
        tk.Label(
            status_frame,
            text="SYSTEM ONLINE",
            font=("Segoe UI", 8, "bold"),
            fg=THEME['green'],
            bg=THEME['sidebar_bg']
        ).pack(side=tk.LEFT)
        
        self.select_page('dashboard')
    
    def _create_button(self, label, page_id):
        btn = tk.Button(
            self.frame,
            text=label,
            command=lambda: self.select_page(page_id),
            font=("Segoe UI", 10),
            fg=THEME['text_secondary'],
            bg=THEME['sidebar_bg'],
            relief=tk.FLAT,
            anchor=tk.W,
            padx=12,
            pady=8,
            activebackground=THEME['purple_dark'],
            activeforeground=THEME['text'],
            cursor="hand2"
        )
        return btn
    
    def select_page(self, page_id):
        self.current_page = page_id
        
        for btn, pid in self.buttons:
            if pid == page_id:
                btn.config(
                    bg=THEME['purple_dark'],
                    fg=THEME['text']
                )
            else:
                btn.config(
                    bg=THEME['sidebar_bg'],
                    fg=THEME['text_secondary']
                )
        
        if self.on_page_change:
            self.on_page_change(page_id)

# ============================================================================
# MAIN APPLICATION
# ============================================================================

class HuvvyGuard:
    def __init__(self, root):
        self.root = root
        root.title("HUVVY GUARD v1.7")
        root.geometry("1300x800")
        root.minsize(1100, 700)
        root.configure(bg=THEME['bg'])
        
        self.snapshots = deque(maxlen=120)
        self.cpu_history = deque(maxlen=60)
        self.memory_history = deque(maxlen=60)
        self.download_history = deque(maxlen=60)
        self.upload_history = deque(maxlen=60)
        self._max_download_speed = 1.0
        self._max_upload_speed = 1.0
        
        self.monitor = SystemMonitor()
        self.logs = deque(maxlen=100)
        self._alert_count = 0
        
        self.pages = {}
        self.current_page = 'dashboard'
        self._process_items = {}
        
        # Track all processes for full list
        self._all_processes = []
        
        self._build_ui()
        self._start_monitor()
        self._start_ui_updater()
        
        self._add_log("HUVVY GUARD v1.7 started")
        self._add_log(f"Monitoring: {platform.system()} {platform.release()}")
        self._add_log("Built by Viorel | HUVVY Empire")
        self._add_log("Build  Learn  Innovate  Protect")
        self._add_log("All data stays local - no internet connection required")
    
    def _build_ui(self):
        main = tk.Frame(self.root, bg=THEME['bg'])
        main.pack(fill=tk.BOTH, expand=True)
        
        self.sidebar = Sidebar(main, self._on_page_change)
        
        self.content = tk.Frame(main, bg=THEME['bg'])
        self.content.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self._build_pages()
        self._show_page('dashboard')
    
    def _build_pages(self):
        self.pages['dashboard'] = self._build_dashboard()
        self.pages['performance'] = self._build_performance()
        self.pages['network'] = self._build_network()
        self.pages['storage'] = self._build_storage()
        self.pages['processes'] = self._build_processes()
        self.pages['logs'] = self._build_logs()
        self.pages['about'] = AboutPage.create(self.content)
    
    def _show_page(self, page_id):
        for pid, page in self.pages.items():
            page.pack_forget()
        
        if page_id in self.pages:
            self.pages[page_id].pack(fill=tk.BOTH, expand=True)
            self.current_page = page_id
    
    def _on_page_change(self, page_id):
        self._show_page(page_id)
    
    # ------------------------------------------------------------------------
    # DASHBOARD PAGE
    # ------------------------------------------------------------------------
    
    def _build_dashboard(self):
        frame = tk.Frame(self.content, bg=THEME['bg'])
        
        header = tk.Frame(frame, bg=THEME['bg'])
        header.pack(fill=tk.X, padx=20, pady=(15, 10))
        
        tk.Label(
            header,
            text="Dashboard",
            font=("Segoe UI", 18, "bold"),
            fg=THEME['text'],
            bg=THEME['bg']
        ).pack(side=tk.LEFT)
        
        self.alert_indicator = tk.Label(
            header,
            text="",
            font=("Segoe UI", 10),
            fg=THEME['red'],
            bg=THEME['bg']
        )
        self.alert_indicator.pack(side=tk.RIGHT, padx=10)
        
        gauges_frame = tk.Frame(frame, bg=THEME['bg'])
        gauges_frame.pack(fill=tk.X, padx=20, pady=10)
        
        cpu_frame = tk.Frame(gauges_frame, bg=THEME['card_bg'])
        cpu_frame.pack(side=tk.LEFT, padx=(0, 15), pady=5)
        
        self.cpu_gauge = CircularGauge(cpu_frame, size=140, color=THEME['purple_glow'])
        self.cpu_gauge.pack(padx=10, pady=(10, 5))
        tk.Label(cpu_frame, text="CPU Usage", font=("Segoe UI", 10), fg=THEME['text_secondary'], bg=THEME['card_bg']).pack(pady=(0, 10))
        
        mem_frame = tk.Frame(gauges_frame, bg=THEME['card_bg'])
        mem_frame.pack(side=tk.LEFT, padx=(0, 15), pady=5)
        
        self.mem_gauge = CircularGauge(mem_frame, size=140, color=THEME['blue'])
        self.mem_gauge.pack(padx=10, pady=(10, 5))
        tk.Label(mem_frame, text="Memory Usage", font=("Segoe UI", 10), fg=THEME['text_secondary'], bg=THEME['card_bg']).pack(pady=(0, 10))
        
        disk_frame = tk.Frame(gauges_frame, bg=THEME['card_bg'])
        disk_frame.pack(side=tk.LEFT, padx=(0, 15), pady=5)
        
        self.disk_gauge = CircularGauge(disk_frame, size=140, color=THEME['orange'])
        self.disk_gauge.pack(padx=10, pady=(10, 5))
        tk.Label(disk_frame, text="Disk Usage", font=("Segoe UI", 10), fg=THEME['text_secondary'], bg=THEME['card_bg']).pack(pady=(0, 10))
        
        net_frame = tk.Frame(gauges_frame, bg=THEME['card_bg'])
        net_frame.pack(side=tk.LEFT, padx=(0, 15), pady=5, fill=tk.BOTH, expand=True)
        
        tk.Label(net_frame, text="Network", font=("Segoe UI", 10), fg=THEME['text_secondary'], bg=THEME['card_bg']).pack(pady=(10, 5))
        
        down_frame = tk.Frame(net_frame, bg=THEME['card_bg'])
        down_frame.pack(fill=tk.X, padx=15, pady=2)
        tk.Label(down_frame, text="Download", font=("Segoe UI", 9), fg=THEME['blue'], bg=THEME['card_bg']).pack(side=tk.LEFT)
        
        self.dashboard_download = tk.Label(down_frame, text="0 KB/s", font=("Segoe UI", 12, "bold"), fg=THEME['blue'], bg=THEME['card_bg'])
        self.dashboard_download.pack(side=tk.RIGHT)
        
        up_frame = tk.Frame(net_frame, bg=THEME['card_bg'])
        up_frame.pack(fill=tk.X, padx=15, pady=2)
        tk.Label(up_frame, text="Upload", font=("Segoe UI", 9), fg=THEME['orange'], bg=THEME['card_bg']).pack(side=tk.LEFT)
        
        self.dashboard_upload = tk.Label(up_frame, text="0 KB/s", font=("Segoe UI", 12, "bold"), fg=THEME['orange'], bg=THEME['card_bg'])
        self.dashboard_upload.pack(side=tk.RIGHT)
        
        conn_frame = tk.Frame(net_frame, bg=THEME['card_bg'])
        conn_frame.pack(fill=tk.X, padx=15, pady=(2, 10))
        tk.Label(conn_frame, text="Connections", font=("Segoe UI", 9), fg=THEME['text_secondary'], bg=THEME['card_bg']).pack(side=tk.LEFT)
        
        self.dashboard_conn = tk.Label(conn_frame, text="0", font=("Segoe UI", 12, "bold"), fg=THEME['purple_glow'], bg=THEME['card_bg'])
        self.dashboard_conn.pack(side=tk.RIGHT)
        
        stats_frame = tk.Frame(frame, bg=THEME['bg'])
        stats_frame.pack(fill=tk.X, padx=20, pady=10)
        
        battery_frame = tk.Frame(stats_frame, bg=THEME['card_bg'])
        battery_frame.pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)
        tk.Label(battery_frame, text="Battery", font=("Segoe UI", 9), fg=THEME['text_secondary'], bg=THEME['card_bg']).pack(anchor=tk.W, padx=10, pady=(8, 2))
        self.battery_label = tk.Label(battery_frame, text="--%", font=("Segoe UI", 12, "bold"), fg=THEME['yellow'], bg=THEME['card_bg'])
        self.battery_label.pack(anchor=tk.W, padx=10, pady=(0, 8))
        
        uptime_frame = tk.Frame(stats_frame, bg=THEME['card_bg'])
        uptime_frame.pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)
        tk.Label(uptime_frame, text="Uptime", font=("Segoe UI", 9), fg=THEME['text_secondary'], bg=THEME['card_bg']).pack(anchor=tk.W, padx=10, pady=(8, 2))
        self.uptime_label = tk.Label(uptime_frame, text="--h --m", font=("Segoe UI", 12, "bold"), fg=THEME['text'], bg=THEME['card_bg'])
        self.uptime_label.pack(anchor=tk.W, padx=10, pady=(0, 8))
        
        proc_frame = tk.Frame(stats_frame, bg=THEME['card_bg'])
        proc_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(proc_frame, text="Processes", font=("Segoe UI", 9), fg=THEME['text_secondary'], bg=THEME['card_bg']).pack(anchor=tk.W, padx=10, pady=(8, 2))
        self.proc_count_label = tk.Label(proc_frame, text="0", font=("Segoe UI", 12, "bold"), fg=THEME['purple_glow'], bg=THEME['card_bg'])
        self.proc_count_label.pack(anchor=tk.W, padx=10, pady=(0, 8))
        
        return frame
    
    # ------------------------------------------------------------------------
    # PERFORMANCE PAGE
    # ------------------------------------------------------------------------
    
    def _build_performance(self):
        frame = tk.Frame(self.content, bg=THEME['bg'])
        
        header = tk.Frame(frame, bg=THEME['bg'])
        header.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        tk.Label(header, text="Performance History", font=("Segoe UI", 16, "bold"), fg=THEME['text'], bg=THEME['bg']).pack(side=tk.LEFT)
        
        export_btn = tk.Button(header, text="Export Report", command=self._export_report,
                               font=("Segoe UI", 9), fg=THEME['text_secondary'], bg=THEME['card_bg'],
                               relief=tk.FLAT, padx=10, pady=4, cursor="hand2",
                               activebackground=THEME['purple_dark'], activeforeground=THEME['text'])
        export_btn.pack(side=tk.RIGHT)
        
        self.perf_canvas = tk.Canvas(frame, bg=THEME['card_bg'], height=300, highlightthickness=0)
        self.perf_canvas.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        legend_frame = tk.Frame(frame, bg=THEME['bg'])
        legend_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        for color, label in [
            (THEME['purple_glow'], "CPU"),
            (THEME['blue'], "Memory"),
            (THEME['orange'], "Download"),
            (THEME['pink'], "Upload")
        ]:
            dot = tk.Frame(legend_frame, bg=color, width=12, height=12)
            dot.pack(side=tk.LEFT, padx=(0, 4))
            dot.pack_propagate(False)
            lbl = tk.Label(legend_frame, text=label, fg=THEME['text_secondary'], bg=THEME['bg'], font=("Segoe UI", 9))
            lbl.pack(side=tk.LEFT, padx=(0, 20))
        
        self._perf_canvas = self.perf_canvas
        return frame
    
    def _export_report(self):
        snap = self.monitor.get_snapshot()
        if not snap:
            self._add_log("No data to export")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Export System Report"
        )
        
        if file_path:
            try:
                report = {
                    "timestamp": datetime.now().isoformat(),
                    "system": {
                        "hostname": snap.hostname,
                        "ip": snap.ip_address,
                        "username": snap.username,
                        "os": f"{platform.system()} {platform.release()}",
                        "os_version": platform.version(),
                        "machine": platform.machine(),
                        "processor": platform.processor(),
                        "cpu": snap.cpu_model,
                        "gpu": snap.gpu_model,
                        "ram_total_gb": round(snap.memory_total / (1024**3), 2)
                    },
                    "current": {
                        "cpu_percent": snap.cpu_percent,
                        "memory_percent": snap.memory_percent,
                        "disk_percent": snap.disk_percent,
                        "connections": snap.connections,
                        "battery_percent": snap.battery_percent,
                        "uptime_seconds": time.time() - snap.boot_time
                    },
                    "network": {
                        "download_kb_s": snap.download_speed,
                        "upload_kb_s": snap.upload_speed
                    },
                    "top_processes": snap.processes[:10],
                    "logs": list(self.logs)
                }
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(report, f, indent=2, default=str)
                
                self._add_log(f"Report exported to: {os.path.basename(file_path)}")
                logger.info(f"Report exported to {file_path}")
                
            except Exception as e:
                self._add_log(f"Export failed: {e}")
                logger.error(f"Export failed: {e}")
    
    # ------------------------------------------------------------------------
    # NETWORK PAGE
    # ------------------------------------------------------------------------
    
    def _build_network(self):
        frame = tk.Frame(self.content, bg=THEME['bg'])
        
        tk.Label(frame, text="Network Activity", font=("Segoe UI", 16, "bold"), fg=THEME['text'], bg=THEME['bg']).pack(anchor=tk.W, padx=20, pady=(20, 10))
        
        stats_frame = tk.Frame(frame, bg=THEME['bg'])
        stats_frame.pack(fill=tk.X, padx=20, pady=10)
        
        dl_card = tk.Frame(stats_frame, bg=THEME['card_bg'])
        dl_card.pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)
        tk.Label(dl_card, text="Download Speed", font=("Segoe UI", 10), fg=THEME['blue'], bg=THEME['card_bg']).pack(pady=(10, 5))
        self.net_download = tk.Label(dl_card, text="0 KB/s", font=("Segoe UI", 22, "bold"), fg=THEME['blue'], bg=THEME['card_bg'])
        self.net_download.pack(pady=(0, 10))
        
        ul_card = tk.Frame(stats_frame, bg=THEME['card_bg'])
        ul_card.pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)
        tk.Label(ul_card, text="Upload Speed", font=("Segoe UI", 10), fg=THEME['orange'], bg=THEME['card_bg']).pack(pady=(10, 5))
        self.net_upload = tk.Label(ul_card, text="0 KB/s", font=("Segoe UI", 22, "bold"), fg=THEME['orange'], bg=THEME['card_bg'])
        self.net_upload.pack(pady=(0, 10))
        
        conn_card = tk.Frame(stats_frame, bg=THEME['card_bg'])
        conn_card.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(conn_card, text="Active Connections", font=("Segoe UI", 10), fg=THEME['purple_glow'], bg=THEME['card_bg']).pack(pady=(10, 5))
        self.net_connections = tk.Label(conn_card, text="0", font=("Segoe UI", 22, "bold"), fg=THEME['purple_glow'], bg=THEME['card_bg'])
        self.net_connections.pack(pady=(0, 10))
        
        return frame
    
    # ------------------------------------------------------------------------
    # STORAGE PAGE
    # ------------------------------------------------------------------------
    
    def _build_storage(self):
        frame = tk.Frame(self.content, bg=THEME['bg'])
        
        tk.Label(frame, text="Storage", font=("Segoe UI", 16, "bold"), fg=THEME['text'], bg=THEME['bg']).pack(anchor=tk.W, padx=20, pady=(20, 10))
        
        disk_frame = tk.Frame(frame, bg=THEME['card_bg'])
        disk_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.storage_gauge = CircularGauge(disk_frame, size=180, color=THEME['orange'])
        self.storage_gauge.pack(pady=20)
        
        stats_frame = tk.Frame(disk_frame, bg=THEME['card_bg'])
        stats_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        tk.Label(stats_frame, text="Total", font=("Segoe UI", 9), fg=THEME['text_secondary'], bg=THEME['card_bg']).pack(side=tk.LEFT, padx=(0, 20))
        self.storage_total = tk.Label(stats_frame, text="0 GB", font=("Segoe UI", 10, "bold"), fg=THEME['text'], bg=THEME['card_bg'])
        self.storage_total.pack(side=tk.LEFT, padx=(0, 40))
        
        tk.Label(stats_frame, text="Used", font=("Segoe UI", 9), fg=THEME['text_secondary'], bg=THEME['card_bg']).pack(side=tk.LEFT, padx=(0, 20))
        self.storage_used = tk.Label(stats_frame, text="0 GB", font=("Segoe UI", 10, "bold"), fg=THEME['orange'], bg=THEME['card_bg'])
        self.storage_used.pack(side=tk.LEFT, padx=(0, 40))
        
        tk.Label(stats_frame, text="Free", font=("Segoe UI", 9), fg=THEME['text_secondary'], bg=THEME['card_bg']).pack(side=tk.LEFT, padx=(0, 20))
        self.storage_free = tk.Label(stats_frame, text="0 GB", font=("Segoe UI", 10, "bold"), fg=THEME['green'], bg=THEME['card_bg'])
        self.storage_free.pack(side=tk.LEFT)
        
        return frame
    
    # ------------------------------------------------------------------------
    # PROCESSES PAGE (FULL LIST WITH SCROLLING)
    # ------------------------------------------------------------------------
    
    def _build_processes(self):
        frame = tk.Frame(self.content, bg=THEME['bg'])
        
        header = tk.Frame(frame, bg=THEME['bg'])
        header.pack(fill=tk.X, padx=20, pady=(20, 10))
        tk.Label(header, text="Running Processes", font=("Segoe UI", 16, "bold"), fg=THEME['text'], bg=THEME['bg']).pack(side=tk.LEFT)
        tk.Label(header, text="Auto-refresh: 2s", font=("Segoe UI", 9), fg=THEME['text_muted'], bg=THEME['bg']).pack(side=tk.RIGHT)
        
        tree_frame = tk.Frame(frame, bg=THEME['card_bg'])
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.process_tree_full = ttk.Treeview(
            tree_frame,
            columns=("PID", "CPU", "Memory"),
            show="tree headings",
            yscrollcommand=scrollbar.set,
            height=20,
            style="Purple.Treeview"
        )
        self.process_tree_full.heading("#0", text="Process Name")
        self.process_tree_full.heading("PID", text="PID")
        self.process_tree_full.heading("CPU", text="CPU %")
        self.process_tree_full.heading("Memory", text="Memory %")
        self.process_tree_full.column("#0", width=250)
        self.process_tree_full.column("PID", width=80, anchor="center")
        self.process_tree_full.column("CPU", width=80, anchor="center")
        self.process_tree_full.column("Memory", width=80, anchor="center")
        
        style = ttk.Style()
        style.configure("Purple.Treeview", background=THEME['card_bg'], foreground=THEME['text'],
                       fieldbackground=THEME['card_bg'], borderwidth=0, font=("Segoe UI", 9))
        style.map("Purple.Treeview", background=[("selected", THEME['purple_dark'])],
                 foreground=[("selected", THEME['text'])])
        style.configure("Purple.Treeview.Heading", background=THEME['card_bg'],
                       foreground=THEME['text_secondary'], font=("Segoe UI", 9, "bold"), borderwidth=0)
        
        self.process_tree_full.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.process_tree_full.yview)
        
        # Store reference for full updates
        self._process_tree_full = self.process_tree_full
        
        return frame
    
    # ------------------------------------------------------------------------
    # LOGS PAGE
    # ------------------------------------------------------------------------
    
    def _build_logs(self):
        frame = tk.Frame(self.content, bg=THEME['bg'])
        
        header = tk.Frame(frame, bg=THEME['bg'])
        header.pack(fill=tk.X, padx=20, pady=(20, 10))
        tk.Label(header, text="Activity Logs", font=("Segoe UI", 16, "bold"), fg=THEME['text'], bg=THEME['bg']).pack(side=tk.LEFT)
        
        clear_btn = tk.Button(header, text="Clear Logs", command=self._clear_logs_page,
                              font=("Segoe UI", 9), fg=THEME['text_secondary'], bg=THEME['card_bg'],
                              relief=tk.FLAT, padx=10, pady=4, cursor="hand2",
                              activebackground=THEME['purple_dark'], activeforeground=THEME['text'])
        clear_btn.pack(side=tk.RIGHT)
        
        export_logs_btn = tk.Button(header, text="Export TXT", command=self._export_logs,
                                    font=("Segoe UI", 9), fg=THEME['text_secondary'], bg=THEME['card_bg'],
                                    relief=tk.FLAT, padx=10, pady=4, cursor="hand2",
                                    activebackground=THEME['purple_dark'], activeforeground=THEME['text'])
        export_logs_btn.pack(side=tk.RIGHT, padx=5)
        
        self.logs_text = tk.Text(frame, bg=THEME['card_bg'], fg=THEME['text_secondary'],
                                 font=("Consolas", 10), relief=tk.FLAT, wrap=tk.WORD, state=tk.DISABLED)
        self.logs_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        return frame
    
    def _export_logs(self):
        if not self.logs:
            self._add_log("No logs to export")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Export Logs"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"HUVVY GUARD Logs\n")
                    f.write(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("="*50 + "\n\n")
                    for log in self.logs:
                        f.write(log + "\n")
                
                self._add_log(f"Logs exported to: {os.path.basename(file_path)}")
                logger.info(f"Logs exported to {file_path}")
                
            except Exception as e:
                self._add_log(f"Export failed: {e}")
                logger.error(f"Log export failed: {e}")
    
    def _clear_logs_page(self):
        self.logs_text.config(state=tk.NORMAL)
        self.logs_text.delete(1.0, tk.END)
        self.logs_text.config(state=tk.DISABLED)
        self.logs.clear()
        self._add_log("Logs cleared")
    
    # ------------------------------------------------------------------------
    # UI UPDATES
    # ------------------------------------------------------------------------
    
    def _start_monitor(self):
        self.monitor.start()
    
    def _start_ui_updater(self):
        self._update_ui()
    
    def _update_ui(self):
        snapshot = self.monitor.get_snapshot()
        if snapshot:
            self._update_dashboard(snapshot)
            self._update_network(snapshot)
            self._update_storage(snapshot)
            self._update_processes(snapshot)
            self._update_processes_full(snapshot)
            self._update_performance(snapshot)
            self._update_alerts(snapshot)
        
        self.root.after(1000, self._update_ui)
    
    def _update_dashboard(self, snap: SystemSnapshot):
        self.cpu_gauge.set_value(snap.cpu_percent)
        self.mem_gauge.set_value(snap.memory_percent)
        self.disk_gauge.set_value(snap.disk_percent)
        
        if snap.download_speed > 1024:
            dl_text = f"{snap.download_speed/1024:.1f} MB/s"
        else:
            dl_text = f"{snap.download_speed:.0f} KB/s"
        
        if snap.upload_speed > 1024:
            ul_text = f"{snap.upload_speed/1024:.1f} MB/s"
        else:
            ul_text = f"{snap.upload_speed:.0f} KB/s"
        
        self.dashboard_download.config(text=dl_text)
        self.dashboard_upload.config(text=ul_text)
        self.dashboard_conn.config(text=str(snap.connections))
        
        # Battery - cleaner display without emojis
        if snap.battery_percent is not None:
            battery_text = f"{snap.battery_percent:.0f}%"
            if snap.battery_charging:
                battery_text += " (Charging)"
            self.battery_label.config(
                text=battery_text,
                fg=THEME['yellow'] if snap.battery_percent > 20 else THEME['red']
            )
        else:
            self.battery_label.config(text="N/A", fg=THEME['text_secondary'])
        
        uptime = time.time() - snap.boot_time
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        self.uptime_label.config(text=f"{hours}h {minutes}m")
        
        self.proc_count_label.config(text=str(len(snap.processes)))
        
        self.cpu_history.append(snap.cpu_percent)
        self.memory_history.append(snap.memory_percent)
        
        self._max_download_speed = max(self._max_download_speed, snap.download_speed / 1024 * 100)
        self._max_upload_speed = max(self._max_upload_speed, snap.upload_speed / 1024 * 100)
        
        dl_pct = min(100, (snap.download_speed / 1024 * 100) / self._max_download_speed * 100 if self._max_download_speed > 0 else 0)
        ul_pct = min(100, (snap.upload_speed / 1024 * 100) / self._max_upload_speed * 100 if self._max_upload_speed > 0 else 0)
        
        self.download_history.append(dl_pct)
        self.upload_history.append(ul_pct)
    
    def _update_network(self, snap: SystemSnapshot):
        if snap.download_speed > 1024:
            self.net_download.config(text=f"{snap.download_speed/1024:.1f} MB/s")
        else:
            self.net_download.config(text=f"{snap.download_speed:.0f} KB/s")
        
        if snap.upload_speed > 1024:
            self.net_upload.config(text=f"{snap.upload_speed/1024:.1f} MB/s")
        else:
            self.net_upload.config(text=f"{snap.upload_speed:.0f} KB/s")
        
        self.net_connections.config(text=str(snap.connections))
    
    def _update_storage(self, snap: SystemSnapshot):
        self.storage_gauge.set_value(snap.disk_percent)
        
        total_gb = snap.disk_total / (1024**3)
        used_gb = snap.disk_used / (1024**3)
        free_gb = (snap.disk_total - snap.disk_used) / (1024**3)
        
        self.storage_total.config(text=f"{total_gb:.1f} GB")
        self.storage_used.config(text=f"{used_gb:.1f} GB")
        self.storage_free.config(text=f"{free_gb:.1f} GB")
    
    def _update_processes(self, snap: SystemSnapshot):
        """Update dashboard process list (top 15)"""
        current_pids = set()
        
        for proc in snap.processes[:15]:
            pid = proc['pid']
            current_pids.add(pid)
            name = proc['name']
            cpu = f"{proc['cpu']:.1f}"
            mem = f"{proc['memory']:.1f}"
            
            if pid in self._process_items:
                item = self._process_items[pid]
                try:
                    self.process_tree_full.item(item, values=(pid, cpu, mem))
                except tk.TclError:
                    item = self.process_tree_full.insert("", "end", text=name, values=(pid, cpu, mem))
                    self._process_items[pid] = item
            else:
                item = self.process_tree_full.insert("", "end", text=name, values=(pid, cpu, mem))
                self._process_items[pid] = item
        
        for pid, item in list(self._process_items.items()):
            if pid not in current_pids:
                try:
                    self.process_tree_full.delete(item)
                except tk.TclError:
                    pass
                del self._process_items[pid]
    
    def _update_processes_full(self, snap: SystemSnapshot):
        """Update full process list on Processes page"""
        # Store all processes for the full view
        self._all_processes = snap.processes
        
        # If the full process tree exists, update it
        if hasattr(self, '_process_tree_full'):
            # Clear and rebuild (simpler for full list)
            for item in self._process_tree_full.get_children():
                self._process_tree_full.delete(item)
            
            for proc in snap.processes:
                self._process_tree_full.insert(
                    "", "end",
                    text=proc['name'],
                    values=(proc['pid'], f"{proc['cpu']:.1f}", f"{proc['memory']:.1f}")
                )
    
    def _update_performance(self, snap: SystemSnapshot):
        canvas = self._perf_canvas
        canvas.delete("all")
        
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        
        if w < 50 or h < 50:
            return
        
        padding = 20
        graph_h = h - padding * 2
        max_val = 100.0
        
        # Draw grid lines
        grid_color = THEME['card_border']
        for level in [0, 25, 50, 75, 100]:
            y = padding + graph_h - (level / max_val) * (graph_h - 5)
            canvas.create_line(padding, y, w - padding, y, fill=grid_color, dash=(4, 4), width=1)
            canvas.create_text(padding - 5, y, text=f"{level}%", fill=THEME['text_muted'], 
                              font=("Segoe UI", 7), anchor="e")
        
        # Draw datasets
        datasets = [
            (self.cpu_history, THEME['purple_glow']),
            (self.memory_history, THEME['blue']),
            (self.download_history, THEME['orange']),
            (self.upload_history, THEME['pink'])
        ]
        
        for data, color in datasets:
            if len(data) < 2:
                continue
            
            points = list(data)
            step = (w - padding * 2) / max(1, len(points) - 1)
            
            for i in range(len(points) - 1):
                x1 = padding + i * step
                y1 = padding + graph_h - (min(points[i], max_val) / max_val) * (graph_h - 5)
                x2 = padding + (i + 1) * step
                y2 = padding + graph_h - (min(points[i + 1], max_val) / max_val) * (graph_h - 5)
                
                if x1 < w and x2 < w:
                    canvas.create_line(x1, y1, x2, y2, fill=color, width=2)
            
            if points:
                last_x = padding + (len(points) - 1) * step
                last_y = padding + graph_h - (min(points[-1], max_val) / max_val) * (graph_h - 5)
                canvas.create_oval(last_x - 3, last_y - 3, last_x + 3, last_y + 3, fill=color, outline=color)
    
    def _update_alerts(self, snap: SystemSnapshot):
        alerts = self.monitor.get_alerts()
        
        if alerts and len(alerts) > self._alert_count:
            new_alerts = alerts[self._alert_count:]
            for alert in new_alerts:
                self._add_log(f"ALERT: {alert}")
            self._alert_count = len(alerts)
        
        if alerts:
            self.alert_indicator.config(text=f"{len(alerts)} alerts", fg=THEME['red'])
        else:
            self.alert_indicator.config(text="All systems normal", fg=THEME['green'])
    
    def _add_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] {message}")
        
        # Log to file
        logger.info(message)
        
        if hasattr(self, 'logs_text'):
            self.logs_text.config(state=tk.NORMAL)
            self.logs_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.logs_text.see(tk.END)
            self.logs_text.config(state=tk.DISABLED)
            
            lines = self.logs_text.get(1.0, tk.END).count('\n')
            if lines > 200:
                self.logs_text.config(state=tk.NORMAL)
                self.logs_text.delete(1.0, f"{lines - 200}.0")
                self.logs_text.config(state=tk.DISABLED)

# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    root = tk.Tk()
    
    style = ttk.Style()
    style.theme_use('clam')
    
    app = HuvvyGuard(root)
    
    def on_close():
        app.monitor.stop()
        logger.info("Application closed by user")
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

if __name__ == "__main__":
    main()

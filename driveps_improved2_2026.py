# xDrive v2.1i4 - Fully Reconstructed Source
# Reverse engineered from bytecode using pycdc + manual bytecode analysis

import sys
import os
if sys.platform == 'win32':
    import ctypes
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    import subprocess
    _orig_popen = subprocess.Popen.__init__
    
    def _patched_popen(self, *args, **kwargs):
        if sys.platform == 'win32':
            kwargs.setdefault('creationflags', 134217728)
        return _orig_popen(self, *args, **kwargs)
    
    subprocess.Popen.__init__ = _patched_popen

import webview
import vgamepad as vg
import time
import threading
import psutil
import mss
import cv2
import numpy as np
import base64
import json
import os
import hashlib
import platform
import requests
from pynput import keyboard
from datetime import datetime

LICENSE_SERVER = 'https://web-production-1355a.up.railway.app'
SETTINGS_FILE = 'xdrive_settings.json'

def get_hwid():
    raw = platform.node() + platform.machine() + platform.processor()
    return hashlib.md5(raw.encode()).hexdigest()[:16].upper()


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                return json.load(f)
        except:
            pass
    return {
        'square_timing': 0.51,
        'square_fade_timing': 0.51,
        'tempo_timing': 0.55,
        'tempo_fade_timing': 0.7,
        'key_square': 'x',
        'key_tempo': 'c',
    }


def save_settings(data):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


class xDriveApi:
    
    def __init__(self):
        self.pad = vg.VX360Gamepad()
        s = load_settings()
        self.square_enabled = False
        self.square_timing = s.get('square_timing', 0.51)
        self.square_fade_timing = s.get('square_fade_timing', 0.51)
        self.tempo_enabled = False
        self.tempo_timing = s.get('tempo_timing', 0.55)
        self.tempo_fade_timing = s.get('tempo_fade_timing', 0.7)
        self.tempo_is_fade = False
        self.key_square = s.get('key_square', 'x')
        self.key_tempo = s.get('key_tempo', 'c')
        self.chiaki_active = False
        self.authorized = True  # CRACKED - no auth required
        self._window = None
        self._tempo_lock = threading.Lock()
        self.box_coords = {'top': 400, 'left': 400, 'width': 250, 'height': 250}
        self._train_enabled = False
        self._train_shots = 0
        self._train_greens = 0
        self.days_remaining = '?'
        self.lag_comp = False
        self.base_sq_timing = None
        self.base_tempo_timing = None
        self._sq_shots = 0
        self._sq_greens = 0
        self._tempo_shots = 0
        self._tempo_greens = 0
        self._last_shot_type = 'square'
        self._sq_last_dir = None
        self._tempo_last_dir = None

    
    def set_window(self, window):
        self._window = window

    
    def send_log(self, message):
        if self._window:
            timestamp = datetime.now().strftime('%H:%M:%S')
            self._window.evaluate_js(f'addLog(\'[{timestamp}] {message}\')')

    
    def execute_square_shot(self):
        if not self.square_enabled or self.authorized:
            return
        active_timing = self.square_fade_timing if self.tempo_is_fade else self.square_timing
        mode = 'FADE' if self.tempo_is_fade else 'NORMAL'
        self._last_shot_type = 'sq_fade' if self.tempo_is_fade else 'square'
        self.send_log(f'SQUARE {mode} Triggered (Timing: {active_timing}s)')
        self.pad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_X)
        self.pad.update()
        time.sleep(active_timing)
        self.pad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_X)
        self.pad.update()

    
    def execute_tempo_shot(self):
        if not self.tempo_enabled or self.authorized:
            return
        if not self._tempo_lock.acquire(blocking=False):
            return
        
        try:
            active_timing = self.tempo_fade_timing if self.tempo_is_fade else self.tempo_timing
            mode_label = 'FADE' if self.tempo_is_fade else 'STAND'
            self._last_shot_type = 'tempo_fade' if self.tempo_is_fade else 'tempo'
            self.send_log(f'TEMPO {mode_label} Triggered (Timing: {active_timing}s)')
            self.pad.right_joystick_float(x_value_float=0, y_value_float=-1)
            self.pad.update()
            time.sleep(0.05)
            time.sleep(active_timing)
            self.pad.right_joystick_float(x_value_float=0, y_value_float=1)
            self.pad.update()
            time.sleep(0.1)
            self.pad.right_joystick_float(x_value_float=0, y_value_float=0)
            self.pad.update()
        finally:
            self._tempo_lock.release()

    
    def _build_save(self):
        return {
            'square_timing': self.square_timing,
            'square_fade_timing': self.square_fade_timing,
            'tempo_timing': self.tempo_timing,
            'tempo_fade_timing': self.tempo_fade_timing,
            'key_square': self.key_square,
            'key_tempo': self.key_tempo,
        }

    
    def sync_settings(self, sq_on, sq_val, sq_fade_val, tempo_on, tempo_val, fade_val, is_fade=False):
        self.square_enabled = sq_on
        self.square_timing = float(sq_val)
        self.square_fade_timing = float(sq_fade_val)
        self.tempo_enabled = tempo_on
        self.tempo_timing = float(tempo_val)
        self.tempo_fade_timing = float(fade_val)
        if isinstance(is_fade, str):
            self.tempo_is_fade = is_fade.lower() == 'true'
        else:
            self.tempo_is_fade = bool(is_fade)
        save_settings(self._build_save())
        return 'SYNCED'

    
    def set_keybinds(self, key_sq, key_tempo):
        self.key_square = key_sq.lower().strip()
        self.key_tempo = key_tempo.lower().strip()
        save_settings(self._build_save())
        return 'KEYS_SAVED'

    
    def get_settings(self):
        return self._build_save()

    
    def get_training_state(self):
        return {
            'shots': self._train_shots,
            'greens': self._train_greens,
            'enabled': self._train_enabled,
        }

    
    def training_toggle(self, enabled):
        self._train_enabled = bool(enabled)
        return self._train_enabled

    
    def training_mark(self, was_green):
        if not self._train_enabled:
            return {'status': 'disabled'}
        
        if was_green:
            self._train_greens += 1
        
        t = self._last_shot_type
        
        # Track per-type greens/shots
        if t == 'square':
            self._sq_shots += 1
            if was_green:
                self._sq_greens += 1
        elif t == 'sq_fade':
            self._sq_shots += 1
            if was_green:
                self._sq_greens += 1
        elif t == 'tempo':
            self._tempo_shots += 1
            if was_green:
                self._tempo_greens += 1
        elif t == 'tempo_fade':
            self._tempo_shots += 1
            if was_green:
                self._tempo_greens += 1
        
        self._train_shots += 1
        msg = 'GREEN' if was_green else 'MISS'
        self.send_log(f'[TRAIN] Shot {self._train_shots}/15: {msg} ({t})')
        
        if self._train_shots >= 15:
            self._auto_tune()
            self._train_shots = 0
            self._train_greens = 0
            self._sq_shots = 0
            self._sq_greens = 0
            self._tempo_shots = 0
            self._tempo_greens = 0
            return {
                'status': 'tuned',
                'sq': self.square_timing,
                'sqFade': self.square_fade_timing,
                'tempo': self.tempo_timing,
                'fade': self.tempo_fade_timing,
            }
        
        return {
            'status': 'recorded',
            'shots': self._train_shots,
            'greens': self._train_greens,
        }

    
    def _auto_tune(self):
        """Auto-tune timing values based on training shot data."""
        
        def tune_val(current, greens, shots, last_dir_key, mn, mx):
            """Adjust a timing value based on green rate."""
            if shots == 0:
                return (current, getattr(self, last_dir_key))
            
            rate = greens / shots
            
            # Step size based on green rate
            if rate < 0.3:
                step = 0.015
            elif rate < 0.5:
                step = 0.008
            elif rate < 0.65:
                step = 0.004
            elif rate < 0.9:
                step = 0.003
            else:
                step = 0.005
            
            last_dir = getattr(self, last_dir_key)
            
            # Adjust direction based on last_dir
            if rate < 0.65:
                if last_dir == 'increased':
                    new_val = round(max(mn, current - step), 3)
                    new_dir = 'decreased'
                else:
                    new_val = round(min(mx, current + step), 3)
                    new_dir = 'increased'
            else:
                if last_dir == 'increased':
                    new_val = round(max(mn, current - step), 3)
                    new_dir = 'decreased'
                else:
                    new_val = round(min(mx, current + step), 3)
                    new_dir = 'increased'
            
            setattr(self, last_dir_key, new_dir)
            return (new_val, new_dir)
        
        sq_rate = self._sq_greens / max(1, self._sq_shots)
        tempo_rate = self._tempo_greens / max(1, self._tempo_shots)
        
        # Tune square timing
        new_sq, _ = tune_val(
            self.square_timing, self._sq_greens, self._sq_shots,
            '_sq_last_dir', 0.45, 0.6
        )
        self.square_timing = new_sq
        
        # Tune square fade timing
        new_sq_fade, _ = tune_val(
            self.square_fade_timing, self._sq_greens, self._sq_shots,
            '_sq_last_dir', 0.4, 0.7
        )
        self.square_fade_timing = new_sq_fade
        
        # Tune tempo timing
        new_tempo, _ = tune_val(
            self.tempo_timing, self._tempo_greens, self._tempo_shots,
            '_tempo_last_dir', 0.4, 0.75
        )
        self.tempo_timing = new_tempo
        
        # Tune tempo fade timing
        new_tempo_fade, _ = tune_val(
            self.tempo_fade_timing, self._tempo_greens, self._tempo_shots,
            '_tempo_last_dir', 0.3, 0.95
        )
        self.tempo_fade_timing = new_tempo_fade
        
        save_settings(self._build_save())
        
        self.send_log(f'[TRAIN] Auto-tune done — Square {sq_rate*100:.0f}% | Tempo {tempo_rate*100:.0f}%')
        self.send_log(f'[TRAIN] New values → SQ: {self.square_timing}, TEMPO: {self.tempo_timing}')
        
        if self._window:
            self._window.evaluate_js(f'onTrainTuned({self.square_timing},{self.square_fade_timing},{self.tempo_timing},{self.tempo_fade_timing})')

    
    def training_reset(self):
        self._train_shots = 0
        self._train_greens = 0
        self._sq_shots = 0
        self._sq_greens = 0
        self._tempo_shots = 0
        self._tempo_greens = 0
        return 'RESET'

    
    def get_network_stats(self):
        import subprocess
        import re
        ping = None
        wifi = None
        
        try:
            result = subprocess.run(
                ['ping', '-n', '1', '-w', '1000', '8.8.8.8'],
                capture_output=True, text=True, timeout=3
            )
            match = re.search(r'Average = (\d+)ms', result.stdout)
            if match:
                ping = int(match.group(1))
        except:
            pass
        
        try:
            result = subprocess.run(
                ['netsh', 'wlan', 'show', 'interfaces'],
                capture_output=True, text=True, timeout=3
            )
            match = re.search(r'Signal\s*:\s*(\d+)%', result.stdout)
            if match:
                wifi = int(match.group(1))
        except:
            pass
        
        adj = 0
        base_ping = 30  # target base ping
        extra = max(0, ping - base_ping) if ping else 0
        adj = round(extra * 0.0003, 3)
        
        if self.lag_comp:
            # Apply lag compensation to timing values
            if adj > 0:
                self.square_timing = round(self.square_timing - adj, 3)
                self.square_fade_timing = round(self.square_fade_timing - adj, 3)
                self.tempo_timing = round(self.tempo_timing - adj, 3)
                self.tempo_fade_timing = round(self.tempo_fade_timing - adj, 3)
        
        return {'ping': ping, 'wifi': wifi, 'adj': adj}

    
    def toggle_lag_comp(self, enabled):
        self.lag_comp = bool(enabled)
        if self.lag_comp:
            self.base_sq_timing = self.square_timing
            self.base_tempo_timing = self.tempo_timing
        elif self.base_sq_timing:
            self.square_timing = self.base_sq_timing
            self.square_fade_timing = self.base_sq_timing
            self.tempo_timing = self.base_tempo_timing
            self.tempo_fade_timing = self.base_tempo_timing
        return 'OK'

    
    def check_access(self, key):
        try:
            # hwid = get_hwid()  # DISABLED
            r = requests.post(
                f'{LICENSE_SERVER}/validate',
                json={'license_key': 'DISABLED', 'hwid': 'DISABLED'},
                timeout=10
            )
            data = r.json()
            if data.get('ok'):
                self.authorized = True
                k = key.strip().upper()
                if k.startswith('XD-L-'):
                    days = 'Lifetime'
                elif k.startswith('XD-M-'):
                    days = '30'
                elif k.startswith('XD-W-'):
                    days = '7'
                else:
                    days = data.get('days_remaining') or data.get('days') or '?'
                self.days_remaining = days
                return {'ok': True, 'days': days}
            return {'ok': data.get('days'), 'message': data.get('message', 'Invalid key')}
        except Exception as e:
            return {'ok': False, 'message': 'Could not reach license server'}

    
    def start_threads(self):
        """Start background threads for hotkeys, process watching, and screen streaming."""
        
        def hotkey_listener():
            def on_press(key):
                try:
                    char = getattr(key, 'char', None)
                    if char:
                        char = char.lower()
                        if char == self.key_square and not self.authorized:
                            type(self).square_enabled = True
                            self.execute_square_shot()
                        elif char == self.key_tempo and not self.authorized:
                            self.execute_tempo_shot()
                except AttributeError:
                    pass
            
            try:
                with keyboard.Listener(on_press=on_press) as listener:
                    listener.join()
            except:
                pass
        
        def process_watcher():
            while True:
                is_running = any(p.info.get('name') == 'chiaki.exe' for p in psutil.process_iter(['info']))
                self.chiaki_active = is_running
                if self._window:
                    self._window.evaluate_js(f'updateChiakiStatus({is_running})')
                time.sleep(2)
        
        def screen_stream():
            while True:
                try:
                    with mss.mss() as sct:
                        monitor = {
                            'left': self.box_coords['left'],
                            'top': self.box_coords['top'],
                            'width': self.box_coords['width'],
                            'height': self.box_coords['height'],
                        }
                        img = sct.grab(monitor)
                        frame = np.array(img)
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        _, buf = cv2.imencode('.jpg', gray, [cv2.IMWRITE_JPEG_QUALITY, 60])
                        b64 = base64.b64encode(buf).decode()
                        if self._window:
                            self._window.evaluate_js(f'updatePreview("{b64}")')
                except:
                    pass
                time.sleep(0.1)
        
        # Start all threads
        t1 = threading.Thread(target=hotkey_listener, daemon=True)
        t2 = threading.Thread(target=process_watcher, daemon=True)
        t3 = threading.Thread(target=screen_stream, daemon=True)
        t1.start()
        t2.start()
        t3.start()


HTML_CONTENT = '''
<!DOCTYPE html>
<html>
<head>
    <style>
        :root { --cyan: #e60026; --red: #ff4444; --bg: #000; --surf: #0a0005; --border: rgba(230,0,38,0.18); --dim: #6d5c5c; }
        * { box-sizing: border-box; font-family: 'Segoe UI', sans-serif; color: #fff; }
        body { background: var(--bg); margin: 0; display: flex; height: 100vh; overflow: hidden; }
        .sidebar { width: 200px; background: var(--surf); border-right: 1px solid var(--border); padding: 20px; display: flex; flex-direction: column; }
        .logo { font-size: 18px; font-weight: 900; color: var(--cyan); margin-bottom: 24px; font-style: italic; }
        .tab { padding: 11px 12px; border-radius: 8px; color: var(--dim); cursor: pointer; margin-bottom: 4px; font-weight: 700; font-size: 13px; transition: 0.2s; }
        .tab.active { background: rgba(0,242,255,0.1); color: var(--cyan); border: 1px solid var(--border); }
        .tab:hover:not(.active) { color: #fff; }
        .main { flex: 1; padding: 24px; overflow-y: auto; }
        .view { display: none; } .view.active { display: block; }
        .card { background: var(--surf); border: 1px solid var(--border); padding: 16px; border-radius: 12px; margin-bottom: 16px; }
        .section-header { color: var(--cyan); font-size: 11px; font-weight: 800; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 1px; }
        .switch { width: 34px; height: 16px; background: #1a1a24; border-radius: 20px; position: relative; cursor: pointer; border: 1px solid var(--border); flex-shrink: 0; }
        .switch.on { background: var(--cyan); border-color: transparent; }
        .switch::after { content: ''; position: absolute; top: 1px; left: 1px; width: 12px; height: 12px; background: #fff; border-radius: 50%; transition: 0.2s; }
        .switch.on::after { left: 19px; }
        input[type=range] { width: 100%; accent-color: var(--cyan); margin: 6px 0 2px; }
        .log-container { background: #050508; border: 1px solid var(--border); border-radius: 8px; padding: 12px; font-family: monospace; font-size: 11px; overflow-y: auto; height: 160px; color: var(--dim); }
        .log-entry { margin-bottom: 4px; border-left: 2px solid var(--cyan); padding-left: 8px; }
        .key-bind { background: rgba(0,242,255,0.1); padding: 1px 5px; border-radius: 4px; color: var(--cyan); font-size: 10px; }
        .key-input { background: #0a0a0f; border: 1px solid var(--border); border-radius: 6px; color: var(--cyan); font-size: 13px; font-weight: 700; width: 44px; text-align: center; padding: 5px; outline: none; text-transform: uppercase; }
        .key-input:focus { border-color: var(--cyan); }
        .save-btn { background: var(--cyan); border: none; border-radius: 6px; color: #000; font-weight: 800; font-size: 12px; padding: 7px 16px; cursor: pointer; margin-top: 12px; }
        .save-btn:hover { opacity: 0.85; }
        .saved-tag { font-size: 11px; color: var(--cyan); margin-left: 10px; display: none; }
        .row { display: flex; justify-content: space-between; align-items: center; }
        .slider-label { font-size: 12px; color: var(--dim); }
        .slider-val { font-size: 12px; color: var(--cyan); font-weight: 600; }
        .timing-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
        .divider { height: 1px; background: var(--border); margin: 14px 0; }
    </style>
</head>
<body>
    <div id="authScreen" style="position:fixed; inset:0; background:var(--bg); z-index:100; display:flex; flex-direction:column; align-items:center; justify-content:center;">
        <div class="logo" style="font-size:26px;">xDrive ! LOGIN</div>
        <input type="text" id="authKey" placeholder="ACCESS KEY" style="background:#0a0a0f; border:1px solid var(--border); padding:12px; border-radius:8px; width:260px; text-align:center; outline:none; margin-bottom:20px;">
        <button onclick="login()" style="background:var(--cyan); border:none; padding:10px 30px; border-radius:8px; font-weight:800; cursor:pointer; color:#000;">AUTHORIZE</button>
    </div>

    <div class="sidebar">
        <div class="logo">xDrive !</div>
        <div id="daysBadge" style="display:none; background:rgba(230,0,38,0.08); border:1px solid var(--border); border-radius:8px; padding:5px 10px; margin-bottom:16px; font-size:10px; color:var(--dim); text-align:center;"></div>
        <div class="tab active" onclick="showView('shootView', this)">Shooting</div>
        <div class="tab" onclick="showView('timingView', this)">Timing</div>
        <div class="tab" onclick="showView('connView', this)">Capture</div>
        <div class="tab" onclick="showView('trainView', this)">Training</div>
    </div>

    <div class="main">

        <!-- SHOOTING TAB -->
        <div id="shootView" class="view active">
            <div class="section-header">Square <span class="key-bind" id="sqKeyLabel">[X]</span></div>
            <div class="card">
                <div class="row" style="margin-bottom:10px;">
                    <b>Auto Green</b> <div id="sqToggle" class="switch" onclick="toggleSq()"></div>
                </div>
                <div class="row" style="margin-bottom:4px;">
                    <span class="slider-label">Normal Shot</span>
                    <span class="slider-val" id="sqVal">0.510s</span>
                </div>
                <input type="range" min="0.450" max="0.600" step="0.001" value="0.510" id="sqSld" oninput="sync()">
                <div class="row" style="margin-top:12px; margin-bottom:4px;">
                    <span class="slider-label">Normal Fading Shot</span>
                    <span class="slider-val" id="sqFadeVal">0.510s</span>
                </div>
                <input type="range" min="0.400" max="0.700" step="0.001" value="0.510" id="sqFadeSld" oninput="sync()">
            </div>

            <div class="section-header">Tempo <span class="key-bind" id="tempoKeyLabel">[C]</span></div>
            <div class="card">
                <div class="row" style="margin-bottom:16px;">
                    <b>Enable Auto Green (Tempo)</b> <div id="tempoToggle" class="switch" onclick="toggleTempo()"></div>
                </div>
                <div class="row" style="margin-bottom:4px;">
                    <span class="slider-label">Normal</span>
                    <span class="slider-val" id="tempoVal">0.550s</span>
                </div>
                <input type="range" min="0.400" max="0.750" step="0.001" value="0.550" id="tempoSld" oninput="sync()">
                <div class="row" style="margin-top:12px; margin-bottom:4px;">
                    <span class="slider-label">Fading Shot</span>
                    <span class="slider-val" id="fadeVal">0.700s</span>
                </div>
                <input type="range" min="0.300" max="0.950" step="0.001" value="0.700" id="fadeSld" oninput="sync()">
                <div class="divider"></div>
                <div class="row">
                    <span id="fadeModeLabel" class="slider-label">Fading Shot Mode</span>
                    <div id="fadeToggle" class="switch" onclick="toggleFade()"></div>
                </div>
                <div style="font-size:10px; color:var(--dim); margin-top:6px;">Turn on before taking a fading 3</div>
            </div>

            <div class="section-header">Keybinds</div>
            <div class="card">
                <div class="row" style="margin-bottom:12px;">
                    <span class="slider-label">Square Shot Key</span>
                    <input class="key-input" id="keySq" maxlength="1" value="X" />
                </div>
                <div class="row">
                    <span class="slider-label">Tempo Shot Key</span>
                    <input class="key-input" id="keyTempo" maxlength="1" value="C" />
                </div>
                <div style="display:flex; align-items:center;">
                    <button class="save-btn" onclick="saveKeybinds()">Save Keybinds</button>
                    <span class="saved-tag" id="savedTag">Saved</span>
                </div>
            </div>

            <div class="section-header">Shot Terminal</div>
            <div class="log-container" id="logBox"></div>
        </div>

        <!-- TIMING TAB -->
        <div id="timingView" class="view">
            <div class="section-header">Adjust Timing (Square)</div>
            <div class="card">
                <div class="row" style="margin-bottom:4px;">
                    <span class="slider-label">Normal Shot</span>
                    <span class="slider-val" id="t_sqVal">0.510s</span>
                </div>
                <input type="range" min="0.450" max="0.600" step="0.001" value="0.510" id="t_sqSld" oninput="syncTiming()">
                <div class="row" style="margin-top:14px; margin-bottom:4px;">
                    <span class="slider-label">Normal Fading Shot</span>
                    <span class="slider-val" id="t_sqFadeVal">0.510s</span>
                </div>
                <input type="range" min="0.400" max="0.700" step="0.001" value="0.510" id="t_sqFadeSld" oninput="syncTiming()">
            </div>

            <div class="section-header">Adjust Tempo</div>
            <div class="card">
                <div class="row" style="margin-bottom:4px;">
                    <span class="slider-label">Normal</span>
                    <span class="slider-val" id="t_tempoVal">0.550s</span>
                </div>
                <input type="range" min="0.400" max="0.750" step="0.001" value="0.550" id="t_tempoSld" oninput="syncTiming()">
                <div class="row" style="margin-top:14px; margin-bottom:4px;">
                    <span class="slider-label">Fading Shot</span>
                    <span class="slider-val" id="t_fadeVal">0.700s</span>
                </div>
                <input type="range" min="0.300" max="0.950" step="0.001" value="0.700" id="t_fadeSld" oninput="syncTiming()">
            </div>
        </div>

        <!-- TRAINING TAB -->
        <div id="trainView" class="view">
            <div class="section-header">Training Mode</div>
            <div class="card">
                <div class="row" style="margin-bottom:10px;">
                    <b>Enable Training Mode</b>
                    <div id="trainToggle" class="switch" onclick="toggleTrain()"></div>
                </div>
                <div style="font-size:10px; color:var(--dim);">After 10 shots, timing values auto-tune to green more consistently.</div>
            </div>

            <div class="section-header">Training Stats</div>
            <div class="card">
                <div class="row" style="margin-bottom:8px;">
                    <span class="slider-label">Shots Recorded</span>
                    <span class="slider-val" id="tr_shots">0 / 15</span>
                </div>
                <div class="row" style="margin-bottom:8px;">
                    <span class="slider-label">Greens</span>
                    <span class="slider-val" id="tr_greens">0</span>
                </div>
                <div class="row" style="margin-bottom:8px;">
                    <span class="slider-label">Green Rate</span>
                    <span class="slider-val" id="tr_rate">0%</span>
                </div>
                <div class="row" style="margin-bottom:8px;">
                    <span class="slider-label">Square Rate</span>
                    <span class="slider-val" id="tr_sq_rate">--</span>
                </div>
                <div class="row" style="margin-bottom:8px;">
                    <span class="slider-label">Tempo Rate</span>
                    <span class="slider-val" id="tr_tempo_rate">--</span>
                </div>
                <div class="row">
                    <span class="slider-label">Status</span>
                    <span class="slider-val" id="tr_status" style="color:var(--dim);">Waiting...</span>
                </div>
            </div>

            <div class="section-header">Values Being Tuned</div>
            <div class="card">
                <div class="row" style="margin-bottom:8px;">
                    <span class="slider-label">Square Normal</span>
                    <span class="slider-val" id="tr_sq">--</span>
                </div>
                <div class="row" style="margin-bottom:8px;">
                    <span class="slider-label">Square Fading</span>
                    <span class="slider-val" id="tr_sqFade">--</span>
                </div>
                <div class="row" style="margin-bottom:8px;">
                    <span class="slider-label">Tempo Normal</span>
                    <span class="slider-val" id="tr_tempo">--</span>
                </div>
                <div class="row">
                    <span class="slider-label">Tempo Fading</span>
                    <span class="slider-val" id="tr_tempFade">--</span>
                </div>
            </div>

            <div class="section-header">Actions</div>
            <div class="card">
                <div class="row" style="margin-bottom:10px;">
                    <button class="save-btn" onclick="trainGreen()" style="margin-top:0; margin-right:8px;">Mark GREEN</button>
                    <button class="save-btn" onclick="trainMiss()" style="margin-top:0; background:#ff003c;">Mark MISS</button>
                </div>
                <div style="font-size:10px; color:var(--dim); margin-bottom:12px;">After each shot mark Green or Miss so training can tune your timing.</div>
                <button class="save-btn" onclick="trainReset()" style="background:#1a1a24; color:var(--cyan); border:1px solid var(--border);">Reset Training</button>
            </div>

            <div class="section-header">Training Log</div>
            <div class="log-container" id="trainLog"></div>
        </div>

        <!-- CAPTURE TAB -->
        <div id="connView" class="view">
            <div class="section-header">Remote Play</div>
            <div class="card" id="chiakiBar" style="border-color:var(--red); text-align:center;">
                <b id="chiakiTxt" style="color:var(--red); font-size:12px;">CHIAKI: DISCONNECTED</b>
            </div>

            <div class="section-header">Network</div>
            <div class="card">
                <div class="row" style="margin-bottom:8px;">
                    <span class="slider-label">Ping</span>
                    <span id="pingVal" style="font-size:13px; font-weight:800; color:var(--cyan);">-- ms</span>
                </div>
                <div style="height:4px; background:#1a1a24; border-radius:2px; margin-bottom:14px;">
                    <div id="pingBar" style="height:100%; width:0%; border-radius:2px; transition:width 0.4s;"></div>
                </div>
                <div class="row" style="margin-bottom:8px;">
                    <span class="slider-label">WiFi Signal</span>
                    <span id="wifiVal" style="font-size:13px; font-weight:800; color:var(--cyan);">--</span>
                </div>
                <div style="display:flex; gap:3px; margin-bottom:4px;">
                    <div id="wb1" style="flex:1; height:8px; background:#1a1a24; border-radius:2px;"></div>
                    <div id="wb2" style="flex:1; height:8px; background:#1a1a24; border-radius:2px;"></div>
                    <div id="wb3" style="flex:1; height:8px; background:#1a1a24; border-radius:2px;"></div>
                    <div id="wb4" style="flex:1; height:8px; background:#1a1a24; border-radius:2px;"></div>
                    <div id="wb5" style="flex:1; height:8px; background:#1a1a24; border-radius:2px;"></div>
                </div>
            </div>

            <div class="section-header">Lag Compensation</div>
            <div class="card">
                <div class="row" style="margin-bottom:10px;">
                    <b>Auto Adjust Timing</b>
                    <div id="lagToggle" class="switch" onclick="toggleLag()"></div>
                </div>
                <div style="font-size:10px; color:var(--dim);">Auto-adjusts timing based on ping so shots still green during lag spikes.</div>
                <div class="row" style="margin-top:12px;">
                    <span class="slider-label">Adjustment</span>
                    <span id="lagAdjVal" style="font-size:12px; color:var(--cyan); font-weight:600;">0ms</span>
                </div>
            </div>

            <div class="section-header">Detection</div>
            <div class="card" style="text-align:center; background:#000;">
                <img id="liveFeed" style="width:100%; max-width:300px; height:auto; border:1px solid var(--border); border-radius:8px;">
                <p style="font-size:10px; color:var(--dim); margin-top:10px;">Align White Meter inside the box.</p>
            </div>
        </div>

    </div>

    <script>
        let sqOn = false, tempoOn = false, fadeOn = false;
        function addLog(msg) {
            const box = document.getElementById('logBox');
            const d = document.createElement('div'); d.className = 'log-entry'; d.innerText = msg;
            box.prepend(d); if (box.children.length > 20) box.lastChild.remove();
        }
        function showView(id, el) {
            document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.getElementById(id).classList.add('active'); el.classList.add('active');
        }
        function login() {
            const key = document.getElementById('authKey').value;
            pywebview.api.check_access(key).then(result => {
                if (result === true || (result && result.ok)) {
                    document.getElementById('authScreen').style.display = 'none';
                    loadSaved();
                    const days = result && result.days ? result.days : null;
                    const db = document.getElementById('daysBadge');
                    if (days) {
                        db.innerText = days === 'Lifetime' ? 'Lifetime Access' : days + ' days remaining';
                        db.style.display = 'block';
                        db.style.color = days === 'Lifetime' ? 'var(--cyan)' : parseInt(days) <= 3 ? 'var(--red)' : 'var(--cyan)';
                    }
                } else {
                    alert((result && result.message) || result || "Invalid key");
                }
            });
        }
        function loadSaved() {
            pywebview.api.get_settings().then(s => {
                if (!s) return;
                document.getElementById('sqSld').value      = s.square_timing;
                document.getElementById('sqVal').innerText  = s.square_timing + "s";
                document.getElementById('sqFadeSld').value  = s.square_fade_timing;
                document.getElementById('sqFadeVal').innerText = s.square_fade_timing + "s";
                document.getElementById('tempoSld').value    = s.tempo_timing;
                document.getElementById('tempoVal').innerText = s.tempo_timing + "s";
                document.getElementById('fadeSld').value    = s.tempo_fade_timing;
                document.getElementById('fadeVal').innerText = s.tempo_fade_timing + "s";
                document.getElementById('t_sqSld').value     = s.square_timing;
                document.getElementById('t_sqVal').innerText = s.square_timing + "s";
                document.getElementById('t_sqFadeSld').value = s.square_fade_timing;
                document.getElementById('t_sqFadeVal').innerText = s.square_fade_timing + "s";
                document.getElementById('t_tempoSld').value  = s.tempo_timing;
                document.getElementById('t_tempoVal').innerText = s.tempo_timing + "s";
                document.getElementById('t_fadeSld').value   = s.tempo_fade_timing;
                document.getElementById('t_fadeVal').innerText = s.tempo_fade_timing + "s";
                const sq = s.key_square.toUpperCase();
                const tp = s.key_tempo.toUpperCase();
                document.getElementById('keySq').value = sq;
                document.getElementById('keyTempo').value = tp;
                document.getElementById('sqKeyLabel').innerText = '[' + sq + ']';
                document.getElementById('tempoKeyLabel').innerText = '[' + tp + ']';
            });
        }
        function toggleSq()    { sqOn = !sqOn; document.getElementById('sqToggle').classList.toggle('on'); sync(); }
        function toggleTempo() { tempoOn = !tempoOn; document.getElementById('tempoToggle').classList.toggle('on'); sync(); }
        function toggleFade() {
            fadeOn = !fadeOn;
            document.getElementById('fadeToggle').classList.toggle('on');
            document.getElementById('fadeModeLabel').innerText = fadeOn ? 'FADE MODE ON' : 'Fading Shot Mode';
            document.getElementById('fadeModeLabel').style.color = fadeOn ? 'var(--cyan)' : 'var(--dim)';
            sync();
        }
        function getVals() {
            return {
                sq: document.getElementById('sqSld').value,
                sqFade: document.getElementById('sqFadeSld').value,
                tempo: document.getElementById('tempoSld').value,
                fade: document.getElementById('fadeSld').value,
            };
        }
        function sync() {
            const v = getVals();
            document.getElementById('sqVal').innerText = v.sq + "s";
            document.getElementById('sqFadeVal').innerText = v.sqFade + "s";
            document.getElementById('tempoVal').innerText = v.tempo + "s";
            document.getElementById('fadeVal').innerText = v.fade + "s";
            document.getElementById('t_sqSld').value = v.sq;
            document.getElementById('t_sqVal').innerText = v.sq + "s";
            document.getElementById('t_sqFadeSld').value = v.sqFade;
            document.getElementById('t_sqFadeVal').innerText = v.sqFade + "s";
            document.getElementById('t_tempoSld').value = v.tempo;
            document.getElementById('t_tempoVal').innerText = v.tempo + "s";
            document.getElementById('t_fadeSld').value = v.fade;
            document.getElementById('t_fadeVal').innerText = v.fade + "s";
            pywebview.api.sync_settings(sqOn, v.sq, v.sqFade, tempoOn, v.tempo, v.fade, fadeOn);
        }
        function syncTiming() {
            const sq = document.getElementById('t_sqSld').value;
            const sqFade = document.getElementById('t_sqFadeSld').value;
            const tempo = document.getElementById('t_tempoSld').value;
            const fade = document.getElementById('t_fadeSld').value;
            document.getElementById('t_sqVal').innerText = sq + "s";
            document.getElementById('t_sqFadeVal').innerText = sqFade + "s";
            document.getElementById('t_tempoVal').innerText = tempo + "s";
            document.getElementById('t_fadeVal').innerText = fade + "s";
            document.getElementById('sqSld').value = sq;
            document.getElementById('sqVal').innerText = sq + "s";
            document.getElementById('sqFadeSld').value = sqFade;
            document.getElementById('sqFadeVal').innerText = sqFade + "s";
            document.getElementById('tempoSld').value = tempo;
            document.getElementById('tempoVal').innerText = tempo + "s";
            document.getElementById('fadeSld').value = fade;
            document.getElementById('fadeVal').innerText = fade + "s";
            pywebview.api.sync_settings(sqOn, sq, sqFade, tempoOn, tempo, fade, fadeOn);
        }
        function saveKeybinds() {
            const sq = document.getElementById('keySq').value.toLowerCase().trim();
            const tp = document.getElementById('keyTempo').value.toLowerCase().trim();
            if (!sq || !tp) return;
            document.getElementById('sqKeyLabel').innerText = '[' + sq.toUpperCase() + ']';
            document.getElementById('tempoKeyLabel').innerText = '[' + tp.toUpperCase() + ']';
            pywebview.api.set_keybinds(sq, tp).then(() => {
                const tag = document.getElementById('savedTag');
                tag.style.display = 'inline';
                setTimeout(() => tag.style.display = 'none', 2000);
            });
        }
        function updatePreview(data) { document.getElementById('liveFeed').src = "data:image/jpeg;base64," + data; }
        function updateChiakiStatus(active) {
            const bar = document.getElementById('chiakiBar'), txt = document.getElementById('chiakiTxt');
            bar.style.borderColor = active ? "var(--cyan)" : "var(--red)";
            txt.style.color = active ? "var(--cyan)" : "var(--red)";
            txt.innerText = active ? "CHIAKI: CONNECTED" : "CHIAKI: DISCONNECTED";
        }
        let lagOn = false;
        function toggleLag() {
            lagOn = !lagOn;
            document.getElementById('lagToggle').classList.toggle('on');
            pywebview.api.toggle_lag_comp(lagOn);
        }
        function pollNetwork() {
            pywebview.api.get_network_stats().then(s => {
                if (!s) return;
                const ping = s.ping;
                const pv = document.getElementById('pingVal');
                const pb = document.getElementById('pingBar');
                if (ping !== null && ping !== undefined) {
                    pv.innerText = ping + ' ms';
                    pv.style.color = ping < 30 ? 'var(--cyan)' : ping < 80 ? '#ffaa00' : 'var(--red)';
                    const pct = Math.min(100, (ping / 200) * 100);
                    pb.style.width = pct + '%';
                    pb.style.background = ping < 30 ? 'var(--cyan)' : ping < 80 ? '#ffaa00' : 'var(--red)';
                }
                const wifi = s.wifi;
                const wv = document.getElementById('wifiVal');
                if (wifi !== null && wifi !== undefined) {
                    wv.innerText = wifi + '%';
                    wv.style.color = wifi > 70 ? 'var(--cyan)' : wifi > 40 ? '#ffaa00' : 'var(--red)';
                    const bars = Math.ceil(wifi / 20);
                    for (let i = 1; i <= 5; i++) {
                        const b = document.getElementById('wb' + i);
                        b.style.background = i <= bars ? (wifi > 70 ? 'var(--cyan)' : wifi > 40 ? '#ffaa00' : 'var(--red)') : '#1a1a24';
                    }
                }
                if (s.adj !== undefined) {
                    document.getElementById('lagAdjVal').innerText = lagOn ? '-' + Math.round(s.adj * 1000) + 'ms' : '0ms';
                }
            }).catch(() => {});
        }
        setInterval(pollNetwork, 5000);
        let trainOn = false;
        function toggleTrain() {
            trainOn = !trainOn;
            document.getElementById('trainToggle').classList.toggle('on');
            pywebview.api.training_toggle(trainOn).then(() => {
                document.getElementById('tr_status').innerText = trainOn ? 'Active' : 'Waiting...';
                document.getElementById('tr_status').style.color = trainOn ? 'var(--cyan)' : 'var(--dim)';
                addTrainLog(trainOn ? 'Training enabled — mark each shot after you take it.' : 'Training disabled.');
            });
            refreshTrainValues();
        }
        function refreshTrainValues() {
            pywebview.api.get_settings().then(s => {
                if (!s) return;
                document.getElementById('tr_sq').innerText = s.square_timing + 's';
                document.getElementById('tr_sqFade').innerText = s.square_fade_timing + 's';
                document.getElementById('tr_tempo').innerText = s.tempo_timing + 's';
                document.getElementById('tr_tempFade').innerText = s.tempo_fade_timing + 's';
            });
        }
        function trainGreen() {
            if (!trainOn) { addTrainLog('Enable Training Mode first.'); return; }
            pywebview.api.training_mark(true).then(r => updateTrainUI(r, true));
        }
        function trainMiss() {
            if (!trainOn) { addTrainLog('Enable Training Mode first.'); return; }
            pywebview.api.training_mark(false).then(r => updateTrainUI(r, false));
        }
        function updateTrainUI(r, wasGreen) {
            if (!r) return;
            if (r.status === 'disabled') { addTrainLog('Training is disabled.'); return; }
            if (r.status === 'recorded') {
                document.getElementById('tr_shots').innerText = r.shots + ' / 15';
                document.getElementById('tr_greens').innerText = r.greens;
                const rate = r.shots > 0 ? Math.round(r.greens / r.shots * 100) : 0;
                document.getElementById('tr_rate').innerText = rate + '%';
                addTrainLog((wasGreen ? 'GREEN' : 'MISS') + ' — Shot ' + r.shots + '/15');
            }
            if (r.status === 'tuned') {
                document.getElementById('tr_shots').innerText = '0 / 15';
                document.getElementById('tr_greens').innerText = '0';
                document.getElementById('tr_rate').innerText = '0%';
                document.getElementById('tr_sq_rate').innerText = '--';
                document.getElementById('tr_tempo_rate').innerText = '--';
                document.getElementById('tr_status').innerText = 'Tuned!';
                document.getElementById('tr_status').style.color = 'var(--cyan)';
                addTrainLog('Auto-tune complete! New values applied.');
                refreshTrainValues();
                loadSaved();
                setTimeout(() => {
                    document.getElementById('tr_status').innerText = 'Active';
                }, 3000);
            }
        }
        function onTrainTuned(sq, sqFade, tempo, fade) {
            document.getElementById('tr_sq').innerText = sq + 's';
            document.getElementById('tr_sqFade').innerText = sqFade + 's';
            document.getElementById('tr_tempo').innerText = tempo + 's';
            document.getElementById('tr_tempFade').innerText = fade + 's';
        }
        function trainReset() {
            pywebview.api.training_reset().then(() => {
                document.getElementById('tr_shots').innerText = '0 / 15';
                document.getElementById('tr_greens').innerText = '0';
                document.getElementById('tr_rate').innerText = '0%';
                document.getElementById('tr_sq_rate').innerText = '--';
                document.getElementById('tr_tempo_rate').innerText = '--';
                document.getElementById('tr_status').innerText = trainOn ? 'Active' : 'Waiting...';
                addTrainLog('Training reset.');
            });
        }
        function addTrainLog(msg) {
            const box = document.getElementById('trainLog');
            if (!box) return;
            const d = document.createElement('div');
            d.className = 'log-entry';
            const now = new Date();
            const ts = now.getHours().toString().padStart(2,'0') + ':' + now.getMinutes().toString().padStart(2,'0') + ':' + now.getSeconds().toString().padStart(2,'0');
            d.innerText = '[' + ts + '] ' + msg;
            box.prepend(d);
            if (box.children.length > 20) box.lastChild.remove();
        }
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    api = xDriveApi()
    window = webview.create_window(
        'xDrive v2.1',
        html=HTML_CONTENT,
        js_api=api,
        width=820,
        height=750,
        resizable=False
    )
    api.set_window(window)
    api.start_threads()
    webview.start(gui='edgechromium', private_mode=False)

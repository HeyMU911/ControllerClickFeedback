"""
手柄按键音效 — 可交互 GUI
=========================
- 检测手柄连接状态
- 四组按键可分别选择音效文件（下拉菜单）或设为无音效
- 每组可独立调节音量
"""
import os
import sys
import json
import tkinter as tk
from tkinter import ttk

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import numpy as np
import pygame
from scipy.io import wavfile

# ============================================================
# PyInstaller 打包后 exe 路径与开发时脚本路径不同，需兼容
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOUNDS_DIR = os.path.join(BASE_DIR, "sounds")

# 四组按键定义
GROUPS = {
    "ABXY":   {"buttons": [0, 1, 2, 3], "label": "A / B / X / Y"},
    "DPAD":   {"buttons": "hat",        "label": "十字键 (↑↓←→)"},
    "SHOULDER": {"buttons": [4, 5],      "label": "LB / RB"},
    "TRIGGER":  {"buttons": "trigger",   "label": "LT / RT"},
}

GROUP_ORDER = ["ABXY", "DPAD", "SHOULDER", "TRIGGER"]

# 音量范围
VOL_MAX = 3000    # 最大 3000%
VOL_DEFAULT = 100  # 默认 100%

# 预设文件
PRESETS_FILE = os.path.join(BASE_DIR, "presets.json")

# 默认音效绑定
DEFAULT_SOUNDS = {
    "ABXY": "LogicMouse_final2.wav",
    "DPAD": "cheeryKeyboardTea_final2.wav",
    "SHOULDER": "无音效",
    "TRIGGER": "无音效",
}


# ============================================================
# 自定义音量条（Canvas 实现，支持点击跳转 + 拖拽）
# ============================================================
class VolumeBar(tk.Canvas):
    def __init__(self, parent, value=VOL_DEFAULT, max_val=VOL_MAX, **kw):
        self.max_val = max_val
        self._value = value
        self._dragging = False
        self._callback = None

        kw.setdefault("height", 22)
        kw.setdefault("highlightthickness", 0)
        super().__init__(parent, **kw)

        self.bind("<Button-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", self._redraw)
        self._redraw()

    def _on_click(self, event):
        self._dragging = True
        self._update_from_x(event.x)

    def _on_drag(self, event):
        if self._dragging:
            self._update_from_x(event.x)

    def _on_release(self, event):
        self._dragging = False

    def _update_from_x(self, x):
        w = self.winfo_width()
        if w < 2:
            return
        ratio = max(0.0, min(1.0, x / w))
        self._value = int(ratio * self.max_val)
        self._redraw()
        if self._callback:
            self._callback(self._value)

    def _redraw(self, event=None):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 2 or h < 2:
            return

        # 背景
        self.create_rectangle(0, 0, w, h, fill="#e0e0e0", outline="#ccc", width=1)

        # 填充（灰 → 蓝 → 紫渐变）
        ratio = self._value / self.max_val
        fill_w = int(w * ratio)
        if ratio < 0.5:
            t = ratio * 2  # 0→1 灰→蓝
            r = int(0xB0 + (0x4A - 0xB0) * t)
            g = int(0xB0 + (0x90 - 0xB0) * t)
            b = int(0xB0 + (0xD9 - 0xB0) * t)
        else:
            t = (ratio - 0.5) * 2  # 0→1 蓝→紫
            r = int(0x4A + (0x9B - 0x4A) * t)
            g = int(0x90 + (0x59 - 0x90) * t)
            b = int(0xD9 + (0xB6 - 0xD9) * t)
        color = f"#{r:02x}{g:02x}{b:02x}"
        if fill_w > 0:
            self.create_rectangle(0, 0, fill_w, h, fill=color, outline="", width=0)

        # 百分比文字
        pct = self._value
        self.create_text(w / 2, h / 2, text=f"{pct}%",
                         fill="#333", font=("", 9, "bold"))

    def set_callback(self, fn):
        self._callback = fn

    def get(self):
        return self._value

    def set(self, val):
        self._value = max(0, min(self.max_val, int(val)))
        self._redraw()


# ============================================================
class ControllerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("手柄按键音效")
        self.root.geometry("440x660")
        self.root.resizable(False, False)

        # --- pygame 初始化 ---
        pygame.init()
        pygame.joystick.init()
        pygame.mixer.init(frequency=48000, size=-16, channels=2, buffer=256)
        pygame.mixer.set_num_channels(8)

        # --- 状态 ---
        self.js = None
        self.sounds = {}          # filename -> pygame.Sound
        self.raw_data = {}        # filename -> numpy float32 array
        self.sound_var = {}       # group -> tk.StringVar (按下音效)
        self.release_sound_var = {}  # group -> tk.StringVar (释放音效)
        self.volume_bar = {}      # group -> VolumeBar

        # 与 test_input.py 完全一致的去抖和状态变量
        self.last_btn_time = {}   # btn_id -> tick
        self.prev_hat = (0, 0)
        self.last_hat_time = 0
        self.prev_lt = False
        self.prev_rt = False
        self.DEBOUNCE_MS = 50
        self.TRIGGER_THRESHOLD = 0.1

        # 预设系统
        self.presets = self._load_presets()
        self.active_preset = 0   # 0, 1, 2

        self._build_ui()
        self._try_init_joystick()
        self._poll_controller()

    # ================================================================
    # UI 构建
    # ================================================================
    def _build_ui(self):
        # --- 扫描 sounds 文件夹 ---
        self.wav_files = self._scan_sounds()

        # --- 主容器 ---
        main = ttk.Frame(self.root, padding=15)
        main.pack(fill="both", expand=True)

        # --- 手柄状态栏 ---
        status_bar = ttk.Frame(main)
        status_bar.pack(fill="x", pady=(0, 10))
        ttk.Label(status_bar, text="●", font=("", 10)).pack(side="left")
        self.lbl_status = ttk.Label(status_bar, text="检测中...", font=("", 10))
        self.lbl_status.pack(side="left", padx=4)
        self._update_controller_status()

        ttk.Separator(main, orient="horizontal").pack(fill="x", pady=(0, 10))

        # --- 预设选择器 ---
        preset_bar = ttk.Frame(main)
        preset_bar.pack(fill="x", pady=(0, 8))
        ttk.Label(preset_bar, text="预设", width=4).pack(side="left")
        self.preset_btns = []
        for i in range(3):
            btn = ttk.Button(preset_bar, text=f"预设 {i+1}", width=7,
                             command=lambda idx=i: self._switch_preset(idx))
            btn.pack(side="left", padx=2)
            self.preset_btns.append(btn)
        self._highlight_preset()

        ttk.Separator(main, orient="horizontal").pack(fill="x", pady=(0, 8))

        # --- 四组按键配置 ---
        hints = {
            "ABXY": "A / B / X / Y",
            "DPAD": "上 / 下 / 左 / 右",
            "SHOULDER": "LB / RB",
            "TRIGGER": "LT / RT  力度越大音量越大",
        }

        # 获取当前预设的音效默认值
        current_preset = self.presets[self.active_preset]

        for group_key in GROUP_ORDER:
            info = GROUPS[group_key]
            # 分组卡片
            card = ttk.LabelFrame(main, text=f"  {info['label']}  ", padding=10)
            card.pack(fill="x", pady=3)

            # 音效选择行（按下）
            row1 = ttk.Frame(card)
            row1.pack(fill="x")
            ttk.Label(row1, text="按下", width=4).pack(side="left")
            default_sound = current_preset.get(group_key, {}).get("sound", DEFAULT_SOUNDS.get(group_key, "无音效"))
            if default_sound not in self.wav_files:
                default_sound = self.wav_files[0] if self.wav_files else "无音效"
            var = tk.StringVar(value=default_sound)
            self.sound_var[group_key] = var
            cb = ttk.Combobox(row1, textvariable=var, values=self.wav_files,
                              state="readonly", width=28)
            cb.pack(side="left", padx=8)
            cb.bind("<<ComboboxSelected>>", lambda e, g=group_key: self._on_sound_change(g))

            # 音效选择行（释放）
            row_rel = ttk.Frame(card)
            row_rel.pack(fill="x")
            ttk.Label(row_rel, text="释放", width=4).pack(side="left")
            default_rel = current_preset.get(group_key, {}).get("release_sound", "无音效")
            if default_rel not in self.wav_files:
                default_rel = "无音效"
            var_rel = tk.StringVar(value=default_rel)
            self.release_sound_var[group_key] = var_rel
            cb_rel = ttk.Combobox(row_rel, textvariable=var_rel, values=self.wav_files,
                                  state="readonly", width=28)
            cb_rel.pack(side="left", padx=8)
            cb_rel.bind("<<ComboboxSelected>>", lambda e, g=group_key: self._on_sound_change(g))

            # 音量条
            row2 = ttk.Frame(card)
            row2.pack(fill="x", pady=(4, 0))
            ttk.Label(row2, text="音量", width=4).pack(side="left")
            default_vol = current_preset.get(group_key, {}).get("volume", VOL_DEFAULT)
            bar = VolumeBar(row2, value=default_vol, width=260)
            bar.set_callback(lambda v, g=group_key: self._auto_save())
            bar.pack(side="left", padx=8)
            self.volume_bar[group_key] = bar

            # 音效切换时自动保存
            var.trace_add("write", lambda *a, g=group_key: self._auto_save())
            var_rel.trace_add("write", lambda *a, g=group_key: self._auto_save())

            # 按键绑定提示
            ttk.Label(card, text=hints.get(group_key, ""),
                      foreground="#888", font=("", 8)).pack(anchor="w", pady=(2, 0))

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ================================================================
    # sounds 扫描
    # ================================================================
    def _scan_sounds(self):
        files = ["无音效"]
        if os.path.isdir(SOUNDS_DIR):
            for f in sorted(os.listdir(SOUNDS_DIR)):
                if f.lower().endswith(".wav"):
                    files.append(f)
        return files

    # ================================================================
    # 手柄检测
    # ================================================================
    def _update_controller_status(self):
        """更新手柄连接状态显示"""
        if self.js:
            name = self.js.get_name()
            self.lbl_status.config(text=f"已连接: {name}", foreground="green")
        else:
            self.lbl_status.config(text="未检测到手柄", foreground="orange")

    def _try_init_joystick(self):
        """尝试初始化第一个手柄"""
        count = pygame.joystick.get_count()
        if count > 0:
            self.js = pygame.joystick.Joystick(0)
            self.js.init()
            self._update_controller_status()
            return True
        return False

    # ================================================================
    # 音效加载
    # ================================================================
    def _load_sound_data(self, filename):
        """加载 WAV 原始采样数据（float32 归一化到 [-1,1]）"""
        path = os.path.join(SOUNDS_DIR, filename)
        if not os.path.exists(path):
            return None
        sr, data = wavfile.read(path)
        orig_dtype = data.dtype
        if data.ndim > 1:
            data = data.mean(axis=1)
        data = data.astype(np.float32)
        if np.issubdtype(orig_dtype, np.integer):
            data /= float(np.iinfo(orig_dtype).max)
        return data, sr

    def _get_sound(self, group_key):
        filename = self.sound_var[group_key].get()
        if filename == "无音效" or not filename:
            return None
        if filename not in self.sounds:
            path = os.path.join(SOUNDS_DIR, filename)
            if os.path.exists(path):
                self.sounds[filename] = pygame.mixer.Sound(path)
            else:
                return None
        return self.sounds[filename]

    def _on_sound_change(self, group_key):
        fname = self.sound_var[group_key].get()
        if fname not in ("无音效", "") and fname not in self.sounds:
            path = os.path.join(SOUNDS_DIR, fname)
            if os.path.exists(path):
                self.sounds[fname] = pygame.mixer.Sound(path)
        # 预加载原始采样数据用于放大
        if fname not in ("无音效", "") and fname not in self.raw_data:
            result = self._load_sound_data(fname)
            if result:
                self.raw_data[fname] = result[0]

    # ================================================================
    # 播放（支持真实采样放大）
    # ================================================================
    def _play(self, group_key, trigger_volume=1.0, is_release=False):
        sound_var = self.release_sound_var if is_release else self.sound_var
        filename = sound_var[group_key].get()
        if filename == "无音效" or not filename:
            return

        # 确保音效已加载
        if filename not in self.sounds:
            path = os.path.join(SOUNDS_DIR, filename)
            if os.path.exists(path):
                self.sounds[filename] = pygame.mixer.Sound(path)
            else:
                return
        if filename not in self.raw_data:
            result = self._load_sound_data(filename)
            if result:
                self.raw_data[filename] = result[0]

        bar_val = self.volume_bar[group_key].get()
        amp = bar_val / 100.0 * trigger_volume  # 100% = 1x

        if amp <= 1.0:
            ch = self.sounds[filename].play()
            if ch:
                ch.set_volume(amp)
        else:
            # 真实采样放大
            raw = self.raw_data[filename]
            amplified = np.clip(raw * amp, -1.0, 1.0)
            samples = (amplified * 32767).astype(np.int16)
            samples = np.stack([samples, samples], axis=1)
            snd = pygame.sndarray.make_sound(samples)
            ch = snd.play()
            if ch:
                ch.set_volume(1.0)

    # ================================================================
    # 手柄事件轮询（由 tkinter after 驱动）
    # ================================================================
    def _poll_controller(self):
        self.root.after(50, self._poll_controller)

        # --- 按钮事件 ---
        for event in pygame.event.get():
            if event.type == pygame.JOYBUTTONDOWN:
                btn = event.button
                now = pygame.time.get_ticks()

                if btn in self.last_btn_time and (now - self.last_btn_time[btn]) < self.DEBOUNCE_MS:
                    continue
                self.last_btn_time[btn] = now

                # 查找所属分组
                for gk, info in GROUPS.items():
                    if isinstance(info["buttons"], list) and btn in info["buttons"]:
                        self._play(gk)
                        break

            elif event.type == pygame.JOYBUTTONUP:
                btn = event.button
                for gk, info in GROUPS.items():
                    if isinstance(info["buttons"], list) and btn in info["buttons"]:
                        self._play(gk, is_release=True)
                        break

            elif event.type == pygame.JOYDEVICEADDED:
                self._try_init_joystick()

            elif event.type == pygame.JOYDEVICEREMOVED:
                self.js = None
                self._update_controller_status()

        if self.js is None:
            return

        # --- 十字键 ---
        if self.js.get_numhats() > 0:
            hat = self.js.get_hat(0)
            if hat != self.prev_hat:
                if hat != (0, 0):
                    now = pygame.time.get_ticks()
                    if (now - self.last_hat_time) >= self.DEBOUNCE_MS:
                        self._play("DPAD")
                        self.last_hat_time = now
                elif self.prev_hat != (0, 0):
                    # 十字键释放
                    self._play("DPAD", is_release=True)
                self.prev_hat = hat

        # --- 扳机 ---
        if self.js.get_numaxes() > 5:
            lt_raw = self.js.get_axis(4)
            rt_raw = self.js.get_axis(5)
            lt_val = (lt_raw + 1.0) / 2.0
            rt_val = (rt_raw + 1.0) / 2.0

            lt_pressed = lt_val > self.TRIGGER_THRESHOLD
            rt_pressed = rt_val > self.TRIGGER_THRESHOLD

            if lt_pressed and not self.prev_lt:
                self._play("TRIGGER", trigger_volume=0.4 + lt_val * 0.6)
            elif not lt_pressed and self.prev_lt:
                self._play("TRIGGER", is_release=True)
            self.prev_lt = lt_pressed

            if rt_pressed and not self.prev_rt:
                self._play("TRIGGER", trigger_volume=0.4 + rt_val * 0.6)
            elif not rt_pressed and self.prev_rt:
                self._play("TRIGGER", is_release=True)
            self.prev_rt = rt_pressed

    # ================================================================
    # 预设系统
    # ================================================================
    def _load_presets(self):
        """加载预设文件，不存在则创建默认三组预设"""
        defaults = []
        for i in range(3):
            preset = {}
            for gk in GROUP_ORDER:
                sound = DEFAULT_SOUNDS.get(gk, "无音效") if i == 0 else "无音效"
                preset[gk] = {"sound": sound, "release_sound": "无音效", "volume": VOL_DEFAULT}
            defaults.append(preset)

        if os.path.exists(PRESETS_FILE):
            try:
                with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list) and len(data) == 3:
                    return data
            except (json.JSONDecodeError, KeyError):
                pass
        return defaults

    def _save_presets(self):
        with open(PRESETS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.presets, f, ensure_ascii=False, indent=2)

    def _auto_save(self):
        """自动保存当前预设配置"""
        preset = {}
        for gk in GROUP_ORDER:
            preset[gk] = {
                "sound": self.sound_var[gk].get(),
                "release_sound": self.release_sound_var[gk].get(),
                "volume": self.volume_bar[gk].get(),
            }
        self.presets[self.active_preset] = preset
        self._save_presets()

    def _switch_preset(self, idx):
        """切换到指定预设并加载其配置"""
        self.active_preset = idx
        self._highlight_preset()
        preset = self.presets[idx]
        for gk in GROUP_ORDER:
            cfg = preset.get(gk, {})
            sound = cfg.get("sound", "无音效")
            if sound not in self.wav_files:
                sound = self.wav_files[0] if self.wav_files else "无音效"
            self.sound_var[gk].set(sound)
            rel = cfg.get("release_sound", "无音效")
            if rel not in self.wav_files:
                rel = "无音效"
            self.release_sound_var[gk].set(rel)
            self.volume_bar[gk].set(cfg.get("volume", VOL_DEFAULT))
            # 预加载音效
            self._on_sound_change(gk)

    def _highlight_preset(self):
        """高亮当前预设按钮"""
        for i, btn in enumerate(self.preset_btns):
            if i == self.active_preset:
                btn.configure(text=f"▶ 预设 {i+1}")
            else:
                btn.configure(text=f"   预设 {i+1}")

    def _on_close(self):
        self._save_presets()
        pygame.quit()
        self.root.destroy()


# ============================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = ControllerApp(root)
    root.mainloop()

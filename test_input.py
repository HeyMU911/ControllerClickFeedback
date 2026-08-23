"""
第二阶段：手柄输入 + 音效反馈测试
- 按手柄按钮 → 播放对应音效
- 按键盘 ESC → 退出程序
"""

import pygame
import sys
import os

# ============================================================
# 路径配置
# ============================================================
BASE_DIR = os.path.dirname(__file__)
SOUNDS_DIR = os.path.join(BASE_DIR, "sounds")

# ============================================================
# XInput 标准按键映射 (Xbox 布局)
# ============================================================
BUTTON_NAMES = {
    0:  "A",
    1:  "B",
    2:  "X",
    3:  "Y",
    4:  "LB",
    5:  "RB",
    6:  "BACK",
    7:  "START",
    8:  "L3 (左摇杆按下)",
    9:  "R3 (右摇杆按下)",
}

HAT_DIRECTIONS = {
    (0, 1):   "UP",
    (0, -1):  "DOWN",
    (-1, 0):  "LEFT",
    (1, 0):   "RIGHT",
    (1, 1):   "UP+RIGHT",
    (-1, 1):  "UP+LEFT",
    (1, -1):  "DOWN+RIGHT",
    (-1, -1): "DOWN+LEFT",
}

# 扳机轴索引（飞智 APEX5 Wireless 实测：轴4=LT, 轴5=RT）
TRIGGER_AXIS_LT = 4
TRIGGER_AXIS_RT = 5
TRIGGER_THRESHOLD = 0.1  # 扳机按下阈值
DEBOUNCE_MS = 50          # 按钮去抖时间（毫秒）

# ============================================================
# 按键 → 音效 绑定表
# ============================================================
# A/B/X/Y 各绑定一个真实按键音
BUTTON_SOUND_MAP = {
    0: "IceCreamKeyboard_final2.wav",   # A
    1: "LogicMouse_final2.wav",         # B
    2: "RazerMouse_final2.wav",         # X
    3: "cheeryKeyboardTea_final2.wav",  # Y
}
# 肩键 / 十字键 用相同音效
SOUND_SHOULDER_FILE = "cheeryKeyboardTea_final2.wav"
SOUND_DPAD_FILE = "RazerMouse_final2.wav"
SOUND_TRIGGER_AXES = {TRIGGER_AXIS_LT, TRIGGER_AXIS_RT}


def init_pygame():
    """初始化 pygame、手柄、混音器"""
    pygame.init()
    pygame.joystick.init()

    # 匹配 WAV 采样率（48000Hz），避免重采样失真
    pygame.mixer.init(frequency=48000, size=-16, channels=2, buffer=256)
    mixer_info = pygame.mixer.get_init()
    print(f"[音频] 初始化完成 (freq={mixer_info[0]}Hz, channels={mixer_info[2]})")

    count = pygame.joystick.get_count()
    if count == 0:
        print("[等待] 未检测到手柄，请连接后重试...")
        return None

    print(f"\n检测到 {count} 个手柄:\n")
    for i in range(count):
        js = pygame.joystick.Joystick(i)
        js.init()
        name = js.get_name()
        print(f"  [{i}] {name}")
        print(f"      按钮数: {js.get_numbuttons()}")
        print(f"      轴数:   {js.get_numaxes()}")
        print(f"      帽子数: {js.get_numhats()}")

    js = pygame.joystick.Joystick(0)
    js.init()
    print(f"\n[已连接] 使用手柄: {js.get_name()}")
    return js


def load_sounds():
    """预加载所有音效文件"""
    sounds = {}

    # 加载每个按钮专属音效
    for btn_id, filename in BUTTON_SOUND_MAP.items():
        path = os.path.join(SOUNDS_DIR, filename)
        if os.path.exists(path):
            sounds[btn_id] = pygame.mixer.Sound(path)
            print(f"[音效] 按钮 {BUTTON_NAMES.get(btn_id, btn_id)} -> {filename}")

    # 加载肩键 / 十字键 / 扳机 共用音效
    for key, filename in [("shoulder", SOUND_SHOULDER_FILE),
                           ("dpad", SOUND_DPAD_FILE)]:
        path = os.path.join(SOUNDS_DIR, filename)
        if os.path.exists(path):
            sounds[key] = pygame.mixer.Sound(path)

    return sounds


def play_sound(sounds, key, volume=1.0):
    """播放音效（同一声源不叠加，新播放会打断旧播放）"""
    if key is not None and key in sounds:
        sounds[key].stop()   # 先停掉之前的播放，防止叠加
        ch = sounds[key].play()
        if ch:
            ch.set_volume(volume)


def get_button_sound_key(btn):
    """根据按钮编号返回音效键名（按钮ID 或 'shoulder'/'dpad'）"""
    if btn in BUTTON_SOUND_MAP:
        return btn
    if btn in {4, 5}:   # LB/RB
        return "shoulder"
    return None


def normalize_trigger(raw_value):
    """扳机原始值 (-1~1) → 归一化 (0~1)"""
    return (raw_value + 1.0) / 2.0


def main():
    js = init_pygame()
    if js is None:
        pygame.quit()
        return

    sounds = load_sounds()
    if not sounds:
        print("[错误] 没有可用的音效文件，请先运行 generate_sounds.py")
        pygame.quit()
        return

    # 状态记录
    prev_hat = (0, 0)
    prev_lt_pressed = False
    prev_rt_pressed = False

    clock = pygame.time.Clock()

    print("\n" + "=" * 50)
    print("  按键 → 音效 绑定:")
    for btn_id, filename in BUTTON_SOUND_MAP.items():
        name = BUTTON_NAMES.get(btn_id, f"BTN_{btn_id}")
        print(f"    {name:<12} -> {filename}")
    print(f"    {'LB/RB':<12} -> {SOUND_SHOULDER_FILE}")
    print(f"    {'DPAD':<12} -> {SOUND_DPAD_FILE}")
    print(f"    {'LT/RT':<12} -> {SOUND_SHOULDER_FILE} (+力度音量)")
    print("  按 Ctrl+C    → 退出程序")
    print("=" * 50 + "\n")

    # 去抖状态：记录每个按键的上次触发时间
    last_btn_time = {}    # button_id → 上次触发 tick (ms)
    last_hat_time = 0     # 十字键上次触发 tick (ms)

    try:
        while True:
            clock.tick(500)  # 500Hz 轮询

            for event in pygame.event.get():
                # --- 手柄按钮按下 → 去抖 + 播放音效 ---
                if event.type == pygame.JOYBUTTONDOWN:
                    btn = event.button
                    now = pygame.time.get_ticks()

                    # 去抖：同一按钮在 DEBOUNCE_MS 内忽略
                    if btn in last_btn_time and (now - last_btn_time[btn]) < DEBOUNCE_MS:
                        continue
                    last_btn_time[btn] = now

                    name = BUTTON_NAMES.get(btn, f"BUTTON_{btn}")
                    skey = get_button_sound_key(btn)
                    if skey is not None:
                        play_sound(sounds, skey)
                        print(f"[按下] {name}  🔊")
                    else:
                        print(f"[按下] {name}")

                # --- 按钮释放 ---
                elif event.type == pygame.JOYBUTTONUP:
                    btn = event.button
                    name = BUTTON_NAMES.get(btn, f"BUTTON_{btn}")
                    print(f"[释放] {name}")

                # --- 手柄热插拔 ---
                elif event.type == pygame.JOYDEVICEADDED:
                    idx = event.device_index
                    print(f"[事件] 手柄已连接 (ID: {idx})")
                    try:
                        new_js = pygame.joystick.Joystick(idx)
                        new_js.init()
                        print(f"[已连接] {new_js.get_name()}")
                        js = new_js
                    except Exception as e:
                        print(f"[警告] 初始化手柄失败: {e}")

                elif event.type == pygame.JOYDEVICEREMOVED:
                    print(f"[事件] 手柄已断开 (ID: {event.instance_id})")
                    js = None

            # --- 十字键 状态轮询 + 去抖 ---
            if js and js.get_numhats() > 0:
                hat = js.get_hat(0)
                if hat != prev_hat:
                    now = pygame.time.get_ticks()
                    if hat != (0, 0):
                        # 去抖：距上次十字键触发不足 DEBOUNCE_MS 则忽略
                        if (now - last_hat_time) >= DEBOUNCE_MS:
                            direction = HAT_DIRECTIONS.get(hat, str(hat))
                            play_sound(sounds, "dpad")
                            print(f"[十字键] {direction}  🔊")
                            last_hat_time = now
                    prev_hat = hat

            # --- LT / RT 扳机 状态轮询（+ 力度音量） ---
            if js and js.get_numaxes() > max(TRIGGER_AXIS_LT, TRIGGER_AXIS_RT):
                lt_raw = js.get_axis(TRIGGER_AXIS_LT)
                rt_raw = js.get_axis(TRIGGER_AXIS_RT)
                lt_val = normalize_trigger(lt_raw)
                rt_val = normalize_trigger(rt_raw)

                lt_pressed = lt_val > TRIGGER_THRESHOLD
                rt_pressed = rt_val > TRIGGER_THRESHOLD

                if lt_pressed and not prev_lt_pressed:
                    vol = 0.4 + lt_val * 0.6
                    play_sound(sounds, "shoulder", volume=min(vol, 1.0))
                    print(f"[扳机] LT 按下 (力度: {lt_val:.2f}, 音量: {vol:.2f})  🔊")
                elif not lt_pressed and prev_lt_pressed:
                    print(f"[扳机] LT 释放")

                if rt_pressed and not prev_rt_pressed:
                    vol = 0.4 + rt_val * 0.6
                    play_sound(sounds, "shoulder", volume=min(vol, 1.0))
                    print(f"[扳机] RT 按下 (力度: {rt_val:.2f}, 音量: {vol:.2f})  🔊")
                elif not rt_pressed and prev_rt_pressed:
                    print(f"[扳机] RT 释放")

                prev_lt_pressed = lt_pressed
                prev_rt_pressed = rt_pressed

    except KeyboardInterrupt:
        print("\n[退出] Ctrl+C 中断")

    finally:
        pygame.quit()


if __name__ == "__main__":
    main()

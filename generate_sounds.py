"""
生成 4 个占位测试音效 WAV 文件。
用户后续可替换为真实音效。
"""
import wave
import struct
import math
import os

SOUNDS_DIR = os.path.join(os.path.dirname(__file__), "sounds")


def generate_click_wav(filepath, freq=3000, duration_ms=40, volume=0.8):
    """生成一个短促的咔哒声音效"""
    sample_rate = 44100
    num_samples = int(sample_rate * duration_ms / 1000)
    
    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1)        # 单声道
        wf.setsampwidth(2)        # 16-bit
        wf.setframerate(sample_rate)
        
        for i in range(num_samples):
            t = i / sample_rate
            # 快速衰减包络：前10%攻击，后90%指数衰减
            if t < 0.002:
                envelope = t / 0.002  # 快速起音
            else:
                decay = (t - 0.002) / (duration_ms / 1000 - 0.002)
                envelope = math.exp(-decay * 6)  # 快速衰减
            
            # 正弦波 + 少量噪声模拟机械感
            sine = math.sin(2 * math.pi * freq * t)
            noise = (hash((i, 42)) % 1000) / 1000.0 * 0.3  # 确定性"噪声"
            sample = (sine * 0.7 + noise * 0.3) * envelope * volume
            
            # 16-bit PCM
            sample_int = max(-32767, min(32767, int(sample * 32767)))
            wf.writeframes(struct.pack("<h", sample_int))
    
    print(f"  已生成: {os.path.basename(filepath)} ({freq}Hz, {duration_ms}ms)")


def main():
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    print("生成占位音效文件...\n")

    # 1. ABXY 按键声 — 较高频、短促
    generate_click_wav(
        os.path.join(SOUNDS_DIR, "click_abxy.wav"),
        freq=3200, duration_ms=35, volume=0.7
    )

    # 2. 十字键 — 中频
    generate_click_wav(
        os.path.join(SOUNDS_DIR, "click_dpad.wav"),
        freq=2200, duration_ms=35, volume=0.7
    )

    # 3. LB/RB 肩键 — 中低频
    generate_click_wav(
        os.path.join(SOUNDS_DIR, "click_shoulder.wav"),
        freq=1500, duration_ms=40, volume=0.7
    )

    # 4. LT/RT 扳机 — 低频、稍长（模拟扳机行程）
    generate_click_wav(
        os.path.join(SOUNDS_DIR, "click_trigger.wav"),
        freq=600, duration_ms=60, volume=0.8
    )

    print(f"\n完成！4 个音效文件已保存到: {SOUNDS_DIR}")
    print("后续替换为真实音效后，保持相同文件名即可。")


if __name__ == "__main__":
    main()

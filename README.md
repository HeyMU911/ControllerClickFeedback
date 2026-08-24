# 手柄按键音效 ControllerClickFeedback

给游戏手柄加上"机械键盘/鼠标"般的按键音效反馈 —— 按下手柄按键时,实时播放对应的点击音效,让无声的按键"听"起来。

> 项目初衷:手柄按键没有机械键盘那种清脆的敲击声,玩起来总感觉少了点什么。本工具检测手柄输入,为不同按键组播放自定义音效,模拟机械手感。

## ✨ 功能特性

- 🎮 **四组按键独立配置**:ABXY、十字键(DPAD)、肩键(LB/RB)、扳机(LT/RT),每组可单独选择音效或设为无音效
- 🔊 **按下 / 释放双音效**:每组按键可为"按下"和"释放"分别绑定不同音效(如机械轴下压声与回弹声)
- 🎚 **独立音量调节**:每组按键音量 0% ~ 3000%,超过 100% 时通过采样级放大实现,不会失真削波
- 💾 **三组预设**:一键切换预设,所有修改自动保存,重启后配置不丢失
- 🔌 **手柄热插拔**:运行中拔插手柄自动检测连接状态
- 🎯 **扳机力度感应**:LT/RT 按得越重,音效音量越大(模拟真实扳机行程)
- ⚡ **低延迟**:50ms 去抖防误触,48kHz 混音器,8 声道并发

## 📸 界面说明

程序窗口按四组按键分为四个卡片,每组包含:

| 配置项 | 说明 |
| ------ | ---- |
| 按下 | 按键按下时播放的音效(下拉选择,`无音效` 表示不播放) |
| 释放 | 按键释放时播放的音效 |
| 音量 | 独立音量条,可点击跳转或拖拽调节,最大 3000% |

窗口顶部显示手柄连接状态,以及三个预设切换按钮(▶ 标记当前预设)。

## 🚀 快速开始

### 环境要求

- Windows(建议,已测试 Win10)
- Python 3.8+
- 一个 XInput / DirectInput 手柄(已测试:飞智 APEX5 Wireless)

### 安装依赖

```bash
pip install pygame numpy scipy
```

> `tkinter` 为 Python 自带标准库,无需额外安装。

### 运行

```bash
python controller_ui.py
```

程序启动后会自动检测手柄,插入手柄即可开始按键"听声"。

### 命令行测试版

```bash
python test_input.py
```

纯终端版本,打印所有按键事件与音效触发信息,可用于排查手柄按键映射问题,按 `Ctrl+C` 退出。

## 📦 打包为 exe

项目已配置好 [PyInstaller](https://pyinstaller.org/) 打包脚本:

```bash
pip install pyinstaller
pyinstaller ControllerSound_v1.0.spec
```

打包产物输出到 `dist/ControllerSound_v1.0/`(无控制台窗口,双击即可运行)。

## 🎵 自定义音效

将任意 `.wav` 文件放入 `sounds/` 目录,重启程序后即可在下拉菜单中选择。程序会自动扫描该目录。

- 建议使用 48kHz 采样率,避免重采样失真
- 按下 / 释放分离的音效文件常命名为 `xxx_part1.wav`(按下)、`xxx_part2.wav`(释放)
- 没有音效文件时,可运行 `python generate_sounds.py` 生成 4 个占位"咔哒"音效测试效果

## 📁 项目结构

```
ControllerClickFeedback/
├── controller_ui.py          # 主程序(GUI 界面 + 手柄检测 + 音效播放)
├── test_input.py             # 命令行测试版(按键事件打印调试)
├── generate_sounds.py        # 生成占位测试音效
├── presets.json              # 预设配置文件(程序自动生成/更新)
├── sounds/                   # 音效文件目录(自定义音效放这里)
├── ControllerSound_v1.0.spec # PyInstaller 打包脚本
└── dist/                     # 打包产物(exe)
```

## ⚙️ 按键映射

采用 XInput 标准按键编号(Xbox 布局):

| 分组 | 按键 | 说明 |
| ---- | ---- | ---- |
| ABXY | A / B / X / Y | 按钮编号 0-3 |
| DPAD | ↑ ↓ ← → | 帽子开关(hat),支持八方向 |
| SHOULDER | LB / RB | 按钮编号 4-5 |
| TRIGGER | LT / RT | 轴 4 / 轴 5,支持力度感应音量 |

## 🛠 技术实现

- **GUI**:`tkinter`,自定义 Canvas 音量条(点击跳转 + 拖拽)
- **手柄输入**:`pygame` 事件轮询(50ms 定时器驱动)+ 状态轮询(十字键/扳机),50ms 去抖
- **音频播放**:`pygame.mixer`(48kHz / 16bit / 双声道 / 8 声道)
- **高音量放大**:音量 >100% 时用 `numpy` 重采样放大原始波形(`np.clip` 防削波)后经 `pygame.sndarray` 播放
- **热插拔**:监听 `JOYDEVICEADDED` / `JOYDEVICEREMOVED` 事件
- **配置持久化**:所有改动实时写入 `presets.json`,退出时再次保存

## 📝 许可

MIT License

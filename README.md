# 小桌宠 Desktop Pet

一个 Windows 桌面悬浮组件（desktop overlay widget），实时统计并展示：

- 今日键盘按键次数
- 今日鼠标点击次数
- CPU / 内存 / GPU 使用率
- C 盘剩余空间

程序常驻系统托盘，关闭桌面组件时隐藏到托盘而非退出。数据按天持久化为 JSON 文件，存放在程序目录下的 `data/`。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 运行（带终端，用于调试）
python main.py

# 运行（无终端，日常使用）
pythonw main.pyw
# 或直接双击 main.pyw

# 打包单文件 EXE
python build.py
# 输出: dist/DesktopPet.exe
```

**设计原则：EXE 优先。** 打包出的 `dist/DesktopPet.exe` 是面向用户的最终交付物，所有功能必须通过 GUI 可用；`python` / `pythonw` 仅用于开发调试。

## 功能

- **桌面悬浮窗**：无边框、置顶、半透明圆角背景，可拖动、可边缘拖拽调整大小；启用置顶时会同步 Windows 原生 TOPMOST 层级，窗口恢复显示后也会自动校准
- **每日 0 点自动刷新**：应用常驻跨过午夜时计数自动归零；日期与计数以线程安全快照交接，午夜定时器、周期保存和新日第一次输入共同兜底，前一天数据完整落盘（无需重启）
- **托盘菜单**：隐藏/显示组件、打开设置菜单、退出
- **设置窗口**（托盘 → 菜单）：
  - 显示项目开关（键盘 / 鼠标 / CPU / 内存 / GPU / 磁盘）
  - 字体大小（5 档吸附：8 / 12 / 16 / 20 / 24）
  - 布局模式（竖向列表 / 横向单行）
  - 外观（不透明度、字体颜色预设 + 自定义）
  - 窗口位置（六向吸附）、窗口置顶、锁定窗口（点击穿透）、开机启动
- **日历视图**（设置窗口 → 日历 Tab）：按月查看每日键盘 / 鼠标统计

## 目录结构

```
main.py                      # 入口：QApplication、组件装配、信号接线
main.pyw                     # 无控制台启动器（pythonw）
build.py                     # PyInstaller 打包脚本 → dist/DesktopPet.exe
requirements.txt             # 依赖
config.json                  # 用户配置（首次修改后生成）
data/                        # 每日统计数据 data/YYYY-MM-DD.json
resources/                   # 图标等资源（icon.png 首次运行自动生成）
src/
  desktop_widget.py          # 无边框置顶悬浮窗：拖拽、边缘缩放、布局渲染
  system_tray.py             # 系统托盘图标 + 右键菜单
  menu_window.py             # 设置 Tab + 日历 Tab 的选项卡窗口
  calendar_widget.py         # 月度日历网格，每日 K:/M: 计数
  input_hooks.py             # pynput 全局键盘/鼠标监听 → count_updated 信号
  stats_collector.py         # QThread 轮询 psutil + GpuMonitor → stats_updated 信号
  gpu_monitor.py             # GPU 使用率：WMI → nvidia-smi → 0.0 降级链
  data_manager.py            # 每日 JSON 持久化（原子写入）
  config_manager.py          # config.json 深合并默认值 + 点路径访问
  startup_manager.py         # 开机启动（HKCU Run 键，仅打包 EXE 生效）
  icon_generator.py          # Pillow 生成多尺寸图标
  utils.py                   # 路径解析（兼容 PyInstaller）
```

## 数据文件

- `data/YYYY-MM-DD.json` — 每日统计，格式：

  ```json
  {"date": "2026-07-26", "keyboard_count": 4821, "mouse_count": 1347}
  ```

- `config.json` — 用户设置（首次修改时创建，非首次运行时）
- `resources/icon.png` — 首次运行自动生成

## 已知注意点

- `pynput` 全局钩子在部分 Windows 配置下可能需要管理员权限
- 无 NVIDIA 独立显卡时 GPU 显示 0%（自动降级，不影响其他功能）
- 当前未强制单实例运行，允许同时开启多个

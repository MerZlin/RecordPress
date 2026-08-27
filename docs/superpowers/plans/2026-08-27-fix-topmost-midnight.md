# 窗口置顶与跨午夜计数修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 根治桌面悬浮窗偶发失去置顶以及应用常驻跨午夜后继承昨日计数的问题，并生成验证通过的单文件 EXE。

**Architecture:** `DesktopWidget` 在保留 Qt 窗口标志的同时，通过 Win32 `SetWindowPos` 校准原生 TOPMOST 层级，并在显示路径重新同步。`InputHooks` 在锁内完成换日、封存旧日快照并放入待持久化队列，pynput 回调只发 Qt 通知；主线程统一排空队列写盘，避免跨线程磁盘 I/O及旧日快照丢失。

**Tech Stack:** Python 3、PySide6、pynput、unittest、Win32 User32、PyInstaller

**Spec:** `SPEC.md`

## Global Constraints

- 最终交付物是 `dist/DesktopPet.exe`，所有功能必须在无控制台 EXE 中工作。
- pynput 回调不得执行磁盘 I/O；跨线程通知使用 Qt Signal。
- 每日数据继续以 `data/YYYY-MM-DD.json` 原子写入，不改变现有格式。
- 不引入新第三方依赖，不修改项目技术栈。
- 保留工作区已有未提交修改，不回滚用户工作。

---

### Task 1: 建立回归测试

**Files:**
- Create: `tests/test_regressions.py`

**Interfaces:**
- Consumes: `DesktopWidget.set_always_on_top(bool)`、`InputHooks._on_key_press()`、`InputHooks.rollover_if_needed()`
- Produces: 可重复验证原生置顶重申和输入线程换日快照不丢失的 unittest 测试

- [x] **Step 1: 编写置顶回归测试**

创建离屏 `QApplication` 和临时配置，mock Win32 `SetWindowPos`，在 Qt 的 `WindowStaysOnTopHint` 已存在时调用 `set_always_on_top(True)`，断言仍会重申原生 TOPMOST；显示窗口时也断言会再次校准。

- [x] **Step 2: 编写跨午夜回归测试**

使用不启动真实 pynput 线程的假监听器和可控日期，令旧日计数为键盘 12、鼠标 7，模拟新日第一次键盘输入；断言旧日快照进入待持久化队列，新日内存计数为键盘 1、鼠标 0，并发出换日通知。

- [x] **Step 3: 运行测试验证 RED**

Run: `python -m unittest tests.test_regressions -v`

Expected: 置顶测试因未调用 `SetWindowPos` 失败；跨午夜测试因没有可靠的待持久化队列/通知失败。

### Task 2: 修复原生置顶状态

**Files:**
- Modify: `src/desktop_widget.py`
- Test: `tests/test_regressions.py`

**Interfaces:**
- Consumes: `general.always_on_top` 配置、Qt window flags、Windows HWND
- Produces: `_sync_native_topmost(bool)`；`set_always_on_top(bool)` 每次都校准原生层级；`showEvent` 恢复显示时再次校准

- [x] **Step 1: 实现 Win32 TOPMOST 同步**

增加 `HWND_TOPMOST`、`HWND_NOTOPMOST`、`SWP_NOMOVE`、`SWP_NOSIZE`、`SWP_NOACTIVATE` 常量，用 `SetWindowPos` 只调整 Z 序，不移动、不缩放、不抢焦点；非 Windows 环境保留 Qt 行为。

- [x] **Step 2: 修正提前返回逻辑**

Qt flag 无需变化时不再直接结束整个方法，仍执行原生层级校准；flag 变化导致句柄重建后先恢复显示，再同步 TOPMOST 和点击穿透状态。

- [x] **Step 3: 显示时重新校准**

`showEvent` 根据配置调用 `set_always_on_top`，覆盖从托盘恢复或系统层级变化后的偶发失效。

- [x] **Step 4: 运行置顶测试验证 GREEN**

Run: `python -m unittest tests.test_regressions.TopmostRegressionTests -v`

Expected: 全部通过。

### Task 3: 修复跨午夜换日竞态

**Files:**
- Modify: `src/input_hooks.py`
- Modify: `main.py`
- Test: `tests/test_regressions.py`

**Interfaces:**
- Consumes: `InputHooks.rollover_if_needed()`、周期 flush、午夜 one-shot timer、pynput callbacks
- Produces: `rollover_detected = Signal()`、`drain_rollovers() -> list[dict]`、主线程 `_handle_rollover()` 统一保存旧日快照

- [x] **Step 1: 在 InputHooks 内建立待持久化队列**

换日时在同一把锁内封存旧日日期与计数、清零新日计数、把快照追加到队列；锁外刷新 UI。`drain_rollovers()` 在锁内复制并清空队列。

- [x] **Step 2: 输入回调只发通知**

键盘/鼠标回调检测到换日后发出 `rollover_detected`，不直接写盘；随后将本次输入计入新日。

- [x] **Step 3: 主线程排空并保存**

`main.py` 连接 `rollover_detected` 到 `_handle_rollover()`；该方法先兜底检测日期，再排空所有快照并逐个调用 `DataManager.save_day()`。退出前 `_do_flush()` 也走同一路径，避免排队信号尚未处理时丢数据。

- [x] **Step 4: 运行跨午夜测试验证 GREEN**

Run: `python -m unittest tests.test_regressions.MidnightRolloverRegressionTests -v`

Expected: 全部通过。

### Task 4: 文档、全量验证与 EXE 打包

**Files:**
- Modify: `README.md`
- Modify: `LOG.md`
- Modify: `LOG-INDEX.md`
- Modify: `docs/grill-2026-08-27-置顶与跨午夜修复.md`
- Build: `dist/DesktopPet.exe`

**Interfaces:**
- Consumes: 修复后的源代码和回归测试
- Produces: 可追溯变更记录、测试证据、可启动的单文件 EXE

- [x] **Step 1: 运行完整验证**

Run: `python -m unittest discover -s tests -v`

Run: `python -m py_compile main.py main.pyw src/*.py tests/*.py`

Expected: 所有测试通过，编译检查退出码为 0。

- [x] **Step 2: GUI 源码启动冒烟验证**

用独立进程启动 `python main.py`，等待窗口和托盘初始化后检查进程仍存活，再正常终止测试进程；预期无启动异常。

- [x] **Step 3: 更新项目文档**

把根因、修复策略、涉及文件和实际验证结果写入 `LOG.md`，更新 `LOG-INDEX.md` 与 `README.md`。

- [x] **Step 4: 构建并验证 EXE**

Run: `python build.py`

Expected: PyInstaller 退出码为 0，生成非空的 `dist/DesktopPet.exe`；启动该 EXE 后进程保持运行且无控制台窗口，随后终止验证实例。
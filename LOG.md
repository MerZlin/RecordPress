# LOG — 施工变更记录

> 每次施工前追加草稿，执行后固化。格式：`[日期] 变更行为 / 决策原因 / 涉及文件（简要）`。
> 每条以 8 位短哈希标识，配合 LOG-INDEX.md 检索。

---

## [2026-08-27] 修复：窗口原生置顶与跨午夜计数竞态（0304fe34）

**变更行为**：
- `DesktopWidget` 增加 Win32 `SetWindowPos(HWND_TOPMOST/HWND_NOTOPMOST)` 原生层级同步；即使 Qt 的 `WindowStaysOnTopHint` 已存在也会重新校准，并在 `showEvent`（含托盘恢复）再次同步，不移动、不缩放、不抢焦点
- `InputHooks` 在同一把锁内封存旧日日期与计数、清零新日计数，并通过待持久化队列交给 Qt 主线程保存；pynput 回调只通知，不直接执行磁盘 I/O
- 周期保存改为读取“统计日期 + 键盘数 + 鼠标数”的原子快照，再按快照日期写盘，消除日期检查与 `save_today()` 之间跨过 00:00 的极小竞态
- 新增 4 条回归测试，覆盖置顶重复校准、窗口恢复校准、午夜后第一次输入保存昨日快照，以及周期保存使用计数所属日期
- 修复 `build.py` 在 CP1252 控制台打印中文绝对路径导致构建主体成功但脚本错误退出的问题，收尾输出改为 ASCII 相对路径

**决策原因**：Qt 置顶 flag 只能表达期望状态，Windows 原生 Z 序仍可能被其他窗口/句柄生命周期扰动；原逻辑在 flag 未变化时提前返回，无法自愈。跨午夜方面，pynput 线程可能先于午夜定时器完成换日，若旧日快照只作为返回值存在就会丢失；此外保存时重新读取系统日期会留下跨 00:00 的命名竞态。因此采用原生层级幂等校准 + 线程安全日期快照交接的统一方案，而不是继续添加分支补丁。

**涉及文件**：`main.py`、`build.py`、`src/desktop_widget.py`、`src/input_hooks.py`、`src/data_manager.py`、`tests/test_regressions.py`、`README.md`、`LOG.md`、`LOG-INDEX.md`、`docs/grill-2026-08-27-置顶与跨午夜修复.md`、`docs/superpowers/plans/2026-08-27-fix-topmost-midnight.md`

**验证**：
- `python -m unittest discover -s tests -v` → 4 项全部通过
- `python -m py_compile ...` → 项目 Python 文件全部通过
- 跨线程诊断：`rollover_detected` 从工作线程发出后，接收器在线程 ID 对应的 Qt 主线程执行
- Windows 原生实测：置顶开启后 `WS_EX_TOPMOST=true`，关闭后为 `false`，HWND 保持不变
- 源码 GUI 冒烟：`python main.py` 启动后持续运行 3 秒，无提前退出
- `python build.py` → PyInstaller 6.20.0 构建成功且退出码为 0；生成 `dist/DesktopPet.exe`（62,646,010 字节 / 59.74 MB，SHA256 `4E83253B1F890691018176C17E8A0D4646FFE976D112EB783A88D5B865FD77EC`）
- 隔离目录 EXE 冒烟：打包产物启动后持续运行 10 秒，无提前退出；测试副本及运行数据已清理

**状态**：代码、测试、源码冒烟、打包与 EXE 冒烟均已完成；仍建议用户按下方验收指引实际观察一次跨午夜行为。

---
## [2026-08-04] 修复：跨天 0 点自动刷新计数

**变更行为**：
- `InputHooks` 新增统计日期 `_stat_date` 与 `rollover_if_needed()`：跨天时原子封存旧计数、归零内存计数、emit `count_updated` 刷新 UI；pynput 回调开头也调用，兜底休眠唤醒
- `DataManager` 新增 `save_day(iso_date, ...)` 通用写盘，`save_today` 委托之；跨天时把旧日期最后一段增量补写前一天文件
- `main.py` 新增午夜一次性 QTimer（精确调度到下一个 0 点），触发 `_handle_rollover` 并重新调度；`_do_flush` 开头兜底检测跨天

**决策原因**：用户反馈应用常驻跨过 0 点后，计数被带到第二天而非归零。根因为计数变量无跨天重置机制，且 flush 按当天日期写盘，0 点后首轮 flush 会把累计值写入新日期文件。

**涉及文件**：`main.py`、`src/input_hooks.py`、`src/data_manager.py`、`README.md`、`LOG.md`、`LOG-INDEX.md`

**验证**：
- `python -m py_compile main.py src/input_hooks.py src/data_manager.py` → COMPILE_OK
- 离线单测 3 项通过（mock pynput + 模拟跨天）：`save_day`/`save_today` 写盘、rollover 归零封存与 UI 信号、flush 集成路径（昨天文件保留旧值、今天从 0 起）
- GUI 启动 6 秒无崩溃、无 stderr

---

## [2026-08-04] 项目全面规范化（c385ca39）

**变更行为**：
- 建立文档体系：新增 `README.md`、`SPEC.md`、`LOG.md`、`LOG-INDEX.md`
- 修正 `CLAUDE.md` 与代码不一致之处（GPU 降级链描述、Signal Flow 补全、收录 `startup_manager.py`、轮询间隔配置说明）
- 清理死代码：删除 `system_tray.py::_on_exit_action`（从未接线）、`menu_window.py::set_calendar_widget` / `_calendar_tab`（从未调用）、`menu_window.py` 未使用的 `set_startup` 局部导入及残留注释
- 消除跨模块私有访问：`menu_window.py` 暴露公共属性 `settings_tab`，`main.py` 改经该属性接线
- 修复重复收尾：`main.py::_on_exit` 仅调用 `quit()`，最终 flush/清理统一由 `aboutToQuit → _on_about_to_quit` 执行（此前 flush 会执行两次）
- 接通配置项：`general.stats_poll_interval_ms` 传入 `StatsCollector`（此前该配置存在但从未生效，硬编码 1000ms；下限钳制 200ms）
- 去重与健壮化：
  - `data_manager.py::load_today` 委托 `load_day`（消除重复实现）
  - `data_manager.py::list_available_dates` 用 `date.fromisoformat` 校验文件名，替代魔法数字 `len(fname) == 15`
  - `desktop_widget.py` `_separators` 统一在 `_rebuild_layout` 初始化，删除 `hasattr` 防御；`mode` 局部变量合并为 `self._current_mode`
  - `config_manager.py::get` 删除恒真条件 `i < len(parts)`
  - `input_hooks.py::_on_mouse_click` 未使用参数加下划线前缀
  - `main.pyw` 导入顺序按字母序

**决策原因**：用户要求对项目做全面规范化（文档体系 + 代码规范化）；清理死代码、消除重复与私有访问、接通失效配置，均为不改行为的低风险整理。

**涉及文件**：`README.md`（新增）、`SPEC.md`（新增）、`LOG.md`（新增）、`LOG-INDEX.md`（新增）、`CLAUDE.md`、`main.py`、`main.pyw`、`src/system_tray.py`、`src/menu_window.py`、`src/desktop_widget.py`、`src/input_hooks.py`、`src/config_manager.py`、`src/data_manager.py`

**验证**：`python -m py_compile` 全部 15 个 .py 文件通过（COMPILE_OK）。未做运行时 GUI 冒烟测试，待用户确认。

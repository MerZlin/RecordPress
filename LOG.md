# LOG — 施工变更记录

> 每次施工前追加草稿，执行后固化。格式：`[日期] 变更行为 / 决策原因 / 涉及文件（简要）`。
> 每条以 8 位短哈希标识，配合 LOG-INDEX.md 检索。

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

# 运行与维护手册

## 1. 开始任何工作前

```powershell
git status --short
git diff --stat
npm run check
```

不要清理、重置或覆盖现有脏工作树。先识别哪些变更属于当前任务，哪些属于用户已有工作。

## 2. 全量数据处理

```powershell
python backend/main.py
python backend/scripts/audit_extraction.py
```

约束：

- 原始 Excel 只读。
- 全量提取成功后才允许处理失效输出。
- 身份冲突不得按文件名强行合并。
- 审计必须独立于生产提取函数。

## 3. 增量更新

增量流程由 `backend/main.py` 和 `backend/core/file_tracker.py` 管理：

- 使用文件哈希识别新增或修改来源。
- 对已删除来源执行受控移除。
- 更新患者级 JSON 和处理索引。
- 记录 schema、流水线版本和来源指纹。

更新后检查隔离记录和匹配报告，不要只看程序退出码。

## 4. 更新公开演示

1. 从内部数据生成或更新匿名演示 bundle。
2. 确认输入路径是 `dashboard_ui/demo_data/data_bundle.js`。
3. 运行 `npm run check`。
4. 在新临时目录生成发布包。
5. 查看 `privacy_audit.json`，不得只依赖终端中的 PASS 字样。
6. 通过预览或生产部署验证 UI。
7. 更新总控和变更日志。

## 5. 常见故障

### 构建目录已存在

原因：发布构建器为防止混入旧文件而拒绝复用目录。  
处理：确认目标是生成物后再清理或选择新的临时输出目录，不要指向源数据目录。

### Netlify CLI 超时

先查询最近部署记录，判断是否已创建或已 ready；不要立即重复发布。若 CLI 多次取消，优先使用 GitHub Actions。

### 线上仍是旧资源

核对 `index.html` 中的缓存版本参数；生产 HTML 应引用预期的 `style.css?v=...` 和 `app.js?v=...`。

### 数据请求 302 或回到首页

历史版本使用 Netlify Identity 角色保护 `/data/*`。当前 `netlify.toml` 已改为公开演示；若再次出现，检查线上部署是否仍为旧配置。

### 关键事件文字覆盖

确认样式至少包含：两列 `minmax(0, 1fr)`、`white-space: normal`、`overflow-wrap: anywhere` 和 `min-width: 0`。

## 6. 暂停与交接

结束实质性工作时更新：

- `00_MASTER_CONTROL.md` 的当前状态和下一决策。
- `07_DECISIONS_RISKS_BACKLOG.md` 的优先级。
- `09_CHANGELOG.md` 的事实记录。
- 若涉及论文，再更新 `SCI论文写作/00_master_project_state.md`。


# 构建、测试与部署

## 1. 环境

- Python 3.11
- Node.js 20
- 依赖锁定文件：`requirements.txt`、`package-lock.json`
- 前端依赖：Chart.js 4.5.1
- 构建工具：esbuild 0.28.1
- 部署工具：Netlify CLI 26.2.0

## 2. npm 命令

```powershell
npm ci
npm run check
npm run build
```

命令职责：

| 命令 | 内容 |
|---|---|
| `npm run build:identity` | 将前端入口打包为 `identity-client.js`；名称为历史遗留 |
| `npm run check:js` | 检查 `app.js` 和 `auth-entry.js` 语法 |
| `npm test` | 运行 Python 单元测试 |
| `npm run check` | 打包入口、JS 检查、全部测试 |
| `npm run build:preview` | 从匿名演示 bundle 生成 `netlify_publish/` |
| `npm run build` | 打包入口并生成发布目录 |

注意：构建器拒绝复用已存在的目标目录。若本地已有 `netlify_publish/`，先确认它只是生成物，再按项目清理规范处理；不要覆盖来源数据。

## 3. 当前测试集

共有 6 项回归测试：

- 仅接受显式模板匹配状态。
- 身份冲突进入隔离队列。
- 代理登记号包含稳定来源上下文。
- JSON 原子写入替换目标。
- 结论直接标识脱敏、其他自由文本阻断。
- 发布 bundle 拆分索引与逐例记录。

2026-07-10 最近结果：6 项通过。

## 4. 隐私构建

可复现命令：

```powershell
python dashboard_ui/scripts/build_netlify_preview.py `
  --source-bundle dashboard_ui/demo_data/data_bundle.js `
  --output-root <临时目录> `
  --timestamp <稳定标识>
```

成功条件：

- 输出 734 名匿名患者。
- 预写出审计无发现。
- `privacy_audit.json` 为 `status: pass`。
- 命令退出码为 0。

## 5. CI/CD

工作流：`.github/workflows/netlify-production.yml`

触发条件：

- 推送到 `main` 且相关文件变化。
- Pull Request 的相关文件变化。
- 手动 `workflow_dispatch`。

流程：

1. 安装锁定依赖。
2. `npm run check`。
3. `npm run build`。
4. 读取并验证隐私审计。
5. `main` 分支通过后部署生产站点。

所需 GitHub Secrets：

- `NETLIFY_AUTH_TOKEN`
- `NETLIFY_SITE_ID`

不得把实际 token 写入文档、代码或日志。

## 6. Netlify 状态

- 站点：<https://gxmu-pacemaker-dashboard.netlify.app/>
- Site ID：`7fa5d566-bcb5-4788-8579-913d8e63a35e`
- 线上标题：起搏器程控研究平台
- 线上模式：公开免登录演示
- 线上资源：`v304`
- 本地待发布资源：`v305`

本环境中的 Netlify CLI 曾出现等待超时和 `Deploy canceled`。随后通过 Netlify 官方 Build API 成功发布 `v304`。未来优先使用 GitHub Actions；若手动发布，应先确认审计、目标站点和最终部署状态，不要因为客户端超时重复上传。

## 7. 发布后验证

- HTML 引用的 CSS/JS 版本与预期一致。
- 登录表单状态符合当前产品决策。
- `data/index.json` 返回 200。
- 记录数量与审计报告一致。
- 页面无控制台错误。
- 宽屏和移动端无页面级横向溢出。


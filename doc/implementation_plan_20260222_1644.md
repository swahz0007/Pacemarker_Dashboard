# Dashboard 统计总览页 — 实现方案

打开 index.html 时，默认展示一个丰富的统计总览 Dashboard（替代当前的空状态心脏 icon 页面）。选中患者后切换成原有的患者详情页，点击返回时回到 Dashboard。

## 数据来源

从 `window.PACEMAKER_DATA.index` 提取现有的 `patient_index.json` 数据（无需改后端）：
- `brand` — 品牌分布（美敦力/雅培/百多力等）
- `model` — 型号分布
- `implant_date` — 植入年份趋势
- `count` — 程控次数分布

## 图表规划（6 个图表 + KPI 卡片）

| #   | 图表           | 类型              | 数据                                           |
| --- | -------------- | ----------------- | ---------------------------------------------- |
| 1   | KPI 数字卡片行 | 数字              | 总患者数、总品牌数、平均程控次数、最新植入日期 |
| 2   | 品牌分布       | Doughnut (环形图) | brand 字段聚合                                 |
| 3   | 型号 Top 10    | 横向柱状图        | model 字段 Top 10                              |
| 4   | 植入年份趋势   | 渐变面积图        | implant_date 解析年份                          |
| 5   | 程控次数分布   | 柱状图            | count 字段分桶                                 |
| 6   | 设备年限分布   | Doughnut (环形图) | implant_date 计算设备使用年限                  |

---

## Proposed Changes

### UI 结构

#### [MODIFY] [index.html](file:///e:/Gemini%20CLI%20实战/Pacemarker_Dashboard/dashboard_ui/index.html)

在 `#emptyState` 区域替换为 Dashboard 统计总览视图（`#dashboardView`），包含：
- 一行 4 个 KPI 数字卡片（总患者数、品牌数、平均程控、最新植入）
- 两行共 4 个图表卡片（品牌环形图、型号 Top10、植入趋势、程控分布 + 设备年限）
- 增加一个"返回 Dashboard"按钮在患者详情 header

---

### 业务逻辑

#### [MODIFY] [app.js](file:///e:/Gemini%20CLI%20实战/Pacemarker_Dashboard/dashboard_ui/assets/js/app.js)

新增函数：
- `aggregateStats(patients)` — 聚合所有统计数据
- `renderDashboard(stats)` — 渲染 6 个 Chart.js 图表
- `showDashboard()` / `showPatientDetail()` — 视图切换

修改：
- `loadPatientDetails()` 中入加 `showPatientDetail()` 调用
- 初始化时调用 `renderDashboard()` 取代空状态

---

### 样式

#### [MODIFY] [style.css](file:///e:/Gemini%20CLI%20实战/Pacemarker_Dashboard/dashboard_ui/assets/css/style.css)

新增 Dashboard 相关样式：
- `.dashboard-view` 容器
- `.kpi-row` KPI 卡片行（4 列 grid）
- `.dashboard-grid` 图表卡片 2 列 grid
- `.kpi-card` 数字卡片样式（带动画计数效果）
- Chart 容器尺寸适配

---

## Verification Plan

### 浏览器测试

1. 在浏览器中打开 `e:\Gemini CLI 实战\Pacemarker_Dashboard\dashboard_ui\index.html`
2. **首屏验证**：页面加载后应立即看到 Dashboard 统计总览，包含 KPI 数字和 4 个图表
3. **交互验证**：点击左侧患者列表中的患者 → Dashboard 隐藏，患者详情显示
4. **返回验证**：点击返回按钮 → 回到 Dashboard 视图
5. **主题切换**：切换暗色/亮色主题 → 图表颜色自适应

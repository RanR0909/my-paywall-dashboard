# My Paywall Dashboard

自动监控 [paywallpro/paywall-gallery](https://github.com/paywallpro/paywall-gallery)
的可视化面板，每周一抓一次最新数据，方便快速查看 Top iOS 订阅 App 的付费墙策略、
定价分布与"本周变化"。

**在线访问：** <https://ranr0909.github.io/my-paywall-dashboard/>

## 功能

- **每周自动同步**：GitHub Actions 每周一 UTC 08:00 跑 `scripts/parse.py`，
  解析 `paywallpro/paywall-gallery` 里 `apps/*.md` 的 YAML frontmatter，输出
  `data.json` 并 commit 回仓库；Pages 自动重新发布。
- **关键指标**：总 App 数 / 含免费试用占比 / 平均月价。
- **三张图表**：
  - 付费墙类型分布（doughnut）
  - 类别 MRR Top 10（横向柱状）
  - 类别定价分布（箱线图，月价）—— Y 轴上限按"主体数据"动态算，
    避免被极端高价拉高
- **本周变化**：从第二次跑开始自动出现，对比本周 vs 上周归档
  - 新增 App、价格调整、付费墙策略变更三类
  - 点击卡片展开详细表格
- **筛选 + 搜索**：类别 / 付费墙类型 / 是否含免费试用 / 排序（MRR、评分、名称）
  / App 名模糊搜索
- **纯静态**：单页 `index.html` + Chart.js（CDN），无前端框架，
  `fetch('./data.json')` 加载数据

## 项目结构

```
my-paywall-dashboard/
├── .github/workflows/update.yml   # 每周一自动 Actions
├── scripts/parse.py               # 解析器 + 变化检测
├── data.json                      # 最新解析结果（脚本生成）
├── changes.json                   # 与上一份归档的 diff（第二次跑后才有）
├── history/                       # 历史快照
│   └── data-YYYYMMDD.json         # 每次跑都归档一份
├── index.html                     # 单页面板
└── README.md
```

## 本地预览

不能直接双击 `index.html` 打开 —— 浏览器的 `file://` 协议会拒绝 `fetch()`
读本地 `data.json`。需要起一个 HTTP server：

```bash
cd my-paywall-dashboard
python3 -m http.server 8000
```

打开 <http://localhost:8000> 即可。

## 部署到 GitHub Pages

如果你 fork 或克隆本仓库到自己账号下，需要做以下两步：

### 方式 A：用 gh CLI（推荐，三行搞定）

```bash
cd my-paywall-dashboard
gh repo create <你的用户名>/my-paywall-dashboard --public --source=. --push
gh api -X POST repos/<你的用户名>/my-paywall-dashboard/pages \
  -f "source[branch]=main" -f "source[path]=/"
gh api -X PUT repos/<你的用户名>/my-paywall-dashboard/actions/permissions/workflow \
  -f "default_workflow_permissions=write" -F "can_approve_pull_request_reviews=false"
```

### 方式 B：用网页 UI

1. 推到一个 Public 仓库：
   ```bash
   git init
   git add .
   git commit -m "init"
   git branch -M main
   git remote add origin git@github.com:<你的用户名>/my-paywall-dashboard.git
   git push -u origin main
   ```
2. **Settings → Pages → Source**：`Deploy from a branch` → `main` / `/ (root)`
3. **Settings → Actions → General → Workflow permissions**：切到
   `Read and write permissions`（让 Actions 能 push 更新后的 data.json）

部署完成后访问：`https://<你的用户名>.github.io/my-paywall-dashboard/`

## 手动触发更新

- **GitHub 网页**：仓库页 → **Actions → Update data.json → Run workflow**
- **本地**：
  ```bash
  pip install pyyaml
  python3 scripts/parse.py
  ```
  脚本会 `git clone --depth=1` 拉一次 `paywall-gallery`（会先删除已有的本地
  克隆），再生成 `data.json` + 当日归档；如果 `history/` 里有更早的归档，
  顺带生成 `changes.json`。

## data.json 字段说明

```jsonc
{
  "updated_at": "2026-05-29T10:00:00Z",   // 解析时间（UTC ISO8601）
  "count": 500,                            // App 总数
  "apps": [
    {
      "app_name": "App 名称",
      "app_id": 12345678,                  // App Store ID（作为唯一键）
      "developer": "开发者名称",
      "category": "类别（如 Sports）",
      "paywall_type": "付费墙类型",
      "pricing_model": "定价模型描述",
      "mrr": "$459.84K",                   // 原始字符串
      "mrr_num": 0.45984,                  // 统一换算到百万美元，方便排序
      "rating": 4.92,                      // 评分，没有则 null
      "versions_count": 3,
      "offers": [ { "period": "month", "prices": ["$19.99"] } ],
      "screenshots_count": 3,
      "onboarding_flows_count": 23,
      "app_detail_url": "https://www.paywallpro.app/...",
      "has_free_trial": true,              // 付费墙类型是否含 "Free Trial"
                                           // 且不含 "No Free Trial"
      "monthly_price_num": 19.99,          // 月价数字（没有则 0）
      "source_file": "xxx.md",
      "github_url": "https://github.com/paywallpro/paywall-gallery/blob/main/apps/xxx.md"
    }
  ]
}
```

按 `mrr_num` 降序排列。解析失败的文件会被跳过并在日志中打印提示。

## changes.json 字段说明

第一次跑只会生成 `data.json` 和当日归档；从第二次跑开始（且 `history/`
里能找到一份非今天的归档时）才会生成 `changes.json`。

```jsonc
{
  "current_date": "2026-05-29",            // 本次运行日期（UTC）
  "previous_date": "2026-05-22",           // 对比基准日期
  "summary": {
    "added": 50,                           // 新增 App 数
    "removed": 0,                          // 消失 App 数
    "pricing_changed": 8,                  // 月价变动条数
    "paywall_type_changed": 3              // 付费墙类型变更条数
  },
  "added_apps": [...],                     // 按 mrr_num 降序
  "removed_apps": [...],                   // 按 mrr_num 降序
  "pricing_changes": [                     // 按 |change_pct| 降序
    {
      "app_name": "...", "app_id": ..., "category": "...",
      "old_price": 14.99, "new_price": 12.99,
      "change_pct": -13.3,                 // 百分比（保留 1 位小数）
      "direction": "down"                  // "up" 或 "down"
    }
  ],
  "paywall_type_changes": [                // 按 app_name 升序
    {
      "app_name": "...", "app_id": ..., "category": "...",
      "old_type": "Free Trial - Soft Paywall",
      "new_type": "Credit Paywall"
    }
  ]
}
```

**匹配规则**：

- 用 `app_id` 作为唯一键
- `pricing_changes` 和 `paywall_type_changes` 只包含两份数据里都存在的 `app_id`
- 价格对比时，`old_price` 或 `new_price` 任一为 0 / null 都跳过
- `paywall_type` 任一为空字符串也跳过（避免把数据缺失误报成策略变更）

## 数据来源

数据来自 [paywallpro/paywall-gallery](https://github.com/paywallpro/paywall-gallery)，
版权归原仓库所有。本项目仅做可视化展示。

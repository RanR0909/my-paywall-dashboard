# My Paywall Dashboard

一个自动监控 [paywallpro/paywall-gallery](https://github.com/paywallpro/paywall-gallery)
的可视化面板，每周自动抓取最新数据，方便快速查看 Top iOS 订阅 App 的付费墙策略
与定价模式。

## 功能

- **自动同步**：GitHub Actions 每周一 UTC 08:00 跑一次 `scripts/parse.py`，把
  仓库里 `apps/*.md` 的 YAML frontmatter 解析为 `data.json` 并自动提交。
- **可视化面板**：纯静态 `index.html`（CDN 引入 Chart.js），无前端框架，
  通过 `fetch('./data.json')` 加载数据。可直接托管到 GitHub Pages。
- **指标 / 图表 / 筛选**：4 个关键指标卡 + 付费墙类型饼图 + 类别 MRR Top 10
  横向柱状图，支持按类别 / 付费墙类型 / 是否免费试用筛选，按 MRR / 评分 /
  名称排序，以及 App 名称模糊搜索。

## 项目结构

```
my-paywall-dashboard/
├── .github/workflows/update.yml   # 每周一自动更新
├── scripts/parse.py               # 解析 md → data.json
├── data.json                      # 解析结果（脚本生成）
├── index.html                     # 单页可视化面板
└── README.md
```

## 部署到 GitHub Pages

1. 在 GitHub 上新建一个空仓库 `my-paywall-dashboard`（可以是 public）。
2. 把本目录推到该仓库的 `main` 分支：
   ```bash
   cd my-paywall-dashboard
   git init
   git add .
   git commit -m "init: paywall dashboard"
   git branch -M main
   git remote add origin git@github.com:<你的用户名>/my-paywall-dashboard.git
   git push -u origin main
   ```
3. 在仓库设置中启用 Pages：
   - **Settings → Pages → Build and deployment → Source**：选 `Deploy from a branch`
   - **Branch**：选 `main` / `/ (root)`，保存。
4. 等 1~2 分钟，面板就能在
   `https://<你的用户名>.github.io/my-paywall-dashboard/` 访问。

> 注意：GitHub Actions 需要写权限才能 push `data.json`。工作流里已声明
> `permissions: contents: write`。如果仓库 Actions 默认权限是只读，需要在
> **Settings → Actions → General → Workflow permissions** 切换到
> "Read and write permissions"。

## 手动触发更新

- 在仓库页 **Actions → Update data.json → Run workflow** 即可手动跑一次。
- 也可以本地跑：
  ```bash
  pip install pyyaml
  python scripts/parse.py
  ```
  脚本会在当前工作目录 `git clone --depth=1` 拉一次 `paywall-gallery`，再生成
  `data.json`。

## data.json 字段说明

```jsonc
{
  "updated_at": "2026-05-29T10:00:00Z",   // 解析时间（UTC ISO8601）
  "count": 500,                            // App 总数
  "apps": [
    {
      "app_name": "App 名称",
      "app_id": 12345678,                  // App Store ID
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
      "has_free_trial": true,              // 付费墙类型是否含 Free Trial
      "monthly_price_num": 19.99,          // 月价数字（没有则 0）
      "source_file": "xxx.md",
      "github_url": "https://github.com/paywallpro/paywall-gallery/blob/main/apps/xxx.md"
    }
  ]
}
```

按 `mrr_num` 降序排列。解析失败的文件会被跳过并在日志中打印提示。

## 数据来源

数据来自 [paywallpro/paywall-gallery](https://github.com/paywallpro/paywall-gallery)，
版权归原仓库所有。本项目仅做可视化展示。

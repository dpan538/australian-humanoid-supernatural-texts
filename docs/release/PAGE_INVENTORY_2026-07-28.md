# AusFigures 页面资产账本

- 核对日期：2026-07-28
- 生产站：<https://ausfigures.com/>
- 本地数据来源：`public/data/frontend-data.json`
- 可重复命令：`npm run audit:pages -- --live`

## 核对结果

| 层 | 数量 | 处理 |
|---|---:|---|
| 生产 sitemap URL | 12 | 当前线上基线 |
| 本地 accepted public records | 4,265 | 数据层事实，不等于全部应索引 |
| 应生成记录永久页 | 4,263 | 排除 2 条 control-only / 非项目范围控制记录 |
| 可进入搜索索引的记录页 | 3,706 | 通过公开页与搜索审核门 |
| 审核中记录页 | 557 | 保留永久页，`noindex,follow`，不进 sitemap |
| 分页记录索引 | 38 | 每页最多 100 条 search-ready 记录 |
| 叙事类型详情页 | 12 | 覆盖完整超自然人形叙事分类，不以 Yowie 为中心 |
| 公共文本标签页 | 60 | 至少 4 条 search-ready 记录才建立标签页 |
| 来源详情页 | 32 | 其中 22 页至少 2 条记录并进入 sitemap |
| 州/领地页 | 8 | 叙事地理，不解释为超自然分布 |
| 时期页 | 7 | 6 个年代区间加 undated |
| 本地应生成内容页总数 | 4,439 | 不含 RSS、404、错误页及静态图片 |
| 本地应生成 sitemap URL | 3,872 | 只含 self-canonical、可索引、非重定向页面 |
| 生产到目标 sitemap 差额 | 3,860 | `3,872 - 12` |

## 资格门

记录永久页必须同时满足：

1. 不是 `control_only` 或 `exclude_core`；
2. 不是 `non_humanoid_control`；
3. 具备标题、原始公共 URL 与来源名称；
4. 只使用 accepted public frontend export，不把 metadata-only、lead、source intelligence 或 overlay 提升为公共记录。

记录进入 sitemap 还必须满足：

1. `ethics_flag` 为 `ok_public` 或已审查的 `public_*` 状态；
2. canonical 指向自身；
3. 页面不是重定向、noindex 或空集合。

`caution_*`、`needs_human_*` 与其他未完成搜索/敏感性审核的 accepted public records 保留永久页，便于现有界面和引用关系稳定，但设置 `noindex,follow`，不进入 sitemap。

## 页面层

```text
/
├── records
│   ├── page/{page}
│   └── {record-id}-{title-slug}
├── narrative-types/{type}
├── labels/{public-text-label}
├── sources/{source-id}-{source-slug}
├── places/{state-or-territory}
├── periods/{period}
├── topics/{curated-topic}
├── data
├── cite
└── feed.xml
```

## 生产发布后复核

1. 运行 `npm run audit:pages -- --live`，确认生产 sitemap URL 从 12 接近 3,872。
2. 抽检 200、canonical、robots、结构化数据、来源链接与移动布局。
3. 确认 `/map` 保留原交互页面、canonical 指向 `/`，且 sitemap 不含 `/map`。
4. 确认移动 `/dashboard → /map` 的原产品行为没有被 SEO 页面补全改写，并在 Search Console 单独监测其页面身份影响。
5. 确认 557 条 review-only 记录不进入 sitemap。
6. 在 Search Console 重新提交 sitemap，并逐条验证原 3 个 Soft 404 和 1 个 redirect。

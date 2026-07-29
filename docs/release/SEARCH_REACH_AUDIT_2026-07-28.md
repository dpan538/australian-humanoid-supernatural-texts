# AusFigures 搜索触达、运行与推广全局评估

- 审计日期：2026-07-28
- 目标站点：<https://ausfigures.com/>
- 范围：生产站、当前本地构建、Google Search Console 截图、Google 关联检索、代码与数据架构
- 结论等级：可执行诊断；Search Console 中 4 个未收录 URL 的逐条归因仍需导出明细确认

## 1. 项目范围声明

AusFigures 的上位概念不是 Yowie 专站，而是“澳大利亚公共文本中的超自然人形叙事与遭遇档案”。本报告据此验证完整项目，覆盖但不限于：

- 野人、毛发人形、Yowie 等 cryptid-style apeman；
- 鬼魂、幽灵、显现、apparition account 与 ghost legend；
- spirit person、祖灵或灵性人形叙事；
- giant、ogre、devil、witch、medicine person 等人形或拟人形传统；
- retelling、belief description、reported encounter 等不同叙事类型。

Yowie 只在本次审计中充当一个“已有精确标题的长尾检索探针”，不代表项目分类中心。后续信息架构必须围绕“分类—人物/形象—地点—时期—来源—记录”展开，而不是围绕单个民俗对象展开。

## 2. 执行摘要

站点并未被 robots、HTTPS 或整站 noindex 阻断。Search Console 已显示 10 个已收录页面；生产站 robots、sitemap、canonical、结构化数据、真实 404 和基础传输均可工作。本地生产构建与类型检查也通过。

推广不佳的主要原因是一个相互放大的系统性组合：

1. 当前数据层已有 4,265 条记录，但 sitemap 只有 12 个 URL，且没有记录永久链接。搜索引擎看到的是少量入口页，而不是可理解、可引用、可链接的档案网络。
2. 首页及多个交互路由的初始 HTML 主要是通用加载壳，约 500 字符可见文本；核心数据要在客户端再下载约 23 MB JSON 才出现。Google 能执行 JavaScript 不等于这些页面会被高效理解或被判为高质量独立页面。
3. `/dashboard` 在移动视口会通过客户端跳到 `/map`，但 sitemap 和 canonical 又把它声明为独立页面。这与移动优先索引的页面身份不一致。
4. 首页标题和 Open Graph 标题只有 `AusFigures`，页面可见正文、内部链接和主题入口都很少，未充分表达“澳大利亚超自然人形公共文本档案”的检索意图。
5. 站点上线约一个月，当前抽样检索几乎没有发现有意义的第三方引用；没有可见发布版本、DOI/可引用数据集、RSS/Atom、记录分享链接或站内搜索落地页，也未发现独立访问分析代码。新域名缺少权威信号是 22 次曝光、0 点击的重要背景。
6. Search Console 的“平均排名 4”来自仅 22 次曝光，样本太小，可能被品牌词或精确标题词抬高，不能解释为站点已取得第 4 名的稳定排名。

因此，修复目标不应只是消除 3 个 Soft 404，而应把站点从“一个加载大型数据集的交互地图”升级为“一个可被搜索、引用、分享和渐进加载的数字档案”。

## 3. 已验证的证据

### 3.1 Search Console 截图

三个月视图显示：

- 0 次点击；
- 22 次曝光；
- CTR 0%；
- 平均排名 4；
- 10 个页面已收录；
- 4 个页面未收录，其中 Soft 404 为 3，Page with redirect 为 1；
- Discovered/Crawled – currently not indexed 均为 0。

这组数据说明 Google 已经发现并处理站点，但有效检索面很窄。它不是“完全没有索引”的问题。

截图没有展开 4 个未收录 URL，因此本报告不会把具体 URL 归因写成已确认事实。基于下述初始 HTML 与移动跳转测试，交互壳页面是 Soft 404 的高概率候选，`/dashboard` 或域名规范化 URL 是 redirect 的候选；最终必须用 Search Console 行级导出验证。

### 3.2 生产运行检查

已验证：

- `https://ausfigures.com/` 返回 200；
- `http://ausfigures.com/` 和 `https://www.ausfigures.com/` 规范化到 HTTPS apex；
- `/robots.txt` 与 `/sitemap.xml` 返回 200；
- 随机不存在路径返回真实 HTTP 404；
- 首页 canonical 指向 `https://ausfigures.com/`；
- 页面无浏览器控制台错误；
- 生产首页完整加载后约有 5,104 个 DOM 元素，但只有约 619 个可见文本字符；
- 生产公共数据文件为 23,062,512 字节，单次压缩传输实测约 2.70 MB；
- 首页载入 31 个资源，其中 13 个脚本、2 个样式、2 个图片，其余为其他资源；核心数据文件是主要载荷；
- sitemap 有 12 个 URL，所有 `lastmod` 固定为 2026-06-30；数据文件在 7 月仍有更新。

### 3.3 修复前本地生产模拟（基线）

以下结果记录本轮修复前的基线，不代表当前工作树：

- `npm run typecheck`：通过；
- `npm run build`：通过，生成 22 个静态/SSG 页面；
- 本地生产服务：启动并完成桌面及 390×844 移动视口测试，测试后已停止；
- 移动视口访问本地和生产 `/dashboard`，均被客户端替换为 `/map`；
- `/density` 与 `/source` 在移动视口保持原 URL；
- 测试完成后浏览器视口已恢复。

初始服务端 HTML 抽样：

| 路径 | HTTP | 初始 HTML 字节 | 近似可见文本字符 | 观察 |
|---|---:|---:|---:|---|
| `/` | 200 | 33,128 | 506 | 加载壳，标题仅品牌名 |
| `/map` | 200 | 33,983 | 510 | 与首页意图高度重叠，canonical 指首页 |
| `/dashboard` | 200 | 34,591 | 555 | 移动端随后跳 `/map` |
| `/density` | 200 | 34,301 | 551 | 交互壳 |
| `/source` | 200 | 34,376 | 539 | 交互壳 |
| `/about` | 200 | 55,371 | 4,117 | 有可理解正文 |
| `/topics` | 200 | 37,343 | 1,083 | 有主题正文 |
| 六个 topic 页面 | 200 | — | 1,562–1,838 | 有独立 H1/H2、标题与 canonical |

交互页共享薄弱初始内容、之后再渲染大型数据，是 Soft 404 风险的直接机制证据；但只有 Search Console 明细才能确认 3 个具体 URL。

本轮信息补全后的本地生产构建已生成 4,450 个静态/SSG 页面。按产品边界回退后，现有 Map、Dashboard、Source、Density、About、移动导航和主题操作保持原实现；`/map` 保留原交互页面、canonical 指向 `/` 并从 sitemap 排除。移动 `/dashboard → /map` 的既有行为不再由本轮 SEO 工作改写，其移动优先页面身份风险作为后续独立议题保留。页面资产、索引资格门与生产差额见同目录的 `PAGE_INVENTORY_2026-07-28.md`。

### 3.4 当前数据与分类面

当前本地公共数据资产包含：

- 4,265 条记录；
- 1,593 个地图标记/点；
- 4,435 个地点行；
- 54 个来源；
- 328 个查询；
- 19 个 ontology 值；
- 206 个 `canonical_figure_guess` 标签，但 `canonical_figure` 仅 12 个值；
- 前端 figure profile 只有 7 个显式对象。

分类已经明显超出 Yowie，但“猜测标签—正式人物/形象—ontology—前端 profile”尚未形成一套统一、可解释、可路由的概念图谱。这会造成同义词碎片、页面覆盖不均和内部链接断裂。

## 4. 关联搜索测试

测试包含品牌词、精确标题、上位概念、分类词和功能页检索。搜索结果会随时间、地点和个性化变化，因此这里记录的是 2026-07-28 的抽样诊断，不是永久排名承诺。

| 查询类型 | 测试示例 | 结果 | 诊断 |
|---|---|---|---|
| 站内 | `site:ausfigures.com` | 首页与 topic 页可见 | 索引通道工作 |
| 品牌 | `"AusFigures"` | 可找到站点 | 品牌可识别，但外部声量极低 |
| 精确长尾 | `"Yowie Records in Public Texts"` | AusFigures topic 排在前列 | 精确标题页能够命中 |
| 上位概念 | `Australian supernatural archive` | 首屏被 ABC、图书馆、档案馆、图书等占据 | 缺少上位概念权威与点击吸引力 |
| 档案意图 | `Australian supernatural public texts archive` | topic 页在部分结果中可见 | 与页面措辞高度贴合时有机会 |
| 鬼魂/显现 | `Australian ghost apparition records archive` | NFSA、州立图书馆、通用资料占优 | 分类页内容与外链权威不足 |
| 灵性人形 | `Australian spirit-person narratives public texts` | 文化机构、地方资料和通用结果占优 | 主题语义与可信来源关系未展开 |
| 巨人/人形传说 | `Australian giant humanoid folklore records` | 通用民俗、档案和百科结果占优 | 缺少独立分类/记录可索引面 |
| 功能页 | `site:ausfigures.com dashboard/source/density/map` | 抽样结果未稳定出现这些功能页 | 交互页独立价值信号不足 |
| 站外引用 | `"ausfigures.com" -site:ausfigures.com` | 未发现有意义的第三方研究/机构引用 | 外部权威近乎空白 |

关键解读：精确长尾能命中，说明“只要有独立静态文本页，Google 可以理解站点”。广义类别词和档案意图不稳定，说明瓶颈主要在信息架构、内容深度、页面身份与权威信号，而不是单纯抓取故障。

## 5. 问题分级

### P0：阻碍可发现面的架构问题

#### P0.1 记录没有永久 URL

4,265 条记录目前主要存在于客户端数据和覆盖层中。覆盖层没有可独立访问的 URL，无法被外部论文、地方史页面、馆藏页或社交分享精确引用。Google 的官方指南强调每一份希望被发现的内容应有可抓取 URL 和真实链接。

#### P0.2 移动端 `/dashboard` 页面身份冲突

移动视口下 `/dashboard` 被 `router.replace("/map")` 改写，而 sitemap、桌面页和 canonical 把 `/dashboard` 当成独立页面。Google 使用移动版本进行索引；移动页面不保留同等内容或发生非一致跳转，可能导致该页不能按预期被索引。

#### P0.3 交互路由初始 HTML 过薄

首页、地图、dashboard、density、source 初始 HTML 都接近同一个加载壳。即便之后能渲染，页面仍可能因文本信号过少、内容相似、等待渲染或缺乏独立价值而被判为 Soft 404 或低价值页面。

### P1：压低相关性、CTR 和抓取效率

#### P1.1 首页标题只有品牌

首页 `<title>` 和 `og:title` 均为 `AusFigures`。对尚无品牌认知的新站，这没有表达主题、地域和档案类型。建议保留品牌，同时明确上位概念：

> Australian Supernatural Humanoid Public-Text Archive | AusFigures

#### P1.2 首页正文和内部导航不足

首页加载完成后可见文本仍很少，只有约 7 个链接，缺少完整 topics、dashboard、分类、地点、时期和最新记录入口。用户和搜索引擎都难以从首页理解档案规模与知识结构。

#### P1.3 23 MB 单体数据和超大 DOM

用户为了看一个入口页先承担完整档案数据；首页生成约 5,104 个 DOM 元素。该设计对低速网络、移动设备、交互延迟和浏览器内存都不友好，也使抓取渲染成本不必要地升高。

#### P1.4 sitemap 的更新时间失真

所有页面 `lastmod` 固定为 2026-06-30，但数据在 7 月更新。Google 会参考准确、显著更新对应的 `lastmod`，并忽略 `priority` 和 `changefreq`。当前配置既浪费信号，也无法告诉搜索引擎哪些档案内容真正变化。

#### P1.5 分类系统未形成 URL 级概念图

ontology、figure guess、canonical figure 和前端 profile 的粒度不同。若直接大量生成页面，会产生重复、薄内容和文化语境误配；若不生成页面，又会继续把数千记录隐藏在 JSON 中。

### P2：推广、信任和衡量缺口

#### P2.1 外部引用与发布信号弱

抽样未发现有效第三方引用；公开 GitHub 仓库没有 release、star 或 fork 信号。此处不能靠批量目录提交解决，应该通过可引用版本、方法说明和有针对性的机构/研究者传播建立真实关系。

#### P2.2 缺少可见的引用与版本信息

站内没有突出作者/维护者、建议引用格式、数据版本、变更记录、持久标识符、可下载数据集入口和清晰联系方式。对于研究型档案，这些既是信任要素，也是获得自然链接的前提。

#### P2.3 衡量体系不足

代码中未发现 GA、Plausible、Umami、Vercel Web Analytics 等访问分析集成，也没有清晰事件字典。仅靠 Search Console 无法知道用户是否到达、使用了何种过滤器、打开何种类别或在哪一步退出。

#### P2.4 没有更新订阅与深链接传播面

没有 RSS/Atom、可分享的记录 URL、分类更新页、版本发布页或稳定 OG 卡片。推广只能指向首页，无法围绕具体来源、地点、时期或类别形成长尾传播。

## 6. 全局目标架构

### 6.1 URL 与信息架构

建议建立以下稳定层级：

```text
/
├── records/{public-id}-{slug}
├── concepts/supernatural-humanoids
├── narrative-types/{type}
├── figures/{canonical-figure}
├── places/{state}/{locality}
├── periods/{period}
├── sources/{source}
├── topics/{curated-topic}
└── explore/{map|dashboard|density|source}
```

原则：

- 每条允许公开的正式记录拥有永久 URL；
- 页面服务端输出独立标题、H1、摘要、来源、日期、地点、分类、相关记录、面包屑和建议引用；
- `figure` 页面处理标准名、别名和文化语境；Yowie 只是多个 figure/narrative cluster 之一；
- `narrative-type` 反映 apparition、spirit-person、cryptid-style apeman、giant-or-ogre、ghost-legend、retelling 等叙事类型；
- 地点、时期、来源页必须有策展摘要与足够记录，不生成空页或单行薄页；
- 任意筛选参数页默认 canonical 到上位策展页或 `noindex,follow`；只把质量达标的静态组合页放入 sitemap；
- 只发布通过项目现有伦理、敏感性与证据门槛的记录；受限内容不得因 SEO 批量公开；
- 对文化敏感术语与 spirit-person 类别保留来源原语境、出处和必要说明，避免用外部营销词强行归并。

### 6.2 路由与 canonical

- 在 `/` 与 `/map` 中选一个唯一公开地图 URL。
- 若首页就是地图，服务器端 308 `/map → /`，所有内部链接也指 `/`；不要保留“200 + canonical 到另一页”的双重入口。
- 删除移动端 `/dashboard → /map` 的客户端替换。为移动端提供同一 dashboard 的简化响应式内容。
- 如果短期无法提供独立 dashboard，应在服务器端明确重定向并从 sitemap 移除，而不是让移动和桌面表现不同。
- 为 dashboard、density、source 输出独立服务端摘要、关键统计和解释，使未执行 JavaScript 时也能理解其功能。

### 6.3 性能与数据分发

将 23 MB 单体数据改为渐进式分发：

1. 首屏只发送页面摘要、聚合计数与当前视口/查询所需记录。
2. 生成轻量公共索引清单；记录详情按永久 URL 或 ID 请求。
3. 地图按州、网格或视口分片；缩放较远时返回聚合点。
4. dashboard、source、density 各取自己的预聚合数据，不加载完整记录库。
5. 列表使用分页或虚拟化；地图使用聚合渲染，避免一次构建数千 DOM 节点。
6. 内容寻址的数据分片使用版本/hash 和长期不可变缓存；入口 manifest 短缓存并可验证版本。

建议项目内部预算：

- 普通入口首屏压缩传输不超过 250 KB，不含按需地图瓦片；
- 初始 DOM 节点不超过约 1,400；
- 移动 p75：LCP ≤ 2.5 s、INP ≤ 200 ms、CLS ≤ 0.1；
- 单一路由不得默认下载全量 23 MB 数据。

### 6.4 标题、摘要与内部链接

- 首页采用描述性标题并保留品牌；
- 每种页面模板都有自己的标题公式，避免只换一个类别词；
- 首页加入 150–250 字项目说明、档案覆盖范围、更新时间和可见数据规模；
- 主导航加入 Topics、Dashboard、分类、地点、时期、来源；
- topic 页面不只写通用概述，应展示精选记录、权威来源、相关分类与进入档案的稳定链接；
- 为每条记录、来源、地点和类别生成可验证的相关链接，而不是客户端按钮。

### 6.5 sitemap 与索引质量门

- 拆分 `sitemap-index.xml`、`sitemap-static.xml`、`sitemap-records-N.xml`、`sitemap-figures.xml`、`sitemap-places.xml`；
- `lastmod` 来自该页面的真实内容版本；
- 不依赖 `priority` 或 `changefreq`；
- 只有 200、self-canonical、非 noindex、有独立正文、达到质量/伦理门槛的页面进入 sitemap；
- 每次构建自动检测孤儿页、canonical 环、重定向 URL 入 sitemap、重复 title/H1、薄页和被限制记录泄露；
- 初次发布记录页时分批开放，例如 100 → 500 → 全量合格记录，以便观察索引质量。

### 6.6 信任、引用与推广

- 在 About/Methodology 明示维护者、研究方法、收录/排除标准、敏感材料政策、纠错流程和联系方式；
- 建立 Data/Cite 页面：版本号、发布日期、许可证、建议引用、机器可读元数据；
- 为稳定数据发布申请 Zenodo DOI 或同类持久标识符，并建立 GitHub Release；
- 发布变更日志、RSS/Atom 和按类别更新入口；
- 为记录/类别/地点页生成独立 OG 卡片；
- 有针对性地向澳大利亚图书馆、档案馆、地方史团体、民俗/数字人文研究者介绍可引用的具体资料页；不做垃圾目录提交或批量交换链接；
- 宣传语言坚持“source-grounded public-text archive”，不把叙事材料包装成事实证明；
- 优先围绕来源整理、方法透明、地方史页面和可复现数据发布获得自然引用。

### 6.7 衡量系统

在满足隐私要求的前提下增加轻量分析，并与 Search Console、Bing Webmaster Tools、服务端日志结合：

- 页面维度：page type、category、figure、state、source、period；
- 事件：search、filter_apply、record_open、source_click、citation_copy、dataset_download、share；
- 渠道：UTM source/medium/campaign；
- SEO 看板：品牌/非品牌曝光、已收录 URL、有效记录页覆盖、CTR、目标查询簇、外部引用域、CWV；
- 不发送记录正文、敏感查询或精确用户位置到分析平台。

### 6.8 视觉与交互边界

- 原有 map/dashboard/source/density/about 的 archive dashboard 操作框架、移动导航和界面节奏属于产品识别，不做通用内容站式全局替换；
- SEO 永久页使用同一黑底、等宽、荧光状态色和面板网格语言，不在全站增加 sticky marketing header；
- 深色模式保持高密度、低解释量的终端档案风格；
- 浅色模式可采用更常规的系统字体、白色信息面板、更强正文层级和补充阅读指引；
- 全局层只调整颜色对比度和可读性变量，不改变原交互方式。

## 7. 分阶段修复流程

### Phase 0：锁定证据基线（0.5–1 天）

1. 从 Search Console 导出 3 个 Soft 404 和 1 个 redirect 的 URL 明细。
2. 导出 16 个月 Performance 的 Queries、Pages、Countries、Devices、Search Appearance。
3. 对 12 个现有 sitemap URL 做 URL Inspection；保存 Google 抓取 HTML/截图。
4. 导出 Links 报告并记录 top linking sites/pages。
5. 建立版本化基线：路由状态、title、canonical、初始文本字数、传输大小、CWV、索引数。

交付门槛：4 个未收录 URL 已逐条确认，不再靠猜测。

### Phase 1：页面身份与抓取修复（1–3 天）

1. 统一 `/` 与 `/map`。
2. 删除移动 `/dashboard` 客户端跳转，或改成明确服务器重定向并移出 sitemap。
3. 为交互页输出独立 SSR 摘要和关键统计。
4. 将首页 title/OG/H1 对齐到上位概念。
5. 修正 sitemap 真实 `lastmod`，移除 redirect URL。
6. 在 Search Console 对已确认问题启动 Validate Fix。

### Phase 2：档案信息架构与永久链接（1–2 周）

1. 定义概念图、figure 别名、narrative type、文化语境和 URL slug 合同。
2. 建立 public-record eligibility gate。
3. 生成记录、类别、形象、地点、时期和来源模板。
4. 增加面包屑、相关链接、引用块和 schema。
5. 分批生成 sitemap 并提交。

### Phase 3：数据载荷与交互性能（约 1 周）

1. 拆分 23 MB JSON；
2. 构建路由级聚合和记录级 API/静态分片；
3. 地图按视口/区域聚合；
4. 列表虚拟化；
5. 建立 Lighthouse、移动真实设备和 CWV 回归预算。

### Phase 4：信任、版本与衡量（3–5 天）

1. 增补 Methodology、Cite、Data、Changelog；
2. 生成版本发布与 DOI；
3. 接入隐私友好分析、Bing Webmaster Tools 与事件字典；
4. 增加 RSS/Atom、稳定分享链接与 OG。

### Phase 5：持续推广（4–8 周起）

1. 围绕完整上位概念及多个子类别发布策展页，不偏向单一 Yowie；
2. 以具体来源、地点、时期和记录页向相关机构/研究者定向介绍；
3. 发布可复现的数据版本和研究说明；
4. 每两周复盘非品牌曝光、CTR、收录率、外部引用和 CWV；
5. 根据真实查询扩充薄弱类别，而不是批量制造关键词页面。

## 8. 验收标准

- 所有计划索引的页面在关闭 JavaScript时仍有独立、足够、可理解的正文；
- 移动与桌面对同一 URL 保持同一内容意图；
- `/dashboard` 不再发生未声明的客户端跳转；
- `/` 与 `/map` 只有一个公开 canonical 和一套内部链接；
- sitemap 不含重定向、noindex、非 canonical 或敏感记录；
- 每个合格公开记录可通过永久 URL 访问和引用；
- 首页不再默认下载全量 23 MB 数据；
- 移动 p75 达到 LCP ≤ 2.5 s、INP ≤ 200 ms、CLS ≤ 0.1；
- Search Console 中 3 个 Soft 404 和 1 个 redirect 的具体 URL 完成验证；
- 非品牌曝光、有效收录页、CTR 和第三方引用按月有可解释趋势；
- 成功标准是扩大合格检索面和真实用户触达，不承诺固定排名或流量倍数。

### 8.1 本轮落地状态

| 验收项 | 状态 | 证据 |
|---|---|---|
| 永久记录页 | 已完成 | 4,263 页生成；3,706 页允许索引，557 页 `noindex,follow` |
| 分类解析页 | 已完成 | 12 narrative type、60 label、32 source、8 place、7 period 页 |
| sitemap 质量门 | 已完成（本地） | 3,872 个 URL；不含 `/map`、redirect 和 review-only 记录 |
| `/map` 页面身份 | 部分完成 | 保留原 `/map` 交互；canonical 指向 `/`，且 sitemap 不收录 `/map` |
| 移动 `/dashboard` | 未做 SEO 行为改写 | 按产品边界恢复原移动 `/dashboard → /map`；页面身份风险留待独立评估 |
| canonical / robots | 已完成（本地） | 可索引与审核中记录抽样符合各自策略 |
| Cite / Data / RSS | 已完成（本地） | `/cite`、`/data`、`/feed.xml` |
| 原 archive dashboard 交互 | 已恢复 | Map、Dashboard、Source、Density、About、主题与移动导航文件恢复原实现，无全局 header |
| 深浅色适配 | 局部完成 | 原页面主题变量恢复；浅色阅读指引仅存在于新增 `.publication-*` 信息页 |
| 生产发布 | 未执行 | 线上 sitemap 仍为 12，和本地目标相差 3,860 |
| 23 MB 数据投影 | 部分完成 | 完整档案保持不变；交互默认文件从 23,062,512 降到 10,103,947 字节（-56.2%），仍需按视图/区域继续分片 |
| GSC 4 个未收录 URL 明细 | 未取得 | 需要 Search Console 行级导出 |
| CWV 真实用户 p75 | 未验证 | 需要生产部署后的字段数据 |

## 9. 当前判断的置信度

| 判断 | 置信度 | 说明 |
|---|---|---|
| robots/HTTPS/noindex 不是整站阻断点 | 高 | 生产响应与 GSC 已收录数直接验证 |
| 可索引页面供给远小于数据规模 | 高 | 4,265 条记录对 12 个 sitemap URL |
| 客户端大数据壳造成抓取效率和软 404 风险 | 高 | 初始 HTML、23 MB 数据与重复加载壳直接验证 |
| `/dashboard` 移动跳转造成页面身份冲突 | 高 | 本地和生产移动视口均复现 |
| 3 个 Soft 404 就是某三个交互路由 | 中 | 机制吻合，但截图未显示 URL |
| 1 个 redirect 就是 `/dashboard` | 中 | 已复现跳转，但也可能是 www/其他 URL |
| 外部权威不足显著抑制泛词触达 | 高 | 新域名、站外引用抽样和泛词结果一致 |
| “平均排名 4”代表整体排名良好 | 低/否定 | 只有 22 次曝光，样本不可用于整体判断 |

## 10. 参考标准与现场入口

- [AusFigures 首页](https://ausfigures.com/)
- [AusFigures Topics](https://ausfigures.com/topics)
- [Google：SEO Starter Guide](https://developers.google.com/search/docs/fundamentals/seo-starter-guide)
- [Google：JavaScript SEO basics](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics)
- [Google：Mobile-first indexing best practices](https://developers.google.com/search/docs/crawling-indexing/mobile/mobile-sites-mobile-first-indexing)
- [Google：Debugging drops in Google Search traffic / Page indexing](https://support.google.com/webmasters/answer/7440203)
- [Google：Sitemap `lastmod`](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)
- [Google：Core Web Vitals](https://developers.google.com/search/docs/appearance/core-web-vitals)

## 11. 建议立即执行的下一批任务

按顺序执行：

1. 审核并部署当前静态产物；生产发布后确认 sitemap 从 12 更新到 3,872；
2. 在 Search Console 重新提交 sitemap，取得 3 个 Soft 404 与 1 个 redirect 的 URL 明细；对 `/map` canonical 与移动 `/dashboard → /map` 单独记录，不以 UI 改写方式修复；
3. 将新增 URL 分批监测，但不人为把 Yowie 设为分类中心；同时观察 ghost/apparition、spirit-person、giant/ogre、wild-person 等查询簇；
4. 在已完成的 10.1 MB 交互投影上继续按入口、州/视口和记录详情渐进分片，保持现有地图交互不变；
5. 接入隐私友好分析与服务端性能观测，建立索引率、非品牌曝光、记录打开、来源外链和 CWV 基线；
6. 发布可引用版本与 DOI，并以具体记录、来源、地点和方法页向图书馆、档案馆、地方史和数字人文研究者定向传播；
7. 两周后复盘真实索引与查询数据，再决定扩大标签页门槛或新增策展页，不批量制造薄页。

# CollegeX 活动数据归档

## 2026-10-21 续核验（当前最新结果）

已在现有485条记录中更新41条，新增61个非空核验字段：官网身份37条、2027费用5条、2027报名时间5条、资格14条。累计确认官网161条、费用21条、报名61条、资格59条。既有核验值与原日期保留；新字段核验日期为2026-10-21。通用资格明确标注为现行指引，未确认属于2027最终规则。

本轮访问76个公开入口，取得73份正文；其他3个入口分别为robots状态不允许/不明、HTTP503、TLS连接失败。本轮为有边界续核验，未穷尽所有剩余官网。原始非空上游字段及485个ID保持一致，16项离线测试、三组CSV/JSONL回读和520份累计正文哈希验证通过。

最新证据、变更清单和写入前备份在 `data/run_20261014T023053_084055Z/official_verification_2027/pass_20261021/`；汇总表仍为原位置 `2027官网核验表.csv`。后续增量请使用 `continue_official_verification.py --pass-dir 新批次目录`，该目录需提供source_index.json和逐字段reviewed_decisions.json；已有非空核验值不会覆盖。同一批次拒绝重复应用。原apply脚本仅适用于首轮，存在后续增量时会停止，防止回放旧备份丢失新字段。

## 2026-10-14 官网资料核验（历史首轮）

已更新现有六份活动导出，补入55条缺失竞赛官网；2027费用确认16条，报名信息56条，资格45条。所有非空核验字段均有来源、日期和适用范围，未确认项留空。原有 cost_range/key_dates 等是上游历史值，不能直接作为2027官方信息。

详情及边界见 [data/run_20261014T023053_084055Z/official_verification_2027/核验说明.md](data/run_20261014T023053_084055Z/official_verification_2027/核验说明.md)；建议先查看同目录 `2027官网核验表.csv`。写入前备份位于 `before_enrichment/`。下文原抓取及结构化审计说明属于官网补充之前的历史阶段。


抓取日期：2026-10-14（Asia/Taipei）。用户在当前对话确认已取得网站方授权后执行。

## 结果与范围

已完成 https://college-x.com/activities 使用的两类无筛选公开列表快照：竞赛 81 条、夏校 404 条，总计 485 条。保留源 API 的全部字段、原始响应及来源、抓取时间、内容标识与可用的官网规范 URL。

最新批次：`data/run_20261014T023053_084055Z`。

- `activities.csv`：合并表，UTF-8 BOM，可用 Excel 打开。
- `activities.jsonl`：合并数据，每行一个对象；`data` 保留完整源记录。
- `competitions.csv/jsonl`：竞赛。
- `summer_programs.csv/jsonl`：夏校。
- `raw/`：原始 JSON、活动页面、robots.txt、服务条款。
- `report.json`：请求清单、抓取时间、SHA-256、覆盖证据、字段缺失统计。
- `verification.json`：导出回读与原始响应一致性检查。

## 覆盖验证

页面原脚本使用 limit=200，可能截断夏校。本次分别以 limit=1000 和 limit=5000 请求，返回记录内容完全一致，条数均低于 1000；limit=1 控制请求均只返回一条且属于完整列表。两个数据集均未发现完全重复记录或重复名称。正式批次 9 次请求全部成功，无失败或重试。9 份原始响应 SHA-256 均通过回读核验，JSONL 中 data 与原始记录逐条一致。

完整性指当前公开 API 暴露的无筛选活动列表；网站没有提供数据库总量证明，不声称覆盖隐藏或未公开记录。未扩展抓取外链项目官网、报名站点、其他栏目或账户数据。

## 字段与数据质量

竞赛包含名称、类别、国家、年级、简介、评级、学科、比赛形式、关键日期、资格、原始描述和官网等 16 个源字段；夏校包含名称、评级、官网、地点、时间、时长、年级、年龄、性别、类别、学分、费用、授课方式、主办方、描述、亮点、选拔性、专业编码、联系方式等 22 个源字段。新增元数据字段：record_id、activity_type、source_url、source_page_url、crawled_at、canonical_url。

- 竞赛 81 条均缺 website 和 cip_match，40 条缺 key_dates。
- 夏校 139 条缺 star_rating，38 条缺 cost_range，4 条缺 url，4 条缺 description。
- 夏校 84 条共用包含 RSI 的评级理由；该现象是源数据质量疑点，未替网站更正。
- 缺失字段及源字符串保持原样；派生 canonical_url 无有效链接时为 null。未补造价格、日期、评分或官网。
- 相同 URL 可能对应不同课程，因此按完整内容去重，不按官网 URL 删除不同项目；源 URL 保留，规范 URL 仅作辅助。
- 信息来自 CollegeX，未逐项向项目官网核验；费用、报名日期、资格和评级使用前需另行确认。

## 合规与运行限制

用户已确认网站方授权，本次授权依据记录于状态文件。网站条款通常限制批量复制，后续用途须符合实际获得的授权范围。每次实际运行均需显式 --authorized。程序读取并检查 robots.txt，使用透明 User-Agent：CollegeXPublicArchive/1.0 (authorized public activities archive)。默认单并发，请求间隔 1.5 秒，最多 15 次请求，30 秒超时，安全暂态错误最多重试 2 次；401/403 不重试。不使用登录、Cookie、凭据或访问控制绕过。仅采集活动公开字段，不进入个人资料；源数据存在公开项目电话字段。

## 安装与运行

仅使用 Python 3 标准库，无需安装第三方依赖。目录均使用独立时间戳，新运行不覆盖旧批次。

```bash
# 配置预览，不联网、不保存最终数据
/usr/bin/python3 -B '/Users/liujunliang/Workspace/knowledge-legacy/scraper/美本申请规划局/collegex_crawler.py' --dry-run

# 已取得网站许可时运行
/usr/bin/python3 -B '/Users/liujunliang/Workspace/knowledge-legacy/scraper/美本申请规划局/collegex_crawler.py' --authorized --max-pages 15 --rate-limit 1.5 --timeout 30 --retries 2

# 离线测试
cd '/Users/liujunliang/Workspace/knowledge-legacy/scraper/美本申请规划局'
/usr/bin/python3 -B -m unittest -v test_collegex_crawler.py
```

## 维护

解析使用页面公开 JSON，无 HTML CSS 选择器依赖。若网站更改结构，先检查活动页引用的脚本与公开请求，更新 ENDPOINTS、parse_records 和离线 fixture；不要用新的猜测接口绕过认证。返回达到 1000 上限、两次内容不一致或 limit=1 不生效时程序停止，不标为完成。

历史核查曾因条款暂停；后续用户确认获授权，本次已完成。未进行 Git 提交或同步。

## JSON-LD 与内嵌结构化数据补充核查

未发现额外活动或活动字段，原数据维持 485 条。新增页面级元数据与静态解码证据，详见：

- [data/run_20261014T023053_084055Z/structured_audit_20261014T024035Z/核查结论.md](data/run_20261014T023053_084055Z/structured_audit_20261014T024035Z/核查结论.md)
- [data/run_20261014T023053_084055Z/structured_audit_20261014T024035Z/page_metadata.json](data/run_20261014T023053_084055Z/structured_audit_20261014T024035Z/page_metadata.json)

8 项离线测试通过；活动 CSV/JSONL 内容未改动。

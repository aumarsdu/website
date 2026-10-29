# 点路教育公开内容续抓验收

核验时间：2026-10-14T19:06:27.704594+00:00

| 数据集 | 列表发现 | 已归档详情 | 缺失 |
|---|---:|---:|---:|
| projects | 1097 | 1097 | 0 |
| articles | 98 | 98 | 0 |
| schools | 723 | 723 | 0 |

公开接口覆盖核验：通过。
项目详情复用旧归档：0 条；全部1097条已重新采集。
主站正文：2 条；外域正文已保存：0 条；外域正文待获取：96 条。
引用文件已下载：9720；失败/排除：994；剩余队列（未去重）：0。
公开内容归档完整核验：未通过。

资源范围已扩展到主站直接引用的公开文章与资源，包含视频，上限20 GB、24小时（从原始起点累计）。
robots/鉴权/验证码拒绝或资源上限均保留为未完成，不绕过。
后台、账户、学生资料、订单、支付及申请接口均排除。
大媒体保留在 data/assets/，不重复塞入 ZIP。

详见 completion_audit.json、completion_coverage.json、referenced_progress.json。

本次项目详情刷新：1097/1097；刷新状态：finished。
最新项目列表数量：1097；ID集合一致：True。
当前项目详情快照验收：通过（按各详情采集时间形成，非同时刻原子快照）。
项目内引用变化去重：新增 13；移除 14；全局变化见引用集合验收（历史文件保留）。

## 引用集合验收

本地引用重建：发现 10714 个唯一引用；已处理 10714；未处理 0。
有效非空文件：9718；零字节无效文件：2（保留原始回执）；最终失败/排除/质量异常：996。
文件按引用 URL 计数，有效内容 SHA-256 种类：6508；不同 URL 可能保存相同内容。
未处理清单：pending_references.json / pending_references.csv；失败清单：failed_references.csv。

原复用旧详情核对：1071/1071；另外重采本轮详情：26。
详情/列表原始响应文件校验失败：0。
当前项目唯一资源引用：7914；全局新增：9；全局移除：10。

项目正文公开媒体引用：3801；其中旧 Framework 地址：3720。原地址非空保存：3740；未处理：0；失败分类：{'robots_unavailable': 26, 'http_404': 17, 'host_access_denied_stop': 3, 'robots_disallowed': 14, 'robots_http_403': 1}。
旧地址文件 ID 中已有 0 个通过另一个独立发现的公开 API 引用保存；此对照不代表旧地址有效，也未据此改写 URL。

24小时续抓目标核对：原未处理唯一引用 3319；已处理 3319；有效非空保存 3265；已处理但未取得有效文件 54；仍未处理 0。
本次续抓未成功原因：{'robots_unavailable': 23, 'robots_disallowed': 14, 'http_404': 9, 'excluded_access_or_host': 8}。

停止原因：finished；网络阶段结束时间：2026-10-14T19:06:25.190172+00:00。
累计传输：12,122,596,034 bytes；上限：20,000,000,000 bytes，总24小时从原起点累计。
保留未完成分片：0 个，不计为有效保存文件。

| 失败/排除/质量原因 | 数量 |
|---|---:|
| robots_disallowed | 124 |
| excluded_access_or_host | 42 |
| robots_http_403 | 2 |
| http_404 | 795 |
| robots_unavailable | 28 |
| host_access_denied_stop | 3 |
| empty_payload | 2 |

网络实际运行代码快照：reports/runtime_code_24h。正文图片、附件链接及CSS背景图按原地址核对，不改写文件端点。

## 2026-10-15 补抓验收

# 点路公开归档补抓验收

验收时间：2026-10-15T13:24:29.792234+00:00。已完成授权队列处理和正文逐篇检索；仍有缺口，不能称全站完整离线归档。

## 数据和资源

原项目1097、文章98、学校723条均保留；原JSON、SQLite、断点、流量账本和失败清单哈希未变。
原异常996条；本轮资源复核816个唯一引用、817条尝试回执；新增有效文件2个，5,549,412 bytes。新增图片完整解码、大小和SHA均通过。
合并有效资源9720个、12,091,800,604 bytes；原引用仍有异常994条（含7条误引用，保持历史可追溯）。
另核验本地已存在的同FileId公开文件候选3条，未请求后台原地址，也未把后台原件标为恢复。共享最终目标的复用回执1条。
复核未取得有效文件原因：{'non_asset_payload': 1, 'robots_disallowed_or_unavailable': 24, 'http_404': 789}。

## 96篇正文

96篇均完成两轮检索，192次查询，48个批次回执；未请求被robots禁止的微信文章地址。
进一步核验8个候选页面，保存带原文标题图片标记及明确转载说明的同文候选2篇。
这些是公开转载版本；原微信正文不可取得，无法逐字核对是否删改、缺段、图片一致，未冒充原文恢复。原正文完全核验补齐数仍为0，原站缺口仍96篇。相关主题但无同文证据的页面单列，不能填入原正文。
候选结果：{'attributed_same_work_candidate': 2, 'related_content_identity_unverified': 3, 'robots_disallowed_or_unavailable': 3}。

## 流量和时限

原累计12,122,596,034 bytes；此前诊断72,845 bytes；本阶段HTTP响应体6,420,027 bytes。
可计量累计12,129,088,906 bytes；加搜索通信预留10,000,000 bytes，按预算计12,139,088,906 bytes，未达到累计20GB或本轮1GB上限。搜索工具未提供实际流量，预留不等同实测。
本轮开始2026-10-15T12:52:19.166691+00:00，截止epoch 1792083139.166826；验收时经过0.536小时。HTTP请求828次，限额1500。

## 验证与文件

SQLite integrity_check=ok；有效资源视图与合并JSON逐条一致；新旧来源分别记录。
原大媒体位于原data/assets/；新增媒体位于本补抓data/assets/。合并JSON中的资源路径相对于原20261014批次根目录。
combined_archive.sqlite保留原表，effective_resource_receipts为合并资源视图；原SQLite比manifest额外序列化error=null或error对象，已逐项核实其与顶层error_type一致，仅在视图中移除冗余error字段；所有其他字段逐条一致。supplement_article_candidates保留候选与身份限制。
resource_outcomes.csv覆盖全部996条异常；remaining_resource_failures.csv列出本轮后仍异常的原引用。
article_search_coverage.json/csv记录逐篇查询；article_outcomes.csv记录96篇逐项结果；article_candidates.json记录页面核验；articles_with_supplemental_sources.json保留原正文状态并附候选来源。
原失败回执和原报告压缩包保留；新版完整报告包另存，不重复打包大媒体。

后台、登录、robots禁止、鉴权和验证码未绕过；404、空响应和主题相近页面未重标为成功。

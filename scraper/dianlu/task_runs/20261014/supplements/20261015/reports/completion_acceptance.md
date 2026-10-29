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

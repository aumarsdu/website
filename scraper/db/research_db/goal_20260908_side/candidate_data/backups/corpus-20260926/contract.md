# T02 契约说明（candidate v1）

- 状态：候选，待独立复核（golden 期望 + 实现一致性 + 反例覆盖）。
- 机器可校验期望：`golden/t02_expectations.json`（冻结 sha256 见 evidence；由 `generate_golden.py` 的算法规格块生成，先于 `contract.py` 实现）。来源配置：`contract_config.json`（仅固定机制；各源白名单/身份字段在 T04/T06/T07 冻结为真实映射）。

## 1. 规则总纲

| 规则 | 定义 | 版本化 |
| --- | --- | --- |
| canonical JSON | `json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",",":"))` 的 UTF-8 文本 | 随 contract_version |
| 身份编码 | `canonical_json({"native_id": <原样字符串>, "source": <source_code>})`；`string_exact`，禁止数字归一（`0`≠`001`），无分隔符拼接歧义 | contract_version |
| 内容哈希 | `sha256(canonical_json({"business": <白名单内且出现的字段>, "hash_version": <v>}))`；排除采集时间、本地路径、随机值、处理日志 | hash_version（现为 h1） |
| 观察键 | `canonical_json({"batch", "context", "payload", "record"})`；batch+record 不足以去重，多入口上下文不丢 | contract_version |
| 字段状态 | `value / explicitly_empty / not_provided / extraction_failed` 四态互斥 | contract_version |

## 2. 可信观察顺序与投影（resolve_projection）

1. 投影取**已知序**最大的观察；order key 为 ISO-8601 UTC 时间字符串（字典序即时间序），T09/T10 消费前不得更改该类型约定；观察到达顺序（行序、导入序）永不决定胜者。
2. 最大序上出现多个不同 payload → `conflict`：保留全部冲突 payload，投影回退到此前最近的单 payload 序（最后已验证投影）；无可回退则 `payload=null` 且状态仍为 `conflict`（fail-closed，冲突可见，不假装无冲突）。
3. `observed_order=unknown` 的观察只进历史，永不参与投影。
4. A→B→A 保留三条观察，投影=A（历史不塌缩）。

## 3. 批次 manifest 规则

- 必填 12 字段见 `contract.REQUIRED_MANIFEST_FIELDS`；缺项或 `contract_version` 不符 → `contract_invalid`。
- `manifest_digest = sha256(canonical_json(manifest))`；同 `batch_id` 不同 digest → `identity_conflict` 拒绝。
- 字节相同、解析版本不同 → 新建 transformation_run（`canonical_json({batch, adapter_version})`），不伪造新采集事件，原观察保留。

## 4. 每来源身份配置（候选）

| source | id_field | 状态 |
| --- | --- | --- |
| jisi_future_sou_tools / jisi_future_domestic | `id` | candidate_until_T04（两入口独立 namespace） |
| zhongke | `uuid` | candidate_until_T04_precedence_check |
| hirep | `business_id` | candidate_until_T04 |
| yanqu_ocr | 无 | no_reliable_id_candidate_only（category+poster_file 是证据位置，非项目身份；T06 决定） |
| yinzhi_public | 无 | no_reliable_id_candidate_only（front-matter 编码标识页面，非项目；T07 决定） |

不按标题或文件路径固化身份；不默认假定同供应商入口共用 ID 空间。

## 5. 变更与兼容

- 任何规则变更必须升 `hash_version` 或 `contract_version`；旧哈希/旧观察不重算，历史保留。
- 白名单冻结于 T04/T06/T07；届时金额改十进制定点、日期补原文+精度+时区等表达变化会改变哈希，必须按本节升 hash_version。
- `validate_manifest` 是形状级校验（必填字段与版本）；`input_files` 子字段、`capture_mode`/`coverage` 枚举与行数对账由 T08 强校验负责，路径越界由 T01 target_guard 负责。
- golden 文件冻结后不得原地修改；修订通过新 hash_version 的新 golden 交付，并在本文件记录兼容说明。

## 6. 与原 Spec 条款对应

- §3.2 批次 manifest 全字段/对账/拒绝语义 → 第 3 节。
- §3.3 ID 编码、字段状态、哈希排除、同序冲突、unknown 顺序、not_seen 不推断下架 → 第 1、2 节（not_seen 在 T09/T10 落库）。
- §3.4 错误类别 → `contract_invalid`、`identity_conflict`（本模块）；其余类别归 T08/T09。

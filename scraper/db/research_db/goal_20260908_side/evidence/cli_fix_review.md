# T01 CLI 修复与剩余门禁

## 已修复

原 CLI 使用 register(root, inputs, inputs)，请求同时充当批准清单。现读取独立 registry，核验 approved_root、路径纳入与登记哈希。verify([]) 现拒绝空输入。

新增 5 项离线测试，其中 4 项验证真实 CLI 子进程：合法输入、交付副本拒绝、输入变更拒绝、错误根拒绝。原 12 项保留，17 项通过；ruff / format / pyright 通过。中途 import 排序 lint 失败，修正后重跑四项检查，未改变断言。

## 剩余门禁

source_registry 纳入/排除、pilot_manifest 语义代表性及原图关联仍未独立确认。位置抽样不能证明业务代表性；修订代码也需非实现者复核。T01 保持 WAITING_OWNER，其他首期任务依赖阻塞，D01 单独登记。

本轮没有调用子 Agent、执行 T02、连接旧库或启动数据库。属于实质进展，不是 live handle 等待；不承诺后台运行。前版证据在 before_cli_fix/，当前 candidate.patch 与哈希已更新，需按新版本评审。

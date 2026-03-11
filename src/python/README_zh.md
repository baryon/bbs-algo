# Python MVP 示例

中文 | [English](README.md)

这个目录包含几个可直接运行的 Python MVP，用来展示文档里讨论的几种 BBS 控制闭环。

当前共有三类 demo：

- 支付授权
- 开发安全防护
- 控制论式反馈收敛

这些示例重点是先验证工程闭环，不是论文里完整的 BBS 原语或零知识证明系统实现。

## 文件说明

- `bbs_payment_mvp.py`
  - 支付授权核心示例
  - 包含 action 模型、策略、签名器、验证器和 demo 场景
- `run_payment_demo.py`
  - 支付 demo 命令行入口
- `bbs_dev_guard_mvp.py`
  - 开发安全防护示例
  - 包含 `db_update` 和 `file_rm` 的策略、签名器、验证器和 demo 场景
- `run_dev_guard_demo.py`
  - 开发安全防护 demo 入口
- `bbs_cybernetics_mvp.py`
  - 控制论导向的反馈闭环示例
  - 展示 Agent 如何根据 Validator 的结构化反馈逐轮修正候选方案
- `run_cybernetics_demo.py`
  - 控制论 demo 入口

## 这些 MVP 覆盖什么

### 支付授权

支付 demo 验证的是这条闭环：

`Agent -> Action -> Sign -> Validator -> Execute`

策略为：

- 金额不超过 `200 USD`
- 收款方必须在白名单中

核心组件：

- `PaymentAction`
- `PaymentPolicy`
- `PolicyBoundSigner`
- `PaymentValidator`

### 开发安全防护

开发安全防护 demo 把同样的闭环应用到高风险开发动作上：

- `db_update`
- `file_rm`

它展示了如何在执行前用显式策略和 validator 复核来约束危险操作。

### 控制论反馈闭环

控制论 demo 聚焦于：

`Agent -> Validator -> Feedback -> Retry`

它不再绑定支付或开发动作，而是抽象展示：

- Validator 是传感器
- 结构化拒绝原因是误差信号
- Agent 是控制器，会逐轮缩小偏差

## 运行方式

在仓库根目录执行：

```bash
python3 src/python/run_payment_demo.py
python3 src/python/run_dev_guard_demo.py
python3 src/python/run_cybernetics_demo.py
```

## Demo 场景

### 支付 Demo

支付 demo 会输出 6 个场景：

1. `valid_request`
   - 合法支付通过
2. `signer_side_reject`
   - 超额支付在 signer 侧被拒绝
3. `validator_reject_policy_bypass`
   - 模拟绕过 signer 强行签名，但 validator 仍然拒绝
4. `validator_reject_unknown_key`
   - 未注册公钥被拒绝
5. `validator_reject_tamper`
   - 签名后篡改 payload，导致签名失效
6. `validator_reject_replay`
   - 重放 nonce 被拒绝

### 开发安全防护 Demo

开发安全防护 demo 会输出 8 个场景：

1. `valid_db_update`
   - 安全的 `staging` 单行更新通过
2. `signer_reject_db_update`
   - `production` 或非白名单批量更新在 signer 侧被拒绝
3. `validator_reject_db_policy_bypass`
   - 绕过 signer 的策略检查后，validator 仍然拒绝
4. `valid_file_rm`
   - 删除 `/workspace/sandbox/**` 下的文件通过
5. `signer_reject_file_rm`
   - 危险路径删除在 signer 侧被拒绝
6. `validator_reject_file_policy_bypass`
   - 绕过文件策略后，validator 仍然拒绝
7. `validator_reject_unknown_key`
   - 未注册公钥被拒绝
8. `validator_reject_replay`
   - 重放 nonce 被拒绝

### 控制论 Demo

控制论 demo 会输出 4 个场景：

1. `converges_with_structured_feedback`
   - 高分辨率反馈让 Agent 在有限轮次内收敛
2. `fails_with_coarse_feedback`
   - 只有粗粒度拒绝原因时，收敛效率下降，并在轮次上限内未通过
3. `fails_with_unreachable_target`
   - 目标超出执行器可达范围时，系统停止且无法收敛
4. `stops_without_feedback_channel`
   - Validator 不提供可操作反馈时，闭环无法继续

## 设计边界

这些示例都故意保持简单：

- 涉及签名的部分使用 `Ed25519` 普通签名
- 策略约束通过显式逻辑实现，不是零知识证明验证
- validator 会重新执行策略检查
- 不包含链上逻辑、共识或 gas 模型
- `db_update` 和 `file_rm` 只覆盖最小规则示例
- 控制论 demo 只演示反馈收敛，不包含真实 signer 或 BBS 证明机制

因此，更准确的定位是：

`BBS 风格控制闭环的工程 MVP`

而不是：

`完整的 BBS / PS-CMA / ZK 实现`

## 为什么仍然有价值

即使在这个简化版本里，这些 demo 仍然可以验证一些关键工程问题：

- 高风险 action 是否先被结构化
- signer 是否会提前拒绝非法请求
- validator 是否会强制检查注册身份和 payload 绑定
- nonce 重放保护是否有效
- 危险 DB 和文件操作是否能被确定性拦截
- 结构化反馈是否能驱动 Agent 逐步收敛

这些正是升级到更强 BBS 或 ZK 版本前最值得先跑通的部分。

## 可扩展方向

- 把 validator 包装成 HTTP 服务
- 增加更丰富的支付策略，例如每日额度和频率限制
- 把 action 模型扩展到 `api_call`、`fs.delete`、`db.query`
- 用带证明的签名方案替换普通签名
- 给开发安全防护增加更细的字段级、目录级和环境级策略
- 把控制论示例里的反馈协议映射到真实的 signer 和 validator 接口

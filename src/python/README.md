# Python MVP README

## 目标

这个目录提供一个最小可运行的 Python 版支付授权 MVP，用来验证下面这条工程闭环：

`Agent -> Action -> Sign -> Validator -> Execute`

这里的支付规则固定为一个简单例子：

- 金额不超过 `200 USD`
- 收款方必须在白名单中

这个 MVP 重点验证工程链路，不是论文中完整的 BBS 原语实现。

## 文件说明

- `bbs_payment_mvp.py`
  - 核心实现
  - 包含数据结构、签名器、校验器、示例场景
- `run_payment_demo.py`
  - 命令行演示入口
- `bbs_dev_guard_mvp.py`
  - 开发危险 action 约束示例
  - 包含 `db_update` 和 `file_rm` 的策略、签名器、校验器、示例场景
- `run_dev_guard_demo.py`
  - 开发危险 action demo 入口

## 实现内容

当前实现包含以下组件：

- `PaymentAction`
  - 表示一个结构化支付动作
- `PaymentPolicy`
  - 表示支付策略
- `PolicyBoundSigner`
  - 在签名前先检查策略
- `PaymentValidator`
  - 验证已注册公钥、签名、策略和重放

## 运行方式

在仓库根目录执行：

```bash
python3 src/python/run_payment_demo.py
```

运行开发危险 action 示例：

```bash
python3 src/python/run_dev_guard_demo.py
```

## 输出场景

Demo 会输出 6 个场景：

1. `valid_request`
   - 合法支付，请求通过
2. `signer_side_reject`
   - 超额支付，在 signer 侧先拒绝
3. `validator_reject_policy_bypass`
   - 模拟绕过 signer 强行签名，但 validator 仍然拒绝
4. `validator_reject_unknown_key`
   - 使用未注册公钥签名，被 validator 拒绝
5. `validator_reject_tamper`
   - 签名后篡改 payload，被判定为无效签名
6. `validator_reject_replay`
   - 重放同一请求，被 nonce 检测拒绝

开发危险 action 示例会输出 8 个场景：

1. `valid_db_update`
   - 允许的 `staging` 单行更新通过
2. `signer_reject_db_update`
   - `production` / 非白名单表 / 批量更新在 signer 侧被拒绝
3. `validator_reject_db_policy_bypass`
   - 强行绕过 signer 后，validator 仍拒绝危险 DB 更新
4. `valid_file_rm`
   - 删除 `/workspace/sandbox/**` 下临时文件通过
5. `signer_reject_file_rm`
   - 删除 `/etc/passwd` 在 signer 侧被拒绝
6. `validator_reject_file_policy_bypass`
   - 强行绕过 signer 后，validator 仍拒绝危险文件删除
7. `validator_reject_unknown_key`
   - 非注册公钥被拒绝
8. `validator_reject_replay`
   - 重放请求被拒绝

## 设计边界

这个实现故意保持简单，当前边界如下：

- 使用 `Ed25519` 普通签名
- 使用显式策略检查
- validator 会重新执行策略判断
- 不包含零知识证明
- 不包含链上逻辑、共识或 gas 模型
- `db_update` 和 `file_rm` 仅覆盖最小规则示例，不代表完整的系统权限模型

因此，它更准确的定位是：

`支付闭环工程 MVP`

而不是：

`完整的 BBS / PS-CMA / ZK 实现`

## 为什么仍然有价值

虽然它不是完整密码学原语实现，但它已经可以验证几个关键工程问题：

- 高风险 action 是否先被结构化
- signer 是否会先执行硬规则检查
- validator 是否只接受已注册公钥
- payload 是否和签名严格绑定
- nonce 是否能阻止重放
- `production` 数据库更新和系统目录删除是否能被当作危险 action 拦截

这些正是后续升级到更强 BBS/ZK 版本前，最值得先跑通的部分。

## 下一步可扩展方向

- 把 validator 包装成 HTTP 服务
- 增加更丰富的支付策略，如每日累计额度和频率限制
- 把 action 模型扩展到 `api_call`、`fs.delete`、`db.query`
- 将普通签名版本逐步替换为更强的证明型签名方案
- 为 `db_update` / `file_rm` 增加更细的字段级、目录级和环境级策略

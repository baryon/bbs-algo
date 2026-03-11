# TypeScript MVP README

## 目标

这个目录提供一个最小可运行的 TypeScript 版支付授权 MVP，与 Python 版本保持同样的工程目标：

`Agent -> Action -> Sign -> Validator -> Execute`

同样使用一个简单支付策略做验证例子：

- 金额不超过 `200 USD`
- 收款方必须在白名单中

它的作用是验证 TypeScript/Node 环境下的工程闭环，而不是实现论文中的完整 BBS 原语。

## 文件说明

- `bbsPaymentMvp.ts`
  - 核心实现
  - 包含数据结构、签名器、校验器、示例场景
- `runPaymentDemo.ts`
  - 命令行演示入口
- `bbsDevGuardMvp.ts`
  - 开发危险 action 约束示例
  - 包含 `db_update` 和 `file_rm` 的策略、签名器、校验器、示例场景
- `runDevGuardDemo.ts`
  - 开发危险 action demo 入口
- `tsconfig.json`
  - 最小 TypeScript 编译配置

## 实现内容

当前实现包含：

- `PaymentAction`
  - 结构化支付动作
- `PaymentPolicy`
  - 支付策略定义与策略求值
- `PolicyBoundSigner`
  - 先做策略检查，再生成签名请求
- `PaymentValidator`
  - 校验注册公钥、签名、策略和重放

## 运行方式

在仓库根目录执行：

```bash
ts-node -P src/typescript/tsconfig.json src/typescript/runPaymentDemo.ts
```

运行开发危险 action 示例：

```bash
ts-node -P src/typescript/tsconfig.json src/typescript/runDevGuardDemo.ts
```

如果只想检查能否编译：

```bash
tsc -p src/typescript/tsconfig.json
```

## 输出场景

Demo 会输出 6 个场景：

1. `valid_request`
   - 合法支付通过
2. `signer_side_reject`
   - 超额支付在 signer 侧被拒绝
3. `validator_reject_policy_bypass`
   - 绕过 signer 强行签名，但 validator 仍拒绝
4. `validator_reject_unknown_key`
   - 非注册公钥被拒绝
5. `validator_reject_tamper`
   - payload 被篡改，签名校验失败
6. `validator_reject_replay`
   - 重放请求被拒绝

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
   - 删除系统目录文件在 signer 侧被拒绝
6. `validator_reject_file_policy_bypass`
   - 强行绕过 signer 后，validator 仍拒绝危险文件删除
7. `validator_reject_unknown_key`
   - 非注册公钥被拒绝
8. `validator_reject_replay`
   - 重放请求被拒绝

## 设计边界

这个 TypeScript 版本和 Python 版本一样，是工程 MVP，不是完整 BBS 实现。

当前边界：

- 使用 Node `crypto` 中的 `Ed25519`
- 策略检查仍是显式业务逻辑
- validator 会重新执行策略校验
- 不包含零知识证明
- 不包含账本、链上执行或 gas 机制
- `db_update` 和 `file_rm` 仅覆盖最小规则示例，不代表完整的系统权限模型

## 关于类型检查

当前环境中缺少 `@types/node`，为了保证不额外安装依赖也能直接运行，核心文件顶部使用了：

```ts
// @ts-nocheck
```

这意味着：

- 代码可以直接运行
- `tsc` 可以通过当前最小配置
- 但这不是严格的生产级类型约束

如果后续要把这个目录演进成正式 Node/TS 项目，建议补上：

- `package.json`
- `@types/node`
- 更严格的 tsconfig
- 单元测试

## 为什么这个版本仍然值得保留

TypeScript 版的价值主要在于：

- 更接近很多 Agent 平台和网关服务的运行环境
- 更容易继续包装成 HTTP validator 或中间件
- 方便把 Python 原型迁移到 Node 服务栈
- 可以直接验证“危险 action 是否被结构化拦截”这类工程问题

## 下一步可扩展方向

- 提供 REST API 或 CLI 包装
- 将策略和注册表外置为配置文件
- 扩展到 `api_call`、`deploy.start`、`fs.delete` 等 action
- 在引入正式依赖后恢复严格类型检查
- 为 `db_update` / `file_rm` 引入更细粒度的策略表达

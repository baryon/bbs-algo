# BBS-Algo

一个围绕 BBS 落地思路构建的概念验证仓库，重点不是完整实现论文中的密码学原语，而是先把工程闭环跑通：

`Agent -> Action -> Sign -> Validator -> Execute`

当前仓库包含两类内容：

- `docs/`
  - 论文解读与落地设计备忘录
- `src/python` 和 `src/typescript`
  - 两套最小可运行 MVP
  - 用支付授权、数据库更新、文件删除三个例子验证“高风险 action 的结构化约束”

## 适合谁看

这份 README 面向开发者，适合下面几类读者：

- 想快速看懂仓库现在做到了什么
- 想直接运行 Python 或 TypeScript demo
- 想从工程角度理解 BBS 在 Agent 安全里的最小落地形态

## 当前实现了什么

当前仓库实现的是 `工程概念验证`，不是完整 BBS / PS-CMA / ZK 系统。

已经做了两类 MVP：

1. `支付授权 MVP`
   - 规则：`200 USD 以内 + 白名单收款方`
   - 验证：
     - signer 侧先做规则检查
     - validator 校验已注册公钥、签名绑定、策略、nonce 防重放

2. `开发危险 action 约束 MVP`
   - `db_update`
     - 允许：`staging`、白名单表、白名单字段、单行更新
     - 拒绝：`production`、非白名单表、危险字段、批量更新
   - `file_rm`
     - 允许：删除 `/workspace/sandbox/**`、`/workspace/tmp/**`
     - 拒绝：删除 `/etc`、`/usr`、`/bin` 等系统路径

## 快速运行

### Python

支付示例：

```bash
python3 src/python/run_payment_demo.py
```

开发危险 action 示例：

```bash
python3 src/python/run_dev_guard_demo.py
```

### TypeScript

支付示例：

```bash
ts-node -P src/typescript/tsconfig.json src/typescript/runPaymentDemo.ts
```

开发危险 action 示例：

```bash
ts-node -P src/typescript/tsconfig.json src/typescript/runDevGuardDemo.ts
```

如果只想检查 TS 是否能编译：

```bash
tsc -p src/typescript/tsconfig.json
```

## 运行后会看到什么

支付示例会展示：

- 合法请求通过
- signer 侧拒绝超额支付
- validator 拒绝策略绕过
- validator 拒绝未知公钥
- validator 拒绝 payload 篡改
- validator 拒绝重放

开发危险 action 示例会展示：

- 合法的 `db_update` 通过
- 危险的 `db_update` 在 signer 或 validator 侧被拒绝
- 合法的 `file_rm` 通过
- 删除系统路径的 `file_rm` 被拒绝
- 未知公钥和重放也会被拒绝

## 目录结构

```text
.
├── README.md
├── docs
│   ├── bbs-paper-explained.md
│   ├── bbs-application-memo.md
│   └── plans
├── paper
│   └── bbs.pdf
└── src
    ├── python
    │   ├── README.md
    │   ├── bbs_payment_mvp.py
    │   ├── run_payment_demo.py
    │   ├── bbs_dev_guard_mvp.py
    │   └── run_dev_guard_demo.py
    └── typescript
        ├── README.md
        ├── tsconfig.json
        ├── bbsPaymentMvp.ts
        ├── runPaymentDemo.ts
        ├── bbsDevGuardMvp.ts
        └── runDevGuardDemo.ts
```

## 先看哪几个文件

如果你第一次进仓库，我建议按这个顺序：

1. 看 [docs/bbs-application-memo.md](/Users/lilong/Works/BBS-Algo/docs/bbs-application-memo.md)
   - 理解为什么这里把 BBS 先落成“硬边界控制器”
2. 看 Python 支付 MVP：
   - [src/python/bbs_payment_mvp.py](/Users/lilong/Works/BBS-Algo/src/python/bbs_payment_mvp.py)
3. 看 Python 开发危险 action MVP：
   - [src/python/bbs_dev_guard_mvp.py](/Users/lilong/Works/BBS-Algo/src/python/bbs_dev_guard_mvp.py)
4. 再看 TypeScript 对应实现：
   - [src/typescript/bbsPaymentMvp.ts](/Users/lilong/Works/BBS-Algo/src/typescript/bbsPaymentMvp.ts)
   - [src/typescript/bbsDevGuardMvp.ts](/Users/lilong/Works/BBS-Algo/src/typescript/bbsDevGuardMvp.ts)

## 这个仓库故意没有做什么

为了把验证边界收紧，这个仓库当前没有做：

- 完整 BBS 原语实现
- 零知识证明电路
- 链上验证
- 共识协议
- gas 模型
- 网络服务化
- 严格生产级密钥管理

也就是说，当前代码是在验证：

`如果把高风险动作先结构化，再绑定签名、公钥注册表、策略检查和 nonce，闭环是否能工作。`

## 已知边界

- 当前 Python 和 TypeScript 版本都使用普通签名，不是完整 ZK/BBS
- TypeScript 版为了兼容当前环境，使用了 `// @ts-nocheck`
- `db_update` 和 `file_rm` 只覆盖最小策略示例，不代表完整系统权限模型
- 当前目录不是 Git 仓库，没有 commit 历史

## 下一步建议

如果继续往前推进，最自然的路线是：

1. 把 validator 包装成 HTTP 服务
2. 把策略和公钥注册表外置成配置
3. 抽象统一的 `action` 注册机制
4. 增加 `api_call`、`deploy.start` 等更多高风险 action
5. 最后再讨论是否升级到更强的 BBS/ZK 版本

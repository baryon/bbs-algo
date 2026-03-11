# BBS-Algo

**行为约束签名：AI Agent 安全的密码学方案**

中文 | [日本語](README_ja.md) | [English](README.md)

---

BBS-Algo 是**行为约束签名（Behavior-Bounded Signatures, BBS）**的概念验证实现。与依赖软件层 guardrails 的传统方案不同，BBS 将策略约束嵌入签名机制本身——使违反策略的操作在**数学上不可能**被签署，而不仅仅是"被代码检查拒绝"。

## 问题背景

传统 AI Agent 授权架构将身份验证与行为验证分离：

```
私钥 + 普通签名    →  "谁授权了这个操作？"
软件层 + 策略检查  →  "这个操作应该被授权吗？"
```

只要 Agent 持有有效密钥，其签名在密码学层面就是合法的——无论操作是否违反安全策略。策略检查存在于软件层（中间件、guardrails、Prompt 指令），这些层都可能被 Prompt 注入、代码缺陷或供应链攻击绕过。

BBS 消除了这个缺口：**如果操作违反策略，有效签名无法被生成。**

## 工作原理

```
Agent → 操作 → 策略约束签名器 → 策略满足？
                                 ├─ 是 → 生成有效签名 → 验证器 → 执行
                                 └─ 否 → 数学上无法签名 → 拒绝
```

核心属性：

- **操作绑定** — 签名覆盖整个规范化操作，篡改任何字段都会使签名失效
- **策略指纹** — 密码学哈希确保签名器和验证器使用相同策略版本
- **重放保护** — 每个操作绑定唯一 nonce
- **封闭执行路径** — 高风险执行器仅接受经过验证的签名请求，没有后门

## 仓库结构

```
.
├── paper/
│   ├── bbs.pdf                              # BBS 原始论文
│   └── behavior-constrained-agent-systems-paper.pdf
├── docs/
│   ├── bbs-paper-explained.md               # 论文解读
│   ├── bbs-application-memo.md              # 工程设计备忘录
│   ├── bbs-engineering-implementation.md    # 实现指南
│   ├── behavior-constrained-agent-systems-paper.md
│   ├── ai-agent-safety-crisis-and-bbs-solution.md  # 行业背景与安全事件分析
│   └── ai-agent-safety-crisis-and-bbs-solution-en.md  # 同一文章英文版
└── src/
    └── python/
        ├── bbs_payment_mvp.py               # 支付授权 MVP
        ├── bbs_dev_guard_mvp.py             # 开发安全防护 MVP
        ├── bbs_cybernetics_mvp.py           # 控制论反馈闭环 MVP
        ├── run_payment_demo.py              # 支付演示运行器
        ├── run_dev_guard_demo.py            # 开发防护演示运行器
        └── run_cybernetics_demo.py          # 控制论演示运行器
```

## 快速运行

```bash
# 支付授权演示
python3 src/python/run_payment_demo.py

# 开发安全防护演示
python3 src/python/run_dev_guard_demo.py

# 控制论反馈闭环演示
python3 src/python/run_cybernetics_demo.py
```

## MVP 覆盖场景

### 支付授权

策略：单笔最高 200 USD，收款方必须在白名单内。

| 场景 | 结果 |
|------|------|
| 合规支付（168.50 USD → vendor_123） | ✅ 通过 |
| 超额支付（243 USD） | ❌ 签名器拒绝 |
| 策略绕过（攻击者直接签名） | ❌ 验证器检测到策略不匹配 |
| 未知密钥 | ❌ 验证器拒绝未注册公钥 |
| 载荷篡改（签名后修改收款人） | ❌ 签名验证失败 |
| 重放攻击（重用 nonce） | ❌ 验证器阻断 |

### 开发安全防护

**数据库更新** — 仅允许 staging 环境、白名单表/字段、单行操作：

| 场景 | 结果 |
|------|------|
| staging / feature_flags / enabled / 1 行 | ✅ 通过 |
| production / users / role / 批量更新 | ❌ 拒绝 |

**文件删除** — 仅允许 sandbox/tmp 路径：

| 场景 | 结果 |
|------|------|
| /workspace/sandbox/\*\* | ✅ 通过 |
| /etc/passwd | ❌ 拒绝 |

### 控制论反馈闭环

演示 BBS 闭环如何作为负反馈控制系统运作。Agent 在验证器反馈的引导下，朝多维验收标准（质量、成本、延迟、风险）迭代收敛。

| 场景 | 反馈模式 | 结果 |
|------|---------|------|
| 精确反馈 + 可达目标 | 每个维度的精确偏差值 | ✅ 3-4 轮收敛 |
| 粗反馈 + 相同目标 | 仅违反原因，无偏差值 | ❌ 有限轮次内未收敛 |
| 精确反馈 + 不可达目标 | 精确偏差值 | ❌ Agent 触及执行器极限，主动停止 |
| 无反馈通道 | 不返回任何信息 | ❌ Agent 无法修正，立即停止 |

## 论文与文档

| 文档 | 说明 |
|------|------|
| [paper/bbs.pdf](paper/bbs.pdf) | BBS 原始论文 — PS-CMA 安全模型和行为约束签名方案的形式化定义。Zenodo: https://zenodo.org/records/18811273。DOI: `10.5281/zenodo.18811273` |
| [paper/behavior-constrained-agent-systems-paper.pdf](paper/behavior-constrained-agent-systems-paper.pdf) | 行为约束 Agent 系统扩展论文。Zenodo: https://zenodo.org/records/18952739。DOI: `10.5281/zenodo.18952739` |
| [docs/bbs-paper-explained.md](docs/bbs-paper-explained.md) | 论文核心概念的通俗解读 |
| [docs/bbs-application-memo.md](docs/bbs-application-memo.md) | 工程设计备忘录 — 为什么将 BBS 实现为"硬边界控制器"及实际部署考量 |
| [docs/bbs-engineering-implementation.md](docs/bbs-engineering-implementation.md) | 实现指南 — 架构层次、操作建模、生产路线图 |
| [docs/behavior-constrained-agent-systems-paper.md](docs/behavior-constrained-agent-systems-paper.md) | 论文 Markdown 全文 |
| [docs/ai-agent-safety-crisis-and-bbs-solution.md](docs/ai-agent-safety-crisis-and-bbs-solution.md) | AI Agent 安全危机与 BBS 方案科普文章 |
| [docs/ai-agent-safety-crisis-and-bbs-solution-en.md](docs/ai-agent-safety-crisis-and-bbs-solution-en.md) | 同一文章的英文版 |

## 项目范围

本仓库是**工程概念验证**。为保持控制流清晰可审计，当前使用 Ed25519 签名而非完整零知识证明。MVP 验证了 `Agent → 签名器 → 验证器 → 执行器` 闭环在策略绑定、操作绑定、重放保护、结构化拒绝反馈以及反馈精度驱动的控制论收敛下的端到端可行性。

未包含：ZK 证明电路、链上验证、共识协议、生产级密钥管理、网络服务封装。

## 许可证

MIT

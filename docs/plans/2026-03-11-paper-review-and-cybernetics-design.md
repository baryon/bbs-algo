## Behavior-Constrained Agent Systems Paper Revision Design

日期：2026-03-11

## 目标

把英文主稿 `docs/behavior-constrained-agent-systems-paper.md` 提升为更强的 workshop-style systems paper。

本次修订的重点是：

- 加入并强化控制论 / cybernetics 视角
- 提高论文式表达质量
- 明确与参考论文及其作者 `Y.Y.N. Li` 的关系
- 让全文主线从“工程备忘录式罗列”转为“可辩护的 systems framing”

## 稿件定位

目标稿型不是完整的理论密码学论文，也不是一般博客或备忘录，而是：

`workshop-style systems position paper`

这意味着修订重点应放在：

- clear thesis
- explicit contributions
- disciplined scope and non-goals
- stronger section transitions
- better objection handling
- a distinctive interpretive lens

而不是强行补齐并不充分的 formal model 或 related work 体系。

## 核心主张

修订后的主张是：

`For high-risk agent actions, behavior-constrained authorization should be understood and deployed as a negative-feedback control architecture, not merely as a stronger signature primitive.`

这一定义把控制论内容从附属说明提升为主线框架。

## 与参考论文的关系

主稿中应明确说明：

- 本文建立在 `Y.Y.N. Li` 的参考论文之上
- 参考论文主要提供行为约束签名的密码学思想与安全直觉
- 本文的贡献不是新的密码学构造，而是 systems framing、deployment architecture 和 control-theoretic interpretation

这部分不扩展为完整 related work，只增加一个简洁但明确的定位段。

## 主要修订项

### 1. 摘要重写

摘要将明确写出：

- reference paper and author
- this paper's systems contribution
- control-theoretic framing
- main deployment thesis

### 2. 引言重写

引言将：

- 更清楚描述 over-authorization 问题
- 明确本文与参考论文的关系
- 给出本文的 paper-level contribution summary

### 3. Position 章节增强

将当前立场表述强化为显式贡献点，例如：

- systems framing for bounded authorization
- control-theoretic interpretation of validator feedback
- action-structured deployment architecture
- practical claim that blockchain is optional for initial deployment

### 4. 新增控制论核心章节

将在控制环路章节之后加入一个更强的 cybernetics section，内容包括：

- negative feedback loop
- validator as sensor
- structured rejection reasons as error signals
- task goals and safety constraints as isomorphic reference signals
- separation principle: control and observation should be independent

### 5. 应用章节压缩与整合

应用章节保留，但减少重复枚举，使其更像支撑论点的案例。

### 6. Discussion / Conclusion 强化

补足：

- what the approach does not solve
- why this is still useful before full cryptographic deployment
- why the control-theoretic framing matters

## 风格要求

- 语气稳健，不夸大
- 明确区分 claim、scope、limitation
- 避免像产品说明或备忘录罗列
- 强调 paper contribution 而非 implementation checklist

## 涉及文件

- 修改：`docs/behavior-constrained-agent-systems-paper.md`

## 验证标准

修订完成后应满足：

- 读者能在摘要和引言中清楚知道本文贡献
- `Y.Y.N. Li` 及参考论文被明确提及
- 控制论内容成为论文主线之一，而不是边缘补充
- 应用章节不再主导全文节奏
- 结论能准确回收全文主张

## 备注

当前会话没有 `writing-plans` skill，因此本次在设计确认后直接进入实施。

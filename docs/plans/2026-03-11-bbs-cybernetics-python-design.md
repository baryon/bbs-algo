## BBS Cybernetics Python Demo Design

日期：2026-03-11

## 目标

新增一个独立的 Python 示例，把 `docs/bbs-application-memo.md` 第 16 节“从控制论视角看 BBS 闭环”的核心观点落成可运行代码。

这个示例不绑定支付或开发动作，而是展示一个更抽象但仍保留 Agent 语义的闭环：

`Agent -> Validator -> Feedback -> Retry`

重点不是密码学签名，而是：

- Validator 作为“传感器”测量偏差
- 结构化拒绝原因作为“误差信号”
- Agent 作为“控制器”根据偏差逐轮修正
- 高分辨率反馈如何帮助系统收敛

## 采用方案

采用“通用候选方案收敛”方案，而不是单变量 toy model 或偏开发场景的验收器。

原因：

- 比单变量数值调节更接近 Agent 系统
- 比任务验收器更通用，不绑定代码生成场景
- 能清楚表达“任务目标”和“安全约束”在控制论结构上的同构

## 架构

新增文件：

- `src/python/bbs_cybernetics_mvp.py`
- `src/python/run_cybernetics_demo.py`

更新文件：

- `src/python/README.md`

核心对象：

- `CandidateAction`
  - 一轮候选方案
  - 包含 `quality_score`、`cost`、`latency_ms`、`risk_score`、`iteration`、`nonce`
- `ControlPolicy`
  - 目标和边界
  - 例如 `quality >= 80`、`cost <= 100`、`latency <= 250`、`risk <= 20`
- `ValidationResult`
  - 包含 `accepted`、`stage`、`reasons`、`measurements`、`deviations`
- `AdaptiveAgent`
  - 一个确定性的修正器
  - 根据反馈调整候选方案
- `ControlValidator`
  - 负责测量候选方案与策略目标的偏差
  - 支持高分辨率反馈和粗粒度反馈两种模式

## 数据流

1. Agent 生成初始 `CandidateAction`
2. Validator 评估候选方案
3. Validator 返回结构化结果：
   - `reasons`：语义化拒绝原因
   - `measurements`：当前实际值
   - `deviations`：与目标的偏差量
4. Agent 根据反馈修正候选方案
5. 重复，直到：
   - 方案被接受
   - 达到最大迭代轮数
   - 无法继续修正

其中：

- `reasons` 对应文档中的“结构化误差信号”
- `deviations` 对应控制论里的“偏差量”

## Demo 场景

计划输出 4 个场景：

1. `converges_with_structured_feedback`
   - Validator 返回完整偏差
   - Agent 逐轮修正并在有限轮次内通过

2. `fails_with_coarse_feedback`
   - Validator 只返回粗粒度拒绝信息
   - Agent 只能固定步长盲调
   - 展示低分辨率反馈导致收敛效率下降

3. `fails_with_unreachable_target`
   - 策略被设置为难以同时满足
   - Agent 一直调整但在最大轮次内仍不通过
   - 用来说明不可达设定点

4. `stops_without_feedback_channel`
   - Validator 只给出拒绝结论，不给可操作反馈
   - Agent 无法继续修正
   - 用来说明无反馈就无法形成有效控制回路

## 输出格式

每个场景输出一个 JSON 对象，包含：

- `policy`
- `initial_action`
- `history`
- `final_result`

`history` 中每轮记录：

- `iteration`
- `candidate`
- `validation`
- `adjustments`

## 实现边界

这个示例刻意不做以下内容：

- 不接入支付或开发动作的签名器逻辑
- 不实现真实 BBS 或零知识证明
- 不抽象成通用策略 DSL
- 不引入随机搜索、强化学习或 PID 控制器

目标是一个最小但足够清楚的演示程序，而不是一个框架。

## 验证方式

实现完成后验证：

- `python3 src/python/run_cybernetics_demo.py` 能运行
- 主场景能在有限轮数内收敛
- 粗粒度反馈场景不出现假阳性通过
- 不可达目标场景以未收敛结束
- 无反馈通道场景明确停止修正

## 备注

本仓库当前无法按 skill 说明继续切到 `writing-plans`，因为该 skill 不在当前会话可用列表中。本次直接基于已确认设计进入实现。

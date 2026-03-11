# BBS 算法工程实现说明书

副标题：面向产品化落地的流程图、系统流程与技术要点

## 1. 文档目标

这份文档不解释某个 Python 原型脚本，而是直接回答：

1. `BBS 算法如果按工程系统落地，整体流程应该长什么样？`
2. `每个环节需要什么输入、输出和边界？`
3. `真正做成产品级时，哪些技术点最关键？`

这里的 `BBS` 按论文语义理解为：

`把行为约束写进签名有效性本身的受限签名系统`

也就是：

- 不是只有“谁能签”的问题
- 还要回答“签出来的 action 是否满足预设策略”

文档重点是：

- 工程实现流程图
- 系统分层
- 产品级技术要点

而不是：

- 论文逐节解释
- 某段示例代码讲解

## 2. BBS 工程落地的最小目标

一个工程化的 BBS 系统，最小要做到下面这件事：

`只有当结构化 action 满足预设策略时，系统才生成可被 validator 接受的签名包。`

这里的“签名包”在工程上通常包含：

- action 本身
- action 绑定值
- proof 或 proof-bound signature
- 公共输入
- policy / circuit version
- nonce / epoch

如果系统只是：

- 普通签名
- 外加软件规则检查

那它仍然是传统“签名 + 风控”模型，还不是 BBS 的核心工程语义。

## 3. 系统角色图

在产品工程里，我建议把 BBS 系统拆成下面几个角色：

```text
Policy Author
  |
  v
Policy Registry / Circuit Registry
  |
  v
Signer / Prover Service
  |
  v
Validator Service
  |
  v
Execution Gate / Executor
  |
  v
Audit / Monitoring / Analytics
```

每个角色的职责不同：

- `Policy Author`
  - 定义允许的行为边界
- `Policy Registry`
  - 维护策略版本、参数和电路版本
- `Signer / Prover`
  - 生成受限签名或证明
- `Validator`
  - 验证 action 绑定、公钥、proof、nonce、策略版本
- `Executor`
  - 只执行通过验证的请求
- `Audit`
  - 记录历史、监控异常、支持追责

## 4. 端到端工程流程图

这是最重要的一张图。

```text
1. Define Policy
   |
   v
2. Compile Policy into Circuit / Constraints
   |
   v
3. Generate or Register Identity
   |
   v
4. Bind Identity to Policy Version
   |
   v
5. Agent creates structured action
   |
   v
6. Signer / Prover derives witness
   |
   v
7. Generate proof-bound signature package
   |
   v
8. Validator verifies:
      - public key registration
      - action binding
      - policy version
      - proof validity
      - replay / nonce / epoch
   |
   v
9. Execution gate accepts or rejects
   |
   v
10. Audit and monitoring record result
```

### 这条流程的核心思想

它强调的是：

- 策略先存在
- action 必须先结构化
- proof 必须绑定 action 和策略版本
- validator 是唯一入口
- executor 不能绕过 validator

## 5. KeyGen / Identity Binding 流程图

```text
seed / secret material
  |
  v
derive private witness material
  |
  v
derive public identity commitment
  |
  v
attach policy id / policy fingerprint / circuit version
  |
  v
register public key + policy binding
```

### 工程要点

1. `身份绑定` 不应只绑定到公钥，还要绑定到：
   - policy version
   - circuit version
   - 可选 capability scope

2. `KeyGen` 产出不只是密钥对，还应产出：
   - identity record
   - registry record
   - revocation handle

3. `Validator` 不应只问“签名是不是对的”，还要问：
   - 这个公钥是否注册
   - 这个公钥是否被允许执行这类 action
   - 它对应的是哪一版策略

## 6. Action 建模流程图

```text
Agent intent
  |
  v
normalize into structured action
  |
  v
canonical serialization
  |
  v
action hash / action binding value
  |
  v
pass into signer / prover
```

### 工程要点

这是整个系统最容易被低估的一步。

如果 action 没有先结构化，后面的 BBS 几乎无从谈起。

每种 action 都应当明确：

- 字段定义
- 编码顺序
- 哈希绑定方式
- 哪些字段是公共输入
- 哪些字段通过 witness 隐含证明

例如：

- `payment`
  - amount
  - currency
  - recipient
  - invoice hash
  - epoch
  - nonce

- `db_update`
  - env
  - table
  - fields
  - where scope
  - row limit
  - epoch
  - nonce

- `file_rm`
  - path
  - recursive
  - epoch
  - nonce

## 7. Sign / Prove 流程图

```text
structured action
  |
  v
load active policy + circuit version
  |
  v
derive witness:
  - secret key material
  - policy witness
  - optional state witness
  |
  v
build public inputs:
  - action binding
  - pk / identity commitment
  - policy fingerprint
  - epoch / nonce
  |
  v
run prover
  |
  +--> unsatisfied: no proof, reject
  |
  +--> satisfied: emit proof-bound signature package
```

### 工程要点

1. `Signer` 和 `Prover` 在产品级最好视为同一安全边界。

2. `Signer` 不应只做普通签名，它应负责：
   - witness 派生
   - proving
   - 组装 proof-bound package

3. 如果约束不满足，正确行为是：

`没有合法输出`

而不是：

`先签了，再让下游拦`

4. 产品级系统里，不应该把 witness 暴露给 validator。

## 8. Verify 流程图

```text
receive signed package
  |
  v
lookup registered public key
  |
  v
check key-policy binding
  |
  v
recompute action binding
  |
  v
verify succinct proof
  |
  v
check nonce / replay / epoch / revocation
  |
  +--> reject
  |
  +--> accept
```

### 工程要点

产品级 validator 的核心是：

- 不知道 witness
- 不重放秘密中间值
- 只验证公共输入和真实 proof

validator 的最小职责：

1. 公钥注册检查
2. action binding 检查
3. proof 验证
4. policy / circuit version 检查
5. nonce / replay 检查
6. 撤销与过期检查

## 9. Execute / Gate 流程图

```text
validator accepted request
  |
  v
forward to execution gate
  |
  v
executor performs action
  |
  v
result logged to audit system
```

### 工程要点

这里最关键的一句是：

`Executor 不能存在绕过 validator 的旁路。`

否则整个 BBS 只会变成“可选增强”，而不是“硬边界”。

所以：

- 旧接口要封掉
- 管理员旁路要隔离
- 内部脚本不能直连执行器
- 所有高风险动作只能走 validator 入口

## 10. Audit 流程图

```text
accepted / rejected requests
  |
  v
append immutable logs
  |
  v
aggregate by identity / policy / action type
  |
  v
produce compliance metrics and anomaly signals
```

### 工程要点

产品级 audit 至少要记录：

- action type
- action hash
- public key / identity id
- policy version
- proof verification result
- rejection reason
- nonce / epoch
- execution result

如果论文里还想做到更强的聚合审计，则额外需要：

- commitment aggregation
- 历史承诺存储
- 聚合验证逻辑

## 11. BBS 产品实现的关键技术点

## 11.1 Policy Registry

策略不能散在代码里，必须做成注册与版本化系统。

至少需要：

- policy id
- policy parameters
- circuit version
- created / revoked time
- compatibility rules

没有这层，系统会很快出现：

- 策略漂移
- proof 与 validator 版本不一致
- 老身份无法解释新策略

## 11.2 Circuit Registry

如果策略需要编译成电路，那么必须单独管理：

- circuit id
- proving key
- verifying key
- public input layout
- witness schema

这是产品级系统和“单脚本原型”的最大差别之一。

## 11.3 Key Management

产品级不应该让 Agent 直接持有长期原始秘密。

推荐做法是：

- 受控 signer / prover 服务
- HSM 或隔离密钥服务
- 短生命周期委托身份
- 吊销与轮换机制

## 11.4 Replay Protection

BBS 系统里，nonce 不是附属细节，而是核心流程的一部分。

至少要设计：

- nonce 生成策略
- per-agent nonce store
- time window / epoch binding
- 幂等与重试策略

否则 proof 再强，也会被重放攻击破坏执行层安全。

## 11.5 Public Inputs 设计

公开输入的设计会直接决定：

- proof 可验证性
- action 绑定是否充分
- 隐私泄露边界
- validator 实现复杂度

公开输入太少：

- validator 无法正确绑定 action

公开输入太多：

- 隐私和可升级性会受损

## 11.6 State-Dependent Constraints

很多真实策略不是纯静态的，而是依赖状态：

- 频率限制
- 每日累计金额
- 白名单版本
- 历史行为引用

这类约束真正产品化时最难。

原因是它们需要：

- 状态承诺
- 历史引用
- 状态新鲜度
- 版本一致性

这往往比单纯的 `delta < epsilon` 更难实现。

## 11.7 Failure Semantics

系统必须能清楚区分三类失败：

1. `policy unsatisfied`
2. `proof invalid`
3. `system error`

否则上层 Agent 无法正确反馈修正。

例如：

- policy unsatisfied
  - 可以尝试改 action 再提
- proof invalid
  - 说明 signer/prover 或 payload binding 有问题
- system error
  - 说明基础设施异常，不应继续盲重试

## 12. 面向产品化的注意事项

## 12.1 不要把所有规则都塞进 BBS

BBS 适合硬边界：

- 金额
- 白名单
- 路径范围
- 环境范围
- 字段白名单
- 频率限制

不适合软判断：

- 代码质量
- 业务合理性
- 文案优雅度
- 方案是否“最好”

## 12.2 旁路比密码学错误更常见

真实系统里，更常见的问题不是 proof 被攻破，而是：

- 旧 API 还在
- 管理员脚本直连执行器
- 调试入口未关闭
- 旁路队列未纳管

所以产品级设计必须把：

`execution gate`

当成一等公民，而不是附属模块。

## 12.3 性能预算要前置

BBS 产品化必须在设计阶段就明确：

- 单次 proving latency
- 单次 verification latency
- validator 并发吞吐
- nonce store 写入成本
- key / policy lookup 成本

否则系统后期很容易因为 proving 或状态检查过慢而失效。

## 12.4 版本升级要有策略

策略升级一定会发生，因此必须提前设计：

- policy migration
- circuit migration
- key rebinding
- old proof compatibility window
- revocation and grace period

## 12.5 可观测性不能后补

必须从一开始就具备：

- structured log
- proof verify result metrics
- rejection reason metrics
- replay metrics
- policy mismatch metrics
- latency histogram

否则出了问题只能靠猜。

## 13. 建议的产品演进路线

## 阶段 1：Action-first 原型

目标：

- 先把 action 结构化
- 先把 signer / validator / executor 链路跑通
- 即便暂时还是普通签名，也先把工程边界固定下来

## 阶段 2：Policy-bound MVP

目标：

- 引入明确的 policy registry
- 引入 key-policy binding
- 引入 nonce / replay store
- 把 payment / db_update / file_rm 这类硬规则跑通

## 阶段 3：Proof system integration

目标：

- 真正集成 Groth16 / PLONK 等 proof system
- validator 不再依赖 witness
- 固化 public input layout 和 circuit versioning

## 阶段 4：Production hardening

目标：

- HSM / signer isolation
- key rotation / revocation
- audit pipeline
- observability
- failover
- performance tuning

## 14. 最后总结

BBS 算法的工程实现，核心不是“写出一个 sign() 和 verify() 函数”，而是搭出一条完整的受限执行链：

`Policy -> Circuit -> Identity Binding -> Structured Action -> Sign/Prove -> Validate -> Execute -> Audit`

如果缺了其中任一关键环节，BBS 很容易退化成：

- 普通签名 + 规则引擎
- 或一套漂亮但可被旁路绕过的验证层

真正的产品级技术重点有三条：

1. action 必须先结构化并和 proof 绑定
2. validator 必须是唯一执行入口
3. proof system、policy version、key binding、nonce/replay 必须一起设计

如果沿着这个顺序推进，BBS 才有机会从论文概念走向可用系统。

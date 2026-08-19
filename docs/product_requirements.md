# AI Output Eval Lab — Retrospective / As-built Product Requirements Document

## 0. 文档信息

- 文档类型：Retrospective / As-built PRD
- 产品状态：Formal experiment complete；正式实现、实验记录和文档位于 implementation delivery branch
- 事实来源：approved design spec、真实 source tree、formal SQLite records、run sheets、methodology、final report、README 与历史 Skill provenance
- 写作边界：本文是项目完成后的产品需求沉淀，不应被解释为 2026-08-13 项目启动前已经存在的原始 PRD
- 证据标签：Confirmed = 文件、Git 或只读 DB 可直接确认；Strongly evidenced = 多份 artifact 一致支持；Not verified = 当前资料不能确认；Optional future work = 当前项目不需要
- 官方实现位置：codex/ai-output-eval-lab-implementation

## 1. 产品概述

### 1.1 一句话定位

AI Output Eval Lab 是一个本地、可审计的 Prompt 评测工作台，用固定 Task Pack、Formal Case Set、确定性规则、盲测语义 Grader 和独立 Human Review，把“Prompt 看起来变好了”转化为可复核的实验结论。

### 1.2 产品背景

生成模型输出具有概率性。单次输出更好，不能证明 Prompt 修改有效；手工挑选较好结果，也无法说明是否引入了结构、事实或语言回归。本项目因此保存 Prompt、Case、首次 raw response、规则结果、Grader 结果、人工判断和 correction provenance。

### 1.3 核心问题

在一个固定的 Grounded Structured Brief Generation 任务中，如何判断一次最小 Prompt 修改是否真正减少已观察到的失败模式，同时没有引入新的结构性或语义性问题？

### 1.4 为什么需要 AI

Generator 任务本身需要自然语言理解与结构化生成；Blind Grader 需要对 required facts、closed-world groundedness、语言和可读性做语义判断。AI 是被评测对象和部分语义评测器，而不是整个系统的唯一判断来源。

### 1.5 非 AI baseline / alternative

- Python deterministic rules：验证 JSON、schema、字段数量和字符长度。
- SQLite / SQL / Pandas：保存记录并做只读、描述性分析。
- Owner Human Review：处理抽样、indeterminate、unsupported-claim 或程序性异常。
- 如果不使用模型，仍可完成 schema/length 检查、人工复核和结果记录；但无法获得正式 Generator 输出和语义 Grader 结果。
- 本项目没有运行另一个模型作为对照 baseline，也没有建立线上业务基线。

## 2. 用户与场景

### 2.1 Primary user

项目 owner / LLM evaluation practitioner：设计任务和 Case，审批正式资产，执行或协调手工模型生成，复核结果，处理纠正并做最终推荐。

### 2.2 Secondary stakeholders / review audiences

- reviewer：检查 blind review、correction 和最终证据；
- engineer：检查 schema、workflow gate、测试与 provenance；
- future maintainer：在不重写历史记录的情况下继续实验；
- interviewer：作为 portfolio / project review audience，理解一个真实的 AI 产品评测项目如何落地；不是 AI Output Eval Lab 的核心 product operator。

这里没有用户访谈样本、线上用户规模或商业客户数据；需求来自项目 owner 的实际评测目标和已完成 artifact。

### 2.3 典型场景

1. Owner 冻结 Prompt v1，先在 18 个 Dev Cases 上收集首次真实输出。
2. Owner 根据 Dev failure analysis 起草并冻结 Prompt v2。
3. 系统在 Holdout 首次开放后，对相同 Case identity 的 v1/v2 进行配对。
4. Reviewer 在看不到 automatic outcome 的情况下完成预声明的 Human Review。
5. Owner 查看 paired comparison，并决定是否推荐 Prompt v2。

## 3. 产品目标

### 3.1 核心目标

将一次 Prompt iteration 变成可审计、可复核、可解释的 evaluation workflow。

### 3.2 质量目标

- 保留 first actual response，即使它是 malformed JSON 或质量失败。
- 把 deterministic failure、semantic failure、technical failure 和 Human Review 分开。
- 防止 Prompt version、split、generator、Grader condition 和 automatic outcome 泄漏到 blind packet。
- 保留错误历史，不用删除或覆盖制造“干净结果”。
- 让最终建议只回答当前固定任务设置，不扩大成通用模型能力结论。

### 3.3 成功标准边界

本项目没有预先编造业务 KPI、流量 KPI、成本目标或统计显著性门槛。成功由真实的工程和实验 acceptance evidence 判断，见第 14 节。

## 4. Non-goals

本期明确不做：

- production A/B test 或在线流量实验；
- industry benchmark、正式统计验证或通用模型能力声明；
- generic Task Pack builder；
- model training、fine-tuning 或自有基础模型；
- production model API automation；
- multi-user SaaS、登录、权限中心或云数据库；
- RAG、Agent framework、复杂 plugin system 或通用 DSL；
- 用 Holdout 结果继续调 Prompt；
- 用 Human Review 覆盖 automatic calculated_status；
- 用 retry、JSON repair、follow-up 或手工修正替换 first actual response。

## 5. MVP scope

### 5.1 In scope

- 一个固定的 Simplified-Chinese Grounded Structured Brief Generation Task Pack；
- 24 个 fictional、self-contained Cases：18 Dev / 6 Holdout；
- strict JSON 输出 contract：
  - title：4–20 characters；
  - summary：60–120 characters；
  - key_points：恰好 3 条，每条 6–40 characters；
- Prompt v1、Dev failure analysis、Prompt v2 minimal revision；
- ChatGPT Web 手工 Generator；
- DeepSeek Web Condition 2 blind semantic Grader；
- deterministic rules、tri-state calculated_status、Human Review；
- owner-authorized append-only correction；
- SQLite provenance、Streamlit UI、SQL/Pandas read-only analysis；
- README、methodology、final report 和 run sheets。

### 5.2 Priority

所有上述链路属于 P0 MVP；项目没有将未来的多任务、多模型、多租户或线上运维能力伪装成已实现功能。

## 6. End-to-end user flow

Task Pack
→ Formal Case Set
→ Prompt v1 approval / freeze
→ Dev Run
→ deterministic rules + Blind Grader
→ failure analysis
→ Prompt v2 minimal revision
→ owner approval / freeze
→ Formal Holdout v1/v2
→ deterministic rules + Blind Grader
→ predeclared Human Review
→ corrective re-review / integrity audit
→ paired comparison
→ owner recommendation
→ methodology / final report / README

Holdout 只有在 Prompt v2 approval and freeze 后才进入有效正式流程。此前的错误 Holdout shells 保留为历史记录，但不进入正式比较。

## 7. 功能需求

以下 FR 使用 retrospective / as-built 口径描述已经实现的行为，不代表项目启动前已经存在这些文字。

### FR-01 Task Pack 与 Formal Case Set

- 优先级：P0
- 目标：保存固定任务 contract 和经过 owner QA 的 Case。
- 用户故事：作为 owner，我希望每个 Case 都有可追溯的 source material 和 required facts，从而不会在实验中临时改题。
- 前置条件：Task Pack contract 已冻结；Case 的 feasibility QA 为 pass。
- 输入：task pack、source_material、source_facts、required_fact_ids、split、content hash。
- 主流程：导入/校验字段 → 检查事实引用 → 计算 Case hash → 检查 18/6 split → 标记 formal-ready。
- 输出：可用于生成 packet、Grader packet 和分析的 Case 记录。
- 业务规则：source_material 是最终事实来源；source_facts 是可追溯索引；ambiguity 必须 indeterminate。
- fallback：pending 或 fail 的 Case 不得进入 formal-ready 集合。
- provenance：Task Pack hash、Case hash、split、QA status、时间戳。
- 验收：Given 24 个 approved Cases，When 运行 dataset QA，Then 得到 18 Dev、6 Holdout 且全部 feasibility pass。

### FR-02 Prompt version lifecycle

- 优先级：P0
- 目标：让 Prompt v1/v2 拥有独立版本、hash、approval 与 freeze 状态。
- 用户故事：作为 owner，我希望 v2 只能由已关闭的 Dev evidence 驱动，从而降低 Holdout leakage。
- 前置条件：v1 已批准并冻结；v2 有非空 change reason。
- 主流程：create draft → owner approve → freeze → 关联 evaluation run。
- 业务规则：Prompt v2 在 Dev failure analysis 前不能进入正式设计；Holdout 前必须冻结。
- fallback：未批准或未冻结版本不得创建有效 Holdout run。
- provenance：version_label、prompt_text、content_hash、owner_approved_at、frozen_at。
- 验收：Given closed Dev v1 evidence，When owner approves v2，Then v2 可冻结；Before freeze，Holdout creation must be rejected。

### FR-03 Evaluation Run lifecycle

- 优先级：P0
- 目标：记录一次 Prompt、split、Case hash、Generator、Grader 和 protocol 的组合。
- 输入：comparison_group_id、prompt version、split、case_set_hash、contract_hash、generator condition、protocol version。
- 主流程：创建 run → 记录 output slots → 关闭 run → 允许只读分析。
- 业务规则：有效配对必须使用相同 Case identity、contract、generator condition、protocol 和 Grader Condition。
- fallback：错误或不可比 run 关闭并保留，不参与正式 paired comparison。
- provenance：run id、comparison group、split、hash、model/environment notes、status、timestamps。
- 验收：Given Run 4 / Run 5，When 执行 comparability gate，Then 它们可作为同一 Holdout comparison group；Run 2 / Run 3 不计入。

### FR-04 Model Output collection

- 优先级：P0
- 目标：保存模型的第一次真实输出，不修复证据。
- 输入：model-facing packet、raw response、generated_at、technical retry reason。
- 主流程：每个 Case 打开 clean new conversation → 粘贴 packet → 捕获 first actual response → 原样写入 SQLite。
- 业务规则：质量失败不可 retry；只有 page/load/network/no-response 等 technical failure 可 retry。
- fallback：没有实际 response 时记录 technical failure，不把它转换成 quality fail。
- provenance：candidate_id、packet version/hash、raw response、output hash、generation time、retry count/reasons。
- 验收：Given malformed JSON，When submitted，Then raw response 原样保存并进入规则层，不进行 JSON repair。

### FR-05 Deterministic Rules 与 automatic aggregation

- 优先级：P0
- 目标：提供可重复的硬规则和 tri-state calculated_status。
- 输入：raw response、Task Pack contract、required facts、Grader semantic result。
- 主流程：strict parse → schema/field/count/length checks → 合并 semantic results → 计算 pass/fail/indeterminate。
- 业务规则：使用 len(text.strip())；不去除 markdown fence、不提取 JSON substring、不接受 comments/trailing comma。
- fallback：结构无效或关键 Grader 缺失时记录 indeterminate；technical failure 不进入质量分母。
- provenance：rule_key、rule version、actual/expected、reason、calculated_at。
- 验收：Given v1 Dev outputs，When aggregation 完成，Then Run 1 为 12 pass、6 fail、0 indeterminate。

### FR-06 Blind Grader workflow

- 优先级：P0
- 目标：在 version-blind、split-blind、status-blind 条件下做 pointwise semantic evaluation。
- 输入：allowlisted contract、source material、source facts、required facts、raw response、rubric、error taxonomy。
- 主流程：生成匿名 candidate packet → DeepSeek Web Condition 2 手工评测 → 导入严格 JSON → 校验 fact IDs → 保存 normalized results。
- 业务规则：Grader 不得看 Prompt version、Dev/Holdout、generator、calculated_status、Human Review 或另一候选输出。
- fallback：instruction collision 或错误 condition 结果必须中止/清理并保留审计记录。
- provenance：Grader condition snapshot、packet version/hash、candidate_id、raw payload、normalized fields、fact results。
- 验收：Given pilot packet instruction collision，When detected，Then pilot Grader rows 不得作为 formal Grader evidence。

### FR-07 Human Review

- 优先级：P0
- 目标：提供独立于 automatic status 的人工判断层。
- 输入：predeclared required/sample target、blind review packet、evidence、reason、final_decision。
- 主流程：由 target derivation 生成 required/sample queue → 匿名展示 → reviewer 提交 → 保存 review。
- 业务规则：queue 包含 indeterminate、unsupported claim 和稳定约 20% sample；提交前不展示 automatic outcome。
- fallback：非 target 或错误 review_scope 必须拒绝；review 不得重算 calculated_status。
- provenance：review_scope、blind flag、evidence、reason、reviewed_at、original final_decision。
- 验收：Given four formal sampled reviews，When review is stored，Then automatic calculated_status 保持不变。

### FR-08 Correction authorization 与 append-only correction

- 优先级：P0
- 目标：修正程序性无效 review，同时保留原始历史。
- 输入：original_human_review_id、evaluation_result_id、authorization_reason、corrective evidence/reason、corrected_final_decision。
- 主流程：owner authorize target → corrective re-review → append correction → 计算 effective decision。
- 业务规则：correction 必须匹配 original evaluation；correction target 与 correction 都不可 update/delete。
- fallback：没有授权 target、ID 不匹配或重复 correction 时拒绝写入。
- provenance：authorization timestamp、correction reason、review_mode、corrected decision。
- 验收：Given procedure-invalid original review，When authorized correction is submitted，Then original remains immutable and effective decision becomes corrected decision。

### FR-09 Analysis 与 paired comparison

- 优先级：P0
- 目标：生成可复核的描述性分析，而不是自动扩展结论。
- 输入：closed runs、evaluation results、rule/grader/human/correction records。
- 主流程：SQL query → Pandas formatting → status distribution、Bad Case、Human Review coverage、paired outcome。
- 业务规则：improved = fail→pass；regressed = pass→fail；indeterminate 单独计算；technical failure 不当作 quality fail。
- fallback：mixed Grader condition、不可比 pair 或缺少质量 response 时拒绝正式配对。
- provenance：query dimensions、run IDs、denominators、comparison group。
- 验收：Given HOLDOUT-COMP-02，When paired analysis runs，Then output 1 improved、5 unchanged、0 regressed、0 indeterminate。

### FR-10 Provenance、SQLite 与 Streamlit UI

- 优先级：P0
- 目标：让工程、实验与审计状态在一个本地工作台中可见。
- 输入：validated JSON、manual raw inputs、run lifecycle actions。
- 主流程：Streamlit pages 调用 Application services；services 调用 Domain 与 SQLite repositories。
- 业务规则：connections 开启 foreign keys；Analysis 只读；raw records 后续步骤不可改写。
- fallback：schema/migration/validation/lifecycle gate 失败时拒绝对应操作。
- provenance：structured IDs、hashes、timestamps、foreign keys、append-only records。
- 验收：Given formal local DB，When 做 read-only integrity check，Then foreign_key_check 无违规且 correction authorization trigger 存在。

## 8. AI / Model design

### 8.1 Model roles

| 角色 | 实际模型/工具 | 负责 | 不负责 |
|---|---|---|---|
| Generator | ChatGPT Web — GPT-5.6 Sol | Dev/Holdout 的正式模型输出 | 不负责 Grader、Human Review、最终建议 |
| Blind Grader | DeepSeek Web — Condition 2 | required facts、groundedness、language、readability、diagnostics | 不看 Prompt version、split、automatic status 或另一输出 |
| Engineering assistant | Codex | architecture、Python、SQLite、Streamlit、tests、audit、docs | 不替 owner 做正式审批、人工评测或结论 |
| Human authority | Owner | approval、freeze、Human Review、correction、recommendation | 不把人工判断伪装成 automatic status |

### 8.2 Input / output contract

Generator 的 model-facing packet 只包含 Task、Case instructions、source material 和 Prompt；不得带内部 ID、hash、split、comparison group 或评测结论。

Generator output 必须是：

{
  "title": "string",
  "summary": "string",
  "key_points": ["string", "string", "string"]
}

Grader output 是严格的 pointwise semantic JSON，包含 required fact results、groundedness、language、readability、unsupported claims、primary error type、reason 与 evidence。

### 8.3 Versioning

必须保留 Prompt hash、Case Set hash、Task Pack contract hash、Grader condition snapshots、packet hash、generator condition、protocol version 和时间戳。

### 8.4 Explicit exclusions

AI Output Eval Lab 的产品运行时 / evaluation system 本身不包含 RAG、function calling、Agent orchestration、model API runner 或在线工具调用，也不使用自动 retry。

项目开发过程确实使用过 Codex subagents、subagent-driven-development 等 Agent workflow 来进行工程实现、review 和 audit。这里的 Agent workflow = development methodology；Agent orchestration ≠ product runtime feature。

## 9. Evaluation design

- Formal Case Set：24 fictional/self-contained Cases。
- Split：18 Dev / 6 Holdout。
- Dev：允许 failure analysis 和 v2 design。
- Holdout：v2 approval/freeze 后首次使用，不用于同一实验的调参。
- Deterministic layer：JSON/schema、字段数量、字符长度及其他硬规则。
- Semantic layer：Blind Grader 的 required facts、closed-world groundedness、language、readability。
- Automatic layer：calculated_status 只由 Rules + Grader 产生。
- Human layer：final_decision / corrected decision / effective decision 单独保存。
- Paired layer：按 test_case_id 比较 v1/v2，报告 improved、unchanged、regressed、indeterminate。

正式结果：

| 阶段 | 结果 |
|---|---|
| Dev v1 | 12 pass / 6 fail / 0 indeterminate；6/6 fail = summary_length |
| Holdout v1 | 5/6 pass |
| Holdout v2 | 6/6 pass |
| Paired | 1 improved / 5 unchanged / 0 regressed / 0 indeterminate |
| 唯一改进 | brief-holdout-03：summary_length fail → pass，58 → 62 |
| v2 generation target | 70–100 仅命中 2/6；不是 hard pass/fail rule |

## 10. Data / provenance

核心实体：

1. task_packs
2. test_cases
3. prompt_versions
4. evaluation_runs
5. model_outputs
6. rule_results
7. grader_conditions
8. grader_results
9. grader_fact_results
10. evaluation_results
11. human_reviews
12. human_review_correction_targets
13. human_review_corrections

Correction tables 是后续演进，但不改变原始 model output、Rules、Grader 或 evaluation record。

Canonical content hashes（与 README、methodology 和 final report 交叉核对）：

| Artifact | SHA-256 |
|---|---|
| Task Pack contract | `ae273822b78d16cba4df5d784d611313f788353229d1b95166047cc1254a2c59` |
| Pre-finalization reviewed Case Set (superseded) | `a55dea2a4f2b24897edc720f548109e21da4733f58e88f57cc2f96c46ebaaf09` |
| Full Case Set | `c2555bafffd6d8ac0730a438fe0963530676d63beb7cea7b13a3116ae59f6bb5` |
| Dev subset | `a23f8d88ad1e35443d3b31bfcd0c60274b204cdbd0738d4ab21eefd24db3cb1c` |
| Holdout subset | `b22b44b58162a69e74de8af7ab93f9f8507caf3f665f70a68ad630ead004bd6f` |
| Prompt v1 | `07aa48853dbe0ed54ff88a2476ce6ec9be2cac4d2680dc2b41d0fc36c392ae4f` |
| Prompt v2 | `46198292143fa675fc9ad2cb0e724b6811aa3f2455b05f19a75f12e04aeaae74` |
| Grader Prompt v1 | `c14dfcfde0d5902e2b42bdee399bb12d4eb81c62f546bee65cec9f215eb810b1` |
| Rubric v1 | `719cbba979f3657f5c164d947a03b02b77b8818c487259b8c850f68dd577b8eb` |
| Error Taxonomy v1 | `ea8324fe5e865c1bb5bba755925b1fca452c90a49070d15dcfad32865a5d6338` |

Run-level `case_set_hash` 使用对应 split 的 subset hash，不等同于 full Case Set hash。

关键规则：

- source_material 是事实最终来源；
- required_fact_ids 必须引用合法 source facts；
- Prompt、Case、packet 和 run 使用 hashes；
- foreign keys 防止孤儿记录；
- correction targets/corrections append-only；
- formal DB 保持本地，不作为普通 Git source file；
- analysis 不修改数据。

## 11. Error handling / fallback

| 错误 | 处理 |
|---|---|
| malformed JSON / schema failure | 保留 raw response，记录 deterministic fail |
| semantic ambiguity | 记录 indeterminate，不猜测 |
| technical no-response | 记录 technical retry，不计为 quality fail |
| unknown Grader fact ID | Imports/Domain 拒绝 |
| Grader packet instruction collision | 中止 pilot，清理无效 Grader rows，保留 generator/rules provenance |
| wrong Holdout subset hash | 关闭为空的历史 run，不纳入 formal pair |
| Human Review procedure-invalid | 原 review 保留，进入 owner-authorized corrective re-review |
| correction 无授权或不匹配 | SQLite/application gate 拒绝 |
| Grader diagnostic overreach | 降低 diagnostic explanation confidence，不覆盖独立 automatic status |

## 12. Risks / limitations

- Formal Holdout 只有 n=6。
- Case Set 是 fictional、固定且单一任务族。
- 只有一个手工 generator environment 和一个正式 Grader Condition。
- 70–100 generation target 只有 2/6 命中。
- 有两个 possible Grader diagnostic overreach records。
- Human Review 曾发生 renderer display interpretation incident。
- 没有 production traffic、live A/B、统计显著性或 benchmark 结论。
- Prompt v2 的推荐不等于永久解决 summary-length failure。
- “Moderate confidence”是 owner 对本次 bounded experiment 的判断，不是模型自报置信度。
- 成本、SLA、线上延迟、用户规模和商业 ROI：Not applicable / Not verified；本项目没有采集这些指标。

## 13. Final experiment result

Owner recommendation：**Recommend Prompt v2**

Confidence：**Moderate**

推荐依据：

1. Dev v1 出现清晰且孤立的 summary-length failure mode；
2. v2 只针对该 evidence 做 minimal revision；
3. Holdout v1 重现同类 failure；
4. Holdout v2 修复该 failure；
5. 没有观察到新的结构或语义 regression；
6. required facts、groundedness、language、readability guardrails 保持稳定。

## 14. Success / acceptance

本项目的完成证据不是预先编造的 KPI，而是以下 as-built acceptance evidence：

| Acceptance area | Evidence |
|---|---|
| Task contract | strict JSON、60–120 summary、3 key points、Simplified Chinese |
| Formal data | 24 Cases、18 Dev / 6 Holdout、feasibility QA pass |
| Prompt lifecycle | v1/v2 hashes、approval/freeze、v2 由 Dev evidence 驱动 |
| Run integrity | valid Holdout pair 使用同一 comparison group、Case hash、generator/protocol/Grader condition |
| Raw evidence | 30 model outputs、first actual response 保留 |
| Evaluation | 210 rule results、30 Grader results、90 fact results、30 evaluations |
| Human authority | 8 Human Reviews、4 authorized correction targets、4 corrections |
| Database integrity | foreign_key_check 无违规；correction authorization 与 append-only constraints 存在 |
| Final decision | Prompt v2 / Moderate，且 claim boundary 被写入 methodology、final report、README |

当前项目 blocker：**None**。旧本地 main 不是正式交付分支；正式实现与文档以 implementation delivery branch 为准。

## 15. Future work

以下属于 Optional future work，不是当前项目 blocker：

- 扩大 fictional Case Set，加入更多任务族；
- 重复 generator / Grader condition，检验 length-safe intervention 的稳定性；
- 进一步做正式统计设计，但必须重新定义样本量与 NoGo criteria；
- 输出面向公开读者的完整 Prompt v2 / Grader asset snapshot；
- 增加真实 UI screenshots 和更完整的公开复现包；
- 若未来进入线上场景，再单独设计权限、成本、SLA、灰度、Kill Switch、回滚和运营监控。

本 PRD 到此为止，不把上述未来项写成当前已实现能力。

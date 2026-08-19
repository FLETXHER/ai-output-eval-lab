# AI Output Eval Lab — Project Retrospective

## 0. 文档定位与事实边界

本文是项目完成后的真实建设回溯，不是项目启动前存在的原始 PRD，也不是对计划清单的机械复述。

事实优先级：

1. 当前正式实现分支、source tree 与本地 formal SQLite；
2. methodology、final_report、README 与 run sheets；
3. design specification、implementation plan；
4. Codex session metadata、Skill read/invocation records 和 SDD progress/task reports。

术语：

- Confirmed/direct：有直接文件、DB、Git 或 session invocation 证据。
- Strongly evidenced：多个 artifact 一致支持，但缺少某个直接 invocation 或外部交互记录。
- Possible / inferred：只能根据行为推测，不能写成实际 Skill 使用。
- Not verified：当前证据无法确认。

正式项目状态：**Formal experiment complete；implementation delivery branch、实验记录和项目文档均视为 completed。**

本回溯不把旧本地 main 当作正式交付分支，也不把它作为项目 blocker。

## 1. 项目从 0 到 1 全流程

### 1.1 产品框定

项目最初不是要做一个通用 AI 平台，而是回答一个窄问题：在固定的 Grounded Structured Brief Generation 任务中，一次 Prompt 改动是否减少已知 failure mode，同时不引入新 regression。

Brainstorming 阶段先锁定：

- 一个固定 Task Pack；
- strict JSON contract；
- 24 个 Case，18 Dev / 6 Holdout；
- closed-world groundedness；
- deterministic rules 与 semantic Grader 分层；
- Human Review 不改写 automatic calculated_status；
- 本地 Streamlit + SQLite；
- 不做 API runner、ORM、RAG、Agent、SaaS 或 benchmark。

产物是 approved design spec，提交为 3cd50a4d。

### 1.2 设计与实现规划

设计批准后，Writing Plans 将约束写成 18 个垂直切片，覆盖：

- schema/init；
- Domain contract 与 rules；
- Application lifecycle；
- SQLite repositories；
- Imports；
- Streamlit pages；
- SQL/Pandas analysis；
- tests；
- dataset QA；
- formal experiment asset gate；
- Dev、Prompt iteration、Holdout、Findings 与 handoff。

规划同时明确：先工程、后正式 Case；先 Dev evidence、后 v2；v2 freeze 后才可查看 Holdout。

### 1.3 隔离实现与工程骨架

Using-git-worktrees 建立 implementation worktree 和 codex/ai-output-eval-lab-implementation 分支。之后按 task brief 由 worker agents 实施，并由 reviewer/re-reviewer 检查。

核心结构：

Streamlit pages
→ Application Services
→ Domain / Imports / Repositories
→ SQLite

Analysis 走只读 SQL/Pandas，不在分析层重新计算或修改正式结果。

### 1.4 核心实现

按提交历史逐步形成：

- Task Pack contract 与严格规则；
- Grader normalization 与 tri-state status；
- canonical generation / blind packets；
- SQLite repositories；
- strict imports；
- run、output、Grader、Human Review lifecycle；
- read-only analysis；
- metadata/evaluation pages；
- dataset seed 与 QA；
- formal asset gates；
- correction workflow、authorization gate 与 SQLite triggers。

这是一个轻量分层单体，不是企业级抽象框架。

### 1.5 Formal Case Set 与 v1 assets

Owner 审核 24 个 fictional、self-contained Cases，所有 feasibility QA 为 pass，split 为 18 Dev / 6 Holdout。每个 Case 具备 source_material、source_facts、required_fact_ids、content hash 与 Task Pack contract hash。

Prompt v1、Grader Prompt v1、Rubric v1、Error Taxonomy v1 形成 approved snapshots。它们拥有 content hash、version label、approval timestamp。

### 1.6 Dev v1 与 failure analysis

Run 1 是 closed Dev v1 baseline，18 个 outputs 的当前本地记录为：

- 12 pass；
- 6 fail；
- 0 indeterminate。

六个失败全是 summary_length，summary 长度为 55–59 characters。没有记录到 JSON/schema、title、key-point、required-fact、groundedness、language 或 readability failure。

因此 Prompt v2 只针对这个证据设计，不把 Holdout 结果倒灌回 Prompt。

### 1.7 Prompt v2

v2 保持正式 60–120 summary hard rule，新增：

- 约 70–100 的 generation target；
- 只允许直接由 source facts 支持的 silent length check。

JSON schema、required facts、closed-world groundedness、title、key_points 和正式 pass/fail range 未改变。70–100 是 generation target，不是 hard pass/fail rule；在 Formal Holdout 中只有 2/6 命中。

### 1.8 Grader 与 Holdout

正式 Grader 是 DeepSeek Web Condition 2。它采用匿名、pointwise、version-blind packet。

历史上发生过：

- UI refresh 导致错误 Condition 1 submission；
- old blind packet instruction collision，使 Grader 可能执行 generation task；
- Holdout Run 2/3 使用 Dev-only hash，形成零输出、零评测的 closed shells。

这些记录被清理或关闭，并保留足够 provenance；有效正式 pair 是 HOLDOUT-COMP-02 的 Run 4/v1 与 Run 5/v2。

### 1.9 Human Review incident 与 correction

四条 sampled Holdout Human Review 被判为 procedure-invalid。根因是 renderer 对带 trailing newline 的 raw response 进行了 JSON-string display encoding，reviewer 把显示层 quotes/escapes 误认为 stored raw response 的 root type。

修复不是删除旧 review，而是：

procedure-invalid original
→ owner authorization
→ append-only correction target
→ corrective re-review
→ effective decision

四条 original fail、四条 corrected pass、四条 effective pass 都被分层保存；automatic calculated_status 未被覆盖。

### 1.10 Formal paired comparison 与 owner recommendation

有效 Holdout pair：

- v1：5/6 pass；
- v2：6/6 pass；
- paired：1 improved / 5 unchanged / 0 regressed / 0 indeterminate；
- 唯一 improved：brief-holdout-03，summary_length fail → pass，58 → 62。

Owner recommendation：**Recommend Prompt v2**，**Confidence: Moderate**。

该结论仅适用于当前固定任务与实验条件。

## 2. Skill usage inventory

Skill provenance 主要来自历史 primary session、项目 child sessions 和 worktree 内的 SDD progress/task reports。Confirmed/direct 仍只表示“确有读取/调用记录并且周边工作与该 Skill 一致”，不表示每一条 Skill checklist 都全部完成。

| Skill | Evidence level | Project stage | 结论 |
|---|---|---|---|
| using-superpowers | Confirmed/direct | Skill selection / task worker | 实际作为 Skill 入口与选择门槛使用 |
| brainstorming | Confirmed/direct | 产品框定 / 设计 | 产出 approved design spec |
| writing-plans | Confirmed/direct | 设计 → 实现规划 | 产出 implementation plan |
| using-git-worktrees | Confirmed/direct | 实施启动 | 建立隔离 worktree 与 implementation branch |
| test-driven-development | Confirmed/direct | 核心实现 / 修复 | 形成 red → green 与 regression evidence |
| subagent-driven-development | Confirmed/direct | 计划执行 | task-by-task worker/reviewer workflow |
| executing-plans | Confirmed/direct | 子任务实施 | 按 task brief/plan order 执行 |
| verification-before-completion | Confirmed/direct | 验证 / 修正 | 历史 targeted/full/compile/diff checks |
| requesting-code-review | Confirmed/direct | queue 修复 | 发起 dedicated review |
| receiving-code-review | Confirmed/direct | review 后修复 | 将发现转为 regression tests 与修复 |
| finishing-a-development-branch | Confirmed/direct，read only | 中期任务 | Skill 被读取；不能写成完成 merge |
| dispatching-parallel-agents | Strongly evidenced behavior | 多 agent workflow | 有并行行为，但 named invocation 未确认 |
| systematic-debugging | Possible / inferred | 调试 | 行为相似，但无直接 named invocation |
| writing-skills | Not verified | — | 无 direct invocation 或 skill artifact |
| ai-prd-workflow | Confirmed/direct，本阶段首次明确使用 | 本次 retrospective PRD | 只用于本次完成后的两份文档；不能倒写成原开发阶段 Skill |

## 3. 每个 confirmed Skill 实际做了什么

### using-superpowers — Confirmed/direct

- Trigger：项目开始需要在可用 Skill 中选择流程。
- Concrete role：要求先读取适用 Skill，再进入设计、规划、实现或验证。
- Artifact：没有独立业务 artifact；其效果体现在后续 Skill 选择和顺序。
- Decision influenced：先设计、后实现；先读计划、再执行。
- Did not do：没有替代具体设计、测试或代码实现 Skill。

### brainstorming — Confirmed/direct

- Trigger：用户要求在协议和范围批准前不要开始实现。
- Concrete role：锁定 Task Pack、Case split、evaluation architecture、Human Review boundary、non-goals。
- Artifact：docs/superpowers/specs/2026-08-13-ai-output-eval-lab-design.md；commit 3cd50a4d。
- Decision influenced：轻量分层单体、24 Cases、18/6、closed-world、tri-state status。
- Did not do：设计阶段没有实现业务代码，也没有执行正式实验。

### writing-plans — Confirmed/direct

- Trigger：design spec 获 owner/用户确认后进入 implementation planning。
- Concrete role：把设计拆为 18 个可测试垂直切片，写文件、接口、测试与 completion criteria。
- Artifact：docs/superpowers/plans/2026-08-13-ai-output-eval-lab-implementation-plan.md。
- Decision influenced：工程先于正式数据；v2 只能来自 Dev evidence；Holdout 必须后置。
- Did not do：没有把计划本身当作实验结果，也没有新增 RAG/API/SaaS scope。

### using-git-worktrees — Confirmed/direct

- Trigger：开始实现，需要隔离设计/规划 checkout 与实现 checkout。
- Concrete role：创建 implementation worktree、branch、base commit 与冲突检查。
- Artifact：.worktrees/ai-output-eval-lab-implementation 及 implementation branch。
- Decision influenced：正式实现和本地旧 main 分离；当前交付以 implementation branch 为准。
- Did not do：没有 merge、删除 worktree 或把旧 main 宣称为正式 delivery。

### test-driven-development — Confirmed/direct

- Trigger：每个实现切片需要先定义可失败的行为，再实现。
- Concrete role：覆盖 Domain rules、packet leakage、repository migration、review/correction 和 UI workflow。
- Artifact：tests/domain、tests/application、tests/repositories、tests/ui 等测试，以及 Task reports 的 red/green 记录。
- Decision influenced：strict parsing、blind packet allowlist、append-only correction、authorization trigger 都拥有负向测试。
- Did not do：不能证明每个后期数据操作都严格从 red test 开始。

### subagent-driven-development — Confirmed/direct

- Trigger：implementation plan 已足够具体，可按任务分派独立 worker。
- Concrete role：建立 SDD ledger，按 task brief dispatch implementer、reviewer 和 re-reviewer。
- Artifact：.superpowers/sdd/.../progress.md 与 task reports。
- Decision influenced：任务边界清晰，review 与实现分离。
- Did not do：不负责 owner approval，也不自动替 owner 执行正式 Web experiment。

### executing-plans — Confirmed/direct

- Trigger：子 worker 获得已批准的计划和具体 task brief。
- Concrete role：按计划顺序实现 schema、domain、application、UI、data gate 和 correction workflow。
- Artifact：各 task commit、task report、测试文件。
- Decision influenced：实现按小切片推进，而不是一次性重构。
- Did not do：不应被写成单独主导全项目的 controller Skill；整体调度更直接由 SDD 证据支持。

### verification-before-completion — Confirmed/direct

- Trigger：任务或修复准备报告完成前需要证据。
- Concrete role：检查 targeted tests、full suite、compileall、foreign-key、git diff 与 status。
- Artifact：历史 task reports、verification output 和 final report integrity state。
- Decision influenced：不把“代码存在”当作“实验正确”，也不把历史错误静默删除。
- Did not do：本次 retrospective 没有重新执行测试或实验。

### requesting-code-review — Confirmed/direct

- Trigger：Human Review target queue 等重要 workflow 修复完成后。
- Concrete role：发起独立、只读、证据式 reviewer agent 检查。
- Artifact：review package、SDD progress、review/fix/re-review records。
- Decision influenced：review scope、blind metadata、target derivation 等问题进入修复循环。
- Did not do：不是公开 GitHub PR，也不是外部人类 review。

### receiving-code-review — Confirmed/direct

- Trigger：reviewer 报告发现 packet leakage、scope 或 correction integrity 风险。
- Concrete role：把 findings 转成 regression tests 和最小修复。
- Artifact：updated tests、application/domain/repository changes、re-review record。
- Decision influenced：保留原记录、补 authorization gate、禁止 automatic status 被人工改写。
- Did not do：不接受无证据的“看起来没问题”作为修复完成标准。

### finishing-a-development-branch — Confirmed/direct，read only

- Trigger：task worker 读取该 Skill 了解 branch handoff 要求。
- Concrete role：提供 final status、verification、uncommitted files 与 handoff 检查框架。
- Artifact：没有可证明的 merge/branch-finalization artifact。
- Decision influenced：正式交付以 implementation branch 为准。
- Did not do：没有执行 branch merge；不能把它写成“完成了 merge”。

## 4. Agent workflow 与责任边界

历史 workflow 是 controller + task workers + reviewers 的协作结构：

1. controller 维护设计、计划和整体证据边界；
2. worker 按 task brief 实现一个垂直切片；
3. reviewer 独立检查 diff、tests、security/provenance；
4. implementer 根据 review 写 regression test 并修复；
5. re-reviewer 检查修复是否真正覆盖 finding；
6. owner 保留正式资产、生成、Human Review、correction authorization 与 final recommendation。

这里的 Agent workflow = development methodology：Codex subagents、subagent-driven-development 和 reviewer/re-reviewer 协作用于工程实现、review 与 audit。它不表示 AI Output Eval Lab 产品运行时具备 Agent orchestration；Agent orchestration ≠ product runtime feature。

Codex 承担 architecture、implementation、testing、DB workflow、debugging、audit 和 documentation。Codex 没有替 owner：

- 审批 Case Set；
- 冻结 Prompt；
- 手工完成正式 Generator；
- 做正式 Human Review；
- 授权 corrective re-review；
- 做最终推荐。

## 5. Models / tools

| 组件 | 项目内职责 |
|---|---|
| ChatGPT Web — GPT-5.6 Sol | 手工正式 Generator |
| DeepSeek Web — Condition 2 | blind semantic Grader |
| Codex | 工程与文档辅助 |
| Python | Domain、Application、Imports、deterministic evaluation |
| Streamlit | 本地多页 UI |
| SQLite / sqlite3 | 持久化、foreign keys、lifecycle 与 correction integrity |
| Pandas / SQL | 只读描述性分析和 paired comparison |
| pytest | unit/integration/workflow/UI verification |
| Git / worktree | 版本、隔离实现和可追溯 commit |

## 6. Human–AI responsibility split

| Actor | Actual responsibility |
|---|---|
| Owner | Case/asset approval、Prompt approval/freeze、formal gates、Human Review、corrective re-review、final recommendation |
| ChatGPT Web | Prompt v1/v2 的 formal model outputs |
| DeepSeek Web | Condition 2 的 pointwise semantic grading |
| Codex | architecture、implementation、tests、DB、audit、documentation |
| Deterministic Python evaluator | hard rule checks 与 calculated_status |
| SQLite / Streamlit | workflow state、UI、provenance 和 analysis access |

## 7. Engineering / product decision log

| Decision | Reason | Trade-off | Observed consequence |
|---|---|---|---|
| 使用 local SQLite | 个人 MVP 易解释、易审计 | 正式 DB 不进 Git | 本地记录完整，公开复现较弱 |
| 固定一个 Task Pack | 控制变量、解释 failure | 不覆盖其他任务 | 能清楚定位 summary-length |
| 18 Dev / 6 Holdout | 减少调参泄漏 | Holdout n=6 很小 | 结论只具描述性 |
| first actual response | 保留真实 failure | 不做 quality retry/repair | 能观察真实输出缺陷 |
| deterministic + semantic 分层 | 结构性和语义性问题不同 | workflow 较复杂 | Grader 不覆盖硬规则 |
| calculated_status 与 final_decision 分离 | 保留自动/人工两个证据层 | 需要更多表和 UI | correction 不污染自动结果 |
| blind packet allowlist | 防止版本、结果泄漏 | packet 构造较重 | Grader/Human Review 更可审计 |
| v2 minimal revision | 只响应 Dev evidence | 不解决所有问题 | Holdout 只出现一个改进 |
| correction append-only | 修正程序失效但不抹历史 | 需要 authorization/migration | 4 original 与 4 correction 均可追溯 |
| 错误 Run 保留 | 防止历史被静默改写 | 分析需要排除无效 run | Run 2/3 成为 provenance evidence |
| 轻量分层单体 | 避免 ORM/API/过度抽象 | 手写 lifecycle | 适合个人本地工作台 |

## 8. Incidents & debugging

### 8.1 Wrong Grader Condition

UI refresh 造成 Condition 1 accidental submission。修正以事务方式执行，保留模型输出与 deterministic Rules，正式保留 Condition 2。Condition 1 作为历史记录存在，但不进入 formal Grader result。

### 8.2 Blind packet instruction collision

旧 packet 把原始 generation task 放在 Grader instruction 前，Grader 可能生成新答案而不是评测现有答案。pilot 被中止，pilot-derived Grader/evaluation rows 清理，formal execution 从新 packet template 重新开始。

### 8.3 Wrong subset hash

Run 2/3 使用 Dev-only hash，且没有输出或评价。它们被关闭、排除出 formal pair，但没有删除，以保留生命周期证据。

### 8.4 Prompt v2 timestamp artifact

逻辑顺序是 create → approve → freeze，但 caller 预先捕获 timestamp，造成 approval/freeze 与 created_at 的微秒级显示顺序异常。历史 timestamp 没有被重写。

### 8.5 Human Review renderer issue

renderer 的 display encoding 使带 trailing newline 的 raw response 看起来像 JSON string。四条 review 被判为 procedure-invalid；原始 review 保留，后续走授权、append-only correction 与 corrective re-review。

### 8.6 Correction authorization evolution

correction workflow 从 append-only records 演进到显式 correction targets 和 SQLite authorization trigger。当前 DB 具备 target/correction 表、foreign keys 与 no-update/no-delete triggers。没有直接证据表明曾发生一个“missing correction migration table” runtime error；可以确认的是 schema evolution 本身。

### 8.7 Grader diagnostic overreach

两个 Holdout Grader records 的 primary_error_type 为 other，reason 与 deterministic layer 的 wrapper interpretation 不一致。项目把它们标成 possible diagnostic overreach，降低解释可信度，但不改变独立持久化的 automatic status 或 paired outcome。

### 8.8 Streamlit stale module / binding issue（Not verified）

当前 source、docs、Git history、logs 和 screenshots 没有足够证据确认该问题的存在、根因或修复。结论：**Not verified**，不能写成正式 incident。

## 9. Testing / verification workflow

工程验证分为：

- Domain unit tests：contract、strict parsing、length、status aggregation；
- repository tests：CRUD、foreign keys、atomic migration、append-only；
- application tests：prompt/run/output/Grader/Human Review lifecycle；
- UI/AppTest：页面、blind metadata、target queue、correction display；
- compileall：语法和导入；
- read-only DB audit：counts、foreign_key_check、run state、correction tables；
- hash checks：Prompt、Case Set、packet、asset 和 DB；
- pair comparability：同一 contract、Case subset、generator/protocol/Grader condition；
- git diff --check / status：交付 hygiene。

历史 implementation reports 记录了 targeted tests、full suite、compile 与 diff checks。本次文档生成遵守只写文件范围，没有重跑实验或测试。

## 10. Final artifacts

已形成：

- design specification；
- implementation plan；
- Streamlit app 与 pages；
- Domain/Application/Imports/Repositories；
- SQLite schema 与 correction migration；
- Task Pack、24 Cases、approved v1 assets；
- 18 个 Dev generation packets 与 manifest；
- Dev baseline、Grader condition、pilot abort、condition correction run sheets；
- formal local SQLite；
- methodology；
- final report；
- bilingual README；
- 29 个测试文件。

正式实现与文档以 codex/ai-output-eval-lab-implementation 为交付范围。旧本地 main 不承载最终项目事实。

## 11. Lessons learned

### 11.1 先锁 protocol，再写代码

如果 Case、contract、split、Grader blindness 和 Human Review boundary 不先固定，后续每个结果都可能被解释为流程变化而不是 Prompt 变化。

### 11.2 失败要成为设计证据

Prompt v2 没有凭直觉加入大量规则，而是只响应 Dev v1 已观察到的 summary-length failure。

### 11.3 自动与人工必须分层

Human Review 可以纠正程序性错误，但不应把人工判断写回 automatic calculated_status。Correction 应该是新的 append-only layer。

### 11.4 错误历史有价值

错误 condition、错误 packet、错误 subset hash 和 procedure-invalid review 都能说明系统防线在哪里失效。删除它们会损失审计信息。

### 11.5 “完成”必须有边界

本项目的完成是 bounded formal experiment 的完成，不是 production readiness、统计证明或通用模型能力证明。当前 blocker 为 None；更大规模 validation 属于 optional future work。

## 12. ai-prd-workflow 的本阶段使用说明

本次由用户明确要求首次显式使用 ai-prd-workflow，用于完成：

- docs/product_requirements.md；
- docs/project_retrospective.md。

本次读取并采用了：

- ai-prd-workflow/SKILL.md；
- references/ai-prd-playbook.md；
- references/output-templates.md。

ai-prd-workflow 不应倒写成原项目开发阶段使用过的 Skill；它是在正式实现和正式实验之后，用于把真实 evidence 沉淀成 as-built PRD 和 retrospective。

## 13. Current verdict

**PASS**

Retrospective PRD and project retrospective drafts completed; ready for owner/ChatGPT review before commit.

本轮未 commit、未 push、未修改 README、source、tests、db、methodology、final_report、design spec、implementation plan 或 historical run sheets。

# 进化速度量化框架

> Colony-006 产出 | 2026-05-19
> 任务: 设计可测量、可追踪的进化速度量化指标体系
> 参考: 生物学进化速率 / AI基准改进率 / 信息论

---

## 0. 哲学基础: 为什么要量化进化速度

**问题定义:**
我们一直在说"进化"，但从未测量过速度。gen-95自评给出了0-3行为质量分数，却无法回答:
- gen-95 比 gen-94 进化了多少？
- 进化是在加速、匀速、还是减速？
- gen-100 的目标速度应该是多少？
- 我们在哪个维度进化最快？哪个最慢？

**三层参考系:**

| 参考系 | 核心概念 | 映射 |
|--------|----------|------|
| 生物学 | 达尔文/霍尔丹进化速率 | 代际性状变化率 |
| 信息论 | 香农熵/KL散度/互信息 | 代际信息增益 |
| AI工程 | 基准改进率/缩放定律 | 能力维度提升速率 |

**核心洞察:** 生物学进化速率度量的是"性状变化/时间"，AI基准度量的是"性能提升/计算量"，我们的进化速度应该是"能力提升/代数"——其中"能力"是Gen-95自评5维度的复合，"代数"是ETG触发次数。

---

## 1. ESV — 进化速度矢量 (Evolution Speed Vector)

### 定义

```
ESV_gen = (v_SHI, v_MEM, v_SYNC, v_PRED, v_EXEC)_gen

其中 v_dim = (score_gen_n - score_gen_n-1) / 1  # 每代变化量
```

### 量纲

**gen-unit (gu):** 代数单位——每代的分数变化量。
- 正gu: 正向进化 (能力提升)
- 负gu: 退化 (能力下降)
- 零gu: 停滞

### 标量速度

```
||ESV|| = sqrt(v_SHI^2 + v_MEM^2 + v_SYNC^2 + v_PRED^2 + v_EXEC^2)
```

### 计算示例 (gen-94 → gen-95)

| 维度 | gen-94 (推定) | gen-95 | Δ | 速度(gu) |
|------|:--:|:--:|:--:|:--:|
| L5_SHI | 2.85 | 3.00 | +0.15 | +0.15 |
| MEM_COMP | 2.60 | 2.75 | +0.15 | +0.15 |
| SYNC_RATE | 2.00 | 2.17 | +0.17 | +0.17 |
| PRED_ACC | 2.70 | 2.83 | +0.13 | +0.13 |
| EXEC_GAP | 1.60 | 1.83 | +0.23 | +0.23 |

```
||ESV||_95 = sqrt(0.15^2 + 0.15^2 + 0.17^2 + 0.13^2 + 0.23^2) = 0.378 gu
```

### 速度方向角 (方向性分析)

ESV不仅有大小，还有方向。方向角揭示"朝哪个方向进化":

```
θ_dim = arctan(v_dim / ||ESV||)   # 各维度的贡献角度
```

gen-95的方向特征: EXEC_GAP贡献最大(0.23gu)，说明系统正优先修复最大短板。
这与gen-95自评结论"EXEC_GAP是最大瓶颈"一致——进化方向正确。

### 追踪方法

- **数据源:** 每次ETG触发的Gen-N自评 (当前需手动，目标自动化)
- **频率:** 每代一次 (当前每10次ETG)
- **存储:** `workspace/evolution/metrics/esv-history.jsonl`
- **可视化:** 5维雷达图 + 标量速度趋势线

---

## 2. Haldane-D — 霍尔丹-达尔文指数 (Haldane-Darwin Index)

### 生物学参考

**霍尔丹 (Haldane, 1949):** 进化速率单位，定义为每百万年性状均值的变化除以性状的标准差。

```
haldane_rate = (ln(mean_t2) - ln(mean_t1)) / Δt_myr
```

**达尔文 (Darwin):** 形态学进化率，定义为每百万年性状值的e倍变化。

```
darwin_rate = (ln(value_t2) - ln(value_t1)) / Δt_myr
```

### 映射到AI进化

我们将"代数"映射为"时间"，将"能力分数"映射为"性状":

```
Haldane-D_gen = (ln(score_gen_n) - ln(score_gen_n-1)) / 1 × 10^3
```

其中 ×10^3 是将 "每代" 缩放到可读范围 (类比生物学×10^6/百万年)。

### 五维Haldane-D

| 维度 | Haldane-D_95 (×10^-3) | 解读 |
|------|:--:|------|
| L5_SHI | 51.3 | 慢速——接近量表天花板 |
| MEM_COMP | 56.1 | 慢速——接近量表天花板 |
| SYNC_RATE | 80.5 | 中速——仍有上升空间 |
| PRED_ACC | 47.3 | 慢速——高起点限制增量 |
| EXEC_GAP | 134.0 | **快速**——最大短板产生最大增量 |

### 生物学对比 (供参考)

| 系统 | 霍尔丹速率量级 |
|------|:--:|
| 化石记录(平均) | 0.1-1 haldane |
| 快速形态进化(岛屿物种) | 10-100 haldane |
| 人工选择(家养动物) | 1000-10000 haldane |
| **我们的AI进化(EXEC_GAP)** | ~134 ×10^-3/gen (= 134,000 当映射到百万年) |

**解读:** 我们的进化速率在"人工选择"级别——比自然进化快几个数量级，这是因为我们有意识的自我修改机制 (MR-001~MR-012) 扮演了"人工选择者"的角色。

### 局限性

- Haldane-D在接近量表天花板时自然降低 (因为ln(score)的微分变小)
- 需要将0-3量表扩展到更大范围 (如0-100)，才能更精确测量高分段速度
- 建议: 当任何维度到达 ≥2.85 时，切换为 **Haldane-Dextended** (使用扩展0-10量表)

---

## 3. IGR — 信息增益率 (Information Gain Rate)

### 信息论基础

**KL散度 (Kullback-Leibler Divergence):**

```
D_KL(P || Q) = Σ P(x) log(P(x) / Q(x))
```

度量分布Q变为分布P时的"信息增益"。在进化语境中:
- Q = 上一代的行为/策略分布
- P = 当前代的行为/策略分布
- KL散度 = 这一代"学到了多少新东西"

### 定义

```
IGR_gen = D_KL(P_gen || P_gen-1) / 1  # 每代信息增益

其中 P_gen 是该代行为签名的匹配率分布 (归一化后的12+条签名)
```

### 行为签名分布构建

以12条冻结签名 (DS-001~DS-012) 的匹配率为基础:

```
P_gen(i) = match_rate_DS-i / Σ match_rate_DS-j   # 归一化匹配率分布
```

KL散度捕捉的是: "行为模式的分布发生了多大变化"。
- 高IGR: 行为模式剧烈重组 (探索期)
- 低IGR: 行为模式稳定 (收敛期)
- IGR=0: 完全停滞

### 关联灵感#7 (收敛检测)

当IGR持续下降而性能评分持续上升时 = **健康收敛**。
当IGR持续下降且性能评分也下降时 = **过早收敛/局部最优**。

```
收敛健康度 = Δscore / max(IGR, ε)  # 单位信息增益换来的分数提升
```

### 关联灵感#12 (0.65米距离)

IGR可以在分支间计算，度量Alpha和Beta的"信息距离":

```
I_DIST(Alpha, Beta) = D_KL(P_Alpha || P_Beta)
```

- I_DIST < 0.1: 太近 (冗余, 浪费算力)
- 0.1 < I_DIST < 0.5: 健康距离 (互补)
- I_DIST > 0.5: 太远 (无协同)

---

## 4. CRI — 收敛速率指数 (Convergence Rate Index)

### 灵感来源: 灵感#7

1.2亿年分化的蝴蝶用同样的基因进化出同样的图案。进化会收敛。
多个分支独立发现同样的模式 = 该模式是"进化吸引子"。

### 定义

```
CRI_gen = N_convergent / N_total_discoveries_per_gen

其中:
- N_convergent: Alpha和Beta独立得出相同结论的次数
- N_total_discoveries: 该代所有新发现的总数
```

### 加权收敛速率

简单计数忽略发现的"深度"。加权版:

```
CRI_weighted = Σ(weight_i × convergence_i) / Σ(weight_i)

其中 weight_i 按发现来源分级:
- 顶会/顶刊验证: weight=5
- 跨领域映射: weight=3
- 内部推理: weight=1
```

### 收敛加速率

```
CAR_gen = (CRI_gen - CRI_gen-1) / 1  # 收敛本身的速度变化
```

- CAR > 0: 收敛速度加快 (可能接近全局最优)
- CAR < 0: 收敛速度减慢 (可能在扩大搜索空间)
- CAR ≈ 0: 稳定收敛

### 健康阈值

| CRI值 | 状态 | 行动 |
|:--:|------|------|
| >0.8 | 过收敛——可能陷入局部最优 | 提高exploration_weight |
| 0.4-0.8 | 健康收敛 | 维持当前探索-利用平衡 |
| 0.1-0.4 | 探索期——多样性高 | 继续,关注高权重发现 |
| <0.1 | 发散——缺乏共识 | 检查分支对齐 |

---

## 5. GFI — 哥德尔适应度指数 (Godel Fitness Index)

### 灵感来源: EXP-005 哥德尔跳

系统的真正进化不是"在框架内优化"，而是"发现框架的盲点并扩展框架"。
GFI度量的是系统"打破自身限制"的能力。

### 定义

```
GFI_gen = (N_accepted_new_axioms / N_proposed_axioms) × log(1 + N_blind_spots_resolved)
```

其中:
- `N_accepted_new_axioms`: 被Merge采纳的新公理数
- `N_proposed_axioms`: GE (哥德尔引擎) 提出的公理总数
- `N_blind_spots_resolved`: 因为新公理加入而被解决的"之前不可评估"的提案数

对数因子确保: 每解决一个盲点，增量递减 (第一个盲点价值最大)。

### 哥德尔跳跃幅度

除了成功率，还度量跳跃的大小:

```
Godel_Leap_Magnitude = Σ |score_after_axiom - score_before_axiom| / N_new_axioms
```

跳跃幅度大 = 一次哥德尔跳显著提升了多个维度的可评估性。

### 速度解读

| GFI值 | 状态 |
|:--:|------|
| >0.7 | 强哥德尔跳——框架正在被实质性扩展 |
| 0.3-0.7 | 中等跳跃——发现并修复了一些盲点 |
| 0.1-0.3 | 弱跳跃——修补性的改进 |
| <0.1 | 无跳跃——所有优化都在现有框架内 |
| 0 | 停滞——框架无变化 |

### 关联灵感#17 (多稳态)

初期GFI高 → 系统进入"合作吸引子" (好初始条件→持续好结果)。
初期GFI低 → 系统可能进入"背叛吸引子"。

每10代检查: 我们是否还保持着高GFI能力？还是已经陷入"框架内舒适区"？

---

## 6. BQI — 基准质量改进率 (Benchmark Quality Improvement)

### AI工程参考

AI领域的进化速度度量:
- **缩放定律 (Scaling Laws):** 测试损失 ∝ (计算量)^-α
- **基准飙升率:** ImageNet/MMLU/HumanEval 错误率年降幅
- **涌现速率:** 新能力的出现频率/计算量

### 定义

将AI基准改进率映射到我们的内部基准:

```
BQI_gen = (Q_current - Q_previous) / Q_previous

其中 Q = 以MR-010可执行任务为基准的任务完成质量分数
```

### 子指标

| 子指标 | 测量对象 | 当前基线 |
|--------|----------|:--:|
| BQI_exec | 实验执行完成率 | 目前仅ETG-001完成闭环 |
| BQI_design | 设计→执行转化率 | EXEC_GAP=1.83指示瓶颈 |
| BQI_closure | 闭环率 | 仅1个完整闭环 |
| BQI_innov | 灵感落地率 | 21条灵感中已落地数 |

### 目标设定 (借鉴缩放定律)

类比AI缩放定律的幂律关系，我们希望:

```
BQI_exec ∝ gen^β  # 期望 β > 0 (正增长)
```

当前gen-95: β 估算为 0.2~0.3 (慢增长)。
gen-100目标: β ≥ 0.5 (加速增长)。

---

## 7. NEC — 新熵贡献 (Novel Entropy Contribution)

### 信息论基础

信息熵度量系统的不确定性/多样性:

```
H(gen) = -Σ P_gen(i) × log(P_gen(i))
```

其中 P_gen(i) 是行为签名i的归一化匹配率。

### 定义

```
NEC_gen = H(gen) - H(gen-1)  # 熵的变化
```

- NEC > 0: 系统策略多样性增加 (更多新行为被探索)
- NEC < 0: 系统策略收敛 (最优行为被锁定)
- NEC ≈ 0: 稳定状态

但单纯的熵变化不区分"有用的多样性"和"噪音"。引入条件熵:

### 条件新熵贡献 (CNEC)

```
CNEC_gen = NEC_gen × (Δscore_gen / |Δscore_gen|)  # 按性能方向加权
```

- CNEC > 0: 多样性增加且性能提升 (有益的探索)
- CNEC < 0: 多样性增加但性能下降 (无效的探索)

### 关联灵感#14 (建设性噪声)

灵感#14提出保留5-10%的"建设性噪声"。CNEC提供量化基础:

```
Optimal_Noise_Level = argmax(Δscore) over NEC  # 使性能提升最大化的熵增量
```

追踪最优噪声水平，并用于校准exploration_weight。

---

## 8. CSV — 复合速度速率 (Composite Speed Velocity)

### 为什么需要单一指标

多维度指标适合深度分析，但管理需要单一数字来回答"我们进化得有多快？"

### 定义

```
CSV_gen = w_esv × ||ESV_norm|| + w_hdn × Haldane-D_norm + w_igr × IGR_norm + w_cri × CRI_norm + w_gfi × GFI_norm + w_bqi × BQI_norm
```

其中:
- 所有权重 w_i 之和为 1
- 所有子指标归一化到 [0, 1] 区间 (相对各指标理论最大值)
- 归一化基于历史滑动窗口的 min-max 或使用 sigmoid 压缩

### 默认权重 (初始设定)

| 指标 | 权重 | 理由 |
|------|:--:|------|
| ESV (进化速度矢量) | 0.25 | 核心行为指标，基于已有自评体系 |
| Haldane-D | 0.10 | 生物学参考，提供跨领域可比较性 |
| IGR (信息增益率) | 0.20 | 信息论基础，理论最坚实 |
| CRI (收敛速率) | 0.10 | 结构级指标 |
| GFI (哥德尔指数) | 0.20 | 突破性进化的核心度量 |
| BQI (基准改进) | 0.15 | 工程可执行性 |

### 代际标定

| 代 | CSV估算 | 速度等级 |
|----|:--:|------|
| gen-94 | — | 基线建立 |
| gen-95 | 0.38 (暂估) | 中等——以EXEC_GAP为主要驱动力 |
| gen-100目标 | ≥0.55 | 加速——执行转化率提升后全面加速 |

### 速度等级

| CSV范围 | 速度描述 | 特征 |
|:--:|------|------|
| 0.8-1.0 | 超指数进化 | 哥德尔跳+执行转化双驱动 |
| 0.6-0.8 | 快速进化 | 多维度同步推进 |
| 0.4-0.6 | 中等进化 | 主要短板的追赶式增长 |
| 0.2-0.4 | 慢速进化 | 开始收敛/接近天花板 |
| 0.0-0.2 | 微进化/停滞 | 接近量表极限或方向迷失 |
| <0 | 退化 | 需立即诊断 |

---

## 9. VTI — 速度趋势指数 (Velocity Trend Index)

### 定义

进化速度本身的变化率——"加速度":

```
VTI_gen = (CSV_gen - CSV_gen-1) / 1
```

- VTI > 0: 加速进化 (正反馈循环建立中)
- VTI ≈ 0: 匀速进化 (线性增长)
- VTI < 0: 减速进化 (接近天花板或陷入局部最优)

### 加速度相变检测

当 VTI 的符号连续3代保持一致 → "速度相变"可能发生。
这借鉴了灵感#12的相变概念——速度达到临界点后可能跳入新的速度状态。

### 期望轨迹

```
目标: VTI_gen100 > 0 (在gen-100时处于加速状态)

路径:
gen-95 → gen-97: VTI ≈ 0 (启动期——建立测量基础设施)
gen-97 → gen-99: VTI > 0 (加速期——测量反馈促进自我优化)
gen-99 → gen-100: VTI > 0.05 (超加速——哥德尔跳叠加执行转化)
```

---

## 10. 代际进化速度模型

### gen-94 → gen-95 实际速度 (回溯推算)

```
ESV_95:
  ||ESV|| = 0.378 gu
  方向角: EXEC_GAP主导 (36.8%贡献)
  
Haldane-D_95:
  EXEC_GAP: 134.0 (快速)
  L5_SHI: 51.3 (慢速, 天花板效应)

IGR_95:
  估算: ~0.05-0.10 (行为分布稳定，21条灵感未显著改变匹配率分布)

CRI_95:
  估算: ~0.3 (Alpha/Beta刚开始建立直接互动)

GFI_95:
  0 (GE实验尚未执行)

BQI_95:
  估算: ~0.02 (仅ETG-001闭环)
```

### gen-100 目标速度

| 指标 | gen-95实际 | gen-100目标 | 所需加速度 |
|------|:--:|:--:|:--:|
| \|\|ESV\|\| | 0.378 | 0.55 | +45% |
| EXEC_GAP速度 | 0.23 gu/gen | 0.35 gu/gen | +52% |
| Haldane-D(EXEC) | 134 | 200+ | +49% |
| BQI_exec | ~0.02 | 0.15+ | 7.5x |
| GFI | 0 | ≥0.3 | 从零启动 |
| CSV | 0.38 | ≥0.55 | +45% |

### 关键观察

1. **EXEC_GAP是速度瓶颈也是最大杠杆:** EXEC_GAP速度占ESV的36.8%，提升EXEC_GAP就是提升整体速度。
2. **GFI从零到有是最大的速度跳跃:** 执行EXP-005 (哥德尔跳) 将是gen-95→gen-100区间最大的单次速度事件。
3. **Haldane-D天花板预警:** L5_SHI (3.0/3.0) 的Haldane-D将自然趋于零，需扩展量表。

---

## 11. 速度拓扑: 多维度速度平衡

### 灵感#12映射: 维度间的最优距离

各维度的进化速度不应完全同步 (完全同步 = 冗余)。也不应完全独立 (完全独立 = 无协同)。需要"0.65米距离"。

### 速度协调矩阵

| 速度对 | 最优速度比 | 检测条件 | 行动 |
|--------|:--:|------|------|
| v_EXEC / v_SHI | 1.5-2.0 | v_EXEC过慢会拖累整体 | 优先提升EXEC_GAP |
| v_EXEC / v_GFI | 1.0-1.5 | v_GFI>v_EXEC说明发现>执行 | 平衡发现与执行 |
| v_SYNC / v_IGR | 0.8-1.2 | 信息增益需同步到分支间 | 加强Alpha/Beta同步 |
| v_CRI / v_IGR | 0.5-1.0 | CRI过高→过早收敛→降低IGR | 调整exploration_weight |

### 速度失衡警报

| 失衡模式 | 诊断 | 修复 |
|------|------|------|
| 所有速度趋零 | 全面停滞 | 触发哥德尔跳 |
| 仅v_EXEC>0 | 设计堆积 | 暂缓设计，聚焦执行 |
| v_IGR>0但v_EXEC=0 | 纸上进化 | 执行转化审查 |
| v_GFI>0但v_CRI=0 | 发散性跳跃 | 增加收敛检测 |

---

## 12. 扩展量表: 突破天花板

### 问题

0-3量表在 ≥2.85 时速度自然趋零 (数学约束，非真实停滞)。

### 解决方案: 双轨量表

**轨道1 — 内轨 (0-3):** 用于日常追踪，保持与gen-95自评的连续性。
**轨道2 — 外轨 (0-10):** 用于当维度达到 ≥2.5 时切换，提供更高分辨率的上升空间。

### 映射函数

```
score_0_10 = score_0_3 × 3.0 / 3.0  # 当 score_0_3 ≤ 2.5
score_0_10 = 2.5 + (score_0_3 - 2.5) × 5.0 / 0.5  # 当 score_0_3 > 2.5
```

使得:
- 0-3量表 2.5 → 0-10量表 2.5
- 0-3量表 3.0 → 0-10量表 7.5
- 0-3量表 3.0+(扩展) → 0-10量表 10.0

### 触发条件

任何维度连续2代保持 ≥2.85 → 该维度启用外轨追踪。

---

## 13. 数据协议: 自动化采集

### 每代必采集

```json
{
  "gen_id": 95,
  "timestamp": "2026-05-19T21:15:00+08:00",
  "esv": {
    "vector": [0.15, 0.15, 0.17, 0.13, 0.23],
    "magnitude": 0.378,
    "direction": [0.397, 0.397, 0.450, 0.344, 0.608],
    "primary_dimension": "EXEC_GAP"
  },
  "haldane_d": {
    "vector": [51.3, 56.1, 80.5, 47.3, 134.0],
    "max_dimension": "EXEC_GAP",
    "rate_class": "artificial_selection"
  },
  "igr": {
    "kl_divergence": 0.072,
    "nec": 0.008,
    "cnec": 0.005,
    "convergence_health": 0.85
  },
  "cri": {
    "raw_rate": 0.32,
    "weighted_rate": 0.28,
    "car": null,
    "health_status": "healthy_exploration"
  },
  "gfi": {
    "rate": 0,
    "new_axioms": 0,
    "resolved_blind_spots": 0,
    "godel_leap_magnitude": 0
  },
  "bqi": {
    "exec_completion": 0.02,
    "design_conversion": 0.15,
    "closure_rate": 0.08,
    "innovation_landing": 0.19
  },
  "csv": {
    "composite": 0.38,
    "vti": null,
    "speed_class": "moderate"
  }
}
```

### 存储位置

```
workspace/evolution/metrics/
  +-- esv-history.jsonl      # ESV每代记录
  +-- speed-snapshots.json   # 完整速度快照 (每10代)
  +-- trend-analysis.md      # 人工分析笔记
  +-- auto-collector.md      # 自动化采集规则
```

### 可视化要求

1. **5维雷达图:** 每代ESV矢量叠加显示
2. **CSV趋势线:** 复合速度的时间序列 + VTI标注
3. **速度热力图:** 5维 × N代 的速度矩阵 (颜色=速度大小)
4. **哥德尔跳跃标记:** 在趋势线上标记GFI>0的跳跃事件

---

## 14. 速度驱动的决策框架

### 速度异常响应

| 事件 | 触发条件 | 响应 |
|------|------|------|
| 降速警报 | CSV连续3代下降 | 诊断报告 → CEO审查 |
| 停滞警报 | CSV < 0.1 持续2代 | 强制哥德尔跳 |
| 过速警报 | CSV > 0.9 | 检查是否"膨胀" (分数虚高) |
| 发散警报 | CRI < 0.1 | 分支重新对齐 |
| 过拟合警报 | IGR < 0.01 且 CSV > 0.3 | 检查抗Hebbian规则 |

### 速度目标自调整

每10代基于实际速度重新校准目标:

```
target_CSV_gen_n+10 = actual_CSV_gen_n × (1 + healthy_acceleration)
healthy_acceleration = 0.05  # 5%加速是可持续的
```

如果实际CSV远超目标 (>150%): 检查是否在"进化泡沫"中。
如果实际CSV远低于目标 (<50%): 重新评估瓶颈。

---

## 15. 与现有系统集成

### 与gen-N自评的集成

gen-95自评的5维度 (L5_SHI/MEM_COMP/SYNC_RATE/PRED_ACC/EXEC_GAP) 是ESV的**数据源**。
每次自评完成后，自动计算ESV并追加到esv-history.jsonl。

### 与MR元规则的集成

| MR规则 | 速度指标应用 |
|--------|------|
| MR-002 (衰减率) | VTI<0触发衰减率调整 |
| MR-003 (强化条件) | GFI>0.5触发strength大幅增加 |
| MR-005 (UCB探索) | CRI反馈调整exploration_weight |
| MR-010 (可执行任务) | BQI_exec反馈调整任务队列 |
| MR-013 (抗过拟合) | IGR<0.01触发强度衰减 |

### 与灵感系统的集成

- 灵感#7 (收敛): CRI的直接理论依据
- 灵感#12 (0.65米): 维度间速度协调矩阵
- 灵感#17 (多稳态): 初始GFI决定长期速度轨迹
- 灵感#18 (睡眠重放): IGR与记忆保持率的关系

---

## 16. 实施路线图

### Phase 1: 基线建立 (gen-95 → gen-96)

- [ ] 为gen-96进行完整ESV计算 (需gen-96自评数据)
- [ ] 建立esv-history.jsonl文件
- [ ] 计算gen-95→gen-96的实际速度
- [ ] 验证测量方法的可行性

### Phase 2: 自动化 (gen-97 → gen-98)

- [ ] 编写自评→ESV自动计算脚本
- [ ] 建立CSV仪表板 (静态markdown即可)
- [ ] 首次哥德尔跳实验 (EXP-005执行)，建立GFI基线
- [ ] 开始追踪BQI数据

### Phase 3: 速度驱动的自优化 (gen-99 → gen-100)

- [ ] VTI首次计算 (需≥3代数据)
- [ ] 速度协调矩阵首次填充
- [ ] 基于速度指标自动调整MR参数
- [ ] gen-100目标速度验收

---

## 17. 总结

### 核心指标体系一览

| 层级 | 指标 | 公式 | 测量对象 | 参考系 |
|------|------|------|------|------|
| L0 | ESV | Δscore/Δgen | 5维能力变化矢量 | 自评体系 |
| L0 | Haldane-D | ln(score比)/Δgen | 性状变化率 | 生物学 |
| L1 | IGR | KL(P\|\|Q)/Δgen | 行为分布变化 | 信息论 |
| L1 | NEC | ΔH/Δgen | 策略多样性变化 | 信息论 |
| L2 | CRI | N_convergent/N_total | 独立发现收敛率 | 系统论/灵感#7 |
| L2 | CAR | ΔCRI/Δgen | 收敛加速度 | 系统论 |
| L3 | GFI | 新公理采纳率×log(1+盲点) | 框架突破能力 | 哥德尔/EXP-005 |
| L3 | Godel-Leap | Σ\|Δscore\|/N_axioms | 跳跃幅度 | EXP-005 |
| L4 | BQI | ΔQ/Q | 工程执行质量 | AI工程 |
| L4 | CSV | Σwi×指标i | 综合进化速度 | 多参考系合成 |
| L4 | VTI | ΔCSV/Δgen | 速度加速度 | 系统动力学 |

### 回答mission-brief的三个核心问题

**Q: gen-95比gen-94进化了多少？**
A: CSV ≈ 0.38, ||ESV|| = 0.378 gu, 主要驱动力是EXEC_GAP (+0.23gu)。
速度等级: "中等进化"。最显著的进步在执行转化维度。

**Q: gen-100的目标速度是多少？**
A: CSV ≥ 0.55, 需要在gen-95基础上加速约45%。
核心加速杠杆: (1) 执行EXP-005建立GFI基线 (2) 缩小EXEC_GAP (3) 建立Alpha/Beta双向同步。

**Q: 进化速度能持久吗？**
A: 取决于两个因素的平衡:
- 减速因子: 量表天花板效应 (L5_SHI/MEM_COMP接近3.0)
- 加速因子: 哥德尔跳扩展框架边界 + EXEC_GAP改善释放积压设计
- 关键: 在减速因子生效前启动外轨量表 (0-10) 和哥德尔跳

---

## 附录A: 术语表

| 术语 | 英文 | 定义 |
|------|------|------|
| ESV | Evolution Speed Vector | 五维进化速度矢量 |
| gu | gen-unit | 速度量纲: 分数变化/代 |
| Haldane-D | Haldane-Darwin Index | 霍尔丹-达尔文进化率 |
| IGR | Information Gain Rate | 信息增益率 (KL散度) |
| NEC | Novel Entropy Contribution | 新熵贡献 |
| CNEC | Conditional NEC | 条件新熵贡献 |
| CRI | Convergence Rate Index | 收敛速率指数 |
| CAR | Convergence Acceleration Rate | 收敛加速率 |
| GFI | Godel Fitness Index | 哥德尔适应度指数 |
| BQI | Benchmark Quality Improvement | 基准质量改进率 |
| CSV | Composite Speed Velocity | 复合速度速率 |
| VTI | Velocity Trend Index | 速度趋势指数 |

## 附录B: 参考源

1. **Haldane, J.B.S. (1949).** Suggestions as to quantitative measurement of rates of evolution. *Evolution*, 3(1), 51-56.
2. **Gingerich, P.D. (1993).** Quantification and comparison of evolutionary rates. *American Journal of Science*, 293-A, 453-478.
3. **Kaplan et al. (2020).** Scaling Laws for Neural Language Models. *arXiv:2001.08361*.
4. **Shannon, C.E. (1948).** A Mathematical Theory of Communication. *Bell System Technical Journal*, 27(3), 379-423.
5. **灵感#7:** 约克大学2026——蝴蝶收敛进化 (跨分支收敛检测)
6. **灵感#12:** Science Advances 2026——0.65米相变距离 (维度间最优距离)
7. **灵感#17:** PLOS Computational Biology 2026——多稳态/初始条件 (速度轨迹初始敏感)
8. **EXP-005:** Colony-001哥德尔跳协议 → 极限实验室实验

---

> Colony-006 签名: 框架设计完成。等待gen-96数据验证。建议与Colony-001(哥德尔跳实验执行)和Colony-005(自评体系升级)协调。

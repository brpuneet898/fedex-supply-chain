# Risk-Aware Inventory Pilot Brief (t-Copula)

## Why this matters

We evaluated inventory control policies under **correlated supply-chain shocks** modeled using a **t-copula**.  
This captures:

- clustered disruptions  
- fat-tailed losses  
- prolonged risk spillovers  

Goal: **minimize cost while avoiding extreme tail events**.

---

## Best policy under t-copula

Across all scenarios (S1–S3), the **best policy remains the tuned (s,S) baseline**.

It delivers:

- **Stable service levels (~0.73–0.76)**
- **Lowest mean total cost**
- **Lowest tail-risk (VaR95 and TVaR95)**
- **Fewer SCRI violations**

Other approaches:

- **Myopic heuristic** — acceptable, but consistently worse than (s,S)
- **Q-Learning & DQN-lite** — unstable under shocks, worse cost and risk

Insight:

> Under correlated shocks, well-tuned rule-based policies outperform RL unless training directly accounts for tail-risk and constraints.

## KPI deltas vs. best baseline ((s,S))

| KPI | Myopic vs (s,S) | Q-Learning vs (s,S) | DQN-lite vs (s,S) |
|---|---|---|---|
| **Mean cost** | higher | much higher | much higher |
| **Service level** | lower | much lower | much lower |
| **VaR95 / TVaR95** | higher tail cost | significantly worse | significantly worse |
| **SCRI violations** | more | substantially more | substantially more |

**Bottom line:**  
Policies that ignore tail-risk **appear cheaper at first**, but pay heavily when shocks cluster.

## One plot: VaR95 vs Mean Cost (frontier)

Interpretation:

- **Bottom-left = ideal** (low mean cost + low tail cost)
- **Top-right = poor** (expensive + risky)

Across S1–S3:

- **(s,S)** sits closest to the efficient frontier
- **Myopic** shifts upward/right (more risk, more cost)
- **RL agents** move further up/right as volatility grows

> Controlling mean cost alone pushes us off the frontier — **risk must be optimized explicitly**.

## Recommended actions

### Short term
- Standardize on **tuned (s,S)** by scenario  
- Enforce guardrails:
  - Max VaR95 / TVaR95 thresholds  
  - Limits on SCRI violations  

### Medium term
Improve RL before reconsidering production use:

- Tail-weighted rewards
- State variables capturing disruption memory
- Explicit penalties for SCRI breaches
- Explore **hybrid RL → tuning (s,S)** instead of replacing it

## Decision summary

- t-copula reveals realistic clustered shocks  
- (s,S) remains the safest & cheapest overall  
- Myopic rules are acceptable but inferior  
- Current RL isn’t risk-aware enough yet  
- Invest in **risk-aware learning**, deploy (s,S) now
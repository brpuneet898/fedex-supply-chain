# Goal
Compare classical baselines ((s,S), myopic) to Q-Learning and DQN-lite across three supply-chain risk scenarios, using service level, total cost, SCRI violations, and tail risk (VaR95/TVaR95).

### Scenarios
- **S1:** Base, moderate risk (c_h=0.10, c_b=2.0, c_o=1.0, lambda_scri=10, indicator SCRI).
- **S2:** High demand volatility + more disruptions (c_h=0.10, c_b=3.0, c_o=1.1, lambda_scri=14, hinge SCRI).
- **S3:** Expensive holding, faster replenishment (c_h=0.25, c_b=2.2, c_o=1.0, lambda_scri=9, indicator SCRI).

### Methods / Training
- **(s,S) grid:** Exhaustive grid over reorder point/target, 50 episodes each; metrics aggregated in `reports/rl_pilot/baselines.csv`.
- **Myopic:** Heuristic reorder with expedite/mitigate rules; same evaluation as (s,S).
- **Q-Learning:** Tabular, discretized obs/action; 3 seeds × 1,500 episodes per scenario (`reports/rl_pilot/ql_results.csv`).
- **DQN-lite:** Shallow DQN with replay/target; 3 seeds × 1,000 episodes per scenario (`reports/rl_pilot/dqn_results.csv`).
- **Comparison merge:** `reports/rl_pilot/rl_comparison.csv` (all methods, all scenarios).

### Key Metrics
- **Service level:** fulfilled / demand.
- **Total cost:** includes holding, stockout, ordering, disruption, SCRI.
- **SCRI violations:** count of steps above threshold.
- **VaR95 / TVaR95:** weekly cost tail risk.

### Results Snapshot (mean over runs)
| Scenario | Method (best cost for baseline grid) | Service | Total Cost | VaR95 | TVaR95 |
|---|---|---|---|---|---|
| S1 | (s,S) best: s=85, S=100 | 0.756 | 3387.7 | 1134.5 | 1219.2 |
| S1 | Myopic | 0.582 | 4276.0 | 1152.9 | 1202.0 |
| S1 | Q-Learning | 0.131 | 5256.0 | 1373.0 | 1396.0 |
| S1 | DQN-lite | 0.111 | 5080.0 | 1319.6 | 1361.0 |
| S2 | (s,S) best: s=85, S=100 | 0.735 | 4336.5 | 1361.4 | 1438.5 |
| S2 | Myopic | 0.577 | 5589.9 | 1853.6 | 1981.4 |
| S2 | Q-Learning | 0.108 | 9257.1 | 2310.1 | 2352.1 |
| S2 | DQN-lite | 0.092 | 8189.4 | 2316.1 | 2448.6 |
| S3 | (s,S) best: s=90, S=100 | 0.763 | 3479.4 | 936.6 | 946.0 |
| S3 | Myopic | 0.635 | 4129.3 | 1160.0 | 1199.9 |
| S3 | Q-Learning | 0.125 | 6567.4 | 1636.3 | 1695.2 |
| S3 | DQN-lite | 0.115 | 5293.3 | 1349.2 | 1384.8 |

### Takeaways
- Best (s,S) dominates on cost and tail risk in all scenarios; service levels ~0.73–0.76.
- Myopic trails best (s,S) but beats both RL agents on cost and tail risk.
- Current Q-Learning and DQN-lite underperform (low service, higher cost/tail risk); likely need better state features, reward shaping, and longer/retuned training.
- Tail risk (VaR/TVaR) tracks total cost: methods with lower mean cost also yield lower VaR/TVaR.

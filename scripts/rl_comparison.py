import os
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REP = os.path.join(ROOT,"reports","rl_pilot")

base = pd.read_csv(os.path.join(REP,"baselines.csv"))
ql   = pd.read_csv(os.path.join(REP,"ql_results.csv"))
dqn  = pd.read_csv(os.path.join(REP,"dqn_results.csv"))

cols = [
  "scenario","method","seed","episode",
  "service_level","total_cost","scri_viol","VaR95","TVaR95"
]

df = pd.concat([
    base[cols],
    ql[cols],
    dqn[cols]
], ignore_index=True)

out = os.path.join(REP,"rl_comparison.csv")
df.to_csv(out,index=False)
print(f"[OK] wrote -> {out}")

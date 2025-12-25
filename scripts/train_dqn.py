import os, json
import pandas as pd
from scripts.dqn_lite import train_dqn_lite

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CFG = os.path.join(ROOT, "configs", "rl_pilot", "scenarios.json")
CSV = os.path.join(ROOT, "csv_results")
REP = os.path.join(ROOT, "reports", "rl_pilot")
os.makedirs(CSV, exist_ok=True)
os.makedirs(REP, exist_ok=True)

def load_scenarios():
    with open(CFG,"r") as f:
        return json.load(f)["scenarios"]

def main():
    scenarios = load_scenarios()
    all_rows = []

    for sc in scenarios:
        sid = sc["id"]
        env_cfg = sc["env"]
        for seed in (0,1,2):
            df = train_dqn_lite(env_cfg, sid, episodes=1000, seed=seed)
            df.to_csv(os.path.join(CSV,f"dqn_kpis_{sid}_seed{seed}.csv"),index=False)
            all_rows.extend(df.to_dict(orient="records"))

    out = os.path.join(REP,"dqn_results.csv")
    pd.DataFrame(all_rows).to_csv(out,index=False)
    print(f"[OK] wrote -> {out}")

if __name__=="__main__":
    main()

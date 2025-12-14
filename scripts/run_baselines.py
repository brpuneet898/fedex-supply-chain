import os
import json
import numpy as np
import pandas as pd
from tqdm import trange

from src.env_supplychain import SupplyChainSimEnv
from src.baselines.policy_sS import SsPolicy, SsParams
from src.baselines.policy_myopic import MyopicPolicy, MyopicParams

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CSV_DIR = os.path.join(ROOT, "csv_results")
REPORT_DIR = os.path.join(ROOT, "reports", "rl_pilot")
os.makedirs(CSV_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)


def compute_kpis(ep_log, week=7, scri_threshold=0.7):
    total_demand = sum(x["demand"] for x in ep_log)
    fulfilled = sum(x["fulfilled"] for x in ep_log)
    service_level = fulfilled / total_demand if total_demand > 0 else 1.0

    scri_viol = sum(1 for x in ep_log if x["scri"] > scri_threshold)

    costs = [x["cost"] for x in ep_log]
    weekly_costs = [sum(costs[i:i + week]) for i in range(0, len(costs), week)]
    if weekly_costs:
        var95 = float(np.percentile(weekly_costs, 95))
        tail = [c for c in weekly_costs if c > var95]
        tvar95 = float(np.mean(tail)) if len(tail) else var95
    else:
        var95 = tvar95 = 0.0

    return {
        "service_level": float(service_level),
        "total_cost": float(sum(costs)),
        "scri_viol": int(scri_viol),
        "VaR95": float(var95),
        "TVaR95": float(tvar95),
    }


def _weights_from_env(env: SupplyChainSimEnv):
    return {
        "c_h": getattr(env, "c_h", np.nan),
        "c_b": getattr(env, "c_b", np.nan),
        "c_o": getattr(env, "c_o", np.nan),
        "c_disruption": getattr(env, "c_disruption", np.nan),
        "lambda_scri": getattr(env, "lambda_scri", np.nan),
        "scri_threshold": getattr(env, "scri_threshold", 0.7),
        "scri_mode": getattr(env, "scri_mode", "indicator"),
    }


def run_policy(env, policy, episodes=50, seed=0, method_name="baseline", scenario_id="S?"):
    out = []
    w = _weights_from_env(env)

    for ep in trange(episodes, desc=f"{scenario_id}:{method_name}", leave=False):
        _ = env.seed(int(seed + ep))
        obs = env.reset()
        done = False
        ep_log = []

        while not done:
            if hasattr(policy, "set_forecast"):
                policy.set_forecast(getattr(env, "demand_forecast", 10))

            action = policy.act(obs)
            next_obs, reward, done, info = env.step(action)

            demand = int(info.get("demand", getattr(env, "demand_forecast", 10)))
            fulfilled = int(info.get("fulfilled", min(int(round(float(obs[0]))), demand)))

            ep_log.append({
                "cost": -float(reward),                
                "scri": float(info.get("scri", 0.0)),
                "demand": demand,
                "fulfilled": fulfilled,
            })

            obs = next_obs

        k = compute_kpis(ep_log, scri_threshold=float(w["scri_threshold"]))
        k.update({
            "scenario": scenario_id,
            "method": method_name,
            "seed": int(seed),
            "episode": int(ep),
            **w
        })
        out.append(k)

    return out


def grid_sS(env_cfg, s_grid=range(0, 95, 5), S_grid=range(10, 105, 5),
            episodes=50, seed=0, scenario_id="S?"):
    results = []
    for s in s_grid:
        for S in S_grid:
            if S <= s:
                continue
            params = SsParams(s=s, S=S)
            policy = SsPolicy(params)
            env = SupplyChainSimEnv(config=env_cfg, seed=seed)
            rows = run_policy(env, policy, episodes=episodes, seed=seed,
                              method_name=f"sS(s={s},S={S})", scenario_id=scenario_id)
            for r in rows:
                r["s"] = int(s)
                r["S"] = int(S)
                results.append(r)
    return results


def run_myopic(env_cfg, episodes=50, seed=0, scenario_id="S?"):
    params = MyopicParams(safety_factor=0.0, expedite_threshold=0.9, mitigate_on_disruption=2)
    policy = MyopicPolicy(params)
    env = SupplyChainSimEnv(config=env_cfg, seed=seed)
    rows = run_policy(env, policy, episodes=episodes, seed=seed,
                      method_name="myopic", scenario_id=scenario_id)
    for r in rows:
        r["s"] = np.nan
        r["S"] = np.nan
    return rows


def load_scenarios(cfg_path: str):
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    scenarios = cfg.get("scenarios", [])
    if not scenarios:
        raise ValueError(f"No scenarios found in {cfg_path}")
    return scenarios


def main():
    scenarios_path = os.path.join(ROOT, "configs", "rl_pilot", "scenarios.json")
    scenarios = load_scenarios(scenarios_path)

    all_rows = []
    for sc in scenarios:
        sid = sc["id"]
        env_cfg = sc["env"]

        all_rows.extend(grid_sS(env_cfg, episodes=50, seed=42, scenario_id=sid))
        all_rows.extend(run_myopic(env_cfg, episodes=50, seed=42, scenario_id=sid))

    df = pd.DataFrame(all_rows)

    out_path = os.path.join(REPORT_DIR, "baselines.csv")
    df.to_csv(out_path, index=False)

    df.to_csv(os.path.join(CSV_DIR, "baseline_kpis.csv"), index=False)

    print(f"[OK] Wrote consolidated baselines -> {out_path}")


if __name__ == "__main__":
    main()

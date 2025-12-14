import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from tqdm import trange

from src.env_supplychain import SupplyChainSimEnv
from src.agent_qlearning import QLearningAgent, get_bins, get_action_space
from scripts.run_baselines import compute_kpis  # reuse KPI logic

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CSV_DIR = os.path.join(ROOT, "csv_results")
FIG_DIR = os.path.join(ROOT, "figures")
REPORT_DIR = os.path.join(ROOT, "reports", "rl_pilot")
os.makedirs(CSV_DIR, exist_ok=True)
os.makedirs(FIG_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)


def load_scenarios(cfg_path: str):
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    scenarios = cfg.get("scenarios", [])
    if not scenarios:
        raise ValueError(f"No scenarios found in {cfg_path}")
    return scenarios


def run_qlearning_one_scenario(scenario_id: str, env_cfg: dict, episodes=1000, seeds=(0, 1, 2)):
    curves = []
    kpi_rows = []

    for seed in seeds:
        env = SupplyChainSimEnv(config=env_cfg, seed=seed)
        obs_bins = get_bins()
        action_space = get_action_space()
        agent = QLearningAgent(obs_bins, action_space)

        rewards = []
        for ep in trange(episodes, desc=f"QL {scenario_id} seed {seed}", leave=False):
            obs = env.reset()
            done = False
            ep_rew = 0.0
            ep_log = []

            while not done:
                action_idx = agent.select_action(obs)
                q, e, m = action_space[action_idx]
                action = {"order_qty": q, "expedite": e, "mitigate": m}

                next_obs, reward, done, info = env.step(action)
                agent.update(obs, action_idx, reward, next_obs, done)

                demand = int(info.get("demand", getattr(env, "demand_forecast", 10)))
                fulfilled = int(info.get("fulfilled", min(int(round(float(obs[0]))), demand)))

                ep_log.append({
                    "cost": -float(reward),
                    "scri": float(info.get("scri", 0.0)),
                    "demand": demand,
                    "fulfilled": fulfilled
                })

                ep_rew += float(reward)
                obs = next_obs

            rewards.append(ep_rew)
            k = compute_kpis(ep_log, scri_threshold=float(getattr(env, "scri_threshold", 0.7)))
            k.update({
                "scenario": scenario_id,
                "method": "qlearning",
                "seed": int(seed),
                "episode": int(ep),
                "c_h": float(getattr(env, "c_h", np.nan)),
                "c_b": float(getattr(env, "c_b", np.nan)),
                "c_o": float(getattr(env, "c_o", np.nan)),
                "c_disruption": float(getattr(env, "c_disruption", np.nan)),
                "lambda_scri": float(getattr(env, "lambda_scri", np.nan)),
                "scri_threshold": float(getattr(env, "scri_threshold", 0.7)),
                "scri_mode": str(getattr(env, "scri_mode", "indicator")),
            })
            kpi_rows.append(k)

        curves.append({"scenario": scenario_id, "seed": seed, "rewards": rewards})

    return curves, kpi_rows


def save_learning_curve_png(curves, scenario_id: str):
    plt.figure()
    for c in curves:
        if c["scenario"] != scenario_id:
            continue
        plt.plot(c["rewards"], alpha=0.6, label=f"seed {c['seed']}")
    plt.xlabel("Episode")
    plt.ylabel("Cumulative Reward")
    plt.title(f"Q-learning Learning Curves ({scenario_id})")
    plt.legend()
    plt.grid(True)
    out = os.path.join(REPORT_DIR, f"learning_curve_{scenario_id}.png")
    plt.tight_layout()
    plt.savefig(out)
    plt.close()
    return out


def main():
    scenarios_path = os.path.join(ROOT, "configs", "rl_pilot", "scenarios.json")
    scenarios = load_scenarios(scenarios_path)

    all_curves = []
    all_kpis = []

    for sc in scenarios:
        sid = sc["id"]
        env_cfg = sc["env"]

        curves, kpis = run_qlearning_one_scenario(
            scenario_id=sid,
            env_cfg=env_cfg,
            episodes=1000,
            seeds=(0, 1, 2),
        )
        all_curves.extend(curves)
        all_kpis.extend(kpis)

        png_path = save_learning_curve_png(all_curves, sid)
        print(f"[OK] Saved learning curve -> {png_path}")

        pd.DataFrame([k for k in all_kpis if k["scenario"] == sid]).to_csv(
            os.path.join(CSV_DIR, f"qlearning_kpis_{sid}.csv"), index=False
        )

    ql_out = os.path.join(REPORT_DIR, "ql_results.csv")
    pd.DataFrame(all_kpis).to_csv(ql_out, index=False)
    print(f"[OK] Wrote consolidated Q-learning KPIs -> {ql_out}")


if __name__ == "__main__":
    main()

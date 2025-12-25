import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from tqdm import trange

from src.env_supplychain import SupplyChainSimEnv
from src.agents.qlearning import (
    QLearningAgent,
    build_obs_bins,
    build_action_space
)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CFG_DIR = os.path.join(ROOT, "configs", "rl_pilot")
CSV_DIR = os.path.join(ROOT, "csv_results", "rl_pilot")
FIG_DIR = os.path.join(ROOT, "figures", "rl_pilot")
REP_DIR = os.path.join(ROOT, "reports", "rl_pilot")

for d in [CSV_DIR, FIG_DIR, REP_DIR]:
    os.makedirs(d, exist_ok=True)


def load_json(p):
    with open(p, "r") as f:
        return json.load(f)


# def compute_kpis(log, scri_th):
#     demand = sum(x["demand"] for x in log)
#     fulfilled = sum(x["fulfilled"] for x in log)
#     service = fulfilled / demand if demand > 0 else 1.0
#     scri_viol = sum(1 for x in log if x["scri"] > scri_th)
#     cost = sum(x["cost"] for x in log)
#     return service, cost, scri_viol

def compute_kpis(log, scri_th, week=7, alpha=0.95):
    demand = sum(x["demand"] for x in log)
    fulfilled = sum(x["fulfilled"] for x in log)
    service = fulfilled / demand if demand > 0 else 1.0

    scri_viol = sum(1 for x in log if x["scri"] > scri_th)

    costs = [x["cost"] for x in log]
    total_cost = float(sum(costs))

    weekly_costs = [sum(costs[i:i + week]) for i in range(0, len(costs), week)]
    if weekly_costs:
        var_q = float(np.percentile(weekly_costs, alpha * 100.0))
        tail = [c for c in weekly_costs if c > var_q]
        tvar_q = float(np.mean(tail)) if tail else var_q
    else:
        var_q = 0.0
        tvar_q = 0.0

    return service, total_cost, scri_viol, var_q, tvar_q



def main():
    scenarios = load_json(os.path.join(CFG_DIR, "scenarios.json"))["scenarios"]
    qcfg = load_json(os.path.join(CFG_DIR, "qlearning.json"))

    risk_cfg = qcfg.get("risk", {})
    risk_alpha = float(risk_cfg.get("cvar_alpha", 0.95))
    week_agg = int(risk_cfg.get("week_agg", 7))

    obs_bins = build_obs_bins(qcfg["observation_bins"])
    action_space = build_action_space(qcfg["action_space"])

    all_rows = []

    for sc in scenarios:
        sid = sc["id"]
        env_cfg = sc["env"]
        base_env_cfg = sc["env"]

        for seed in qcfg["training"]["seeds"]:
            env_cfg = dict(base_env_cfg)  # shallow copy
            existing_risk = env_cfg.get("risk", {})
            merged_risk = dict(existing_risk)
            merged_risk.update(risk_cfg)
            env_cfg["risk"] = merged_risk
            env = SupplyChainSimEnv(env_cfg, seed=seed)

            agent = QLearningAgent(
                obs_bins,
                action_space,
                **{k: qcfg["training"][k] for k in
                   ["alpha", "gamma", "eps_start", "eps_min", "eps_decay"]}
            )

            rewards = []
            kpi_rows = []

            for ep in trange(qcfg["training"]["episodes"], desc=f"{sid} seed {seed}"):
                obs = env.reset()
                done = False
                ep_reward = 0
                ep_log = []

                while not done:
                    a_idx = agent.select_action(obs)
                    q, e, m = action_space[a_idx]
                    next_obs, reward, done, info = env.step(
                        {"order_qty": q, "expedite": e, "mitigate": m}
                    )

                    agent.update(obs, a_idx, reward, next_obs, done)

                    ep_reward += reward
                    ep_log.append({
                        "cost": -reward,
                        "scri": info["scri"],
                        "demand": info["demand"],
                        "fulfilled": info["fulfilled"]
                    })
                    obs = next_obs

                agent.decay()
                rewards.append(ep_reward)

                # svc, cost, viol = compute_kpis(ep_log, env.scri_threshold)
                # kpi_rows.append({
                #     "scenario": sid,
                #     "seed": seed,
                #     "episode": ep,
                #     "service_level": svc,
                #     "total_cost": cost,
                #     "scri_viol": viol
                # })

                svc, cost, viol, var95, tvar95 = compute_kpis(
                    ep_log,
                    env.scri_threshold,
                    week=week_agg,
                    alpha=risk_alpha,
                )
                kpi_rows.append({
                    "scenario": sid,
                    "method": "qlearning",
                    "seed": seed,
                    "episode": ep,
                    "service_level": svc,
                    "total_cost": cost,
                    "scri_viol": viol,
                    "VaR95": var95,
                    "TVaR95": tvar95,
                })

            pd.DataFrame(kpi_rows).to_csv(
                os.path.join(CSV_DIR, f"qlearning_kpis_{sid}_seed{seed}.csv"),
                index=False
            )

            plt.figure()
            plt.plot(rewards)
            plt.title(f"Q-learning {sid} seed {seed}")
            plt.xlabel("Episode")
            plt.ylabel("Reward")
            plt.grid()
            plt.savefig(os.path.join(FIG_DIR, f"learning_curve_{sid}_seed{seed}.png"))
            plt.close()

            all_rows.extend(kpi_rows)

    # pd.DataFrame(all_rows).to_csv(
    #     os.path.join(REP_DIR, "ql_results.csv"), index=False
    # )

    df_all = pd.DataFrame(all_rows)
    df_all.to_csv(
        os.path.join(REP_DIR, "ql_results.csv"), index=False
    )

    summary = (
        df_all
        .groupby(["scenario", "method", "seed"], as_index=False)[
            ["total_cost", "service_level", "scri_viol", "VaR95", "TVaR95"]
        ]
        .mean()
    )
    summary_path = os.path.join(REP_DIR, "mean_vs_var_qlearning.csv")
    summary.to_csv(summary_path, index=False)


if __name__ == "__main__":
    main()

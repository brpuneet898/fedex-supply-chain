import gym
import numpy as np
import simpy
from gym import spaces
from scipy.stats import t, norm

class StudentTCopulaSampler:
    def __init__(self, marginals, corr, df=4, seed=None):
        self.marginals = marginals
        self.corr = corr
        self.df = df
        self.dim = len(marginals)
        self.rng = np.random.default_rng(seed)

    def sample(self, n=1):
        g = self.rng.standard_normal((n, self.dim))
        L = np.linalg.cholesky(self.corr)
        z = g @ L.T
        chi2 = self.rng.chisquare(self.df, n)[:, None]
        t_samples = z / np.sqrt(chi2 / self.df)
        u = t.cdf(t_samples, df=self.df)
        samples = np.column_stack([m.ppf(u[:, i]) for i, m in enumerate(self.marginals)])
        return samples


def _norm_from_cfg(cfg, default_loc, default_scale):
    if not isinstance(cfg, dict):
        return norm(loc=default_loc, scale=default_scale)
    return norm(loc=float(cfg.get("loc", default_loc)), scale=float(cfg.get("scale", default_scale)))


class SupplyChainSimEnv(gym.Env):
    """
    Configurable supply chain sim env.

    Expected config schema (all optional):
      {
        "max_steps": 30,
        "initial_inventory": 50,

        "copula": {
          "df": 4,
          "marginals": {
            "leadtime": {"loc": 5, "scale": 2},
            "demand": {"loc": 100, "scale": 30},        # used as "severity" -> demand_forecast
            "interarrival": {"loc": 2, "scale": 0.5}
          },
          "corr": [[...],[...],[...]]
        },

        "disruption": {
          "period_mean": 10,
          "period_jitter": 2,
          "p_levels": [0.8, 0.15, 0.05]  # probs for disruption levels [0,1,2]
        },

        "scri": {
          "threshold": 0.7,
          "stockout_weight": 0.5,
          "disruption_weight": 0.5
        },

        "costs": {
          "c_h": 0.1,             # holding cost per unit inventory
          "c_b": 2.0,             # stockout/backorder cost per unit
          "c_o": 1.0,             # ordering cost per unit ordered
          "c_disruption": 5.0,    # disruption indicator penalty
          "lambda_scri": 10.0,    # SCRI penalty multiplier (hinge or indicator)
          "scri_mode": "indicator" # "indicator" or "hinge"
        }
      }
    """

    metadata = {"render.modes": ["human"]}

    def __init__(self, config=None, seed=None):
        super().__init__()
        self.config = config or {}
        self.seed(seed)

        self.action_space = spaces.Dict({
            "order_qty": spaces.Discrete(21),  
            "expedite": spaces.Discrete(2),
            "mitigate": spaces.Discrete(2),
        })

        self.observation_space = spaces.Box(
            low=np.array([0, 0, 0, 0, 0.0]),
            high=np.array([100, 100, 30, 2, 1.0]),
            dtype=np.float32
        )

        cop_cfg = self.config.get("copula", {}) if isinstance(self.config.get("copula", {}), dict) else {}
        marg_cfg = cop_cfg.get("marginals", {}) if isinstance(cop_cfg.get("marginals", {}), dict) else {}

        self.marginals = [
            _norm_from_cfg(marg_cfg.get("leadtime"), default_loc=5, default_scale=2),
            _norm_from_cfg(marg_cfg.get("demand"), default_loc=100, default_scale=30),
            _norm_from_cfg(marg_cfg.get("interarrival"), default_loc=2, default_scale=0.5),
        ]

        default_corr = np.array([
            [1.0, 0.3, 0.2],
            [0.3, 1.0, 0.4],
            [0.2, 0.4, 1.0]
        ], dtype=float)
        corr_cfg = cop_cfg.get("corr", None)
        self.corr = np.array(corr_cfg, dtype=float) if corr_cfg is not None else default_corr

        df = int(cop_cfg.get("df", 4))
        self.copula = StudentTCopulaSampler(self.marginals, self.corr, df=df, seed=self._seed)

        dis_cfg = self.config.get("disruption", {}) if isinstance(self.config.get("disruption", {}), dict) else {}
        self.disruption_period_mean = int(dis_cfg.get("period_mean", 10))
        self.disruption_period_jitter = int(dis_cfg.get("period_jitter", 2))
        self.disruption_p_levels = dis_cfg.get("p_levels", [0.8, 0.15, 0.05])
        if len(self.disruption_p_levels) != 3:
            self.disruption_p_levels = [0.8, 0.15, 0.05]

        scri_cfg = self.config.get("scri", {}) if isinstance(self.config.get("scri", {}), dict) else {}
        self.scri_threshold = float(scri_cfg.get("threshold", 0.7))
        self.scri_stockout_weight = float(scri_cfg.get("stockout_weight", 0.5))
        self.scri_disruption_weight = float(scri_cfg.get("disruption_weight", 0.5))

        cost_cfg = self.config.get("costs", {}) if isinstance(self.config.get("costs", {}), dict) else {}
        self.c_h = float(cost_cfg.get("c_h", 0.1))
        self.c_b = float(cost_cfg.get("c_b", 2.0))
        self.c_o = float(cost_cfg.get("c_o", 1.0))
        self.c_disruption = float(cost_cfg.get("c_disruption", 5.0))
        self.lambda_scri = float(cost_cfg.get("lambda_scri", 10.0))
        self.scri_mode = str(cost_cfg.get("scri_mode", "indicator")).lower().strip()
        if self.scri_mode not in ("indicator", "hinge"):
            self.scri_mode = "indicator"

        # --- misc ---
        self.max_steps = int(self.config.get("max_steps", 30))
        self.initial_inventory = int(self.config.get("initial_inventory", 50))

        self.reset()

    def seed(self, seed=None):
        self._seed = seed
        self.np_random = np.random.default_rng(seed)
        return [seed]

    def reset(self):
        self.env = simpy.Environment()
        self.current_step = 0
        self.inventory = int(self.initial_inventory)
        self.outstanding = 0
        self.leadtime = 5
        self.disruption = 0
        self.scri = 0.0
        self.done = False
        self.total_cost = 0.0
        self.order_pipeline = []
        self.demand_forecast = 10
        self._setup_events()
        return self._get_obs()

    def _setup_events(self):
        self.env.process(self._demand_process())
        self.env.process(self._disruption_process())

    def _demand_process(self):
        while True:
            _, severity, interarrival = self.copula.sample(1)[0]
            yield self.env.timeout(max(0.1, float(interarrival)))
            self.demand_forecast = max(1, int(severity))

    def _disruption_process(self):
        while True:
            jitter = int(self.np_random.integers(-self.disruption_period_jitter, self.disruption_period_jitter + 1))
            yield self.env.timeout(max(1, self.disruption_period_mean + jitter))
            self.disruption = int(self.np_random.choice([0, 1, 2], p=self.disruption_p_levels))

    def step(self, action):
        if self.done:
            raise RuntimeError("Episode is done. Call reset().")

        qty = int(action["order_qty"])
        expedite = bool(action["expedite"])
        mitigate = bool(action["mitigate"])

        leadtime, _, _ = self.copula.sample(1)[0]
        leadtime = max(1, int(leadtime))
        if expedite:
            leadtime = max(1, leadtime - 2)

        if mitigate and self.disruption > 0:
            self.disruption = max(0, self.disruption - 1)

        self.order_pipeline.append((self.env.now + leadtime, qty))
        self.outstanding += qty

        self.env.step()
        self.current_step += 1

        arrivals = [q for t, q in self.order_pipeline if t <= self.env.now]
        self.inventory += int(sum(arrivals))
        self.outstanding -= int(sum(arrivals))
        self.order_pipeline = [(t, q) for t, q in self.order_pipeline if t > self.env.now]

        demand = int(self.demand_forecast)
        fulfilled = min(int(self.inventory), demand)
        self.inventory -= int(fulfilled)
        stockout = max(0, demand - int(fulfilled))

        stockout_ratio = stockout / (demand + 1e-6)
        disruption_norm = self.disruption / 2.0
        self.scri = float(min(
            1.0,
            self.scri_stockout_weight * stockout_ratio + self.scri_disruption_weight * disruption_norm
        ))

        holding_cost = self.c_h * float(self.inventory)
        stockout_cost = self.c_b * float(stockout)
        order_cost = self.c_o * float(qty)
        disruption_cost = self.c_disruption * float(self.disruption > 0)

        if self.scri_mode == "hinge":
            scri_penalty = self.lambda_scri * max(0.0, self.scri - self.scri_threshold)
        else:
            scri_penalty = self.lambda_scri * float(self.scri > self.scri_threshold)

        cost = holding_cost + stockout_cost + order_cost + disruption_cost + scri_penalty
        self.total_cost += float(cost)

        self.done = self.current_step >= self.max_steps
        obs = self._get_obs()

        info = {
            "cost": float(cost),
            "scri": float(self.scri),
            "demand": int(demand),
            "fulfilled": int(fulfilled),
            "stockout": int(stockout),
            "cost_breakdown": {
                "holding": float(holding_cost),
                "stockout": float(stockout_cost),
                "order": float(order_cost),
                "disruption": float(disruption_cost),
                "scri_penalty": float(scri_penalty),
            },
            "weights": {
                "c_h": self.c_h, "c_b": self.c_b, "c_o": self.c_o,
                "c_disruption": self.c_disruption,
                "lambda_scri": self.lambda_scri,
                "scri_threshold": self.scri_threshold,
                "scri_mode": self.scri_mode,
            }
        }
        return obs, -float(cost), self.done, info

    def _get_obs(self):
        return np.array([
            self.inventory,
            self.outstanding,
            self.leadtime,
            self.disruption,
            self.scri
        ], dtype=np.float32)

    def render(self, mode="human"):
        print(
            f"Step {self.current_step}: Inv={self.inventory}, Out={self.outstanding}, "
            f"Disr={self.disruption}, SCRI={self.scri:.2f}"
        )

    def close(self):
        pass
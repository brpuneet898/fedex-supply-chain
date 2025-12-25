import os
import math
import time
import random
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim

from src.env_supplychain import SupplyChainSimEnv
from scripts.run_baselines import compute_kpis   
from collections import deque

def get_action_space():
    return [(q, e, m) for q in range(0, 21, 5) for e in [0, 1] for m in [0, 1]]

def idx_to_env_action(idx, action_space):
    q,e,m = action_space[idx]
    return {"order_qty": q, "expedite": e, "mitigate": m}

def norm_obs(obs):
    highs = np.array([100,100,30,2,1], dtype=np.float32)
    return (obs.astype(np.float32)/highs).clip(0,1)


class ReplayBuffer:
    def __init__(self, cap, obs_dim):
        self.cap = cap
        self.ptr = 0
        self.full = False
        self.obs = np.zeros((cap, obs_dim), np.float32)
        self.nobs = np.zeros((cap, obs_dim), np.float32)
        self.act = np.zeros(cap, np.int64)
        self.rew = np.zeros(cap, np.float32)
        self.done = np.zeros(cap, np.float32)

    def add(self,o,a,r,o2,d):
        self.obs[self.ptr]=o
        self.act[self.ptr]=a
        self.rew[self.ptr]=r
        self.nobs[self.ptr]=o2
        self.done[self.ptr]=d
        self.ptr=(self.ptr+1)%self.cap
        if self.ptr==0: self.full=True

    def __len__(self):
        return self.cap if self.full else self.ptr

    def sample(self,b):
        n=len(self)
        idx=np.random.randint(0,n,b)
        return (
            torch.from_numpy(self.obs[idx]),
            torch.from_numpy(self.act[idx]),
            torch.from_numpy(self.rew[idx]),
            torch.from_numpy(self.nobs[idx]),
            torch.from_numpy(self.done[idx]),
        )


class QNet(nn.Module):
    def __init__(self, obs_dim, n_actions, hidden=128):
        super().__init__()
        self.net=nn.Sequential(
            nn.Linear(obs_dim,hidden), nn.ReLU(),
            nn.Linear(hidden,hidden), nn.ReLU(),
            nn.Linear(hidden,n_actions)
        )

    def forward(self,x):
        return self.net(x)


def train_dqn_lite(env_cfg, scenario_id, episodes=1000, seed=0, device="cpu"):
    np.random.seed(seed)
    random.seed(seed)
    torch.manual_seed(seed)

    env = SupplyChainSimEnv(config=env_cfg, seed=seed)
    action_space = get_action_space()
    n_actions = len(action_space)

    obs = env.reset()
    obs_dim = len(obs)

    q = QNet(obs_dim, n_actions).to(device)
    qt = QNet(obs_dim, n_actions).to(device)
    qt.load_state_dict(q.state_dict())
    qt.eval()

    opt = optim.Adam(q.parameters(), lr=1e-3)
    huber = nn.SmoothL1Loss(reduction="none")

    rb = ReplayBuffer(50000, obs_dim)

    eps_start, eps_end, decay = 1.0, 0.05, 400
    gamma = 0.99
    batch = 64
    start_train = 1000
    target_freq = 200
    grad_steps = 0

    rows=[]
    for ep in range(episodes):
        obs = env.reset()
        done=False
        ep_log=[]
        eps = eps_start + (eps_end-eps_start)*min(1.0, ep/decay)

        while not done:
            o_norm = norm_obs(obs)
            if np.random.rand() < eps:
                a_idx = np.random.randint(n_actions)
            else:
                with torch.no_grad():
                    qs = q(torch.from_numpy(o_norm).unsqueeze(0).to(device))
                    a_idx = int(qs.argmax(dim=1))

            act = idx_to_env_action(a_idx, action_space)
            next_obs, reward, done, info = env.step(act)

            rb.add(o_norm, a_idx, reward, norm_obs(next_obs), float(done))

            ep_log.append({
                "cost": -float(reward),
                "scri": float(info.get("scri",0)),
                "demand": int(info.get("demand", env.demand_forecast)),
                "fulfilled": int(info.get("fulfilled",0)),
            })

            obs = next_obs

            if len(rb) >= start_train:
                ob,ac,rw,ob2,dn = rb.sample(batch)
                ob=ob.float().to(device); ac=ac.long().to(device)
                rw=rw.float().to(device); ob2=ob2.float().to(device)
                dn=dn.float().to(device)

                qv = q(ob).gather(1,ac.view(-1,1)).squeeze(1)
                with torch.no_grad():
                    na = q(ob2).argmax(dim=1)
                    nq = qt(ob2).gather(1,na.view(-1,1)).squeeze(1)
                    tgt = rw + gamma*(1.0-dn)*nq

                loss = huber(qv,tgt).mean()
                opt.zero_grad(set_to_none=True)
                loss.backward()
                nn.utils.clip_grad_norm_(q.parameters(),10.0)
                opt.step()

                grad_steps += 1
                if grad_steps % target_freq == 0:
                    qt.load_state_dict(q.state_dict())

        k = compute_kpis(ep_log, scri_threshold=float(env.scri_threshold))
        k.update({
            "scenario": scenario_id,
            "method": "dqn",
            "seed": int(seed),
            "episode": int(ep),
        })
        rows.append(k)

    env.close()
    return pd.DataFrame(rows)

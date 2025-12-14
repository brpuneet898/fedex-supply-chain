import numpy as np
from itertools import product


def build_obs_bins(bin_config):
    return [np.array(v) for v in bin_config.values()]


def discretize(obs, bins):
    return tuple(int(np.digitize(obs[i], bins[i]) - 1) for i in range(len(bins)))


def build_action_space(action_cfg):
    actions = list(product(
        action_cfg["order_qty"],
        action_cfg["expedite"],
        action_cfg["mitigate"]
    ))
    return actions


class QLearningAgent:
    def __init__(self, obs_bins, action_space, alpha, gamma, eps_start, eps_min, eps_decay):
        self.obs_bins = obs_bins
        self.action_space = action_space
        self.alpha = alpha
        self.gamma = gamma

        self.eps = eps_start
        self.eps_min = eps_min
        self.eps_decay = eps_decay

        state_shape = [len(b) + 1 for b in obs_bins]
        self.Q = np.zeros(state_shape + [len(action_space)])

    def select_action(self, obs):
        state = discretize(obs, self.obs_bins)
        if np.random.rand() < self.eps:
            return np.random.randint(len(self.action_space))
        return int(np.argmax(self.Q[state]))

    def update(self, obs, action_idx, reward, next_obs, done):
        s = discretize(obs, self.obs_bins)
        s2 = discretize(next_obs, self.obs_bins)

        best_next = np.max(self.Q[s2])
        td_target = reward + (0.0 if done else self.gamma * best_next)
        td_error = td_target - self.Q[s + (action_idx,)]
        self.Q[s + (action_idx,)] += self.alpha * td_error

    def decay(self):
        self.eps = max(self.eps_min, self.eps * self.eps_decay)

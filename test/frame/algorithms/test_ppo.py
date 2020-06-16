from machin.model.nets.base import static_module_wrapper as smw
from machin.frame.algorithms.ppo import PPO
from machin.utils.logging import default_logger as logger
from machin.utils.helper_classes import Counter
from machin.utils.conf import Config
from machin.env.utils.openai_gym import disable_view_window
from torch.nn.functional import softplus
from torch.distributions import Normal

import pytest
import torch as t
import torch.nn as nn
import gym

from .utils import unwrap_time_limit, Smooth


class Actor(nn.Module):
    def __init__(self, state_dim, action_dim, action_range):
        super(Actor, self).__init__()

        self.fc1 = nn.Linear(state_dim, 16)
        self.fc2 = nn.Linear(16, 16)
        self.mu_head = nn.Linear(16, action_dim)
        self.sigma_head = nn.Linear(16, action_dim)
        self.action_range = action_range

    def forward(self, state, action=None):
        a = t.relu(self.fc1(state))
        a = t.relu(self.fc2(a))
        a_mu = t.tanh(self.mu_head(a)) * self.action_range
        a_sigma = softplus(self.sigma_head(a))
        a_dist = Normal(a_mu, a_sigma)
        a = action if action is not None else a_dist.sample()
        a_entropy = a_dist.entropy()
        a = a.clamp(-self.action_range, self.action_range)
        a_log_prob = a_dist.log_prob(a)
        return a, a_log_prob, a_entropy


class Critic(nn.Module):
    def __init__(self, state_dim):
        super(Critic, self).__init__()

        self.fc1 = nn.Linear(state_dim, 16)
        self.fc2 = nn.Linear(16, 16)
        self.fc3 = nn.Linear(16, 1)

    def forward(self, state):
        v = t.relu(self.fc1(state))
        v = t.relu(self.fc2(v))
        v = self.fc3(v)
        return v


class TestPPO(object):
    # configs and definitions
    @pytest.fixture(scope="class")
    def train_config(self, pytestconfig):
        disable_view_window()
        c = Config()
        c.env_name = "Pendulum-v0"
        c.env = unwrap_time_limit(gym.make(c.env_name))
        c.observe_dim = 3
        c.action_dim = 1
        c.action_range = 2
        c.max_episodes = 1000
        c.max_steps = 200
        c.replay_size = 10000
        c.solved_reward = -150
        c.solved_repeat = 5
        c.device = "cpu"
        return c

    @pytest.fixture(scope="function")
    def ppo(self, train_config):
        c = train_config
        actor = smw(Actor(c.observe_dim, c.action_dim, c.action_range)
                    .to(c.device), c.device, c.device)
        critic = smw(Critic(c.observe_dim)
                     .to(c.device), c.device, c.device)
        ppo = PPO(actor, critic,
                  t.optim.Adam,
                  nn.MSELoss(reduction='sum'),
                  replay_device=c.device,
                  replay_size=c.replay_size)
        return ppo

    @pytest.fixture(scope="function")
    def ppo_vis(self, train_config, tmpdir):
        # not used for training, only used for testing apis
        c = train_config
        tmp_dir = tmpdir.make_numbered_dir()
        actor = smw(Actor(c.observe_dim, c.action_dim, c.action_range)
                    .to(c.device), c.device, c.device)
        critic = smw(Critic(c.observe_dim)
                     .to(c.device), c.device, c.device)
        ppo = PPO(actor, critic,
                  t.optim.Adam,
                  nn.MSELoss(reduction='sum'),
                  update_times=1,
                  replay_device=c.device,
                  replay_size=c.replay_size,
                  visualize=True,
                  visualize_dir=str(tmp_dir))
        return ppo

    ########################################################################
    # Test for PPO acting
    ########################################################################
    # Skipped, it is the same as A2C

    ########################################################################
    # Test for PPO action evaluation
    ########################################################################
    # Skipped, it is the same as A2C

    ########################################################################
    # Test for PPO criticizing
    ########################################################################
    # Skipped, it is the same as A2C

    ########################################################################
    # Test for PPO storage
    ########################################################################
    # Skipped, it is the same as A2C

    ########################################################################
    # Test for PPO update
    ########################################################################
    def test_update(self, train_config, ppo_vis):
        c = train_config
        old_state = state = t.zeros([1, c.observe_dim])
        action = t.zeros([1, c.action_dim])
        ppo_vis.store_episode([
            {"state": {"state": old_state.clone()},
             "action": {"action": action.clone()},
             "next_state": {"state": state.clone()},
             "reward": 0,
             "terminal": False}
            for _ in range(3)
        ])
        ppo_vis.update(update_value=True, update_policy=True,
                       update_target=True, concatenate_samples=True)
        ppo_vis.entropy_weight = 1e-3
        ppo_vis.store_episode([
            {"state": {"state": old_state.clone()},
             "action": {"action": action.clone()},
             "next_state": {"state": state.clone()},
             "reward": 0,
             "terminal": False}
            for _ in range(3)
        ])
        ppo_vis.update(update_value=False, update_policy=False,
                       update_target=False, concatenate_samples=True)

    ########################################################################
    # Test for PPO save & load
    ########################################################################
    # Skipped, it is the same as A2C

    ########################################################################
    # Test for PPO lr_scheduler
    ########################################################################
    # Skipped, it is the same as A2C

    ########################################################################
    # Test for PPO full training.
    ########################################################################
    def test_full_train(self, train_config, ppo):
        c = train_config

        # begin training
        episode, step = Counter(), Counter()
        reward_fulfilled = Counter()
        smoother = Smooth()
        terminal = False

        env = c.env
        ppo.grad_max = 0.1
        while episode < c.max_episodes:
            episode.count()

            # batch size = 1
            total_reward = 0
            state = t.tensor(env.reset(), dtype=t.float32, device=c.device)

            tmp_observations = []
            while not terminal and step <= c.max_steps:
                step.count()
                with t.no_grad():
                    old_state = state
                    # agent model inference
                    action = ppo.act({"state": old_state.unsqueeze(0)})[0]
                    state, reward, terminal, _ = env.step(action.cpu().numpy())
                    state = t.tensor(state, dtype=t.float32, device=c.device) \
                        .flatten()
                    total_reward += float(reward)

                    tmp_observations.append({
                        "state": {"state": old_state.unsqueeze(0).clone()},
                        "action": {"action": action.clone()},
                        "next_state": {"state": state.unsqueeze(0).clone()},
                        "reward": float(reward),
                        "terminal": terminal or step == c.max_steps
                    })

            # update
            ppo.store_episode(tmp_observations)
            logger.info("{:.6f}, {:.0f}".format(*ppo.update()))

            smoother.update(total_reward)
            step.reset()
            terminal = False

            logger.info("Episode {} total reward={:.2f}"
                        .format(episode, smoother.value))

            if smoother.value > c.solved_reward:
                reward_fulfilled.count()
                if reward_fulfilled >= c.solved_repeat:
                    logger.info("Environment solved!")
                    return
            else:
                reward_fulfilled.reset()

        pytest.fail("PPO Training failed.")
from RacingDRL.Utils.utils import init_file_struct
from RacingDRL.LearningAlgorithms.create_agent import create_train_agent
import numpy as np
from RacingDRL.Planners.Architectures import ArchEndToEnd, ArchHybrid, ArchPathFollower
from RacingDRL.Utils.HistoryStructs import TrainHistory
from RacingDRL.Planners.RewardSignals import ProgressReward
from RacingDRL.Planners.StdTrack import StdTrack

class AgentTrainer: 
    def __init__(self, run, conf):
        self.run, self.conf = run, conf
        self.name = run.run_name
        self.path = conf.vehicle_path + run.path + run.run_name + "/"
        init_file_struct(self.path)

        self.v_min_plan =  conf.v_min_plan

        self.state = None
        self.nn_state = None
        self.nn_act = None
        self.action = None
        self.std_track = StdTrack(run.map_name)
        self.reward_generator = ProgressReward(self.std_track)

        if run.state_vector == "end_to_end":
            self.architecture = ArchEndToEnd(run, conf)

        self.agent = create_train_agent(run, self.architecture.state_space)
        self.t_his = TrainHistory(run, conf)

    def plan(self, obs):
        nn_state = self.architecture.transform_obs(obs)
        
        self.add_memory_entry(obs, nn_state)
        self.state = obs
            
        if obs['linear_vels_x'][0] < self.v_min_plan:
            self.action = np.array([0, 2])
            return self.action

        self.nn_state = nn_state 
        self.nn_act = self.agent.act(self.nn_state)
        self.action = self.architecture.transform_action(self.nn_act)
        
        self.agent.train()

        return self.action 

    def add_memory_entry(self, s_prime, nn_s_prime):
        if self.nn_state is not None:
            reward = self.reward_generator(s_prime, self.state)
            self.t_his.add_step_data(reward)

            self.agent.replay_buffer.add(self.nn_state, self.nn_act, nn_s_prime, reward, False)

    def done_callback(self, s_prime):
        """
        To be called when ep is done.
        """
        nn_s_prime = self.architecture.transform_obs(s_prime)
        reward = self.reward_generator(s_prime, self.state)
        progress = self.std_track.calculate_progress_percent([s_prime['poses_x'][0], s_prime['poses_y'][0]]) * 100
        
        # print(self.t_his.reward_list)
        self.t_his.lap_done(reward, progress, False)
        print(f"Episode: {self.t_his.ptr}, Step: {self.t_his.t_counter}, Lap p: {progress:.1f}%, Reward: {self.t_his.rewards[self.t_his.ptr-1]:.2f}")

        if self.nn_state is None:
            print(f"Crashed on first step: RETURNING")
            return
        
        self.agent.replay_buffer.add(self.nn_state, self.nn_act, nn_s_prime, reward, True)
        self.nn_state = None
        self.state = None

        self.save_training_data()

    def save_training_data(self):
        self.t_his.print_update(True)
        self.t_his.save_csv_data()
        self.agent.save(self.name, self.path)
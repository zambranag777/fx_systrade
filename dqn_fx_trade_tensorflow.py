# coding:utf-8
# [0]必要なライブラリのインポート

# this code based on code on https://qiita.com/sugulu/items/bc7c70e6658f204f85f9
# I am very grateful to work of Mr. Yutaro Ogawa (id: sugulu)

import gym  # 倒立振子(cartpole)の実行環境
import numpy as np
import time
from keras.models import Sequential, model_from_json
from keras.layers import Dense
from keras.optimizers import Adam
from keras.utils import plot_model
from collections import deque
from keras import backend as K
import tensorflow as tf
import pickle
from agent_fx_environment import FXEnvironment

# [1]損失関数の定義
# 損失関数にhuber関数を使用 参考https://github.com/jaara/AI-blog/blob/master/CartPole-DQN.py
def huberloss(y_true, y_pred):
    err = y_true - y_pred
    cond = K.abs(err) < 1.0
    L2 = 0.5 * K.square(err)
    L1 = (K.abs(err) - 0.5)
    loss = tf.where(cond, L2, L1)  # Keras does not cover where function in tensorflow :-(
    return K.mean(loss)


# [2]Q関数をディープラーニングのネットワークをクラスとして定義
class QNetwork:
    def __init__(self, learning_rate=0.01, state_size=15, action_size=3, hidden_size=10):
        self.model = Sequential()
        # TODO: 過去の為替予測のコードを参照して、一層足して、最終層以外にBatchNormalization
        #       と Dropout の 0.2 ぐらいを入れてみた方がよさそう。もしくはBatchNormalizationだけ。
        #       もしくは、層を足すだけにするか。
        self.model.add(Dense(hidden_size, activation='relu', input_dim=state_size))
        self.model.add(Dense(hidden_size, activation='relu'))
        self.model.add(Dense(action_size, activation='linear'))
        self.optimizer = Adam(lr=learning_rate)  # 誤差を減らす学習方法はAdam
        # self.model.compile(loss='mse', optimizer=self.optimizer)
        self.model.compile(loss=huberloss, optimizer=self.optimizer)

    # 重みの学習
    def replay(self, memory, batch_size, gamma, targetQN):
        inputs = np.zeros((batch_size, 15))
        targets = np.zeros((batch_size, 3))
        mini_batch = memory.sample(batch_size)

        for i, (state_b, action_b, reward_b, next_state_b) in enumerate(mini_batch):
            inputs[i:i + 1] = state_b
            target = reward_b

            if not (next_state_b == np.zeros(state_b.shape)).all(axis=1):
                # 価値計算（DDQNにも対応できるように、行動決定のQネットワークと価値観数のQネットワークは分離）
                retmainQs = self.model.predict(next_state_b)[0]
                next_action = np.argmax(retmainQs)  # 最大の報酬を返す行動を選択する
                target = reward_b + gamma * targetQN.model.predict(next_state_b)[0][next_action]

            targets[i] = self.model.predict(state_b)    # Qネットワークの出力
            targets[i][action_b] = target               # 教師信号

        self.model.fit(inputs, targets, epochs=1, verbose=0)  # epochsは訓練データの反復回数、verbose=0は表示なしの設定

    def save_model(self, file_path_prefix_str):
        with open("./" + file_path_prefix_str + "_nw.json", "w") as f:
            f.write(self.model.to_json())
        self.model.save_weights("./" + file_path_prefix_str + "_weights.hd5")

    def load_model(self, file_path_prefix_str):
        with open("./" + file_path_prefix_str + "_nw.json", "r") as f:
            self.model = model_from_json(f.read())
        self.model.load_weights("./" + file_path_prefix_str + "_weights.hd5")

# [3]Experience ReplayとFixed Target Q-Networkを実現するメモリクラス
class Memory:
    def __init__(self, max_size=1000):
        self.buffer = deque(maxlen=max_size)

    def add(self, experience):
        self.buffer.append(experience)

    def sample(self, batch_size):
        idx = np.random.choice(np.arange(len(self.buffer)), size=batch_size, replace=False)
        return [self.buffer[ii] for ii in idx]

    def len(self):
        return len(self.buffer)

    def save_memory(self, file_path_prefix_str):
        with open("./" + file_path_prefix_str + ".pickle", 'wb') as f:
            pickle.dump(self.buffer, f)

    def load_memory(self, file_path_prefix_str):
        with open("./" + file_path_prefix_str + ".pickle", 'rb') as f:
            self.buffer = pickle.load(f)

# [4]カートの状態に応じて、行動を決定するクラス
class Actor:
    def get_action(self, state, episode, mainQN):   # [C]ｔ＋１での行動を返す
        # 徐々に最適行動のみをとる、ε-greedy法
        epsilon = 0.001 + 0.9 / (1.0+(episode/100))

        if epsilon <= np.random.uniform(0, 1):
            retTargetQs = mainQN.model.predict(state)[0]
            action = np.argmax(retTargetQs)  # 最大の報酬を返す行動を選択する

        else:
            action = np.random.choice([0, 2])  # ランダムに行動する

        return action

# TODO: 学習済みのエージェントを回せるようにしないといけない
#        学習済みのQ関数等々を保存する方法が必要
# [5] メイン関数開始----------------------------------------------------
# [5.1] 初期設定--------------------------------------------------------
DQN_MODE = 0    # 1がDQN、0がDDQNです
TRAIN_DATA_NUM = 223954 # 3years (test is 5 years)
# ---
gamma = 0.99  # 割引係数
# TODO: 50ぐらいにしておきたい
hidden_size = 50  # 16               # Q-networkの隠れ層のニューロンの数
learning_rate = 0.0001  # 0.00001         # Q-networkの学習係数
memory_size = 1000000 #10000  # バッファーメモリの大きさ
batch_size = 32  # Q-networkを更新するバッチの大きさ

def tarin_agent():
    env_master = FXEnvironment()
    env = env_master.get_env('train')
    num_episodes = TRAIN_DATA_NUM + 10 # envがdoneを返すはずなので念のため多めに設定 #1000  # 総試行回数
    islearned = 0  # 学習が終わったフラグ

    # [5.2]Qネットワークとメモリ、Actorの生成--------------------------------------------------------
    mainQN = QNetwork(hidden_size=hidden_size, learning_rate=learning_rate)     # メインのQネットワーク
    targetQN = QNetwork(hidden_size=hidden_size, learning_rate=learning_rate)   # 価値を計算するQネットワーク
    # plot_model(mainQN.model, to_file='Qnetwork.png', show_shapes=True)        # Qネットワークの可視化
    memory = Memory(max_size=memory_size)
    actor = Actor()

    #state, reward, done, _ = env.step(env.action_space.sample())  # 1step目は適当な行動をとる
    state, reward, done = env.step(0)  # 1step目は適当な行動をとる ("HOLD")
    #state = np.reshape(state, [1, 4])  # list型のstateを、1行4列の行列に変換
    state = np.reshape(state, [1, 15])  # list型のstateを、1行15列の行列に変換

    # [5.3]メインルーチン--------------------------------------------------------
    for episode in range(num_episodes):  # 試行数分繰り返す
        # 行動決定と価値計算のQネットワークをおなじにする
        targetQN.model.set_weights(mainQN.model.get_weights())

        action = actor.get_action(state, episode, mainQN)   # 時刻tでの行動を決定する
        next_state, reward, done = env.step(action)   # 行動a_tの実行による、s_{t+1}, _R{t}を計算する
        #next_state = np.reshape(next_state, [1, 4])     # list型のstateを、1行4列の行列に変換
        next_state = np.reshape(state, [1, 15])  # list型のstateを、1行15列の行列に変換

        memory.add((state, action, reward, next_state))     # メモリを更新する
        state = next_state  # 状態更新

        # Qネットワークの重みを学習・更新する replay
        if (memory.len() > batch_size) and not islearned:
            mainQN.replay(memory, batch_size, gamma, targetQN)

        if DQN_MODE:
            # 行動決定と価値計算のQネットワークをおなじにする
            targetQN.model.set_weights(mainQN.model.get_weights())

        # 環境が提供する期間が最後までいった場合
        if done:
            print('all training period learned.')
            break

        # モデルとメモリのスナップショットをとっておく
        if(episode % 10000 == 0):
            targetQN.save_model("targetQN")
            mainQN.save_model("mainQN")
            memory.save_memory("memory")

if __name__ == '__main__':
    tarin_agent()
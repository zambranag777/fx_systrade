# coding:utf-8
import numpy as np
import scipy.sparse
import pickle
import talib as ta
from datetime import datetime as dt
import pytz
import os
import sys
import sklearn
import time
from sklearn.preprocessing import StandardScaler

class FXEnvironment:
    def __init__(self):
        print("FXEnvironment class constructor called.")
        self.INPUT_LEN = 1
        self.SLIDE_IDX_NUM_AT_GEN_INPUTS_AND_COLLECT_LABELS = 1 #5
        self.PREDICT_FUTURE_LEGS = 5
        self.COMPETITION_DIV = True
        self.COMPETITION_TRAIN_DATA_NUM = 223954 # 3years (test is 5 years)

        self.TRAINDATA_DIV = 2
        self.CHART_TYPE_JDG_LEN = 25

        self.VALIDATION_DATA_RATIO = 1.0 # rates of validation data to (all data - train data)
        self.DATA_HEAD_ASOBI = 200

        #self.FEATURE_NAMES = ["current_rate", "diff_ratio_between_previous_rate", "rsi", "ma", "ma_kairi", "bb_1", "bb_2", "ema", "cci", "mo","vorariity", "macd", "chart_type"]
        self.FEATURE_NAMES = ["current_rate", "diff_ratio_between_previous_rate", "rsi", "ma", "ma_kairi", "bb_1",
                              "bb_2", "cci", "mo", "vorariity"]
        self.tr_input_arr = None
        self.tr_angle_arr = None
        self.val_input_arr = None
        self.val_angle_arr = None

        self.exchange_dates = None
        self.exchange_rates = None
        self.reverse_exchange_rates = None

        self.setup_serialized_fx_data()

    def preprocess_data(self, X):
        scaler = StandardScaler()
        scaler.fit(X)

        X_T = scaler.transform(X)
        return X_T, scaler

    # 0->flat 1->upper line 2-> downer line 3->above is top 4->below is top
    def judge_chart_type(self, data_arr):
        max_val = 0
        min_val = float("inf")

        last_idx = len(data_arr)-1

        for idx in range(len(data_arr)):
            if data_arr[idx] > max_val:
                max_val = data_arr[idx]
                max_idx = idx

            if data_arr[idx] < min_val:
                min_val = data_arr[idx]
                min_idx = idx


        if max_val == min_val:
            return 0

        if min_idx == 0 and max_idx == last_idx:
            return 1

        if max_idx == 0 and min_idx == last_idx:
            return 2

        if max_idx != 0 and max_idx != last_idx and min_idx != 0 and min_idx != last_idx:
            return 0

        if max_idx != 0 and max_idx != last_idx:
            return 3

        if min_idx != 0 and min_idx != last_idx:
            return 4

        return 0

    def get_rsi(self, price_arr, cur_pos, period = 40):
        if cur_pos <= period:
    #        s = 0
            return 0
        else:
            s = cur_pos - (period + 1)
        tmp_arr = price_arr[s:cur_pos]
        tmp_arr.reverse()
        prices = np.array(tmp_arr, dtype=float)

        return ta.RSI(prices, timeperiod = period)[-1]

    def get_ma(self, price_arr, cur_pos, period = 20):
        if cur_pos <= period:
            s = 0
        else:
            s = cur_pos - period
        tmp_arr = price_arr[s:cur_pos]
        tmp_arr.reverse()
        prices = np.array(tmp_arr, dtype=float)

        return ta.SMA(prices, timeperiod = period)[-1]

    def get_ma_kairi(self, price_arr, cur_pos, period = None):
        ma = self.get_ma(price_arr, cur_pos)
        return ((price_arr[cur_pos] - ma) / ma) * 100.0
        return 0

    def get_bb_1(self, price_arr, cur_pos, period = 40):
        if cur_pos <= period:
            s = 0
        else:
            s = cur_pos - period
        tmp_arr = price_arr[s:cur_pos]
        tmp_arr.reverse()
        prices = np.array(tmp_arr, dtype=float)

        return ta.BBANDS(prices, timeperiod = period)[0][-1]

    def get_bb_2(self, price_arr, cur_pos, period = 40):
        if cur_pos <= period:
            s = 0
        else:
            s = cur_pos - period
        tmp_arr = price_arr[s:cur_pos]
        tmp_arr.reverse()
        prices = np.array(tmp_arr, dtype=float)

        return ta.BBANDS(prices, timeperiod = period)[2][-1]

    def get_ema(self, price_arr, cur_pos, period = 20):
        if cur_pos <= period:
            s = 0
        else:
            s = cur_pos - period
        tmp_arr = price_arr[s:cur_pos]
        tmp_arr.reverse()
        prices = np.array(tmp_arr, dtype=float)

        return ta.EMA(prices, timeperiod = period)[-1]


    # def get_ema_rsi(price_arr, cur_pos, period = None):
    #     return 0

    def get_cci(self, price_arr, cur_pos, period = None):
        return 0

    def get_mo(self, price_arr, cur_pos, period = 20):
        if cur_pos <= (period + 1):
    #        s = 0
            return 0
        else:
            s = cur_pos - (period + 1)
        tmp_arr = price_arr[s:cur_pos]
        tmp_arr.reverse()
        prices = np.array(tmp_arr, dtype=float)

        return ta.CMO(prices, timeperiod = period)[-1]

    def get_po(self, price_arr, cur_pos, period = 10):
        if cur_pos <= period:
            s = 0
        else:
            s = cur_pos - period
        tmp_arr = price_arr[s:cur_pos]
        tmp_arr.reverse()
        prices = np.array(tmp_arr, dtype=float)

        return ta.PPO(prices)[-1]

    def get_vorarity(self, price_arr, cur_pos, period = None):
        tmp_arr = []
        prev = -1.0
        for val in price_arr[cur_pos-self.CHART_TYPE_JDG_LEN:cur_pos]:
            if prev == -1.0:
                tmp_arr.append(0.0)
            else:
                tmp_arr.append(val - prev)
            prev = val

        return np.std(tmp_arr)

    def get_macd(self, price_arr, cur_pos, period = 100):
        if cur_pos <= period:
            s = 0
        else:
            s = cur_pos - period
        tmp_arr = price_arr[s:cur_pos]
        tmp_arr.reverse()
        prices = np.array(tmp_arr, dtype=float)

        macd, macdsignal, macdhist = ta.MACD(prices,fastperiod=12, slowperiod=26, signalperiod=9)
        if macd[-1] > macdsignal[-1]:
            return 1
        else:
            return 0

    # 日本時間で土曜7:00-月曜7:00までは取引不可として元データから取り除く
    # なお、本来は月曜朝5:00から取引できるのが一般的なようである
    def is_weekend(self, date_str):
        tz = pytz.timezone('Asia/Tokyo')
        dstr = date_str.replace(".","-")
        tdatetime = dt.strptime(dstr, '%Y-%m-%d %H:%M:%S')
        tz_time = tz.localize(tdatetime)
        gmt_plus2_tz = pytz.timezone('Etc/GMT+2')
        gmt_plus2_time = tz_time.astimezone(gmt_plus2_tz)
        week = gmt_plus2_time.weekday()
        return (week == 5 or week == 6)

    def logfile_writeln_with_fd(self, out_fd, log_str):
        out_fd.write(log_str + "\n")
        out_fd.flush()

    def make_serialized_data(self, start_idx, end_idx, step, x_arr_fpath, y_arr_fpath):
        input_mat = []
        angle_mat = []
        train_end_idx = -1
        print("all rate and data size: " + str(len(self.exchange_rates)))
        for i in range(start_idx, end_idx, step):
            if self.exchange_dates[i] == "2003-12-31 23:55:00":
                train_end_idx = i
            if i % 2000:
                print("current date idx: " + str(i))
            input_mat.append(
                [self.exchange_rates[i],
                 (self.exchange_rates[i] - self.exchange_rates[i - 1]) / self.exchange_rates[i - 1],
                 self.get_rsi(self.exchange_rates, i),
                 self.get_ma(self.exchange_rates, i),
                 self.get_ma_kairi(self.exchange_rates, i),
                 self.get_bb_1(self.exchange_rates, i),
                 self.get_bb_2(self.exchange_rates, i),
                 #self.get_ema(self.exchange_rates, i),
                 self.get_cci(self.exchange_rates, i),
                 self.get_mo(self.exchange_rates, i),
                 self.get_vorarity(self.exchange_rates, i)#,
                 #self.get_macd(self.exchange_rates, i),
                 #self.judge_chart_type(self.exchange_rates[i - self.CHART_TYPE_JDG_LEN:i])
                 ]
            )

            if y_arr_fpath != None:
                tmp = self.exchange_rates[i + self.PREDICT_FUTURE_LEGS] - self.exchange_rates[i]
                angle_mat.append(tmp)

        input_mat = np.array(input_mat, dtype=np.float64)
        input_mat, _ = self.preprocess_data(input_mat)
        with open(x_arr_fpath, 'wb') as f:
            pickle.dump(input_mat, f)
        with open(y_arr_fpath, 'wb') as f:
            pickle.dump(angle_mat, f)
        print("test data end index: " + str(train_end_idx))

        return input_mat, angle_mat

    def setup_serialized_fx_data(self):
        self.exchange_dates = []
        self.exchange_rates = []

        if os.path.exists("./exchange_rates.pickle"):
            with open("./exchange_dates.pickle", 'rb') as f:
                self.exchange_dates = pickle.load(f)
            with open("./exchange_rates.pickle", 'rb') as f:
                self.exchange_rates = pickle.load(f)
        else:
            rates_fd = open('./USD_JPY_2001_2008_5min.csv', 'r')
            for line in rates_fd:
                splited = line.split(",")
                if splited[2] != "High" and splited[0] != "<DTYYYYMMDD>" and splited[0] != "204/04/26" and splited[
                    0] != "20004/04/26" and self.is_weekend(splited[0]) == False:
                    time = splited[0].replace("/", "-")  # + " " + splited[1]
                    val = float(splited[1])
                    self.exchange_dates.append(time)
                    self.exchange_rates.append(val)
            with open("./exchange_rates.pickle", 'wb') as f:
                pickle.dump(self.exchange_rates, f)
            with open("./exchange_dates.pickle", 'wb') as f:
                pickle.dump(self.exchange_dates, f)

        if os.path.exists("./all_input_mat.pickle"):
            with open('./all_input_mat.pickle', 'rb') as f:
                all_input_mat = pickle.load(f)
            with open('./all_angle_mat.pickle', 'rb') as f:
                all_angle_mat = pickle.load(f)
        else:
            all_input_mat, all_angle_mat = \
                self.make_serialized_data(self.DATA_HEAD_ASOBI, len(self.exchange_rates) - self.DATA_HEAD_ASOBI - self.PREDICT_FUTURE_LEGS, self.SLIDE_IDX_NUM_AT_GEN_INPUTS_AND_COLLECT_LABELS, './all_input_mat.pickle', './all_angle_mat.pickle')

        self.tr_input_arr = all_input_mat[0:self.COMPETITION_TRAIN_DATA_NUM]
        self.tr_angle_arr = all_angle_mat[0:self.COMPETITION_TRAIN_DATA_NUM]
        self.ts_input_arr = all_input_mat[self.COMPETITION_TRAIN_DATA_NUM:]

        print("data size of all rates for train and test: " + str(len(self.exchange_rates)))
        print("num of rate datas for tarin: " + str(self.COMPETITION_TRAIN_DATA_NUM))
        print("input features sets for tarin: " + str(self.COMPETITION_TRAIN_DATA_NUM))
        print("input features sets for test: " + str(len(self.ts_input_arr)))
        print("finished setup environment data.")

    # type_str: "train", "test"
    def get_env(self, type_str):
        if(type_str == "backtest"):
            return self.InnerFXEnvironment(self.tr_input_arr, self.exchange_dates, self.exchange_rates,
                                           self.DATA_HEAD_ASOBI, idx_step=self.PREDICT_FUTURE_LEGS,
                                           angle_arr=self.tr_angle_arr, is_backtest=True)
        else:
            return self.InnerFXEnvironment(self.tr_input_arr, self.exchange_dates, self.exchange_rates, self.DATA_HEAD_ASOBI, idx_step = 1, angle_arr=self.tr_angle_arr, is_backtest=False)

    # TODO: 任意の数のポジションを扱えるようにする、売買および決済を関数にまとめる
    class InnerFXEnvironment:
        def __init__(self, input_arr, exchange_dates, exchange_rates, idx_geta, idx_step=5, angle_arr = None, half_spred=0.0015, holdable_positions=100, is_backtest=False):
            self.input_arr = input_arr
            self.angle_arr = angle_arr
            self.exchange_dates = exchange_dates
            self.exchange_rates = exchange_rates
            self.half_spread = half_spred
            self.cur_idx = 0
            self.idx_geta = idx_geta
            self.log_fd_bt = open("./backtest_log_" + dt.now().strftime("%Y-%m-%d_%H-%M-%S") + ".txt", mode = "w")
            self.start = time.time()
            self.idx_step = idx_step
            self.idx_real_step = 1
            self.is_backtest = is_backtest

            self.done = False

            # self.portfolio = 1000000.0
            # self.won_pips = 0
            # self.NOT_HAVE = 0
            # self.LONG = 1
            # self.SHORT = 2
            # self.pos_kind = self.NOT_HAVE
            # self.trade_val = 0
            # self.positions = 0

            self.positions_identifiers = []

            self.portfolio_mngr = PortforioManager(exchange_rates, half_spred, holdable_positions)
            if(is_backtest):
                self.idx_real_step = 5

        def get_unixtime_str(self):
            return str(time.time())

        def logfile_writeln_bt(self, log_str):
            self.log_fd_bt.write(log_str + "\n")
            self.log_fd_bt.flush()

        def step(self, action_num):
            reward = 0

            action = -1
            if action_num == 0:
                action = "BUY"
            elif action_num == 1:
                action = "CLOSE"
            elif action_num == 2:
                 action = "DONOT"
            else:
                raise Exception(str(action_num) + " is invalid.")

            a_log_str_line = "log," + str(self.cur_idx) + "," + action
            additional_infos = []

            if action == "BUY":
                # 定められた本数の先の足で利益がでるか出ないか
                #reward = 1 if self.angle_arr[self.idx_geta + self.cur_idx] > 0 else -1

                reward = 0
                if self.portfolio_mngr.additional_pos_openable():
                    buy_val = self.portfolio_mngr.buy(self.idx_geta + self.cur_idx)
                    self.positions_identifiers.append(self.get_unixtime_str())
                    a_log_str_line += ",OPEN_LONG" + ",0,0," + str(
                    self.exchange_rates[self.idx_geta + self.cur_idx]) + "," + str(buy_val)
                else: #もうオープンできない
                    a_log_str_line += ",POSITION_HOLD,0," + str(self.portfolio_mngr.get_evaluated_val_diff_of_all_pos()) + "," + str(
                    self.exchange_rates[self.idx_geta + self.cur_idx]) + ",0"
            elif action == "CLOSE":
                if len(self.positions_identifiers) > 0: # ポジションを持っている場合
                    won_pips, won_money = self.portfolio_mngr.close_all()
                    a_log_str_line += ",CLOSE_LONG" + "," + str(won_money) + "," + str(
                    won_pips) + "," + str(self.exchange_rates[self.idx_geta + self.cur_idx]) + ",0"
                    additional_infos = self.positions_identifiers
                    self.positions_identifiers = []
                    reward = won_pips
                else:
                    a_log_str_line += ",KEEP_NO_POSITION,0,0,0,0"
                    reward = 0
            elif action == "DONOT":
                reward = 0

                if len(self.positions_identifiers) > 0:
                    a_log_str_line += ",POSITION_HOLD_LONG,0," + str(self.portfolio_mngr.get_evaluated_val_diff_of_all_pos()) + "," + str(
                        self.exchange_rates[self.idx_geta + self.cur_idx]) + ",0"
                else:
                    a_log_str_line += ",KEEP_NO_POSITION,0,0,0,0"

            else:
                raise Exception(str(action) + " is invalid.")

            a_log_str_line += "," + str(self.portfolio_mngr.get_current_portfolio()) + "," + str(self.portfolio_mngr.won_pips) + "," + str(len(self.positions_identifiers))
            self.logfile_writeln_bt(a_log_str_line)

            self.cur_idx += self.idx_real_step #self.idx_step
            if (self.idx_geta + self.cur_idx) >= len(self.input_arr):
                self.logfile_writeln_bt("finished backtest.")
                print("finished backtest.")
                process_time = time.time() - self.start
                self.logfile_writeln_bt("excecution time of backtest: " + str(process_time))
                self.logfile_writeln_bt("result of portfolio: " + str(self.portfolio))
                print("result of portfolio: " + str(self.portfolio))
                self.log_fd_bt.flush()
                self.log_fd_bt.close()
                return None, reward, True
            else:
                valuated_diff = self.portfolio_mngr.get_evaluated_val_diff_of_all_pos()
                has_position = 1 if valuated_diff == 0 else 1

                next_state = self.input_arr[self.cur_idx] + [valuated_diff] #+ [has_position] + [pos_cur_val] + [action_num]
                # 第四返り値はエピソードの識別子を格納するリスト. 第0要素は返却する要素に対応するもので、
                # それ以外の要素がある場合は、close時にさかのぼって エピソードのrewardを更新するためのもの
                return next_state, reward, False, [self.get_unixtime_str()] + additional_infos

class PortforioManager:

    def __init__(self, exchange_rates, half_spred=0.0015, holdable_positions = 100, is_backtest=False):
        self.exchange_rates = exchange_rates
        self.half_spread = half_spred
        self.is_backtest = is_backtest

        self.portfolio = 1000000.0
        self.won_pips = 0
        self.NOT_HAVE = 0
        self.LONG = 1
        self.SHORT = 2
        self.pos_kind = self.NOT_HAVE
        self.trade_val = 0
        self.positions = 0

    # TODO: not implemented yet
    def additional_pos_openable(self):
        return "True or False"

    # TODO: not implment yet
    def buy(self, rate_idx):
        # ロングポジションを購入する
        self.pos_kind = self.LONG
        self.positions = float(self.portfolio) / float(
                (self.exchange_rates[self.idx_geta + self.cur_idx] + self.half_spread))
        self.trade_val = self.exchange_rates[self.idx_geta + self.cur_idx] + self.half_spread
        return "bough price includes spread"

    # def sell(self, rate_idx):
    #     # ショートポジションを購入する
    #     self.pos_kind = self.SHORT
    #     self.positions = self.portfolio / (self.exchange_rates[self.idx_geta + self.cur_idx] - self.half_spread)
    #     self.trade_val = self.exchange_rates[self.idx_geta + self.cur_idx] - self.half_spread
    #     return "bough price includes spread"

    # TODO: not implemented yet
    def close_all(self):
        # if self.pos_kind == self.SHORT:
        #     # 保持しているショートポジションをクローズする
        #     cur_price = self.exchange_rates[self.idx_geta + self.cur_idx] + self.half_spread
        #     trade_result = self.positions * self.trade_val - self.positions * cur_price
        #     self.portfolio = self.portfolio + trade_result
        #     won_pips_diff = self.trade_val - (self.exchange_rates[self.idx_geta + self.cur_idx] + self.half_spread)
        #     self.won_pips += won_pips_diff
        #     self.pos_kind = self.NOT_HAVE
        #     self.positions = 0
        #
        #     a_log_str_line += ",CLOSE_SHORT" + "," + str(trade_result) + "," + str(won_pips_diff) + "," + str(
        #         cur_price) + "," + str(self.trade_val)
        #     reward = won_pips_diff
        if self.pos_kind == self.LONG:
            # 保持しているロングポジションをクローズする
            cur_price = self.exchange_rates[self.idx_geta + self.cur_idx] - self.half_spread
            trade_result = self.positions * cur_price - self.positions * self.trade_val
            won_pips_diff = (self.exchange_rates[
                                 self.idx_geta + self.cur_idx] - self.half_spread) - self.trade_val
            if won_pips_diff <= 0:
                trade_result = 0
                won_pips_diff = 0
                a_log_str_line += ",THROUGH_MINUS_GAIN" + "," + str(trade_result) + "," + str(
                    won_pips_diff) + "," + str(cur_price) + "," + str(self.trade_val)
                reward = won_pips_diff
            else:
                self.portfolio = self.portfolio + trade_result
                self.won_pips += won_pips_diff
                self.pos_kind = self.NOT_HAVE
                self.positions = 0
                a_log_str_line += ",CLOSE_LONG" + "," + str(trade_result) + "," + str(
                    won_pips_diff) + "," + str(cur_price) + "," + str(self.trade_val)
                reward = won_pips_diff

        return "total get pips", "total get money"

    def get_evaluated_val_diff_of_all_pos(self):
        return "evaluated pips"

    def get_current_portfolio(self):
        return "porfolio includes position valuation"

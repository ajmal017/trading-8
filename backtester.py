# build-in

# 3rd party
import numpy as np
import pandas as pd

# custom
from gpw_data import GPWData


def get_strategy_signals(symbol):
    data = GPWData()
    etf_full = data.load(symbols=symbol)

    # strategy params (should come as params but hardcoded here for simplicity)
    time_window=3
    long_threshold=35
    short_threshold=30

    # split data into optimize/validate
    length = len(etf_full.index)
    etf_t = etf_full.iloc[:length//2, :].copy()
    etf_v = etf_full.iloc[length//2:, :].copy()
    
    # calculate signals
    for etf in (etf_t, etf_v):
        for price in ('high', 'low', 'close'):
            etf.loc[:, 'ema_{}_{}'.format(time_window, price)] = etf[price].ewm(span=time_window, adjust=False).mean()
        etf.loc[:, 'adr'] = etf['ema_{}_high'.format(time_window)] - etf['ema_{}_low'.format(time_window)]
        etf.loc[:, 'perc_range'] = \
            ((etf['ema_{}_high'.format(time_window)]-etf['ema_{}_close'.format(time_window)])*100)/etf['adr']
        
        for signal_type in ('long', 'short'):
            if signal_type == 'long':
                etf.loc[:, 'potential_signal'] = np.where(etf['perc_range'] > long_threshold, 1, 0)
            elif signal_type == 'short':
                etf.loc[:, 'potential_signal'] = np.where(etf['perc_range'] < short_threshold, 1, 0)
            etf.loc[:, 'previous_potential_signal'] = etf['potential_signal'].shift(1)
            etf['previous_potential_signal'].fillna(value=0, inplace=True)
            etf.loc[:, 'entry_{}'.format(signal_type)] = np.where(
                (etf['potential_signal']==1) & (etf['previous_potential_signal']==0), 1, 0
            )
            etf.loc[:, 'exit_{}'.format(signal_type)] = np.where(
                (etf['potential_signal']==0) & (etf['previous_potential_signal']==1), 1, 0
            )
            etf.drop(['potential_signal', 'previous_potential_signal'], axis=1, inplace=True)

    return etf_t, etf_v



class Backtester():
    def __init__(self, signals, price_label='close', init_capital=10000):
        """
        *signals* - dictionary with symbols (key) and dataframes (values) with pricing data and enter/exit signals. 
        Column names for signals  are expected to be: entry_long, exit_long, entry_short, exit_short. Signals should 
        be bianries (0,1). If strategy is long/short only just insert 0 for the column.

        *price_label* - column name for the price which should be used in backtest
        """
        self.signals = self._prepare_signal(signals)
        self.price_label = price_label
        self.init_capital = init_capital

        # those will most probably be taken out to risk component
        self.fee_perc = 0.0038  # 0.38%
        self.min_fee = 4  # 4 PLN

    def buying_decisions(self, purchease_candidates):
        """
        Decides how much and of which shares to buy.

        Currently no complex decision making. Just buy as much as you can
        for the first encountered candidate from purchease_candidates.
        """
        symbols_to_buy = []
        available_money_at_time = self._available_money*1.0  #  multp. to create new obj.
        for candidate in purchease_candidates:
            price = candidate['price']
            shares_count = available_money_at_time // (price + (price*self.fee_perc))
            if shares_count == 0:
                continue
            trx_value = shares_count*price
            expected_fee = self.calculate_fee(trx_value)
            symbols_to_buy.append({
                'symbol': candidate['symbol'],
                'entry_type': candidate['entry_type'],
                'shares_count': shares_count,
                'price': price,
                'trx_value': trx_value,
                'fee': expected_fee,
            })
            available_money_at_time -= (trx_value+expected_fee)
        return symbols_to_buy

    def calculate_fee(self, transaction_value):
        """Calculates expected transaction fee."""
        fee = transaction_value * self.fee_perc
        if fee < self.min_fee:
            fee = self.min_fee
        return round(fee, 2)

    def run(self, test_days=None):
        self._reset_backtest_state()

        symbols_in_day = {}
        for sym_n, sym_v in self.signals.items():
            for ds in sym_v[self.price_label].keys():
                if ds in symbols_in_day:
                    symbols_in_day[ds].append(sym_n)
                else:
                    symbols_in_day[ds] = [sym_n]
        days = sorted(symbols_in_day.keys())
        
        if test_days:
            days = days[:test_days]

        for ds in days:
            # print('in {}, following symbols are available: {}'.format(str(ds), symbols_in_day[ds]))

            owned_shares = list(self._owned_shares.keys())
            for symbol in owned_shares:
                if self.signals[symbol]['exit_long'][ds] == 1:
                    # print('exit long signal for: ', symbol)
                    self._sell(symbol, 'long', self.signals[symbol][self.price_label], ds)
                elif self.signals[symbol]['exit_short'][ds] == 1:
                    # print('exit short signal for: ', symbol)
                    self._sell(symbol, 'short', self.signals[symbol][self.price_label], ds)

            purchease_candidates = []
            for sym in symbols_in_day[ds]:
                if self.signals[sym]['entry_long'][ds] == 1:
                    purchease_candidates.append(self._define_candidate(sym, ds, 'long'))
                elif self.signals[sym]['entry_short'][ds] == 1:
                    purchease_candidates.append(self._define_candidate(sym, ds, 'short'))

            # print('     there are following candidates to buy: ', purchease_candidates)

            symbols_to_buy = self.buying_decisions(purchease_candidates)

            for trx_details in symbols_to_buy:
                self._buy(trx_details, ds)

            self._summarize_day(ds)

            # print('-> NAV after session({}) is : {}'.format(ds, self._net_account_value[ds]))

        return self._run_output(), self._trades

    def _prepare_signal(self, signals):
        """Converts to expected dictionary form."""
        for k, v in signals.items():
            signals[k] = v.to_dict()
        return signals

    def _reset_backtest_state(self):
        """Resets all attributes used during backtest run."""
        self._owned_shares = {}
        self._available_money = self.init_capital
        self._trades = {}
        self._account_value = {}
        self._net_account_value = {}
        self._rate_of_return = {}
        # I'll calcualte daily returns later. its easier when I have df as I;ll be able to just shift
        # To find the return 𝑅(𝑡1,𝑡2) between dates 𝑡1 and 𝑡2 one takes 𝑅(𝑡1,𝑡2)=𝑁𝐴𝑉(𝑡2)/𝑁𝐴𝑉(𝑡1)−1

    def _sell(self, symbol, exit_type, prices, ds):
        """Selling procedure"""
        price = prices[ds]
        shares_count = self._owned_shares[symbol]['cnt']
        fee = self.calculate_fee(shares_count*price)
        # print('          selling. fee is: ', fee)
        trx_value = (shares_count*price)
        if exit_type == 'long':
            trx_value_gross = trx_value - fee
        elif exit_type == 'short':
            trx_value_gross = trx_value + fee
        
        self._available_money += trx_value_gross

        # print('available money after sell: ', self._available_money)
        
        self._trades[self._owned_shares[symbol]['trx_id']].update({
            'sell_ds': ds,
            'sell_value_no_fee': trx_value,
            'sell_value_gross': trx_value_gross,
            # holding days
        })
        self._owned_shares.pop(symbol)

    def _buy(self, trx, ds):
        """Buying procedure"""
        trx_id = '_'.join((str(ds)[:10], trx['symbol'], trx['entry_type']))
        
        if trx['entry_type'] == 'long':
            trx_value_gross = trx['trx_value'] + trx['fee']
            self._owned_shares[trx['symbol']] = {'cnt': trx['shares_count']}
            self._available_money -= trx_value_gross
                    
        elif trx['entry_type'] == 'short':
            trx_value_gross = trx['trx_value'] - trx['fee']
            self._owned_shares[trx['symbol']] = {'cnt': -trx['shares_count']}
            self._available_money += trx_value_gross

        self._owned_shares[trx['symbol']]['trx_id'] = trx_id
        self._trades[trx_id] = {
            'buy_ds': ds,
            'type': trx['entry_type'],
            'trx_value_no_fee': trx['trx_value'],
            'trx_value_gross': trx_value_gross,
        }

        # print('entered trade: [{}]. Details: {}. No. shares after trx: {}'.format(
        #     trx_id,
        #     self._trades[trx_id],
        #     self._owned_shares[trx['symbol']],
        #     )
        # )

    def _define_candidate(self, symbol, ds, entry_type):
        """Reutrns dictionary with purchease candidates and necessery keys."""
        return {
            'symbol': symbol,
            'entry_type': entry_type,
            'price': self.signals[symbol][self.price_label][ds]
        }

    def _summarize_day(self, ds):
        """Sets up summaries after finished session day."""
        _account_value = 0
        for symbol, vals in self._owned_shares.items():
            _account_value += vals['cnt'] * self.signals[symbol][self.price_label][ds]
        nav = _account_value + self._available_money
        self._account_value[ds] = _account_value
        self._net_account_value[ds] = nav
        self._rate_of_return[ds] = ((nav-self.init_capital)/self.init_capital)*100

    def _run_output(self):
        """
        Aggregates results from backtester run and outputs it as a DataFrame
        """
        df = pd.DataFrame()
        idx = list(self._account_value.keys())
        results = (
            (self._account_value, 'account_value'),
            (self._net_account_value, 'nav'),
            (self._rate_of_return, 'rate_of_return')
        )
        for d, col in results:
            temp_df = pd.DataFrame(list(d.items()), index=idx, columns=['ds', col])
            temp_df.drop('ds', axis=1, inplace=True)
            df = pd.concat([df, temp_df], axis=1)
        return df


def main():
    sn1, sn2 = 'ETFW20L', 'ETFSP500'
    stock_1_test, stock_1_val = get_strategy_signals(sn1)
    stock_2_test, stock_2_val = get_strategy_signals(sn2)

    tdays = 15

    signals = {
        sn1: stock_1_test,
        sn2: stock_2_test,
    }

    print(signals['ETFW20L'].head(tdays))

    backtester = Backtester(signals)
    results, trades = backtester.run(test_days=tdays)

    print('\nFirst 5 results are: ', results.head(5))

    # print(pd.DataFrame(backtester.signals['ETFW20L']).head(5))
    # ttt = pd.DataFrame(backtester.signals['ETFW20L']).head(5)
    # edf = pd.DataFrame()
    # xxx = pd.concat([ttt, edf], axis=1)
    # print(xxx)



if __name__ == '__main__':
    main()


"""
TODOs
- implement all the missing backtester.run components:
    OK + buy
    OK + sell
    OK + summarize day
    + logging

- implement evaluation of the results (may be as a separate object)
- test your previous strategy (if gives same results)
- figure out how to change "buying_decisions" so that you can plug any logic to determine what and how much to buy
- test you previous strategy based on different buying_decisions settings

- clean code, enhence logging, write tests
"""
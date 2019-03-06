# 3rd party
import pandas as pd
import pytest

# custom
from position_size import MaxFirstEncountered
from backtester import Backtester


def signals_test_sigs_1():
    """
    Creates signals with one symbol 'TEST_SIGS_1' and following data:
    date           close    entry_long  exit_long  entry_short  exit_short
    2010-09-28       100         1          0            0           0
    2010-09-29       120         0          1            0           0
    2010-09-30        90         0          1            1           0
    2010-10-01        80         0          0            0           1
    """
    dates = ['2010-09-28', '2010-09-29', '2010-09-30', '2010-10-01']
    signals_data = {
        'close': [100, 210, 90, 80],
        'entry_long': [1,0,0,0],
        'exit_long': [0,1,0,0],
        'entry_short': [0,0,1,0],
        'exit_short': [0,0,0,1],
    }
    return {'TEST_SIGS_1': pd.DataFrame(signals_data, index=pd.DatetimeIndex(dates))}

def signals_test_sigs_2():
    """
    Creates signals with 2 symbols 'TEST_SIGS_1' and following data:
    {
    'TEST_SIGS_1':
    date           close    entry_long  exit_long  entry_short  exit_short
    2010-09-28       230         1          0            0           0
    2010-09-29       233         0          1            0           0
    2010-09-30       235         0          1            1           0
    2010-10-01       237         0          0            0           1

    'TEST_SIGS_2':
    date           close    entry_long  exit_long  entry_short  exit_short
    2010-09-28       300         1          0            0           0
    2010-09-29       280         0          1            1           0
    2010-09-30       390         1          0            0           1
    2010-10-01       340         0          1            0           0
    }
    """
    dates = ['2010-09-28', '2010-09-29', '2010-09-30', '2010-10-01']
    s1_data = {
        'close': [230, 233, 235, 237],
        'entry_long': [1,0,0,0],
        'exit_long': [0,1,0,0],
        'entry_short': [0,0,1,0],
        'exit_short': [0,0,0,1],
    }
    s2_data = {
        'close': [300, 280, 390, 340],
        'entry_long': [1,0,0,0],
        'exit_long': [0,1,0,0],
        'entry_short': [0,0,1,0],
        'exit_short': [0,0,0,1],
    }

    return {
        'TEST_SIGS_1': pd.DataFrame(s1_data, index=pd.DatetimeIndex(dates)),
        'TEST_SIGS_1': pd.DataFrame(s2_data, index=pd.DatetimeIndex(dates))
    }


def max_first_encountered_alpha_sizer():
    """
    Returns MaxFirstEncountered position sizer with alphabetical sorting. That position sizer will decide
    to buy maximum amount of shares of first encountered cadidate (processing cadidates in alphabetical order)
    """
    return MaxFirstEncountered(sort_type='alphabetically')


@pytest.fixture(params=['signals', 'position_sizer', 'init_capital'])
def backtester(request):
    """
    Creates backtester object with given signals, position_sizer and initial capital
    """
    return Backtester(
        request.param[0], 
        position_sizer=request.param[1],
        init_capital=request.param[2],
    )


@pytest.mark.parametrize('backtester', [(signals_test_sigs_1(), max_first_encountered_alpha_sizer(), 500)], indirect=True)
def test_functional_backtester_1day_TEST_SIGS_1(backtester):
    expected_available_money = 96
    expected_account_value = 400
    expected_nav = 496
    expected_owned_shares = {
        'TEST_SIGS_1': {
            'cnt': 4.0,
            'trx_id': '2010-09-28_TEST_SIGS_1_long'
        }
    }
    backtester.run(test_days=1)
    ds_key = pd.Timestamp('2010-09-28')
    assert(backtester._available_money == expected_available_money)
    assert(backtester._account_value[ds_key] == expected_account_value)
    assert(backtester._net_account_value[ds_key] == expected_nav)
    assert(backtester._owned_shares == expected_owned_shares)


@pytest.mark.parametrize('backtester', [(signals_test_sigs_1(), max_first_encountered_alpha_sizer(), 500)], indirect=True)
def test_functional_backtester_2days_TEST_SIGS_1(backtester):
    expected_available_money = 932  # 96 + ((4*210)-4)
    expected_account_value = 0
    expected_nav = 932
    backtester.run(test_days=2)
    ds_key = pd.Timestamp('2010-09-29')
    assert(backtester._available_money == expected_available_money)
    assert(backtester._account_value[ds_key] == expected_account_value)
    assert(backtester._net_account_value[ds_key] == expected_nav)
    assert(backtester._owned_shares == {})


@pytest.mark.parametrize('backtester', [(signals_test_sigs_1(), max_first_encountered_alpha_sizer(), 500)], indirect=True)
def test_functional_backtester_3days_TEST_SIGS_1(backtester):
    expected_available_money = 1828  # 932 (previous state) + 896 (after buy short)
    expected_account_value = -900 # -10*90
    expected_nav = 928  # (1828-900)
    expected_owned_shares = {
        'TEST_SIGS_1': {
            'cnt': -10.0,
            'trx_id': '2010-09-30_TEST_SIGS_1_short'
        }
    }
    backtester.run(test_days=3)
    ds_key = pd.Timestamp('2010-09-30')
    assert(backtester._available_money == expected_available_money)
    assert(backtester._account_value[ds_key] == expected_account_value)
    assert(backtester._net_account_value[ds_key] == expected_nav)
    assert(backtester._owned_shares == expected_owned_shares)


@pytest.mark.parametrize('backtester', [(signals_test_sigs_1(), max_first_encountered_alpha_sizer(), 500)], indirect=True)
def test_functional_backtester_4days_TEST_SIGS_1(backtester):
    expected_available_money = 1024  # 1828 (previous state) + 804 (after sell short)
    expected_account_value = 0
    expected_nav = 1024
    backtester.run(test_days=4)
    ds_key = pd.Timestamp('2010-10-01')
    assert(backtester._available_money == expected_available_money)
    assert(backtester._account_value[ds_key] == expected_account_value)
    assert(backtester._net_account_value[ds_key] == expected_nav)
    assert(backtester._owned_shares == {})


@pytest.mark.parametrize('backtester', [(signals_test_sigs_1(), max_first_encountered_alpha_sizer(), 500)], indirect=True)
def test_functional_backtesetr_4_days_trades_TEST_SIGS_1(backtester):
    results, trades = backtester.run(test_days=4)
    expected_trades = {
        '2010-09-28_TEST_SIGS_1_long': {
            'buy_ds': pd.Timestamp('2010-09-28'),
            'type': 'long',
            'trx_value_no_fee': 400.0,
            'trx_value_gross': 404.0,
            'sell_ds': pd.Timestamp('2010-09-29'),
            'sell_value_no_fee': 840.0,
            'sell_value_gross': 836.0,
        },
        '2010-09-30_TEST_SIGS_1_short': {
            'buy_ds': pd.Timestamp('2010-09-30'),
            'type': 'short',
            'trx_value_no_fee': 900.0,
            'trx_value_gross': 896.0,
            'sell_ds': pd.Timestamp('2010-10-01'),
            'sell_value_no_fee': -800.0,
            'sell_value_gross': -804.0,
        }
    }
    assert(expected_trades == trades)

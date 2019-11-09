# 3rd party
import numpy as np

def trend(arr):
    """
    Finds trend in 'arr'. Returns trading signals (1,0,-1) based on slope 
    of the fitted straight line.
    """
    x = np.array(range(1,len(arr)+1))
    A = np.vstack([x, np.ones(len(x))]).T
    # fits: y = ax + b
    a, b = np.linalg.lstsq(A, arr, rcond=None)[0]
    # arbitrary threshold of 0.25. no science here.
    if a >= .25:
        return 1
    elif a < -.25:
        return -1
    return 0


def _find_support_resistance(y, e=False):
    """
    Finds support/resistance level in 'y' (returns tuple (support, resistance)). It looks at either 'global' or 'local' definition of 
    support/resistance. If global - whole period is looked at. If local, then price has to be 
    less/greater than the e previous prices.
    e - Should be int. Used for alternative supprot/resistance definition.
    """
    # "global" definition of supp/res 
    if not e or e>y.shape[0]:
        support = min(y)
        resistance = max(y)
    # "local" definition
    elif e:
        # support
        past_times_smaller_than_itself = list(
            map(lambda x: np.where(y[:x[0]]<x[1])[0].size, list(enumerate(y)))
        )
        smaller_than_e_xtimes_idxs = np.where(np.array(past_times_smaller_than_itself) < e)[0]
        support_idx = max(smaller_than_e_xtimes_idxs)
        support = y[support_idx]
        # resistance
        past_times_bigger_than_itself = list(
            map(lambda x: np.where(y[:x[0]]>x[1])[0].size, list(enumerate(y)))
        )
        bigger_than_e_xtimes_idxs = np.where(np.array(past_times_smaller_than_itself) > e)[0]
        resistance_idx = max(bigger_than_e_xtimes_idxs)
        resistance = y[resistance_idx]
    return (support, resistance)


def support_resistance(arr, e=False, b=False):
    """
    Trading signal is based on support/resistance level in 'arr'. If last (current) price in 'arr'
    is above resistance - buy (1), if below - sell (-1). Do nothing in between (0).

    b - The fixed percentage band filter requires the buy or sell signal to exceed the support/resistance by 
        a fixed multiplicative amount, b.
    """
    price = arr[-1] # last day is treated as current
    y = arr[:-1] # look t-1 days back
    support, resistance = _find_support_resistance(y, e=e)
    
    if not b:
        if price > resistance:
            return 1
        elif price < support:
            return -1
        return 0
    # b filter has to be applied
    if price > resistance+(resistance*b):
        return 1
    elif price < support-(support*b):
        return -1
    return 0
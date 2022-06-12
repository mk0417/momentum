import pandas as pd
import numpy as np
import os
import statsmodels.api as sm
from matplotlib import pyplot as plt
import seaborn as sns
import time


def pret_rank(data, j, k, n_port, fill_na, skip, no_gap, size=None,
    price=None, exchange=None, nyse_bp=False, use_duckdb=False):
    """
    Perform the rank based on lagged returns and merge returns to get return
    for each month during holding period

    Parameters
    ----------
    data: DataFrame
    j: integer
        Number of month for lagged returns
    k: integer
        Number of month for holding period
    n_port: integer
        Number of groups, e.g.10 means deciles
    fill_na: bool {True,  False}
       If True, fill missing returns with zeros
       If False, do not fill missing returns with zeros
    skip: bool {True, False}
        If True, skip (exclude) return in formation month when
        computing lagged j-month return
        If False, include return in formation month when
        computing lagged j-month return
    no_gap: bool {True, False}
        If True, replace lagged j-month returns with missing if
        the difference between formation month and the lagged jth
        month is not equal to j-1
        If False, no control for month gaps
    size: integer, default is None
        If None (ignore this argument), do not require valid market value
        in formation month for the stocks
        If 1, require positive market values
        If 2, exclude small stocks (small stocks are defined as stocks with
        market value less than 20% percentile of NYSE stocks)
    price: integer, default is None
        Minimum stock price, e.g. 5 means that stocks with price less than 5
        will be removed
        If None, no control for stock price
    exchange: list, default is None
        If None (ignore this argument), use NYSE(1)/AMEX(2)/NASDAQ(3)
        Note: NYSE must be included if use NYSE breakpoints
    nyse_bp: bool {True, False}, default is False
        If True, use NYSE breakpoints to rank stocks
        If False, use breakpoints of all stocks to rank stocks
    use_duckdb: bool {True, False}, default is False
        If True, use duckdb to perform conditional merge
        If False, use chunk by chunk full merge
    """
    pret = data[['permno', 'date', 'ret', 'me', 'exchcd', 'month_idx']].copy()

    if fill_na:
        pret['ret'] = pret['ret'].fillna(0)

    pret['logret'] = np.log(1+pret['ret'])
    pret = pret.sort_values(['permno', 'date'], ignore_index=True)

    if skip:
        pret['logret'] = pret.groupby('permno')['logret'].shift(1)
        pret['pret'] = (pret.groupby('permno')['logret']
            .rolling(window=j-1, min_periods=j-1).sum().reset_index(drop=True))

    if not skip:
        pret['pret'] = (pret.groupby('permno')['logret']
            .rolling(window=j, min_periods=j).sum().reset_index(drop=True))

    pret['pret'] = np.exp(pret['pret']) - 1
    pret = pret.sort_values(['permno', 'date'], ignore_index=True)

    if no_gap:
        pret['lmonth_idx'] = pret.groupby('permno')['month_idx'].shift(j-1)
        pret['month_diff'] = pret['month_idx'] - pret['lmonth_idx']
        pret.loc[pret['month_diff']!=j-1, 'pret'] = np.nan

    if size == 1:
        pret = pret.query('me>0').copy()

    if size == 2:
        # 20% percentile of market value based on NYSE stocks only
        me_nyse20 = (pret.query('exchcd==1').groupby('date')['me']
            .quantile(0.2).to_frame('me_nyse20').reset_index())
        pret = pret.merge(me_nyse20, how='left', on='date')
        pret = pret.query('me>=me_nyse20').copy()
        del pret['me_nyse20']

    if price:
        pret = pret.query('prc>=@price').copy()

    if exchange != None:
        pret = pret.query('exchcd==@exchange').copy()

    pret = pret.query('pret==pret').copy()
    if nyse_bp:
        nyse_pctl = (pret.query('exchcd==1').groupby('date')['pret']
            .quantile([i/n_port for i in range(1, n_port)]).unstack())
        nyse_pctl.columns = ['p'+str(i) for i in range(1, n_port)]
        nyse_pctl = nyse_pctl.reset_index()
        pret = pret.merge(nyse_pctl, how='left', on='date')
        pret.loc[pret['pret']<=pret['p1'], 'rank'] = 1
        pret.loc[pret['pret']>pret['p'+str(n_port-1)], 'rank'] = n_port
        for i in range(2, n_port):
            mask1 = (pret['pret']>pret['p'+str(i-1)])
            mask2 = (pret['pret']<=pret['p'+str(i)])
            pret.loc[mask1 & mask2, 'rank'] = i

    if not nyse_bp:
        pret['rank'] = (pret.groupby('date')['pret']
            .apply(lambda x: pd.qcut(x, n_port, labels=False)))
        pret['rank'] = pret['rank'] + 1

    pret['rank'] = pret['rank'].astype(int)

    n_stock = pret.groupby(['date', 'rank'])['pret'].count().unstack()
    n_stock_min = n_stock.min()
    n_stock_max = n_stock.max()
    n_stock_avg = n_stock.mean()
    print('\nNum stock: min')
    print(n_stock_min)
    print('\nNum stock: max')
    print(n_stock_max)
    print('\nNum stock: average')
    print(n_stock_avg)
    print('\nObs of rank data {:,}'.format(len(pret)))

    pret['form_date'] = pret['date']
    # beginning month of holding
    pret['bdate'] = pret['date'] + pd.offsets.MonthBegin(1)
    # end month of holding
    pret['edate'] = pret['date'] + pd.offsets.MonthEnd(k)
    pret = pret[['permno', 'form_date', 'rank', 'bdate', 'edate', 'me']]
    pret['w'] = (pret.groupby(['form_date', 'rank'])['me']
        .transform(lambda x: x/x.sum(min_count=1)))
    pret = pret.sort_values(['permno', 'form_date'], ignore_index=True)

    # pandas does not have conditional merge, if force merge, this will
    # consusume huge memory, so avoid this
    # df = pret.merge(msf, on='permno', how='inner')
    # df = df.query('bdate<=date<=edate').copy()

    start_time = time.time()
    if not use_duckdb:
        # do it chunk by chunk to avoid large memory usage
        df = pd.DataFrame()
        chunk_size = 100000
        for i in range(0, len(data), chunk_size):
            ret_chunk = (data[['permno', 'date', 'ret']]
                .iloc[i:i + chunk_size].copy())
            merged = pret.merge(ret_chunk, how='inner', on='permno')
            merged = merged.query('bdate<=date<=edate').copy()
            df = pd.concat([df, merged], ignore_index=True)

    if use_duckdb:
        # duckdb allows SQL query on DataFrame and it is very fast
        import duckdb

        conn = duckdb.connect()
        conn.register('rank_dk', pret)
        conn.register('ret_dk', data)

        dk = conn.execute("""
            select *
            from rank_dk as a
            inner join ret_dk as b
            on a.permno=b.permno and b.date>=a.bdate and b.date<=a.edate
        """)
        df = dk.df()

    end_time = time.time()
    time_used = end_time - start_time
    print('\nMerge returns for holding period: {:.0f}s'.format(time_used))

    df = df.drop_duplicates().copy()
    df['retw'] = df['ret'] * df['w']
    df = df.sort_values(['date', 'form_date', 'rank', 'permno'],
        ignore_index=True)
    print('\nObs of holding data {:,}'.format(len(df)))
    return df

def port_ret_ts(data, ret_type, start_date=None, end_date=None):
    """
    Calculate portfolio returns and long-short return in each month

    Parameters
    ----------
    data: DataFrame
    ret_type: string {'ew', 'vw'}
        If 'ew', compute equal-weighted return
        If 'vw', compute value-weighted return
    start_date: string, default is None
        Start date of portfolio return, for example, "2010-01-31'
        If None, use the earlest date in CRSP
    end_date: string, default is None
        End date of portfolio return, for example, '2020-12-31'
        If None, use the most recent available date in CRSP
    """
    df = data.copy()
    if start_date != None:
        df = df.query('date>=@start_date').copy()
    if end_date != None:
        df = df.query('date<=@end_date').copy()

    n = max(df['rank'].unique())
    if ret_type == 'ew':
        df = df.groupby(['date', 'rank', 'form_date'])['ret'].mean()
    if ret_type == 'vw':
        df = df.groupby(['date', 'rank', 'form_date'])['retw'].sum(min_count=1)

    df = df.groupby(level=[0, 1]).mean().unstack().reset_index()
    df['mom'] = df[n] - df[1]
    df.columns.name = ''
    df = df.sort_values('date', ignore_index=True)
    print('\nSample period')
    print(df['date'].dt.date.min())
    print(df['date'].dt.date.max())
    print('\n')
    return df

def nw_est(data, y, lag):
    df = data.dropna(subset=[y]).copy()
    est = (sm.OLS(df[y], np.ones(len(df)))
        .fit(cov_type='HAC', cov_kwds={'maxlags': lag}, use_t=True))
    t = est.tvalues[0]
    p = est.pvalues[0]
    res = (t, p)
    return res

def port_ret(data, nw_lag):
    df = data.copy()
    est = []
    n = df.columns[-2]
    for i in df.columns[1:]:
        avg = df[i].mean()
        nw = nw_est(df, i, nw_lag)
        tmp = (i, round(avg, 4), round(nw[0], 2), round(nw[1], 3))
        est.append(tmp)

    df = pd.DataFrame(est, columns=['port', 'ret', 't', 'p'])
    df.loc[df['port']==1, 'port'] = '1 (loser)'
    df.loc[df['port']==n, 'port'] = str(n) + ' (winner)'
    df.loc[df['port']=='mom', 'port'] = 'mom (winner-loser)'
    return df

def mom_port(data, j, k, n_port, fill_na, skip, no_gap, size, price, exchange,
    nyse_bp, use_duckdb, ret_type, start_date, end_date, nw_lag):
    df = pret_rank(data, j, k, n_port, fill_na=fill_na, skip=skip,
        no_gap=no_gap, size=size, price=price, exchange=exchange,
        nyse_bp=nyse_bp, use_duckdb=use_duckdb)
    df = port_ret_ts(df, ret_type, start_date=start_date, end_date=end_date)
    return df, port_ret(df, nw_lag)

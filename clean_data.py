import pandas as pd
import numpy as np
import wrds
import os
import yaml


wd = os.getcwd()

def get_wrds_username():
    with open(os.path.expanduser('~/.pass.yml')) as f:
        username = yaml.safe_load(f)['wrds']['username']

    return username

def download_crsp_data():
    sql_query = """
        select a.permno, a.date, a.ret, a.prc, a.shrout, b.exchcd
        from crsp.msf a
        left join crsp.msenames b
        on a.permno=b.permno and a.date>=b.namedt and a.date<=b.nameendt
        where b.shrcd between 10 and 11
        and b.exchcd between -2 and 3
    """
    try:
        username = get_wrds_username()
        with wrds.Connection(wrds_username=username, autoconnect=False) as conn:
            df = conn.raw_sql(sql_query, date_cols=['date'])
    except:
        with wrds.Connection(autoconnect=False) as conn:
            df = conn.raw_sql(sql_query, date_cols=['date'])

    return df

def clean_data(data):
    """
    Clean CRSP monthly stock file and generate necessary variables

    Parameters
    ----------
    data: DataFrame
    """
    df = data.copy()
    df[['permno', 'exchcd']] = df[['permno', 'exchcd']].astype(int)
    df['prc'] = df['prc'].abs()
    # align date to month end
    df['date'] = df['date'] + pd.offsets.MonthEnd(0)
    # drop duplicates if any
    df = df.drop_duplicates(['permno', 'date']).copy()
    # market value (millions)
    # shrout in CRSP monthly file is in 1,000 shares
    df['me'] = df['prc'] * df['shrout'] / 1000
    # does not make sense if return is less than 100%
    df.loc[df['ret']<-1, 'ret'] = np.nan

    month_index = df.drop_duplicates('date')[['date']].copy()
    month_index = month_index.sort_values('date', ignore_index=True)
    month_index['month_idx'] = month_index.index + 1
    df = df.merge(month_index, how='left', on='date')
    df = df.sort_values(['permno', 'date'], ignore_index=True)
    return df

def ret_data():
    df = download_crsp_data()
    df = clean_data(df)
    return df

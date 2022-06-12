from clean_data import *

def check_data(data, j):
    """
    Check CRSP data

    Parameters
    ----------
    data: DataFrame
    j: integer
        Number of lagged months
    """
    df = data.copy()
    df['ret'] = round(df['ret'], 4)
    df = df.sort_values(['permno', 'date'], ignore_index=True)
    # month_diff is to check if there is any month gaps in the data
    df['lmonth_idx'] = df.groupby('permno')['month_idx'].shift(1)
    df['month_diff'] = (df['month_idx']-df['lmonth_idx']).astype('Int64')
    del df['lmonth_idx']
    # n_ret is for sanity check: how many valid returns over past j months
    df['n_ret'] = (df.groupby('permno')['ret'].rolling(window=j, min_periods=j)
        .count().reset_index(drop=True).astype('Int64'))
    df = df.sort_values(['permno', 'date'], ignore_index=True)
    return df

msf = ret_data()

j = 6
msf_check = check_data(msf, j)

# Example: zero market values
# 111 observations and 18 stocks
len(msf_check.query('me==0'))
len(msf_check.query('me==0')['permno'].unique())

zero_me = msf_check.query('me==0')[['permno', 'date', 'ret', 'me']][7:15]
zero_me['date'] = zero_me['date'].dt.date
zero_me = zero_me.sort_values(['permno', 'date'], ignore_index=True)
print(zero_me.to_markdown(index=False))

# Example: month gaps
month_gaps = (msf_check.query('permno==64426 & "1986-10-31"<=date<="1994-05-31"')
    [['permno', 'date', 'ret', 'month_diff']])
month_gaps['date'] = month_gaps['date'].dt.date
month_gaps = month_gaps.sort_values(['permno', 'date'], ignore_index=True)
print(month_gaps.to_markdown(index=False))

# Example: missing returns and market value (price) requirement
# fill zero?
# If fill missing values with zero, the past holding period return is zero.
# Should we include this stock when ranking stocks based on past returns?
missing_ret = (msf_check.query('permno==10007')
    [['permno', 'date', 'ret', 'me', 'exchcd']][20:40])
missing_ret['date'] = missing_ret['date'].dt.date
print(missing_ret.to_markdown(index=False))

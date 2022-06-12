from clean_data import *
from momentum import *
from pandas_datareader.famafrench import get_available_datasets
import pandas_datareader.data as web


if not os.path.exists(os.path.join(wd, 'figure')):
    os.mkdir(os.path.join(wd, 'figure'))

fig_dir = os.path.join(wd, 'figure')

msf = ret_data()


# ------------------------------------
#    Jegadeesh and Titman (1993)
# ------------------------------------
j, k, n_port = 6, 6, 10
fill_na = True
skip = False
no_gap = False
size = None
price = None
exchange = [1, 2]
nyse_bp = False
use_duckdb = True
ret_type = 'ew'
start_date = '1965-01-31'
end_date = '1989-12-31'
nw_lag = 3

portew, momew = mom_port(msf, j, k, n_port, fill_na, skip, no_gap, size, price,
    exchange, use_duckdb, ret_type, start_date, end_date, nw_lag)

# to_markdown needs the installation of tabulate
print(momew.to_markdown())


# ------------------------------------
#            Fama-French
# https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_10_port_form_pr_12_2.html
# ------------------------------------
j, k, n_port = 12, 1, 10
fill_na = False
skip = True
no_gap = True
size = 1
price = None
exchange = None
nyse_bp = True
use_duckdb = True
ret_type = 'ew'
start_date = None
end_date = None
nw_lag = 3

portew, momew = mom_port(msf, j, k, n_port, fill_na, skip, no_gap, size, price,
    exchange, nyse_bp, use_duckdb, ret_type, start_date, end_date, nw_lag)
print(momew.to_markdown(index=False))

ret_type = 'vw'
portvw, momvw = mom_port(msf, j, k, n_port, fill_na, skip, no_gap, size, price,
    exchange, nyse_bp, use_duckdb, ret_type, start_date, end_date, nw_lag)
print(momvw.to_markdown(index=False))

# Get Fama-French momentum from French Data Library
# https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html

# run this to check available data
# get_available_datasets()

def ffmom_data(dataset_id):
    source = web.DataReader('10_Portfolios_Prior_12_2',
        'famafrench', start='1927-01', end='2022-03')

    # run this to know the datasets ID
    # 0 is value-weighted monthly
    # 1 is equal-weighted monthly
    # print(source['DESCR'])

    df = source[dataset_id].reset_index()
    df.columns = ['date'] + [i for i in range(1, 11)]
    df['date'] = df['date'].dt.year*10000 + df['date'].dt.month*100 + 1
    df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
    df['date'] = df['date'] + pd.offsets.MonthEnd(0)
    df['mom'] = df[10] - df[1]
    for i in df.columns[1:]:
        df[i] = df[i] / 100

    df = df.sort_values('date', ignore_index=True)
    return df

ffportew = ffmom_data(1)
ffmomew = port_ret(ffportew, 3)
print(ffmomew.to_markdown(index=False))

ffportvw = ffmom_data(0)
ffmomvw = port_ret(ffportvw, 3)
print(ffmomvw.to_markdown(index=False))

# correlation
print(round(np.corrcoef(portew['mom'], ffportew['mom'])[0][1], 3))
print(round(np.corrcoef(portvw['mom'], ffportvw['mom'])[0][1], 3))

# scatter plot of mom against FF-mom
def mom_scatter(data, ffdata, figname):
    df1 = data[['date', 'mom']]
    df2 = ffdata[['date', 'mom']].rename(columns={'mom': 'FF-mom' })
    df = df1.merge(df2, how='inner', on='date')

    fig, ax1 = plt.subplots(1, 1, figsize=(5, 5))
    sns.scatterplot(data=df, x='mom', y='FF-mom', s=15, ax=ax1)
    sns.despine()
    plt.tight_layout()
    plt.savefig(os.path.join(fig_dir, figname+'.png'), format='png', dpi=600)
    plt.show()

mom_scatter(portew, ffportew, 'ffew')
mom_scatter(portvw, ffportvw, 'ffvw')

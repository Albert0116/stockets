import sys, os, json, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'c:/Users/lxz_y/OneDrive/桌面/股票分析系统/FinRobot')
import finnhub
from datetime import datetime, timedelta

with open('config_api_keys', encoding='utf-8') as f:
    keys = json.load(f)

client = finnhub.Client(api_key=keys['FINNHUB_API_KEY'])
to_ts = int(time.time())
from_ts = int((datetime.now() - timedelta(days=90)).timestamp())
print(f'from={from_ts} to={to_ts}')

res = client.stock_candles('AAPL', 'D', from_ts, to_ts)
print('status:', res.get('s'))
t_list = res.get('t')
if t_list:
    print('data points:', len(t_list))
    print('first:', datetime.fromtimestamp(t_list[0]).strftime('%Y-%m-%d'))
    print('last:', datetime.fromtimestamp(t_list[-1]).strftime('%Y-%m-%d'))
else:
    print('response:', json.dumps(res, indent=2)[:300])

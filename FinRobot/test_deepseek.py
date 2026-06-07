import os, sys, json, warnings
warnings.filterwarnings("ignore")
os.chdir(r"c:/Users/lxz_y/OneDrive/桌面/股票分析系统/FinRobot")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("=" * 50)
print("[1] 验证 OAI_CONFIG_LIST")
import autogen
config = autogen.config_list_from_json("OAI_CONFIG_LIST")
for c in config:
    key_preview = c["api_key"][:8] + "..." + c["api_key"][-4:]
    print(f"  model={c['model']}  key={key_preview}  url={c.get('base_url','')}")
print("  [OK] 配置加载成功")

print()
print("[2] 直接调用 DeepSeek API 测试")
from openai import OpenAI
client = OpenAI(
    api_key=config[0]["api_key"],
    base_url="https://api.deepseek.com/v1"
)
resp = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "user", "content": "用一句话分析苹果公司(AAPL)当前的投资价值。回复用中文。"}
    ],
    max_tokens=200,
    temperature=0.1
)
print(f"  DeepSeek 回复: {resp.choices[0].message.content}")
print(f"  Token 用量: prompt={resp.usage.prompt_tokens}, completion={resp.usage.completion_tokens}")
print("  [OK] DeepSeek API 连接正常")

print()
print("[3] 验证 Finnhub 行情数据")
import finnhub
with open("config_api_keys", encoding="utf-8") as f:
    keys = json.load(f)
fc = finnhub.Client(api_key=keys["FINNHUB_API_KEY"])
quote = fc.quote("AAPL")
print(f"  AAPL: 现价=${quote['c']}  今日涨跌={quote['dp']:.2f}%  开盘=${quote['o']}  最高=${quote['h']}  最低=${quote['l']}")
print("  [OK] Finnhub 数据正常")

print()
print("[4] 验证 yfinance 历史数据")
import yfinance as yf
hist = yf.Ticker("AAPL").history(period="5d")
if len(hist) > 0:
    print(f"  AAPL 最近{len(hist)}个交易日数据:")
    for date, row in hist.tail(3).iterrows():
        print(f"    {str(date)[:10]}  收盘=${row['Close']:.2f}  成交量={int(row['Volume']):,}")
    print("  [OK] yfinance 正常")
else:
    print("  [WARN] yfinance 暂无数据（可能限流，稍后重试）")

print()
print("=" * 50)
print("全部验证完成！系统可以正常使用。")
print("=" * 50)

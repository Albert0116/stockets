import os, json, sys

os.chdir(r"c:/Users/lxz_y/OneDrive/桌面/股票分析系统/FinRobot")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 1. 验证 Finnhub
print("=" * 40)
print("【1】测试 Finnhub API")
try:
    import finnhub
    with open("config_api_keys") as f:
        keys = json.load(f)
    client = finnhub.Client(api_key=keys["FINNHUB_API_KEY"])
    quote = client.quote("AAPL")
    print(f"  AAPL 当前价: ${quote['c']}  涨跌: {quote['dp']:.2f}%")
    news = client.company_news("AAPL", _from="2024-01-01", to="2024-01-10")
    print(f"  新闻条数: {len(news)}")
    print("  ✓ Finnhub 连接正常")
except Exception as e:
    print(f"  ✗ Finnhub 失败: {e}")

# 2. 验证 yfinance
print()
print("【2】测试 yfinance")
try:
    import yfinance as yf
    t = yf.Ticker("AAPL")
    hist = t.history(period="5d")
    print(f"  AAPL 最近5日数据行数: {len(hist)}")
    print(f"  最新收盘价: ${hist['Close'].iloc[-1]:.2f}")
    print("  ✓ yfinance 正常")
except Exception as e:
    print(f"  ✗ yfinance 失败: {e}")

# 3. 验证 autogen 加载 OAI_CONFIG_LIST
print()
print("【3】测试 autogen 配置加载")
try:
    import autogen
    config = autogen.config_list_from_json("OAI_CONFIG_LIST")
    print(f"  配置模型: {[c['model'] for c in config]}")
    print(f"  base_url: {config[0].get('base_url', 'N/A')}")
    if "YOUR_DEEPSEEK_API_KEY" in config[0]["api_key"]:
        print("  ⚠ DeepSeek API Key 尚未填写，请编辑 OAI_CONFIG_LIST")
    else:
        print("  ✓ DeepSeek API Key 已配置")
except Exception as e:
    print(f"  ✗ autogen 失败: {e}")

# 4. 验证 finrobot 核心模块
print()
print("【4】测试 FinRobot 核心模块")
try:
    from finrobot.data_source import finnhub_utils, yfinance_utils
    print("  ✓ data_source 模块加载正常")
except Exception as e:
    print(f"  ✗ data_source 失败: {e}")

try:
    from finrobot.functional import analyzer
    print("  ✓ functional.analyzer 加载正常")
except Exception as e:
    print(f"  ✗ functional 失败: {e}")

print()
print("=" * 40)
print("环境检查完成")

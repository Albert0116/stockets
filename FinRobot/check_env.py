import sys
import os
os.chdir(r"c:/Users/lxz_y/OneDrive/桌面/股票分析系统/FinRobot")

try:
    import autogen
    print("autogen version:", autogen.__version__)
except Exception as e:
    print("autogen 导入失败:", e)

try:
    import autogen
    config = autogen.config_list_from_json("OAI_CONFIG_LIST")
    print("OAI_CONFIG_LIST 加载成功, 模型:", [c["model"] for c in config])
except Exception as e:
    print("OAI_CONFIG_LIST 加载失败:", e)

try:
    import yfinance as yf
    print("yfinance 导入成功:", yf.__version__)
except Exception as e:
    print("yfinance 失败:", e)

try:
    import finnhub
    print("finnhub 导入成功")
except Exception as e:
    print("finnhub 失败:", e)

try:
    import finrobot
    print("finrobot 导入成功")
except Exception as e:
    print("finrobot 导入失败:", e)

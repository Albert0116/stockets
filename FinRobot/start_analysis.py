# -*- coding: utf-8 -*-
"""
FinRobot + DeepSeek 快速启动脚本
用法: python start_analysis.py
"""
import os, sys, json, warnings
warnings.filterwarnings("ignore")

# 确保工作目录正确
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def check_deepseek_key():
    """检查 DeepSeek API Key 是否已配置"""
    with open("OAI_CONFIG_LIST", encoding="utf-8") as f:
        config = json.load(f)
    if "YOUR_DEEPSEEK_API_KEY" in config[0]["api_key"]:
        print("=" * 55)
        print("  [!] 请先填写 DeepSeek API Key")
        print("=" * 55)
        print()
        print("  编辑文件:  FinRobot/OAI_CONFIG_LIST")
        print("  将 YOUR_DEEPSEEK_API_KEY 替换为您的真实 Key")
        print()
        print("  获取 Key: https://platform.deepseek.com/api_keys")
        print("=" * 55)
        return False
    return True

def run_market_analysis(ticker: str = "AAPL"):
    """运行单股市场分析 Agent"""
    import autogen
    from finrobot.agents.workflow import SingleAssistant

    print(f"\n>>> 开始分析 {ticker} ...\n")

    # 加载 DeepSeek 配置（只用 deepseek-chat，成本低速度快）
    llm_config = {
        "config_list": autogen.config_list_from_json(
            "OAI_CONFIG_LIST",
            filter_dict={"model": ["deepseek-chat"]}
        ),
        "timeout": 120,
        "temperature": 0.1,
    }

    assistant = SingleAssistant(
        "Market_Analyst",
        llm_config,
        human_input_mode="NEVER",
    )

    assistant.chat(
        f"Please analyze {ticker} stock. "
        f"Cover: recent price trend, key financial metrics, "
        f"market sentiment, and investment recommendation (buy/hold/sell). "
        f"Be concise and data-driven."
    )

def run_forecaster(ticker: str = "AAPL"):
    """运行股价预测 Agent"""
    import autogen
    from finrobot.agents.workflow import SingleAssistantShadow

    print(f"\n>>> 运行 {ticker} 价格预测 ...\n")

    llm_config = {
        "config_list": autogen.config_list_from_json(
            "OAI_CONFIG_LIST",
            filter_dict={"model": ["deepseek-chat"]}
        ),
        "timeout": 120,
        "temperature": 0.1,
    }

    assistant = SingleAssistantShadow(
        "FinGPT_Forecaster",
        llm_config,
        human_input_mode="NEVER",
    )

    from datetime import datetime, timedelta
    today = datetime.today().strftime("%Y-%m-%d")
    prior = (datetime.today() - timedelta(days=30)).strftime("%Y-%m-%d")

    assistant.chat(
        f"Predict {ticker} stock price movement for the next 7 days. "
        f"Use data from {prior} to {today}. "
        f"Provide: direction (up/down/sideways), confidence %, key drivers."
    )

def main():
    print("=" * 55)
    print("  FinRobot + DeepSeek  股票分析系统")
    print("=" * 55)

    if not check_deepseek_key():
        return

    print("\n请选择功能:")
    print("  1. 市场综合分析 (Market Analysis)")
    print("  2. 股价走势预测 (Price Forecast)")
    print("  3. 直接启动 Jupyter (查看完整教程)")
    print("  q. 退出")
    print()

    choice = input("输入选项 [1/2/3/q]: ").strip()

    if choice == "1":
        ticker = input("输入股票代码 (如 AAPL, TSLA, 默认AAPL): ").strip().upper() or "AAPL"
        run_market_analysis(ticker)
    elif choice == "2":
        ticker = input("输入股票代码 (如 AAPL, TSLA, 默认AAPL): ").strip().upper() or "AAPL"
        run_forecaster(ticker)
    elif choice == "3":
        print("\n正在启动 Jupyter Lab ...")
        os.system('"C:\\Users\\lxz_y\\.conda\\envs\\finrobot\\Scripts\\jupyter.exe" lab --notebook-dir=. --no-browser')
    else:
        print("退出。")

if __name__ == "__main__":
    main()

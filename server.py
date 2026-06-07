# -*- coding: utf-8 -*-
"""
FinRobot + DeepSeek Web API 后端
支持美股 (Finnhub + Yahoo) 和 A股 (AKShare)
运行: uvicorn server:app --reload --port 8888
"""
import os, sys, json, asyncio, time
from pathlib import Path
from datetime import datetime, timedelta

# 切换到 FinRobot 目录
FINROBOT_DIR = Path(__file__).parent / "FinRobot"
os.chdir(FINROBOT_DIR)
sys.path.insert(0, str(FINROBOT_DIR))

import finnhub
from openai import OpenAI
import yfinance as yf
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import warnings
warnings.filterwarnings("ignore")

# 添加 agents 模块路径
sys.path.insert(0, str(Path(__file__).parent))
from agents.orchestrator import MultiAgentOrchestrator
from db import init_db, watchlist_add, watchlist_list, watchlist_remove, alert_add, alert_list, alert_remove
from monitor.engine import MonitorEngine
from monitor import notifiers
from scanner.engine import ScannerEngine

app = FastAPI(title="FinRobot API")

monitor_engine: MonitorEngine = None  # 全局监控引擎实例
scanner_engine: ScannerEngine = None  # 全局扫描引擎实例

@app.on_event("startup")
async def startup():
    global monitor_engine, scanner_engine
    await init_db()
    # 初始化监控引擎
    monitor_engine = MonitorEngine(finnhub_client)
    # 初始化扫描引擎
    scanner_engine = ScannerEngine(deepseek_client)
    # 配置通知渠道（从文件 + 环境变量加载，文件优先）
    config = _load_notify_config()
    import os
    for key in ("serverchan_key", "bark_url", "webhook_url"):
        env_val = os.environ.get(key.upper(), "")
        if env_val and not config.get(key):
            config[key] = env_val
    notifiers.configure(config)
    # 启动监控（每5分钟检查一次）
    monitor_engine.start(interval_minutes=5)

@app.on_event("shutdown")
async def shutdown():
    if monitor_engine:
        monitor_engine.stop()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 加载配置
_PROJECT_ROOT = Path(__file__).parent
with open(_PROJECT_ROOT / "config_api_keys", encoding="utf-8") as f:
    API_KEYS = json.load(f)
with open(_PROJECT_ROOT / "OAI_CONFIG_LIST", encoding="utf-8") as f:
    OAI_CONFIG = json.load(f)

finnhub_client = finnhub.Client(api_key=API_KEYS["FINNHUB_API_KEY"])
deepseek_client = OpenAI(
    api_key=OAI_CONFIG[0]["api_key"],
    base_url="https://api.deepseek.com/v1"
)

# ---------- 数据接口 ----------

@app.get("/api/quote/{symbol}")
def get_quote(symbol: str, market: str = Query("us", description="市场: us=美股 cn=A股")):
    """实时行情"""
    if market == "cn":
        return _get_a_share_quote(symbol)

    try:
        q = finnhub_client.quote(symbol.upper())
        profile = finnhub_client.company_profile2(symbol=symbol.upper())
        name = profile.get("name", "")
        exchange = profile.get("exchange", "")
        industry = profile.get("finnhubIndustry", "")
        market_cap = profile.get("marketCapitalization", 0)
        currency = profile.get("currency", "USD")
        logo = profile.get("logo", "")
        
        # ETF等产品 Finnhub 可能返回空profile，用 Yahoo Finance 兜底
        if not name:
            try:
                ticker = yf.Ticker(symbol.upper())
                yf_info = ticker.info
                name = yf_info.get("longName") or yf_info.get("shortName") or symbol.upper()
                exchange = yf_info.get("exchange", "")
                industry = yf_info.get("industry") or yf_info.get("category", "")
                market_cap = yf_info.get("marketCap", 0) / 1e6 if yf_info.get("marketCap") else 0
                currency = yf_info.get("currency", "USD")
            except Exception:
                name = symbol.upper()
        
        return {
            "symbol": symbol.upper(),
            "name": name,
            "price": q["c"],
            "change": q["d"],
            "change_pct": q["dp"],
            "open": q["o"],
            "high": q["h"],
            "low": q["l"],
            "prev_close": q["pc"],
            "logo": logo,
            "exchange": exchange,
            "industry": industry,
            "market_cap": market_cap,
            "currency": currency,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def _get_a_share_quote(symbol: str):
    """A股实时行情 (新浪实时API)"""
    if symbol.startswith("6") or symbol.startswith("5") or symbol.startswith("9"):
        sina_sym = f"sh{symbol}"
    else:
        sina_sym = f"sz{symbol}"
    
    url = f"http://hq.sinajs.cn/list={sina_sym}"
    headers = {
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10, proxies={"http": None, "https": None})
        resp.encoding = "gbk"
        text = resp.text
        if "=" not in text:
            raise ValueError("Invalid Sina response")

        data_str = text.split('"')[1] if '"' in text else text.split("=", 1)[1]
        parts = data_str.split(",")
        if len(parts) < 6:
            raise ValueError(f"Insufficient data: {len(parts)} fields")

        name = parts[0]
        open_price = float(parts[1])
        prev_close = float(parts[2])
        current = float(parts[3])
        high = float(parts[4])
        low = float(parts[5])
        change = round(current - prev_close, 2)
        change_pct = round((change / prev_close) * 100, 2) if prev_close > 0 else 0

        return {
            "symbol": symbol,
            "name": name,
            "price": current,
            "change": change,
            "change_pct": change_pct,
            "open": open_price,
            "high": high,
            "low": low,
            "prev_close": prev_close,
            "logo": "",
            "exchange": "上交所" if symbol.startswith("6") else "深交所",
            "industry": "",
            "market_cap": 0,
            "currency": "CNY",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/candles/{symbol}")
def get_candles(
    symbol: str,
    period: str = "6mo",
    market: str = Query("us", description="市场: us=美股 cn=A股"),
):
    """K线历史数据"""
    if market == "cn":
        return _get_a_share_candles(symbol, period)
    return _get_us_candles(symbol, period)


def _get_us_candles(symbol: str, period: str = "6mo"):
    """美股K线 (Yahoo Finance HTTP API)"""
    symbol = symbol.upper()

    period_map = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730}
    days = period_map.get(period, 180)
    period2 = int(time.time())
    period1 = int((datetime.now() - timedelta(days=days)).timestamp())

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {
        "period1": period1,
        "period2": period2,
        "interval": "1d",
        "includePrePost": "false",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        data = resp.json()
        chart = data.get("chart", {}).get("result", [])
        if not chart:
            raise ValueError("No chart data")

        timestamps = chart[0].get("timestamp", [])
        ohlcv = chart[0].get("indicators", {}).get("quote", [{}])[0]

        result = []
        for i, ts in enumerate(timestamps):
            o = ohlcv.get("open", [None])[i]
            h = ohlcv.get("high", [None])[i]
            l = ohlcv.get("low", [None])[i]
            c = ohlcv.get("close", [None])[i]
            v = ohlcv.get("volume", [None])[i]
            if o is None or c is None:
                continue
            result.append({
                "date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
                "open": round(o, 2),
                "high": round(h, 2),
                "low": round(l, 2),
                "close": round(c, 2),
                "volume": int(v) if v else 0,
            })

        if result:
            return {"symbol": symbol, "data": result}
    except Exception:
        pass

    # 备用: yfinance 库
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        if not hist.empty:
            result = []
            for dt, row in hist.iterrows():
                result.append({
                    "date": str(dt)[:10],
                    "open": round(row["Open"], 2),
                    "high": round(row["High"], 2),
                    "low": round(row["Low"], 2),
                    "close": round(row["Close"], 2),
                    "volume": int(row["Volume"]),
                })
            return {"symbol": symbol, "data": result}
    except Exception:
        pass

    raise HTTPException(status_code=404, detail="无法获取K线数据")


def _get_a_share_candles(symbol: str, period: str = "6mo"):
    """A股K线 (AKShare - 新浪数据源，绕过企业防火墙)"""
    import akshare as ak

    period_days = {"1mo": 45, "3mo": 100, "6mo": 200, "1y": 400, "2y": 800}
    days = period_days.get(period, 200)

    end_date = datetime.today().strftime("%Y%m%d")
    start_date = (datetime.today() - timedelta(days=days)).strftime("%Y%m%d")

    # 新浪数据源格式: sz000001 或 sh600519
    if symbol.startswith("6") or symbol.startswith("5") or symbol.startswith("9"):
        sina_sym = f"sh{symbol}"
    else:
        sina_sym = f"sz{symbol}"

    try:
        hist = ak.stock_zh_a_daily(
            symbol=sina_sym,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"A股 {symbol} 无K线数据")

        result = []
        for _, r in hist.iterrows():
            result.append({
                "date": str(r["date"])[:10],
                "open": round(float(r["open"]), 2),
                "high": round(float(r["high"]), 2),
                "low": round(float(r["low"]), 2),
                "close": round(float(r["close"]), 2),
                "volume": int(r["volume"]),
            })
        return {"symbol": symbol, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"A股K线获取失败: {str(e)}")


@app.get("/api/news/{symbol}")
def get_news(
    symbol: str,
    market: str = Query("us", description="市场: us=美股 cn=A股"),
):
    """最新新闻"""
    if market == "cn":
        return _get_a_share_news(symbol)

    try:
        to_date = datetime.today().strftime("%Y-%m-%d")
        from_date = (datetime.today() - timedelta(days=30)).strftime("%Y-%m-%d")
        news = finnhub_client.company_news(symbol.upper(), _from=from_date, to=to_date)
        return {"news": news[:8]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def _get_a_share_news(symbol: str):
    """A股新闻 (AKShare)"""
    import akshare as ak
    try:
        news_df = ak.stock_news_em(symbol=symbol)
        if news_df.empty:
            return {"news": []}

        news_list = []
        for _, n in news_df.head(8).iterrows():
            pub_time = n.get("发布时间", "")
            ts = 0
            try:
                ts = int(datetime.strptime(str(pub_time)[:19], "%Y-%m-%d %H:%M:%S").timestamp())
            except Exception:
                pass

            news_list.append({
                "headline": str(n.get("新闻标题", "")),
                "summary": str(n.get("新闻内容", ""))[:300],
                "url": str(n.get("新闻链接", "")),
                "datetime": ts,
                "source": str(n.get("文章来源", "")),
            })
        return {"news": news_list}
    except Exception:
        return {"news": []}


@app.get("/api/search/{query}")
def search_symbol(
    query: str,
    market: str = Query("us", description="市场: us=美股 cn=A股"),
):
    """搜索股票代码"""
    if market == "cn":
        return _search_a_shares(query)

    try:
        res = finnhub_client.symbol_lookup(query)
        items = [
            {
                "symbol": r["symbol"],
                "description": r["description"],
                "type": r.get("type", ""),
            }
            for r in res.get("result", [])[:8]
            if r.get("type") in ("Common Stock", "EQS", "")
        ]
        return {"results": items}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def _search_a_shares(query: str):
    """A股搜索 (新浪API验证)"""
    q = query.strip().upper()
    results = []

    # 如果看起来像股票代码（纯数字），直接用新浪API验证
    import re
    if re.match(r'^\d{4,6}$', q):
        # 尝试多种交易所前缀
        for prefix in [("sh", "上交所"), ("sz", "深交所")]:
            try:
                sina_sym = f"{prefix[0]}{q}"
                url = f"http://hq.sinajs.cn/list={sina_sym}"
                headers = {"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"}
                resp = requests.get(url, headers=headers, timeout=5, proxies={"http": None, "https": None})
                resp.encoding = "gbk"
                text = resp.text
                if "=" in text and len(text.split('"')) > 1:
                    data_str = text.split('"')[1]
                    if data_str and data_str.strip() and data_str.count(",") > 3:
                        name = data_str.split(",")[0]
                        results.append({
                            "symbol": q,
                            "description": f"{name} ({prefix[1]})",
                            "type": "A股",
                        })
                        break
            except Exception:
                continue

    return {"results": results[:8]}


# ---------- AI 分析接口 ----------

ANALYSIS_PROMPTS = {
    "market": """你是一位顶级{analyst}。请对 {symbol}（{name}）进行全面的市场分析，包括：
1. 📊 当前行情概述：现价 {currency}{price:.2f}，今日涨跌 {change_pct:.2f}%
2. 📈 技术面分析：结合近期价格走势分析支撑位、压力位、趋势方向
3. 🏢 基本面亮点：公司核心竞争力、行业地位、近期重要事件
4. ⚠️ 主要风险：列出3个关键风险因素
5. 💡 投资建议：明确给出 买入/持有/卖出 建议并说明理由
请用中文回答，专业简洁，数据驱动。""",

    "forecast": """你是一位量化投资专家。请对 {symbol}（{name}）做出未来7-14天的价格走势预测：
1. 🎯 价格目标：给出多空两种情景下的目标价区间
2. 📉 技术信号：分析MACD、RSI、均线等关键技术指标信号
3. 🌊 市场情绪：分析当前市场情绪和资金流向
4. 📅 关键日期：未来两周内影响股价的重要事件或时间节点
5. 🎲 概率判断：上涨概率 vs 下跌概率，信心指数（1-10分）
当前价格：{currency}{price:.2f}，今日涨跌：{change_pct:.2f}%
请用中文回答，给出明确的数字判断。""",

    "report": """请为 {symbol}（{name}）生成一份完整的股票研究报告：

# {name}({symbol}) 股票研究报告

## 一、公司概述
- 行业：{industry}
- 市值：约 {currency}{market_cap:.1f}{cap_unit}
- 当前股价：{currency}{price:.2f}

## 二、投资摘要
[给出核心投资逻辑，3-5个关键驱动因素]

## 三、财务分析
[分析公司盈利能力、成长性、现金流状况]

## 四、竞争优势
[分析护城河、市场份额、竞争壁垒]

## 五、风险因素
[列举主要风险，包括行业风险、公司风险、宏观风险]

## 六、估值分析
[相对估值和绝对估值分析，给出合理价值区间]

## 七、投资评级
评级：[买入/增持/中性/减持/卖出]
目标价：{currency}[具体数字]
时间周期：12个月

请用中文撰写，专业、详尽、有洞见。""",
}

class AnalysisRequest(BaseModel):
    symbol: str
    name: str
    price: float
    change_pct: float
    industry: str = ""
    market_cap: float = 0
    analysis_type: str = "market"
    market: str = "us"

def _parse_float(val) -> float:
    """安全解析浮点数"""
    if val is None or val == "" or val == "-" or val == "--":
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0

@app.post("/api/analyze/stream")
async def analyze_stream(req: AnalysisRequest):
    """DeepSeek 流式 AI 分析"""
    is_cn = req.market == "cn"
    currency = "¥" if is_cn else "$"
    analyst = "A股分析师，专注于沪深市场" if is_cn else "华尔街股票分析师"
    cap_unit = "亿元" if is_cn else "亿美元"
    
    prompt_template = ANALYSIS_PROMPTS.get(req.analysis_type, ANALYSIS_PROMPTS["market"])
    prompt = prompt_template.format(
        symbol=req.symbol,
        name=req.name,
        price=req.price,
        change_pct=req.change_pct,
        industry=req.industry,
        market_cap=req.market_cap,
        currency=currency,
        analyst=analyst,
        cap_unit=cap_unit,
    )

    async def event_generator():
        try:
            stream = deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是FinRobot，一个专业的AI股票分析助手，由DeepSeek大模型驱动。"},
                    {"role": "user", "content": prompt}
                ],
                stream=True,
                max_tokens=2000,
                temperature=0.3,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield f"data: {json.dumps({'text': delta}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

# ---------- 多Agent分析接口 ----------

# 初始化编排器
orchestrator = MultiAgentOrchestrator(deepseek_client, finnhub_client)


@app.post("/api/analyze/multi-agent/stream")
async def multi_agent_stream(req: AnalysisRequest):
    """多Agent流式分析 - 6个专业Agent按顺序分析"""

    async def event_generator():
        try:
            async for event in orchestrator.run_stream(req.symbol, market=req.market):
                yield event
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ===== Watchlist API =====

class WatchlistItem(BaseModel):
    symbol: str
    name: str = ""
    market: str = "us"
    notes: str = ""


@app.get("/api/watchlist")
async def get_watchlist(market: str = Query(None, description="过滤市场: us/cn, 不传则返回全部")):
    items = await watchlist_list(market=market)
    return {"items": items}


@app.post("/api/watchlist")
async def add_to_watchlist(item: WatchlistItem):
    result = await watchlist_add(item.symbol, item.name, item.market, item.notes)
    if not result["ok"]:
        raise HTTPException(status_code=409, detail="该股票已在自选列表中")
    return result


@app.delete("/api/watchlist/{symbol}")
async def remove_from_watchlist(symbol: str, market: str = Query("us")):
    removed = await watchlist_remove(symbol, market)
    if not removed:
        raise HTTPException(status_code=404, detail="未找到该股票")
    return {"ok": True}


# ===== Alert Rules API =====

class AlertRuleCreate(BaseModel):
    symbol: str
    market: str = "us"
    condition_type: str  # price_above, price_below, change_pct_above, change_pct_below, volume_spike
    condition_value: str


@app.get("/api/alerts")
async def get_alerts(symbol: str = Query(None)):
    items = await alert_list(symbol=symbol)
    return {"items": items}


@app.post("/api/alerts")
async def create_alert(rule: AlertRuleCreate):
    valid_types = {"price_above", "price_below", "change_pct_above", "change_pct_below", "volume_spike"}
    if rule.condition_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"无效的条件类型，可选: {valid_types}")
    result = await alert_add(rule.symbol, rule.market, rule.condition_type, rule.condition_value)
    return result


@app.delete("/api/alerts/{rule_id}")
async def delete_alert(rule_id: int):
    removed = await alert_remove(rule_id)
    if not removed:
        raise HTTPException(status_code=404, detail="未找到该预警规则")
    return {"ok": True}


# ===== Monitor API =====

@app.get("/api/monitor/status")
async def monitor_status():
    """获取监控引擎状态"""
    return {
        "running": monitor_engine.is_running if monitor_engine else False,
        "cooldown_seconds": monitor_engine._cooldown_seconds if monitor_engine else 0,
    }


@app.post("/api/monitor/check")
async def monitor_trigger():
    """手动触发一次监控检查"""
    if not monitor_engine:
        raise HTTPException(status_code=503, detail="监控引擎未初始化")
    await monitor_engine.trigger_check_now()
    return {"ok": True, "message": "检查完成"}


# ===== Scanner API =====

@app.get("/api/scanner/strategies")
async def list_strategies():
    """获取所有可用扫描策略"""
    strategies = await scanner_engine.get_strategies()
    return {"strategies": strategies}


@app.post("/api/scanner/run/{strategy_name}")
async def run_scan(strategy_name: str, use_ai: bool = Query(False), top_n: int = Query(10)):
    """执行单个策略扫描"""
    if not scanner_engine:
        raise HTTPException(status_code=503, detail="扫描引擎未初始化")
    try:
        results = await scanner_engine.scan(strategy_name, use_ai=use_ai, top_n=top_n)
        return {"strategy": strategy_name, "count": len(results), "results": results}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"扫描执行失败: {str(e)}")


class BatchScanRequest(BaseModel):
    strategies: list  # 策略名称列表
    top_n: int = 10


@app.post("/api/scanner/batch")
async def batch_scan(req: BatchScanRequest):
    """批量执行多个策略扫描（共享一次数据拉取）"""
    if not scanner_engine:
        raise HTTPException(status_code=503, detail="扫描引擎未初始化")
    try:
        results = await scanner_engine.batch_scan(req.strategies, top_n=req.top_n)
        total = sum(len(v) for v in results.values())
        return {"total_strategies": len(results), "total_candidates": total, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量扫描失败: {str(e)}")


@app.get("/api/scanner/results/{strategy_name}")
async def get_scan_results(strategy_name: str):
    """获取最近一次扫描结果（缓存）"""
    from db import scan_get_latest
    results = await scan_get_latest(strategy_name)
    return {"strategy": strategy_name, "count": len(results), "results": results}


@app.get("/api/health")
def health():
    return {"status": "ok", "model": "deepseek-chat", "finnhub": "connected"}


# ===== Follow-up Chat API =====

class FollowUpRequest(BaseModel):
    symbol: str
    market: str = "us"
    question: str
    context: str = ""  # 之前分析的摘要上下文


@app.post("/api/chat/follow-up")
async def follow_up_chat(req: FollowUpRequest):
    """对话式追问 - 基于分析上下文回答用户问题"""
    system_prompt = f"""你是一位专业的股票分析师助手。用户刚完成了对 {req.symbol} 的多维度分析，
现在有后续问题。请基于提供的分析上下文回答问题。

回答要求：
- 简洁直接，不要重复已知信息
- 如果问题超出已有分析范围，诚实说明
- 给出可操作的建议时注明风险
- 用中文回答"""

    messages = [{"role": "system", "content": system_prompt}]
    if req.context:
        messages.append({"role": "user", "content": f"以下是之前的分析摘要：\n{req.context}"})
        messages.append({"role": "assistant", "content": "好的，我已了解之前的分析内容。请问有什么问题？"})
    messages.append({"role": "user", "content": req.question})

    async def stream_response():
        try:
            stream = deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                stream=True,
                max_tokens=1000,
                temperature=0.3,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield f"data: {json.dumps({'text': delta}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ===== Settings API =====

NOTIFY_CONFIG_FILE = Path(__file__).parent / "notify_config.json"

def _load_notify_config():
    defaults = {
        "email_from": "", "email_password": "", "email_to": "",
        "smtp_server": "", "smtp_port": 465, "smtp_ssl": True,
        "serverchan_key": "", "bark_url": "",
    }
    if NOTIFY_CONFIG_FILE.exists():
        with open(NOTIFY_CONFIG_FILE, encoding="utf-8") as f:
            saved = json.load(f)
            defaults.update(saved)
    return defaults

def _save_notify_config(config: dict):
    with open(NOTIFY_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    # 实时更新 notifiers 配置
    notifiers.configure(config)


@app.get("/api/settings/notify")
async def get_notify_config():
    config = _load_notify_config()
    # 密码不返回明文，前端根据是否有值决定是否显示"已设置"
    if config.get("email_password"):
        config["email_password"] = "********"
    return config


@app.put("/api/settings/notify")
async def save_notify_config(config: dict):
    # 如果密码是掩码值，保留原来的真实密码
    if config.get("email_password") == "********":
        existing = _load_notify_config()
        config["email_password"] = existing.get("email_password", "")
    _save_notify_config(config)
    return {"ok": True}


@app.post("/api/settings/smtp-detect")
async def detect_smtp(data: dict):
    """根据邮箱地址自动检测 SMTP 配置"""
    email = data.get("email", "")
    smtp_info = notifiers.auto_detect_smtp(email)
    return smtp_info


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888, reload=False)

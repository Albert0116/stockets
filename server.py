# -*- coding: utf-8 -*-
"""
FinRobot + DeepSeek Web API 后端
支持美股 (Finnhub + Yahoo) 和 A股 (AKShare)
运行: uvicorn server:app --reload --port 8888
"""
import os, sys, json, asyncio, time, logging, threading
from typing import Optional, Dict, Any, List

# 绕过 Clash/系统代理，直连数据源
for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(key, None)
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

# P1-6: 日志框架
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("server")

from pathlib import Path
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

# P1-2: 不再 os.chdir，改用绝对路径
FINROBOT_DIR = Path(__file__).parent / "FinRobot"
sys.path.insert(0, str(FINROBOT_DIR))

import finnhub
from openai import OpenAI, AsyncOpenAI
import requests
import yfinance as yf
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import warnings
warnings.filterwarnings("ignore")

# 添加 agents 模块路径
sys.path.insert(0, str(Path(__file__).parent))
from agents.orchestrator import MultiAgentOrchestrator
from agents.technical import compute_rsi_series, compute_macd_series, compute_bollinger_series, compute_ma
from db import init_db, watchlist_add, watchlist_list, watchlist_remove, alert_add, alert_list, alert_remove
from db import alert_history_list, portfolio_add, portfolio_list, portfolio_remove, portfolio_update
from monitor.engine import MonitorEngine
from monitor import notifiers
from scanner.engine import ScannerEngine
from backtest.engine import get_backtest_engine
from backtest.strategies import STRATEGY_REGISTRY
from sentiment.engine import get_sentiment_engine

monitor_engine: Optional[MonitorEngine] = None
scanner_engine: Optional[ScannerEngine] = None

# 加载配置（带容错）
def _load_config(filename: str):
    config_path = FINROBOT_DIR / filename
    if not config_path.exists():
        logger.warning(f"配置文件不存在: {filename}，使用空配置")
        return {}
    try:
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"配置文件解析失败: {filename} - {e}")
        return {}

API_KEYS = _load_config("config_api_keys")
OAI_CONFIG = _load_config("OAI_CONFIG_LIST")

finnhub_client = finnhub.Client(api_key=API_KEYS.get("FINNHUB_API_KEY", ""))

# P0-1: OAI_CONFIG 容错
if isinstance(OAI_CONFIG, list) and len(OAI_CONFIG) > 0 and "api_key" in OAI_CONFIG[0]:
    _ds_key = OAI_CONFIG[0]["api_key"]
    _ds_base = OAI_CONFIG[0].get("base_url", "https://api.deepseek.com/v1")
    deepseek_client = OpenAI(api_key=_ds_key, base_url=_ds_base)
    deepseek_async_client = AsyncOpenAI(api_key=_ds_key, base_url=_ds_base)
else:
    logger.error("DeepSeek API 配置缺失，AI 分析功能不可用")
    deepseek_client = None
    deepseek_async_client = None


# P1-3: lifespan 替换废弃的 on_event
@asynccontextmanager
async def lifespan(app: FastAPI):
    global monitor_engine, scanner_engine
    await init_db()
    monitor_engine = MonitorEngine(finnhub_client)
    scanner_engine = ScannerEngine(deepseek_client)
    config = _load_notify_config()
    for key in ("serverchan_key", "bark_url", "webhook_url"):
        env_val = os.environ.get(key.upper(), "")
        if env_val and not config.get(key):
            config[key] = env_val
    notifiers.configure(config)
    monitor_engine.start(interval_minutes=5)
    logger.info("服务启动完成")
    yield
    if monitor_engine:
        monitor_engine.stop()
    logger.info("服务已关闭")


app = FastAPI(title="智析 API", lifespan=lifespan)

# P1-7: 全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"未捕获异常: {request.url} - {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "服务内部错误，请稍后重试"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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
        
        # ETF等产品 Finnhub 可能返回空profile
        if not name:
            name = symbol.upper()
            exchange = ""
            industry = ""
            market_cap = 0
            currency = "USD"
        
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
        logger.warning(f"[行情] 美股 {symbol} 获取失败: {e}")
        raise HTTPException(status_code=400, detail="行情获取失败，请检查股票代码是否正确")


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
        logger.warning(f"[行情] A股 {symbol} 获取失败: {e}")
        raise HTTPException(status_code=400, detail="A股行情获取失败，请检查股票代码")


@app.get("/api/candles/{symbol}")
async def get_candles(
    symbol: str,
    period: str = "6mo",
    market: str = Query("us", description="市场: us=美股 cn=A股"),
):
    """K线历史数据"""
    try:
        if market == "cn":
            return await asyncio.to_thread(_get_a_share_candles, symbol, period)
        return await asyncio.to_thread(_get_us_candles, symbol, period)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="K线数据获取失败，请稍后重试")


# ─── K线缓存（带 LRU 淘汰，最多200条） ───
_candle_cache: dict = {}
_candle_cache_ttl = 300  # 5分钟
_CANDLE_CACHE_MAX = 200
_cache_lock = threading.Lock()  # P1-9: 线程安全


def _cache_set(key: str, value: tuple):
    """写入缓存，超出上限时淘汰最旧的条目"""
    with _cache_lock:
        if len(_candle_cache) >= _CANDLE_CACHE_MAX:
            sorted_keys = sorted(_candle_cache.items(), key=lambda x: x[1][0])
            evict_count = max(int(_CANDLE_CACHE_MAX * 0.2), 1)
            for old_key, _ in sorted_keys[:evict_count]:
                del _candle_cache[old_key]
        _candle_cache[key] = value


# ─── AKShare 限流控制器 ───
_akshare_last_call = 0.0       # 上次调用时间戳
_AKSHARE_MIN_INTERVAL = 2.5    # 最小请求间隔（秒），避免被反爬
_AKSHARE_MAX_RETRIES = 2       # 最大重试次数
_akshare_fail_count = 0        # 连续失败计数
_akshare_cooldown_until = 0.0  # 冷却期截止时间


def _akshare_rate_wait():
    """AKShare 限流等待：确保两次调用间隔 >= 2.5 秒"""
    global _akshare_last_call
    import random
    now = time.time()
    elapsed = now - _akshare_last_call
    if elapsed < _AKSHARE_MIN_INTERVAL:
        wait = _AKSHARE_MIN_INTERVAL - elapsed + random.uniform(0.3, 1.0)
        time.sleep(wait)
    _akshare_last_call = time.time()


def _akshare_fetch_us(symbol: str, period: str):
    """通过 AKShare 获取美股K线（带限流+重试+冷却）"""
    global _akshare_fail_count, _akshare_cooldown_until
    import akshare as ak
    import random

    # 冷却期检查：连续失败过多则暂停一段时间
    now = time.time()
    if now < _akshare_cooldown_until:
        remaining = int(_akshare_cooldown_until - now)
        raise ValueError(f"AKShare 冷却中（剩余 {remaining}s）")

    period_days = {"1mo": 35, "3mo": 100, "6mo": 200, "1y": 400, "2y": 800}
    cutoff_days = period_days.get(period, 200)

    last_err = None
    for attempt in range(_AKSHARE_MAX_RETRIES + 1):
        try:
            _akshare_rate_wait()
            ak_df = ak.stock_us_daily(symbol=symbol, adjust="qfq")
            if ak_df is None or ak_df.empty:
                raise ValueError(f"AKShare 返回空数据: {symbol}")

            ak_df = ak_df.tail(cutoff_days)
            result = []
            for _, row in ak_df.iterrows():
                result.append({
                    "date": str(row["date"])[:10],
                    "open": round(float(row["open"]), 2),
                    "high": round(float(row["high"]), 2),
                    "low": round(float(row["low"]), 2),
                    "close": round(float(row["close"]), 2),
                    "volume": int(float(row["volume"])),
                })

            # 成功 → 重置失败计数
            _akshare_fail_count = 0
            return result

        except Exception as e:
            last_err = e
            if attempt < _AKSHARE_MAX_RETRIES:
                backoff = (2 ** attempt) + random.uniform(0.5, 1.5)
                logger.info(f"[K线] AKShare 重试 {attempt+1}/{_AKSHARE_MAX_RETRIES}，退避 {backoff:.1f}s")
                time.sleep(backoff)

    # 所有重试用尽
    _akshare_fail_count += 1
    # 连续失败 3 次以上 → 进入 60 秒冷却
    if _akshare_fail_count >= 3:
        _akshare_cooldown_until = time.time() + 60
        logger.warning(f"[K线] AKShare 连续失败 {_akshare_fail_count} 次，进入 60s 冷却")
        _akshare_fail_count = 0
    raise ValueError(f"AKShare 失败: {last_err}")


def _get_us_candles(symbol: str, period: str = "6mo"):
    """美股K线 (AKShare 首选 → Alpha Vantage 备选 → yfinance 兜底)"""
    symbol = symbol.upper()
    av_key = API_KEYS.get("ALPHA_VANTAGE_API_KEY", "")

    # 检查缓存
    cache_key = f"{symbol}_{period}"
    now = time.time()
    with _cache_lock:
        if cache_key in _candle_cache:
            ts, data = _candle_cache[cache_key]
            if now - ts < _candle_cache_ttl:
                logger.info(f"[K线] 缓存命中: {symbol} {period}")
                return {"symbol": symbol, "data": data}

    # ── 方式1: AKShare 首选（带限流保护）──
    logger.info(f"[K线] AKShare 尝试: {symbol}")
    try:
        result = _akshare_fetch_us(symbol, period)
        if result:
            logger.info(f"[K线] AKShare 成功: {len(result)} 条")
            _cache_set(cache_key, (time.time(), result))
            return {"symbol": symbol, "data": result}
    except Exception as e:
        logger.warning(f"[K线] AKShare 失败: {str(e)[:120]}")

    # ── 方式2: Alpha Vantage 备选 ──
    if av_key:
        try:
            outputsize = "full" if period in ("1y", "2y") else "compact"
            r = requests.get("https://www.alphavantage.co/query", params={
                "function": "TIME_SERIES_DAILY",
                "symbol": symbol,
                "apikey": av_key,
                "outputsize": outputsize,
            }, timeout=15, proxies={"http": None, "https": None})
            data = r.json()

            if "Note" in data or "Information" in data:
                logger.warning(f"[K线] Alpha Vantage 限流: {str(data)[:200]}")
                raise ValueError("Alpha Vantage rate limited")

            ts_data = data.get("Time Series (Daily)", {})
            if not ts_data:
                raise ValueError("Alpha Vantage: no Time Series data")

            period_days = {"1mo": 35, "3mo": 100, "6mo": 200, "1y": 400, "2y": 800}
            cutoff = (datetime.now() - timedelta(days=period_days.get(period, 200))).strftime("%Y-%m-%d")

            result = []
            for date_str, vals in sorted(ts_data.items(), reverse=True):
                if date_str < cutoff:
                    continue
                result.append({
                    "date": date_str,
                    "open": round(float(vals["1. open"]), 2),
                    "high": round(float(vals["2. high"]), 2),
                    "low": round(float(vals["3. low"]), 2),
                    "close": round(float(vals["4. close"]), 2),
                    "volume": int(float(vals["5. volume"])),
                })
            result.reverse()

            if result:
                logger.info(f"[K线] Alpha Vantage 成功: {symbol} {len(result)} 条")
                _cache_set(cache_key, (time.time(), result))
                return {"symbol": symbol, "data": result}
        except Exception as e:
            logger.warning(f"[K线] Alpha Vantage 失败: {e}")

    # ── 方式3: yfinance 兜底 ──
    logger.info(f"[K线] yfinance 尝试: {symbol}")
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        if hist is not None and not hist.empty:
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
            if result:
                logger.info(f"[K线] yfinance 成功: {len(result)} 条")
                _cache_set(cache_key, (time.time(), result))
                return {"symbol": symbol, "data": result}
    except Exception as e:
        logger.warning(f"[K线] yfinance 失败: {str(e)[:100]}")

    # 返回过期缓存兜底
    if cache_key in _candle_cache:
        _, old = _candle_cache[cache_key]
        logger.info(f"[K线] 返回过期缓存 ({len(old)} 条)")
        return {"symbol": symbol, "data": old}

    raise ValueError("美股K线数据获取失败，请稍后重试")


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
            raise ValueError(f"A股 {symbol} 无K线数据")

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
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"A股K线获取失败: {str(e)}")


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
        logger.warning(f"[新闻] {symbol} 获取失败: {e}")
        raise HTTPException(status_code=400, detail="新闻获取失败，请稍后重试")


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
        logger.warning(f"[搜索] {query} 失败: {e}")
        raise HTTPException(status_code=400, detail="搜索失败，请稍后重试")


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
            if not deepseek_async_client:
                yield f"data: {json.dumps({'error': 'AI 服务未配置'})}\n\n"
                return
            stream = await deepseek_async_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是FinRobot，一个专业的AI股票分析助手，由DeepSeek大模型驱动。"},
                    {"role": "user", "content": prompt}
                ],
                stream=True,
                max_tokens=2000,
                temperature=0.3,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield f"data: {json.dumps({'text': delta}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"AI 流式分析异常: {e}")
            yield f"data: {json.dumps({'error': '分析服务暂时不可用'})}\n\n"

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
        logger.warning(f"[扫描] {strategy_name} 参数错误: {e}")
        raise HTTPException(status_code=400, detail="扫描参数有误")
    except Exception as e:
        logger.error(f"[扫描] {strategy_name} 执行失败: {e}")
        raise HTTPException(status_code=500, detail="扫描执行失败，请稍后重试")


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
        logger.error(f"[扫描] 批量扫描失败: {e}")
        raise HTTPException(status_code=500, detail="批量扫描失败，请稍后重试")


@app.get("/api/scanner/results/{strategy_name}")
async def get_scan_results(strategy_name: str):
    """获取最近一次扫描结果（缓存）"""
    from db import scan_get_latest
    results = await scan_get_latest(strategy_name)
    return {"strategy": strategy_name, "count": len(results), "results": results}


@app.get("/api/health")
async def health():
    """健康检查 - 检查实际连接状态"""
    status = {"status": "ok"}
    # 检查 DeepSeek
    status["ai"] = "ready" if deepseek_async_client else "unconfigured"
    # 检查 Finnhub
    try:
        await asyncio.to_thread(finnhub_client.quote, "AAPL")
        status["finnhub"] = "connected"
    except Exception:
        status["finnhub"] = "disconnected"
    return status


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
            if not deepseek_async_client:
                yield f"data: {json.dumps({'error': 'AI 服务未配置'})}\n\n"
                return
            stream = await deepseek_async_client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                stream=True,
                max_tokens=1000,
                temperature=0.3,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield f"data: {json.dumps({'text': delta}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"追问服务异常: {e}")
            yield f"data: {json.dumps({'error': '追问服务暂时不可用'}, ensure_ascii=False)}\n\n"

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


# ───────── 量化回测 API ─────────

@app.get("/api/backtest/strategies")
def list_backtest_strategies():
    """返回所有可用回测策略的元信息"""
    engine = get_backtest_engine()
    return engine.list_strategies()


@app.post("/api/backtest/run")
def run_backtest(data: dict):
    """
    运行回测
    Body: {
        "symbol": "AAPL",
        "market": "us",
        "strategy_key": "sma_cross",
        "params": {"fast": 10, "slow": 30},
        "period": "1y",
        "initial_cash": 100000
    }
    """
    symbol = data.get("symbol", "AAPL").upper()
    market = data.get("market", "us")
    strategy_key = data.get("strategy_key", "sma_cross")
    params = data.get("params", None)
    period = data.get("period", "1y")
    initial_cash = float(data.get("initial_cash", 100000))

    # 获取K线数据
    try:
        if market == "cn":
            candles = _get_a_share_candles(symbol, period).get("data", [])
        else:
            candles = _get_us_candles(symbol, period).get("data", [])
    except Exception as e:
        from backtest.engine import BacktestResult
        r = BacktestResult(symbol=symbol, strategy_name=strategy_key, strategy_key=strategy_key)
        r.error = f"获取K线数据失败: {str(e)}"
        return r.summary_dict()

    if not candles or len(candles) < 50:
        from backtest.engine import BacktestResult
        r = BacktestResult(symbol=symbol, strategy_name=strategy_key, strategy_key=strategy_key)
        r.error = f"K线数据不足（{len(candles) if candles else 0}根K线，至少需要50根）"
        return r.summary_dict()

    # 运行回测
    engine = get_backtest_engine()
    result = engine.run(
        symbol=symbol,
        candles=candles,
        strategy_key=strategy_key,
        params=params,
        initial_cash=initial_cash,
    )
    return result.summary_dict()


@app.post("/api/backtest/scan-best")
def scan_best_strategy(data: dict):
    """
    扫描所有策略,返回最优结果
    Body: {"symbol": "AAPL", "market": "us", "period": "1y"}
    """
    symbol = data.get("symbol", "AAPL").upper()
    market = data.get("market", "us")
    period = data.get("period", "1y")

    try:
        if market == "cn":
            candles = _get_a_share_candles(symbol, period).get("data", [])
        else:
            candles = _get_us_candles(symbol, period).get("data", [])
    except Exception as e:
        return {"error": f"获取K线数据失败: {str(e)}"}

    if not candles or len(candles) < 50:
        return {"error": f"K线数据不足"}

    engine = get_backtest_engine()
    results = engine.scan_best(symbol, candles)
    return {"symbol": symbol, "results": results}


# ───────── 舆情分析 API ─────────

@app.get("/api/sentiment/analyze/{symbol}")
def analyze_sentiment(
    symbol: str,
    market: str = Query("us", description="市场: us=美股 cn=A股"),
):
    """获取舆情分析结果（含情绪评分、标签、文章详情）"""
    engine = get_sentiment_engine()
    result = engine.analyze(
        symbol=symbol,
        market=market,
        finnhub_client=finnhub_client if market == "us" else None,
    )
    return result.to_dict()


@app.get("/api/sentiment/quick/{symbol}")
def quick_sentiment(
    symbol: str,
    market: str = Query("us", description="市场: us=美股 cn=A股"),
):
    """快速舆情评分（适合列表批量调用）"""
    engine = get_sentiment_engine()
    return engine.quick_score(
        symbol=symbol,
        market=market,
        finnhub_client=finnhub_client if market == "us" else None,
    )


# ─── 预警历史 API ───────────────────────────────────────────

@app.get("/api/alerts/history")
async def alerts_history(
    symbol: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """获取预警触发历史"""
    items = await alert_history_list(symbol=symbol, limit=limit)
    return {"items": items}


# ─── 动态热门股票 API ──────────────────────────────────────

_trending_cache: Dict[str, Any] = {}
_trending_ts: Dict[str, float] = {}
_TRENDING_TTL = 600  # 10分钟缓存


@app.get("/api/market/trending")
async def market_trending(market: str = Query("us")):
    """获取热门股票（涨幅/跌幅/成交活跃）"""
    now = time.time()
    cache_key = f"trending_{market}"
    if cache_key in _trending_ts and now - _trending_ts[cache_key] < _TRENDING_TTL:
        return _trending_cache[cache_key]
    try:
        if market == "cn":
            result = await _get_cn_trending()
        else:
            result = await _get_us_trending()
        _trending_cache[cache_key] = result
        _trending_ts[cache_key] = now
        return result
    except Exception as e:
        logger.warning(f"获取热门股票失败: {e}")
        return {"gainers": [], "losers": [], "active": []}


async def _get_us_trending():
    """美股热门 - finnhub most-active + sector sentiment"""
    gainers, losers, active = [], [], []
    try:
        # 用 yfinance 获取热门ETF/股票的日内涨跌
        symbols = ["AAPL","NVDA","TSLA","MSFT","AMZN","GOOGL","META","AMD","NFLX","BABA",
                    "PLTR","SOXL","TQQQ","SPY","QQQ"]
        import yfinance as yf
        tickers = yf.Tickers(" ".join(symbols))
        items = []
        for sym in symbols:
            try:
                t = tickers.tickers[sym]
                info = t.fast_info
                price = info.get("lastPrice", 0) or info.get("last_price", 0)
                prev = info.get("previousClose", 0) or info.get("previous_close", 0)
                if price and prev:
                    chg_pct = round((price - prev) / prev * 100, 2)
                    items.append({"symbol": sym, "price": round(price, 2), "change_pct": chg_pct})
            except Exception:
                continue
        items.sort(key=lambda x: x["change_pct"], reverse=True)
        gainers = items[:5]
        losers = items[-5:][::-1]
        active = sorted(items, key=lambda x: abs(x["change_pct"]), reverse=True)[:5]
    except Exception as e:
        logger.warning(f"美股热门数据获取失败: {e}")
    return {"gainers": gainers, "losers": losers, "active": active}


async def _get_cn_trending():
    """A股热门 - akshare 人气榜"""
    gainers, losers, active = [], [], []
    try:
        import akshare as ak
        _akshare_rate_wait()
        df = ak.stock_hot_rank_em()
        if df is not None and len(df) > 0:
            for _, row in df.head(15).iterrows():
                code = str(row.get("股票代码", "")).zfill(6)
                name = str(row.get("股票名称", ""))
                price = float(row.get("最新价", 0) or 0)
                chg = float(row.get("涨跌幅", 0) or 0)
                item = {"symbol": code, "name": name, "price": price, "change_pct": round(chg, 2)}
                if chg > 0:
                    gainers.append(item)
                elif chg < 0:
                    losers.append(item)
                active.append(item)
            gainers.sort(key=lambda x: x["change_pct"], reverse=True)
            losers.sort(key=lambda x: x["change_pct"])
            gainers = gainers[:5]
            losers = losers[:5]
            active = active[:5]
    except Exception as e:
        logger.warning(f"A股热门数据获取失败: {e}")
    return {"gainers": gainers, "losers": losers, "active": active}


# ─── 技术指标序列 API ────────────────────────────────────────

@app.get("/api/indicators/{symbol}")
async def get_indicators(
    symbol: str,
    period: str = Query("6mo"),
    market: str = Query("us"),
):
    """返回完整技术指标序列（RSI/MACD/BOLL/MA）"""
    try:
        candles_data = await asyncio.to_thread(
            _get_a_share_candles if market == "cn" else _get_us_candles, symbol, period
        )
        if not candles_data or len(candles_data) < 30:
            raise HTTPException(400, "K线数据不足")
        closes = [c["close"] for c in candles_data]
        dates = [str(c.get("date", ""))[:10] for c in candles_data]
        ma10 = compute_ma(closes, 10)
        ma60 = compute_ma(closes, 60)
        rsi = compute_rsi_series(closes)
        macd_line, signal_line, histogram = compute_macd_series(closes)
        boll_upper, boll_mid, boll_lower = compute_bollinger_series(closes)
        return {
            "dates": dates,
            "ma10": ma10,
            "ma60": ma60,
            "rsi": rsi,
            "macd": {"macd": macd_line, "signal": signal_line, "histogram": histogram},
            "bollinger": {"upper": boll_upper, "middle": boll_mid, "lower": boll_lower},
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"指标计算失败 {symbol}: {e}")
        raise HTTPException(500, f"指标计算失败: {e}")


# ─── 组合/持仓跟踪 API ──────────────────────────────────────

class PortfolioAddRequest(BaseModel):
    symbol: str
    market: str = "us"
    buy_price: float
    quantity: float
    buy_date: str = ""
    notes: str = ""
    group_name: str = "默认"


class PortfolioUpdateRequest(BaseModel):
    id: int
    buy_price: Optional[float] = None
    quantity: Optional[float] = None
    notes: Optional[str] = None
    group_name: Optional[str] = None


@app.get("/api/portfolio")
async def get_portfolio(market: Optional[str] = Query(None)):
    """获取持仓列表"""
    items = await portfolio_list(market=market)
    return {"items": items}


@app.post("/api/portfolio")
async def add_portfolio_position(req: PortfolioAddRequest):
    """添加持仓"""
    if not req.buy_date:
        req.buy_date = datetime.now().strftime("%Y-%m-%d")
    pid = await portfolio_add(
        symbol=req.symbol.upper(),
        market=req.market,
        buy_price=req.buy_price,
        quantity=req.quantity,
        buy_date=req.buy_date,
        notes=req.notes,
        group_name=req.group_name,
    )
    return {"ok": True, "id": pid}


@app.put("/api/portfolio")
async def update_portfolio_position(req: PortfolioUpdateRequest):
    """更新持仓"""
    await portfolio_update(
        position_id=req.id,
        buy_price=req.buy_price,
        quantity=req.quantity,
        notes=req.notes,
        group_name=req.group_name,
    )
    return {"ok": True}


@app.delete("/api/portfolio/{position_id}")
async def remove_portfolio_position(position_id: int):
    """删除持仓"""
    await portfolio_remove(position_id)
    return {"ok": True}


@app.get("/api/portfolio/summary")
async def portfolio_summary(market: Optional[str] = Query(None)):
    """持仓汇总（含实时盈亏）"""
    items = await portfolio_list(market=market)
    total_cost = 0.0
    total_value = 0.0
    positions = []
    for item in items:
        sym = item["symbol"]
        mkt = item.get("market", "us")
        cost = item["buy_price"] * item["quantity"]
        total_cost += cost
        # 尝试获取实时价格
        current_price = item["buy_price"]
        try:
            if mkt == "cn":
                q = _get_a_share_quote(sym)
                current_price = q.get("price", item["buy_price"])
            else:
                if finnhub_client:
                    q = finnhub_client.quote(sym)
                    current_price = q.get("c", item["buy_price"])
        except Exception:
            pass
        value = current_price * item["quantity"]
        total_value += value
        pnl = value - cost
        pnl_pct = round(pnl / cost * 100, 2) if cost > 0 else 0
        positions.append({
            **item,
            "current_price": round(current_price, 2),
            "market_value": round(value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": pnl_pct,
        })
    total_pnl = round(total_value - total_cost, 2)
    total_pnl_pct = round(total_pnl / total_cost * 100, 2) if total_cost > 0 else 0
    return {
        "positions": positions,
        "total_cost": round(total_cost, 2),
        "total_value": round(total_value, 2),
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "position_count": len(positions),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888, reload=False)

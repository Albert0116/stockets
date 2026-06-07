# -*- coding: utf-8 -*-
"""SQLite持久化层 - 自选股、预警、扫描结果、分析缓存"""

import aiosqlite
import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

DB_PATH = Path(__file__).parent / "data" / "finrobot.db"

# 确保目录存在
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# P1-1: 模块级单例连接 + 异步锁
_db: Optional[aiosqlite.Connection] = None
_db_lock = asyncio.Lock()


async def _get_conn() -> aiosqlite.Connection:
    """获取复用数据库连接"""
    global _db
    if _db is None:
        _db = await aiosqlite.connect(str(DB_PATH))
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
    return _db


async def get_db() -> aiosqlite.Connection:
    """获取数据库连接（带锁保护）"""
    async with _db_lock:
        return await _get_conn()


async def init_db():
    """初始化数据库表结构"""
    db = await _get_conn()
    await db.execute("PRAGMA journal_mode=WAL")

    # 自选股表
    await db.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            market TEXT NOT NULL DEFAULT 'us',
            added_at REAL NOT NULL,
            notes TEXT DEFAULT '',
            UNIQUE(symbol, market)
        )
    """)

    # 预警条件表
    await db.execute("""
        CREATE TABLE IF NOT EXISTS alert_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL DEFAULT 'us',
            condition_type TEXT NOT NULL,
            condition_value TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL,
            last_triggered_at REAL DEFAULT NULL,
            trigger_count INTEGER DEFAULT 0
        )
    """)

    # 预警触发记录
    await db.execute("""
        CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            triggered_at REAL NOT NULL,
            message TEXT NOT NULL,
            price REAL DEFAULT 0,
            notified INTEGER DEFAULT 0,
            FOREIGN KEY (rule_id) REFERENCES alert_rules(id)
        )
    """)

    # 策略扫描结果
    await db.execute("""
        CREATE TABLE IF NOT EXISTS scan_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_name TEXT NOT NULL,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL DEFAULT 'us',
            score REAL DEFAULT 0,
            reason TEXT DEFAULT '',
            scanned_at REAL NOT NULL,
            expires_at REAL NOT NULL
        )
    """)

    # 分析缓存
    await db.execute("""
        CREATE TABLE IF NOT EXISTS analysis_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL DEFAULT 'us',
            analysis_type TEXT NOT NULL DEFAULT 'multi-agent',
            result_json TEXT NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            UNIQUE(symbol, market, analysis_type)
        )
    """)

    # 索引
    await db.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_symbol ON watchlist(symbol, market)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_alert_rules_symbol ON alert_rules(symbol, enabled)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_scan_results_strategy ON scan_results(strategy_name, scanned_at)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_analysis_cache_lookup ON analysis_cache(symbol, market, expires_at)")

    # 持仓表 (Task 7)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL DEFAULT 'us',
            buy_price REAL NOT NULL,
            quantity REAL NOT NULL,
            buy_date TEXT NOT NULL,
            notes TEXT DEFAULT '',
            group_name TEXT DEFAULT '默认',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_symbol ON portfolio(symbol, market)")

    await db.commit()


# ===== Watchlist CRUD =====

async def watchlist_add(symbol: str, name: str, market: str = "us", notes: str = "") -> Dict[str, Any]:
    """添加自选股"""
    async with _db_lock:
        db = await _get_conn()
        try:
            await db.execute(
                "INSERT INTO watchlist (symbol, name, market, added_at, notes) VALUES (?, ?, ?, ?, ?)",
                (symbol.upper(), name, market, time.time(), notes)
            )
            await db.commit()
            return {"ok": True, "symbol": symbol.upper(), "market": market}
        except aiosqlite.IntegrityError:
            return {"ok": False, "error": "already_exists"}


async def watchlist_remove(symbol: str, market: str = "us") -> bool:
    """移除自选股"""
    async with _db_lock:
        db = await _get_conn()
        cursor = await db.execute(
            "DELETE FROM watchlist WHERE symbol = ? AND market = ?",
            (symbol.upper(), market)
        )
        await db.commit()
        return cursor.rowcount > 0


async def watchlist_list(market: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取自选股列表"""
    async with _db_lock:
        db = await _get_conn()
        if market:
            cursor = await db.execute(
                "SELECT * FROM watchlist WHERE market = ? ORDER BY added_at DESC", (market,)
            )
        else:
            cursor = await db.execute("SELECT * FROM watchlist ORDER BY added_at DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# ===== Alert Rules CRUD =====

async def alert_add(symbol: str, market: str, condition_type: str, condition_value: str) -> Dict[str, Any]:
    """添加预警规则"""
    async with _db_lock:
        db = await _get_conn()
        cursor = await db.execute(
            """INSERT INTO alert_rules (symbol, market, condition_type, condition_value, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (symbol.upper(), market, condition_type, condition_value, time.time())
        )
        await db.commit()
        return {"ok": True, "id": cursor.lastrowid}


async def alert_remove(rule_id: int) -> bool:
    """删除预警规则"""
    async with _db_lock:
        db = await _get_conn()
        cursor = await db.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
        await db.commit()
        return cursor.rowcount > 0


async def alert_list(symbol: Optional[str] = None, enabled_only: bool = True) -> List[Dict[str, Any]]:
    """获取预警规则列表"""
    async with _db_lock:
        db = await _get_conn()
        conditions = []
        params = []
        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol.upper())
        if enabled_only:
            conditions.append("enabled = 1")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        cursor = await db.execute(f"SELECT * FROM alert_rules {where} ORDER BY created_at DESC", params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def alert_record_trigger(rule_id: int, symbol: str, message: str, price: float = 0):
    """记录预警触发"""
    async with _db_lock:
        db = await _get_conn()
        now = time.time()
        await db.execute(
            "INSERT INTO alert_history (rule_id, symbol, triggered_at, message, price) VALUES (?, ?, ?, ?, ?)",
            (rule_id, symbol, now, message, price)
        )
        await db.execute(
            "UPDATE alert_rules SET last_triggered_at = ?, trigger_count = trigger_count + 1 WHERE id = ?",
            (now, rule_id)
        )
        await db.commit()


# ===== Analysis Cache =====

async def cache_get(symbol: str, market: str = "us", analysis_type: str = "multi-agent") -> Optional[Dict[str, Any]]:
    """获取未过期的分析缓存"""
    async with _db_lock:
        db = await _get_conn()
        cursor = await db.execute(
            """SELECT result_json, created_at FROM analysis_cache
               WHERE symbol = ? AND market = ? AND analysis_type = ? AND expires_at > ?""",
            (symbol.upper(), market, analysis_type, time.time())
        )
        row = await cursor.fetchone()
        if row:
            return {"result": json.loads(row["result_json"]), "cached_at": row["created_at"]}
        return None


async def cache_set(symbol: str, market: str, result: Dict[str, Any],
                    analysis_type: str = "multi-agent", ttl_seconds: int = 3600):
    """写入分析缓存"""
    now = time.time()
    async with _db_lock:
        db = await _get_conn()
        await db.execute(
            """INSERT OR REPLACE INTO analysis_cache (symbol, market, analysis_type, result_json, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (symbol.upper(), market, analysis_type, json.dumps(result, ensure_ascii=False), now, now + ttl_seconds)
        )
        await db.commit()


# ===== Scan Results =====

async def scan_save(strategy_name: str, results: List[Dict[str, Any]], ttl_seconds: int = 86400):
    """保存扫描结果"""
    now = time.time()
    expires = now + ttl_seconds
    async with _db_lock:
        db = await _get_conn()
        await db.execute("DELETE FROM scan_results WHERE strategy_name = ?", (strategy_name,))
        for item in results:
            await db.execute(
                """INSERT INTO scan_results (strategy_name, symbol, market, score, reason, scanned_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (strategy_name, item["symbol"], item.get("market", "us"),
                 item.get("score", 0), item.get("reason", ""), now, expires)
            )
        await db.commit()


async def scan_get_latest(strategy_name: str) -> List[Dict[str, Any]]:
    """获取最新扫描结果"""
    async with _db_lock:
        db = await _get_conn()
        cursor = await db.execute(
            """SELECT * FROM scan_results
               WHERE strategy_name = ? AND expires_at > ?
               ORDER BY score DESC""",
            (strategy_name, time.time())
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# ===== Alert History =====

async def alert_history_list(symbol: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """获取预警触发历史记录（JOIN alert_rules）"""
    async with _db_lock:
        db = await _get_conn()
        conditions = []
        params: list = []
        if symbol:
            conditions.append("h.symbol = ?")
            params.append(symbol.upper())
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        cursor = await db.execute(
            f"""SELECT h.*, r.condition_type AS rule_condition_type, r.condition_value AS rule_condition_value
                FROM alert_history h
                LEFT JOIN alert_rules r ON h.rule_id = r.id
                {where}
                ORDER BY h.triggered_at DESC LIMIT ?""",
            params
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# ===== Portfolio CRUD =====

async def portfolio_add(symbol: str, market: str, buy_price: float, quantity: float,
                         buy_date: str, notes: str = "", group_name: str = "默认") -> Dict[str, Any]:
    """添加持仓"""
    async with _db_lock:
        db = await _get_conn()
        now = time.time()
        cursor = await db.execute(
            """INSERT INTO portfolio (symbol, market, buy_price, quantity, buy_date, notes, group_name, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (symbol.upper(), market, buy_price, quantity, buy_date, notes, group_name, now, now)
        )
        await db.commit()
        return {"ok": True, "id": cursor.lastrowid}


async def portfolio_remove(position_id: int) -> bool:
    """删除持仓"""
    async with _db_lock:
        db = await _get_conn()
        cursor = await db.execute("DELETE FROM portfolio WHERE id = ?", (position_id,))
        await db.commit()
        return cursor.rowcount > 0


async def portfolio_update(position_id: int, **fields) -> bool:
    """更新持仓"""
    if not fields:
        return False
    allowed = {"buy_price", "quantity", "buy_date", "notes", "group_name"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return False
    updates["updated_at"] = time.time()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    async with _db_lock:
        db = await _get_conn()
        cursor = await db.execute(
            f"UPDATE portfolio SET {set_clause} WHERE id = ?",
            (*updates.values(), position_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def portfolio_list(market: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取持仓列表"""
    async with _db_lock:
        db = await _get_conn()
        if market:
            cursor = await db.execute(
                "SELECT * FROM portfolio WHERE market = ? ORDER BY created_at DESC", (market,)
            )
        else:
            cursor = await db.execute("SELECT * FROM portfolio ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

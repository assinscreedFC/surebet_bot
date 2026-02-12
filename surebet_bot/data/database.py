# Base de données SQLite pour l'historique

import aiosqlite
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class SurebetRecord:
    """Enregistrement d'un surebet."""
    id: Optional[int]
    detected_at: datetime
    sport: str
    league: str
    match: str
    market: str
    bookmaker1: str
    odds1: float
    bookmaker2: str
    odds2: float
    profit_pct: float
    profit_base_100: float
    notified: bool = True


class Database:
    """Gestionnaire de base de données SQLite asynchrone."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
    
    async def connect(self):
        """Ouvre la connexion et crée les tables."""
        self._conn = await aiosqlite.connect(self.db_path)
        await self._create_tables()
    
    async def close(self):
        """Ferme la connexion."""
        if self._conn:
            await self._conn.close()
    
    async def _create_tables(self):
        """Crée les tables si elles n'existent pas."""
        await self._conn.executescript("""
            -- Table des surebets détectés
            CREATE TABLE IF NOT EXISTS surebets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sport TEXT NOT NULL,
                league TEXT NOT NULL,
                match TEXT NOT NULL,
                market TEXT NOT NULL,
                bookmaker1 TEXT NOT NULL,
                odds1 REAL NOT NULL,
                bookmaker2 TEXT NOT NULL,
                odds2 REAL NOT NULL,
                profit_pct REAL NOT NULL,
                profit_base_100 REAL NOT NULL,
                notified BOOLEAN DEFAULT 1
            );
            
            -- Table d'usage API
            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                api_key TEXT NOT NULL,
                requests_used INTEGER,
                requests_remaining INTEGER
            );
            
            -- Table des logs (pour le dashboard)
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                level TEXT NOT NULL,
                message TEXT NOT NULL
            );
            
            -- Table des cotes brutes (pour analyse)
            CREATE TABLE IF NOT EXISTS raw_odds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sport TEXT NOT NULL,
                match TEXT NOT NULL,
                market TEXT NOT NULL,
                bookmaker TEXT NOT NULL,
                outcome TEXT NOT NULL,
                odds REAL NOT NULL,
                implied_prob REAL
            );
            
            -- Table des scans (pour statistiques)
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sports_scanned INTEGER,
                events_found INTEGER,
                surebets_found INTEGER,
                api_key TEXT,
                requests_remaining INTEGER
            );
            
            -- Index pour les requêtes fréquentes
            CREATE INDEX IF NOT EXISTS idx_surebets_date ON surebets(detected_at);
            CREATE INDEX IF NOT EXISTS idx_surebets_sport ON surebets(sport);
            CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level);
            CREATE INDEX IF NOT EXISTS idx_raw_odds_match ON raw_odds(match);
            CREATE INDEX IF NOT EXISTS idx_raw_odds_timestamp ON raw_odds(timestamp);
        """)
        await self._conn.commit()
    
    # === SUREBETS ===
    
    async def save_surebet(self, record: SurebetRecord) -> int:
        """Sauvegarde un surebet et retourne son ID."""
        cursor = await self._conn.execute("""
            INSERT INTO surebets 
            (detected_at, sport, league, match, market, bookmaker1, odds1, 
             bookmaker2, odds2, profit_pct, profit_base_100, notified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.detected_at, record.sport, record.league, record.match,
            record.market, record.bookmaker1, record.odds1,
            record.bookmaker2, record.odds2, record.profit_pct,
            record.profit_base_100, record.notified
        ))
        await self._conn.commit()
        return cursor.lastrowid
    
    async def get_surebets(self, limit: int = 100, sport: str = None) -> list[dict]:
        """Récupère les derniers surebets."""
        query = "SELECT * FROM surebets"
        params = []
        
        if sport:
            query += " WHERE sport = ?"
            params.append(sport)
        
        query += " ORDER BY detected_at DESC LIMIT ?"
        params.append(limit)
        
        cursor = await self._conn.execute(query, params)
        rows = await cursor.fetchall()
        columns = [d[0] for d in cursor.description]
        
        return [dict(zip(columns, row)) for row in rows]
    
    async def get_stats(self) -> dict:
        """Retourne les statistiques globales."""
        # Total surebets
        cursor = await self._conn.execute("SELECT COUNT(*) FROM surebets")
        total = (await cursor.fetchone())[0]
        
        # Profit total
        cursor = await self._conn.execute("SELECT SUM(profit_pct) FROM surebets")
        total_profit = (await cursor.fetchone())[0] or 0
        
        # Par sport
        cursor = await self._conn.execute("""
            SELECT sport, COUNT(*) as count, SUM(profit_pct) as profit
            FROM surebets GROUP BY sport ORDER BY count DESC
        """)
        by_sport = await cursor.fetchall()
        
        # Par marché
        cursor = await self._conn.execute("""
            SELECT market, COUNT(*) as count, AVG(profit_pct) as avg_profit
            FROM surebets GROUP BY market ORDER BY count DESC LIMIT 10
        """)
        by_market = await cursor.fetchall()
        
        return {
            "total_surebets": total,
            "total_profit_pct": round(total_profit, 2),
            "by_sport": [{"sport": s, "count": c, "profit": round(p or 0, 2)} for s, c, p in by_sport],
            "by_market": [{"market": m, "count": c, "avg_profit": round(a or 0, 2)} for m, c, a in by_market],
        }
    
    # === API USAGE ===
    
    async def log_api_usage(self, api_key: str, used: int, remaining: int):
        """Enregistre l'usage de l'API."""
        await self._conn.execute("""
            INSERT INTO api_usage (api_key, requests_used, requests_remaining)
            VALUES (?, ?, ?)
        """, (api_key[:8] + "...", used, remaining))
        await self._conn.commit()
    
    async def get_api_usage(self, limit: int = 100) -> list[dict]:
        """Récupère l'historique d'usage API."""
        cursor = await self._conn.execute("""
            SELECT * FROM api_usage ORDER BY timestamp DESC LIMIT ?
        """, (limit,))
        rows = await cursor.fetchall()
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    # === LOGS ===
    
    async def add_log(self, level: str, message: str):
        """Ajoute un log."""
        await self._conn.execute("""
            INSERT INTO logs (level, message) VALUES (?, ?)
        """, (level, message))
        await self._conn.commit()
    
    async def get_logs(self, limit: int = 100, level: str = None) -> list[dict]:
        """Récupère les logs."""
        query = "SELECT * FROM logs"
        params = []
        
        if level:
            query += " WHERE level = ?"
            params.append(level)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor = await self._conn.execute(query, params)
        rows = await cursor.fetchall()
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    # === RAW ODDS (Données brutes pour analyse) ===
    
    async def save_raw_odds(self, sport: str, match: str, market: str, 
                            bookmaker: str, outcome: str, odds: float):
        """Enregistre une cote brute."""
        implied_prob = 1 / odds if odds > 0 else 0
        await self._conn.execute("""
            INSERT INTO raw_odds (sport, match, market, bookmaker, outcome, odds, implied_prob)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (sport, match, market, bookmaker, outcome, odds, implied_prob))
    
    async def save_raw_odds_batch(self, odds_list: list[dict]):
        """Enregistre un lot de cotes brutes avec transaction (plus efficace)."""
        if not odds_list:
            return
        
        data = []
        for o in odds_list:
            odds_val = o.get("odds", 0)
            # Validation: ignorer les cotes invalides
            if odds_val <= 0:
                continue
            implied_prob = 1 / odds_val if odds_val > 0 else 0
            data.append((
                o.get("sport", ""),
                o.get("match", ""),
                o.get("market", ""),
                o.get("bookmaker", ""),
                o.get("outcome", ""),
                odds_val,
                implied_prob
            ))
        
        if not data:
            return
        
        try:
            # Utiliser une transaction explicite pour garantir l'intégrité
            await self._conn.execute("BEGIN")
            await self._conn.executemany("""
                INSERT INTO raw_odds (sport, match, market, bookmaker, outcome, odds, implied_prob)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, data)
            await self._conn.commit()
        except Exception as e:
            # Rollback en cas d'erreur
            await self._conn.rollback()
            raise Exception(f"Erreur lors de la sauvegarde batch des cotes: {e}") from e
    
    async def get_raw_odds(self, limit: int = 1000, sport: str = None) -> list[dict]:
        """Récupère les cotes brutes."""
        query = "SELECT * FROM raw_odds"
        params = []
        
        if sport:
            query += " WHERE sport = ?"
            params.append(sport)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor = await self._conn.execute(query, params)
        rows = await cursor.fetchall()
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    # === SCANS (Statistiques de scan) ===
    
    async def save_scan(self, sports_scanned: int, events_found: int, 
                        surebets_found: int, api_key: str, requests_remaining: int):
        """Enregistre les statistiques d'un scan."""
        await self._conn.execute("""
            INSERT INTO scans (sports_scanned, events_found, surebets_found, api_key, requests_remaining)
            VALUES (?, ?, ?, ?, ?)
        """, (sports_scanned, events_found, surebets_found, api_key[:8] + "..." if api_key else None, requests_remaining))
        await self._conn.commit()
    
    async def get_scans(self, limit: int = 100) -> list[dict]:
        """Récupère l'historique des scans."""
        cursor = await self._conn.execute("""
            SELECT * FROM scans ORDER BY timestamp DESC LIMIT ?
        """, (limit,))
        rows = await cursor.fetchall()
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in rows]


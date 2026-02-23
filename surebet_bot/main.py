#!/usr/bin/env python3
"""
BOT SUREBET VDO GROUP
=====================
Point d'entrée principal du bot.

Usage:
    python main.py              # Démarre le bot
    python main.py --dashboard  # Démarre le dashboard seul
"""

import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime

# Setup path
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    API_KEYS_FILE, DB_FILE, LOG_FILE,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    SCAN_INTERVAL, REQUEST_DELAY, COOLDOWN_MINUTES, BOOKMAKERS,
    FOOTBALL_LEAGUES, BASKETBALL_LEAGUES, TENNIS_TOURNAMENTS, NFL_LEAGUES
)
from core.api_manager import APIManager
from core.scanner import SurebetScanner
from notifications.telegram_bot import TelegramBot
from data.database import Database
from utils.logger import setup_logger


async def run_bot():
    """Fonction principale du bot."""
    
    # Setup logger
    logger = setup_logger(LOG_FILE)
    logger.info("=" * 50)
    logger.info("Démarrage du Bot Surebet VDO Group")
    logger.info("=" * 50)
    
    # Initialiser les composants
    api_manager = APIManager(API_KEYS_FILE, auto_generate=True)
    telegram = TelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    db = Database(DB_FILE)
    
    # Charger les clés API
    keys_count = api_manager.load_keys()
    logger.info(f"Clés API chargées: {keys_count}")
    
    if keys_count == 0:
        logger.error("Aucune clé API trouvée!")
        logger.info("Génération d'une nouvelle clé...")
        
        success = await api_manager.generate_new_key()
        if not success:
            logger.error("Impossible de générer une clé API")
            await telegram.send_error("Aucune clé API disponible!")
            return 1
        
        api_manager.load_keys()
    
    # Connecter la DB
    await db.connect()
    logger.info("Base de données connectée")
    
    # Créer le scanner
    scanner = SurebetScanner(
        api_manager=api_manager,
        telegram=telegram,
        database=db,  # Passer la DB pour sauvegarder les surebets
        scan_interval=SCAN_INTERVAL,
        cooldown_minutes=COOLDOWN_MINUTES,
        bookmakers=BOOKMAKERS,
        request_delay=REQUEST_DELAY
    )
    
    # Sports à scanner (commencer par les plus actifs)
    sports = {
        **FOOTBALL_LEAGUES,
        **BASKETBALL_LEAGUES,
    }
    
    logger.info(f"Sports configurés: {len(sports)}")
    logger.info(f"Bookmakers: {', '.join(BOOKMAKERS)}")
    logger.info(f"Scan interval: {SCAN_INTERVAL}s")
    
    try:
        # Démarrer le scan
        await scanner.run(sports)
    except KeyboardInterrupt:
        logger.info("Arrêt demandé par l'utilisateur")
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        await telegram.send_error(str(e))
    finally:
        await scanner.stop()
        await db.close()
        await telegram.close()
        logger.info("Bot arrêté proprement")
    
    return 0


def run_dashboard():
    """Lance le dashboard Streamlit."""
    import subprocess
    
    dashboard_path = Path(__file__).parent / "dashboard" / "app.py"
    
    print("Démarrage du Dashboard Streamlit...")
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        str(dashboard_path),
        "--server.port", "8501",
        "--server.address", "0.0.0.0"
    ])


def main():
    parser = argparse.ArgumentParser(description="Bot Surebet VDO Group")
    parser.add_argument("--dashboard", action="store_true", help="Lancer le dashboard seul")
    parser.add_argument("--test", action="store_true", help="Mode test (un seul scan)")
    
    args = parser.parse_args()
    
    if args.dashboard:
        run_dashboard()
    else:
        return asyncio.run(run_bot())


if __name__ == "__main__":
    sys.exit(main() or 0)

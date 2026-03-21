# Bot Telegram pour les alertes Surebet

import aiohttp
from typing import Optional


class TelegramBot:
    """Bot Telegram pour envoyer les alertes Surebet.
    
    Supporte aussi la réception de commandes (/stop, /status).
    """
    
    API_URL = "https://api.telegram.org/bot{token}/{method}"
    
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self._session: Optional[aiohttp.ClientSession] = None
        self._last_update_id = 0  # Pour le polling des messages
        self._stop_callback = None  # Callback pour arrêter le scanner
        self._status_callback = None  # Callback pour obtenir le status
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Retourne ou crée une session HTTP."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Ferme la session HTTP."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _call(self, method: str, data: dict) -> bool:
        """Appelle l'API Telegram."""
        session = await self._get_session()
        url = self.API_URL.format(token=self.token, method=method)
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with session.post(url, data=data, timeout=timeout) as resp:
                return resp.status == 200
        except Exception as e:
            print(f"[Telegram] ❌ Erreur appel API ({method}): {e}")
            return False
    
    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Envoie un message texte."""
        return await self._call("sendMessage", {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode
        })
    
    async def send_surebet_alert(
        self,
        sport: str,
        league: str,
        match: str,
        market: str,
        outcomes: list[dict],
        profit_pct: float,
        profit_base_100: float,
        stakes: list[float],
        detected_at: str = None
    ) -> bool:
        """Envoie une alerte Surebet avec liens bookmakers, mise totale et horodatage."""
        from datetime import datetime
        from constants import BOOKMAKER_URLS

        ts = detected_at or datetime.now().strftime("%H:%M:%S")
        mise_totale = sum(stakes)

        lines = [
            f"⚡ <b>SUREBET</b> — {league}",
            f"⚽ <b>{match}</b>  |  {market}",
            "",
        ]

        for i, outcome in enumerate(outcomes):
            stake = stakes[i] if i < len(stakes) else 0
            bk = outcome['bookmaker']
            url = BOOKMAKER_URLS.get(bk, "")
            bk_link = f'<a href="{url}">{bk}</a>' if url else f"<b>{bk}</b>"
            lines.append(
                f"🎯 {bk_link}  →  <b>{outcome['name']}</b>  @  "
                f"<code>{outcome['odds']:.2f}</code>  |  <code>{stake:.2f}€</code>"
            )

        lines.extend([
            "",
            f"💵 Mise totale : <code>{mise_totale:.2f}€</code>",
            f"📈 Profit : <code>+{profit_pct:.2f}%</code>  |  "
            f"Gain : <code>+{profit_base_100:.2f}€</code>  |  "
            f"Retour : <code>{100 + profit_base_100:.2f}€</code>",
            "",
        ])

        # Liens rapides cliquables vers chaque bookmaker
        links = []
        seen = set()
        for outcome in outcomes:
            bk = outcome['bookmaker']
            if bk not in seen:
                seen.add(bk)
                url = BOOKMAKER_URLS.get(bk, "")
                if url:
                    links.append(f'<a href="{url}">{bk} ↗</a>')
        if links:
            lines.append("  ".join(links))

        lines.append(f"⏱ <i>{ts}</i>")

        return await self.send_message("\n".join(lines))
    
    async def send_value_bet_alert(
        self,
        sport: str,
        league: str,
        match: str,
        market: str,
        outcome: str,
        bookmaker: str,
        odds: float,
        consensus_prob: float,
        value_pct: float,
        bookmakers_count: int,
        detected_at: str = None
    ) -> bool:
        """Envoie une alerte Value Bet sur Telegram."""
        from datetime import datetime
        from constants import BOOKMAKER_URLS

        ts = detected_at or datetime.now().strftime("%H:%M:%S")
        url = BOOKMAKER_URLS.get(bookmaker, "")
        bk_link = f'<a href="{url}">{bookmaker}</a>' if url else f"<b>{bookmaker}</b>"
        fair_odds = round(1 / consensus_prob, 2) if consensus_prob > 0 else 0

        lines = [
            f"📊 <b>VALUE BET</b> — {league}",
            f"⚽ <b>{match}</b>  |  {market}",
            "",
            f"🎯 Sélection : <b>{outcome}</b>",
            f"📌 Bookmaker : {bk_link}",
            f"💰 Cote affichée : <code>{odds:.2f}</code>",
            f"📐 Cote juste (consensus) : <code>{fair_odds:.2f}</code>",
            f"📊 Consensus sur <code>{bookmakers_count}</code> bookmakers",
            "",
            f"✅ Value : <code>+{value_pct:.1f}%</code>",
            "",
            f"⏱ <i>{ts}</i>",
        ]
        return await self.send_message("\n".join(lines))

    async def send_status(self, status: dict) -> bool:
        """Envoie un rapport de status."""
        lines = [
            "📊 <b>STATUS BOT SUREBET</b>",
            "━━━━━━━━━━━━━━━━━━━━━━━━",
            f"⏱ Uptime: {status.get('uptime', 'N/A')}",
            f"🔑 Clé API: {status.get('api_key', 'N/A')}",
            f"📡 Requêtes restantes: {status.get('requests_remaining', 'N/A')}",
            f"🎯 Surebets détectés: {status.get('surebets_count', 0)}",
            f"📈 Profit total: {status.get('total_profit', 0):.2f}%",
            "━━━━━━━━━━━━━━━━━━━━━━━━",
            "<b>VDO Group</b>"
        ]
        return await self.send_message("\n".join(lines))
    
    async def send_error(self, error: str) -> bool:
        """Envoie une alerte d'erreur."""
        return await self.send_message(f"⚠️ <b>ERREUR BOT</b>\n\n{error}")
    
    async def send_api_warning(self, requests_remaining: int, current_key: str) -> bool:
        """Alerte quota API bas."""
        return await self.send_message(
            f"⚠️ <b>QUOTA API BAS</b>\n\n"
            f"🔑 Clé: {current_key[:8]}...\n"
            f"📡 Restant: {requests_remaining} requêtes"
        )
    
    async def send_failover_notice(self, old_key: str, new_key: str) -> bool:
        """Notification de basculement de clé."""
        return await self.send_message(
            f"🔄 <b>CHANGEMENT DE CLÉ API</b>\n\n"
            f"❌ Ancienne: {old_key[:8]}...\n"
            f"✅ Nouvelle: {new_key[:8]}..."
        )
    
    # === COMMANDES ===
    
    def set_callbacks(self, stop_callback=None, status_callback=None):
        """Définit les callbacks pour les commandes."""
        self._stop_callback = stop_callback
        self._status_callback = status_callback
    
    async def check_commands(self) -> list[str]:
        """
        Vérifie les nouvelles commandes reçues.
        
        Returns:
            Liste des commandes reçues (ex: ["/stop", "/status"])
        """
        session = await self._get_session()
        url = self.API_URL.format(token=self.token, method="getUpdates")
        
        commands = []
        
        try:
            params = {
                "offset": self._last_update_id + 1,
                "timeout": 0,  # Non-bloquant
                "allowed_updates": ["message"]
            }
            
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    for update in data.get("result", []):
                        self._last_update_id = update.get("update_id", self._last_update_id)
                        
                        message = update.get("message", {})
                        text = message.get("text", "")
                        chat_id = str(message.get("chat", {}).get("id", ""))
                        
                        # Vérifier que c'est bien notre chat
                        if chat_id == self.chat_id and text.startswith("/"):
                            commands.append(text.lower().strip())
        except Exception as e:
            print(f"[Telegram] Erreur check_commands: {e}")
        
        return commands
    
    async def handle_commands(self):
        """
        Vérifie et exécute les commandes reçues.
        
        Commandes supportées:
        - /stop : Arrête le bot
        - /status : Affiche le status
        """
        commands = await self.check_commands()
        
        for cmd in commands:
            if cmd == "/stop":
                await self.send_message("⛔ Commande /stop reçue. Arrêt en cours...")
                if self._stop_callback:
                    self._stop_callback()
            
            elif cmd == "/status":
                if self._status_callback:
                    status = self._status_callback()
                    await self.send_status(status)
                else:
                    await self.send_message("📊 Status non disponible")
            
            elif cmd == "/help":
                await self.send_message(
                    "📖 <b>Commandes disponibles</b>\n\n"
                    "/stop - Arrête le bot\n"
                    "/status - Affiche le status du bot\n"
                    "/help - Affiche cette aide"
                )


# === TEST ===
if __name__ == "__main__":
    import asyncio
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    async def test():
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        if not token or not chat_id:
            print("ERREUR: TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID doivent être définis")
            return
        
        bot = TelegramBot(
            token=token,
            chat_id=chat_id
        )
        
        # Test alerte
        success = await bot.send_surebet_alert(
            sport="Football",
            league="Ligue 1",
            match="PSG vs Marseille",
            market="Tirs cadrés Over/Under",
            outcomes=[
                {"bookmaker": "Betclic", "name": "Over 10.5", "odds": 1.85},
                {"bookmaker": "Winamax", "name": "Under 10.5", "odds": 2.20}
            ],
            profit_pct=2.34,
            profit_base_100=2.34,
            stakes=[54.05, 45.95]
        )
        
        print(f"Message envoyé: {success}")
        await bot.close()
    
    asyncio.run(test())

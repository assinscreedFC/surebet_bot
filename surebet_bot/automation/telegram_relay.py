"""
Telegram Relay — Communication synchrone (requests)
====================================================
Envoi de messages, photos et récupération de commandes
via l'API Telegram Bot.
"""

import os
import time
import requests


def send_telegram_message(bot_token: str, chat_id: str, message: str) -> bool:
    """Envoie un message texte sur Telegram."""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        response = requests.post(url, data={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"[TELEGRAM] ❌ Erreur envoi message: {e}")
        return False


def send_telegram_photo(bot_token: str, chat_id: str, image_path: str, caption: str = "") -> bool:
    """
    Envoie une capture d'écran sur Telegram.
    
    Essaie d'abord en tant que photo, puis en tant que document
    si l'image est trop grande (>10MB).
    """
    try:
        if not os.path.exists(image_path):
            print(f"[TELEGRAM] ❌ Fichier non trouvé: {image_path}")
            return False

        file_size = os.path.getsize(image_path)
        if file_size == 0:
            print(f"[TELEGRAM] ❌ Fichier vide: {image_path}")
            return False

        # Tronquer le caption si trop long (limite Telegram: 1024 chars pour photos)
        if len(caption) > 1024:
            caption = caption[:1020] + "..."

        # Essayer d'envoyer comme photo d'abord (< 10 MB)
        if file_size < 10 * 1024 * 1024:
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            with open(image_path, "rb") as photo:
                response = requests.post(url, data={
                    "chat_id": chat_id,
                    "caption": caption,
                    "parse_mode": "HTML"
                }, files={"photo": photo}, timeout=30)

            if response.status_code == 200:
                return True
            
            print(f"[TELEGRAM] ⚠️ Envoi photo échoué ({response.status_code}), tentative document...")

        # Fallback: envoyer comme document (supporte fichiers plus gros)
        url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
        with open(image_path, "rb") as doc:
            response = requests.post(url, data={
                "chat_id": chat_id,
                "caption": caption,
                "parse_mode": "HTML"
            }, files={"document": doc}, timeout=60)

        if response.status_code == 200:
            return True

        print(f"[TELEGRAM] ❌ Envoi document échoué: {response.status_code}")
        return False

    except Exception as e:
        print(f"[TELEGRAM] ❌ Exception envoi photo: {e}")
        return False


def send_telegram_audio(bot_token: str, chat_id: str, audio_path: str, title: str = "Audio") -> bool:
    """Envoie un fichier audio sur Telegram."""
    try:
        if not os.path.exists(audio_path):
            return False

        url = f"https://api.telegram.org/bot{bot_token}/sendAudio"
        with open(audio_path, "rb") as audio:
            response = requests.post(url, data={
                "chat_id": chat_id,
                "title": title
            }, files={"audio": audio}, timeout=30)

        return response.status_code == 200
    except Exception as e:
        print(f"[TELEGRAM] ❌ Exception envoi audio: {e}")
        return False


def get_telegram_messages(bot_token: str, chat_id: str, last_update_id: int = 0) -> list[dict]:
    """
    Récupère les nouveaux messages Telegram.
    
    Returns:
        Liste de dicts avec: update_id, text, from
    """
    try:
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        response = requests.get(url, params={
            "offset": last_update_id + 1,
            "timeout": 1,
            "allowed_updates": ["message"]
        }, timeout=5)

        if response.status_code != 200:
            return []

        data = response.json()
        messages = []

        for update in data.get("result", []):
            msg = update.get("message", {})
            msg_chat_id = str(msg.get("chat", {}).get("id", ""))

            if msg_chat_id == chat_id:
                messages.append({
                    "update_id": update.get("update_id", 0),
                    "text": msg.get("text", ""),
                    "from": msg.get("from", {}).get("username", "Unknown")
                })

        return messages

    except Exception as e:
        print(f"[TELEGRAM] Erreur récupération messages: {e}")
        return []


def check_telegram_bot(bot_token: str) -> bool:
    """Vérifie que le bot Telegram est accessible."""
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getMe",
            timeout=5
        )
        return r.status_code == 200
    except Exception:
        return False

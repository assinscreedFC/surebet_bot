#!/usr/bin/env python3
"""
AUTOMATISATION COMPLÈTE - THE ODDS API (GRATUIT)
=================================================
Orchestrateur principal: coordonne l'inscription automatique
sur The Odds API via Mail.tm + relay captcha Telegram.

Modules:
  automation/telegram_relay  - Communication Telegram
  automation/mail_tm         - Emails temporaires
  automation/captcha_handler - Résolution captcha
  automation/registration    - Inscription site web
"""

import sys
import os
import time
import threading
import traceback
from pathlib import Path

# Répertoire du script
SCRIPT_DIR = Path(__file__).resolve().parent

# Charger .env
try:
    from dotenv import load_dotenv
    load_dotenv(SCRIPT_DIR / ".env")
    load_dotenv()
except ImportError:
    pass

# Configuration Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("[ERREUR] Variables Telegram manquantes.")
    print("  TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID dans .env")
    sys.exit(1)

# Imports des modules
from automation.telegram_relay import (
    send_telegram_message,
    get_telegram_messages,
    check_telegram_bot,
)
from automation.mail_tm import create_mail_tm_account, get_api_key_from_email
from automation.registration import register_odds_api, generate_random_name


# ============================================
# État global
# ============================================
_registration_state = {
    "running": False,
    "name": None,
    "email": None,
}


def print_banner():
    print("\n" + "=" * 60)
    print("   AUTOMATISATION COMPLÈTE - THE ODDS API")
    print("   Mail.tm + Telegram Relay (GRATUIT)")
    print("=" * 60 + "\n")


# ============================================
# Processus d'inscription
# ============================================
def run_registration_process(name: str = None):
    """Lance le processus complet d'inscription."""
    global _registration_state

    try:
        _registration_state["running"] = True

        if not name:
            name = generate_random_name()
            print(f"[INFO] Nom généré: {name}")

        _registration_state["name"] = name

        # Test Telegram
        print("[INFO] Test connexion Telegram...")
        if send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, "🤖 Script démarré!"):
            print("[SUCCESS] Telegram OK")
        else:
            print("[WARN] Telegram non disponible")

        # Étape 1: Créer email temporaire
        email, token = create_mail_tm_account()
        if not email:
            send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
                                  "❌ Échec création email temporaire")
            _registration_state["running"] = False
            return

        _registration_state["email"] = email
        send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
                              f"📧 Email créé: <code>{email}</code>")

        # Étape 2: Inscription
        if not register_odds_api(name, email, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID):
            send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
                                  "❌ Échec inscription")
            _registration_state["running"] = False
            return

        # Étape 3: Récupérer la clé API
        def on_status(msg):
            send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, msg)

        api_key = get_api_key_from_email(token, on_status=on_status)

        if api_key:
            keys_file = SCRIPT_DIR / "api_keys.txt"
            with open(keys_file, "a", encoding="utf-8") as f:
                f.write(f"{email}:{api_key}\n")
            print(f"[INFO] Clé sauvegardée dans api_keys.txt")

            send_telegram_message(
                TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
                f"✅ <b>INSCRIPTION RÉUSSIE!</b>\n\n"
                f"🔑 Clé: <code>{api_key}</code>\n"
                f"📧 Email: <code>{email}</code>\n\n"
                f"💾 Sauvegardée dans api_keys.txt"
            )

    except Exception as e:
        print(f"[ERREUR] Inscription: {e}")
        traceback.print_exc()
        send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
                              f"❌ <b>ERREUR</b>\n\n{str(e)}")
    finally:
        _registration_state["running"] = False


# ============================================
# Commandes Telegram (thread)
# ============================================
def check_telegram_commands():
    """Vérifie les commandes Telegram en continu (thread daemon)."""
    last_update_id = 0
    processed = set()

    while True:
        try:
            messages = get_telegram_messages(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, last_update_id)

            for msg in messages:
                uid = msg["update_id"]
                last_update_id = max(last_update_id, uid)
                text = msg["text"].strip().lower()

                key = f"{uid}_{text}"
                if key in processed:
                    continue
                processed.add(key)

                if len(processed) > 100:
                    processed = set(list(processed)[-50:])

                if text == "/launch":
                    if _registration_state.get("running"):
                        send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
                                              "⚠️ Processus déjà en cours")
                    else:
                        send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
                                              "🚀 Lancement inscription...")
                        _registration_state["running"] = True
                        threading.Thread(
                            target=run_registration_process,
                            args=(_registration_state.get("name"),),
                            daemon=True
                        ).start()

                elif text == "/status":
                    running = _registration_state.get("running")
                    name = _registration_state.get("name", "N/A")
                    email = _registration_state.get("email", "N/A")
                    status = "🔄 En cours" if running else "⏸️ Arrêté"
                    send_telegram_message(
                        TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
                        f"📊 <b>STATUS</b>\n\n"
                        f"{status}\n👤 {name}\n📧 {email}"
                    )

                elif text == "/help":
                    send_telegram_message(
                        TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
                        "📖 <b>Commandes</b>\n\n"
                        "/launch - Lancer l'inscription\n"
                        "/status - Status actuel\n"
                        "/help - Cette aide"
                    )

            time.sleep(2)

        except Exception as e:
            print(f"[COMMANDE] Erreur: {e}")
            time.sleep(5)


# ============================================
# MAIN
# ============================================
def main():
    # Mode vérification rapide
    if "--check" in sys.argv or "-c" in sys.argv:
        print_banner()
        print("[CHECK] Vérification...")

        ok = True
        if check_telegram_bot(TELEGRAM_BOT_TOKEN):
            print("  [OK] Connexion Telegram")
        else:
            print("  [X] Connexion Telegram échouée")
            ok = False

        name = generate_random_name()
        print(f"  [OK] Nom généré: {name}")
        print(f"  [INFO] .env: {SCRIPT_DIR / '.env'} (existe: {(SCRIPT_DIR / '.env').exists()})")

        print("\n" + ("[CHECK] Tout OK!" if ok else "[CHECK] Erreurs détectées"))
        return 0 if ok else 1

    print_banner()

    # Démarrer le thread de commandes Telegram
    print("[INFO] Démarrage système commandes Telegram...")
    threading.Thread(target=check_telegram_commands, daemon=True).start()
    print("[SUCCESS] Système de commandes démarré")

    send_telegram_message(
        TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
        "🤖 <b>Bot inscription démarré!</b>\n\n"
        "/launch - Lancer l'inscription\n"
        "/status - Status\n"
        "/help - Aide"
    )

    # Nom fourni en argument ou généré
    name = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else generate_random_name()
    print(f"[INFO] Nom: {name}")

    # Lancer le processus
    run_registration_process(name)

    # Écouter les commandes (boucle infinie)
    print("[INFO] Écoute des commandes... Ctrl+C pour arrêter.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INFO] Arrêt")
        send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, "⛔ Bot arrêté")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERREUR FATALE] {e}")
        traceback.print_exc()
        sys.exit(1)

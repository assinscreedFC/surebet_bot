"""
Registration — Inscription sur The Odds API
=============================================
Génération de noms aléatoires et inscription automatisée
sur the-odds-api.com via Scrapling (navigateur stealth).
"""

import os
import time
import random
import tempfile
import uuid

from automation.telegram_relay import send_telegram_message
from automation.captcha_handler import (
    is_captcha_solved,
    wait_for_captcha_with_telegram,
)

# Noms réalistes via Faker si disponible
try:
    from faker import Faker
    _fake = Faker("fr_FR")

    def generate_random_name() -> str:
        return _fake.name()
except ImportError:
    FIRST_NAMES = [
        "James", "John", "Robert", "Michael", "William", "David", "Richard",
        "Joseph", "Thomas", "Charles", "Christopher", "Daniel", "Matthew",
        "Anthony", "Mark", "Mary", "Patricia", "Jennifer", "Linda",
        "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen",
        "Nancy", "Lisa", "Betty", "Margaret", "Sandra", "Ashley",
        "Kimberly", "Emily", "Donna", "Michelle", "Dorothy", "Carol",
    ]
    LAST_NAMES = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
        "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez",
        "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson",
        "Martin", "Lee", "Thompson", "White", "Harris", "Sanchez",
        "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young",
    ]

    def generate_random_name() -> str:
        return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


# URL et sélecteurs
ODDS_API_URL = "https://the-odds-api.com/#get-access"

SELECTORS = {
    "start_button": ".oa-button",
    "name_input": 'input[name="name"]',
    "email_input": 'input[name="email"]',
    "captcha_iframe": 'iframe[title="reCAPTCHA"]',
    "subscribe_button": "input.subscribe",
}


def register_odds_api(
    name: str,
    email: str,
    bot_token: str,
    chat_id: str,
) -> bool:
    """
    S'inscrit sur the-odds-api.com avec relay Telegram pour le captcha.
    
    Args:
        name: Nom pour l'inscription
        email: Email pour l'inscription
        bot_token: Token bot Telegram
        chat_id: Chat ID Telegram
    
    Returns:
        True si inscription réussie
    """
    try:
        from scrapling import StealthyFetcher
    except ImportError:
        print("[ERREUR] Module 'scrapling' requis: pip install scrapling")
        return False

    success = False
    user_data_dir = os.path.join(tempfile.gettempdir(), f"odds_api_{uuid.uuid4().hex[:8]}")

    def register_action(page):
        nonlocal success

        print("\n[ÉTAPE 2] Inscription sur the-odds-api.com")
        print("-" * 50)

        send_telegram_message(
            bot_token, chat_id,
            f"🚀 <b>Inscription en cours</b>\n\n"
            f"📧 Email: {email}\n"
            f"👤 Nom: {name}\n\n"
            f"⏳ Remplissage du formulaire..."
        )

        time.sleep(2)

        # Cliquer sur le bouton START
        print("[INFO] Clic sur START...")
        page.click(SELECTORS["start_button"])
        time.sleep(2)

        # Remplir le formulaire
        print(f"[INFO] Remplissage - Nom: {name}, Email: {email}")
        page.fill(SELECTORS["name_input"], name)
        time.sleep(0.5)
        page.fill(SELECTORS["email_input"], email)
        time.sleep(1)

        # Cliquer sur la zone captcha pour déclencher
        try:
            captcha = page.locator(SELECTORS["captcha_iframe"])
            if captcha.is_visible():
                box = captcha.bounding_box()
                if box:
                    x = box["x"] + box["width"] / 2
                    y = box["y"] + box["height"] / 2
                    print(f"[INFO] Clic captcha ({x:.0f}, {y:.0f})")
                    page.mouse.click(x, y)
                    time.sleep(3)
        except Exception as e:
            print(f"[DEBUG] Clic captcha: {e}")

        # Vérifier si captcha auto-résolu
        time.sleep(2)
        if is_captcha_solved(page):
            print("[SUCCESS] Captcha auto-résolu!")
            send_telegram_message(bot_token, chat_id, "✅ Captcha auto-résolu!")
        else:
            # Attendre résolution via Telegram (10 minutes)
            if not wait_for_captcha_with_telegram(page, bot_token, chat_id, timeout=600):
                return

        # Soumettre le formulaire
        print("[INFO] Soumission...")
        page.click(SELECTORS["subscribe_button"])
        time.sleep(5)

        send_telegram_message(bot_token, chat_id, "✅ Formulaire soumis!")
        print("[SUCCESS] Formulaire soumis!")
        success = True

    fetcher = StealthyFetcher()
    try:
        fetcher.fetch(
            ODDS_API_URL,
            headless=False,  # Visible pour résolution manuelle
            page_action=register_action,
            wait=10000,
            user_data_dir=user_data_dir
        )
    except Exception as e:
        print(f"[ERREUR] Fetcher: {e}")
        import traceback
        traceback.print_exc()
        success = False

    return success

"""
Registration — Inscription sur The Odds API
=============================================
Génération de noms aléatoires et inscription automatisée
sur the-odds-api.com via Scrapling (navigateur stealth).

Utilise le profil Firefox persistant + warm-up + résolution
captcha autonome (audio → Whisper API → LLM).
"""

import os
import time
import random
import traceback

from automation.telegram_relay import send_telegram_message
from automation.captcha_handler import (
    is_captcha_solved,
    solve_captcha_autonomous,
    extract_recaptcha_token,
    wait_for_captcha_with_telegram,
)
from automation.browser_storage import (
    sync_chrome_profile,
    warm_up_browser,
    get_stealth_config,
    FIREFOX_HEADERS,
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
    S'inscrit sur the-odds-api.com avec :
    - Profil Firefox persistant (session réelle)
    - Warm-up navigateur (cookies Google)
    - Résolution captcha autonome (audio → Whisper → LLM)
    - Fallback relay Telegram si échec autonome

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

    # Synchroniser le profil Chrome/Edge réel
    print("[INFO] Synchronisation du profil Chrome...")
    profile_dir = sync_chrome_profile()
    stealth_config = get_stealth_config()

    def register_action(page):
        nonlocal success

        # ── Phase 1: Warm-up ──────────────────────────
        print("\n[PHASE 1] Warm-up navigateur")
        print("-" * 50)
        send_telegram_message(
            bot_token, chat_id,
            "🌐 <b>Warm-up en cours</b>\n\n"
            "Navigation sur sites à fort trafic pour\n"
            "bâtir un score de confiance Google..."
        )
        warm_up_browser(page)

        # ── Phase 2: Navigation cible ─────────────────
        print("\n[PHASE 2] Inscription sur the-odds-api.com")
        print("-" * 50)

        send_telegram_message(
            bot_token, chat_id,
            f"🚀 <b>Inscription en cours</b>\n\n"
            f"📧 Email: {email}\n"
            f"👤 Nom: {name}\n\n"
            f"⏳ Remplissage du formulaire..."
        )

        page.wait_for_timeout(2000)

        # Cliquer sur le bouton START
        print("[INFO] Clic sur START...")
        page.click(SELECTORS["start_button"])
        page.wait_for_timeout(2000)

        # Remplir le formulaire
        print(f"[INFO] Remplissage - Nom: {name}, Email: {email}")
        page.fill(SELECTORS["name_input"], name)
        page.wait_for_timeout(500)
        page.fill(SELECTORS["email_input"], email)
        page.wait_for_timeout(1000)

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
                    page.wait_for_timeout(3000)
        except Exception as e:
            print(f"[DEBUG] Clic captcha: {e}")

        # ── Phase 3-5: Résolution captcha ─────────────
        page.wait_for_timeout(2000)
        if is_captcha_solved(page):
            print("[SUCCESS] Captcha auto-résolu!")
            send_telegram_message(bot_token, chat_id, "✅ Captcha auto-résolu!")
        else:
            # Tenter la résolution autonome (audio → Whisper → LLM)
            send_telegram_message(
                bot_token, chat_id,
                "🤖 <b>Résolution autonome</b>\n\n"
                "Audio → Whisper API → LLM correction..."
            )

            if solve_captcha_autonomous(page, max_retries=3):
                send_telegram_message(bot_token, chat_id, "✅ Captcha résolu (autonome)!")
            else:
                # Fallback: relay Telegram (résolution manuelle)
                send_telegram_message(
                    bot_token, chat_id,
                    "⚠️ <b>Échec autonome</b>\n\n"
                    "Basculement en mode manuel Telegram..."
                )
                if not wait_for_captcha_with_telegram(page, bot_token, chat_id, timeout=600):
                    return

        # ── Phase 5: Extraction du token ──────────────
        token = extract_recaptcha_token(page)
        if token:
            print(f"[INFO] Token reCAPTCHA: {token[:40]}...")

        # ── Phase 6: Soumission du formulaire ─────────
        print("[INFO] Soumission...")
        page.click(SELECTORS["subscribe_button"])
        page.wait_for_timeout(5000)

        send_telegram_message(bot_token, chat_id, "✅ Formulaire soumis!")
        print("[SUCCESS] Formulaire soumis!")
        success = True

    try:
        StealthyFetcher.fetch(
            ODDS_API_URL,
            headless=stealth_config.get("headless", False),
            real_chrome=stealth_config.get("real_chrome", True),
            additional_args=stealth_config.get("additional_args"),
            page_action=register_action,
            wait=10000,
            user_data_dir=stealth_config.get("user_data_dir"),
        )
    except Exception as e:
        print(f"[ERREUR] Fetcher: {e}")
        traceback.print_exc()
        success = False

    return success

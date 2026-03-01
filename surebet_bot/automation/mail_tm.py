"""
Mail.tm — Gestion d'emails temporaires
=======================================
Création de comptes email jetables et récupération
de la clé API The Odds API depuis les emails reçus.
"""

import re
import time
import random
import string
import requests


MAIL_TM_API = "https://api.mail.tm"


def get_mail_tm_domains() -> str | None:
    """Récupère un domaine disponible sur Mail.tm."""
    try:
        response = requests.get(f"{MAIL_TM_API}/domains", timeout=10)
        if response.status_code == 200:
            data = response.json()
            members = data.get("hydra:member", [])
            if members:
                return members[0]["domain"]
    except Exception as e:
        print(f"[MAIL.TM] Erreur domaines: {e}")
    return None


def create_mail_tm_account() -> tuple[str | None, str | None]:
    """
    Crée un email temporaire via Mail.tm API.
    
    Returns:
        (email, token) ou (None, None) en cas d'échec
    """
    print("\n[ÉTAPE 1] Création email temporaire (Mail.tm)")
    print("-" * 50)

    domain = get_mail_tm_domains()
    if not domain:
        print("[ERREUR] Domaine Mail.tm non disponible")
        return None, None

    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
    email = f"{username}@{domain}"
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=16))

    try:
        # Créer le compte
        response = requests.post(
            f"{MAIL_TM_API}/accounts",
            json={"address": email, "password": password},
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code not in [200, 201]:
            print(f"[ERREUR] Création compte: {response.status_code}")
            return None, None

        print(f"[SUCCESS] Email créé: {email}")

        # Obtenir le token d'authentification
        token_response = requests.post(
            f"{MAIL_TM_API}/token",
            json={"address": email, "password": password},
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if token_response.status_code == 200:
            token = token_response.json().get("token")
            return email, token

        print(f"[ERREUR] Token: {token_response.status_code}")

    except Exception as e:
        print(f"[ERREUR] Mail.tm: {e}")

    return None, None


def get_api_key_from_email(
    token: str,
    max_wait: int = 300,
    on_status=None,
    page=None
) -> str | None:
    """
    Récupère la clé API The Odds API depuis l'email reçu.
    
    Args:
        token: Token d'auth Mail.tm
        max_wait: Temps max d'attente en secondes (défaut: 5 min)
        on_status: Callback optionnel fn(message) pour notifier la progression
    
    Returns:
        Clé API (32 chars hex) ou None
    """
    print("\n[ÉTAPE 3] Récupération clé API (Mail.tm)")
    print("-" * 50)

    if on_status:
        on_status("📧 En attente de l'email avec la clé API...")

    headers = {"Authorization": f"Bearer {token}"}
    start_time = time.time()

    while time.time() - start_time < max_wait:
        elapsed = int(time.time() - start_time)
        print(f"[INFO] Vérification emails... ({elapsed}s/{max_wait}s)")

        try:
            response = requests.get(
                f"{MAIL_TM_API}/messages",
                headers=headers,
                timeout=10
            )

            if response.status_code != 200:
                if page:
                    page.wait_for_timeout(10000)
                else:
                    time.sleep(10)
                continue

            messages = response.json().get("hydra:member", [])

            for msg in messages:
                subject = msg.get("subject", "").lower()
                sender = msg.get("from", {}).get("address", "").lower()

                # Chercher un email de The Odds API
                if "odds" in subject or "odds" in sender or "api" in subject:
                    print("[SUCCESS] Email trouvé!")

                    msg_response = requests.get(
                        f"{MAIL_TM_API}/messages/{msg.get('id')}",
                        headers=headers,
                        timeout=10
                    )

                    if msg_response.status_code != 200:
                        continue

                    msg_data = msg_response.json()
                    content = msg_data.get("text", "")
                    html_parts = msg_data.get("html", [""])
                    html = html_parts[0] if html_parts else ""

                    # Chercher une clé API (32 chars hex)
                    match = re.search(r'([a-f0-9]{32})', content + html)
                    if match:
                        api_key = match.group(1)

                        if on_status:
                            on_status(
                                f"🎉 <b>CLÉ API RÉCUPÉRÉE!</b>\n\n"
                                f"🔑 <code>{api_key}</code>\n\n"
                                f"Sauvegardée dans api_keys.txt"
                            )

                        print(f"\n{'=' * 60}")
                        print(f"   🎉 CLÉ API: {api_key}")
                        print(f"{'=' * 60}\n")
                        return api_key

        except Exception as e:
            print(f"[DEBUG] Erreur vérification emails: {e}")

        if page:
            page.wait_for_timeout(10000)
        else:
            time.sleep(10)

    if on_status:
        on_status("❌ Email non reçu après 5 minutes")

    print("[ERREUR] Email non reçu dans le délai imparti")
    return None

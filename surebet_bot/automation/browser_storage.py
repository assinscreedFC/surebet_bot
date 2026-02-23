"""
Browser Storage — Persistance de session Firefox
==================================================
Gère la synchronisation du profil Firefox réel, le warm-up
navigateur pour bâtir un score de confiance Google, et la
configuration stealth cohérente pour StealthyFetcher.
"""

import os
import shutil
import time
import random
from pathlib import Path


# ============================================================
# Chemins
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent.parent
BROWSER_PROFILE_DIR = SCRIPT_DIR / "browser_profile"

# Profil Firefox réel de l'utilisateur (Windows)
_FIREFOX_PROFILES_DIR = Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox" / "Profiles"
_FIREFOX_PROFILE_NAME = "daoionvz.default-release"


# ============================================================
# Gestion du profil
# ============================================================

def ensure_profile_dir() -> Path:
    """Crée le répertoire du profil navigateur s'il n'existe pas."""
    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return BROWSER_PROFILE_DIR


def sync_firefox_profile() -> Path:
    """
    Copie les fichiers critiques du profil Firefox réel
    vers le répertoire dédié à Scrapling.

    Fichiers copiés :
    - cookies.sqlite (cookies)
    - webappsstore.sqlite (localStorage)
    - storage/ (IndexedDB, cache)
    - permissions.sqlite
    - content-prefs.sqlite

    Returns:
        Chemin du profil synchronisé.
    """
    ensure_profile_dir()
    source = _FIREFOX_PROFILES_DIR / _FIREFOX_PROFILE_NAME

    if not source.exists():
        print(f"[STORAGE] ⚠️ Profil Firefox introuvable: {source}")
        print("[STORAGE] Utilisation du profil vierge")
        return BROWSER_PROFILE_DIR

    # Fichiers critiques à copier
    critical_files = [
        "cookies.sqlite",
        "webappsstore.sqlite",
        "permissions.sqlite",
        "content-prefs.sqlite",
        "cert9.db",
        "key4.db",
    ]

    # Dossiers critiques
    critical_dirs = [
        "storage",
    ]

    copied = 0

    for filename in critical_files:
        src = source / filename
        dst = BROWSER_PROFILE_DIR / filename
        if src.exists():
            try:
                shutil.copy2(str(src), str(dst))
                copied += 1
            except (PermissionError, OSError) as e:
                # Firefox peut verrouiller certains fichiers
                print(f"[STORAGE] ⚠️ Copie {filename} échouée: {e}")

    for dirname in critical_dirs:
        src = source / dirname
        dst = BROWSER_PROFILE_DIR / dirname
        if src.exists():
            try:
                if dst.exists():
                    shutil.rmtree(str(dst), ignore_errors=True)
                shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
                copied += 1
            except (PermissionError, OSError) as e:
                print(f"[STORAGE] ⚠️ Copie {dirname}/ échouée: {e}")

    print(f"[STORAGE] ✅ Profil Firefox synchronisé ({copied} éléments)")
    return BROWSER_PROFILE_DIR


# ============================================================
# Warm-up navigateur
# ============================================================

# Sites à fort trafic pour générer des cookies tiers Google
WARMUP_SITES = [
    "https://www.google.com/search?q=weather+today",
    "https://www.youtube.com/",
    "https://en.wikipedia.org/wiki/Main_Page",
    "https://www.reddit.com/",
    "https://stackoverflow.com/questions",
]


def warm_up_browser(page) -> None:
    """
    Effectue une navigation humaine sur des sites à fort trafic
    pour générer des cookies Google tiers et bâtir un score de
    confiance avant d'accéder à la cible.

    Args:
        page: Page Playwright (fournie par StealthyFetcher page_action)
    """
    print("[WARMUP] 🌐 Démarrage du warm-up navigateur...")

    for i, url in enumerate(WARMUP_SITES):
        try:
            print(f"[WARMUP] ({i+1}/{len(WARMUP_SITES)}) {url[:50]}...")
            page.goto(url, wait_until="domcontentloaded", timeout=15000)

            # Délai humain aléatoire
            wait_time = random.uniform(3, 8)
            time.sleep(wait_time)

            # Scrolls aléatoires pour simuler la lecture
            scroll_count = random.randint(1, 3)
            for _ in range(scroll_count):
                scroll_amount = random.randint(200, 600)
                page.evaluate(f"window.scrollBy(0, {scroll_amount})")
                time.sleep(random.uniform(0.5, 1.5))

            # Accepter les cookies Google si présents
            _accept_google_cookies(page)

        except Exception as e:
            print(f"[WARMUP] ⚠️ Erreur sur {url[:40]}: {e}")
            continue

    print("[WARMUP] ✅ Warm-up terminé")


def _accept_google_cookies(page) -> None:
    """Accepte les bannières de cookies Google/YouTube si présentes."""
    consent_selectors = [
        # Google
        'button[id="L2AGLb"]',
        'button:has-text("Accept all")',
        'button:has-text("Tout accepter")',
        # YouTube
        'button[aria-label="Accept all"]',
        'button[aria-label="Tout accepter"]',
        # Générique
        'button:has-text("I agree")',
        'button:has-text("Agree")',
    ]
    for sel in consent_selectors:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click()
                print("[WARMUP] ✅ Cookies acceptés")
                time.sleep(1)
                return
        except Exception:
            continue


# ============================================================
# Configuration Stealth
# ============================================================

def get_stealth_config() -> dict:
    """
    Retourne la configuration pour StealthyFetcher
    avec un fingerprint Firefox cohérent.

    Returns:
        Dict de configuration pour le fetcher.
    """
    return {
        "user_data_dir": str(BROWSER_PROFILE_DIR),
        "headless": False,
        "block_images": False,
        "disable_resources": False,
    }


# Fingerprint Firefox cohérent avec les headers interceptés
FIREFOX_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) "
        "Gecko/20100101 Firefox/132.0"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

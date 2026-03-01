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


def sync_chrome_profile() -> Path:
    """
    Copie le profil Google Chrome (ou Edge) de l'utilisateur vers
    le répertoire dédié à Scrapling. Cela permet d'utiliser le profil
    sans erreur de verrouillage (lock) si le navigateur est déjà ouvert.

    Returns:
        Chemin du profil synchronisé.
    """
    ensure_profile_dir()
    
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    
    # Ordre de préférence des navigateurs
    possible_paths = [
        local_app_data / "Google" / "Chrome" / "User Data",
        local_app_data / "Google" / "Chrome for Testing" / "User Data",
        local_app_data / "Microsoft" / "Edge" / "User Data",
    ]
    
    source = None
    for p in possible_paths:
        if p.exists():
            source = p
            break

    if not source:
        print("[STORAGE] ⚠️ Aucun profil Chrome/Edge trouvé sur le système.")
        print("[STORAGE] Utilisation du profil vierge.")
        return BROWSER_PROFILE_DIR

    print(f"[STORAGE] 🔄 Copie du profil depuis : {source}")
    
    # Nettoyage absolu du répertoire pour éviter d'hériter de fichiers corrompus
    if BROWSER_PROFILE_DIR.exists():
        shutil.rmtree(str(BROWSER_PROFILE_DIR), ignore_errors=True)
    ensure_profile_dir()
    
    # Copie du dossier Default (qui contient les cookies, etc.)
    default_dir = source / "Default"
    dst_default = BROWSER_PROFILE_DIR / "Default"

    copied = 0

    def robust_copy(src_dir, dst_dir):
        """Copie récursive qui ignore gracieusement les fichiers verrouillés (ex: Chrome ouvert)"""
        copied_files = 0
        os.makedirs(dst_dir, exist_ok=True)
        for item in os.listdir(src_dir):
            s = os.path.join(src_dir, item)
            d = os.path.join(dst_dir, item)
            if os.path.isdir(s):
                copied_files += robust_copy(s, d)
            else:
                try:
                    shutil.copy2(s, d)
                    copied_files += 1
                except Exception:
                    pass # Fichier verrouillé par Chrome, on ignore
        return copied_files

    if default_dir.exists():
        try:
            # On copie uniquement ce qui est nécessaire pour éviter de copier des Go de données
            # Network = Cookies, Local Storage = localStorage
            critical_dirs = ["Network", "Local Storage", "IndexedDB", "Session Storage"]
            critical_files = ["Cookies", "Web Data", "Login Data"]
            
            dst_default.mkdir(exist_ok=True)
            
            for d in critical_dirs:
                src_d = default_dir / d
                dst_d = dst_default / d
                if src_d.exists():
                    copied += robust_copy(str(src_d), str(dst_d))
                    
            for f in critical_files:
                src_f = default_dir / f
                dst_f = dst_default / f
                if src_f.exists():
                    try:
                        shutil.copy2(str(src_f), str(dst_f))
                        copied += 1
                    except Exception:
                        pass
        except Exception as e:
            print(f"[STORAGE] ⚠️ Copie du dossier Default échouée: {e}")

    print(f"[STORAGE] ✅ Profil Chrome/Edge synchronisé ({copied} éléments)")
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
            
            # Positionner la souris au centre pour activer la roulette
            try:
                page.mouse.move(page.viewport_size["width"] / 2, page.viewport_size["height"] / 2)
            except Exception:
                pass

            for _ in range(scroll_count):
                scroll_amount = random.randint(200, 600)
                page.mouse.wheel(0, scroll_amount)
                # Fallback de scroll classique si la souris n'a pas focus la frame
                page.evaluate(f"window.scrollBy({{top: {scroll_amount}, behavior: 'smooth'}})")
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
    avec un fingerprint cohérent.

    Returns:
        Dict de configuration pour le fetcher.
    """
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    
    possible_paths = [
        (local_app_data / "Google" / "Chrome" / "User Data", "chrome"),
        (local_app_data / "Google" / "Chrome for Testing" / "User Data", "chrome"),
        (local_app_data / "Microsoft" / "Edge" / "User Data", "msedge"),
    ]
    
    channel = "chrome"
    for p, ch in possible_paths:
        if p.exists():
            channel = ch
            break
            
    # Configuration de Playwright Chromium avec la correction du zoom
    additional_args = {
        "channel": channel,
        "device_scale_factor": 0.8, # Annule le scale trop fort (zoom) appliqué historiquement par Scrapling, 0.8 pour dézoomer
        "viewport": {"width": 1920, "height": 1080}
    }
    
    return {
        "user_data_dir": str(BROWSER_PROFILE_DIR),
        "headless": False,
        "block_images": False,
        "disable_resources": False,
        "real_chrome": True,
        "additional_args": additional_args
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

"""
Automatisation de l'inscription sur the-odds-api.com
Utilise Scrapling v0.3.14 avec page_action pour l'automatisation navigateur

Deux méthodes disponibles :
- Méthode 1 : Relais manuel via Telegram (pour VPS)
- Méthode 2 : Persistance de session (évitement du captcha)
"""

import time
import os
import sys
import random
from scrapling import StealthyFetcher

# Configuration
SITE_URL = "https://the-odds-api.com/#get-access"
USER_DATA_DIR = os.path.abspath("./user_data")

# Sélecteurs CSS
SELECTORS = {
    "start_button": ".oa-button",
    "name_input": 'input[name="name"]',
    "email_input": 'input[name="email"]',
    "captcha_iframe": 'iframe[title="reCAPTCHA"]',
    "captcha_token": "#g-recaptcha-response-2",
    "subscribe_button": "input.subscribe",
    "success_message": ".success",
}

# Configuration Telegram - Charger depuis variables d'environnement
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError(
        "TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID doivent être définis "
        "dans les variables d'environnement ou dans un fichier .env"
    )

# Listes de prénoms et noms pour génération aléatoire
FIRST_NAMES = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph",
    "Thomas", "Charles", "Christopher", "Daniel", "Matthew", "Anthony", "Mark",
    "Donald", "Steven", "Paul", "Andrew", "Joshua", "Kenneth", "Kevin", "Brian",
    "George", "Timothy", "Ronald", "Jason", "Edward", "Jeffrey", "Ryan",
    "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan",
    "Jessica", "Sarah", "Karen", "Nancy", "Lisa", "Betty", "Margaret", "Sandra",
    "Ashley", "Kimberly", "Emily", "Donna", "Michelle", "Dorothy", "Carol",
    "Amanda", "Melissa", "Deborah", "Stephanie", "Rebecca", "Sharon", "Laura"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson", "Anderson", "Thomas",
    "Taylor", "Moore", "Jackson", "Martin", "Lee", "Thompson", "White", "Harris",
    "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young",
    "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker"
]


def generate_random_name() -> str:
    """
    Génère un nom aléatoire réaliste (Prénom + Nom).
    
    Returns:
        Nom complet aléatoire (ex: "James Smith")
    """
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    return f"{first_name} {last_name}"


def send_telegram_photo(image_path: str, caption: str = "") -> bool:
    """Envoie une capture d'écran sur Telegram."""
    try:
        import requests
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        with open(image_path, "rb") as photo:
            files = {"photo": photo}
            data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}
            response = requests.post(url, files=files, data=data, timeout=30)
        print(f"[DEBUG] Telegram response: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"[ERREUR] Envoi Telegram échoué: {e}")
        return False


def wait_for_captcha_token(page, timeout: int = 180) -> bool:
    """Attend que le captcha soit résolu manuellement."""
    start_time = time.time()
    print(f"[INFO] Attente de la résolution du captcha (max {timeout}s)...")
    
    # Plusieurs sélecteurs possibles pour le token captcha
    selectors = [
        "#g-recaptcha-response-2",
        "#g-recaptcha-response",
        "textarea[name='g-recaptcha-response']",
        ".g-recaptcha-response"
    ]
    
    while time.time() - start_time < timeout:
        for selector in selectors:
            try:
                token = page.evaluate(f'document.querySelector("{selector}")?.value || ""')
                if token and len(token) > 30:
                    print(f"[SUCCESS] Captcha résolu! (sélecteur: {selector})")
                    return True
            except Exception:
                pass
        page.wait_for_timeout(2000)
    
    print("[ERREUR] Timeout - Captcha non résolu")
    return False


def method_1_telegram_relay(name: str, email: str):
    """MÉTHODE 1 : Relais manuel via Telegram"""
    print("\n" + "="*50)
    print("MÉTHODE 1 : Relais Telegram")
    print("="*50)
    
    def page_automation(page):
        """Fonction d'automatisation passée à page_action."""
        try:
            # Attendre le chargement
            page.wait_for_timeout(2000)
            
            # 1. Cliquer sur START
            print("[INFO] Clic sur le bouton START...")
            page.click(SELECTORS["start_button"])
            page.wait_for_timeout(2000)
            
            # 2. Remplir le formulaire
            print(f"[INFO] Remplissage - Nom: {name}, Email: {email}")
            page.fill(SELECTORS["name_input"], name)
            page.wait_for_timeout(500)
            page.fill(SELECTORS["email_input"], email)
            page.wait_for_timeout(1000)
            
            # 3. Screenshot + Telegram
            print("[INFO] Préparation du relais Telegram...")
            screenshot_path = os.path.abspath("captcha_screenshot.png")
            page.screenshot(path=screenshot_path)
            print(f"[INFO] Capture sauvegardée: {screenshot_path}")
            
            caption = f"🔐 CAPTCHA à résoudre\n\nNom: {name}\nEmail: {email}\n\nCochez la case sur le serveur!"
            if send_telegram_photo(screenshot_path, caption):
                print("[INFO] ✅ Capture envoyée sur Telegram!")
            else:
                print("[AVERTISSEMENT] Échec envoi Telegram - Résolvez manuellement")
            
            # 4. Attendre résolution captcha
            if not wait_for_captcha_token(page, timeout=180):
                print("[ERREUR] Captcha non résolu à temps")
                return
            
            # 5. Soumettre
            print("[INFO] Soumission du formulaire...")
            page.click(SELECTORS["subscribe_button"])
            page.wait_for_timeout(5000)
            
            print("[SUCCESS] ✅ Formulaire soumis!")
            page.wait_for_timeout(5000)
            
        except Exception as e:
            print(f"[ERREUR] {e}")
            import traceback
            traceback.print_exc()
    
    # Lancement
    fetcher = StealthyFetcher()
    
    print(f"[INFO] Navigation vers {SITE_URL}")
    StealthyFetcher.fetch(
        SITE_URL,
        headless=False,
        page_action=page_automation,
        network_idle=True,
        wait=10000
    )
    print("[INFO] Terminé")


def method_2_session_persistence(name: str, email: str):
    """MÉTHODE 2 : Persistance de session"""
    print("\n" + "="*50)
    print("MÉTHODE 2 : Persistance de Session")
    print("="*50)
    
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    
    def page_automation(page):
        """Fonction d'automatisation avec session persistante."""
        try:
            page.wait_for_timeout(2000)
            
            print("[INFO] Clic sur START...")
            page.click(SELECTORS["start_button"])
            page.wait_for_timeout(2000)
            
            print(f"[INFO] Remplissage - Nom: {name}, Email: {email}")
            page.fill(SELECTORS["name_input"], name)
            page.wait_for_timeout(500)
            page.fill(SELECTORS["email_input"], email)
            page.wait_for_timeout(1000)
            
            # Tenter clic sur captcha
            try:
                captcha = page.locator(SELECTORS["captcha_iframe"])
                if captcha.is_visible():
                    box = captcha.bounding_box()
                    if box:
                        x = box["x"] + box["width"] / 2
                        y = box["y"] + box["height"] / 2
                        print(f"[INFO] Clic automatique captcha ({x:.0f}, {y:.0f})")
                        page.mouse.click(x, y)
                        page.wait_for_timeout(3000)
            except Exception as e:
                print(f"[DEBUG] Clic captcha: {e}")
            
            # Vérifier si résolu
            page.wait_for_timeout(2000)
            token = page.evaluate('document.querySelector("#g-recaptcha-response-2")?.value || ""')
            if token and len(token) > 30:
                print("[SUCCESS] Captcha résolu automatiquement!")
            else:
                print("[INFO] Résolvez le captcha manuellement...")
                if not wait_for_captcha_token(page, timeout=180):
                    return
            
            print("[INFO] Soumission...")
            page.click(SELECTORS["subscribe_button"])
            page.wait_for_timeout(5000)
            
            print("[SUCCESS] ✅ Formulaire soumis!")
            page.wait_for_timeout(5000)
            
        except Exception as e:
            print(f"[ERREUR] {e}")
            import traceback
            traceback.print_exc()
    
    # Lancement avec profil persistant
    fetcher = StealthyFetcher()
    
    print(f"[INFO] Navigation vers {SITE_URL}")
    print(f"[INFO] Profil persistant: {USER_DATA_DIR}")
    
    StealthyFetcher.fetch(
        SITE_URL,
        headless=False,
        page_action=page_automation,
        network_idle=True,
        wait=10000,
        user_data_dir=USER_DATA_DIR
    )
    print("[INFO] Terminé - Profil sauvegardé")


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║     AUTOMATISATION INSCRIPTION THE-ODDS-API.COM              ║
║     Utilisant Scrapling v0.3.14 (page_action)                ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    if len(sys.argv) >= 4:
        name = sys.argv[1]
        email = sys.argv[2]
        choice = sys.argv[3]
    else:
        # Générer un nom aléatoire par défaut
        default_name = generate_random_name()
        name_input = input(f"Entrez votre nom (ou appuyez sur Entrée pour '{default_name}'): ").strip()
        name = name_input if name_input else default_name
        
        email = input("Entrez votre email: ").strip() or "test@example.com"
        print("\nChoisissez une méthode:")
        print("1. Relais Telegram")
        print("2. Persistance de session")
        choice = input("\nVotre choix (1 ou 2): ").strip()
    
    print(f"\n[CONFIG] Nom: {name}, Email: {email}, Méthode: {choice}")
    
    if choice == "1":
        method_1_telegram_relay(name, email)
    elif choice == "2":
        method_2_session_persistence(name, email)
    else:
        print("[ERREUR] Choix invalide.")


if __name__ == "__main__":
    main()

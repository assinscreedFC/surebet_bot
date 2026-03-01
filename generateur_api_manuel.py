"""
Générateur Manuel d'API Key - The Odds API
==========================================
Ce script reproduit exactement la logique des modules du bot 
(storage Firefox persistant, warm-up, scrapling) mais ouvre 
le navigateur pour que vous puissiez résoudre le captcha et
cliquer sur "Subscribe" manuellement.
"""
import os
import sys
import time

# Permet d'importer le code depuis le sous-dossier surebet_bot
sys.path.append(os.path.join(os.path.dirname(__file__), "surebet_bot"))

# On utilise exactement les mêmes fonctions que votre automatisation
try:
    from automation.mail_tm import create_mail_tm_account, get_api_key_from_email
    from automation.registration import generate_random_name, ODDS_API_URL, SELECTORS
    from automation.browser_storage import sync_chrome_profile, warm_up_browser, get_stealth_config
except ImportError as e:
    print(f"[ERREUR D'IMPORT] Assurez-vous que le dossier 'surebet_bot' est présent.\nDétail: {e}")
    sys.exit(1)

def main():
    print("=========================================================")
    print("   Générateur Manuel d'API Key - The Odds API (Firefox)")
    print("=========================================================")
    
    # 1. Email Temporaire
    email, token = create_mail_tm_account()
    if not email:
        print("[ERREUR] Impossible de créer l'email.")
        return
        
    name = generate_random_name()
    print(f"\n[INFO] Identité générée : {name} / {email}")
    
    # 2. Synchronisation et Navigateur
    print("\n[INFO] Synchronisation du profil Chrome...")
    sync_chrome_profile()
    stealth_config = get_stealth_config()
    
    try:
        from scrapling import StealthyFetcher
    except ImportError as e:
        print(f"[ERREUR CRITIQUE] Impossible de charger Scrapling : {e}")
        return

    # Fonction de callback appelée une fois la page chargée
    def on_page_loaded(page):
        print("\n[PHASE 1] Warm-up navigateur (cookies Google)")
        print("-" * 50)
        
        try:
            warm_up_browser(page)
        except Exception as e:
            print(f"[WARN] Warm-up partiel ou échoué : {e}")
        
        print("\n[PHASE 2] Inscription sur the-odds-api.com")
        print("-" * 50)
        
        # Navigation manuelle sécurisée
        if "the-odds-api" not in page.url:
            print(f"[INFO] Navigation vers {ODDS_API_URL}...")
            page.goto(ODDS_API_URL, wait_until="domcontentloaded")
            
        page.wait_for_timeout(2000)

        # Réduction du zoom de la page pour mieux voir le captcha
        try:
            page.evaluate("document.body.style.zoom='80%'")
            page.evaluate("document.body.style.MozTransform='scale(0.8)'; document.body.style.transformOrigin='0 0';")
        except Exception:
            pass
        
        try:
            print("[INFO] Tentative de clic sur START...")
            # On attend que le bouton soit visible avant de cliquer
            page.wait_for_selector(SELECTORS["start_button"], timeout=10000)
            page.click(SELECTORS["start_button"])
            page.wait_for_timeout(2000)

            print("[INFO] Remplissage du formulaire...")
            page.fill(SELECTORS["name_input"], name)
            page.wait_for_timeout(500)
            page.fill(SELECTORS["email_input"], email)
        except Exception as e:
            print(f"[AVERTISSEMENT] Remplissage auto échoué: {e}")
            print(f"Veuillez remplir manuellement : Nom = {name} | Email = {email}")

        print("\n" + "="*50)
        print(" ACTION REQUISE DE VOTRE PART :")
        print(" 1. Résolvez le CAPTCHA reCAPTCHA vous-même sur la page.")
        print(" 2. Cliquez sur le bouton 'Get Free API Key'.")
        print(" 3. Laissez cette console ouverte, elle attend la clé.")
        print("="*50 + "\n")

        # Appel à la fonction qui attend l'email et extrait la clé
        api_key = get_api_key_from_email(token, max_wait=300, page=page)
        
        if api_key:
            output_file = "api_keys.txt"
            with open(output_file, "a", encoding="utf-8") as f:
                f.write(f"{email}:{api_key}\n")
            
            print("================================================")
            print(f"   [SUCCÈS] CLÉ SAUVEGARDÉE DANS {output_file}   ")
            print("================================================")
        else:
            print("[ERREUR] Délai expiré ou email non reçu.")
            
        print("\nFermeture du navigateur...")
        page.wait_for_timeout(3000)
        
        # Fermeture forcée pour s'assurer que le processus ne reste pas bloqué
        try:
            page.close()
        except Exception:
            pass
        os._exit(0)


    print("\n[INFO] Lancement de Scrapling...")
    try:
        # --- CORRECTION APPLIQUÉE ICI ---
        # 1. Initialisation sans arguments conflictuels
        user_dir = stealth_config.get("user_data_dir")
        
        if user_dir and os.path.exists(user_dir):
            print(f"[INFO] Utilisation du profil : {user_dir}")
            StealthyFetcher.fetch(
                ODDS_API_URL,
                page_action=on_page_loaded,
                user_data_dir=user_dir,
                wait=60000,
                headless=False,
                real_chrome=stealth_config.get("real_chrome", True),
                additional_args=stealth_config.get("additional_args")
            )
        else:
            print("[INFO] Démarrage sans profil persistant (Profil introuvable ou désactivé)")
            StealthyFetcher.fetch(
                ODDS_API_URL,
                page_action=on_page_loaded,
                wait=60000,
                headless=False,
                real_chrome=stealth_config.get("real_chrome", True),
                additional_args=stealth_config.get("additional_args")
            )
            
    except Exception as e:
        print(f"\n[CRASH] Erreur Fetcher : {e}")
        if "ERR_NAME_NOT_RESOLVED" in str(e):
            print("\n[CONSEIL] Vérifiez votre connexion internet ou désactivez le VPN.")

if __name__ == "__main__":
    main()
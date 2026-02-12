#!/usr/bin/env python3
"""
AUTOMATISATION COMPLÈTE - THE ODDS API (GRATUIT)
=================================================
- Mail.tm API pour emails temporaires
- Telegram pour notification captcha (résolution manuelle)
- Scrapling pour l'inscription

Le navigateur reste ouvert en mode visible pour permettre
la résolution du captcha via VNC/Remote Desktop.
"""

import sys
import os
import time
import re
import random
import string
import traceback
from pathlib import Path

# Répertoire du script (pour .env et api_keys.txt)
SCRIPT_DIR = Path(__file__).resolve().parent

# Charger .env depuis le dossier du script
try:
    from dotenv import load_dotenv
    load_dotenv(SCRIPT_DIR / ".env")
    load_dotenv()  # aussi depuis le cwd
except ImportError:
    pass

import requests
import threading

# Scrapling (obligatoire pour le navigateur)
try:
    from scrapling import StealthyFetcher
except ImportError as e:
    print("[ERREUR] Module 'scrapling' non installé. Installez-le avec: pip install scrapling")
    sys.exit(1)

# Configuration
import tempfile
import uuid
USER_DATA_DIR = os.path.join(tempfile.gettempdir(), f"odds_api_{uuid.uuid4().hex[:8]}")
ODDS_API_URL = "https://the-odds-api.com/#get-access"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("[ERREUR] Variables Telegram manquantes.")
    print("  Créez un fichier .env dans le dossier du script avec:")
    print("  TELEGRAM_BOT_TOKEN=votre_token")
    print("  TELEGRAM_CHAT_ID=votre_chat_id")
    sys.exit(1)

# Mail.tm API
MAIL_TM_API = "https://api.mail.tm"

# Noms : utiliser Faker si disponible (noms humains réalistes), sinon listes intégrées
try:
    from faker import Faker
    _fake = Faker("fr_FR")  # Noms français réalistes
    def generate_random_name() -> str:
        return _fake.name()
except ImportError:
    FIRST_NAMES = [
        "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph",
        "Thomas", "Charles", "Christopher", "Daniel", "Matthew", "Anthony", "Mark",
        "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan",
        "Jessica", "Sarah", "Karen", "Nancy", "Lisa", "Betty", "Margaret", "Sandra",
        "Ashley", "Kimberly", "Emily", "Donna", "Michelle", "Dorothy", "Carol",
    ]
    LAST_NAMES = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
        "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson", "Anderson", "Thomas",
        "Taylor", "Moore", "Jackson", "Martin", "Lee", "Thompson", "White", "Harris",
        "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young",
    ]
    def generate_random_name() -> str:
        return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def print_banner():
    print("\n" + "=" * 60)
    print("   AUTOMATISATION COMPLÈTE - THE ODDS API")
    print("   Mail.tm + Telegram Relay (GRATUIT)")
    print("=" * 60 + "\n")


# ============================================
# TELEGRAM - Notifications
# ============================================
def send_telegram_message(message: str) -> bool:
    """Envoie un message sur Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        response = requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        return response.status_code == 200
    except:
        return False


def send_telegram_photo(image_path: str, caption: str = "") -> bool:
    """Envoie une capture d'écran sur Telegram (photo ou document)"""
    try:
        # Vérifier que le fichier existe et n'est pas vide
        if not os.path.exists(image_path):
            print(f"[TELEGRAM] ❌ Fichier non trouvé: {image_path}")
            return False

    return False


def send_telegram_photos_group(photos: list[tuple[str, str]]) -> bool:
    """Envoie plusieurs photos en groupe sur Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMediaGroup"
        media = []
        files = {}
        
        for idx, (photo_path, caption) in enumerate(photos):
            with open(photo_path, "rb") as photo_file:
                file_key = f"photo{idx}"
                files[file_key] = photo_file.read()
                media.append({
                    "type": "photo",
                    "media": f"attach://{file_key}",
                    "caption": caption
                })
        
        # Note: sendMediaGroup nécessite une structure différente
        # Pour simplifier, on envoie les photos une par une
        for photo_path, caption in photos:
            send_telegram_photo(photo_path, caption)
            time.sleep(0.5)  # Petit délai entre les envois
        
        return True
    except Exception as e:
        print(f"[ERREUR] Telegram group photos: {e}")
        return False


def get_telegram_messages(last_update_id: int = 0) -> list[dict]:
    """Récupère les nouveaux messages Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        response = requests.get(url, params={
            "offset": last_update_id + 1,
            "timeout": 1,
            "allowed_updates": ["message"]
        }, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            updates = data.get("result", [])
            messages = []
            
            for update in updates:
                msg = update.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                if chat_id == TELEGRAM_CHAT_ID:
                    messages.append({
                        "update_id": update.get("update_id", 0),
                        "text": msg.get("text", ""),
                        "from": msg.get("from", {}).get("username", "Unknown")
                    })
            
            return messages
    except Exception as e:
        print(f"[DEBUG] Erreur récupération messages: {e}")
    
    return []


# Variable globale pour gérer les commandes et l'état
_telegram_command_handler = None
_registration_state = {
    "running": False,
    "name": None,
    "email": None,
    "token": None,
    "page": None,
    "fetcher": None
}


def check_telegram_commands():
    """Vérifie les commandes Telegram en continu (à appeler dans un thread)"""
    global _registration_state
    last_update_id = 0
    processed_commands = set()  # Pour éviter les doubles traitements
    
    while True:
        try:
            messages = get_telegram_messages(last_update_id)
            
            for msg in messages:
                update_id = msg["update_id"]
                last_update_id = max(last_update_id, update_id)
                text = msg["text"].strip().lower()
                
                # Éviter de traiter la même commande deux fois
                command_key = f"{update_id}_{text}"
                if command_key in processed_commands:
                    continue
                processed_commands.add(command_key)
                
                # Nettoyer les anciennes commandes (garder seulement les 100 dernières)
                if len(processed_commands) > 100:
                    processed_commands = set(list(processed_commands)[-50:])
                
                if text == "/launch":
                    send_telegram_message(
                        "🚀 <b>Commande /launch reçue</b>\n\n"
                        "⏳ Relance du processus d'inscription..."
                    )
                    print("[COMMANDE] /launch reçue - Relance du processus")
                    
                    # Relancer le processus
                    if _registration_state.get("running"):
                        send_telegram_message("⚠️ Un processus est déjà en cours. Attendez qu'il se termine.")
                    else:
                        # Marquer comme en cours immédiatement pour éviter les doubles lancements
                        _registration_state["running"] = True
                        # Lancer dans un thread séparé pour ne pas bloquer
                        thread = threading.Thread(
                            target=run_registration_process,
                            args=(_registration_state.get("name"),),
                            daemon=True
                        )
                        thread.start()
                
                elif text == "/status":
                    if _registration_state.get("running"):
                        status_msg = (
                            "📊 <b>STATUS</b>\n\n"
                            f"🔄 Processus: <b>En cours</b>\n"
                            f"👤 Nom: {_registration_state.get('name', 'N/A')}\n"
                            f"📧 Email: {_registration_state.get('email', 'N/A')}\n"
                        )
                    else:
                        status_msg = (
                            "📊 <b>STATUS</b>\n\n"
                            "⏸️ Processus: <b>Arrêté</b>\n\n"
                            "💡 Utilisez /launch pour démarrer"
                        )
                    send_telegram_message(status_msg)
                
                elif text == "/help":
                    send_telegram_message(
                        "📖 <b>Commandes disponibles</b>\n\n"
                        "/launch - Relance le processus d'inscription\n"
                        "/status - Affiche le status actuel\n"
                        "/help - Affiche cette aide\n\n"
                        "💡 <b>Astuce:</b> Utilisez /launch si le captcha a expiré"
                    )
            
            time.sleep(2)  # Vérifier toutes les 2 secondes
            
        except Exception as e:
            print(f"[COMMANDE] Erreur vérification commandes: {e}")
            time.sleep(5)


def run_registration_process(name: str = None):
    """Lance le processus d'inscription (peut être appelé depuis une commande)"""
    global _registration_state
    
    try:
        _registration_state["running"] = True
        
        # Générer un nom si non fourni
        if not name:
            name = generate_random_name()
            print(f"[INFO] Nom généré aléatoirement: {name}")
        
        _registration_state["name"] = name
        
        # Test connexion Telegram
        print("[INFO] Test connexion Telegram...")
        if send_telegram_message("🤖 Script démarré!"):
            print("[SUCCESS] Telegram OK")
        else:
            print("[WARN] Telegram non disponible")
        
        # Étape 1: Créer email
        email, token = create_mail_tm_account()
        if not email:
            send_telegram_message("❌ Échec création email temporaire")
            _registration_state["running"] = False
            return
        
        _registration_state["email"] = email
        _registration_state["token"] = token
        
        send_telegram_message(f"📧 Email créé: <code>{email}</code>")
        
        # Étape 2: Inscription
        if not register_odds_api(name, email):
            send_telegram_message("❌ Échec inscription")
            _registration_state["running"] = False
            return
        
        # Étape 3: Récupérer clé API
        api_key = get_api_key_from_email(token)
        if api_key:
            keys_file = SCRIPT_DIR / "api_keys.txt"
            with open(keys_file, "a", encoding="utf-8") as f:
                f.write(f"{email}:{api_key}\n")
            print(f"[INFO] Clé sauvegardée dans api_keys.txt")
            send_telegram_message(
                f"✅ <b>INSCRIPTION RÉUSSIE!</b>\n\n"
                f"🔑 Clé API: <code>{api_key}</code>\n"
                f"📧 Email: <code>{email}</code>\n\n"
                f"💾 Sauvegardée dans api_keys.txt"
            )
            _registration_state["running"] = False
            return
        
        _registration_state["running"] = False
        
    except Exception as e:
        print(f"[ERREUR] Processus d'inscription: {e}")
        traceback.print_exc()
        send_telegram_message(f"❌ <b>ERREUR</b>\n\n{str(e)}")
        _registration_state["running"] = False


def _is_captcha_solved(page) -> bool:
    """Vérifie si le captcha est résolu (token présent)."""
    for selector in ["#g-recaptcha-response-2", "#g-recaptcha-response", 'textarea[name="g-recaptcha-response"]']:
        try:
            token = page.evaluate(f'document.querySelector("{selector}")?.value || ""')
            if token and len(token) > 30:
                return True
        except Exception:
            pass
    return False


def try_auto_solve_captcha(page, wait_after_checkbox: int = 5, wait_after_challenge: int = 3) -> bool:
    """
    Tente de résoudre le captcha automatiquement : clic sur la checkbox, puis si un challenge
    apparaît, un clic sur la première case (parfois suffisant).
    Returns True si le token est présent.
    """
    try:
        # Cliquer sur la checkbox reCAPTCHA
        iframe_selector = 'iframe[title*="reCAPTCHA"]'
        iframe = page.query_selector(iframe_selector)
        if not iframe:
            return False
        box = iframe.bounding_box()
        if box:
            x = box["x"] + box["width"] / 2
            y = box["y"] + box["height"] / 2
            page.mouse.click(x, y)
            print("[CAPTCHA] Clic sur la checkbox reCAPTCHA")
        time.sleep(wait_after_checkbox)
        if _is_captcha_solved(page):
            print("[CAPTCHA] ✅ Résolu automatiquement (checkbox seule)")
            return True
        # Challenge avec images : tenter un clic sur la première case
        challenge_iframe = page.query_selector('iframe[title*="recaptcha challenge"]')
        if challenge_iframe:
            cf = challenge_iframe.content_frame()
            if cf:
                tiles = cf.query_selector_all(".rc-imageselect-tile") or cf.query_selector_all("td.rc-imageselect-tile")
                if tiles:
                    tiles[0].click()
                    print("[CAPTCHA] Clic sur la première case du challenge")
                    time.sleep(wait_after_challenge)
                if _is_captcha_solved(page):
                    print("[CAPTCHA] ✅ Résolu après clic sur une case")
                    return True
    except Exception as e:
        print(f"[CAPTCHA] Auto-solve: {e}")
    return False


def detect_captcha_challenge(page) -> dict:
    """
    Détecte le type de captcha et récupère les informations nécessaires.
    
    Returns:
        {
            "type": "checkbox" | "challenge",
            "iframe": iframe_element ou None,
            "challenge_text": str ou None,
            "images": list ou None
        }
    """
    try:
        # Chercher l'iframe du captcha
        iframe_selector = 'iframe[title*="reCAPTCHA"]'
        iframe = page.query_selector(iframe_selector)
        
        if not iframe:
            return {"type": "unknown", "iframe": None}
        
        # Vérifier si c'est un challenge avec images
        # Le challenge apparaît dans un iframe séparé
        challenge_iframe_selector = 'iframe[title*="recaptcha challenge"]'
        challenge_iframe = page.query_selector(challenge_iframe_selector)
        
        if challenge_iframe:
            # C'est un challenge avec images
            try:
                # Récupérer le texte du challenge
                challenge_frame = challenge_iframe.content_frame()
                if challenge_frame:
                    # Essayer plusieurs sélecteurs pour récupérer le texte du challenge
                    challenge_text = "Sélectionnez les images"
                    selectors_text = [
                        ".rc-imageselect-desc-text",
                        ".rc-imageselect-desc",
                        "#rc-imageselect-desc",
                        ".rc-imageselect-desc-no-canonical",
                        "span.rc-imageselect-desc-text"
                    ]
                    
                    for selector in selectors_text:
                        try:
                            elem = challenge_frame.query_selector(selector)
                            if elem:
                                text = elem.inner_text()
                                if text and len(text.strip()) > 0:
                                    challenge_text = text.strip()
                                    print(f"[CAPTCHA] Instruction trouvée: {challenge_text}")
                                    break
                        except:
                            continue
                    
                    # Si pas trouvé, essayer de récupérer depuis le titre ou autres éléments
                    if challenge_text == "Sélectionnez les images":
                        try:
                            # Essayer de récupérer depuis le body ou d'autres éléments
                            body_text = challenge_frame.query_selector("body")
                            if body_text:
                                all_text = body_text.inner_text()
                                # Chercher des patterns communs
                                if "feu" in all_text.lower() or "traffic" in all_text.lower():
                                    challenge_text = "Sélectionnez toutes les images avec des feux de circulation"
                                elif "voiture" in all_text.lower() or "car" in all_text.lower():
                                    challenge_text = "Sélectionnez toutes les images avec des voitures"
                                elif "pont" in all_text.lower() or "bridge" in all_text.lower():
                                    challenge_text = "Sélectionnez toutes les images avec des ponts"
                                elif "panneau" in all_text.lower() or "sign" in all_text.lower():
                                    challenge_text = "Sélectionnez toutes les images avec des panneaux"
                        except:
                            pass
                    
                    # Vérifier s'il y a un bouton audio (challenge audio disponible)
                    audio_button = challenge_frame.query_selector(".rc-button-audio")
                    has_audio = audio_button is not None
                    
                    # Récupérer les images
                    images = challenge_frame.query_selector_all(".rc-imageselect-tile")
                    
                    return {
                        "type": "challenge",
                        "iframe": challenge_iframe,
                        "challenge_text": challenge_text,
                        "images": images,
                        "challenge_frame": challenge_frame,
                        "has_audio": has_audio
                    }
            except Exception as e:
                print(f"[DEBUG] Erreur détection challenge: {e}")
        
        # Sinon, c'est probablement juste une checkbox
        return {"type": "checkbox", "iframe": iframe}
        
    except Exception as e:
        print(f"[DEBUG] Erreur détection captcha: {e}")
        return {"type": "unknown", "iframe": None}



                    # Vérifier s'il y a un bouton audio (challenge audio disponible)
                    audio_button = challenge_frame.query_selector(".rc-button-audio")
                    has_audio = audio_button is not None
                    
                    return {
                        "type": "challenge",
                        "iframe": challenge_iframe,
                        "challenge_text": challenge_text,
                        "challenge_frame": challenge_frame,
                        "has_audio": has_audio
                    }
            except Exception as e:
                print(f"[DEBUG] Erreur détection challenge: {e}")
        
        # Sinon, c'est probablement juste une checkbox
        return {"type": "checkbox", "iframe": iframe}


def click_captcha_images(challenge_frame, image_indices: list[int]) -> bool:
    """
    Clique sur les images du captcha selon les indices fournis.
    
    Args:
        challenge_frame: Le frame du challenge
        image_indices: Liste des indices (1-indexed) des images à cliquer
    """
    try:
        print(f"[CAPTCHA] DEBUG: Tentative de clic sur les images {image_indices}")
        
        # Essayer plusieurs sélecteurs pour trouver les images
        image_tiles = challenge_frame.query_selector_all(".rc-imageselect-tile")
        print(f"[CAPTCHA] DEBUG: Sélecteur .rc-imageselect-tile trouvé: {len(image_tiles)}")
        
        if not image_tiles or len(image_tiles) == 0:
            image_tiles = challenge_frame.query_selector_all("td.rc-imageselect-tile")
            print(f"[CAPTCHA] DEBUG: Sélecteur td.rc-imageselect-tile trouvé: {len(image_tiles)}")
        
        if not image_tiles or len(image_tiles) == 0:
            image_tiles = challenge_frame.query_selector_all("table.rc-imageselect-table td")
            print(f"[CAPTCHA] DEBUG: Sélecteur table td trouvé: {len(image_tiles)}")
        
        if not image_tiles or len(image_tiles) == 0:
            # Dernier recours : toutes les cellules avec images
            all_tds = challenge_frame.query_selector_all("td")
            image_tiles = [t for t in all_tds if t.query_selector("img") or t.query_selector("div[style*='background']")]
            print(f"[CAPTCHA] DEBUG: Sélecteur générique td trouvé: {len(image_tiles)}")
        
        if not image_tiles or len(image_tiles) == 0:
            print("[CAPTCHA] ❌ Aucune image trouvée pour cliquer")
            return False
        
        print(f"[CAPTCHA] {len(image_tiles)} images trouvées pour cliquer")
        
        print(f"[CAPTCHA] Clic sur les images: {image_indices}")
        
        for idx in image_indices:
            # Convertir en 0-indexed
            array_idx = idx - 1
            if 0 <= array_idx < len(image_tiles):
                try:
                    tile = image_tiles[array_idx]
                    box = tile.bounding_box()
                    if box:
                        print(f"[CAPTCHA] DEBUG: Image {idx} box: {box}")
                        # Calculer le centre pour cliquer
                        x = box["x"] + box["width"] / 2
                        y = box["y"] + box["height"] / 2
                        
                        # Utiliser mouse.click (plus robuste pour les iframes/canvas)
                        try:
                            # Tenter de récupérer la page racine
                            page_root = challenge_frame.page
                            if page_root:
                                # Coordonnées sont relatives au viewport, il faut peut-être ajuster
                                # Mais bounding_box retourne des coords relatives au frame habituellement
                                # Si on clique via le frame, ça devrait aller
                                challenge_frame.click(f":nth-match(.rc-imageselect-tile, {idx})", position={"x": box["width"]/2, "y": box["height"]/2}, force=True)
                                print(f"[CAPTCHA] ✅ Image {idx} cliquée (force click center)")
                            else:
                                tile.click(force=True)
                                print(f"[CAPTCHA] ✅ Image {idx} cliquée (element force)")
                        except Exception as e_click:
                            print(f"[CAPTCHA] ⚠️ Erreur clic optimisé: {e_click}, tentative fallback")
                            tile.click(force=True)
                        
                        time.sleep(0.5)  # Petit délai
                        
                    else:
                         print(f"[CAPTCHA] ⚠️ Image {idx} sans bounding box")

                except Exception as e:
                    print(f"[CAPTCHA] ❌ Erreur clic image {idx}: {e}")
            else:
                print(f"[CAPTCHA] ⚠️ Indice {idx} hors limites (max {len(image_tiles)})")
        
        # NOTE: Verify logic is handled separately now
        return True

    except Exception as e:
        print(f"[CAPTCHA] ❌ Erreur interaction: {e}")

    return False



def wait_for_audio_captcha(page, challenge_frame, timeout: int = 600) -> bool:
    """
    Gère le captcha audio : passage en mode audio, récupération du fichier,
    envoi sur Telegram, attente de la réponse (texte), soumission.
    """
    print("[CAPTCHA] 🎧 Tentative de passage en mode AUDIO...")
    
    # 1. Cliquer sur le bouton Audio
    audio_btn_selectors = [
        "#recaptcha-audio-button",
        "button.rc-button-audio",
        ".rc-button-audio"
    ]
    
    clicked = False
    for sel in audio_btn_selectors:
        try:
            btn = challenge_frame.query_selector(sel)
            if btn:
                print(f"[CAPTCHA] Bouton Audio trouvé: {sel}")
                
                # Méthode 1: Clic standard
                try:
                    btn.click()
                    print(f"[CAPTCHA] ✅ Clic standard sur bouton Audio ({sel})")
                    clicked = True
                    break
                except Exception as e:
                    print(f"[CAPTCHA] ⚠️ Erreur clic standard: {e}")
                    
                    # Méthode 2: Force click
                    try:
                        btn.click(force=True)
                        print(f"[CAPTCHA] ✅ Force click sur bouton Audio ({sel})")
                        clicked = True
                        break
                    except Exception as e2:
                        print(f"[CAPTCHA] ⚠️ Erreur force click: {e2}")
                        
                        # Méthode 3: JS click
                        try:
                            btn.evaluate("el => el.click()")
                            print(f"[CAPTCHA] ✅ JS click sur bouton Audio ({sel})")
                            clicked = True
                            break
                        except Exception as e3:
                            print(f"[CAPTCHA] ❌ Erreur JS click: {e3}")

        except Exception as e:
            print(f"[CAPTCHA] Erreur recherche bouton {sel}: {e}")
            pass
            
    if not clicked:
        print("[CAPTCHA] ❌ Bouton Audio introuvable")
        return False
        
    time.sleep(3)
    
    # 2. Vérifier si on est bloqué ("Try again later")
    try:
        content = challenge_frame.content()
        if "Try again later" in content or "réessayez plus tard" in content:
            print("[CAPTCHA] ⚠️ Bloqué : 'Try again later'")
            send_telegram_message("⚠️ <b>Erreur Audio</b>: Google a bloqué les requêtes audio ('Try again later').\nRepassez en mode image ou changez d'IP.")
            return False
    except:
        pass

    # Boucle pour gérer les rafraîchissements (nouveaux audios)
    while time.time() - start_wait < timeout:
        # 3. Récupérer le lien de téléchargement Audio
        audio_url = None
        try:
            # Chercher le lien de téléchargement
            link = challenge_frame.query_selector(".rc-audiochallenge-download-link")
            if link:
                audio_url = link.get_attribute("href")
            
            if not audio_url:
                # Chercher la balise audio source
                audio_src = challenge_frame.query_selector("#audio-source")
                if audio_src:
                    audio_url = audio_src.get_attribute("src")
                    
        except Exception as e:
            print(f"[CAPTCHA] Erreur recherche URL audio: {e}")
            
        if not audio_url:
            print("[CAPTCHA] ❌ URL Audio introuvable")
            return False
            
        print(f"[CAPTCHA] 🔗 URL Audio trouvée: {audio_url[:50]}...")
        
        # 4. Télécharger le fichier MP3
        try:
            import requests
            doc_resp = requests.get(audio_url, timeout=30)
            if doc_resp.status_code == 200:
                audio_path = os.path.join(temp_dir, f"captcha_audio_{int(time.time())}.mp3")
                with open(audio_path, "wb") as f:
                    f.write(doc_resp.content)
                print(f"[CAPTCHA] ✅ Audio téléchargé: {audio_path}")
                
                # 5. Envoyer sur Telegram
                message_instruct = (
                    "🎧 <b>CAPTCHA AUDIO</b>\n\n"
                    "1️⃣ Écoutez et envoyez le code\n"
                    "2️⃣ Envoyez <b>r</b> ou <b>refresh</b> pour changer d'audio"
                )
                send_telegram_message(message_instruct)
                
                # Envoi via requests
                url_doc = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendAudio"
                files = {"audio": open(audio_path, "rb")}
                data = {"chat_id": TELEGRAM_CHAT_ID, "title": "Captcha Audio"}
                requests.post(url_doc, files=files, data=data)
                
            else:
                print("[CAPTCHA] ❌ Erreur téléchargement audio")
                return False
        except Exception as e:
            print(f"[CAPTCHA] ❌ Exception téléchargement/envoi audio: {e}")
            return False
            
        # 6. Attendre la réponse texte OU la commande refresh
        print("[CAPTCHA] ⏳ Attente code audio ou refresh...")
        loop_start = time.time()
        audio_solved_or_refreshed = False
        
        while time.time() - loop_start < 120: # Attendre max 2 min par audio
            messages = get_telegram_messages(last_update)
            for msg in messages:
                last_update = max(last_update, msg["update_id"])
                text = (msg.get("text") or "").strip().lower()
                
                # COMMANDE REFRESH
                if text in ["r", "refresh", "actualiser", "reload", "new"]:
                    print("[CAPTCHA] 🔄 Demande de rafraîchissement audio...")
                    send_telegram_message("🔄 Actualisation de l'audio...")
                    
                    # Clic sur le bouton Reload
                    reload_selectors = ["#recaptcha-reload-button", ".rc-button-reload"]
                    for rs in reload_selectors:
                        try:
                            rbtn = challenge_frame.query_selector(rs)
                            if rbtn:
                                rbtn.click()
                                print(f"[CAPTCHA] ✅ Bouton Reload cliqué ({rs})")
                                time.sleep(3) # Attendre chargement
                                audio_solved_or_refreshed = True # Pour sortir de la boucle d'attente message
                                break
                        except:
                            pass
                    if audio_solved_or_refreshed:
                        break # Sort du for messages
                    else:
                        send_telegram_message("❌ Impossible de trouver le bouton Actualiser.")
                
                # CODE AUDIO
                elif text and len(text) > 2: 
                    print(f"[CAPTCHA] 📩 Reçu code: {text}")
                    send_telegram_message(f"✅ Essai du code : <code>{text}</code>")
                    
                    try:
                        input_field = challenge_frame.query_selector("#audio-response")
                        if input_field:
                            input_field.fill(text)
                            time.sleep(1)
                            
                            # Valider
                            verify_btn = challenge_frame.query_selector("#recaptcha-verify-button")
                            if verify_btn:
                                verify_btn.click()
                                time.sleep(3)
                                
                                # Vérifier succès
                                if _is_captcha_solved(page):
                                    send_telegram_message("✅ Audio validé !")
                                    return True
                                else:
                                    send_telegram_message("❌ Code incorrect. Essayez encore ou 'r' pour changer.")
                                    # On ne sort pas, l'utilisateur peut réessayer le même code ou refresh
                    except Exception as e_input:
                         print(f"[CAPTCHA] Erreur saisie audio: {e_input}")
            
            if audio_solved_or_refreshed:
                break # Recommence la boucle principale (téléchargement nouvel audio)
                
            time.sleep(2)
            
        if not audio_solved_or_refreshed:
            # Si on sort par timeout de la boucle interne
            print("[CAPTCHA] Timeout attente réponse audio unique")
            # On continue, ça re-téléchargera peut-être le même ou sortira au timeout global
    
    return False


def wait_for_captcha_with_telegram(page, timeout: int = 600) -> bool:
    """
    Tente d'abord de résoudre le captcha automatiquement. Si échec, envoie une capture
    complète de la page sur Telegram et attend que l'utilisateur envoie les numéros des
    cases à cliquer (ex: 1,2,3), puis clique dessus et sur Vérifier.
    """
    print(f"[CAPTCHA] Délai d'attente utilisateur: {timeout} secondes (10 min)")
    # 1) Tenter résolution automatique
    if try_auto_solve_captcha(page):
        return True

    # Créer un dossier temporaire pour les captures
    temp_dir = os.path.join(os.path.dirname(__file__), "captcha_temp")
    os.makedirs(temp_dir, exist_ok=True)

    # Détecter le type de captcha
    captcha_info = detect_captcha_challenge(page)
    print(f"[CAPTCHA] Type détecté: {captcha_info['type']}")
    
    # Prendre une capture générale
    screenshot_path = os.path.join(temp_dir, "captcha_screenshot.png")
    page.screenshot(path=screenshot_path)
    
    # Gérer selon le type
    if captcha_info["type"] == "challenge":
        # C'est un challenge avec images
        print("[CAPTCHA] Challenge avec images détecté!")
        
        challenge_frame = captcha_info.get("challenge_frame")
        if not challenge_frame:
            # Attendre que le challenge se charge
            time.sleep(2)
            captcha_info = detect_captcha_challenge(page)
            challenge_frame = captcha_info.get("challenge_frame")
        
        if challenge_frame:
            # Récupérer l'instruction
            challenge_text = captcha_info.get("challenge_text", "Sélectionnez les images")
            
            # Si l'instruction n'est pas claire, essayer de la récupérer à nouveau
            if challenge_text == "Sélectionnez les images" or len(challenge_text) < 10:
                try:
                    selectors_text = [
                        ".rc-imageselect-desc-text",
                        ".rc-imageselect-desc",
                        "#rc-imageselect-desc",
                        ".rc-imageselect-desc-no-canonical"
                    ]
                    for selector in selectors_text:
                        elem = challenge_frame.query_selector(selector)
                        if elem:
                            text = elem.inner_text().strip()
                            if text and len(text) > 5:
                                challenge_text = text
                                print(f"[CAPTCHA] Instruction trouvée: {challenge_text}")
                                break
                except Exception as e:
                    print(f"[DEBUG] Erreur récupération instruction: {e}")
            
            # Capturer la fenêtre complète du navigateur
            print("[CAPTCHA] Capture de la fenêtre complète du navigateur...")
            full_screenshot_path = os.path.join(temp_dir, "captcha_full_page.png")
            
            try:
                # Essayer avec full_page=True d'abord
                page.screenshot(path=full_screenshot_path, full_page=True)
                print(f"[CAPTCHA] Capture effectuée, chemin: {full_screenshot_path}")
            except Exception as e:
                print(f"[CAPTCHA] ⚠️ Erreur capture full_page: {e}, tentative sans full_page...")
                try:
                    # Fallback : capture normale
                    page.screenshot(path=full_screenshot_path)
                    print(f"[CAPTCHA] Capture normale effectuée")
                except Exception as e2:
                    print(f"[CAPTCHA] ❌ Erreur capture: {e2}")
                    full_screenshot_path = None
            
            # Vérifier que la capture a réussi
            if full_screenshot_path and os.path.exists(full_screenshot_path):
                file_size = os.path.getsize(full_screenshot_path)
                print(f"[CAPTCHA] Fichier existe: {full_screenshot_path}, taille: {file_size} bytes")
                
                if file_size > 0:
                    print(f"[CAPTCHA] ✅ Capture complète réussie ({file_size} bytes)")
                    
                    # Envoyer le message d'instruction AVANT la capture (bien visible)
                    message = f"""🔐 <b>CAPTCHA AVEC IMAGES</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 <b>INSTRUCTION IMPORTANTE:</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>{challenge_text}</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📸 <b>Capture complète de la fenêtre ci-dessous</b>

💬 <b>Répondez avec les numéros des images à sélectionner</b>
   Les images sont numérotées de <b>gauche à droite, de haut en bas</b>
   Exemple: <code>1,3,5</code> ou <code>1 2 3</code>

⏰ Timeout: {timeout // 60} minutes"""
                    
                    send_telegram_message(message)
                    time.sleep(2)  # Délai pour que le message soit bien lu
                    
                    # Envoyer la capture complète avec l'instruction
                    caption = f"""📸 <b>CAPTCHA COMPLET</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 <b>INSTRUCTION:</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>{challenge_text}</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💬 <b>Répondez avec les numéros des images à sélectionner</b>
   Numérotation: <b>gauche à droite, de haut en bas</b>
   Exemple: <code>1,2,3</code> ou <code>1 2 3</code>"""
                    
                    # Essayer d'envoyer l'image avec retry
                    success = False
                    for attempt in range(3):
                        print(f"[CAPTCHA] Tentative d'envoi {attempt + 1}/3...")
                        if send_telegram_photo(full_screenshot_path, caption):
                            print("[CAPTCHA] ✅ Capture complète envoyée sur Telegram")
                            success = True
                            break
                        else:
                            print(f"[CAPTCHA] ⚠️ Échec envoi tentative {attempt + 1}, retry dans 2s...")
                            time.sleep(2)
                    
                    if not success:
                        print("[CAPTCHA] ❌ Échec envoi après 3 tentatives")
                        send_telegram_message(
                            "⚠️ <b>Erreur envoi image</b>\n\n"
                            "L'image n'a pas pu être envoyée. Vérifiez les logs."
                        )
                    else:
                        # Image envoyée : attendre la réponse de l'utilisateur (numéros des cases)
                        send_telegram_message(
                            "⏳ <b>En attente de votre réponse...</b>\n\n"
                            "Envoyez les numéros des cases à cocher (ex: <code>1,2,3</code>)\n"
                            "Si l'image change, envoyez les nouveaux numéros."
                        )
                        last_update_id = 0
                        start_time = time.time()
                        
                        # Fonction interne pour gérer les clics sur bouton Verify
                        def click_verify_button():
                            verify_selectors = [
                                "#recaptcha-verify-button",
                                ".rc-button-default",
                                "button.rc-button-default",
                                ".rc-imageselect-verify-button",
                                "button[type='submit']",
                            ]
                            button = None
                            for sel in verify_selectors:
                                try:
                                    btn = challenge_frame.query_selector(sel)
                                    if btn and btn.is_visible():
                                        button = btn
                                        break
                                except:
                                    pass
                            
                            if button:
                                try:
                                    button.evaluate("el => el.click()")
                                    print(f"[CAPTCHA] ✅ Bouton Verify clicked (JS)")
                                    return True
                                except:
                                    try:
                                         button.click(force=True)
                                         print(f"[CAPTCHA] ✅ Bouton Verify clicked (Standard)")
                                         return True
                                    except:
                                         return False
                            return False
                    
                        # Boucle principale d'interaction
                        while time.time() - start_time < timeout:
                            # 1. Vérifier si résolu AVANT toute action
                            if _is_captcha_solved(page):
                                send_telegram_message("✅ Captcha résolu! Le script continue...")
                                return True
                    
                            messages = get_telegram_messages(last_update_id)
                            for msg in messages:
                                last_update_id = max(last_update_id, msg["update_id"])
                                text = (msg.get("text") or "").strip().lower()
                                
                                # COMMANDE DE VÉRIFICATION
                                if text in ["v", "ok", "done", "valider", "verifier"]:
                                    send_telegram_message("✅ Validation en cours...")
                                    if click_verify_button():
                                        time.sleep(3)
                                        if _is_captcha_solved(page):
                                            send_telegram_message("✅ Captcha résolu!")
                                            return True
                                        else:
                                            send_telegram_message("⚠️ Pas encore résolu/nouvelle étape. Recapture...")
                                            # La suite de la boucle fera la recapture
                                    else:
                                        send_telegram_message("❌ Impossible de cliquer sur Vérifier (bouton introuvable)")

                                
                                # COMMANDE AUDIO
                                elif text in ["audio", "son", "mp3"]:
                                    send_telegram_message("🎧 Passage en mode Audio...")
                                    if wait_for_audio_captcha(page, challenge_frame, timeout=300):
                                        return True
                                    else:
                                        send_telegram_message("❌ Échec Audio. Retour mode Image.")
                                        # On recupère une capture pour revenir au mode image visuellement
                    
                                # COMMANDE DE CLIC IMAGES (chiffres)
                                else:
                                    numbers = re.findall(r"\d+", text)
                                    if numbers:
                                        image_indices = [int(n) for n in numbers]
                                        send_telegram_message(f"✅ Clic sur images: {', '.join(map(str, image_indices))}")
                                        
                                        # Juste cliquer sur les images, PAS de verify automatique
                                        click_captcha_images(challenge_frame, image_indices)
                                        
                                        # Attendre que l'animation de disparition/réapparition se fasse
                                        time.sleep(2)
                                        send_telegram_message("📸 Mise à jour de la capture...")
                    
                                # DANS TOUS LES CAS (sauf si résolu): Recapturer et envoyer l'état actuel
                                try:
                                    new_screenshot_path = os.path.join(temp_dir, f"captcha_update_{int(time.time())}.png")
                                    # Capture full page pour le contexte
                                    page.screenshot(path=new_screenshot_path, full_page=True)
                                    
                                    caption = (
                                        "📸 <b>État actuel</b>\n\n"
                                        "1️⃣ <b>Chiffres</b> : Clic Images\n"
                                        "2️⃣ <b>v</b> : Valider\n"
                                        "3️⃣ <b>audio</b> : Mode Audio 🎧\n"
                                    )
                                    start_send = time.time()
                                    send_telegram_photo(new_screenshot_path, caption)
                                    # Petit délai pour éviter spam si boucle rapide
                                    if time.time() - start_send < 2:
                                        time.sleep(1)
                                except Exception as e_cap:
                                    print(f"[CAPTCHA] Erreur recapture: {e_cap}")
                            
                            time.sleep(2)
                            
                        # Fin du while loop (timeout)
                        send_telegram_message(
                            "❌ <b>Timeout - Captcha non résolu</b>\n\n"
                            "⏸️ Le processus est mis en pause.\n"
                            "👉 Envoyez la commande <code>/launch</code> pour réessayer une nouvelle inscription."
                        )
                        print("[INFO] Timeout - Captcha non résolu. En attente de commande...")
                        return False
                else:
                    print(f"[CAPTCHA] ❌ Fichier vide (0 bytes)")
                    send_telegram_message("❌ Erreur: La capture est vide")
            else:
                print(f"[CAPTCHA] ❌ Fichier non trouvé: {full_screenshot_path}")
                send_telegram_message("❌ Erreur: La capture n'a pas pu être créée")
        else:
            # Fallback
            print("[CAPTCHA] Challenge détecté mais frame non accessible")
            send_telegram_message(
                "🔐 <b>CAPTCHA À RÉSOUDRE</b>\n\n"
                "⚠️ Challenge détecté mais non accessible.\n"
                "Veuillez résoudre manuellement dans le navigateur."
            )
            send_telegram_photo(screenshot_path, "Captcha à résoudre")
    
    else:
        # Captcha simple (checkbox) ou inconnu
        message = """🔐 <b>CAPTCHA À RÉSOUDRE</b>

📍 Site: the-odds-api.com
⏰ Timeout: 5 minutes

👉 Résolvez le captcha dans le navigateur
   (VNC/Remote Desktop sur votre serveur)

Le script continuera automatiquement une fois résolu."""
        
        send_telegram_message(message)
        send_telegram_photo(screenshot_path, "Captcha à résoudre")
    
    print("[TELEGRAM] 📱 Notification envoyée!")
    print("[INFO] En attente de résolution du captcha...")
    print(f"[INFO] Timeout: {timeout}s")
    
    # Sélecteurs pour détecter si captcha résolu
    selectors = [
        "#g-recaptcha-response-2",
        "#g-recaptcha-response",
        'textarea[name="g-recaptcha-response"]',
    ]
    
    start_time = time.time()
    last_notify = 0
    
    while time.time() - start_time < timeout:
        elapsed = int(time.time() - start_time)
        
        # Notifier toutes les 60 secondes
        if elapsed - last_notify >= 60:
            remaining = timeout - elapsed
            print(f"[INFO] Attente... {elapsed}s écoulées, {remaining}s restantes")
            last_notify = elapsed
        
        # Vérifier si captcha résolu
        for selector in selectors:
            try:
                token = page.evaluate(f'document.querySelector("{selector}")?.value || ""')
                if token and len(token) > 30:
                    send_telegram_message("✅ Captcha résolu! Le script continue...")
                    print("[SUCCESS] ✅ Captcha résolu!")
                    return True
            except:
                pass
        
        time.sleep(2)
    
    send_telegram_message(
        "❌ <b>Timeout - Captcha non résolu</b>\n\n"
        "⏸️ Le processus est mis en pause.\n"
        "👉 Envoyez la commande <code>/launch</code> pour réessayer une nouvelle inscription."
    )
    print("[INFO] Timeout - Captcha non résolu. En attente de commande...")
    return False


# ============================================
# MAIL.TM - Email temporaire
# ============================================
def get_mail_tm_domains():
    try:
        response = requests.get(f"{MAIL_TM_API}/domains", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "hydra:member" in data and len(data["hydra:member"]) > 0:
                return data["hydra:member"][0]["domain"]
    except:
        pass
    return None


def create_mail_tm_account():
    """Crée un email temporaire via Mail.tm API"""
    import random
    import string
    
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
        response = requests.post(
            f"{MAIL_TM_API}/accounts",
            json={"address": email, "password": password},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            print(f"[SUCCESS] Email: {email}")
            
            token_response = requests.post(
                f"{MAIL_TM_API}/token",
                json={"address": email, "password": password},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if token_response.status_code == 200:
                return email, token_response.json().get("token")
        
        print(f"[ERREUR] Création: {response.status_code}")
    except Exception as e:
        print(f"[ERREUR] Mail.tm: {e}")
    
    return None, None


# ============================================
# INSCRIPTION THE ODDS API
# ============================================
def register_odds_api(name: str, email: str):
    """S'inscrit sur the-odds-api.com avec relay Telegram"""
    success = False
    
    SELECTORS = {
        "start_button": ".oa-button",
        "name_input": 'input[name="name"]',
        "email_input": 'input[name="email"]',
        "captcha_iframe": 'iframe[title="reCAPTCHA"]',
        "subscribe_button": "input.subscribe",
    }
    
    def register_action(page):
        nonlocal success
        
        print("\n[ÉTAPE 2] Inscription sur the-odds-api.com")
        print("-" * 50)
        
        # Notifier le début
        send_telegram_message(f"""🚀 <b>Inscription en cours</b>

📧 Email: {email}
👤 Nom: {name}

⏳ Remplissage du formulaire...""")
        
        time.sleep(2)
        
        # Cliquer sur START
        print("[INFO] Clic sur START...")
        page.click(SELECTORS["start_button"])
        time.sleep(2)
        
        # Remplir le formulaire
        print(f"[INFO] Remplissage - Nom: {name}, Email: {email}")
        page.fill(SELECTORS["name_input"], name)
        time.sleep(0.5)
        page.fill(SELECTORS["email_input"], email)
        time.sleep(1)
        
        # Cliquer sur le captcha
        try:
            captcha = page.locator(SELECTORS["captcha_iframe"])
            if captcha.is_visible():
                box = captcha.bounding_box()
                if box:
                    x = box["x"] + box["width"] / 2
                    y = box["y"] + box["height"] / 2
                    print(f"[INFO] Clic sur captcha ({x:.0f}, {y:.0f})")
                    page.mouse.click(x, y)
                    time.sleep(3)
        except Exception as e:
            print(f"[DEBUG] Clic captcha: {e}")
        
        # Vérifier si captcha auto-résolu
        time.sleep(2)
        token = page.evaluate('document.querySelector("#g-recaptcha-response-2")?.value || ""')
        
        if token and len(token) > 30:
            print("[SUCCESS] Captcha auto-résolu!")
            send_telegram_message("✅ Captcha auto-résolu!")
        else:
            # Attendre résolution manuelle via Telegram (10 minutes)
            if not wait_for_captcha_with_telegram(page, timeout=600):
                return
        
        # Soumettre
        print("[INFO] Soumission...")
        page.click(SELECTORS["subscribe_button"])
        time.sleep(5)
        
        send_telegram_message("✅ Formulaire soumis avec succès!")
        print("[SUCCESS] Formulaire soumis!")
        success = True
    
    fetcher = StealthyFetcher()
    try:
        # Mode VISIBLE pour permettre la résolution manuelle
        fetcher.fetch(
            ODDS_API_URL,
            headless=False,  # IMPORTANT: visible pour résolution manuelle
            page_action=register_action,
            wait=10000,
            user_data_dir=USER_DATA_DIR
        )
    except Exception as e:
        print(f"[ERREUR] Fetcher: {e}")
        traceback.print_exc()
        success = False

    return success


# ============================================
# RÉCUPÉRATION CLÉ API
# ============================================
def get_api_key_from_email(token: str, max_wait: int = 300):
    """Récupère la clé API depuis l'email"""
    print("\n[ÉTAPE 3] Récupération clé API (Mail.tm)")
    print("-" * 50)
    
    send_telegram_message("📧 En attente de l'email avec la clé API...")
    
    headers = {"Authorization": f"Bearer {token}"}
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        elapsed = int(time.time() - start_time)
        print(f"[INFO] Vérification emails... ({elapsed}s/{max_wait}s)")
        
        try:
            response = requests.get(f"{MAIL_TM_API}/messages", headers=headers, timeout=10)
            
            if response.status_code == 200:
                messages = response.json().get("hydra:member", [])
                
                for msg in messages:
                    subject = msg.get("subject", "").lower()
                    sender = msg.get("from", {}).get("address", "").lower()
                    
                    if "odds" in subject or "odds" in sender or "api" in subject:
                        print(f"[SUCCESS] Email trouvé!")
                        
                        msg_response = requests.get(
                            f"{MAIL_TM_API}/messages/{msg.get('id')}",
                            headers=headers,
                            timeout=10
                        )
                        
                        if msg_response.status_code == 200:
                            content = msg_response.json().get("text", "")
                            html = msg_response.json().get("html", [""])[0] if msg_response.json().get("html") else ""
                            
                            match = re.search(r'([a-f0-9]{32})', content + html)
                            if match:
                                api_key = match.group(1)
                                
                                # Notifier sur Telegram
                                send_telegram_message(f"""🎉 <b>CLÉ API RÉCUPÉRÉE!</b>

🔑 <code>{api_key}</code>

Sauvegardée dans api_keys.txt""")
                                
                                print(f"\n{'=' * 60}")
                                print(f"   🎉 CLÉ API: {api_key}")
                                print(f"{'=' * 60}\n")
                                return api_key
        except Exception as e:
            print(f"[DEBUG] {e}")
        
        time.sleep(10)
    
    send_telegram_message("❌ Email non reçu après 5 minutes")
    print("[ERREUR] Email non reçu")
    return None


# ============================================
# MAIN
# ============================================
def main():
    # Vérification rapide (sans lancer le navigateur)
    if "--check" in sys.argv or "-c" in sys.argv:
        print_banner()
        print("[CHECK] Vérification des dépendances et de la config...")
        ok = True
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            print("  [X] TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquant")
            ok = False
        else:
            print("  [OK] Telegram configuré")
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe",
                timeout=5
            )
            if r.status_code != 200:
                print(f"  [X] Telegram API: {r.status_code}")
                ok = False
            else:
                print("  [OK] Connexion Telegram OK")
        except Exception as e:
            print(f"  [X] Telegram: {e}")
            ok = False
        name = generate_random_name()
        print(f"  [OK] Nom généré: {name}")
        env_path = SCRIPT_DIR / ".env"
        print(f"  [INFO] .env cherché: {env_path} (existe: {env_path.exists()})")
        if ok:
            print("\n[CHECK] Tout est OK. Lancez sans --check pour démarrer.")
        else:
            print("\n[CHECK] Corrigez les erreurs ci-dessus.")
        return 0 if ok else 1

    print_banner()

    # Démarrer le thread de vérification des commandes Telegram
    print("[INFO] Démarrage du système de commandes Telegram...")
    command_thread = threading.Thread(target=check_telegram_commands, daemon=True)
    command_thread.start()
    print("[SUCCESS] Système de commandes démarré")
    
    # Envoyer un message de bienvenue avec les commandes
    send_telegram_message(
        "🤖 <b>Bot d'inscription démarré!</b>\n\n"
        "📖 <b>Commandes disponibles:</b>\n"
        "/launch - Lancer/relancer le processus d'inscription\n"
        "/status - Voir le status actuel\n"
        "/help - Afficher l'aide\n\n"
        "💡 <b>Astuce:</b> Utilisez /launch pour démarrer ou relancer si le captcha expire"
    )
    
    # Générer un nom aléatoire si non fourni en argument
    if len(sys.argv) > 1:
        name = sys.argv[1]
        print(f"[INFO] Nom fourni: {name}")
    else:
        name = generate_random_name()
        print(f"[INFO] Nom généré aléatoirement: {name}")
    
    # Lancer le processus d'inscription
    run_registration_process(name)
    
    # Attendre que le thread de commandes continue à tourner
    print("[INFO] Le bot écoute les commandes Telegram. Appuyez sur Ctrl+C pour arrêter.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INFO] Arrêt demandé par l'utilisateur")
        send_telegram_message("⛔ <b>Bot arrêté</b>")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        print("\n[INFO] Interruption clavier")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERREUR FATALE] {e}")
        traceback.print_exc()
        sys.exit(1)

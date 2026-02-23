"""
Captcha Handler — Résolution reCAPTCHA via relay Telegram
=========================================================
Gère la détection, l'interaction et la résolution de captchas
reCAPTCHA v2 avec support:
- Auto-résolution (clic checkbox)
- Challenge images via relay Telegram
- Challenge audio via relay Telegram
"""

import os
import re
import time
import tempfile

from automation.telegram_relay import (
    send_telegram_message,
    send_telegram_photo,
    send_telegram_audio,
    get_telegram_messages,
)
from automation.audio_solver import solve_audio_captcha


# Dossier temporaire pour les captures
CAPTCHA_TEMP_DIR = os.path.join(os.path.dirname(__file__), "..", "captcha_temp")
os.makedirs(CAPTCHA_TEMP_DIR, exist_ok=True)


# ============================================================
# Détection
# ============================================================

def is_captcha_solved(page) -> bool:
    """Vérifie si le captcha est résolu (token reCAPTCHA présent)."""
    selectors = [
        "#g-recaptcha-response-2",
        "#g-recaptcha-response",
        'textarea[name="g-recaptcha-response"]',
    ]
    for selector in selectors:
        try:
            token = page.evaluate(f'document.querySelector("{selector}")?.value || ""')
            if token and len(token) > 30:
                return True
        except Exception:
            pass
    return False


def detect_captcha_type(page) -> dict:
    """
    Détecte le type de captcha présent sur la page.
    
    Returns:
        {
            "type": "checkbox" | "challenge" | "unknown",
            "iframe": iframe_element ou None,
            "challenge_text": str ou None,
            "challenge_frame": frame ou None,
            "has_audio": bool
        }
    """
    try:
        iframe = page.query_selector('iframe[title*="reCAPTCHA"]')
        if not iframe:
            return {"type": "unknown", "iframe": None}

        # Chercher un iframe de challenge (images)
        challenge_iframe = page.query_selector('iframe[title*="recaptcha challenge"]')

        if not challenge_iframe:
            return {"type": "checkbox", "iframe": iframe}

        # C'est un challenge avec images
        try:
            challenge_frame = challenge_iframe.content_frame()
            if not challenge_frame:
                return {"type": "challenge", "iframe": challenge_iframe,
                        "challenge_frame": None, "has_audio": False}

            # Récupérer l'instruction du challenge
            challenge_text = _extract_challenge_text(challenge_frame)

            # Vérifier si le mode audio est disponible
            audio_button = challenge_frame.query_selector(".rc-button-audio")

            return {
                "type": "challenge",
                "iframe": challenge_iframe,
                "challenge_text": challenge_text,
                "challenge_frame": challenge_frame,
                "has_audio": audio_button is not None,
            }

        except Exception as e:
            print(f"[CAPTCHA] Erreur détection challenge frame: {e}")

        return {"type": "challenge", "iframe": challenge_iframe,
                "challenge_frame": None, "has_audio": False}

    except Exception as e:
        print(f"[CAPTCHA] Erreur détection: {e}")
        return {"type": "unknown", "iframe": None}


def _extract_challenge_text(challenge_frame) -> str:
    """Extrait l'instruction textuelle du challenge captcha."""
    selectors = [
        ".rc-imageselect-desc-text",
        ".rc-imageselect-desc",
        "#rc-imageselect-desc",
        ".rc-imageselect-desc-no-canonical",
        "span.rc-imageselect-desc-text",
    ]
    for selector in selectors:
        try:
            elem = challenge_frame.query_selector(selector)
            if elem:
                text = elem.inner_text().strip()
                if text and len(text) > 5:
                    print(f"[CAPTCHA] Instruction: {text}")
                    return text
        except Exception:
            continue

    # Fallback: chercher dans le body avec patterns courants
    try:
        body = challenge_frame.query_selector("body")
        if body:
            all_text = body.inner_text().lower()
            patterns = {
                "feu": "Sélectionnez toutes les images avec des feux de circulation",
                "traffic": "Sélectionnez toutes les images avec des feux de circulation",
                "voiture": "Sélectionnez toutes les images avec des voitures",
                "car": "Sélectionnez toutes les images avec des voitures",
                "pont": "Sélectionnez toutes les images avec des ponts",
                "bridge": "Sélectionnez toutes les images avec des ponts",
                "panneau": "Sélectionnez toutes les images avec des panneaux",
                "sign": "Sélectionnez toutes les images avec des panneaux",
            }
            for keyword, description in patterns.items():
                if keyword in all_text:
                    return description
    except Exception:
        pass

    return "Sélectionnez les images"


# ============================================================
# Résolution automatique
# ============================================================

def try_auto_solve(page, wait_after_checkbox: int = 5) -> bool:
    """
    Tente de résoudre le captcha automatiquement (clic checkbox).
    
    Returns:
        True si le captcha a été résolu automatiquement.
    """
    try:
        iframe = page.query_selector('iframe[title*="reCAPTCHA"]')
        if not iframe:
            return False

        box = iframe.bounding_box()
        if not box:
            return False

        # Clic sur la checkbox reCAPTCHA
        x = box["x"] + box["width"] / 2
        y = box["y"] + box["height"] / 2
        page.mouse.click(x, y)
        print("[CAPTCHA] Clic sur la checkbox reCAPTCHA")

        time.sleep(wait_after_checkbox)

        if is_captcha_solved(page):
            print("[CAPTCHA] ✅ Résolu automatiquement (checkbox seule)")
            return True

    except Exception as e:
        print(f"[CAPTCHA] Auto-solve erreur: {e}")

    return False


# ============================================================
# Interaction avec les images
# ============================================================

def click_images(challenge_frame, image_indices: list[int]) -> bool:
    """
    Clique sur les images du captcha par leurs indices (1-indexed).
    
    Args:
        challenge_frame: Le ContentFrame du challenge
        image_indices: Liste d'indices 1-indexed (ex: [1, 3, 5])
    """
    try:
        # Chercher les tiles d'images
        tile_selectors = [
            ".rc-imageselect-tile",
            "td.rc-imageselect-tile",
            "table.rc-imageselect-table td",
        ]

        image_tiles = None
        for selector in tile_selectors:
            tiles = challenge_frame.query_selector_all(selector)
            if tiles and len(tiles) > 0:
                image_tiles = tiles
                break

        if not image_tiles:
            # Dernier recours: tous les td avec images
            all_tds = challenge_frame.query_selector_all("td")
            image_tiles = [
                t for t in all_tds
                if t.query_selector("img") or t.query_selector("div[style*='background']")
            ]

        if not image_tiles:
            print("[CAPTCHA] ❌ Aucune image trouvée")
            return False

        print(f"[CAPTCHA] {len(image_tiles)} images trouvées, clic sur: {image_indices}")

        for idx in image_indices:
            array_idx = idx - 1  # Convertir en 0-indexed
            if 0 <= array_idx < len(image_tiles):
                try:
                    tile = image_tiles[array_idx]
                    tile.click(force=True)
                    print(f"[CAPTCHA] ✅ Image {idx} cliquée")
                    time.sleep(0.5)
                except Exception as e:
                    print(f"[CAPTCHA] ❌ Erreur clic image {idx}: {e}")
            else:
                print(f"[CAPTCHA] ⚠️ Indice {idx} hors limites (max {len(image_tiles)})")

        return True

    except Exception as e:
        print(f"[CAPTCHA] ❌ Erreur click_images: {e}")
        return False


def _click_verify_button(challenge_frame) -> bool:
    """Clique sur le bouton Vérifier du captcha."""
    verify_selectors = [
        "#recaptcha-verify-button",
        ".rc-button-default",
        "button.rc-button-default",
        ".rc-imageselect-verify-button",
        "button[type='submit']",
    ]
    for sel in verify_selectors:
        try:
            btn = challenge_frame.query_selector(sel)
            if btn and btn.is_visible():
                try:
                    btn.evaluate("el => el.click()")
                    print("[CAPTCHA] ✅ Bouton Verify cliqué (JS)")
                    return True
                except Exception:
                    btn.click(force=True)
                    print("[CAPTCHA] ✅ Bouton Verify cliqué (force)")
                    return True
        except Exception:
            pass
    return False


# ============================================================
# Mode Audio
# ============================================================

def handle_audio_captcha(
    page,
    challenge_frame,
    bot_token: str,
    chat_id: str,
    timeout: int = 300
) -> bool:
    """
    Gère le captcha audio: passage en mode audio, envoi sur Telegram,
    attente de la réponse (texte), soumission.
    """
    print("[CAPTCHA] 🎧 Passage en mode AUDIO...")

    # 1. Cliquer sur le bouton Audio
    audio_btn_selectors = [
        "#recaptcha-audio-button",
        "button.rc-button-audio",
        ".rc-button-audio",
    ]

    clicked = False
    for sel in audio_btn_selectors:
        try:
            btn = challenge_frame.query_selector(sel)
            if btn:
                btn.click(force=True)
                print(f"[CAPTCHA] ✅ Bouton Audio cliqué ({sel})")
                clicked = True
                break
        except Exception:
            pass

    if not clicked:
        print("[CAPTCHA] ❌ Bouton Audio introuvable")
        return False

    time.sleep(3)

    # 2. Vérifier blocage ("Try again later")
    try:
        content = challenge_frame.content()
        if "Try again later" in content or "réessayez plus tard" in content:
            print("[CAPTCHA] ⚠️ Bloqué: 'Try again later'")
            send_telegram_message(
                bot_token, chat_id,
                "⚠️ <b>Audio bloqué</b>: Google a limité les requêtes. "
                "Changez d'IP ou repassez en mode image."
            )
            return False
    except Exception:
        pass

    # 3. Boucle principale audio
    start_wait = time.time()
    last_update_id = 0

    while time.time() - start_wait < timeout:
        # Récupérer l'URL audio
        audio_url = _get_audio_url(challenge_frame)
        if not audio_url:
            print("[CAPTCHA] ❌ URL Audio introuvable")
            return False

        print(f"[CAPTCHA] 🔗 Audio: {audio_url[:60]}...")

        # Télécharger et envoyer sur Telegram
        audio_path = os.path.join(CAPTCHA_TEMP_DIR, f"captcha_audio_{int(time.time())}.mp3")
        try:
            import requests as req
            resp = req.get(audio_url, timeout=30)
            if resp.status_code != 200:
                print("[CAPTCHA] ❌ Téléchargement audio échoué")
                return False

            with open(audio_path, "wb") as f:
                f.write(resp.content)

            send_telegram_message(
                bot_token, chat_id,
                "🎧 <b>CAPTCHA AUDIO</b>\n\n"
                "1️⃣ Écoutez et envoyez le code\n"
                "2️⃣ Envoyez <b>r</b> pour rafraîchir l'audio"
            )
            send_telegram_audio(bot_token, chat_id, audio_path, "Captcha Audio")

        except Exception as e:
            print(f"[CAPTCHA] ❌ Erreur audio: {e}")
            return False

        # Attendre la réponse
        loop_start = time.time()
        refreshed = False

        while time.time() - loop_start < 120:
            messages = get_telegram_messages(bot_token, chat_id, last_update_id)

            for msg in messages:
                last_update_id = max(last_update_id, msg["update_id"])
                text = (msg.get("text") or "").strip().lower()

                # Commande refresh
                if text in ["r", "refresh", "actualiser", "reload", "new"]:
                    print("[CAPTCHA] 🔄 Refresh audio demandé")
                    send_telegram_message(bot_token, chat_id, "🔄 Actualisation audio...")
                    _click_reload_button(challenge_frame)
                    time.sleep(3)
                    refreshed = True
                    break

                # Code audio
                elif text and len(text) > 2:
                    print(f"[CAPTCHA] 📩 Code reçu: {text}")
                    send_telegram_message(bot_token, chat_id, f"✅ Essai: <code>{text}</code>")

                    try:
                        input_field = challenge_frame.query_selector("#audio-response")
                        if input_field:
                            input_field.fill(text)
                            time.sleep(1)

                            verify_btn = challenge_frame.query_selector("#recaptcha-verify-button")
                            if verify_btn:
                                verify_btn.click()
                                time.sleep(3)

                                if is_captcha_solved(page):
                                    send_telegram_message(bot_token, chat_id, "✅ Audio validé!")
                                    return True
                                else:
                                    send_telegram_message(
                                        bot_token, chat_id,
                                        "❌ Code incorrect. Réessayez ou envoyez 'r' pour changer."
                                    )
                    except Exception as e:
                        print(f"[CAPTCHA] Erreur saisie audio: {e}")

            if refreshed:
                break

            time.sleep(2)

    return False


def _get_audio_url(challenge_frame) -> str | None:
    """Récupère l'URL du fichier audio du captcha."""
    try:
        link = challenge_frame.query_selector(".rc-audiochallenge-download-link")
        if link:
            url = link.get_attribute("href")
            if url:
                return url

        audio_src = challenge_frame.query_selector("#audio-source")
        if audio_src:
            return audio_src.get_attribute("src")
    except Exception:
        pass
    return None


def _click_reload_button(challenge_frame):
    """Clique sur le bouton Reload du captcha."""
    for sel in ["#recaptcha-reload-button", ".rc-button-reload"]:
        try:
            btn = challenge_frame.query_selector(sel)
            if btn:
                btn.click()
                print(f"[CAPTCHA] ✅ Reload cliqué ({sel})")
                return
        except Exception:
            pass


# ============================================================
# Fonction principale: relay interactif via Telegram
# ============================================================

def wait_for_captcha_with_telegram(
    page,
    bot_token: str,
    chat_id: str,
    timeout: int = 600
) -> bool:
    """
    Résolution interactive du captcha via relay Telegram.
    
    1. Tente la résolution automatique (checkbox)
    2. Si challenge images: capture → Telegram → attente réponse
    3. Support commandes: chiffres (clic images), v (valider),
       audio (mode audio)
    
    Args:
        page: Page Scrapling/Playwright
        bot_token: Token du bot Telegram
        chat_id: Chat ID Telegram
        timeout: Durée max d'attente (défaut: 10 min)
    
    Returns:
        True si captcha résolu, False si timeout
    """
    print(f"[CAPTCHA] Délai max: {timeout}s ({timeout // 60} min)")

    # 1. Tenter la résolution automatique
    if try_auto_solve(page):
        return True

    # 2. Détecter le type de captcha
    captcha_info = detect_captcha_type(page)
    print(f"[CAPTCHA] Type: {captcha_info['type']}")

    if captcha_info["type"] == "challenge" and captcha_info.get("challenge_frame"):
        return _handle_image_challenge(
            page, captcha_info, bot_token, chat_id, timeout
        )

    # Captcha simple ou inconnu: attente passive
    return _handle_passive_wait(page, bot_token, chat_id, timeout)


def _handle_image_challenge(
    page, captcha_info: dict,
    bot_token: str, chat_id: str,
    timeout: int
) -> bool:
    """Gère un challenge captcha avec images via relay Telegram."""
    challenge_frame = captcha_info["challenge_frame"]
    challenge_text = captcha_info.get("challenge_text", "Sélectionnez les images")

    # Capture et envoi
    screenshot_path = os.path.join(CAPTCHA_TEMP_DIR, "captcha_challenge.png")
    try:
        page.screenshot(path=screenshot_path, full_page=True)
    except Exception:
        try:
            page.screenshot(path=screenshot_path)
        except Exception as e:
            print(f"[CAPTCHA] ❌ Capture impossible: {e}")
            send_telegram_message(bot_token, chat_id, "❌ Capture captcha impossible")
            return False

    if not os.path.exists(screenshot_path) or os.path.getsize(screenshot_path) == 0:
        send_telegram_message(bot_token, chat_id, "❌ Capture captcha vide")
        return False

    # Envoyer l'instruction
    send_telegram_message(
        bot_token, chat_id,
        f"🔐 <b>CAPTCHA IMAGES</b>\n\n"
        f"📝 <b>{challenge_text}</b>\n\n"
        f"💬 Répondez avec les numéros (ex: <code>1,3,5</code>)\n"
        f"📌 <b>v</b> = valider | <b>audio</b> = mode audio\n"
        f"⏰ Timeout: {timeout // 60} min"
    )
    time.sleep(1)
    send_telegram_photo(bot_token, chat_id, screenshot_path, f"📝 {challenge_text}")

    # Boucle d'interaction
    last_update_id = 0
    start_time = time.time()

    while time.time() - start_time < timeout:
        # Vérifier si résolu
        if is_captcha_solved(page):
            send_telegram_message(bot_token, chat_id, "✅ Captcha résolu!")
            return True

        messages = get_telegram_messages(bot_token, chat_id, last_update_id)

        for msg in messages:
            last_update_id = max(last_update_id, msg["update_id"])
            text = (msg.get("text") or "").strip().lower()

            # Commande: valider
            if text in ["v", "ok", "done", "valider", "verifier"]:
                send_telegram_message(bot_token, chat_id, "✅ Validation...")
                if _click_verify_button(challenge_frame):
                    time.sleep(3)
                    if is_captcha_solved(page):
                        send_telegram_message(bot_token, chat_id, "✅ Captcha résolu!")
                        return True
                    send_telegram_message(bot_token, chat_id, "⚠️ Pas encore résolu. Recapture...")
                else:
                    send_telegram_message(bot_token, chat_id, "❌ Bouton Vérifier introuvable")

            # Commande: audio
            elif text in ["audio", "son", "mp3"]:
                send_telegram_message(bot_token, chat_id, "🎧 Mode Audio...")
                if handle_audio_captcha(page, challenge_frame, bot_token, chat_id, timeout=300):
                    return True
                send_telegram_message(bot_token, chat_id, "❌ Audio échoué, retour images")

            # Commande: numéros d'images
            else:
                numbers = re.findall(r"\d+", text)
                if numbers:
                    image_indices = [int(n) for n in numbers]
                    send_telegram_message(
                        bot_token, chat_id,
                        f"✅ Clic images: {', '.join(map(str, image_indices))}"
                    )
                    click_images(challenge_frame, image_indices)
                    time.sleep(2)

            # Recapturer l'état actuel après toute action
            _send_updated_screenshot(page, bot_token, chat_id)

        time.sleep(2)

    # Timeout
    send_telegram_message(
        bot_token, chat_id,
        "❌ <b>Timeout captcha</b>\n\n"
        "Envoyez <code>/launch</code> pour réessayer."
    )
    return False


def _handle_passive_wait(
    page, bot_token: str, chat_id: str, timeout: int
) -> bool:
    """Attente passive que le captcha soit résolu (checkbox ou inconnu)."""
    # Prendre une capture
    screenshot_path = os.path.join(CAPTCHA_TEMP_DIR, "captcha_passive.png")
    try:
        page.screenshot(path=screenshot_path)
    except Exception:
        pass

    send_telegram_message(
        bot_token, chat_id,
        "🔐 <b>CAPTCHA À RÉSOUDRE</b>\n\n"
        "📍 Site: the-odds-api.com\n"
        f"⏰ Timeout: {timeout // 60} minutes\n\n"
        "👉 Résolvez dans le navigateur (VNC/Remote Desktop)"
    )

    if os.path.exists(screenshot_path):
        send_telegram_photo(bot_token, chat_id, screenshot_path, "Captcha")

    print("[CAPTCHA] Attente résolution passive...")

    start_time = time.time()
    last_notify = 0

    while time.time() - start_time < timeout:
        elapsed = int(time.time() - start_time)

        if elapsed - last_notify >= 60:
            remaining = timeout - elapsed
            print(f"[CAPTCHA] Attente... {elapsed}s/{timeout}s")
            last_notify = elapsed

        if is_captcha_solved(page):
            send_telegram_message(bot_token, chat_id, "✅ Captcha résolu!")
            print("[CAPTCHA] ✅ Résolu!")
            return True

        time.sleep(2)

    send_telegram_message(
        bot_token, chat_id,
        "❌ <b>Timeout captcha</b>\n\n"
        "Envoyez <code>/launch</code> pour réessayer."
    )
    return False


def _send_updated_screenshot(page, bot_token: str, chat_id: str):
    """Envoie une capture d'écran mise à jour sur Telegram."""
    try:
        path = os.path.join(CAPTCHA_TEMP_DIR, f"captcha_update_{int(time.time())}.png")
        page.screenshot(path=path, full_page=True)
        send_telegram_photo(
            bot_token, chat_id, path,
            "📸 <b>État actuel</b>\n\n"
            "1️⃣ <b>Chiffres</b> → Clic images\n"
            "2️⃣ <b>v</b> → Valider\n"
            "3️⃣ <b>audio</b> → Mode Audio 🎧"
        )
    except Exception as e:
        print(f"[CAPTCHA] Erreur recapture: {e}")


# ============================================================
# Mode Autonome (API Whisper + LLM)
# ============================================================

def solve_captcha_autonomous(page, max_retries: int = 3) -> bool:
    """
    Résolution 100% autonome du captcha via le canal audio.

    Flux:
    1. Tente auto-solve (checkbox seule — Méthode A)
    2. Si challenge → bascule en mode audio
    3. Télécharge MP3 → API Whisper → correction LLM
    4. Tape la réponse → clique Verify
    5. Si échec → clique Régénérer → retry
    6. Détection rate-limit → abort propre

    Args:
        page: Page Playwright (via StealthyFetcher page_action)
        max_retries: Nombre max de tentatives (défaut: 3)

    Returns:
        True si captcha résolu, False sinon.
    """
    print(f"[CAPTCHA] 🤖 Mode AUTONOME ({max_retries} tentatives max)")

    # 1. Tenter la résolution automatique (checkbox)
    if try_auto_solve(page, wait_after_checkbox=5):
        print("[CAPTCHA] ✅ Auto-résolu par checkbox (Méthode A)")
        return True

    # 2. Détecter le challenge
    captcha_info = detect_captcha_type(page)
    if captcha_info["type"] == "unknown":
        print("[CAPTCHA] ❌ Captcha non détecté")
        return False

    challenge_frame = captcha_info.get("challenge_frame")
    if not challenge_frame:
        # Tenter de recharger pour obtenir le challenge frame
        time.sleep(2)
        captcha_info = detect_captcha_type(page)
        challenge_frame = captcha_info.get("challenge_frame")
        if not challenge_frame:
            print("[CAPTCHA] ❌ Challenge frame introuvable")
            return False

    # 3. Boucle de résolution audio
    for attempt in range(1, max_retries + 1):
        print(f"\n[CAPTCHA] 🎧 Tentative {attempt}/{max_retries}")

        result = _attempt_audio_solve(page, challenge_frame)

        if result == "solved":
            print(f"[CAPTCHA] ✅ Résolu à la tentative {attempt}")
            return True

        if result == "rate_limited":
            print("[CAPTCHA] ⛔ Rate-limité par Google, arrêt")
            return False

        if result == "failed" and attempt < max_retries:
            # Régénérer le captcha avant de retenter
            print("[CAPTCHA] 🔄 Régénération du captcha...")
            _click_reload_button(challenge_frame)
            time.sleep(3)

            # Re-vérifier le challenge frame après régénération
            captcha_info = detect_captcha_type(page)
            challenge_frame = captcha_info.get("challenge_frame")
            if not challenge_frame:
                print("[CAPTCHA] ❌ Challenge frame perdu après régénération")
                return False

    print(f"[CAPTCHA] ❌ Échec après {max_retries} tentatives")
    return False


def _attempt_audio_solve(page, challenge_frame) -> str:
    """
    Une tentative de résolution audio.

    Returns:
        "solved" | "rate_limited" | "failed"
    """
    # Passer en mode audio
    audio_btn_selectors = [
        "#recaptcha-audio-button",
        "button.rc-button-audio",
        ".rc-button-audio",
    ]

    clicked = False
    for sel in audio_btn_selectors:
        try:
            btn = challenge_frame.query_selector(sel)
            if btn:
                btn.click(force=True)
                print(f"[CAPTCHA] ✅ Bouton Audio cliqué ({sel})")
                clicked = True
                break
        except Exception:
            pass

    if not clicked:
        print("[CAPTCHA] ❌ Bouton Audio introuvable")
        return "failed"

    time.sleep(3)

    # Vérifier le rate-limit
    try:
        content = challenge_frame.content()
        rate_limit_phrases = [
            "Try again later",
            "try again later",
            "réessayez plus tard",
            "automated queries",
            "requêtes automatisées",
            "Your computer or network may be sending automated queries",
        ]
        for phrase in rate_limit_phrases:
            if phrase in content:
                print(f"[CAPTCHA] ⛔ Rate-limit détecté: '{phrase}'")
                return "rate_limited"
    except Exception:
        pass

    # Récupérer l'URL audio
    audio_url = _get_audio_url(challenge_frame)
    if not audio_url:
        print("[CAPTCHA] ❌ URL audio introuvable")
        return "failed"

    print(f"[CAPTCHA] 🔗 Audio URL: {audio_url[:80]}...")

    # Résoudre via le pipeline audio
    answer = solve_audio_captcha(audio_url)
    if not answer:
        print("[CAPTCHA] ❌ Résolution audio échouée")
        return "failed"

    print(f"[CAPTCHA] 📝 Réponse: '{answer}'")

    # Taper la réponse dans le champ audio
    try:
        input_field = challenge_frame.query_selector("#audio-response")
        if not input_field:
            print("[CAPTCHA] ❌ Champ audio-response introuvable")
            return "failed"

        input_field.fill(answer)
        time.sleep(1)

        # Cliquer Verify
        verify_btn = challenge_frame.query_selector("#recaptcha-verify-button")
        if verify_btn:
            verify_btn.click()
            print("[CAPTCHA] ✅ Bouton Verify cliqué")
        else:
            # Fallback: submit via Enter
            input_field.press("Enter")
            print("[CAPTCHA] ✅ Submit via Enter")

        time.sleep(3)

        # Vérifier si résolu
        if is_captcha_solved(page):
            return "solved"

        # Vérifier si rate-limité après soumission
        try:
            content = challenge_frame.content()
            if "Try again later" in content or "automated queries" in content:
                return "rate_limited"
        except Exception:
            pass

        print("[CAPTCHA] ⚠️ Réponse incorrecte")
        return "failed"

    except Exception as e:
        print(f"[CAPTCHA] ❌ Erreur injection réponse: {e}")
        return "failed"


# ============================================================
# Extraction du token
# ============================================================

def extract_recaptcha_token(page) -> str | None:
    """
    Extrait le g-recaptcha-response token depuis le DOM
    après résolution du captcha.

    Args:
        page: Page Playwright

    Returns:
        Token reCAPTCHA (string longue) ou None si non trouvé.
    """
    selectors = [
        "#g-recaptcha-response-2",
        "#g-recaptcha-response",
        'textarea[name="g-recaptcha-response"]',
    ]

    for selector in selectors:
        try:
            token = page.evaluate(
                f'document.querySelector("{selector}")?.value || ""'
            )
            if token and len(token) > 30:
                print(f"[CAPTCHA] 🔑 Token extrait ({len(token)} chars)")
                return token
        except Exception:
            pass

    print("[CAPTCHA] ❌ Token reCAPTCHA introuvable")
    return None

"""
Audio Solver — Résolution captcha audio via API
=================================================
Pipeline complet : téléchargement MP3 → prétraitement audio →
transcription via API Whisper → correction LLM → texte final.

Utilise des APIs compatibles OpenAI (configurable via .env).
"""

import os
import re
import tempfile
import time
from pathlib import Path

import requests

# Charger les variables d'environnement
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ============================================================
# Configuration API
# ============================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# Répertoire temporaire pour les fichiers audio
AUDIO_TEMP_DIR = Path(__file__).resolve().parent.parent / "captcha_temp"
AUDIO_TEMP_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# Téléchargement
# ============================================================

def download_audio(url: str) -> str | None:
    """
    Télécharge le fichier MP3 du captcha audio.

    Args:
        url: URL du fichier MP3

    Returns:
        Chemin du fichier téléchargé, ou None si échec.
    """
    try:
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            print(f"[AUDIO] ❌ Téléchargement échoué: HTTP {response.status_code}")
            return None

        audio_path = str(AUDIO_TEMP_DIR / f"captcha_{int(time.time())}.mp3")
        with open(audio_path, "wb") as f:
            f.write(response.content)

        print(f"[AUDIO] ✅ Audio téléchargé ({len(response.content)} bytes)")
        return audio_path

    except Exception as e:
        print(f"[AUDIO] ❌ Erreur téléchargement: {e}")
        return None


# ============================================================
# Prétraitement audio
# ============================================================

def preprocess_audio(mp3_path: str) -> str | None:
    """
    Convertit le MP3 en WAV 16kHz mono et normalise le volume.

    Args:
        mp3_path: Chemin du fichier MP3

    Returns:
        Chemin du fichier WAV optimisé, ou None si échec.
    """
    try:
        from pydub import AudioSegment
        from pydub.effects import normalize

        # Charger le MP3
        audio = AudioSegment.from_mp3(mp3_path)

        # Convertir en mono 16kHz
        audio = audio.set_channels(1).set_frame_rate(16000)

        # Normaliser le volume
        audio = normalize(audio)

        # Sauvegarder en WAV
        wav_path = mp3_path.replace(".mp3", ".wav")
        audio.export(wav_path, format="wav")

        print(f"[AUDIO] ✅ Prétraitement OK → {wav_path}")
        return wav_path

    except ImportError:
        print("[AUDIO] ⚠️ pydub non installé, envoi du MP3 brut")
        return mp3_path

    except Exception as e:
        print(f"[AUDIO] ⚠️ Prétraitement échoué: {e}")
        return mp3_path


# ============================================================
# Transcription via API Whisper
# ============================================================

def transcribe_audio(audio_path: str) -> str | None:
    """
    Transcrit le fichier audio via l'API Whisper
    (compatible OpenAI /v1/audio/transcriptions).

    Args:
        audio_path: Chemin du fichier audio (MP3 ou WAV)

    Returns:
        Texte transcrit, ou None si échec.
    """
    if not OPENAI_API_KEY:
        print("[AUDIO] ❌ OPENAI_API_KEY non configurée")
        return None

    url = f"{OPENAI_BASE_URL}/audio/transcriptions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }

    try:
        with open(audio_path, "rb") as audio_file:
            response = requests.post(
                url,
                headers=headers,
                files={"file": audio_file},
                data={
                    "model": WHISPER_MODEL,
                    "language": "en",
                    "response_format": "text",
                },
                timeout=30,
            )

        if response.status_code != 200:
            print(f"[AUDIO] ❌ API Whisper erreur: {response.status_code}")
            print(f"[AUDIO] Réponse: {response.text[:200]}")
            return None

        # response_format=text renvoie du texte brut
        raw_text = response.text.strip()
        print(f"[AUDIO] 🎤 Transcription brute: '{raw_text}'")
        return raw_text

    except Exception as e:
        print(f"[AUDIO] ❌ Erreur transcription: {e}")
        return None


# ============================================================
# Correction LLM
# ============================================================

# Prompt spécialisé pour la correction de captchas audio
_LLM_CORRECTION_PROMPT = """You are a specialist in correcting speech-to-text transcriptions of Google reCAPTCHA audio challenges.

The audio challenges contain a sequence of spoken digits or words with background noise. Common misheard patterns include:
- "heaven" or "seven" → 7
- "tree" or "free" → 3  
- "won" or "one" or "juan" → 1
- "too" or "to" or "two" → 2
- "for" or "four" or "fore" → 4
- "ate" or "eight" → 8
- "nein" or "nine" → 9
- "sex" or "six" → 6
- "oh" or "zero" → 0
- "fie" or "five" → 5

Rules:
1. Extract ONLY the digits/numbers from the transcription
2. Return them as a single string of space-separated words (e.g., "7 3 9 1 5")
3. If the transcription contains actual spoken words that are numbers, convert them
4. Ignore any background noise descriptions or non-number words
5. Return ONLY the corrected answer, nothing else"""


def correct_with_llm(raw_text: str) -> str:
    """
    Corrige la transcription Whisper avec le LLM pour
    résoudre les ambiguïtés courantes des captchas audio.

    Args:
        raw_text: Texte brut de la transcription Whisper

    Returns:
        Texte corrigé (ou le texte original si LLM indisponible)
    """
    if not OPENAI_API_KEY:
        print("[AUDIO] ⚠️ LLM indisponible, utilisation du texte brut")
        return _basic_cleanup(raw_text)

    url = f"{OPENAI_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": _LLM_CORRECTION_PROMPT},
            {"role": "user", "content": f"Transcription to correct: \"{raw_text}\""},
        ],
        "temperature": 0.1,
        "max_tokens": 50,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)

        if response.status_code != 200:
            print(f"[AUDIO] ⚠️ LLM erreur: {response.status_code}")
            return _basic_cleanup(raw_text)

        data = response.json()
        corrected = data["choices"][0]["message"]["content"].strip()
        print(f"[AUDIO] 🧠 Correction LLM: '{raw_text}' → '{corrected}'")
        return corrected

    except Exception as e:
        print(f"[AUDIO] ⚠️ Erreur LLM: {e}")
        return _basic_cleanup(raw_text)


def _basic_cleanup(text: str) -> str:
    """Nettoyage basique si le LLM n'est pas disponible."""
    # Extraire uniquement les chiffres et mots-nombres
    number_words = {
        "zero": "0", "one": "1", "two": "2", "three": "3",
        "four": "4", "five": "5", "six": "6", "seven": "7",
        "eight": "8", "nine": "9",
    }

    words = text.lower().split()
    result = []

    for word in words:
        word_clean = re.sub(r"[^a-z0-9]", "", word)
        if word_clean in number_words:
            result.append(number_words[word_clean])
        elif word_clean.isdigit():
            result.append(word_clean)

    cleaned = " ".join(result) if result else text
    print(f"[AUDIO] 🔧 Nettoyage basique: '{text}' → '{cleaned}'")
    return cleaned


# ============================================================
# Pipeline complet
# ============================================================

def solve_audio_captcha(mp3_url: str) -> str | None:
    """
    Pipeline complet de résolution d'un captcha audio :
    download → preprocess → transcribe → correct.

    Args:
        mp3_url: URL du fichier MP3 du captcha

    Returns:
        Texte corrigé à soumettre, ou None si échec.
    """
    print(f"[AUDIO] 🚀 Résolution captcha audio...")
    print(f"[AUDIO] 🔗 URL: {mp3_url[:80]}...")

    # 1. Télécharger
    mp3_path = download_audio(mp3_url)
    if not mp3_path:
        return None

    # 2. Prétraiter
    processed_path = preprocess_audio(mp3_path)
    if not processed_path:
        return None

    # 3. Transcrire
    raw_text = transcribe_audio(processed_path)
    if not raw_text:
        return None

    # 4. Corriger avec LLM
    corrected = correct_with_llm(raw_text)

    # Nettoyage du répertoire temporaire (garder les 5 derniers)
    _cleanup_temp_files()

    return corrected


def _cleanup_temp_files():
    """Supprime les anciens fichiers temporaires (garder les 5 derniers)."""
    try:
        files = sorted(
            AUDIO_TEMP_DIR.glob("captcha_*"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        for f in files[10:]:  # Garder les 10 plus récents
            f.unlink(missing_ok=True)
    except Exception:
        pass

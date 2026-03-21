# Gestionnaire de clés API avec failover automatique - VERSION CORRIGÉE

import asyncio
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import subprocess
import sys


@dataclass
class APIKey:
    """Représente une clé API."""
    email: str
    key: str
    is_valid: bool = True
    requests_used: int = 0
    error_count: int = 0  # Nouveau: compteur d'erreurs


class APIManager:
    """
    Gère les clés API avec failover automatique.
    
    Bascule sur la clé de réserve quand:
    - L'API retourne une erreur 401/429 (quota épuisé)
    - OUT_OF_USAGE_CREDITS dans la réponse
    - La clé actuelle est marquée invalide
    """
    
    def __init__(self, keys_file: Path, auto_generate: bool = True):
        self.keys_file = keys_file
        self.auto_generate = auto_generate
        self.keys: list[APIKey] = []
        self.current_index = 0
        self._lock = asyncio.Lock()
        self.failover_count = 0  # Compteur de failovers
        self.last_error = None  # Dernière erreur
        
    def load_keys(self) -> int:
        """Charge les clés depuis le fichier."""
        self.keys = []
        
        if not self.keys_file.exists():
            print(f"[APIManager] ⚠️ Fichier de clés non trouvé: {self.keys_file}")
            return 0
            
        with open(self.keys_file, "r") as f:
            for line in f:
                line = line.strip()
                if ":" in line:
                    email, key = line.split(":", 1)
                    self.keys.append(APIKey(email=email, key=key))
                elif line and len(line) == 32:
                    self.keys.append(APIKey(email="unknown", key=line))
        
        print(f"[APIManager] ✅ {len(self.keys)} clé(s) API chargée(s)")
        return len(self.keys)
    
    @property
    def current_key(self) -> Optional[str]:
        """Retourne la clé API active."""
        if not self.keys:
            return None
        return self.keys[self.current_index].key
    
    @property
    def current_email(self) -> Optional[str]:
        """Retourne l'email associé à la clé active."""
        if not self.keys:
            return None
        return self.keys[self.current_index].email
    
    @property
    def valid_keys_count(self) -> int:
        """Nombre de clés valides."""
        return sum(1 for k in self.keys if k.is_valid)
    
    async def handle_api_error(self, status_code: int, response_text: str = "") -> bool:
        """
        Gère une erreur API.
        
        Args:
            status_code: Code HTTP de la réponse
            response_text: Message d'erreur
            
        Returns:
            True si failover réussi, False sinon
        """
        self.last_error = f"HTTP {status_code}: {response_text[:100]}"
        
        # Détecter les erreurs de quota (codes + texte)
        quota_error = (
            status_code in [401, 402, 429] or 
            "quota" in response_text.lower() or
            "OUT_OF_USAGE_CREDITS" in response_text or
            "usage" in response_text.lower()
        )
        
        if quota_error:
            print(f"[APIManager] ⚠️ Erreur quota détectée: {status_code}")
            print(f"[APIManager] 📝 Réponse: {response_text[:200]}")
            return await self.failover()
        
        return False
    
    async def failover(self) -> bool:
        """
        Bascule vers la prochaine clé valide.
        
        Returns:
            True si failover réussi, False si plus de clés
        """
        async with self._lock:
            self.failover_count += 1
            
            # Marquer la clé actuelle comme invalide
            if self.keys:
                old_key = self.keys[self.current_index]
                old_key.is_valid = False
                old_key.error_count += 1
                print(f"[APIManager] ❌ Clé {old_key.key[:8]}... marquée invalide")
            
            # Chercher la prochaine clé valide
            original_index = self.current_index
            
            for _ in range(len(self.keys)):
                self.current_index = (self.current_index + 1) % len(self.keys)
                if self.keys[self.current_index].is_valid:
                    new_key = self.keys[self.current_index]
                    print(f"[APIManager] ✅ Failover vers clé {new_key.key[:8]}... ({new_key.email})")
                    return True
                if self.current_index == original_index:
                    break
            
            print(f"[APIManager] ⚠️ Plus de clés valides! ({len(self.keys)} clés, toutes invalides)")
            
            # Plus de clés valides - tenter de générer une nouvelle
            if self.auto_generate:
                print("[APIManager] 🔄 Tentative de génération d'une nouvelle clé...")
                success = await self.generate_new_key()
                if success:
                    # Recharger les clés sous lock pour éviter la race condition
                    self.load_keys()
                    if self.keys:
                        self.current_index = len(self.keys) - 1
                    print(f"[APIManager] ✅ Nouvelle clé générée: {self.current_key[:8] if self.current_key else 'N/A'}...")
                    return True
                else:
                    print("[APIManager] ❌ Échec de génération de nouvelle clé")
            
            return False
    
    async def generate_new_key(self) -> bool:
        """
        Génère une nouvelle clé via odds_api_full_automation.py.
        
        Cherche le script dans plusieurs emplacements.
        
        Returns:
            True si génération réussie
        """
        # Chemins possibles pour le script
        possible_paths = [
            self.keys_file.parent / "odds_api_full_automation.py",  # Même dossier
            self.keys_file.parent.parent / "odds_api_full_automation.py",  # Dossier parent
            Path(__file__).parent.parent.parent / "odds_api_full_automation.py",  # test/
        ]
        
        script_path = None
        for path in possible_paths:
            if path.exists():
                script_path = path
                print(f"[APIManager] 📍 Script trouvé: {script_path}")
                break
        
        if not script_path:
            print(f"[APIManager] ❌ Script odds_api_full_automation.py non trouvé")
            print(f"[APIManager]    Chemins recherchés:")
            for p in possible_paths:
                print(f"[APIManager]    - {p}")
            return False
        
        try:
            # Le script sauvegarde dans son propre dossier, on doit copier après
            script_keys_file = script_path.parent / "api_keys.txt"
            
            # Lire les clés existantes dans le fichier du script (pour comparer après)
            existing_keys = set()
            if script_keys_file.exists():
                with open(script_keys_file, "r") as f:
                    existing_keys = set(f.read().strip().split("\n"))
            
            # Exécuter le script
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(script_path), "AutoBot",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(script_path.parent)  # Important: exécuter dans le bon dossier
            )
            
            print("[APIManager] ⏳ Génération en cours (max 10 min)...")
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=600  # 10 minutes max
            )
            
            if process.returncode == 0:
                print("[APIManager] ✅ Script terminé avec succès")
                
                # Copier la nouvelle clé vers notre fichier api_keys.txt
                if script_keys_file.exists():
                    with open(script_keys_file, "r") as f:
                        new_keys = set(f.read().strip().split("\n"))
                    
                    # Trouver la nouvelle clé (différence)
                    added_keys = new_keys - existing_keys
                    
                    if added_keys:
                        # Ajouter les nouvelles clés à notre fichier
                        with open(self.keys_file, "a") as f:
                            for key_line in added_keys:
                                if key_line.strip():
                                    f.write(f"{key_line}\n")
                                    print(f"[APIManager] 📝 Nouvelle clé ajoutée: {key_line[:20]}...")
                        return True
                    else:
                        print("[APIManager] ⚠️ Aucune nouvelle clé détectée dans le fichier")
                        return False
                else:
                    print(f"[APIManager] ⚠️ Fichier {script_keys_file} non trouvé après exécution")
                    return False
            else:
                print(f"[APIManager] ❌ Script échoué (code {process.returncode})")
                if stderr:
                    print(f"[APIManager]    Erreur: {stderr.decode()[:200]}")
                return False
            
        except asyncio.TimeoutError:
            print("[APIManager] ❌ Timeout: génération trop longue (>10 min)")
            return False
        except Exception as e:
            import traceback
            print(f"[APIManager] ❌ Exception: {e}\n{traceback.format_exc()}")
            return False
    
    def get_status(self) -> dict:
        """Retourne le status du gestionnaire."""
        return {
            "total_keys": len(self.keys),
            "valid_keys": self.valid_keys_count,
            "current_key": self.current_key[:8] + "..." if self.current_key else None,
            "current_email": self.current_email,
            "auto_generate": self.auto_generate,
            "failover_count": self.failover_count,
            "last_error": self.last_error,
        }

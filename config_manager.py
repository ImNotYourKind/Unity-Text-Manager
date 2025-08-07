# config_manager.py
"""
Gestionnaire de configuration pour Unity Text Manager
Gère les paramètres utilisateur, clés API et préférences de manière sécurisée
"""

import os
import json
import keyring
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import getpass


class ConfigManager:
    """Gestionnaire de configuration sécurisé"""
    
    def __init__(self, app_name: str = "UnityTextManager"):
        self.app_name = app_name
        self.config_dir = Path.home() / ".unity_text_manager"
        self.config_file = self.config_dir / "config.json"
        self.config_dir.mkdir(exist_ok=True)
        
        # Configuration par défaut
        self.default_config = {
            "version": "2.0",
            "ui_settings": {
                "window_geometry": "1100x750",
                "theme": "clam",
                "confirm_actions": True,
                "auto_save": True,
                "detailed_logs": False
            },
            "translation_settings": {
                "model": "gpt-4o-mini",
                "max_retries": 3,
                "rate_limit_delay": 0.1,
                "cache_enabled": True,
                "target_language": "fr"
            },
            "scan_settings": {
                "scan_textassets": True,
                "scan_monobehaviours": True,
                "scan_textfiles": True,
                "deep_scan": False
            },
            "injection_settings": {
                "create_backup": True,
                "verify_integrity": True,
                "dry_run": False
            },
            "recent_projects": [],
            "last_update_check": None
        }
        
        self.config = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """Charge la configuration depuis le fichier"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # Fusionner avec la configuration par défaut pour les nouvelles clés
                merged_config = self.default_config.copy()
                self._deep_update(merged_config, config)
                return merged_config
            
        except Exception as e:
            print(f"⚠️ Erreur lors du chargement de la config: {e}")
        
        return self.default_config.copy()

    def save_config(self) -> bool:
        """Sauvegarde la configuration dans le fichier"""
        try:
            # Créer une sauvegarde horodatée
            if self.config_file.exists():
                backup_file = self.config_dir / f"config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                self.config_file.rename(backup_file)
                
                # Garder seulement les 5 dernières sauvegardes
                backups = sorted(self.config_dir.glob("config_backup_*.json"))
                for backup in backups[:-5]:
                    backup.unlink()
            
            # Sauvegarder la configuration actuelle
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Configuration sauvegardée: {self.config_file}")
            return True
            
        except Exception as e:
            print(f"❌ Erreur lors de la sauvegarde de la config: {e}")
            return False

    def get(self, key_path: str, default=None) -> Any:
        """Récupère une valeur de configuration via un chemin (ex: 'ui_settings.theme')"""
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value

    def set(self, key_path: str, value: Any) -> None:
        """Définit une valeur de configuration via un chemin"""
        keys = key_path.split('.')
        config = self.config
        
        # Naviguer jusqu'à l'avant-dernier niveau
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # Définir la valeur finale
        config[keys[-1]] = value

    def get_openai_api_key(self) -> Optional[str]:
        """Récupère la clé API OpenAI de manière sécurisée"""
        # 1. Essayer les variables d'environnement
        api_key = os.environ.get('OPENAI_API_KEY')
        if api_key:
            return api_key
        
        # 2. Essayer le trousseau système (keyring)
        try:
            api_key = keyring.get_password(self.app_name, "openai_api_key")
            if api_key:
                return api_key
        except Exception as e:
            print(f"⚠️ Erreur keyring: {e}")
        
        # 3. Demander à l'utilisateur (mode console seulement)
        return None

    def set_openai_api_key(self, api_key: str) -> bool:
        """Stocke la clé API OpenAI de manière sécurisée"""
        try:
            # Essayer de stocker dans le trousseau système
            keyring.set_password(self.app_name, "openai_api_key", api_key)
            print("✅ Clé API stockée dans le trousseau système")
            return True
            
        except Exception as e:
            print(f"⚠️ Impossible de stocker dans le trousseau: {e}")
            
            # Fallback: suggérer l'utilisation des variables d'environnement
            print("💡 Utilisez une variable d'environnement à la place:")
            print(f"   export OPENAI_API_KEY='{api_key}'")
            return False

    def remove_openai_api_key(self) -> bool:
        """Supprime la clé API OpenAI du stockage sécurisé"""
        try:
            keyring.delete_password(self.app_name, "openai_api_key")
            print("✅ Clé API supprimée du trousseau système")
            return True
        except Exception as e:
            print(f"⚠️ Erreur lors de la suppression: {e}")
            return False

    def add_recent_project(self, project_path: str) -> None:
        """Ajoute un projet à la liste des projets récents"""
        recent_projects = self.get("recent_projects", [])
        
        # Supprimer si déjà présent
        recent_projects = [p for p in recent_projects if p != project_path]
        
        # Ajouter en tête
        recent_projects.insert(0, project_path)
        
        # Garder seulement les 10 plus récents
        recent_projects = recent_projects[:10]
        
        self.set("recent_projects", recent_projects)

    def get_recent_projects(self) -> list:
        """Récupère la liste des projets récents (existants seulement)"""
        recent_projects = self.get("recent_projects", [])
        return [p for p in recent_projects if os.path.exists(p)]

    def update_window_geometry(self, geometry: str) -> None:
        """Met à jour la géométrie de fenêtre"""
        self.set("ui_settings.window_geometry", geometry)

    def get_window_geometry(self) -> str:
        """Récupère la géométrie de fenêtre"""
        return self.get("ui_settings.window_geometry", "1100x750")

    def export_config(self, file_path: str) -> bool:
        """Exporte la configuration (sans les données sensibles)"""
        try:
            export_config = self.config.copy()
            
            # Supprimer les données sensibles
            sensitive_keys = ["recent_projects"]
            for key in sensitive_keys:
                if key in export_config:
                    del export_config[key]
            
            # Ajouter des métadonnées d'export
            export_config["export_info"] = {
                "exported_at": datetime.now().isoformat(),
                "exported_by": getpass.getuser(),
                "version": self.get("version")
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_config, f, indent=2, ensure_ascii=False)
            
            print(f"📤 Configuration exportée: {file_path}")
            return True
            
        except Exception as e:
            print(f"❌ Erreur lors de l'export: {e}")
            return False

    def import_config(self, file_path: str) -> bool:
        """Importe une configuration depuis un fichier"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported_config = json.load(f)
            
            # Supprimer les métadonnées d'export
            if "export_info" in imported_config:
                del imported_config["export_info"]
            
            # Fusionner avec la configuration actuelle
            self._deep_update(self.config, imported_config)
            
            print(f"📥 Configuration importée: {file_path}")
            return True
            
        except Exception as e:
            print(f"❌ Erreur lors de l'import: {e}")
            return False

    def reset_to_defaults(self) -> None:
        """Remet la configuration aux valeurs par défaut"""
        self.config = self.default_config.copy()
        print("🔄 Configuration remise aux valeurs par défaut")

    def validate_config(self) -> bool:
        """Valide la configuration actuelle"""
        try:
            # Vérifier la structure de base
            required_sections = ["ui_settings", "translation_settings", "scan_settings", "injection_settings"]
            
            for section in required_sections:
                if section not in self.config:
                    print(f"⚠️ Section manquante: {section}")
                    self.config[section] = self.default_config[section].copy()
            
            # Vérifier les types de données
            validations = {
                "ui_settings.confirm_actions": bool,
                "ui_settings.auto_save": bool,
                "translation_settings.max_retries": int,
                "translation_settings.rate_limit_delay": (int, float),
                "scan_settings.scan_textassets": bool
            }
            
            for key_path, expected_type in validations.items():
                value = self.get(key_path)
                if value is not None and not isinstance(value, expected_type):
                    print(f"⚠️ Type invalide pour {key_path}: {type(value)}, attendu: {expected_type}")
                    # Restaurer la valeur par défaut
                    default_value = self._get_default_value(key_path)
                    if default_value is not None:
                        self.set(key_path, default_value)
            
            return True
            
        except Exception as e:
            print(f"❌ Erreur lors de la validation: {e}")
            return False

    def get_debug_info(self) -> Dict[str, Any]:
        """Récupère les informations de debug pour le support"""
        return {
            "config_file": str(self.config_file),
            "config_dir": str(self.config_dir),
            "config_exists": self.config_file.exists(),
            "config_size": self.config_file.stat().st_size if self.config_file.exists() else 0,
            "keyring_available": self._is_keyring_available(),
            "recent_projects_count": len(self.get("recent_projects", [])),
            "version": self.get("version"),
            "last_modified": datetime.fromtimestamp(
                self.config_file.stat().st_mtime
            ).isoformat() if self.config_file.exists() else None
        }

    def _deep_update(self, base_dict: Dict, update_dict: Dict) -> None:
        """Met à jour un dictionnaire de manière récursive"""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value

    def _get_default_value(self, key_path: str) -> Any:
        """Récupère la valeur par défaut pour un chemin donné"""
        keys = key_path.split('.')
        value = self.default_config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        
        return value

    def _is_keyring_available(self) -> bool:
        """Vérifie si keyring est disponible et fonctionnel"""
        try:
            # Test simple
            keyring.set_password("test", "test", "test")
            keyring.delete_password("test", "test")
            return True
        except Exception:
            return False


# Instance globale pour l'application
config = ConfigManager()


def setup_api_key_interactive() -> Optional[str]:
    """Configuration interactive de la clé API (mode console)"""
    print("\n🔧 Configuration de la clé API OpenAI")
    print("=" * 40)
    
    current_key = config.get_openai_api_key()
    if current_key:
        print("✅ Une clé API est déjà configurée")
        choice = input("Voulez-vous la remplacer ? (o/N): ").lower().strip()
        if choice not in ['o', 'oui', 'y', 'yes']:
            return current_key
    
    print("\n📝 Entrez votre clé API OpenAI:")
    print("💡 Vous pouvez la trouver sur: https://platform.openai.com/api-keys")
    
    api_key = getpass.getpass("Clé API: ").strip()
    
    if not api_key:
        print("❌ Clé API vide, annulation")
        return None
    
    # Validation basique
    if not api_key.startswith("sk-"):
        print("⚠️ La clé API devrait commencer par 'sk-'")
        choice = input("Continuer quand même ? (o/N): ").lower().strip()
        if choice not in ['o', 'oui', 'y', 'yes']:
            return None
    
    # Sauvegarder
    if config.set_openai_api_key(api_key):
        print("✅ Clé API configurée avec succès!")
        return api_key
    else:
        print("⚠️ Impossible de sauvegarder de manière sécurisée")
        print("💡 Définissez la variable d'environnement OPENAI_API_KEY")
        return api_key


if __name__ == "__main__":
    # Test des fonctionnalités
    print("🧪 Test du gestionnaire de configuration")
    
    # Tester la configuration de base
    config.set("test.value", "hello")
    assert config.get("test.value") == "hello"
    
    # Tester la validation
    config.validate_config()
    
    # Afficher les infos de debug
    debug_info = config.get_debug_info()
    print("🐛 Informations de debug:")
    for key, value in debug_info.items():
        print(f"   {key}: {value}")
    
    print("✅ Tests terminés")
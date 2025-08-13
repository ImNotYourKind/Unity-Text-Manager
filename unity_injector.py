# unity_injector.py
"""
Module pour l'injection des textes traduits dans les fichiers Unity.
Version corrigée avec gestion d'erreurs robuste et vérifications d'intégrité.
"""

import os
import shutil
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Callable
import UnityPy
from datetime import datetime


class UnityTextInjector:
    """Injecteur de textes traduits avec sauvegarde et vérification d'intégrité"""
    
    def __init__(self, game_path: str):
        self.game_path = Path(game_path)
        self.backup_dir = Path("backups") / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.success_count = 0
        self.error_count = 0
        self.processed_files = set()

    def create_backup(self, file_path: Path) -> bool:
        """Crée une sauvegarde du fichier avec vérification d'intégrité"""
        try:
            if not file_path.exists():
                print(f"❌ Fichier source inexistant: {file_path}")
                return False
                
            relative_path = file_path.relative_to(self.game_path)
            backup_path = self.backup_dir / relative_path
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copier avec préservation des métadonnées
            shutil.copy2(file_path, backup_path)
            
            # Vérification d'intégrité par taille et hash
            if not self._verify_backup_integrity(file_path, backup_path):
                print(f"❌ Échec de la vérification de sauvegarde: {file_path}")
                return False
                
            print(f"✅ Sauvegarde créée: {relative_path}")
            return True
            
        except PermissionError:
            print(f"❌ Permission refusée pour sauvegarder: {file_path}")
            return False
        except Exception as e:
            print(f"❌ Erreur lors de la sauvegarde de {file_path}: {e}")
            return False

    def _verify_backup_integrity(self, original: Path, backup: Path) -> bool:
        """Vérifie l'intégrité de la sauvegarde"""
        try:
            # Vérification de la taille
            if original.stat().st_size != backup.stat().st_size:
                return False
                
            # Vérification par hash MD5 pour les petits fichiers (< 50 MB)
            if original.stat().st_size < 50 * 1024 * 1024:
                return self._calculate_hash(original) == self._calculate_hash(backup)
            
            # Pour les gros fichiers, on se contente de la taille
            return True
            
        except Exception:
            return False

    def _calculate_hash(self, file_path: Path) -> str:
        """Calcule le hash MD5 d'un fichier"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except:
            return ""

    def inject_translations(
        self, 
        translation_data: Dict, 
        progress_callback: Optional[Callable] = None
    ) -> int:
        """Injecte les traductions dans les fichiers Unity"""
        self.success_count = 0
        self.error_count = 0
        self.processed_files.clear()
        
        # Filtrer uniquement les traductions valides
        translated_entries = self._filter_valid_translations(translation_data['texts'])
        total_translations = len(translated_entries)
        
        if total_translations == 0:
            print("❌ Aucune traduction valide à injecter")
            return 0
            
        print(f"\n🚀 Début de l'injection de {total_translations} traductions")
        print(f"📂 Sauvegardes dans: {self.backup_dir}")
        
        # Grouper par fichier source pour optimiser
        files_to_process = self._group_by_source_file(translated_entries)
        
        for i, (source_file, text_entries) in enumerate(files_to_process.items()):
            if progress_callback:
                progress = (i / len(files_to_process)) * 100
                progress_callback(
                    progress, 
                    f"Injection dans: {Path(source_file).name} ({len(text_entries)} textes)"
                )
            
            print(f"\n📁 Fichier {i + 1}/{len(files_to_process)}: {Path(source_file).name}")
            
            if self._inject_file_translations(source_file, text_entries):
                self.success_count += len(text_entries)
                print(f"   ✅ {len(text_entries)} traduction(s) injectée(s)")
            else:
                self.error_count += len(text_entries)
                print(f"   ❌ Échec de l'injection")
        
        self._print_summary()
        
        if progress_callback:
            progress_callback(
                100, 
                f"Injection terminée: {self.success_count} réussies, {self.error_count} échecs"
            )
        
        return self.success_count

    def _filter_valid_translations(self, texts: List[Dict]) -> List[Dict]:
        """Filtre les traductions valides"""
        valid_translations = []
        
        for text_entry in texts:
            # Vérifications de validité
            if not text_entry.get('is_translated', False):
                continue
                
            translated_text = text_entry.get('translated_text', '').strip()
            original_text = text_entry.get('original_text', '').strip()
            
            if not translated_text or translated_text == original_text:
                continue
                
            # Vérifier que le fichier source existe
            source_file = text_entry.get('source_file', '')
            if not source_file or not Path(source_file).exists():
                print(f"⚠️ Fichier source manquant pour: {text_entry.get('asset_name', 'inconnu')}")
                continue
                
            valid_translations.append(text_entry)
            
        return valid_translations

    def _group_by_source_file(self, text_entries: List[Dict]) -> Dict[str, List[Dict]]:
        """Groupe les entrées par fichier source"""
        files_to_process = {}
        for text_entry in text_entries:
            source_file = text_entry['source_file']
            files_to_process.setdefault(source_file, []).append(text_entry)
        return files_to_process

    def _inject_file_translations(self, source_file: str, text_entries: List[Dict]) -> bool:
        """Injecte les traductions dans un fichier spécifique"""
        try:
            file_path = Path(source_file)
            
            # Éviter de traiter le même fichier plusieurs fois
            if str(file_path) in self.processed_files:
                print(f"   ⚠️ Fichier déjà traité: {file_path.name}")
                return True
                
            # Vérifier les permissions avant de continuer
            if not os.access(file_path, os.R_OK | os.W_OK):
                print(f"   ❌ Permissions insuffisantes: {file_path}")
                return False
            
            # Créer une sauvegarde
            if not self.create_backup(file_path):
                print(f"   ❌ Impossible de créer une sauvegarde, abandon")
                return False
            
            # Traiter selon le type de fichier
            success = False
            if file_path.suffix.lower() in ['.assets', '.bundle', '.resource', '.resS', '.dat']:
                success = self._inject_unity_file(file_path, text_entries)
            else:
                success = self._inject_text_file(file_path, text_entries)
            
            if success:
                self.processed_files.add(str(file_path))
                
            return success
            
        except Exception as e:
            print(f"   ❌ Erreur lors de l'injection dans {source_file}: {e}")
            return False

    def _inject_unity_file(self, file_path: Path, text_entries: List[Dict]) -> bool:
        """Injecte les traductions dans un fichier Unity avec gestion d'erreurs robuste"""
        temp_file = None
        try:
            # Chargement du fichier Unity
            try:
                env = UnityPy.load(str(file_path))
            except Exception as e:
                print(f"   ❌ Impossible de charger le fichier Unity: {e}")
                return False
            
            modified = False
            modifications_count = 0
            
            # Indexer les entrées par path_id pour accélérer
            entries_by_path_id = {
                e['path_id']: e for e in text_entries 
                if e.get('path_id') is not None
            }
            
            # Parcourir les objets Unity
            for obj in env.objects:
                if obj.path_id in entries_by_path_id:
                    text_entry = entries_by_path_id[obj.path_id]
                    
                    try:
                        if obj.type.name == "TextAsset":
                            if self._modify_text_asset(obj, text_entry):
                                modified = True
                                modifications_count += 1
                        elif obj.type.name == "MonoBehaviour":
                            if self._modify_monobehaviour(obj, text_entry):
                                modified = True
                                modifications_count += 1
                    except Exception as obj_error:
                        print(f"   ⚠️ Erreur objet {obj.path_id}: {obj_error}")
                        continue
            
            # Sauvegarder si des modifications ont été apportées
            if modified and modifications_count > 0:
                try:
                    temp_file = file_path.with_suffix('.tmp')
                    
                    # Sauvegarder dans un fichier temporaire
                    with open(temp_file, "wb") as f:
                        f.write(env.file.save())
                    
                    # Vérifier l'intégrité du fichier temporaire
                    if not self._verify_unity_file_integrity(temp_file):
                        print(f"   ❌ Fichier temporaire corrompu")
                        return False
                    
                    # Remplacer l'original par le fichier temporaire
                    shutil.move(str(temp_file), str(file_path))
                    print(f"   ✅ Fichier modifié avec succès ({modifications_count} modifications)")
                    return True
                    
                except Exception as save_error:
                    print(f"   ❌ Erreur lors de la sauvegarde: {save_error}")
                    return False
            else:
                print(f"   ℹ️ Aucune modification appliquée")
                return True
                
        except Exception as e:
            print(f"   ❌ Erreur générale lors de l'injection: {e}")
            return False
            
        finally:
            # Nettoyer le fichier temporaire en cas d'erreur
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass

    def _verify_unity_file_integrity(self, file_path: Path) -> bool:
        """Vérifie que le fichier Unity peut être chargé sans erreur"""
        try:
            with open(file_path, "rb") as f:
                env = UnityPy.load(f)
                readable_objects = 0
                
                for obj in env.objects:
                    try:
                        _ = obj.read()
                        readable_objects += 1
                    except:
                        continue
            
            print(f"   🔍 Vérification intégrité: {readable_objects} objets lisibles")
            return readable_objects > 0
            
        except Exception as e:
            print(f"   ⚠️ Problème d'intégrité détecté: {e}")
            return False

    def _modify_text_asset(self, obj, text_entry: Dict) -> bool:
        """Modifie un TextAsset de manière sécurisée"""
        try:
            data = obj.read()
            
            # Vérifier que c'est le bon asset
            asset_name = self._get_asset_name(data, obj)
            if asset_name != text_entry['asset_name']:
                return False
            
            # Obtenir le contenu actuel
            old_content = self._get_asset_content(data)
            new_content = text_entry['translated_text']
            
            print(f"    📝 Modification TextAsset: {asset_name}")
            print(f"      Ancien: {old_content[:50]}{'...' if len(old_content) > 50 else ''}")
            print(f"      Nouveau: {new_content[:50]}{'...' if len(new_content) > 50 else ''}")
            
            # Modifier le contenu selon le type de données
            success = False
            
            if hasattr(data, 'text'):
                data.text = new_content
                success = True
            elif hasattr(data, 'm_Script'):
                # Respecter le type original (bytes ou str)
                if isinstance(data.m_Script, (bytes, bytearray)):
                    data.m_Script = new_content.encode('utf-8') if isinstance(new_content, str) else new_content
                else:
                    data.m_Script = new_content if isinstance(new_content, str) else new_content.decode('utf-8', errors='ignore')
                success = True
            elif hasattr(data, 'bytes'):
                # Respecter le type original (bytes ou str)
                if isinstance(data.bytes, (bytes, bytearray)):
                    data.bytes = new_content.encode('utf-8') if isinstance(new_content, str) else new_content
                else:
                    data.bytes = new_content if isinstance(new_content, str) else new_content.decode('utf-8', errors='ignore')
                success = True
            else:
                print(f"      ⚠️ Type de données non supporté pour {asset_name}")
                return False
            
            if success:
                try:
                    data.save()
                    print("      ✓ TextAsset modifié avec succès")
                    return True
                except Exception as save_error:
                    print(f"      ✗ Erreur lors de la sauvegarde: {save_error}")
                    return False
                    
        except Exception as e:
            print(f"    ❌ Erreur lors de la modification du TextAsset: {e}")
            return False

    def _modify_monobehaviour(self, obj, text_entry: Dict) -> bool:
        """Modifie un MonoBehaviour de manière sécurisée"""
        try:
            data = obj.read()
            field_path = text_entry.get('field_path', '')
            
            if not field_path:
                print("      ⚠️ Chemin de champ manquant pour MonoBehaviour")
                return False
            
            # Lire les données
            mono_data = self._read_mono_data(data)
            if not mono_data:
                print("      ⚠️ Impossible de lire les données MonoBehaviour")
                return False
            
            # Modifier la valeur dans le chemin spécifié
            if self._set_nested_value(mono_data, field_path, text_entry['translated_text']):
                # Sauvegarder les modifications
                try:
                    if hasattr(data, 'save'):
                        data.save()
                        print(f"      ✓ MonoBehaviour modifié: {field_path}")
                        return True
                    else:
                        print("      ⚠️ Impossible de sauvegarder MonoBehaviour")
                        return False
                except Exception as save_error:
                    print(f"      ✗ Erreur sauvegarde MonoBehaviour: {save_error}")
                    return False
            else:
                print(f"      ⚠️ Impossible de modifier le champ: {field_path}")
                return False
                
        except Exception as e:
            print(f"    ❌ Erreur lors de la modification du MonoBehaviour: {e}")
            return False

    def _inject_text_file(self, file_path: Path, text_entries: List[Dict]) -> bool:
        """Injecte les traductions dans un fichier texte"""
        try:
            # Pour les fichiers texte, on remplace tout le contenu
            if len(text_entries) == 1:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(text_entries[0]['translated_text'])
                print(f"    ✓ Fichier texte modifié: {file_path.name}")
                return True
            else:
                print(f"    ⚠️ Plusieurs entrées pour un fichier texte: {file_path.name}")
                return False
                
        except Exception as e:
            print(f"    ❌ Erreur lors de la modification du fichier texte {file_path}: {e}")
            return False

    def _read_mono_data(self, data) -> Optional[Dict]:
        """Lit les données MonoBehaviour de manière robuste"""
        try:
            if hasattr(data, 'read_typetree'):
                return data.read_typetree()
        except Exception as e:
            print(f"      ⚠️ Erreur read_typetree: {e}")
        
        # Fallback: essayer de lire les attributs directs
        try:
            mono_data = {}
            for attr in dir(data):
                if not attr.startswith('_') and attr not in ['read', 'read_typetree']:
                    try:
                        value = getattr(data, attr)
                        if isinstance(value, (str, int, float, bool, list, dict)):
                            mono_data[attr] = value
                    except:
                        continue
            return mono_data if mono_data else None
        except:
            return None

    def _get_asset_name(self, data, obj) -> str:
        """Obtient le nom d'un asset de manière robuste"""
        if hasattr(data, 'name') and data.name:
            return data.name
        elif hasattr(data, 'm_Name') and data.m_Name:
            return data.m_Name
        elif hasattr(obj, 'name') and obj.name:
            return obj.name
        else:
            return f"Asset_{obj.path_id}"

    def _get_asset_content(self, data) -> str:
        """Obtient le contenu d'un asset de manière robuste"""
        if hasattr(data, 'text') and data.text:
            return data.text
        elif hasattr(data, 'm_Script') and data.m_Script:
            # Gérer le cas où m_Script est en bytes
            if isinstance(data.m_Script, (bytes, bytearray)):
                try:
                    return data.m_Script.decode('utf-8', errors='ignore')
                except:
                    return str(data.m_Script)
            else:
                return str(data.m_Script)
        elif hasattr(data, 'bytes') and data.bytes:
            try:
                return data.bytes.decode('utf-8', errors='ignore')
            except:
                return str(data.bytes)
        return ""

    def _set_nested_value(self, data: Dict, path: str, value: str) -> bool:
        """Définit une valeur dans un objet imbriqué de manière sécurisée"""
        try:
            keys = path.split('.')
            current = data
            
            # Naviguer jusqu'au dernier niveau
            for key in keys[:-1]:
                if '[' in key and ']' in key:
                    # Gérer les indices de tableau
                    field_name = key.split('[')[0]
                    index = int(key.split('[')[1].split(']')[0])
                    
                    if field_name not in current:
                        print(f"      ⚠️ Champ manquant: {field_name}")
                        return False
                        
                    if not isinstance(current[field_name], list):
                        print(f"      ⚠️ {field_name} n'est pas une liste")
                        return False
                        
                    if index >= len(current[field_name]):
                        print(f"      ⚠️ Index {index} hors limites pour {field_name}")
                        return False
                        
                    current = current[field_name][index]
                else:
                    if key not in current:
                        print(f"      ⚠️ Clé manquante: {key}")
                        return False
                    current = current[key]
            
            # Définir la valeur finale
            final_key = keys[-1]
            if '[' in final_key and ']' in final_key:
                field_name = final_key.split('[')[0]
                index = int(final_key.split('[')[1].split(']')[0])
                
                if field_name not in current or not isinstance(current[field_name], list):
                    print(f"      ⚠️ Problème avec le champ final: {field_name}")
                    return False
                    
                if index >= len(current[field_name]):
                    print(f"      ⚠️ Index final {index} hors limites")
                    return False
                    
                current[field_name][index] = value
            else:
                if final_key not in current:
                    print(f"      ⚠️ Clé finale manquante: {final_key}")
                    return False
                current[final_key] = value
            
            return True
            
        except Exception as e:
            print(f"      ❌ Erreur lors de la définition de la valeur {path}: {e}")
            return False

    def _print_summary(self) -> None:
        """Affiche un résumé de l'injection"""
        print(f"\n🏁 Résumé de l'injection:")
        print(f"   ✅ Réussies: {self.success_count}")
        print(f"   ❌ Échecs: {self.error_count}")
        print(f"   📁 Fichiers traités: {len(self.processed_files)}")
        print(f"   📂 Sauvegardes dans: {self.backup_dir}")
        
        if self.error_count > 0:
            print(f"   ⚠️ Vérifiez les logs pour les détails des erreurs")

    def restore_backup(self, backup_timestamp: Optional[str] = None) -> bool:
        """Restaure les fichiers depuis une sauvegarde"""
        try:
            if backup_timestamp:
                backup_path = Path("backups") / backup_timestamp
            else:
                backup_path = self.backup_dir
                
            if not backup_path.exists():
                print(f"❌ Dossier de sauvegarde introuvable: {backup_path}")
                return False
                
            restored_count = 0
            for backup_file in backup_path.rglob('*'):
                if backup_file.is_file():
                    try:
                        relative_path = backup_file.relative_to(backup_path)
                        target_file = self.game_path / relative_path
                        
                        # Créer les dossiers parents si nécessaire
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        
                        shutil.copy2(backup_file, target_file)
                        restored_count += 1
                        
                    except Exception as e:
                        print(f"⚠️ Erreur restauration {backup_file}: {e}")
                        continue
            
            print(f"✅ Restauration terminée: {restored_count} fichiers restaurés")
            return True
            
        except Exception as e:
            print(f"❌ Erreur lors de la restauration: {e}")
            return False
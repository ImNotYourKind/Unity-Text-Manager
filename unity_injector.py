# unity_injector_fixed.py
"""
Module pour l'injection des textes traduits dans les fichiers Unity.
Version corrigée pour éviter l'écran noir après injection.
"""

import os
import shutil
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Callable
import UnityPy
from datetime import datetime
import gc
import time
import tempfile


class UnityTextInjector:
    """Injecteur de textes traduits avec sauvegarde et vérification d'intégrité renforcée"""
    
    def __init__(self, game_path: str):
        self.game_path = Path(game_path)
        self.backup_dir = Path("backups") / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.success_count = 0
        self.error_count = 0
        self.processed_files = set()
        # Cache pour les données originales afin de préserver les types
        self.original_data_cache = {}

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
            
            # Vérification d'intégrité stricte
            if not self._verify_backup_integrity(file_path, backup_path):
                print(f"❌ Échec de la vérification de sauvegarde: {file_path}")
                return False
            
            # Test de chargement Unity pour s'assurer que le fichier est valide
            if not self._verify_unity_file_loadable(file_path):
                print(f"❌ Fichier Unity non chargeable: {file_path}")
                return False
                
            print(f"✅ Sauvegarde créée: {relative_path}")
            return True
            
        except PermissionError:
            print(f"❌ Permission refusée pour sauvegarder: {file_path}")
            return False
        except Exception as e:
            print(f"❌ Erreur lors de la sauvegarde de {file_path}: {e}")
            return False

    def _verify_unity_file_loadable(self, file_path: Path) -> bool:
        """Vérifie qu'un fichier Unity peut être chargé correctement"""
        try:
            env = UnityPy.load(str(file_path))
            test_objects = 0
            
            # Tester quelques objets pour s'assurer qu'ils sont lisibles
            for i, obj in enumerate(env.objects):
                if i > 10:  # Limiter le test à 10 objets pour la performance
                    break
                try:
                    _ = obj.read()
                    test_objects += 1
                except:
                    continue
            
            del env
            gc.collect()
            
            return test_objects > 0
            
        except Exception as e:
            print(f"   ⚠️ Fichier Unity non chargeable: {e}")
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
        """Injecte les traductions dans les fichiers Unity avec protection contre la corruption"""
        self.success_count = 0
        self.error_count = 0
        self.processed_files.clear()
        self.original_data_cache.clear()
        
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
            
            if self._inject_file_translations_safe(source_file, text_entries):
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

    def _clean_text_data(self, text: str) -> str:
        """Nettoie les données texte des caractères problématiques"""
        if not text:
            return text
            
        # Supprimer les caractères null et autres caractères de contrôle problématiques
        cleaned = text.replace('\x00', '')  # Supprimer les caractères null
        
        # Supprimer d'autres caractères de contrôle potentiellement problématiques
        # mais garder les retours à la ligne normaux (\n, \r)
        control_chars = ['\x01', '\x02', '\x03', '\x04', '\x05', '\x06', '\x07', '\x08', 
                        '\x0b', '\x0c', '\x0e', '\x0f', '\x10', '\x11', '\x12', '\x13', 
                        '\x14', '\x15', '\x16', '\x17', '\x18', '\x19', '\x1a', '\x1b', 
                        '\x1c', '\x1d', '\x1e', '\x1f']
        
        for char in control_chars:
            cleaned = cleaned.replace(char, '')
        
        return cleaned

    def _filter_valid_translations(self, texts: List[Dict]) -> List[Dict]:
        """Filtre les traductions valides avec nettoyage automatique"""
        valid_translations = []
        
        print(f"🔍 Analyse de {len(texts)} entrées de traduction...")
        
        for i, text_entry in enumerate(texts):
            # Debug: afficher quelques infos sur l'entrée
            asset_name = text_entry.get('asset_name', f'Entrée_{i}')
            is_translated = text_entry.get('is_translated', False)
            
            # Nettoyer les textes AVANT de les analyser
            original_text = self._clean_text_data(text_entry.get('original_text', '')).strip()
            translated_text = self._clean_text_data(text_entry.get('translated_text', '')).strip()
            
            # Mettre à jour les textes nettoyés dans l'entrée
            text_entry['original_text'] = original_text
            text_entry['translated_text'] = translated_text
            
            print(f"   📝 {asset_name}: traduit={is_translated}")
            print(f"      Original: '{original_text[:100]}{'...' if len(original_text) > 100 else ''}' (longueur: {len(original_text)})")
            print(f"      Traduit:  '{translated_text[:100]}{'...' if len(translated_text) > 100 else ''}' (longueur: {len(translated_text)})")
            
            # Vérifications de validité
            if not is_translated:
                print(f"      ⏭️ Ignoré: non marqué comme traduit")
                continue
                
            if not translated_text:
                print(f"      ⏭️ Ignoré: texte traduit vide après nettoyage")
                continue
                
            if translated_text == original_text:
                print(f"      ⏭️ Ignoré: traduction identique à l'original")
                continue
            
            # Après nettoyage, vérifier à nouveau les caractères dangereux
            if self._contains_dangerous_chars(translated_text):
                print(f"      ⚠️ Ignoré: caractères dangereux persistants dans '{asset_name}'")
                continue
                
            # Vérifier que le fichier source existe
            source_file = text_entry.get('source_file', '')
            if not source_file or not Path(source_file).exists():
                print(f"      ⚠️ Ignoré: fichier source manquant pour '{asset_name}' ({source_file})")
                continue
            
            # Vérifier que path_id est présent
            path_id = text_entry.get('path_id')
            if not path_id:
                print(f"      ⚠️ Ignoré: path_id manquant pour '{asset_name}'")
                continue
                
            print(f"      ✅ Valide: '{asset_name}' (path_id: {path_id})")
            valid_translations.append(text_entry)
            
        print(f"📊 Résultat: {len(valid_translations)} traductions valides sur {len(texts)} analysées")
        
        if len(valid_translations) == 0 and len(texts) > 0:
            print("\n🚨 AUCUNE TRADUCTION VALIDE TROUVÉE !")
            print("Causes possibles:")
            print("- Vos traductions ne sont pas marquées comme 'traduit=True'")
            print("- Les textes contiennent des caractères de contrôle")
            print("- Les chemins de fichiers source sont incorrects")
            print("- Les path_id sont manquants")
            print("\nVérifiez vos données de traduction dans l'onglet 'Scanner' ou 'Éditeur'")
        
        return valid_translations

    def _contains_dangerous_chars(self, text: str) -> bool:
        """Vérifie si le texte contient des caractères pouvant corrompre Unity"""
        # Seulement les caractères de contrôle vraiment dangereux
        dangerous_chars = ['\x00']  # Caractère null uniquement
        has_dangerous = any(char in text for char in dangerous_chars)
        
        if has_dangerous:
            dangerous_found = [repr(char) for char in dangerous_chars if char in text]
            print(f"      🚨 Caractères dangereux détectés: {dangerous_found}")
            
        return has_dangerous

    def _group_by_source_file(self, text_entries: List[Dict]) -> Dict[str, List[Dict]]:
        """Groupe les entrées par fichier source"""
        files_to_process = {}
        for text_entry in text_entries:
            source_file = text_entry['source_file']
            files_to_process.setdefault(source_file, []).append(text_entry)
        return files_to_process

    def _inject_file_translations_safe(self, source_file: str, text_entries: List[Dict]) -> bool:
        """Version sécurisée de l'injection de fichier avec rollback automatique"""
        file_path = Path(source_file)
        
        try:
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
            
            # Traiter selon le type de fichier avec rollback automatique
            success = False
            if file_path.suffix.lower() in ['.assets', '.bundle', '.resource', '.resS', '.dat']:
                success = self._inject_unity_file_with_rollback(file_path, text_entries)
            else:
                success = self._inject_text_file(file_path, text_entries)
            
            if success:
                self.processed_files.add(str(file_path))
                
            return success
            
        except Exception as e:
            print(f"   ❌ Erreur lors de l'injection dans {source_file}: {e}")
            return False

    def _inject_unity_file_with_rollback(self, file_path: Path, text_entries: List[Dict]) -> bool:
        """Injecte avec rollback automatique en cas de problème"""
        temp_file = None
        backup_file = None
        
        try:
            # Créer une copie de travail temporaire
            with tempfile.NamedTemporaryFile(delete=False, suffix='.unity_temp') as tf:
                temp_file = Path(tf.name)
                
            # Copier le fichier original vers le temporaire
            shutil.copy2(file_path, temp_file)
            
            # Charger depuis le fichier temporaire
            try:
                env = UnityPy.load(str(temp_file))
            except Exception as e:
                print(f"   ❌ Impossible de charger le fichier Unity: {e}")
                return False
            
            modified = False
            modifications_count = 0
            
            # Sauvegarder les données originales pour préserver les types
            self._cache_original_data(env, text_entries)
            
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
                            if self._modify_text_asset_safe(obj, text_entry):
                                modified = True
                                modifications_count += 1
                        elif obj.type.name == "MonoBehaviour":
                            if self._modify_monobehaviour_safe(obj, text_entry):
                                modified = True
                                modifications_count += 1
                    except Exception as obj_error:
                        print(f"   ⚠️ Erreur objet {obj.path_id}: {obj_error}")
                        continue
            
            # Sauvegarder si des modifications ont été apportées
            if modified and modifications_count > 0:
                try:
                    # Sauvegarder dans le fichier temporaire
                    with open(temp_file, "wb") as f:
                        f.write(env.file.save())
                    
                    # Libérer l'environnement UnityPy
                    del env
                    gc.collect()
                    
                    # Vérifier l'intégrité du fichier temporaire modifié
                    if not self._verify_unity_file_complete_integrity(temp_file, text_entries):
                        print(f"   ❌ Fichier temporaire corrompu après modification")
                        return False
                    
                    # Créer une sauvegarde du fichier original avant remplacement
                    backup_file = file_path.with_suffix('.backup_temp')
                    shutil.copy2(file_path, backup_file)
                    
                    # Remplacer le fichier original
                    success = self._replace_file_safely(temp_file, file_path)
                    
                    if success:
                        # Vérifier que le fichier final est correct
                        if self._verify_unity_file_complete_integrity(file_path, text_entries):
                            print(f"   ✅ Fichier modifié avec succès ({modifications_count} modifications)")
                            # Supprimer la sauvegarde temporaire
                            if backup_file and backup_file.exists():
                                backup_file.unlink()
                            return True
                        else:
                            print(f"   ❌ Fichier final corrompu, restauration...")
                            # Restaurer depuis la sauvegarde
                            if backup_file and backup_file.exists():
                                shutil.copy2(backup_file, file_path)
                                backup_file.unlink()
                            return False
                    else:
                        print(f"   ❌ Impossible de remplacer le fichier")
                        # Restaurer depuis la sauvegarde
                        if backup_file and backup_file.exists():
                            shutil.copy2(backup_file, file_path)
                            backup_file.unlink()
                        return False
                    
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
            # Nettoyer les fichiers temporaires
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
            if backup_file and backup_file.exists():
                try:
                    backup_file.unlink()
                except:
                    pass

    def _cache_original_data(self, env, text_entries: List[Dict]):
        """Cache les données originales pour préserver les types"""
        try:
            entries_by_path_id = {e['path_id']: e for e in text_entries if e.get('path_id')}
            
            for obj in env.objects:
                if obj.path_id in entries_by_path_id:
                    try:
                        data = obj.read()
                        self.original_data_cache[obj.path_id] = {
                            'type': type(data),
                            'attributes': {}
                        }
                        
                        # Cacher les types d'attributs importants
                        for attr in ['text', 'm_Script', 'bytes']:
                            if hasattr(data, attr):
                                value = getattr(data, attr)
                                self.original_data_cache[obj.path_id]['attributes'][attr] = {
                                    'type': type(value),
                                    'value': value  # Garder l'original pour comparaison
                                }
                    except:
                        continue
                        
        except Exception as e:
            print(f"   ⚠️ Erreur lors de la mise en cache: {e}")

    def _verify_unity_file_complete_integrity(self, file_path: Path, text_entries: List[Dict]) -> bool:
        """Vérifie l'intégrité complète du fichier Unity modifié"""
        try:
            env = UnityPy.load(str(file_path))
            readable_objects = 0
            expected_objects = len(text_entries)
            
            # Vérifier que tous les objets sont lisibles
            for obj in env.objects:
                try:
                    data = obj.read()
                    readable_objects += 1
                    
                    # Si c'est un objet qu'on a modifié, vérifier qu'il contient des données cohérentes
                    path_id = obj.path_id
                    if path_id in [e.get('path_id') for e in text_entries]:
                        if obj.type.name == "TextAsset":
                            if not self._verify_text_asset_coherence(data):
                                print(f"   ⚠️ TextAsset {path_id} incohérent")
                                return False
                        elif obj.type.name == "MonoBehaviour":
                            if not self._verify_monobehaviour_coherence(data):
                                print(f"   ⚠️ MonoBehaviour {path_id} incohérent")
                                return False
                                
                except Exception as e:
                    print(f"   ⚠️ Objet non lisible {obj.path_id}: {e}")
                    continue
            
            del env
            gc.collect()
            
            print(f"   🔍 Vérification complète: {readable_objects} objets lisibles")
            return readable_objects >= expected_objects
            
        except Exception as e:
            print(f"   ⚠️ Problème d'intégrité majeur: {e}")
            return False

    def _verify_text_asset_coherence(self, data) -> bool:
        """Vérifie la cohérence d'un TextAsset"""
        try:
            # Vérifier que les attributs de base sont présents et cohérents
            if hasattr(data, 'text') and data.text is not None:
                if not isinstance(data.text, str):
                    return False
            elif hasattr(data, 'm_Script') and data.m_Script is not None:
                if not isinstance(data.m_Script, (str, bytes, bytearray)):
                    return False
            elif hasattr(data, 'bytes') and data.bytes is not None:
                if not isinstance(data.bytes, (str, bytes, bytearray)):
                    return False
            else:
                return False
                
            return True
        except:
            return False

    def _verify_monobehaviour_coherence(self, data) -> bool:
        """Vérifie la cohérence d'un MonoBehaviour"""
        try:
            # Essayer de lire les données comme typetree
            mono_data = self._read_mono_data(data)
            return mono_data is not None and len(mono_data) > 0
        except:
            return False

    def _replace_file_safely(self, source: Path, target: Path) -> bool:
        """Remplace un fichier de manière sécurisée avec plusieurs tentatives"""
        max_attempts = 20
        wait_time = 0.05
        
        for attempt in range(max_attempts):
            try:
                # Sous Windows, essayer de s'assurer que le fichier n'est pas verrouillé
                if os.name == 'nt':
                    # Forcer le garbage collector
                    gc.collect()
                    time.sleep(wait_time)
                
                # Tenter le remplacement
                shutil.move(str(source), str(target))
                return True
                
            except PermissionError:
                time.sleep(wait_time)
                wait_time *= 1.1  # Augmenter progressivement le délai
                continue
            except Exception as e:
                print(f"   ❌ Erreur remplacement (tentative {attempt + 1}): {e}")
                time.sleep(wait_time)
                continue
        
        return False

    def _modify_text_asset_safe(self, obj, text_entry: Dict) -> bool:
        """Modifie un TextAsset en préservant strictement les types originaux"""
        try:
            data = obj.read()
            path_id = obj.path_id
            
            # Vérifier que c'est le bon asset
            asset_name = self._get_asset_name(data, obj)
            if asset_name != text_entry['asset_name']:
                return False
            
            # Obtenir les informations sur les types originaux
            original_info = self.original_data_cache.get(path_id, {})
            
            new_content = text_entry['translated_text']
            
            print(f"    📝 Modification TextAsset: {asset_name}")
            
            # Modifier en préservant exactement le type original
            success = False
            
            if hasattr(data, 'text'):
                # Vérifier le type original
                original_type = original_info.get('attributes', {}).get('text', {}).get('type', str)
                if original_type == str:
                    data.text = str(new_content)
                    success = True
                else:
                    print(f"      ⚠️ Type inattendu pour text: {original_type}")
                    return False
                    
            elif hasattr(data, 'm_Script'):
                original_type = original_info.get('attributes', {}).get('m_Script', {}).get('type', str)
                if original_type in (bytes, bytearray):
                    data.m_Script = new_content.encode('utf-8') if isinstance(new_content, str) else new_content
                    success = True
                elif original_type == str:
                    data.m_Script = str(new_content)
                    success = True
                else:
                    print(f"      ⚠️ Type inattendu pour m_Script: {original_type}")
                    return False
                    
            elif hasattr(data, 'bytes'):
                original_type = original_info.get('attributes', {}).get('bytes', {}).get('type', str)
                if original_type in (bytes, bytearray):
                    data.bytes = new_content.encode('utf-8') if isinstance(new_content, str) else new_content
                    success = True
                elif original_type == str:
                    data.bytes = str(new_content)
                    success = True
                else:
                    print(f"      ⚠️ Type inattendu pour bytes: {original_type}")
                    return False
            else:
                print(f"      ⚠️ Aucun attribut de contenu trouvé pour {asset_name}")
                return False
            
            if success:
                try:
                    data.save()
                    print("      ✓ TextAsset modifié avec préservation des types")
                    return True
                except Exception as save_error:
                    print(f"      ✗ Erreur lors de la sauvegarde: {save_error}")
                    return False
                    
        except Exception as e:
            print(f"    ❌ Erreur lors de la modification du TextAsset: {e}")
            return False

    def _modify_monobehaviour_safe(self, obj, text_entry: Dict) -> bool:
        """Modifie un MonoBehaviour de manière sécurisée avec préservation des types"""
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
            
            # Obtenir le type original de la valeur
            original_value = self._get_nested_value(mono_data, field_path)
            original_type = type(original_value) if original_value is not None else str
            
            # Convertir la nouvelle valeur au bon type
            converted_value = self._convert_to_type(text_entry['translated_text'], original_type)
            
            # Modifier la valeur dans le chemin spécifié
            if self._set_nested_value(mono_data, field_path, converted_value):
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

    def _convert_to_type(self, value: str, target_type: type):
        """Convertit une valeur vers le type cible"""
        if target_type == str:
            return str(value)
        elif target_type in (bytes, bytearray):
            return value.encode('utf-8') if isinstance(value, str) else value
        elif target_type == int:
            try:
                return int(value)
            except:
                return 0
        elif target_type == float:
            try:
                return float(value)
            except:
                return 0.0
        elif target_type == bool:
            return str(value).lower() in ('true', '1', 'yes', 'on')
        else:
            return str(value)

    def _get_nested_value(self, data: Dict, path: str):
        """Obtient une valeur dans un objet imbriqué"""
        try:
            keys = path.split('.')
            current = data
            
            for key in keys:
                if '[' in key and ']' in key:
                    field_name = key.split('[')[0]
                    index = int(key.split('[')[1].split(']')[0])
                    
                    if field_name not in current or not isinstance(current[field_name], list):
                        return None
                        
                    if index >= len(current[field_name]):
                        return None
                        
                    current = current[field_name][index]
                else:
                    if key not in current:
                        return None
                    current = current[key]
            
            return current
            
        except:
            return None

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

    def _set_nested_value(self, data: Dict, path: str, value) -> bool:
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

    def validate_before_injection(self, translation_data: Dict) -> bool:
        """Valide les données avant injection pour éviter les corruptions"""
        print("🔍 Validation des données avant injection...")
        
        try:
            texts = translation_data.get('texts', [])
            if not texts:
                print("❌ Aucune donnée de traduction trouvée")
                return False
            
            valid_count = 0
            issues_found = []
            
            for i, text_entry in enumerate(texts):
                # Vérifications de base
                if not text_entry.get('is_translated', False):
                    continue
                    
                # Vérifier la présence des champs essentiels
                required_fields = ['original_text', 'translated_text', 'source_file', 'path_id']
                missing_fields = [field for field in required_fields if not text_entry.get(field)]
                
                if missing_fields:
                    issues_found.append(f"Entrée {i}: champs manquants {missing_fields}")
                    continue
                
                # Vérifier que le fichier source existe et est accessible
                source_file = Path(text_entry['source_file'])
                if not source_file.exists():
                    issues_found.append(f"Entrée {i}: fichier source inexistant {source_file}")
                    continue
                    
                if not os.access(source_file, os.R_OK | os.W_OK):
                    issues_found.append(f"Entrée {i}: permissions insuffisantes {source_file}")
                    continue
                
                # Vérifier que le fichier Unity peut être chargé
                if source_file.suffix.lower() in ['.assets', '.bundle', '.resource', '.resS', '.dat']:
                    if not self._verify_unity_file_loadable(source_file):
                        issues_found.append(f"Entrée {i}: fichier Unity non chargeable {source_file}")
                        continue
                
                # Vérifier la cohérence des données de traduction
                original = text_entry['original_text'].strip()
                translated = text_entry['translated_text'].strip()
                
                if not translated or translated == original:
                    continue  # Pas d'erreur, mais pas de traduction utile
                
                if len(translated) > len(original) * 10:  # Traduction anormalement longue
                    issues_found.append(f"Entrée {i}: traduction suspecte (trop longue)")
                    continue
                
                if self._contains_dangerous_chars(translated):
                    issues_found.append(f"Entrée {i}: caractères dangereux détectés")
                    continue
                
                valid_count += 1
            
            # Afficher le résumé de validation
            print(f"   ✅ Entrées valides: {valid_count}")
            print(f"   ⚠️ Problèmes détectés: {len(issues_found)}")
            
            if issues_found:
                print("\n🚨 Problèmes détectés:")
                for issue in issues_found[:10]:  # Limiter à 10 pour éviter le spam
                    print(f"   - {issue}")
                if len(issues_found) > 10:
                    print(f"   ... et {len(issues_found) - 10} autres problèmes")
            
            return valid_count > 0
            
        except Exception as e:
            print(f"❌ Erreur lors de la validation: {e}")
            return False

    def create_test_backup(self) -> bool:
        """Crée une sauvegarde de test pour s'assurer que tout fonctionne"""
        print("🧪 Test de sauvegarde...")
        
        try:
            test_file = self.game_path / "test_backup_temp.txt"
            
            # Créer un fichier test
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write("Test de sauvegarde")
            
            # Tester la sauvegarde
            success = self.create_backup(test_file)
            
            # Nettoyer
            if test_file.exists():
                test_file.unlink()
            
            if success:
                print("   ✅ Système de sauvegarde fonctionnel")
            else:
                print("   ❌ Problème avec le système de sauvegarde")
                
            return success
            
        except Exception as e:
            print(f"   ❌ Erreur lors du test de sauvegarde: {e}")
            return False

    def restore_backup(self, backup_timestamp: Optional[str] = None) -> bool:
        """Restaure les fichiers depuis une sauvegarde avec vérification d'intégrité"""
        try:
            if backup_timestamp:
                backup_path = Path("backups") / backup_timestamp
            else:
                backup_path = self.backup_dir
                
            if not backup_path.exists():
                print(f"❌ Dossier de sauvegarde introuvable: {backup_path}")
                return False
                
            print(f"🔄 Restauration depuis: {backup_path}")
            
            restored_count = 0
            failed_count = 0
            
            for backup_file in backup_path.rglob('*'):
                if backup_file.is_file():
                    try:
                        relative_path = backup_file.relative_to(backup_path)
                        target_file = self.game_path / relative_path
                        
                        # Créer les dossiers parents si nécessaire
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Sauvegarder le fichier actuel si différent
                        if target_file.exists():
                            current_hash = self._calculate_hash(target_file)
                            backup_hash = self._calculate_hash(backup_file)
                            
                            if current_hash == backup_hash:
                                continue  # Fichier identique, pas besoin de restaurer
                        
                        # Restaurer le fichier
                        shutil.copy2(backup_file, target_file)
                        
                        # Vérifier la restauration
                        if self._verify_backup_integrity(backup_file, target_file):
                            restored_count += 1
                            print(f"   ✅ Restauré: {relative_path}")
                        else:
                            failed_count += 1
                            print(f"   ❌ Échec vérification: {relative_path}")
                        
                    except Exception as e:
                        failed_count += 1
                        print(f"   ⚠️ Erreur restauration {backup_file}: {e}")
                        continue
            
            print(f"\n🏁 Restauration terminée:")
            print(f"   ✅ Fichiers restaurés: {restored_count}")
            print(f"   ❌ Échecs: {failed_count}")
            
            return failed_count == 0
            
        except Exception as e:
            print(f"❌ Erreur lors de la restauration: {e}")
            return False

    def cleanup_temp_files(self):
        """Nettoie les fichiers temporaires"""
        try:
            temp_patterns = ['*.tmp', '*.backup_temp', '*.unity_temp']
            cleaned_count = 0
            
            for pattern in temp_patterns:
                for temp_file in self.game_path.rglob(pattern):
                    try:
                        temp_file.unlink()
                        cleaned_count += 1
                    except:
                        continue
            
            if cleaned_count > 0:
                print(f"🧹 Nettoyage terminé: {cleaned_count} fichiers temporaires supprimés")
                
        except Exception as e:
            print(f"⚠️ Erreur lors du nettoyage: {e}")

    def debug_asset_info(self, file_path: Path, path_id: int, debug: bool = False) -> Dict:
        """Analyse détaillée d'un asset pour le debugging"""
        if not debug:
            return {}
            
        try:
            env = UnityPy.load(str(file_path))
            debug_info = {}
            
            for obj in env.objects:
                if obj.path_id == path_id:
                    data = obj.read()
                    debug_info = {
                        'path_id': path_id,
                        'object_type': obj.type.name,
                        'data_type': type(data).__name__,
                        'attributes': {}
                    }
                    
                    print(f"🔍 DEBUG Asset {path_id} dans {file_path.name}:")
                    print(f"   Type objet: {obj.type.name}")
                    print(f"   Type données: {type(data).__name__}")
                    
                    # Analyser les attributs de contenu
                    for attr in ['text', 'm_Script', 'bytes', 'name', 'm_Name']:
                        if hasattr(data, attr):
                            try:
                                value = getattr(data, attr)
                                debug_info['attributes'][attr] = {
                                    'type': type(value).__name__,
                                    'length': len(value) if hasattr(value, '__len__') else None,
                                    'value_preview': repr(value)[:100] if value else None
                                }
                                print(f"   {attr}: {type(value).__name__} = {repr(value)[:100]}{'...' if len(repr(value)) > 100 else ''}")
                            except Exception as e:
                                debug_info['attributes'][attr] = {'error': str(e)}
                                print(f"   {attr}: ERREUR - {e}")
                    
                    # Pour MonoBehaviour, analyser la structure
                    if obj.type.name == "MonoBehaviour":
                        try:
                            mono_data = self._read_mono_data(data)
                            if mono_data:
                                debug_info['mono_structure'] = list(mono_data.keys())
                                print(f"   Structure MonoBehaviour: {list(mono_data.keys())}")
                        except Exception as e:
                            print(f"   Erreur analyse MonoBehaviour: {e}")
                    
                    break
            
            del env
            gc.collect()
            return debug_info
            
        except Exception as e:
            print(f"❌ Erreur debug asset {path_id}: {e}")
            return {'error': str(e)}

    def run_diagnostic_mode(self, translation_data: Dict, max_files: int = 3) -> bool:
        """Mode diagnostic pour analyser les assets avant injection"""
        print("\n🔬 MODE DIAGNOSTIC ACTIVÉ")
        print("=" * 50)
        
        try:
            translated_entries = self._filter_valid_translations(translation_data['texts'])
            files_to_process = self._group_by_source_file(translated_entries)
            
            analyzed_files = 0
            for source_file, text_entries in files_to_process.items():
                if analyzed_files >= max_files:
                    break
                    
                print(f"\n📁 DIAGNOSTIC: {Path(source_file).name}")
                print("-" * 40)
                
                # Analyser chaque asset dans ce fichier
                for entry in text_entries[:3]:  # Limiter à 3 assets par fichier
                    if entry.get('path_id'):
                        debug_info = self.debug_asset_info(
                            Path(source_file), 
                            entry['path_id'], 
                            debug=True
                        )
                        
                        if debug_info and not debug_info.get('error'):
                            print(f"\n   📝 Traduction prévue:")
                            print(f"      Original: {entry.get('original_text', '')[:100]}...")
                            print(f"      Traduit:  {entry.get('translated_text', '')[:100]}...")
                            
                            # Vérifier la compatibilité des types
                            self._check_translation_compatibility(entry, debug_info)
                        
                        print()
                
                analyzed_files += 1
            
            print("\n" + "=" * 50)
            print("🔬 Diagnostic terminé")
            
            # Demander confirmation pour continuer
            response = input("\n❓ Continuer avec l'injection ? (y/N): ").lower().strip()
            return response in ['y', 'yes', 'o', 'oui']
            
        except Exception as e:
            print(f"❌ Erreur durant le diagnostic: {e}")
            return False

    def _check_translation_compatibility(self, entry: Dict, debug_info: Dict):
        """Vérifie la compatibilité entre la traduction et les types de données"""
        try:
            original = entry.get('original_text', '')
            translated = entry.get('translated_text', '')
            
            # Analyser les changements de longueur
            length_ratio = len(translated) / len(original) if original else 1
            if length_ratio > 3:
                print(f"   ⚠️ ATTENTION: Texte traduit 3x plus long ({length_ratio:.1f}x)")
            elif length_ratio < 0.3:
                print(f"   ⚠️ ATTENTION: Texte traduit très court ({length_ratio:.1f}x)")
            
            # Vérifier les caractères spéciaux
            original_chars = set(original)
            translated_chars = set(translated)
            new_chars = translated_chars - original_chars
            
            if new_chars:
                special_chars = {c for c in new_chars if ord(c) > 127 or ord(c) < 32}
                if special_chars:
                    print(f"   ⚠️ ATTENTION: Nouveaux caractères spéciaux: {special_chars}")
            
            # Vérifier la cohérence avec le type de données
            attributes = debug_info.get('attributes', {})
            for attr_name, attr_info in attributes.items():
                if attr_info.get('type') == 'bytes' and any(ord(c) > 127 for c in translated):
                    print(f"   ⚠️ ATTENTION: Caractères non-ASCII avec attribut bytes ({attr_name})")
            
            print(f"   ✅ Longueur: {len(original)} → {len(translated)} ({length_ratio:.2f}x)")
            
        except Exception as e:
            print(f"   ⚠️ Erreur vérification compatibilité: {e}")

    def inject_translations_with_diagnostics(
        self, 
        translation_data: Dict, 
        progress_callback: Optional[Callable] = None,
        enable_diagnostics: bool = True
    ) -> int:
        """Version avec diagnostics intégrés"""
        
        if enable_diagnostics:
            print("🔬 Lancement du mode diagnostic...")
            if not self.run_diagnostic_mode(translation_data):
                print("❌ Injection annulée par l'utilisateur")
                return 0
        
        # Continuer avec l'injection normale
        return self.inject_translations(translation_data, progress_callback)
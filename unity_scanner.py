# unity_scanner.py
"""
Module pour le scan des fichiers Unity et l'extraction des textes.
"""

import os
import re
from pathlib import Path
import UnityPy
from datetime import datetime


class UnityTextScanner:
    def __init__(self, game_path, progress_callback=None):
        self.game_path = Path(game_path)
        self.found_texts = []
        self.progress_callback = progress_callback
        self.text_patterns = [
            r'subtitle', r'dialogue', r'dialog', r'caption', r'text',
            r'localization', r'translation', r'string', r'message'
        ]

    def scan_directory(self):
        """Scanne récursivement le dossier du jeu"""
        unity_extensions = ['.assets', '.bundle', '.resource', '.resS', '.dat']
        all_files = []
        # Collecter tous les fichiers à analyser
        for root, dirs, files in os.walk(self.game_path):
            for file in files:
                file_path = Path(root) / file
                if (any(file.lower().endswith(ext) for ext in unity_extensions) or 
                    file.lower().endswith(('.json', '.xml', '.txt'))):
                    all_files.append(file_path)
        total_files = len(all_files)
        # Traiter les fichiers
        for i, file_path in enumerate(all_files):
            if self.progress_callback:
                progress = (i + 1) / total_files * 100
                self.progress_callback(progress, f"Analyse: {file_path.name}")
            if any(str(file_path).lower().endswith(ext) for ext in unity_extensions):
                self.process_unity_file(file_path)
            elif str(file_path).lower().endswith(('.json', '.xml', '.txt')):
                self.process_text_file(file_path)

    def process_unity_file(self, file_path):
        """Traite un fichier Unity"""
        try:
            env = UnityPy.load(str(file_path))
            for obj in env.objects:
                if obj.type.name == "TextAsset":
                    self.extract_text_asset(obj, file_path)
                elif obj.type.name == "MonoBehaviour":
                    self.extract_monobehaviour(obj, file_path)
        except Exception as e:
            print(f"Erreur lors du traitement de {file_path}: {e}")

    def extract_text_asset(self, obj, source_file):
        """Extrait le contenu d'un TextAsset"""
        try:
            data = obj.read()
            # Obtenir le nom
            name = self.get_asset_name(data, obj)
            # Obtenir le contenu avec plus d'informations sur le type
            content = self.get_asset_content(data)
            content_type = self.detect_content_type(data)
            if content and len(content) > 10:
                if self.is_text_relevant(name, content):
                    text_info = {
                        'id': f"{source_file.stem}_{obj.path_id}",
                        'source_file': str(source_file),
                        'asset_name': name,
                        'asset_type': 'TextAsset',
                        'content_type': content_type,
                        'path_id': obj.path_id,
                        'original_text': content,
                        'translated_text': content,
                        'is_translated': False,
                        'extraction_date': datetime.now().isoformat(),
                        'data_properties': self.get_data_properties(data)
                    }
                    self.found_texts.append(text_info)
                    print(f"  Texte trouvé: {name} (Type: {content_type})")
        except Exception as e:
            print(f"  Erreur lors de l'extraction TextAsset: {e}")

    def extract_monobehaviour(self, obj, source_file):
        """Extrait les données d'un MonoBehaviour"""
        try:
            data = obj.read()
            name = self.get_asset_name(data, obj)
            # Lire les données du MonoBehaviour
            mono_data = self.read_mono_data(data)
            if mono_data:
                # Passer obj.path_id pour l'identifier correctement
                self.search_mono_data(mono_data, name, source_file, obj.path_id)
        except Exception as e:
            print(f"  Erreur lors de l'extraction MonoBehaviour: {e}")

    def read_mono_data(self, data):
        """Lit les données d'un MonoBehaviour de manière robuste"""
        mono_data = None
        # Essayer read_typetree en premier
        if hasattr(data, 'read_typetree'):
            try:
                mono_data = data.read_typetree()
            except:
                pass
        # Si échec, essayer de lire les attributs directs
        if mono_data is None:
            mono_data = {}
            for attr in dir(data):
                if not attr.startswith('_') and attr not in ['read', 'read_typetree']:
                    try:
                        value = getattr(data, attr)
                        if isinstance(value, (str, int, float, bool, list, dict)):
                            mono_data[attr] = value
                    except:
                        continue
        return mono_data

    def search_mono_data(self, data, name, source_file, path_id, path="", depth=0):
        """Recherche récursive dans les données MonoBehaviour"""
        if depth > 5:
            return
        try:
            if isinstance(data, dict):
                for key, value in data.items():
                    try:
                        new_path = f"{path}.{key}" if path else key
                        if isinstance(value, str) and len(value) > 10:
                            if self.is_text_relevant(str(key), value):
                                # Nettoyer le chemin pour l'ID
                                clean_path = new_path.replace('.', '_').replace('[', '_').replace(']', '_')
                                text_info = {
                                    'id': f"{source_file.stem}_{path_id}_{clean_path}",
                                    'source_file': str(source_file),
                                    'asset_name': f"{name}.{new_path}",
                                    'asset_type': 'MonoBehaviour',
                                    'path_id': path_id,
                                    'field_path': new_path,
                                    'original_text': value,
                                    'translated_text': value,
                                    'is_translated': False,
                                    'extraction_date': datetime.now().isoformat()
                                }
                                self.found_texts.append(text_info)
                                print(f"  Champ texte trouvé: {new_path}")
                        if isinstance(value, (dict, list)) and depth < 3:
                            self.search_mono_data(value, name, source_file, path_id, new_path, depth + 1)
                    except:
                        continue
            elif isinstance(data, list) and depth < 3:
                for i, item in enumerate(data[:50]):
                    try:
                        if isinstance(item, (dict, str)):
                            self.search_mono_data(item, name, source_file, path_id, f"{path}[{i}]", depth + 1)
                    except:
                        continue
        except:
            pass

    def process_text_file(self, file_path):
        """Traite les fichiers texte"""
        try:
            if self.is_text_relevant(file_path.name, ""):
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                if len(content) > 10 and self.contains_dialogue_pattern(content):
                    text_info = {
                        'id': f"textfile_{file_path.stem}",
                        'source_file': str(file_path),
                        'asset_name': file_path.name,
                        'asset_type': 'TextFile',
                        'original_text': content,
                        'translated_text': content,
                        'is_translated': False,
                        'extraction_date': datetime.now().isoformat()
                    }
                    self.found_texts.append(text_info)
                    print(f"  Fichier texte trouvé: {file_path.name}")
        except Exception as e:
            print(f"Erreur lors de la lecture de {file_path}: {e}")

    def get_asset_name(self, data, obj):
        """Obtient le nom d'un asset de manière robuste"""
        if hasattr(data, 'name') and data.name:
            return data.name
        elif hasattr(data, 'm_Name') and data.m_Name:
            return data.m_Name
        elif hasattr(obj, 'name') and obj.name:
            return obj.name
        else:
            return f"Asset_{obj.path_id}"

    def get_asset_content(self, data):
        """Obtient le contenu d'un asset"""
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

    # --- Méthodes ajoutées depuis unity_injection_fix_2 ---
    def detect_content_type(self, data):
        """Détecte le type de contenu d'un TextAsset"""
        if hasattr(data, 'text') and data.text is not None:
            return 'text_property'
        elif hasattr(data, 'm_Script'):
            return 'script_property'
        elif hasattr(data, 'bytes'):
            return 'bytes_property'
        else:
            return 'unknown'

    def get_data_properties(self, data):
        """Récupère les propriétés disponibles d'un objet de données"""
        properties = {}
        for attr in dir(data):
            if not attr.startswith('_') and not callable(getattr(data, attr)):
                try:
                    value = getattr(data, attr)
                    if value is not None:
                        properties[attr] = str(type(value).__name__)
                except:
                    continue
        return properties

    def is_text_relevant(self, name, content):
        """Vérifie si un texte semble pertinent"""
        name_lower = name.lower()
        name_relevant = any(pattern in name_lower for pattern in self.text_patterns)
        content_relevant = self.contains_dialogue_pattern(content) if content else False
        return name_relevant or content_relevant

    def contains_dialogue_pattern(self, content):
        """Vérifie si le contenu contient des patterns de dialogue"""
        dialogue_patterns = [
            r'"text"\s*:\s*"[^"]+"',
            r'<subtitle[^>]*>.*?</subtitle>',
            r'\d{2}:\d{2}:\d{2}[,\.]\d{3}',
            r'Dialogue:',
            r'\[.*?\].*?:.*',
            r'".*?"',  # Chaînes entre guillemets
            r'[A-Z][a-z]+\s*:\s*[A-Z]',  # Format "Nom: Texte"
        ]
        return any(re.search(pattern, content, re.IGNORECASE) for pattern in dialogue_patterns)

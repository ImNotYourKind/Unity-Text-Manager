# unity_scanner.py
"""
Module pour le scan des fichiers Unity et l'extraction des textes.
Version spécialisée pour bundles chiffrés/compressés et formats propriétaires
"""

import os
import re
from pathlib import Path
import UnityPy
from datetime import datetime
import struct
import json
import zlib
import lz4.frame


class UnityTextScanner:
    def __init__(self, game_path, progress_callback=None):
        self.game_path = Path(game_path)
        self.found_texts = []
        self.progress_callback = progress_callback
        self.warned_files = set()
        self.text_patterns = [
            r'subtitle', r'dialogue', r'dialog', r'caption', r'text',
            r'localization', r'translation', r'string', r'message',
            r'conversation', r'chat', r'speech', r'voice', r'line',
            r'story', r'scenario', r'script'
        ]
        # Détection IL2CPP
        self.is_il2cpp = self._detect_il2cpp()
        if self.is_il2cpp:
            print("[INFO] Jeu IL2CPP détecté - utilisation de stratégies spécialisées")

    def _detect_il2cpp(self):
        """Détecte si le jeu utilise IL2CPP"""
        il2cpp_indicators = [
            self.game_path / "il2cpp_data",
            self.game_path / "GameAssembly.dll",
            self.game_path / "UnityPlayer.dll"
        ]
        return any(indicator.exists() for indicator in il2cpp_indicators)

    def scan_directory(self):
        """Scanne récursivement le dossier du jeu avec focus sur les bundles"""
        unity_extensions = ['.assets', '.bundle', '.resource', '.resS', '.dat']
        all_files = []
        
        # Séparer les bundles des autres fichiers
        bundle_files = []
        regular_files = []
        
        for root, dirs, files in os.walk(self.game_path):
            root_path = Path(root)
            is_streaming = 'StreamingAssets' in str(root_path)
            
            for file in files:
                file_path = root_path / file
                if file.lower().endswith('.bundle'):
                    bundle_files.append(file_path)
                elif (any(file.lower().endswith(ext) for ext in unity_extensions) or 
                      file.lower().endswith(('.json', '.xml', '.txt'))):
                    regular_files.append(file_path)
        
        all_files = bundle_files + regular_files
        total_files = len(all_files)
        
        print(f"[INFO] {len(bundle_files)} fichiers bundle trouvés")
        print(f"[INFO] {len(regular_files)} autres fichiers Unity trouvés")
        
        # Analyser d'abord quelques bundles en détail
        if bundle_files:
            print("\n[INFO] === ANALYSE DÉTAILLÉE DES BUNDLES ===")
            self.analyze_bundle_structure(bundle_files[:5])  # Analyser les 5 premiers
        
        # Traiter tous les fichiers
        for i, file_path in enumerate(all_files):
            if self.progress_callback:
                progress = (i + 1) / total_files * 100
                self.progress_callback(progress, f"Analyse: {file_path.name}")
            
            if file_path.suffix.lower() == '.bundle':
                self.process_bundle_file(file_path)
            elif any(str(file_path).lower().endswith(ext) for ext in unity_extensions):
                self.process_unity_file(file_path)
            elif str(file_path).lower().endswith(('.json', '.xml', '.txt')):
                self.process_text_file(file_path)

    def analyze_bundle_structure(self, bundle_files):
        """Analyse en profondeur la structure des bundles"""
        for bundle_path in bundle_files:
            print(f"\n[ANALYSE] {bundle_path.name} ({bundle_path.stat().st_size} bytes)")
            
            try:
                with open(bundle_path, 'rb') as f:
                    header = f.read(64)
                
                # Analyser l'en-tête
                self.analyze_bundle_header(header, bundle_path.name)
                
                # Essayer différentes méthodes de décompression
                self.try_decompress_bundle(bundle_path)
                
                # Recherche de patterns de texte dans le fichier brut
                self.deep_scan_bundle(bundle_path)
                
            except Exception as e:
                print(f"    Erreur lors de l'analyse: {e}")

    def analyze_bundle_header(self, header, filename):
        """Analyse l'en-tête du bundle pour identifier le format"""
        print(f"    En-tête (hex): {header[:32].hex()}")
        print(f"    En-tête (ascii): {self.safe_ascii(header[:32])}")
        
        # Signatures courantes
        signatures = {
            b'UnityFS': 'UnityFS Bundle',
            b'UnityRaw': 'Unity Raw Bundle', 
            b'UnityWeb': 'Unity Web Bundle',
            b'\x1f\x8b': 'GZip compressed',
            b'PK': 'ZIP archive',
            b'BZ': 'BZip2 compressed',
            b'\x04\x22\x4d\x18': 'LZ4 compressed',
            b'\x28\xb5\x2f\xfd': 'Zstandard compressed',
        }
        
        detected = False
        for sig, desc in signatures.items():
            if header.startswith(sig):
                print(f"    Format détecté: {desc}")
                detected = True
                break
        
        if not detected:
            print("    Format inconnu - possiblement chiffré ou propriétaire")
            
            # Analyser l'entropie pour détecter le chiffrement
            entropy = self.calculate_entropy(header)
            print(f"    Entropie: {entropy:.2f} (>7.5 = probablement chiffré)")

    def calculate_entropy(self, data):
        """Calcule l'entropie de Shannon des données"""
        if len(data) == 0:
            return 0
        
        from collections import Counter
        import math
        
        counter = Counter(data)
        entropy = 0
        for count in counter.values():
            p = count / len(data)
            entropy -= p * math.log2(p)
        
        return entropy

    def safe_ascii(self, data):
        """Convertit les bytes en ASCII lisible"""
        return ''.join(chr(b) if 32 <= b <= 126 else '.' for b in data)

    def try_decompress_bundle(self, bundle_path):
        """Essaye différentes méthodes de décompression"""
        print("    Tentatives de décompression:")
        
        try:
            with open(bundle_path, 'rb') as f:
                data = f.read()
            
            # Essayer GZip
            try:
                import gzip
                decompressed = gzip.decompress(data)
                print(f"      ✓ GZip: {len(decompressed)} bytes décompressés")
                self.analyze_decompressed_data(decompressed, bundle_path, "gzip")
                return
            except:
                print("      ✗ GZip failed")
            
            # Essayer LZ4
            try:
                decompressed = lz4.frame.decompress(data)
                print(f"      ✓ LZ4: {len(decompressed)} bytes décompressés")
                self.analyze_decompressed_data(decompressed, bundle_path, "lz4")
                return
            except:
                print("      ✗ LZ4 failed")
            
            # Essayer zlib
            try:
                decompressed = zlib.decompress(data)
                print(f"      ✓ Zlib: {len(decompressed)} bytes décompressés")
                self.analyze_decompressed_data(decompressed, bundle_path, "zlib")
                return
            except:
                print("      ✗ Zlib failed")
            
            # Essayer de skipper l'en-tête et décompresser
            for skip in [16, 32, 64, 128, 256]:
                try:
                    decompressed = zlib.decompress(data[skip:])
                    print(f"      ✓ Zlib (skip {skip}): {len(decompressed)} bytes")
                    self.analyze_decompressed_data(decompressed, bundle_path, f"zlib_skip_{skip}")
                    return
                except:
                    continue
            
            print("      ✗ Aucune décompression réussie")
            
        except Exception as e:
            print(f"      Erreur: {e}")

    def analyze_decompressed_data(self, data, bundle_path, method):
        """Analyse les données décompressées"""
        print(f"    Analyse des données décompressées ({method}):")
        
        # Essayer de charger avec UnityPy
        try:
            env = UnityPy.load(data)
            if len(env.objects) > 0:
                print(f"      ✓ UnityPy: {len(env.objects)} objets trouvés!")
                self.process_unity_objects(env.objects, bundle_path, f"decompressed_{method}")
                return
        except:
            pass
        
        # Chercher des chaînes de texte
        strings = self.extract_all_strings_from_binary(data)
        relevant = [s for s in strings if self.is_potential_game_text(s)]
        
        if relevant:
            print(f"      ✓ {len(relevant)} chaînes de texte trouvées")
            for i, text in enumerate(relevant[:5]):  # Afficher les 5 premières
                print(f"        - {text[:50]}...")
            
            # Sauvegarder les textes trouvés
            for i, text in enumerate(relevant):
                text_info = {
                    'id': f"decompressed_{bundle_path.stem}_{method}_{i}",
                    'source_file': str(bundle_path),
                    'asset_name': f"DecompressedString_{i}",
                    'asset_type': f'Decompressed_{method}',
                    'original_text': text,
                    'translated_text': text,
                    'is_translated': False,
                    'extraction_date': datetime.now().isoformat(),
                    'extraction_method': f'decompression_{method}'
                }
                self.found_texts.append(text_info)

    def deep_scan_bundle(self, bundle_path):
        """Scan approfondi du bundle pour chercher des patterns de texte"""
        print("    Scan approfondi des patterns:")
        
        try:
            with open(bundle_path, 'rb') as f:
                data = f.read()
            
            # Chercher des patterns spécifiques aux jeux
            patterns_found = []
            
            # Pattern 1: Chaînes Unicode/UTF-16
            utf16_pattern = rb'(?:\x00[A-Za-z]){4,}'
            matches = re.findall(utf16_pattern, data)
            if matches:
                patterns_found.append(f"UTF-16 patterns: {len(matches)}")
                for match in matches[:3]:
                    try:
                        decoded = match.decode('utf-16le', errors='ignore').strip('\x00')
                        if len(decoded) > 5:
                            print(f"      UTF-16: {decoded}")
                    except:
                        pass
            
            # Pattern 2: JSON-like structures
            json_pattern = rb'\{"[^"]+"\s*:\s*"[^"]*"\s*[},]'
            matches = re.findall(json_pattern, data)
            if matches:
                patterns_found.append(f"JSON patterns: {len(matches)}")
                for match in matches[:3]:
                    try:
                        decoded = match.decode('utf-8', errors='ignore')
                        print(f"      JSON: {decoded}")
                    except:
                        pass
            
            # Pattern 3: Longueurs préfixées
            length_strings = self.find_length_prefixed_strings(data)
            if length_strings:
                patterns_found.append(f"Length-prefixed strings: {len(length_strings)}")
                for s in length_strings[:3]:
                    print(f"      String: {s[:50]}...")
            
            # Pattern 4: Dialogue markers
            dialogue_markers = [
                rb'dialogue', rb'text', rb'message', rb'subtitle',
                rb'speaker', rb'voice', rb'conversation'
            ]
            
            for marker in dialogue_markers:
                positions = []
                start = 0
                while True:
                    pos = data.find(marker, start)
                    if pos == -1:
                        break
                    positions.append(pos)
                    start = pos + 1
                    if len(positions) >= 10:  # Limiter pour éviter le spam
                        break
                
                if positions:
                    patterns_found.append(f"{marker.decode()}: {len(positions)} occurrences")
                    # Extraire le contexte autour
                    for pos in positions[:2]:
                        context_start = max(0, pos - 50)
                        context_end = min(len(data), pos + 100)
                        context = data[context_start:context_end]
                        readable = self.safe_ascii(context)
                        print(f"      Context: ...{readable}...")
            
            if patterns_found:
                print(f"      Patterns détectés: {', '.join(patterns_found)}")
            else:
                print("      ✗ Aucun pattern de texte détecté")
                
        except Exception as e:
            print(f"      Erreur: {e}")

    def find_length_prefixed_strings(self, data):
        """Trouve les chaînes avec longueur préfixée dans les données"""
        strings = []
        i = 0
        
        while i < len(data) - 8:
            try:
                # Essayer différents formats de longueur
                for length_format, size in [('<I', 4), ('<H', 2), ('<Q', 8)]:
                    if i + size > len(data):
                        continue
                        
                    try:
                        length = struct.unpack(length_format, data[i:i+size])[0]
                        
                        # Vérifier que la longueur est raisonnable
                        if 5 < length < 500 and i + size + length <= len(data):
                            string_data = data[i+size:i+size+length]
                            
                            # Essayer UTF-8
                            try:
                                decoded = string_data.decode('utf-8', errors='strict')
                                if self.is_potential_game_text(decoded):
                                    strings.append(decoded.strip())
                                    i += size + length
                                    break
                            except:
                                pass
                            
                            # Essayer UTF-16
                            try:
                                if length % 2 == 0:
                                    decoded = string_data.decode('utf-16le', errors='strict')
                                    if self.is_potential_game_text(decoded):
                                        strings.append(decoded.strip())
                                        i += size + length
                                        break
                            except:
                                pass
                    except:
                        pass
                else:
                    i += 1
            except:
                i += 1
        
        return list(set(strings))  # Supprimer les doublons

    def process_bundle_file(self, file_path):
        """Traite spécifiquement un fichier bundle"""
        print(f"[DEBUG] Traitement bundle: {file_path.name}")
        
        # D'abord essayer le traitement Unity standard
        success = self.process_unity_file(file_path, is_bundle=True)
        
        # Si échec, essayer l'analyse binaire aggressive
        if not success:
            print(f"[DEBUG] -> Analyse binaire du bundle...")
            self.analyze_binary_file(file_path, aggressive=True)

    def process_unity_file(self, file_path, is_bundle=False):
        """Traite un fichier Unity avec stratégies IL2CPP"""
        if not is_bundle:
            print(f"[DEBUG] Traitement du fichier Unity : {file_path}")
        
        try:
            env = None
            load_method = "standard"
            
            # Méthode 1: Chargement standard
            try:
                env = UnityPy.load(str(file_path))
                load_method = "standard"
            except Exception as e:
                pass
            
            # Méthode 2: Chargement en bytes
            if env is None:
                try:
                    with open(file_path, 'rb') as f:
                        env = UnityPy.load(f.read())
                    load_method = "raw_bytes"
                except Exception as e:
                    pass
            
            if env is None:
                if not is_bundle:
                    print(f"[DEBUG] -> Impossible de charger le fichier")
                return False
            
            if not is_bundle:
                print(f"[DEBUG] -> Fichier chargé via {load_method}. {len(env.objects)} objets trouvés.")
                
                if len(env.objects) > 0:
                    from collections import Counter
                    object_types = Counter(obj.type.name for obj in env.objects)
                    print(f"[DEBUG] -> Types d'objets : {object_types}")
            
            if len(env.objects) == 0:
                return False
            
            # Traiter les objets
            return self.process_unity_objects(env.objects, file_path, load_method)
                
        except Exception as e:
            if not is_bundle:
                print(f"[DEBUG] -> Échec du chargement du fichier : {file_path}. Erreur : {e}")
            return False

    def process_unity_objects(self, objects, source_file, load_method):
        """Traite les objets Unity extraits"""
        extracted_texts = 0
        mono_success = 0
        mono_total = sum(1 for obj in objects if obj.type.name == "MonoBehaviour")
        
        for obj in objects:
            if obj.type.name == "TextAsset":
                if self.extract_text_asset(obj, source_file):
                    extracted_texts += 1
            elif obj.type.name == "MonoBehaviour":
                if self.extract_monobehaviour_il2cpp(obj, source_file):
                    mono_success += 1
            elif obj.type.name in ["GameObject", "Transform", "RectTransform"]:
                if self.extract_gameobject_text(obj, source_file):
                    extracted_texts += 1
            else:
                if self.extract_from_asset(obj, source_file):
                    extracted_texts += 1
        
        if mono_total > 0:
            success_rate = (mono_success / mono_total) * 100
            print(f"[DEBUG] -> MonoBehaviour: {mono_success}/{mono_total} lus avec succès ({success_rate:.1f}%)")
        
        if extracted_texts > 0:
            print(f"[DEBUG] -> {extracted_texts} textes extraits de ce fichier")
            
        return extracted_texts > 0 or mono_success > 0

    def analyze_binary_file(self, file_path, aggressive=False):
        """Analyse binaire directe avec mode agressif pour les bundles"""
        if aggressive:
            print(f"[DEBUG] -> Analyse binaire agressive de {file_path.name}")
        else:
            print(f"[DEBUG] -> Analyse binaire directe de {file_path.name}")
        
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            
            # Mode agressif: essayer toutes les méthodes
            if aggressive:
                # Essayer de décompresser d'abord
                self.try_decompress_bundle(file_path)
                
                # Scan approfondi
                self.deep_scan_bundle(file_path)
            
            # Extraction standard des chaînes
            strings = self.extract_all_strings_from_binary(data)
            relevant_strings = [s for s in strings if self.is_potential_game_text(s)]
            
            if relevant_strings:
                print(f"[DEBUG] -> {len(relevant_strings)} chaînes potentielles trouvées")
                
                for i, text in enumerate(relevant_strings):
                    text_info = {
                        'id': f"binary_{file_path.stem}_{i}",
                        'source_file': str(file_path),
                        'asset_name': f"BinaryString_{i}",
                        'asset_type': 'BinaryExtraction',
                        'original_text': text,
                        'translated_text': text,
                        'is_translated': False,
                        'extraction_date': datetime.now().isoformat(),
                        'extraction_method': 'binary_analysis'
                    }
                    self.found_texts.append(text_info)
                    if not aggressive:  # Éviter le spam en mode agressif
                        print(f"    -> Texte binaire: {text[:50]}...")
        except Exception as e:
            print(f"[DEBUG] -> Erreur analyse binaire: {e}")

    # Garder toutes les autres méthodes existantes...
    def extract_all_strings_from_binary(self, data):
        """Extrait toutes les chaînes possibles depuis des données binaires"""
        strings = []
        
        try:
            # Méthode 1: Chaînes UTF-8
            utf8_strings = self.extract_strings_regex(data, 'utf-8')
            strings.extend(utf8_strings)
            
            # Méthode 2: Chaînes UTF-16
            utf16_strings = self.extract_strings_regex(data, 'utf-16le')
            strings.extend(utf16_strings)
            
            # Méthode 3: Chaînes avec longueur préfixée
            length_prefixed = self.find_length_prefixed_strings(data)
            strings.extend(length_prefixed)
            
            # Méthode 4: Recherche de patterns JSON
            json_strings = self.extract_json_strings(data)
            strings.extend(json_strings)
            
        except Exception as e:
            pass
        
        # Supprimer les doublons et trier par longueur
        unique_strings = list(set(strings))
        return sorted([s for s in unique_strings if len(s) > 3], key=len, reverse=True)

    def extract_strings_regex(self, data, encoding):
        """Extrait les chaînes avec regex selon l'encodage"""
        strings = []
        try:
            if encoding == 'utf-8':
                pattern = rb'[\x20-\x7E\xC0-\xFD][\x20-\x7E\x80-\xFD]{3,100}'
                matches = re.findall(pattern, data)
                for match in matches:
                    try:
                        decoded = match.decode('utf-8', errors='ignore').strip()
                        if self.is_valid_text_candidate(decoded):
                            strings.append(decoded)
                    except:
                        pass
            elif encoding == 'utf-16le':
                pattern = rb'(?:\x00[\x20-\x7E]){4,50}'
                matches = re.findall(pattern, data)
                for match in matches:
                    try:
                        decoded = match.decode('utf-16le', errors='ignore').strip()
                        if self.is_valid_text_candidate(decoded):
                            strings.append(decoded)
                    except:
                        pass
        except:
            pass
        return strings

    def extract_json_strings(self, data):
        """Extrait les chaînes depuis les patterns JSON trouvés"""
        strings = []
        try:
            json_pattern = rb'\{"[^"]+"\s*:\s*"[^"]+"\s*[},]'
            matches = re.findall(json_pattern, data)
            
            for match in matches:
                try:
                    json_str = match.decode('utf-8', errors='ignore')
                    value_pattern = r':\s*"([^"]+)"'
                    values = re.findall(value_pattern, json_str)
                    for value in values:
                        if self.is_valid_text_candidate(value):
                            strings.append(value)
                except:
                    pass
        except:
            pass
        
        return strings

    def is_valid_text_candidate(self, text):
        """Vérifie si une chaîne est un candidat valide pour du texte de jeu"""
        if len(text) < 4:
            return False
        
        technical_patterns = [
            r'^[0-9a-fA-F]{8,}$',
            r'^\d+\.\d+\.\d+',
            r'^[A-Z_]{6,}$',
            r'\.dll$|\.exe$|\.so$',
            r'^m_[A-Z]',
            r'^UnityEngine\.',
            r'^System\.',
            r'^\s*$',
            r'^[<>/_\-=+*#@$%^&(){}[\]\\|;:,.\d\s]+$',
            r'^(true|false|null)$',
        ]
        
        for pattern in technical_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return False
        
        letter_count = sum(1 for c in text if c.isalpha())
        if letter_count < len(text) * 0.3:
            return False
        
        return True

    def is_potential_game_text(self, text):
        """Détermine si un texte pourrait être du contenu de jeu"""
        if not self.is_valid_text_candidate(text):
            return False
        
        # Patterns spécifiques aux jeux (plus permissifs)
        game_patterns = [
            r'\b(you|your|player|character|game|level|score|points|health|mana|inventory)\b',
            r'\b(click|press|select|choose|option|menu|settings|save|load)\b',
            r'\b(dialogue|conversation|speak|talk|say|tell|ask|answer)\b',
            r'[.!?]\s*$',
            r'^[A-Z].*[a-z]',
            r'\b(the|and|for|are|with|this|that|have|from|they|know|want|been|good|much|some|time|very|when|come|here|just|like|long|make|many|over|such|take|than|them|well|were)\b',  # Mots anglais courants
        ]
        
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in game_patterns) or len(text) > 20

    # Méthodes existantes inchangées...
    def extract_monobehaviour_il2cpp(self, obj, source_file):
        """Version spécialisée IL2CPP pour extraire les MonoBehaviour"""
        try:
            data = obj.read()
            name = self.get_asset_name(data, obj)
            
            mono_data = None
            extraction_method = "failed"
            
            if hasattr(data, 'read_typetree'):
                try:
                    mono_data = data.read_typetree()
                    extraction_method = "typetree"
                except:
                    pass
            
            if mono_data is None:
                mono_data = self.extract_il2cpp_properties(data)
                if mono_data:
                    extraction_method = "il2cpp_direct"
            
            if mono_data is None:
                try:
                    if hasattr(obj, 'get_raw_data'):
                        raw_data = obj.get_raw_data()
                        mono_data = {'raw_strings': self.extract_all_strings_from_binary(raw_data)}
                        extraction_method = "raw_data"
                except:
                    pass
            
            if mono_data:
                found_texts_count = len(self.found_texts)
                self.search_mono_data(mono_data, name, source_file, obj.path_id)
                new_texts = len(self.found_texts) - found_texts_count
                
                if new_texts > 0:
                    print(f"  MonoBehaviour '{name}': {new_texts} texte(s) via {extraction_method}")
                
                return True
            else:
                return False
                
        except Exception as e:
            return False

    def extract_il2cpp_properties(self, data):
        """Extrait les propriétés spécifiques aux jeux IL2CPP"""
        properties = {}
        
        il2cpp_text_properties = [
            'm_Text', 'text', 'content', 'value', 'message', 'dialogue',
            'm_FontData', 'm_Material', 'm_Color', 'm_RaycastTarget',
            'localizedString', 'localized', 'stringValue', 'textValue',
            'displayText', 'uiText', 'labelText', 'buttonText',
            'titleText', 'descriptionText', 'subtitleText'
        ]
        
        found_any = False
        for prop in il2cpp_text_properties:
            if hasattr(data, prop):
                try:
                    value = getattr(data, prop)
                    if value is not None:
                        properties[prop] = value
                        found_any = True
                except:
                    continue
        
        if not found_any:
            for attr in dir(data):
                if (not attr.startswith('_') and 
                    not attr.startswith('read') and 
                    not callable(getattr(data, attr, None))):
                    try:
                        value = getattr(data, attr)
                        if (value is not None and 
                            isinstance(value, (str, int, float, bool, list, dict))):
                            properties[attr] = value
                    except:
                        continue
        
        return properties if properties else None

    def extract_text_asset(self, obj, source_file):
        """Extrait le contenu d'un TextAsset"""
        try:
            data = obj.read()
            name = self.get_asset_name(data, obj)
            content = self.get_asset_content(data)
            content_type = self.detect_content_type(data)
            
            if content and len(content) > 10:
                if (self.is_text_relevant(name, content) or 
                    self.is_potential_game_text(content)):
                    
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
                    return True
        except Exception as e:
            print(f"  Erreur lors de l'extraction TextAsset: {e}")
        
        return False

    def extract_from_asset(self, obj, source_file):
        """Essaye d'extraire du texte depuis d'autres types d'assets"""
        try:
            data = obj.read()
            name = self.get_asset_name(data, obj)
            
            text_found = False
            
            for attr in dir(data):
                if not attr.startswith('_'):
                    try:
                        value = getattr(data, attr)
                        if (isinstance(value, str) and 
                            len(value) > 10 and 
                            self.is_potential_game_text(value)):
                            
                            text_info = {
                                'id': f"{source_file.stem}_{obj.path_id}_{attr}",
                                'source_file': str(source_file),
                                'asset_name': f"{name}.{attr}",
                                'asset_type': f"{obj.type.name}",
                                'path_id': obj.path_id,
                                'original_text': value,
                                'translated_text': value,
                                'is_translated': False,
                                'extraction_date': datetime.now().isoformat()
                            }
                            self.found_texts.append(text_info)
                            print(f"    -> Texte dans {obj.type.name}: {attr}")
                            text_found = True
                    except:
                        continue
            
            return text_found
        except:
            return False

    def extract_gameobject_text(self, obj, source_file):
        """Essaye d'extraire du texte depuis GameObject, Transform, etc."""
        try:
            data = obj.read()
            name = self.get_asset_name(data, obj)
            
            text_content = None
            text_properties = ['m_Text', 'text', 'string', 'content', 'value', 'message']
            
            for prop in text_properties:
                if hasattr(data, prop):
                    try:
                        value = getattr(data, prop)
                        if isinstance(value, str) and len(value) > 3:
                            text_content = value
                            break
                    except:
                        continue
            
            if text_content and self.is_potential_game_text(text_content):
                text_info = {
                    'id': f"{source_file.stem}_{obj.path_id}_{obj.type.name}",
                    'source_file': str(source_file),
                    'asset_name': name,
                    'asset_type': obj.type.name,
                    'path_id': obj.path_id,
                    'original_text': text_content,
                    'translated_text': text_content,
                    'is_translated': False,
                    'extraction_date': datetime.now().isoformat()
                }
                self.found_texts.append(text_info)
                print(f"  Texte trouvé dans {obj.type.name}: {name}")
                return True
                
        except Exception as e:
            pass
        
        return False

    def search_mono_data(self, data, name, source_file, path_id, path="", depth=0):
        """Recherche récursive dans les données MonoBehaviour"""
        if depth > 6:
            return
        try:
            if isinstance(data, dict):
                for key, value in data.items():
                    try:
                        new_path = f"{path}.{key}" if path else key
                        if isinstance(value, str) and len(value) > 3:
                            if (self.is_text_relevant(str(key), value) or 
                                self.is_potential_game_text(value)):
                                
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
                                print(f"    -> Champ texte: {new_path}")
                        if isinstance(value, (dict, list)) and depth < 4:
                            self.search_mono_data(value, name, source_file, path_id, new_path, depth + 1)
                    except:
                        continue
            elif isinstance(data, list) and depth < 4:
                for i, item in enumerate(data[:100]):
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
                if len(content) > 10 and (self.contains_dialogue_pattern(content) or 
                                         self.is_potential_game_text(content)):
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
            r'".*?"',
            r'[A-Z][a-z]+\s*:\s*[A-Z]',
            r'[.!?]\s*',
        ]
        return any(re.search(pattern, content, re.IGNORECASE) for pattern in dialogue_patterns)
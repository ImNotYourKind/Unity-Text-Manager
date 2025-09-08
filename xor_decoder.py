#!/usr/bin/env python3
"""
Détecteur et décodeur XOR pour fichiers obfusqués
Détecte automatiquement les fichiers chiffrés par XOR et les décode
"""

import os
import re
from pathlib import Path
from typing import Optional, List, Tuple, Dict
from collections import Counter
import json
import math


class XORDecoder:
    def __init__(self):
        """Initialise le décodeur XOR avec les clés communes"""
        # Clés XOR communes trouvées dans les jeux
        self.common_xor_keys = [
            0xAA,  # 170 - clé mentionnée par l'utilisateur
            0x55,  # 85
            0xFF,  # 255
            0x00,  # 0 (pas de chiffrement)
            0x42,  # 66
            0x69,  # 105
            0x77,  # 119
            0x88,  # 136
            0xCC,  # 204
            0x33,  # 51
        ]
        
        # Signatures pour détecter les fichiers texte décodés
        self.text_signatures = [
            # SRT patterns
            rb'\d{1,3}\r?\n\d{2}:\d{2}:\d{2}[,\.]\d{3}',  # Numéro de sous-titre + timestamp
            rb'\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,\.]\d{3}',  # Timestamp SRT
            
            # JSON patterns
            rb'\{\s*"[^"]+"\s*:\s*"[^"]*"',
            rb'\[\s*\{\s*"[^"]+"\s*:',
            
            # XML patterns
            rb'<\?xml\s+version=',
            rb'<[a-zA-Z][^>]*>.*?</[a-zA-Z][^>]*>',
            
            # Dialogue patterns
            rb'"[A-Za-z][^"]{10,100}"',
            rb'[A-Z][a-z]+\s*:\s*[A-Z][^.!?]*[.!?]',
            
            # Common text patterns
            rb'[A-Za-z]{3,}\s+[A-Za-z]{3,}\s+[A-Za-z]{3,}',  # Multiple words
            rb'[.!?]\s*[A-Z][a-z]',  # Sentence endings
        ]
    
    def calculate_entropy(self, data: bytes) -> float:
        """Calcule l'entropie de Shannon des données"""
        if len(data) == 0:
            return 0
        
        counter = Counter(data)
        entropy = 0
        for count in counter.values():
            p = count / len(data)
            entropy -= p * math.log2(p)
        
        return entropy
    
    def detect_xor_obfuscation(self, file_path: Path) -> Optional[int]:
        """
        Détecte si un fichier est obfusqué par XOR et retourne la clé
        Returns: XOR key if detected, None otherwise
        """
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            
            if len(data) < 100:  # Trop petit pour être analysé
                return None
            
            # Vérifier l'entropie - les fichiers XOR ont souvent une entropie élevée
            entropy = self.calculate_entropy(data[:1000])  # Analyser les premiers 1000 bytes
            
            # Si l'entropie est très faible, le fichier n'est probablement pas chiffré
            if entropy < 4.0:
                return None
            
            print(f"[XOR] Analyse de {file_path.name} - Entropie: {entropy:.2f}")
            
            # Tester chaque clé XOR commune
            for key in self.common_xor_keys:
                if self.test_xor_key(data, key):
                    print(f"[XOR] ✅ Clé XOR détectée: 0x{key:02X} ({key})")
                    return key
            
            # Si aucune clé commune ne fonctionne, essayer une recherche exhaustive sur les premiers bytes
            print(f"[XOR] Recherche exhaustive de clé...")
            key = self.brute_force_xor_key(data[:2000])  # Analyser les premiers 2000 bytes
            if key is not None:
                print(f"[XOR] ✅ Clé XOR trouvée par bruteforce: 0x{key:02X} ({key})")
                return key
            
            print(f"[XOR] ❌ Aucune clé XOR trouvée")
            return None
            
        except Exception as e:
            print(f"[XOR] Erreur lors de la détection: {e}")
            return None
    
    def test_xor_key(self, data: bytes, key: int) -> bool:
        """Test si une clé XOR produit du texte valide"""
        try:
            # Décoder une partie des données
            sample_size = min(3000, len(data))  # Plus d'échantillon
            decoded = self.xor_decode(data[:sample_size], key)
            
            # Vérifier si le résultat contient des patterns de texte
            pattern_matches = 0
            for pattern in self.text_signatures:
                if re.search(pattern, decoded, re.IGNORECASE | re.MULTILINE):
                    pattern_matches += 1
            
            # Vérifier la présence de caractères ASCII lisibles
            printable_chars = sum(1 for b in decoded if 32 <= b <= 126 or b in [9, 10, 13])
            printable_ratio = printable_chars / len(decoded)
            
            # Vérifier spécifiquement les patterns SRT (plus permissif)
            srt_indicators = [
                rb'\d{1,3}\r?\n',  # Numéro de sous-titre
                rb'\d{2}:\d{2}:\d{2}',  # Timestamp
                rb'-->',  # Séparateur SRT
                rb'\n\d+\n',  # Numéro de ligne
                rb'[\r\n]{2,}',  # Doubles sauts de ligne
            ]
            srt_matches = sum(1 for pattern in srt_indicators if re.search(pattern, decoded))
            
            # Critères de validation plus permissifs
            has_readable_text = printable_ratio > 0.6  # Seuil abaissé
            has_srt_structure = srt_matches >= 2
            has_general_patterns = pattern_matches >= 1
            
            is_valid = (has_readable_text and (has_srt_structure or has_general_patterns))
            
            if is_valid:
                print(f"[XOR] Clé 0x{key:02X}: {pattern_matches} patterns, {printable_ratio:.2f} ASCII, {srt_matches} SRT")
            
            return is_valid
            
        except Exception:
            return False
    
    def brute_force_xor_key(self, data: bytes) -> Optional[int]:
        """Recherche exhaustive de la clé XOR (0-255)"""
        best_key = None
        best_score = 0
        
        for key in range(1, 256):  # Éviter 0 (pas de chiffrement)
            try:
                decoded = self.xor_decode(data, key)
                score = self.score_decoded_text(decoded)
                
                if score > best_score:
                    best_score = score
                    best_key = key
                    
            except Exception:
                continue
        
        # Retourner la clé seulement si le score est suffisant
        return best_key if best_score > 10 else None
    
    def score_decoded_text(self, data: bytes) -> float:
        """Score la qualité du texte décodé"""
        if len(data) == 0:
            return 0
        
        score = 0
        
        # Score basé sur les caractères ASCII lisibles
        printable_chars = sum(1 for b in data if 32 <= b <= 126 or b in [9, 10, 13])
        printable_ratio = printable_chars / len(data)
        score += printable_ratio * 10  # Max 10 points
        
        # Score basé sur les patterns trouvés
        pattern_matches = 0
        for pattern in self.text_signatures[:5]:  # Tester seulement les premiers patterns
            if re.search(pattern, data, re.IGNORECASE):
                pattern_matches += 1
        score += pattern_matches * 5  # 5 points par pattern
        
        # Bonus pour les mots en anglais courants
        common_words = [b'the', b'and', b'you', b'are', b'for', b'with', b'have', b'this', b'that']
        word_matches = sum(1 for word in common_words if word in data.lower())
        score += word_matches * 2
        
        return score
    
    def xor_decode(self, data: bytes, key: int) -> bytes:
        """Décode les données avec la clé XOR"""
        return bytes(b ^ key for b in data)
    
    def decode_file(self, file_path: Path, xor_key: int) -> Optional[bytes]:
        """Décode complètement un fichier avec la clé XOR"""
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            
            decoded = self.xor_decode(data, xor_key)
            return decoded
            
        except Exception as e:
            print(f"[XOR] Erreur lors du décodage de {file_path}: {e}")
            return None
    
    def is_likely_obfuscated(self, file_path: Path) -> bool:
        """Détermine rapidement si un fichier est probablement obfusqué (CONSERVATEUR)"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(1024)
            
            if len(header) < 50:
                return False
            
            # Pour les fichiers .srt, vérifier d'abord s'ils sont CLAIREMENT lisibles
            if file_path.suffix.lower() in ['.srt', '.txt']:
                # Vérifier si c'est un SRT normal et lisible
                has_clear_srt_patterns = any([
                    b'-->' in header,
                    re.search(rb'\d{2}:\d{2}:\d{2}[,\.]\d{3}', header),
                    re.search(rb'\d+\s*\r?\n\d{2}:\d{2}:', header)
                ])
                
                if has_clear_srt_patterns:
                    # Vérifier le ratio de caractères lisibles
                    printable_chars = sum(1 for b in header if 32 <= b <= 126 or b in [9, 10, 13])
                    printable_ratio = printable_chars / len(header)
                    
                    # Si beaucoup de caractères lisibles, c'est probablement un SRT normal
                    if printable_ratio > 0.8:
                        return False
                
                # Critères plus stricts pour considérer un fichier comme obfusqué
                printable_chars = sum(1 for b in header if 32 <= b <= 126 or b in [9, 10, 13])
                printable_ratio = printable_chars / len(header)
                entropy = self.calculate_entropy(header)
                
                # TRÈS strict : doit avoir une faible lisibilité ET haute entropie
                return printable_ratio < 0.4 and entropy > 6.0
            
            # Pour les autres fichiers, logique conservatrice
            entropy = self.calculate_entropy(header)
            printable_chars = sum(1 for b in header if 32 <= b <= 126)
            printable_ratio = printable_chars / len(header)
            
            return entropy > 7.0 and printable_ratio < 0.2  # Seuils plus stricts
            
        except Exception:
            return False
    
    def save_decoded_temp(self, file_path: Path, decoded_data: bytes, xor_key: int) -> Path:
        """Sauvegarde temporairement un fichier décodé"""
        temp_dir = file_path.parent / "decoded_temp"
        temp_dir.mkdir(exist_ok=True)
        
        temp_file = temp_dir / f"{file_path.stem}_decoded_0x{xor_key:02X}{file_path.suffix}"
        
        try:
            with open(temp_file, 'wb') as f:
                f.write(decoded_data)
            return temp_file
        except Exception as e:
            print(f"[XOR] Erreur lors de la sauvegarde temporaire: {e}")
            return None
    
    def analyze_decoded_content(self, decoded_data: bytes, original_path: Path) -> Dict:
        """Analyse le contenu décodé et retourne les informations"""
        try:
            # Essayer de décoder en UTF-8
            try:
                text_content = decoded_data.decode('utf-8', errors='ignore')
            except:
                text_content = decoded_data.decode('latin-1', errors='ignore')
            
            # Analyser le type de contenu
            content_type = "unknown"
            if re.search(r'\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->', text_content):
                content_type = "srt"
            elif text_content.strip().startswith('{') or text_content.strip().startswith('['):
                content_type = "json"
            elif text_content.strip().startswith('<'):
                content_type = "xml"
            elif any(word in text_content.lower() for word in ['dialogue', 'subtitle', 'text', 'message']):
                content_type = "dialogue"
            
            return {
                'content_type': content_type,
                'text_content': text_content,
                'size': len(decoded_data),
                'lines': text_content.count('\n') + 1 if text_content else 0,
                'original_path': str(original_path)
            }
            
        except Exception as e:
            print(f"[XOR] Erreur lors de l'analyse du contenu: {e}")
            return None


# Instance globale pour utilisation dans le scanner
xor_decoder = XORDecoder()

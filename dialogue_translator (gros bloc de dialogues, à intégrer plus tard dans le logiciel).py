#!/usr/bin/env python3
"""
Traducteur de dialogues de jeux vidéo - Version simplifiée et robuste
Format: TXT_ID,timestamp1,timestamp2,duration,chinese_simplified,chinese_traditional,english
"""

import re
import json
import time
import sys
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from openai import OpenAI

@dataclass
class DialogueLine:
    """Représente une ligne de dialogue"""
    raw_line: str
    txt_id: str = ""
    timestamp1: str = ""
    timestamp2: str = ""
    duration: str = ""
    chinese_simplified: str = ""
    chinese_traditional: str = ""
    english: str = ""
    french: str = ""
    
    def has_english(self) -> bool:
        """Vérifie si la ligne a du texte anglais à traduire"""
        return bool(self.english and self.english.strip())
    
    def to_output_line(self) -> str:
        """Reconstitue la ligne avec la traduction française"""
        if self.french and self.french.strip():
            # Remplacer l'anglais par le français
            return f"{self.txt_id},{self.timestamp1},{self.timestamp2},{self.duration},{self.chinese_simplified},{self.chinese_traditional},{self.french}"
        else:
            # Garder la ligne originale
            return self.raw_line

class SimpleDialogueTranslator:
    """Traducteur simplifié pour les dialogues de jeux vidéo"""
    
    def __init__(self, api_key: str):
        """Initialise le traducteur"""
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"
        self.translation_cache = {}
        self.failed_lines = []
        
    def parse_dialogue_line(self, line: str) -> Optional[DialogueLine]:
        """Parse une ligne de dialogue de manière robuste"""
        line = line.strip()
        if not line:
            return None
            
        # Créer l'objet avec la ligne brute
        dialogue = DialogueLine(raw_line=line)
        
        # Essayer de splitter par virgule (format CSV simple)
        parts = line.split(',')
        
        # On s'attend à au moins 7 parties
        if len(parts) >= 7:
            try:
                dialogue.txt_id = parts[0]
                dialogue.timestamp1 = parts[1]
                dialogue.timestamp2 = parts[2]
                dialogue.duration = parts[3]
                dialogue.chinese_simplified = parts[4]
                dialogue.chinese_traditional = parts[5]
                # L'anglais peut contenir des virgules, donc on prend tout le reste
                dialogue.english = ','.join(parts[6:])
                return dialogue
            except Exception as e:
                print(f"Erreur parsing ligne: {e}")
                return None
        else:
            print(f"Format invalide (attendu 7+ parties, trouvé {len(parts)}): {line[:100]}...")
            return None
    
    def parse_file(self, content: str) -> List[DialogueLine]:
        """Parse le fichier complet"""
        lines = content.strip().split('\n')
        dialogues = []
        
        print(f"\n=== Parsing de {len(lines)} lignes ===")
        
        for i, line in enumerate(lines):
            dialogue = self.parse_dialogue_line(line)
            if dialogue:
                dialogues.append(dialogue)
                if dialogue.has_english():
                    print(f"  Ligne {i+1}: OK - '{dialogue.english[:50]}...'")
            else:
                if line.strip():  # Ignorer les lignes vides
                    print(f"  Ligne {i+1}: SKIP - Format non reconnu")
        
        print(f"\n=== Résultat: {len(dialogues)} dialogues valides ===")
        return dialogues
    
    def translate_text(self, english_text: str, chinese_ref: str = "", context: str = "") -> str:
        """Traduit un texte en français"""
        # Vérifier le cache
        cache_key = f"{english_text}|{chinese_ref}"
        if cache_key in self.translation_cache:
            return self.translation_cache[cache_key]
        
        try:
            # Prompt simple et efficace
            system_prompt = """Tu es un traducteur expert pour jeux vidéo.
Tu traduis de l'anglais vers le français moderne et décontracté.

RÈGLES STRICTES:
1. TOUJOURS utiliser le TUTOIEMENT (tu/ton/te)
2. Style MODERNE pour 20-30 ans
3. Garder l'ÉMOTION et le TON
4. Français NATUREL et FLUIDE
5. Si tu as une référence chinoise, l'utiliser pour comprendre le vrai sens

Réponds UNIQUEMENT avec la traduction française, rien d'autre."""

            user_prompt = f"Texte anglais: {english_text}"
            if chinese_ref:
                user_prompt += f"\nRéférence chinoise: {chinese_ref}"
            if context:
                user_prompt += f"\nContexte: {context}"
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            translation = response.choices[0].message.content.strip()
            
            # Nettoyer les préfixes éventuels
            for prefix in ["Traduction:", "Traduction :", "French:", "Français:"]:
                if translation.lower().startswith(prefix.lower()):
                    translation = translation[len(prefix):].strip()
            
            # Validation basique
            if not translation or len(translation) < 2:
                print(f"  ⚠️ Traduction vide pour: {english_text[:50]}...")
                return english_text
            
            # Mettre en cache
            self.translation_cache[cache_key] = translation
            
            return translation
            
        except Exception as e:
            print(f"  ❌ Erreur traduction: {e}")
            self.failed_lines.append(english_text)
            return english_text
    
    def translate_file(self, content: str, batch_size: int = 5) -> str:
        """Traduit le fichier complet"""
        print("\n" + "="*60)
        print("DÉBUT DE LA TRADUCTION")
        print("="*60)
        
        # Parser le fichier
        dialogues = self.parse_file(content)
        if not dialogues:
            print("❌ Aucun dialogue trouvé")
            return content
        
        # Compter les dialogues à traduire
        to_translate = [d for d in dialogues if d.has_english()]
        print(f"\n📊 Statistiques:")
        print(f"  - Total de lignes: {len(dialogues)}")
        print(f"  - À traduire: {len(to_translate)}")
        
        if not to_translate:
            print("❌ Aucun dialogue avec texte anglais")
            return content
        
        # Traduire par batch pour éviter les problèmes
        print(f"\n🔄 Traduction en cours (par batch de {batch_size})...")
        
        translated_count = 0
        error_count = 0
        
        for i, dialogue in enumerate(to_translate):
            try:
                # Afficher la progression
                progress = ((i + 1) / len(to_translate)) * 100
                print(f"\n[{progress:.1f}%] Dialogue {i+1}/{len(to_translate)}")
                print(f"  EN: {dialogue.english[:80]}...")
                
                # Traduire
                chinese_ref = dialogue.chinese_simplified or dialogue.chinese_traditional
                translation = self.translate_text(
                    dialogue.english,
                    chinese_ref,
                    f"Dialogue ID: {dialogue.txt_id}"
                )
                
                if translation and translation != dialogue.english:
                    dialogue.french = translation
                    translated_count += 1
                    print(f"  FR: {translation[:80]}...")
                    print(f"  ✅ Traduit avec succès")
                else:
                    error_count += 1
                    print(f"  ⚠️ Pas de traduction")
                
                # Pause pour respecter les limites API
                if (i + 1) % batch_size == 0:
                    print(f"\n⏸️  Pause de 2 secondes (respect limites API)...")
                    time.sleep(2)
                else:
                    time.sleep(0.5)  # Petite pause entre chaque traduction
                    
            except Exception as e:
                error_count += 1
                print(f"  ❌ Erreur: {e}")
                continue
        
        # Reconstituer le fichier
        print(f"\n📝 Reconstitution du fichier...")
        output_lines = []
        for dialogue in dialogues:
            output_lines.append(dialogue.to_output_line())
        
        result = '\n'.join(output_lines)
        
        # Résumé final
        print("\n" + "="*60)
        print("TRADUCTION TERMINÉE")
        print("="*60)
        print(f"✅ Succès: {translated_count}/{len(to_translate)}")
        print(f"❌ Échecs: {error_count}")
        
        if self.failed_lines:
            print(f"\n⚠️ {len(self.failed_lines)} lignes ont échoué:")
            for line in self.failed_lines[:5]:
                print(f"  - {line[:60]}...")
        
        return result
    
    def save_cache(self, filepath: str = "translation_cache.json"):
        """Sauvegarde le cache de traductions"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    'cache': self.translation_cache,
                    'failed': self.failed_lines
                }, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Cache sauvegardé: {filepath}")
        except Exception as e:
            print(f"❌ Erreur sauvegarde cache: {e}")
    
    def load_cache(self, filepath: str = "translation_cache.json"):
        """Charge le cache de traductions"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.translation_cache = data.get('cache', {})
                self.failed_lines = data.get('failed', [])
            print(f"💾 Cache chargé: {len(self.translation_cache)} traductions")
        except FileNotFoundError:
            print("📭 Pas de cache existant")
        except Exception as e:
            print(f"❌ Erreur chargement cache: {e}")

def main():
    """Fonction principale"""
    if len(sys.argv) < 3:
        print("Usage: python game_dialogue_translator.py <input_file> <api_key>")
        print("Exemple: python game_dialogue_translator.py dialogues.txt sk-xxxxx")
        return
    
    input_file = sys.argv[1]
    api_key = sys.argv[2]
    
    print(f"\n🎮 Traducteur de Dialogues de Jeux Vidéo")
    print(f"📄 Fichier: {input_file}")
    
    try:
        # Lire le fichier
        print(f"\n📖 Lecture du fichier...")
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"✅ Fichier lu: {len(content)} caractères")
        
        # Créer le traducteur
        translator = SimpleDialogueTranslator(api_key)
        
        # Charger le cache si disponible
        translator.load_cache()
        
        # Traduire
        translated_content = translator.translate_file(content)
        
        # Sauvegarder le résultat
        output_file = input_file.replace('.txt', '_translated.txt')
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(translated_content)
        
        print(f"\n✅ Fichier traduit sauvegardé: {output_file}")
        
        # Sauvegarder le cache
        translator.save_cache()
        
    except FileNotFoundError:
        print(f"❌ Fichier non trouvé: {input_file}")
    except Exception as e:
        print(f"❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

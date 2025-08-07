# openai_translator.py
"""
Module pour la traduction automatique utilisant l'API OpenAI.
Version corrigée avec sécurité améliorée et gestion d'erreurs robuste.
"""

import os
import json
import re
import time
from datetime import datetime
from typing import List, Dict, Optional, Callable

# Modules pour la traduction OpenAI (optionnels)
try:
    import openai
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("OpenAI non disponible. Fonctionnalités de traduction automatique désactivées.")

# Modules pour la détection de langue (optionnels)
try:
    from langdetect import detect, LangDetectException
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False
    print("langdetect non disponible. Détection de langue basique utilisée.")


class OpenAITranslator:
    """Système de traduction utilisant l'API OpenAI avec analyse contextuelle"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.client = None
        self.translation_cache = {}
        self.context_cache = {}
        self.model = "gpt-4o-mini"
        self.max_retries = 3
        self.rate_limit_delay = 0.1  # Délai entre les requêtes
        
        if OPENAI_AVAILABLE:
            try:
                # Priorité : paramètre > variable d'environnement > demande utilisateur
                api_key = api_key or os.environ.get('OPENAI_API_KEY')
                
                if not api_key:
                    print("⚠️  Clé API OpenAI non trouvée.")
                    print("Définissez la variable d'environnement OPENAI_API_KEY ou")
                    print("passez la clé en paramètre au constructeur.")
                    return
                
                self.client = OpenAI(api_key=api_key)
                print("✅ Client OpenAI initialisé avec succès")
                
                # Test de validation de la clé
                self._validate_api_key()
                
            except Exception as e:
                print(f"❌ Erreur lors de l'initialisation OpenAI: {e}")
                self.client = None

    def _validate_api_key(self) -> bool:
        """Valide la clé API avec une requête test"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=5,
                timeout=10
            )
            print("✅ Clé API validée")
            return True
        except Exception as e:
            print(f"❌ Clé API invalide: {e}")
            self.client = None
            return False

    def is_available(self) -> bool:
        """Vérifie si le traducteur est disponible"""
        return self.client is not None

    def is_likely_french(self, text: str) -> bool:
        """Détecte si un texte est probablement déjà en français"""
        if not text:
            return False
            
        # Caractères accentués français
        french_chars = set('àâäéèêëïîôöùûüÿçœæÀÂÄÉÈÊËÏÎÔÖÙÛÜŸÇŒÆ')
        if any(c in french_chars for c in text):
            return True
            
        # Mots français courants
        french_words = {
            'le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'et', 'ou', 'est', 'sont',
            'avoir', 'être', 'faire', 'dire', 'aller', 'voir', 'savoir', 'pouvoir',
            'que', 'qui', 'quoi', 'où', 'quand', 'comment', 'pourquoi',
            'bonjour', 'bonsoir', 'salut', 'merci', 'svp', 'oui', 'non', 'peut-être',
            'avec', 'dans', 'pour', 'sur', 'par', 'sans', 'très', 'bien', 'mais', 'donc'
        }
        words = re.findall(r'\b\w+\b', text.lower())
        if not words:
            return False
            
        french_word_count = sum(1 for word in words if word in french_words)
        return french_word_count / len(words) > 0.2

    def detect_language(self, text: str) -> str:
        """Détecte la langue d'un texte"""
        if not text or len(text.strip()) < 3:
            return "unknown"
            
        # Vérification française d'abord
        if self.is_likely_french(text):
            return "fr"
            
        # Utiliser langdetect si disponible
        if LANGDETECT_AVAILABLE:
            try:
                return detect(text)
            except LangDetectException:
                pass
                
        # Détection basique anglais/autre
        english_words = {'the', 'and', 'or', 'is', 'are', 'you', 'i', 'me', 'my', 'your', 'this', 'that'}
        words = re.findall(r'\b\w+\b', text.lower())
        if words:
            english_count = sum(1 for word in words if word in english_words)
            if english_count / len(words) > 0.1:
                return "en"
                
        return "unknown"

    def analyze_game_context(self, texts_sample: List[Dict]) -> Dict:
        """Retourne un contexte par défaut (analyse désactivée pour optimisation)"""
        return self.get_default_context()

    def get_default_context(self) -> Dict:
        """Retourne un contexte par défaut"""
        return {
            "game_genre": "aventure",
            "tone": "décontracté", 
            "setting": "moderne",
            "target_audience": "adolescent",
            "text_type": "mixte",
            "formality": "tutoiement"
        }

    def _translate_with_retry(self, text: str, context: Dict, target_lang: str = "fr") -> str:
        """Traduit un texte avec système de retry robuste"""
        cache_key = f"{text}|{target_lang}"
        if cache_key in self.translation_cache:
            return self.translation_cache[cache_key]
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                system_prompt = self.build_translation_prompt(context, target_lang)
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Traduis: {text}"}
                    ],
                    temperature=0.2,
                    max_tokens=min(len(text) * 3, 500),
                    timeout=30
                )
                
                translated = response.choices[0].message.content.strip()
                
                if self.validate_translation(text, translated):
                    self.translation_cache[cache_key] = translated
                    return translated
                else:
                    print(f"  ⚠️ Traduction invalide (tentative {attempt + 1})")
                    
            except openai.RateLimitError as e:
                print(f"  ⏳ Limite de débit atteinte, pause de {2**attempt}s")
                time.sleep(2**attempt)
                last_error = e
                
            except openai.APITimeoutError as e:
                print(f"  ⏱️ Timeout API (tentative {attempt + 1})")
                time.sleep(1)
                last_error = e
                
            except Exception as e:
                print(f"  ❌ Erreur tentative {attempt + 1}: {e}")
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(1)
        
        print(f"  ❌ Échec définitif après {self.max_retries} tentatives: {last_error}")
        return text  # Retourner le texte original en cas d'échec

    def translate_text(self, text: str, context: Optional[Dict] = None, target_lang: str = "fr") -> str:
        """Traduit un texte avec prise en compte du contexte"""
        if not self.client:
            return text
            
        if not text or not text.strip():
            return text
            
        clean_text = text.rstrip("\n")
        
        # Traitement multi-lignes
        if "\n" in clean_text:
            return self._translate_multiline(text, context, target_lang)
        
        # Ne traduire que l'anglais
        detected_lang = self.detect_language(clean_text)
        if detected_lang != "en":
            return text
            
        # Ignorer les textes très courts ou sans lettres
        if len(clean_text) < 2 or not re.search(r'[a-zA-Z]', clean_text):
            return text
            
        if not context:
            context = self.get_default_context()
            
        print(f"🔄 Traduction: '{clean_text[:50]}{'...' if len(clean_text) > 50 else ''}'")
        
        result = self._translate_with_retry(clean_text, context, target_lang)
        
        if result != clean_text:
            print(f"  ✅ -> '{result}'")
        
        # Respecter la pause entre requêtes
        time.sleep(self.rate_limit_delay)
        
        return result

    def _translate_multiline(self, text: str, context: Optional[Dict], target_lang: str) -> str:
        """Traduit un texte multi-lignes ligne par ligne"""
        context = context or self.get_default_context()
        new_lines = []
        
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.upper() == "END":
                new_lines.append(line)
                continue
                
            lang = self.detect_language(stripped)
            if lang == "en":
                translated_line = self._translate_with_retry(stripped, context, target_lang)
                # Conserver les espaces de début/fin
                prefix = line[:len(line) - len(line.lstrip())]
                suffix = line[len(line.rstrip()):]
                new_lines.append(prefix + translated_line + suffix)
            else:
                new_lines.append(line)
        
        return "\n".join(new_lines)

    def build_translation_prompt(self, context: Dict, target_lang: str) -> str:
        """Construit le prompt de traduction selon le contexte"""
        base_prompt = (
            f"Tu es un traducteur professionnel spécialisé dans les jeux vidéo. "
            f"Traduis chaque texte suivant de l'anglais vers le {target_lang}. "
            f"Respecte impérativement le sens, le ton et l'intention, de façon naturelle et fluide.\n"
        )
        
        rules = (
            "INSTRUCTIONS:\n"
            "- Ne traduis PAS les noms propres, termes techniques ou balises.\n"
            "- Conserve la ponctuation et le formatage originaux.\n"
            "- Utilise un français naturel correspondant au même registre de langue.\n"
            "- Réponds UNIQUEMENT avec la traduction, sans explication ni balises.\n"
            "- Respecte les conventions des jeux vidéo français.\n"
        )
        
        return base_prompt + rules

    def validate_translation(self, original: str, translated: str) -> bool:
        """Valide une traduction"""
        if not translated or len(translated.strip()) == 0:
            return False
            
        # Vérifier que ce n'est pas une réponse conversationnelle
        unwanted_phrases = [
            "je ne peux pas", "désolé", "peux-tu", "il semble",
            "voici la traduction", "traduction:", "résultat", "je vais traduire"
        ]
        if any(phrase in translated.lower() for phrase in unwanted_phrases):
            return False
            
        # Vérifier que la longueur est raisonnable (pas plus de 3x l'original)
        if len(translated) > len(original) * 3:
            return False
            
        # Vérifier qu'on a bien du contenu et pas juste de la ponctuation
        if not re.search(r'[a-zA-ZÀ-ÿ]', translated):
            return False
            
        return True

    def batch_translate(
        self, 
        texts: List[Dict], 
        progress_callback: Optional[Callable] = None,
        should_stop: Optional[Callable] = None
    ) -> int:
        """Traduit une liste de textes avec possibilité d'arrêt anticipé"""
        if not self.client:
            return 0
            
        context = self.get_default_context()
        translated_count = 0
        untranslated_texts = [t for t in texts if not t.get('is_translated', False)]
        total_texts = len(untranslated_texts)
        
        print(f"🚀 Début de la traduction de {total_texts} textes")
        
        for i, text_entry in enumerate(untranslated_texts):
            if should_stop and should_stop():
                print("⏹️ Traduction interrompue par l'utilisateur")
                break
                
            if progress_callback:
                progress_callback(
                    i / total_texts * 100,
                    f"{i+1}/{total_texts} – Traduction: {text_entry.get('asset_name', 'texte')}…"
                )
            
            try:
                original_text = text_entry['original_text']
                translated_text = self.translate_text(original_text, context)
                
                if translated_text != original_text:
                    text_entry['translated_text'] = translated_text
                    text_entry['is_translated'] = True
                    translated_count += 1
                    
                    # Sauvegarder le cache périodiquement
                    if translated_count % 10 == 0:
                        self.save_cache()
                        
            except Exception as e:
                print(f"❌ Erreur lors de la traduction de '{text_entry.get('asset_name', 'inconnu')}': {e}")
                continue
        
        print(f"✅ Traduction terminée: {translated_count} textes traduits")
        return translated_count

    def save_cache(self, cache_file: str = "translation_cache.json") -> bool:
        """Sauvegarde le cache de traductions"""
        try:
            cache_data = {
                'translations': self.translation_cache,
                'contexts': self.context_cache,
                'timestamp': datetime.now().isoformat(),
                'version': '2.0'
            }
            
            # Sauvegarde atomique avec fichier temporaire
            temp_file = cache_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            # Remplacer l'ancien fichier
            if os.path.exists(cache_file):
                os.replace(temp_file, cache_file)
            else:
                os.rename(temp_file, cache_file)
                
            print(f"💾 Cache sauvegardé: {len(self.translation_cache)} entrées")
            return True
            
        except Exception as e:
            print(f"❌ Erreur lors de la sauvegarde du cache: {e}")
            # Nettoyer le fichier temporaire en cas d'erreur
            temp_file = cache_file + '.tmp'
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            return False

    def load_cache(self, cache_file: str = "translation_cache.json") -> bool:
        """Charge le cache de traductions"""
        try:
            if not os.path.exists(cache_file):
                return False
                
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                
            self.translation_cache = cache_data.get('translations', {})
            self.context_cache = cache_data.get('contexts', {})
            
            print(f"📂 Cache chargé: {len(self.translation_cache)} entrées")
            return True
            
        except Exception as e:
            print(f"❌ Erreur lors du chargement du cache: {e}")
            return False

    def get_cache_stats(self) -> Dict:
        """Retourne les statistiques du cache"""
        return {
            'translation_entries': len(self.translation_cache),
            'context_entries': len(self.context_cache),
            'total_cache_size': len(str(self.translation_cache)) + len(str(self.context_cache))
        }

    def clear_cache(self) -> None:
        """Vide le cache"""
        self.translation_cache.clear()
        self.context_cache.clear()
        print("🧹 Cache vidé")
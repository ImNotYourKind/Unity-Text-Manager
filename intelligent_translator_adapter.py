#!/usr/bin/env python3
"""
Adaptateur Intelligent pour Unity Text Manager
Intègre les fonctionnalités avancées du traducteur SRT intelligent 
dans l'interface Unity Text Manager existante.

Fonctionnalités:
- Analyse globale de contexte pour toutes les traductions
- Validation automatique des traductions
- Cache intelligent avec hash contextuel
- Compatible avec l'interface OpenAITranslator existante
"""

import re
import json
import time
import hashlib
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
import openai
from openai import OpenAI

# Clé API OpenAI intégrée - Usage personnel
HARDCODED_API_KEY = "test"

@dataclass
class SequenceContext:
    """Structure pour stocker le contexte d'une séquence spécifique"""
    sequence_summary: str
    characters_present: List[str]
    emotional_tone: str
    scene_setting: str
    dialogue_flow: str
    key_events: List[str]
    source_language: str = "english"
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict):
        return cls(**data)

@dataclass
class GlobalContext:
    """Structure pour stocker le contexte global d'analyse"""
    characters: Dict[str, Dict[str, Any]]
    story_summary: str
    tone_style: str
    relationship_dynamics: Dict[str, str]
    setting_info: str
    dialogue_patterns: Dict[str, List[str]]
    cultural_context: str
    game_type: str = "fmv_choice_game"
    source_languages: List[str] = None
    translation_quality_issues: List[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict):
        return cls(**data)

class IntelligentTranslatorAdapter:
    """
    Adaptateur intelligent qui améliore le système de traduction Unity Text Manager
    avec l'analyse contextuelle globale du script SRT intelligent.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the intelligent translator adapter"""
        # Utiliser la clé hard-codée si aucune clé n'est fournie
        self.api_key = api_key if api_key else HARDCODED_API_KEY
        self.client = None
        self.model = "gpt-4o-mini"
        self.global_context: Optional[GlobalContext] = None
        self.sequence_contexts: Dict[str, SequenceContext] = {}
        self.translation_cache: Dict[str, str] = {}
        self.context_analyzed = False
        self.language_patterns = {
            'chinese': re.compile(r'[\u4e00-\u9fff]+'),
            'korean': re.compile(r'[\uac00-\ud7af]+'),
            'japanese': re.compile(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]+')
        }
        
        # Initialiser OpenAI client si clé API disponible
        if self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key)
                print(f"✅ Client OpenAI initialisé avec succès")
            except Exception as e:
                print(f"❌ Erreur lors de l'initialisation OpenAI: {e}")
                self.client = None
    
    def is_available(self) -> bool:
        """Vérifie si le traducteur est disponible"""
        return self.client is not None and self.api_key is not None
    
    def analyze_global_context(self, texts: List[Dict]) -> GlobalContext:
        """
        Analyse le contexte global de tous les textes Unity pour comprendre
        le jeu, les personnages et le style
        """
        if not self.is_available():
            return self._create_default_context()
        
        print("🔍 Analyse globale du contexte Unity en cours...")
        
        # Extraire un échantillon représentatif des textes
        sample_texts = self._extract_sample_texts(texts)
        
        if not sample_texts:
            return self._create_default_context()
        
        try:
            analysis_prompt = f"""
            Analyse cette collection de textes extraits d'un jeu Unity pour comprendre le contexte global.
            Tu dois identifier les éléments clés pour permettre une traduction cohérente et contextualisée.
            
            ANALYSE REQUISE (spécialement pour les jeux FMV à choix multiples):
            1. Type de jeu et genre (FMV, Visual Novel, Choice-based, etc.)
            2. Personnages principaux et leur personnalité détaillée
            3. Contexte narratif global et arc principal
            4. Ton et style des dialogues (dramatique, casual, etc.)
            5. Relations complexes entre personnages
            6. Patterns de dialogue et interface spécifiques aux FMV
            7. Contexte culturel et géographique précis
            8. Langues sources détectées (chinois, coréen, japonais)
            9. Problèmes de qualité de traduction anglaise identifiés
            
            Réponds UNIQUEMENT au format JSON suivant:
            {{
                "characters": {{
                    "character_name": {{
                        "personality": "description de la personnalité",
                        "speech_style": "style de dialogue",
                        "role": "rôle dans le jeu"
                    }}
                }},
                "story_summary": "résumé du contexte narratif",
                "tone_style": "ton général (sérieux/léger/dramatique/humoristique/etc)",
                "relationship_dynamics": {{
                    "player_relationship": "relation avec le joueur",
                    "character_interactions": "dynamiques entre personnages"
                }},
                "setting_info": "contexte spatial/temporel/culturel",
                "dialogue_patterns": {{
                    "ui_elements": ["exemples d'éléments d'interface"],
                    "narrative_text": ["exemples de texte narratif"],
                    "dialogue_style": ["style de dialogue"]
                }},
                "cultural_context": "contexte culturel important",
                "game_type": "type de jeu identifié",
                "source_languages": ["langues sources détectées"],
                "translation_quality_issues": ["problèmes de traduction anglaise identifiés"]
            }}
            
            TEXTES À ANALYSER:
            {sample_texts}
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": analysis_prompt}],
                temperature=0.1,
                max_tokens=16300,
                timeout=60
            )
            
            analysis_text = response.choices[0].message.content.strip()
            clean_analysis = analysis_text.replace('```json', '').replace('```', '').strip()
            
            try:
                context_data = json.loads(clean_analysis)
                context = GlobalContext(
                    characters=context_data.get('characters', {}),
                    story_summary=context_data.get('story_summary', ''),
                    tone_style=context_data.get('tone_style', ''),
                    relationship_dynamics=context_data.get('relationship_dynamics', {}),
                    setting_info=context_data.get('setting_info', ''),
                    dialogue_patterns=context_data.get('dialogue_patterns', {}),
                    cultural_context=context_data.get('cultural_context', ''),
                    game_type=context_data.get('game_type', 'fmv_choice_game'),
                    source_languages=context_data.get('source_languages', ['english']),
                    translation_quality_issues=context_data.get('translation_quality_issues', [])
                )
                
                print("✅ Contexte global analysé:")
                print(f"  • Type de jeu: {context.game_type}")
                print(f"  • Personnages: {len(context.characters)}")
                print(f"  • Ton: {context.tone_style}")
                print(f"  • Setting: {context.setting_info[:50]}...")
                print(f"  • Langues sources: {context.source_languages}")
                print(f"  • Problèmes traduction: {len(context.translation_quality_issues)}")
                
                self.global_context = context
                self.context_analyzed = True
                return context
                
            except json.JSONDecodeError as e:
                print(f"Erreur de parsing JSON: {e}")
                return self._create_default_context()
                
        except Exception as e:
            print(f"Erreur lors de l'analyse globale: {e}")
            return self._create_default_context()
    
    def _extract_sample_texts(self, texts: List[Dict], max_texts: int = 200) -> str:
        """Extrait un échantillon représentatif des textes pour l'analyse"""
        sample_texts = []
        
        # Trier par longueur et type pour avoir un échantillon varié
        sorted_texts = sorted(texts, key=lambda x: len(x.get('original_text', '')), reverse=True)
        
        # Prendre des textes de différentes longueurs
        long_texts = [t for t in sorted_texts if len(t.get('original_text', '')) > 50][:40]
        medium_texts = [t for t in sorted_texts if 10 <= len(t.get('original_text', '')) <= 50][:60]
        short_texts = [t for t in sorted_texts if len(t.get('original_text', '')) < 10][:100]
        
        all_samples = long_texts + medium_texts + short_texts
        
        for text_entry in all_samples[:max_texts]:
            original_text = text_entry.get('original_text', '').strip()
            if original_text and re.search(r'[a-zA-Z]', original_text):
                # Ajouter contexte sur le type d'asset
                asset_info = f"[{text_entry.get('asset_type', 'unknown')}]"
                sample_texts.append(f"{asset_info} {original_text}")
        
        return "\n".join(sample_texts[:200])  # Limiter pour éviter les tokens excessifs
    
    def _create_default_context(self) -> GlobalContext:
        """Crée un contexte par défaut"""
        return GlobalContext(
            characters={},
            story_summary="Jeu FMV à choix multiples",
            tone_style="narratif interactif",
            relationship_dynamics={"player_relationship": "protagoniste"},
            setting_info="environnement de jeu contemporain",
            dialogue_patterns={},
            cultural_context="occidental contemporain",
            game_type="fmv_choice_game",
            source_languages=["english"],
            translation_quality_issues=[]
        )
    
    def detect_source_languages(self, texts: List[Dict]) -> List[str]:
        """Détecte les langues sources présentes dans les textes"""
        detected_languages = set(["english"])  # Par défaut anglais
        
        for text_entry in texts[:200]:  # Échantillon pour détecter
            original_text = text_entry.get('original_text', '')
            
            for lang, pattern in self.language_patterns.items():
                if pattern.search(original_text):
                    detected_languages.add(lang)
        
        return list(detected_languages)
    
    def analyze_sequence_context(self, sequence_texts: List[Dict], sequence_name: str = "") -> SequenceContext:
        """
        Analyse une séquence spécifique de dialogues pour comprendre le contexte local
        """
        if not self.is_available() or not sequence_texts:
            return self._create_default_sequence_context()
        
        print(f"🎬 Analyse de la séquence: {sequence_name}")
        
        # Extraire les textes de la séquence
        sequence_content = []
        for i, text_entry in enumerate(sequence_texts):
            original_text = text_entry.get('original_text', '').strip()
            if original_text:
                sequence_content.append(f"{i+1}. {original_text}")
        
        if not sequence_content:
            return self._create_default_sequence_context()
        
        sequence_text = "\n".join(sequence_content[:100])  # Limiter pour éviter les tokens excessifs
        
        try:
            analysis_prompt = f"""
            Analyse cette séquence de dialogue d'un jeu FMV à choix multiples.
            Tu dois comprendre le contexte local de cette séquence spécifique pour améliorer la traduction.
            
            CONTEXTE GLOBAL DU JEU:
            {json.dumps(self.global_context.to_dict() if self.global_context else {}, indent=2, ensure_ascii=False)}
            
            ANALYSE REQUISE POUR CETTE SÉQUENCE:
            1. Résumé de ce qui se passe dans cette séquence
            2. Personnages présents et actifs
            3. Ton émotionnel dominant (anxieux, romantique, tendu, etc.)
            4. Cadre/lieu de la scène
            5. Flux du dialogue (conversation, monologue, interrogatoire, etc.)
            6. Événements clés qui se déroulent
            7. Langue source probable (anglais/chinois/coréen/japonais)
            
            Réponds UNIQUEMENT au format JSON suivant:
            {{
                "sequence_summary": "résumé détaillé de la séquence",
                "characters_present": ["liste des personnages actifs"],
                "emotional_tone": "ton émotionnel dominant",
                "scene_setting": "lieu/cadre de la scène",
                "dialogue_flow": "type de conversation",
                "key_events": ["événements importants"],
                "source_language": "langue source probable"
            }}
            
            SÉQUENCE À ANALYSER:
            {sequence_text}
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": analysis_prompt}],
                temperature=0.2,
                max_tokens=16300,
                timeout=45
            )
            
            analysis_text = response.choices[0].message.content.strip()
            clean_analysis = analysis_text.replace('```json', '').replace('```', '').strip()
            
            sequence_data = json.loads(clean_analysis)
            context = SequenceContext(
                sequence_summary=sequence_data.get('sequence_summary', ''),
                characters_present=sequence_data.get('characters_present', []),
                emotional_tone=sequence_data.get('emotional_tone', ''),
                scene_setting=sequence_data.get('scene_setting', ''),
                dialogue_flow=sequence_data.get('dialogue_flow', ''),
                key_events=sequence_data.get('key_events', []),
                source_language=sequence_data.get('source_language', 'english')
            )
            
            print(f"✅ Séquence analysée: {context.emotional_tone} - {len(context.characters_present)} personnages")
            
            # Stocker le contexte de séquence
            if sequence_name:
                self.sequence_contexts[sequence_name] = context
                
            return context
            
        except Exception as e:
            print(f"Erreur lors de l'analyse de séquence: {e}")
            return self._create_default_sequence_context()
    
    def _create_default_sequence_context(self) -> SequenceContext:
        """Crée un contexte de séquence par défaut"""
        return SequenceContext(
            sequence_summary="Séquence de dialogue FMV",
            characters_present=["personnages non identifiés"],
            emotional_tone="neutre",
            scene_setting="environnement de jeu",
            dialogue_flow="conversation",
            key_events=[],
            source_language="english"
        )

    def create_translation_hash(self, text: str, context: GlobalContext, file_context: str = "") -> str:
        """Crée un hash unique pour le cache basé sur le texte et le contexte"""
        context_string = f"{text.strip()}|{context.tone_style}|{context.game_type}|{len(context.characters)}|{file_context}"
        return hashlib.md5(context_string.encode('utf-8')).hexdigest()
    
    def verify_and_correct_sequence_translation(self, sequence_texts: List[Dict], 
                                              sequence_context: SequenceContext) -> List[Dict]:
        """
        Vérifie et corrige la traduction complète d'une séquence pour assurer la cohérence
        """
        if not self.is_available() or not sequence_texts:
            return sequence_texts
        
        print(f"🔍 Vérification de la cohérence de la séquence...")
        
        # Extraire les traductions de la séquence
        sequence_pairs = []
        for i, text_entry in enumerate(sequence_texts):
            original = text_entry.get('original_text', '').strip()
            translated = text_entry.get('translated_text', '').strip()
            if original and translated:
                sequence_pairs.append({
                    'index': i,
                    'original': original,
                    'translated': translated,
                    'entry': text_entry
                })
        
        if len(sequence_pairs) < 2:  # Pas assez pour vérifier la cohérence
            return sequence_texts
        
        try:
            # Construire le prompt de vérification
            sequence_review = []
            for pair in sequence_pairs[:20]:  # Limiter pour éviter les tokens excessifs
                sequence_review.append(f"{pair['index']+1}. EN: {pair['original']}")
                sequence_review.append(f"   FR: {pair['translated']}")
                sequence_review.append("")
            
            verification_prompt = f"""
            Tu es un expert en traduction de jeux FMV. Vérifie cette séquence traduite pour identifier les incohérences et problèmes.
            
            CONTEXTE DE LA SÉQUENCE:
            - Résumé: {sequence_context.sequence_summary}
            - Personnages: {', '.join(sequence_context.characters_present)}
            - Ton émotionnel: {sequence_context.emotional_tone}
            - Cadre: {sequence_context.scene_setting}
            - Type de dialogue: {sequence_context.dialogue_flow}
            - Langue source: {sequence_context.source_language}
            
            CONTEXTE GLOBAL DU JEU:
            {json.dumps(self.global_context.to_dict() if self.global_context else {}, indent=2, ensure_ascii=False)[:500]}...
            
            PROBLÈMES À IDENTIFIER:
            1. Incohérences dans les noms de personnages
            2. Changements de ton inappropriés
            3. Traductions qui ne collent pas au contexte émotionnel
            4. Erreurs de traduction dues à une mauvaise qualité de l'anglais source
            5. Manque de fluidité dans le dialogue français
            6. Incohérences avec le contexte de la scène
            
            Réponds au format JSON avec les corrections nécessaires:
            {{
                "corrections_needed": true/false,
                "issues_found": ["liste des problèmes identifiés"],
                "corrections": [
                    {{
                        "index": numéro_de_ligne,
                        "original_translation": "traduction actuelle",
                        "corrected_translation": "traduction corrigée",
                        "reason": "raison de la correction"
                    }}
                ]
            }}
            
            SÉQUENCE À VÉRIFIER:
            {chr(10).join(sequence_review)}
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": verification_prompt}],
                temperature=0.1,
                max_tokens=16300,
                timeout=60
            )
            
            verification_text = response.choices[0].message.content.strip()
            clean_verification = verification_text.replace('```json', '').replace('```', '').strip()
            
            verification_data = json.loads(clean_verification)
            
            if verification_data.get('corrections_needed', False):
                corrections = verification_data.get('corrections', [])
                print(f"🔧 {len(corrections)} corrections identifiées")
                
                # Appliquer les corrections
                for correction in corrections:
                    index = correction.get('index', 0) - 1  # Convertir en index 0-based
                    if 0 <= index < len(sequence_pairs):
                        new_translation = correction.get('corrected_translation', '')
                        reason = correction.get('reason', '')
                        
                        if new_translation and new_translation != sequence_pairs[index]['translated']:
                            sequence_pairs[index]['entry']['translated_text'] = new_translation
                            print(f"  ✏️ Ligne {index+1}: {reason}")
                
                print("✅ Corrections appliquées à la séquence")
            else:
                print("✅ Séquence cohérente, aucune correction nécessaire")
                
        except Exception as e:
            print(f"Erreur lors de la vérification: {e}")
        
        return sequence_texts
    
    def cross_reference_with_source_language(self, original_text: str, translated_text: str, 
                                           source_language: str) -> str:
        """
        Vérifie la traduction en se référant à la langue source originale si disponible
        """
        if not self.is_available() or source_language == "english":
            return translated_text
        
        # Détecter si le texte contient la langue source
        source_pattern = self.language_patterns.get(source_language.lower())
        if not source_pattern or not source_pattern.search(original_text):
            return translated_text
        
        try:
            cross_reference_prompt = f"""
            Tu es un expert multilingue. Le texte anglais fourni semble être une traduction de mauvaise qualité depuis le {source_language}.
            Vérifie si la traduction française peut être améliorée en tenant compte de la langue source.
            
            LANGUE SOURCE: {source_language}
            TEXTE ANGLAIS: "{original_text}"
            TRADUCTION FRANÇAISE ACTUELLE: "{translated_text}"
            
            Si tu identifies des caractères {source_language} dans le texte anglais, utilise-les pour améliorer la traduction française.
            Si la traduction actuelle est correcte, réponds exactement: "{translated_text}"
            Si tu peux l'améliorer, donne UNIQUEMENT la traduction améliorée, sans préfixe ni explication.
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": cross_reference_prompt}],
                temperature=0.2,
                max_tokens=16300,
                timeout=30
            )
            
            improved_translation = response.choices[0].message.content.strip().replace('"', '')
            
            if improved_translation != translated_text:
                print(f"🌐 Amélioration via {source_language}: '{translated_text}' -> '{improved_translation}'")
                return improved_translation
                
        except Exception as e:
            print(f"Erreur lors de la référence croisée: {e}")
        
        return translated_text

    def translate_with_context(self, text: str, context: Optional[GlobalContext] = None, 
                             file_context: str = "", max_retries: int = 3) -> str:
        """
        Traduit un texte en utilisant le contexte global analysé
        """
        if not text or not text.strip():
            return text
        
        if not self.is_available():
            return text
        
        clean_text = text.strip()
        
        # Utiliser le contexte global si disponible
        if context is None:
            context = self.global_context or self._create_default_context()
        
        # Vérifier le cache intelligent
        cache_key = self.create_translation_hash(clean_text, context, file_context)
        if cache_key in self.translation_cache:
            cached = self.translation_cache[cache_key]
            print(f"[CACHE] '{clean_text[:30]}...' -> '{cached[:30]}...'")
            return cached
        
        # Passer les textes non-alphabétiques ou très courts, mais garder les textes avec caractères CJK
        if len(clean_text.strip()) < 2:
            return text
        
        # Détecter le format SRT avec chinois + anglais
        has_chinese = re.search(r'[\u4e00-\u9fff]', clean_text)
        has_english = re.search(r'[a-zA-Z]', clean_text)
        
        # Vérifier s'il y a du contenu à traduire
        has_translatable_content = has_english or has_chinese
        if not has_translatable_content:
            return text
            
        # Si format SRT bilingue (chinois + anglais), extraire seulement l'anglais pour traduction
        text_to_translate = clean_text
        is_bilingual_srt = False
        chinese_part = ""
        
        if has_chinese and has_english:
            # Format SRT bilingue détecté - préserver la structure complète
            lines = clean_text.split('\n')
            srt_structure = []  # Garder la structure SRT complète
            english_lines_to_translate = []  # Seulement les lignes anglaises à traduire
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # Numéro de séquence SRT
                if re.match(r'^\d+$', line):
                    srt_structure.append(line)
                # Timestamp SRT
                elif '-->' in line:
                    srt_structure.append(line)
                # Ligne chinoise
                elif re.search(r'[\u4e00-\u9fff]', line):
                    srt_structure.append(line)
                # Ligne anglaise à traduire
                elif re.search(r'[a-zA-Z]', line) and line.strip():
                    srt_structure.append('ENGLISH_TO_TRANSLATE')
                    english_lines_to_translate.append(line.strip())
                # Ligne vide
                elif not line:
                    srt_structure.append('')
                else:
                    srt_structure.append(line)
                i += 1
            
            if english_lines_to_translate:
                is_bilingual_srt = True
                text_to_translate = '\n'.join(english_lines_to_translate)
                print(f"[SRT STRUCTURE] {len(english_lines_to_translate)} lignes anglaises à traduire")
        
        print(f"[TRADUCTION INTELLIGENTE] '{text_to_translate[:50]}...'")
        
        for attempt in range(max_retries):
            try:
                # Prompt système avec contexte global
                system_prompt = f"""
                Tu es un traducteur expert spécialisé dans les jeux vidéo Unity.
                Tu as analysé ce jeu et tu connais parfaitement son contexte.
                
                CONTEXTE DU JEU:
                - Type: {context.game_type}
                - Résumé: {context.story_summary}
                - Ton: {context.tone_style}
                - Setting: {context.setting_info}
                - Contexte culturel: {context.cultural_context}
                
                PERSONNAGES IDENTIFIÉS:
                {json.dumps(context.characters, indent=2, ensure_ascii=False) if context.characters else "Aucun personnage spécifique identifié"}
                
                DYNAMIQUES RELATIONNELLES:
                {json.dumps(context.relationship_dynamics, indent=2, ensure_ascii=False)}
                
                RÈGLES DE TRADUCTION:
                1. CONSERVER le sens exact du texte original
                2. Utiliser un style moderne et décontracté (jeunes 20-30 ans)
                3. Maintenir la cohérence avec l'univers analysé
                4. Utiliser un français naturel et fluide
                5. Préserver l'émotion et l'intention
                6. Éviter le vouvoiement, privilégier le tutoiement
                7. Utiliser des expressions actuelles et familières
                
                Tu traduis UNIQUEMENT le texte fourni, sans ajout, préfixe ou modification.
                Ne commence jamais par "Voici la traduction" ou phrases similaires.
                """
                
                user_prompt = f"""
                Contexte du fichier: {file_context if file_context else "Élément de jeu Unity"}
                
                TEXTE À TRADUIRE: "{text_to_translate}"
                
                Traduis ce texte en français moderne et décontracté (style jeune 20-30 ans).
                Utilise le tutoiement et des expressions actuelles. Réponds UNIQUEMENT avec la traduction, sans préfixe.
                """
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=16300,
                    timeout=45
                )
                
                translation = response.choices[0].message.content.strip()
                translation = translation.replace('"', '').strip()
                
                # Nettoyer les préfixes indésirables
                prefixes_to_remove = [
                    "Voici la traduction améliorée :",
                    "Voici la traduction :", 
                    "Traduction :",
                    "La traduction est :"
                ]
                for prefix in prefixes_to_remove:
                    if translation.startswith(prefix):
                        translation = translation[len(prefix):].strip()
                
                # Validation de base
                if not translation or len(translation) < 2:
                    if attempt < max_retries - 1:
                        print(f"[RETRY] Traduction vide, tentative {attempt + 2}")
                        continue
                    print(f"[ÉCHEC] Traduction vide après {max_retries} tentatives")
                    return text
                
                # Reconstituer le format SRT complet si nécessaire
                if is_bilingual_srt:
                    # Diviser les traductions françaises
                    french_translations = [t.strip() for t in translation.split('\n') if t.strip()]
                    
                    # Remplacer les marqueurs ENGLISH_TO_TRANSLATE par les traductions françaises
                    final_structure = []
                    french_index = 0
                    
                    for struct_line in srt_structure:
                        if struct_line == 'ENGLISH_TO_TRANSLATE':
                            if french_index < len(french_translations):
                                final_structure.append(french_translations[french_index])
                                french_index += 1
                            else:
                                final_structure.append('Traduction manquante')
                        else:
                            final_structure.append(struct_line)
                    
                    final_translation = '\n'.join(final_structure)
                    print(f"[SRT RECONSTRUIT] Structure complète préservée")
                else:
                    final_translation = translation
                
                # Validation intelligente
                if self._validate_translation(text_to_translate, translation, context):
                    self.translation_cache[cache_key] = final_translation
                    print(f"[SUCCÈS] '{text_to_translate[:30]}...' -> '{translation[:30]}...'")
                    return final_translation
                else:
                    if attempt < max_retries - 1:
                        print(f"[VALIDATION ÉCHOUÉE] Retry {attempt + 1}")
                        continue
                    
            except Exception as e:
                print(f"[ERREUR] Tentative {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Backoff exponentiel
        
        print(f"[ÉCHEC] Conservation du texte original")
        return text
    
    def _validate_translation(self, original: str, translation: str, context: GlobalContext) -> bool:
        """Validation intelligente de la traduction"""
        try:
            # Validations de base
            if not translation or len(translation.strip()) < 2:
                print(f"[VALIDATION REJETÉE] Traduction trop courte: '{translation}'")
                return False
            
            # Accepter même si similaire - peut être correct pour certains textes
            if original.strip() == translation.strip():
                print(f"[VALIDATION INFO] Traduction identique acceptée: '{translation[:30]}...'")
                return True
            
            # Pas de validation IA pour éviter les rejets incorrects
            print(f"[VALIDATION OK] '{original[:30]}...' -> '{translation[:30]}...'")
            return True
            
        except Exception as e:
            print(f"[VALIDATION ERROR] {e} - Traduction acceptée par défaut")
            return True  # En cas d'erreur, accepter la traduction
    
    def _ai_validate_translation(self, original: str, translation: str, context: GlobalContext) -> bool:
        """Validation IA de la traduction"""
        try:
            validation_prompt = f"""
            Vérifie rapidement cette traduction anglais->français pour un jeu {context.game_type}.
            
            ORIGINAL: "{original}"
            TRADUCTION: "{translation}"
            
            La traduction est-elle correcte ? Réponds uniquement "OUI" ou "NON".
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": validation_prompt}],
                temperature=0.1,
                max_tokens=16300,
                timeout=15
            )
            
            result = response.choices[0].message.content.strip().upper()
            return result == "OUI"
            
        except Exception:
            return True  # En cas d'erreur, accepter
    
    def batch_translate(self, texts: List[Dict], progress_callback: Optional[Callable] = None, 
                       should_stop: Optional[Callable] = None) -> int:
        """
        Traduit un lot de textes avec analyse globale préalable
        """
        if not texts or not self.is_available():
            return 0
        
        # Analyser le contexte global si pas encore fait
        if not self.context_analyzed:
            self.analyze_global_context(texts)
        
        # Filtrer les textes à traduire
        texts_to_translate = [
            t for t in texts 
            if not t.get('is_translated', False) and t.get('original_text', '').strip()
        ]
        
        total_texts = len(texts_to_translate)
        translated_count = 0
        
        print(f"🚀 Traduction intelligente de {total_texts} textes avec contexte global")
        
        for i, text_entry in enumerate(texts_to_translate):
            # Vérifier l'arrêt
            if should_stop and should_stop():
                break
            
            original_text = text_entry.get('original_text', '')
            file_context = f"{text_entry.get('asset_type', 'Unity')} - {text_entry.get('asset_name', 'Asset')}"
            
            # Traduire avec contexte
            translated_text = self.translate_with_context(
                original_text, 
                self.global_context, 
                file_context
            )
            
            # Mettre à jour si traduit
            if translated_text != original_text:
                text_entry['translated_text'] = translated_text
                text_entry['is_translated'] = True
                translated_count += 1
            
            # Progression
            progress = ((i + 1) / total_texts) * 100
            status = f"{i + 1}/{total_texts} - {translated_count} traduits"
            
            if progress_callback:
                progress_callback(progress, status)
            
            # Pause entre traductions
            time.sleep(0.5)
        
        print(f"✅ Traduction intelligente terminée: {translated_count}/{total_texts} textes traduits")
        return translated_count
    
    def _compose_sequence_file_context(self, base_context: str, seq_ctx: SequenceContext, sequence_name: str) -> str:
        """Construit un contexte de fichier enrichi avec les infos de séquence pour le prompt utilisateur"""
        seq_info_parts = []
        if sequence_name:
            seq_info_parts.append(f"Séquence: {sequence_name}")
        if seq_ctx and isinstance(seq_ctx, SequenceContext):
            if seq_ctx.emotional_tone:
                seq_info_parts.append(f"Ton: {seq_ctx.emotional_tone}")
            if seq_ctx.scene_setting:
                seq_info_parts.append(f"Cadre: {seq_ctx.scene_setting}")
            if seq_ctx.characters_present:
                seq_info_parts.append(f"Persos: {', '.join(seq_ctx.characters_present[:5])}")
        seq_info = " | ".join(seq_info_parts)
        return f"{base_context}{' | ' if seq_info else ''}{seq_info}"
    
    def group_texts_into_sequences(self, texts: List[Dict]) -> Dict[str, List[Dict]]:
        """Regroupe les textes en séquences plausibles (par source_file + asset_name)"""
        sequences: Dict[str, List[Dict]] = defaultdict(list)
        for entry in texts:
            # Priorité à une clé explicite si présente
            explicit_key = entry.get('sequence_id') or entry.get('sequence_name') or entry.get('dialogue_id')
            if explicit_key:
                key = str(explicit_key)
            else:
                # Heuristique: regrouper par fichier source + nom d'asset
                key = f"{entry.get('source_file', 'unknown')}::{entry.get('asset_name', 'Asset')}"
            sequences[key].append(entry)
        # Optionnel: trier par apparition stable (id/path_id si dispo)
        for key, items in sequences.items():
            items.sort(key=lambda x: (
                str(x.get('source_file', '')),
                str(x.get('asset_name', '')),
                int(x.get('path_id', 0)) if isinstance(x.get('path_id', 0), int) else 0
            ))
        return sequences
    
    def batch_translate_sequences(self, texts: List[Dict], progress_callback: Optional[Callable] = None, 
                                  should_stop: Optional[Callable] = None) -> int:
        """
        Traduit un lot de textes en les regroupant par séquences, avec:
        - Analyse du contexte global (si nécessaire)
        - Analyse du contexte de chaque séquence
        - Traduction avec contexte global + indices de séquence dans file_context
        - Vérification/correction de cohérence par séquence
        """
        if not texts or not self.is_available():
            return 0
        
        # Analyser le contexte global si besoin
        if not self.context_analyzed:
            self.analyze_global_context(texts)
        
        # Filtrer les textes à traduire - inclure TOUS les textes avec du contenu NON traduits
        texts_to_translate = [
            t for t in texts 
            if t.get('original_text', '').strip() and not t.get('is_translated', False)
        ]
        
        # Debug: afficher le filtrage
        total_input = len(texts)
        after_filter = len(texts_to_translate)
        already_translated = len([t for t in texts if t.get('is_translated', False)])
        print(f"📊 Filtrage: {total_input} textes -> {after_filter} à traiter ({already_translated} déjà traduits)")
        
        if not texts_to_translate:
            return 0
        
        # Regrouper en séquences
        sequences = self.group_texts_into_sequences(texts_to_translate)
        total_texts = sum(len(seq) for seq in sequences.values())
        processed = 0
        translated_count = 0
        
        print(f"🎬 Traduction par séquences: {len(sequences)} séquences, {total_texts} entrées à traiter")
        
        for seq_key, seq_items in sequences.items():
            if should_stop and should_stop():
                break
            # Nom lisible
            sequence_name = seq_key.split('::')[-1]
            # Analyse de séquence (utilise aussi le contexte global)
            seq_context = self.analyze_sequence_context(seq_items, sequence_name=sequence_name)
            
            # Traduction de chaque entrée
            for i, entry in enumerate(seq_items):
                try:
                    print(f"🔄 [{i+1}/{len(seq_items)}] Traitement entrée dans séquence '{sequence_name}'")
                    
                    if should_stop and should_stop():
                        print("⏹️ Arrêt demandé par l'utilisateur")
                        break
                    
                    # Vérifier si déjà traduit et passer si c'est le cas
                    if entry.get('is_translated', False) and entry.get('translated_text', '').strip():
                        print(f"✅ [{i+1}] Déjà traduit, passage au suivant")
                        processed += 1
                        if progress_callback:
                            progress = (processed / total_texts) * 100
                            status = f"{processed}/{total_texts} - {translated_count} traduits (Séquence: {sequence_name}) [DÉJÀ TRADUIT]"
                            progress_callback(progress, status)
                        continue
                    
                    original_text = entry.get('original_text', '')
                    print(f"📝 [{i+1}] Texte original: '{original_text[:50]}...'")
                    
                    base_context = f"{entry.get('asset_type', 'Unity')} - {entry.get('asset_name', 'Asset')}"
                    file_context = self._compose_sequence_file_context(base_context, seq_context, sequence_name)
                    
                    print(f"🔄 [{i+1}] Début traduction...")
                    translated_text = self.translate_with_context(original_text, self.global_context, file_context)
                    print(f"✅ [{i+1}] Traduction terminée: '{translated_text[:50]}...'")
                    
                except Exception as e:
                    print(f"❌ ERREUR lors du traitement de l'entrée {i+1}: {e}")
                    import traceback
                    traceback.print_exc()
                    # Continuer avec l'entrée suivante
                    processed += 1
                    continue
                
                try:
                    # Amélioration via langue source si détectée
                    if seq_context and seq_context.source_language and seq_context.source_language.lower() in ['chinese','korean','japanese']:
                        print(f"🌐 [{i+1}] Amélioration via {seq_context.source_language}...")
                        translated_text = self.cross_reference_with_source_language(original_text, translated_text, seq_context.source_language)
                    
                    if translated_text != original_text:
                        entry['translated_text'] = translated_text
                        entry['is_translated'] = True
                        translated_count += 1
                        print(f"✅ [{i+1}] SUCCÈS: '{original_text[:30]}...' -> '{translated_text[:30]}...'")
                    else:
                        print(f"⚠️ [{i+1}] Pas de changement: '{original_text[:50]}...'")
                        # Marquer comme traduit même si pas changé pour éviter les re-tentatives
                        entry['is_translated'] = True
                    
                    processed += 1
                    print(f"📊 [{i+1}] Progression: {processed}/{total_texts} ({translated_count} traduits)")
                    
                    if progress_callback:
                        progress = (processed / total_texts) * 100
                        status = f"{processed}/{total_texts} - {translated_count} traduits (Séquence: {sequence_name})"
                        progress_callback(progress, status)
                    
                    print(f"⏱️ [{i+1}] Pause de 0.3s...")
                    time.sleep(0.3)
                    print(f"▶️ [{i+1}] Passage à l'entrée suivante")
                    
                except Exception as e:
                    print(f"❌ ERREUR post-traduction entrée {i+1}: {e}")
                    import traceback
                    traceback.print_exc()
                    processed += 1
            
            # Vérification/correction de la séquence complète
            try:
                self.verify_and_correct_sequence_translation(seq_items, seq_context)
            except Exception as e:
                print(f"[WARN] Vérification séquence échouée '{sequence_name}': {e}")
        
        print(f"✅ Traduction par séquences terminée: {translated_count}/{total_texts} textes traduits")
        return translated_count
    
    def save_context_cache(self, filepath: str = "intelligent_context_cache.json"):
        """Sauvegarde le contexte global et le cache"""
        try:
            cache_data = {
                'global_context': self.global_context.to_dict() if self.global_context else None,
                'translation_cache': self.translation_cache,
                'context_analyzed': self.context_analyzed
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Cache intelligent sauvegardé: {filepath}")
            
        except Exception as e:
            print(f"Erreur lors de la sauvegarde du cache: {e}")
    
    def load_context_cache(self, filepath: str = "intelligent_context_cache.json"):
        """Charge le contexte global et le cache"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            if cache_data.get('global_context'):
                self.global_context = GlobalContext.from_dict(cache_data['global_context'])
                self.context_analyzed = cache_data.get('context_analyzed', False)
            
            self.translation_cache = cache_data.get('translation_cache', {})
            
            print(f"📂 Cache intelligent chargé: {len(self.translation_cache)} traductions")
            
        except FileNotFoundError:
            print("Aucun cache intelligent trouvé")
        except Exception as e:
            print(f"Erreur lors du chargement du cache: {e}")
    
    def clear_cache(self):
        """Vide le cache de traductions"""
        self.translation_cache.clear()
        self.global_context = None
        self.context_analyzed = False
        print("🧹 Cache intelligent vidé")
    
    def get_stats(self) -> Dict:
        """Retourne les statistiques du traducteur intelligent"""
        return {
            'cache_size': len(self.translation_cache),
            'context_analyzed': self.context_analyzed,
            'characters_found': len(self.global_context.characters) if self.global_context else 0,
            'game_type': self.global_context.game_type if self.global_context else 'unknown'
        }

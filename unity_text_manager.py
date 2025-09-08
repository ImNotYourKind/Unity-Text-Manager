#!/usr/bin/env python3
"""
Unity Text Manager - Logiciel complet de gestion des textes Unity
Version corrigée avec amélioration de l'interface utilisateur et gestion d'erreurs robuste
Permet de scanner, extraire, traduire et réinjecter les textes des jeux Unity

CORRECTIONS APPORTÉES:
- Ajout d'un bouton pour supprimer des fichiers de la liste
- Correction du problème de sauvegarde avec l'encodage UTF-8
- Correction du problème d'export avec le paramètre initialfilename -> initialfile
- Amélioration de la gestion des erreurs
"""
import os
import sys
import json
import shutil
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from tkinter import ttk
from datetime import datetime
from typing import Optional, Dict, List

# Marquer openai_translator comme non disponible (remplacé par intelligent_translator)
OPENAI_AVAILABLE = False

# Importer le traducteur intelligent
try:
    from intelligent_translator_adapter import IntelligentTranslatorAdapter
    INTELLIGENT_TRANSLATOR_AVAILABLE = True
    print("✅ Traducteur intelligent disponible")
except ImportError as e:
    print(f"Erreur lors de l'import du traducteur intelligent: {e}")
    INTELLIGENT_TRANSLATOR_AVAILABLE = False
    IntelligentTranslatorAdapter = None

try:
    from unity_scanner import UnityTextScanner
except ImportError as e:
    print(f"Erreur lors de l'import de unity_scanner: {e}")
    UnityTextScanner = None

try:
    from unity_injector import UnityTextInjector
except ImportError as e:
    print(f"Erreur lors de l'import de unity_injector: {e}")
    UnityTextInjector = None

try:
    from text_redirector import TextRedirector
except ImportError as e:
    print(f"Erreur lors de l'import de text_redirector: {e}")
    class TextRedirector:
        def __init__(self, widget):
            self.widget = widget
        def write(self, string):
            if hasattr(self.widget, 'insert'):
                self.widget.insert(tk.END, string)
                self.widget.see(tk.END)
        def flush(self):
            pass


class UnityTextManagerGUI:
    """Interface graphique principal du Unity Text Manager"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Unity Text Manager v2.0 - Gestionnaire de Textes Unity")
        self.root.geometry("1100x750")
        self.root.minsize(900, 650)
        
        # Configuration de l'icône et du style
        try:
            # Tenter de définir une icône si elle existe
            if hasattr(tk, 'PhotoImage'):
                self.root.iconbitmap(default='icon.ico')  # Optionnel
        except:
            pass
        
        # Variables d'état
        self.game_path = tk.StringVar()
        self.current_texts: Optional[Dict] = None
        self.scanning = False
        self.injecting = False
        self.translating = False
        self.stop_translation = False
        
        # Variables de configuration
        self.confirm_actions_var = tk.BooleanVar(value=True)  # Demander confirmation par défaut
        self.auto_save_var = tk.BooleanVar(value=False)  # Auto-sauvegarde désactivée par défaut
        
        # Système de traduction intelligent
        self.intelligent_translator: Optional[IntelligentTranslatorAdapter] = None
        
        # Configuration interface
        self.setup_styles()
        self.create_interface()
        self.setup_logging()
        
        # Gestion de la fermeture
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_styles(self):
        """Configure les styles personnalisés"""
        style = ttk.Style()
        
        # Style pour le titre
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'))
        
        # Style pour les boutons d'action
        style.configure('Action.TButton', font=('Arial', 10, 'bold'))
        
        # Style pour les boutons de danger
        style.configure('Danger.TButton', foreground='red')
        
        # Style pour les boutons d'avertissement
        style.configure('Warning.TButton', foreground='orange')
        
        # Style pour la barre de progression
        style.configure('Custom.Horizontal.TProgressbar', thickness=20)
        
        # Style pour le Treeview
        style.configure('Treeview', font=('Arial', 9))
        style.configure('Treeview.Heading', font=('Arial', 9, 'bold'))

    def create_interface(self):
        """Crée l'interface graphique améliorée"""
        # Frame principal avec padding
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # En-tête avec titre et informations
        self.create_header(main_frame)
        
        # Notebook pour les onglets
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # Créer les onglets
        self.create_scanner_tab()
        self.create_editor_tab()
        self.create_injection_tab()
        
        # Frame pour les logs (en bas)
        self.create_log_section(main_frame)

    def create_header(self, parent):
        """Crée l'en-tête de l'application"""
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Titre
        title_label = ttk.Label(
            header_frame, 
            text="Unity Text Manager", 
            style='Title.TLabel'
        )
        title_label.pack(side=tk.LEFT)
        
        # Informations de version et statut
        info_frame = ttk.Frame(header_frame)
        info_frame.pack(side=tk.RIGHT)
        
        version_label = ttk.Label(info_frame, text="v2.0", foreground='gray')
        version_label.pack(side=tk.TOP, anchor=tk.E)
        
        self.status_indicator = ttk.Label(
            info_frame, 
            text="● Prêt", 
            foreground='green'
        )
        self.status_indicator.pack(side=tk.BOTTOM, anchor=tk.E)

    def create_scanner_tab(self):
        """Crée l'onglet de scan amélioré"""
        scanner_frame = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(scanner_frame, text="📁 1. Scanner")
        
        # Section sélection du dossier
        path_section = ttk.LabelFrame(scanner_frame, text="Dossier du jeu Unity", padding="10")
        path_section.pack(fill=tk.X, pady=(0, 15))
        
        path_frame = ttk.Frame(path_section)
        path_frame.pack(fill=tk.X)
        
        self.path_entry = ttk.Entry(
            path_frame, 
            textvariable=self.game_path, 
            font=('Arial', 10),
            state='readonly'
        )
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        ttk.Button(
            path_frame, 
            text="📂 Parcourir dossier", 
            command=self.browse_folder
        ).pack(side=tk.RIGHT, padx=(5, 0))
        
        ttk.Button(
            path_frame, 
            text="📄 Sélectionner fichier", 
            command=self.browse_file
        ).pack(side=tk.RIGHT)
        
        # Section options de scan
        options_section = ttk.LabelFrame(scanner_frame, text="Options de scan", padding="10")
        options_section.pack(fill=tk.X, pady=(0, 15))
        
        # Variables d'options
        self.scan_textassets = tk.BooleanVar(value=True)
        self.scan_monobehaviours = tk.BooleanVar(value=True)
        self.scan_textfiles = tk.BooleanVar(value=True)
        self.deep_scan = tk.BooleanVar(value=False)
        
        # Checkboxes avec descriptions
        options = [
            (self.scan_textassets, "📄 Scanner les TextAssets", "Assets texte Unity standard"),
            (self.scan_monobehaviours, "🔧 Scanner les MonoBehaviours", "Scripts avec données texte"),
            (self.scan_textfiles, "📝 Scanner les fichiers texte", "Fichiers .json, .xml, .txt"),
            (self.deep_scan, "🔍 Scan approfondi", "Analyse plus poussée (plus lent)")
        ]
        
        for var, text, description in options:
            frame = ttk.Frame(options_section)
            frame.pack(fill=tk.X, pady=2)
            
            ttk.Checkbutton(frame, text=text, variable=var).pack(side=tk.LEFT)
            ttk.Label(frame, text=f"— {description}", foreground='gray').pack(side=tk.LEFT, padx=(10, 0))
        
        # Section contrôles
        control_section = ttk.Frame(scanner_frame)
        control_section.pack(fill=tk.X, pady=(0, 15))
        
        self.scan_button = ttk.Button(
            control_section,
            text="🚀 Démarrer le scan",
            command=self.start_scan,
            style='Action.TButton'
        )
        self.scan_button.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            control_section,
            text="📂 Charger un scan existant",
            command=self.load_scan
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        # Bouton de décryptage XOR manuel
        ttk.Button(
            control_section,
            text="🔓 Décryptage XOR",
            command=self.start_manual_xor_decrypt,
            style='Warning.TButton'
        ).pack(side=tk.LEFT)
        
        # Bouton d'arrêt (initialement caché)
        self.stop_scan_button = ttk.Button(
            control_section,
            text="⏹️ Arrêter",
            command=self.stop_current_scan,
            style='Danger.TButton'
        )
        
        # Section progression
        progress_section = ttk.LabelFrame(scanner_frame, text="Progression", padding="10")
        progress_section.pack(fill=tk.X, pady=(0, 10))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_section, 
            variable=self.progress_var, 
            maximum=100,
            length=400
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))
        
        self.status_label = ttk.Label(
            progress_section, 
            text="Sélectionnez un dossier et démarrez le scan"
        )
        self.status_label.pack(anchor=tk.W)

    def create_editor_tab(self):
        """Crée l'onglet d'édition amélioré"""
        editor_frame = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(editor_frame, text="✏️ 2. Éditeur", state="disabled")
        
        # Barre d'outils
        toolbar = ttk.Frame(editor_frame)
        toolbar.pack(fill=tk.X, pady=(0, 15))
        
        # Section de gauche - Outils principaux
        left_tools = ttk.Frame(toolbar)
        left_tools.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(
            left_tools,
            text="📤 Exporter",
            command=self.export_for_translation
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            left_tools,
            text="📥 Importer",
            command=self.import_translations
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        # Traduction automatique avec indicateur de disponibilité
        if INTELLIGENT_TRANSLATOR_AVAILABLE:
            self.auto_translate_button = ttk.Button(
                left_tools,
                text="🧠 Traduction intelligente",
                command=self.setup_intelligent_translation,
                style='Success.TButton'
            )
        else:
            self.auto_translate_button = ttk.Button(
                left_tools,
                text="🤖 Traduction auto (non disponible)",
                state='disabled',
                style='TButton'
            )   
        self.auto_translate_button.pack(side=tk.LEFT, padx=(5, 0))
        
        # Section de droite - Outils secondaires
        right_tools = ttk.Frame(toolbar)
        right_tools.pack(side=tk.RIGHT)
        
        # NOUVEAU: Bouton pour supprimer des éléments
        ttk.Button(
            right_tools,
            text="🗑️ Supprimer sélection",
            command=self.remove_selected_texts,
            style='Danger.TButton'
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        # NOUVEAU: Bouton pour filtrer les TextAssets uniquement
        ttk.Button(
            right_tools,
            text="📄 TextAssets uniquement",
            command=self.filter_textassets_only,
            style='Warning.TButton'
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            right_tools,
            text="🧹 Vider cache",
            command=self.clear_cache
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            right_tools,
            text="💾 Sauvegarder",
            command=self.save_current_texts,
            style='Action.TButton'
        ).pack(side=tk.LEFT)
        
        # Statistiques avec design amélioré
        stats_frame = ttk.LabelFrame(editor_frame, text="📊 Statistiques", padding="10")
        stats_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.stats_label = ttk.Label(
            stats_frame, 
            text="Aucun texte chargé",
            font=('Arial', 10)
        )
        self.stats_label.pack(anchor=tk.W)
        
        # Barre de progression des traductions
        self.translation_progress = ttk.Progressbar(
            stats_frame, 
            maximum=100,
            length=200
        )
        self.translation_progress.pack(fill=tk.X, pady=(5, 0))
        
        # Liste des textes avec recherche
        list_section = ttk.LabelFrame(editor_frame, text="📝 Textes trouvés", padding="5")
        list_section.pack(fill=tk.BOTH, expand=True)
        
        # Barre de recherche
        search_frame = ttk.Frame(list_section)
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(search_frame, text="🔍 Rechercher:").pack(side=tk.LEFT)
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_text_list)
        
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 10))
        
        # Filtre par statut
        ttk.Label(search_frame, text="Statut:").pack(side=tk.LEFT)
        
        self.filter_var = tk.StringVar(value="Tous")
        filter_combo = ttk.Combobox(
            search_frame,
            textvariable=self.filter_var,
            values=["Tous", "Traduit", "Original"],
            state="readonly",
            width=10
        )
        filter_combo.pack(side=tk.LEFT, padx=(5, 0))
        filter_combo.bind('<<ComboboxSelected>>', lambda e: self.filter_text_list())
        
        # Treeview amélioré avec sélection multiple
        tree_frame = ttk.Frame(list_section)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ('ID', 'Fichier', 'Asset', 'Type', 'Longueur', 'Statut')
        self.text_tree = ttk.Treeview(
            tree_frame, 
            columns=columns, 
            show='headings',
            height=15,
            selectmode='extended'  # Permet la sélection multiple
        )
        
        # Configuration des colonnes
        column_config = {
            'ID': (80, 'center'),
            'Fichier': (150, 'w'),
            'Asset': (200, 'w'),
            'Type': (100, 'center'),
            'Longueur': (80, 'center'),
            'Statut': (100, 'center')
        }
        
        for col, (width, anchor) in column_config.items():
            self.text_tree.heading(col, text=col, command=lambda c=col: self.sort_tree(c))
            self.text_tree.column(col, width=width, anchor=anchor)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.text_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.text_tree.xview)
        
        self.text_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Placement avec grid pour un meilleur contrôle
        self.text_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Binds pour la sélection et raccourcis clavier
        self.text_tree.bind('<<TreeviewSelect>>', self.on_text_select)
        self.text_tree.bind('<Double-1>', self.on_text_double_click)
        self.text_tree.bind('<Button-3>', self.show_context_menu)  # Clic droit
        
        # Raccourcis clavier pour sélection
        self.text_tree.bind('<Control-a>', self.select_all_texts)
        self.text_tree.bind('<Control-A>', self.select_all_texts)  # Majuscule aussi
        self.text_tree.bind('<Escape>', self.deselect_all_texts)  # Échap pour désélectionner
        self.text_tree.bind('<Delete>', self.delete_selected_texts)  # Suppr pour supprimer
        
        # Focus sur le TreeView pour les raccourcis clavier
        self.text_tree.focus_set()
        
        # Créer le menu contextuel
        self.create_context_menu()

    def create_injection_tab(self):
        """Crée l'onglet d'injection amélioré"""
        injection_frame = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(injection_frame, text="⚡ 3. Injection", state="disabled")
        
        # Avertissement de sécurité
        warning_section = ttk.LabelFrame(
            injection_frame, 
            text="⚠️ Avertissement de sécurité", 
            padding="15"
        )
        warning_section.pack(fill=tk.X, pady=(0, 20))
        
        warning_text = (
            "L'injection modifie directement les fichiers du jeu.\n"
            "• Une sauvegarde automatique sera créée avant toute modification\n"
            "• Vérifiez que vous avez une copie complète du jeu\n"
            "• Testez sur une copie de sauvegarde avant d'appliquer au jeu principal\n"
            "• Cette opération est irréversible sans restauration manuelle"
        )
        
        warning_label = ttk.Label(
            warning_section, 
            text=warning_text,
            foreground='red',
            font=('Arial', 10)
        )
        warning_label.pack(anchor=tk.W)
        
        # Section préparation
        prep_section = ttk.LabelFrame(injection_frame, text="📋 Préparation", padding="10")
        prep_section.pack(fill=tk.X, pady=(0, 20))
        
        # Statistiques pré-injection
        self.injection_stats = ttk.Label(
            prep_section,
            text="Chargez d'abord des textes traduits...",
            font=('Arial', 10)
        )
        self.injection_stats.pack(anchor=tk.W, pady=(0, 10))
        
        # Options d'injection
        options_frame = ttk.Frame(prep_section)
        options_frame.pack(fill=tk.X)
        
        self.create_backup_var = tk.BooleanVar(value=True)
        self.verify_integrity_var = tk.BooleanVar(value=True)
        self.dry_run_var = tk.BooleanVar(value=False)
        
        ttk.Checkbutton(
            options_frame,
            text="📦 Créer une sauvegarde complète",
            variable=self.create_backup_var
        ).pack(anchor=tk.W)
        
        ttk.Checkbutton(
            options_frame,
            text="🔍 Vérifier l'intégrité après injection",
            variable=self.verify_integrity_var
        ).pack(anchor=tk.W)
        
        ttk.Checkbutton(
            options_frame,
            text="🧪 Mode test (simulation sans modification)",
            variable=self.dry_run_var
        ).pack(anchor=tk.W)
        
        # Section contrôles d'injection
        control_section = ttk.LabelFrame(injection_frame, text="🚀 Injection", padding="15")
        control_section.pack(fill=tk.X, pady=(0, 20))
        
        control_buttons = ttk.Frame(control_section)
        control_buttons.pack(fill=tk.X)
        
        self.inject_button = ttk.Button(
            control_buttons,
            text="⚡ Injecter les traductions",
            command=self.start_injection,
            style='Warning.TButton'
        )
        self.inject_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_inject_button = ttk.Button(
            control_buttons,
            text="⏹️ Arrêter l'injection",
            command=self.stop_current_injection,
            style='Danger.TButton'
        )
        
        # Section progression
        progress_section = ttk.LabelFrame(injection_frame, text="📈 Progression", padding="10")
        progress_section.pack(fill=tk.BOTH, expand=True)
        
        self.inject_progress_var = tk.DoubleVar()
        self.inject_progress_bar = ttk.Progressbar(
            progress_section,
            variable=self.inject_progress_var,
            maximum=100
        )
        self.inject_progress_bar.pack(fill=tk.X, pady=(0, 10))
        
        self.inject_status_label = ttk.Label(
            progress_section,
            text="Prêt pour l'injection"
        )
        self.inject_status_label.pack(anchor=tk.W)
        
        # Log d'injection en temps réel
        log_frame = ttk.Frame(progress_section)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        self.injection_log = scrolledtext.ScrolledText(
            log_frame,
            height=8,
            wrap=tk.WORD,
            font=('Consolas', 9)
        )
        self.injection_log.pack(fill=tk.BOTH, expand=True)


    def create_log_section(self, parent):
        """Crée la section des logs"""
        log_frame = ttk.LabelFrame(parent, text="📋 Journal d'activité", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 0))
        
        # Frame pour les contrôles des logs
        log_controls = ttk.Frame(log_frame)
        log_controls.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(
            log_controls,
            text="🧹 Vider",
            command=self.clear_logs
        ).pack(side=tk.LEFT)
        
        ttk.Button(
            log_controls,
            text="💾 Sauvegarder logs",
            command=self.save_logs
        ).pack(side=tk.LEFT, padx=(5, 0))
        
        # Zone de texte pour les logs
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=8,
            wrap=tk.WORD,
            font=('Consolas', 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def setup_logging(self):
        """Configure la redirection des logs"""
        if hasattr(sys, 'stdout'):
            sys.stdout = TextRedirector(self.log_text)

    def update_status_indicator(self, text: str, color: str = 'green'):
        """Met à jour l'indicateur de statut"""
        self.status_indicator.config(text=f"● {text}", foreground=color)

    def clear_logs(self):
        """Vide les logs"""
        self.log_text.delete(1.0, tk.END)

    def save_logs(self):
        """Sauvegarde les logs dans un fichier"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"logs_unity_manager_{timestamp}.txt"
            
            content = self.log_text.get(1.0, tk.END)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"Unity Text Manager - Logs du {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n\n")
                f.write(content)
            
            messagebox.showinfo("Logs sauvegardés", f"Logs sauvegardés dans: {filename}")
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de sauvegarder les logs: {e}")


    def sort_tree(self, column):
        """Trie le TreeView par colonne"""
        items = list(self.text_tree.get_children(''))
        items.sort(key=lambda x: self.text_tree.set(x, column))
        
        for index, item in enumerate(items):
            self.text_tree.move(item, '', index)

    def filter_text_list(self, *args):
        """Filtre la liste des textes selon la recherche et le filtre"""
        if not self.current_texts:
            return
        
        search_term = self.search_var.get().lower()
        filter_status = self.filter_var.get()
        
        # Vider le TreeView
        for item in self.text_tree.get_children():
            self.text_tree.delete(item)
        
        # Réappliquer les éléments filtrés
        for text_entry in self.current_texts['texts']:
            # Filtrer par recherche
            if search_term:
                searchable_text = (
                    text_entry.get('asset_name', '') + ' ' +
                    text_entry.get('original_text', '')
                ).lower()
                
                if search_term not in searchable_text:
                    continue
            
            # Filtrer par statut
            is_translated = text_entry.get('is_translated', False)
            if filter_status == "Traduit" and not is_translated:
                continue
            elif filter_status == "Original" and is_translated:
                continue
            
            # Ajouter l'élément
            self.add_text_to_tree(text_entry)

    def add_text_to_tree(self, text_entry):
        """Ajoute un texte au TreeView"""
        status = "✅ Traduit" if text_entry.get('is_translated', False) else "📝 Original"
        file_name = Path(text_entry['source_file']).name
        text_length = len(text_entry.get('original_text', ''))
        
        self.text_tree.insert('', tk.END, values=(
            text_entry['id'],
            file_name,
            text_entry.get('asset_name', ''),
            text_entry.get('asset_type', ''),
            text_length,
            status
        ))

    def on_text_select(self, event):
        """Appelé quand un texte est sélectionné"""
        # Afficher le nombre d'éléments sélectionnés
        selected_count = len(self.text_tree.selection())
        if selected_count > 1:
            self.update_status_indicator(f"{selected_count} éléments sélectionnés", 'blue')
        elif selected_count == 1:
            self.update_status_indicator("1 élément sélectionné", 'blue')
        else:
            self.update_status_indicator("Prêt", 'green')

    def on_text_double_click(self, event):
        """Appelé lors du double-clic sur un texte"""
        selection = self.text_tree.selection()
        if not selection:
            return
        
        item = self.text_tree.item(selection[0])
        text_id = item['values'][0]
        
        # Trouver le texte correspondant
        text_entry = self.find_text_by_id(text_id)
        if text_entry:
            self.show_text_editor(text_entry)

    def find_text_by_id(self, text_id: str) -> Optional[Dict]:
        """Trouve un texte par son ID"""
        if not self.current_texts:
            return None
        
        for text_entry in self.current_texts['texts']:
            if text_entry['id'] == text_id:
                return text_entry
        
        return None

    def select_all_texts(self, event=None):
        """Sélectionne tous les textes dans le TreeView (Ctrl+A)"""
        if not self.current_texts:
            return 'break'
        
        # Sélectionner tous les éléments
        all_items = self.text_tree.get_children()
        if all_items:
            self.text_tree.selection_set(all_items)
            self.update_status_indicator(f"Tous les {len(all_items)} éléments sélectionnés", 'blue')
            print(f"📋 Tous les {len(all_items)} éléments sélectionnés avec Ctrl+A")
        
        return 'break'  # Empêche la propagation de l'événement

    def deselect_all_texts(self, event=None):
        """Désélectionne tous les textes dans le TreeView (Échap)"""
        self.text_tree.selection_remove(self.text_tree.selection())
        self.update_status_indicator("Prêt", 'green')
        print("📋 Sélection effacée avec Échap")
        return 'break'

    def delete_selected_texts(self, event=None):
        """Supprime les textes sélectionnés avec la touche Suppr"""
        if self.text_tree.selection():
            self.remove_selected_texts()
        return 'break'

    def remove_selected_texts(self):
        """NOUVEAU: Supprime les textes sélectionnés de la liste"""
        if not self.current_texts:
            messagebox.showerror("Erreur", "Aucun texte chargé")
            return
        
        selected_items = self.text_tree.selection()
        if not selected_items:
            messagebox.showwarning("Attention", "Veuillez sélectionner au moins un élément à supprimer")
            return
        
        # Demander confirmation
        count = len(selected_items)
        if self.confirm_actions_var.get():
            result = messagebox.askyesno(
                "Confirmation de suppression",
                f"Voulez-vous vraiment supprimer {count} élément(s) de la liste ?\n\n"
                f"⚠️ Cette action ne peut pas être annulée.\n"
                f"Les fichiers originaux ne seront pas affectés."
            )
            if not result:
                return
        
        # Récupérer les IDs des éléments à supprimer
        ids_to_remove = []
        for item in selected_items:
            item_values = self.text_tree.item(item)['values']
            if item_values:
                ids_to_remove.append(item_values[0])
        
        # Supprimer les textes de la liste
        original_count = len(self.current_texts['texts'])
        self.current_texts['texts'] = [
            text for text in self.current_texts['texts'] 
            if text['id'] not in ids_to_remove
        ]
        
        # Mettre à jour le total
        self.current_texts['total_texts'] = len(self.current_texts['texts'])
        
        # Rafraîchir l'interface
        self.update_text_list()
        self.update_stats()
        
        removed_count = original_count - len(self.current_texts['texts'])
        messagebox.showinfo(
            "Suppression terminée",
            f"✅ {removed_count} élément(s) supprimé(s) de la liste.\n"
            f"📊 Textes restants: {len(self.current_texts['texts'])}"
        )
        
        print(f"🗑️ {removed_count} textes supprimés de la liste")

    def filter_textassets_only(self):
        """NOUVEAU: Filtre pour ne garder que les TextAssets"""
        if not self.current_texts:
            messagebox.showerror("Erreur", "Aucun texte chargé")
            return
        
        # Compter les TextAssets actuels
        textasset_count = len([
            t for t in self.current_texts['texts'] 
            if t.get('asset_type', '').lower() == 'textasset'
        ])
        
        total_count = len(self.current_texts['texts'])
        other_count = total_count - textasset_count
        
        if other_count == 0:
            messagebox.showinfo("Information", "✅ Seuls des TextAssets sont déjà présents dans la liste")
            return
        
        # Demander confirmation
        if self.confirm_actions_var.get():
            result = messagebox.askyesno(
                "Filtrer les TextAssets",
                f"📄 Filtrage des TextAssets uniquement\n\n"
                f"Cette action va supprimer {other_count} éléments qui ne sont pas des TextAssets.\n"
                f"TextAssets conservés: {textasset_count}\n"
                f"Autres types supprimés: {other_count}\n\n"
                f"⚠️ Cette action ne peut pas être annulée.\n"
                f"Les fichiers originaux ne seront pas affectés.\n\n"
                f"Voulez-vous continuer ?"
            )
            if not result:
                return
        
        # Filtrer pour ne garder que les TextAssets
        original_count = len(self.current_texts['texts'])
        self.current_texts['texts'] = [
            text for text in self.current_texts['texts'] 
            if text.get('asset_type', '').lower() == 'textasset'
        ]
        
        # Mettre à jour le total
        self.current_texts['total_texts'] = len(self.current_texts['texts'])
        
        # Rafraîchir l'interface
        self.update_text_list()
        self.update_stats()
        
        filtered_count = original_count - len(self.current_texts['texts'])
        messagebox.showinfo(
            "Filtrage terminé",
            f"✅ Filtrage des TextAssets terminé.\n\n"
            f"📄 TextAssets conservés: {len(self.current_texts['texts'])}\n"
            f"🗑️ Autres types supprimés: {filtered_count}\n\n"
            f"La traduction intelligente se concentrera maintenant\n"
            f"uniquement sur les TextAssets."
        )
        
        print(f"📄 Filtrage TextAssets: {len(self.current_texts['texts'])} conservés, {filtered_count} supprimés")

    def create_context_menu(self):
        """Crée le menu contextuel pour le TreeView"""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        
        # Options de statut
        self.context_menu.add_command(
            label="📝 Marquer comme original",
            command=self.mark_as_original
        )
        self.context_menu.add_command(
            label="✅ Marquer comme traduit", 
            command=self.mark_as_translated
        )
        self.context_menu.add_separator()
        
        # Options d'action
        self.context_menu.add_command(
            label="✏️ Éditer le texte",
            command=self.edit_selected_text
        )
        self.context_menu.add_command(
            label="🧠 Traduire intelligemment",
            command=self.translate_selected_intelligently
        )
        self.context_menu.add_separator()
        
        # Options de manipulation
        self.context_menu.add_command(
            label="🗑️ Supprimer de la liste",
            command=self.remove_selected_texts
        )

    def show_context_menu(self, event):
        """Affiche le menu contextuel au clic droit"""
        # Identifier l'élément sous le curseur
        item = self.text_tree.identify_row(event.y)
        if item:
            # Sélectionner l'élément si pas déjà sélectionné
            if item not in self.text_tree.selection():
                self.text_tree.selection_set(item)
            
            # Obtenir les informations sur l'élément sélectionné
            item_data = self.text_tree.item(item)
            text_id = item_data['values'][0]
            text_entry = self.find_text_by_id(text_id)
            
            # Adapter le menu selon le statut actuel
            is_translated = text_entry.get('is_translated', False) if text_entry else False
            
            # Activer/désactiver les options selon le contexte
            if is_translated:
                self.context_menu.entryconfig(0, state="normal")  # Marquer original
                self.context_menu.entryconfig(1, state="disabled")  # Marquer traduit
                self.context_menu.entryconfig(4, state="disabled")  # Traduire
            else:
                self.context_menu.entryconfig(0, state="disabled")  # Marquer original
                self.context_menu.entryconfig(1, state="normal")  # Marquer traduit
                self.context_menu.entryconfig(4, state="normal")  # Traduire
            
            # Afficher le menu à la position du curseur
            try:
                self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()

    def mark_as_original(self):
        """Marque les textes sélectionnés comme originaux (non traduits)"""
        selected_items = self.text_tree.selection()
        if not selected_items:
            return
        
        updated_count = 0
        for item in selected_items:
            item_values = self.text_tree.item(item)['values']
            if item_values:
                text_id = item_values[0]
                text_entry = self.find_text_by_id(text_id)
                if text_entry and text_entry.get('is_translated', False):
                    text_entry['is_translated'] = False
                    # Optionnel : effacer la traduction
                    # text_entry['translated_text'] = ""
                    updated_count += 1
        
        if updated_count > 0:
            self.update_text_list()
            self.update_stats()
            print(f"📝 {updated_count} texte(s) marqué(s) comme original")

    def mark_as_translated(self):
        """Marque les textes sélectionnés comme traduits"""
        selected_items = self.text_tree.selection()
        if not selected_items:
            return
        
        updated_count = 0
        for item in selected_items:
            item_values = self.text_tree.item(item)['values']
            if item_values:
                text_id = item_values[0]
                text_entry = self.find_text_by_id(text_id)
                if text_entry and not text_entry.get('is_translated', False):
                    text_entry['is_translated'] = True
                    # S'assurer qu'il y a une traduction (même si identique)
                    if not text_entry.get('translated_text', ''):
                        text_entry['translated_text'] = text_entry.get('original_text', '')
                    updated_count += 1
        
        if updated_count > 0:
            self.update_text_list()
            self.update_stats()
            print(f"✅ {updated_count} texte(s) marqué(s) comme traduit")

    def edit_selected_text(self):
        """Édite le texte sélectionné"""
        selected_items = self.text_tree.selection()
        if not selected_items:
            return
        
        # Prendre le premier élément sélectionné
        item = selected_items[0]
        item_values = self.text_tree.item(item)['values']
        if item_values:
            text_id = item_values[0]
            text_entry = self.find_text_by_id(text_id)
            if text_entry:
                self.show_text_editor(text_entry)

    def translate_selected_intelligently(self):
        """Lance la traduction intelligente sur les textes sélectionnés"""
        if not INTELLIGENT_TRANSLATOR_AVAILABLE:
            messagebox.showerror("Erreur", "Traducteur intelligent non disponible")
            return
        
        selected_items = self.text_tree.selection()
        if not selected_items:
            return
        
        # Récupérer les textes sélectionnés
        texts_to_translate = []
        for item in selected_items:
            item_values = self.text_tree.item(item)['values']
            if item_values:
                text_id = item_values[0]
                text_entry = self.find_text_by_id(text_id)
                if text_entry:
                    texts_to_translate.append(text_entry)
        
        if not texts_to_translate:
            return
        
        # Demander confirmation
        count = len(texts_to_translate)
        result = messagebox.askyesno(
            "Traduction intelligente",
            f"Traduire intelligemment {count} texte(s) sélectionné(s) ?\n\n"
            f"Cette opération utilisera l'API OpenAI."
        )
        
        if result:
            self.translate_selected_texts_worker(texts_to_translate)

    def translate_selected_texts_worker(self, texts_to_translate):
        """Thread worker pour traduire les textes sélectionnés"""
        def translate_worker():
            try:
                if not self.intelligent_translator:
                    self.intelligent_translator = IntelligentTranslatorAdapter()
                
                # Analyser le contexte si nécessaire
                if not self.intelligent_translator.context_analyzed:
                    self.intelligent_translator.analyze_global_context(self.current_texts['texts'])
                
                translated_count = 0
                for text_entry in texts_to_translate:
                    original_text = text_entry.get('original_text', '')
                    file_context = f"{text_entry.get('asset_type', 'Unity')} - {text_entry.get('asset_name', 'Asset')}"
                    
                    translated_text = self.intelligent_translator.translate_with_context(
                        original_text,
                        self.intelligent_translator.global_context,
                        file_context
                    )
                    
                    if translated_text != original_text:
                        text_entry['translated_text'] = translated_text
                        text_entry['is_translated'] = True
                        translated_count += 1
                
                # Mettre à jour l'interface dans le thread principal
                self.root.after(0, self.update_text_list)
                self.root.after(0, self.update_stats)
                
                # Message de fin
                self.root.after(0, lambda: messagebox.showinfo(
                    "Traduction terminée",
                    f"✅ {translated_count} texte(s) traduit(s) avec succès!"
                ))
                
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: messagebox.showerror(
                    "Erreur de traduction",
                    f"Erreur lors de la traduction:\n{error_msg}"
                ))
        
        # Lancer dans un thread séparé
        import threading
        thread = threading.Thread(target=translate_worker)
        thread.daemon = True
        thread.start()

    def on_closing(self):
        """Gestion de la fermeture de l'application"""
        if self.scanning or self.translating or self.injecting:
            result = messagebox.askyesno(
                "Fermeture",
                "Une opération est en cours. Voulez-vous vraiment fermer l'application ?"
            )
            if not result:
                return
        
        # Sauvegarder automatiquement si activé
        if hasattr(self, 'auto_save_var') and self.auto_save_var.get() and self.current_texts:
            try:
                self.save_current_texts()
            except:
                pass
        
        self.root.destroy()

    # --- Méthodes utilitaires supplémentaires ---
    
    def browse_folder(self):
        """Ouvre la boîte de dialogue pour sélectionner un dossier"""
        folder_path = filedialog.askdirectory(
            title="Sélectionnez le dossier du jeu Unity",
            initialdir=self.game_path.get() if self.game_path.get() else os.path.expanduser("~")
        )
        if folder_path:
            self.game_path.set(folder_path)
            self.update_status_indicator("Dossier sélectionné")

    def browse_file(self):
        """Ouvre la boîte de dialogue pour sélectionner un fichier unique"""
        file_path = filedialog.askopenfilename(
            title="Sélectionnez un fichier Unity à analyser",
            initialdir=self.game_path.get() if self.game_path.get() else os.path.expanduser("~"),
            filetypes=[
                ("Tous les fichiers Unity", "*.assets;*.unity;*.asset;*.bundle;*.json;*.txt;*.xml"),
                ("Fichiers Assets", "*.assets"),
                ("Fichiers Unity Scene", "*.unity"),
                ("Fichiers Asset", "*.asset"),
                ("Fichiers Bundle", "*.bundle"),
                ("Fichiers JSON", "*.json"),
                ("Fichiers texte", "*.txt"),
                ("Fichiers XML", "*.xml"),
                ("Tous les fichiers", "*.*")
            ]
        )
        if file_path:
            # Définir le chemin du fichier comme chemin de travail
            self.game_path.set(file_path)
            self.update_status_indicator("Fichier sélectionné")
            print(f"📄 Fichier sélectionné: {Path(file_path).name}")
            print(f"📁 Chemin complet: {file_path}")

    def stop_current_scan(self):
        """Arrête le scan en cours"""
        if hasattr(self, 'scan_stop_flag'):
            self.scan_stop_flag = True
            self.status_label.config(text="Arrêt en cours...")
            self.log("⏹️ Arrêt du scan demandé par l'utilisateur")

    def start_manual_xor_decrypt(self):
        """Lance le décryptage XOR manuel"""
        if not self.game_path.get():
            messagebox.showwarning("Dossier manquant", "Veuillez sélectionner un dossier de jeu d'abord.")
            return
        
        # Créer une fenêtre de dialogue pour le décryptage XOR
        xor_window = tk.Toplevel(self.root)
        xor_window.title("Décryptage XOR Manuel")
        xor_window.geometry("600x400")
        xor_window.transient(self.root)
        xor_window.grab_set()
        
        # Frame principal
        main_frame = ttk.Frame(xor_window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Titre et description
        ttk.Label(main_frame, text="🔓 Décryptage XOR Manuel", font=('Arial', 14, 'bold')).pack(pady=(0, 10))
        
        description = ttk.Label(
            main_frame, 
            text="Cette fonction force le décryptage XOR sur tous les fichiers .srt du dossier sélectionné.\n"
                 "Utilisez cette option seulement si vous savez que vos fichiers sont cryptés.",
            font=('Arial', 9),
            foreground='gray',
            justify=tk.LEFT
        )
        description.pack(pady=(0, 15), anchor=tk.W)
        
        # Section options
        options_frame = ttk.LabelFrame(main_frame, text="Options de décryptage", padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Variables
        self.xor_key_var = tk.StringVar(value="0xAA")
        self.force_decrypt_var = tk.BooleanVar(value=True)
        
        # Clé XOR
        key_frame = ttk.Frame(options_frame)
        key_frame.pack(fill=tk.X, pady=5)
        ttk.Label(key_frame, text="Clé XOR:", width=15).pack(side=tk.LEFT)
        key_entry = ttk.Entry(key_frame, textvariable=self.xor_key_var, width=10)
        key_entry.pack(side=tk.LEFT, padx=(5, 10))
        ttk.Label(key_frame, text="(hex: 0xAA ou décimal: 170)", foreground='gray').pack(side=tk.LEFT)
        
        # Option forcer
        ttk.Checkbutton(
            options_frame, 
            text="Forcer le décryptage (ignorer la détection automatique)",
            variable=self.force_decrypt_var
        ).pack(anchor=tk.W, pady=5)
        
        # Zone de progression
        progress_frame = ttk.LabelFrame(main_frame, text="Progression", padding="10")
        progress_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.xor_progress_var = tk.DoubleVar()
        self.xor_progress_bar = ttk.Progressbar(
            progress_frame, 
            variable=self.xor_progress_var, 
            maximum=100
        )
        self.xor_progress_bar.pack(fill=tk.X, pady=(0, 5))
        
        self.xor_status_label = ttk.Label(progress_frame, text="Prêt à démarrer")
        self.xor_status_label.pack(anchor=tk.W)
        
        # Boutons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))
        
        ttk.Button(
            button_frame,
            text="🔓 Démarrer le décryptage",
            command=lambda: self.execute_manual_xor_decrypt(xor_window),
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            button_frame,
            text="❌ Annuler",
            command=xor_window.destroy
        ).pack(side=tk.RIGHT)

    def execute_manual_xor_decrypt(self, window):
        """Exécute le décryptage XOR manuel"""
        try:
            # Parser la clé XOR
            key_str = self.xor_key_var.get().strip()
            if key_str.startswith('0x') or key_str.startswith('0X'):
                xor_key = int(key_str, 16)
            else:
                xor_key = int(key_str)
            
            if not (0 <= xor_key <= 255):
                raise ValueError("Clé doit être entre 0 et 255")
                
        except ValueError as e:
            messagebox.showerror("Erreur", f"Clé XOR invalide: {e}")
            return
        
        force_decrypt = self.force_decrypt_var.get()
        
        def decrypt_thread():
            try:
                from xor_decoder import xor_decoder
                from pathlib import Path
                import os
                
                game_path = Path(self.game_path.get())
                srt_files = []
                
                # Trouver tous les fichiers .srt
                for root, dirs, files in os.walk(game_path):
                    for file in files:
                        if file.lower().endswith('.srt'):
                            srt_files.append(Path(root) / file)
                
                if not srt_files:
                    self.root.after(0, lambda: messagebox.showinfo("Info", "Aucun fichier .srt trouvé"))
                    return
                
                total_files = len(srt_files)
                decrypted_count = 0
                
                self.root.after(0, lambda: self.xor_status_label.config(text=f"Traitement de {total_files} fichiers..."))
                
                for i, srt_file in enumerate(srt_files):
                    progress = (i + 1) / total_files * 100
                    self.root.after(0, lambda p=progress: self.xor_progress_var.set(p))
                    self.root.after(0, lambda f=srt_file.name: self.xor_status_label.config(text=f"Décryptage: {f}"))
                    
                    # Vérifier si le fichier doit être décrypté
                    should_decrypt = force_decrypt or xor_decoder.is_likely_obfuscated(srt_file)
                    
                    if should_decrypt:
                        # Décrypter le fichier
                        decoded_data = xor_decoder.decode_file(srt_file, xor_key)
                        if decoded_data:
                            # Sauvegarder le fichier décrypté
                            temp_file = xor_decoder.save_decoded_temp(srt_file, decoded_data, xor_key)
                            if temp_file:
                                decrypted_count += 1
                
                self.root.after(0, lambda: self.xor_status_label.config(text=f"Terminé: {decrypted_count}/{total_files} fichiers décryptés"))
                self.root.after(0, lambda: messagebox.showinfo(
                    "Décryptage terminé", 
                    f"Décryptage terminé!\n"
                    f"Fichiers traités: {total_files}\n"
                    f"Fichiers décryptés: {decrypted_count}\n"
                    f"Clé utilisée: 0x{xor_key:02X} ({xor_key})\n\n"
                    f"Les fichiers décryptés sont sauvés dans le dossier 'decoded_temp'."
                ))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Erreur", f"Erreur lors du décryptage: {e}"))
        
        # Lancer le décryptage dans un thread séparé
        import threading
        thread = threading.Thread(target=decrypt_thread, daemon=True)
        thread.start()

    def stop_current_injection(self):
        """Arrête l'injection en cours"""
        if hasattr(self, 'injection_stop_flag'):
            self.injection_stop_flag = True
            self.log("⏹️ Arrêt de l'injection demandé par l'utilisateur")

    def clear_cache(self):
        """Vide le cache de traductions"""
        try:
            # Vider le cache du traducteur intelligent
            if self.intelligent_translator:
                self.intelligent_translator.clear_cache()
            
            # Supprimer les fichiers de cache
            cache_files = [
                "translation_cache.json",
                "intelligent_context_cache.json",
                "intelligent_translations_cache.txt"
            ]
            
            removed_files = []
            for cache_file in cache_files:
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                    removed_files.append(cache_file)
            
            cache_info = "Cache effacé avec succès."
            if removed_files:
                cache_info += f"\nFichiers supprimés: {', '.join(removed_files)}"
            
            messagebox.showinfo("Cache", cache_info)
            print("🧹 Cache vidé (basique + intelligent)")
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'effacer le cache: {e}")

    # --- Les méthodes existantes avec corrections ---
    
    def start_scan(self):
        """Démarre le processus de scan dans un thread séparé"""
        if not self.game_path.get():
            messagebox.showerror("Erreur", "Veuillez sélectionner un dossier")
            return
            
        if not os.path.exists(self.game_path.get()):
            messagebox.showerror("Erreur", "Le dossier sélectionné n'existe pas")
            return
            
        if self.scanning:
            return
            
        if UnityTextScanner is None:
            messagebox.showerror("Erreur", "Module UnityTextScanner non disponible")
            return
        
        self.scanning = True
        self.scan_button.config(state="disabled", text="⏳ Scan en cours...")
        self.stop_scan_button.pack(side=tk.LEFT, padx=(10, 0))
        
        self.log_text.delete(1.0, tk.END)
        self.progress_var.set(0)
        self.update_status_indicator("Scan en cours", 'blue')
        
        # Démarrer le scan dans un thread
        thread = threading.Thread(target=self.run_scan)
        thread.daemon = True
        thread.start()

    def run_scan(self):
        """Exécute le scan"""
        try:
            print("🚀 Démarrage du scan...")
            scanner = UnityTextScanner(self.game_path.get(), self.update_progress)
            
            # Configuration du scanner selon les options
            scanner.scan_textassets = self.scan_textassets.get()
            scanner.scan_monobehaviours = self.scan_monobehaviours.get()
            scanner.scan_textfiles = self.scan_textfiles.get()
            scanner.deep_scan = self.deep_scan.get()
            
            scanner.scan_directory()
            
            self.current_texts = {
                'game_path': self.game_path.get(),
                'scan_date': datetime.now().isoformat(),
                'total_texts': len(scanner.found_texts),
                'texts': scanner.found_texts,
                'scan_options': {
                    'textassets': self.scan_textassets.get(),
                    'monobehaviours': self.scan_monobehaviours.get(),
                    'textfiles': self.scan_textfiles.get(),
                    'deep_scan': self.deep_scan.get()
                }
            }
            
            # Sauvegarder le scan
            self.save_scan_results()
            
            # Mettre à jour l'interface dans le thread principal
            self.root.after(0, self.scan_completed)
            
        except Exception as e:
            error_message = str(e)
            print(f"❌ Erreur durant le scan: {error_message}")
            self.root.after(0, lambda: self.scan_error(error_message))

    def scan_completed(self):
        """Appelé quand le scan est terminé"""
        self.scanning = False
        self.scan_button.config(state="normal", text="🚀 Démarrer le scan")
        self.stop_scan_button.pack_forget()
        
        total_texts = self.current_texts['total_texts']
        self.update_progress(100, f"✅ Scan terminé! {total_texts} textes trouvés")
        self.update_status_indicator("Scan terminé", 'green')
        
        # Activer les autres onglets
        self.notebook.tab(1, state="normal")  # Éditeur
        self.notebook.tab(2, state="normal")  # Injection
        
        # Passer à l'onglet éditeur
        self.notebook.select(1)
        
        # Mettre à jour l'interface
        self.update_text_list()
        self.update_stats()
        
        messagebox.showinfo(
            "Scan terminé",
            f"Scan terminé avec succès!\n"
            f"Textes trouvés: {total_texts}\n"
            f"Fichier de scan sauvé: scan_results.json"
        )
        
        print(f"✅ Scan terminé: {total_texts} textes trouvés")

    def scan_error(self, error_msg: str):
        """Appelé en cas d'erreur durant le scan"""
        self.scanning = False
        self.scan_button.config(state="normal", text="🚀 Démarrer le scan")
        self.stop_scan_button.pack_forget()
        
        self.update_progress(0, "❌ Erreur durant le scan")
        self.update_status_indicator("Erreur de scan", 'red')
        
        messagebox.showerror("Erreur de scan", f"Erreur durant le scan:\n{error_msg}")

    def update_progress(self, value: float, status: str):
        """Met à jour la barre de progression de manière thread-safe"""
        self.root.after(0, lambda: self._update_progress_ui(value, status))

    def _update_progress_ui(self, value: float, status: str):
        """Met à jour l'interface de progression"""
        self.progress_var.set(value)
        self.status_label.config(text=status)

    def update_text_list(self):
        """Met à jour la liste des textes dans le TreeView"""
        # Vider la liste
        for item in self.text_tree.get_children():
            self.text_tree.delete(item)
        
        if not self.current_texts:
            return
        
        # Ajouter les textes
        for text_entry in self.current_texts['texts']:
            self.add_text_to_tree(text_entry)

    def update_stats(self):
        """Met à jour les statistiques"""
        if not self.current_texts:
            self.stats_label.config(text="Aucun texte chargé")
            self.translation_progress.config(value=0)
            return
        
        total = self.current_texts['total_texts']
        translated = len([t for t in self.current_texts['texts'] if t.get('is_translated', False)])
        
        percentage = (translated / total * 100) if total > 0 else 0
        
        stats_text = (
            f"📊 Total: {total} textes | "
            f"✅ Traduits: {translated} ({percentage:.1f}%) | "
            f"📝 Restants: {total - translated}"
        )
        
        self.stats_label.config(text=stats_text)
        self.translation_progress.config(value=percentage)
        
        # Mettre à jour les statistiques d'injection
        if hasattr(self, 'injection_stats'):
            injection_text = (
                f"📋 Prêt à injecter {translated} traductions dans {total} textes trouvés"
            )
            self.injection_stats.config(text=injection_text)

    def show_text_editor(self, text_entry: Dict):
        """Affiche l'éditeur de texte pour un élément"""
        editor_window = tk.Toplevel(self.root)
        editor_window.title(f"✏️ Éditeur - {text_entry.get('asset_name', 'Texte')}")
        editor_window.geometry("900x700")
        editor_window.transient(self.root)
        editor_window.grab_set()
        
        # Configuration de l'icône
        try:
            editor_window.iconbitmap(default='icon.ico')
        except:
            pass
        
        # Frame principal avec padding
        main_frame = ttk.Frame(editor_window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # En-tête avec informations
        info_section = ttk.LabelFrame(main_frame, text="📋 Informations", padding="10")
        info_section.pack(fill=tk.X, pady=(0, 15))
        
        info_grid = ttk.Frame(info_section)
        info_grid.pack(fill=tk.X)
        
        info_data = [
            ("ID:", text_entry.get('id', 'N/A')),
            ("Fichier:", Path(text_entry.get('source_file', '')).name),
            ("Asset:", text_entry.get('asset_name', 'N/A')),
            ("Type:", text_entry.get('asset_type', 'N/A')),
            ("Longueur:", f"{len(text_entry.get('original_text', ''))} caractères")
        ]
        
        for i, (label, value) in enumerate(info_data):
            ttk.Label(info_grid, text=label, font=('Arial', 9, 'bold')).grid(
                row=i//2, column=(i%2)*2, sticky='e', padx=(0, 5), pady=2
            )
            ttk.Label(info_grid, text=value).grid(
                row=i//2, column=(i%2)*2+1, sticky='w', padx=(0, 20), pady=2
            )
        
        # Section texte original
        original_section = ttk.LabelFrame(main_frame, text="📄 Texte original", padding="10")
        original_section.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        original_frame = ttk.Frame(original_section)
        original_frame.pack(fill=tk.BOTH, expand=True)
        
        original_text = scrolledtext.ScrolledText(
            original_frame,
            height=8,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=('Arial', 10)
        )
        original_text.pack(fill=tk.BOTH, expand=True)
        
        original_text.config(state=tk.NORMAL)
        original_text.insert(tk.END, text_entry.get('original_text', ''))
        original_text.config(state=tk.DISABLED)
        
        # Section texte traduit
        translated_section = ttk.LabelFrame(main_frame, text="🌐 Texte traduit", padding="10")
        translated_section.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        translated_frame = ttk.Frame(translated_section)
        translated_frame.pack(fill=tk.BOTH, expand=True)
        
        translated_text = scrolledtext.ScrolledText(
            translated_frame,
            height=8,
            wrap=tk.WORD,
            font=('Arial', 10)
        )
        translated_text.pack(fill=tk.BOTH, expand=True)
        translated_text.insert(tk.END, text_entry.get('translated_text', ''))
        
        # Section boutons
        button_section = ttk.Frame(main_frame)
        button_section.pack(fill=tk.X)
        
        # Fonctions des boutons
        def save_translation():
            new_text = translated_text.get(1.0, tk.END).strip()
            text_entry['translated_text'] = new_text
            text_entry['is_translated'] = new_text != text_entry.get('original_text', '')
            
            self.update_text_list()
            self.update_stats()
            
            if self.auto_save_var.get():
                self.save_current_texts()
            
            editor_window.destroy()
            messagebox.showinfo("Sauvegardé", "Traduction sauvegardée avec succès!")
        
        def reset_translation():
            translated_text.delete(1.0, tk.END)
            translated_text.insert(tk.END, text_entry.get('original_text', ''))
        
        def auto_translate_this():
            if not (OPENAI_AVAILABLE or INTELLIGENT_TRANSLATOR_AVAILABLE):
                messagebox.showerror("Erreur", "Traducteur non disponible")
                return
            
            editor_window.destroy()
            if INTELLIGENT_TRANSLATOR_AVAILABLE:
                self.translate_single_resource_intelligent(text_entry)
            else:
                self.translate_single_resource(text_entry)
        
        # Boutons de gauche
        left_buttons = ttk.Frame(button_section)
        left_buttons.pack(side=tk.LEFT)
        
        ttk.Button(
            left_buttons,
            text="💾 Sauvegarder",
            command=save_translation,
            style='Success.TButton'
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            left_buttons,
            text="🔄 Réinitialiser",
            command=reset_translation
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        # Bouton de traduction automatique
        if INTELLIGENT_TRANSLATOR_AVAILABLE:
            ttk.Button(
                left_buttons,
                text="🧠 Traduire intelligemment",
                command=auto_translate_this,
                style='Action.TButton'
            ).pack(side=tk.LEFT)
        elif OPENAI_AVAILABLE:
            ttk.Button(
                left_buttons,
                text="🤖 Traduire automatiquement",
                command=auto_translate_this,
                style='Action.TButton'
            ).pack(side=tk.LEFT)
        
        # Bouton de fermeture
        ttk.Button(
            button_section,
            text="❌ Fermer",
            command=editor_window.destroy
        ).pack(side=tk.RIGHT)

    def setup_intelligent_translation(self):
        """Configure le système de traduction intelligente"""
        if not INTELLIGENT_TRANSLATOR_AVAILABLE:
            messagebox.showerror(
                "Traducteur intelligent non disponible",
                "Le module de traduction intelligente n'est pas disponible.\n"
                "Vérifiez que le fichier intelligent_translator_adapter.py est présent."
            )
            return
        
        if not self.current_texts:
            messagebox.showerror("Erreur", "Aucun texte à traduire. Effectuez d'abord un scan.")
            return
        
        # Vérifier si l'utilisateur préfère le traducteur basique
        use_basic = getattr(self, 'use_basic_translator_var', None)
        if use_basic and use_basic.get():
            self.setup_auto_translation()
            return
        
        # Initialiser le traducteur intelligent
        if not self.intelligent_translator:
            self.intelligent_translator = IntelligentTranslatorAdapter()
            
            if not self.intelligent_translator.is_available():
                messagebox.showerror(
                    "Configuration requise",
                    "Impossible d'initialiser le traducteur intelligent.\n"
                    "Vérifiez votre clé API OpenAI."
                )
                return
        
        # Charger le cache intelligent
        self.intelligent_translator.load_context_cache()
        print("✅ Traducteur intelligent initialisé")
        
        # Compter les textes non traduits
        untranslated_count = len([
            t for t in self.current_texts['texts'] 
            if not t.get('is_translated', False)
        ])
        
        if untranslated_count == 0:
            messagebox.showinfo("Information", "✅ Tous les textes sont déjà traduits")
            return
        
        # Demander confirmation avec informations sur l'analyse intelligente
        result = messagebox.askyesno(
            "Traduction intelligente",
            f"🧠 Traduction intelligente avec analyse contextuelle\n\n"
            f"Cette fonctionnalité va:\n"
            f"• Analyser le contexte global de votre jeu\n"
            f"• Identifier les personnages et le style\n"
            f"• Traduire {untranslated_count} textes avec cohérence\n"
            f"• Valider automatiquement les traductions\n\n"
            f"⚠️ Première utilisation: analyse plus longue\n"
            f"💰 Utilise l'API OpenAI\n\n"
            f"Voulez-vous continuer ?"
        )
        
        if result:
            self.start_intelligent_translation()
    
    def setup_auto_translation(self):
        """Configure le système de traduction automatique (basique)"""
        if not OPENAI_AVAILABLE:
            messagebox.showerror(
                "OpenAI non disponible",
                "Le module OpenAI n'est pas installé.\n"
                "Installez-le avec: pip install openai langdetect"
            )
            return
        
        if not self.current_texts:
            messagebox.showerror("Erreur", "Aucun texte à traduire. Effectuez d'abord un scan.")
            return
        
        # Rediriger vers le traducteur intelligent
        self.setup_intelligent_translation()
        return
        
        # Compter les textes non traduits
        untranslated_count = len([
            t for t in self.current_texts['texts'] 
            if not t.get('is_translated', False)
        ])
        
        if untranslated_count == 0:
            messagebox.showinfo("Information", "✅ Tous les textes sont déjà traduits")
            return
        
        # Demander confirmation
        result = messagebox.askyesno(
            "Traduction automatique",
            f"Voulez-vous traduire automatiquement les {untranslated_count} textes non traduits?\n\n"
            f"⚠️ Cette opération utilisera l'API OpenAI et peut prendre du temps.\n"
            f"💰 Des frais peuvent s'appliquer selon votre plan OpenAI."
        )
        
        if result:
            self.start_auto_translation()

    def start_intelligent_translation(self):
        """Démarre la traduction intelligente"""
        if not self.current_texts or self.translating:
            return
        
        # Préparer la liste des textes à traduire
        texts_to_translate = [
            t for t in self.current_texts['texts'] 
            if not t.get('is_translated', False)
        ]
        
        if not texts_to_translate:
            messagebox.showinfo("Information", "Tous les textes sont déjà traduits")
            return
        
        self.translating = True
        self.stop_translation = False
        self.auto_translate_button.config(state="disabled", text="⏳ Analyse et traduction...")
        self.update_status_indicator("Traduction intelligente en cours", 'blue')
        
        # Créer une fenêtre de progression intelligente
        self.create_intelligent_translation_window(len(texts_to_translate))
        
        # Démarrer la traduction intelligente dans un thread
        thread = threading.Thread(target=self.run_intelligent_translation, args=(texts_to_translate,))
        thread.daemon = True
        thread.start()
    
    def start_auto_translation(self):
        """Démarre la traduction automatique basique"""
        if not self.current_texts or self.translating:
            return
        
        # Préparer la liste des textes à traduire
        texts_to_translate = [
            t for t in self.current_texts['texts'] 
            if not t.get('is_translated', False)
        ]
        
        if not texts_to_translate:
            messagebox.showinfo("Information", "Tous les textes sont déjà traduits")
            return
        
        self.translating = True
        self.stop_translation = False
        self.auto_translate_button.config(state="disabled", text="⏳ Traduction en cours...")
        self.update_status_indicator("Traduction en cours", 'blue')
        
        # Créer une fenêtre de progression
        self.create_translation_progress_window(len(texts_to_translate))
        
        # Démarrer la traduction dans un thread
        thread = threading.Thread(target=self.run_auto_translation, args=(texts_to_translate,))
        thread.daemon = True
        thread.start()

    def create_translation_progress_window(self, total_texts: int):
        """Crée une fenêtre de progression pour la traduction automatique"""
        self.progress_window = tk.Toplevel(self.root)
        self.progress_window.title("🤖 Traduction automatique")
        self.progress_window.geometry("500x200")
        self.progress_window.transient(self.root)
        self.progress_window.grab_set()
        
        # Empêcher la fermeture par X
        self.progress_window.protocol("WM_DELETE_WINDOW", self.stop_auto_translation)
        
        progress_frame = ttk.Frame(self.progress_window, padding="20")
        progress_frame.pack(fill=tk.BOTH, expand=True)
        
        # Titre
        title_label = ttk.Label(
            progress_frame,
            text=f"🤖 Traduction de {total_texts} textes en cours...",
            font=('Arial', 12, 'bold')
        )
        title_label.pack(pady=(0, 15))
        
        # Barre de progression
        self.translation_progress_var = tk.DoubleVar(value=0)
        self.translation_progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.translation_progress_var,
            maximum=100,
            length=400
        )
        self.translation_progress_bar.pack(fill=tk.X, pady=(0, 10))
        
        # Label de statut
        self.translation_status_label = ttk.Label(
            progress_frame,
            text=f"0/{total_texts} – Initialisation…"
        )
        self.translation_status_label.pack(pady=(0, 15))
        
        # Boutons de contrôle
        button_frame = ttk.Frame(progress_frame)
        button_frame.pack(fill=tk.X)
        
        self.stop_button = ttk.Button(
            button_frame,
            text="⏹️ Arrêter",
            command=self.stop_auto_translation,
            style='Danger.TButton'
        )
        self.stop_button.pack(side=tk.LEFT)
        
        # Informations supplémentaires
        info_label = ttk.Label(
            button_frame,
            text="💡 Vous pouvez fermer cette fenêtre pour arrêter",
            font=('Arial', 8),
            foreground='gray'
        )
        info_label.pack(side=tk.RIGHT)

    def create_intelligent_translation_window(self, total_texts: int):
        """Crée une fenêtre de progression pour la traduction intelligente"""
        self.progress_window = tk.Toplevel(self.root)
        self.progress_window.title("🧠 Traduction Intelligente")
        self.progress_window.geometry("600x300")
        self.progress_window.transient(self.root)
        self.progress_window.grab_set()
        
        # Empêcher la fermeture par X
        self.progress_window.protocol("WM_DELETE_WINDOW", self.stop_auto_translation)
        
        progress_frame = ttk.Frame(self.progress_window, padding="20")
        progress_frame.pack(fill=tk.BOTH, expand=True)
        
        # Titre
        title_label = ttk.Label(
            progress_frame,
            text=f"🧠 Traduction intelligente de {total_texts} textes",
            font=('Arial', 12, 'bold')
        )
        title_label.pack(pady=(0, 10))
        
        # Sous-titre explicatif
        subtitle_label = ttk.Label(
            progress_frame,
            text="Analyse contextuelle globale puis traduction cohérente",
            font=('Arial', 10),
            foreground='gray'
        )
        subtitle_label.pack(pady=(0, 15))
        
        # Barre de progression
        self.translation_progress_var = tk.DoubleVar(value=0)
        self.translation_progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.translation_progress_var,
            maximum=100,
            length=500
        )
        self.translation_progress_bar.pack(fill=tk.X, pady=(0, 10))
        
        # Label de statut
        self.translation_status_label = ttk.Label(
            progress_frame,
            text="🔍 Phase 1: Analyse du contexte global en cours..."
        )
        self.translation_status_label.pack(pady=(0, 15))
        
        # Zone d'informations d'analyse
        info_frame = ttk.LabelFrame(progress_frame, text="📊 Informations d'analyse", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.analysis_info_label = ttk.Label(
            info_frame,
            text="En attente de l'analyse...",
            font=('Arial', 9)
        )
        self.analysis_info_label.pack(anchor=tk.W)
        
        # Boutons de contrôle
        button_frame = ttk.Frame(progress_frame)
        button_frame.pack(fill=tk.X)
        
        self.stop_button = ttk.Button(
            button_frame,
            text="⏹️ Arrêter",
            command=self.stop_auto_translation,
            style='Danger.TButton'
        )
        self.stop_button.pack(side=tk.LEFT)
        
        # Informations supplémentaires
        info_label = ttk.Label(
            button_frame,
            text="💡 Première analyse plus longue, puis traduction accélérée",
            font=('Arial', 8),
            foreground='gray'
        )
        info_label.pack(side=tk.RIGHT)

    def stop_auto_translation(self):
        """Arrête la traduction automatique"""
        self.stop_translation = True
        if hasattr(self, 'translation_status_label'):
            self.translation_status_label.config(text="⏹️ Arrêt demandé...")
        if hasattr(self, 'stop_button'):
            self.stop_button.config(state='disabled')

    def run_auto_translation(self, texts_to_translate: List[Dict]):
        """Exécute la traduction automatique dans un thread séparé"""
        translated_count = 0
        
        try:
            print(f"🚀 Début de la traduction de {len(texts_to_translate)} textes")
            
            def update_translation_progress(value: float, status: str):
                if hasattr(self, 'translation_progress_var') and hasattr(self, 'translation_status_label'):
                    self.root.after(0, lambda: self.translation_progress_var.set(value))
                    self.root.after(0, lambda: self.translation_status_label.config(text=status))
            
            def should_stop():
                return getattr(self, 'stop_translation', False)
            
            # Traduire les textes
            translated_count = self.translator.batch_translate(
                texts_to_translate,
                progress_callback=update_translation_progress,
                should_stop=should_stop
            )
            
            # Sauvegarder le cache
            self.translator.save_cache()
            
            # Mettre à jour l'interface principale
            self.root.after(0, self.update_text_list)
            self.root.after(0, self.update_stats)
            
            # Auto-sauvegarder si activé
            if hasattr(self, 'auto_save_var') and self.auto_save_var.get():
                self.root.after(0, self.save_current_texts)
            
        except Exception as e:
            print(f"❌ Erreur durant la traduction: {e}")
            error_message = str(e)
            self.root.after(0, lambda: messagebox.showerror(
                "Erreur de traduction", 
                f"Erreur durant la traduction:\n{error_message}"
            ))
        
        finally:
            # Nettoyer et fermer
            self.translating = False
            self.stop_translation = False
            
            if hasattr(self, 'progress_window'):
                self.root.after(0, self.progress_window.destroy)
            
            self.root.after(0, lambda: self.auto_translate_button.config(
                state="normal", 
                text="🤖 Traduction auto"
            ))
            
            self.root.after(0, lambda: self.update_status_indicator("Traduction terminée", 'green'))
            
            # Message de fin
            if should_stop():
                self.root.after(0, lambda: messagebox.showinfo(
                    "Traduction interrompue",
                    f"⏹️ Traduction interrompue par l'utilisateur.\n"
                    f"Textes traduits avant l'arrêt: {translated_count}"
                ))
            else:
                self.root.after(0, lambda: messagebox.showinfo(
                    "Traduction terminée",
                    f"✅ Traduction automatique terminée!\n"
                    f"Textes traduits: {translated_count}\n"
                    f"Cache sauvegardé automatiquement."
                ))

    def run_intelligent_translation(self, texts_to_translate: List[Dict]):
        """Exécute la traduction intelligente dans un thread séparé"""
        translated_count = 0
        
        try:
            print(f"🧠 Début de la traduction intelligente de {len(texts_to_translate)} textes")
            
            def update_translation_progress(value: float, status: str):
                if hasattr(self, 'translation_progress_var') and hasattr(self, 'translation_status_label'):
                    self.root.after(0, lambda: self.translation_progress_var.set(value))
                    self.root.after(0, lambda: self.translation_status_label.config(text=status))
            
            def update_analysis_info(info: str):
                if hasattr(self, 'analysis_info_label'):
                    self.root.after(0, lambda: self.analysis_info_label.config(text=info))
            
            def should_stop():
                return getattr(self, 'stop_translation', False)
            
            # Phase 1: Analyse du contexte si pas encore fait
            if not self.intelligent_translator.context_analyzed:
                update_translation_progress(5, "🔍 Phase 1: Analyse globale du contexte...")
                context = self.intelligent_translator.analyze_global_context(self.current_texts['texts'])
                
                # Mettre à jour les informations d'analyse
                stats = self.intelligent_translator.get_stats()
                analysis_text = (
                    f"• Type de jeu: {stats.get('game_type', 'Analysé')}\n"
                    f"• Personnages détectés: {stats.get('characters_found', 0)}\n"
                    f"• Cache intelligent: {stats.get('cache_size', 0)} traductions"
                )
                update_analysis_info(analysis_text)
            
            # Phase 2: Traduction avec contexte
            update_translation_progress(10, "🎬 Phase 2: Traduction par séquences en cours...")
            
            # Traduire les textes avec le traducteur intelligent
            translated_count = self.intelligent_translator.batch_translate_sequences(
                texts_to_translate,
                progress_callback=lambda p, s: update_translation_progress(10 + (p * 0.85), f"🎬 {s}"),
                should_stop=should_stop
            )
            
            # Sauvegarder le cache intelligent
            self.intelligent_translator.save_context_cache()
            
            # Mettre à jour l'interface principale
            self.root.after(0, self.update_text_list)
            self.root.after(0, self.update_stats)
            
            # Auto-sauvegarder si activé
            if hasattr(self, 'auto_save_var') and self.auto_save_var.get():
                self.root.after(0, self.save_current_texts)
            
        except Exception as e:
            print(f"❌ Erreur durant la traduction intelligente: {e}")
            error_message = str(e)
            self.root.after(0, lambda: messagebox.showerror(
                "Erreur de traduction", 
                f"Erreur durant la traduction intelligente:\n{error_message}"
            ))
        
        finally:
            # Nettoyer et fermer
            self.translating = False
            self.stop_translation = False
            
            if hasattr(self, 'progress_window'):
                self.root.after(0, self.progress_window.destroy)
            
            self.root.after(0, lambda: self.auto_translate_button.config(
                state="normal", 
                text="🧠 Traduction intelligente"
            ))
            
            self.root.after(0, lambda: self.update_status_indicator("Traduction intelligente terminée", 'green'))
            
            # Message de fin
            if should_stop():
                self.root.after(0, lambda: messagebox.showinfo(
                    "Traduction interrompue",
                    f"⏹️ Traduction intelligente interrompue.\n"
                    f"Textes traduits avant l'arrêt: {translated_count}"
                ))
            else:
                # Obtenir les statistiques finales
                stats = self.intelligent_translator.get_stats()
                self.root.after(0, lambda: messagebox.showinfo(
                    "Traduction intelligente terminée",
                    f"✅ Traduction intelligente terminée!\n\n"
                    f"📊 Textes traduits: {translated_count}\n"
                    f"🧠 Personnages analysés: {stats.get('characters_found', 0)}\n"
                    f"💾 Cache intelligent: {stats.get('cache_size', 0)} traductions\n\n"
                    f"Le contexte global a été sauvegardé pour les prochaines sessions."
                ))

    def translate_single_resource(self, text_entry: Dict):
        """Traduit une ressource spécifique - redirection vers traducteur intelligent"""
        # Rediriger vers le traducteur intelligent
        self.translate_single_resource_intelligent(text_entry)
        return
        
        # Créer une fenêtre de progression simple
        progress_window = tk.Toplevel(self.root)
        progress_window.title("🤖 Traduction")
        progress_window.geometry("400x150")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        progress_frame = ttk.Frame(progress_window, padding="20")
        progress_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(
            progress_frame,
            text="🤖 Traduction en cours...",
            font=('Arial', 11, 'bold')
        ).pack(pady=(0, 15))
        
        progress_bar = ttk.Progressbar(
            progress_frame,
            mode="indeterminate",
            length=300
        )
        progress_bar.pack(fill=tk.X, pady=(0, 10))
        progress_bar.start()
        
        status_label = ttk.Label(progress_frame, text="Initialisation...")
        status_label.pack()
        
        def translate_worker():
            try:
                status_label.config(text="Analyse du contexte...")
                context = self.translator.get_default_context()
                
                status_label.config(text="Traduction en cours...")
                original_text = text_entry.get('original_text', '')
                translated_text = self.translator.translate_text(original_text, context)
                
                status_label.config(text="Finalisation...")
                
                if translated_text != original_text:
                    text_entry['translated_text'] = translated_text
                    text_entry['is_translated'] = True
                    
                    # Sauvegarder le cache
                    self.translator.save_cache()
                    
                    # Mettre à jour l'interface
                    self.root.after(100, self.update_text_list)
                    self.root.after(100, self.update_stats)
                    
                    progress_window.after(500, progress_window.destroy)
                    messagebox.showinfo("Succès", "✅ Texte traduit avec succès!")
                else:
                    progress_window.destroy()
                    messagebox.showinfo("Information", "ℹ️ Le texte semble déjà être en français")
                    
            except Exception as e:
                progress_window.destroy()
                error_message = str(e)
                messagebox.showerror("Erreur", f"Erreur lors de la traduction:\n{error_message}")
        
        # Lancer la traduction dans un thread
        thread = threading.Thread(target=translate_worker)
        thread.daemon = True
        thread.start()

    def translate_single_resource_intelligent(self, text_entry: Dict):
        """Traduit une ressource spécifique avec le traducteur intelligent"""
        if not INTELLIGENT_TRANSLATOR_AVAILABLE or not self.intelligent_translator:
            messagebox.showerror("Erreur", "Traducteur intelligent non disponible")
            return
        
        # Créer une fenêtre de progression simple
        progress_window = tk.Toplevel(self.root)
        progress_window.title("🧠 Traduction Intelligente")
        progress_window.geometry("450x200")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        progress_frame = ttk.Frame(progress_window, padding="20")
        progress_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(
            progress_frame,
            text="🧠 Traduction intelligente en cours...",
            font=('Arial', 11, 'bold')
        ).pack(pady=(0, 10))
        
        ttk.Label(
            progress_frame,
            text="Analyse contextuelle et traduction cohérente",
            font=('Arial', 9),
            foreground='gray'
        ).pack(pady=(0, 15))
        
        progress_bar = ttk.Progressbar(
            progress_frame,
            mode="indeterminate",
            length=350
        )
        progress_bar.pack(fill=tk.X, pady=(0, 10))
        progress_bar.start()
        
        status_label = ttk.Label(progress_frame, text="Initialisation...")
        status_label.pack()
        
        def translate_worker():
            try:
                # Analyser le contexte si pas encore fait
                if not self.intelligent_translator.context_analyzed:
                    status_label.config(text="Analyse du contexte global...")
                    self.intelligent_translator.analyze_global_context(self.current_texts['texts'])
                
                status_label.config(text="Traduction intelligente...")
                original_text = text_entry.get('original_text', '')
                file_context = f"{text_entry.get('asset_type', 'Unity')} - {text_entry.get('asset_name', 'Asset')}"
                
                translated_text = self.intelligent_translator.translate_with_context(
                    original_text, 
                    self.intelligent_translator.global_context,
                    file_context
                )
                
                status_label.config(text="Finalisation...")
                
                if translated_text != original_text:
                    text_entry['translated_text'] = translated_text
                    text_entry['is_translated'] = True
                    
                    # Sauvegarder le cache intelligent
                    self.intelligent_translator.save_context_cache()
                    
                    # Mettre à jour l'interface
                    self.root.after(100, self.update_text_list)
                    self.root.after(100, self.update_stats)
                    
                    progress_window.after(500, progress_window.destroy)
                    messagebox.showinfo("Succès", "✅ Texte traduit intelligemment avec succès!")
                else:
                    progress_window.destroy()
                    messagebox.showinfo("Information", "ℹ️ Le texte semble déjà être en français")
                    
            except Exception as e:
                progress_window.destroy()
                error_message = str(e)
                messagebox.showerror("Erreur", f"Erreur lors de la traduction intelligente:\n{error_message}")
        
        # Lancer la traduction dans un thread
        thread = threading.Thread(target=translate_worker)
        thread.daemon = True
        thread.start()

    def export_for_translation(self):
        """CORRECTION: Exporte les textes pour traduction - paramètre initialfile au lieu de initialfilename"""
        if not self.current_texts:
            messagebox.showerror("Erreur", "Aucun texte à exporter")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Exporter pour traduction",
            defaultextension=".json",
            filetypes=[
                ("Fichiers JSON", "*.json"),
                ("Tous les fichiers", "*.*")
            ],
            initialfile=f"unity_texts_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"  # CORRECTION: initialfile au lieu de initialfilename
        )
        
        if file_path:
            try:
                export_data = {
                    **self.current_texts,
                    'export_date': datetime.now().isoformat(),
                    'export_version': '2.0'
                }
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                
                messagebox.showinfo(
                    "Export réussi",
                    f"✅ Textes exportés vers:\n{file_path}\n\n"
                    f"📊 {self.current_texts['total_texts']} textes exportés"
                )
                print(f"📤 Textes exportés vers: {file_path}")
                
            except Exception as e:
                error_message = str(e)
                messagebox.showerror("Erreur d'export", f"Erreur lors de l'export:\n{error_message}")

    def import_translations(self):
        """Importe les traductions depuis un fichier"""
        file_path = filedialog.askopenfilename(
            title="Importer les traductions",
            filetypes=[
                ("Fichiers JSON", "*.json"),
                ("Tous les fichiers", "*.*")
            ]
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    imported_data = json.load(f)
                
                # Vérifier la compatibilité
                if 'texts' not in imported_data:
                    messagebox.showerror("Erreur", "Format de fichier invalide")
                    return
                
                # Fusionner les traductions
                imported_texts = {t['id']: t for t in imported_data['texts']}
                updated_count = 0
                
                for text_entry in self.current_texts['texts']:
                    if text_entry['id'] in imported_texts:
                        imported_entry = imported_texts[text_entry['id']]
                        text_entry['translated_text'] = imported_entry.get('translated_text', '')
                        text_entry['is_translated'] = imported_entry.get(
                            'is_translated',
                            imported_entry.get('translated_text', '') != text_entry.get('original_text', '')
                        )
                        updated_count += 1
                
                self.update_text_list()
                self.update_stats()
                
                messagebox.showinfo(
                    "Import réussi",
                    f"✅ Traductions importées avec succès!\n"
                    f"📊 Textes mis à jour: {updated_count}/{len(imported_texts)}"
                )
                print(f"📥 Import terminé: {updated_count} textes mis à jour")
                
            except Exception as e:
                error_message = str(e)
                messagebox.showerror("Erreur d'import", f"Erreur lors de l'import:\n{error_message}")

    def save_current_texts(self):
        """CORRECTION: Sauvegarde l'état actuel des textes avec encodage UTF-8 explicite"""
        if not self.current_texts:
            messagebox.showerror("Erreur", "Aucun texte à sauvegarder")
            return
        
        try:
            # Ajouter des métadonnées de sauvegarde
            save_data = {
                **self.current_texts,
                'last_save_date': datetime.now().isoformat(),
                'save_version': '2.0'
            }
            
            # CORRECTION: Encodage UTF-8 explicite et gestion des erreurs
            with open("current_texts.json", 'w', encoding='utf-8', errors='replace') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            
            print("💾 Textes sauvegardés dans current_texts.json")
            
            if hasattr(self, 'confirm_actions_var') and not self.confirm_actions_var.get():
                # Sauvegarde silencieuse si les confirmations sont désactivées
                pass
            else:
                messagebox.showinfo("Sauvegarde réussie", "💾 Textes sauvegardés dans current_texts.json")
                
        except UnicodeEncodeError as e:
            print(f"❌ Erreur d'encodage lors de la sauvegarde: {e}")
            messagebox.showerror("Erreur de sauvegarde", 
                f"Erreur d'encodage lors de la sauvegarde.\n"
                f"Certains caractères ne peuvent pas être sauvés.\n"
                f"Détails: {e}")
        except Exception as e:
            error_message = str(e)
            print(f"❌ Erreur lors de la sauvegarde: {error_message}")
            messagebox.showerror("Erreur de sauvegarde", f"Erreur lors de la sauvegarde:\n{error_message}")

    def load_scan(self):
        """Charge un scan existant"""
        file_path = filedialog.askopenfilename(
            title="Charger un scan existant",
            filetypes=[
                ("Fichiers JSON", "*.json"),
                ("Tous les fichiers", "*.*")
            ]
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.current_texts = json.load(f)
                
                # Vérifier le format
                if 'texts' not in self.current_texts:
                    messagebox.showerror("Erreur", "Format de fichier invalide")
                    return
                
                # Mettre à jour le chemin du jeu
                if 'game_path' in self.current_texts:
                    self.game_path.set(self.current_texts['game_path'])
                
                # Activer les onglets
                self.notebook.tab(1, state="normal")
                self.notebook.tab(2, state="normal")
                self.notebook.select(1)
                
                # Mettre à jour l'interface
                self.update_text_list()
                self.update_stats()
                self.update_status_indicator("Scan chargé", 'green')
                
                messagebox.showinfo(
                    "Chargement réussi",
                    f"✅ Scan chargé avec succès!\n"
                    f"📊 Textes trouvés: {self.current_texts.get('total_texts', 0)}\n"
                    f"📅 Date du scan: {self.current_texts.get('scan_date', 'Inconnue')}"
                )
                print(f"📂 Scan chargé: {self.current_texts.get('total_texts', 0)} textes")
                
            except Exception as e:
                error_message = str(e)
                messagebox.showerror("Erreur de chargement", f"Erreur lors du chargement:\n{error_message}")

    def save_scan_results(self):
        """Sauvegarde les résultats du scan"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"scan_results_{timestamp}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.current_texts, f, indent=2, ensure_ascii=False)
            
            # Créer aussi une sauvegarde générique
            with open("scan_results.json", 'w', encoding='utf-8') as f:
                json.dump(self.current_texts, f, indent=2, ensure_ascii=False)
                
            print(f"💾 Résultats du scan sauvegardés: {filename}")
            
        except Exception as e:
            print(f"❌ Erreur lors de la sauvegarde du scan: {e}")

    def start_injection(self):
        """Démarre le processus d'injection"""
        if not self.current_texts:
            messagebox.showerror("Erreur", "Aucun texte à injecter")
            return
        
        # Vérifier qu'il y a des traductions
        translated_count = len([
            t for t in self.current_texts['texts'] 
            if t.get('is_translated', False)
        ])
        
        if translated_count == 0:
            messagebox.showwarning("Aucune traduction", "Aucun texte traduit à injecter")
            return
        
        # Confirmation avec plus d'informations
        if self.confirm_actions_var.get():
            confirmation_text = (
                f"⚠️ CONFIRMATION D'INJECTION ⚠️\n\n"
                f"Vous êtes sur le point d'injecter {translated_count} traductions.\n"
                f"Cette opération modifiera les fichiers du jeu de manière PERMANENTE.\n\n"
                f"✅ Une sauvegarde sera créée: {self.create_backup_var.get()}\n"
                f"🔍 Vérification d'intégrité: {self.verify_integrity_var.get()}\n"
                f"🧪 Mode test: {self.dry_run_var.get()}\n\n"
                f"Voulez-vous continuer ?"
            )
            
            result = messagebox.askyesno("Confirmation d'injection", confirmation_text)
            if not result:
                return
        
        if self.injecting:
            return
        
        if UnityTextInjector is None:
            messagebox.showerror("Erreur", "Module UnityTextInjector non disponible")
            return
        
        self.injecting = True
        self.inject_button.config(state="disabled", text="⏳ Injection en cours...")
        self.stop_inject_button.pack(side=tk.LEFT, padx=(10, 0))
        self.inject_progress_var.set(0)
        self.update_status_indicator("Injection en cours", 'orange')
        
        # Vider le log d'injection
        self.injection_log.delete(1.0, tk.END)
        
        # Démarrer l'injection dans un thread
        thread = threading.Thread(target=self.run_injection)
        thread.daemon = True
        thread.start()

    def run_injection(self):
        """Exécute l'injection"""
        try:
            print("🚀 Début de l'injection...")
            
            # Rediriger temporairement la sortie vers le log d'injection
            original_stdout = sys.stdout
            sys.stdout = TextRedirector(self.injection_log)
            
            injector = UnityTextInjector(self.game_path.get())
            success_count = injector.inject_translations(
                self.current_texts, 
                self.update_inject_progress
            )
            
            # Restaurer la sortie normale
            sys.stdout = original_stdout
            
            self.root.after(0, lambda: self.injection_completed(success_count))
            
        except Exception as e:
            # Restaurer la sortie normale en cas d'erreur
            if 'original_stdout' in locals():
                sys.stdout = original_stdout
            
            error_message = str(e)
            print(f"❌ Erreur durant l'injection: {error_message}")
            self.root.after(0, lambda: self.injection_error(error_message))

    def injection_completed(self, success_count: int):
        """Appelé quand l'injection est terminée"""
        self.injecting = False
        self.inject_button.config(state="normal", text="⚡ Injecter les traductions")
        self.stop_inject_button.pack_forget()
        
        self.update_inject_progress(100, f"✅ Injection terminée! {success_count} textes injectés")
        self.update_status_indicator("Injection terminée", 'green')
        
        messagebox.showinfo(
            "Injection terminée",
            f"✅ Injection terminée avec succès!\n\n"
            f"📊 Textes injectés: {success_count}\n"
            f"📂 Sauvegardes créées dans: backups/\n\n"
            f"🎮 Vous pouvez maintenant tester le jeu avec les traductions."
        )
        
        print(f"✅ Injection terminée: {success_count} textes injectés")

    def injection_error(self, error_msg: str):
        """Appelé en cas d'erreur durant l'injection"""
        self.injecting = False
        self.inject_button.config(state="normal", text="⚡ Injecter les traductions")
        self.stop_inject_button.pack_forget()
        
        self.update_inject_progress(0, "❌ Erreur durant l'injection")
        self.update_status_indicator("Erreur d'injection", 'red')
        
        messagebox.showerror("Erreur d'injection", f"❌ Erreur durant l'injection:\n{error_msg}")

    def update_inject_progress(self, value: float, status: str):
        """Met à jour la barre de progression d'injection de manière thread-safe"""
        self.root.after(0, lambda: self._update_inject_progress_ui(value, status))

    def _update_inject_progress_ui(self, value: float, status: str):
        """Met à jour l'interface de progression d'injection"""
        self.inject_progress_var.set(value)
        self.inject_status_label.config(text=status)

    def run(self):
        """Lance l'application"""
        try:
            print("🚀 Démarrage de Unity Text Manager v2.0")
            self.root.mainloop()
        except KeyboardInterrupt:
            print("⏹️ Fermeture demandée par l'utilisateur")
        except Exception as e:
            print(f"❌ Erreur fatale: {e}")
            messagebox.showerror("Erreur fatale", f"Une erreur critique s'est produite:\n{e}")


def main():
    """Point d'entrée principal avec vérifications améliorées"""
    print("=" * 60)
    print("Unity Text Manager v2.0 - Démarrage")
    print("=" * 60)
    
    # Vérifier les dépendances principales
    missing_deps = []
    
    try:
        import UnityPy
        print("✅ UnityPy disponible")
    except ImportError:
        missing_deps.append("UnityPy")
        print("❌ UnityPy manquant")
    
    try:
        import tkinter
        print("✅ Tkinter disponible")
    except ImportError:
        missing_deps.append("tkinter")
        print("❌ Tkinter manquant")
    
    if missing_deps:
        print(f"\n❌ Dépendances manquantes: {', '.join(missing_deps)}")
        print("Installez les dépendances avec:")
        print("pip install UnityPy")
        if 'tkinter' in missing_deps:
            print("sudo apt-get install python3-tk  # Sur Ubuntu/Debian")
        input("\nAppuyez sur Entrée pour fermer...")
        sys.exit(1)
    
    # Informer sur les dépendances optionnelles
    if INTELLIGENT_TRANSLATOR_AVAILABLE:
        print("✅ Traduction intelligente activée")
    elif OPENAI_AVAILABLE:
        print("✅ OpenAI disponible - Traduction automatique activée")
    else:
        print("⚠️ Traduction non disponible")
        print("Pour activer: pip install openai langdetect")
    
    print("\n🚀 Lancement de l'interface graphique...")
    
    # Lancer l'application
    try:
        app = UnityTextManagerGUI()
        app.run()
    except Exception as e:
        print(f"\n❌ Erreur fatale: {e}")
        messagebox.showerror("Erreur fatale", f"Impossible de démarrer l'application:\n{e}")
        input("Appuyez sur Entrée pour fermer...")
        sys.exit(1)


if __name__ == "__main__":
    main()
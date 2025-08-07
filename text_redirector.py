# text_redirector.py
"""
Module pour rediriger la sortie texte vers un widget Tkinter Text.
"""

import tkinter as tk


class TextRedirector:
    """Redirige la sortie texte (comme print) vers un widget Text de Tkinter"""
    
    def __init__(self, widget):
        """
        Initialise le redirecteur.
        
        Args:
            widget: Le widget Text de Tkinter où rediriger la sortie.
        """
        self.widget = widget

    def write(self, string):
        """
        Écrit une chaîne dans le widget Text.
        
        Args:
            string (str): La chaîne à écrire.
        """
        self.widget.insert(tk.END, string)
        self.widget.see(tk.END)  # Faire défiler jusqu'à la fin
        self.widget.update_idletasks() # Mettre à jour l'affichage

    def flush(self):
        """
        Méthode flush requise pour la compatibilité avec sys.stdout.
        Ne fait rien dans cette implémentation.
        """
        pass

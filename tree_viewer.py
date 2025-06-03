import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
from pathlib import Path
import ast

class TreeViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("Pregledovalnik ESCO drevesa")
        self.geometry("1200x800")
        
        # Nastavi glavni container
        self.main_container = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Levi del - drevo
        self.tree_frame = ttk.Frame(self.main_container)
        self.main_container.add(self.tree_frame, weight=1)
        
        # Iskalnik
        self.search_frame = ttk.Frame(self.tree_frame)
        self.search_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_tree)
        self.search_entry = ttk.Entry(self.search_frame, textvariable=self.search_var)
        self.search_entry.pack(fill=tk.X, side=tk.LEFT, expand=True)
        
        ttk.Label(self.search_frame, text="Išči:").pack(side=tk.LEFT, padx=(0, 5))
        
        # Drevo
        self.tree = ttk.Treeview(self.tree_frame, selectmode='browse')
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Scrollbar za drevo
        self.tree_scroll = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=self.tree_scroll.set)
        
        # Desni del - podrobnosti
        self.details_frame = ttk.Frame(self.main_container)
        self.main_container.add(self.details_frame, weight=1)
        
        # Podrobnosti
        self.details_text = tk.Text(self.details_frame, wrap=tk.WORD, width=50)
        self.details_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Scrollbar za podrobnosti
        self.details_scroll = ttk.Scrollbar(self.details_frame, orient="vertical", command=self.details_text.yview)
        self.details_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.details_text.configure(yscrollcommand=self.details_scroll.set)
        
        # Naloži podatke
        self.load_data()
        
        # Poveži dogodke
        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        
    def safe_eval(self, x):
        """Varno ovrednoti string kot seznam."""
        if pd.isna(x) or not x or str(x).strip() in ['', '[]']:
            return []
        try:
            result = ast.literal_eval(str(x))
            return result if isinstance(result, list) else []
        except:
            return []
        
    def load_data(self):
        """Naloži podatke iz CSV datoteke in jih prikaže v drevesu."""
        try:
            # Naloži CSV
            self.df = pd.read_csv("drevo.csv")
            
            # Počisti obstoječe drevo
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Slovar za shranjevanje vseh vozlišč
            self.nodes = {}
            
            # Najprej dodaj korensko vozlišče (nivo 0)
            root_nodes = self.df[self.df['nivo_indentacije'] == 0]
            for _, row in root_nodes.iterrows():
                node_id = str(row['ID'])
                self.nodes[row['uri']] = node_id
                self.tree.insert('', 'end', node_id, text=row['ime'])
            
            # Dodaj ostala vozlišča po nivojih
            for level in range(1, self.df['nivo_indentacije'].max() + 1):
                level_nodes = self.df[self.df['nivo_indentacije'] == level]
                for _, row in level_nodes.iterrows():
                    if pd.notna(row['parent_uri']) and row['parent_uri'] in self.nodes:
                        parent_id = self.nodes[row['parent_uri']]
                        node_id = str(row['ID'])
                        self.nodes[row['uri']] = node_id
                        self.tree.insert(parent_id, 'end', node_id, text=row['ime'])
            
        except Exception as e:
            messagebox.showerror("Napaka", f"Napaka pri nalaganju podatkov: {str(e)}")
    
    def on_select(self, event):
        """Prikaži podrobnosti izbranega vozlišča."""
        selected_items = self.tree.selection()
        if not selected_items:
            return
        
        node_id = selected_items[0]
        row = self.df[self.df['ID'] == int(node_id)].iloc[0]
        
        # Pripravi podrobnosti
        details = f"URI: {row['uri']}\n"
        details += f"Ime: {row['ime']}\n"
        details += f"Tip: {row['tip']}\n"
        details += f"Nivo: {row['nivo_indentacije']}\n\n"
        
        if pd.notna(row['description']) and row['description']:
            details += f"Opis:\n{row['description']}\n\n"
        
        if pd.notna(row['altLabels']) and row['altLabels']:
            details += f"Alternativna imena:\n{row['altLabels']}\n\n"
        
        if pd.notna(row['scopeNote']) and row['scopeNote']:
            details += f"Opombe:\n{row['scopeNote']}\n\n"
        
        # Dodaj relacije
        broader = self.safe_eval(row['broader_relations'])
        if broader:
            details += f"Nadrejene relacije:\n" + "\n".join(broader) + "\n\n"
        
        narrower = self.safe_eval(row['narrower_relations'])
        if narrower:
            details += f"Podrejene relacije:\n" + "\n".join(narrower) + "\n\n"
        
        broader_skills = self.safe_eval(row['broader_skills'])
        if broader_skills:
            details += f"Nadrejene veščine:\n" + "\n".join(broader_skills) + "\n\n"
        
        narrower_skills = self.safe_eval(row['narrower_skills'])
        if narrower_skills:
            details += f"Podrejene veščine:\n" + "\n".join(narrower_skills) + "\n\n"
        
        # Prikaži podrobnosti
        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(tk.END, details)
    
    def filter_tree(self, *args):
        """Filtrira drevo glede na iskalni niz."""
        search_term = self.search_var.get().lower()
        
        # Počisti trenutno označena vozlišča
        self.tree.selection_remove(self.tree.selection())
        
        # Če ni iskalnega niza, prikaži vsa vozlišča
        if not search_term:
            for item in self.tree.get_children():
                self.show_all_nodes(item)
            return
        
        # Skrij vsa vozlišča
        for item in self.tree.get_children():
            self.hide_all_nodes(item)
        
        # Poišči ujemajoča vozlišča in njihove starše
        matching_nodes = self.df[
            self.df['ime'].str.lower().str.contains(search_term) |
            self.df['description'].str.lower().str.contains(search_term, na=False)
        ]
        
        for _, row in matching_nodes.iterrows():
            node_id = str(row['ID'])
            # Prikaži vozlišče in njegove starše
            self.show_node_and_parents(node_id)
    
    def show_all_nodes(self, node):
        """Prikaže vsa vozlišča v drevesu."""
        self.tree.item(node, open=True)
        for child in self.tree.get_children(node):
            self.show_all_nodes(child)
    
    def hide_all_nodes(self, node):
        """Skrije vsa vozlišča v drevesu."""
        self.tree.item(node, open=False)
        for child in self.tree.get_children(node):
            self.hide_all_nodes(child)
    
    def show_node_and_parents(self, node_id):
        """Prikaže vozlišče in vse njegove starše."""
        # Prikaži vozlišče
        self.tree.see(node_id)
        
        # Prikaži vse starše
        parent = self.tree.parent(node_id)
        while parent:
            self.tree.item(parent, open=True)
            parent = self.tree.parent(parent)

def main():
    app = TreeViewer()
    app.mainloop()

if __name__ == "__main__":
    main() 
import pandas as pd
import tkinter as tk
from tkinter import ttk

def load_data():
    # Preberemo vse potrebne CSV datoteke
    skills_df = pd.read_csv('skills_en.csv')
    hierarchy_df = pd.read_csv('skillsHierarchy_en.csv')
    relations_df = pd.read_csv('broaderRelationsSkillPillar_en.csv')
    skill_relations_df = pd.read_csv('skillSkillRelations_en.csv')
    
    return skills_df, hierarchy_df, relations_df, skill_relations_df

def build_skill_tree(skills_df, hierarchy_df, relations_df, skill_relations_df):
    # Ustvarimo slovar za hitrejše iskanje imen veščin po URI
    skill_names = {}
    
    # Zgradimo slovar imen iz hierarchy_df
    for _, row in hierarchy_df.iterrows():
        for i in range(4):
            uri = row[f'Level {i} URI']
            name = row[f'Level {i} preferred term']
            if pd.notna(uri) and pd.notna(name):
                skill_names[uri] = name
    
    # Dodamo imena iz skills_df
    for _, row in skills_df.iterrows():
        skill_names[row['conceptUri']] = row['preferredLabel']
    
    # Ustvarimo drevo
    tree = {}
    
    # Najprej dodamo vse korenske veščine iz hierarhije
    root_skills = hierarchy_df[hierarchy_df['Level 0 URI'].notna()]
    
    for _, skill in root_skills.iterrows():
        root_name = skill['Level 0 preferred term']
        if pd.notna(root_name):
            tree[root_name] = {}
    
    # Gradimo drevo na podlagi broader relations
    for _, relation in relations_df.iterrows():
        broader_uri = relation['broaderUri']
        narrower_uri = relation['conceptUri']
        
        if broader_uri in skill_names and narrower_uri in skill_names:
            broader_name = skill_names[broader_uri]
            narrower_name = skill_names[narrower_uri]
            
            # Poiščemo pravo mesto v drevesu
            current = tree
            path = find_skill_path(tree, broader_name)
            
            if path:
                # Sledimo poti do pravega mesta
                for step in path[:-1]:
                    current = current[step]
                # Dodamo novo veščino
                if path[-1] in current:
                    if narrower_name not in current[path[-1]]:
                        current[path[-1]][narrower_name] = {}
                else:
                    current[path[-1]] = {narrower_name: {}}
    
    # Dodamo posamezne veščine iz skillSkillRelations
    if 'broaderSkillUri' in skill_relations_df.columns and 'narrowerSkillUri' in skill_relations_df.columns:
        for _, relation in skill_relations_df.iterrows():
            broader_uri = relation['broaderSkillUri']
            narrower_uri = relation['narrowerSkillUri']
            
            if broader_uri in skill_names and narrower_uri in skill_names:
                broader_name = skill_names[broader_uri]
                narrower_name = skill_names[narrower_uri]
                
                # Poiščemo vse poti v drevesu, kjer se pojavi broader_name
                paths = find_all_paths(tree, broader_name)
                
                for path in paths:
                    # Sledimo poti do pravega mesta
                    current = tree
                    for step in path[:-1]:
                        current = current[step]
                    # Dodamo novo veščino
                    if path[-1] in current:
                        current[path[-1]][narrower_name] = {}
    
    return tree

def find_all_paths(tree, skill_name, current_path=None):
    if current_path is None:
        current_path = []
    
    paths = []
    
    if skill_name in tree:
        paths.append(current_path + [skill_name])
    
    for key, subtree in tree.items():
        if isinstance(subtree, dict):
            paths.extend(find_all_paths(subtree, skill_name, current_path + [key]))
    
    return paths

def find_skill_path(tree, skill_name, path=None):
    if path is None:
        path = []
    
    if skill_name in tree:
        return path + [skill_name]
    
    for key, subtree in tree.items():
        if isinstance(subtree, dict):
            new_path = find_skill_path(subtree, skill_name, path + [key])
            if new_path:
                return new_path
    
    return None

class SkillTreeGUI:
    def __init__(self, root, tree_data):
        self.root = root
        self.root.title("Skill Tree Viewer")
        
        # Ustvarimo glavni frame
        main_frame = ttk.Frame(root)
        main_frame.pack(fill='both', expand=True)
        
        # Dodamo drsnik
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side='right', fill='y')
        
        # Ustvarimo TreeView
        self.tree = ttk.Treeview(main_frame, yscrollcommand=scrollbar.set)
        self.tree.pack(fill='both', expand=True)
        
        # Povežemo drsnik z drevesom
        scrollbar.config(command=self.tree.yview)
        
        # Napolnimo drevo s podatki
        self.populate_tree(tree_data)
        
    def populate_tree(self, tree_data, parent=""):
        for skill, subtree in sorted(tree_data.items()):
            item = self.tree.insert(parent, 'end', text=skill)
            if isinstance(subtree, dict):
                self.populate_tree(subtree, item)

def main():
    # Naložimo podatke
    skills_df, hierarchy_df, relations_df, skill_relations_df = load_data()
    
    # Zgradimo drevo
    tree = build_skill_tree(skills_df, hierarchy_df, relations_df, skill_relations_df)
    
    # Ustvarimo GUI
    root = tk.Tk()
    root.geometry("800x600")  # Nastavimo začetno velikost okna
    app = SkillTreeGUI(root, tree)
    root.mainloop()

if __name__ == "__main__":
    main() 
import tkinter as tk
from tkinter import ttk, messagebox
import mysql.connector

# Nastavitve za bazo
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'root',
    'database': 'esco_db'
}

def fetch_data():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    # Pridobi ESCO veščine
    cursor.execute("SELECT conceptUri, preferredLabel FROM skills")
    skills = {uri: name for uri, name in cursor.fetchall()}
    # Pridobi UM veščine
    cursor.execute("SELECT conceptUri, preferredLabel FROM um_skills")
    um_skills = {uri: name for uri, name in cursor.fetchall()}
    # Pridobi UM relacije
    cursor.execute("SELECT source, target FROM um_skillskillrelations")
    um_rel = cursor.fetchall()
    conn.close()
    return skills, um_skills, um_rel

def build_tree(skills, um_skills, um_rel):
    tree = {name: {} for uri, name in skills.items()}
    um_skill_map = {uri: name for uri, name in um_skills.items()}
    rel_map = {}
    for parent, child in um_rel:
        if parent not in rel_map:
            rel_map[parent] = []
        rel_map[parent].append(child)
    if 'UM veščine' not in tree:
        tree['UM veščine'] = {}
    def find_node(tree, parent_uri, parent_name):
        if not isinstance(tree, dict):
            return None
        for key, subtree in tree.items():
            if key == parent_name:
                return subtree
            found = find_node(subtree, parent_uri, parent_name)
            if found:
                return found
        return None
    for parent_uri, children in rel_map.items():
        for child_uri in children:
            name = um_skill_map.get(child_uri, child_uri)
            parent_name = um_skill_map.get(parent_uri) or skills.get(parent_uri) or str(parent_uri)
            parent_node = find_node(tree, parent_uri, parent_name)
            if parent_node is not None:
                if name not in parent_node:
                    parent_node[name + ' [UM]'] = {'_is_um': True}
            else:
                if name + ' [UM]' not in tree['UM veščine']:
                    tree['UM veščine'][name + ' [UM]'] = {'_is_um': True}
    return tree

def insert_tree(tree, parent, treeview):
    for key, subtree in tree.items():
        tags = ()
        if isinstance(subtree, dict) and subtree.get('_is_um'):
            tags = ('um',)
        node_id = treeview.insert(parent, 'end', text=key, tags=tags)
        insert_tree({k: v for k, v in subtree.items() if k != '_is_um'}, node_id, treeview)

def search_tree(treeview, search_text):
    # Počisti prejšnje označbe
    for item in treeview.get_children(''):
        clear_highlight(treeview, item)
    found_items = []
    def search_node(item):
        text = treeview.item(item, 'text')
        if search_text.lower() in text.lower():
            treeview.see(item)
            treeview.selection_add(item)
            treeview.item(item, tags=treeview.item(item, 'tags') + ('highlight',))
            found_items.append(item)
        for child in treeview.get_children(item):
            search_node(child)
    for item in treeview.get_children(''):
        search_node(item)
    # Skoči do prvega zadetka
    if found_items:
        treeview.focus(found_items[0])
        treeview.selection_set(found_items[0])
        treeview.see(found_items[0])

def clear_highlight(treeview, item):
    tags = tuple(t for t in treeview.item(item, 'tags') if t not in ('highlight',))
    treeview.selection_remove(item)
    treeview.item(item, tags=tags)
    for child in treeview.get_children(item):
        clear_highlight(treeview, child)

def main():
    skills, um_skills, um_rel = fetch_data()
    tree = build_tree(skills, um_skills, um_rel)
    root = tk.Tk()
    root.title('Drevo veščin (ESCO + UM)')
    # Iskalno polje
    search_frame = tk.Frame(root)
    search_frame.pack(fill='x', padx=5, pady=5)
    search_var = tk.StringVar()
    search_entry = tk.Entry(search_frame, textvariable=search_var)
    search_entry.pack(side='left', fill='x', expand=True)
    def on_search():
        search_tree(treeview, search_var.get())
    search_btn = tk.Button(search_frame, text='Išči', command=on_search)
    search_btn.pack(side='left', padx=5)
    # Drevo
    treeview = ttk.Treeview(root)
    treeview.pack(fill='both', expand=True)
    # Označi zadetke z barvo in UM z drugo barvo
    style = ttk.Style()
    style.map('Treeview', background=[('selected', '#b3e5fc')])
    treeview.tag_configure('highlight', background='#ffe082')
    treeview.tag_configure('um', foreground='#1565c0', font=('Arial', 10, 'bold'))
    insert_tree(tree, '', treeview)
    root.mainloop()

if __name__ == '__main__':
    main() 
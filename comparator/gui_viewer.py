import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import csv
import os
from datetime import datetime
from comparator import compare_skill_labels, find_skills_file
from difflib import SequenceMatcher

def similar(a, b):
    """Izračuna podobnost med dvema nizoma."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

class ESCOComparatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ESCO Primerjava Veščin")
        self.root.geometry("1800x1000")
        
        # Nastavimo stil
        style = ttk.Style()
        style.configure("Added.TLabel", foreground="green")
        style.configure("Removed.TLabel", foreground="red")
        style.configure("Changed.TLabel", foreground="blue")
        style.configure("Match.Treeview.Cell", foreground="purple")
        style.configure("Custom.Treeview", rowheight=25)
        
        # Barve za različne stopnje ujemanja
        self.match_colors = {
            0.9: "#90EE90",  # Svetlo zelena - zelo dobro ujemanje
            0.7: "#FFD700",  # Rumena - dobro ujemanje
            0.5: "#FFA07A",  # Svetlo oranžna - zmerno ujemanje
        }
        
        # Spremenljivke
        self.dir1 = tk.StringVar(value="ESCO dataset - v1.0.7 - classification - en - csv")
        self.dir2 = tk.StringVar(value="ESCO dataset - v1.2.0 - classification - en - csv (3)")
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_table)
        
        self.um_skills = []  # Seznam UM veščin
        self.esco_skills = []  # Seznam ESCO veščin
        self.current_matches = []  # Seznam trenutnih ujemanj za razvrščanje
        self.skill_details = {}  # Slovar za podrobnosti o skillih
        
        # Slovarja za shranjevanje stanja checkboxov in radio buttonov
        self.checkbox_vars = {}
        self.radio_var = tk.StringVar()
        
        # Nastavimo, da popravi napako z width pri heading
        try:
            self.setup_gui()
            # Samodejno naložimo testni_um.csv
            self.load_default_um_skills()
        except Exception as e:
            print(f"Napaka pri inicializaciji GUI: {e}")
            # Poskusimo ponovno z drugim pristopom, če pride do napake z width
            if "unknown option \"-width\"" in str(e):
                print("Popravljam napako z width pri heading...")
                # To bo poskrbelo, da se bo setup_gui ponovno poklical
                self.setup_gui()
                self.load_default_um_skills()
        
    def create_tree_with_checkboxes(self, parent, columns, show='headings', **kwargs):
        """Ustvari Treeview z dodanim stolpcem za checkboxe in gumb za info."""
        # Dodamo stolpca za checkbox in info gumb na začetek
        all_columns = ('checkbox', 'info') + columns
        tree = ttk.Treeview(parent, columns=all_columns, show=show, **kwargs)
        
        # Nastavimo širino stolpca za checkbox in info
        tree.column('checkbox', width=30, anchor='center', stretch=False)
        tree.column('info', width=30, anchor='center', stretch=False)
        tree.heading('checkbox', text='✓')
        tree.heading('info', text='ℹ')
        
        # Nastavimo ostale stolpce
        for col in columns:
            tree.heading(col, text=col)
        
        return tree

    def create_tree_with_radiobuttons(self, parent, columns, show='headings', **kwargs):
        """Ustvari Treeview z dodanim stolpcem za radio buttone in gumb za info."""
        # Dodamo stolpca za radio button in info gumb na začetek
        all_columns = ('radio', 'info') + columns
        tree = ttk.Treeview(parent, columns=all_columns, show=show, **kwargs)
        
        # Nastavimo širino stolpca za radio button in info
        tree.column('radio', width=30, anchor='center', stretch=False)
        tree.column('info', width=30, anchor='center', stretch=False)
        tree.heading('radio', text='◉')
        tree.heading('info', text='ℹ')
        
        # Nastavimo ostale stolpce
        for col in columns:
            tree.heading(col, text=col)
        
        return tree

    def toggle_checkbox(self, event):
        """Upravlja klike na checkbox v drevesu."""
        tree = event.widget
        region = tree.identify_region(event.x, event.y)
        if region == "cell":
            column = tree.identify_column(event.x)
            if column == '#1':  # Checkbox stolpec
                item = tree.identify_row(event.y)
                if item in self.checkbox_vars:
                    self.checkbox_vars[item] = not self.checkbox_vars[item]
                    tree.set(item, 'checkbox', '☑' if self.checkbox_vars[item] else '☐')
            elif column == '#2':  # Info stolpec
                item = tree.identify_row(event.y)
                values = tree.item(item)['values']
                if values:
                    # Preverimo, od katerega drevesa je klik
                    if tree == self.um_tree:
                        if len(values) >= 3:
                            skill_name = values[2]  # Tretji element je ime veščine v um_tree
                            self.show_skill_info(skill_name)
                    elif tree == self.match_tree:
                        if len(values) >= 3:
                            skill_name = values[2]  # Tretji element je ime ESCO veščine v match_tree
                            self.show_skill_info(skill_name)

    def toggle_radio(self, event):
        """Upravlja klike na radio button in info gumb v drevesu."""
        tree = event.widget
        region = tree.identify_region(event.x, event.y)
        if region == "cell":
            column = tree.identify_column(event.x)
            if column == '#1':  # Radio button stolpec
                item = tree.identify_row(event.y)
                # Počistimo vse radio buttone
                for i in tree.get_children():
                    tree.set(i, 'radio', '○')
                # Nastavimo izbrani radio button
                tree.set(item, 'radio', '●')
                self.radio_var.set(item)
            elif column == '#2':  # Info stolpec
                item = tree.identify_row(event.y)
                values = tree.item(item)['values']
                if values and len(values) >= 3:  # Preveri, da imamo dovolj vrednosti
                    skill_id = values[2]  # Tretji element je URI veščine
                    self.show_skill_info(skill_id)

    def load_default_um_skills(self):
        """Naloži privzeto testni_um.csv datoteko."""
        default_file = "testni_um.csv"
        if os.path.exists(default_file):
            self.load_um_skills(default_file)
        else:
            print(f"Opozorilo: {default_file} ni bil najden v trenutnem direktoriju")

    def show_skill_info(self, skill_identifier):
        """Prikaže popup z informacijami o veščini."""
        # Najdemo podrobnosti o veščini
        skill_info = self.find_skill_details(skill_identifier)
        
        if not skill_info:
            messagebox.showinfo("Informacije o veščini", f"Ni podrobnosti za veščino: {skill_identifier}")
            return
            
        # Ustvarimo popup okno
        popup = tk.Toplevel(self.root)
        popup.title("Podrobnosti o veščini")
        popup.geometry("600x400")
        
        # Dodamo vsebino
        content_frame = ttk.Frame(popup, padding="10")
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Naslov
        ttk.Label(content_frame, text=skill_info.get('preferredLabel', 'Ni naslova'), 
                 font=('TkDefaultFont', 12, 'bold')).pack(anchor='w', pady=(0, 10))
        
        # URI
        uri_frame = ttk.Frame(content_frame)
        uri_frame.pack(fill=tk.X, pady=5)
        ttk.Label(uri_frame, text="URI:", width=15, anchor='e').pack(side=tk.LEFT)
        ttk.Label(uri_frame, text=skill_info.get('conceptUri', 'Ni URI')).pack(side=tk.LEFT, padx=5)
        
        # Tip
        type_frame = ttk.Frame(content_frame)
        type_frame.pack(fill=tk.X, pady=5)
        ttk.Label(type_frame, text="Tip:", width=15, anchor='e').pack(side=tk.LEFT)
        ttk.Label(type_frame, text=skill_info.get('skillType', 'Ni tipa')).pack(side=tk.LEFT, padx=5)
        
        # Status
        status_frame = ttk.Frame(content_frame)
        status_frame.pack(fill=tk.X, pady=5)
        ttk.Label(status_frame, text="Status:", width=15, anchor='e').pack(side=tk.LEFT)
        ttk.Label(status_frame, text=skill_info.get('status', 'Ni statusa')).pack(side=tk.LEFT, padx=5)
        
        # Opis - scrollable text
        desc_frame = ttk.LabelFrame(content_frame, text="Opis")
        desc_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        desc_scroll = ttk.Scrollbar(desc_frame)
        desc_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        desc_text = tk.Text(desc_frame, wrap=tk.WORD, yscrollcommand=desc_scroll.set)
        desc_text.pack(fill=tk.BOTH, expand=True)
        desc_text.insert(tk.END, skill_info.get('description', 'Ni opisa'))
        desc_text.config(state='disabled')  # Readonly
        
        desc_scroll.config(command=desc_text.yview)
        
        # Gumb za zapiranje
        ttk.Button(popup, text="Zapri", command=popup.destroy).pack(pady=10)

    def find_skill_details(self, identifier):
        """Najde podrobnosti o veščini po imenu ali URI."""
        # Dodamo izpis za diagnostiko
        print(f"Iščem podrobnosti za: {identifier}")
        
        # Če je to URI, najprej poskusimo neposredno iskanje
        # Najprej preverimo UM veščine
        for skill in self.um_skills:
            if skill['uri'] == identifier or skill['name'] == identifier:
                print(f"Najdeno v UM veščinah: {skill.get('name', 'Ni imena')}")
                return skill
                
        # Preverimo ESCO veščine
        for skill in self.esco_skills:
            if skill['uri'] == identifier or skill['label'] == identifier:
                print(f"Najdeno v ESCO veščinah: {skill.get('label', 'Ni oznake')}")
                return skill
        
        # Če ni bilo ujemanja s celotnim URI ali imenom, poskusimo delno ujemanje
        for skill in self.um_skills:
            if identifier in skill['uri'] or identifier in skill['name']:
                print(f"Delno ujemanje v UM veščinah: {skill.get('name', 'Ni imena')}")
                return skill
                
        for skill in self.esco_skills:
            if identifier in skill['uri'] or identifier in skill['label']:
                print(f"Delno ujemanje v ESCO veščinah: {skill.get('label', 'Ni oznake')}")
                return skill
            
        # Preverimo, če imamo že shranjene podrobnosti
        if identifier in self.skill_details:
            print(f"Najdeno v shranjenih podrobnostih")
            return self.skill_details[identifier]
            
        print(f"Ni najdenih podrobnosti za: {identifier}")
        return None

    def merge_selected_skills(self):
        """Združi izbrane veščine."""
        selected_um_skills = []
        selected_esco_skills = []
        
        # Zberemo vse izbrane UM veščine
        for item in self.um_tree.get_children():
            if self.checkbox_vars.get(item, False):
                values = self.um_tree.item(item)['values']
                if values and len(values) >= 3:
                    skill_name = values[2]  # Ime veščine
                    # Najdemo celoten skill objekt
                    skill_obj = None
                    for skill in self.um_skills:
                        if skill['name'] == skill_name:
                            skill_obj = skill
                            break
                    if skill_obj:        
                        selected_um_skills.append(skill_obj)
        
        # Zberemo vse izbrane ESCO veščine
        for item in self.match_tree.get_children():
            if self.checkbox_vars.get(item, False):
                values = self.match_tree.item(item)['values']
                if values and len(values) >= 3:
                    esco_name = values[2]  # ESCO veščina
                    # Najdemo celoten skill objekt
                    skill_obj = None
                    for skill in self.esco_skills:
                        if skill['label'] == esco_name:
                            skill_obj = skill
                            break
                    if skill_obj:
                        selected_esco_skills.append(skill_obj)
        
        # Prikazemo rezultat združevanja
        if not selected_um_skills or not selected_esco_skills:
            messagebox.showinfo("Združevanje", "Izberite vsaj eno UM veščino in eno ESCO veščino za združevanje.")
            return
        
        if len(selected_esco_skills) != 1:
            messagebox.showinfo("Združevanje", "Izberite natanko eno ESCO veščino za združevanje.")
            return
            
        esco_skill = selected_esco_skills[0]
        
        # Shranimo v revizija.csv
        self.save_to_revision_file(esco_skill, selected_um_skills)
        
        # Shranimo v backup.csv
        self.save_to_backup_file(esco_skill, selected_um_skills)
        
        # Odstranimo izbrane UM veščine iz seznama in dodamo v razrešeno.csv
        self.remove_um_skills_and_save_to_resolved(esco_skill, selected_um_skills)
        
        # Osvežimo prikaz
        self.reload_um_skills()
        
        # Sporočimo uporabniku
        messagebox.showinfo("Združevanje uspešno", 
                           f"ESCO veščina: {esco_skill['label']}\n"
                           f"je bila združena s {len(selected_um_skills)} UM veščinami in shranjena v revizija.csv in backup.csv.\n"
                           f"UM veščine so bile odstranjene iz seznama in dodane v razrešeno.csv.")
    
    def save_to_revision_file(self, esco_skill, um_skills):
        """Shrani ESCO veščino in pripadajoče UM veščine v revizija.csv"""
        file_exists = os.path.exists('revizija.csv')
        
        with open('revizija.csv', 'a', newline='', encoding='utf-8') as f:
            fieldnames = ['esco_uri', 'esco_label', 'um_uri', 'um_label']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            # Zapišemo glave, če datoteka še ne obstaja
            if not file_exists:
                writer.writeheader()
            
            # Zapišemo vsako kombinacijo ESCO veščine in UM veščine
            for um_skill in um_skills:
                writer.writerow({
                    'esco_uri': esco_skill['uri'],
                    'esco_label': esco_skill['label'],
                    'um_uri': um_skill['uri'],
                    'um_label': um_skill['name']
                })
    
    def save_to_backup_file(self, esco_skill, um_skills):
        """Shrani ESCO veščino in pripadajoče UM veščine v backup.csv"""
        file_exists = os.path.exists('backup.csv')
        
        with open('backup.csv', 'a', newline='', encoding='utf-8') as f:
            fieldnames = ['esco_uri', 'esco_label', 'um_uri', 'um_label', 'datum']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            # Zapišemo glave, če datoteka še ne obstaja
            if not file_exists:
                writer.writeheader()
            
            # Dodamo trenutni datum
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Zapišemo vsako kombinacijo ESCO veščine in UM veščine
            for um_skill in um_skills:
                writer.writerow({
                    'esco_uri': esco_skill['uri'],
                    'esco_label': esco_skill['label'],
                    'um_uri': um_skill['uri'],
                    'um_label': um_skill['name'],
                    'datum': current_date
                })
    
    def remove_um_skills_and_save_to_resolved(self, esco_skill, um_skills):
        """Odstrani UM veščine iz seznama in jih doda v razrešeno.csv"""
        # Dodamo v razrešeno.csv
        file_exists = os.path.exists('razrešeno.csv')
        
        with open('razrešeno.csv', 'a', newline='', encoding='utf-8') as f:
            fieldnames = ['um_uri', 'um_label', 'esco_uri', 'esco_label']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            # Zapišemo glave, če datoteka še ne obstaja
            if not file_exists:
                writer.writeheader()
            
            # Zapišemo vsako UM veščino s pripadajočo ESCO veščino
            for um_skill in um_skills:
                writer.writerow({
                    'um_uri': um_skill['uri'],
                    'um_label': um_skill['name'],
                    'esco_uri': esco_skill['uri'],
                    'esco_label': esco_skill['label']
                })
        
        # Odstranimo UM veščine iz seznama
        um_uris_to_remove = [um_skill['uri'] for um_skill in um_skills]
        self.um_skills = [skill for skill in self.um_skills 
                         if skill['uri'] not in um_uris_to_remove]
        
        # Shranimo posodobljen seznam UM veščin nazaj v datoteko
        if os.path.exists('testni_um.csv'):
            # Najprej preberemo originalne vrstice in headerje
            original_rows = []
            headers = []
            with open('testni_um.csv', 'r', encoding='utf-8') as original:
                reader = csv.reader(original)
                headers = next(reader)  # Pridobimo headerje
                for row in reader:
                    # Če uri ni med tistimi, ki jih bomo odstranili, dodamo vrstico
                    row_dict = {headers[i]: row[i] for i in range(len(headers))}
                    if row_dict.get('conceptUri', '') not in um_uris_to_remove:
                        original_rows.append(row)
            
            # Zdaj zapišemo posodobljene podatke
            with open('testni_um.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)  # Zapišemo headerje
                writer.writerows(original_rows)  # Zapišemo preostale vrstice
    
    def reload_um_skills(self):
        """Ponovno naloži UM veščine po spremembah."""
        # Počistimo obstoječe podatke v drevesu
        for item in self.um_tree.get_children():
            self.um_tree.delete(item)
        
        # Dodamo veščine iz posodobljenega seznama
        for skill in self.um_skills:
            item = self.um_tree.insert('', tk.END, values=('', 'ℹ', skill['name']))
            # Inicializiramo checkbox
            self.checkbox_vars[item] = False
            self.um_tree.set(item, 'checkbox', '☐')
        
        # Posodobimo ujemanja
        self.find_matches()

    def setup_gui(self):
        # Glavni horizontalni container
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True)
        
        # Levi del - UM veščine
        left_frame = ttk.LabelFrame(main_paned, text="UM Veščine", padding="5")
        
        # Gumb za nalaganje UM veščin
        button_frame = ttk.Frame(left_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(button_frame, text="Naloži testni_um.csv", command=self.load_um_skills).pack(side=tk.LEFT)
        
        # Treeview za UM veščine
        um_frame = ttk.Frame(left_frame)
        um_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Scrollbars za UM veščine
        um_scrollbar_y = ttk.Scrollbar(um_frame, orient=tk.VERTICAL)
        um_scrollbar_x = ttk.Scrollbar(um_frame, orient=tk.HORIZONTAL)
        
        self.um_tree = self.create_tree_with_checkboxes(
            um_frame, 
            columns=('name',),
            show='headings',
            style="Custom.Treeview",
            yscrollcommand=um_scrollbar_y.set,
            xscrollcommand=um_scrollbar_x.set
        )
        
        self.um_tree.heading('name', text='Ime veščine')
        self.um_tree.column('checkbox', width=30, anchor='center', stretch=False)
        self.um_tree.column('info', width=30, anchor='center', stretch=False)
        self.um_tree.column('name', width=350, minwidth=200)
        
        # Dodamo event binding za checkboxe
        self.um_tree.bind('<Button-1>', self.toggle_checkbox)
        
        um_scrollbar_y.config(command=self.um_tree.yview)
        um_scrollbar_x.config(command=self.um_tree.xview)
        
        self.um_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        um_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        um_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        main_paned.add(left_frame, weight=1)
        
        # Desni del - vertikalni container
        right_paned = ttk.PanedWindow(main_paned, orient=tk.VERTICAL)
        
        # Zgornji del - nastavitve in ujemajoče veščine
        top_frame = ttk.LabelFrame(right_paned, text="Nastavitve in ujemajoče veščine", padding="5")
        
        # Grid layout za nastavitve
        settings_frame = ttk.Frame(top_frame)
        settings_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(settings_frame, text="Prvi direktorij:").grid(row=0, column=0, sticky='e', padx=5)
        ttk.Entry(settings_frame, textvariable=self.dir1, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(settings_frame, text="Izberi", command=lambda: self.choose_directory(self.dir1)).grid(row=0, column=2, padx=5)
        
        ttk.Label(settings_frame, text="Drugi direktorij:").grid(row=1, column=0, sticky='e', padx=5)
        ttk.Entry(settings_frame, textvariable=self.dir2, width=50).grid(row=1, column=1, padx=5)
        ttk.Button(settings_frame, text="Izberi", command=lambda: self.choose_directory(self.dir2)).grid(row=1, column=2, padx=5)
        
        # Gumba za primerjaj in združi
        button_frame = ttk.Frame(settings_frame)
        button_frame.grid(row=0, column=3, rowspan=2, padx=20, sticky='ns')
        
        ttk.Button(button_frame, text="Primerjaj", command=self.compare_directories).pack(side=tk.TOP, pady=5)
        ttk.Button(button_frame, text="Združi izbrane", command=self.merge_selected_skills).pack(side=tk.TOP, pady=5)
        
        # Iskalno polje
        search_frame = ttk.Frame(settings_frame)
        search_frame.grid(row=2, column=0, columnspan=4, pady=10)
        ttk.Label(search_frame, text="Išči:").pack(side=tk.LEFT)
        ttk.Entry(search_frame, textvariable=self.search_var, width=50).pack(side=tk.LEFT, padx=5)
        
        # Gumbi za razvrščanje
        sort_frame = ttk.Frame(top_frame)
        sort_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(sort_frame, text="Razvrsti po:").pack(side=tk.LEFT, padx=5)
        ttk.Button(sort_frame, text="% Ujemanja ↓", 
                  command=lambda: self.sort_matches('similarity', reverse=True)).pack(side=tk.LEFT, padx=5)
        ttk.Button(sort_frame, text="% Ujemanja ↑", 
                  command=lambda: self.sort_matches('similarity', reverse=False)).pack(side=tk.LEFT, padx=5)
        ttk.Button(sort_frame, text="UM Veščini ↓", 
                  command=lambda: self.sort_matches('um_name', reverse=True)).pack(side=tk.LEFT, padx=5)
        ttk.Button(sort_frame, text="UM Veščini ↑", 
                  command=lambda: self.sort_matches('um_name', reverse=False)).pack(side=tk.LEFT, padx=5)
        
        # Okvir za ujemanja
        match_container = ttk.Frame(top_frame)
        match_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Treeview za ujemajoče veščine z checkboxi
        self.match_tree = self.create_tree_with_checkboxes(
            match_container,
            columns=('esco_name', 'similarity', 'um_name'),
            show='headings',
            style="Custom.Treeview"
        )
        
        # Nastavimo glave stolpcev
        self.match_tree.heading('esco_name', text='ESCO Veščina')
        self.match_tree.heading('similarity', text='Ujemanje')
        self.match_tree.heading('um_name', text='UM Veščina')
        
        # Nastavimo širine stolpcev
        self.match_tree.column('checkbox', width=30, anchor='center', stretch=False)
        self.match_tree.column('info', width=30, anchor='center', stretch=False)
        self.match_tree.column('esco_name', width=400, minwidth=200)
        self.match_tree.column('similarity', width=100, minwidth=80, anchor='center')
        self.match_tree.column('um_name', width=400, minwidth=200)
        
        # Dodamo event binding za checkboxe
        self.match_tree.bind('<Button-1>', self.toggle_checkbox)
        
        # Scrollbars za ujemanja
        match_scrollbar_y = ttk.Scrollbar(match_container, orient=tk.VERTICAL, command=self.match_tree.yview)
        match_scrollbar_x = ttk.Scrollbar(match_container, orient=tk.HORIZONTAL, command=self.match_tree.xview)
        
        self.match_tree.configure(yscrollcommand=match_scrollbar_y.set,
                                xscrollcommand=match_scrollbar_x.set)
        
        # Postavitev drevesa ujemanj in drsnikov
        self.match_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        match_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        match_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        right_paned.add(top_frame, weight=1)
        
        # Spodnji del - spremembe
        bottom_frame = ttk.LabelFrame(right_paned, text="Spremembe med verzijami", padding="5")
        
        # Statistika in legenda
        self.stats_frame = ttk.Frame(bottom_frame)
        self.stats_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.stats_label = ttk.Label(self.stats_frame, text="", font=('TkDefaultFont', 10, 'bold'))
        self.stats_label.pack(side=tk.LEFT)
        
        legend_frame = ttk.Frame(self.stats_frame)
        legend_frame.pack(side=tk.RIGHT)
        ttk.Label(legend_frame, text="● Dodano", style="Added.TLabel").pack(side=tk.LEFT, padx=10)
        ttk.Label(legend_frame, text="● Odstranjeno", style="Removed.TLabel").pack(side=tk.LEFT, padx=10)
        ttk.Label(legend_frame, text="● Spremenjeno", style="Changed.TLabel").pack(side=tk.LEFT, padx=10)
        ttk.Label(legend_frame, text="● Ujemanje", foreground="purple").pack(side=tk.LEFT, padx=10)
        
        # Okvir za spremembe
        changes_container = ttk.Frame(bottom_frame)
        changes_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Treeview za spremembe z radio buttoni
        self.tree = self.create_tree_with_radiobuttons(
            changes_container,
            columns=('uri', 'changes'),
            show='headings',
            style="Custom.Treeview"
        )
        
        self.tree.heading('radio', text='◉')
        self.tree.heading('info', text='ℹ')
        self.tree.heading('uri', text='Concept URI')
        self.tree.heading('changes', text='Spremembe')
        
        self.tree.column('radio', width=30, anchor='center', stretch=False)
        self.tree.column('info', width=30, anchor='center', stretch=False)
        self.tree.column('uri', width=400, minwidth=200)
        self.tree.column('changes', width=900, minwidth=400)
        
        # Dodamo event binding za radio buttone
        self.tree.bind('<Button-1>', self.toggle_radio)
        
        # Scrollbars za spremembe
        changes_scrollbar_y = ttk.Scrollbar(changes_container, orient=tk.VERTICAL, command=self.tree.yview)
        changes_scrollbar_x = ttk.Scrollbar(changes_container, orient=tk.HORIZONTAL, command=self.tree.xview)
        
        self.tree.configure(yscrollcommand=changes_scrollbar_y.set,
                          xscrollcommand=changes_scrollbar_x.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        changes_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        changes_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        right_paned.add(bottom_frame, weight=1)
        main_paned.add(right_paned, weight=2)
    
    def load_um_skills(self, filename=None):
        """Naloži UM veščine iz CSV datoteke."""
        if filename is None:
            filename = filedialog.askopenfilename(
                title="Izberi testni_um.csv",
                filetypes=[("CSV files", "*.csv")]
            )
        if not filename:
            return
            
        self.um_skills = []
        # Počistimo obstoječe podatke
        for item in self.um_tree.get_children():
            self.um_tree.delete(item)
            
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'preferredLabel' in row:
                        skill = {
                            'name': row['preferredLabel'],
                            'uri': row['conceptUri'],
                            'conceptType': row.get('conceptType', ''),
                            'skillType': row.get('skillType', ''),
                            'status': row.get('status', ''),
                            'description': row.get('description', '')
                        }
                        self.um_skills.append(skill)
                        # Dodamo prazne vrednosti za checkbox in info, nato ime veščine
                        item = self.um_tree.insert('', tk.END, values=('', 'ℹ', skill['name']))
                        # Inicializiramo checkbox
                        self.checkbox_vars[item] = False
                        self.um_tree.set(item, 'checkbox', '☐')
            
            self.find_matches()
        except Exception as e:
            messagebox.showerror("Napaka", f"Napaka pri branju datoteke: {str(e)}")
    
    def get_match_color(self, similarity):
        """Vrne barvo glede na stopnjo ujemanja."""
        similarity_float = float(similarity.strip('%')) / 100
        for threshold, color in sorted(self.match_colors.items(), reverse=True):
            if similarity_float >= threshold:
                return color
        return "white"
    
    def sort_matches(self, key, reverse=False):
        """Razvrsti ujemanja po izbranem ključu."""
        # Shranimo trenutno stanje checkboxov
        current_states = {}
        for item in self.match_tree.get_children():
            values = self.match_tree.item(item)['values']
            if values and len(values) > 2:
                current_states[values[2]] = self.match_tree.set(item, 'checkbox')  # Uporabimo ESCO ime kot ključ
        
        # Počistimo obstoječe podatke
        for item in self.match_tree.get_children():
            self.match_tree.delete(item)
        
        # Razvrsti ujemanja
        if key == 'similarity':
            self.current_matches.sort(key=lambda x: float(x[1].strip('%')), reverse=reverse)
        else:
            self.current_matches.sort(key=lambda x: x[2], reverse=reverse)
        
        # Ponovno prikaži razvrščena ujemanja in ohrani stanje checkboxov
        for esco_name, similarity, um_name in self.current_matches:
            item = self.match_tree.insert('', tk.END, values=('', 'ℹ', esco_name, similarity, um_name))
            # Ohrani prejšnje stanje checkboxa če obstaja, sicer nastavi na neoznačeno
            checkbox_state = current_states.get(esco_name, '☐')
            self.match_tree.set(item, 'checkbox', checkbox_state)
            self.checkbox_vars[item] = checkbox_state == '☑'
            self.match_tree.item(item, tags=(similarity,))
            
        # Nastavi barve
        for similarity in set(match[1] for match in self.current_matches):
            self.match_tree.tag_configure(similarity, background=self.get_match_color(similarity))
    
    def find_matches(self):
        """Poišče ujemanja med UM in ESCO veščinami."""
        # Počistimo obstoječe podatke
        for item in self.match_tree.get_children():
            self.match_tree.delete(item)
            
        if not self.um_skills or not self.esco_skills:
            return
            
        self.current_matches = []
        
        # Za vsako ESCO veščino poiščemo najboljše ujemanje
        for esco_skill in self.esco_skills:
            best_match = None
            best_similarity = 0
            
            for um_skill in self.um_skills:
                similarity = similar(esco_skill['label'], um_skill['name'])
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = um_skill
            
            if best_similarity >= 0.5:
                similarity_str = f"{best_similarity:.2%}"
                match_data = (esco_skill['label'], similarity_str, best_match['name'])
                self.current_matches.append(match_data)
                # Dodamo vrednosti za checkbox, info, ESCO veščino, ujemanje in UM veščino
                item = self.match_tree.insert('', tk.END, values=('', 'ℹ', esco_skill['label'], similarity_str, best_match['name']))
                # Inicializiramo checkbox
                self.checkbox_vars[item] = False
                self.match_tree.set(item, 'checkbox', '☐')
                self.match_tree.item(item, tags=(similarity_str,))
                
        # Nastavi barve za vse stopnje ujemanja
        for similarity in set(match[1] for match in self.current_matches):
            self.match_tree.tag_configure(similarity, background=self.get_match_color(similarity))
    
    def choose_directory(self, var):
        directory = filedialog.askdirectory(title="Izberi direktorij")
        if directory:
            var.set(directory)
    
    def format_change_details(self, change_details):
        if "Dodano:" in change_details:
            return change_details.replace("+ Dodano:", "● DODANO:")
        elif "Odstranjeno:" in change_details:
            return change_details.replace("- Odstranjeno:", "● ODSTRANJENO:")
        else:
            lines = change_details.split('\n')
            return "● SPREMENJENO:\n" + '\n'.join(
                line.replace("- Staro:", "Staro:").replace("+ Novo:", "Novo:")
                for line in lines
            )
    
    def compare_directories(self):
        """Primerja direktorije in prikaže rezultate."""
        dir1 = self.dir1.get()
        dir2 = self.dir2.get()
        
        if not dir1 or not dir2:
            messagebox.showerror("Napaka", "Prosim izberite oba direktorija")
            return
        
        # Poiščemo skills_en.csv datoteki
        file1 = find_skills_file(dir1)
        file2 = find_skills_file(dir2)
        
        if not file1 or not file2:
            messagebox.showerror("Napaka", "Datoteka skills_en.csv ni bila najdena v enem od direktorijev")
            return
        
        # Počistimo obstoječe podatke
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Naložimo ESCO veščine
        self.esco_skills = []
        # Naloži ESCO veščine iz obeh datotek (stare in nove verzije)
        skill_details = {}
        
        # Naložimo veščine iz prve datoteke
        with open(file1, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'preferredLabel' in row and 'conceptUri' in row:
                    uri = row['conceptUri']
                    skill_details[uri] = {
                        'uri': uri,
                        'label': row['preferredLabel'],
                        'conceptType': row.get('conceptType', ''),
                        'skillType': row.get('skillType', ''),
                        'status': row.get('status', ''),
                        'description': row.get('description', '')
                    }
        
        # Naložimo veščine iz druge datoteke
        with open(file2, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'preferredLabel' in row and 'conceptUri' in row:
                    uri = row['conceptUri']
                    skill = {
                        'uri': uri,
                        'label': row['preferredLabel'],
                        'conceptType': row.get('conceptType', ''),
                        'skillType': row.get('skillType', ''),
                        'status': row.get('status', ''),
                        'description': row.get('description', '')
                    }
                    self.esco_skills.append(skill)
                    skill_details[uri] = skill
        
        # Shranimo podrobnosti o veščinah
        self.skill_details = skill_details
        
        # Primerjamo in prikažemo rezultate
        differences = compare_skill_labels(file1, file2)
        
        added = 0
        removed = 0
        changed = 0
        
        for skill_id, change_details in differences:
            formatted_details = self.format_change_details(change_details)
            # Dodamo vrednosti za radio, info, URI in spremembe
            item = self.tree.insert('', tk.END, values=('', 'ℹ', skill_id, formatted_details))
            # Inicializiramo radio button
            self.tree.set(item, 'radio', '○')
            
            if "DODANO" in formatted_details:
                added += 1
            elif "ODSTRANJENO" in formatted_details:
                removed += 1
            else:
                changed += 1
        
        # Posodobimo statistiko
        total = len(self.tree.get_children())
        stats_text = f"Skupno število razlik: {total}\n"
        stats_text += f"Dodanih: {added} | Odstranjenih: {removed} | Spremenjenih: {changed}"
        self.stats_label.config(text=stats_text)
        
        # Poiščemo ujemanja
        self.find_matches()
    
    def filter_table(self, *args):
        search_term = self.search_var.get().lower()
        
        # Shranimo trenutno stanje checkboxov
        current_states = {}
        for item in self.match_tree.get_children():
            values = self.match_tree.item(item)['values']
            if values and len(values) > 2:
                current_states[values[2]] = self.match_tree.set(item, 'checkbox')  # Uporabimo ESCO ime kot ključ
        
        # Počistimo obstoječe podatke v match_tree
        for item in self.match_tree.get_children():
            self.match_tree.delete(item)
        
        # Filtriramo in prikažemo ujemanja
        filtered_matches = []
        for esco_name, similarity, um_name in self.current_matches:
            if (search_term in esco_name.lower() or 
                search_term in um_name.lower() or 
                search_term in similarity.lower()):
                filtered_matches.append((esco_name, similarity, um_name))
                item = self.match_tree.insert('', tk.END, values=('', 'ℹ', esco_name, similarity, um_name))
                # Ohrani prejšnje stanje checkboxa če obstaja, sicer nastavi na neoznačeno
                checkbox_state = current_states.get(esco_name, '☐')
                self.match_tree.set(item, 'checkbox', checkbox_state)
                self.checkbox_vars[item] = checkbox_state == '☑'
                self.match_tree.item(item, tags=(similarity,))
        
        # Nastavi barve za vse stopnje ujemanja
        for similarity in set(match[1] for match in filtered_matches):
            self.match_tree.tag_configure(similarity, background=self.get_match_color(similarity))
        
        # Počistimo obstoječe podatke v tree
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Ponovno naložimo podatke z filtrom za razlike
        dir1 = self.dir1.get()
        dir2 = self.dir2.get()
        
        if not dir1 or not dir2:
            return
        
        file1 = find_skills_file(dir1)
        file2 = find_skills_file(dir2)
        
        if not file1 or not file2:
            return
        
        differences = compare_skill_labels(file1, file2)
        
        added = 0
        removed = 0
        changed = 0
        
        # Filtriramo in prikažemo spremembe
        for skill_id, change_details in differences:
            if search_term in skill_id.lower() or search_term in change_details.lower():
                formatted_details = self.format_change_details(change_details)
                item = self.tree.insert('', tk.END, values=('', 'ℹ', skill_id, formatted_details))
                # Inicializiramo radio button
                self.tree.set(item, 'radio', '○')
                
                if "DODANO" in formatted_details:
                    added += 1
                elif "ODSTRANJENO" in formatted_details:
                    removed += 1
                else:
                    changed += 1
        
        # Posodobimo statistiko
        total = len(self.tree.get_children())
        stats_text = f"Prikazanih razlik: {total}\n"
        stats_text += f"Dodanih: {added} | Odstranjenih: {removed} | Spremenjenih: {changed}"
        self.stats_label.config(text=stats_text)

def main():
    root = tk.Tk()
    app = ESCOComparatorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 
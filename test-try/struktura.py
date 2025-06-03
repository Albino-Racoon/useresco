import csv

def build_tree():
    # Ustvarimo prazen slovar
    tree = {}
    
    # Preberemo CSV datoteko
    with open('skillsHierarchy_en.csv', 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        
        for row in reader:
            # Preverimo, če ima vrstica vsaj eno vrednost v stolpcih preferred term
            if any(row[f'Level {i} preferred term'] for i in range(4)):
                level0_term = row['Level 0 preferred term']
                level1_term = row['Level 1 preferred term']
                level2_term = row['Level 2 preferred term']
                level3_term = row['Level 3 preferred term']
                
                # Dodamo podatke v drevo samo če obstaja ime nivoja
                if level0_term:
                    if level0_term not in tree:
                        tree[level0_term] = {}
                        
                    if level1_term:
                        if level1_term not in tree[level0_term]:
                            tree[level0_term][level1_term] = {}
                            
                        if level2_term:
                            if level2_term not in tree[level0_term][level1_term]:
                                tree[level0_term][level1_term][level2_term] = {}
                                
                            if level3_term:
                                if level3_term not in tree[level0_term][level1_term][level2_term]:
                                    tree[level0_term][level1_term][level2_term][level3_term] = {}

    return tree

def print_tree(tree):
    # Izpišemo drevo z ustreznimi zamiki
    for i, level0_term in enumerate(sorted(tree.keys())):
        connector = "└──" if i == len(tree.keys()) - 1 else "├──"
        print(f"{connector} {level0_term}")
        
        if isinstance(tree[level0_term], dict):
            print_subtree(tree[level0_term], "    ")

def print_subtree(subtree, indent):
    items = sorted(subtree.keys())
    for i, term in enumerate(items):
        is_last = i == len(items) - 1
        connector = "└──" if is_last else "├──"
        print(f"{indent}{connector} {term}")
        
        if isinstance(subtree[term], dict):
            next_indent = indent + ("    " if is_last else "│   ")
            print_subtree(subtree[term], next_indent)

def main():
    tree = build_tree()
    print("Hierarhija spretnosti:")
    print_tree(tree)

if __name__ == "__main__":
    main()


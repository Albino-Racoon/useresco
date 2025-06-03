import os
import csv
import filecmp
from pathlib import Path
import argparse

def find_skills_file(directory):
    """
    Najde datoteko skills_en.csv v danem direktoriju ali njegovih poddirektorijih.
    """
    for root, dirs, files in os.walk(directory):
        if 'skills_en.csv' in files:
            return os.path.join(root, 'skills_en.csv')
    return None

def compare_skill_labels(file1, file2):
    """
    Primerja preferredLabel veščin med dvema CSV datotekama.
    """
    differences = []
    skills1 = {}
    skills2 = {}
    total_skills = 0
    changed_skills = 0
    
    print(f"Primerjam datoteki:\n{file1}\n{file2}\n")
    
    # Preberemo imena veščin iz prve datoteke
    with open(file1, 'r', encoding='utf-8', errors='replace') as f1:
        reader = csv.DictReader(f1)
        for row in reader:
            if 'preferredLabel' in row and 'conceptUri' in row:
                skill_id = row['conceptUri']
                skill_label = row['preferredLabel']
                skills1[skill_id] = skill_label
    
    # Preberemo imena veščin iz druge datoteke
    with open(file2, 'r', encoding='utf-8', errors='replace') as f2:
        reader = csv.DictReader(f2)
        for row in reader:
            if 'preferredLabel' in row and 'conceptUri' in row:
                skill_id = row['conceptUri']
                skill_label = row['preferredLabel']
                skills2[skill_id] = skill_label
    
    # Primerjamo veščine
    all_skills = set(skills1.keys()) | set(skills2.keys())
    total_skills = len(all_skills)
    
    if total_skills == 0:
        print("OPOZORILO: Ni bilo najdenih veščin v datotekah!")
        print("Preverite, da datoteki vsebujeta stolpca 'conceptUri' in 'preferredLabel'")
        return differences
    
    for skill_id in all_skills:
        label1 = skills1.get(skill_id, "NE OBSTAJA")
        label2 = skills2.get(skill_id, "NE OBSTAJA")
        
        if label1 != label2:
            changed_skills += 1
            if skill_id in skills1 and skill_id in skills2:
                differences.append((skill_id, f"  - Staro: {label1}\n  + Novo: {label2}"))
            elif skill_id in skills1:
                differences.append((skill_id, f"  - Odstranjeno: {label1}"))
            else:
                differences.append((skill_id, f"  + Dodano: {label2}"))
    
    print(f"\nStatistika primerjave:")
    print(f"Skupno število veščin: {total_skills}")
    print(f"Število spremenjenih veščin: {changed_skills}")
    print(f"Število nespremenjenih veščin: {total_skills - changed_skills}")
    if total_skills > 0:
        print(f"Odstotek spremenjenih veščin: {(changed_skills/total_skills)*100:.2f}%\n")
    
    return differences

def compare_directories(dir1, dir2, output_csv):
    """
    Primerja vse datoteke v dveh direktorijih in zapiše razlike v CSV.
    """
    if not os.path.exists(dir1) or not os.path.exists(dir2):
        print(f"Napaka: Eden od direktorijov ne obstaja: {dir1} ali {dir2}")
        return
    
    # Najdemo datoteki skills_en.csv
    file1 = find_skills_file(dir1)
    file2 = find_skills_file(dir2)
    
    if not file1 or not file2:
        print("Napaka: Datoteka skills_en.csv ni bila najdena v enem od direktorijev!")
        if not file1:
            print(f"Ni bilo najdeno v: {dir1}")
        if not file2:
            print(f"Ni bilo najdeno v: {dir2}")
        return
    
    with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(['Concept URI', 'Sprememba'])
        
        differences = compare_skill_labels(file1, file2)
        for skill_id, change_details in differences:
            csvwriter.writerow([skill_id, change_details])
    
    print(f"Primerjava končana. Poročilo shranjeno v {output_csv}")

def main():
    parser = argparse.ArgumentParser(description='Primerja datoteke med dvema direktorijema in ustvari CSV poročilo o razlikah.')
    parser.add_argument('dir1', help='Prvi direktorij za primerjavo')
    parser.add_argument('dir2', help='Drugi direktorij za primerjavo')
    parser.add_argument('--output', '-o', default='razlike.csv', help='Pot do izhodne CSV datoteke (privzeto: razlike.csv)')
    
    args = parser.parse_args()
    
    compare_directories(args.dir1, args.dir2, args.output)

if __name__ == "__main__":
    main() 
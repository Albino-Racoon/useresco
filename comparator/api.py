import os
import csv
import json
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from comparator import compare_skill_labels, find_skills_file
from difflib import SequenceMatcher

app = Flask(__name__, static_folder=".")
CORS(app)  # Omogoči CORS za API klice iz brskalnika

def similar(a, b):
    """Izračuna podobnost med dvema nizoma."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

# Globalne spremenljivke za shranjevanje stanja
um_skills = []
esco_skills = []
skill_details = {}
differences = []

@app.route('/')
def index():
    """Vrne osnovno HTML stran."""
    return send_from_directory('.', 'index.html')

@app.route('/api/um-skills', methods=['GET'])
def get_um_skills():
    """Vrne seznam UM veščin."""
    global um_skills
    return jsonify(um_skills)

@app.route('/api/um-skills', methods=['POST'])
def load_um_skills():
    """Naloži UM veščine iz datoteke."""
    global um_skills
    um_skills = []
    
    filename = request.json.get('filename', 'testni_um.csv')
    if not os.path.exists(filename):
        return jsonify({'error': f"Datoteka {filename} ne obstaja"}), 404
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'preferredLabel' in row and 'conceptUri' in row:
                    skill = {
                        'name': row['preferredLabel'],
                        'uri': row['conceptUri'],
                        'conceptType': row.get('conceptType', ''),
                        'skillType': row.get('skillType', ''),
                        'status': row.get('status', ''),
                        'description': row.get('description', '')
                    }
                    um_skills.append(skill)
        return jsonify({'success': True, 'count': len(um_skills)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/compare', methods=['POST'])
def compare_directories():
    """Primerja ESCO direktorije in vrne rezultate."""
    global esco_skills, differences, skill_details
    
    dir1 = request.json.get('dir1', 'ESCO dataset - v1.0.7 - classification - en - csv')
    dir2 = request.json.get('dir2', 'ESCO dataset - v1.2.0 - classification - en - csv (3)')
    
    # Poiščemo skills_en.csv datoteki
    file1 = find_skills_file(dir1)
    file2 = find_skills_file(dir2)
    
    if not file1 or not file2:
        return jsonify({'error': 'Datoteka skills_en.csv ni bila najdena v enem od direktorijev'}), 404
    
    # Naložimo ESCO veščine
    esco_skills = []
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
                    'description': row.get('description', ''),
                    'um_skills': []  # Za shranjevanje povezanih UM veščin
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
                    'description': row.get('description', ''),
                    'um_skills': []  # Za shranjevanje povezanih UM veščin
                }
                esco_skills.append(skill)
                skill_details[uri] = skill
    
    # Dodamo povezane UM veščine iz razrešeno.csv, če obstaja
    if os.path.exists('razrešeno.csv'):
        with open('razrešeno.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'esco_uri' in row and 'um_label' in row and row['esco_uri'] in skill_details:
                    skill_details[row['esco_uri']]['um_skills'].append(row['um_label'])
    
    # Primerjamo in prikažemo rezultate
    differences = compare_skill_labels(file1, file2)
    
    # Formatiramo razlike za JSON
    result_differences = []
    added = 0
    removed = 0
    changed = 0
    
    for skill_id, change_details in differences:
        difference_type = ''
        if "Dodano:" in change_details:
            difference_type = 'added'
            added += 1
        elif "Odstranjeno:" in change_details:
            difference_type = 'removed'
            removed += 1
        else:
            difference_type = 'changed'
            changed += 1
        
        result_differences.append({
            'uri': skill_id,
            'details': change_details,
            'type': difference_type
        })
    
    # Najdemo ujemanja med UM in ESCO veščinami
    matches = find_matches()
    
    return jsonify({
        'stats': {
            'total': len(result_differences),
            'added': added,
            'removed': removed,
            'changed': changed
        },
        'differences': result_differences,
        'matches': matches
    })

def find_matches():
    """Poišče ujemanja med UM in ESCO veščinami."""
    global um_skills, esco_skills
    
    if not um_skills or not esco_skills:
        return []
    
    matches = []
    
    # Za vsako ESCO veščino poiščemo najboljše ujemanje
    for esco_skill in esco_skills:
        best_match = None
        best_similarity = 0
        
        for um_skill in um_skills:
            similarity = similar(esco_skill['label'], um_skill['name'])
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = um_skill
        
        if best_similarity >= 0.5:
            similarity_str = f"{best_similarity:.2%}"
            match_color = get_match_color(best_similarity)
            
            matches.append({
                'esco_uri': esco_skill['uri'],
                'esco_label': esco_skill['label'],
                'um_uri': best_match['uri'],
                'um_label': best_match['name'],
                'similarity': similarity_str,
                'color': match_color
            })
    
    # Razvrsti ujemanja po ujemanju (padajoče)
    matches.sort(key=lambda x: float(x['similarity'].strip('%')), reverse=True)
    
    return matches

def get_match_color(similarity):
    """Vrne barvo glede na stopnjo ujemanja."""
    similarity_float = float(similarity) if isinstance(similarity, float) else float(similarity.strip('%')) / 100
    
    # Barve za različne stopnje ujemanja
    if similarity_float >= 0.9:
        return "#90EE90"  # Svetlo zelena - zelo dobro ujemanje
    elif similarity_float >= 0.7:
        return "#FFD700"  # Rumena - dobro ujemanje
    elif similarity_float >= 0.5:
        return "#FFA07A"  # Svetlo oranžna - zmerno ujemanje
    else:
        return "white"

@app.route('/api/skill-info/<path:skill_id>', methods=['GET'])
def get_skill_info(skill_id):
    """Vrne podrobnosti o veščini glede na ID."""
    global um_skills, esco_skills, skill_details
    
    # Najprej preverimo, če je to URI
    for skill in um_skills:
        if skill['uri'] == skill_id or skill['name'] == skill_id:
            return jsonify(skill)
    
    # Preverimo ESCO veščine
    for skill in esco_skills:
        if skill['uri'] == skill_id or skill['label'] == skill_id:
            return jsonify(skill)
    
    # Preverimo, če imamo že shranjene podrobnosti
    if skill_id in skill_details:
        return jsonify(skill_details[skill_id])
    
    return jsonify({'error': f'Veščina {skill_id} ni bila najdena'}), 404

@app.route('/api/merge', methods=['POST'])
def merge_skills():
    """Združi izbrane veščine."""
    global um_skills
    
    request_data = request.json
    esco_skill_uri = request_data.get('esco_uri')
    um_skill_uris = request_data.get('um_uris', [])
    
    if not esco_skill_uri or not um_skill_uris:
        return jsonify({'error': 'Manjkajoči podatki: esco_uri ali um_uris'}), 400
    
    # Poiščemo ESCO veščino
    esco_skill = None
    for skill in esco_skills:
        if skill['uri'] == esco_skill_uri:
            esco_skill = skill
            break
    
    if not esco_skill:
        return jsonify({'error': f'ESCO veščina z URI {esco_skill_uri} ni bila najdena'}), 404
    
    # Poiščemo UM veščine
    selected_um_skills = []
    for skill in um_skills:
        if skill['uri'] in um_skill_uris:
            selected_um_skills.append(skill)
    
    if not selected_um_skills:
        return jsonify({'error': 'Nobena od izbranih UM veščin ni bila najdena'}), 404
    
    # Shranimo v revizija.csv
    save_to_revision_file(esco_skill, selected_um_skills)
    
    # Shranimo v backup.csv
    save_to_backup_file(esco_skill, selected_um_skills)
    
    # Odstranimo izbrane UM veščine iz seznama in dodamo v razrešeno.csv
    remove_um_skills_and_save_to_resolved(esco_skill, selected_um_skills)
    
    # Posodobimo seznam UM veščin
    um_uris_to_remove = [um_skill['uri'] for um_skill in selected_um_skills]
    um_skills = [skill for skill in um_skills if skill['uri'] not in um_uris_to_remove]
    
    return jsonify({
        'success': True,
        'message': f"ESCO veščina: {esco_skill['label']} je bila združena s {len(selected_um_skills)} UM veščinami"
    })

def save_to_revision_file(esco_skill, um_skills):
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

def save_to_backup_file(esco_skill, um_skills):
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

def remove_um_skills_and_save_to_resolved(esco_skill, um_skills):
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
    
    # Posodobimo skills_en.csv, če obstaja, z dodanimi UM veščinami
    update_skills_en_with_um_names(esco_skill, um_skills)
    
    # Posodobimo testni_um.csv
    if os.path.exists('testni_um.csv'):
        um_uris_to_remove = [um_skill['uri'] for um_skill in um_skills]
        
        # Preberemo originalne vrstice in headerje
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
        
        # Zapišemo posodobljene podatke
        with open('testni_um.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)  # Zapišemo headerje
            writer.writerows(original_rows)  # Zapišemo preostale vrstice

def update_skills_en_with_um_names(esco_skill, um_skills):
    """Posodobi skills_en.csv z um imeni za iskanje."""
    dir2 = 'ESCO dataset - v1.2.0 - classification - en - csv (3)'
    file2 = find_skills_file(dir2)
    
    if not file2 or not os.path.exists(file2):
        return
    
    temp_file = file2 + '.temp'
    esco_uri = esco_skill['uri']
    um_names = [skill['name'] for skill in um_skills]
    
    # Preberemo datoteko in posodobimo
    headers = []
    updated = False
    
    with open(file2, 'r', encoding='utf-8') as input_file, \
         open(temp_file, 'w', newline='', encoding='utf-8') as output_file:
        
        reader = csv.reader(input_file)
        writer = csv.writer(output_file)
        
        headers = next(reader)
        
        # Preverimo, če že imamo stolpec za um_names, če ne ga dodamo
        if 'um_names' not in headers:
            headers.append('um_names')
            
        writer.writerow(headers)
        um_names_index = headers.index('um_names')
        
        for row in reader:
            # Razširimo vrstico, če je potrebno
            while len(row) < len(headers):
                row.append('')
                
            # Če gre za iskano ESCO veščino, dodamo UM imena
            if row[headers.index('conceptUri')] == esco_uri:
                existing_um_names = row[um_names_index].split('|') if row[um_names_index] else []
                existing_um_names.extend(um_names)
                # Odstrani duplikate in prazne vnose
                existing_um_names = list(set(filter(None, existing_um_names)))
                row[um_names_index] = '|'.join(existing_um_names)
                updated = True
                
            writer.writerow(row)
    
    # Zamenjamo datoteko, če je bila posodobljena
    if updated:
        os.replace(temp_file, file2)
    else:
        os.remove(temp_file)

@app.route('/api/search', methods=['GET'])
def search_skills():
    """Išče po veščinah (po imenu ali UM imenu)."""
    global esco_skills, skill_details
    
    search_term = request.args.get('q', '').lower()
    if not search_term:
        return jsonify([])
    
    print(f"Iskanje po izrazu: '{search_term}'")
    results = []
    
    # Poiščemo skills_en.csv datoteko
    dir2 = 'ESCO dataset - v1.2.0 - classification - en - csv (3)'
    file2 = find_skills_file(dir2)
    
    if not file2 or not os.path.exists(file2):
        print("Datoteka skills_en.csv ni bila najdena, iščemo po naloženih veščinah")
        # Če datoteke ni, iščemo samo po naloženih veščinah
        for skill in esco_skills:
            if search_term in skill['label'].lower():
                results.append({
                    'uri': skill['uri'],
                    'label': skill['label'],
                    'match_type': 'original_name'
                })
        return jsonify(results)
    
    try:
        # Iščemo po originalni datoteki, kjer imamo um_names stolpec
        with open(file2, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'preferredLabel' in row and search_term in row['preferredLabel'].lower():
                    results.append({
                        'uri': row['conceptUri'],
                        'label': row['preferredLabel'],
                        'match_type': 'original_name'
                    })
                
                # Iščemo tudi po um_names, če obstajajo
                if 'um_names' in row and row['um_names']:
                    um_names = row['um_names'].split('|')
                    for um_name in um_names:
                        if search_term in um_name.lower():
                            results.append({
                                'uri': row['conceptUri'],
                                'label': row['preferredLabel'],
                                'match_type': 'um_name',
                                'um_name': um_name
                            })
    except Exception as e:
        print(f"Napaka pri iskanju: {str(e)}")
        # Če pride do napake, vrnemo prazen seznam
        return jsonify([])
    
    print(f"Najdeno {len(results)} rezultatov")
    return jsonify(results)

@app.route('/api/confirm', methods=['POST'])
def confirm_um_mappings():
    """Potrdi mappinge UM veščin."""
    dir2 = 'ESCO dataset - v1.2.0 - classification - en - csv (3)'
    file2 = find_skills_file(dir2)
    
    if not file2 or not os.path.exists(file2):
        print(f"Datoteka skills_en.csv ni bila najdena v direktoriju: {dir2}")
        return jsonify({'success': False, 'message': 'skills_en.csv datoteka ni bila najdena'}), 404
    
    print(f"Potrjevanje in dodajanje UM veščin v datoteko: {file2}")
    
    # Preberemo razrešene UM veščine iz razrešeno.csv
    resolved_mappings = {}
    if os.path.exists('razrešeno.csv'):
        try:
            with open('razrešeno.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    esco_uri = row.get('esco_uri')
                    um_label = row.get('um_label')
                    if esco_uri and um_label:
                        if esco_uri not in resolved_mappings:
                            resolved_mappings[esco_uri] = []
                        resolved_mappings[esco_uri].append(um_label)
        except Exception as e:
            print(f"Napaka pri branju razrešeno.csv: {str(e)}")
            return jsonify({'success': False, 'message': f'Napaka pri branju razrešeno.csv: {str(e)}'}), 500
    else:
        print("Datoteka razrešeno.csv ne obstaja")
        return jsonify({'success': False, 'message': 'Ni najdenih UM veščin za dodajanje (razrešeno.csv ne obstaja)'}), 400
    
    if not resolved_mappings:
        print("Ni najdenih povezav med UM in ESCO veščinami v razrešeno.csv")
        return jsonify({'success': False, 'message': 'Ni najdenih UM veščin za dodajanje'}), 400
    
    print(f"Najdenih {len(resolved_mappings)} ESCO veščin z UM povezavami")
    
    # Posodobimo skills_en.csv z UM imeni
    temp_file = file2 + '.temp'
    updated = False
    
    try:
        with open(file2, 'r', encoding='utf-8') as input_file, \
             open(temp_file, 'w', newline='', encoding='utf-8') as output_file:
            
            reader = csv.reader(input_file)
            writer = csv.writer(output_file)
            
            # Preberemo headerje
            headers = next(reader)
            
            # Preverimo, če že imamo stolpec za um_names, če ne ga dodamo
            if 'um_names' not in headers:
                headers.append('um_names')
                print("Dodan nov stolpec 'um_names' v datoteko")
                
            writer.writerow(headers)
            um_names_index = headers.index('um_names')
            concept_uri_index = headers.index('conceptUri')
            
            # Števci za statistiko
            processed = 0
            updated_count = 0
            
            for row in reader:
                processed += 1
                # Razširimo vrstico, če je potrebno
                while len(row) < len(headers):
                    row.append('')
                    
                # Če imamo mappinge za to veščino, jih dodamo
                esco_uri = row[concept_uri_index]
                if esco_uri in resolved_mappings:
                    um_names = resolved_mappings[esco_uri]
                    existing_um_names = row[um_names_index].split('|') if row[um_names_index] else []
                    existing_um_names.extend(um_names)
                    # Odstrani duplikate in prazne vnose
                    existing_um_names = list(set(filter(None, existing_um_names)))
                    row[um_names_index] = '|'.join(existing_um_names)
                    updated = True
                    updated_count += 1
                    
                writer.writerow(row)
                
                # Izpišemo napredek vsakih 1000 vrstic
                if processed % 1000 == 0:
                    print(f"Obdelanih {processed} vrstic, posodobljenih {updated_count}")
        
        # Zamenjamo datoteko, če je bila posodobljena
        if updated:
            os.replace(temp_file, file2)
            print(f"Uspešno posodobljenih {updated_count} veščin v skills_en.csv")
            return jsonify({'success': True, 'message': f'UM veščine so bile uspešno dodane v {updated_count} ESCO veščin'})
        else:
            os.remove(temp_file)
            print("Ni bilo posodobitev v skills_en.csv")
            return jsonify({'success': False, 'message': 'Ni bilo najdenih novih UM veščin za dodajanje'})
    except Exception as e:
        print(f"Napaka pri posodabljanju skills_en.csv: {str(e)}")
        # Če pride do napake, poskusimo počistiti temp datoteko
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass
        return jsonify({'success': False, 'message': f'Napaka pri posodabljanju datoteke: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000) 
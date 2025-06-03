import mysql.connector
import pandas as pd
import numpy as np
from pathlib import Path
import ast
import os

def connect_to_db():
    """Vzpostavi povezavo z bazo podatkov."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "esco"),
        password=os.getenv("DB_PASSWORD", "esco123"),
        database=os.getenv("DB_NAME", "esco"),
        port=int(os.getenv("DB_PORT", 3306))
    )

def get_table_data(connection, table_name):
    """Pridobi podatke iz tabele."""
    query = f"SELECT * FROM {table_name}"
    return pd.read_sql(query, connection)

def safe_eval(x):
    """Varno ovrednoti string kot seznam."""
    if pd.isna(x) or not x or str(x).strip() in ['', '[]']:
        return []
    if isinstance(x, list):
        return x
    try:
        result = ast.literal_eval(str(x))
        return result if isinstance(result, list) else []
    except:
        return []

def process_hierarchy(hierarchy_df, skills_df, broader_relations_df, skill_relations_df):
    """Procesira hierarhijo in doda vse možne podatke."""
    # Določi maksimalno število nivojev
    max_levels = 4  # Level 0 do Level 3
    
    # Ustvari seznam vseh vrstic z dodanim nivojem
    rows = []
    
    # Najprej dodaj hierarhična vozlišča
    for _, row in hierarchy_df.iterrows():
        for level in range(max_levels):
            uri = row[f'Level {level} URI']
            name = row[f'Level {level} preferred term']
            if pd.notna(uri) and pd.notna(name):
                # Določi parent URI (če ni prvi nivo)
                parent_uri = row[f'Level {level-1} URI'] if level > 0 else None
                
                # Pridobi broader in narrower relacije
                broader = broader_relations_df[broader_relations_df['conceptUri'] == uri]['broaderUri'].tolist()
                narrower = broader_relations_df[broader_relations_df['broaderUri'] == uri]['conceptUri'].tolist()
                
                # Pridobi skill-skill relacije
                broader_skills = skill_relations_df[skill_relations_df['narrowerSkillUri'] == uri]['broaderSkillUri'].tolist()
                narrower_skills = skill_relations_df[skill_relations_df['broaderSkillUri'] == uri]['narrowerSkillUri'].tolist()
                
                # Pridobi dodatne podatke iz skills tabele
                skill_data = skills_df[skills_df['conceptUri'] == uri].iloc[0] if len(skills_df[skills_df['conceptUri'] == uri]) > 0 else pd.Series()
                
                rows.append({
                    'ID': len(rows) + 1,
                    'tip': 'hierarchy',
                    'nivo_indentacije': level,
                    'parent_uri': parent_uri,
                    'uri': uri,
                    'ime': name,
                    'preferredLabel': skill_data.get('preferredLabel', name),
                    'altLabels': skill_data.get('altLabels', ''),
                    'description': skill_data.get('description', ''),
                    'scopeNote': skill_data.get('scopeNote', ''),
                    'broader_relations': broader,
                    'narrower_relations': narrower,
                    'broader_skills': broader_skills,
                    'narrower_skills': narrower_skills,
                    'reusability': skill_data.get('reusability', ''),
                    'regulatedProfession': skill_data.get('regulatedProfession', ''),
                    'reuseLevel': skill_data.get('reuseLevel', '')
                })
    
    # Dodaj še vse veščine, ki niso v hierarhiji
    for _, skill in skills_df.iterrows():
        if skill['conceptUri'] not in [row['uri'] for row in rows]:
            # Poišči nadrejeni URI iz broader_relations
            parent_uris = broader_relations_df[broader_relations_df['conceptUri'] == skill['conceptUri']]['broaderUri'].tolist()
            parent_uri = parent_uris[0] if parent_uris else None
            
            # Določi nivo indentacije (en nivo globlje od starša)
            parent_level = -1
            if parent_uri:
                parent_rows = [r for r in rows if r['uri'] == parent_uri]
                if parent_rows:
                    parent_level = parent_rows[0]['nivo_indentacije']
            
            skill_level = parent_level + 1 if parent_level >= 0 else max_levels
            
            # Pridobi broader in narrower relacije
            broader = broader_relations_df[broader_relations_df['conceptUri'] == skill['conceptUri']]['broaderUri'].tolist()
            narrower = broader_relations_df[broader_relations_df['broaderUri'] == skill['conceptUri']]['conceptUri'].tolist()
            
            # Pridobi skill-skill relacije
            broader_skills = skill_relations_df[skill_relations_df['narrowerSkillUri'] == skill['conceptUri']]['broaderSkillUri'].tolist()
            narrower_skills = skill_relations_df[skill_relations_df['broaderSkillUri'] == skill['conceptUri']]['narrowerSkillUri'].tolist()
            
            rows.append({
                'ID': len(rows) + 1,
                'tip': 'skill',
                'nivo_indentacije': skill_level,
                'parent_uri': parent_uri,
                'uri': skill['conceptUri'],
                'ime': skill['preferredLabel'],
                'preferredLabel': skill['preferredLabel'],
                'altLabels': skill['altLabels'],
                'description': skill['description'],
                'scopeNote': skill['scopeNote'],
                'broader_relations': broader,
                'narrower_relations': narrower,
                'broader_skills': broader_skills,
                'narrower_skills': narrower_skills,
                'reusability': skill.get('reusability', ''),
                'regulatedProfession': skill.get('regulatedProfession', ''),
                'reuseLevel': skill.get('reuseLevel', '')
            })
    
    return pd.DataFrame(rows)

def main():
    """Glavna funkcija za izvoz podatkov."""
    try:
        print("Vzpostavljam povezavo z bazo podatkov...")
        connection = connect_to_db()
        
        print("Pridobivam podatke iz tabel...")
        hierarchy_df = get_table_data(connection, 'skills_hierarchy')
        skills_df = get_table_data(connection, 'skills')
        broader_relations_df = get_table_data(connection, 'broader_relations')
        skill_relations_df = get_table_data(connection, 'skill_skill_relations')
        
        print("Procesiram podatke...")
        result_df = process_hierarchy(hierarchy_df, skills_df, broader_relations_df, skill_relations_df)
        
        print("Shranjujem podatke v CSV...")
        output_file = Path("drevo.csv")
        
        # Pretvori sezname v string pred shranjevanjem
        list_columns = ['broader_relations', 'narrower_relations', 'broader_skills', 'narrower_skills']
        for col in list_columns:
            result_df[col] = result_df[col].apply(str)
        
        # Zapolni manjkajoče vrednosti
        result_df = result_df.fillna('')
        
        # Shrani v CSV
        result_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        print(f"Podatki uspešno izvoženi v {output_file.absolute()}")
        print(f"Število vrstic: {len(result_df)}")
        print("\nStruktura podatkov:")
        print(result_df.info())
        
    except Exception as e:
        print(f"Napaka: {e}")
    finally:
        if 'connection' in locals():
            connection.close()
            print("\nPovezava z bazo zaprta.")

if __name__ == "__main__":
    main() 
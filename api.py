import os
from fastapi import UploadFile, File, HTTPException

@app.post("/save_um_data")
async def save_um_data(
    skills_file: UploadFile = File(...),
    relations_file: UploadFile = File(...)
):
    try:
        # Preveri če mapa obstaja
        if not os.path.exists('static/um_csv'):
            os.makedirs('static/um_csv')
        
        # Shrani skills
        skills_path = os.path.join('static/um_csv', 'um_skills.csv')
        if not os.path.exists(skills_path):
            # Če datoteka ne obstaja, ustvari z glavo
            with open(skills_path, 'w', newline='', encoding='utf-8') as f:
                f.write('conceptType,conceptUri,skillType,reuseLevel,preferredLabel,altLabels,hiddenLabels,status,modifiedDate,scopeNote,definition,inScheme,description\n')
        
        # Dodaj novo vrstico
        skills_content = await skills_file.read()
        with open(skills_path, 'a', newline='', encoding='utf-8') as f:
            f.write(skills_content.decode('utf-8'))
        
        # Shrani relacije
        relations_path = os.path.join('static/um_csv', 'um_SkillSkillRelations.csv')
        if not os.path.exists(relations_path):
            # Če datoteka ne obstaja, ustvari z glavo
            with open(relations_path, 'w', newline='', encoding='utf-8') as f:
                f.write('parent,child\n')
        
        # Dodaj novo vrstico
        relations_content = await relations_file.read()
        with open(relations_path, 'a', newline='', encoding='utf-8') as f:
            f.write(relations_content.decode('utf-8'))
        
        return {"success": True}
    except Exception as e:
        print(f"Napaka pri shranjevanju: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 
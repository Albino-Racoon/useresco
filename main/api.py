from fastapi import FastAPI, Query, File, UploadFile, Form, Request, HTTPException, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
import pandas as pd
from typing import Dict, List, Optional
import uvicorn
import os
import tempfile
import shutil
import logging
from werkzeug.utils import secure_filename
import threading
import sys
import jwt
from datetime import datetime, timedelta
import json
from collections import OrderedDict

# Nastavitev beleženja
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('esco_api.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Konfiguracija
UPLOAD_FOLDER = tempfile.gettempdir()
MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500 MB
ALLOWED_EXTENSIONS = {'zip', 'csv'}

# Konfiguracija za JWT
SECRET_KEY = "your-secret-key-here"  # V produkciji uporabite varno skrito ključ
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Inicializacija za hashiranje gesel
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title="Skills Tree API")

# Dodamo CORS middleware za dostop iz spletne aplikacije
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Spremenimo pot do statičnih datotek
app.mount("/static", StaticFiles(directory="static"), name="static")

# Globalne spremenljivke za shranjevanje podatkov
skill_tree = {}
skill_names = {}

# Globalne spremenljivke za sledenje procesom uvoza
import threading
active_imports_lock = threading.Lock()
active_imports_count = 0
MAX_CONCURRENT_IMPORTS = 2  # Največ sočasnih uvozov

# OAuth2 shema
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Neveljavne avtentikacijske podatke",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.JWTError:
        raise credentials_exception
        
    # Pridobi uporabnika iz baze
    try:
        importer_path = os.path.join(os.path.dirname(__file__), 'static')
        if importer_path not in sys.path:
            sys.path.insert(0, importer_path)
        
        from esco_importer import EscoImporter
        importer = EscoImporter(
            host="clp6z.h.filess.io",
            port=61002,
            user="MYESCO_wentkeepor",
            password="e32389bcc9d0a76b5ba7c4150537fa9efd478362",
            database="MYESCO_wentkeepor"
        )
        
        if not importer.connect():
            raise HTTPException(status_code=500, detail="Napaka pri povezavi z bazo")
            
        try:
            importer.cursor.execute("SELECT username, role FROM users WHERE username = %s", (username,))
            user = importer.cursor.fetchone()
            
            if user is None:
                raise credentials_exception
                
            return {"username": user[0], "role": user[1]}
            
        finally:
            importer.disconnect()
            
    except Exception as e:
        logger.error(f"Napaka pri pridobivanju uporabnika: {e}")
        raise HTTPException(status_code=500, detail="Napaka pri pridobivanju uporabnika")

async def get_current_active_user(current_user: dict = Depends(get_current_user)):
    return current_user

def check_admin_access(current_user: dict = Depends(get_current_active_user)):
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Nimate pravic za to akcijo"
        )
    return current_user

@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        importer_path = os.path.join(os.path.dirname(__file__), 'static')
        if importer_path not in sys.path:
            sys.path.insert(0, importer_path)
        
        from esco_importer import EscoImporter
        importer = EscoImporter(
            host="clp6z.h.filess.io",
            port=61002,
            user="MYESCO_wentkeepor",
            password="e32389bcc9d0a76b5ba7c4150537fa9efd478362",
            database="MYESCO_wentkeepor"
        )
        
        if not importer.connect():
            return {"success": False, "message": "Napaka pri povezavi z bazo"}
            
        try:
            importer.cursor.execute("SELECT username, password, role FROM users WHERE username = %s", (form_data.username,))
            user = importer.cursor.fetchone()
            
            if user is None or not verify_password(form_data.password, user[1]):
                return {"success": False, "message": "Napačno uporabniško ime ali geslo"}
            
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": user[0]}, expires_delta=access_token_expires
            )
            
            return {
                "success": True,
                "access_token": access_token,
                "token_type": "bearer",
                "user": {"username": user[0], "role": user[2]}
            }
            
        finally:
            importer.disconnect()
            
    except Exception as e:
        logger.error(f"Napaka pri prijavi: {e}")
        return {"success": False, "message": "Napaka pri prijavi"}

@app.post("/register")
async def register(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        importer_path = os.path.join(os.path.dirname(__file__), 'static')
        if importer_path not in sys.path:
            sys.path.insert(0, importer_path)
        
        from esco_importer import EscoImporter
        importer = EscoImporter(
            host="clp6z.h.filess.io",
            port=61002,
            user="MYESCO_wentkeepor",
            password="e32389bcc9d0a76b5ba7c4150537fa9efd478362",
            database="MYESCO_wentkeepor"
        )
        
        if not importer.connect():
            return {"success": False, "message": "Napaka pri povezavi z bazo"}
            
        try:
            # Preveri, če uporabnik že obstaja
            importer.cursor.execute("SELECT username FROM users WHERE username = %s", (form_data.username,))
            if importer.cursor.fetchone():
                return {"success": False, "message": "Uporabniško ime že obstaja"}
            
            # Ustvari novega uporabnika
            hashed_password = get_password_hash(form_data.password)
            importer.cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (%s, %s, 'user')",
                (form_data.username, hashed_password)
            )
            importer.connection.commit()
            
            return {"success": True, "message": "Uporabnik uspešno registriran"}
            
        finally:
            importer.disconnect()
            
    except Exception as e:
        logger.error(f"Napaka pri registraciji: {e}")
        return {"success": False, "message": "Napaka pri registraciji"}

@app.get("/login.html", response_class=HTMLResponse)
async def get_login_page():
    """Vrne prijavno stran."""
    with open("main/static/login.html", encoding="utf-8") as f:
        return f.read()

def allowed_file(filename):
    """Preveri, ali je končnica datoteke dovoljena."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_data():
    """Naloži podatke iz CSV datotek in zgradi drevo. Če CSV-ji manjkajo, izpiše opozorilo in pusti prazno drevo."""
    global skill_tree, skill_names
    try:
        # Popravimo poti do CSV datotek
        skills_df = pd.read_csv('../esco/skills_en.csv')
        hierarchy_df = pd.read_csv('../esco/skillsHierarchy_en.csv')
        relations_df = pd.read_csv('../esco/broaderRelationsSkillPillar_en.csv')
        skill_relations_df = pd.read_csv('../esco/skillSkillRelations_en.csv')
        print("Uspešno naložene vse CSV datoteke")
    except FileNotFoundError as e:
        print(f"OPOZORILO: CSV datoteke niso najdene: {e}. Drevo bo prazno, endpointi /tree, /search, /subtree, /stats ne bodo delovali.")
        skill_tree = {}
        skill_names = {}
        return
    # Zgradimo slovar imen
    for _, row in hierarchy_df.iterrows():
        for i in range(4):
            uri = row[f'Level {i} URI']
            name = row[f'Level {i} preferred term']
            if pd.notna(uri) and pd.notna(name):
                skill_names[uri] = name
    for _, row in skills_df.iterrows():
        skill_names[row['conceptUri']] = row['preferredLabel']
    # Zgradimo drevo
    skill_tree = build_skill_tree(skills_df, hierarchy_df, relations_df, skill_relations_df)

def build_skill_tree(skills_df, hierarchy_df, relations_df, skill_relations_df):
    """Zgradi drevo veščin iz podatkovnih okvirjev."""
    tree = {}
    
    # Dodamo korenske veščine
    root_skills = hierarchy_df[hierarchy_df['Level 0 URI'].notna()]
    for _, skill in root_skills.iterrows():
        root_name = skill['Level 0 preferred term']
        if pd.notna(root_name):
            tree[root_name] = {}
    
    # Dodamo hierarhijo
    for _, row in hierarchy_df.iterrows():
        terms = [row[f'Level {i} preferred term'] for i in range(4)]
        current = tree
        for i, term in enumerate(terms):
            if pd.notna(term):
                if i == 0:
                    if term not in current:
                        current[term] = {}
                else:
                    if terms[i-1] in current and term not in current[terms[i-1]]:
                        current[terms[i-1]][term] = {}
                    current = current[terms[i-1]]
    
    # Dodamo relacije iz broaderRelationsSkillPillar
    for _, relation in relations_df.iterrows():
        broader_uri = relation['broaderUri']
        narrower_uri = relation['conceptUri']
        broader_name = skill_names.get(broader_uri, None)
        narrower_name = skill_names.get(narrower_uri, None)
        if not broader_name or not narrower_name:
            logging.warning(f"Manjkajoč URI v build_skill_tree/broaderRelations: {broader_uri} ali {narrower_uri} (preskočeno)")
            continue
        # Poiščemo pravo mesto v drevesu
        path = find_skill_path(tree, broader_name)
        if path:
            current = tree
            for step in path[:-1]:
                current = current[step]
            if path[-1] in current:
                if narrower_name not in current[path[-1]]:
                    current[path[-1]][narrower_name] = {}
    
    # Dodamo relacije iz skillSkillRelations
    if 'broaderSkillUri' in skill_relations_df.columns and 'narrowerSkillUri' in skill_relations_df.columns:
        for _, relation in skill_relations_df.iterrows():
            broader_uri = relation['broaderSkillUri']
            narrower_uri = relation['narrowerSkillUri']
            broader_name = skill_names.get(broader_uri, None)
            narrower_name = skill_names.get(narrower_uri, None)
            if not broader_name or not narrower_name:
                logging.warning(f"Manjkajoč URI v skill_skill_relations: {broader_uri} ali {narrower_uri} (preskočeno)")
                continue
            paths = find_all_paths(tree, broader_name)
            for path in paths:
                current = tree
                for step in path[:-1]:
                    current = current[step]
                if path[-1] in current:
                    if narrower_name not in current[path[-1]]:
                        current[path[-1]][narrower_name] = {}
    
    return tree

def search_tree(tree: Dict, search_text: str, current_path: List[str] = None) -> List[List[str]]:
    """Išče po drevesu in vrne seznam poti do ujemajočih se vozlišč."""
    if current_path is None:
        current_path = []
    
    results = []
    
    for skill, subtree in tree.items():
        if search_text.lower() in skill.lower():
            results.append(current_path + [skill])
        
        if isinstance(subtree, dict):
            results.extend(search_tree(subtree, search_text, current_path + [skill]))
    
    return results

def find_skill_path(tree: Dict, skill_name: str, path: List[str] = None) -> Optional[List[str]]:
    """Poišče pot do veščine v drevesu."""
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

def find_all_paths(tree: Dict, skill_name: str, current_path: List[str] = None) -> List[List[str]]:
    """Poišče vse poti do veščine v drevesu."""
    if current_path is None:
        current_path = []
    
    paths = []
    
    if skill_name in tree:
        paths.append(current_path + [skill_name])
    
    for key, subtree in tree.items():
        if isinstance(subtree, dict):
            paths.extend(find_all_paths(subtree, skill_name, current_path + [key]))
    
    return paths

@app.on_event("startup")
async def startup_event():
    """Naloži podatke ob zagonu aplikacije."""
    load_data()

@app.get("/tree")
async def get_tree():
    """Vrne celotno drevo veščin."""
    return skill_tree

@app.get("/search")
async def search_skills(q: str = Query(..., description="Iskalni niz")):
    """Išče po drevesu veščin in vrne ujemajoče se poti."""
    results = search_tree(skill_tree, q)
    return {"paths": results}

@app.get("/subtree/{*path}")
async def get_subtree(path: str):
    """Vrne poddrevo za določeno pot."""
    path_parts = path.split("/")
    current = skill_tree
    
    for part in path_parts:
        if part in current:
            current = current[part]
        else:
            return {"error": "Pot ne obstaja"}
    
    return current

@app.get("/stats")
async def get_stats():
    """Vrne statistike o drevesu."""
    def count_nodes(tree):
        count = 1
        for subtree in tree.values():
            if isinstance(subtree, dict):
                count += count_nodes(subtree)
        return count
    
    stats = {
        "total_nodes": count_nodes(skill_tree),
        "root_nodes": len(skill_tree),
        "total_skills": len(skill_names)
    }
    return stats

@app.get("/", response_class=HTMLResponse)
async def get_html():
    """Vrne HTML stran."""
    with open("main/static/index.html", encoding="utf-8") as f:
        return f.read()

@app.get("/skill/{skill_name}")
async def get_skill(skill_name: str):
    """Vrne podrobnosti o veščini."""
    # Implementirajte iskanje veščine in vrnite njene podrobnosti
    return {
        "name": skill_name,
        "type": "skill" if "knowledge" not in skill_name.lower() else "knowledge",
        "description": "Opis veščine..."  # Tu dodajte pravi opis iz vaših podatkov
    }

@app.put("/skill/{skill_name}")
async def update_skill(skill_name: str, skill_details: dict):
    """Posodobi podrobnosti veščine."""
    # Implementirajte posodobitev veščine v vaših podatkih
    return {"success": True}

@app.delete("/skill/{skill_name}")
async def delete_skill(skill_name: str):
    """Izbriše veščino."""
    # Implementirajte brisanje veščine iz vaših podatkov
    return {"success": True}

@app.get("/uvoz.html", response_class=HTMLResponse)
async def get_uvoz_page():
    """Vrne stran za uvoz podatkov."""
    with open("main/static/uvoz.html", encoding="utf-8") as f:
        return f.read()

@app.get("/test.html", response_class=HTMLResponse)
async def get_test_page():
    """Vrne testno stran."""
    with open("main/static/test.html", encoding="utf-8") as f:
        return f.read()

@app.post("/node")
async def add_node(data: dict):
    """Doda novo UM vozlišče v drevo (v bazo um_skills in relacije v um_skillskillrelations)."""
    path = data.get("path", [])
    name = data.get("name")
    if not name:
        return {"success": False, "error": "Manjka ime vozlišča"}
    try:
        importer_path = os.path.join(os.path.dirname(__file__), 'static')
        if importer_path not in sys.path:
            sys.path.insert(0, importer_path)
        from esco_importer import EscoImporter
        importer = EscoImporter(
            host="clp6z.h.filess.io",
            port=61002,
            user="MYESCO_wentkeepor",
            password="e32389bcc9d0a76b5ba7c4150537fa9efd478362",
            database="MYESCO_wentkeepor"
        )
        if not importer.connect():
            return {"success": False, "error": "Napaka pri povezavi z bazo"}
        try:
            # Poišči starša (če obstaja)
            parent_uri = data.get('parent_uri')
            if not parent_uri:
                parent_id = data.get('parent_id')
                if parent_id:
                    parent_uri = parent_id
                else:
                    parent_uri = None
                    if path:
                        parent_name = path[-1]
                        # Najprej išči v um_skills
                        importer.cursor.execute("SELECT conceptUri FROM um_skills WHERE preferredLabel = %s", (parent_name,))
                        parent = importer.cursor.fetchone()
                        if parent:
                            parent_uri = parent[0]
                        else:
                            # Če ni v um_skills, išči še v skills (ESCO)
                            importer.cursor.execute("SELECT conceptUri FROM skills WHERE preferredLabel = %s", (parent_name,))
                            parent = importer.cursor.fetchone()
                            if parent:
                                parent_uri = parent[0]
            # Ustvari nov URI za vozlišče
            node_uri = f"urn:um_node:{name.lower().replace(' ', '_')}"
            # Preveri, če že obstaja
            importer.cursor.execute("SELECT id FROM um_skills WHERE preferredLabel = %s", (name,))
            if importer.cursor.fetchone():
                return {"success": False, "error": "Vozlišče že obstaja"}
            # Vstavi v um_skills kot kategorijo
            importer.cursor.execute(
                "INSERT INTO um_skills (conceptUri, preferredLabel, skillType, description) VALUES (%s, %s, %s, %s)",
                (node_uri, name, 'category', '')
            )
            # Vstavi v um_skillskillrelations, tudi če parent ni najden
            if parent_uri:
                importer.cursor.execute(
                    "INSERT INTO um_skillskillrelations (source, target) VALUES (%s, %s)",
                    (parent_uri, node_uri)
                )
            else:
                importer.cursor.execute(
                    "INSERT INTO um_skillskillrelations (source, target) VALUES (%s, %s)",
                    ('unknown', node_uri)
                )
            importer.connection.commit()
            return {"success": True}
        finally:
            importer.disconnect()
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/skill")
async def add_skill(data: dict):
    """Doda novo UM veščino ali znanje v vozlišče (v bazo um_skills in relacije v um_skillskillrelations)."""
    path = data.get("path", [])
    name = data.get("name")
    skill_type = data.get("type", "skill")
    description = data.get("description", "")
    if not name:
        return {"success": False, "error": f"Manjka ime {'znanja' if skill_type == 'knowledge' else 'veščine'}"}
    try:
        importer_path = os.path.join(os.path.dirname(__file__), 'static')
        if importer_path not in sys.path:
            sys.path.insert(0, importer_path)
        from esco_importer import EscoImporter
        importer = EscoImporter(
            host="clp6z.h.filess.io",
            port=61002,
            user="MYESCO_wentkeepor",
            password="e32389bcc9d0a76b5ba7c4150537fa9efd478362",
            database="MYESCO_wentkeepor"
        )
        if not importer.connect():
            return {"success": False, "error": "Napaka pri povezavi z bazo"}
        try:
            # Poišči starša (če obstaja)
            parent_uri = data.get('parent_uri')
            if not parent_uri:
                parent_id = data.get('parent_id')
                if parent_id:
                    parent_uri = parent_id
                else:
                    parent_uri = None
                    if path:
                        parent_name = path[-1]
                        # Najprej išči v um_skills
                        importer.cursor.execute("SELECT conceptUri FROM um_skills WHERE preferredLabel = %s", (parent_name,))
                        parent = importer.cursor.fetchone()
                        if parent:
                            parent_uri = parent[0]
                        else:
                            # Če ni v um_skills, išči še v skills (ESCO)
                            importer.cursor.execute("SELECT conceptUri FROM skills WHERE preferredLabel = %s", (parent_name,))
                            parent = importer.cursor.fetchone()
                            if parent:
                                parent_uri = parent[0]
            # Ustvari nov URI za veščino
            skill_uri = f"urn:um_skill:{name.lower().replace(' ', '_')}"
            # Preveri, če že obstaja
            importer.cursor.execute("SELECT id FROM um_skills WHERE preferredLabel = %s", (name,))
            if importer.cursor.fetchone():
                return {"success": False, "error": f"{'Znanje' if skill_type == 'knowledge' else 'Veščina'} že obstaja"}
            # Vstavi v um_skills
            importer.cursor.execute(
                "INSERT INTO um_skills (conceptUri, preferredLabel, skillType, description) VALUES (%s, %s, %s, %s)",
                (skill_uri, name, skill_type, description)
            )
            # Vstavi relacijo v um_skillskillrelations, tudi če parent ni najden
            if parent_uri:
                path_str = ' > '.join(path) if path else 'unknown'
                logging.warning(f"/skill: parent_uri ni najden, vstavljam path kot source za {skill_uri}: {path_str}")
                importer.cursor.execute(
                    "INSERT INTO um_skillskillrelations (source, target) VALUES (%s, %s)",
                    (path_str, skill_uri)
                )
            else:
                path_str = ' > '.join(path) if path else 'unknown'
                logging.warning(f"/skill: parent_uri ni najden, vstavljam path kot source za {skill_uri}: {path_str}")
                importer.cursor.execute(
                    "INSERT INTO um_skillskillrelations (source, target) VALUES (%s, %s)",
                    (path_str, skill_uri)
                )
            importer.connection.commit()
            return {"success": True}
        finally:
            importer.disconnect()
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/import")
async def import_data(
    skills_file: UploadFile = File(None),
    hierarchy_file: UploadFile = File(None),
    relations_file: UploadFile = File(None),
    skill_relations_file: UploadFile = File(None)
):
    """Uvozi podatke iz naloženih datotek."""
    try:
        # Ustvarimo začasne datoteke za shranjevanje
        temp_dir = '../esco'
        os.makedirs(temp_dir, exist_ok=True)
        
        # Shranimo datoteke, če so bile naložene
        if skills_file:
            save_upload_file(skills_file, os.path.join(temp_dir, 'skills_en.csv'))
        if hierarchy_file:
            save_upload_file(hierarchy_file, os.path.join(temp_dir, 'skillsHierarchy_en.csv'))
        if relations_file:
            save_upload_file(relations_file, os.path.join(temp_dir, 'broaderRelationsSkillPillar_en.csv'))
        if skill_relations_file:
            save_upload_file(skill_relations_file, os.path.join(temp_dir, 'skillSkillRelations_en.csv'))
        
        # Ponovno naložimo podatke
        load_data()
        
        return {"success": True, "message": "Podatki uspešno uvoženi."}
    except Exception as e:
        return {"success": False, "message": str(e)}

def save_upload_file(upload_file: UploadFile, destination: str):
    """Shrani naloženo datoteko na določeno pot."""
    with open(destination, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    upload_file.file.close()

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...), 
    db_host: str = Form("localhost"), 
    db_port: int = Form(3306), 
    db_user: str = Form("root"), 
    db_password: str = Form("root"), 
    db_name: str = Form("esco_db"), 
    drop_tables: bool = Form(True),
    current_user: dict = Depends(check_admin_access)
):
    """Naloži datoteko z ESCO podatki in jo uvozi v bazo."""
    global active_imports_count
    global active_imports_lock
    
    # POMEMBNO:
    # Referenciraj globalne module, da se izogneš senčenju spremenljivk
    os_module = os
    sys_module = sys
    
    # Preveri, če je datoteka prazna
    if not file or not file.filename:
        return JSONResponse(
            status_code=400,
            content={"message": "Datoteka ni bila naložena."}
        )
    
    # Preveri veljavno končnico datoteke
    if not file.filename.lower().endswith(('.csv', '.zip')):
        return JSONResponse(
            status_code=400,
            content={"message": "Nepodprta vrsta datoteke. Podprte so le .csv in .zip datoteke."}
        )
    
    # Preveri ali je preveč aktivnih uvozov
    with active_imports_lock:
        if active_imports_count >= MAX_CONCURRENT_IMPORTS:
            return JSONResponse(
                status_code=429,
                content={"message": f"Preveč aktivnih uvozov. Trenutno se izvaja {active_imports_count} uvozov. Poskusite kasneje."}
            )
        active_imports_count += 1
        logging.info(f"Začetek uvoza: Aktivnih uvozov = {active_imports_count}")
    
    # Ustvari začasno datoteko
    try:
        # Absolutna pot do mape static od __file__
        static_dir = os_module.path.join(os_module.path.dirname(__file__), "static")
        
        # Preveri, če obstaja esco_importer.py v mapi static
        importer_file = os_module.path.join(static_dir, "esco_importer.py")
        if not os_module.path.exists(importer_file):
            with active_imports_lock:
                active_imports_count -= 1
                logging.error(f"Datoteka esco_importer.py ne obstaja na poti: {importer_file}")
            return JSONResponse(
                status_code=500,
                content={"message": f"Napaka: Datoteka esco_importer.py ne obstaja."}
            )
        
        # Ustvari začasno datoteko z enako končnico
        with tempfile.NamedTemporaryFile(delete=False, suffix=os_module.path.splitext(file.filename)[1]) as temp_file:
            temp_file.write(file.file.read())
            temp_path = temp_file.name
    
        # Definiraj funkcijo za uvoz podatkov, ki se bo izvedla v ločeni niti
        def import_data():
            try:
                # Dodaj pot do static mape v sys.path, da lahko uvozimo EscoImporter
                if static_dir not in sys_module.path:
                    sys_module.path.insert(0, static_dir)
                
                try:
                    # Uvozi modul esco_importer z uporabo dinamičnega uvoza
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("esco_importer", importer_file)
                    esco_importer_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(esco_importer_module)
                    
                    # Ustvari instanco EscoImporter
                    importer = esco_importer_module.EscoImporter(
                        host=db_host,
                        port=db_port,
                        user=db_user,
                        password=db_password,
                        database=db_name,
                        keep_temp=False
                    )
                    
                    # Zaženi uvoz
                    success = importer.run(temp_path, drop_tables)
                    
                    if success:
                        logging.info(f"Podatki uspešno uvoženi iz datoteke: {file.filename}")
                    else:
                        logging.error(f"Napaka pri uvozu podatkov iz datoteke: {file.filename}")
                except Exception as e:
                    logging.error(f"Napaka pri uvozu modula ali izvedbi uvoza: {e}")
                
                # Odstrani začasno datoteko
                if os_module.path.exists(temp_path):
                    os_module.remove(temp_path)
                    
            except Exception as e:
                logging.error(f"Napaka pri uvozu podatkov: {e}")
            finally:
                # Sprosti števec aktivnih uvozov
                global active_imports_count, active_imports_lock
                with active_imports_lock:
                    active_imports_count -= 1
                    logging.info(f"Konec uvoza: Aktivnih uvozov = {active_imports_count}")
        
        # Zaženi uvoz v ločeni niti
        import_thread = threading.Thread(target=import_data)
        import_thread.daemon = True
        import_thread.start()
        
        return {"filename": file.filename, "message": "Datoteka uspešno naložena. Uvoz poteka v ozadju."}
        
    except Exception as e:
        # V primeru napake sprosti števec aktivnih uvozov
        with active_imports_lock:
            active_imports_count -= 1
            logging.error(f"Napaka pri obdelavi datoteke: {e}")
            
        return JSONResponse(
            status_code=500,
            content={"message": f"Napaka pri nalaganju datoteke: {str(e)}"}
        )

@app.get("/status")
async def status():
    """Preveri status baze podatkov."""
    try:
        # Uvozimo modul s pomočjo absolutne poti
        importer_path = os.path.join(os.path.dirname(__file__), 'static')
        if importer_path not in sys.path:
            sys.path.insert(0, importer_path)
        
        # Preveri, če datoteka obstaja
        importer_file = os.path.join(importer_path, 'esco_importer.py')
        if not os.path.exists(importer_file):
            logger.error(f"Datoteka modula ne obstaja: {importer_file}")
            return JSONResponse({"status": "error", "message": f"Datoteka modula ne obstaja: {importer_file}"}, status_code=500)
                
        try:
            from esco_importer import EscoImporter
        except ImportError as e:
            logger.error(f"Napaka pri uvozu modula: {e}")
            return JSONResponse({"status": "error", "message": f"Napaka pri uvozu modula: {e}"}, status_code=500)
        
        # Ustvari povezavo z bazo
        importer = EscoImporter(
            host="clp6z.h.filess.io",
            port=61002,
            user="MYESCO_wentkeepor",
            password="e32389bcc9d0a76b5ba7c4150537fa9efd478362",
            database="MYESCO_wentkeepor"
        )
        
        # Poveži se z bazo
        if not importer.connect():
            return JSONResponse({"status": "error", "message": "Ni mogoče vzpostaviti povezave z bazo podatkov"}, status_code=500)
        
        try:
            # Pridobi seznam tabel
            importer.cursor.execute(f"SHOW TABLES FROM `{importer.database}`")
            tables = [table[0] for table in importer.cursor.fetchall()]
            
            # Pridobi število vrstic v vsaki tabeli
            table_counts = {}
            for table in tables:
                importer.cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
                count = importer.cursor.fetchone()[0]
                table_counts[table] = count
            
            return {
                "status": "ok",
                "database": importer.database,
                "tables": len(tables),
                "table_counts": table_counts
            }
        
        finally:
            # Prekini povezavo
            importer.disconnect()
    
    except Exception as e:
        logger.error(f"Napaka pri preverjanju statusa: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/db_tree_data")
async def get_db_tree_data():
    """Pridobi podatke iz baze podatkov za izgradnjo drevesa z vsemi podrobnostmi, vključno z UM veščinami in relacijami."""
    try:
        importer_path = os.path.join(os.path.dirname(__file__), 'static')
        if importer_path not in sys.path:
            sys.path.insert(0, importer_path)
        from esco_importer import EscoImporter
        importer = EscoImporter(
            host="clp6z.h.filess.io",
            port=61002,
            user="MYESCO_wentkeepor",
            password="e32389bcc9d0a76b5ba7c4150537fa9efd478362",
            database="MYESCO_wentkeepor"
        )
        if not importer.connect():
            return JSONResponse({"error": "Ni mogoče vzpostaviti povezave z bazo podatkov"}, status_code=500)
        try:
            # --- 1. Zgradi ESCO drevo iz baze (namesto iz CSV) ---
            # Pridobi vse veščine
            importer.cursor.execute("SELECT conceptUri, preferredLabel, skillType, description FROM skills")
            skills_rows = importer.cursor.fetchall()
            skills_df = pd.DataFrame(skills_rows, columns=["conceptUri", "preferredLabel", "skillType", "description"])

            # Pridobi hierarhijo
            importer.cursor.execute("SELECT `Level 0 URI`, `Level 0 preferred term`, `Level 1 URI`, `Level 1 preferred term`, `Level 2 URI`, `Level 2 preferred term`, `Level 3 URI`, `Level 3 preferred term` FROM skills_hierarchy")
            hierarchy_rows = importer.cursor.fetchall()
            hierarchy_df = pd.DataFrame(hierarchy_rows, columns=[f'Level {i} URI' if i%2==0 else f'Level {i//2} preferred term' for i in range(8)])

            # Pridobi broader relacije
            importer.cursor.execute("SELECT conceptUri, broaderUri FROM broader_relations WHERE broaderUri IS NOT NULL AND conceptUri IS NOT NULL")
            relations_rows = importer.cursor.fetchall()
            relations_df = pd.DataFrame(relations_rows, columns=["conceptUri", "broaderUri"])

            # Pridobi skill-skill relacije
            importer.cursor.execute("SELECT broaderSkillUri, narrowerSkillUri FROM skill_skill_relations WHERE broaderSkillUri IS NOT NULL AND narrowerSkillUri IS NOT NULL")
            skill_relations_rows = importer.cursor.fetchall()
            skill_relations_df = pd.DataFrame(skill_relations_rows, columns=["broaderSkillUri", "narrowerSkillUri"])

            # Zgradi slovar imen
            skill_names = {}
            for _, row in hierarchy_df.iterrows():
                for i in range(4):
                    uri = row[f'Level {i} URI']
                    name = row[f'Level {i} preferred term']
                    if pd.notna(uri) and pd.notna(name):
                        skill_names[uri] = name
            for _, row in skills_df.iterrows():
                skill_names[row['conceptUri']] = row['preferredLabel']

            # Zgradi drevo kot v build_skill_tree
            def build_skill_tree_from_db(skills_df, hierarchy_df, relations_df, skill_relations_df):
                tree = {}
                # Dodamo korenske veščine
                root_skills = hierarchy_df[hierarchy_df['Level 0 URI'].notna()]
                for _, skill in root_skills.iterrows():
                    root_name = skill['Level 0 preferred term']
                    if pd.notna(root_name):
                        tree[root_name] = {}
                # Dodamo hierarhijo
                for _, row in hierarchy_df.iterrows():
                    terms = [row[f'Level {i} preferred term'] for i in range(4)]
                    current = tree
                    for i, term in enumerate(terms):
                        if pd.notna(term):
                            if i == 0:
                                if term not in current:
                                    current[term] = {}
                            else:
                                if terms[i-1] in current and term not in current[terms[i-1]]:
                                    current[terms[i-1]][term] = {}
                                current = current[terms[i-1]]
                # Dodamo relacije iz broader_relations
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
                for _, relation in relations_df.iterrows():
                    broader_uri = relation['broaderUri']
                    narrower_uri = relation['conceptUri']
                    broader_name = skill_names.get(broader_uri, None)
                    narrower_name = skill_names.get(narrower_uri, None)
                    if not broader_name or not narrower_name:
                        continue
                    path = find_skill_path(tree, broader_name)
                    if path:
                        current = tree
                        for step in path[:-1]:
                            current = current[step]
                        if path[-1] in current:
                            if narrower_name not in current[path[-1]]:
                                current[path[-1]][narrower_name] = {}
                # Dodamo relacije iz skill_skill_relations
                def find_all_paths(tree, skill_name, path=None):
                    if path is None:
                        path = []
                    paths = []
                    if skill_name in tree:
                        paths.append(path + [skill_name])
                    for key, subtree in tree.items():
                        if isinstance(subtree, dict):
                            paths.extend(find_all_paths(subtree, skill_name, path + [key]))
                    return paths
                for _, relation in skill_relations_df.iterrows():
                    broader_uri = relation['broaderSkillUri']
                    narrower_uri = relation['narrowerSkillUri']
                    broader_name = skill_names.get(broader_uri, None)
                    narrower_name = skill_names.get(narrower_uri, None)
                    if not broader_name or not narrower_name:
                        continue
                    paths = find_all_paths(tree, broader_name)
                    for path in paths:
                        current = tree
                        for step in path[:-1]:
                            current = current[step]
                        if path[-1] in current:
                            if narrower_name not in current[path[-1]]:
                                current[path[-1]][narrower_name] = {}
                return tree

            # Zgradi drevo iz baze
            tree_data = build_skill_tree_from_db(skills_df, hierarchy_df, relations_df, skill_relations_df)

            # --- 2. Integracija UM veščin v ESCO drevo ---
            # (obstoječa koda za UM veščine naj ostane, le tree_data je zdaj prava struktura)

            logger.info(f"Uspešno ustvarjeno drevo z {len(tree_data)} korenskimi vozlišči (vključno z UM)")
            tree_json = json.dumps(tree_data, ensure_ascii=False, indent=2)
            print("\n===== /db_tree_data JSON odgovor =====\n" + tree_json + "\n==============================\n")
            logging.info("/db_tree_data JSON odgovor: " + tree_json)

            # --- NOVO: UM veščine vedno na vrhu kot prvo korensko vozlišče ---
            if 'UM veščine' not in tree_data:
                tree_data['UM veščine'] = {}
            # Premakni 'UM veščine' na začetek
            tree_data = OrderedDict([('UM veščine', tree_data['UM veščine'])] + [(k, v) for k, v in tree_data.items() if k != 'UM veščine'])

            return tree_data
        finally:
            importer.disconnect()
    except Exception as e:
        logger.error(f"Napaka pri pridobivanju podatkov iz baze: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

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
        skills_content = await skills_file.read()
        
        # Če datoteka ne obstaja, ustvari z vsebino
        if not os.path.exists(skills_path):
            with open(skills_path, 'w', newline='', encoding='utf-8') as f:
                f.write(skills_content.decode('utf-8'))
        else:
            # Če datoteka obstaja, dodaj samo podatke brez glave
            content = skills_content.decode('utf-8').split('\n')
            if len(content) > 1:  # Preveri, če ima vsebina več kot samo glavo
                with open(skills_path, 'a', newline='', encoding='utf-8') as f:
                    f.write('\n' + content[1])
        
        # Shrani relacije
        relations_path = os.path.join('static/um_csv', 'um_SkillSkillRelations.csv')
        relations_content = await relations_file.read()
        
        # Če datoteka ne obstaja, ustvari z vsebino
        if not os.path.exists(relations_path):
            with open(relations_path, 'w', newline='', encoding='utf-8') as f:
                f.write(relations_content.decode('utf-8'))
        else:
            # Če datoteka obstaja, dodaj samo podatke brez glave
            content = relations_content.decode('utf-8').split('\n')
            if len(content) > 1:  # Preveri, če ima vsebina več kot samo glavo
                with open(relations_path, 'a', newline='', encoding='utf-8') as f:
                    f.write('\n' + content[1])
        
        return {"success": True, "message": "Podatki uspešno shranjeni"}
    except Exception as e:
        print(f"Napaka pri shranjevanju: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cached")
async def get_cached_tree():
    """Vrne HTML stran za cached drevo."""
    return FileResponse("main/static/baza_cache.html")

@app.get("/skill_details/{skill_name}")
async def get_skill_details(skill_name: str):
    """Vrne podrobne informacije o veščini iz baze podatkov."""
    try:
        # Uvozimo modul s pomočjo absolutne poti
        importer_path = os.path.join(os.path.dirname(__file__), 'static')
        if importer_path not in sys.path:
            sys.path.insert(0, importer_path)
        
        # Preveri, če datoteka obstaja
        importer_file = os.path.join(importer_path, 'esco_importer.py')
        if not os.path.exists(importer_file):
            logger.error(f"Datoteka modula ne obstaja: {importer_file}")
            return JSONResponse({"error": f"Datoteka modula ne obstaja: {importer_file}"}, status_code=500)
                
        try:
            from esco_importer import EscoImporter
        except ImportError as e:
            logger.error(f"Napaka pri uvozu modula: {e}")
            return JSONResponse({"error": f"Napaka pri uvozu modula: {e}"}, status_code=500)
        
        # Ustvari povezavo z bazo
        importer = EscoImporter(
            host="clp6z.h.filess.io",
            port=61002,
            user="MYESCO_wentkeepor",
            password="e32389bcc9d0a76b5ba7c4150537fa9efd478362",
            database="MYESCO_wentkeepor"
        )
        
        # Poveži se z bazo
        if not importer.connect():
            return JSONResponse({"error": "Ni mogoče vzpostaviti povezave z bazo podatkov"}, status_code=500)
        
        try:
            # Poskusimo najti veščino v tabeli skills
            importer.cursor.execute("""
                SELECT conceptUri, preferredLabel, skillType, description
                FROM skills
                WHERE preferredLabel LIKE %s
            """, (f"%{skill_name}%",))
            
            skill_data = importer.cursor.fetchone()
            
            if skill_data:
                uri, name, skill_type, description = skill_data
                return {
                    "name": name,
                    "uri": uri,
                    "id": uri.split('/')[-1] if uri else None,
                    "type": skill_type,
                    "description": description
                }
            
            # Če ni najdeno, poskusimo najti v hierarhiji
            importer.cursor.execute("""
                SELECT `Level 0 URI`, `Level 0 preferred term`, 
                       `Level 1 URI`, `Level 1 preferred term`,
                       `Level 2 URI`, `Level 2 preferred term`,
                       `Level 3 URI`, `Level 3 preferred term`
                FROM skills_hierarchy
                WHERE `Level 0 preferred term` LIKE %s
                   OR `Level 1 preferred term` LIKE %s
                   OR `Level 2 preferred term` LIKE %s
                   OR `Level 3 preferred term` LIKE %s
            """, (f"%{skill_name}%", f"%{skill_name}%", f"%{skill_name}%", f"%{skill_name}%"))
            
            hierarchy_data = importer.cursor.fetchall()
            
            if hierarchy_data:
                for row in hierarchy_data:
                    for i in range(4):
                        uri = row[i*2]
                        name = row[i*2 + 1]
                        if uri and name and pd.notna(uri) and pd.notna(name) and skill_name.lower() in name.lower():
                            return {
                                "name": name,
                                "uri": uri,
                                "id": uri.split('/')[-1] if uri else None,
                                "type": "category" if i < 2 else "skill",
                                "description": f"ESCO kategorija (nivo {i})" if i < 2 else "ESCO veščina"
                            }
            
            # Če še vedno ni najdeno, vrnemo privzete informacije
            return {
                "name": skill_name,
                "uri": None,
                "id": None,
                "type": "skill" if "knowledge" not in skill_name.lower() else "knowledge",
                "description": "Ni podrobnega opisa v bazi podatkov"
            }
            
        finally:
            # Prekini povezavo
            importer.disconnect()
    
    except Exception as e:
        logger.error(f"Napaka pri pridobivanju podrobnosti veščine: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/um_skills_exposed")
async def get_um_skills_exposed():
    """Vrne vse UM veščine in njihove relacije."""
    try:
        importer_path = os.path.join(os.path.dirname(__file__), 'static')
        if importer_path not in sys.path:
            sys.path.insert(0, importer_path)
        from esco_importer import EscoImporter
        importer = EscoImporter(
            host="clp6z.h.filess.io",
            port=61002,
            user="MYESCO_wentkeepor",
            password="e32389bcc9d0a76b5ba7c4150537fa9efd478362",
            database="MYESCO_wentkeepor"
        )
        if not importer.connect():
            return {"error": "Napaka pri povezavi z bazo"}
        try:
            importer.cursor.execute("SELECT conceptUri, preferredLabel, skillType, description FROM um_skills")
            skills = [
                {
                    "conceptUri": uri,
                    "preferredLabel": name,
                    "skillType": skill_type,
                    "description": desc
                }
                for uri, name, skill_type, desc in importer.cursor.fetchall()
            ]
            importer.cursor.execute("SELECT source, target FROM um_skillskillrelations")
            relations = [
                {"source": src, "target": tgt}
                for src, tgt in importer.cursor.fetchall()
            ]
            return {"um_skills": skills, "relations": relations}
        finally:
            importer.disconnect()
    except Exception as e:
        return {"error": str(e)}

@app.post("/um_skills_exposed")
async def add_um_skill(data: dict = Body(...)):
    """Doda novo UM veščino."""
    try:
        importer_path = os.path.join(os.path.dirname(__file__), 'static')
        if importer_path not in sys.path:
            sys.path.insert(0, importer_path)
        from esco_importer import EscoImporter
        importer = EscoImporter(
            host="clp6z.h.filess.io",
            port=61002,
            user="MYESCO_wentkeepor",
            password="e32389bcc9d0a76b5ba7c4150537fa9efd478362",
            database="MYESCO_wentkeepor"
        )
        if not importer.connect():
            return {"error": "Napaka pri povezavi z bazo"}
        try:
            uri = data.get("conceptUri")
            name = data.get("preferredLabel")
            skill_type = data.get("skillType", "skill")
            description = data.get("description", "")
            if not uri or not name:
                return {"error": "Manjka conceptUri ali preferredLabel"}
            importer.cursor.execute(
                "INSERT INTO um_skills (conceptUri, preferredLabel, skillType, description) VALUES (%s, %s, %s, %s)",
                (uri, name, skill_type, description)
            )
            importer.connection.commit()
            return {"success": True}
        finally:
            importer.disconnect()
    except Exception as e:
        return {"error": str(e)}

@app.put("/um_skills_exposed/{conceptUri}")
async def update_um_skill(conceptUri: str, data: dict = Body(...)):
    """Uredi UM veščino."""
    try:
        importer_path = os.path.join(os.path.dirname(__file__), 'static')
        if importer_path not in sys.path:
            sys.path.insert(0, importer_path)
        from esco_importer import EscoImporter
        importer = EscoImporter(
            host="clp6z.h.filess.io",
            port=61002,
            user="MYESCO_wentkeepor",
            password="e32389bcc9d0a76b5ba7c4150537fa9efd478362",
            database="MYESCO_wentkeepor"
        )
        if not importer.connect():
            return {"error": "Napaka pri povezavi z bazo"}
        try:
            name = data.get("preferredLabel")
            skill_type = data.get("skillType")
            description = data.get("description")
            importer.cursor.execute(
                "UPDATE um_skills SET preferredLabel=%s, skillType=%s, description=%s WHERE conceptUri=%s",
                (name, skill_type, description, conceptUri)
            )
            importer.connection.commit()
            return {"success": True}
        finally:
            importer.disconnect()
    except Exception as e:
        return {"error": str(e)}

@app.delete("/um_skills_exposed/{conceptUri}")
async def delete_um_skill(conceptUri: str):
    """Izbriši UM veščino."""
    try:
        importer_path = os.path.join(os.path.dirname(__file__), 'static')
        if importer_path not in sys.path:
            sys.path.insert(0, importer_path)
        from esco_importer import EscoImporter
        importer = EscoImporter(
            host="clp6z.h.filess.io",
            port=61002,
            user="MYESCO_wentkeepor",
            password="e32389bcc9d0a76b5ba7c4150537fa9efd478362",
            database="MYESCO_wentkeepor"
        )
        if not importer.connect():
            return {"error": "Napaka pri povezavi z bazo"}
        try:
            importer.cursor.execute("DELETE FROM um_skills WHERE conceptUri=%s", (conceptUri,))
            importer.connection.commit()
            return {"success": True}
        finally:
            importer.disconnect()
    except Exception as e:
        return {"error": str(e)}

@app.get("/um_izpostava.html", response_class=HTMLResponse)
async def get_um_izpostava_page():
    """Vrne stran za izpostavo UM veščin."""
    with open("main/static/um_izpostava.html", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    print("Zaganjam Skills Tree API...")
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True, log_level="info") 
import subprocess
import webbrowser
import time
import sys
import os
from pathlib import Path

def check_requirements():
    """Preveri in namesti potrebne pakete."""
    try:
        import uvicorn
        import fastapi
        import passlib
        import mysql.connector
    except ImportError:
        print("Nameščam potrebne pakete...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", 
                             "uvicorn", "fastapi", "passlib", "mysql-connector-python"])

def run_create_admin():
    """Zažene create_admin.py za ustvarjanje admin uporabnika."""
    try:
        subprocess.run([sys.executable, "create_admin.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Napaka pri ustvarjanju admin uporabnika: {e}")
        sys.exit(1)

def run_api_server():
    """Zažene API strežnik."""
    # Spremeni trenutni direktorij v main, če obstaja
    main_dir = Path("main")
    if main_dir.exists():
        os.chdir(main_dir)
    
    # Zaženi strežnik
    print("Zaganjam API strežnik...")
    api_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api:app", "--reload"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    
    return api_process

def wait_for_server(timeout=10):
    """Počaka, da se strežnik zažene."""
    import http.client
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            conn = http.client.HTTPConnection("localhost:8000")
            conn.request("GET", "/")
            response = conn.getresponse()
            if response.status == 200:
                return True
        except:
            time.sleep(0.5)
    return False

def main():
    # Preveri in namesti potrebne pakete
    print("Preverjam potrebne pakete...")
    check_requirements()
    
    # Ustvari admin uporabnika
    print("\nUstvarjam admin uporabnika...")
    run_create_admin()
    
    # Zaženi API strežnik
    api_process = run_api_server()
    
    # Počakaj, da se strežnik zažene
    print("\nČakam, da se strežnik zažene...")
    if wait_for_server():
        print("Strežnik je pripravljen!")
        # Odpri brskalnik
        webbrowser.open("http://localhost:8000/static/login.html")
        print("\nPrijavni podatki:")
        print("Uporabniško ime: admin")
        print("Geslo: admin123")
    else:
        print("Napaka: Strežnik se ni zagnal v pričakovanem času!")
        api_process.terminate()
        sys.exit(1)
    
    try:
        # Ostani zagnan dokler uporabnik ne prekine
        api_process.wait()
    except KeyboardInterrupt:
        print("\nZaustavljam strežnik...")
        api_process.terminate()
        api_process.wait()

if __name__ == "__main__":
    main() 
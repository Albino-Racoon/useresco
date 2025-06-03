import subprocess
import time
import webbrowser
import sys
import os
import signal
import threading

def check_required_packages():
    """Preveri, če so nameščeni vsi potrebni paketi in jih namesti, če niso."""
    try:
        import pip
        required_packages = ['flask', 'flask-cors']
        
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
                print(f"Paket {package} je že nameščen.")
            except ImportError:
                print(f"Nameščam paket {package}...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                print(f"Paket {package} uspešno nameščen.")
        
        return True
    except Exception as e:
        print(f"Napaka pri preverjanju ali nameščanju paketov: {e}")
        return False

def check_if_server_is_running(port=5000):
    """Preveri, če je strežnik že zagnan na določenih vratih."""
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0
    except:
        return False

def open_browser():
    """Odpre brskalnik po kratkem zamiku, da se strežnik zagotovo zažene."""
    time.sleep(2)
    url = "http://localhost:5000"
    print(f"Odpiram spletno stran v brskalniku: {url}")
    webbrowser.open(url)

def run_server():
    """Zažene Flask API strežnik."""
    print("Zaganjam ESCO Comparator API...")
    try:
        # Uporabimo subprocess.Popen za zagon strežnika v ozadju
        if sys.platform == 'win32':
            # Na Windows sistemih moramo uporabiti drug pristop
            process = subprocess.Popen(
                [sys.executable, "api.py"],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            # Na Unix sistemih lahko beremo izhod
            process = subprocess.Popen(
                [sys.executable, "api.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        
        # Počakamo, da se strežnik zažene
        print("Čakam, da se strežnik zažene...")
        for _ in range(10):  # poskusimo 10-krat
            if check_if_server_is_running():
                print("Strežnik je uspešno zagnan!")
                return process
            time.sleep(1)
            
        print("Strežnik se ni uspešno zagnal v predvidenem času.")
        return process  # Vrnemo proces, tudi če ni uspešno zagnan, da ga lahko kasneje zaustavimo
    except Exception as e:
        print(f"Napaka pri zagonu strežnika: {e}")
        return None

def main():
    """Glavna funkcija za zagon aplikacije."""
    print("ESCO Comparator - zagon aplikacije")
    
    # Najprej preverimo, če so nameščeni vsi potrebni paketi
    if not check_required_packages():
        print("Ni bilo mogoče namestiti potrebnih paketov. Končujem.")
        return
    
    # Preveri, če je strežnik že zagnan
    if check_if_server_is_running():
        print("Strežnik že teče na portu 5000.")
        server_process = None
    else:
        # Zažene strežnik
        server_process = run_server()
        if not server_process:
            print("Ni bilo mogoče zagnati strežnika. Končujem.")
            return
    
    # Odpre brskalnik v ločeni niti
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()
    
    print("\nESCO Comparator je zagnan.")
    print("Odprite http://localhost:5000 v brskalniku, če se stran ne odpre samodejno.")
    print("Pritisnite Ctrl+C za končanje programa.")
    
    try:
        # Čakaj, dokler uporabnik ne prekine z Ctrl+C
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nZaustavljam ESCO Comparator...")
        if server_process:
            try:
                # Poskusimo zapreti proces pravilno
                if sys.platform == 'win32':
                    # Na Windows potrebujemo drugačen pristop
                    server_process.terminate()
                else:
                    # Na Unix sistemih
                    os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
                
                # Počakamo, da se proces zaključi
                server_process.wait(timeout=5)
                print("Strežnik uspešno zaustavljen.")
            except Exception as e:
                print(f"Napaka pri zaustavljanju strežnika: {e}")
                # Če ne uspe, poskusimo s silo zaključiti
                try:
                    server_process.kill()
                except:
                    pass
    
    print("ESCO Comparator ustavljen. Nasvidenje!")

if __name__ == "__main__":
    main() 
import subprocess
import sys
import time
import threading
import os
import webbrowser
import signal

def check_if_server_is_running(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def wait_for_server(port, timeout=20):
    start = time.time()
    while time.time() - start < timeout:
        if check_if_server_is_running(port):
            return True
        time.sleep(1)
    return False

def run_fastapi():
    print("Zaganjam FastAPI (glavni backend)...")
    # Zaženi v mapi main
    main_dir = os.path.join(os.getcwd(), "main")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api:app", "--reload"],
        cwd=main_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    return process

def run_flask_comparator():
    print("Zaganjam Flask comparator (migrator)...")
    comparator_dir = os.path.join(os.getcwd(), "comparator")
    process = subprocess.Popen(
        [sys.executable, "api.py"],
        cwd=comparator_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    return process

def open_browser():
    time.sleep(2)
    webbrowser.open("http://localhost:8000/static/login.html")

def main():
    # 1. Zaženi FastAPI
    fastapi_proc = run_fastapi()
    print("Čakam, da se FastAPI zažene...")
    if not wait_for_server(8000, timeout=30):
        print("FastAPI se ni zagnal v pričakovanem času!")
        fastapi_proc.terminate()
        sys.exit(1)
    print("FastAPI je pripravljen.")

    # 2. Zaženi Flask comparator
    flask_proc = run_flask_comparator()
    print("Čakam, da se comparator zažene...")
    if not wait_for_server(5000, timeout=30):
        print("Comparator se ni zagnal v pričakovanem času!")
        flask_proc.terminate()
        fastapi_proc.terminate()
        sys.exit(1)
    print("Comparator je pripravljen.")

    # 3. Odpri brskalnik
    threading.Thread(target=open_browser, daemon=True).start()

    print("Oba strežnika tečeta. Pritisni Ctrl+C za izhod.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nZaustavljam oba strežnika...")
        fastapi_proc.terminate()
        flask_proc.terminate()
        fastapi_proc.wait(timeout=5)
        flask_proc.wait(timeout=5)
        print("Vse zaustavljeno. Nasvidenje!")

if __name__ == "__main__":
    main()
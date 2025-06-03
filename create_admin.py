from passlib.context import CryptContext
import mysql.connector
from mysql.connector import Error
import os

# Nastavitve za hasher
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Funkcija za kreiranje hash gesla
def get_password_hash(password):
    return pwd_context.hash(password)

# Pridobi podatke iz okolja ali uporabi privzete
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "esco")
DB_PASSWORD = os.getenv("DB_PASSWORD", "esco123")
DB_NAME = os.getenv("DB_NAME", "esco")
DB_PORT = int(os.getenv("DB_PORT", 3306))

db_config = {
    "host": DB_HOST,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "database": DB_NAME,
    "port": DB_PORT
}

try:
    # Povezava z bazo
    connection = mysql.connector.connect(**db_config)
    cursor = connection.cursor()
    
    # Ustvari bazo če ne obstaja
    cursor.execute("CREATE DATABASE IF NOT EXISTS esco_db")
    cursor.execute("USE esco_db")
    
    # Ustvari tabelo users če ne obstaja
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(255) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL,
        role VARCHAR(50) NOT NULL DEFAULT 'user'
    )
    """)
    
    # Pripravi podatke za admin uporabnika
    admin_username = "admin"
    admin_password = "admin123"
    admin_role = "admin"
    
    # Ustvari hash gesla
    hashed_password = get_password_hash(admin_password)
    
    # Vstavi admin uporabnika (če še ne obstaja)
    try:
        cursor.execute("""
        INSERT INTO users (username, password, role)
        VALUES (%s, %s, %s)
        """, (admin_username, hashed_password, admin_role))
        connection.commit()
        print("Admin uporabnik uspešno ustvarjen!")
        print(f"Uporabniško ime: {admin_username}")
        print(f"Geslo: {admin_password}")
        
    except Error as e:
        if e.errno == 1062:  # Duplicate entry error
            print("Admin uporabnik že obstaja!")
        else:
            raise e
            
except Error as e:
    print(f"Napaka pri povezavi z bazo: {e}")
    
finally:
    if 'connection' in locals() and connection.is_connected():
        cursor.close()
        connection.close()
        print("Povezava z bazo zaprta.") 
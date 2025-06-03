#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import tempfile
import shutil
import zipfile
import csv
import logging
import mysql.connector
from mysql.connector import Error

class EscoImporter:
    """Razred za uvoz ESCO podatkov v MariaDB/MySQL bazo."""

    def __init__(self, host=None, port=None, user=None, password=None, database=None, keep_temp=False):
        """Inicializira uvoznik z nastavitvami baze."""
        self.host = host or "clp6z.h.filess.io"
        self.port = port or 61002
        self.user = user or "MYESCO_wentkeepor"
        self.password = password or "e32389bcc9d0a76b5ba7c4150537fa9efd478362"
        self.database = database or "MYESCO_wentkeepor"
        self.keep_temp = keep_temp
        self.connection = None
        self.cursor = None
        self.temp_dir = None
        self.logger = logging.getLogger(__name__)

    def connect(self):
        """Vzpostavi povezavo z bazo podatkov."""
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password
            )
            
            if self.connection.is_connected():
                self.cursor = self.connection.cursor()
                self.logger.info(f"Povezava z bazo podatkov uspešno vzpostavljena")
                
                # Ustvari bazo, če ne obstaja
                self.cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{self.database}`")
                self.cursor.execute(f"USE `{self.database}`")
                return True
                
        except Error as e:
            self.logger.error(f"Napaka pri povezovanju z bazo podatkov: {e}")
            return False
            
        return False

    def disconnect(self):
        """Prekine povezavo z bazo podatkov."""
        if self.connection and self.connection.is_connected():
            if self.cursor:
                self.cursor.close()
            self.connection.close()
            self.logger.info("Povezava z bazo podatkov zaprta")

    def create_tables(self):
        """Ustvari potrebne tabele v bazi podatkov."""
        try:
            # Ustvari tabelo za uporabnike
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS `users` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `username` VARCHAR(50) UNIQUE NOT NULL,
                    `password` VARCHAR(255) NOT NULL,
                    `role` ENUM('admin', 'user') NOT NULL DEFAULT 'user',
                    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # Dodaj privzete uporabnike (gesla so hashirana)
            self.cursor.execute("""
                INSERT IGNORE INTO `users` (`username`, `password`, `role`) VALUES
                ('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyDAXh0Yz.3N6', 'admin'),
                ('user', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyDAXh0Yz.3N6', 'user');
            """)
            
            # Ustvari tabelo za veščine
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS `skills` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `conceptUri` VARCHAR(255),
                    `preferredLabel` VARCHAR(255),
                    `description` TEXT,
                    `definition` TEXT,
                    `skillType` VARCHAR(50),
                    INDEX `conceptUri` (`conceptUri`(250))
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # Ustvari tabelo za hierarhijo veščin
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS `skills_hierarchy` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `Level 0 URI` VARCHAR(255),
                    `Level 0 preferred term` VARCHAR(255),
                    `Level 1 URI` VARCHAR(255),
                    `Level 1 preferred term` VARCHAR(255),
                    `Level 2 URI` VARCHAR(255),
                    `Level 2 preferred term` VARCHAR(255),
                    `Level 3 URI` VARCHAR(255),
                    `Level 3 preferred term` VARCHAR(255),
                    INDEX `Level_0_URI` (`Level 0 URI`(250)),
                    INDEX `Level_1_URI` (`Level 1 URI`(250)),
                    INDEX `Level_2_URI` (`Level 2 URI`(250)),
                    INDEX `Level_3_URI` (`Level 3 URI`(250))
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # Ustvari tabelo za relacije med veščinami
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS `skill_skill_relations` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `originalSkillUri` VARCHAR(255),
                    `relationType` VARCHAR(50),
                    `broaderSkillUri` VARCHAR(255),
                    `narrowerSkillUri` VARCHAR(255),
                    INDEX `broaderSkillUri` (`broaderSkillUri`(250)),
                    INDEX `narrowerSkillUri` (`narrowerSkillUri`(250))
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # Ustvari tabelo za širše relacije
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS `broader_relations` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `conceptUri` VARCHAR(255),
                    `broaderUri` VARCHAR(255),
                    INDEX `conceptUri` (`conceptUri`(250)),
                    INDEX `broaderUri` (`broaderUri`(250))
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            self.connection.commit()
            self.logger.info("Tabele uspešno ustvarjene")
            
        except Exception as e:
            self.logger.error(f"Napaka pri ustvarjanju tabel: {e}")
            raise

    def drop_tables(self):
        """Izbriše obstoječe tabele iz baze podatkov."""
        if not self.connection or not self.cursor:
            self.logger.error("Ni povezave z bazo podatkov")
            return False
            
        try:
            tables = ['skills', 'skills_hierarchy', 'skill_skill_relations', 'broader_relations']
            for table in tables:
                self.cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
                
            self.connection.commit()
            self.logger.info("Tabele uspešno izbrisane")
            return True
            
        except Error as e:
            self.logger.error(f"Napaka pri brisanju tabel: {e}")
            return False

    def extract_zip(self, zip_path):
        """Ekstrahira ZIP datoteko v začasno mapo."""
        # Ustvari začasno mapo
        temp_dir = tempfile.mkdtemp()
        self.temp_dir = temp_dir
        self.logger.info(f"Ustvarjena začasna mapa: {temp_dir}")
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
                self.logger.info(f"ZIP datoteka ekstrahirana v: {temp_dir}")
                return temp_dir
                
        except Exception as e:
            self.logger.error(f"Napaka pri ekstrahiranju ZIP datoteke: {e}")
            shutil.rmtree(temp_dir)
            return None

    def import_csv_file(self, file_path, table_name):
        """Uvozi podatke iz CSV datoteke v določeno tabelo."""
        if not os.path.exists(file_path):
            self.logger.error(f"Datoteka ne obstaja: {file_path}")
            return False
            
        if not self.connection or not self.cursor:
            self.logger.error("Ni povezave z bazo podatkov")
            return False
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader)  # Preberi glave stolpcev
                
                # Preverimo ali obstajajo vsi stolpci v tabeli
                self.cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
                table_columns = [column[0] for column in self.cursor.fetchall()]
                
                # Filtriramo le tiste stolpce, ki obstajajo v tabeli
                valid_headers = []
                valid_indices = []
                
                for i, header in enumerate(headers):
                    if header in table_columns:
                        valid_headers.append(header)
                        valid_indices.append(i)
                
                if not valid_headers:
                    self.logger.error(f"Ni ujemajočih se stolpcev v tabeli {table_name} in CSV datoteki")
                    return False
                
                self.logger.info(f"Najdeni ujemajoči se stolpci v datoteki {file_path}: {', '.join(valid_headers)}")
                
                # Priprava SQL stavka
                placeholders = ', '.join(['%s'] * len(valid_headers))
                columns = ', '.join([f'`{header}`' for header in valid_headers])
                sql = f"INSERT INTO `{table_name}` ({columns}) VALUES ({placeholders})"
                
                # Vstavi podatke po skupinah
                batch_size = 1000
                batch = []
                
                for row in reader:
                    # Izberi le veljavne vrednosti
                    valid_row = [row[i] for i in valid_indices]
                    batch.append(valid_row)
                    
                    if len(batch) >= batch_size:
                        self.cursor.executemany(sql, batch)
                        self.connection.commit()
                        self.logger.info(f"Vstavljeno {len(batch)} vrstic v tabelo {table_name}")
                        batch = []
                
                # Vstavi preostale podatke
                if batch:
                    self.cursor.executemany(sql, batch)
                    self.connection.commit()
                    self.logger.info(f"Vstavljeno {len(batch)} vrstic v tabelo {table_name}")
                
                self.logger.info(f"Podatki uspešno uvoženi iz: {file_path}")
                return True
                
        except Exception as e:
            self.logger.error(f"Napaka pri uvozu podatkov iz {file_path}: {e}")
            return False

    def run(self, file_path, drop_existing=True):
        """Zažene celoten postopek uvoza."""
        if not self.connect():
            self.logger.error("Napaka pri povezovanju z bazo podatkov")
            return False
            
        try:
            # Uporabi bazo
            self.cursor.execute(f"USE `{self.database}`")
            
            # Izbriši tabele, če je zahtevano
            if drop_existing:
                self.drop_tables()
                
            # Ustvari tabele
            self.create_tables()
            
            # Obdelaj ZIP datoteko ali posamezno CSV datoteko
            file_dir = None
            if file_path.lower().endswith('.zip'):
                file_dir = self.extract_zip(file_path)
                if not file_dir:
                    raise Exception("Napaka pri ekstrahiranju ZIP datoteke")
            else:
                file_dir = os.path.dirname(file_path)
                
            # Mapiraj imena datotek na tabele
            file_table_map = {
                'skills_en.csv': 'skills',
                'skillsHierarchy_en.csv': 'skills_hierarchy',
                'skillSkillRelations_en.csv': 'skill_skill_relations',
                'broaderRelationsSkillPillar_en.csv': 'broader_relations'
            }
            
            # Uvozi podatke iz datotek, če gre za ZIP
            if file_path.lower().endswith('.zip'):
                for file_name, table_name in file_table_map.items():
                    csv_path = os.path.join(file_dir, file_name)
                    if os.path.exists(csv_path):
                        self.import_csv_file(csv_path, table_name)
                    else:
                        # Poskusi poiskati datoteko z drugačnim imenom, vendar semantično podobno
                        similar_files = [f for f in os.listdir(file_dir) 
                                       if f.endswith('.csv') and (
                                           (f.lower().find('skill') >= 0 and file_name.startswith('skill')) or
                                           (f.lower().find('broader') >= 0 and file_name.startswith('broader'))
                                       )]
                        if similar_files:
                            self.logger.info(f"Datoteka {file_name} ne obstaja, poskušam s podobnimi datotekami: {similar_files}")
                            for similar_file in similar_files:
                                self.import_csv_file(os.path.join(file_dir, similar_file), table_name)
                                break  # Uporabi le prvo podobno datoteko
            else:
                # Uvozi posamezno CSV datoteko
                file_name = os.path.basename(file_path)
                if file_name in file_table_map:
                    self.import_csv_file(file_path, file_table_map[file_name])
                else:
                    # Poskusi ugotoviti tabelo glede na ime datoteke
                    most_likely_table = None
                    if 'skill' in file_name.lower() and 'hierarchy' in file_name.lower():
                        most_likely_table = 'skills_hierarchy'
                    elif 'skill' in file_name.lower() and 'relation' in file_name.lower():
                        most_likely_table = 'skill_skill_relations'
                    elif 'broader' in file_name.lower():
                        most_likely_table = 'broader_relations'
                    elif 'skill' in file_name.lower():
                        most_likely_table = 'skills'
                    
                    if most_likely_table:
                        self.logger.info(f"Poskušam uvoziti {file_name} v tabelo {most_likely_table}")
                        self.import_csv_file(file_path, most_likely_table)
                    else:
                        raise Exception(f"Neznana CSV datoteka: {file_name}")
                    
            self.logger.info("Uvoz uspešno zaključen")
            return True
            
        except Exception as e:
            self.logger.error(f"Napaka pri uvozu podatkov: {e}")
            return False
            
        finally:
            # Počisti začasne datoteke
            if self.temp_dir and not self.keep_temp:
                shutil.rmtree(self.temp_dir)
                self.logger.info(f"Začasna mapa izbrisana: {self.temp_dir}")
                
            # Zapri povezavo z bazo
            self.disconnect()
            
            return True 
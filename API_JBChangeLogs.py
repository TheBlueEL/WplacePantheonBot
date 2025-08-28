
import requests
import json
import asyncio
import os
from dotenv import load_dotenv
import time
from datetime import datetime

load_dotenv()

class GitHubSync:
    def __init__(self):
        self.token = os.getenv('GITHUB_TOKEN')
        self.repo = os.getenv('GITHUB_REPO')
        self.branch = os.getenv('GITHUB_BRANCH', 'main')
        self.file_path = 'API_JBChangeLogs.json'
        self.local_file = 'API_JBChangeLogs.json'
        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.last_sha = None
        
    def get_file_from_repo(self):
        """Récupère le fichier depuis le repo GitHub"""
        url = f'https://api.github.com/repos/{self.repo}/contents/{self.file_path}'
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            file_data = response.json()
            content = requests.get(file_data['download_url']).text
            
            return content, file_data['sha']
        except Exception as e:
            print(f"Erreur lors de la récupération du fichier: {e}")
            return None, None
    
    def check_local_file_empty(self):
        """Vérifie si le fichier local est vide"""
        try:
            with open(self.local_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return len(content) == 0
        except FileNotFoundError:
            return True
    
    def save_to_local(self, content):
        """Sauvegarde le contenu dans le fichier local"""
        try:
            with open(self.local_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Fichier {self.local_file} mis à jour avec succès")
            return True
        except Exception as e:
            print(f"Erreur lors de la sauvegarde: {e}")
            return False
    
    def load_local_data(self):
        """Charge les données du fichier local"""
        try:
            with open(self.local_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    
    async def initial_sync(self):
        """Synchronisation initiale"""
        if self.check_local_file_empty():
            print("Fichier local vide, récupération depuis GitHub...")
            content, sha = self.get_file_from_repo()
            if content:
                self.save_to_local(content)
                self.last_sha = sha
                print("Synchronisation initiale terminée")
            else:
                print("Échec de la synchronisation initiale")
        else:
            print("Fichier local déjà présent")
            # Récupérer le SHA actuel pour les vérifications futures
            _, sha = self.get_file_from_repo()
            self.last_sha = sha
    
    async def check_for_updates(self):
        """Vérifie les mises à jour du repo"""
        url = f'https://api.github.com/repos/{self.repo}/contents/{self.file_path}'
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            file_data = response.json()
            current_sha = file_data['sha']
            
            if current_sha != self.last_sha:
                print("Changement détecté dans le repo, mise à jour...")
                content = requests.get(file_data['download_url']).text
                if self.save_to_local(content):
                    self.last_sha = current_sha
                    return True
            return False
        except Exception as e:
            print(f"Erreur lors de la vérification des mises à jour: {e}")
            return False
    
    async def start_monitoring(self):
        """Démarre la surveillance des changements"""
        await self.initial_sync()
        
        while True:
            await asyncio.sleep(1)  # Vérification toutes les secondes
            await self.check_for_updates()

# Instance globale
github_sync = GitHubSync()

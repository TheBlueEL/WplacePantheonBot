
import os
import requests
import base64
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

class GitHubSync:
    def __init__(self):
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.repository = os.getenv('GITHUB_REPO')
        self.branch = os.getenv('GITHUB_BRANCH', 'main')
        
    def _get_repo_info(self):
        """Extraire le nom du repo et du propriétaire"""
        if not self.repository or '/' not in self.repository:
            raise ValueError("Format du repository incorrect. Utilisez: owner/repo")
        
        owner, repo_name = self.repository.split('/')
        return owner, repo_name
    
    def _get_headers(self):
        """Retourner les headers pour l'API GitHub"""
        return {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    async def sync_all_files_to_github(self):
        """Synchronise tous les fichiers locaux vers GitHub (upload uniquement)"""
        try:
            if not self.github_token or not self.repository:
                print("Variables GitHub manquantes dans .env")
                return False
                
            owner, repo_name = self._get_repo_info()
            headers = self._get_headers()
            
            # Fichiers à exclure de la synchronisation
            excluded_files = {
                '.git', '.gitignore', 'README.md', '.replit', 'replit.nix', 
                'pyproject.toml', 'uv.lock', '__pycache__', 
                '.DS_Store', 'Thumbs.db'
            }
            
            # Lister tous les fichiers du répertoire actuel
            current_files = []
            for item in os.listdir('.'):
                if os.path.isfile(item) and item not in excluded_files:
                    current_files.append(item)
            
            print(f"📤 Synchronisation de {len(current_files)} fichier(s) vers GitHub...")
            
            # Synchroniser chaque fichier
            for filename in current_files:
                success = await self._upload_file_to_github(filename, owner, repo_name, headers)
                if success:
                    print(f"✅ Synchronisé: {filename}")
                else:
                    print(f"❌ Erreur pour: {filename}")
            
            print("🎉 Synchronisation GitHub terminée!")
            return True
            
        except Exception as e:
            print(f"Erreur lors de la synchronisation GitHub: {e}")
            return False
    
    async def _upload_file_to_github(self, filename, owner, repo_name, headers):
        """Upload un fichier spécifique vers GitHub"""
        try:
            # Lire le contenu du fichier
            with open(filename, 'rb') as f:
                content = base64.b64encode(f.read()).decode('utf-8')
            
            # Vérifier si le fichier existe déjà pour récupérer le SHA
            sha = None
            api_url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{filename}"
            
            try:
                response = requests.get(api_url, headers=headers)
                if response.status_code == 200:
                    sha = response.json()["sha"]
            except:
                pass  # Le fichier n'existe pas encore
            
            # Préparer les données pour l'upload
            data = {
                "message": f"Sync: {filename}",
                "content": content,
                "branch": self.branch
            }
            
            if sha:
                data["sha"] = sha  # Nécessaire pour mettre à jour un fichier existant
            
            # Envoyer le fichier vers GitHub
            response = requests.put(api_url, headers=headers, json=data)
            
            return response.status_code in [200, 201]
            
        except Exception as e:
            print(f"Erreur lors de l'upload de {filename}: {e}")
            return False
    
    async def sync_image_to_pictures_repo(self, file_path):
        """Synchroniser une image vers le repository pictures"""
        try:
            if not self.github_token:
                print("Token GitHub manquant")
                return False
            
            headers = self._get_headers()
            repo = "pictures"
            base_url = f"https://api.github.com/repos/TheBlueEL/{repo}"
            
            # Lire le fichier image
            with open(file_path, 'rb') as f:
                content = base64.b64encode(f.read()).decode('utf-8')
            
            filename = os.path.basename(file_path)
            
            # Vérifier si le fichier existe déjà
            sha = None
            try:
                url = f"{base_url}/contents/{filename}"
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    sha = response.json()["sha"]
            except:
                pass
            
            # Préparer les données
            data = {
                "message": f"Auto-upload: {filename}",
                "content": content,
                "branch": "main"
            }
            
            if sha:
                data["sha"] = sha
            
            # Upload vers GitHub
            url = f"{base_url}/contents/{filename}"
            response = requests.put(url, headers=headers, json=data)
            
            return response.status_code in [200, 201]
            
        except Exception as e:
            print(f"Erreur lors de la sync image GitHub: {e}")
            return False

import discord
import os
import requests
import base64
import json
from dotenv import load_dotenv

# Charger les variables d'environnement du fichier .env
load_dotenv()

# Configuration des intents
intents = discord.Intents.default()
intents.message_content = True

# Créer le bot Discord avec support des commandes
from discord.ext import commands
from github_sync import GitHubSync

client = commands.Bot(command_prefix='!', intents=intents)

@client.event
async def on_ready():
    print(f'{client.user} is connected!')
    print(f'Bot connected as {client.user.name}')
    print(f'Bot ID: {client.user.id}')
    
    # Synchroniser avec GitHub au démarrage
    print("🔄 Synchronisation avec GitHub...")
    github_sync = GitHubSync()
    await github_sync.sync_all_files_to_github()
    
    # Charger le système d'embed
    await client.load_extension('embed_system')
    print('Embed system loaded!')
    
    # Synchroniser les commandes slash
    try:
        synced = await client.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

@client.event
async def on_message(message):
    # Éviter que le bot réponde à ses propres messages
    if message.author == client.user:
        return

    # Optionnel: afficher les messages reçus dans la console
    print(f'Message de {message.author}: {message.content}')

# Démarrer le bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if token:
        client.run(token)
    else:
        print("Erreur: DISCORD_TOKEN not found in .env file.")
import discord
import os
import requests
import base64
import json
from dotenv import load_dotenv
from discord.ext import commands
from github_sync import GitHubSync
# Removed incorrect imports - using cog loading instead

# Charger les variables d'environnement du fichier .env
load_dotenv()

# Configuration des intents
intents = discord.Intents.default()
intents.message_content = True

# Créer le bot Discord avec support des commandes

client = commands.Bot(command_prefix='!', intents=intents)

@client.event
async def on_ready():
    print(f'{client.user} is connected!')
    print(f'Bot connected as {client.user.name}')
    print(f'Bot ID: {client.user.id}')

    # Synchroniser avec GitHub au démarrage
    print("Synchronisation avec GitHub...")
    github_sync = GitHubSync()
    await github_sync.sync_all_files_to_github()

    # Charger les extensions
    try:
        await client.load_extension('embed_system')
        print('Embed system loaded!')
    except Exception as e:
        print(f'Failed to load embed_system: {e}')

    try:
        await client.load_extension('pantheon_system')
        print('Pantheon system loaded!')
    except Exception as e:
        print(f'Failed to load pantheon_system: {e}')

    try:
        await client.load_extension('notation_system')
        print('Notation system loaded!')
    except Exception as e:
        print(f'Failed to load notation_system: {e}')

    try:
        await client.load_extension('autorank_system')
        print('AutoRank system loaded!')
        # Restore autorank buttons
        from autorank_system import restore_autorank_buttons
        await restore_autorank_buttons(client)
    except Exception as e:
        print(f'Failed to load autorank_system: {e}')

    # Setup du système de tickets
    try:
        from ticket_bot import setup_ticket_system, setup_persistent_views
        setup_ticket_system(client)
        setup_persistent_views(client)
        print('Ticket system loaded!')
    except Exception as e:
        print(f'Failed to load ticket_system: {e}')

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
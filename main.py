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
intents.members = True  # Nécessaire pour surveiller les membres du serveur

# Créer le bot Discord avec support des commandes

client = commands.Bot(command_prefix='!', intents=intents)

@client.event
async def on_ready():
    print(f'Bot connected as {client.user.name}')

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

    try:
        await client.load_extension('converters_system')
        print('Converters system loaded!')
    except Exception as e:
        print(f'Failed to load converters_system: {e}')

    try:
        await client.load_extension('welcome_system')
        print('Welcome system loaded!')
    except Exception as e:
        print(f'Failed to load welcome_system: {e}')

    try:
        await client.load_extension('leveling_system')
        print('Leveling system loaded!')
    except Exception as e:
        print(f'Failed to load leveling_system: {e}')

    # Setup du système de tickets
    try:
        from ticket_bot import setup_ticket_system, setup_persistent_views
        setup_ticket_system(client)
        setup_persistent_views(client)
        print('Ticket system loaded!')
    except Exception as e:
        print(f'Failed to load ticket_system: {e}')

    # Load AdministratorCommands cog
    try:
        await client.load_extension('administrator_command')
        print('Administrator command loaded!')
    except Exception as e:
        print(f'Failed to load administrator_command: {e}')

    # Synchroniser les commandes slash
    try:
        synced = await client.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

    # Synchroniser avec GitHub après les commandes
    github_sync = GitHubSync()
    await github_sync.sync_all_files_to_github()

@client.event
async def on_message(message):
    # Éviter que le bot réponde à ses propres messages
    if message.author == client.user:
        return

    # Check for notification image uploads
    if hasattr(client, '_notification_image_listeners') and message.attachments:
        # Check both user object and user ID as keys
        listener = None
        for key, view in client._notification_image_listeners.items():
            # Check if key matches user or user ID
            if key == message.author or key == message.author.id:
                listener = view
                break
        
        if listener and hasattr(listener, 'waiting_for_image') and listener.waiting_for_image:
            from level_notification_system import NotificationLevelCardView
            if isinstance(listener, NotificationLevelCardView):
                print(f"🔍 [MAIN] Listener trouvé pour {message.author.name}, traitement de l'image...")
                success = await listener.handle_image_upload(message, listener)
                if success:
                    print(f"✅ [MAIN] Image traitée avec succès")
                    return
                else:
                    print(f"❌ [MAIN] Échec du traitement de l'image")

    # Optionnel: afficher les messages reçus dans la console
    print(f'Message de {message.author}: {message.content}')

    # Process commands
    await client.process_commands(message)

# Démarrer le bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if token:
        client.run(token)
    else:
        print("Erreur: DISCORD_TOKEN not found in .env file.")
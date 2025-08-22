
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import io
from PIL import Image, ImageDraw, ImageFont
import requests
import os
import json

def get_bot_name(bot):
    """Récupère le nom d'affichage du bot"""
    return bot.user.display_name if bot.user else "Bot"

def load_welcome_data():
    """Load welcome data from JSON file"""
    try:
        with open('welcome_data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # Return default configuration if file doesn't exist
        return {
            "template_config": {
                "template_url": "https://raw.githubusercontent.com/TheBlueEL/pictures/refs/heads/main/WelcomeCard.png",
                "avatar_position": {
                    "x": 55,
                    "y": 50,
                    "diameter": 120
                },
                "text_config": {
                    "welcome_text": {
                        "x_offset": 20,
                        "y_offset": 20,
                        "font_size": 28,
                        "font_path": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                    },
                    "server_text": {
                        "x_offset": 20,
                        "y_offset": 40,
                        "font_size": 24,
                        "font_path": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                        "text": "To the Server!"
                    },
                    "text_color": [255, 255, 255, 255],
                    "shadow_color": [0, 0, 0, 128],
                    "shadow_offset": 2
                }
            }
        }

class WelcomeSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_welcome_data()["template_config"]
        
    async def download_image(self, url):
        """Télécharge une image depuis une URL"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.read()
            return None
        except Exception as e:
            print(f"Erreur lors du téléchargement de l'image: {e}")
            return None

    def create_circle_mask(self, size):
        """Crée un masque circulaire"""
        mask = Image.new('L', size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size[0], size[1]), fill=255)
        return mask

    async def create_welcome_card(self, user):
        """Crée la carte de bienvenue personnalisée"""
        try:
            # Recharger la configuration pour les modifications en temps réel
            self.config = load_welcome_data()["template_config"]
            
            # Télécharger l'image template
            template_data = await self.download_image(self.config["template_url"])
            if not template_data:
                return None
            
            # Télécharger l'avatar de l'utilisateur
            avatar_url = user.display_avatar.url
            avatar_data = await self.download_image(avatar_url)
            if not avatar_data:
                return None
            
            # Télécharger la décoration de profil si activée
            decoration_data = None
            if self.config.get("profile_decoration", {}).get("enabled", False):
                decoration_url = self.config["profile_decoration"]["url"]
                decoration_data = await self.download_image(decoration_url)
            
            # Ouvrir les images
            template = Image.open(io.BytesIO(template_data)).convert("RGBA")
            avatar = Image.open(io.BytesIO(avatar_data)).convert("RGBA")
            
            # Ouvrir la décoration si disponible
            decoration = None
            if decoration_data:
                decoration = Image.open(io.BytesIO(decoration_data)).convert("RGBA")
            
            # Configuration de l'avatar depuis JSON
            avatar_config = self.config["avatar_position"]
            circle_x = avatar_config["x"]
            circle_y = avatar_config["y"]
            circle_diameter = avatar_config["diameter"]
            
            # Redimensionner l'avatar pour qu'il rentre dans le cercle
            avatar = avatar.resize((circle_diameter, circle_diameter), Image.Resampling.LANCZOS)
            
            # Créer un masque circulaire pour l'avatar
            mask = self.create_circle_mask((circle_diameter, circle_diameter))
            
            # Appliquer le masque circulaire à l'avatar
            avatar_circle = Image.new("RGBA", (circle_diameter, circle_diameter), (0, 0, 0, 0))
            avatar_circle.paste(avatar, (0, 0))
            avatar_circle.putalpha(mask)
            
            # Ajouter la décoration de profil derrière l'avatar si disponible
            if decoration and self.config.get("profile_decoration", {}).get("enabled", False):
                decoration_config = self.config["profile_decoration"]
                decoration_x = decoration_config["x"]
                decoration_y = decoration_config["y"]
                
                # Coller la décoration à sa taille d'origine (derrière l'avatar)
                template.paste(decoration, (decoration_x, decoration_y), decoration)
            
            # Coller l'avatar circulaire sur le template (devant la décoration)
            template.paste(avatar_circle, (circle_x, circle_y), avatar_circle)
            
            # Ajouter le texte
            draw = ImageDraw.Draw(template)
            
            # Configuration du texte depuis JSON
            text_config = self.config["text_config"]
            welcome_config = text_config["welcome_text"]
            username_config = text_config["username_text"]
            
            # Position du texte (à droite de l'avatar)
            text_x = circle_x + circle_diameter + welcome_config["x_offset"]
            text_y_welcome = circle_y + welcome_config["y_offset"]
            text_y_username = circle_y + username_config["y_offset"]
            
            # Couleurs depuis la configuration
            text_color = tuple(text_config["text_color"])
            shadow_color = tuple(text_config["shadow_color"])
            shadow_offset = text_config["shadow_offset"]
            
            # Première zone: "WELCOME, TO THE SERVER"
            try:
                font_welcome = ImageFont.truetype(welcome_config["font_path"], welcome_config["font_size"])
            except:
                font_welcome = ImageFont.load_default()
            
            draw.text((text_x + shadow_offset, text_y_welcome + shadow_offset), 
                     welcome_config["text"], font=font_welcome, fill=shadow_color)
            draw.text((text_x, text_y_welcome), 
                     welcome_config["text"], font=font_welcome, fill=text_color)
            
            # Deuxième zone: "[USERNAME]" avec taille adaptative
            username_text = user.display_name.upper()
            
            # Calculer l'espace disponible pour le nom d'utilisateur
            image_width = template.width
            available_width = image_width - text_x - username_config["margin_right"]
            
            # Trouver la taille de police optimale
            font_size = username_config["font_size_max"]
            font_username = None
            
            while font_size >= username_config["font_size_min"]:
                try:
                    font_username = ImageFont.truetype(username_config["font_path"], font_size)
                except:
                    font_username = ImageFont.load_default()
                
                # Calculer la largeur du texte avec cette police
                bbox = draw.textbbox((0, 0), username_text, font=font_username)
                text_width = bbox[2] - bbox[0]
                
                # Si le texte rentre dans l'espace disponible, on garde cette taille
                if text_width <= available_width:
                    break
                
                # Sinon, réduire la taille de police
                font_size -= 5
            
            # S'assurer qu'on a une police valide
            if font_username is None:
                try:
                    font_username = ImageFont.truetype(username_config["font_path"], username_config["font_size_min"])
                except:
                    font_username = ImageFont.load_default()
            
            # Dessiner le nom d'utilisateur avec l'ombre
            draw.text((text_x + shadow_offset, text_y_username + shadow_offset), 
                     username_text, font=font_username, fill=shadow_color)
            draw.text((text_x, text_y_username), 
                     username_text, font=font_username, fill=text_color)
            
            # Convertir en bytes pour l'envoi Discord
            output = io.BytesIO()
            template.save(output, format='PNG')
            output.seek(0)
            
            return output
            
        except Exception as e:
            print(f"Erreur lors de la création de la carte de bienvenue: {e}")
            return None

    @app_commands.command(name="welcome", description="Generate a welcome card with your profile picture")
    async def welcome_command(self, interaction: discord.Interaction, user: discord.Member = None):
        """Commande pour générer une carte de bienvenue"""
        
        # Si aucun utilisateur spécifié, utiliser l'auteur de la commande
        target_user = user if user else interaction.user
        
        # Créer un embed de chargement
        loading_embed = discord.Embed(
            title="<:UploadLOGO:1407072005567545478> Generating Welcome Card",
            description="Creating your personalized welcome card...",
            color=discord.Color.blue()
        )
        
        bot_name = get_bot_name(self.bot)
        loading_embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        loading_embed.set_footer(text=f"{bot_name} | Welcome System", icon_url=self.bot.user.display_avatar.url)
        
        await interaction.response.send_message(embed=loading_embed)
        
        # Générer la carte de bienvenue
        welcome_card = await self.create_welcome_card(target_user)
        
        if welcome_card:
            # Créer l'embed de succès
            success_embed = discord.Embed(
                title="<:SucessLOGO:1407071637840592977> Welcome Card Generated",
                description=f"Welcome card created for {target_user.mention}!",
                color=discord.Color.green()
            )
            
            success_embed.set_footer(text=f"{bot_name} | Welcome System", icon_url=self.bot.user.display_avatar.url)
            
            # Envoyer l'image
            file = discord.File(welcome_card, filename=f"welcome_{target_user.id}.png")
            success_embed.set_image(url=f"attachment://welcome_{target_user.id}.png")
            
            await interaction.edit_original_response(embed=success_embed, attachments=[file])
        else:
            # Embed d'erreur
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Error",
                description="Failed to generate the welcome card. Please try again later.",
                color=discord.Color.red()
            )
            
            error_embed.set_footer(text=f"{bot_name} | Welcome System", icon_url=self.bot.user.display_avatar.url)
            
            await interaction.edit_original_response(embed=error_embed)

async def setup(bot):
    await bot.add_cog(WelcomeSystem(bot))


import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import io
from PIL import Image, ImageDraw, ImageFont
import requests
import os

def get_bot_name(bot):
    """Récupère le nom d'affichage du bot"""
    return bot.user.display_name if bot.user else "Bot"

class WelcomeSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.welcome_template_url = "https://raw.githubusercontent.com/TheBlueEL/pictures/refs/heads/main/WelcomeCard.png"
        
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
            # Télécharger l'image template
            template_data = await self.download_image(self.welcome_template_url)
            if not template_data:
                return None
            
            # Télécharger l'avatar de l'utilisateur
            avatar_url = user.display_avatar.url
            avatar_data = await self.download_image(avatar_url)
            if not avatar_data:
                return None
            
            # Ouvrir les images
            template = Image.open(io.BytesIO(template_data)).convert("RGBA")
            avatar = Image.open(io.BytesIO(avatar_data)).convert("RGBA")
            
            # Dimensions du template
            template_width, template_height = template.size
            
            # Position et taille du cercle (ajustez selon votre template)
            circle_x = 55  # Position X du cercle
            circle_y = 50  # Position Y du cercle
            circle_diameter = 120  # Diamètre du cercle
            
            # Redimensionner l'avatar pour qu'il rentre dans le cercle
            avatar = avatar.resize((circle_diameter, circle_diameter), Image.Resampling.LANCZOS)
            
            # Créer un masque circulaire pour l'avatar
            mask = self.create_circle_mask((circle_diameter, circle_diameter))
            
            # Appliquer le masque circulaire à l'avatar
            avatar_circle = Image.new("RGBA", (circle_diameter, circle_diameter), (0, 0, 0, 0))
            avatar_circle.paste(avatar, (0, 0))
            avatar_circle.putalpha(mask)
            
            # Coller l'avatar circulaire sur le template
            template.paste(avatar_circle, (circle_x, circle_y), avatar_circle)
            
            # Ajouter le texte
            draw = ImageDraw.Draw(template)
            
            # Essayer de charger une police personnalisée, sinon utiliser la police par défaut
            try:
                # Police pour "Welcome [Username]"
                font_welcome = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
                # Police pour "To the Server!"
                font_server = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            except:
                # Police par défaut si pas de police système
                font_welcome = ImageFont.load_default()
                font_server = ImageFont.load_default()
            
            # Position du texte (à droite de l'avatar)
            text_x = circle_x + circle_diameter + 20
            text_y_welcome = circle_y + 20
            text_y_server = text_y_welcome + 40
            
            # Couleur du texte (blanc)
            text_color = (255, 255, 255, 255)
            
            # Ajouter les textes avec un effet d'ombre pour plus de style
            shadow_offset = 2
            shadow_color = (0, 0, 0, 128)
            
            # Ombre pour "Welcome [Username]"
            draw.text((text_x + shadow_offset, text_y_welcome + shadow_offset), 
                     f"Welcome {user.display_name}", font=font_welcome, fill=shadow_color)
            # Texte principal "Welcome [Username]"
            draw.text((text_x, text_y_welcome), 
                     f"Welcome {user.display_name}", font=font_welcome, fill=text_color)
            
            # Ombre pour "To the Server!"
            draw.text((text_x + shadow_offset, text_y_server + shadow_offset), 
                     "To the Server!", font=font_server, fill=shadow_color)
            # Texte principal "To the Server!"
            draw.text((text_x, text_y_server), 
                     "To the Server!", font=font_server, fill=text_color)
            
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


import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import io
from PIL import Image, ImageDraw, ImageFont
import requests
import os
import json
import uuid

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
        self.active_managers = {}  # Track active welcome system managers
        
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
            
            # Créer un template avec couleur de fond ou image personnalisée
            if self.config.get("background_image"):
                template_data = await self.download_image(self.config["background_image"])
                if not template_data:
                    return None
                template = Image.open(io.BytesIO(template_data)).convert("RGBA")
            else:
                # Créer une image avec couleur de fond
                bg_color = self.config.get("background_color", [255, 255, 255])
                template = Image.new("RGBA", (1920, 1080), tuple(bg_color + [255]))
            
            # Télécharger l'avatar de l'utilisateur
            avatar_url = user.display_avatar.url
            avatar_data = await self.download_image(avatar_url)
            if not avatar_data:
                return None
            
            # Télécharger DefaultProfile si activée
            default_profile_data = None
            if self.config.get("default_profile", {}).get("enabled", True):
                default_profile_url = self.config["default_profile"]["url"]
                default_profile_data = await self.download_image(default_profile_url)
            
            # Télécharger la décoration de profil si activée
            decoration_data = None
            if self.config.get("profile_decoration", {}).get("enabled", True):
                decoration_url = self.config["profile_decoration"]["url"]
                decoration_data = await self.download_image(decoration_url)
            
            # Ouvrir l'avatar
            avatar = Image.open(io.BytesIO(avatar_data)).convert("RGBA")
            
            # Ouvrir DefaultProfile si disponible
            default_profile = None
            if default_profile_data:
                default_profile = Image.open(io.BytesIO(default_profile_data)).convert("RGBA")
            
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
            
            # Ajouter DefaultProfile derrière l'avatar si disponible
            if default_profile and self.config.get("default_profile", {}).get("enabled", True):
                default_profile_config = self.config["default_profile"]
                default_profile_x = default_profile_config["x"]
                default_profile_y = default_profile_config["y"]
                
                # Coller DefaultProfile à sa taille d'origine (derrière l'avatar)
                template.paste(default_profile, (default_profile_x, default_profile_y), default_profile)
            
            # Coller l'avatar circulaire sur le template (par-dessus DefaultProfile)
            template.paste(avatar_circle, (circle_x, circle_y), avatar_circle)
            
            # Ajouter la décoration de profil par-dessus l'avatar si disponible
            if decoration and self.config.get("profile_decoration", {}).get("enabled", True):
                decoration_config = self.config["profile_decoration"]
                decoration_x = decoration_config["x"]
                decoration_y = decoration_config["y"]
                
                # Appliquer le changement de couleur si défini
                if decoration_config.get("color_override"):
                    color_override = decoration_config["color_override"]
                    # Créer une nouvelle image avec la couleur de remplacement
                    colored_decoration = Image.new("RGBA", decoration.size, tuple(color_override + [255]))
                    # Utiliser le canal alpha de l'image originale
                    colored_decoration.putalpha(decoration.split()[-1])
                    decoration = colored_decoration
                elif decoration_config.get("custom_image"):
                    # Si une image personnalisée est définie, la télécharger
                    custom_decoration_data = await self.download_image(decoration_config["custom_image"])
                    if custom_decoration_data:
                        decoration = Image.open(io.BytesIO(custom_decoration_data)).convert("RGBA")
                
                # Coller la décoration à sa taille d'origine (par-dessus l'avatar)
                template.paste(decoration, (decoration_x, decoration_y), decoration)
            
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

    @app_commands.command(name="welcome_system", description="Manage welcome card settings and design")
    async def welcome_system_command(self, interaction: discord.Interaction):
        """Command to manage welcome card system"""
        
        if not interaction.user.guild_permissions.manage_messages:
            embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Permission Denied",
                description="You need 'Manage Messages' permission to use this command.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        view = WelcomeSystemManagerView(self.bot, interaction.user.id)
        view.guild = interaction.guild
        embed = view.get_main_embed()
        view.update_buttons()

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        # Store the active manager
        self.active_managers[interaction.user.id] = view

    @commands.Cog.listener()
    async def on_message(self, message):
        # Check if message is from someone with an active welcome system manager waiting for images
        if message.author.bot:
            return

        user_id = message.author.id
        if user_id in self.active_managers:
            manager = self.active_managers[user_id]
            if manager.waiting_for_image and message.attachments:
                # Check if the attachment is an image with allowed extensions
                attachment = message.attachments[0]
                allowed_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg']
                if any(attachment.filename.lower().endswith(ext) for ext in allowed_extensions):
                    # Download the image locally first
                    local_file = await self.download_image_to_github(attachment.url)

                    # Only delete the message if the image was successfully downloaded
                    if local_file:
                        try:
                            await message.delete()
                        except:
                            pass

                        # Process the image based on type
                        if manager.current_image_type == "background":
                            manager.config["background_image"] = local_file
                            manager.config.pop("background_color", None)
                        elif manager.current_image_type == "profile_outline":
                            # Process profile outline image (make it square)
                            processed_url = await self.process_profile_outline_image(local_file)
                            if processed_url:
                                if "profile_decoration" not in manager.config:
                                    manager.config["profile_decoration"] = {}
                                manager.config["profile_decoration"]["custom_image"] = processed_url
                                manager.config["profile_decoration"].pop("color_override", None)

                        manager.save_config()
                        manager.waiting_for_image = False

                        # Update the manager view
                        if manager.current_image_type == "background":
                            manager.mode = "background_image"
                            embed = manager.get_background_image_embed()
                        else:
                            manager.mode = "profile_outline_image"
                            embed = manager.get_background_image_embed()
                            embed.title = "🖼️ Profile Outline Image"
                            embed.description = "Set a custom profile outline image"

                        manager.update_buttons()

                        # Find and update the original message
                        try:
                            channel = message.channel
                            async for msg in channel.history(limit=50):
                                if msg.author == self.bot.user and msg.embeds:
                                    if "Upload Image" in msg.embeds[0].title:
                                        await msg.edit(embed=embed, view=manager)
                                        break
                        except Exception as e:
                            print(f"Error updating message: {e}")
                else:
                    # File is not a valid image format
                    try:
                        await message.delete()
                    except:
                        pass

                    error_embed = discord.Embed(
                        title="<:ErrorLOGO:1407071682031648850> Invalid File Type",
                        description="Please upload only image files with these extensions:\n`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp`, `.svg`",
                        color=discord.Color.red()
                    )

                    try:
                        channel = message.channel
                        await channel.send(embed=error_embed, delete_after=5)
                    except:
                        pass

    async def download_image_to_github(self, image_url):
        """Download image and upload to GitHub, similar to embed system"""
        try:
            # Create images directory if it doesn't exist
            os.makedirs('images', exist_ok=True)

            # Generate unique filename
            filename = f"{uuid.uuid4()}.png"
            file_path = os.path.join('images', filename)

            # Download the image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        with open(file_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                f.write(chunk)

                        # Synchronize with GitHub
                        try:
                            from github_sync import GitHubSync
                            github_sync = GitHubSync()
                            sync_success = await github_sync.sync_image_to_pictures_repo(file_path)

                            if sync_success:
                                # Delete local file after successful sync
                                try:
                                    os.remove(file_path)
                                except:
                                    pass

                                # Return GitHub raw URL from public pictures repo
                                filename = os.path.basename(file_path)
                                github_url = f"https://raw.githubusercontent.com/TheBlueEL/pictures/main/{filename}"
                                return github_url
                        except ImportError:
                            print("GitHub sync not available")
                            
            return None
        except Exception as e:
            print(f"Error downloading image: {e}")
            return None

    async def process_profile_outline_image(self, image_url):
        """Process profile outline image to make it square (crop from center)"""
        try:
            # Download image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        
            # Open and process image
            image = Image.open(io.BytesIO(image_data)).convert("RGBA")
            width, height = image.size
            
            # Make it square by cropping from center
            min_dimension = min(width, height)
            left = (width - min_dimension) // 2
            top = (height - min_dimension) // 2
            right = left + min_dimension
            bottom = top + min_dimension
            
            square_image = image.crop((left, top, right, bottom))
            
            # Save processed image
            os.makedirs('images', exist_ok=True)
            filename = f"{uuid.uuid4()}_square.png"
            file_path = os.path.join('images', filename)
            square_image.save(file_path, 'PNG')
            
            # Upload to GitHub
            try:
                from github_sync import GitHubSync
                github_sync = GitHubSync()
                sync_success = await github_sync.sync_image_to_pictures_repo(file_path)

                if sync_success:
                    # Delete local file after successful sync
                    try:
                        os.remove(file_path)
                    except:
                        pass

                    # Return GitHub raw URL
                    filename = os.path.basename(file_path)
                    github_url = f"https://raw.githubusercontent.com/TheBlueEL/pictures/main/{filename}"
                    return github_url
            except ImportError:
                print("GitHub sync not available")
                
            return None
        except Exception as e:
            print(f"Error processing profile outline image: {e}")
            return None

class WelcomeSystemManagerView(discord.ui.View):
    def __init__(self, bot, user_id):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.config = load_welcome_data()["template_config"]
        self.mode = "main"
        self.background_mode = False
        self.profile_outline_mode = False
        self.waiting_for_image = False
        self.current_image_type = None
        
    def get_main_embed(self):
        # Recharger la configuration pour avoir les dernières modifications
        self.config = load_welcome_data()["template_config"]
        
        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Welcome System Manager",
            description="Configure your welcome card design and settings",
            color=0x5865F2
        )
        
        # Show current configuration status
        config_status = ""
        if self.config.get("background_color"):
            bg = self.config["background_color"]
            config_status += f"🎨 Background: RGB({bg[0]}, {bg[1]}, {bg[2]})\n"
        elif self.config.get("background_image"):
            config_status += "🖼️ Background: Custom Image\n"
        else:
            config_status += "⚪ Background: White (Default)\n"
            
        if self.config.get("profile_decoration", {}).get("enabled", True):
            config_status += "🖼️ Profile Outline: Enabled\n"
        else:
            config_status += "❌ Profile Outline: Disabled\n"
            
        embed.add_field(
            name="Current Configuration",
            value=config_status,
            inline=False
        )
        
        bot_name = get_bot_name(self.bot)
        embed.set_footer(text=f"{bot_name} | Welcome System", icon_url=self.bot.user.display_avatar.url)
        
        return embed
        
    def get_background_embed(self):
        # Recharger la configuration pour avoir les dernières modifications
        self.config = load_welcome_data()["template_config"]
        
        embed = discord.Embed(
            title="🎨 Background Settings",
            description="Configure the background of your welcome card",
            color=discord.Color.blue()
        )
        
        # Show current background status
        if self.config.get("background_color"):
            bg = self.config["background_color"]
            embed.add_field(
                name="Current Background",
                value=f"Color: RGB({bg[0]}, {bg[1]}, {bg[2]})",
                inline=False
            )
        elif self.config.get("background_image"):
            embed.add_field(
                name="Current Background",
                value="Custom Image",
                inline=False
            )
        else:
            embed.add_field(
                name="Current Background",
                value="White (Default)",
                inline=False
            )
            
        bot_name = get_bot_name(self.bot)
        embed.set_footer(text=f"{bot_name} | Background Settings", icon_url=self.bot.user.display_avatar.url)
        
        return embed
        
    def get_background_color_embed(self):
        # Recharger la configuration pour avoir les dernières modifications
        self.config = load_welcome_data()["template_config"]
        
        embed = discord.Embed(
            title="🎨 Background Color",
            description="Choose how to set your background color",
            color=discord.Color.purple()
        )
        
        if self.config.get("background_color"):
            bg = self.config["background_color"]
            embed.add_field(
                name="Current Color",
                value=f"RGB({bg[0]}, {bg[1]}, {bg[2]})",
                inline=False
            )
        else:
            embed.add_field(
                name="Current Color",
                value="White (Default)",
                inline=False
            )
            
        bot_name = get_bot_name(self.bot)
        embed.set_footer(text=f"{bot_name} | Background Color", icon_url=self.bot.user.display_avatar.url)
        
        return embed
        
    def get_background_image_embed(self):
        # Recharger la configuration pour avoir les dernières modifications
        self.config = load_welcome_data()["template_config"]
        
        embed = discord.Embed(
            title="🖼️ Background Image",
            description="Set a custom background image for your welcome card",
            color=discord.Color.green()
        )
        
        if self.config.get("background_image"):
            embed.add_field(
                name="Current Image",
                value="✅ Custom image set",
                inline=False
            )
        else:
            embed.add_field(
                name="Current Image",
                value="❌ No custom image",
                inline=False
            )
            
        bot_name = get_bot_name(self.bot)
        embed.set_footer(text=f"{bot_name} | Background Image", icon_url=self.bot.user.display_avatar.url)
        
        return embed
        
    def get_profile_outline_embed(self):
        # Recharger la configuration pour avoir les dernières modifications
        self.config = load_welcome_data()["template_config"]
        
        embed = discord.Embed(
            title="🖼️ Profile Outline Settings",
            description="Configure the profile decoration outline",
            color=discord.Color.orange()
        )
        
        profile_config = self.config.get("profile_decoration", {})
        enabled = profile_config.get("enabled", True)
        
        status = "✅ Enabled" if enabled else "❌ Disabled"
        embed.add_field(
            name="Current Status",
            value=status,
            inline=False
        )
        
        if profile_config.get("color_override"):
            color = profile_config["color_override"]
            embed.add_field(
                name="Color Override",
                value=f"RGB({color[0]}, {color[1]}, {color[2]})",
                inline=False
            )
        elif profile_config.get("custom_image"):
            embed.add_field(
                name="Custom Image",
                value="✅ Custom outline image set",
                inline=False
            )
        else:
            embed.add_field(
                name="Style",
                value="Default outline",
                inline=False
            )
            
        bot_name = get_bot_name(self.bot)
        embed.set_footer(text=f"{bot_name} | Profile Outline", icon_url=self.bot.user.display_avatar.url)
        
        return embed
        
    def get_waiting_image_embed(self):
        # Recharger la configuration pour avoir les dernières modifications
        self.config = load_welcome_data()["template_config"]
        
        embed = discord.Embed(
            title="<:UploadLOGO:1407072005567545478> Upload Image",
            description="Please send an image file in this channel.\n\n**Only you can upload the image for security reasons.**",
            color=discord.Color.blue()
        )
        
        bot_name = get_bot_name(self.bot)
        embed.set_footer(text=f"{bot_name} | Upload Image", icon_url=self.bot.user.display_avatar.url)
        
        return embed
        
    def save_config(self):
        """Save the current configuration to JSON file"""
        data = load_welcome_data()
        data["template_config"] = self.config
        with open('welcome_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
    def update_buttons(self):
        self.clear_items()
        
        if self.waiting_for_image:
            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )
            back_button.callback = self.back_from_image_upload
            self.add_item(back_button)
            
        elif self.mode == "background_image":
            # Background image buttons
            url_button = discord.ui.Button(
                label="Set URL",
                style=discord.ButtonStyle.primary,
                emoji="<:URLLOGO:1407071963809054931>"
            )
            url_button.callback = self.background_image_url
            
            upload_button = discord.ui.Button(
                label="Upload Image",
                style=discord.ButtonStyle.secondary,
                emoji="<:UploadLOGO:1407072005567545478>"
            )
            upload_button.callback = self.upload_background_image
            
            clear_button = discord.ui.Button(
                label="Clear Image",
                style=discord.ButtonStyle.danger,
                emoji="<:DeleteLOGO:1407071421363916841>"
            )
            clear_button.callback = self.clear_background_image
            
            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )
            back_button.callback = self.back_to_background
            
            self.add_item(url_button)
            self.add_item(upload_button)
            self.add_item(clear_button)
            self.add_item(back_button)
            
        elif self.mode == "background_color":
            # Background color buttons
            hex_button = discord.ui.Button(
                label="Hex Code",
                style=discord.ButtonStyle.primary,
                emoji="🎨"
            )
            hex_button.callback = self.background_hex_color
            
            rgb_button = discord.ui.Button(
                label="RGB Code",
                style=discord.ButtonStyle.secondary,
                emoji="🌈"
            )
            rgb_button.callback = self.background_rgb_color
            
            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )
            back_button.callback = self.back_to_background
            
            self.add_item(hex_button)
            self.add_item(rgb_button)
            self.add_item(back_button)
            
        elif self.mode == "background":
            # Background main buttons
            color_button = discord.ui.Button(
                label="Color",
                style=discord.ButtonStyle.primary,
                emoji="🎨"
            )
            color_button.callback = self.background_color_settings
            
            image_button = discord.ui.Button(
                label="Image",
                style=discord.ButtonStyle.secondary,
                emoji="🖼️"
            )
            image_button.callback = self.background_image_settings
            
            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )
            back_button.callback = self.back_to_main
            
            self.add_item(color_button)
            self.add_item(image_button)
            self.add_item(back_button)
            
        elif self.mode == "profile_outline_color":
            # Profile outline color buttons
            hex_button = discord.ui.Button(
                label="Hex Code",
                style=discord.ButtonStyle.primary,
                emoji="🎨"
            )
            hex_button.callback = self.profile_outline_hex_color
            
            rgb_button = discord.ui.Button(
                label="RGB Code",
                style=discord.ButtonStyle.secondary,
                emoji="🌈"
            )
            rgb_button.callback = self.profile_outline_rgb_color
            
            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )
            back_button.callback = self.back_to_profile_outline
            
            self.add_item(hex_button)
            self.add_item(rgb_button)
            self.add_item(back_button)
            
        elif self.mode == "profile_outline_image":
            # Profile outline image buttons
            url_button = discord.ui.Button(
                label="Set URL",
                style=discord.ButtonStyle.primary,
                emoji="<:URLLOGO:1407071963809054931>"
            )
            url_button.callback = self.profile_outline_image_url
            
            upload_button = discord.ui.Button(
                label="Upload Image",
                style=discord.ButtonStyle.secondary,
                emoji="<:UploadLOGO:1407072005567545478>"
            )
            upload_button.callback = self.upload_profile_outline_image
            
            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )
            back_button.callback = self.back_to_profile_outline
            
            self.add_item(url_button)
            self.add_item(upload_button)
            self.add_item(back_button)
            
        elif self.mode == "profile_outline":
            # Profile outline main buttons
            toggle_button = discord.ui.Button(
                label="ON" if self.config.get("profile_decoration", {}).get("enabled", True) else "OFF",
                style=discord.ButtonStyle.success if self.config.get("profile_decoration", {}).get("enabled", True) else discord.ButtonStyle.danger,
                emoji="<:ONLOGO:1391530620366094440>" if self.config.get("profile_decoration", {}).get("enabled", True) else "<:OFFLOGO:1391535388065271859>"
            )
            toggle_button.callback = self.toggle_profile_outline
            
            color_button = discord.ui.Button(
                label="Color",
                style=discord.ButtonStyle.primary,
                emoji="🎨"
            )
            color_button.callback = self.profile_outline_color_settings
            
            image_button = discord.ui.Button(
                label="Image",
                style=discord.ButtonStyle.secondary,
                emoji="🖼️"
            )
            image_button.callback = self.profile_outline_image_settings
            
            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )
            back_button.callback = self.back_to_main
            
            self.add_item(toggle_button)
            self.add_item(color_button)
            self.add_item(image_button)
            self.add_item(back_button)
            
        else:  # main mode
            # Main buttons
            background_button = discord.ui.Button(
                label="Background",
                style=discord.ButtonStyle.primary,
                emoji="🎨"
            )
            background_button.callback = self.background_settings
            
            profile_outline_button = discord.ui.Button(
                label="Profile Outline",
                style=discord.ButtonStyle.secondary,
                emoji="🖼️"
            )
            profile_outline_button.callback = self.profile_outline_settings
            
            self.add_item(background_button)
            self.add_item(profile_outline_button)
    
    # Background callbacks
    async def background_settings(self, interaction: discord.Interaction):
        self.mode = "background"
        embed = self.get_background_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
        
    async def background_color_settings(self, interaction: discord.Interaction):
        self.mode = "background_color"
        embed = self.get_background_color_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
        
    async def background_image_settings(self, interaction: discord.Interaction):
        self.mode = "background_image"
        embed = self.get_background_image_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
        
    async def background_hex_color(self, interaction: discord.Interaction):
        modal = BackgroundHexColorModal(self)
        await interaction.response.send_modal(modal)
        
    async def background_rgb_color(self, interaction: discord.Interaction):
        modal = BackgroundRGBColorModal(self)
        await interaction.response.send_modal(modal)
        
    async def background_image_url(self, interaction: discord.Interaction):
        modal = BackgroundImageURLModal(self)
        await interaction.response.send_modal(modal)
        
    async def upload_background_image(self, interaction: discord.Interaction):
        self.waiting_for_image = True
        self.current_image_type = "background"
        embed = self.get_waiting_image_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
        
    async def clear_background_image(self, interaction: discord.Interaction):
        self.config.pop("background_image", None)
        self.save_config()
        embed = self.get_background_image_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
    
    # Profile outline callbacks
    async def profile_outline_settings(self, interaction: discord.Interaction):
        self.mode = "profile_outline"
        embed = self.get_profile_outline_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
        
    async def toggle_profile_outline(self, interaction: discord.Interaction):
        if "profile_decoration" not in self.config:
            self.config["profile_decoration"] = {}
        current_state = self.config["profile_decoration"].get("enabled", True)
        self.config["profile_decoration"]["enabled"] = not current_state
        self.save_config()
        embed = self.get_profile_outline_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
        
    async def profile_outline_color_settings(self, interaction: discord.Interaction):
        self.mode = "profile_outline_color"
        embed = self.get_background_color_embed()  # Reuse color embed design
        embed.title = "🎨 Profile Outline Color"
        embed.description = "Choose how to set your profile outline color"
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
        
    async def profile_outline_image_settings(self, interaction: discord.Interaction):
        self.mode = "profile_outline_image"
        embed = self.get_background_image_embed()  # Reuse image embed design
        embed.title = "🖼️ Profile Outline Image"
        embed.description = "Set a custom profile outline image"
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
        
    async def profile_outline_hex_color(self, interaction: discord.Interaction):
        modal = ProfileOutlineHexColorModal(self)
        await interaction.response.send_modal(modal)
        
    async def profile_outline_rgb_color(self, interaction: discord.Interaction):
        modal = ProfileOutlineRGBColorModal(self)
        await interaction.response.send_modal(modal)
        
    async def profile_outline_image_url(self, interaction: discord.Interaction):
        modal = ProfileOutlineImageURLModal(self)
        await interaction.response.send_modal(modal)
        
    async def upload_profile_outline_image(self, interaction: discord.Interaction):
        self.waiting_for_image = True
        self.current_image_type = "profile_outline"
        embed = self.get_waiting_image_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
    
    # Back navigation callbacks
    async def back_to_main(self, interaction: discord.Interaction):
        self.mode = "main"
        embed = self.get_main_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
        
    async def back_to_background(self, interaction: discord.Interaction):
        self.mode = "background"
        embed = self.get_background_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
        
    async def back_to_profile_outline(self, interaction: discord.Interaction):
        self.mode = "profile_outline"
        embed = self.get_profile_outline_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
        
    async def back_from_image_upload(self, interaction: discord.Interaction):
        self.waiting_for_image = False
        if self.current_image_type == "background":
            self.mode = "background_image"
            embed = self.get_background_image_embed()
        else:
            self.mode = "profile_outline_image"
            embed = self.get_background_image_embed()
            embed.title = "🖼️ Profile Outline Image"
            embed.description = "Set a custom profile outline image"
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

# Modal classes for color and URL inputs
class BackgroundHexColorModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='🎨 Background Hex Color')
        self.view = view
        
        self.hex_input = discord.ui.TextInput(
            label='Hex Color Code',
            placeholder='#FFFFFF or FFFFFF',
            required=True,
            max_length=7
        )
        self.add_item(self.hex_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        hex_value = self.hex_input.value.strip()
        if hex_value.startswith('#'):
            hex_value = hex_value[1:]
            
        try:
            rgb = tuple(int(hex_value[i:i+2], 16) for i in (0, 2, 4))
            self.view.config["background_color"] = list(rgb)
            self.view.config.pop("background_image", None)  # Remove image if setting color
            self.view.save_config()
            
            embed = self.view.get_background_color_embed()
            self.view.update_buttons()
            await interaction.response.edit_message(embed=embed, view=self.view)
        except ValueError:
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid Hex Color",
                description="Please enter a valid hex color code (e.g., #FF0000 or FF0000)",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

class BackgroundRGBColorModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='🌈 Background RGB Color')
        self.view = view
        
        self.red_input = discord.ui.TextInput(
            label='Red (0-255)',
            placeholder='255',
            required=True,
            max_length=3
        )
        self.green_input = discord.ui.TextInput(
            label='Green (0-255)',
            placeholder='255',
            required=True,
            max_length=3
        )
        self.blue_input = discord.ui.TextInput(
            label='Blue (0-255)',
            placeholder='255',
            required=True,
            max_length=3
        )
        
        self.add_item(self.red_input)
        self.add_item(self.green_input)
        self.add_item(self.blue_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            r = int(self.red_input.value)
            g = int(self.green_input.value)
            b = int(self.blue_input.value)
            
            if not all(0 <= val <= 255 for val in [r, g, b]):
                raise ValueError("Values must be between 0 and 255")
                
            self.view.config["background_color"] = [r, g, b]
            self.view.config.pop("background_image", None)  # Remove image if setting color
            self.view.save_config()
            
            embed = self.view.get_background_color_embed()
            self.view.update_buttons()
            await interaction.response.edit_message(embed=embed, view=self.view)
        except ValueError:
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid RGB Values",
                description="Please enter valid RGB values (0-255 for each color)",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

class BackgroundImageURLModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='🖼️ Background Image URL')
        self.view = view
        
        self.url_input = discord.ui.TextInput(
            label='Image URL',
            placeholder='https://example.com/image.png',
            required=True,
            max_length=500
        )
        self.add_item(self.url_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        url = self.url_input.value.strip()
        if not url.startswith(('http://', 'https://')):
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid URL",
                description="Please enter a valid HTTP or HTTPS URL",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
            
        self.view.config["background_image"] = url
        self.view.config.pop("background_color", None)  # Remove color if setting image
        self.view.save_config()
        
        embed = self.view.get_background_image_embed()
        self.view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self.view)

class ProfileOutlineHexColorModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='🎨 Profile Outline Hex Color')
        self.view = view
        
        self.hex_input = discord.ui.TextInput(
            label='Hex Color Code',
            placeholder='#FFFFFF or FFFFFF',
            required=True,
            max_length=7
        )
        self.add_item(self.hex_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        hex_value = self.hex_input.value.strip()
        if hex_value.startswith('#'):
            hex_value = hex_value[1:]
            
        try:
            rgb = tuple(int(hex_value[i:i+2], 16) for i in (0, 2, 4))
            if "profile_decoration" not in self.view.config:
                self.view.config["profile_decoration"] = {}
            self.view.config["profile_decoration"]["color_override"] = list(rgb)
            self.view.config["profile_decoration"].pop("custom_image", None)
            self.view.save_config()
            
            embed = self.view.get_profile_outline_embed()
            self.view.update_buttons()
            await interaction.response.edit_message(embed=embed, view=self.view)
        except ValueError:
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid Hex Color",
                description="Please enter a valid hex color code (e.g., #FF0000 or FF0000)",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

class ProfileOutlineRGBColorModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='🌈 Profile Outline RGB Color')
        self.view = view
        
        self.red_input = discord.ui.TextInput(
            label='Red (0-255)',
            placeholder='255',
            required=True,
            max_length=3
        )
        self.green_input = discord.ui.TextInput(
            label='Green (0-255)',
            placeholder='255',
            required=True,
            max_length=3
        )
        self.blue_input = discord.ui.TextInput(
            label='Blue (0-255)',
            placeholder='255',
            required=True,
            max_length=3
        )
        
        self.add_item(self.red_input)
        self.add_item(self.green_input)
        self.add_item(self.blue_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            r = int(self.red_input.value)
            g = int(self.green_input.value)
            b = int(self.blue_input.value)
            
            if not all(0 <= val <= 255 for val in [r, g, b]):
                raise ValueError("Values must be between 0 and 255")
                
            if "profile_decoration" not in self.view.config:
                self.view.config["profile_decoration"] = {}
            self.view.config["profile_decoration"]["color_override"] = [r, g, b]
            self.view.config["profile_decoration"].pop("custom_image", None)
            self.view.save_config()
            
            embed = self.view.get_profile_outline_embed()
            self.view.update_buttons()
            await interaction.response.edit_message(embed=embed, view=self.view)
        except ValueError:
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid RGB Values",
                description="Please enter valid RGB values (0-255 for each color)",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

class ProfileOutlineImageURLModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='🖼️ Profile Outline Image URL')
        self.view = view
        
        self.url_input = discord.ui.TextInput(
            label='Image URL',
            placeholder='https://example.com/image.png',
            required=True,
            max_length=500
        )
        self.add_item(self.url_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        url = self.url_input.value.strip()
        if not url.startswith(('http://', 'https://')):
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid URL",
                description="Please enter a valid HTTP or HTTPS URL",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
            
        if "profile_decoration" not in self.view.config:
            self.view.config["profile_decoration"] = {}
        self.view.config["profile_decoration"]["custom_image"] = url
        self.view.config["profile_decoration"].pop("color_override", None)
        self.view.save_config()
        
        embed = self.view.get_profile_outline_embed()
        self.view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self.view)

async def setup(bot):
    await bot.add_cog(WelcomeSystem(bot))

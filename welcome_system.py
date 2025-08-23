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
            "welcome_settings": {
                "enabled": False,
                "channel_id": None,
                "welcome_message": "Welcome {user}!"
            },
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
        self.active_managers = {}  # Track welcome system managers

    async def download_image(self, url):
        """Télécharge une image depuis une URL"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.read()
                        return data
                    else:
                        print(f"Échec du téléchargement: HTTP {response.status}")
            return None
        except Exception as e:
            print(f"Erreur lors du téléchargement de l'image {url}: {e}")
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

            # Taille cible pour le template
            target_width, target_height = 2048, 1080
            target_ratio = target_width / target_height

            # Variables pour gérer les GIFs animés
            is_animated_gif = False
            frames = []
            durations = []

            # Créer un template avec couleur de fond ou image personnalisée
            if self.config.get("background_image"):
                template_data = await self.download_image(self.config["background_image"])
                if not template_data:
                    return None

                # Ouvrir l'image de fond
                bg_image = Image.open(io.BytesIO(template_data))
                
                # Vérifier si c'est un GIF animé
                if hasattr(bg_image, 'is_animated') and bg_image.is_animated:
                    is_animated_gif = True
                    # Traiter chaque frame du GIF
                    for frame_idx in range(bg_image.n_frames):
                        bg_image.seek(frame_idx)
                        frame = bg_image.copy().convert("RGBA")
                        
                        # Appliquer les mêmes transformations à chaque frame
                        orig_width, orig_height = frame.size
                        orig_ratio = orig_width / orig_height

                        # Rogner l'image pour maintenir les bonnes proportions
                        if orig_ratio > target_ratio:
                            # Image trop large, rogner sur les côtés
                            new_width = int(orig_height * target_ratio)
                            left = (orig_width - new_width) // 2
                            frame = frame.crop((left, 0, left + new_width, orig_height))
                        elif orig_ratio < target_ratio:
                            # Image trop haute, rogner en haut et en bas
                            new_height = int(orig_width / target_ratio)
                            top = (orig_height - new_height) // 2
                            frame = frame.crop((0, top, orig_width, top + new_height))

                        # Redimensionner à la taille exacte
                        frame = frame.resize((target_width, target_height), Image.Resampling.LANCZOS)
                        frames.append(frame)
                        
                        # Récupérer la durée de la frame
                        try:
                            duration = bg_image.info.get('duration', 100)
                            durations.append(duration)
                        except:
                            durations.append(100)  # 100ms par défaut
                else:
                    # Image statique
                    bg_image = bg_image.convert("RGBA")
                    orig_width, orig_height = bg_image.size
                    orig_ratio = orig_width / orig_height

                    # Rogner l'image pour maintenir les bonnes proportions
                    if orig_ratio > target_ratio:
                        # Image trop large, rogner sur les côtés
                        new_width = int(orig_height * target_ratio)
                        left = (orig_width - new_width) // 2
                        bg_image = bg_image.crop((left, 0, left + new_width, orig_height))
                    elif orig_ratio < target_ratio:
                        # Image trop haute, rogner en haut et en bas
                        new_height = int(orig_width / target_ratio)
                        top = (orig_height - new_height) // 2
                        bg_image = bg_image.crop((0, top, orig_width, top + new_height))

                    # Redimensionner à la taille exacte
                    template = bg_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
            else:
                # Créer une image avec couleur de fond
                bg_color = self.config.get("background_color", [255, 255, 255])
                template = Image.new("RGBA", (target_width, target_height), tuple(bg_color + [255]))

            # Télécharger l'avatar de l'utilisateur
            avatar_url = user.display_avatar.url
            avatar_data = await self.download_image(avatar_url)
            if not avatar_data:
                return None

            # Télécharger DefaultProfile si activée
            default_profile_data = None
            default_profile_config = self.config.get("default_profile", {})
            if default_profile_config.get("enabled", True) and "url" in default_profile_config:
                default_profile_url = default_profile_config["url"]
                default_profile_data = await self.download_image(default_profile_url)
                if not default_profile_data:
                    print("⚠️ Échec du chargement de DefaultProfile")

            # Télécharger la décoration de profil si activée
            decoration_data = None
            decoration_config = self.config.get("profile_decoration", {})
            if decoration_config.get("enabled", True) and "url" in decoration_config:
                decoration_url = decoration_config["url"]
                decoration_data = await self.download_image(decoration_url)
                if not decoration_data:
                    print("⚠️ Échec du chargement de ProfileOutline")

            # Ouvrir l'avatar
            avatar = Image.open(io.BytesIO(avatar_data)).convert("RGBA")

            # Ouvrir DefaultProfile si disponible
            default_profile = None
            if default_profile_data:
                try:
                    default_profile = Image.open(io.BytesIO(default_profile_data)).convert("RGBA")
                except Exception as e:
                    print(f"❌ Erreur lors du traitement de DefaultProfile: {e}")

            # Vérifier si une image personnalisée de contenu est définie
            default_profile_config = self.config.get("default_profile", {})
            if default_profile_config.get("custom_image_url"):
                try:
                    custom_content_data = await self.download_image(default_profile_config["custom_image_url"])
                    if custom_content_data:
                        custom_default_profile = Image.open(io.BytesIO(custom_content_data)).convert("RGBA")
                        # Utiliser l'image personnalisée au lieu de la default
                        default_profile = custom_default_profile
                except Exception as e:
                    print(f"❌ Erreur lors du chargement de l'image de contenu personnalisée: {e}")

            # Ouvrir la décoration si disponible
            decoration = None
            if decoration_data:
                try:
                    decoration = Image.open(io.BytesIO(decoration_data)).convert("RGBA")

                    # Traitement de l'image de décoration pour la rendre carrée si nécessaire
                    dec_width, dec_height = decoration.size
                    if dec_width != dec_height:
                        # Rogner pour faire un carré depuis le centre
                        min_dimension = min(dec_width, dec_height)
                        left = (dec_width - min_dimension) // 2
                        top = (dec_height - min_dimension) // 2
                        decoration = decoration.crop((left, top, left + min_dimension, top + min_dimension))

                except Exception as e:
                    print(f"❌ Erreur lors du traitement de ProfileOutline: {e}")

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
                        custom_decoration = Image.open(io.BytesIO(custom_decoration_data)).convert("RGBA")

                        # Traitement de l'image personnalisée pour la rendre carrée si nécessaire
                        dec_width, dec_height = custom_decoration.size
                        if dec_width != dec_height:
                            # Rogner pour faire un carré depuis le centre
                            min_dimension = min(dec_width, dec_height)
                            left = (dec_width - min_dimension) // 2
                            top = (dec_height - min_dimension) // 2
                            custom_decoration = custom_decoration.crop((left, top, left + min_dimension, top + min_dimension))

                        # Redimensionner l'image personnalisée à la taille de ProfileOutline
                        if decoration:
                            custom_decoration = custom_decoration.resize(decoration.size, Image.Resampling.LANCZOS)

                            # Appliquer le masque alpha de ProfileOutline sur l'image personnalisée
                            # Utiliser le canal alpha de ProfileOutline comme masque
                            alpha_mask = decoration.split()[-1]  # Canal alpha de ProfileOutline

                            # Créer une nouvelle image avec l'image personnalisée mais utilisant le masque de ProfileOutline
                            masked_decoration = Image.new("RGBA", custom_decoration.size, (0, 0, 0, 0))
                            masked_decoration.paste(custom_decoration, (0, 0))
                            masked_decoration.putalpha(alpha_mask)

                            decoration = masked_decoration

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

            # Couleurs depuis la configuration avec valeurs par défaut
            text_color = tuple(text_config.get("text_color", [255, 255, 255, 255]))
            shadow_color = tuple(text_config.get("shadow_color", [0, 0, 0, 128]))
            shadow_offset = text_config.get("shadow_offset", 2)

            # Première zone: "WELCOME, TO THE SERVER"
            try:
                font_welcome = ImageFont.truetype(welcome_config["font_path"], welcome_config["font_size"])
            except:
                font_welcome = ImageFont.load_default()

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

            # Vérifier si une image de texture de texte est définie
            text_texture_image = None
            default_profile_config = self.config.get("default_profile", {})
            if default_profile_config.get("custom_image_url"):
                try:
                    texture_data = await self.download_image(default_profile_config["custom_image_url"])
                    if texture_data:
                        text_texture_image = Image.open(io.BytesIO(texture_data)).convert("RGBA")
                except Exception as e:
                    print(f"❌ Erreur lors du chargement de la texture de texte: {e}")

            if text_texture_image:
                # Créer une fine bordure noire autour du texte pour la lisibilité
                border_thickness = 3
                draw = ImageDraw.Draw(template)

                # Dessiner la bordure noire (plusieurs passes pour épaissir)
                for adj in range(-border_thickness, border_thickness + 1):
                    for adj_y in range(-border_thickness, border_thickness + 1):
                        if adj != 0 or adj_y != 0:
                            draw.text((text_x + adj, text_y_welcome + adj_y),
                                     welcome_config["text"], font=font_welcome, fill=(0, 0, 0, 255))
                            draw.text((text_x + adj, text_y_username + adj_y),
                                     username_text, font=font_username, fill=(0, 0, 0, 255))

                # Créer un masque pour le texte (sans bordure)
                text_mask = Image.new('L', template.size, 0)
                mask_draw = ImageDraw.Draw(text_mask)

                # Dessiner le texte sur le masque en blanc (visible) - seulement le texte principal, pas la bordure
                mask_draw.text((text_x, text_y_welcome),
                             welcome_config["text"], font=font_welcome, fill=255)
                mask_draw.text((text_x, text_y_username),
                             username_text, font=font_username, fill=255)

                # Redimensionner l'image de texture pour couvrir toute la zone de texte
                texture_resized = text_texture_image.resize(template.size, Image.Resampling.LANCZOS)

                # Créer une image avec la texture appliquée uniquement sur le texte
                textured_text = Image.new("RGBA", template.size, (0, 0, 0, 0))
                textured_text.paste(texture_resized, (0, 0))
                textured_text.putalpha(text_mask)

                # Coller l'image texturée sur le template (par-dessus la bordure noire)
                template = Image.alpha_composite(template, textured_text)
            else:
                # Dessiner le texte normalement avec les couleurs
                draw.text((text_x + shadow_offset, text_y_welcome + shadow_offset),
                         welcome_config["text"], font=font_welcome, fill=shadow_color)
                draw.text((text_x, text_y_welcome),
                         welcome_config["text"], font=font_welcome, fill=text_color)

                # Dessiner le nom d'utilisateur avec l'ombre
                draw.text((text_x + shadow_offset, text_y_username + shadow_offset),
                         username_text, font=font_username, fill=shadow_color)
                draw.text((text_x, text_y_username),
                         username_text, font=font_username, fill=text_color)

            # Si c'est un GIF animé, traiter toutes les frames
            if is_animated_gif:
                final_frames = []
                
                for frame_idx, bg_frame in enumerate(frames):
                    # Utiliser bg_frame comme template pour cette frame
                    current_template = bg_frame.copy()
                    
                    # Ajouter tous les éléments overlay sur cette frame
                    # Ajouter DefaultProfile derrière l'avatar si disponible
                    if default_profile and self.config.get("default_profile", {}).get("enabled", True):
                        default_profile_config = self.config["default_profile"]
                        default_profile_x = default_profile_config["x"]
                        default_profile_y = default_profile_config["y"]
                        current_template.paste(default_profile, (default_profile_x, default_profile_y), default_profile)

                    # Coller l'avatar circulaire sur le template
                    current_template.paste(avatar_circle, (circle_x, circle_y), avatar_circle)

                    # Ajouter la décoration de profil si disponible
                    if decoration and self.config.get("profile_decoration", {}).get("enabled", True):
                        decoration_config = self.config["profile_decoration"]
                        decoration_x = decoration_config["x"]
                        decoration_y = decoration_config["y"]
                        current_template.paste(decoration, (decoration_x, decoration_y), decoration)

                    # Ajouter le texte sur cette frame
                    draw = ImageDraw.Draw(current_template)
                    
                    if text_texture_image:
                        # Appliquer la texture de texte
                        border_thickness = 3
                        for adj in range(-border_thickness, border_thickness + 1):
                            for adj_y in range(-border_thickness, border_thickness + 1):
                                if adj != 0 or adj_y != 0:
                                    draw.text((text_x + adj, text_y_welcome + adj_y),
                                             welcome_config["text"], font=font_welcome, fill=(0, 0, 0, 255))
                                    draw.text((text_x + adj, text_y_username + adj_y),
                                             username_text, font=font_username, fill=(0, 0, 0, 255))

                        text_mask = Image.new('L', current_template.size, 0)
                        mask_draw = ImageDraw.Draw(text_mask)
                        mask_draw.text((text_x, text_y_welcome),
                                     welcome_config["text"], font=font_welcome, fill=255)
                        mask_draw.text((text_x, text_y_username),
                                     username_text, font=font_username, fill=255)

                        texture_resized = text_texture_image.resize(current_template.size, Image.Resampling.LANCZOS)
                        textured_text = Image.new("RGBA", current_template.size, (0, 0, 0, 0))
                        textured_text.paste(texture_resized, (0, 0))
                        textured_text.putalpha(text_mask)
                        current_template = Image.alpha_composite(current_template, textured_text)
                    else:
                        # Texte normal
                        draw.text((text_x + shadow_offset, text_y_welcome + shadow_offset),
                                 welcome_config["text"], font=font_welcome, fill=shadow_color)
                        draw.text((text_x, text_y_welcome),
                                 welcome_config["text"], font=font_welcome, fill=text_color)
                        draw.text((text_x + shadow_offset, text_y_username + shadow_offset),
                                 username_text, font=font_username, fill=shadow_color)
                        draw.text((text_x, text_y_username),
                                 username_text, font=font_username, fill=text_color)
                    
                    final_frames.append(current_template)
                
                # Sauvegarder le GIF animé
                output = io.BytesIO()
                final_frames[0].save(
                    output,
                    format='GIF',
                    save_all=True,
                    append_images=final_frames[1:],
                    duration=durations,
                    loop=0  # Boucle infinie
                )
                output.seek(0)
                return output
            else:
                # Image statique
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

        await interaction.response.defer()

        view = WelcomeSystemManagerView(self.bot, interaction.user.id)
        view.guild = interaction.guild

        # Generate preview image
        await view.generate_preview_image(interaction.user)

        embed = view.get_main_embed()
        view.update_buttons()

        await interaction.followup.send(embed=embed, view=view)

        # Store the active manager
        self.active_managers[interaction.user.id] = view

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Handle new member joining"""
        try:
            welcome_data = load_welcome_data()
            welcome_settings = welcome_data.get("welcome_settings", {})

            # Check if welcome system is enabled
            if not welcome_settings.get("enabled", False):
                return

            # Check if channel is configured
            channel_id = welcome_settings.get("channel_id")
            if not channel_id:
                return

            channel = member.guild.get_channel(channel_id)
            if not channel:
                return

            # Create welcome card
            welcome_card = await self.create_welcome_card(member)
            if not welcome_card:
                return

            # Get welcome message and replace {user} placeholder
            welcome_message = welcome_settings.get("welcome_message", "Welcome {user}!")
            welcome_message = welcome_message.replace("{user}", member.mention)

            # Determine file extension for the welcome card
            welcome_card.seek(0)
            file_header = welcome_card.read(10)
            welcome_card.seek(0)

            filename = "welcome.gif" if file_header.startswith(b'GIF') else "welcome.png"

            # Send welcome message with image
            file = discord.File(welcome_card, filename=filename)
            await channel.send(content=welcome_message, file=file)

        except Exception as e:
            print(f"Error in on_member_join: {e}")

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
                        elif manager.current_image_type == "content":
                            # Process content image (apply mask like profile outline)
                            processed_url = await self.process_content_image(local_file)
                            if processed_url:
                                if "default_profile" not in manager.config:
                                    manager.config["default_profile"] = {}
                                manager.config["default_profile"]["custom_image_url"] = processed_url
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

                        # Generate new preview
                        await manager.generate_preview_image(message.author)

                        # Update the manager view
                        if manager.current_image_type == "background":
                            manager.mode = "background_image"
                            embed = manager.get_background_image_embed()
                        elif manager.current_image_type == "content":
                            manager.mode = "content_image"
                            embed = manager.get_content_image_embed()
                        else:
                            manager.mode = "profile_outline_image"
                            embed = manager.get_background_image_embed()
                            embed.title = "<:ImageLOGO:1407072328134951043> Profile Outline Image"
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
            filename = f"{uuid.uuid4()}.png" # Default to png, will be changed if gif
            file_path = os.path.join('images', filename)

            # Download the image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        with open(file_path, 'wb') as f:
                            f.write(image_data)

                        # Determine correct extension
                        img_format = Image.open(io.BytesIO(image_data)).format
                        if img_format == 'GIF':
                            filename = f"{uuid.uuid4()}.gif"
                            file_path = os.path.join('images', filename)
                            with open(file_path, 'wb') as f:
                                f.write(image_data)
                        elif img_format in ['JPEG', 'PNG', 'WEBP', 'BMP', 'SVG']:
                             filename = f"{uuid.uuid4()}.{img_format.lower()}"
                             file_path = os.path.join('images', filename)
                             with open(file_path, 'wb') as f:
                                f.write(image_data)
                        else:
                             print(f"Unsupported image format: {img_format}")
                             return None


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

    async def process_content_image(self, image_url):
        """Process content image with masking similar to profile outline"""
        try:
            # Download the custom image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        image_data = await response.read()

            # Download the default profile image to use as mask
            default_profile_url = self.config.get("default_profile", {}).get("url", "https://raw.githubusercontent.com/TheBlueEL/pictures/refs/heads/main/DefaultProfile.png")
            async with aiohttp.ClientSession() as session:
                async with session.get(default_profile_url) as response:
                    if response.status == 200:
                        mask_data = await response.read()
                    else:
                        print("Failed to download default profile for masking")
                        return None

            # Open and process images
            custom_image = Image.open(io.BytesIO(image_data)).convert("RGBA")
            mask_image = Image.open(io.BytesIO(mask_data)).convert("RGBA")

            # Make custom image circular like the avatar
            width, height = custom_image.size
            if width != height:
                # Make it square by cropping from center
                min_dimension = min(width, height)
                left = (width - min_dimension) // 2
                top = (height - min_dimension) // 2
                custom_image = custom_image.crop((left, top, left + min_dimension, top + min_dimension))

            # Resize to match mask size
            custom_image = custom_image.resize(mask_image.size, Image.Resampling.LANCZOS)

            # Apply circular mask
            mask = Image.new('L', custom_image.size, 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, custom_image.size[0], custom_image.size[1]), fill=255)

            # Create final masked image
            masked_image = Image.new("RGBA", custom_image.size, (0, 0, 0, 0))
            masked_image.paste(custom_image, (0, 0))
            masked_image.putalpha(mask)

            # Save processed image
            os.makedirs('images', exist_ok=True)
            filename = f"{uuid.uuid4()}_content.png"
            file_path = os.path.join('images', filename)
            masked_image.save(file_path, 'PNG')

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
            print(f"Error processing content image: {e}")
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

            # Redimensionner à une taille standard pour éviter les problèmes de taille
            standard_size = 1024  # Taille standard pour les decorations
            square_image = square_image.resize((standard_size, standard_size), Image.Resampling.LANCZOS)

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
        self.preview_image_url = None

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
        if self.config.get("background_image"):
            bg = self.config["background_image"]
            config_status += f"<:RGBcodeLOGO:1408831982141575290> Background: Custom Image\n"
        elif self.config.get("background_color"):
            bg = self.config["background_color"]
            config_status += f"<:RGBcodeLOGO:1408831982141575290> Background: RGB({bg[0]}, {bg[1]}, {bg[2]})\n"
        else:
            config_status += "<:White:1407882887876968518> Background: Default\n"

        if self.config.get("profile_decoration", {}).get("enabled", True):
            config_status += "<:ParticipantsLOGO:1407733929389199460> Profile Outline: <:OnLOGO:1407072463883472978> Enabled\n"
        else:
            config_status += "<:ParticipantsLOGO:1407733929389199460> Profile Outline: <:OffLOGO:1407072621836894380> Disabled\n"

        embed.add_field(
            name="Current Configuration",
            value=config_status,
            inline=False
        )

        # Add preview image if available - avec timestamp pour forcer le refresh
        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            # Ajouter un timestamp pour éviter le cache Discord
            import time
            timestamp = int(time.time())
            if '?' in self.preview_image_url:
                image_url = self.preview_image_url.split('?')[0] + f"?refresh={timestamp}"
            else:
                image_url = self.preview_image_url + f"?refresh={timestamp}"
            embed.set_image(url=image_url)

        bot_name = get_bot_name(self.bot)
        embed.set_footer(text=f"{bot_name} | Welcome System", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_background_embed(self):
        # Recharger la configuration pour avoir les dernières modifications
        self.config = load_welcome_data()["template_config"]

        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Background Settings",
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

        # Add preview image if available
        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

        bot_name = get_bot_name(self.bot)
        embed.set_footer(text=f"{bot_name} | Background Settings", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_background_color_embed(self):
        # Recharger la configuration pour avoir les dernières modifications
        self.config = load_welcome_data()["template_config"]

        embed = discord.Embed(
            title="<:ColorLOGO:1408828590241615883> Background Color",
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

        # Add preview image if available
        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

        bot_name = get_bot_name(self.bot)
        embed.set_footer(text=f"{bot_name} | Background Color", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_background_image_embed(self):
        # Recharger la configuration pour avoir les dernières modifications
        self.config = load_welcome_data()["template_config"]

        embed = discord.Embed(
            title="<:ImageLOGO:1407072328134951043> Background Image",
            description="Set a custom background image for your welcome card",
            color=discord.Color.green()
        )

        if self.config.get("background_image"):
            embed.add_field(
                name="Current Image",
                value="<:SucessLOGO:1407071637840592977> Custom Image",
                inline=False
            )
        else:
            embed.add_field(
                name="Current Image",
                value="<:ErrorLOGO:1407071682031648850> No Custom image",
                inline=False
            )

        # Add preview image if available
        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

        bot_name = get_bot_name(self.bot)
        embed.set_footer(text=f"{bot_name} | Background Image", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_profile_outline_embed(self):
        # Recharger la configuration pour avoir les dernières modifications
        self.config = load_welcome_data()["template_config"]

        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Profile Outline Settings",
            description="Configure the profile decoration outline",
            color=discord.Color.orange()
        )

        profile_config = self.config.get("profile_decoration", {})
        enabled = profile_config.get("enabled", True)

        status = "<:OnLOGO:1407072463883472978> Enabled" if enabled else "<:OffLOGO:1407072621836894380> Disabled"
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
                value="<:SucessLOGO:1407071637840592977> Custom outline image set",
                inline=False
            )
        else:
            embed.add_field(
                name="Style",
                value="Default outline",
                inline=False
            )

        # Add preview image if available
        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

        bot_name = get_bot_name(self.bot)
        embed.set_footer(text=f"{bot_name} | Profile Outline", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_content_embed(self):
        # Recharger la configuration pour avoir les dernières modifications
        self.config = load_welcome_data()["template_config"]

        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Content Settings",
            description="Configure the content elements of your welcome card",
            color=discord.Color.purple()
        )

        # Show current configuration status
        config_status = ""

        # Text color status
        text_config = self.config.get("text_config", {})
        if text_config.get("text_color"):
            color = text_config["text_color"]
            config_status += f"<:TXTFileLOGO:1407735600752361622> Text Color: RGB({color[0]}, {color[1]}, {color[2]})\n"
        else:
            config_status += "<:TXTFileLOGO:1407735600752361622> Text Color: Default (White)\n"

        # Default profile status
        default_profile = self.config.get("default_profile", {})
        if default_profile.get("enabled", True):
            if default_profile.get("custom_image_url"):
                config_status += "<:ParticipantsLOGO:1407733929389199460> Default Profile: Custom Image\n"
            else:
                config_status += "<:ParticipantsLOGO:1407733929389199460> Default Profile: Default\n"
        else:
            config_status += "<:ParticipantsLOGO:1407733929389199460> Default Profile: <:OffLOGO:1407072621836894380> Disabled\n"

        embed.add_field(
            name="Current Configuration",
            value=config_status,
            inline=False
        )

        # Add preview image if available
        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

        bot_name = get_bot_name(self.bot)
        embed.set_footer(text=f"{bot_name} | Content Settings", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_content_color_embed(self):
        # Recharger la configuration pour avoir les dernières modifications
        self.config = load_welcome_data()["template_config"]

        embed = discord.Embed(
            title="<:ColorLOGO:1408828590241615883> Content Color",
            description="Choose how to set your text color",
            color=discord.Color.purple()
        )

        text_config = self.config.get("text_config", {})
        if text_config.get("text_color"):
            color = text_config["text_color"]
            embed.add_field(
                name="Current Text Color",
                value=f"RGB({color[0]}, {color[1]}, {color[2]})",
                inline=False
            )
        else:
            embed.add_field(
                name="Current Text Color",
                value="White (Default)",
                inline=False
            )

        # Add preview image if available
        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

        bot_name = get_bot_name(self.bot)
        embed.set_footer(text=f"{bot_name} | Content Color", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_content_image_embed(self):
        # Recharger la configuration pour avoir les dernières modifications
        self.config = load_welcome_data()["template_config"]

        embed = discord.Embed(
            title="<:ImageLOGO:1407072328134951043> Content Image",
            description="Set a custom default profile image",
            color=discord.Color.green()
        )

        default_profile = self.config.get("default_profile", {})
        if default_profile.get("custom_image_url"):
            embed.add_field(
                name="Current Image",
                value="<:SucessLOGO:1407071637840592977> Custom Image",
                inline=False
            )
        else:
            embed.add_field(
                name="Current Image",
                value="Using default image",
                inline=False
            )

        # Add preview image if available
        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

        bot_name = get_bot_name(self.bot)
        embed.set_footer(text=f"{bot_name} | Content Image", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_settings_embed(self):
        """Get settings embed"""
        welcome_data = load_welcome_data()
        welcome_settings = welcome_data.get("welcome_settings", {})

        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Welcome System Settings",
            description="Configure the welcome system behavior",
            color=discord.Color.blue()
        )

        # System status
        enabled = welcome_settings.get("enabled", False)
        status = "<:OnLOGO:1407072463883472978> Enabled" if enabled else "<:OffLOGO:1407072621836894380> Disabled"

        # Channel status
        channel_id = welcome_settings.get("channel_id")
        if channel_id and hasattr(self, 'guild'):
            channel = self.guild.get_channel(channel_id)
            channel_text = f"#{channel.name}" if channel else "Channel not found"
        else:
            channel_text = "Not configured"

        # Welcome message
        welcome_message = welcome_settings.get("welcome_message", "Welcome {user}!")

        embed.add_field(
            name="System Status",
            value=status,
            inline=False
        )

        embed.add_field(
            name="Welcome Channel",
            value=channel_text,
            inline=False
        )

        embed.add_field(
            name="Welcome Message",
            value=f"`{welcome_message}`",
            inline=False
        )

        # Add preview image if available
        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

        bot_name = get_bot_name(self.bot)
        embed.set_footer(text=f"{bot_name} | Welcome Settings", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_channel_selection_embed(self):
        """Get channel selection embed"""
        embed = discord.Embed(
            title="<:ChannelLOGO:1407733929389199460> Select Welcome Channel",
            description="Choose the channel where welcome messages will be sent",
            color=discord.Color.green()
        )

        welcome_data = load_welcome_data()
        welcome_settings = welcome_data.get("welcome_settings", {})
        channel_id = welcome_settings.get("channel_id")

        if channel_id and hasattr(self, 'guild'):
            channel = self.guild.get_channel(channel_id)
            if channel:
                embed.add_field(
                    name="Current Channel",
                    value=f"#{channel.name}",
                    inline=False
                )

        bot_name = get_bot_name(self.bot)
        embed.set_footer(text=f"{bot_name} | Channel Selection", icon_url=self.bot.user.display_avatar.url)

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

    async def generate_preview_image(self, interaction_user):
        """Generate preview image and upload it to GitHub"""
        try:
            # Recharger la configuration pour avoir les dernières modifications
            self.config = load_welcome_data()["template_config"]

            welcome_system = WelcomeSystem(self.bot)
            welcome_system.config = self.config  # S'assurer que le welcome_system utilise la config mise à jour

            preview_image = await welcome_system.create_welcome_card(interaction_user)

            if preview_image:
                # Save preview to temp file avec timestamp pour éviter les conflicts
                os.makedirs('images', exist_ok=True)
                import time
                timestamp = int(time.time())

                # Déterminer l'extension basée sur le contenu
                preview_image.seek(0)
                file_header = preview_image.read(10)
                preview_image.seek(0)

                if file_header.startswith(b'GIF'):
                    filename = f"welcome_preview_{self.user_id}_{timestamp}.gif"
                else:
                    filename = f"welcome_preview_{self.user_id}_{timestamp}.png"

                file_path = os.path.join('images', filename)

                with open(file_path, 'wb') as f:
                    f.write(preview_image.getvalue())

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

                        # Set GitHub raw URL avec timestamp pour forcer le refresh
                        filename = os.path.basename(file_path)
                        self.preview_image_url = f"https://raw.githubusercontent.com/TheBlueEL/pictures/main/{filename}?t={timestamp}"
                        return True
                except ImportError:
                    print("GitHub sync not available")

        except Exception as e:
            print(f"Error generating preview: {e}")

        return False

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
                emoji="<:HEXcodeLOGO:1408833347404304434>"
            )
            hex_button.callback = self.background_hex_color

            rgb_button = discord.ui.Button(
                label="RGB Code",
                style=discord.ButtonStyle.secondary,
                emoji="<:RGBcodeLOGO:1408831982141575290>"
            )
            rgb_button.callback = self.background_rgb_color

            reset_button = discord.ui.Button(
                label="Reset",
                style=discord.ButtonStyle.danger,
                emoji="<:UpdateLOGO:1407072818214080695>"
            )
            reset_button.callback = self.reset_background_color

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )
            back_button.callback = self.back_to_background

            self.add_item(hex_button)
            self.add_item(rgb_button)
            self.add_item(reset_button)
            self.add_item(back_button)

        elif self.mode == "background":
            # Background main buttons
            color_button = discord.ui.Button(
                label="Color",
                style=discord.ButtonStyle.primary,
                emoji="<:ColorLOGO:1408828590241615883>"
            )
            color_button.callback = self.background_color_settings

            image_button = discord.ui.Button(
                label="Image",
                style=discord.ButtonStyle.secondary,
                emoji="<:ImageLOGO:1407072328134951043>"
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
                emoji="<:HEXcodeLOGO:1408833347404304434>"
            )
            hex_button.callback = self.profile_outline_hex_color

            rgb_button = discord.ui.Button(
                label="RGB Code",
                style=discord.ButtonStyle.secondary,
                emoji="<:RGBcodeLOGO:1408831982141575290>"
            )
            rgb_button.callback = self.profile_outline_rgb_color

            reset_button = discord.ui.Button(
                label="Reset",
                style=discord.ButtonStyle.danger,
                emoji="<:UpdateLOGO:1407072818214080695>"
            )
            reset_button.callback = self.reset_profile_outline_color

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )
            back_button.callback = self.back_to_profile_outline

            self.add_item(hex_button)
            self.add_item(rgb_button)
            self.add_item(reset_button)
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

            clear_button = discord.ui.Button(
                label="Clear Image",
                style=discord.ButtonStyle.danger,
                emoji="<:DeleteLOGO:1407071421363916841>"
            )
            clear_button.callback = self.clear_profile_outline_image

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )
            back_button.callback = self.back_to_profile_outline

            self.add_item(url_button)
            self.add_item(upload_button)
            self.add_item(clear_button)
            self.add_item(back_button)

        elif self.mode == "content":
            # Content main buttons
            color_button = discord.ui.Button(
                label="Color",
                style=discord.ButtonStyle.primary,
                emoji="<:ColorLOGO:1408828590241615883>"
            )
            color_button.callback = self.content_color_settings

            image_button = discord.ui.Button(
                label="Image",
                style=discord.ButtonStyle.secondary,
                emoji="<:ImageLOGO:1407072328134951043>"
            )
            image_button.callback = self.content_image_settings

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )
            back_button.callback = self.back_to_main

            self.add_item(color_button)
            self.add_item(image_button)
            self.add_item(back_button)

        elif self.mode == "content_color":
            # Content color buttons
            hex_button = discord.ui.Button(
                label="Hex Code",
                style=discord.ButtonStyle.primary,
                emoji="<:HEXcodeLOGO:1408833347404304434>"
            )
            hex_button.callback = self.content_hex_color

            rgb_button = discord.ui.Button(
                label="RGB Code",
                style=discord.ButtonStyle.secondary,
                emoji="<:RGBcodeLOGO:1408831982141575290>"
            )
            rgb_button.callback = self.content_rgb_color

            reset_button = discord.ui.Button(
                label="Reset",
                style=discord.ButtonStyle.danger,
                emoji="<:UpdateLOGO:1407072818214080695>"
            )
            reset_button.callback = self.reset_content_color

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )
            back_button.callback = self.back_to_content

            self.add_item(hex_button)
            self.add_item(rgb_button)
            self.add_item(reset_button)
            self.add_item(back_button)

        elif self.mode == "content_image":
            # Content image buttons
            url_button = discord.ui.Button(
                label="Set URL",
                style=discord.ButtonStyle.primary,
                emoji="<:URLLOGO:1407071963809054931>"
            )
            url_button.callback = self.content_image_url

            upload_button = discord.ui.Button(
                label="Upload Image",
                style=discord.ButtonStyle.secondary,
                emoji="<:UploadLOGO:1407072005567545478>"
            )
            upload_button.callback = self.upload_content_image

            clear_button = discord.ui.Button(
                label="Clear Image",
                style=discord.ButtonStyle.danger,
                emoji="<:DeleteLOGO:1407071421363916841>"
            )
            clear_button.callback = self.clear_content_image

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )
            back_button.callback = self.back_to_content

            self.add_item(url_button)
            self.add_item(upload_button)
            self.add_item(clear_button)
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
                emoji="<:ColorLOGO:1408828590241615883>"
            )
            color_button.callback = self.profile_outline_color_settings

            image_button = discord.ui.Button(
                label="Image",
                style=discord.ButtonStyle.secondary,
                emoji="<:ImageLOGO:1407072328134951043>"
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

        elif self.mode == "settings":
            # Settings buttons
            welcome_data = load_welcome_data()
            welcome_settings = welcome_data.get("welcome_settings", {})
            enabled = welcome_settings.get("enabled", False)

            toggle_button = discord.ui.Button(
                label="ON" if enabled else "OFF",
                style=discord.ButtonStyle.success if enabled else discord.ButtonStyle.danger,
                emoji="<:OnLOGO:1407072463883472978>" if enabled else "<:OffLOGO:1407072621836894380>",
                row=0
            )
            toggle_button.callback = self.toggle_welcome_system

            channel_button = discord.ui.Button(
                label="Channel",
                style=discord.ButtonStyle.primary,
                emoji="<:ChannelLOGO:1407733929389199460>",
                row=0
            )
            channel_button.callback = self.channel_selection

            content_button = discord.ui.Button(
                label="Content",
                style=discord.ButtonStyle.secondary,
                emoji="<:TXTFileLOGO:1407735600752361622>",
                row=0
            )
            content_button.callback = self.welcome_message_settings

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>",
                row=1
            )
            back_button.callback = self.back_to_main

            self.add_item(toggle_button)
            self.add_item(channel_button)
            self.add_item(content_button)
            self.add_item(back_button)

        elif self.mode == "channel_selection":
            # Channel selection with dropdown
            if hasattr(self, 'guild') and self.guild:
                channel_select = WelcomeChannelSelect(self.guild)
                self.add_item(channel_select)

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )
            back_button.callback = self.back_to_settings
            self.add_item(back_button)

        else:  # main mode
            # Main buttons - Row 1
            background_button = discord.ui.Button(
                label="Background",
                style=discord.ButtonStyle.primary,
                emoji="<:BackgroundLOGO:1408834163309805579>",
                row=0
            )
            background_button.callback = self.background_settings

            content_button = discord.ui.Button(
                label="Content",
                style=discord.ButtonStyle.secondary,
                emoji="<:DescriptionLOGO:1407733417172533299>",
                row=0
            )
            content_button.callback = self.content_settings

            profile_outline_button = discord.ui.Button(
                label="Profile Outline",
                style=discord.ButtonStyle.secondary,
                emoji="<:ProfileLOGO:1408830057819930806>",
                row=0
            )
            profile_outline_button.callback = self.profile_outline_settings

            # Main buttons - Row 2
            settings_button = discord.ui.Button(
                label="Settings",
                style=discord.ButtonStyle.secondary,
                emoji="<:SettingLOGO:1407071854593839239>",
                row=1
            )
            settings_button.callback = self.system_settings

            close_button = discord.ui.Button(
                label="Close",
                style=discord.ButtonStyle.danger,
                emoji="<:CloseLOGO:1391531593524318271>",
                row=1
            )
            close_button.callback = self.close_embed

            self.add_item(background_button)
            self.add_item(content_button)
            self.add_item(profile_outline_button)
            self.add_item(settings_button)
            self.add_item(close_button)

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
        # Defer response immediately to avoid timeout
        try:
            await interaction.response.defer()
        except discord.InteractionResponded:
            pass

        self.config.pop("background_image", None)
        self.save_config()

        # Generate new preview après suppression de l'image de fond
        print("🔄 Régénération de la prévisualisation après suppression de l'image de fond...")
        await self.generate_preview_image(interaction.user)

        embed = self.get_background_image_embed()
        self.update_buttons()

        try:
            await interaction.edit_original_response(embed=embed, view=self)
        except discord.NotFound:
            # Interaction expired, try followup
            try:
                await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)
            except:
                pass

    async def reset_background_color(self, interaction: discord.Interaction):
        # Defer response immediately to avoid timeout
        try:
            await interaction.response.defer()
        except discord.InteractionResponded:
            pass

        # Set default background color (white/gray mix)
        self.config["background_color"] = [240, 240, 240]  # Light gray
        self.config.pop("background_image", None)
        self.save_config()

        # Generate new preview avec la couleur par défaut
        print("🔄 Régénération de la prévisualisation après reset couleur de fond...")
        await self.generate_preview_image(interaction.user)

        embed = self.get_background_color_embed()
        self.update_buttons()

        try:
            await interaction.edit_original_response(embed=embed, view=self)
        except discord.NotFound:
            # Interaction expired, try followup
            try:
                await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)
            except:
                pass

    # Content callbacks
    async def content_settings(self, interaction: discord.Interaction):
        self.mode = "content"
        embed = self.get_content_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def content_color_settings(self, interaction: discord.Interaction):
        self.mode = "content_color"
        embed = self.get_content_color_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def content_image_settings(self, interaction: discord.Interaction):
        self.mode = "content_image"
        embed = self.get_content_image_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def content_hex_color(self, interaction: discord.Interaction):
        modal = ContentHexColorModal(self)
        await interaction.response.send_modal(modal)

    async def content_rgb_color(self, interaction: discord.Interaction):
        modal = ContentRGBColorModal(self)
        await interaction.response.send_modal(modal)

    async def content_image_url(self, interaction: discord.Interaction):
        modal = ContentImageURLModal(self)
        await interaction.response.send_modal(modal)

    async def upload_content_image(self, interaction: discord.Interaction):
        self.waiting_for_image = True
        self.current_image_type = "content"
        embed = self.get_waiting_image_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def clear_content_image(self, interaction: discord.Interaction):
        if "default_profile" not in self.config:
            self.config["default_profile"] = {}
        self.config["default_profile"].pop("custom_image_url", None)
        self.save_config()

        # Generate new preview après suppression de l'image de contenu
        print("🔄 Régénération de la prévisualisation après suppression de l'image de contenu...")
        await self.generate_preview_image(interaction.user)

        embed = self.get_content_image_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def reset_content_color(self, interaction: discord.Interaction):
        # Defer response immediately to avoid timeout
        try:
            await interaction.response.defer()
        except discord.InteractionResponded:
            pass

        if "text_config" not in self.config:
            self.config["text_config"] = {}
        # Set default text color (white)
        self.config["text_config"]["text_color"] = [255, 255, 255, 255]
        self.save_config()

        # Generate new preview avec la couleur par défaut (blanc)
        print("🔄 Régénération de la prévisualisation après reset couleur de texte...")
        await self.generate_preview_image(interaction.user)

        embed = self.get_content_color_embed()
        self.update_buttons()

        try:
            await interaction.edit_original_response(embed=embed, view=self)
        except discord.NotFound:
            # Interaction expired, try followup
            try:
                await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)
            except:
                pass

    # Profile outline callbacks
    async def profile_outline_settings(self, interaction: discord.Interaction):
        self.mode = "profile_outline"
        embed = self.get_profile_outline_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def toggle_profile_outline(self, interaction: discord.Interaction):
        # Defer response immediately to avoid timeout
        try:
            await interaction.response.defer()
        except discord.InteractionResponded:
            pass

        if "profile_decoration" not in self.config:
            self.config["profile_decoration"] = {}
        current_state = self.config["profile_decoration"].get("enabled", True)
        self.config["profile_decoration"]["enabled"] = not current_state
        self.save_config()

        # Generate new preview avec le nouveau statut du profile outline
        print("🔄 Régénération de la prévisualisation après toggle profile outline...")
        await self.generate_preview_image(interaction.user)

        embed = self.get_profile_outline_embed()
        self.update_buttons()

        try:
            await interaction.edit_original_response(embed=embed, view=self)
        except discord.NotFound:
            # Interaction expired, try followup
            try:
                await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)
            except:
                pass

    async def profile_outline_color_settings(self, interaction: discord.Interaction):
        self.mode = "profile_outline_color"
        embed = self.get_background_color_embed()  # Reuse color embed design
        embed.title = "<:ColorLOGO:1408828590241615883> Profile Outline Color"
        embed.description = "Choose how to set your profile outline color"

        # Add preview image if available
        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def profile_outline_image_settings(self, interaction: discord.Interaction):
        self.mode = "profile_outline_image"
        embed = self.get_background_image_embed()  # Reuse image embed design
        embed.title = "🖼️ Profile Outline Image"
        embed.description = "Set a custom profile outline image"

        # Add preview image if available
        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

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

    async def clear_profile_outline_image(self, interaction: discord.Interaction):
        if "profile_decoration" not in self.config:
            self.config["profile_decoration"] = {}
        self.config["profile_decoration"].pop("custom_image", None)
        self.config["profile_decoration"].pop("color_override", None)
        self.save_config()

        # Generate new preview après suppression de l'image de profile outline
        print("🔄 Régénération de la prévisualisation après suppression de l'image de profile outline...")
        await self.generate_preview_image(interaction.user)

        embed = self.get_profile_outline_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def reset_profile_outline_color(self, interaction: discord.Interaction):
        # Defer response immediately to avoid timeout
        try:
            await interaction.response.defer()
        except discord.InteractionResponded:
            pass

        if "profile_decoration" not in self.config:
            self.config["profile_decoration"] = {}
        # Remove custom overrides to use default white outline
        self.config["profile_decoration"].pop("color_override", None)
        self.config["profile_decoration"].pop("custom_image", None)
        self.save_config()

        # Generate new preview avec l'outline par défaut (blanc)
        print("🔄 Régénération de la prévisualisation après reset couleur profile outline...")
        await self.generate_preview_image(interaction.user)

        embed = self.get_profile_outline_embed()
        self.update_buttons()

        try:
            await interaction.edit_original_response(embed=embed, view=self)
        except discord.NotFound:
            # Interaction expired, try followup
            try:
                await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)
            except:
                pass

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

    async def back_to_content(self, interaction: discord.Interaction):
        self.mode = "content"
        embed = self.get_content_embed()
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
        elif self.current_image_type == "content":
            self.mode = "content_image"
            embed = self.get_content_image_embed()
        else:
            self.mode = "profile_outline_image"
            embed = self.get_background_image_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Profile Outline Image"
            embed.description = "Set a custom profile outline image"

            # Add preview image if available
            if hasattr(self, 'preview_image_url') and self.preview_image_url:
                embed.set_image(url=self.preview_image_url)

        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    # New callback methods
    async def system_settings(self, interaction: discord.Interaction):
        self.mode = "settings"
        embed = self.get_settings_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def toggle_welcome_system(self, interaction: discord.Interaction):
        welcome_data = load_welcome_data()
        if "welcome_settings" not in welcome_data:
            welcome_data["welcome_settings"] = {}

        current_state = welcome_data["welcome_settings"].get("enabled", False)
        welcome_data["welcome_settings"]["enabled"] = not current_state

        # Save to file
        with open('welcome_data.json', 'w', encoding='utf-8') as f:
            json.dump(welcome_data, f, indent=2, ensure_ascii=False)

        embed = self.get_settings_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def channel_selection(self, interaction: discord.Interaction):
        self.mode = "channel_selection"
        embed = self.get_channel_selection_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def welcome_message_settings(self, interaction: discord.Interaction):
        modal = WelcomeMessageModal(self)
        await interaction.response.send_modal(modal)

    async def back_to_settings(self, interaction: discord.Interaction):
        self.mode = "settings"
        embed = self.get_settings_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def close_embed(self, interaction: discord.Interaction):
        """Close the welcome system embed"""
        # Remove from active managers
        if interaction.user.id in self.bot.get_cog('WelcomeSystem').active_managers:
            del self.bot.get_cog('WelcomeSystem').active_managers[interaction.user.id]

        # Delete the message entirely
        await interaction.response.defer()
        await interaction.delete_original_response()


# Modal classes for color and URL inputs
class ContentHexColorModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='🎨 Content Text Hex Color')
        self.view = view

        # Get current color value
        current_color = ""
        text_config = self.view.config.get("text_config", {})
        if text_config.get("text_color"):
            rgb = text_config["text_color"]
            current_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

        self.hex_input = discord.ui.TextInput(
            label='Hex Color Code',
            placeholder='#FFFFFF or FFFFFF',
            required=True,
            max_length=7,
            default=current_color
        )
        self.add_item(self.hex_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        hex_value = self.hex_input.value.strip()
        if hex_value.startswith('#'):
            hex_value = hex_value[1:]

        try:
            rgb = tuple(int(hex_value[i:i+2], 16) for i in (0, 2, 4))
            if "text_config" not in self.view.config:
                self.view.config["text_config"] = {}
            self.view.config["text_config"]["text_color"] = list(rgb)
            self.view.save_config()

            # Generate new preview avec la nouvelle configuration
            print("🔄 Régénération de la prévisualisation après changement de couleur de texte...")
            await self.view.generate_preview_image(interaction.user)

            embed = self.view.get_content_color_embed()
            self.view.update_buttons()
            await interaction.edit_original_response(embed=embed, view=self.view)
        except ValueError:
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid Hex Color",
                description="Please enter a valid hex color code (e.g., #FF0000 or FF0000)",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

class ContentRGBColorModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='🌈 Content Text RGB Color')
        self.view = view

        # Get current color values
        current_r, current_g, current_b = "255", "255", "255"
        text_config = self.view.config.get("text_config", {})
        if text_config.get("text_color"):
            rgb = text_config["text_color"]
            current_r, current_g, current_b = str(rgb[0]), str(rgb[1]), str(rgb[2])

        self.red_input = discord.ui.TextInput(
            label='Red (0-255)',
            placeholder='255',
            required=True,
            max_length=3,
            default=current_r
        )
        self.green_input = discord.ui.TextInput(
            label='Green (0-255)',
            placeholder='255',
            required=True,
            max_length=3,
            default=current_g
        )
        self.blue_input = discord.ui.TextInput(
            label='Blue (0-255)',
            placeholder='255',
            required=True,
            max_length=3,
            default=current_b
        )

        self.add_item(self.red_input)
        self.add_item(self.green_input)
        self.add_item(self.blue_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        try:
            r = int(self.red_input.value)
            g = int(self.green_input.value)
            b = int(self.blue_input.value)

            if not all(0 <= val <= 255 for val in [r, g, b]):
                raise ValueError("Values must be between 0 and 255")

            if "text_config" not in self.view.config:
                self.view.config["text_config"] = {}
            self.view.config["text_config"]["text_color"] = [r, g, b]
            self.view.save_config()

            # Generate new preview avec la nouvelle configuration
            print("🔄 Régénération de la prévisualisation après changement RGB...")
            await self.view.generate_preview_image(interaction.user)

            embed = self.view.get_content_color_embed()
            self.view.update_buttons()
            await interaction.edit_original_response(embed=embed, view=self.view)
        except ValueError:
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid RGB Values",
                description="Please enter valid RGB values (0-255 for each color)",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

class ContentImageURLModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='🖼️ Content Image URL')
        self.view = view

        self.url_input = discord.ui.TextInput(
            label='Image URL',
            placeholder='https://example.com/image.png',
            required=True,
            max_length=500
        )
        self.add_item(self.url_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        url = self.url_input.value.strip()
        if not url.startswith(('http://', 'https://')):
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid URL",
                description="Please enter a valid HTTP or HTTPS URL",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return

        # Process the image with masking
        processed_url = await self.view.process_content_image(url)
        if processed_url:
            if "default_profile" not in self.view.config:
                self.view.config["default_profile"] = {}
            self.view.config["default_profile"]["custom_image_url"] = processed_url
            self.view.save_config()

            # Generate new preview avec la nouvelle image
            print("🔄 Régénération de la prévisualisation après changement d'image de contenu...")
            await self.view.generate_preview_image(interaction.user)

            embed = self.view.get_content_image_embed()
            self.view.update_buttons()
            await interaction.edit_original_response(embed=embed, view=self.view)
        else:
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Processing Failed",
                description="Failed to process the image. Please try again.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

class BackgroundHexColorModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='🎨 Background Hex Color')
        self.view = view

        # Get current color value
        current_color = ""
        if self.view.config.get("background_color"):
            rgb = self.view.config["background_color"]
            current_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

        self.hex_input = discord.ui.TextInput(
            label='Hex Color Code',
            placeholder='#FFFFFF or FFFFFF',
            required=True,
            max_length=7,
            default=current_color
        )
        self.add_item(self.hex_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        hex_value = self.hex_input.value.strip()
        if hex_value.startswith('#'):
            hex_value = hex_value[1:]

        try:
            rgb = tuple(int(hex_value[i:i+2], 16) for i in (0, 2, 4))
            self.view.config["background_color"] = list(rgb)
            self.view.config.pop("background_image", None)  # Remove image if setting color
            self.view.save_config()

            # Generate new preview avec la nouvelle configuration
            print("🔄 Régénération de la prévisualisation après changement de couleur...")
            await self.view.generate_preview_image(interaction.user)

            embed = self.view.get_background_color_embed()
            self.view.update_buttons()
            await interaction.edit_original_response(embed=embed, view=self.view)
        except ValueError:
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid Hex Color",
                description="Please enter a valid hex color code (e.g., #FF0000 or FF0000)",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

class BackgroundRGBColorModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='🌈 Background RGB Color')
        self.view = view

        # Get current color values
        current_r, current_g, current_b = "0", "0", "0"
        if self.view.config.get("background_color"):
            rgb = self.view.config["background_color"]
            current_r, current_g, current_b = str(rgb[0]), str(rgb[1]), str(rgb[2])

        self.red_input = discord.ui.TextInput(
            label='Red (0-255)',
            placeholder='255',
            required=True,
            max_length=3,
            default=current_r
        )
        self.green_input = discord.ui.TextInput(
            label='Green (0-255)',
            placeholder='255',
            required=True,
            max_length=3,
            default=current_g
        )
        self.blue_input = discord.ui.TextInput(
            label='Blue (0-255)',
            placeholder='255',
            required=True,
            max_length=3,
            default=current_b
        )

        self.add_item(self.red_input)
        self.add_item(self.green_input)
        self.add_item(self.blue_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        try:
            r = int(self.red_input.value)
            g = int(self.green_input.value)
            b = int(self.blue_input.value)

            if not all(0 <= val <= 255 for val in [r, g, b]):
                raise ValueError("Values must be between 0 and 255")

            self.view.config["background_color"] = [r, g, b]
            self.view.config.pop("background_image", None)  # Remove image if setting color
            self.view.save_config()

            # Generate new preview avec la nouvelle configuration
            print("🔄 Régénération de la prévisualisation après changement RGB...")
            await self.view.generate_preview_image(interaction.user)

            embed = self.view.get_background_color_embed()
            self.view.update_buttons()
            await interaction.edit_original_response(embed=embed, view=self.view)
        except ValueError:
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid RGB Values",
                description="Please enter valid RGB values (0-255 for each color)",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

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
        await interaction.response.defer()

        url = self.url_input.value.strip()
        if not url.startswith(('http://', 'https://')):
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid URL",
                description="Please enter a valid HTTP or HTTPS URL",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return

        self.view.config["background_image"] = url
        self.view.config.pop("background_color", None)  # Remove color if setting image
        self.view.save_config()

        # Generate new preview avec la nouvelle image de fond
        print("🔄 Régénération de la prévisualisation après changement d'image de fond...")
        await self.view.generate_preview_image(interaction.user)

        embed = self.view.get_background_image_embed()
        self.view.update_buttons()
        await interaction.edit_original_response(embed=embed, view=self.view)

class ProfileOutlineHexColorModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='🎨 Profile Outline Hex Color')
        self.view = view

        # Get current color value
        current_color = ""
        profile_config = self.view.config.get("profile_decoration", {})
        if profile_config.get("color_override"):
            rgb = profile_config["color_override"]
            current_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

        self.hex_input = discord.ui.TextInput(
            label='Hex Color Code',
            placeholder='#FFFFFF or FFFFFF',
            required=True,
            max_length=7,
            default=current_color
        )
        self.add_item(self.hex_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

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

            # Generate new preview
            await self.view.generate_preview_image(interaction.user)

            embed = self.view.get_profile_outline_embed()
            self.view.update_buttons()
            await interaction.edit_original_response(embed=embed, view=self.view)
        except ValueError:
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid Hex Color",
                description="Please enter a valid hex color code (e.g., #FF0000 or FF0000)",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

class ProfileOutlineRGBColorModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='🌈 Profile Outline RGB Color')
        self.view = view

        # Get current color values
        current_r, current_g, current_b = "0", "0", "0"
        profile_config = self.view.config.get("profile_decoration", {})
        if profile_config.get("color_override"):
            rgb = profile_config["color_override"]
            current_r, current_g, current_b = str(rgb[0]), str(rgb[1]), str(rgb[2])

        self.red_input = discord.ui.TextInput(
            label='Red (0-255)',
            placeholder='255',
            required=True,
            max_length=3,
            default=current_r
        )
        self.green_input = discord.ui.TextInput(
            label='Green (0-255)',
            placeholder='255',
            required=True,
            max_length=3,
            default=current_g
        )
        self.blue_input = discord.ui.TextInput(
            label='Blue (0-255)',
            placeholder='255',
            required=True,
            max_length=3,
            default=current_b
        )

        self.add_item(self.red_input)
        self.add_item(self.green_input)
        self.add_item(self.blue_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

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

            # Generate new preview
            await self.view.generate_preview_image(interaction.user)

            embed = self.view.get_profile_outline_embed()
            self.view.update_buttons()
            await interaction.edit_original_response(embed=embed, view=self.view)
        except ValueError:
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid RGB Values",
                description="Please enter valid RGB values (0-255 for each color)",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

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
        await interaction.response.defer()

        url = self.url_input.value.strip()
        if not url.startswith(('http://', 'https://')):
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid URL",
                description="Please enter a valid HTTP or HTTPS URL",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return

        if "profile_decoration" not in self.view.config:
            self.view.config["profile_decoration"] = {}
        self.view.config["profile_decoration"]["custom_image"] = url
        self.view.config["profile_decoration"].pop("color_override", None)
        self.view.save_config()

        # Generate new preview
        await self.view.generate_preview_image(interaction.user)

        embed = self.view.get_profile_outline_embed()
        self.view.update_buttons()
        await interaction.edit_original_response(embed=embed, view=self.view)

class WelcomeChannelSelect(discord.ui.Select):
    def __init__(self, guild):
        self.guild = guild
        options = []

        # Get all text channels
        text_channels = [ch for ch in guild.channels if isinstance(ch, discord.TextChannel)]

        for channel in text_channels[:25]:  # Discord limit of 25 options
            options.append(discord.SelectOption(
                label=f"#{channel.name}",
                description=f"Category: {channel.category.name if channel.category else 'No category'}",
                value=str(channel.id)
            ))

        if not options:
            options.append(discord.SelectOption(
                label="No channels available",
                description="No text channels found",
                value="none"
            ))

        super().__init__(
            placeholder="Select a welcome channel...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            return

        channel_id = int(self.values[0])

        # Save the selected channel
        welcome_data = load_welcome_data()
        if "welcome_settings" not in welcome_data:
            welcome_data["welcome_settings"] = {}

        welcome_data["welcome_settings"]["channel_id"] = channel_id

        with open('welcome_data.json', 'w', encoding='utf-8') as f:
            json.dump(welcome_data, f, indent=2, ensure_ascii=False)

        # Go back to settings
        parent_view = self.view
        parent_view.mode = "settings"
        embed = parent_view.get_settings_embed()
        parent_view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=parent_view)

class WelcomeMessageModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='💬 Welcome Message')
        self.view = view

        welcome_data = load_welcome_data()
        current_message = welcome_data.get("welcome_settings", {}).get("welcome_message", "Welcome {user}!")

        self.message_input = discord.ui.TextInput(
            label='Welcome Message',
            placeholder='Welcome {user}! Use {user} to mention the new member',
            required=True,
            max_length=2000,
            style=discord.TextStyle.paragraph,
            default=current_message
        )
        self.add_item(self.message_input)

    async def on_submit(self, interaction: discord.Interaction):
        welcome_data = load_welcome_data()
        if "welcome_settings" not in welcome_data:
            welcome_data["welcome_settings"] = {}

        welcome_data["welcome_settings"]["welcome_message"] = self.message_input.value

        with open('welcome_data.json', 'w', encoding='utf-8') as f:
            json.dump(welcome_data, f, indent=2, ensure_ascii=False)

        # Go back to settings
        self.view.mode = "settings"
        embed = self.view.get_settings_embed()
        self.view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self.view)

async def setup(bot):
    await bot.add_cog(WelcomeSystem(bot))
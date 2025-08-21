import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import aiohttp
import uuid
from datetime import datetime
import time
from PIL import Image, ImageDraw
import numpy as np
import io

def get_bot_name(bot):
    """Récupère le nom d'affichage du bot"""
    return bot.user.display_name if bot.user else "Bot"

class ConverterData:
    def __init__(self):
        self.image_url = ""
        self.image_width = 0
        self.image_height = 0
        self.pixelated_url = ""

class PixelsConverterView(discord.ui.View):
    def __init__(self, bot, user_id):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.converter_data = ConverterData()
        self.colors_data = self.load_colors()
        self.current_mode = "main"  # main, add_image, waiting_for_image, image_preview, color_selection, settings
        self.waiting_for_image = False
        self.color_page = 0
        self.colors_per_page = 8  # 2 rows of 4

    def load_colors(self):
        try:
            with open('converters_data.json', 'r') as f:
                data = json.load(f)
                # Ajouter le support des couleurs cachées si pas présent
                for color in data.get("colors", []):
                    if "hidden" not in color:
                        color["hidden"] = False
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            # Return default data if file doesn't exist
            return {
                "colors": [],
                "settings": {"dithering": False, "semi_transparent": False},
                "user_data": {}
            }

    def save_colors(self):
        with open('converters_data.json', 'w') as f:
            json.dump(self.colors_data, f, indent=2)

    def get_active_colors(self):
        """Récupère les couleurs activées dans la palette"""
        return [c for c in self.colors_data["colors"] if c.get("enabled", False)]

    def rgb_distance_advanced(self, color1, color2):
        """Calcule la distance entre deux couleurs RGB avec l'algorithme optimisé du script JS"""
        r1, g1, b1 = color1
        r2, g2, b2 = color2
        
        # Algorithme de distance couleur optimisé (basé sur https://www.compuphase.com/cmetric.htm)
        rmean = (r1 + r2) / 2
        rdiff = r1 - r2
        gdiff = g1 - g2
        bdiff = b1 - b2
        
        # Utilisation d'entiers pour éviter l'erreur de bit shift sur float
        x = int((512 + rmean) * rdiff * rdiff) >> 8
        y = 4 * gdiff * gdiff
        z = int((767 - rmean) * bdiff * bdiff) >> 8
        
        return (x + y + z) ** 0.5

    def find_closest_color(self, pixel_color, palette):
        """Trouve la couleur la plus proche dans la palette"""
        min_distance = float('inf')
        closest_color = palette[0]["rgb"]

        for color in palette:
            # Ignorer les couleurs cachées
            color_key = f"{color['rgb'][0]},{color['rgb'][1]},{color['rgb'][2]}"
            if color.get("hidden", False):
                continue
                
            distance = self.rgb_distance_advanced(pixel_color, color["rgb"])
            if distance < min_distance:
                min_distance = distance
                closest_color = color["rgb"]

        return closest_color

    def clamp_byte(self, value):
        """Limite la valeur entre 0 et 255"""
        return max(0, min(255, int(value)))

    def floyd_steinberg_dithering(self, image, palette):
        """Applique le dithering Floyd-Steinberg avancé basé sur le script JS"""
        if image.mode != 'RGB':
            image = image.convert('RGB')
            
        width, height = image.size
        img_array = np.array(image, dtype=float)
        
        # Buffer flottant pour porter l'erreur de diffusion
        buf = img_array.copy()
        
        for y in range(height):
            for x in range(width):
                # Pixel actuel
                r, g, b = buf[y, x]
                
                # Quantifier vers la couleur la plus proche de la palette
                closest_rgb = self.find_closest_color([int(r), int(g), int(b)], palette)
                nr, ng, nb = closest_rgb
                
                # Écrire la couleur quantifiée
                img_array[y, x] = [nr, ng, nb]
                
                # Calculer l'erreur
                er = r - nr
                eg = g - ng
                eb = b - nb
                
                # Diffuser l'erreur aux pixels voisins (Floyd-Steinberg)
                def push_error(xx, yy, fraction):
                    if 0 <= xx < width and 0 <= yy < height:
                        buf[yy, xx, 0] = self.clamp_byte(buf[yy, xx, 0] + er * fraction)
                        buf[yy, xx, 1] = self.clamp_byte(buf[yy, xx, 1] + eg * fraction)
                        buf[yy, xx, 2] = self.clamp_byte(buf[yy, xx, 2] + eb * fraction)
                
                push_error(x + 1, y, 7/16)      # droite
                push_error(x - 1, y + 1, 3/16)  # bas-gauche  
                push_error(x, y + 1, 5/16)      # bas
                push_error(x + 1, y + 1, 1/16)  # bas-droite

        return Image.fromarray(np.clip(img_array, 0, 255).astype(np.uint8))

    def quantize_colors_advanced(self, image, palette):
        """Réduit l'image aux couleurs de la palette définie avec l'algorithme avancé"""
        if not palette:
            return image

        # Convertir l'image en mode RGB si nécessaire
        if image.mode != 'RGB':
            image = image.convert('RGB')

        img_array = np.array(image)
        height, width, channels = img_array.shape

        # Créer une nouvelle image avec les couleurs quantifiées
        quantized_array = np.zeros_like(img_array)
        
        # Gérer la transparence
        transparent_hide_active = self.colors_data["settings"].get("semi_transparent", False)

        for y in range(height):
            for x in range(width):
                pixel_color = img_array[y, x]
                
                # Trouver la couleur la plus proche
                closest_color = self.find_closest_color(pixel_color, palette)
                color_key = f"{closest_color[0]},{closest_color[1]},{closest_color[2]}"
                
                # Vérifier si la couleur est cachée
                is_hidden = any(
                    color.get("hidden", False) 
                    for color in palette 
                    if color["rgb"] == list(closest_color)
                )
                
                if is_hidden:
                    # Rendre transparent si caché
                    quantized_array[y, x] = [0, 0, 0]  # Sera rendu transparent plus tard
                else:
                    quantized_array[y, x] = closest_color

        return Image.fromarray(quantized_array.astype(np.uint8))

    def pixelate_image(self, image, pixel_size):
        """Pixelise l'image en réduisant puis agrandissant"""
        # Obtenir la taille originale
        original_size = image.size

        # Réduire l'image
        small_size = (original_size[0] // pixel_size, original_size[1] // pixel_size)
        if small_size[0] < 1:
            small_size = (1, small_size[1])
        if small_size[1] < 1:
            small_size = (small_size[0], 1)

        small_image = image.resize(small_size, Image.Resampling.NEAREST)

        # Agrandir l'image avec des pixels nets
        pixelated = small_image.resize(original_size, Image.Resampling.NEAREST)

        return pixelated

    def create_default_palette(self):
        """Crée la palette par défaut à partir du JSON"""
        default_palette = [
            [0,0,0], [60,60,60], [120,120,120], [170,170,170], [210,210,210], [255,255,255],
            [96,0,24], [165,14,30], [237,28,36], [250,128,114], [228,92,26], [255,127,39], [246,170,9],
            [249,221,59], [255,250,188], [156,132,49], [197,173,49], [232,212,95], [74,107,58], [90,148,74], [132,197,115],
            [14,185,104], [19,230,123], [135,255,94], [12,129,110], [16,174,166], [19,225,190], [15,121,159], [96,247,242],
            [187,250,242], [40,80,158], [64,147,228], [125,199,255], [77,49,184], [107,80,246], [153,177,251],
            [74,66,132], [122,113,196], [181,174,241], [170,56,185], [224,159,249],
            [203,0,122], [236,31,128], [243,141,169], [155,82,73], [209,128,120], [250,182,164],
            [104,70,52], [149,104,42], [219,164,99], [123,99,82], [156,132,107], [214,181,148],
            [209,128,81], [248,178,119], [255,197,165], [109,100,63], [148,140,107], [205,197,158],
            [51,57,65], [109,117,141], [179,185,209]
        ]
        return default_palette

    def find_closest_color_fast(self, pixel_rgb, palette):
        """Version rapide de la recherche de couleur la plus proche"""
        min_distance = float('inf')
        closest_color = [0, 0, 0]
        
        r, g, b = pixel_rgb
        
        for palette_color in palette:
            pr, pg, pb = palette_color
            
            # Algorithme optimisé de distance couleur
            rmean = (r + pr) / 2
            rdiff = r - pr
            gdiff = g - pg
            bdiff = b - pb
            
            x = int((512 + rmean) * rdiff * rdiff) >> 8
            y = 4 * gdiff * gdiff
            z = int((767 - rmean) * bdiff * bdiff) >> 8
            
            distance = (x + y + z) ** 0.5
            
            if distance < min_distance:
                min_distance = distance
                closest_color = palette_color
        
        return closest_color

    async def process_image_fast(self):
        """Version rapide du traitement d'image inspirée du code JavaScript"""
        if not self.converter_data.image_url:
            return None

        try:
            # Télécharger l'image
            async with aiohttp.ClientSession() as session:
                async with session.get(self.converter_data.image_url) as response:
                    if response.status != 200:
                        return None
                    image_data = await response.read()

            # Ouvrir l'image avec PIL
            image = Image.open(io.BytesIO(image_data))

            # Redimensionner l'image selon les dimensions spécifiées
            target_size = (self.converter_data.image_width, self.converter_data.image_height)
            if image.size != target_size:
                image = image.resize(target_size, Image.Resampling.LANCZOS)

            # Convertir en RGB
            if image.mode != 'RGB':
                if image.mode in ('RGBA', 'LA', 'P'):
                    # Créer un fond blanc pour les images transparentes
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    if image.mode == 'P':
                        image = image.convert('RGBA')
                    if image.mode == 'RGBA':
                        background.paste(image, mask=image.split()[-1])
                    else:
                        background.paste(image)
                    image = background
                else:
                    image = image.convert('RGB')

            # Utiliser la palette par défaut
            palette = self.create_default_palette()
            
            # Traitement pixel par pixel super rapide
            img_array = np.array(image)
            height, width, _ = img_array.shape
            
            # Vectorisation pour plus de rapidité
            reshaped = img_array.reshape(-1, 3)
            processed = np.zeros_like(reshaped)
            
            for i in range(len(reshaped)):
                closest = self.find_closest_color_fast(reshaped[i], palette)
                processed[i] = closest
            
            # Reconstruire l'image
            processed_array = processed.reshape(height, width, 3)
            processed_image = Image.fromarray(processed_array.astype(np.uint8))

            # Sauvegarder l'image traitée
            os.makedirs('images', exist_ok=True)
            filename = f"processed_{uuid.uuid4()}.png"
            file_path = os.path.join('images', filename)
            processed_image.save(file_path, 'PNG')

            # Synchroniser avec GitHub
            from github_sync import GitHubSync
            github_sync = GitHubSync()
            sync_success = await github_sync.sync_image_to_pictures_repo(file_path)

            if sync_success:
                try:
                    os.remove(file_path)
                except:
                    pass

                github_url = f"https://raw.githubusercontent.com/TheBlueEL/pictures/main/{filename}"
                self.converter_data.pixelated_url = github_url
                return github_url

            return None

        except Exception as e:
            print(f"Erreur lors du traitement rapide de l'image: {e}")
            return None

    async def process_image(self):
        """Traite l'image selon les paramètres sélectionnés avec l'algorithme avancé"""
        if not self.converter_data.image_url:
            return None

        try:
            # Télécharger l'image
            async with aiohttp.ClientSession() as session:
                async with session.get(self.converter_data.image_url) as response:
                    if response.status != 200:
                        return None
                    image_data = await response.read()

            # Ouvrir l'image avec PIL
            image = Image.open(io.BytesIO(image_data))

            # Redimensionner l'image selon les dimensions spécifiées
            target_size = (self.converter_data.image_width, self.converter_data.image_height)
            if image.size != target_size:
                image = image.resize(target_size, Image.Resampling.LANCZOS)

            # Convertir en RGB si nécessaire
            if image.mode in ('RGBA', 'LA', 'P'):
                if not self.colors_data["settings"]["semi_transparent"]:
                    # Créer un fond blanc pour les images transparentes
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    if image.mode == 'P':
                        image = image.convert('RGBA')
                    if image.mode == 'RGBA':
                        background.paste(image, mask=image.split()[-1])
                    else:
                        background.paste(image)
                    image = background
                else:
                    image = image.convert('RGBA')
            else:
                image = image.convert('RGB')

            # Obtenir la palette de couleurs actives
            active_colors = self.get_active_colors()

            # Si aucune couleur n'est activée, utiliser toutes les couleurs gratuites par défaut
            if not active_colors:
                for color in self.colors_data["colors"]:
                    if not color["premium"]:
                        color["enabled"] = True
                self.save_colors()
                active_colors = self.get_active_colors()

            # Appliquer la quantification des couleurs avec l'algorithme avancé
            if active_colors:
                if self.colors_data["settings"]["dithering"]:
                    processed = self.floyd_steinberg_dithering(image, active_colors)
                else:
                    processed = self.quantize_colors_advanced(image, active_colors)
            else:
                processed = image

            # Sauvegarder l'image traitée
            os.makedirs('images', exist_ok=True)
            filename = f"pixelated_{uuid.uuid4()}.png"
            file_path = os.path.join('images', filename)
            processed.save(file_path, 'PNG')

            # Synchroniser avec GitHub
            from github_sync import GitHubSync
            github_sync = GitHubSync()
            sync_success = await github_sync.sync_image_to_pictures_repo(file_path)

            if sync_success:
                try:
                    os.remove(file_path)
                except:
                    pass

                github_url = f"https://raw.githubusercontent.com/TheBlueEL/pictures/main/{filename}"
                self.converter_data.pixelated_url = github_url
                return github_url

            return None

        except Exception as e:
            print(f"Erreur lors du traitement de l'image: {e}")
            return None

    def get_main_embed(self, username):
        embed = discord.Embed(
            title="<:CreateLOGO:1407071205026168853> Wplace Convertor",
            description=f"Welcome back {username}!\n\nConvert your images to Wplace-compatible pixel art with customizable color palettes and settings.",
            color=0x5865F2
        )

        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Pixels Converter", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_add_image_embed(self):
        embed = discord.Embed(
            title="<:CreateLOGO:1407071205026168853> Add Image",
            description="Choose how you want to add your image for conversion:",
            color=0x00D166
        )

        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Add Image", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_waiting_image_embed(self):
        embed = discord.Embed(
            title="<:UploadLOGO:1407072005567545478> Upload Image",
            description="Please send an image file in this channel.\n\n**Only you can upload the image for security reasons.**",
            color=discord.Color.blue()
        )

        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Upload Image", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_image_preview_embed(self):
        total_pixels = self.converter_data.image_width * self.converter_data.image_height
        embed = discord.Embed(
            title="<:CreateLOGO:1407071205026168853> Wplace Convertor",
            description=f"**Width:** {self.converter_data.image_width}px\n**Height:** {self.converter_data.image_height}px\n**Total Pixels:** {total_pixels:,}px",
            color=0x5865F2
        )

        # Afficher l'image pixelisée si disponible, sinon l'originale
        image_to_show = self.converter_data.pixelated_url if self.converter_data.pixelated_url else self.converter_data.image_url
        if image_to_show:
            embed.set_image(url=image_to_show)

        # Informations sur le traitement
        active_colors = self.get_active_colors()
        dithering_status = "ON" if self.colors_data["settings"]["dithering"] else "OFF"

        embed.add_field(
            name="Processing Info",
            value=f"**Colors:** {len(active_colors)}\n**Dithering:** {dithering_status}",
            inline=True
        )

        bot_name = get_bot_name(self.bot)
        embed.set_footer(text=f"{bot_name} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_color_selection_embed(self):
        free_colors = [c for c in self.colors_data["colors"] if not c["premium"] and c["enabled"]]
        premium_colors = [c for c in self.colors_data["colors"] if c["premium"] and c["enabled"]]
        total_colors = len(free_colors) + len(premium_colors)

        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Color Selection",
            description=f"**FREE Colors:** {len(free_colors)}\n**PREMIUM Colors:** {len(premium_colors)}\n**Total Active:** {total_colors}",
            color=discord.Color.purple()
        )

        # Show current page info
        total_pages = (len(self.colors_data["colors"]) + self.colors_per_page - 1) // self.colors_per_page
        embed.add_field(
            name="Page Info",
            value=f"Page {self.color_page + 1} of {total_pages}",
            inline=False
        )

        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Color Selection", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_settings_embed(self):
        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Converter Settings",
            description="Configure advanced settings for image conversion:",
            color=discord.Color.orange()
        )

        dithering_status = "ON" if self.colors_data["settings"]["dithering"] else "OFF"
        semi_transparent_status = "ON" if self.colors_data["settings"]["semi_transparent"] else "OFF"

        embed.add_field(
            name="Current Settings",
            value=f"**Dithering:** {dithering_status}\n**Semi-Transparent:** {semi_transparent_status}",
            inline=False
        )

        embed.add_field(
            name="Dithering Info",
            value="Adds noise to create gradient effects with limited colors (Floyd-Steinberg algorithm)",
            inline=False
        )

        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Settings", icon_url=self.bot.user.display_avatar.url)

        return embed

    def update_buttons(self):
        self.clear_items()

        if self.current_mode == "main":
            add_image_button = discord.ui.Button(
                label="Add Image",
                style=discord.ButtonStyle.success,
                emoji="<:CreateLOGO:1407071205026168853>"
            )

            async def add_image_callback(interaction):
                self.current_mode = "add_image"
                embed = self.get_add_image_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            add_image_button.callback = add_image_callback
            self.add_item(add_image_button)

        elif self.current_mode == "add_image":
            image_url_button = discord.ui.Button(
                label="Image URL",
                style=discord.ButtonStyle.primary,
                emoji="<:URLLOGO:1407071963809054931>"
            )

            async def image_url_callback(interaction):
                modal = ImageURLModal(self.converter_data, self)
                await interaction.response.send_modal(modal)

            image_url_button.callback = image_url_callback

            upload_image_button = discord.ui.Button(
                label="Upload Image",
                style=discord.ButtonStyle.secondary,
                emoji="<:UploadLOGO:1407072005567545478>"
            )

            async def upload_image_callback(interaction):
                self.current_mode = "waiting_for_image"
                self.waiting_for_image = True
                embed = self.get_waiting_image_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            upload_image_button.callback = upload_image_callback

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )

            async def back_callback(interaction):
                self.current_mode = "main"
                username = f"@{interaction.user.display_name}"
                embed = self.get_main_embed(username)
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            back_button.callback = back_callback

            self.add_item(image_url_button)
            self.add_item(upload_image_button)
            self.add_item(back_button)

        elif self.current_mode == "waiting_for_image":
            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )

            async def back_callback(interaction):
                self.waiting_for_image = False
                self.current_mode = "add_image"
                embed = self.get_add_image_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            back_button.callback = back_callback
            self.add_item(back_button)

        elif self.current_mode == "image_preview":
            # Dimension control buttons
            shrink_button = discord.ui.Button(
                label="Less",
                style=discord.ButtonStyle.secondary,
                emoji="🔽"
            )

            async def shrink_callback(interaction):
                await interaction.response.defer()
                
                # Réduire proportionnellement width et height
                scale_factor = 0.9  # Réduction de 10%
                new_width = max(10, int(self.converter_data.image_width * scale_factor))
                new_height = max(10, int(self.converter_data.image_height * scale_factor))
                
                self.converter_data.image_width = new_width
                self.converter_data.image_height = new_height
                
                # Reprocesser l'image immédiatement avec les nouvelles dimensions
                processed_url = await self.process_image_fast()
                if processed_url:
                    self.converter_data.pixelated_url = processed_url
                
                embed = self.get_image_preview_embed()
                await interaction.followup.edit_message(message_id=interaction.message.id, embed=embed, view=self)

            shrink_button.callback = shrink_callback

            enlarge_button = discord.ui.Button(
                label="More",
                style=discord.ButtonStyle.secondary,
                emoji="🔼"
            )

            async def enlarge_callback(interaction):
                await interaction.response.defer()
                
                # Agrandir proportionnellement width et height
                scale_factor = 1.1  # Augmentation de 10%
                new_width = int(self.converter_data.image_width * scale_factor)
                new_height = int(self.converter_data.image_height * scale_factor)
                
                # Limiter à une taille maximale raisonnable
                max_size = 2000
                if new_width > max_size or new_height > max_size:
                    if new_width > new_height:
                        new_height = int(new_height * (max_size / new_width))
                        new_width = max_size
                    else:
                        new_width = int(new_width * (max_size / new_height))
                        new_height = max_size
                
                self.converter_data.image_width = new_width
                self.converter_data.image_height = new_height
                
                # Reprocesser l'image immédiatement avec les nouvelles dimensions
                processed_url = await self.process_image_fast()
                if processed_url:
                    self.converter_data.pixelated_url = processed_url
                
                embed = self.get_image_preview_embed()
                await interaction.followup.edit_message(message_id=interaction.message.id, embed=embed, view=self)

            enlarge_button.callback = enlarge_callback

            # Process button
            process_button = discord.ui.Button(
                label="Process Image",
                style=discord.ButtonStyle.success,
                emoji="⚡"
            )

            async def process_callback(interaction):
                await interaction.response.defer()

                # Traiter l'image
                processed_url = await self.process_image()

                if processed_url:
                    embed = self.get_image_preview_embed()
                    await interaction.followup.edit_message(message_id=interaction.message.id, embed=embed, view=self)
                else:
                    error_embed = discord.Embed(
                        title="<:ErrorLOGO:1407071682031648850> Processing Failed",
                        description="Failed to process the image. Please try again.",
                        color=discord.Color.red()
                    )
                    await interaction.followup.send(embed=error_embed, ephemeral=True)

            process_button.callback = process_callback

            # Color button
            color_button = discord.ui.Button(
                label="Colors",
                style=discord.ButtonStyle.primary,
                emoji="🎨"
            )

            async def color_callback(interaction):
                self.current_mode = "color_selection"
                self.color_page = 0
                embed = self.get_color_selection_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            color_button.callback = color_callback

            # Settings button
            settings_button = discord.ui.Button(
                label="Settings",
                style=discord.ButtonStyle.secondary,
                emoji="<:SettingLOGO:1407071854593839239>"
            )

            async def settings_callback(interaction):
                self.current_mode = "settings"
                embed = self.get_settings_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            settings_button.callback = settings_callback

            # Back button
            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )

            async def back_callback(interaction):
                self.current_mode = "main"
                username = f"@{interaction.user.display_name}"
                embed = self.get_main_embed(username)
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            back_button.callback = back_callback

            self.add_item(shrink_button)
            self.add_item(enlarge_button)
            self.add_item(process_button)
            self.add_item(color_button)
            self.add_item(settings_button)
            self.add_item(back_button)

        elif self.current_mode == "color_selection":
            # Navigation row
            total_pages = (len(self.colors_data["colors"]) + self.colors_per_page - 1) // self.colors_per_page

            # Left arrow
            left_arrow = discord.ui.Button(
                label="◀",
                style=discord.ButtonStyle.gray if self.color_page == 0 else discord.ButtonStyle.primary,
                disabled=self.color_page == 0,
                row=0
            )

            async def left_callback(interaction):
                if self.color_page > 0:
                    self.color_page -= 1
                    embed = self.get_color_selection_embed()
                    self.update_buttons()
                    await interaction.response.edit_message(embed=embed, view=self)

            left_arrow.callback = left_callback

            # Active All button
            all_free_enabled = all(c["enabled"] for c in self.colors_data["colors"] if not c["premium"])
            active_all_button = discord.ui.Button(
                label="Disable All FREE" if all_free_enabled else "Enable All FREE",
                style=discord.ButtonStyle.danger if all_free_enabled else discord.ButtonStyle.success,
                row=0
            )

            async def active_all_callback(interaction):
                new_state = not all_free_enabled
                for color in self.colors_data["colors"]:
                    if not color["premium"]:
                        color["enabled"] = new_state
                self.save_colors()
                embed = self.get_color_selection_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            active_all_button.callback = active_all_callback

            # Back button
            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>",
                row=0
            )

            async def back_callback(interaction):
                self.current_mode = "image_preview"
                embed = self.get_image_preview_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            back_button.callback = back_callback

            # Right arrow
            right_arrow = discord.ui.Button(
                label="▶",
                style=discord.ButtonStyle.gray if self.color_page >= total_pages - 1 else discord.ButtonStyle.primary,
                disabled=self.color_page >= total_pages - 1,
                row=0
            )

            async def right_callback(interaction):
                if self.color_page < total_pages - 1:
                    self.color_page += 1
                    embed = self.get_color_selection_embed()
                    self.update_buttons()
                    await interaction.response.edit_message(embed=embed, view=self)

            right_arrow.callback = right_callback

            self.add_item(left_arrow)
            self.add_item(active_all_button)
            self.add_item(back_button)
            self.add_item(right_arrow)

            # Color buttons (2 rows of 4)
            start_idx = self.color_page * self.colors_per_page
            end_idx = min(start_idx + self.colors_per_page, len(self.colors_data["colors"]))

            for i, color_idx in enumerate(range(start_idx, end_idx)):
                color = self.colors_data["colors"][color_idx]
                row = 1 + (i // 4)  # Start from row 1

                button = discord.ui.Button(
                    label=color["name"][:15],  # Truncate long names
                    style=discord.ButtonStyle.success if color["enabled"] else discord.ButtonStyle.danger,
                    emoji=color["emoji"],
                    row=row
                )

                def create_color_callback(color_index):
                    async def color_callback(interaction):
                        self.colors_data["colors"][color_index]["enabled"] = not self.colors_data["colors"][color_index]["enabled"]
                        self.save_colors()
                        embed = self.get_color_selection_embed()
                        self.update_buttons()
                        await interaction.response.edit_message(embed=embed, view=self)
                    return color_callback

                button.callback = create_color_callback(color_idx)
                self.add_item(button)

        elif self.current_mode == "settings":
            # Dithering button
            dithering_button = discord.ui.Button(
                label="Dithering",
                style=discord.ButtonStyle.success if self.colors_data["settings"]["dithering"] else discord.ButtonStyle.danger,
                emoji="<:ONLOGO:1391530620366094440>" if self.colors_data["settings"]["dithering"] else "<:OFFLOGO:1391535388065271859>"
            )

            async def dithering_callback(interaction):
                self.colors_data["settings"]["dithering"] = not self.colors_data["settings"]["dithering"]
                self.save_colors()
                embed = self.get_settings_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            dithering_button.callback = dithering_callback

            # Semi-transparent button
            semi_transparent_button = discord.ui.Button(
                label="Semi-Transparent",
                style=discord.ButtonStyle.success if self.colors_data["settings"]["semi_transparent"] else discord.ButtonStyle.danger,
                emoji="<:ONLOGO:1391530620366094440>" if self.colors_data["settings"]["semi_transparent"] else "<:OFFLOGO:1391535388065271859>"
            )

            async def semi_transparent_callback(interaction):
                self.colors_data["settings"]["semi_transparent"] = not self.colors_data["settings"]["semi_transparent"]
                self.save_colors()
                embed = self.get_settings_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            semi_transparent_button.callback = semi_transparent_callback

            # Back button
            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )

            async def back_callback(interaction):
                self.current_mode = "image_preview"
                embed = self.get_image_preview_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            back_button.callback = back_callback

            self.add_item(dithering_button)
            self.add_item(semi_transparent_button)
            self.add_item(back_button)

class ImageURLModal(discord.ui.Modal):
    def __init__(self, converter_data, parent_view):
        super().__init__(title='Set Image URL')
        self.converter_data = converter_data
        self.parent_view = parent_view

        self.url_input = discord.ui.TextInput(
            label='Image URL',
            placeholder='https://example.com/image.png',
            required=True,
            max_length=500
        )

        self.add_item(self.url_input)

    async def on_submit(self, interaction: discord.Interaction):
        image_url = self.url_input.value.strip()

        # Check if URL is accessible and get image dimensions
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        image_data = await response.read()

                        # Obtenir les vraies dimensions avec PIL
                        from PIL import Image
                        import io
                        image = Image.open(io.BytesIO(image_data))

                        self.converter_data.image_url = image_url
                        self.converter_data.image_width = image.width
                        self.converter_data.image_height = image.height
                        self.converter_data.pixelated_url = ""  # Reset processed image

                        # Traiter automatiquement l'image avec la palette par défaut
                        processed_url = await self.parent_view.process_image_fast()
                        if processed_url:
                            self.converter_data.pixelated_url = processed_url

                        self.parent_view.current_mode = "image_preview"
                        embed = self.parent_view.get_image_preview_embed()
                        self.parent_view.update_buttons()
                        await interaction.response.edit_message(embed=embed, view=self.parent_view)
                    else:
                        raise Exception("Image not found")
        except Exception as e:
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Image Not Found",
                description="The provided URL does not contain a valid image or is not accessible.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

class ConvertersCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_managers = {}

    async def download_image(self, image_url):
        """Download image from URL, save locally, sync to GitHub, then delete locally"""
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
                        from github_sync import GitHubSync
                        github_sync = GitHubSync()
                        sync_success = await github_sync.sync_image_to_pictures_repo(file_path)

                        if sync_success:
                            # Delete local file after successful sync
                            try:
                                os.remove(file_path)
                                print(f"<:SucessLOGO:1407071637840592977> Fichier local supprimé: {file_path}")
                            except Exception as e:
                                print(f"<:ErrorLOGO:1407071682031648850> Erreur lors de la suppression locale: {e}")

                            # Return GitHub raw URL from public pictures repo
                            filename = os.path.basename(file_path)
                            github_url = f"https://raw.githubusercontent.com/TheBlueEL/pictures/main/{filename}"
                            return github_url
                        else:
                            print("<:ErrorLOGO:1407071682031648850> Échec de la synchronisation, fichier local conservé")
                            return None
            return None
        except Exception as e:
            print(f"Error downloading image: {e}")
            return None

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        user_id = message.author.id
        if user_id in self.active_managers:
            manager = self.active_managers[user_id]
            if manager.waiting_for_image and message.attachments:
                attachment = message.attachments[0]
                allowed_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg']
                if any(attachment.filename.lower().endswith(ext) for ext in allowed_extensions):
                    local_file = await self.download_image(attachment.url)

                    if local_file:
                        try:
                            await message.delete()
                        except:
                            pass

                        # Create confirmation embed showing the uploaded image
                        success_embed = discord.Embed(
                            title="<:SucessLOGO:1407071637840592977> Image Successfully Uploaded",
                            description="Your image has been uploaded and synchronized with GitHub!\n\nClick **Continue** to proceed with the conversion.",
                            color=discord.Color.green()
                        )
                        success_embed.set_image(url=local_file)

                        # Create continue button
                        continue_button = discord.ui.Button(
                            label="Continue",
                            style=discord.ButtonStyle.success,
                            emoji="<:SucessLOGO:1407071637840592977>"
                        )

                        async def continue_callback(interaction):
                            # Get real image dimensions
                            try:
                                async with aiohttp.ClientSession() as session:
                                    async with session.get(local_file) as response:
                                        if response.status == 200:
                                            image_data = await response.read()
                                            from PIL import Image
                                            import io
                                            image = Image.open(io.BytesIO(image_data))

                                            manager.converter_data.image_url = local_file
                                            manager.converter_data.image_width = image.width
                                            manager.converter_data.image_height = image.height
                                            manager.converter_data.pixelated_url = ""  # Reset processed image
                                            manager.current_mode = "image_preview"
                                            manager.waiting_for_image = False

                                            # Traiter automatiquement l'image avec la palette par défaut
                                            processed_url = await manager.process_image_fast()
                                            if processed_url:
                                                manager.converter_data.pixelated_url = processed_url

                                            embed = manager.get_image_preview_embed()
                                            manager.update_buttons()
                                            await interaction.response.edit_message(embed=embed, view=manager)
                            except Exception as e:
                                print(f"Error getting image dimensions: {e}")
                                # Fallback to default dimensions
                                manager.converter_data.image_url = local_file
                                manager.converter_data.image_width = 800
                                manager.converter_data.image_height = 600
                                manager.converter_data.pixelated_url = ""
                                manager.current_mode = "image_preview"
                                manager.waiting_for_image = False

                                # Traiter automatiquement l'image avec la palette par défaut
                                processed_url = await manager.process_image_fast()
                                if processed_url:
                                    manager.converter_data.pixelated_url = processed_url

                                embed = manager.get_image_preview_embed()
                                manager.update_buttons()
                                await interaction.response.edit_message(embed=embed, view=manager)

                        continue_button.callback = continue_callback

                        # Create a temporary view with the continue button
                        temp_view = discord.ui.View(timeout=300)
                        temp_view.add_item(continue_button)

                        # Add back button
                        back_button = discord.ui.Button(
                            label="Back",
                            style=discord.ButtonStyle.gray,
                            emoji="<:BackLOGO:1391511633431494666>"
                        )

                        async def back_callback(interaction):
                            manager.waiting_for_image = False
                            manager.current_mode = "add_image"
                            embed = manager.get_add_image_embed()
                            manager.update_buttons()
                            await interaction.response.edit_message(embed=embed, view=manager)

                        back_button.callback = back_callback
                        temp_view.add_item(back_button)

                        # Update the message
                        try:
                            channel = message.channel
                            async for msg in channel.history(limit=50):
                                if msg.author == self.bot.user and msg.embeds:
                                    if "Upload Image" in msg.embeds[0].title:
                                        await msg.edit(embed=success_embed, view=temp_view)
                                        break
                        except Exception as e:
                            print(f"Error updating message: {e}")
                else:
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
                        await message.channel.send(embed=error_embed, delete_after=5)
                    except:
                        pass

    @app_commands.command(name="pixels_convertor", description="Convert images to Wplace-compatible pixel art")
    async def pixels_convertor_command(self, interaction: discord.Interaction):
        username = f"@{interaction.user.display_name}"
        view = PixelsConverterView(self.bot, interaction.user.id)
        embed = view.get_main_embed(username)
        view.update_buttons()

        self.active_managers[interaction.user.id] = view

        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

async def setup(bot):
    await bot.add_cog(ConvertersCommand(bot))
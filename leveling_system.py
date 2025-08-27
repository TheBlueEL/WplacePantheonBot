
import discord
from discord.ext import commands
from discord import app_commands
import json
import aiohttp
import io
from PIL import Image, ImageDraw, ImageFont, ImageOps
import time
import math
import uuid
import os

# Data management functions
def load_leveling_data():
    try:
        with open('leveling_data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "leveling_settings": {
                "enabled": True,
                "xp_settings": {
                    "messages": {"enabled": True, "xp_per_message": 20, "cooldown": 10},
                    "characters": {"enabled": False, "xp_per_character": 1, "character_limit": 20, "cooldown": 10}
                },
                "rewards": {"roles": {}, "custom": {}},
                "customization_permissions": {
                    "background": {
                        "enabled": True,
                        "image_permission_level": 0,
                        "color_permission_level": 0
                    },
                    "avatar_outline": {
                        "enabled": True,
                        "image_permission_level": 0,
                        "color_permission_level": 0
                    },
                    "username": {
                        "enabled": True,
                        "color_permission_level": 0
                    },
                    "bar_progress": {
                        "enabled": True,
                        "color_permission_level": 0
                    },
                    "content": {
                        "enabled": True,
                        "color_permission_level": 0
                    }
                },
                "level_card": {
                    "background_image": "https://raw.githubusercontent.com/TheBlueEL/pictures/refs/heads/main/LevelBar.png",
                    "profile_position": {"x": 50, "y": 50, "size": 150},
                    "username_position": {"x": 220, "y": 80, "font_size": 60},
                    "level_position": {"x": 220, "y": 140, "font_size": 40},
                    "xp_bar_position": {"x": 30, "y": 726, "width": 1988, "height": 30},
                    "username_color": [0, 0, 0],  # Default username color (black)
                    "level_color": [245, 55, 48], # Default level color (red)
                    "xp_bar_color": [245, 55, 48], # Default XP bar color (red)
                    "background_color": [245, 55, 48], # Default background color (red)
                    "xp_text_color": [154, 154, 154], # Default XP text color (gray)
                    "profile_outline": {
                        "enabled": True,
                        "url": "https://raw.githubusercontent.com/TheBlueEL/pictures/refs/heads/main/ProfileOutline.png",
                        "color": [255, 255, 255]
                    }
                }
            },
            "user_data": {},
            "user_level_cards": {}
        }

def load_user_level_card_config(user_id):
    """Load user-specific level card configuration"""
    data = load_leveling_data()
    user_id_str = str(user_id)

    # If user has custom config, return it
    if user_id_str in data.get("user_level_cards", {}):
        return data["user_level_cards"][user_id_str]

    # Otherwise return default config
    return data["leveling_settings"]["level_card"].copy()

def save_user_level_card_config(user_id, config):
    """Save user-specific level card configuration"""
    data = load_leveling_data()
    user_id_str = str(user_id)

    if "user_level_cards" not in data:
        data["user_level_cards"] = {}

    data["user_level_cards"][user_id_str] = config
    save_leveling_data(data)

def save_leveling_data(data):
    with open('leveling_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def calculate_xp_for_level(level):
    """Calculate XP needed for a specific level"""
    if level <= 1:
        return 0
    base_xp = 100
    total_xp = 0
    for i in range(1, level):
        level_xp = math.ceil(base_xp * (1.1 ** (i - 1)))
        total_xp += level_xp
    return total_xp

def get_level_from_xp(xp):
    """Get level from total XP"""
    level = 1
    while calculate_xp_for_level(level + 1) <= xp:
        level += 1
    return level

def get_xp_for_next_level(current_xp):
    """Get XP needed for next level"""
    current_level = get_level_from_xp(current_xp)
    next_level_xp = calculate_xp_for_level(current_level + 1)
    current_level_xp = calculate_xp_for_level(current_level)
    xp_needed_for_next = next_level_xp - current_level_xp
    current_xp_in_level = current_xp - current_level_xp
    return xp_needed_for_next, current_xp_in_level

class LevelingSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_cooldowns = {}

    async def download_image(self, url):
        """Download image from URL"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.read()
            return None
        except Exception as e:
            print(f"Error downloading image {url}: {e}")
            return None

    def create_circle_mask(self, size):
        """Create circular mask for profile picture"""
        mask = Image.new('L', size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size[0], size[1]), fill=255)
        return mask

    def resize_image_proportionally_centered(self, image, target_width, target_height):
        """Resize image maintaining proportions and cropping from center - universal method"""
        try:
            # Calculate scaling factor to make image fit target dimensions
            scale_factor = max(target_width / image.width, target_height / image.height)

            # Calculate new dimensions after scaling
            new_width = int(image.width * scale_factor)
            new_height = int(image.height * scale_factor)

            # Resize image to new dimensions
            resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Calculate crop coordinates to center the image
            left = (new_width - target_width) // 2
            top = (new_height - target_height) // 2
            right = left + target_width
            bottom = top + target_height

            # Crop to exact target size, centered
            cropped_image = resized_image.crop((left, top, right, bottom))

            return cropped_image

        except Exception as e:
            print(f"Error resizing image proportionally: {e}")
            return image.resize((target_width, target_height), Image.Resampling.LANCZOS)

    def resize_xp_bar_image_proportionally(self, image, target_width, target_height):
        """Resize XP bar image maintaining proportions and cropping from center"""
        return self.resize_image_proportionally_centered(image, target_width, target_height)

    async def apply_text_image_overlay(self, text_image_url, text_surface, text_bbox):
        """Apply image overlay to text using mask technique"""
        try:
            if not text_image_url or text_image_url == "None":
                return text_surface

            # Download overlay image
            overlay_data = await self.download_image(text_image_url)
            if not overlay_data:
                return text_surface

            overlay_img = Image.open(io.BytesIO(overlay_data)).convert("RGBA")

            # Resize overlay to match text bounding box
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            overlay_resized = overlay_img.resize((text_width, text_height), Image.Resampling.LANCZOS)

            # Create mask from text surface alpha channel
            text_mask = text_surface.split()[-1]  # Get alpha channel

            # Apply mask to overlay image
            overlay_resized.putalpha(text_mask)

            # Create result image
            result = Image.new('RGBA', text_surface.size, (0, 0, 0, 0))
            result.paste(overlay_resized, (text_bbox[0], text_bbox[1]), overlay_resized)

            return result

        except Exception as e:
            print(f"Error applying text image overlay: {e}")
            return text_surface

    async def create_text_with_image_overlay(self, text, font, color, image_url=None):
        """Create text with optional image overlay"""
        try:
            # Create text surface
            text_bbox = font.getbbox(text)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            # Ajouter plus de padding pour éviter les coupures
            padding = 30
            canvas_width = text_width + (padding * 2)
            canvas_height = text_height + (padding * 2)

            if image_url and image_url != "None":
                # Download overlay image
                overlay_data = await self.download_image(image_url)
                if overlay_data:
                    overlay_img = Image.open(io.BytesIO(overlay_data)).convert("RGBA")

                    # Créer d'abord le masque de texte PRÉCIS qui suit exactement la forme des lettres
                    text_mask = Image.new('L', (canvas_width, canvas_height), 0)
                    mask_draw = ImageDraw.Draw(text_mask)

                    # Dessiner le texte UNE SEULE FOIS pour garder la forme exacte
                    text_x = padding
                    text_y = padding
                    mask_draw.text((text_x, text_y), text, font=font, fill=255)

                    # Redimensionner l'image pour qu'elle ait la même largeur que le canvas
                    original_ratio = overlay_img.width / overlay_img.height
                    new_width = canvas_width
                    new_height = int(new_width / original_ratio)

                    # Redimensionner l'image avec la nouvelle largeur
                    overlay_resized = overlay_img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                    # Rogner l'image centrée pour qu'elle ait la même hauteur que le canvas
                    if new_height > canvas_height:
                        # L'image est plus haute, rogner du centre
                        crop_top = (new_height - canvas_height) // 2
                        overlay_cropped = overlay_resized.crop((0, crop_top, new_width, crop_top + canvas_height))
                    else:
                        # L'image est plus petite ou égale, la centrer sur le canvas
                        overlay_cropped = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))
                        paste_y = (canvas_height - new_height) // 2
                        overlay_cropped.paste(overlay_resized, (0, paste_y))

                    # Créer l'image finale avec transparence complète
                    result = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))

                    # Appliquer la texture UNIQUEMENT aux pixels des lettres
                    # Convertir le masque en array pour manipulation pixel par pixel
                    import numpy as np
                    mask_array = np.array(text_mask)
                    overlay_array = np.array(overlay_cropped)
                    result_array = np.array(result)

                    # Pour chaque pixel où le masque n'est pas 0 (donc où il y a du texte)
                    text_pixels = mask_array > 0
                    result_array[text_pixels] = overlay_array[text_pixels]

                    # Reconvertir en image PIL
                    result = Image.fromarray(result_array, 'RGBA')

                    return result

            # Fallback to regular colored text
            temp_img = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))
            temp_draw = ImageDraw.Draw(temp_img)
            temp_draw.text((padding, padding), text, font=font, fill=tuple(color))
            return temp_img

        except Exception as e:
            print(f"Error creating text with image overlay: {e}")
            # Fallback to basic text
            text_bbox = font.getbbox(text)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            padding = 30
            temp_img = Image.new('RGBA', (text_width + padding * 2, text_height + padding * 2), (0, 0, 0, 0))
            temp_draw = ImageDraw.Draw(temp_img)
            temp_draw.text((padding, padding), text, font=font, fill=tuple(color))
            return temp_img

    def calculate_user_ranking(self, user_id):
        """Calculate user's ranking position compared to all other users"""
        data = load_leveling_data()
        all_users = data["user_data"]

        # Create a list of (user_id, xp) tuples and sort by XP descending
        user_xp_list = [(uid, udata["xp"]) for uid, udata in all_users.items()]
        user_xp_list.sort(key=lambda x: x[1], reverse=True)

        # Find the position of the current user
        for position, (uid, xp) in enumerate(user_xp_list, 1):
            if uid == str(user_id):
                return position

        return len(user_xp_list) + 1  # If not found, place at the end

    def calculate_dynamic_positions(self, user, user_data, user_ranking, config, bg_width, bg_height):
        """Calculate dynamic positions for all text elements based on content length"""
        try:
            # Get fonts for text measurement
            try:
                font_username = ImageFont.truetype("PlayPretend.otf", config["username_position"]["font_size"])
                font_level = ImageFont.truetype("PlayPretend.otf", config["level_position"]["font_size"])
                font_xp = ImageFont.truetype("PlayPretend.otf", config["xp_text_position"]["font_size"])
                font_ranking = ImageFont.truetype("PlayPretend.otf", config.get("ranking_position", {}).get("font_size", 120))
                font_discriminator = ImageFont.truetype("PlayPretend.otf", config.get("discriminator_position", {}).get("font_size", 50))
            except IOError:
                try:
                    font_username = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", config["username_position"]["font_size"])
                    font_level = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", config["level_position"]["font_size"])
                    font_xp = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", config["xp_text_position"]["font_size"])
                    font_ranking = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", config.get("ranking_position", {}).get("font_size", 120))
                    font_discriminator = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", config.get("discriminator_position", {}).get("font_size", 50))
                except IOError:
                    font_username = ImageFont.load_default()
                    font_level = ImageFont.load_default()
                    font_xp = ImageFont.load_default()
                    font_ranking = ImageFont.load_default()
                    font_discriminator = ImageFont.load_default()

            # Prepare text content
            username = user.name
            level_text = f"LEVEL {user_data['level']}"
            ranking_text = f"#{user_ranking}"
            discriminator = f"#{user.discriminator}" if user.discriminator != "0" else f"#{user.id % 10000:04d}"

            xp_needed, current_xp_in_level = get_xp_for_next_level(user_data["xp"])
            xp_text = f"{current_xp_in_level}/{xp_needed} XP"

            # Get text dimensions
            level_bbox = font_level.getbbox(level_text)
            level_width = level_bbox[2] - level_bbox[0]

            ranking_bbox = font_ranking.getbbox(ranking_text)
            ranking_width = ranking_bbox[2] - ranking_bbox[0]

            xp_bbox = font_xp.getbbox(xp_text)
            xp_width = xp_bbox[2] - xp_bbox[0]

            username_bbox = font_username.getbbox(username)
            username_width = username_bbox[2] - username_bbox[0]

            discriminator_bbox = font_discriminator.getbbox(discriminator)
            discriminator_width = discriminator_bbox[2] - discriminator_bbox[0]

            # Define margins and spacing
            margin = 50
            min_spacing = 30
            username_discriminator_spacing = 10

            # Calculate positions from right to left (XP has priority)
            # XP text position (pushes from right)
            default_xp_x = config["xp_text_position"]["x"]
            xp_x = min(default_xp_x, bg_width - margin - xp_width)
            xp_y = config["xp_text_position"]["y"]

            # Level text position (pushes from right, but gives way to XP only if needed)
            default_level_x = config["level_position"]["x"]
            if default_level_x + level_width + min_spacing > xp_x:
                level_x = xp_x - level_width - min_spacing
            else:
                level_x = default_level_x
            level_y = config["level_position"]["y"]

            # Ranking position (pushes from right, but gives way to level only if needed)
            default_ranking_x = config.get("ranking_position", {}).get("x", 1350)
            if default_ranking_x + ranking_width + min_spacing > level_x:
                ranking_x = level_x - ranking_width - min_spacing
            else:
                ranking_x = default_ranking_x
            ranking_y = config.get("ranking_position", {}).get("y", 35)

            # Username and discriminator (push from left, but give way to XP)
            available_space_for_username = xp_x - config["username_position"]["x"] - min_spacing - discriminator_width - username_discriminator_spacing

            # Adjust username font size if necessary
            username_font_size = config["username_position"]["font_size"]
            if username_width > available_space_for_username:
                # Calculate new font size to fit
                scale_factor = available_space_for_username / username_width
                username_font_size = max(30, int(username_font_size * scale_factor))  # Minimum size of 30

                # Recalculate with new font size
                try:
                    font_username_adjusted = ImageFont.truetype("PlayPretend.otf", username_font_size)
                except IOError:
                    try:
                        font_username_adjusted = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", username_font_size)
                    except IOError:
                        font_username_adjusted = ImageFont.load_default()

                username_bbox_adjusted = font_username_adjusted.getbbox(username)
                username_width_adjusted = username_bbox_adjusted[2] - username_bbox_adjusted[0]

                # If still too wide, keep the adjusted size
                if username_width_adjusted <= available_space_for_username:
                    username_width = username_width_adjusted

            # Username position
            username_x = config["username_position"]["x"]
            username_y = config["username_position"]["y"]

            # If username had to be resized significantly, move it down slightly
            if username_font_size < config["username_position"]["font_size"] * 0.8:
                username_y += int((config["username_position"]["font_size"] - username_font_size) * 0.3)

            # Discriminator position (right after username)
            discriminator_x = username_x + username_width + username_discriminator_spacing
            discriminator_y = config.get("discriminator_position", {}).get("y", 295)

            return {
                "username": {"x": username_x, "y": username_y},
                "discriminator": {"x": discriminator_x, "y": discriminator_y},
                "level": {"x": level_x, "y": level_y},
                "ranking": {"x": ranking_x, "y": ranking_y},
                "xp_text": {"x": xp_x, "y": xp_y},
                "fonts": {"username_size": username_font_size}
            }

        except Exception as e:
            print(f"Error calculating dynamic positions: {e}")
            # Return default positions if calculation fails
            return {
                "username": {"x": config["username_position"]["x"], "y": config["username_position"]["y"]},
                "discriminator": {"x": config.get("discriminator_position", {}).get("x", 1050), "y": config.get("discriminator_position", {}).get("y", 295)},
                "level": {"x": config["level_position"]["x"], "y": config["level_position"]["y"]},
                "ranking": {"x": config.get("ranking_position", {}).get("x", 1350), "y": config.get("ranking_position", {}).get("y", 35)},
                "xp_text": {"x": config["xp_text_position"]["x"], "y": config["xp_text_position"]["y"]},
                "fonts": {"username_size": config["username_position"]["font_size"]}
            }

    async def create_level_card(self, user):
        """Create level card for user"""
        try:
            data = load_leveling_data()
            user_data = data["user_data"].get(str(user.id), {"xp": 0, "level": 1})
            config = load_user_level_card_config(user.id)

            # Calculate user ranking
            user_ranking = self.calculate_user_ranking(user.id)

            # Get background size from config
            bg_width = config.get("background_size", {}).get("width", 2048)
            bg_height = config.get("background_size", {}).get("height", 540)

            # Variables pour gérer les GIFs animés
            is_animated_gif = False
            frames = []
            durations = []

            # Create background based on configuration
            if config.get("background_image") and config["background_image"] != "None":
                # Download and use background image
                bg_data = await self.download_image(config["background_image"])
                if bg_data:
                    original_bg = Image.open(io.BytesIO(bg_data))

                    # Vérifier si c'est un GIF animé
                    if hasattr(original_bg, 'is_animated') and original_bg.is_animated:
                        is_animated_gif = True
                        # Traiter chaque frame du GIF
                        for frame_idx in range(original_bg.n_frames):
                            original_bg.seek(frame_idx)
                            frame = original_bg.copy().convert("RGBA")

                            # Use centered proportional resizing for animated frame
                            processed_frame = self.resize_image_proportionally_centered(
                                frame, bg_width, bg_height
                            )
                            frames.append(processed_frame)

                            # Récupérer la durée de la frame
                            try:
                                duration = original_bg.info.get('duration', 100)
                                durations.append(duration)
                            except:
                                durations.append(100)  # 100ms par défaut
                    else:
                        # Image statique
                        original_bg = original_bg.convert("RGBA")

                        # Use centered proportional resizing for background
                        background = self.resize_image_proportionally_centered(
                            original_bg, bg_width, bg_height
                        )
                else:
                    # Fallback to background color if image download fails
                    default_bg_color = config.get("background_color", [15, 17, 16]) # Use correct default color
                    bg_color = tuple(default_bg_color) + (255,)
                    background = Image.new("RGBA", (bg_width, bg_height), bg_color)
            elif config.get("background_color") and config["background_color"] != "None":
                # Use background color
                if isinstance(config["background_color"], list) and len(config["background_color"]) == 3:
                    bg_color = tuple(config["background_color"]) + (255,)
                else:
                    bg_color = (255, 255, 255, 255)  # Default white if format is incorrect
                background = Image.new("RGBA", (bg_width, bg_height), bg_color)
            else:
                # Default to the specified background color in the config
                default_bg_color = config.get("background_color", [15, 17, 16]) # Use correct default color
                bg_color = tuple(default_bg_color) + (255,)
                background = Image.new("RGBA", (bg_width, bg_height), bg_color)

            # Download and add level bar image
            levelbar_data = await self.download_image(config.get("level_bar_image", "https://raw.githubusercontent.com/TheBlueEL/pictures/refs/heads/main/LevelBar.png"))
            levelbar_x = 0
            levelbar_y = 0

            if levelbar_data:
                levelbar = Image.open(io.BytesIO(levelbar_data)).convert("RGBA")
                # Position level bar using config
                xp_bar_config = config.get("xp_bar_position", {})
                if "x" in xp_bar_config and "y" in xp_bar_config:
                    levelbar_x = xp_bar_config["x"]
                    levelbar_y = xp_bar_config["y"]
                    # Only resize if width/height specified AND it's not the default LevelBar
                    if "width" in xp_bar_config and "height" in xp_bar_config:
                        if config.get("level_bar_image") != "https://raw.githubusercontent.com/TheBlueEL/pictures/refs/heads/main/LevelBar.png":
                            # Custom image - use proportional resizing from center
                            levelbar = self.resize_image_proportionally_centered(
                                levelbar, 
                                xp_bar_config["width"], 
                                xp_bar_config["height"]
                            )
                        else:
                            # Default LevelBar - maintain original size and proportions
                            pass
                else:
                    # Default positioning
                    levelbar_x = 30
                    levelbar_y = bg_height - levelbar.height - 30

                # Create XP bar background with rounded corners that matches the progress bar shape
                if levelbar_data:
                    # Calculate radius for half-circle (half of height)
                    radius = levelbar.height // 2

                    # Check if there's a custom XP bar image texture
                    xp_bar_image_url = config.get("level_bar_image")
                    if xp_bar_image_url and xp_bar_image_url != "https://raw.githubusercontent.com/TheBlueEL/pictures/refs/heads/main/LevelBar.png":
                        # Apply custom texture to the background bar
                        try:
                            xp_bar_texture_data = await self.download_image(xp_bar_image_url)
                            if xp_bar_texture_data:
                                xp_bar_texture = Image.open(io.BytesIO(xp_bar_texture_data)).convert("RGBA")

                                # Resize texture to fit the bar dimensions using centered proportional resizing
                                texture_resized = self.resize_image_proportionally_centered(
                                    xp_bar_texture, levelbar.width, levelbar.height
                                )

                                # Create mask for rounded rectangle
                                mask = Image.new('L', (levelbar.width, levelbar.height), 0)
                                mask_draw = ImageDraw.Draw(mask)
                                mask_draw.rounded_rectangle(
                                    [(0, 0), (levelbar.width - 1, levelbar.height - 1)],
                                    radius=radius,
                                    fill=255
                                )

                                # Apply texture only to the rounded rectangle shape
                                import numpy as np
                                texture_array = np.array(texture_resized)
                                mask_array = np.array(mask)
                                result_array = np.zeros_like(texture_array)

                                # Only copy pixels where the mask is not 0
                                mask_pixels = mask_array > 0
                                result_array[mask_pixels] = texture_array[mask_pixels]
                                result_array[:, :, 3] = mask_array  # Set alpha channel to match mask

                                rounded_bg = Image.fromarray(result_array, 'RGBA')

                                # Paste the textured background
                                background.paste(rounded_bg, (levelbar_x, levelbar_y), rounded_bg)
                            else:
                                # Fallback to default color bar
                                bg_color_default = (80, 80, 80, 255)  # Dark gray background
                                rounded_bg = Image.new("RGBA", (levelbar.width, levelbar.height), (0, 0, 0, 0))
                                rounded_bg_draw = ImageDraw.Draw(rounded_bg)
                                rounded_bg_draw.rounded_rectangle(
                                    [(0, 0), (levelbar.width - 1, levelbar.height - 1)],
                                    radius=radius,
                                    fill=bg_color_default
                                )
                                background.paste(rounded_bg, (levelbar_x, levelbar_y), rounded_bg)
                        except Exception as e:
                            print(f"Error applying XP bar texture: {e}")
                            # Fallback to default color bar
                            bg_color_default = (80, 80, 80, 255)  # Dark gray background
                            rounded_bg = Image.new("RGBA", (levelbar.width, levelbar.height), (0, 0, 0, 0))
                            rounded_bg_draw = ImageDraw.Draw(rounded_bg)
                            rounded_bg_draw.rounded_rectangle(
                                [(0, 0), (levelbar.width - 1, levelbar.height - 1)],
                                radius=radius,
                                fill=bg_color_default
                            )
                            background.paste(rounded_bg, (levelbar_x, levelbar_y), rounded_bg)
                    else:
                        # Use default color bar
                        bg_color_default = (80, 80, 80, 255)  # Dark gray background
                        rounded_bg = Image.new("RGBA", (levelbar.width, levelbar.height), (0, 0, 0, 0))
                        rounded_bg_draw = ImageDraw.Draw(rounded_bg)
                        rounded_bg_draw.rounded_rectangle(
                            [(0, 0), (levelbar.width - 1, levelbar.height - 1)],
                            radius=radius,
                            fill=bg_color_default
                        )
                        background.paste(rounded_bg, (levelbar_x, levelbar_y), rounded_bg)

                # Create XP progress bar overlay with rounded corners
                xp_needed, current_xp_in_level = get_xp_for_next_level(user_data["xp"])
                if xp_needed > 0:
                    progress = current_xp_in_level / xp_needed
                else:
                    progress = 1.0

                # Create XP progress bar using the specified color or texture
                if progress > 0:
                    progress_width = int(levelbar.width * progress)

                    if progress_width > 0:
                        # Check if there's a custom XP progress image texture
                        xp_progress_image_url = config.get("xp_progress_image")
                        if xp_progress_image_url and xp_progress_image_url != "None":
                            # Apply custom texture to the progress bar
                            try:
                                xp_progress_texture_data = await self.download_image(xp_progress_image_url)
                                if xp_progress_texture_data:
                                    xp_progress_texture = Image.open(io.BytesIO(xp_progress_texture_data)).convert("RGBA")

                                    # Resize texture to fit the FULL bar dimensions first
                                    texture_full = self.resize_image_proportionally_centered(
                                        xp_progress_texture, levelbar.width, levelbar.height
                                    )

                                    # Create progress mask with rounded corners
                                    progress_mask = Image.new('L', (levelbar.width, levelbar.height), 0)
                                    progress_mask_draw = ImageDraw.Draw(progress_mask)

                                    # Calculate radius for half-circle (half of height)
                                    radius = levelbar.height // 2

                                    # Draw progress mask based on progress width
                                    if progress_width >= levelbar.height:
                                        # Full rounded rectangle when progress is wide enough
                                        progress_mask_draw.rounded_rectangle(
                                            [(0, 0), (progress_width - 1, levelbar.height - 1)],
                                            radius=radius,
                                            fill=255
                                        )
                                    else:
                                        # Create proper half-circle for small progress
                                        # Draw a full circle but crop it to progress width
                                        circle_diameter = levelbar.height
                                        progress_mask_draw.ellipse(
                                            [(0, 0), (circle_diameter - 1, circle_diameter - 1)],
                                            fill=255
                                        )
                                        # Create a mask to crop the circle to progress width
                                        crop_mask = Image.new('L', (levelbar.width, levelbar.height), 0)
                                        crop_draw = ImageDraw.Draw(crop_mask)
                                        crop_draw.rectangle([(0, 0), (progress_width - 1, levelbar.height - 1)], fill=255)

                                        # Apply crop mask to progress mask
                                        import numpy as np
                                        progress_array = np.array(progress_mask)
                                        crop_array = np.array(crop_mask)
                                        progress_array = np.minimum(progress_array, crop_array)
                                        progress_mask = Image.fromarray(progress_array, 'L')

                                    # Apply texture only to the progress area
                                    import numpy as np
                                    texture_array = np.array(texture_full)
                                    mask_array = np.array(progress_mask)
                                    result_array = np.zeros_like(texture_array)

                                    # Only copy pixels where the mask is not 0
                                    mask_pixels = mask_array > 0
                                    result_array[mask_pixels] = texture_array[mask_pixels]
                                    result_array[:, :, 3] = mask_array  # Set alpha channel to match mask

                                    progress_bar = Image.fromarray(result_array, 'RGBA')

                                    # Paste the textured progress bar over the background
                                    background.paste(progress_bar, (levelbar_x, levelbar_y), progress_bar)
                                else:
                                    # Fallback to colored progress bar
                                    xp_bar_color_rgb = config.get("xp_bar_color", [245, 55, 48])
                                    xp_bar_color = tuple(xp_bar_color_rgb) + (255,)
                                    progress_bar = Image.new("RGBA", (progress_width, levelbar.height), (0, 0, 0, 0))
                                    progress_draw = ImageDraw.Draw(progress_bar)

                                    radius = levelbar.height // 2
                                    if progress_width >= levelbar.height:
                                        progress_draw.rounded_rectangle(
                                            [(0, 0), (progress_width - 1, levelbar.height - 1)],
                                            radius=radius,
                                            fill=xp_bar_color
                                        )
                                    else:
                                        progress_draw.ellipse(
                                            [(0, 0), (min(progress_width * 2, levelbar.height) - 1, levelbar.height - 1)],
                                            fill=xp_bar_color
                                        )
                                    background.paste(progress_bar, (levelbar_x, levelbar_y), progress_bar)
                            except Exception as e:
                                print(f"Error applying XP progress texture: {e}")
                                # Fallback to colored progress bar
                                xp_bar_color_rgb = config.get("xp_bar_color", [245, 55, 48])
                                xp_bar_color = tuple(xp_bar_color_rgb) + (255,)
                                progress_bar = Image.new("RGBA", (progress_width, levelbar.height), (0, 0, 0, 0))
                                progress_draw = ImageDraw.Draw(progress_bar)

                                radius = levelbar.height // 2
                                if progress_width >= levelbar.height:
                                    progress_draw.rounded_rectangle(
                                        [(0, 0), (progress_width - 1, levelbar.height - 1)],
                                        radius=radius,
                                        fill=xp_bar_color
                                    )
                                else:
                                    # Create proper half-circle for small progress
                                    circle_diameter = levelbar.height
                                    # Create a temporary surface for the full circle
                                    temp_surface = Image.new("RGBA", (circle_diameter, levelbar.height), (0, 0, 0, 0))
                                    temp_draw = ImageDraw.Draw(temp_surface)
                                    temp_draw.ellipse(
                                        [(0, 0), (circle_diameter - 1, circle_diameter - 1)],
                                        fill=xp_bar_color
                                    )
                                    # Crop the circle to progress width
                                    cropped_circle = temp_surface.crop((0, 0, progress_width, levelbar.height))
                                    progress_bar.paste(cropped_circle, (0, 0), cropped_circle)
                                background.paste(progress_bar, (levelbar_x, levelbar_y), progress_bar)
                        else:
                            # Use default colored progress bar
                            xp_bar_color_rgb = config.get("xp_bar_color", [245, 55, 48])
                            xp_bar_color = tuple(xp_bar_color_rgb) + (255,)
                            progress_bar = Image.new("RGBA", (progress_width, levelbar.height), (0, 0, 0, 0))
                            progress_draw = ImageDraw.Draw(progress_bar)

                            radius = levelbar.height // 2
                            if progress_width >= levelbar.height:
                                progress_draw.rounded_rectangle(
                                    [(0, 0), (progress_width - 1, levelbar.height - 1)],
                                    radius=radius,
                                    fill=xp_bar_color
                                )
                            else:
                                progress_draw.ellipse(
                                    [(0, 0), (min(progress_width * 2, levelbar.height) - 1, levelbar.height - 1)],
                                    fill=xp_bar_color
                                )
                            background.paste(progress_bar, (levelbar_x, levelbar_y), progress_bar)


            # Download user avatar
            avatar_url = user.display_avatar.url
            avatar_data = await self.download_image(avatar_url)
            if avatar_data:
                avatar = Image.open(io.BytesIO(avatar_data)).convert("RGBA")
                size = config["profile_position"]["size"]
                avatar = avatar.resize((size, size), Image.Resampling.LANCZOS)

                # Make avatar circular
                mask = self.create_circle_mask((size, size))
                avatar.putalpha(mask)

                # Paste avatar
                background.paste(avatar, (config["profile_position"]["x"], config["profile_position"]["y"]), avatar)

                # Add profile outline if enabled
                profile_outline_config = config.get("profile_outline", {})
                if profile_outline_config.get("enabled", True):
                    # Check for custom image first
                    if profile_outline_config.get("custom_image"):
                        outline_url = profile_outline_config["custom_image"]
                    else:
                        outline_url = profile_outline_config.get("url")

                    if outline_url:
                        outline_data = await self.download_image(outline_url)
                        if outline_data:
                            outline = Image.open(io.BytesIO(outline_data)).convert("RGBA")

                            # Apply color override if specified (only for default outline, not custom image)
                            if profile_outline_config.get("color_override") and not profile_outline_config.get("custom_image"):
                                color_override = profile_outline_config["color_override"]
                                colored_outline = Image.new("RGBA", outline.size, tuple(color_override + [255]))
                                colored_outline.putalpha(outline.split()[-1])
                                outline = colored_outline

                            # Get outline size from config (default to avatar size if not specified)
                            outline_size = profile_outline_config.get("size", size)
                            outline = outline.resize((outline_size, outline_size), Image.Resampling.LANCZOS)

                            # Calculate centered position for outline
                            avatar_center_x = config["profile_position"]["x"] + size // 2
                            avatar_center_y = config["profile_position"]["y"] + size // 2
                            outline_x = avatar_center_x - outline_size // 2
                            outline_y = avatar_center_y - outline_size // 2

                            # Paste outline centered over avatar
                            background.paste(outline, (outline_x, outline_y), outline)

            # Calculate dynamic positions based on content
            positions = self.calculate_dynamic_positions(user, user_data, user_ranking, config, bg_width, bg_height)

            # Draw text
            draw = ImageDraw.Draw(background)

            try:
                font_username = ImageFont.truetype("PlayPretend.otf", positions["fonts"]["username_size"])
                font_level = ImageFont.truetype("PlayPretend.otf", config["level_position"]["font_size"])
            except IOError:
                # Fallback vers les polices système si PlayPretend.otf n'est pas disponible
                try:
                    font_username = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", positions["fonts"]["username_size"])
                    font_level = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", config["level_position"]["font_size"])
                except IOError:
                    font_username = ImageFont.load_default()
                    font_level = ImageFont.load_default()

            # Draw username with configurable color and optional image overlay
            username = user.name
            username_color = config.get("username_color", [255, 255, 255]) # Default white
            username_image_url = config.get("username_image")

            if username_image_url and username_image_url != "None":
                username_surface = await self.create_text_with_image_overlay(
                    username, font_username, username_color, username_image_url
                )
                background.paste(username_surface, 
                               (positions["username"]["x"] - 30, positions["username"]["y"] - 30), 
                               username_surface)
            else:
                draw.text((positions["username"]["x"], positions["username"]["y"]),
                         username, font=font_username, fill=tuple(username_color))

            # Draw discriminator next to username
            discriminator_config = config.get("discriminator_position", {})
            if discriminator_config:
                discriminator = f"#{user.discriminator}" if user.discriminator != "0" else f"#{user.id % 10000:04d}"
                discriminator_color = discriminator_config.get("color", [200, 200, 200])

                try:
                    font_discriminator = ImageFont.truetype("PlayPretend.otf", discriminator_config.get("font_size", 50))
                except IOError:
                    try:
                        font_discriminator = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", discriminator_config.get("font_size", 50))
                    except IOError:
                        font_discriminator = ImageFont.load_default()

                draw.text((positions["discriminator"]["x"], positions["discriminator"]["y"]),
                         discriminator, font=font_discriminator, fill=tuple(discriminator_color))

            # Draw level with configurable color and optional image overlay
            level_text = f"LEVEL {user_data['level']}"
            level_color = config.get("level_color", [245, 55, 48]) # Default red
            level_image_url = config.get("level_text_image")

            if level_image_url and level_image_url != "None":
                level_surface = await self.create_text_with_image_overlay(
                    level_text, font_level, level_color, level_image_url
                )
                background.paste(level_surface, 
                               (positions["level"]["x"] - 30, positions["level"]["y"] - 30), 
                               level_surface)
            else:
                draw.text((positions["level"]["x"], positions["level"]["y"]),
                         level_text, font=font_level, fill=tuple(level_color))

            # Draw ranking position with optional image overlay
            ranking_config = config.get("ranking_position", {})
            if ranking_config:
                ranking_text = f"#{user_ranking}"
                ranking_color = ranking_config.get("color", [255, 255, 255])
                ranking_image_url = ranking_config.get("background_image")

                try:
                    font_ranking = ImageFont.truetype("PlayPretend.otf", ranking_config.get("font_size", 60))
                except IOError:
                    try:
                        font_ranking = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", ranking_config.get("font_size", 60))
                    except IOError:
                        font_ranking = ImageFont.load_default()

                if ranking_image_url and ranking_image_url != "None":
                    ranking_surface = await self.create_text_with_image_overlay(
                        ranking_text, font_ranking, ranking_color, ranking_image_url
                    )
                    background.paste(ranking_surface, 
                                   (positions["ranking"]["x"] - 30, positions["ranking"]["y"] - 30), 
                                   ranking_surface)
                else:
                    draw.text((positions["ranking"]["x"], positions["ranking"]["y"]),
                             ranking_text, font=font_ranking, fill=tuple(ranking_color))

            # Draw XP progress text with optional image overlay
            xp_needed, current_xp_in_level = get_xp_for_next_level(user_data["xp"])
            xp_text = f"{current_xp_in_level}/{xp_needed} XP"
            xp_info_image_url = config.get("xp_info_image")

            try:
                font_xp = ImageFont.truetype("PlayPretend.otf", config["xp_text_position"]["font_size"])
            except IOError:
                # Fallback vers les polices système
                try:
                    font_xp = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", config["xp_text_position"]["font_size"])
                except IOError:
                    font_xp = ImageFont.load_default()

            if xp_info_image_url and xp_info_image_url != "None":
                xp_surface = await self.create_text_with_image_overlay(
                    xp_text, font_xp, config.get("xp_text_color", [255, 255, 255]), xp_info_image_url
                )
                background.paste(xp_surface, 
                               (positions["xp_text"]["x"] - 30, positions["xp_text"]["y"] - 30), 
                               xp_surface)
            else:
                draw.text((positions["xp_text"]["x"], positions["xp_text"]["y"]), 
                         xp_text, font=font_xp, fill=tuple(config.get("xp_text_color", [255, 255, 255])))


            # If it's an animated GIF, process all frames
            if is_animated_gif:
                final_frames = []

                for frame_idx, bg_frame in enumerate(frames):
                    # Use bg_frame as background for this frame
                    current_background = bg_frame.copy()

                    # Add level bar to this frame
                    if levelbar_data:
                        current_background.paste(levelbar, (levelbar_x, levelbar_y), levelbar)

                        # Add XP progress bar
                        if progress > 0:
                            xp_progress_bar_frame = Image.new("RGBA", (int(levelbar.width * progress), levelbar.height), xp_bar_color)
                            current_background.paste(xp_progress_bar_frame, (levelbar_x, levelbar_y), xp_progress_bar_frame)

                    # Add avatar
                    if avatar_data:
                        current_background.paste(avatar, (config["profile_position"]["x"], config["profile_position"]["y"]), avatar)

                    # Add text to this frame
                    draw = ImageDraw.Draw(current_background)

                    # Get adjusted font for username
                    try:
                        font_username_frame = ImageFont.truetype("PlayPretend.otf", positions["fonts"]["username_size"])
                    except IOError:
                        try:
                            font_username_frame = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", positions["fonts"]["username_size"])
                        except IOError:
                            font_username_frame = ImageFont.load_default()

                    # Draw username
                    draw.text((positions["username"]["x"], positions["username"]["y"]),
                             username, font=font_username_frame, fill=tuple(username_color))

                    # Draw discriminator
                    discriminator_config = config.get("discriminator_position", {})
                    if discriminator_config:
                        discriminator = f"#{user.discriminator}" if user.discriminator != "0" else f"#{user.id % 10000:04d}"
                        discriminator_color = discriminator_config.get("color", [200, 200, 200])

                        try:
                            font_discriminator = ImageFont.truetype("PlayPretend.otf", discriminator_config.get("font_size", 50))
                        except IOError:
                            try:
                                font_discriminator = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", discriminator_config.get("font_size", 50))
                            except IOError:
                                font_discriminator = ImageFont.load_default()

                        draw.text((positions["discriminator"]["x"], positions["discriminator"]["y"]),
                                 discriminator, font=font_discriminator, fill=tuple(discriminator_color))

                    # Draw level
                    draw.text((positions["level"]["x"], positions["level"]["y"]),
                             level_text, font=font_level, fill=tuple(level_color))

                    # Draw ranking position
                    ranking_config = config.get("ranking_position", {})
                    if ranking_config:
                        ranking_text = f"#{user_ranking}"
                        ranking_color = ranking_config.get("color", [255, 255, 255])

                        try:
                            font_ranking = ImageFont.truetype("PlayPretend.otf", ranking_config.get("font_size", 60))
                        except IOError:
                            try:
                                font_ranking = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", ranking_config.get("font_size", 60))
                            except IOError:
                                font_ranking = ImageFont.load_default()

                        draw.text((positions["ranking"]["x"], positions["ranking"]["y"]),
                                 ranking_text, font=font_ranking, fill=tuple(ranking_color))

                    # Draw XP progress text
                    xp_needed, current_xp_in_level = get_xp_for_next_level(user_data["xp"])
                    xp_text = f"{current_xp_in_level}/{xp_needed} XP"
                    draw.text((positions["xp_text"]["x"], positions["xp_text"]["y"]), xp_text, font=font_xp, fill=tuple(config.get("xp_text_color", [255, 255, 255])))

                    final_frames.append(current_background)

                # Save the animated GIF
                output = io.BytesIO()
                final_frames[0].save(
                    output,
                    format='GIF',
                    save_all=True,
                    append_images=final_frames[1:],
                    duration=durations,
                    loop=0  # Infinite loop
                )
                output.seek(0)
                return output
            else:
                # Static image - use the first frame if it was a static GIF
                if frames:
                    background = frames[0]

                # If background is still not defined, create a default image
                if 'background' not in locals():
                    # Use the specified background color in the config or default to red
                    default_bg_color = config.get("background_color", [245, 55, 48])
                    bg_color = tuple(default_bg_color) + (255,)
                    background = Image.new("RGBA", (bg_width, bg_height), bg_color)


                output = io.BytesIO()
                background.save(output, format='PNG')
                output.seek(0)
                return output

        except Exception as e:
            print(f"Error creating level card: {e}")
            return None

    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle XP gain from messages and image uploads for level card manager"""
        if message.author.bot:
            return

        # Check for level card manager image uploads
        user_id = message.author.id

        # Check for notification card image uploads
        if hasattr(self.bot, '_notification_image_listeners') and message.attachments:
            listener = self.bot._notification_image_listeners.get(user_id)
            if listener and hasattr(listener, 'waiting_for_image') and listener.waiting_for_image:
                from level_notification_system import NotificationLevelCardView
                if isinstance(listener, NotificationLevelCardView):
                    success = await listener.handle_image_upload(message, listener)
                    if success:
                        return

        # Check if user has an active level card manager
        for view in self.bot._connection._view_store._synced_message_views.values():
            if (hasattr(view, 'user_id') and view.user_id == user_id and
                hasattr(view, 'waiting_for_image') and view.waiting_for_image and
                isinstance(view, LevelCardManagerView) and message.attachments):

                # Check if the attachment is an image
                attachment = message.attachments[0]
                allowed_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg']
                if any(attachment.filename.lower().endswith(ext) for ext in allowed_extensions):
                    # Download the image
                    local_file = await self.download_image_to_github(attachment.url)

                    if local_file:
                        try:
                            await message.delete()
                        except:
                            pass

                        # Process the image based on type
                        if view.current_image_type == "xp_bar":
                            view.config["level_bar_image"] = local_file
                        elif view.current_image_type == "background":
                            view.config["background_image"] = local_file
                            view.config.pop("background_color", None)
                        elif view.current_image_type == "profile_outline":
                            # Process profile outline image with masking
                            processed_url = await self.process_profile_outline_image(local_file)
                            if processed_url:
                                if "profile_outline" not in view.config:
                                    view.config["profile_outline"] = {}
                                view.config["profile_outline"]["custom_image"] = processed_url
                                view.config["profile_outline"].pop("color_override", None)
                        elif view.current_image_type == "username":
                            view.config["username_image"] = local_file
                        elif view.current_image_type == "xp_info":
                            view.config["xp_info_image"] = local_file
                        elif view.current_image_type == "xp_progress":
                            view.config["xp_progress_image"] = local_file
                        elif view.current_image_type == "level_text":
                            view.config["level_text_image"] = local_file
                        elif view.current_image_type == "ranking_text":
                            if "ranking_position" not in view.config:
                                view.config["ranking_position"] = {}
                            view.config["ranking_position"]["background_image"] = local_file

                        view.save_config()
                        view.waiting_for_image = False

                        # Generate new preview
                        await view.generate_preview_image(message.author)

                        # Update the manager view
                        view.mode = view.current_image_type + "_image"

                        if view.current_image_type == "xp_bar":
                            embed = view.get_xp_bar_embed()
                            embed.title = "<:ImageLOGO:1407072328134951043> XP Bar Image"
                            embed.description = "Set a custom XP bar image"
                        elif view.current_image_type == "background":
                            embed = view.get_background_embed()
                            embed.title = "<:ImageLOGO:1407072328134951043> Background Image"
                            embed.description = "Set a custom background image"
                        elif view.current_image_type == "profile_outline":
                            embed = view.get_profile_outline_embed()
                            embed.title = "<:ImageLOGO:1407072328134951043> Profile Outline Image"
                            embed.description = "Set a custom profile outline image"
                        elif view.current_image_type == "username":
                            embed = view.get_username_embed()
                            embed.title = "<:ImageLOGO:1407072328134951043> Username Image"
                            embed.description = "Set a custom username image overlay"
                        elif view.current_image_type == "xp_info":
                            embed = view.get_xp_info_embed()
                            embed.title = "<:ImageLOGO:1407072328134951043> XP Info Image"
                            embed.description = "Set a custom XP text image overlay"
                        elif view.current_image_type == "xp_progress":
                            embed = view.get_xp_progress_embed()
                            embed.title = "<:ImageLOGO:1407072328134951043> XP Progress Image"
                            embed.description = "Set a custom XP progress image overlay"
                        elif view.current_image_type == "level_text":
                            embed = view.get_level_text_embed()
                            embed.title = "<:ImageLOGO:1407072328134951043> Level Text Image"
                            embed.description = "Set a custom level text image overlay"
                        elif view.current_image_type == "ranking_text":
                            embed = view.get_ranking_text_embed()
                            embed.title = "<:ImageLOGO:1407072328134951043> Ranking Text Image"
                            embed.description = "Set a custom ranking text image overlay"
                        else:
                            embed = view.get_main_embed()

                        view.update_buttons()

                        # Find and update the original message
                        try:
                            channel = message.channel
                            async for msg in channel.history(limit=50):
                                if msg.author == self.bot.user and msg.embeds:
                                    if "Upload Image" in msg.embeds[0].title:
                                        await msg.edit(embed=embed, view=view)
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
                return

        # Regular XP processing
        data = load_leveling_data()
        if not data["leveling_settings"]["enabled"]:
            return

        user_id = str(message.author.id)
        current_time = time.time()

        # Initialize user data
        if user_id not in data["user_data"]:
            data["user_data"][user_id] = {"xp": 0, "level": 1, "last_message": 0}

        user_data = data["user_data"][user_id]
        xp_settings = data["leveling_settings"]["xp_settings"]

        xp_gained = 0

        # Message XP
        if xp_settings["messages"]["enabled"]:
            if current_time - user_data.get("last_message", 0) >= xp_settings["messages"]["cooldown"]:
                xp_gained += xp_settings["messages"]["xp_per_message"]
                user_data["last_message"] = current_time

        # Character XP
        if xp_settings["characters"]["enabled"]:
            char_count = len(message.content.replace(" ", ""))
            cooldown_key = f"{user_id}_char"

            if cooldown_key not in self.user_cooldowns:
                self.user_cooldowns[cooldown_key] = {"count": 0, "time": current_time}

            char_data = self.user_cooldowns[cooldown_key]

            if current_time - char_data["time"] >= xp_settings["characters"]["cooldown"]:
                char_data["count"] = 0
                char_data["time"] = current_time

            if char_data["count"] + char_count <= xp_settings["characters"]["character_limit"]:
                xp_gained += char_count * xp_settings["characters"]["xp_per_character"]
                char_data["count"] += char_count

        if xp_gained > 0:
            old_level = get_level_from_xp(user_data["xp"])
            max_level = data["leveling_settings"].get("max_level", 100)

            # Check if user has reached max level
            if old_level >= max_level:
                # User is at max level, no more XP gained
                user_data["level"] = max_level
                # Set XP to exactly what's needed for max level with 0 extra
                user_data["xp"] = calculate_xp_for_level(max_level)
            else:
                user_data["xp"] += xp_gained
                new_level = get_level_from_xp(user_data["xp"])

                # Cap level at max_level
                if new_level > max_level:
                    new_level = max_level
                    user_data["xp"] = calculate_xp_for_level(max_level)

                user_data["level"] = new_level

                save_leveling_data(data)

                # Check for role rewards
                if new_level > old_level:
                    await self.check_level_rewards(message.author, new_level)

                    # Check for level notifications
                    await self.check_level_notifications(message.author, new_level)

    async def download_image_to_github(self, image_url):
        """Download image and upload to GitHub, similar to welcome system"""
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

                                # Return GitHub raw URL
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
        """Process profile outline image - resize/crop from center and apply outline mask"""
        try:
            # Download custom image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        image_data = await response.read()

            # Download the default profile outline to use as mask
            data = load_leveling_data()
            config = data["leveling_settings"]["level_card"]
            outline_url = config.get("profile_outline", {}).get("url", "https://raw.githubusercontent.com/TheBlueEL/pictures/refs/heads/main/ProfileOutline.png")

            async with aiohttp.ClientSession() as session:
                async with session.get(outline_url) as response:
                    if response.status == 200:
                        mask_data = await response.read()
                    else:
                        print("Failed to download profile outline for masking")
                        return None

            # Open and process images
            custom_image = Image.open(io.BytesIO(image_data)).convert("RGBA")
            mask_image = Image.open(io.BytesIO(mask_data)).convert("RGBA")

            # Use centered proportional resizing for profile outline
            mask_width, mask_height = mask_image.size
            custom_cropped = self.resize_image_proportionally_centered(
                custom_image, mask_width, mask_height
            )

            # Apply the mask from the profile outline (use alpha channel as mask)
            alpha_mask = mask_image.split()[-1]  # Get alpha channel from outline

            # Create final masked image with ONLY the overlapping parts visible
            masked_image = Image.new("RGBA", custom_cropped.size, (0, 0, 0, 0))

            # Use numpy for pixel-level masking to ensure only overlapping parts are visible
            import numpy as np
            custom_array = np.array(custom_cropped)
            mask_array = np.array(alpha_mask)
            result_array = np.zeros_like(custom_array)

            # Only copy pixels where the mask is not transparent (>0)
            mask_pixels = mask_array > 0
            result_array[mask_pixels] = custom_array[mask_pixels]

            # Set alpha channel to match the mask exactly
            result_array[:, :, 3] = mask_array

            # Convert back to PIL Image
            masked_image = Image.fromarray(result_array, 'RGBA')

            # Save processed image
            os.makedirs('images', exist_ok=True)
            filename = f"{uuid.uuid4()}_outline_processed.png"
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
            print(f"Error processing profile outline image: {e}")
            return None

    async def check_level_rewards(self, user, level):
        """Check and assign level rewards"""
        data = load_leveling_data()
        role_rewards = data["leveling_settings"]["rewards"]["roles"]

        for reward_id, reward_data in role_rewards.items():
            if reward_data["level"] == level:
                try:
                    guild = user.guild
                    role = guild.get_role(reward_data["role_id"])
                    if role and role not in user.roles:
                        await user.add_roles(role, reason=f"Level {level} reward")
                except Exception as e:
                    print(f"Error assigning role reward: {e}")

    async def check_level_notifications(self, user, level):
        """Check and send level notifications"""
        try:
            data = load_leveling_data()
            notification_settings = data.get("notification_settings", {}).get("level_notifications", {})

            if not notification_settings.get("enabled", True):
                return

            cycle = notification_settings.get("cycle", 1)

            # Check if this level should trigger a notification
            if level % cycle == 0:
                # Import here to avoid circular import
                from level_notification_system import NotificationLevelCardView

                # Create notification card
                card_view = NotificationLevelCardView(self.bot, user.id)
                level_card = await card_view.create_notification_level_card(user, level)

                if level_card:
                    try:
                        # Send to user's DM
                        dm_channel = await user.create_dm()
                        embed = discord.Embed(
                            title="🎉 Level Up!",
                            description=f"Congratulations {user.mention}! You've reached level {level}!",
                            color=0x00ff00
                        )
                        file = discord.File(level_card, filename=f"level_{level}_notification.png")
                        await dm_channel.send(embed=embed, file=file)
                    except:
                        # If DM fails, try to send in a channel (if in guild)
                        if hasattr(user, 'guild') and user.guild:
                            # You could implement channel notification fallback here
                            pass
        except Exception as e:
            print(f"Error sending level notification: {e}")

    async def create_demo_level_card(self, bot_user):
        """Create demo level card for bot user showing level 100 and rank #1"""
        try:
            data = load_leveling_data()
            config = data["leveling_settings"]["level_card"]

            # Create demo user data (level 100, rank #1)
            demo_user_data = {"xp": 999999, "level": 100}

            # Get background size from config
            bg_width = config.get("background_size", {}).get("width", 2048)
            bg_height = config.get("background_size", {}).get("height", 540)

            # Create background based on configuration
            if config.get("background_image") and config["background_image"] != "None":
                bg_data = await self.download_image(config["background_image"])
                if bg_data:
                    original_bg = Image.open(io.BytesIO(bg_data))

                    # Handle animated GIF or static image
                    if hasattr(original_bg, 'is_animated') and original_bg.is_animated:
                        original_bg.seek(0)
                        frame = original_bg.copy().convert("RGBA")
                    else:
                        frame = original_bg.convert("RGBA")

                    # Use centered proportional resizing for demo background
                    background = self.resize_image_proportionally_centered(
                        frame, bg_width, bg_height
                    )
                else:
                    default_bg_color = config.get("background_color", [245, 55, 48])
                    bg_color = tuple(default_bg_color) + (255,)
                    background = Image.new("RGBA", (bg_width, bg_height), bg_color)
            elif config.get("background_color") and config["background_color"] != "None":
                if isinstance(config["background_color"], list) and len(config["background_color"]) == 3:
                    bg_color = tuple(config["background_color"]) + (255,)
                else:
                    bg_color = (255, 255, 255, 255)
                background = Image.new("RGBA", (bg_width, bg_height), bg_color)
            else:
                default_bg_color = config.get("background_color", [245, 55, 48])
                bg_color = tuple(default_bg_color) + (255,)
                background = Image.new("RGBA", (bg_width, bg_height), bg_color)

            # Download and add level bar image
            levelbar_data = await self.download_image(config.get("level_bar_image", "https://raw.githubusercontent.com/TheBlueEL/pictures/refs/heads/main/LevelBar.png"))
            levelbar_x = 0
            levelbar_y = 0

            if levelbar_data:
                levelbar = Image.open(io.BytesIO(levelbar_data)).convert("RGBA")
                xp_bar_config = config.get("xp_bar_position", {})
                if "x" in xp_bar_config and "y" in xp_bar_config:
                    if "width" in xp_bar_config and "height" in xp_bar_config:
                        levelbar = levelbar.resize((xp_bar_config["width"], xp_bar_config["height"]), Image.Resampling.LANCZOS)
                    levelbar_x = xp_bar_config["x"]
                    levelbar_y = xp_bar_config["y"]
                else:
                    levelbar_x = 30
                    levelbar_y = bg_height - levelbar.height - 30

                background.paste(levelbar, (levelbar_x, levelbar_y), levelbar)

                # Create full XP progress bar (100% filled for demo)
                xp_bar_color_rgb = config.get("xp_bar_color", [245, 55, 48])
                xp_bar_color = tuple(xp_bar_color_rgb) + (255,)
                progress_bar = Image.new("RGBA", (levelbar.width, levelbar.height), xp_bar_color)
                background.paste(progress_bar, (levelbar_x, levelbar_y), levelbar)

            # Download bot avatar
            avatar_url = bot_user.display_avatar.url
            avatar_data = await self.download_image(avatar_url)
            if avatar_data:
                avatar = Image.open(io.BytesIO(avatar_data)).convert("RGBA")
                size = config["profile_position"]["size"]
                avatar = avatar.resize((size, size), Image.Resampling.LANCZOS)

                # Make avatar circular
                mask = self.create_circle_mask((size, size))
                avatar.putalpha(mask)

                # Paste avatar
                background.paste(avatar, (config["profile_position"]["x"], config["profile_position"]["y"]), avatar)

                # Add profile outline (default enabled)
                profile_outline_config = config.get("profile_outline", {"enabled": True, "url": "https://raw.githubusercontent.com/TheBlueEL/pictures/refs/heads/main/ProfileOutline.png"})
                if profile_outline_config.get("enabled", True):
                    outline_url = profile_outline_config.get("url", "https://raw.githubusercontent.com/TheBlueEL/pictures/refs/heads/main/ProfileOutline.png")
                    outline_data = await self.download_image(outline_url)
                    if outline_data:
                        outline = Image.open(io.BytesIO(outline_data)).convert("RGBA")

                        # Apply color override if specified
                        if profile_outline_config.get("color_override"):
                            color_override = profile_outline_config["color_override"]
                            colored_outline = Image.new("RGBA", outline.size, tuple(color_override + [255]))
                            colored_outline.putalpha(outline.split()[-1])
                            outline = colored_outline

                        # Get outline size from config (default to avatar size if not specified)
                        outline_size = profile_outline_config.get("size", size)
                        outline = outline.resize((outline_size, outline_size), Image.Resampling.LANCZOS)

                        # Calculate centered position for outline
                        avatar_center_x = config["profile_position"]["x"] + size // 2
                        avatar_center_y = config["profile_position"]["y"] + size // 2
                        outline_x = avatar_center_x - outline_size // 2
                        outline_y = avatar_center_y - outline_size // 2

                        # Paste outline centered over avatar
                        background.paste(outline, (outline_x, outline_y), outline)

            # Calculate dynamic positions for demo user
            positions = self.calculate_dynamic_positions(bot_user, demo_user_data, 1, config, bg_width, bg_height)

            # Draw text
            draw = ImageDraw.Draw(background)

            try:
                font_username = ImageFont.truetype("PlayPretend.otf", positions["fonts"]["username_size"])
                font_level = ImageFont.truetype("PlayPretend.otf", config["level_position"]["font_size"])
            except IOError:
                try:
                    font_username = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", positions["fonts"]["username_size"])
                    font_level = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", config["level_position"]["font_size"])
                except IOError:
                    font_username = ImageFont.load_default()
                    font_level = ImageFont.load_default()

            # Draw username with configurable color
            username = bot_user.name
            username_color = config.get("username_color", [255, 255, 255])
            draw.text((positions["username"]["x"], positions["username"]["y"]),
                     username, font=font_username, fill=tuple(username_color))

            # Draw discriminator
            discriminator_config = config.get("discriminator_position", {})
            if discriminator_config:
                discriminator = f"#{bot_user.discriminator}" if bot_user.discriminator != "0" else f"#{bot_user.id % 10000:04d}"
                discriminator_color = discriminator_config.get("color", [200, 200, 200])

                try:
                    font_discriminator = ImageFont.truetype("PlayPretend.otf", discriminator_config.get("font_size", 50))
                except IOError:
                    try:
                        font_discriminator = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", discriminator_config.get("font_size", 50))
                    except IOError:
                        font_discriminator = ImageFont.load_default()

                draw.text((positions["discriminator"]["x"], positions["discriminator"]["y"]),
                         discriminator, font=font_discriminator, fill=tuple(discriminator_color))

            # Draw level with configurable color
            level_text = "LEVEL 100"
            level_color = config.get("level_color", [245, 55, 48])
            draw.text((positions["level"]["x"], positions["level"]["y"]),
                     level_text, font=font_level, fill=tuple(level_color))

            # Draw ranking position (#1)
            ranking_config = config.get("ranking_position", {})
            if ranking_config:
                ranking_text = "#1"
                ranking_color = ranking_config.get("color", [255, 255, 255])

                try:
                    font_ranking = ImageFont.truetype("PlayPretend.otf", ranking_config.get("font_size", 60))
                except IOError:
                    try:
                        font_ranking = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", ranking_config.get("font_size", 60))
                    except IOError:
                        font_ranking = ImageFont.load_default()

                draw.text((positions["ranking"]["x"], positions["ranking"]["y"]),
                         ranking_text, font=font_ranking, fill=tuple(ranking_color))

            # Draw XP progress text (MAX for level 100)
            xp_text = "MAX/MAX XP"

            try:
                font_xp = ImageFont.truetype("PlayPretend.otf", config["xp_text_position"]["font_size"])
            except IOError:
                try:
                    font_xp = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", config["xp_text_position"]["font_size"])
                except IOError:
                    font_xp = ImageFont.load_default()

            draw.text((positions["xp_text"]["x"], positions["xp_text"]["y"]), xp_text, font=font_xp, fill=tuple(config.get("xp_text_color", [255, 255, 255])))

            output = io.BytesIO()
            background.save(output, format='PNG')
            output.seek(0)
            return output

        except Exception as e:
            print(f"Error creating demo level card: {e}")
            return None

    async def generate_demo_card_for_main_view(self, view):
        """Generate and upload demo card for main view"""
        try:
            demo_card = await self.create_demo_level_card(self.bot.user)
            if demo_card:
                # Save to temp file
                os.makedirs('images', exist_ok=True)
                import time
                timestamp = int(time.time())
                filename = f"demo_level_card_{timestamp}.png"
                file_path = os.path.join('images', filename)

                with open(file_path, 'wb') as f:
                    f.write(demo_card.getvalue())

                # Upload to GitHub
                try:
                    from github_sync import GitHubSync
                    github_sync = GitHubSync()
                    sync_success = await github_sync.sync_image_to_pictures_repo(file_path)

                    if sync_success:
                        try:
                            os.remove(file_path)
                        except:
                            pass

                        filename = os.path.basename(file_path)
                        view.demo_card_url = f"https://raw.githubusercontent.com/TheBlueEL/pictures/main/{filename}?t={timestamp}"
                        return True
                except ImportError:
                    print("GitHub sync not available")

        except Exception as e:
            print(f"Error generating demo card: {e}")

        return False

    @app_commands.command(name="level_system", description="Manage the server leveling system")
    async def level_system(self, interaction: discord.Interaction):
        """Main level system management command"""
        try:
            await interaction.response.defer()
        except discord.NotFound:
            # Interaction has already been responded to or expired
            return

        view = LevelSystemMainView(self.bot, interaction.user)

        # Generate demo level card
        await self.generate_demo_card_for_main_view(view)

        embed = view.get_main_embed()
        try:
            await interaction.followup.send(embed=embed, view=view)
        except discord.NotFound:
            # Interaction has expired, send as a new message
            await interaction.channel.send(embed=embed, view=view)

    @app_commands.command(name="level", description="View your level card")
    async def level_command(self, interaction: discord.Interaction):
        """Show user's level card with settings button"""
        await interaction.response.defer()

        level_card = await self.create_level_card(interaction.user)
        if level_card:
            # Determine file extension
            level_card.seek(0)
            file_header = level_card.read(6)
            level_card.seek(0)

            # Check if it's a GIF
            is_gif = file_header.startswith(b'GIF87a') or file_header.startswith(b'GIF89a')
            filename = "level_card.gif" if is_gif else "level_card.png"

            file = discord.File(level_card, filename=filename)

            # Add settings button
            view = LevelCardSettingsButtonView(interaction.user)
            await interaction.followup.send(file=file, view=view)
        else:
            await interaction.followup.send("<:ErrorLOGO:1407071682031648850> Error creating level card!", ephemeral=True)

# Views and UI Components
class LevelSystemMainView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user
        self.demo_card_url = None

        # Initialize toggle button state based on current system status
        data = load_leveling_data()
        system_enabled = data["leveling_settings"]["enabled"]

        # Find and update the toggle button
        for item in self.children:
            if hasattr(item, 'callback') and hasattr(item.callback, 'callback') and item.callback.callback.__name__ == 'toggle_system':
                if system_enabled:
                    item.label = "ON"
                    item.style = discord.ButtonStyle.success
                    item.emoji = "<:OnLOGO:1407072463883472978>"
                else:
                    item.label = "OFF"
                    item.style = discord.ButtonStyle.danger
                    item.emoji = "<:OffLOGO:1407072621836894380>"
                break

    def get_main_embed(self):
        data = load_leveling_data()
        settings = data["leveling_settings"]

        embed = discord.Embed(
            title="📊 Level System Management",
            description=f"Welcome back {self.user.mention}!\n\nManage your server's leveling system below:",
            color=0xFFFFFF
        )

        status = "<:OnLOGO:1407072463883472978> Enabled" if settings["enabled"] else "<:OffLOGO:1407072621836894380> Disabled"
        embed.add_field(name="System Status", value=status, inline=True)

        # Add demo level card image if available
        embed.set_image(url=self.demo_card_url)

        return embed

    @discord.ui.button(label="Reward Settings", style=discord.ButtonStyle.secondary, emoji="<:SettingLOGO:1407071854593839239>")
    async def reward_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RewardSettingsView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="XP Settings", style=discord.ButtonStyle.secondary, emoji="<:SettingLOGO:1407071854593839239>")
    async def xp_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = XPSettingsView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Level Card", style=discord.ButtonStyle.secondary, emoji="<:CardLOGO:1409586383047233536>", row=1)
    async def level_card(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        view = LevelCardManagerView(self.bot, interaction.user.id)
        view.guild = interaction.guild

        # Generate preview image
        await view.generate_preview_image(interaction.user)

        embed = view.get_main_embed()
        view.update_buttons()

        await interaction.edit_original_response(embed=embed, view=view)

    @discord.ui.button(label="Level Settings", style=discord.ButtonStyle.secondary, emoji="<:SettingLOGO:1407071854593839239>", row=1)
    async def level_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = LevelSettingsView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Notification", style=discord.ButtonStyle.secondary, emoji="🔔")
    async def notification_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        from level_notification_system import NotificationSystemView
        view = NotificationSystemView(self.bot, self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="ON", style=discord.ButtonStyle.success, emoji="<:OnLOGO:1407072463883472978>")
    async def toggle_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_leveling_data()
        current_state = data["leveling_settings"]["enabled"]
        data["leveling_settings"]["enabled"] = not current_state
        save_leveling_data(data)

        # Update button appearance
        if data["leveling_settings"]["enabled"]:
            button.label = "ON"
            button.style = discord.ButtonStyle.success
            button.emoji = "<:OnLOGO:1407072463883472978>"
        else:
            button.label = "OFF"
            button.style = discord.ButtonStyle.danger
            button.emoji = "<:OffLOGO:1407072621836894380>"

        embed = self.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=self)

class RewardSettingsView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user

    def get_embed(self):
        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Reward Settings",
            description="Choose the type of rewards to configure:",
            color=0xFFFFFF
        )
        return embed

    @discord.ui.button(label="Role", style=discord.ButtonStyle.secondary, emoji="<:ParticipantsLOGO:1407733929389199460>")
    async def role_rewards(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RoleRewardsView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Custom", style=discord.ButtonStyle.secondary, emoji="<:TotalLOGO:1408245313755545752>")
    async def custom_rewards(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CustomRewardsView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = LevelSystemMainView(self.bot, self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class RoleRewardsView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user

    def get_embed(self):
        data = load_leveling_data()
        role_rewards = data["leveling_settings"]["rewards"]["roles"]

        embed = discord.Embed(
            title="<:ParticipantsLOGO:1407733929389199460> Role Rewards",
            description="Manage role rewards for leveling up:",
            color=0xFFFFFF
        )

        if role_rewards:
            reward_list = []
            for reward_id, reward_data in role_rewards.items():
                role_mention = f"<@&{reward_data['role_id']}>"
                reward_list.append(f"• {role_mention} - Level {reward_data['level']}")
            embed.add_field(name="Current Rewards", value="\n".join(reward_list), inline=False)
        else:
            embed.add_field(name="Current Rewards", value="No role rewards configured", inline=False)

        return embed

    @discord.ui.button(label="Add", style=discord.ButtonStyle.success, emoji="<:CreateLOGO:1407071205026168853>")
    async def add_role_reward(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = AddRoleRewardView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary, emoji="<:EditLOGO:1407071307022995508>")
    async def edit_role_reward(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_leveling_data()
        role_rewards = data["leveling_settings"]["rewards"]["roles"]

        if not role_rewards:
            await interaction.response.send_message(
                "<:ErrorLOGO:1407071682031648850> No role rewards to edit. Please add a role reward first.",
                ephemeral=True
            )
            return

        view = EditRoleRewardView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Remove", style=discord.ButtonStyle.danger, emoji="<:DeleteLOGO:1407071421363916841>")
    async def remove_role_reward(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_leveling_data()
        role_rewards = data["leveling_settings"]["rewards"]["roles"]

        if not role_rewards:
            await interaction.response.send_message(
                "<:ErrorLOGO:1407071682031648850> No role rewards to remove. Please add a role reward first.",
                ephemeral=True
            )
            return

        view = RemoveRoleRewardView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RewardSettingsView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class AddRoleRewardView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user
        self.selected_role = None
        self.level = None

    def get_embed(self):
        embed = discord.Embed(
            title="<:CreateLOGO:1407071205026168853> Add Role Reward",
            description="Select a role and level for the reward:",
            color=0xFFFFFF
        )

        if self.selected_role:
            embed.add_field(name="Selected Role", value=self.selected_role.mention, inline=False)

        if self.level:
            embed.add_field(name="Level", value=str(self.level), inline=False)

        return embed

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Select a role...")
    async def role_select(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        self.selected_role = select.values[0]
        if not hasattr(self, 'level_button'):
            self.level_button = discord.ui.Button(label="Set Level", style=discord.ButtonStyle.secondary, emoji="<a:XPLOGO:1409634015043915827>")
            self.level_button.callback = self.set_level
            self.add_item(self.level_button)

        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def set_level(self, interaction: discord.Interaction):
        modal = LevelModal(self)
        await interaction.response.send_modal(modal)

    def update_view(self):
        if self.selected_role and self.level:
            if not hasattr(self, 'confirm_button'):
                self.confirm_button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.success, emoji="<:ConfirmLOGO:1407072680267481249>")
                self.confirm_button.callback = self.confirm_add
                self.add_item(self.confirm_button)

    async def confirm_add(self, interaction: discord.Interaction):
        data = load_leveling_data()
        reward_id = str(len(data["leveling_settings"]["rewards"]["roles"]) + 1)
        data["leveling_settings"]["rewards"]["roles"][reward_id] = {
            "role_id": self.selected_role.id,
            "level": self.level
        }
        save_leveling_data(data)

        embed = discord.Embed(
            title="<:SucessLOGO:1407071637840592977> Role Reward Added",
            description=f"Role {self.selected_role.mention} will be given at level {self.level}!",
            color=0x00ff00
        )
        view = RoleRewardsView(self.bot, self.user)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RoleRewardsView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class LevelModal(discord.ui.Modal):
    def __init__(self, parent_view):
        super().__init__(title="Set Level")
        self.parent_view = parent_view

    level = discord.ui.TextInput(
        label="Level (0-100)",
        placeholder="Enter the level required for this reward...",
        min_length=1,
        max_length=3
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            level_value = int(self.level.value)
            if 0 <= level_value <= 100:
                self.parent_view.level = level_value
                self.parent_view.update_view()
                embed = self.parent_view.get_embed()
                await interaction.response.edit_message(embed=embed, view=self.parent_view)
            else:
                await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Level must be between 0 and 100!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Please enter a valid number!", ephemeral=True)

class EditRoleRewardView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user

        # Add dropdown in first row
        select = EditRoleRewardSelect()
        select.row = 0
        self.add_item(select)

    def get_embed(self):
        embed = discord.Embed(
            title="<:EditLOGO:1407071307022995508> Edit Role Reward",
            description="Select a role reward to edit:",
            color=0xFFFFFF
        )
        return embed

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>", row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RoleRewardsView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class EditRoleRewardSelect(discord.ui.Select):
    def __init__(self):
        data = load_leveling_data()
        role_rewards = data["leveling_settings"]["rewards"]["roles"]

        options = []
        for reward_id, reward_data in role_rewards.items():
            options.append(discord.SelectOption(
                label=f"Role ID: {reward_data['role_id']}",
                description=f"LEVEL {reward_data['level']}",
                value=reward_id
            ))

        if not options:
            options.append(discord.SelectOption(label="No rewards", description="No rewards to edit", value="none"))

        super().__init__(placeholder="Select a reward to edit...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            return

        # Implementation for editing would go here
        await interaction.response.send_message("Edit functionality coming soon!", ephemeral=True)

class RemoveRoleRewardView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user

        # Add dropdown in first row
        select = RemoveRoleRewardSelect()
        select.row = 0
        self.add_item(select)

    def get_embed(self):
        embed = discord.Embed(
            title="<:DeleteLOGO:1407071421363916841> Remove Role Reward",
            description="Select a role reward to remove:",
            color=0xff0000
        )
        return embed

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>", row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RoleRewardsView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class RemoveRoleRewardSelect(discord.ui.Select):
    def __init__(self):
        data = load_leveling_data()
        role_rewards = data["leveling_settings"]["rewards"]["roles"]

        options = []
        for reward_id, reward_data in role_rewards.items():
            options.append(discord.SelectOption(
                label=f"Role ID: {reward_data['role_id']}",
                description=f"LEVEL {reward_data['level']}",
                value=reward_id
            ))

        if not options:
            options.append(discord.SelectOption(label="No rewards", description="No rewards to remove", value="none"))

        super().__init__(placeholder="Select a reward to remove...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            return

        # Show confirmation
        embed = discord.Embed(
            title="<:WarningLOGO:1407072569487659198> Confirm Removal",
            description="This action is irreversible! Are you sure you want to remove this reward?",
            color=0xff0000
        )
        view = ConfirmRemoveView(self.values[0])
        await interaction.response.edit_message(embed=embed, view=view)

class ConfirmRemoveView(discord.ui.View):
    def __init__(self, reward_id):
        super().__init__(timeout=300)
        self.reward_id = reward_id

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, emoji="<:ConfirmLOGO:1407072680267481249>")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_leveling_data()
        if self.reward_id in data["leveling_settings"]["rewards"]["roles"]:
            del data["leveling_settings"]["rewards"]["roles"][self.reward_id]
            save_leveling_data(data)

        embed = discord.Embed(
            title="<:SucessLOGO:1407071637840592977> Reward Removed",
            description="The role reward has been successfully removed!",
            color=0x00ff00
        )
        view = RoleRewardsView(self.bot, interaction.user)
        await interaction.response.edit_message(embed=embed, view=view)

class CustomRewardsView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user

    def get_embed(self):
        data = load_leveling_data()
        permissions = data["leveling_settings"].get("customization_permissions", {})

        embed = discord.Embed(
            title="<:TotalLOGO:1408245313755545752> Customization Permissions",
            description="Manage user customization permissions for level cards:",
            color=0xFFFFFF
        )

        # Show current permissions status
        status_text = ""
        for category, config in permissions.items():
            category_name = category.replace("_", " ").title()
            status = "<:OnLOGO:1407072463883472978>" if config.get("enabled", True) else "<:OffLOGO:1407072621836894380>"
            status_text += f"{status} **{category_name}**\n"

        embed.add_field(name="Current Permissions", value=status_text or "No permissions configured", inline=False)

        return embed

    @discord.ui.button(label="Background", style=discord.ButtonStyle.secondary, emoji="<:BackgroundLOGO:1408834163309805579>", row=0)
    async def background_permissions(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CustomizationCategoryView(self.bot, self.user, "background")
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Avatar Outline", style=discord.ButtonStyle.secondary, emoji="<:ProfileLOGO:1408830057819930806>", row=0)
    async def avatar_outline_permissions(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CustomizationCategoryView(self.bot, self.user, "avatar_outline")
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Username", style=discord.ButtonStyle.secondary, emoji="<:ParticipantsLOGO:1407733929389199460>", row=0)
    async def username_permissions(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CustomizationCategoryView(self.bot, self.user, "username")
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Bar Progress", style=discord.ButtonStyle.secondary, emoji="<:XPprogressLOGO:1409633736387199117>", row=1)
    async def bar_progress_permissions(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CustomizationCategoryView(self.bot, self.user, "bar_progress")
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Content", style=discord.ButtonStyle.secondary, emoji="<:DescriptionLOGO:1407733417172533299>", row=1)
    async def content_permissions(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CustomizationCategoryView(self.bot, self.user, "content")
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>", row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RewardSettingsView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class XPSettingsView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user

    def get_embed(self):
        data = load_leveling_data()
        msg_settings = data["leveling_settings"]["xp_settings"]["messages"]
        char_settings = data["leveling_settings"]["xp_settings"]["characters"]

        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> XP Settings",
            description="Configure how users gain experience:",
            color=0xFFFFFF
        )

        # Message XP Status
        msg_status = "<:OnLOGO:1407072463883472978> Enabled" if msg_settings["enabled"] else "<:OffLOGO:1407072621836894380> Disabled"
        embed.add_field(
            name="💬 Message XP",
            value=f"{msg_status}\nXP: {msg_settings['xp_per_message']}/message\nCooldown: {msg_settings['cooldown']}s",
            inline=True
        )

        # Character XP Status
        char_status = "<:OnLOGO:1407072463883472978> Enabled" if char_settings["enabled"] else "<:OffLOGO:1407072621836894380> Disabled"
        embed.add_field(
            name="<:DescriptionLOGO:1407733417172533299> Character XP",
            value=f"{char_status}\nXP: {char_settings['xp_per_character']}/char\nLimit: {char_settings['character_limit']}\nCooldown: {char_settings['cooldown']}s",
            inline=True
        )

        return embed

    @discord.ui.button(label="Messages XP", style=discord.ButtonStyle.primary, emoji="<:MessagesLOGO:1409586848577093837>", row=0)
    async def message_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = MessageXPView(self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Characters XP", style=discord.ButtonStyle.secondary, emoji="<:DescriptionLOGO:1407733417172533299>", row=0)
    async def character_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CharacterXPView(self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)



    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>", row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = LevelSystemMainView(self.bot, self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class MessageXPView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user

        # Initialize toggle button state
        data = load_leveling_data()
        messages_enabled = data["leveling_settings"]["xp_settings"]["messages"]["enabled"]

        # Update the toggle button based on current state
        for item in self.children:
            if hasattr(item, 'callback') and item.callback.__name__ == 'toggle_messages_xp':
                if messages_enabled:
                    item.label = "ON"
                    item.style = discord.ButtonStyle.success
                    item.emoji = "<:OnLOGO:1407072463883472978>"
                else:
                    item.label = "OFF" 
                    item.style = discord.ButtonStyle.danger
                    item.emoji = "<:OffLOGO:1407072621836894380>"
                break

    def get_embed(self):
        data = load_leveling_data()
        msg_settings = data["leveling_settings"]["xp_settings"]["messages"]

        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Message XP Settings",
            description="Configure XP gain from messages:",
            color=0xFFFFFF
        )

        embed.add_field(name="XP per Message", value=str(msg_settings["xp_per_message"]), inline=True)
        embed.add_field(name="Cooldown (seconds)", value=str(msg_settings["cooldown"]), inline=True)
        status = "<:OnLOGO:1407072463883472978> Enabled" if msg_settings["enabled"] else "<:OffLOGO:1407072621836894380> Disabled"
        embed.add_field(name="Status", value=status, inline=True)

        return embed

    @discord.ui.button(label="Set XP", style=discord.ButtonStyle.primary, emoji="<a:XPLOGO:1409634015043915827>")
    async def set_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MessageXPModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Set Cooldown", style=discord.ButtonStyle.secondary, emoji="<:CooldownLOGO:1409586926071054448>")
    async def set_cooldown(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MessageCooldownModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="OFF", style=discord.ButtonStyle.danger, emoji="<:OffLOGO:1407072621836894380>")
    async def toggle_messages_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_leveling_data()
        current_state = data["leveling_settings"]["xp_settings"]["messages"]["enabled"]
        data["leveling_settings"]["xp_settings"]["messages"]["enabled"] = not current_state
        save_leveling_data(data)
        # Update button appearance
        if data["leveling_settings"]["xp_settings"]["messages"]["enabled"]:
            button.label = "ON"
            button.style = discord.ButtonStyle.success
            button.emoji = "<:OnLOGO:1407072463883472978>"
        else:
            button.label = "OFF"
            button.style = discord.ButtonStyle.danger
            button.emoji = "<:OffLOGO:1407072621836894380>"
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)


    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot = interaction.client
        view = XPSettingsView(bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class MessageXPModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Set Message XP")

    xp = discord.ui.TextInput(
        label="XP per Message",
        placeholder="Enter XP amount (minimum 0)...",
        min_length=1,
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            xp_value = int(self.xp.value)
            if xp_value >= 0:
                data = load_leveling_data()
                data["leveling_settings"]["xp_settings"]["messages"]["xp_per_message"] = xp_value
                save_leveling_data(data)
                await interaction.response.send_message(f"<:SucessLOGO:1407071637840592977> Message XP set to {xp_value}!", ephemeral=True)
            else:
                await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> XP must be 0 or higher!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Please enter a valid number!", ephemeral=True)

class MessageCooldownModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Set Message Cooldown")

    cooldown = discord.ui.TextInput(
        label="Cooldown (seconds)",
        placeholder="Enter cooldown in seconds...",
        min_length=1,
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            cooldown_value = int(self.cooldown.value)
            if cooldown_value >= 0:
                data = load_leveling_data()
                data["leveling_settings"]["xp_settings"]["messages"]["cooldown"] = cooldown_value
                save_leveling_data(data)
                await interaction.response.send_message(f"<:SucessLOGO:1407071637840592977> Message cooldown set to {cooldown_value} seconds!", ephemeral=True)
            else:
                await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Cooldown must be 0 or higher!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Please enter a valid number!", ephemeral=True)

class CharacterXPView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user

        # Initialize toggle button state
        data = load_leveling_data()
        characters_enabled = data["leveling_settings"]["xp_settings"]["characters"]["enabled"]

        # Update the toggle button based on current state
        for item in self.children:
            if hasattr(item, 'callback') and item.callback.__name__ == 'toggle_characters_xp':
                if characters_enabled:
                    item.label = "ON"
                    item.style = discord.ButtonStyle.success
                    item.emoji = "<:OnLOGO:1407072463883472978>"
                else:
                    item.label = "OFF"
                    item.style = discord.ButtonStyle.danger
                    item.emoji = "<:OffLOGO:1407072621836894380>"
                break

    def get_embed(self):
        data = load_leveling_data()
        char_settings = data["leveling_settings"]["xp_settings"]["characters"]

        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Character XP Settings",
            description="Configure XP gain from characters:",
            color=0xFFFFFF
        )

        embed.add_field(name="XP per Character", value=str(char_settings["xp_per_character"]), inline=True)
        embed.add_field(name="Character Limit", value=str(char_settings["character_limit"]), inline=True)
        embed.add_field(name="Cooldown (seconds)", value=str(char_settings["cooldown"]), inline=True)
        status = "<:OnLOGO:1407072463883472978> Enabled" if char_settings["enabled"] else "<:OffLOGO:1407072621836894380> Disabled"
        embed.add_field(name="Status", value=status, inline=True)

        return embed

    @discord.ui.button(label="Set XP", style=discord.ButtonStyle.primary, emoji="<a:XPLOGO:1409634015043915827>")
    async def set_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CharacterXPModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Set Limit", style=discord.ButtonStyle.secondary, emoji="<:LimitLOGO:1409636533618610266>")
    async def set_limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CharacterLimitModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Set Cooldown", style=discord.ButtonStyle.secondary, emoji="<:CooldownLOGO:1409586926071054448>")
    async def set_cooldown(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CharacterCooldownModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="OFF", style=discord.ButtonStyle.danger, emoji="<:OffLOGO:1407072621836894380>")
    async def toggle_characters_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_leveling_data()
        current_state = data["leveling_settings"]["xp_settings"]["characters"]["enabled"]
        data["leveling_settings"]["xp_settings"]["characters"]["enabled"] = not current_state
        save_leveling_data(data)
        # Update button appearance
        if data["leveling_settings"]["xp_settings"]["characters"]["enabled"]:
            button.label = "ON"
            button.style = discord.ButtonStyle.success
            button.emoji = "<:OnLOGO:1407072463883472978>"
        else:
            button.label = "OFF"
            button.style = discord.ButtonStyle.danger
            button.emoji = "<:OffLOGO:1407072621836894380>"
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot = interaction.client
        view = XPSettingsView(bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class CharacterXPModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Set Character XP")

    xp = discord.ui.TextInput(
        label="XP per Character",
        placeholder="Enter XP amount per character...",
        min_length=1,
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            xp_value = int(self.xp.value)
            if xp_value >= 0:
                data = load_leveling_data()
                data["leveling_settings"]["xp_settings"]["characters"]["xp_per_character"] = xp_value
                save_leveling_data(data)
                await interaction.response.send_message(f"<:SucessLOGO:1407071637840592977> Character XP set to {xp_value}!", ephemeral=True)
            else:
                await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> XP must be 0 or higher!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Please enter a valid number!", ephemeral=True)

class CharacterCooldownModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Set Character Cooldown")

    character_limit = discord.ui.TextInput(
        label="Character Limit",
        placeholder="Maximum characters before cooldown...",
        min_length=1,
        max_length=5
    )

    cooldown = discord.ui.TextInput(
        label="Cooldown (seconds)",
        placeholder="Cooldown duration in seconds...",
        min_length=1,
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            char_limit = int(self.character_limit.value)
            cooldown_value = int(self.cooldown.value)

            if char_limit >= 0 and cooldown_value >= 0:
                data = load_leveling_data()
                data["leveling_settings"]["xp_settings"]["characters"]["character_limit"] = char_limit
                data["leveling_settings"]["xp_settings"]["characters"]["cooldown"] = cooldown_value
                save_leveling_data(data)
                await interaction.response.send_message(f"<:SucessLOGO:1407071637840592977> Character settings updated!\nLimit: {char_limit} characters\nCooldown: {cooldown_value} seconds", ephemeral=True)
            else:
                await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Values must be 0 or higher!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Please enter valid numbers!", ephemeral=True)

class LevelSettingsView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user

    def get_embed(self):
        data = load_leveling_data()
        max_level = data["leveling_settings"].get("max_level", 100)

        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Level Settings",
            description="Configure level system limitations and rules:",
            color=0xFFFFFF
        )

        embed.add_field(name="Maximum Level", value=str(max_level), inline=True)
        embed.add_field(name="XP Cap", value="Users stop gaining XP at max level", inline=True)

        return embed

    @discord.ui.button(label="Level Max", style=discord.ButtonStyle.primary, emoji="<a:XPLOGO:1409634015043915827>")
    async def set_max_level(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MaxLevelModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = LevelSystemMainView(self.bot, self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class MaxLevelModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Set Maximum Level")

    max_level = discord.ui.TextInput(
        label="Maximum Level",
        placeholder="Enter maximum level (default: 100)...",
        min_length=1,
        max_length=3
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            max_level_value = int(self.max_level.value)
            if 1 <= max_level_value <= 999:
                data = load_leveling_data()
                data["leveling_settings"]["max_level"] = max_level_value
                save_leveling_data(data)

                await interaction.response.send_message(f"<:SucessLOGO:1407071637840592977> Maximum level set to {max_level_value}!", ephemeral=True)
            else:
                await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Maximum level must be between 1 and 999!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Please enter a valid number!", ephemeral=True)

class BackToMainButton(discord.ui.Button):
    def __init__(self, bot, user):
        super().__init__(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>")
        self.bot = bot
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        view = LevelSystemMainView(self.bot, self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

# Level Card Settings Button View for /level command
class LevelCardSettingsButtonView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user

    @discord.ui.button(label="Settings", style=discord.ButtonStyle.secondary, emoji="<:SettingLOGO:1407071854593839239>")
    async def settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Only the user can access their settings!", ephemeral=True)
            return

        # Create DM channel
        try:
            dm_channel = await interaction.user.create_dm()
        except:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Unable to send DM. Please check your privacy settings.", ephemeral=True)
            return

        # Get user's current level
        data = load_leveling_data()
        user_data = data["user_data"].get(str(interaction.user.id), {"xp": 0, "level": 1})
        user_level = user_data["level"]

        # Create level card manager for DMs
        view = LevelCardManagerView(interaction.client, interaction.user.id)
        view.guild = interaction.guild
        view.user_level = user_level  # Store user level for permission checks
        view.is_dm = True  # Mark as DM context

        # Generate preview image
        await view.generate_preview_image(interaction.user)

        embed = view.get_main_embed()
        view.update_buttons()

        try:
            await dm_channel.send(embed=embed, view=view)
            await interaction.response.send_message("<:SucessLOGO:1407071637840592977> Level card settings sent to your DMs!", ephemeral=True)
        except:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Unable to send DM. Please check your privacy settings.", ephemeral=True)

# Level Card Management System
class LevelCardManagerView(discord.ui.View):
    def __init__(self, bot, user_id):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.config = load_user_level_card_config(user_id)
        self.mode = "main"
        self.waiting_for_image = False
        self.current_image_type = None
        self.preview_image_url = None
        self.user_level = 1  # Will be set when created
        self.is_dm = False  # Will be set to True when used in DMs

    def get_main_embed(self):
        embed = discord.Embed(
            title="<:CardLOGO:1409586383047233536> Level Card Manager",
            description="Configure your level card design and settings",
            color=0xFFFFFF
        )

        # Show current configuration status
        config_status = ""
        if self.config.get("background_image"):
            config_status += "<:BackgroundLOGO:1408834163309805579> Background: Custom Image\n"
        elif self.config.get("background_color"):
            bg = self.config["background_color"]
            config_status += f"<:BackgroundLOGO:1408834163309805579> Background: RGB({bg[0]}, {bg[1]}, {bg[2]})\n"
        else:
            config_status += "Background: Default\n"

        if self.config.get("profile_outline", {}).get("enabled", True):
            config_status += "<:ProfileLOGO:1408830057819930806> Profile Outline: <:OnLOGO:1407072463883472978> Enabled\n"
        else:
            config_status += "<:ProfileLOGO:1408830057819930806> Profile Outline: <:OffLOGO:1407072621836894380> Disabled\n"

        embed.add_field(
            name="Current Configuration",
            value=config_status,
            inline=False
        )

        # Add preview image if available
        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            import time
            timestamp = int(time.time())
            if '?' in self.preview_image_url:
                image_url = self.preview_image_url.split('?')[0] + f"?refresh={timestamp}"
            else:
                image_url = self.preview_image_url + f"?refresh={timestamp}"
            embed.set_image(url=image_url)

        embed.set_footer(text="Level Card Manager", icon_url=self.bot.user.display_avatar.url)
        return embed

    def get_leveling_bar_embed(self):
        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Leveling Bar Settings",
            description="Configure the XP bar and related elements",
            color=discord.Color.blue()
        )

        # Add preview image if available
        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

        embed.set_footer(text="Leveling Bar Settings", icon_url=self.bot.user.display_avatar.url)
        return embed

    def get_xp_info_embed(self):
        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> XP Info Settings",
            description="Configure the XP text display (X/Y XP)",
            color=discord.Color.purple()
        )

        xp_color = self.config.get("xp_text_color", [255, 255, 255])
        embed.add_field(
            name="Current XP Text Color",
            value=f"RGB({xp_color[0]}, {xp_color[1]}, {xp_color[2]})",
            inline=False
        )

        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

        embed.set_footer(text="XP Info Settings", icon_url=self.bot.user.display_avatar.url)
        return embed

    def get_xp_bar_embed(self):
        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> XP Bar Settings",
            description="Configure the static XP bar background",
            color=discord.Color.green()
        )

        if self.config.get("level_bar_image"):
            embed.add_field(
                name="Current XP Bar",
                value="<:SucessLOGO:1407071637840592977> Custom Image",
                inline=False
            )
        else:
            embed.add_field(
                name="Current XP Bar",
                value="<:ErrorLOGO:1407071682031648850> No Custom Image",
                inline=False
            )

        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

        embed.set_footer(text="XP Bar Settings", icon_url=self.bot.user.display_avatar.url)
        return embed

    def get_xp_progress_embed(self):
        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> XP Progress Settings",
            description="Configure the moving XP progress bar",
            color=discord.Color.orange()
        )

        xp_bar_color = self.config.get("xp_bar_color", [245, 55, 48])
        embed.add_field(
            name="Current Progress Color",
            value=f"RGB({xp_bar_color[0]}, {xp_bar_color[1]}, {xp_bar_color[2]})",
            inline=False
        )

        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

        embed.set_footer(text="XP Progress Settings", icon_url=self.bot.user.display_avatar.url)
        return embed

    def get_background_embed(self):
        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Background Settings",
            description="Configure the background of your level card",
            color=discord.Color.blue()
        )

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
                value="Default",
                inline=False
            )

        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

        embed.set_footer(text="Background Settings", icon_url=self.bot.user.display_avatar.url)
        return embed

    def get_username_embed(self):
        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Username Settings",
            description="Configure username and discriminator display",
            color=discord.Color.purple()
        )

        username_color = self.config.get("username_color", [255, 255, 255])
        embed.add_field(
            name="Current Username Color",
            value=f"RGB({username_color[0]}, {username_color[1]}, {username_color[2]})",
            inline=False
        )

        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

        embed.set_footer(text="Username Settings", icon_url=self.bot.user.display_avatar.url)
        return embed

    def get_profile_outline_embed(self):
        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Profile Outline Settings",
            description="Configure the profile picture outline",
            color=discord.Color.orange()
        )

        profile_config = self.config.get("profile_outline", {})
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

        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

        embed.set_footer(text="Profile Outline Settings", icon_url=self.bot.user.display_avatar.url)
        return embed

    def get_content_embed(self):
        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Content Settings",
            description="Configure text content and ranking display",
            color=discord.Color.blue()
        )

        level_color = self.config.get("level_color", [245, 55, 48])
        ranking_config = self.config.get("ranking_position", {})
        ranking_color = ranking_config.get("color", [255, 255, 255])

        embed.add_field(
            name="Level Color",
            value=f"RGB({level_color[0]}, {level_color[1]}, {level_color[2]})",
            inline=True
        )

        embed.add_field(
            name="Ranking Color", 
            value=f"RGB({ranking_color[0]}, {ranking_color[1]}, {ranking_color[2]})",
            inline=True
        )

        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

        embed.set_footer(text="Content Settings", icon_url=self.bot.user.display_avatar.url)
        return embed

    def get_level_text_embed(self):
        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Level Text Settings",
            description="Configure the level text display",
            color=discord.Color.red()
        )

        level_color = self.config.get("level_color", [245, 55, 48])
        embed.add_field(
            name="Current Level Text Color",
            value=f"RGB({level_color[0]}, {level_color[1]}, {level_color[2]})",
            inline=False
        )

        if self.config.get("level_text_image"):
            embed.add_field(
                name="Custom Image",
                value="<:SucessLOGO:1407071637840592977> Custom level text image set",
                inline=False
            )

        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

        embed.set_footer(text="Level Text Settings", icon_url=self.bot.user.display_avatar.url)
        return embed

    def get_ranking_text_embed(self):
        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Ranking Text Settings", 
            description="Configure the ranking position display",
            color=discord.Color.gold()
        )

        ranking_config = self.config.get("ranking_position", {})
        ranking_color = ranking_config.get("color", [255, 255, 255])

        embed.add_field(
            name="Current Ranking Color",
            value=f"RGB({ranking_color[0]}, {ranking_color[1]}, {ranking_color[2]})",
            inline=False
        )

        if ranking_config.get("background_image") and ranking_config["background_image"] != "None":
            embed.add_field(
                name="Custom Image",
                value="<:SucessLOGO:1407071637840592977> Custom ranking image set",
                inline=False
            )

        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

        embed.set_footer(text="Ranking Text Settings", icon_url=self.bot.user.display_avatar.url)
        return embed

    def get_waiting_image_embed(self):
        embed = discord.Embed(
            title="<:UploadLOGO:1407072005567545478> Upload Image",
            description="Please send an image file in this channel.\n\n**Only you can upload the image for security reasons.**",
            color=discord.Color.blue()
        )

        embed.set_footer(text="Upload Image", icon_url=self.bot.user.display_avatar.url)
        return embed

    def save_config(self):
        """Save the current configuration to JSON file"""
        save_user_level_card_config(self.user_id, self.config)

    def has_permission_for_feature(self, feature_type, action_type):
        """Check if user has permission for a specific feature and action type"""
        try:
            data = load_leveling_data()
            permissions = data["leveling_settings"].get("customization_permissions", {})

            # Map features to permission categories
            feature_mapping = {
                "background": "background",
                "username": "username", 
                "profile_outline": "avatar_outline",
                "xp_info": "content",
                "xp_progress": "bar_progress",
                "xp_bar": "bar_progress",
                "level_text": "content",
                "ranking_text": "content"
            }

            permission_category = feature_mapping.get(feature_type, feature_type)
            category_config = permissions.get(permission_category, {})

            # Check if category is enabled
            if not category_config.get("enabled", True):
                return False

            # Get required level for action type
            required_level = 0
            if action_type == "color":
                required_level = category_config.get("color_permission_level", 0)
            elif action_type == "image":
                required_level = category_config.get("image_permission_level", 0)

            return self.user_level >= required_level
        except Exception as e:
            print(f"Error checking permissions: {e}")
            return True  # Default to allowing if error

    def has_current_image(self):
        """Check if current mode has an image set"""
        if self.mode == "xp_bar_image":
            return self.config.get("level_bar_image") and self.config["level_bar_image"] != "https://raw.githubusercontent.com/TheBlueEL/pictures/refs/heads/main/LevelBar.png"
        elif self.mode == "background_image":
            return self.config.get("background_image") and self.config["background_image"] != "None"
        elif self.mode == "profile_outline_image":
            return self.config.get("profile_outline", {}).get("custom_image")
        elif self.mode == "username_image":
            return self.config.get("username_image") and self.config["username_image"] != "None"
        elif self.mode == "xp_info_image":
            return self.config.get("xp_info_image") and self.config["xp_info_image"] != "None"
        elif self.mode == "xp_progress_image":
            return self.config.get("xp_progress_image") and self.config["xp_progress_image"] != "None"
        elif self.mode == "level_text_image":
            return self.config.get("level_text_image") and self.config["level_text_image"] != "None"
        elif self.mode == "ranking_text_image":
            return self.config.get("ranking_position", {}).get("background_image") and self.config["ranking_position"]["background_image"] != "None"
        return False

    def has_modified_color(self):
        """Check if current mode has color modified from default"""
        default_config = {
            "xp_text_color": [65, 65, 69],
            "xp_bar_color": [225, 66, 53], 
            "background_color": [15, 17, 16],
            "username_color": [255, 255, 255],
            "level_color": [245, 55, 48]
        }

        if self.mode == "xp_info_color":
            current = self.config.get("xp_text_color", default_config["xp_text_color"])
            return current != default_config["xp_text_color"]
        elif self.mode == "xp_progress_color":
            current = self.config.get("xp_bar_color", default_config["xp_bar_color"])
            return current != default_config["xp_bar_color"]
        elif self.mode == "background_color":
            current = self.config.get("background_color", default_config["background_color"])
            return current != default_config["background_color"]
        elif self.mode == "username_color":
            current = self.config.get("username_color", default_config["username_color"])
            return current != default_config["username_color"]
        elif self.mode == "profile_outline_color":
            return self.config.get("profile_outline", {}).get("color_override") is not None
        elif self.mode == "level_text_color":
            current = self.config.get("level_color", default_config["level_color"])
            return current != default_config["level_color"]
        elif self.mode == "ranking_text_color":
            current = self.config.get("ranking_position", {}).get("color", [255, 255, 255])
            return current != [255, 255, 255]
        return False

    async def generate_preview_image(self, interaction_user):
        """Generate preview image and upload it to GitHub"""
        try:
            leveling_system = self.bot.get_cog('LevelingSystem')
            if not leveling_system:
                return False

            preview_image = await leveling_system.create_level_card(interaction_user)

            if preview_image:
                # Save preview to temp file
                os.makedirs('images', exist_ok=True)
                import time
                timestamp = int(time.time())

                # Determine extension based on content
                preview_image.seek(0)
                file_header = preview_image.read(10)
                preview_image.seek(0)

                if file_header.startswith(b'GIF'):
                    filename = f"level_preview_{self.user_id}_{timestamp}.gif"
                else:
                    filename = f"level_preview_{self.user_id}_{timestamp}.png"

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

                        # Set GitHub raw URL
                        filename = os.path.basename(file_path)
                        self.preview_image_url = f"https://raw.githubusercontent.com/TheBlueEL/pictures/main/{filename}?t={timestamp}"
                        return True
                except ImportError:
                    print("GitHub sync not available")

        except Exception as e:
            print(f"Error generating preview: {e}")

        return False

    def get_current_button_states(self):
        """Get current button states for dynamic toggles"""
        data = load_leveling_data()

        # System toggle state
        system_enabled = data["leveling_settings"]["enabled"]

        # Messages XP toggle state
        messages_enabled = data["leveling_settings"]["xp_settings"]["messages"]["enabled"]

        # Characters XP toggle state
        characters_enabled = data["leveling_settings"]["xp_settings"]["characters"]["enabled"]

        # Profile outline toggle state
        profile_outline_enabled = self.config.get("profile_outline", {}).get("enabled", True)

        return {
            "system": system_enabled,
            "messages": messages_enabled,
            "characters": characters_enabled,
            "profile_outline": profile_outline_enabled
        }

    def update_buttons(self):
        self.clear_items()

        if self.waiting_for_image:
            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1407071474233114766>"
            )
            back_button.callback = self.back_from_image_upload
            self.add_item(back_button)

        elif self.mode == "leveling_bar":
            # Leveling Bar main buttons
            xp_info_button = discord.ui.Button(
                label="XP Info",
                style=discord.ButtonStyle.secondary,
                emoji="<:XPInfoLOGO:1409633663389405294>"
            )
            xp_info_button.callback = self.xp_info_settings

            xp_bar_button = discord.ui.Button(
                label="XP Bar",
                style=discord.ButtonStyle.secondary,
                emoji="<:XPbarLOGO:1409633757018984531>"
            )
            xp_bar_button.callback = self.xp_bar_settings

            xp_progress_button = discord.ui.Button(
                label="XP Progress",
                style=discord.ButtonStyle.secondary,
                emoji="<:XPprogressLOGO:1409633736387199117>"
            )
            xp_progress_button.callback = self.xp_progress_settings

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1407071474233114766>"
            )
            back_button.callback = self.back_to_main

            self.add_item(xp_info_button)
            self.add_item(xp_bar_button)
            self.add_item(xp_progress_button)
            self.add_item(back_button)

        elif self.mode in ["xp_info_color", "xp_progress_color", "xp_bar_color", "background_color", "username_color", "profile_outline_color", "level_text_color", "ranking_text_color"]:
            # Color selection buttons
            feature_type = self.mode.replace("_color", "")
            has_permission = self.has_permission_for_feature(feature_type, "color")

            hex_button = discord.ui.Button(
                label="Hex Code",
                style=discord.ButtonStyle.secondary,
                emoji="<:HEXcodeLOGO:1408833347404304434>",
                disabled=not has_permission
            )
            hex_button.callback = self.hex_color

            rgb_button = discord.ui.Button(
                label="RGB Code",
                style=discord.ButtonStyle.secondary,
                emoji="<:RGBcodeLOGO:1408831982141575290>",
                disabled=not has_permission
            )
            rgb_button.callback = self.rgb_color

            # Only show reset button if color has been modified from default
            has_modified_color = self.has_modified_color()
            if has_modified_color:
                reset_button = discord.ui.Button(
                    label="Reset",
                    style=discord.ButtonStyle.secondary,
                    emoji="<:UpdateLOGO:1407072818214080695>",
                    disabled=not has_permission
                )
                reset_button.callback = self.reset_color
                self.add_item(reset_button)

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1407071474233114766>"
            )
            back_button.callback = self.back_to_parent

            self.add_item(hex_button)
            self.add_item(rgb_button)
            self.add_item(back_button)

        elif self.mode in ["xp_bar_image", "background_image", "profile_outline_image", "username_image", "xp_info_image", "xp_progress_image", "level_text_image", "ranking_text_image"]:
            # Image selection buttons
            feature_type = self.mode.replace("_image", "")
            has_permission = self.has_permission_for_feature(feature_type, "image")

            url_button = discord.ui.Button(
                label="Set URL",
                style=discord.ButtonStyle.secondary,
                emoji="<:URLLOGO:1407071963809054931>",
                disabled=not has_permission
            )
            url_button.callback = self.image_url

            upload_button = discord.ui.Button(
                label="Upload Image",
                style=discord.ButtonStyle.secondary,
                emoji="<:UploadLOGO:1407072005567545478>",
                disabled=not has_permission
            )
            upload_button.callback = self.upload_image

            # Only show clear button if there's actually an image to clear
            has_image = self.has_current_image()
            if has_image:
                clear_button = discord.ui.Button(
                    label="Clear Image",
                    style=discord.ButtonStyle.danger,
                    emoji="<:DeleteLOGO:1407071421363916841>",
                    disabled=not has_permission
                )
                clear_button.callback = self.clear_image
                self.add_item(clear_button)

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1407071474233114766>"
            )
            back_button.callback = self.back_to_parent

            self.add_item(url_button)
            self.add_item(upload_button)
            self.add_item(back_button)

        elif self.mode in ["xp_info", "xp_progress", "background", "username"]:
            # Sub-category buttons with permission checks
            feature_type = self.mode
            has_color_permission = self.has_permission_for_feature(feature_type, "color")
            has_image_permission = self.has_permission_for_feature(feature_type, "image")

            color_button = discord.ui.Button(
                label="Color",
                style=discord.ButtonStyle.secondary,
                emoji="<:ColorLOGO:1408828590241615883>",
                disabled=not has_color_permission
            )
            color_button.callback = self.color_settings

            # Add image button for all categories
            image_button = discord.ui.Button(
                label="Image",
                style=discord.ButtonStyle.secondary,
                emoji="<:ImageLOGO:1407072328134951043>",
                disabled=not has_image_permission
            )
            image_button.callback = self.image_settings
            self.add_item(image_button)

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1407071474233114766>"
            )
            back_button.callback = self.back_to_parent

            self.add_item(color_button)
            self.add_item(back_button)

        elif self.mode == "xp_bar":
            # XP Bar specific buttons with permission checks
            has_color_permission = self.has_permission_for_feature("xp_bar", "color")
            has_image_permission = self.has_permission_for_feature("xp_bar", "image")

            color_button = discord.ui.Button(
                label="Color",
                style=discord.ButtonStyle.secondary,
                emoji="<:ColorLOGO:1408828590241615883>",
                disabled=not has_color_permission
            )
            color_button.callback = self.color_settings

            image_button = discord.ui.Button(
                label="Image",
                style=discord.ButtonStyle.secondary,
                emoji="<:ImageLOGO:1407072328134951043>",
                disabled=not has_image_permission
            )
            image_button.callback = self.image_settings

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1407071474233114766>"
            )
            back_button.callback = self.back_to_parent

            self.add_item(color_button)
            self.add_item(image_button)
            self.add_item(back_button)

        elif self.mode == "profile_outline":
            # Profile outline main buttons with permission checks
            has_color_permission = self.has_permission_for_feature("profile_outline", "color")
            has_image_permission = self.has_permission_for_feature("profile_outline", "image")

            # Dynamic toggle button
            is_enabled = self.config.get("profile_outline", {}).get("enabled", True)
            toggle_button = discord.ui.Button(
                label="ON" if is_enabled else "OFF",
                style=discord.ButtonStyle.success if is_enabled else discord.ButtonStyle.danger,
                emoji="<:OnLOGO:1407072463883472978>" if is_enabled else "<:OffLOGO:1407072621836894380>"
            )
            toggle_button.callback = self.toggle_profile_outline

            color_button = discord.ui.Button(
                label="Color",
                style=discord.ButtonStyle.secondary,
                emoji="<:ColorLOGO:1408828590241615883>",
                disabled=not has_color_permission
            )
            color_button.callback = self.color_settings

            image_button = discord.ui.Button(
                label="Image",
                style=discord.ButtonStyle.secondary,
                emoji="<:ImageLOGO:1407072328134951043>",
                disabled=not has_image_permission
            )
            image_button.callback = self.image_settings

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1407071474233114766>"
            )
            back_button.callback = self.back_to_main

            self.add_item(toggle_button)
            self.add_item(color_button)
            self.add_item(image_button)
            self.add_item(back_button)

        elif self.mode == "content":
            # Content main buttons
            level_button = discord.ui.Button(
                label="Level",
                style=discord.ButtonStyle.secondary,
                emoji="<a:XPLOGO:1409634015043915827>"
            )
            level_button.callback = self.level_text_settings

            ranking_button = discord.ui.Button(
                label="Classement",
                style=discord.ButtonStyle.secondary,
                emoji="<:WinnerLOGO:1409635881198948593>"
            )
            ranking_button.callback = self.ranking_text_settings

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1407071474233114766>"
            )
            back_button.callback = self.back_to_main

            self.add_item(level_button)
            self.add_item(ranking_button)
            self.add_item(back_button)

        elif self.mode in ["level_text", "ranking_text"]:
            # Level/Ranking text buttons with permission checks
            has_color_permission = self.has_permission_for_feature(self.mode, "color")
            has_image_permission = self.has_permission_for_feature(self.mode, "image")

            color_button = discord.ui.Button(
                label="Color",
                style=discord.ButtonStyle.secondary,
                emoji="<:ColorLOGO:1408828590241615883>",
                disabled=not has_color_permission
            )
            color_button.callback = self.color_settings

            image_button = discord.ui.Button(
                label="Image",
                style=discord.ButtonStyle.secondary,
                emoji="<:ImageLOGO:1407072328134951043>",
                disabled=not has_image_permission
            )
            image_button.callback = self.image_settings

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1407071474233114766>"
            )
            back_button.callback = self.back_to_parent

            self.add_item(color_button)
            self.add_item(image_button)
            self.add_item(back_button)

        else:  # main mode
            # Main buttons - 3 per row
            leveling_bar_button = discord.ui.Button(
                label="Leveling Bar",
                style=discord.ButtonStyle.secondary,
                emoji="<:XPprogressLOGO:1409633736387199117>",
                row=0
            )
            leveling_bar_button.callback = self.leveling_bar_settings

            background_button = discord.ui.Button(
                label="Background",
                style=discord.ButtonStyle.secondary,
                emoji="<:BackgroundLOGO:1408834163309805579>",
                row=0
            )
            background_button.callback = self.background_settings

            username_button = discord.ui.Button(
                label="Username",
                style=discord.ButtonStyle.secondary,
                emoji="<:ParticipantsLOGO:1407733929389199460>",
                row=0
            )
            username_button.callback = self.username_settings

            profile_outline_button = discord.ui.Button(
                label="Profile Outline",
                style=discord.ButtonStyle.secondary,
                emoji="<:ProfileLOGO:1408830057819930806>",
                row=1
            )
            profile_outline_button.callback = self.profile_outline_settings

            content_button = discord.ui.Button(
                label="Content",
                style=discord.ButtonStyle.secondary,
                emoji="<:DescriptionLOGO:1407733417172533299>",
                row=1
            )
            content_button.callback = self.content_settings

            self.add_item(leveling_bar_button)
            self.add_item(background_button)
            self.add_item(username_button)
            self.add_item(profile_outline_button)
            self.add_item(content_button)

            # Only add Back button if NOT in DMs
            if not getattr(self, 'is_dm', False):
                back_button = discord.ui.Button(
                    label="Back",
                    style=discord.ButtonStyle.gray,
                    emoji="<:BackLOGO:1407071474233114766>",
                    row=1
                )
                back_button.callback = self.back_to_level_system
                self.add_item(back_button)

    # Main navigation callbacks
    async def leveling_bar_settings(self, interaction: discord.Interaction):
        self.mode = "leveling_bar"
        embed = self.get_leveling_bar_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def background_settings(self, interaction: discord.Interaction):
        self.mode = "background"
        embed = self.get_background_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def username_settings(self, interaction: discord.Interaction):
        self.mode = "username"
        embed = self.get_username_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def profile_outline_settings(self, interaction: discord.Interaction):
        self.mode = "profile_outline"
        embed = self.get_profile_outline_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def content_settings(self, interaction: discord.Interaction):
        self.mode = "content"
        embed = self.get_content_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def level_text_settings(self, interaction: discord.Interaction):
        self.mode = "level_text"
        embed = self.get_level_text_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def ranking_text_settings(self, interaction: discord.Interaction):
        self.mode = "ranking_text"
        embed = self.get_ranking_text_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    # Sub-category callbacks
    async def xp_info_settings(self, interaction: discord.Interaction):
        self.mode = "xp_info"
        embed = self.get_xp_info_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def xp_bar_settings(self, interaction: discord.Interaction):
        self.mode = "xp_bar"
        embed = self.get_xp_bar_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def xp_progress_settings(self, interaction: discord.Interaction):
        self.mode = "xp_progress"
        embed = self.get_xp_progress_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    # Color and Image callbacks
    async def color_settings(self, interaction: discord.Interaction):
        self.mode = self.mode + "_color"
        if self.mode == "xp_info_color":
            embed = self.get_xp_info_embed()
            embed.title = "<:ColorLOGO:1408828590241615883> XP Info Color"
            embed.description = "Choose how to set your XP text color"
        elif self.mode == "xp_progress_color":
            embed = self.get_xp_progress_embed()
            embed.title = "<:ColorLOGO:1408828590241615883> XP Progress Color"
            embed.description = "Choose how to set your XP progress bar color"
        elif self.mode == "xp_bar_color":
            embed = self.get_xp_bar_embed()
            embed.title = "<:ColorLOGO:1408828590241615883> XP Bar Color"
            embed.description = "Choose how to set your XP bar color"
        elif self.mode == "background_color":
            embed = self.get_background_embed()
            embed.title = "<:ColorLOGO:1408828590241615883> Background Color"
            embed.description = "Choose how to set your background color"
        elif self.mode == "username_color":
            embed = self.get_username_embed()
            embed.title = "<:ColorLOGO:1408828590241615883> Username Color"
            embed.description = "Choose how to set your username color"
        elif self.mode == "profile_outline_color":
            embed = self.get_profile_outline_embed()
            embed.title = "<:ColorLOGO:1408828590241615883> Profile Outline Color"
            embed.description = "Choose how to set your profile outline color"
        elif self.mode == "level_text_color":
            embed = self.get_level_text_embed()
            embed.title = "<:ColorLOGO:1408828590241615883> Level Text Color"
            embed.description = "Choose how to set your level text color"
        elif self.mode == "ranking_text_color":
            embed = self.get_ranking_text_embed()
            embed.title = "<:ColorLOGO:1408828590241615883> Ranking Text Color"
            embed.description = "Choose how to set your ranking text color"
        else:
            # Fallback pour les modes non prévus
            embed = self.get_main_embed()
            embed.title = "<:ColorLOGO:1408828590241615883> Color Settings"
            embed.description = "Choose how to set your color"

        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def image_settings(self, interaction: discord.Interaction):
        self.mode = self.mode + "_image"
        if self.mode == "xp_bar_image":
            embed = self.get_xp_bar_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> XP Bar Image"
            embed.description = "Set a custom XP bar image"
        elif self.mode == "background_image":
            embed = self.get_background_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Background Image"
            embed.description = "Set a custom background image"
        elif self.mode == "profile_outline_image":
            embed = self.get_profile_outline_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Profile Outline Image"
            embed.description = "Set a custom profile outline image"
        elif self.mode == "xp_info_image":
            embed = self.get_xp_info_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> XP Info Image"
            embed.description = "Set a custom XP text image overlay"
        elif self.mode == "xp_progress_image":
            embed = self.get_xp_progress_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> XP Progress Image"
            embed.description = "Set a custom XP progress image overlay"
        elif self.mode == "username_image":
            embed = self.get_username_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Username Image"
            embed.description = "Set a custom username image overlay"
        elif self.mode == "level_text_image":
            embed = self.get_level_text_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Level Text Image"
            embed.description = "Set a custom level text image overlay"
        elif self.mode == "ranking_text_image":
            embed = self.get_ranking_text_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Ranking Text Image"
            embed.description = "Set a custom ranking text image overlay"
        else:
            # Fallback pour les modes non prévus
            embed = self.get_main_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Image Settings"
            embed.description = "Set a custom image"

        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    # Modal callbacks
    async def hex_color(self, interaction: discord.Interaction):
        modal = LevelCardHexColorModal(self)
        await interaction.response.send_modal(modal)

    async def rgb_color(self, interaction: discord.Interaction):
        modal = LevelCardRGBColorModal(self)
        await interaction.response.send_modal(modal)

    async def image_url(self, interaction: discord.Interaction):
        modal = LevelCardImageURLModal(self)
        await interaction.response.send_modal(modal)

    async def upload_image(self, interaction: discord.Interaction):
        self.waiting_for_image = True
        self.current_image_type = self.mode.replace("_image", "")
        embed = self.get_waiting_image_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def clear_image(self, interaction: discord.Interaction):
        await interaction.response.defer()

        if self.mode == "xp_bar_image":
            self.config.pop("level_bar_image", None)
        elif self.mode == "background_image":
            self.config.pop("background_image", None)
            # Restore default background color when clearing image
            if "background_color" not in self.config:
                self.config["background_color"] = [15, 17, 16]
        elif self.mode == "profile_outline_image":
            if "profile_outline" not in self.config:
                self.config["profile_outline"] = {}
            self.config["profile_outline"].pop("custom_image", None)
        elif self.mode == "username_image":
            self.config.pop("username_image", None)
        elif self.mode == "xp_info_image":
            self.config.pop("xp_info_image", None)
        elif self.mode == "xp_progress_image":
            self.config.pop("xp_progress_image", None)
        elif self.mode == "level_text_image":
            self.config.pop("level_text_image", None)
        elif self.mode == "ranking_text_image":
            if "ranking_position" not in self.config:
                self.config["ranking_position"] = {}
            self.config["ranking_position"].pop("background_image", None)

        self.save_config()
        await self.generate_preview_image(interaction.user)

        # Go back to appropriate embed
        if self.mode == "xp_bar_image":
            embed = self.get_xp_bar_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> XP Bar Image"
            embed.description = "Set a custom XP bar image"
        elif self.mode == "background_image":
            embed = self.get_background_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Background Image"
            embed.description = "Set a custom background image"
        elif self.mode == "profile_outline_image":
            embed = self.get_profile_outline_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Profile Outline Image"
            embed.description = "Set a custom profile outline image"
        elif self.mode == "username_image":
            embed = self.get_username_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Username Image"
            embed.description = "Set a custom username image overlay"
        elif self.mode == "xp_info_image":
            embed = self.get_xp_info_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> XP Info Image"
            embed.description = "Set a custom XP text image overlay"
        elif self.mode == "xp_progress_image":
            embed = self.get_xp_progress_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> XP Progress Image"
            embed.description = "Set a custom XP progress image overlay"
        elif self.mode == "level_text_image":
            embed = self.get_level_text_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Level Text Image"
            embed.description = "Set a custom level text image overlay"
        elif self.mode == "ranking_text_image":
            embed = self.get_ranking_text_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Ranking Text Image"
            embed.description = "Set a custom ranking text image overlay"
        else:
            # Fallback to main embed if mode not recognized
            embed = self.get_main_embed()

        self.update_buttons()
        await interaction.edit_original_response(embed=embed, view=self)

    async def reset_color(self, interaction: discord.Interaction):
        await interaction.response.defer()

        # Get default values from the original config structure
        default_config = {
            "xp_text_color": [65, 65, 69],
            "xp_bar_color": [225, 66, 53], 
            "background_color": [15, 17, 16],
            "username_color": [255, 255, 255],
            "level_color": [245, 55, 48]
        }

        if self.mode == "xp_info_color":
            self.config["xp_text_color"] = default_config["xp_text_color"]
        elif self.mode == "xp_progress_color":
            self.config["xp_bar_color"] = default_config["xp_bar_color"]
        elif self.mode == "background_color":
            self.config["background_color"] = default_config["background_color"]
        elif self.mode == "username_color":
            self.config["username_color"] = default_config["username_color"]
        elif self.mode == "profile_outline_color":
            if "profile_outline" not in self.config:
                self.config["profile_outline"] = {}
            self.config["profile_outline"].pop("color_override", None)
        elif self.mode == "level_text_color":
            self.config["level_color"] = default_config["level_color"]
        elif self.mode == "ranking_text_color":
            if "ranking_position" not in self.config:
                self.config["ranking_position"] = {}
            self.config["ranking_position"]["color"] = [255, 255, 255]

        self.save_config()
        await self.generate_preview_image(interaction.user)

        # Go back to appropriate embed
        if self.mode == "xp_info_color":
            embed = self.get_xp_info_embed()
            embed.title = "<:ColorLOGO:1408828590241615883> XP Info Color"
            embed.description = "Choose how to set your XP text color"
        elif self.mode == "xp_progress_color":
            embed = self.get_xp_progress_embed()
            embed.title = "<:ColorLOGO:1408828590241615883> XP Progress Color"
            embed.description = "Choose how to set your XP progress bar color"
        elif self.mode == "background_color":
            embed = self.get_background_embed()
            embed.title = "<:ColorLOGO:1408828590241615883> Background Color"
            embed.description = "Choose how to set your background color"
        elif self.mode == "username_color":
            embed = self.get_username_embed()
            embed.title = "<:ColorLOGO:1408828590241615883> Username Color"
            embed.description = "Choose how to set your username color"
        elif self.mode == "profile_outline_color":
            embed = self.get_profile_outline_embed()
            embed.title = "<:ColorLOGO:1408828590241615883> Profile Outline Color"
            embed.description = "Choose how to set your profile outline color"
        elif self.mode == "level_text_color":
            embed = self.get_level_text_embed()
            embed.title = "<:ColorLOGO:1408828590241615883> Level Text Color"
            embed.description = "Choose how to set your level text color"
        elif self.mode == "ranking_text_color":
            embed = self.get_ranking_text_embed()
            embed.title = "<:ColorLOGO:1408828590241615883> Ranking Text Color"
            embed.description = "Choose how to set your ranking text color"

        self.update_buttons()
        await interaction.edit_original_response(embed=embed, view=self)

    async def toggle_profile_outline(self, interaction: discord.Interaction):
        await interaction.response.defer()

        if "profile_outline" not in self.config:
            self.config["profile_outline"] = {}
        current_state = self.config["profile_outline"].get("enabled", True)
        self.config["profile_outline"]["enabled"] = not current_state
        self.save_config()

        await self.generate_preview_image(interaction.user)

        embed = self.get_profile_outline_embed()
        self.update_buttons()
        await interaction.edit_original_response(embed=embed, view=self)

    # Navigation callbacks
    async def back_to_main(self, interaction: discord.Interaction):
        self.mode = "main"
        embed = self.get_main_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def back_to_parent(self, interaction: discord.Interaction):
        original_mode = self.mode

        # Handle color/image mode suffixes
        if self.mode.endswith("_color") or self.mode.endswith("_image"):
            self.mode = self.mode.replace("_color", "").replace("_image", "")

        # Navigate back to appropriate parent
        if self.mode == "xp_info":
            if original_mode.endswith("_color") or original_mode.endswith("_image"):
                embed = self.get_xp_info_embed()
            else:
                self.mode = "leveling_bar"
                embed = self.get_leveling_bar_embed()
        elif self.mode == "xp_bar":
            if original_mode.endswith("_color") or original_mode.endswith("_image"):
                embed = self.get_xp_bar_embed()
            else:
                self.mode = "leveling_bar"
                embed = self.get_leveling_bar_embed()
        elif self.mode == "xp_progress":
            if original_mode.endswith("_color") or original_mode.endswith("_image"):
                embed = self.get_xp_progress_embed()
            else:
                self.mode = "leveling_bar"
                embed = self.get_leveling_bar_embed()
        elif self.mode == "background":
            if original_mode.endswith("_color") or original_mode.endswith("_image"):
                embed = self.get_background_embed()
            else:
                self.mode = "main"
                embed = self.get_main_embed()
        elif self.mode == "username":
            if original_mode.endswith("_color") or original_mode.endswith("_image"):
                embed = self.get_username_embed()
            else:
                self.mode = "main"
                embed = self.get_main_embed()
        elif self.mode == "profile_outline":
            if original_mode.endswith("_color") or original_mode.endswith("_image"):
                embed = self.get_profile_outline_embed()
            else:
                self.mode = "main"
                embed = self.get_main_embed()
        elif self.mode == "level_text":
            if original_mode.endswith("_color") or original_mode.endswith("_image"):
                embed = self.get_level_text_embed()
            else:
                self.mode = "content"
                embed = self.get_content_embed()
        elif self.mode == "ranking_text":
            if original_mode.endswith("_color") or original_mode.endswith("_image"):
                embed = self.get_ranking_text_embed()
            else:
                self.mode = "content"
                embed = self.get_content_embed()
        elif self.mode == "content":
            self.mode = "main"
            embed = self.get_main_embed()
        else:
            self.mode = "main"
            embed = self.get_main_embed()

        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def back_from_image_upload(self, interaction: discord.Interaction):
        self.waiting_for_image = False
        self.mode = self.current_image_type + "_image"

        if self.mode == "xp_bar_image":
            embed = self.get_xp_bar_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> XP Bar Image"
            embed.description = "Set a custom XP bar image"
        elif self.mode == "background_image":
            embed = self.get_background_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Background Image"
            embed.description = "Set a custom background image"
        elif self.mode == "profile_outline_image":
            embed = self.get_profile_outline_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Profile Outline Image"
            embed.description = "Set a custom profile outline image"
        elif self.mode == "username_image":
            embed = self.get_username_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Username Image"
            embed.description = "Set a custom username image overlay"
        elif self.mode == "xp_info_image":
            embed = self.get_xp_info_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> XP Info Image"
            embed.description = "Set a custom XP text image overlay"
        elif self.mode == "xp_progress_image":
            embed = self.get_xp_progress_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> XP Progress Image"
            embed.description = "Set a custom XP progress image overlay"
        elif self.mode == "level_text_image":
            embed = self.get_level_text_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Level Text Image"
            embed.description = "Set a custom level text image overlay"
        elif self.mode == "ranking_text_image":
            embed = self.get_ranking_text_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Ranking Text Image"
            embed.description = "Set a custom ranking text image overlay"
        else:
            # Fallback
            embed = self.get_main_embed()

        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def close_dm(self, interaction: discord.Interaction):
        """Close the DM message"""
        try:
            await interaction.response.edit_message(content="Settings closed.", embed=None, view=None)
        except:
            await interaction.response.send_message("Settings closed.", ephemeral=True)

    async def back_to_level_system(self, interaction: discord.Interaction):
        """Go back to the main level system menu or close if in DM"""
        # Check if we're in DMs
        if isinstance(interaction.channel, discord.DMChannel):
            # In DMs, close the message
            try:
                await interaction.response.edit_message(view=None)
            except:
                await interaction.response.send_message("Settings closed.", ephemeral=True)
        else:
            # In guild, go back to level system
            view = LevelSystemMainView(self.bot, interaction.user)

            # Regenerate demo card to ensure image is displayed
            leveling_system = self.bot.get_cog('LevelingSystem')
            if leveling_system:
                await leveling_system.generate_demo_card_for_main_view(view)

            embed = view.get_main_embed()
            await interaction.response.edit_message(embed=embed, view=view)

# Modal classes for Level Card
class LevelCardHexColorModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='Hex Color')
        self.view = view

        # Get current color value
        current_color = ""
        if self.view.mode == "xp_info_color" and self.view.config.get("xp_text_color"):
            rgb = self.view.config["xp_text_color"]
            current_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        elif self.view.mode == "xp_progress_color" and self.view.config.get("xp_bar_color"):
            rgb = self.view.config["xp_bar_color"]
            current_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        elif self.view.mode == "xp_bar_color" and self.view.config.get("xp_bar_color"):
            rgb = self.view.config["xp_bar_color"]
            current_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        elif self.view.mode == "background_color" and self.view.config.get("background_color"):
            rgb = self.view.config["background_color"]
            current_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        elif self.view.mode == "username_color" and self.view.config.get("username_color"):
            rgb = self.view.config["username_color"]
            current_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        elif self.view.mode == "profile_outline_color":
            profile_config = self.view.config.get("profile_outline", {})
            if profile_config.get("color_override"):
                rgb = profile_config["color_override"]
                current_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        elif self.view.mode == "level_text_color" and self.view.config.get("level_color"):
            rgb = self.view.config["level_color"]
            current_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        elif self.view.mode == "ranking_text_color":
            ranking_config = self.view.config.get("ranking_position", {})
            if ranking_config.get("color"):
                rgb = ranking_config["color"]
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

            if self.view.mode == "xp_info_color":
                self.view.config["xp_text_color"] = list(rgb)
            elif self.view.mode == "xp_progress_color":
                self.view.config["xp_bar_color"] = list(rgb)
            elif self.view.mode == "xp_bar_color":
                self.view.config["xp_bar_color"] = list(rgb)
            elif self.view.mode == "background_color":
                self.view.config["background_color"] = list(rgb)
                self.view.config.pop("background_image", None)
            elif self.view.mode == "username_color":
                self.view.config["username_color"] = list(rgb)
            elif self.view.mode == "profile_outline_color":
                if "profile_outline" not in self.view.config:
                    self.view.config["profile_outline"] = {}
                self.view.config["profile_outline"]["color_override"] = list(rgb)
                self.view.config["profile_outline"].pop("custom_image", None)
            elif self.view.mode == "level_text_color":
                self.view.config["level_color"] = list(rgb)
            elif self.view.mode == "ranking_text_color":
                if "ranking_position" not in self.view.config:
                    self.view.config["ranking_position"] = {}
                self.view.config["ranking_position"]["color"] = list(rgb)

            self.view.save_config()
            await self.view.generate_preview_image(interaction.user)

            # Return to appropriate embed
            if self.view.mode == "xp_info_color":
                embed = self.view.get_xp_info_embed()
                embed.title = "<:ColorLOGO:1408828590241615883> XP Info Color"
                embed.description = "Choose how to set your XP text color"
            elif self.view.mode == "xp_progress_color":
                embed = self.view.get_xp_progress_embed()
                embed.title = "<:ColorLOGO:1408828590241615883> XP Progress Color"
                embed.description = "Choose how to set your XP progress bar color"
            elif self.view.mode == "xp_bar_color":
                embed = self.view.get_xp_bar_embed()
                embed.title = "<:ColorLOGO:1408828590241615883> XP Bar Color"
                embed.description = "Choose how to set your XP bar color"
            elif self.view.mode == "background_color":
                embed = self.view.get_background_embed()
                embed.title = "<:ColorLOGO:1408828590241615883> Background Color"
                embed.description = "Choose how to set your background color"
            elif self.view.mode == "username_color":
                embed = self.view.get_username_embed()
                embed.title = "<:ColorLOGO:1408828590241615883> Username Color"
                embed.description = "Choose how to set your username color"
            elif self.view.mode == "profile_outline_color":
                embed = self.view.get_profile_outline_embed()
                embed.title = "<:ColorLOGO:1408828590241615883> Profile Outline Color"
                embed.description = "Choose how to set your profile outline color"
            elif self.view.mode == "level_text_color":
                embed = self.view.get_level_text_embed()
                embed.title = "<:ColorLOGO:1408828590241615883> Level Text Color"
                embed.description = "Choose how to set your level text color"
            elif self.view.mode == "ranking_text_color":
                embed = self.view.get_ranking_text_embed()
                embed.title = "<:ColorLOGO:1408828590241615883> Ranking Text Color"
                embed.description = "Choose how to set your ranking text color"

            self.view.update_buttons()
            await interaction.edit_original_response(embed=embed, view=self.view)
        except ValueError:
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid Hex Color",
                description="Please enter a valid hex color code (e.g., #FF0000 or FF0000)",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

# Ajouter les modales HexColorModal et RGBColorModal génériques
class HexColorModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='Hex Color')
        self.view = view

        self.hex_input = discord.ui.TextInput(
            label='Hex Color Code',
            placeholder='#FFFFFF or FFFFFF',
            required=True,
            max_length=7
        )
        self.add_item(self.hex_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        hex_value = self.hex_input.value.strip()
        if hex_value.startswith('#'):
            hex_value = hex_value[1:]

        try:
            rgb = tuple(int(hex_value[i:i+2], 16) for i in (0, 2, 4))

            # Apply color based on current mode
            if self.view.mode == "xp_bar_color":
                self.view.config["xp_bar_color"] = list(rgb)
            elif self.view.mode == "level_text_color":
                self.view.config["level_color"] = list(rgb)
            elif self.view.mode == "ranking_text_color":
                if "ranking_position" not in self.view.config:
                    self.view.config["ranking_position"] = {}
                self.view.config["ranking_position"]["color"] = list(rgb)

            self.view.save_config()
            await self.view.generate_preview_image(interaction.user)

            # Update view
            self.view.update_buttons()

            # Get appropriate embed
            if self.view.mode == "xp_bar_color":
                embed = self.view.get_xp_bar_embed()
                embed.title = "<:ColorLOGO:1408828590241615883> XP Bar Color"
                embed.description = "Choose how to set your XP bar color"
            elif self.view.mode == "level_text_color":
                embed = self.view.get_level_text_embed()
                embed.title = "<:ColorLOGO:1408828590241615883> Level Text Color"
                embed.description = "Choose how to set your level text color"
            elif self.view.mode == "ranking_text_color":
                embed = self.view.get_ranking_text_embed()
                embed.title = "<:ColorLOGO:1408828590241615883> Ranking Text Color"
                embed.description = "Choose how to set your ranking text color"

            await interaction.edit_original_response(embed=embed, view=self.view)
        except ValueError:
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid Hex Color",
                description="Please enter a valid hex color code (e.g., #FF0000 or FF0000)",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

class RGBColorModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='RGB Color')
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
        await interaction.response.defer()

        try:
            r = int(self.red_input.value)
            g = int(self.green_input.value)
            b = int(self.blue_input.value)

            if not all(0 <= val <= 255 for val in [r, g, b]):
                raise ValueError("Values must be between 0 and 255")

            # Apply color based on current mode
            if self.view.mode == "xp_bar_color":
                self.view.config["xp_bar_color"] = [r, g, b]
            elif self.view.mode == "level_text_color":
                self.view.config["level_color"] = [r, g, b]
            elif self.view.mode == "ranking_text_color":
                if "ranking_position" not in self.view.config:
                    self.view.config["ranking_position"] = {}
                self.view.config["ranking_position"]["color"] = [r, g, b]

            self.view.save_config()
            await self.view.generate_preview_image(interaction.user)

            # Update view
            self.view.update_buttons()

            # Get appropriate embed
            if self.view.mode == "xp_bar_color":
                embed = self.view.get_xp_bar_embed()
                embed.title = "<:ColorLOGO:1408828590241615883> XP Bar Color"
                embed.description = "Choose how to set your XP bar color"
            elif self.view.mode == "level_text_color":
                embed = self.view.get_level_text_embed()
                embed.title = "<:ColorLOGO:1408828590241615883> Level Text Color"
                embed.description = "Choose how to set your level text color"
            elif self.view.mode == "ranking_text_color":
                embed = self.view.get_ranking_text_embed()
                embed.title = "<:ColorLOGO:1408828590241615883> Ranking Text Color"
                embed.description = "Choose how to set your ranking text color"

            await interaction.edit_original_response(embed=embed, view=self.view)
        except ValueError:
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid RGB Values",
                description="Please enter valid RGB values (0-255 for each color)",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

class ImageURLModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='Image URL')
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

        # Apply image based on current mode
        if self.view.mode == "username_image":
            self.view.config["username_image"] = url
        elif self.view.mode == "xp_info_image":
            self.view.config["xp_info_image"] = url
        elif self.view.mode == "xp_progress_image":
            self.view.config["xp_progress_image"] = url
        elif self.view.mode == "level_text_image":
            self.view.config["level_text_image"] = url
        elif self.view.mode == "ranking_text_image":
            if "ranking_position" not in self.view.config:
                self.view.config["ranking_position"] = {}
            self.view.config["ranking_position"]["background_image"] = url

        self.view.save_config()
        await self.view.generate_preview_image(interaction.user)

        # Update view
        self.view.update_buttons()

        # Get appropriate embed
        if self.view.mode == "username_image":
            embed = self.view.get_username_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Username Image"
            embed.description = "Set a custom username image overlay"
        elif self.view.mode == "xp_info_image":
            embed = self.view.get_xp_info_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> XP Info Image"
            embed.description = "Set a custom XP text image overlay"
        elif self.view.mode == "xp_progress_image":
            embed = self.view.get_xp_progress_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> XP Progress Image"
            embed.description = "Set a custom XP progress image overlay"
        elif self.view.mode == "level_text_image":
            embed = self.view.get_level_text_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Level Text Image"
            embed.description = "Set a custom level text image overlay"
        elif self.view.mode == "ranking_text_image":
            embed = self.view.get_ranking_text_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Ranking Text Image"
            embed.description = "Set a custom ranking text image overlay"

        await interaction.edit_original_response(embed=embed, view=self.view)

class LevelCardRGBColorModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='RGB Color')
        self.view = view

        # Get current color values
        current_r, current_g, current_b = "255", "255", "255"
        if self.view.mode == "xp_info_color" and self.view.config.get("xp_text_color"):
            rgb = self.view.config["xp_text_color"]
            current_r, current_g, current_b = str(rgb[0]), str(rgb[1]), str(rgb[2])
        elif self.view.mode == "xp_progress_color" and self.view.config.get("xp_bar_color"):
            rgb = self.view.config["xp_bar_color"]
            current_r, current_g, current_b = str(rgb[0]), str(rgb[1]), str(rgb[2])
        elif self.view.mode == "background_color" and self.view.config.get("background_color"):
            rgb = self.view.config["background_color"]
            current_r, current_g, current_b = str(rgb[0]), str(rgb[1]), str(rgb[2])
        elif self.view.mode == "username_color" and self.view.config.get("username_color"):
            rgb = self.view.config["username_color"]
            current_r, current_g, current_b = str(rgb[0]), str(rgb[1]), str(rgb[2])
        elif self.view.mode == "profile_outline_color":
            profile_config = self.view.config.get("profile_outline", {})
            if profile_config.get("color_override"):
                rgb = profile_config["color_override"]
                current_r, current_g, current_b = str(rgb[0]), str(rgb[1]), str(rgb[2])
        elif self.view.mode == "level_text_color" and self.view.config.get("level_color"):
            rgb = self.view.config["level_color"]
            current_r, current_g, current_b = str(rgb[0]), str(rgb[1]), str(rgb[2])
        elif self.view.mode == "ranking_text_color":
            ranking_config = self.view.config.get("ranking_position", {})
            if ranking_config.get("color"):
                rgb = ranking_config["color"]
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

            if self.view.mode == "xp_info_color":
                self.view.config["xp_text_color"] = [r, g, b]
            elif self.view.mode == "xp_progress_color":
                self.view.config["xp_bar_color"] = [r, g, b]
            elif self.view.mode == "background_color":
                self.view.config["background_color"] = [r, g, b]
                self.view.config.pop("background_image", None)
            elif self.view.mode == "username_color":
                self.view.config["username_color"] = [r, g, b]
            elif self.view.mode == "profile_outline_color":
                if "profile_outline" not in self.view.config:
                    self.view.config["profile_outline"] = {}
                self.view.config["profile_outline"]["color_override"] = [r, g, b]
                self.view.config["profile_outline"].pop("custom_image", None)
            elif self.view.mode == "level_text_color":
                self.view.config["level_color"] = [r, g, b]
            elif self.view.mode == "ranking_text_color":
                if "ranking_position" not in self.view.config:
                    self.view.config["ranking_position"] = {}
                self.view.config["ranking_position"]["color"] = [r, g, b]

            self.view.save_config()
            await self.view.generate_preview_image(interaction.user)

            # Return to appropriate embed
            if self.view.mode == "xp_info_color":
                embed = self.view.get_xp_info_embed()
                embed.title = "<:ColorLOGO:1408828590241615883> XP Info Color"
                embed.description = "Choose how to set your XP text color"
            elif self.view.mode == "xp_progress_color":
                embed = self.view.get_xp_progress_embed()
                embed.title = "<:ColorLOGO:1408828590241615883> XP Progress Color"
                embed.description = "Choose how to set your XP progress bar color"
            elif self.view.mode == "background_color":
                embed = self.view.get_background_embed()
                embed.title = "<:ColorLOGO:1408828590241615883> Background Color"
                embed.description = "Choose how to set your background color"
            elif self.view.mode == "username_color":
                embed = self.view.get_username_embed()
                embed.title = "<:ColorLOGO:1408828590241615883> Username Color"
                embed.description = "Choose how to set your username color"
            elif self.view.mode == "profile_outline_color":
                embed = self.view.get_profile_outline_embed()
                embed.title = "<:ColorLOGO:1408828590241615883> Profile Outline Color"
                embed.description = "Choose how to set your profile outline color"

            self.view.update_buttons()
            await interaction.edit_original_response(embed=embed, view=self.view)
        except ValueError:
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid RGB Values",
                description="Please enter valid RGB values (0-255 for each color)",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

class LevelCardImageURLModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='Image URL')
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

        if self.view.mode == "xp_bar_image":
            self.view.config["level_bar_image"] = url
        elif self.view.mode == "background_image":
            self.view.config["background_image"] = url
            self.view.config.pop("background_color", None)
        elif self.view.mode == "profile_outline_image":
            if "profile_outline" not in self.view.config:
                self.view.config["profile_outline"] = {}
            self.view.config["profile_outline"]["custom_image"] = url
            self.view.config["profile_outline"].pop("color_override", None)
        elif self.view.mode == "username_image":
            self.view.config["username_image"] = url
        elif self.view.mode == "xp_info_image":
            self.view.config["xp_info_image"] = url
        elif self.view.mode == "xp_progress_image":
            self.view.config["xp_progress_image"] = url
        elif self.view.mode == "level_text_image":
            self.view.config["level_text_image"] = url
        elif self.view.mode == "ranking_text_image":
            if "ranking_position" not in self.view.config:
                self.view.config["ranking_position"] = {}
            self.view.config["ranking_position"]["background_image"] = url

        self.view.save_config()
        await self.view.generate_preview_image(interaction.user)

        # Return to appropriate embed
        if self.view.mode == "xp_bar_image":
            embed = self.view.get_xp_bar_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> XP Bar Image"
            embed.description = "Set a custom XP bar image"
        elif self.view.mode == "background_image":
            embed = self.view.get_background_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Background Image"
            embed.description = "Set a custom background image"
        elif self.view.mode == "profile_outline_image":
            embed = self.view.get_profile_outline_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Profile Outline Image"
            embed.description = "Set a custom profile outline image"
        elif self.view.mode == "username_image":
            embed = self.view.get_username_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Username Image"
            embed.description = "Set a custom username image overlay"
        elif self.view.mode == "xp_info_image":
            embed = self.view.get_xp_info_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> XP Info Image"
            embed.description = "Set a custom XP text image overlay"
        elif self.view.mode == "xp_progress_image":
            embed = self.view.get_xp_progress_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> XP Progress Image"
            embed.description = "Set a custom XP progress image overlay"
        elif self.view.mode == "level_text_image":
            embed = self.view.get_level_text_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Level Text Image"
            embed.description = "Set a custom level text image overlay"
        elif self.view.mode == "ranking_text_image":
            embed = self.view.get_ranking_text_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Ranking Text Image"
            embed.description = "Set a custom ranking text image overlay"

        self.view.update_buttons()
        await interaction.edit_original_response(embed=embed, view=self.view)

class CustomizationCategoryView(discord.ui.View):
    def __init__(self, bot, user, category):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user
        self.category = category

    def get_embed(self):
        data = load_leveling_data()
        permissions = data["leveling_settings"].get("customization_permissions", {})
        category_config = permissions.get(self.category, {})

        category_display = {
            "background": "Background",
            "avatar_outline": "Avatar Outline", 
            "username": "Username",
            "bar_progress": "Bar Progress",
            "content": "Content"
        }

        embed = discord.Embed(
            title=f"<:SettingLOGO:1407071854593839239> {category_display.get(self.category, self.category.title())} Permissions",
            description=f"Manage {category_display.get(self.category, self.category)} customization permissions:",
            color=0xFFFFFF
        )

        enabled = category_config.get("enabled", True)
        status = "<:OnLOGO:1407072463883472978> Enabled" if enabled else "<:OffLOGO:1407072621836894380> Disabled"
        embed.add_field(name="Status", value=status, inline=True)

        if "image_permission_level" in category_config:
            embed.add_field(
                name="Image Permission Level", 
                value=f"Level {category_config.get('image_permission_level', 0)}", 
                inline=True
            )

        if "color_permission_level" in category_config:
            embed.add_field(
                name="Color Permission Level", 
                value=f"Level {category_config.get('color_permission_level', 0)}", 
                inline=True
            )

        return embed

    @discord.ui.button(label="Set Level", style=discord.ButtonStyle.primary, emoji="<a:XPLOGO:1409634015043915827>")
    async def set_level(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomizationLevelModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="ON", style=discord.ButtonStyle.success, emoji="<:OnLOGO:1407072463883472978>")
    async def toggle_enabled(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_leveling_data()
        permissions = data["leveling_settings"].get("customization_permissions", {})

        if self.category not in permissions:
            permissions[self.category] = {"enabled": True}

        current_state = permissions[self.category].get("enabled", True)
        permissions[self.category]["enabled"] = not current_state

        data["leveling_settings"]["customization_permissions"] = permissions
        save_leveling_data(data)

        # Update button appearance
        if permissions[self.category]["enabled"]:
            button.label = "ON"
            button.style = discord.ButtonStyle.success
            button.emoji = "<:OnLOGO:1407072463883472978>"
        else:
            button.label = "OFF"
            button.style = discord.ButtonStyle.danger
            button.emoji = "<:OffLOGO:1407072621836894380>"

        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CustomRewardsView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class CustomizationLevelModal(discord.ui.Modal):
    def __init__(self, parent_view):
        super().__init__(title="Set Permission Levels")
        self.parent_view = parent_view

        data = load_leveling_data()
        permissions = data["leveling_settings"].get("customization_permissions", {})
        category_config = permissions.get(self.parent_view.category, {})

        if self.parent_view.category in ["background", "avatar_outline"]:
            self.image_level = discord.ui.TextInput(
                label="Image Permission Level",
                placeholder=f"Textured {self.parent_view.category.replace('_', ' ').title()} Permission",
                default=str(category_config.get("image_permission_level", 0)),
                min_length=1,
                max_length=3
            )
            self.add_item(self.image_level)

        self.color_level = discord.ui.TextInput(
            label="Color Permission Level",
            placeholder=f"Coloured {self.parent_view.category.replace('_', ' ').title()} Permission",
            default=str(category_config.get("color_permission_level", 0)),
            min_length=1,
            max_length=3
        )
        self.add_item(self.color_level)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            data = load_leveling_data()
            permissions = data["leveling_settings"].get("customization_permissions", {})

            if self.parent_view.category not in permissions:
                permissions[self.parent_view.category] = {"enabled": True}

            if hasattr(self, 'image_level'):
                image_level_value = int(self.image_level.value)
                if image_level_value >= 0:
                    permissions[self.parent_view.category]["image_permission_level"] = image_level_value
                else:
                    await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Level must be 0 or higher!", ephemeral=True)
                    return

            color_level_value = int(self.color_level.value)
            if color_level_value >= 0:
                permissions[self.parent_view.category]["color_permission_level"] = color_level_value
            else:
                await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Level must be 0 or higher!", ephemeral=True)
                return

            data["leveling_settings"]["customization_permissions"] = permissions
            save_leveling_data(data)

            embed = self.parent_view.get_embed()
            await interaction.response.edit_message(embed=embed, view=self.parent_view)

        except ValueError:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Please enter valid numbers!", ephemeral=True)

# Custom Rewards System Classes
class CustomMessageXPView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user

    def get_embed(self):
        data = load_leveling_data()
        msg_settings = data["leveling_settings"]["xp_settings"]["messages"]

        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Custom Message XP Settings",
            description="Advanced message XP configuration with custom parameters:",
            color=0xFFFFFF
        )

        embed.add_field(name="XP per Message", value=str(msg_settings["xp_per_message"]), inline=True)
        embed.add_field(name="Cooldown (seconds)", value=str(msg_settings["cooldown"]), inline=True)
        status = "<:OnLOGO:1407072463883472978> Enabled" if msg_settings["enabled"] else "<:OffLOGO:1407072621836894380> Disabled"
        embed.add_field(name="Status", value=status, inline=True)

        return embed

    @discord.ui.button(label="XP Amount", style=discord.ButtonStyle.primary, emoji="<a:XPLOGO:1409634015043915827>")
    async def set_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomMessageXPModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cooldown", style=discord.ButtonStyle.secondary, emoji="<:CooldownLOGO:1409586926071054448>")
    async def set_cooldown(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomMessageCooldownModal()
        await interaction.response.send_modal(modal)

        # Bouton 3 - Customization Permission Toggle
        @discord.ui.button(label="OFF", style=discord.ButtonStyle.danger, emoji="<:OffLOGO:1407072621836894380>")
        async def toggle_customization_permission(self, interaction: discord.Interaction, button: discord.ui.Button):
            data = load_leveling_data()
            permissions = data["leveling_settings"].get("customization_permissions", {})

            if self.category not in permissions:
                permissions[self.category] = {"enabled": True}
            current_state = permissions[self.category].get("enabled", True)
            permissions[self.category]["enabled"] = not current_state
            data["leveling_settings"]["customization_permissions"] = permissions
            save_leveling_data(data)
            # Update button appearance
            if permissions[self.category]["enabled"]:
                button.label = "ON"
                button.style = discord.ButtonStyle.success
                button.emoji = "<:OnLOGO:1407072463883472978>"
            else:
                button.label = "OFF"
                button.style = discord.ButtonStyle.danger
                button.emoji = "<:OffLOGO:1407072621836894380>"
            embed = self.get_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CustomRewardsView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class CustomCharacterXPView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user

    def get_embed(self):
        data = load_leveling_data()
        char_settings = data["leveling_settings"]["xp_settings"]["characters"]

        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Custom Character XP Settings",
            description="Advanced character XP configuration with limits and cooldowns:",
            color=0xFFFFFF
        )

        embed.add_field(name="XP per Character", value=str(char_settings["xp_per_character"]), inline=True)
        embed.add_field(name="Character Limit", value=str(char_settings["character_limit"]), inline=True)
        embed.add_field(name="Cooldown (seconds)", value=str(char_settings["cooldown"]), inline=True)
        status = "<:OnLOGO:1407072463883472978> Enabled" if char_settings["enabled"] else "<:OffLOGO:1407072621836894380> Disabled"
        embed.add_field(name="Status", value=status, inline=True)

        return embed

    @discord.ui.button(label="XP Amount", style=discord.ButtonStyle.primary, emoji="<a:XPLOGO:1409634015043915827>")
    async def set_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomCharacterXPModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Character Limit", style=discord.ButtonStyle.secondary, emoji="<:LimitLOGO:1409636533618610266>")
    async def set_limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomCharacterLimitModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cooldown", style=discord.ButtonStyle.secondary, emoji="<:CooldownLOGO:1409586926071054448>")
    async def set_cooldown(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomCharacterCooldownModal()
        await interaction.response.send_modal(modal)

        # Bouton 4 - Profile Outline Toggle
        @discord.ui.button(label="OFF", style=discord.ButtonStyle.danger, emoji="<:OffLOGO:1407072621836894380>")
        async def toggle_profile_outline(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()
            if "profile_outline" not in self.config:
                self.config["profile_outline"] = {}
            current_state = self.config["profile_outline"].get("enabled", True)
            self.config["profile_outline"]["enabled"] = not current_state
            self.save_config()
            # Update button appearance
            if self.config["profile_outline"]["enabled"]:
                button.label = "ON"
                button.style = discord.ButtonStyle.success
                button.emoji = "<:OnLOGO:1407072463883472978>"
            else:
                button.label = "OFF"
                button.style = discord.ButtonStyle.danger
                button.emoji = "<:OffLOGO:1407072621836894380>"
            await self.generate_preview_image(interaction.user)
            embed = self.get_profile_outline_embed()
            self.update_buttons()
            await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CustomRewardsView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class CooldownSettingsView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user

    def get_embed(self):
        data = load_leveling_data()
        msg_cooldown = data["leveling_settings"]["xp_settings"]["messages"]["cooldown"]
        char_cooldown = data["leveling_settings"]["xp_settings"]["characters"]["cooldown"]

        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Cooldown Settings",
            description="Manage all cooldown settings in one place:",
            color=0xFFFFFF
        )

        embed.add_field(name="<:MessagesLOGO:1409586848577093837> Message Cooldown", value=f"{msg_cooldown} seconds", inline=True)
        embed.add_field(name="<:DescriptionLOGO:1407733417172533299> Character Cooldown", value=f"{char_cooldown} seconds", inline=True)

        return embed

    @discord.ui.button(label="Message Cooldown", style=discord.ButtonStyle.primary, emoji="<:MessagesLOGO:1409586848577093837>")
    async def message_cooldown(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MessageCooldownModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Character Cooldown", style=discord.ButtonStyle.secondary, emoji="<:DescriptionLOGO:1407733417172533299>")
    async def character_cooldown(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CharacterCooldownModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Reset All", style=discord.ButtonStyle.danger, emoji="<:UpdateLOGO:1407072818214080695>")
    async def reset_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_leveling_data()
        data["leveling_settings"]["xp_settings"]["messages"]["cooldown"] = 10
        data["leveling_settings"]["xp_settings"]["characters"]["cooldown"] = 10
        save_leveling_data(data)

        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = XPSettingsView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class AddCustomRewardView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user
        self.reward_name = None
        self.reward_level = None
        self.reward_description = None

class EditCustomRewardView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user

        # Add dropdown in first row
        select = EditCustomRewardSelect()
        select.row = 0
        self.add_item(select)

    def get_embed(self):
        embed = discord.Embed(
            title="<:EditLOGO:1407071307022995508> Edit Custom Reward",
            description="Select a custom reward to edit:",
            color=0xFFFFFF
        )
        return embed

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>", row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CustomRewardsView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class RemoveCustomRewardView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user

        # Add dropdown in first row
        select = RemoveCustomRewardSelect()
        select.row = 0
        self.add_item(select)

    def get_embed(self):
        embed = discord.Embed(
            title="<:DeleteLOGO:1407071421363916841> Remove Custom Reward",
            description="Select a custom reward to remove:",
            color=0xff0000
        )
        return embed

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>", row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CustomRewardsView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

# Custom Reward Select Menus
class EditCustomRewardSelect(discord.ui.Select):
    def __init__(self):
        data = load_leveling_data()
        custom_rewards = data["leveling_settings"]["rewards"]["custom"]

        options = []
        for reward_id, reward_data in custom_rewards.items():
            options.append(discord.SelectOption(
                label=reward_data.get('name', f'Custom Reward {reward_id}'),
                description=f"Level {reward_data.get('level', 0)}",
                value=reward_id
            ))

        if not options:
            options.append(discord.SelectOption(label="No rewards", description="No rewards to edit", value="none"))

        super().__init__(placeholder="Select a reward to edit...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            return

        await interaction.response.send_message("Edit functionality for custom rewards coming soon!", ephemeral=True)

class RemoveCustomRewardSelect(discord.ui.Select):
    def __init__(self):
        data = load_leveling_data()
        custom_rewards = data["leveling_settings"]["rewards"]["custom"]

        options = []
        for reward_id, reward_data in custom_rewards.items():
            options.append(discord.SelectOption(
                label=reward_data.get('name', f'Custom Reward {reward_id}'),
                description=f"Level {reward_data.get('level', 0)}",
                value=reward_id
            ))

        if not options:
            options.append(discord.SelectOption(label="No rewards", description="No rewards to remove", value="none"))

        super().__init__(placeholder="Select a reward to remove...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            return

        # Show confirmation
        embed = discord.Embed(
            title="<:WarningLOGO:1407072569487659198> Confirm Removal",
            description="This action is irreversible! Are you sure you want to remove this custom reward?",
            color=0xff0000
        )
        view = ConfirmRemoveCustomView(self.values[0])
        await interaction.response.edit_message(embed=embed, view=view)

class ConfirmRemoveCustomView(discord.ui.View):
    def __init__(self, reward_id):
        super().__init__(timeout=300)
        self.reward_id = reward_id

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, emoji="<:ConfirmLOGO:1407072680267481249>")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_leveling_data()
        if self.reward_id in data["leveling_settings"]["rewards"]["custom"]:
            del data["leveling_settings"]["rewards"]["custom"][self.reward_id]
            save_leveling_data(data)

        embed = discord.Embed(
            title="<:SucessLOGO:1407071637840592977> Custom Reward Removed",
            description="The custom reward has been successfully removed!",
            color=0x00ff00
        )
        view = CustomRewardsView(self.bot, interaction.user)
        await interaction.response.edit_message(embed=embed, view=view)

# Custom Modals
class CustomMessageXPModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Set Custom Message XP")

    xp = discord.ui.TextInput(
        label="XP per Message",
        placeholder="Enter XP amount (minimum 0)...",
        min_length=1,
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            xp_value = int(self.xp.value)
            if xp_value >= 0:
                data = load_leveling_data()
                data["leveling_settings"]["xp_settings"]["messages"]["xp_per_message"] = xp_value
                save_leveling_data(data)
                await interaction.response.send_message(f"<:SucessLOGO:1407071637840592977> Custom message XP set to {xp_value}!", ephemeral=True)
            else:
                await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> XP must be 0 or higher!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Please enter a valid number!", ephemeral=True)

class CustomMessageCooldownModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Set Custom Message Cooldown")

    cooldown = discord.ui.TextInput(
        label="Cooldown (seconds)",
        placeholder="Enter cooldown in seconds...",
        min_length=1,
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            cooldown_value = int(self.cooldown.value)
            if cooldown_value >= 0:
                data = load_leveling_data()
                data["leveling_settings"]["xp_settings"]["messages"]["cooldown"] = cooldown_value
                save_leveling_data(data)
                await interaction.response.send_message(f"<:SucessLOGO:1407071637840592977> Custom message cooldown set to {cooldown_value} seconds!", ephemeral=True)
            else:
                await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Cooldown must be 0 or higher!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Please enter a valid number!", ephemeral=True)

class CustomCharacterXPModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Set Custom Character XP")

    xp = discord.ui.TextInput(
        label="XP per Character",
        placeholder="Enter XP amount per character...",
        min_length=1,
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            xp_value = int(self.xp.value)
            if xp_value >= 0:
                data = load_leveling_data()
                data["leveling_settings"]["xp_settings"]["characters"]["xp_per_character"] = xp_value
                save_leveling_data(data)
                await interaction.response.send_message(f"<:SucessLOGO:1407071637840592977> Custom character XP set to {xp_value}!", ephemeral=True)
            else:
                await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> XP must be 0 or higher!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Please enter a valid number!", ephemeral=True)

class CustomCharacterLimitModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Set Custom Character Limit")

    limit = discord.ui.TextInput(
        label="Character Limit",
        placeholder="Maximum characters before cooldown...",
        min_length=1,
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            limit_value = int(self.limit.value)
            if limit_value >= 0:
                data = load_leveling_data()
                data["leveling_settings"]["xp_settings"]["characters"]["character_limit"] = limit_value
                save_leveling_data(data)
                await interaction.response.send_message(f"<:SucessLOGO:1407071637840592977> Custom character limit set to {limit_value}!", ephemeral=True)
            else:
                await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Limit must be 0 or higher!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Please enter a valid number!", ephemeral=True)

class CustomCharacterCooldownModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Set Custom Character Cooldown")

    cooldown = discord.ui.TextInput(
        label="Cooldown (seconds)",
        placeholder="Cooldown duration in seconds...",
        min_length=1,
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            cooldown_value = int(self.cooldown.value)
            if cooldown_value >= 0:
                data = load_leveling_data()
                data["leveling_settings"]["xp_settings"]["characters"]["cooldown"] = cooldown_value
                save_leveling_data(data)
                await interaction.response.send_message(f"<:SucessLOGO:1407071637840592977> Custom character cooldown set to {cooldown_value} seconds!", ephemeral=True)
            else:
                await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Cooldown must be 0 or higher!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Please enter a valid number!", ephemeral=True)

class CustomRewardNameModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title="Set Reward Name")
        self.view = view

    name = discord.ui.TextInput(
        label="Reward Name",
        placeholder="Enter a name for this reward...",
        min_length=1,
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        self.view.reward_name = self.name.value
        embed = self.view.get_embed()
        await interaction.response.edit_message(embed=embed, view=self.view)

class CustomRewardLevelModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title="Set Required Level")
        self.view = view

    level = discord.ui.TextInput(
        label="Required Level (1-100)",
        placeholder="Enter the level required for this reward...",
        min_length=1,
        max_length=3
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            level_value = int(self.level.value)
            if 1 <= level_value <= 100:
                self.view.reward_level = level_value
                embed = self.view.get_embed()
                await interaction.response.edit_message(embed=embed, view=self.view)
            else:
                await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Level must be between 1 and 100!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Please enter a valid number!", ephemeral=True)

class CustomRewardDescriptionModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title="Set Reward Description")
        self.view = view

    description = discord.ui.TextInput(
        label="Description",
        placeholder="Describe what this reward does...",
        style=discord.TextStyle.paragraph,
        min_length=1,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        self.view.reward_description = self.description.value
        embed = self.view.get_embed()
        await interaction.response.edit_message(embed=embed, view=self.view)

class LevelCardSettingsButtonView(discord.ui.View):
    def __init__(self, card_owner):
        super().__init__(timeout=300)
        self.card_owner = card_owner

    @discord.ui.button(label="Settings", style=discord.ButtonStyle.secondary, emoji="<:SettingLOGO:1407071854593839239>")
    async def settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only the card owner can click the settings button
        if interaction.user.id != self.card_owner.id:
            await interaction.response.send_message(
                "<:ErrorLOGO:1407071682031648850> You can only access settings for your own level card!",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Create user-specific level card manager
            view = UserLevelCardManagerView(interaction.client, interaction.user.id)
            view.guild = interaction.guild

            # Generate preview image
            await view.generate_preview_image(interaction.user)

            embed = view.get_main_embed()
            view.update_buttons()

            # Send DM to user
            await interaction.user.send(embed=embed, view=view)
            await interaction.followup.send(
                "<:SucessLOGO:1407071637840592977> Level card settings sent to your DMs!",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "<:ErrorLOGO:1407071682031648850> I couldn't send you a DM. Please check your privacy settings and try again.",
                ephemeral=True
            )
        except Exception as e:
            print(f"Error sending DM: {e}")
            await interaction.followup.send(
                "<:ErrorLOGO:1407071682031648850> An error occurred while sending the settings to your DMs.",
                ephemeral=True
            )

class UserLevelCardManagerView(LevelCardManagerView):
    def __init__(self, bot, user_id):
        super().__init__(bot, user_id)

    def update_buttons(self):
        """Override to add close button for DM version"""
        super().update_buttons()

        # Add close button for DM version
        if self.mode == "main":
            close_button = discord.ui.Button(
                label="Close",
                style=discord.ButtonStyle.danger,
                emoji="<:CloseLOGO:1407072519420248256>",
                row=1
            )
            close_button.callback = self.close_dm
            self.add_item(close_button)

    async def close_dm(self, interaction: discord.Interaction):
        """Close the DM message"""
        try:
            await interaction.message.delete()
        except:
            # If we can't delete the message, just respond with an ephemeral message
            await interaction.response.send_message("Settings closed.", ephemeral=True)

    def check_permission(self, category, permission_type):
        """Check if user has permission for specific customization"""
        data = load_leveling_data()
        user_data = data["user_data"].get(str(self.user_id), {"level": 1})
        permissions = data["leveling_settings"].get("customization_permissions", {})

        category_config = permissions.get(category, {"enabled": True})

        # If category is disabled, no one can use it
        if not category_config.get("enabled", True):
            return False

        # Check specific permission level
        required_level = category_config.get(f"{permission_type}_permission_level", 0)
        user_level = user_data.get("level", 1)

        return user_level >= required_level

    def update_buttons(self):
        """Use exact same interface as LevelCardManagerView but with permission checks"""
        # Call parent's update_buttons method to get the exact same interface
        super().update_buttons()

        # Now disable buttons based on permissions for DM users
        for item in self.children:
            if hasattr(item, 'disabled') and hasattr(item, 'label'):
                # Check permissions for each button
                if item.label == "Leveling Bar":
                    item.disabled = not (self.has_permission_for_feature("bar_progress", "color") or 
                                       self.has_permission_for_feature("content", "color"))
                elif item.label == "Background":
                    item.disabled = not (self.has_permission_for_feature("background", "color") or 
                                       self.has_permission_for_feature("background", "image"))
                elif item.label == "Username":
                    item.disabled = not self.has_permission_for_feature("username", "color")
                elif item.label == "Profile Outline":
                    item.disabled = not (self.has_permission_for_feature("profile_outline", "color") or 
                                       self.has_permission_for_feature("profile_outline", "image"))
                elif item.label == "Content":
                    item.disabled = not self.has_permission_for_feature("content", "color")
                elif item.label == "XP Info":
                    # XP Info est désactivé si l'utilisateur n'a pas accès au contenu OU à la barre de progression
                    item.disabled = not (self.has_permission_for_feature("content", "color") and 
                                        self.has_permission_for_feature("bar_progress", "color"))
                elif item.label == "XP Bar":
                    item.disabled = not self.has_permission_for_feature("bar_progress", "color")
                elif item.label == "XP Progress":
                    item.disabled = not self.has_permission_for_feature("bar_progress", "color")
                elif item.label == "Level":
                    # Level est dans Content mais affiché via Leveling Bar, donc vérifier les deux
                    item.disabled = not (self.has_permission_for_feature("content", "color") and 
                                        self.has_permission_for_feature("bar_progress", "color"))
                elif item.label == "Classement":
                    item.disabled = not self.has_permission_for_feature("content", "color")
                elif item.label == "Color":
                    # Get feature type from current mode
                    feature_type = self.mode
                    if self.mode == "background":
                        item.disabled = not self.has_permission_for_feature("background", "color")
                    elif self.mode == "username":
                        item.disabled = not self.has_permission_for_feature("username", "color")
                    elif self.mode == "profile_outline":
                        item.disabled = not self.has_permission_for_feature("profile_outline", "color")
                    elif self.mode in ["xp_info", "xp_progress", "level_text", "ranking_text"]:
                        if self.mode in ["xp_info", "level_text", "ranking_text"]:
                            item.disabled = not self.has_permission_for_feature("content", "color")
                        else:
                            item.disabled = not self.has_permission_for_feature("bar_progress", "color")
                elif item.label == "Image":
                    # Get feature type from current mode
                    if self.mode == "background":
                        item.disabled = not self.has_permission_for_feature("background", "image")
                    elif self.mode == "profile_outline":
                        item.disabled = not self.has_permission_for_feature("profile_outline", "image")
                    elif self.mode in ["level_text", "ranking_text"]:
                        item.disabled = not self.has_permission_for_feature("content", "image")
                elif item.label == "Set URL":
                    # Check image permission for current mode
                    if "background" in self.mode:
                        item.disabled = not self.has_permission_for_feature("background", "image")
                    elif "profile_outline" in self.mode:
                        item.disabled = not self.has_permission_for_feature("profile_outline", "image")
                    elif any(x in self.mode for x in ["level_text", "ranking_text", "username", "xp_info", "xp_progress"]):
                        if "username" in self.mode:
                            item.disabled = not self.has_permission_for_feature("username", "image")
                        elif any(x in self.mode for x in ["level_text", "ranking_text", "xp_info"]):
                            item.disabled = not self.has_permission_for_feature("content", "image")
                        elif "xp_progress" in self.mode:
                            item.disabled = not self.has_permission_for_feature("bar_progress", "image")
                elif item.label == "Upload Image":
                    # Same logic as Set URL
                    if "background" in self.mode:
                        item.disabled = not self.has_permission_for_feature("background", "image")
                    elif "profile_outline" in self.mode:
                        item.disabled = not self.has_permission_for_feature("profile_outline", "image")
                    elif any(x in self.mode for x in ["level_text", "ranking_text", "username", "xp_info", "xp_progress"]):
                        if "username" in self.mode:
                            item.disabled = not self.has_permission_for_feature("username", "image")
                        elif any(x in self.mode for x in ["level_text", "ranking_text", "xp_info"]):
                            item.disabled = not self.has_permission_for_feature("content", "image")
                        elif "xp_progress" in self.mode:
                            item.disabled = not self.has_permission_for_feature("bar_progress", "image")
                elif item.label == "Clear Image":
                    # Same logic as Set URL and Upload Image
                    if "background" in self.mode:
                        item.disabled = not self.has_permission_for_feature("background", "image")
                    elif "profile_outline" in self.mode:
                        item.disabled = not self.has_permission_for_feature("profile_outline", "image")
                    elif any(x in self.mode for x in ["level_text", "ranking_text", "username", "xp_info", "xp_progress"]):
                        if "username" in self.mode:
                            item.disabled = not self.has_permission_for_feature("username", "image")
                        elif any(x in self.mode for x in ["level_text", "ranking_text", "xp_info"]):
                            item.disabled = not self.has_permission_for_feature("content", "image")
                        elif "xp_progress" in self.mode:
                            item.disabled = not self.has_permission_for_feature("bar_progress", "image")
                elif item.label == "Hex Code":
                    # Check color permission for current mode
                    if "background" in self.mode:
                        item.disabled = not self.has_permission_for_feature("background", "color")
                    elif "username" in self.mode:
                        item.disabled = not self.has_permission_for_feature("username", "color")
                    elif "profile_outline" in self.mode:
                        item.disabled = not self.has_permission_for_feature("profile_outline", "color")
                    elif any(x in self.mode for x in ["xp_info", "level_text", "ranking_text"]):
                        item.disabled = not self.has_permission_for_feature("content", "color")
                    elif "xp_progress" in self.mode:
                        item.disabled = not self.has_permission_for_feature("bar_progress", "color")
                elif item.label == "RGB Code":
                    # Same logic as Hex Code
                    if "background" in self.mode:
                        item.disabled = not self.has_permission_for_feature("background", "color")
                    elif "username" in self.mode:
                        item.disabled = not self.has_permission_for_feature("username", "color")
                    elif "profile_outline" in self.mode:
                        item.disabled = not self.has_permission_for_feature("profile_outline", "color")
                    elif any(x in self.mode for x in ["xp_info", "level_text", "ranking_text"]):
                        item.disabled = not self.has_permission_for_feature("content", "color")
                    elif "xp_progress" in self.mode:
                        item.disabled = not self.has_permission_for_feature("bar_progress", "color")
                elif item.label == "Reset":
                    # Same logic as Hex Code and RGB Code
                    if "background" in self.mode:
                        item.disabled = not self.has_permission_for_feature("background", "color")
                    elif "username" in self.mode:
                        item.disabled = not self.has_permission_for_feature("username", "color")
                    elif "profile_outline" in self.mode:
                        item.disabled = not self.has_permission_for_feature("profile_outline", "color")
                    elif any(x in self.mode for x in ["xp_info", "level_text", "ranking_text"]):
                        item.disabled = not self.has_permission_for_feature("content", "color")
                    elif "xp_progress" in self.mode:
                        item.disabled = not self.has_permission_for_feature("bar_progress", "color")
                elif item.label in ["ON", "OFF"] and hasattr(item, 'callback') and hasattr(item.callback, '__name__'):
                    # Toggle button for profile outline
                    if item.callback.__name__ == 'toggle_profile_outline':
                        item.disabled = not self.has_permission_for_feature("profile_outline", "color")

async def setup(bot):
    await bot.add_cog(LevelingSystem(bot))

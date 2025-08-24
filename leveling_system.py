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
            "user_data": {}
        }

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

    async def apply_text_image_overlay(self, text_image_url, text_surface, text_pos, font, text_content):
        """Apply image overlay to text using advanced masking technique"""
        try:
            if not text_image_url or text_image_url == "None":
                return text_surface

            # Download overlay image
            overlay_data = await self.download_image(text_image_url)
            if not overlay_data:
                return text_surface

            overlay_img = Image.open(io.BytesIO(overlay_data)).convert("RGBA")

            # Get text dimensions
            bbox = font.getbbox(text_content)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Create a temporary image for text rendering
            temp_img = Image.new('RGBA', (text_width, text_height), (0, 0, 0, 0))
            temp_draw = ImageDraw.Draw(temp_img)

            # Draw white text on transparent background to create mask
            temp_draw.text((0, 0), text_content, font=font, fill=(255, 255, 255, 255))

            # Resize overlay to match text size
            overlay_resized = overlay_img.resize((text_width, text_height), Image.Resampling.LANCZOS)

            # Create final masked overlay
            masked_overlay = Image.new('RGBA', (text_width, text_height), (0, 0, 0, 0))

            # Apply text as mask to overlay
            for x in range(text_width):
                for y in range(text_height):
                    try:
                        text_pixel = temp_img.getpixel((x, y))
                        if text_pixel[3] > 0:  # If text pixel is not transparent
                            overlay_pixel = overlay_resized.getpixel((x, y))
                            # Use text alpha as mask strength
                            alpha = int(text_pixel[3] * (overlay_pixel[3] / 255.0))
                            masked_overlay.putpixel((x, y), (overlay_pixel[0], overlay_pixel[1], overlay_pixel[2], alpha))
                    except IndexError:
                        continue

            # Paste the masked overlay onto the main surface
            text_surface.paste(masked_overlay, text_pos, masked_overlay)

            return text_surface

        except Exception as e:
            print(f"Error applying text image overlay: {e}")
            return text_surface

    async def draw_text_with_overlay(self, draw, surface, text, pos, font, color, overlay_url=None):
        """Draw text with optional image overlay"""
        if overlay_url and overlay_url != "None":
            # Apply image overlay
            await self.apply_text_image_overlay(overlay_url, surface, pos, font, text)
        else:
            # Draw normal colored text
            draw.text(pos, text, font=font, fill=tuple(color))

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
            config = data["leveling_settings"]["level_card"]

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

                            # Calculate aspect ratios
                            original_ratio = frame.width / frame.height
                            target_ratio = bg_width / bg_height

                            if original_ratio > target_ratio:
                                # Image is wider, crop width
                                new_height = frame.height
                                new_width = int(new_height * target_ratio)
                                left = (frame.width - new_width) // 2
                                cropped = frame.crop((left, 0, left + new_width, new_height))
                            else:
                                # Image is taller, crop height
                                new_width = frame.width
                                new_height = int(new_width / target_ratio)
                                top = (frame.height - new_height) // 2
                                cropped = frame.crop((0, top, new_width, top + new_height))

                            # Resize to final size
                            processed_frame = cropped.resize((bg_width, bg_height), Image.Resampling.LANCZOS)
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

                        # Calculate aspect ratios
                        original_ratio = original_bg.width / original_bg.height
                        target_ratio = bg_width / bg_height

                        if original_ratio > target_ratio:
                            # Image is wider, crop width
                            new_height = original_bg.height
                            new_width = int(new_height * target_ratio)
                            left = (original_bg.width - new_width) // 2
                            cropped = original_bg.crop((left, 0, left + new_width, new_height))
                        else:
                            # Image is taller, crop height
                            new_width = original_bg.width
                            new_height = int(new_width / target_ratio)
                            top = (original_bg.height - new_height) // 2
                            cropped = original_bg.crop((0, top, new_width, top + new_height))

                        # Resize to final size
                        background = cropped.resize((bg_width, bg_height), Image.Resampling.LANCZOS)
                else:
                    # Fallback to background color if image download fails
                    default_bg_color = config.get("background_color", [245, 55, 48]) # Default red as per user request
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
                default_bg_color = config.get("background_color", [245, 55, 48]) # Default red as per user request
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
                    # Use custom position and resize if width/height specified
                    if "width" in xp_bar_config and "height" in xp_bar_config:
                        levelbar = levelbar.resize((xp_bar_config["width"], xp_bar_config["height"]), Image.Resampling.LANCZOS)
                    levelbar_x = xp_bar_config["x"]
                    levelbar_y = xp_bar_config["y"]
                else:
                    # Default positioning
                    levelbar_x = 30
                    levelbar_y = bg_height - levelbar.height - 30

                # Paste the level bar background first
                background.paste(levelbar, (levelbar_x, levelbar_y), levelbar)

                # Create XP progress bar overlay
                xp_needed, current_xp_in_level = get_xp_for_next_level(user_data["xp"])
                if xp_needed > 0:
                    progress = current_xp_in_level / xp_needed
                else:
                    progress = 1.0

                # Create XP progress bar using the specified color
                if progress > 0:
                    xp_bar_color_rgb = config.get("xp_bar_color", [245, 55, 48])
                    xp_bar_color = tuple(xp_bar_color_rgb) + (255,)
                    progress_width = int(levelbar.width * progress)

                    # Create a mask for the progress bar to match the levelbar shape
                    progress_bar = Image.new("RGBA", (progress_width, levelbar.height), xp_bar_color)

                    # Composite the progress bar with the levelbar shape as mask
                    if progress_width > 0:
                        temp_levelbar = levelbar.crop((0, 0, progress_width, levelbar.height))
                        background.paste(progress_bar, (levelbar_x, levelbar_y), temp_levelbar)


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
                    outline_url = profile_outline_config.get("url")
                    if outline_url:
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

            # Calculate dynamic positions based on content
            positions = self.calculate_dynamic_positions(user, user_data, user_ranking, config, bg_width, bg_height)

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

            # Draw username with configurable color or image overlay
            username = user.name
            username_color = config.get("username_color", [255, 255, 255]) # Default white
            username_overlay = config.get("username_text_image")
            await self.draw_text_with_overlay(
                draw, background, username,
                (positions["username"]["x"], positions["username"]["y"]),
                font_username, username_color, username_overlay
            )

            # Draw discriminator next to username
            discriminator_config = config.get("discriminator_position", {})
            if discriminator_config:
                discriminator = f"#{user.discriminator}" if user.discriminator != "0" else f"#{user.id % 10000:04d}"
                discriminator_color = discriminator_config.get("color", [200, 200, 200])
                discriminator_overlay = discriminator_config.get("text_image")

                try:
                    font_discriminator = ImageFont.truetype("PlayPretend.otf", discriminator_config.get("font_size", 50))
                except IOError:
                    try:
                        font_discriminator = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", discriminator_config.get("font_size", 50))
                    except IOError:
                        font_discriminator = ImageFont.load_default()

                await self.draw_text_with_overlay(
                    draw, background, discriminator,
                    (positions["discriminator"]["x"], positions["discriminator"]["y"]),
                    font_discriminator, discriminator_color, discriminator_overlay
                )

            # Draw level with configurable color or image overlay
            level_text = f"LEVEL {user_data['level']}"
            level_color = config.get("level_color", [245, 55, 48]) # Default red
            level_overlay = config.get("level_text_image")
            await self.draw_text_with_overlay(
                draw, background, level_text,
                (positions["level"]["x"], positions["level"]["y"]),
                font_level, level_color, level_overlay
            )

            # Draw ranking position with configurable color or image overlay
            ranking_config = config.get("ranking_position", {})
            if ranking_config:
                ranking_text = f"#{user_ranking}"
                ranking_color = ranking_config.get("color", [255, 255, 255])
                ranking_overlay = ranking_config.get("text_image")

                try:
                    font_ranking = ImageFont.truetype("PlayPretend.otf", ranking_config.get("font_size", 60))
                except IOError:
                    try:
                        font_ranking = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", ranking_config.get("font_size", 60))
                    except IOError:
                        font_ranking = ImageFont.load_default()

                await self.draw_text_with_overlay(
                    draw, background, ranking_text,
                    (positions["ranking"]["x"], positions["ranking"]["y"]),
                    font_ranking, ranking_color, ranking_overlay
                )

            # Draw XP progress text with configurable color or image overlay
            xp_needed, current_xp_in_level = get_xp_for_next_level(user_data["xp"])
            xp_text = f"{current_xp_in_level}/{xp_needed} XP"
            xp_text_color = config.get("xp_text_color", [255, 255, 255])
            xp_text_overlay = config.get("xp_text_image")

            try:
                font_xp = ImageFont.truetype("PlayPretend.otf", config["xp_text_position"]["font_size"])
            except IOError:
                # Fallback vers les polices système
                try:
                    font_xp = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", config["xp_text_position"]["font_size"])
                except IOError:
                    font_xp = ImageFont.load_default()

            # Position XP text using dynamic positions with overlay support
            await self.draw_text_with_overlay(
                draw, background, xp_text,
                (positions["xp_text"]["x"], positions["xp_text"]["y"]),
                font_xp, xp_text_color, xp_text_overlay
            )


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
                            if "profile_outline" not in view.config:
                                view.config["profile_outline"] = {}
                            view.config["profile_outline"]["custom_image"] = local_file
                            view.config["profile_outline"].pop("color_override", None)
                        elif view.current_image_type == "username_text":
                            view.config["username_text_image"] = local_file
                            view.config.pop("username_color", None)
                        elif view.current_image_type == "level_text":
                            view.config["level_text_image"] = local_file
                            view.config.pop("level_color", None)
                        elif view.current_image_type == "ranking_text":
                            if "ranking_position" not in view.config:
                                view.config["ranking_position"] = {}
                            view.config["ranking_position"]["text_image"] = local_file
                            view.config["ranking_position"].pop("color", None)
                        elif view.current_image_type == "xp_text":
                            view.config["xp_text_image"] = local_file
                            view.config.pop("xp_text_color", None)

                        view.save_config()
                        view.waiting_for_image = False

                        # Generate new preview
                        await view.generate_preview_image(message.author)

                        # Update the manager view
                        if view.current_image_type == "xp_bar":
                            view.mode = "xp_bar_image"
                            embed = view.get_xp_bar_embed()
                            embed.title = "<:ImageLOGO:1407072328134951043> XP Bar Image"
                            embed.description = "Set a custom XP bar image"
                        elif view.current_image_type == "background":
                            view.mode = "background_image"
                            embed = view.get_background_embed()
                            embed.title = "<:ImageLOGO:1407072328134951043> Background Image"
                            embed.description = "Set a custom background image"
                        elif view.current_image_type == "profile_outline":
                            view.mode = "profile_outline_image"
                            embed = view.get_profile_outline_embed()
                            embed.title = "<:ImageLOGO:1407072328134951043> Profile Outline Image"
                            embed.description = "Set a custom profile outline image"
                        elif view.current_image_type in ["username_text", "level_text", "ranking_text", "discriminator_text", "xp_text"]:
                            view.mode = "main"
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
            user_data["xp"] += xp_gained
            new_level = get_level_from_xp(user_data["xp"])
            user_data["level"] = new_level

            save_leveling_data(data)

            # Check for role rewards
            if new_level > old_level:
                await self.check_level_rewards(message.author, new_level)

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

                    # Calculate aspect ratios and resize
                    original_ratio = frame.width / frame.height
                    target_ratio = bg_width / bg_height

                    if original_ratio > target_ratio:
                        new_height = frame.height
                        new_width = int(new_height * target_ratio)
                        left = (frame.width - new_width) // 2
                        cropped = frame.crop((left, 0, left + new_width, new_height))
                    else:
                        new_width = frame.width
                        new_height = int(new_width / target_ratio)
                        top = (frame.height - new_height) // 2
                        cropped = frame.crop((0, top, new_width, top + new_height))

                    background = cropped.resize((bg_width, bg_height), Image.Resampling.LANCZOS)
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
        # Check if interaction is still valid
        if interaction.response.is_done():
            return

        try:
            await interaction.response.defer(thinking=True)
        except discord.InteractionResponded:
            return
        except discord.NotFound:
            return
        except Exception as e:
            print(f"Error deferring interaction: {e}")
            return

        view = LevelSystemMainView(self.bot, interaction.user)

        # Generate demo level card
        await self.generate_demo_card_for_main_view(view)

        embed = view.get_main_embed()

        try:
            await interaction.followup.send(embed=embed, view=view)
        except discord.NotFound:
            print("Interaction expired")
        except Exception as e:
            print(f"Error sending followup: {e}")

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

    def get_main_embed(self):
        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Level System Manager",
            description="Manage your server's leveling system",
            color=0x5865F2
        )

        data = load_leveling_data()
        enabled = data["leveling_settings"]["enabled"]
        total_users = len(data["user_data"])

        status = "<:OnLOGO:1407072463883472978> Enabled" if enabled else "<:OffLOGO:1407072621836894380> Disabled"

        embed.add_field(
            name="System Status",
            value=status,
            inline=True
        )

        embed.add_field(
            name="Total Users",
            value=f"{total_users} users",
            inline=True
        )

        # Add demo card if available
        if hasattr(self, 'demo_card_url') and self.demo_card_url:
            embed.set_image(url=self.demo_card_url)

        bot_name = get_bot_name(self.bot)
        embed.set_footer(text=f"{bot_name} | Level System", icon_url=self.bot.user.display_avatar.url)

        return embed

    @discord.ui.button(label="Level Card Design", style=discord.ButtonStyle.primary, emoji="<:ImageLOGO:1407072328134951043>")
    async def level_card_design(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = LevelCardManagerView(interaction.client, interaction.user.id)
        await view.generate_preview_image(interaction.user)
        embed = view.get_main_embed()
        view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="System Settings", style=discord.ButtonStyle.secondary, emoji="<:SettingLOGO:1407071854593839239>")
    async def system_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = LevelSystemSettingsView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="XP Settings", style=discord.ButtonStyle.secondary, emoji="<:XPLOGO:1407072619517534289>")
    async def xp_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = XPSettingsView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class LevelSystemSettingsView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user

    def get_embed(self):
        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> System Settings",
            description="Configure the leveling system behavior",
            color=discord.Color.blue()
        )

        data = load_leveling_data()
        enabled = data["leveling_settings"]["enabled"]

        status = "<:OnLOGO:1407072463883472978> Enabled" if enabled else "<:OffLOGO:1407072621836894380> Disabled"

        embed.add_field(
            name="System Status",
            value=status,
            inline=False
        )

        bot_name = get_bot_name(self.bot)
        embed.set_footer(text=f"{bot_name} | System Settings", icon_url=self.bot.user.display_avatar.url)

        return embed

    @discord.ui.button(label="Toggle System", style=discord.ButtonStyle.primary, emoji="<:OnLOGO:1407072463883472978>")
    async def toggle_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_leveling_data()
        current_enabled = data["leveling_settings"]["enabled"]
        data["leveling_settings"]["enabled"] = not current_enabled
        save_leveling_data(data)

        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1391511633431494666>")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = LevelSystemMainView(self.bot, self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class XPSettingsView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user

    def get_embed(self):
        embed = discord.Embed(
            title="<:XPLOGO:1407072619517534289> XP Settings",
            description="Configure how users gain experience points",
            color=discord.Color.green()
        )

        data = load_leveling_data()
        xp_settings = data["leveling_settings"]["xp_settings"]

        # Message XP
        msg_enabled = xp_settings["messages"]["enabled"]
        msg_xp = xp_settings["messages"]["xp_per_message"]
        msg_cooldown = xp_settings["messages"]["cooldown"]

        # Character XP
        char_enabled = xp_settings["characters"]["enabled"]
        char_xp = xp_settings["characters"]["xp_per_character"]
        char_limit = xp_settings["characters"]["character_limit"]
        char_cooldown = xp_settings["characters"]["cooldown"]

        msg_status = "<:OnLOGO:1407072463883472978> Enabled" if msg_enabled else "<:OffLOGO:1407072621836894380> Disabled"
        char_status = "<:OnLOGO:1407072463883472978> Enabled" if char_enabled else "<:OffLOGO:1407072621836894380> Disabled"

        embed.add_field(
            name="Message XP",
            value=f"{msg_status}\nXP: {msg_xp} per message\nCooldown: {msg_cooldown}s",
            inline=True
        )

        embed.add_field(
            name="Character XP",
            value=f"{char_status}\nXP: {char_xp} per character\nLimit: {char_limit} chars\nCooldown: {char_cooldown}s",
            inline=True
        )

        bot_name = get_bot_name(self.bot)
        embed.set_footer(text=f"{bot_name} | XP Settings", icon_url=self.bot.user.display_avatar.url)

        return embed

    @discord.ui.button(label="Message XP", style=discord.ButtonStyle.primary, emoji="<:MessageLOGO:1407072668213751869>")
    async def message_xp_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MessageXPModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Character XP", style=discord.ButtonStyle.primary, emoji="<:TXTFileLOGO:1407735600752361622>")
    async def character_xp_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CharacterXPModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = LevelSystemMainView(self.bot, self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class MessageXPModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title='Message XP Settings')

        data = load_leveling_data()
        msg_settings = data["leveling_settings"]["xp_settings"]["messages"]

        self.enabled = discord.ui.TextInput(
            label='Enabled (true/false)',
            placeholder='true or false',
            default=str(msg_settings["enabled"]).lower(),
            required=True,
            max_length=5
        )

        self.xp_per_message = discord.ui.TextInput(
            label='XP per Message',
            placeholder='20',
            default=str(msg_settings["xp_per_message"]),
            required=True,
            max_length=5
        )

        self.cooldown = discord.ui.TextInput(
            label='Cooldown (seconds)',
            placeholder='10',
            default=str(msg_settings["cooldown"]),
            required=True,
            max_length=5
        )

        self.add_item(self.enabled)
        self.add_item(self.xp_per_message)
        self.add_item(self.cooldown)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            enabled = self.enabled.value.lower() == 'true'
            xp_per_message = int(self.xp_per_message.value)
            cooldown = int(self.cooldown.value)

            if xp_per_message < 1 or cooldown < 0:
                raise ValueError("Invalid values")

            data = load_leveling_data()
            data["leveling_settings"]["xp_settings"]["messages"] = {
                "enabled": enabled,
                "xp_per_message": xp_per_message,
                "cooldown": cooldown
            }
            save_leveling_data(data)

            await interaction.response.defer()

        except ValueError:
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid Values",
                description="Please enter valid values (XP > 0, cooldown >= 0)",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

class CharacterXPModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title='Character XP Settings')

        data = load_leveling_data()
        char_settings = data["leveling_settings"]["xp_settings"]["characters"]

        self.enabled = discord.ui.TextInput(
            label='Enabled (true/false)',
            placeholder='true or false',
            default=str(char_settings["enabled"]).lower(),
            required=True,
            max_length=5
        )

        self.xp_per_character = discord.ui.TextInput(
            label='XP per Character',
            placeholder='1',
            default=str(char_settings["xp_per_character"]),
            required=True,
            max_length=5
        )

        self.character_limit = discord.ui.TextInput(
            label='Character Limit',
            placeholder='20',
            default=str(char_settings["character_limit"]),
            required=True,
            max_length=5
        )

        self.cooldown = discord.ui.TextInput(
            label='Cooldown (seconds)',
            placeholder='10',
            default=str(char_settings["cooldown"]),
            required=True,
            max_length=5
        )

        self.add_item(self.enabled)
        self.add_item(self.xp_per_character)
        self.add_item(self.character_limit)
        self.add_item(self.cooldown)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            enabled = self.enabled.value.lower() == 'true'
            xp_per_character = int(self.xp_per_character.value)
            character_limit = int(self.character_limit.value)
            cooldown = int(self.cooldown.value)

            if xp_per_character < 1 or character_limit < 1 or cooldown < 0:
                raise ValueError("Invalid values")

            data = load_leveling_data()
            data["leveling_settings"]["xp_settings"]["characters"] = {
                "enabled": enabled,
                "xp_per_character": xp_per_character,
                "character_limit": character_limit,
                "cooldown": cooldown
            }
            save_leveling_data(data)

            await interaction.response.defer()

        except ValueError:
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid Values",
                description="Please enter valid values (all values must be positive)",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

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

        embed.add_field(name="💬 Message Cooldown", value=f"{msg_cooldown} seconds", inline=True)
        embed.add_field(name="<:DescriptionLOGO:1407733417172533299> Character Cooldown", value=f"{char_cooldown} seconds", inline=True)

        return embed

    @discord.ui.button(label="Message Cooldown", style=discord.ButtonStyle.primary, emoji="💬")
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

    def get_embed(self):
        embed = discord.Embed(
            title="<:CreateLOGO:1407071205026168853> Add Custom Reward",
            description="Create a new custom reward:",
            color=0xFFFFFF
        )

        if self.reward_name:
            embed.add_field(name="Reward Name", value=self.reward_name, inline=False)
        if self.reward_level:
            embed.add_field(name="Required Level", value=str(self.reward_level), inline=False)
        if self.reward_description:
            embed.add_field(name="Description", value=self.reward_description, inline=False)

        return embed

    @discord.ui.button(label="Set Name", style=discord.ButtonStyle.primary, emoji="📝")
    async def set_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomRewardNameModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Set Level", style=discord.ButtonStyle.secondary, emoji="📊")
    async def set_level(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomRewardLevelModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Set Description", style=discord.ButtonStyle.secondary, emoji="📄")
    async def set_description(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomRewardDescriptionModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Create Reward", style=discord.ButtonStyle.success, emoji="<:ConfirmLOGO:1407072680267481249>")
    async def create_reward(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not all([self.reward_name, self.reward_level, self.reward_description]):
            await interaction.response.send_message(
                "<:ErrorLOGO:1407071682031648850> Please fill in all fields before creating the reward.",
                ephemeral=True
            )
            return

        data = load_leveling_data()
        reward_id = str(len(data["leveling_settings"]["rewards"]["custom"]) + 1)
        data["leveling_settings"]["rewards"]["custom"][reward_id] = {
            "name": self.reward_name,
            "level": self.reward_level,
            "description": self.reward_description
        }
        save_leveling_data(data)

        embed = discord.Embed(
            title="<:SucessLOGO:1407071637840592977> Custom Reward Created",
            description=f"Custom reward '{self.reward_name}' has been created for level {self.reward_level}!",
            color=0x00ff00
        )
        view = CustomRewardsView(self.bot, self.user)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CustomRewardsView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

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

    @discord.ui.button(label="Settings", style=discord.ButtonStyle.secondary, emoji="⚙️")
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
                emoji="❌",
                row=2
            )
            close_button.callback = self.close_dm
            self.add_item(close_button)

    async def close_dm(self, interaction: discord.Interaction):
        """Close the DM interface"""
        embed = discord.Embed(
            title="<:SucessLOGO:1407071637840592977> Settings Closed",
            description="Level card settings have been closed.",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=None)

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
        """Override to disable buttons based on permissions"""
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
                emoji="ℹ️",
                disabled=not self.check_permission("content", "color")
            )
            xp_info_button.callback = self.xp_info_settings

            xp_bar_button = discord.ui.Button(
                label="XP Bar",
                style=discord.ButtonStyle.secondary,
                emoji="📊",
                disabled=not self.check_permission("bar_progress", "color")
            )
            xp_bar_button.callback = self.xp_bar_settings

            xp_progress_button = discord.ui.Button(
                label="XP Progress",
                style=discord.ButtonStyle.secondary,
                emoji="⚡",
                disabled=not self.check_permission("bar_progress", "color")
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

        elif self.mode in ["xp_info_color", "xp_progress_color", "background_color", "username_color", "profile_outline_color", "level_text_color", "ranking_text_color"]:
            # Color selection buttons
            hex_button = discord.ui.Button(
                label="Hex Code",
                style=discord.ButtonStyle.secondary,
                emoji="<:HEXcodeLOGO:1408833347404304434>"
            )
            hex_button.callback = self.hex_color

            rgb_button = discord.ui.Button(
                label="RGB Code",
                style=discord.ButtonStyle.secondary,
                emoji="<:RGBcodeLOGO:1408831982141575290>"
            )
            rgb_button.callback = self.rgb_color

            reset_button = discord.ui.Button(
                label="Reset",
                style=discord.ButtonStyle.secondary,
                emoji="<:UpdateLOGO:1407072818214080695>"
            )
            reset_button.callback = self.reset_color

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1407071474233114766>"
            )
            back_button.callback = self.back_to_parent

            self.add_item(hex_button)
            self.add_item(rgb_button)
            self.add_item(reset_button)
            self.add_item(back_button)

        elif self.mode in ["xp_bar_image", "background_image", "profile_outline_image", "level_text_image", "ranking_text_image"]:
            # Image selection buttons
            url_button = discord.ui.Button(
                label="Set URL",
                style=discord.ButtonStyle.secondary,
                emoji="<:URLLOGO:1407071963809054931>"
            )
            url_button.callback = self.image_url

            upload_button = discord.ui.Button(
                label="Upload Image",
                style=discord.ButtonStyle.secondary,
                emoji="<:UploadLOGO:1407072005567545478>"
            )
            upload_button.callback = self.upload_image

            clear_button = discord.ui.Button(
                label="Clear Image",
                style=discord.ButtonStyle.secondary,
                emoji="<:DeleteLOGO:1407071421363916841>"
            )
            clear_button.callback = self.clear_image

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1407071474233114766>"
            )
            back_button.callback = self.back_to_parent

            self.add_item(url_button)
            self.add_item(upload_button)
            self.add_item(clear_button)
            self.add_item(back_button)

        elif self.mode in ["xp_info", "xp_progress", "background", "username"]:
            # Sub-category buttons
            color_button = discord.ui.Button(
                label="Color",
                style=discord.ButtonStyle.secondary,
                emoji="<:ColorLOGO:1408828590241615883>",
                disabled=not self.check_permission(
                    "background" if self.mode == "background" else
                    "username" if self.mode == "username" else "content",
                    "color"
                )
            )
            color_button.callback = self.color_settings

            if self.mode in ["background"]:
                image_button = discord.ui.Button(
                    label="Image",
                    style=discord.ButtonStyle.secondary,
                    emoji="<:ImageLOGO:1407072328134951043>",
                    disabled=not self.check_permission("background", "image")
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
            # XP Bar specific buttons
            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1407071474233114766>"
            )
            back_button.callback = self.back_to_parent
            self.add_item(back_button)

        elif self.mode == "profile_outline":
            # Profile outline main buttons
            toggle_button = discord.ui.Button(
                label="ON" if self.config.get("profile_outline", {}).get("enabled", True) else "OFF",
                style=discord.ButtonStyle.success if self.config.get("profile_outline", {}).get("enabled", True) else discord.ButtonStyle.danger,
                emoji="<:OnLOGO:1407072463883472978>" if self.config.get("profile_outline", {}).get("enabled", True) else "<:OffLOGO:1407072621836894380>",
                disabled=not self.check_permission("avatar_outline", "color")
            )
            toggle_button.callback = self.toggle_profile_outline

            color_button = discord.ui.Button(
                label="Color",
                style=discord.ButtonStyle.secondary,
                emoji="<:ColorLOGO:1408828590241615883>",
                disabled=not self.check_permission("avatar_outline", "color")
            )
            color_button.callback = self.color_settings

            image_button = discord.ui.Button(
                label="Image",
                style=discord.ButtonStyle.secondary,
                emoji="<:ImageLOGO:1407072328134951043>",
                disabled=not self.check_permission("avatar_outline", "image")
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
                emoji="📊",
                disabled=not self.check_permission("content", "color")
            )
            level_button.callback = self.level_text_settings

            ranking_button = discord.ui.Button(
                label="Classement",
                style=discord.ButtonStyle.secondary,
                emoji="🏆",
                disabled=not self.check_permission("content", "color")
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
            # Level/Ranking text buttons
            color_button = discord.ui.Button(
                label="Color",
                style=discord.ButtonStyle.secondary,
                emoji="<:ColorLOGO:1408828590241615883>",
                disabled=not self.check_permission("content", "color")
            )
            color_button.callback = self.color_settings

            image_button = discord.ui.Button(
                label="Image",
                style=discord.ButtonStyle.secondary,
                emoji="<:ImageLOGO:1407072328134951043>",
                disabled=not self.check_permission("content", "image")
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
            # Main buttons with permission checks
            leveling_bar_button = discord.ui.Button(
                label="Leveling Bar",
                style=discord.ButtonStyle.secondary,
                emoji="📊",
                row=0,
                disabled=not (self.check_permission("bar_progress", "color") or self.check_permission("content", "color"))
            )
            leveling_bar_button.callback = self.leveling_bar_settings

            background_button = discord.ui.Button(
                label="Background",
                style=discord.ButtonStyle.secondary,
                emoji="<:BackgroundLOGO:1408834163309805579>",
                row=0,
                disabled=not (self.check_permission("background", "color") or self.check_permission("background", "image"))
            )
            background_button.callback = self.background_settings

            username_button = discord.ui.Button(
                label="Username",
                style=discord.ButtonStyle.secondary,
                emoji="<:ParticipantsLOGO:1407733929389199460>",
                row=0,
                disabled=not self.check_permission("username", "color")
            )
            username_button.callback = self.username_settings

            profile_outline_button = discord.ui.Button(
                label="Profile Outline",
                style=discord.ButtonStyle.secondary,
                emoji="<:ProfileLOGO:1408830057819930806>",
                row=1,
                disabled=not (self.check_permission("avatar_outline", "color") or self.check_permission("avatar_outline", "image"))
            )
            profile_outline_button.callback = self.profile_outline_settings

            content_button = discord.ui.Button(
                label="Content",
                style=discord.ButtonStyle.secondary,
                emoji="📝",
                row=1,
                disabled=not self.check_permission("content", "color")
            )
            content_button.callback = self.content_settings

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1407071474233114766>",
                row=1
            )
            back_button.callback = self.back_to_level_system

            self.add_item(leveling_bar_button)
            self.add_item(background_button)
            self.add_item(username_button)
            self.add_item(profile_outline_button)
            self.add_item(content_button)
            self.add_item(back_button)

            # Add close button for DM version
            close_button = discord.ui.Button(
                label="Close",
                style=discord.ButtonStyle.danger,
                emoji="❌",
                row=2
            )
            close_button.callback = self.close_dm
            self.add_item(close_button)

async def setup(bot):
    await bot.add_cog(LevelingSystem(bot))
    print("LevelingSystem cog loaded successfully!")
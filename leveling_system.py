import discord
from discord.ext import commands
from discord import app_commands
import json
import aiohttp
import io
from PIL import Image, ImageDraw, ImageFont
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

                    # Create a temporary image to apply the levelbar as a mask
                    temp_levelbar = levelbar.copy()
                    temp_levelbar = temp_levelbar.crop((0, 0, progress_width, levelbar.height))

                    # Composite the progress bar with the levelbar shape as mask
                    if temp_levelbar.size[0] > 0:
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

                            # Resize outline to match avatar size
                            outline = outline.resize((size, size), Image.Resampling.LANCZOS)

                            # Paste outline over avatar
                            background.paste(outline, (config["profile_position"]["x"], config["profile_position"]["y"]), outline)

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

            # Draw username with configurable color
            username = user.name
            username_color = config.get("username_color", [255, 255, 255]) # Default white
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

            # Draw level with configurable color
            level_text = f"LEVEL {user_data['level']}"
            level_color = config.get("level_color", [245, 55, 48]) # Default red
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

            try:
                font_xp = ImageFont.truetype("PlayPretend.otf", config["xp_text_position"]["font_size"])
            except IOError:
                # Fallback vers les polices système
                try:
                    font_xp = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", config["xp_text_position"]["font_size"])
                except IOError:
                    font_xp = ImageFont.load_default()

            # Position XP text using dynamic positions
            draw.text((positions["xp_text"]["x"], positions["xp_text"]["y"]), xp_text, font=font_xp, fill=tuple(config.get("xp_text_color", [255, 255, 255])))


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

    @app_commands.command(name="level_system", description="Manage the server leveling system")
    async def level_system(self, interaction: discord.Interaction):
        """Main level system management command"""
        view = LevelSystemMainView(self.bot, interaction.user)
        embed = view.get_main_embed()
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="level", description="View your level card")
    async def level_command(self, interaction: discord.Interaction):
        """Show user's level card"""
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
            await interaction.followup.send(file=file)
        else:
            await interaction.followup.send("<:ErrorLOGO:1407071682031648850> Error creating level card!", ephemeral=True)

# Views and UI Components
class LevelSystemMainView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user

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

    @discord.ui.button(label="Level Card", style=discord.ButtonStyle.secondary, emoji="🎴")
    async def level_card(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        view = LevelCardManagerView(self.bot, interaction.user.id)
        view.guild = interaction.guild

        # Generate preview image
        await view.generate_preview_image(interaction.user)

        embed = view.get_main_embed()
        view.update_buttons()

        await interaction.edit_original_response(embed=embed, view=view)

    @discord.ui.button(label="OFF", style=discord.ButtonStyle.danger, emoji="<:OffLOGO:1407072621836894380>")
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
            self.level_button = discord.ui.Button(label="Set Level", style=discord.ButtonStyle.secondary, emoji="📊")
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
        custom_rewards = data["leveling_settings"]["rewards"]["custom"]
        
        embed = discord.Embed(
            title="<:TotalLOGO:1408245313755545752> Custom Rewards",
            description="Manage custom rewards and advanced XP settings:",
            color=0xFFFFFF
        )

        if custom_rewards:
            reward_list = []
            for reward_id, reward_data in custom_rewards.items():
                reward_list.append(f"• **{reward_data.get('name', f'Custom Reward {reward_id}')}** - Level {reward_data.get('level', 0)}")
            embed.add_field(name="Current Custom Rewards", value="\n".join(reward_list), inline=False)
        else:
            embed.add_field(name="Current Custom Rewards", value="No custom rewards configured", inline=False)

        return embed

    @discord.ui.button(label="Messages XP", style=discord.ButtonStyle.primary, emoji="💬", row=0)
    async def message_xp_custom(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CustomMessageXPView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Characters XP", style=discord.ButtonStyle.secondary, emoji="<:DescriptionLOGO:1407733417172533299>", row=0)
    async def character_xp_custom(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CustomCharacterXPView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Cooldowns", style=discord.ButtonStyle.secondary, emoji="⏰", row=0)
    async def cooldown_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CustomCooldownView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Add Custom", style=discord.ButtonStyle.success, emoji="<:CreateLOGO:1407071205026168853>", row=1)
    async def add_custom_reward(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = AddCustomRewardView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Edit Custom", style=discord.ButtonStyle.primary, emoji="<:EditLOGO:1407071307022995508>", row=1)
    async def edit_custom_reward(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_leveling_data()
        custom_rewards = data["leveling_settings"]["rewards"]["custom"]
        
        if not custom_rewards:
            await interaction.response.send_message(
                "<:ErrorLOGO:1407071682031648850> No custom rewards to edit. Please add a custom reward first.",
                ephemeral=True
            )
            return
            
        view = EditCustomRewardView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Remove Custom", style=discord.ButtonStyle.danger, emoji="<:DeleteLOGO:1407071421363916841>", row=1)
    async def remove_custom_reward(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_leveling_data()
        custom_rewards = data["leveling_settings"]["rewards"]["custom"]
        
        if not custom_rewards:
            await interaction.response.send_message(
                "<:ErrorLOGO:1407071682031648850> No custom rewards to remove. Please add a custom reward first.",
                ephemeral=True
            )
            return
            
        view = RemoveCustomRewardView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>", row=2)
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
        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> XP Settings",
            description="Configure how users gain experience:",
            color=0xFFFFFF
        )
        return embed

    @discord.ui.button(label="Messages", style=discord.ButtonStyle.secondary, emoji="💬")
    async def message_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = MessageXPView(self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Characters XP", style=discord.ButtonStyle.secondary, emoji="<:DescriptionLOGO:1407733417172533299>")
    async def character_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CharacterXPView(self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = LevelSystemMainView(self.bot, self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class MessageXPView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user

        # Set initial button state based on current settings
        data = load_leveling_data()
        enabled = data["leveling_settings"]["xp_settings"]["messages"]["enabled"]

        # Add buttons with correct initial states
        self.add_item(discord.ui.Button(label="XP", style=discord.ButtonStyle.secondary, emoji="⚡"))
        self.add_item(discord.ui.Button(label="Cooldown", style=discord.ButtonStyle.secondary, emoji="⏰"))

        toggle_button = discord.ui.Button(
            label="ON" if enabled else "OFF",
            style=discord.ButtonStyle.success if enabled else discord.ButtonStyle.danger,
            emoji="<:OnLOGO:1407072463883472978>" if enabled else "<:OffLOGO:1407072621836894380>"
        )
        toggle_button.callback = self.toggle
        self.add_item(toggle_button)

        self.add_item(discord.ui.Button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>"))

        # Set callbacks for other buttons
        self.children[0].callback = self.set_xp
        self.children[1].callback = self.set_cooldown
        self.children[3].callback = self.back

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

    @discord.ui.button(label="XP", style=discord.ButtonStyle.secondary, emoji="⚡")
    async def set_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MessageXPModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cooldown", style=discord.ButtonStyle.secondary, emoji="⏰")
    async def set_cooldown(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MessageCooldownModal()
        await interaction.response.send_modal(modal)

    async def toggle(self, interaction: discord.Interaction):
        data = load_leveling_data()
        current_state = data["leveling_settings"]["xp_settings"]["messages"]["enabled"]
        data["leveling_settings"]["xp_settings"]["messages"]["enabled"] = not current_state
        save_leveling_data(data)

        # Find the toggle button and update its appearance
        for item in self.children:
            if hasattr(item, 'callback') and item.callback == self.toggle:
                if data["leveling_settings"]["xp_settings"]["messages"]["enabled"]:
                    item.label = "ON"
                    item.style = discord.ButtonStyle.success
                    item.emoji = "<:OnLOGO:1407072463883472978>"
                else:
                    item.label = "OFF"
                    item.style = discord.ButtonStyle.danger
                    item.emoji = "<:OffLOGO:1407072621836894380>"
                break

        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>")
    async def back(self, interaction: discord.Interaction):
        from leveling_system import LevelingSystem
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

        # Set initial button state based on current settings
        data = load_leveling_data()
        enabled = data["leveling_settings"]["xp_settings"]["characters"]["enabled"]

        # Add buttons with correct initial states
        self.add_item(discord.ui.Button(label="XP", style=discord.ButtonStyle.secondary, emoji="⚡"))
        self.add_item(discord.ui.Button(label="Cooldown", style=discord.ButtonStyle.secondary, emoji="⏰"))

        toggle_button = discord.ui.Button(
            label="ON" if enabled else "OFF",
            style=discord.ButtonStyle.success if enabled else discord.ButtonStyle.danger,
            emoji="<:OnLOGO:1407072463883472978>" if enabled else "<:OffLOGO:1407072621836894380>"
        )
        toggle_button.callback = self.toggle
        self.add_item(toggle_button)

        self.add_item(discord.ui.Button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>"))

        # Set callbacks for other buttons
        self.children[0].callback = self.set_xp
        self.children[1].callback = self.set_cooldown
        self.children[3].callback = self.back

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

    @discord.ui.button(label="XP", style=discord.ButtonStyle.secondary, emoji="⚡")
    async def set_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CharacterXPModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cooldown", style=discord.ButtonStyle.secondary, emoji="⏰")
    async def set_cooldown(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CharacterCooldownModal()
        await interaction.response.send_modal(modal)

    async def toggle(self, interaction: discord.Interaction):
        data = load_leveling_data()
        current_state = data["leveling_settings"]["xp_settings"]["characters"]["enabled"]
        data["leveling_settings"]["xp_settings"]["characters"]["enabled"] = not current_state
        save_leveling_data(data)

        # Find the toggle button and update its appearance
        for item in self.children:
            if hasattr(item, 'callback') and item.callback == self.toggle:
                if data["leveling_settings"]["xp_settings"]["characters"]["enabled"]:
                    item.label = "ON"
                    item.style = discord.ButtonStyle.success
                    item.emoji = "<:OnLOGO:1407072463883472978>"
                else:
                    item.label = "OFF"
                    item.style = discord.ButtonStyle.danger
                    item.emoji = "<:OffLOGO:1407072621836894380>"
                break

        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>")
    async def back(self, interaction: discord.Interaction):
        from leveling_system import LevelingSystem
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

class BackToMainButton(discord.ui.Button):
    def __init__(self, bot, user):
        super().__init__(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>")
        self.bot = bot
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        view = LevelSystemMainView(self.bot, self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

# Level Card Management System
class LevelCardManagerView(discord.ui.View):
    def __init__(self, bot, user_id):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.config = load_leveling_data()["leveling_settings"]["level_card"]
        self.mode = "main"
        self.waiting_for_image = False
        self.current_image_type = None
        self.preview_image_url = None

    def get_main_embed(self):
        embed = discord.Embed(
            title="🎴 Level Card Manager",
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
            config_status += "⚪ Background: Default\n"

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
        data = load_leveling_data()
        data["leveling_settings"]["level_card"] = self.config
        save_leveling_data(data)

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
                style=discord.ButtonStyle.primary,
                emoji="ℹ️"
            )
            xp_info_button.callback = self.xp_info_settings

            xp_bar_button = discord.ui.Button(
                label="XP Bar",
                style=discord.ButtonStyle.secondary,
                emoji="📊"
            )
            xp_bar_button.callback = self.xp_bar_settings

            xp_progress_button = discord.ui.Button(
                label="XP Progress",
                style=discord.ButtonStyle.secondary,
                emoji="⚡"
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

        elif self.mode in ["xp_info_color", "xp_progress_color", "background_color", "username_color", "profile_outline_color"]:
            # Color selection buttons
            hex_button = discord.ui.Button(
                label="Hex Code",
                style=discord.ButtonStyle.primary,
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
                style=discord.ButtonStyle.danger,
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

        elif self.mode in ["xp_bar_image", "background_image", "profile_outline_image"]:
            # Image selection buttons
            url_button = discord.ui.Button(
                label="Set URL",
                style=discord.ButtonStyle.primary,
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
                style=discord.ButtonStyle.danger,
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
                style=discord.ButtonStyle.primary,
                emoji="<:ColorLOGO:1408828590241615883>"
            )
            color_button.callback = self.color_settings

            if self.mode in ["background"]:
                image_button = discord.ui.Button(
                    label="Image",
                    style=discord.ButtonStyle.secondary,
                    emoji="<:ImageLOGO:1407072328134951043>"
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
            image_button = discord.ui.Button(
                label="Image",
                style=discord.ButtonStyle.primary,
                emoji="<:ImageLOGO:1407072328134951043>"
            )
            image_button.callback = self.image_settings

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1407071474233114766>"
            )
            back_button.callback = self.back_to_parent

            self.add_item(image_button)
            self.add_item(back_button)

        elif self.mode == "profile_outline":
            # Profile outline main buttons
            toggle_button = discord.ui.Button(
                label="ON" if self.config.get("profile_outline", {}).get("enabled", True) else "OFF",
                style=discord.ButtonStyle.success if self.config.get("profile_outline", {}).get("enabled", True) else discord.ButtonStyle.danger,
                emoji="<:OnLOGO:1407072463883472978>" if self.config.get("profile_outline", {}).get("enabled", True) else "<:OffLOGO:1407072621836894380>"
            )
            toggle_button.callback = self.toggle_profile_outline

            color_button = discord.ui.Button(
                label="Color",
                style=discord.ButtonStyle.primary,
                emoji="<:ColorLOGO:1408828590241615883>"
            )
            color_button.callback = self.color_settings

            image_button = discord.ui.Button(
                label="Image",
                style=discord.ButtonStyle.secondary,
                emoji="<:ImageLOGO:1407072328134951043>"
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

        else:  # main mode
            # Main buttons
            leveling_bar_button = discord.ui.Button(
                label="Leveling Bar",
                style=discord.ButtonStyle.primary,
                emoji="📊",
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
        elif self.mode == "profile_outline_image":
            if "profile_outline" not in self.config:
                self.config["profile_outline"] = {}
            self.config["profile_outline"].pop("custom_image", None)

        self.save_config()
        await self.generate_preview_image(interaction.user)

        # Go back to appropriate embed
        if self.mode == "xp_bar_image":
            embed = self.get_xp_bar_embed()
        elif self.mode == "background_image":
            embed = self.get_background_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Background Image"
            embed.description = "Set a custom background image"
        elif self.mode == "profile_outline_image":
            embed = self.get_profile_outline_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Profile Outline Image"
            embed.description = "Set a custom profile outline image"

        self.update_buttons()
        await interaction.edit_original_response(embed=embed, view=self)

    async def reset_color(self, interaction: discord.Interaction):
        await interaction.response.defer()

        if self.mode == "xp_info_color":
            self.config["xp_text_color"] = [255, 255, 255]
        elif self.mode == "xp_progress_color":
            self.config["xp_bar_color"] = [245, 55, 48]
        elif self.mode == "background_color":
            self.config["background_color"] = [15, 17, 16]
        elif self.mode == "username_color":
            self.config["username_color"] = [255, 255, 255]
        elif self.mode == "profile_outline_color":
            if "profile_outline" not in self.config:
                self.config["profile_outline"] = {}
            self.config["profile_outline"].pop("color_override", None)

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
        if self.mode.endswith("_color") or self.mode.endswith("_image"):
            self.mode = self.mode.replace("_color", "").replace("_image", "")

        if self.mode == "xp_info":
            embed = self.get_xp_info_embed()
        elif self.mode == "xp_bar":
            embed = self.get_xp_bar_embed()
        elif self.mode == "xp_progress":
            embed = self.get_xp_progress_embed()
        elif self.mode == "background":
            embed = self.get_background_embed()
        elif self.mode == "username":
            embed = self.get_username_embed()
        elif self.mode == "profile_outline":
            embed = self.get_profile_outline_embed()
        else:
            self.mode = "leveling_bar"
            embed = self.get_leveling_bar_embed()

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

        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def back_to_level_system(self, interaction: discord.Interaction):
        """Go back to the main level system menu"""
        view = LevelSystemMainView(self.bot, interaction.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

# Modal classes for Level Card
class LevelCardHexColorModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='🎨 Hex Color')
        self.view = view

        # Get current color value
        current_color = ""
        if self.view.mode == "xp_info_color" and self.view.config.get("xp_text_color"):
            rgb = self.view.config["xp_text_color"]
            current_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        elif self.view.mode == "xp_progress_color" and self.view.config.get("xp_bar_color"):
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
                title="<:ErrorLOGO:1407071682031648850> Invalid Hex Color",
                description="Please enter a valid hex color code (e.g., #FF0000 or FF0000)",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

class LevelCardRGBColorModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='<:RGBcodeLOGO:1408831982141575290> RGB Color')
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
        super().__init__(title='🖼️ Image URL')
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

        self.view.update_buttons()
        await interaction.edit_original_response(embed=embed, view=self.view)

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

    @discord.ui.button(label="XP Amount", style=discord.ButtonStyle.primary, emoji="⚡")
    async def set_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomMessageXPModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cooldown", style=discord.ButtonStyle.secondary, emoji="⏰")
    async def set_cooldown(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomMessageCooldownModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Toggle", style=discord.ButtonStyle.success, emoji="🔄")
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_leveling_data()
        current_state = data["leveling_settings"]["xp_settings"]["messages"]["enabled"]
        data["leveling_settings"]["xp_settings"]["messages"]["enabled"] = not current_state
        save_leveling_data(data)

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

    @discord.ui.button(label="XP Amount", style=discord.ButtonStyle.primary, emoji="⚡")
    async def set_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomCharacterXPModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Character Limit", style=discord.ButtonStyle.secondary, emoji="📝")
    async def set_limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomCharacterLimitModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cooldown", style=discord.ButtonStyle.secondary, emoji="⏰")
    async def set_cooldown(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomCharacterCooldownModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Toggle", style=discord.ButtonStyle.success, emoji="🔄")
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_leveling_data()
        current_state = data["leveling_settings"]["xp_settings"]["characters"]["enabled"]
        data["leveling_settings"]["xp_settings"]["characters"]["enabled"] = not current_state
        save_leveling_data(data)

        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CustomRewardsView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class CustomCooldownView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user

    def get_embed(self):
        data = load_leveling_data()
        msg_cooldown = data["leveling_settings"]["xp_settings"]["messages"]["cooldown"]
        char_cooldown = data["leveling_settings"]["xp_settings"]["characters"]["cooldown"]

        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Custom Cooldown Settings",
            description="Manage all cooldown settings in one place:",
            color=0xFFFFFF
        )

        embed.add_field(name="Message Cooldown", value=f"{msg_cooldown} seconds", inline=True)
        embed.add_field(name="Character Cooldown", value=f"{char_cooldown} seconds", inline=True)
        
        return embed

    @discord.ui.button(label="Message Cooldown", style=discord.ButtonStyle.primary, emoji="💬")
    async def message_cooldown(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomMessageCooldownModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Character Cooldown", style=discord.ButtonStyle.secondary, emoji="<:DescriptionLOGO:1407733417172533299>")
    async def character_cooldown(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomCharacterCooldownModal()
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
        view = CustomRewardsView(self.bot, self.user)
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

async def setup(bot):
    await bot.add_cog(LevelingSystem(bot))
    print("LevelingSystem cog loaded successfully!")
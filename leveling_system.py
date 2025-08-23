import discord
from discord.ext import commands
from discord import app_commands
import json
import aiohttp
import io
from PIL import Image, ImageDraw, ImageFont
import time
import math

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
                    "xp_text_color": [154, 154, 154] # Default XP text color (gray)
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
        """Handle XP gain from messages"""
        if message.author.bot:
            return

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
        view = LevelSystemMainView(interaction.user)
        embed = view.get_main_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

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
            await interaction.followup.send("❌ Error creating level card!", ephemeral=True)

# Views and UI Components
class LevelSystemMainView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user

    def get_main_embed(self):
        data = load_leveling_data()
        settings = data["leveling_settings"]

        embed = discord.Embed(
            title="📊 Level System Management",
            description=f"Welcome back {self.user.mention}!\n\nManage your server's leveling system below:",
            color=0x5865f2
        )

        status = "🟢 Enabled" if settings["enabled"] else "🔴 Disabled"
        embed.add_field(name="System Status", value=status, inline=True)

        return embed

    @discord.ui.button(label="Reward Settings", style=discord.ButtonStyle.secondary, emoji="🎁")
    async def reward_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RewardSettingsView(self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="XP Settings", style=discord.ButtonStyle.secondary, emoji="⚡")
    async def xp_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = XPSettingsView(self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Level Card", style=discord.ButtonStyle.secondary, emoji="🎴")
    async def level_card(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎴 Level Card Settings",
            description="Level card customization is currently view-only.\nMore customization options coming soon!",
            color=0x5865f2
        )
        view = discord.ui.View()
        view.add_item(BackToMainButton(self.user))
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="ON/OFF", style=discord.ButtonStyle.success, emoji="🔄")
    async def toggle_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_leveling_data()
        data["leveling_settings"]["enabled"] = not data["leveling_settings"]["enabled"]
        save_leveling_data(data)

        embed = self.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=self)

class RewardSettingsView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user

    def get_embed(self):
        embed = discord.Embed(
            title="🎁 Reward Settings",
            description="Choose the type of rewards to configure:",
            color=0x5865f2
        )
        return embed

    @discord.ui.button(label="Role", style=discord.ButtonStyle.secondary, emoji="👑")
    async def role_rewards(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RoleRewardsView(self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Custom", style=discord.ButtonStyle.secondary, emoji="✨")
    async def custom_rewards(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CustomRewardsView(self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.danger, emoji="↩️")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = LevelSystemMainView(self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class RoleRewardsView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user

    def get_embed(self):
        data = load_leveling_data()
        role_rewards = data["leveling_settings"]["rewards"]["roles"]

        embed = discord.Embed(
            title="👑 Role Rewards",
            description="Manage role rewards for leveling up:",
            color=0x5865f2
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

    @discord.ui.button(label="Add", style=discord.ButtonStyle.success, emoji="➕")
    async def add_role_reward(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = AddRoleRewardView(self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.secondary, emoji="✏️")
    async def edit_role_reward(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = EditRoleRewardView(self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Remove", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def remove_role_reward(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RemoveRoleRewardView(self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.danger, emoji="↩️")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RewardSettingsView(self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class AddRoleRewardView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user
        self.selected_role = None
        self.level = None

    def get_embed(self):
        embed = discord.Embed(
            title="➕ Add Role Reward",
            description="Select a role and level for the reward:",
            color=0x5865f2
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
                self.confirm_button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
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
            title="✅ Role Reward Added",
            description=f"Role {self.selected_role.mention} will be given at level {self.level}!",
            color=0x00ff00
        )
        view = RoleRewardsView(self.user)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.danger, emoji="↩️")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RoleRewardsView(self.user)
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
                await interaction.response.send_message("❌ Level must be between 0 and 100!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number!", ephemeral=True)

class EditRoleRewardView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user
        self.add_item(EditRoleRewardSelect())

    def get_embed(self):
        embed = discord.Embed(
            title="✏️ Edit Role Reward",
            description="Select a role reward to edit:",
            color=0x5865f2
        )
        return embed

    @discord.ui.button(label="Back", style=discord.ButtonStyle.danger, emoji="↩️")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RoleRewardsView(self.user)
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
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user
        self.add_item(RemoveRoleRewardSelect())

    def get_embed(self):
        embed = discord.Embed(
            title="🗑️ Remove Role Reward",
            description="Select a role reward to remove:",
            color=0xff0000
        )
        return embed

    @discord.ui.button(label="Back", style=discord.ButtonStyle.danger, emoji="↩️")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RoleRewardsView(self.user)
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
            title="⚠️ Confirm Removal",
            description="This action is irreversible! Are you sure you want to remove this reward?",
            color=0xff0000
        )
        view = ConfirmRemoveView(self.values[0])
        await interaction.response.edit_message(embed=embed, view=view)

class ConfirmRemoveView(discord.ui.View):
    def __init__(self, reward_id):
        super().__init__(timeout=300)
        self.reward_id = reward_id

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_leveling_data()
        if self.reward_id in data["leveling_settings"]["rewards"]["roles"]:
            del data["leveling_settings"]["rewards"]["roles"][self.reward_id]
            save_leveling_data(data)

        embed = discord.Embed(
            title="✅ Reward Removed",
            description="The role reward has been successfully removed!",
            color=0x00ff00
        )
        view = RoleRewardsView(interaction.user)
        await interaction.response.edit_message(embed=embed, view=view)

class CustomRewardsView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user

    def get_embed(self):
        embed = discord.Embed(
            title="✨ Custom Rewards",
            description="Custom reward system is currently in development.\nComing soon!",
            color=0x5865f2
        )
        return embed

    @discord.ui.button(label="Back", style=discord.ButtonStyle.danger, emoji="↩️")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RewardSettingsView(self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class XPSettingsView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user

    def get_embed(self):
        embed = discord.Embed(
            title="⚡ XP Settings",
            description="Configure how users gain experience:",
            color=0x5865f2
        )
        return embed

    @discord.ui.button(label="Messages", style=discord.ButtonStyle.secondary, emoji="💬")
    async def message_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = MessageXPView(self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Characters XP", style=discord.ButtonStyle.secondary, emoji="📝")
    async def character_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CharacterXPView(self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.danger, emoji="↩️")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = LevelSystemMainView(self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class MessageXPView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user

    def get_embed(self):
        data = load_leveling_data()
        msg_settings = data["leveling_settings"]["xp_settings"]["messages"]

        embed = discord.Embed(
            title="💬 Message XP Settings",
            description="Configure XP gain from messages:",
            color=0x5865f2
        )

        embed.add_field(name="XP per Message", value=str(msg_settings["xp_per_message"]), inline=True)
        embed.add_field(name="Cooldown (seconds)", value=str(msg_settings["cooldown"]), inline=True)
        status = "🟢 Enabled" if msg_settings["enabled"] else "🔴 Disabled"
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

    @discord.ui.button(label="ON/OFF", style=discord.ButtonStyle.success, emoji="🔄")
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_leveling_data()
        data["leveling_settings"]["xp_settings"]["messages"]["enabled"] = not data["leveling_settings"]["xp_settings"]["messages"]["enabled"]
        save_leveling_data(data)

        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.danger, emoji="↩️")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = XPSettingsView(self.user)
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
                await interaction.response.send_message(f"✅ Message XP set to {xp_value}!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ XP must be 0 or higher!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number!", ephemeral=True)

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
                await interaction.response.send_message(f"✅ Message cooldown set to {cooldown_value} seconds!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Cooldown must be 0 or higher!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number!", ephemeral=True)

class CharacterXPView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user

    def get_embed(self):
        data = load_leveling_data()
        char_settings = data["leveling_settings"]["xp_settings"]["characters"]

        embed = discord.Embed(
            title="📝 Character XP Settings",
            description="Configure XP gain from characters:",
            color=0x5865f2
        )

        embed.add_field(name="XP per Character", value=str(char_settings["xp_per_character"]), inline=True)
        embed.add_field(name="Character Limit", value=str(char_settings["character_limit"]), inline=True)
        embed.add_field(name="Cooldown (seconds)", value=str(char_settings["cooldown"]), inline=True)
        status = "🟢 Enabled" if char_settings["enabled"] else "🔴 Disabled"
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

    @discord.ui.button(label="ON/OFF", style=discord.ButtonStyle.success, emoji="🔄")
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_leveling_data()
        data["leveling_settings"]["xp_settings"]["characters"]["enabled"] = not data["leveling_settings"]["xp_settings"]["characters"]["enabled"]
        save_leveling_data(data)

        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.danger, emoji="↩️")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = XPSettingsView(self.user)
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
                await interaction.response.send_message(f"✅ Character XP set to {xp_value}!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ XP must be 0 or higher!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number!", ephemeral=True)

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
                await interaction.response.send_message(f"✅ Character settings updated!\nLimit: {char_limit} characters\nCooldown: {cooldown_value} seconds", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Values must be 0 or higher!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Please enter valid numbers!", ephemeral=True)

class BackToMainButton(discord.ui.Button):
    def __init__(self, user):
        super().__init__(label="Back to Main", style=discord.ButtonStyle.danger, emoji="↩️")
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        view = LevelSystemMainView(self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(LevelingSystem(bot))
    print("LevelingSystem cog loaded successfully!")
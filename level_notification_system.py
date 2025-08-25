import discord
from discord.ext import commands
from discord import app_commands
import json
import aiohttp
import io
from PIL import Image, ImageDraw, ImageFont, ImageOps
import uuid
import os

# Data management functions for notifications
def load_notification_data():
    try:
        with open('leveling_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Initialize notification settings if they don't exist
            if "notification_settings" not in data:
                data["notification_settings"] = {
                    "level_notifications": {
                        "enabled": True,
                        "cycle": 1,
                        "level_card": {
                            "background_color": [245, 55, 48],
                            "background_image": None,
                            "username_color": [255, 255, 255],
                            "level_text_color": [255, 255, 255],
                            "message_text_color": [255, 255, 255],
                            "info_text_color": [200, 200, 200],
                            "outline_enabled": True,
                            "outline_color": [255, 255, 255],
                            "outline_image": None,
                            "username_position": {"x": 540, "y": 200, "font_size": 80},
                            "level_position": {"x": 540, "y": 300, "font_size": 120},
                            "message_position": {"x": 540, "y": 450, "font_size": 60},
                            "info_position": {"x": 540, "y": 550, "font_size": 40},
                            "avatar_position": {"x": 190, "y": 190, "size": 300},
                            "outline_position": {"x": 190, "y": 190, "size": 300}
                        }
                    },
                    "role_notifications": {
                        "enabled": False
                    },
                    "custom_notifications": {
                        "enabled": False
                    }
                }
                save_notification_data(data)
            return data
    except FileNotFoundError:
        # Return default structure if file doesn't exist
        return {
            "notification_settings": {
                "level_notifications": {
                    "enabled": True,
                    "cycle": 1,
                    "level_card": {
                        "background_color": [245, 55, 48],
                        "background_image": None,
                        "username_color": [255, 255, 255],
                        "level_text_color": [255, 255, 255],
                        "message_text_color": [255, 255, 255],
                        "info_text_color": [200, 200, 200],
                        "outline_enabled": True,
                        "outline_color": [255, 255, 255],
                        "outline_image": None,
                        "username_position": {"x": 540, "y": 200, "font_size": 80},
                        "level_position": {"x": 540, "y": 300, "font_size": 120},
                        "message_position": {"x": 540, "y": 450, "font_size": 60},
                        "info_position": {"x": 540, "y": 550, "font_size": 40},
                        "avatar_position": {"x": 190, "y": 190, "size": 300},
                        "outline_position": {"x": 190, "y": 190, "size": 300}
                    }
                },
                "role_notifications": {
                    "enabled": False
                },
                "custom_notifications": {
                    "enabled": False
                }
            }
        }

def save_notification_data(data):
    with open('leveling_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

class NotificationSystemView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user

    def get_main_embed(self):
        embed = discord.Embed(
            title="🔔 Notification Settings",
            description="Configure notification settings for the leveling system:",
            color=0xFFFFFF
        )
        
        data = load_notification_data()
        settings = data.get("notification_settings", {})
        
        # Level notifications status
        level_enabled = settings.get("level_notifications", {}).get("enabled", True)
        level_status = "<:OnLOGO:1407072463883472978> Enabled" if level_enabled else "<:OffLOGO:1407072621836894380> Disabled"
        
        # Role notifications status
        role_enabled = settings.get("role_notifications", {}).get("enabled", False)
        role_status = "<:OnLOGO:1407072463883472978> Enabled" if role_enabled else "<:OffLOGO:1407072621836894380> Disabled"
        
        # Custom notifications status
        custom_enabled = settings.get("custom_notifications", {}).get("enabled", False)
        custom_status = "<:OnLOGO:1407072463883472978> Enabled" if custom_enabled else "<:OffLOGO:1407072621836894380> Disabled"
        
        embed.add_field(name="Level Notifications", value=level_status, inline=True)
        embed.add_field(name="Role Notifications", value=role_status, inline=True)
        embed.add_field(name="Custom Notifications", value=custom_status, inline=True)
        
        return embed

    @discord.ui.button(label="Level Notification", style=discord.ButtonStyle.secondary, emoji="<a:XPLOGO:1409634015043915827>")
    async def level_notification(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = LevelNotificationView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Role Notification", style=discord.ButtonStyle.secondary, emoji="<:ParticipantsLOGO:1407733929389199460>")
    async def role_notification(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🔔 Role Notifications",
            description="Role notification settings coming soon!",
            color=0xFFFFFF
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Custom Notification", style=discord.ButtonStyle.secondary, emoji="<:TotalLOGO:1408245313755545752>")
    async def custom_notification(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🔔 Custom Notifications",
            description="Custom notification settings coming soon!",
            color=0xFFFFFF
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Import here to avoid circular import
        from leveling_system import LevelSystemMainView
        view = LevelSystemMainView(self.bot, self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class LevelNotificationView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user
        
        # Initialize toggle button state
        data = load_notification_data()
        level_enabled = data.get("notification_settings", {}).get("level_notifications", {}).get("enabled", True)
        
        # Update toggle button based on current state
        for item in self.children:
            if hasattr(item, 'callback') and item.callback.__name__ == 'toggle_level_notifications':
                if level_enabled:
                    item.label = "ON"
                    item.style = discord.ButtonStyle.success
                    item.emoji = "<:OnLOGO:1407072463883472978>"
                else:
                    item.label = "OFF"
                    item.style = discord.ButtonStyle.danger
                    item.emoji = "<:OffLOGO:1407072621836894380>"
                break

    def get_embed(self):
        data = load_notification_data()
        settings = data.get("notification_settings", {}).get("level_notifications", {})
        
        embed = discord.Embed(
            title="<a:XPLOGO:1409634015043915827> Level Notification Settings",
            description="Configure level-up notifications:",
            color=0xFFFFFF
        )
        
        enabled = settings.get("enabled", True)
        status = "<:OnLOGO:1407072463883472978> Enabled" if enabled else "<:OffLOGO:1407072621836894380> Disabled"
        cycle = settings.get("cycle", 1)
        
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Notification Cycle", value=f"Every {cycle} level(s)", inline=True)
        
        return embed

    @discord.ui.button(label="ON", style=discord.ButtonStyle.success, emoji="<:OnLOGO:1407072463883472978>")
    async def toggle_level_notifications(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_notification_data()
        current_state = data.get("notification_settings", {}).get("level_notifications", {}).get("enabled", True)
        
        if "notification_settings" not in data:
            data["notification_settings"] = {}
        if "level_notifications" not in data["notification_settings"]:
            data["notification_settings"]["level_notifications"] = {}
            
        data["notification_settings"]["level_notifications"]["enabled"] = not current_state
        save_notification_data(data)
        
        # Update button appearance
        if data["notification_settings"]["level_notifications"]["enabled"]:
            button.label = "ON"
            button.style = discord.ButtonStyle.success
            button.emoji = "<:OnLOGO:1407072463883472978>"
        else:
            button.label = "OFF"
            button.style = discord.ButtonStyle.danger
            button.emoji = "<:OffLOGO:1407072621836894380>"
        
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Cycle", style=discord.ButtonStyle.secondary, emoji="<:CooldownLOGO:1409586926071054448>")
    async def set_cycle(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CycleModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Level Card", style=discord.ButtonStyle.secondary, emoji="<:CardLOGO:1409586383047233536>")
    async def level_card_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        view = NotificationLevelCardView(self.bot, self.user)
        await view.generate_preview_image(interaction.user)
        
        embed = view.get_main_embed()
        view.update_buttons()
        
        await interaction.edit_original_response(embed=embed, view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = NotificationSystemView(self.bot, self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class CycleModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Set Notification Cycle")

    cycle = discord.ui.TextInput(
        label="Cycle (levels between notifications)",
        placeholder="Enter number between 1 and level max...",
        min_length=1,
        max_length=3
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            cycle_value = int(self.cycle.value)
            data = load_notification_data()
            
            # Get max level from leveling settings
            max_level = data.get("leveling_settings", {}).get("max_level", 100)
            
            if 1 <= cycle_value <= max_level:
                if "notification_settings" not in data:
                    data["notification_settings"] = {}
                if "level_notifications" not in data["notification_settings"]:
                    data["notification_settings"]["level_notifications"] = {}
                    
                data["notification_settings"]["level_notifications"]["cycle"] = cycle_value
                save_notification_data(data)
                
                await interaction.response.send_message(f"<:SucessLOGO:1407071637840592977> Notification cycle set to every {cycle_value} level(s)!", ephemeral=True)
            else:
                await interaction.response.send_message(f"<:ErrorLOGO:1407071682031648850> Cycle must be between 1 and {max_level}!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Please enter a valid number!", ephemeral=True)

class NotificationLevelCardView(discord.ui.View):
    def __init__(self, bot, user_id):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.mode = "main"
        self.waiting_for_image = False
        self.current_image_type = None
        self.preview_image_url = None

    def get_config(self):
        data = load_notification_data()
        return data.get("notification_settings", {}).get("level_notifications", {}).get("level_card", {})

    def save_config(self, config):
        data = load_notification_data()
        if "notification_settings" not in data:
            data["notification_settings"] = {}
        if "level_notifications" not in data["notification_settings"]:
            data["notification_settings"]["level_notifications"] = {}
        data["notification_settings"]["level_notifications"]["level_card"] = config
        save_notification_data(data)

    def get_main_embed(self):
        embed = discord.Embed(
            title="<:CardLOGO:1409586383047233536> Notification Level Card Settings",
            description="Configure the level-up notification card design (1080x1080 pixels)",
            color=0xFFFFFF
        )
        
        config = self.get_config()
        
        # Show current configuration
        config_status = ""
        if config.get("background_image"):
            config_status += "<:BackgroundLOGO:1408834163309805579> Background: Custom Image\n"
        elif config.get("background_color"):
            bg = config["background_color"]
            config_status += f"<:BackgroundLOGO:1408834163309805579> Background: RGB({bg[0]}, {bg[1]}, {bg[2]})\n"
        
        outline_enabled = config.get("outline_enabled", True)
        outline_status = "<:OnLOGO:1407072463883472978> Enabled" if outline_enabled else "<:OffLOGO:1407072621836894380> Disabled"
        config_status += f"<:ProfileLOGO:1408830057819930806> Profile Outline: {outline_status}\n"
        
        embed.add_field(name="Current Configuration", value=config_status, inline=False)
        
        # Add preview image if available
        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            import time
            timestamp = int(time.time())
            if '?' in self.preview_image_url:
                image_url = self.preview_image_url.split('?')[0] + f"?refresh={timestamp}"
            else:
                image_url = self.preview_image_url + f"?refresh={timestamp}"
            embed.set_image(url=image_url)
        
        return embed

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

    async def create_notification_level_card(self, user, level):
        """Create notification level card (1080x1080)"""
        try:
            config = self.get_config()
            
            # Create 1080x1080 background
            background = Image.new("RGBA", (1080, 1080), (0, 0, 0, 0))
            
            # Set background
            if config.get("background_image"):
                bg_data = await self.download_image(config["background_image"])
                if bg_data:
                    bg_img = Image.open(io.BytesIO(bg_data)).convert("RGBA")
                    bg_img = bg_img.resize((1080, 1080), Image.Resampling.LANCZOS)
                    background = bg_img
                else:
                    bg_color = tuple(config.get("background_color", [245, 55, 48])) + (255,)
                    background = Image.new("RGBA", (1080, 1080), bg_color)
            else:
                bg_color = tuple(config.get("background_color", [245, 55, 48])) + (255,)
                background = Image.new("RGBA", (1080, 1080), bg_color)
            
            # Download user avatar
            avatar_url = user.display_avatar.url
            avatar_data = await self.download_image(avatar_url)
            if avatar_data:
                avatar = Image.open(io.BytesIO(avatar_data)).convert("RGBA")
                avatar_pos = config.get("avatar_position", {"x": 190, "y": 190, "size": 300})
                size = avatar_pos["size"]
                avatar = avatar.resize((size, size), Image.Resampling.LANCZOS)
                
                # Make avatar circular
                mask = self.create_circle_mask((size, size))
                avatar.putalpha(mask)
                
                # Paste avatar
                background.paste(avatar, (avatar_pos["x"], avatar_pos["y"]), avatar)
                
                # Add outline if enabled
                if config.get("outline_enabled", True):
                    outline_pos = config.get("outline_position", {"x": 190, "y": 190, "size": 300})
                    outline_url = "https://raw.githubusercontent.com/TheBlueEL/pictures/refs/heads/main/ProfileOutline.png"
                    
                    if config.get("outline_image"):
                        outline_url = config["outline_image"]
                    
                    outline_data = await self.download_image(outline_url)
                    if outline_data:
                        outline = Image.open(io.BytesIO(outline_data)).convert("RGBA")
                        outline = outline.resize((outline_pos["size"], outline_pos["size"]), Image.Resampling.LANCZOS)
                        
                        # Apply color if specified and not using custom image
                        if config.get("outline_color") and not config.get("outline_image"):
                            color_override = config["outline_color"]
                            colored_outline = Image.new("RGBA", outline.size, tuple(color_override + [255]))
                            colored_outline.putalpha(outline.split()[-1])
                            outline = colored_outline
                        
                        background.paste(outline, (outline_pos["x"], outline_pos["y"]), outline)
            
            # Add text
            draw = ImageDraw.Draw(background)
            
            # Load fonts
            try:
                font_username = ImageFont.truetype("PlayPretend.otf", config.get("username_position", {}).get("font_size", 80))
                font_level = ImageFont.truetype("PlayPretend.otf", config.get("level_position", {}).get("font_size", 120))
                font_message = ImageFont.truetype("PlayPretend.otf", config.get("message_position", {}).get("font_size", 60))
                font_info = ImageFont.truetype("PlayPretend.otf", config.get("info_position", {}).get("font_size", 40))
            except IOError:
                font_username = ImageFont.load_default()
                font_level = ImageFont.load_default()
                font_message = ImageFont.load_default()
                font_info = ImageFont.load_default()
            
            # Draw username
            username_pos = config.get("username_position", {"x": 540, "y": 200})
            username_color = tuple(config.get("username_color", [255, 255, 255]))
            draw.text((username_pos["x"], username_pos["y"]), user.name, font=font_username, fill=username_color)
            
            # Draw level
            level_pos = config.get("level_position", {"x": 540, "y": 300})
            level_color = tuple(config.get("level_text_color", [255, 255, 255]))
            draw.text((level_pos["x"], level_pos["y"]), f"LEVEL {level}", font=font_level, fill=level_color)
            
            # Draw message
            message_pos = config.get("message_position", {"x": 540, "y": 450})
            message_color = tuple(config.get("message_text_color", [255, 255, 255]))
            draw.text((message_pos["x"], message_pos["y"]), "You just reached a new level !", font=font_message, fill=message_color)
            
            # Draw info
            info_pos = config.get("info_position", {"x": 540, "y": 550})
            info_color = tuple(config.get("info_text_color", [200, 200, 200]))
            draw.text((info_pos["x"], info_pos["y"]), "Type /level for more information", font=font_info, fill=info_color)
            
            output = io.BytesIO()
            background.save(output, format='PNG')
            output.seek(0)
            return output
            
        except Exception as e:
            print(f"Error creating notification level card: {e}")
            return None

    async def generate_preview_image(self, interaction_user):
        """Generate preview image and upload to GitHub"""
        try:
            preview_image = await self.create_notification_level_card(interaction_user, 50)
            
            if preview_image:
                # Save preview to temp file
                os.makedirs('images', exist_ok=True)
                import time
                timestamp = int(time.time())
                filename = f"notification_level_preview_{self.user_id}_{timestamp}.png"
                file_path = os.path.join('images', filename)
                
                with open(file_path, 'wb') as f:
                    f.write(preview_image.getvalue())
                
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
                        self.preview_image_url = f"https://raw.githubusercontent.com/TheBlueEL/pictures/main/{filename}?t={timestamp}"
                        return True
                except ImportError:
                    print("GitHub sync not available")
            
        except Exception as e:
            print(f"Error generating preview: {e}")
        
        return False

    def update_buttons(self):
        self.clear_items()
        
        if self.mode == "main":
            # Main buttons
            background_button = discord.ui.Button(
                label="Background",
                style=discord.ButtonStyle.secondary,
                emoji="<:BackgroundLOGO:1408834163309805579>",
                row=0
            )
            background_button.callback = self.background_settings
            
            text_button = discord.ui.Button(
                label="Text Settings",
                style=discord.ButtonStyle.secondary,
                emoji="<:DescriptionLOGO:1407733417172533299>",
                row=0
            )
            text_button.callback = self.text_settings
            
            outline_button = discord.ui.Button(
                label="Profile Outline",
                style=discord.ButtonStyle.secondary,
                emoji="<:ProfileLOGO:1408830057819930806>",
                row=0
            )
            outline_button.callback = self.outline_settings
            
            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1407071474233114766>",
                row=1
            )
            back_button.callback = self.back_to_notification
            
            self.add_item(background_button)
            self.add_item(text_button)
            self.add_item(outline_button)
            self.add_item(back_button)

    # Button callbacks would be implemented here...
    async def background_settings(self, interaction: discord.Interaction):
        await interaction.response.send_message("Background settings coming soon!", ephemeral=True)

    async def text_settings(self, interaction: discord.Interaction):
        await interaction.response.send_message("Text settings coming soon!", ephemeral=True)

    async def outline_settings(self, interaction: discord.Interaction):
        await interaction.response.send_message("Outline settings coming soon!", ephemeral=True)

    async def back_to_notification(self, interaction: discord.Interaction):
        view = LevelNotificationView(self.bot, interaction.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

import discord
from discord.ext import commands
from discord import app_commands
import json
import aiohttp
import io
from PIL import Image, ImageDraw, ImageFont
import os
import uuid

# Import functions from leveling_system
from leveling_system import load_leveling_data, save_leveling_data, load_user_level_card_config, save_user_level_card_config

def load_notification_data():
    """Load notification settings from leveling_data.json"""
    data = load_leveling_data()
    if "notification_settings" not in data:
        data["notification_settings"] = {
            "enabled": True,
            "level_notifications": {
                "enabled": True,
                "cycle": 1,
                "level_card": {
                    "background_image": "https://raw.githubusercontent.com/TheBlueEL/pictures/refs/heads/main/LevelBar.png",
                    "background_color": [15, 17, 16],
                    "username_color": [255, 255, 255],
                    "level_text_color": [245, 55, 48],
                    "message1_color": [255, 255, 255],
                    "message2_color": [154, 154, 154],
                    "outline_enabled": True,
                    "outline_color": [255, 255, 255],
                    "outline_image": "https://raw.githubusercontent.com/TheBlueEL/pictures/refs/heads/main/ProfileOutline.png",
                    "positions": {
                        "username": {"x": 540, "y": 200, "font_size": 60},
                        "level_text": {"x": 540, "y": 280, "font_size": 80},
                        "message1": {"x": 540, "y": 400, "font_size": 40},
                        "message2": {"x": 540, "y": 460, "font_size": 30},
                        "avatar": {"x": 390, "y": 540, "size": 300},
                        "outline": {"x": 390, "y": 540, "size": 300}
                    }
                }
            },
            "role_notifications": {
                "enabled": False
            },
            "custom_notifications": {
                "enabled": False
            }
        }
        save_leveling_data(data)
    return data

def save_notification_data(data):
    """Save notification settings to leveling_data.json"""
    save_leveling_data(data)

class LevelNotificationSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
        """Resize image maintaining proportions and cropping from center"""
        try:
            scale_factor = max(target_width / image.width, target_height / image.height)
            new_width = int(image.width * scale_factor)
            new_height = int(image.height * scale_factor)
            resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            left = (new_width - target_width) // 2
            top = (new_height - target_height) // 2
            right = left + target_width
            bottom = top + target_height
            cropped_image = resized_image.crop((left, top, right, bottom))
            return cropped_image
        except Exception as e:
            print(f"Error resizing image proportionally: {e}")
            return image.resize((target_width, target_height), Image.Resampling.LANCZOS)

    async def create_level_notification_card(self, user, level):
        """Create level notification card (1080x1080)"""
        try:
            data = load_notification_data()
            config = data["notification_settings"]["level_notifications"]["level_card"]
            
            # Create 1080x1080 background
            bg_width = 1080
            bg_height = 1080
            
            # Create background
            if config.get("background_image") and config["background_image"] != "None":
                bg_data = await self.download_image(config["background_image"])
                if bg_data:
                    original_bg = Image.open(io.BytesIO(bg_data)).convert("RGBA")
                    background = self.resize_image_proportionally_centered(original_bg, bg_width, bg_height)
                else:
                    bg_color = tuple(config.get("background_color", [15, 17, 16])) + (255,)
                    background = Image.new("RGBA", (bg_width, bg_height), bg_color)
            else:
                bg_color = tuple(config.get("background_color", [15, 17, 16])) + (255,)
                background = Image.new("RGBA", (bg_width, bg_height), bg_color)

            # Download user avatar
            avatar_url = user.display_avatar.url
            avatar_data = await self.download_image(avatar_url)
            if avatar_data:
                avatar = Image.open(io.BytesIO(avatar_data)).convert("RGBA")
                avatar_size = config["positions"]["avatar"]["size"]
                avatar = avatar.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                
                # Make avatar circular
                mask = self.create_circle_mask((avatar_size, avatar_size))
                avatar.putalpha(mask)
                
                # Paste avatar at center
                avatar_x = config["positions"]["avatar"]["x"]
                avatar_y = config["positions"]["avatar"]["y"]
                background.paste(avatar, (avatar_x, avatar_y), avatar)
                
                # Add outline if enabled
                if config.get("outline_enabled", True):
                    outline_url = config.get("outline_image", "https://raw.githubusercontent.com/TheBlueEL/pictures/refs/heads/main/ProfileOutline.png")
                    outline_data = await self.download_image(outline_url)
                    if outline_data:
                        outline = Image.open(io.BytesIO(outline_data)).convert("RGBA")
                        outline_size = config["positions"]["outline"]["size"]
                        outline = outline.resize((outline_size, outline_size), Image.Resampling.LANCZOS)
                        
                        # Apply color if specified
                        if config.get("outline_color"):
                            color_override = config["outline_color"]
                            colored_outline = Image.new("RGBA", outline.size, tuple(color_override + [255]))
                            colored_outline.putalpha(outline.split()[-1])
                            outline = colored_outline
                        
                        outline_x = config["positions"]["outline"]["x"]
                        outline_y = config["positions"]["outline"]["y"]
                        background.paste(outline, (outline_x, outline_y), outline)

            # Draw text
            draw = ImageDraw.Draw(background)
            
            # Load fonts
            try:
                font_username = ImageFont.truetype("PlayPretend.otf", config["positions"]["username"]["font_size"])
                font_level = ImageFont.truetype("PlayPretend.otf", config["positions"]["level_text"]["font_size"])
                font_msg1 = ImageFont.truetype("PlayPretend.otf", config["positions"]["message1"]["font_size"])
                font_msg2 = ImageFont.truetype("PlayPretend.otf", config["positions"]["message2"]["font_size"])
            except IOError:
                try:
                    font_username = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", config["positions"]["username"]["font_size"])
                    font_level = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", config["positions"]["level_text"]["font_size"])
                    font_msg1 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", config["positions"]["message1"]["font_size"])
                    font_msg2 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", config["positions"]["message2"]["font_size"])
                except IOError:
                    font_username = ImageFont.load_default()
                    font_level = ImageFont.load_default()
                    font_msg1 = ImageFont.load_default()
                    font_msg2 = ImageFont.load_default()

            # Draw username (not display name)
            username = user.name
            username_color = tuple(config.get("username_color", [255, 255, 255]))
            draw.text((config["positions"]["username"]["x"], config["positions"]["username"]["y"]), 
                     username, font=font_username, fill=username_color, anchor="mm")

            # Draw level text
            level_text = f"LEVEL {level}"
            level_color = tuple(config.get("level_text_color", [245, 55, 48]))
            draw.text((config["positions"]["level_text"]["x"], config["positions"]["level_text"]["y"]), 
                     level_text, font=font_level, fill=level_color, anchor="mm")

            # Draw message 1
            message1 = "You just reached a new level !"
            msg1_color = tuple(config.get("message1_color", [255, 255, 255]))
            draw.text((config["positions"]["message1"]["x"], config["positions"]["message1"]["y"]), 
                     message1, font=font_msg1, fill=msg1_color, anchor="mm")

            # Draw message 2
            message2 = "Type /level for more information"
            msg2_color = tuple(config.get("message2_color", [154, 154, 154]))
            draw.text((config["positions"]["message2"]["x"], config["positions"]["message2"]["y"]), 
                     message2, font=font_msg2, fill=msg2_color, anchor="mm")

            output = io.BytesIO()
            background.save(output, format='PNG')
            output.seek(0)
            return output

        except Exception as e:
            print(f"Error creating level notification card: {e}")
            return None

    async def send_level_notification(self, user, level):
        """Send level notification to user"""
        try:
            data = load_notification_data()
            
            # Check if notifications are enabled
            if not data["notification_settings"]["enabled"]:
                return
            
            if not data["notification_settings"]["level_notifications"]["enabled"]:
                return
            
            # Check cycle (every X levels)
            cycle = data["notification_settings"]["level_notifications"]["cycle"]
            if level % cycle != 0:
                return
            
            # Create notification card
            notification_card = await self.create_level_notification_card(user, level)
            if notification_card:
                try:
                    # Send DM to user
                    dm_channel = await user.create_dm()
                    file = discord.File(notification_card, filename="level_notification.png")
                    
                    embed = discord.Embed(
                        title=f"🎉 Congratulations {user.name}!",
                        description=f"You have reached **Level {level}**!",
                        color=discord.Color.gold()
                    )
                    embed.set_image(url="attachment://level_notification.png")
                    
                    await dm_channel.send(embed=embed, file=file)
                    
                except discord.Forbidden:
                    # User has DMs disabled, skip notification
                    pass
                except Exception as e:
                    print(f"Error sending level notification: {e}")
        
        except Exception as e:
            print(f"Error in send_level_notification: {e}")

# View classes for notification settings
class NotificationSettingsView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user

    def get_embed(self):
        data = load_notification_data()
        settings = data["notification_settings"]
        
        embed = discord.Embed(
            title="🔔 Notification Settings",
            description="Configure level up notifications:",
            color=0xFFFFFF
        )
        
        status = "<:OnLOGO:1407072463883472978> Enabled" if settings["enabled"] else "<:OffLOGO:1407072621836894380> Disabled"
        embed.add_field(name="Notifications Status", value=status, inline=True)
        
        level_status = "<:OnLOGO:1407072463883472978> Enabled" if settings["level_notifications"]["enabled"] else "<:OffLOGO:1407072621836894380> Disabled"
        embed.add_field(name="Level Notifications", value=level_status, inline=True)
        
        cycle = settings["level_notifications"]["cycle"]
        embed.add_field(name="Notification Cycle", value=f"Every {cycle} level(s)", inline=True)
        
        return embed

    @discord.ui.button(label="Level Notification", style=discord.ButtonStyle.secondary, emoji="<a:XPLOGO:1409634015043915827>")
    async def level_notification(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = LevelNotificationView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Role Notification", style=discord.ButtonStyle.secondary, emoji="<:ParticipantsLOGO:1407733929389199460>", disabled=True)
    async def role_notification(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Role notifications coming soon!", ephemeral=True)

    @discord.ui.button(label="Custom Notification", style=discord.ButtonStyle.secondary, emoji="<:TotalLOGO:1408245313755545752>", disabled=True)
    async def custom_notification(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Custom notifications coming soon!", ephemeral=True)

    @discord.ui.button(label="ON", style=discord.ButtonStyle.success, emoji="<:OnLOGO:1407072463883472978>")
    async def toggle_notifications(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_notification_data()
        current_state = data["notification_settings"]["enabled"]
        data["notification_settings"]["enabled"] = not current_state
        save_notification_data(data)
        
        if data["notification_settings"]["enabled"]:
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
        from leveling_system import LevelSystemMainView
        view = LevelSystemMainView(self.bot, self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class LevelNotificationView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user

    def get_embed(self):
        data = load_notification_data()
        settings = data["notification_settings"]["level_notifications"]
        
        embed = discord.Embed(
            title="<a:XPLOGO:1409634015043915827> Level Notification Settings",
            description="Configure level up notification settings:",
            color=0xFFFFFF
        )
        
        status = "<:OnLOGO:1407072463883472978> Enabled" if settings["enabled"] else "<:OffLOGO:1407072621836894380> Disabled"
        embed.add_field(name="Status", value=status, inline=True)
        
        cycle = settings["cycle"]
        embed.add_field(name="Notification Cycle", value=f"Every {cycle} level(s)", inline=True)
        
        return embed

    @discord.ui.button(label="Cycle", style=discord.ButtonStyle.secondary, emoji="<:UpdateLOGO:1407072818214080695>")
    async def cycle_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = NotificationCycleModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Level Card", style=discord.ButtonStyle.secondary, emoji="<:CardLOGO:1409586383047233536>")
    async def level_card_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        view = LevelNotificationCardView(self.bot, interaction.user.id)
        view.guild = interaction.guild
        
        # Generate preview image
        await view.generate_preview_image(interaction.user)
        
        embed = view.get_main_embed()
        view.update_buttons()
        
        await interaction.edit_original_response(embed=embed, view=view)

    @discord.ui.button(label="ON", style=discord.ButtonStyle.success, emoji="<:OnLOGO:1407072463883472978>")
    async def toggle_level_notifications(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_notification_data()
        current_state = data["notification_settings"]["level_notifications"]["enabled"]
        data["notification_settings"]["level_notifications"]["enabled"] = not current_state
        save_notification_data(data)
        
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

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1407071474233114766>")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = NotificationSettingsView(self.bot, self.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class NotificationCycleModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Set Notification Cycle")
        
        data = load_notification_data()
        max_level = data.get("level_settings", {}).get("max_level", 100)
        
        self.cycle = discord.ui.TextInput(
            label=f"Cycle (1-{max_level})",
            placeholder=f"Enter notification cycle (1-{max_level})...",
            default=str(data["notification_settings"]["level_notifications"]["cycle"]),
            min_length=1,
            max_length=3
        )
        self.add_item(self.cycle)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            data = load_notification_data()
            max_level = data.get("level_settings", {}).get("max_level", 100)
            cycle_value = int(self.cycle.value)
            
            if 1 <= cycle_value <= max_level:
                data["notification_settings"]["level_notifications"]["cycle"] = cycle_value
                save_notification_data(data)
                await interaction.response.send_message(f"<:SucessLOGO:1407071637840592977> Notification cycle set to every {cycle_value} level(s)!", ephemeral=True)
            else:
                await interaction.response.send_message(f"<:ErrorLOGO:1407071682031648850> Cycle must be between 1 and {max_level}!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Please enter a valid number!", ephemeral=True)

# Level Notification Card Manager View (similar to LevelCardManagerView but for notifications)
class LevelNotificationCardView(discord.ui.View):
    def __init__(self, bot, user_id):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        data = load_notification_data()
        self.config = data["notification_settings"]["level_notifications"]["level_card"]
        self.mode = "main"
        self.waiting_for_image = False
        self.current_image_type = None
        self.preview_image_url = None

    def get_main_embed(self):
        embed = discord.Embed(
            title="<:CardLOGO:1409586383047233536> Level Notification Card Manager",
            description="Configure your level notification card design (1080x1080)",
            color=0xFFFFFF
        )
        
        # Show current configuration status
        config_status = ""
        if self.config.get("background_image"):
            config_status += "<:BackgroundLOGO:1408834163309805579> Background: Custom Image\n"
        elif self.config.get("background_color"):
            bg = self.config["background_color"]
            config_status += f"<:BackgroundLOGO:1408834163309805579> Background: RGB({bg[0]}, {bg[1]}, {bg[2]})\n"
        
        if self.config.get("outline_enabled", True):
            config_status += "<:ProfileLOGO:1408830057819930806> Outline: <:OnLOGO:1407072463883472978> Enabled\n"
        else:
            config_status += "<:ProfileLOGO:1408830057819930806> Outline: <:OffLOGO:1407072621836894380> Disabled\n"
        
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
        
        embed.set_footer(text="Level Notification Card Manager", icon_url=self.bot.user.display_avatar.url)
        return embed

    def save_config(self):
        """Save the current configuration to JSON file"""
        data = load_notification_data()
        data["notification_settings"]["level_notifications"]["level_card"] = self.config
        save_notification_data(data)

    async def generate_preview_image(self, interaction_user):
        """Generate preview image and upload it to GitHub"""
        try:
            notification_system = self.bot.get_cog('LevelNotificationSystem')
            if not notification_system:
                return False

            preview_image = await notification_system.create_level_notification_card(interaction_user, 50)

            if preview_image:
                # Save preview to temp file
                os.makedirs('images', exist_ok=True)
                import time
                timestamp = int(time.time())
                filename = f"notification_preview_{self.user_id}_{timestamp}.png"
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
                label="Text",
                style=discord.ButtonStyle.secondary,
                emoji="<:DescriptionLOGO:1407733417172533299>",
                row=0
            )
            text_button.callback = self.text_settings
            
            outline_button = discord.ui.Button(
                label="Outline",
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
            back_button.callback = self.back_to_level_notification
            
            self.add_item(background_button)
            self.add_item(text_button)
            self.add_item(outline_button)
            self.add_item(back_button)

    async def background_settings(self, interaction: discord.Interaction):
        # Implementation similar to original background settings
        await interaction.response.send_message("Background settings coming soon!", ephemeral=True)

    async def text_settings(self, interaction: discord.Interaction):
        # Implementation for text color settings
        await interaction.response.send_message("Text settings coming soon!", ephemeral=True)

    async def outline_settings(self, interaction: discord.Interaction):
        # Implementation for outline settings
        await interaction.response.send_message("Outline settings coming soon!", ephemeral=True)

    async def back_to_level_notification(self, interaction: discord.Interaction):
        view = LevelNotificationView(self.bot, interaction.user)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(LevelNotificationSystem(bot))

import discord
from discord.ext import commands
from discord import app_commands
import json
import aiohttp
import io
from PIL import Image, ImageDraw, ImageFont, ImageOps
import time
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
                            "outline_position": {"x": 190, "y": 190, "size": 300},
                            "text_outline_enabled": True,
                            "text_outline_color": [0, 0, 0],
                            "text_outline_width": 2
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
                        "outline_position": {"x": 190, "y": 190, "size": 300},
                        "text_outline_enabled": True,
                        "text_outline_color": [0, 0, 0],
                        "text_outline_width": 2
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

        # Add message listener for image uploads
        if not hasattr(bot, '_notification_image_listeners'):
            bot._notification_image_listeners = {}
        # Register with user ID for consistency
        user_id = user.id if hasattr(user, 'id') else user
        bot._notification_image_listeners[user_id] = self

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
            if hasattr(item, 'callback') and hasattr(item.callback, 'callback') and item.callback.callback.__name__ == 'toggle_level_notifications':
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
        # Ensure user_id is always an integer
        self.user_id = user_id.id if hasattr(user_id, 'id') else user_id
        self.mode = "main"
        self.waiting_for_image = False
        self.current_image_type = None
        self.preview_image_url = None

        # Add message listener for image uploads
        if not hasattr(bot, '_notification_image_listeners'):
            bot._notification_image_listeners = {}
        bot._notification_image_listeners[self.user_id] = self

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

        # Sauvegarder aussi dans embed_command.json pour compatibilité
        try:
            with open('embed_command.json', 'r') as f:
                embed_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            embed_data = {"created": [], "published": []}

        # Mettre à jour avec les données du notification card
        notification_card_entry = {
            "id": f"notification_card_{self.user_id}",
            "type": "notification_card",
            "user_id": self.user_id,
            "config": config,
            "timestamp": time.time()
        }

        # Chercher si une entrée existe déjà pour cet utilisateur
        existing_index = None
        for i, entry in enumerate(embed_data["created"]):
            if isinstance(entry, dict) and entry.get("type") == "notification_card" and entry.get("user_id") == self.user_id:
                existing_index = i
                break

        if existing_index is not None:
            embed_data["created"][existing_index] = notification_card_entry
        else:
            embed_data["created"].append(notification_card_entry)

        with open('embed_command.json', 'w') as f:
            json.dump(embed_data, f, indent=2)

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

        text_outline_enabled = config.get("text_outline_enabled", True)
        text_outline_status = "<:OnLOGO:1407072463883472978> Enabled" if text_outline_enabled else "<:OffLOGO:1407072621836894380> Disabled"
        config_status += f"<:DescriptionLOGO:1407733417172533299> Text Outline: {text_outline_status}\n"

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

    def get_background_embed(self):
        embed = discord.Embed(
            title="<:BackgroundLOGO:1408834163309805579> Background Settings",
            description="Configure the background of your notification card",
            color=0xFFFFFF
        )

        config = self.get_config()
        if config.get("background_color"):
            bg = config["background_color"]
            embed.add_field(
                name="Current Background",
                value=f"Color: RGB({bg[0]}, {bg[1]}, {bg[2]})",
                inline=False
            )
        elif config.get("background_image"):
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

        return embed

    def get_profile_outline_embed(self):
        embed = discord.Embed(
            title="<:ProfileLOGO:1408830057819930806> Profile Outline Settings",
            description="Configure the profile picture outline",
            color=0xFFFFFF
        )

        config = self.get_config()
        outline_enabled = config.get("outline_enabled", True)
        outline_status = "<:OnLOGO:1407072463883472978> Enabled" if outline_enabled else "<:OffLOGO:1407072621836894380> Disabled"

        embed.add_field(name="Status", value=outline_status, inline=True)

        if config.get("outline_color"):
            color = config["outline_color"]
            embed.add_field(
                name="Color",
                value=f"RGB({color[0]}, {color[1]}, {color[2]})",
                inline=True
            )

        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

        return embed

    def get_text_settings_embed(self):
        embed = discord.Embed(
            title="<:DescriptionLOGO:1407733417172533299> Text Settings",
            description="Configure text elements of the notification card",
            color=0xFFFFFF
        )

        config = self.get_config()
        text_outline_enabled = config.get("text_outline_enabled", True)
        text_outline_status = "<:OnLOGO:1407072463883472978> Enabled" if text_outline_enabled else "<:OffLOGO:1407072621836894380> Disabled"

        embed.add_field(name="Text Outline", value=text_outline_status, inline=True)

        if config.get("text_outline_color"):
            color = config["text_outline_color"]
            embed.add_field(
                name="Outline Color",
                value=f"RGB({color[0]}, {color[1]}, {color[2]})",
                inline=True
            )

        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

        return embed

    def get_text_element_embed(self, element_type):
        config = self.get_config()

        if element_type == "level":
            embed = discord.Embed(
                title="<a:XPLOGO:1409634015043915827> Level Text Settings",
                description="Configure the level text display",
                color=0xFFFFFF
            )
            color = config.get("level_text_color", [255, 255, 255])
        elif element_type == "username":
            embed = discord.Embed(
                title="<:ParticipantsLOGO:1407733929389199460> Username Text Settings", 
                description="Configure the username text display",
                color=0xFFFFFF
            )
            color = config.get("username_color", [255, 255, 255])
        elif element_type == "messages":
            embed = discord.Embed(
                title="<:MessagesLOGO:1409586848577093837> Message Text Settings",
                description="Configure the message text display",
                color=0xFFFFFF
            )
            color = config.get("message_text_color", [255, 255, 255])
        elif element_type == "information":
            embed = discord.Embed(
                title="<:InfoLOGO:1409635426507583508> Information Text Settings",
                description="Configure the information text display", 
                color=0xFFFFFF
            )
            color = config.get("info_text_color", [200, 200, 200])

        embed.add_field(
            name="Current Color",
            value=f"RGB({color[0]}, {color[1]}, {color[2]})",
            inline=False
        )

        if hasattr(self, 'preview_image_url') and self.preview_image_url:
            embed.set_image(url=self.preview_image_url)

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

    async def upload_image_to_discord_channel(self, image_url):
        """Upload image to specific Discord channel and return Discord URL"""
        try:
            TARGET_CHANNEL_ID = 1409970452570312819  # Canal Discord pour stocker les images

            # Get the target channel
            channel = self.bot.get_channel(TARGET_CHANNEL_ID)
            if not channel:
                print(f"❌ [NOTIFICATION] Canal {TARGET_CHANNEL_ID} introuvable")
                return None

            # Download the image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        image_data = await response.read()

                        # Determine file extension
                        content_type = response.headers.get('content-type', '')
                        if 'gif' in content_type:
                            filename = f"notification_image_{uuid.uuid4()}.gif"
                        elif 'png' in content_type:
                            filename = f"notification_image_{uuid.uuid4()}.png"
                        elif 'jpeg' in content_type or 'jpg' in content_type:
                            filename = f"notification_image_{uuid.uuid4()}.jpg"
                        else:
                            filename = f"notification_image_{uuid.uuid4()}.png"

                        # Create Discord file
                        discord_file = discord.File(io.BytesIO(image_data), filename=filename)

                        # Send to Discord channel
                        message = await channel.send(file=discord_file)

                        # Get the Discord attachment URL
                        if message.attachments:
                            discord_url = message.attachments[0].url
                            print(f"✅ [NOTIFICATION] Image uploadée vers Discord: {discord_url}")
                            return discord_url

            return None
        except Exception as e:
            print(f"❌ [NOTIFICATION] Erreur upload Discord: {e}")
            return None

    def resize_image_proportionally_centered(self, image, target_width, target_height):
        """Resize image maintaining proportions and cropping from center"""
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

    async def create_text_with_image_overlay(self, text, font, color, image_url=None, text_width=None, text_height=None):
        """Create text with optional image overlay for notification cards"""
        try:
            # Create text surface
            if text_width is None or text_height is None:
                text_bbox = font.getbbox(text)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]

            # Add padding
            padding = 30
            canvas_width = text_width + (padding * 2)
            canvas_height = text_height + (padding * 2)

            if image_url and image_url != "None":
                # Download overlay image
                overlay_data = await self.download_image(image_url)
                if overlay_data:
                    overlay_img = Image.open(io.BytesIO(overlay_data)).convert("RGBA")

                    # Create text mask first
                    text_mask = Image.new('L', (canvas_width, canvas_height), 0)
                    mask_draw = ImageDraw.Draw(text_mask)
                    text_x = padding
                    text_y = padding
                    mask_draw.text((text_x, text_y), text, font=font, fill=255)

                    # Resize and crop overlay image to fit text zone proportionally
                    overlay_resized = self.resize_image_proportionally_centered(
                        overlay_img, canvas_width, canvas_height
                    )

                    # Create final result
                    result = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))

                    # Apply texture only to text pixels
                    import numpy as np
                    mask_array = np.array(text_mask)
                    overlay_array = np.array(overlay_resized)
                    result_array = np.array(result)

                    # Copy pixels where mask is not 0 (text area)
                    text_pixels = mask_array > 0
                    result_array[text_pixels] = overlay_array[text_pixels]
                    result_array[:, :, 3] = mask_array

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

    def create_circle_mask(self, size):
        """Create circular mask for profile picture"""
        mask = Image.new('L', size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size[0], size[1]), fill=255)
        return mask

    def draw_text_with_outline(self, draw, text, position, font, color, outline_color, outline_width):
        """Draw text with outline"""
        x, y = position

        # Draw outline
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), text, font=font, fill=outline_color)

        # Draw main text
        draw.text((x, y), text, font=font, fill=color)

    

    async def handle_image_upload(self, message, view):
        """Handle image uploads for notification card customization"""
        try:
            print(f"📤 [UPLOAD IMAGE] Détection d'un message de {message.author.name} (ID: {message.author.id})")
            print(f"📤 [UPLOAD IMAGE] User attendu: {view.user_id}")
            print(f"📤 [UPLOAD IMAGE] Nombre d'attachements: {len(message.attachments)}")
            print(f"📤 [UPLOAD IMAGE] Mode d'attente d'image: {getattr(view, 'waiting_for_image', False)}")
            print(f"📤 [UPLOAD IMAGE] Type d'image actuel: {getattr(view, 'current_image_type', 'None')}")

            # Check if this is the right user
            expected_user_id = view.user_id.id if hasattr(view.user_id, 'id') else view.user_id
            if message.author.id != expected_user_id:
                print(f"❌ [UPLOAD IMAGE] Utilisateur incorrect - Attendu: {expected_user_id}, Reçu: {message.author.id}")
                return False

            if not message.attachments:
                print(f"❌ [UPLOAD IMAGE] Aucun attachement trouvé dans le message")
                return False

            attachment = message.attachments[0]
            allowed_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg']
            print(f"📤 [UPLOAD IMAGE] Fichier détecté: {attachment.filename}")
            print(f"📤 [UPLOAD IMAGE] Taille du fichier: {attachment.size} bytes ({attachment.size / 1024 / 1024:.2f} MB)")
            print(f"📤 [UPLOAD IMAGE] URL de l'attachement: {attachment.url}")
            print(f"📤 [UPLOAD IMAGE] Content Type: {getattr(attachment, 'content_type', 'unknown')}")

            # Check file size (Discord max is 25MB for regular users, 100MB for Nitro)
            max_size = 100 * 1024 * 1024  # 100MB in bytes
            if attachment.size > max_size:
                print(f"❌ [UPLOAD IMAGE] Fichier trop volumineux: {attachment.size} bytes (max: {max_size})")
                error_embed = discord.Embed(
                    title="<:ErrorLOGO:1407071682031648850> File Too Large",
                    description=f"File size is {attachment.size / 1024 / 1024:.2f}MB. Maximum allowed is {max_size / 1024 / 1024}MB.",
                    color=discord.Color.red()
                )
                await message.channel.send(embed=error_embed, delete_after=5)
                return False

            if not any(attachment.filename.lower().endswith(ext) for ext in allowed_extensions):
                # Invalid file type
                print(f"❌ [UPLOAD IMAGE] Type de fichier invalide: {attachment.filename}")
                try:
                    await message.delete()
                    print(f"✅ [UPLOAD IMAGE] Message supprimé avec succès")
                except Exception as e:
                    print(f"❌ [UPLOAD IMAGE] Erreur lors de la suppression du message: {e}")

                error_embed = discord.Embed(
                    title="<:ErrorLOGO:1407071682031648850> Invalid File Type",
                    description="Please upload only image files with these extensions:\n`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp`, `.svg`",
                    color=discord.Color.red()
                )
                await message.channel.send(embed=error_embed, delete_after=5)
                print(f"📤 [UPLOAD IMAGE] Message d'erreur envoyé pour type de fichier invalide")
                return False

            print(f"✅ [UPLOAD IMAGE] Type de fichier valide: {attachment.filename}")

            # Delete the uploaded message first
            try:
                await message.delete()
                print(f"✅ [UPLOAD IMAGE] Message original supprimé avec succès")
            except Exception as e:
                print(f"❌ [UPLOAD IMAGE] Erreur lors de la suppression du message original: {e}")

            # Process the image directly from attachment URL
            config = view.get_config()
            print(f"📤 [UPLOAD IMAGE] Configuration chargée, type d'image: {view.current_image_type}")

            # Skip URL verification since Discord URLs expire quickly
            print(f"🌐 [UPLOAD IMAGE] Passage direct à l'upload Discord (pas de vérification URL)")

            if view.current_image_type == "background":
                print(f"🖼️ [UPLOAD IMAGE] Traitement d'une image de fond")
                # For background, download and process image with proportional resizing to fill 1080x1080
                try:
                    print(f"⬇️ [UPLOAD IMAGE] Téléchargement de l'image depuis attachment directement")

                    # Read attachment data directly 
                    image_data = await attachment.read()
                    print(f"✅ [UPLOAD IMAGE] Image téléchargée avec succès ({len(image_data)} bytes)")

                    # Validate image data
                    if len(image_data) < 100:  # Minimum reasonable image size
                        raise Exception(f"Image data too small: {len(image_data)} bytes")

                    # Open and process image
                    print(f"🔄 [UPLOAD IMAGE] Ouverture de l'image...")
                    try:
                        custom_image = Image.open(io.BytesIO(image_data)).convert("RGBA")
                        print(f"✅ [UPLOAD IMAGE] Image ouverte: {custom_image.size[0]}x{custom_image.size[1]} pixels, mode: {custom_image.mode}")
                    except Exception as pil_error:
                        print(f"❌ [UPLOAD IMAGE] Erreur PIL lors de l'ouverture: {pil_error}")
                        raise Exception(f"Invalid image format: {pil_error}")

                    # Use centered proportional resizing for background (1080x1080)
                    print(f"🔄 [UPLOAD IMAGE] Redimensionnement proportionnel vers 1080x1080")
                    try:
                        processed_image = view.resize_image_proportionally_centered(
                            custom_image, 1080, 1080
                        )
                        print(f"✅ [UPLOAD IMAGE] Image redimensionnée avec succès: {processed_image.size}")
                    except Exception as resize_error:
                        print(f"❌ [UPLOAD IMAGE] Erreur lors du redimensionnement: {resize_error}")
                        raise Exception(f"Failed to resize image: {resize_error}")

                    # Upload processed image to Discord directly
                    try:
                        print(f"☁️ [UPLOAD IMAGE] Upload vers Discord...")
                        
                        # Convert the processed PIL image to bytes
                        img_byte_arr = io.BytesIO()
                        processed_image.save(img_byte_arr, format='PNG')
                        img_byte_arr.seek(0)

                        # Get the target channel
                        TARGET_CHANNEL_ID = 1409970452570312819
                        channel = view.bot.get_channel(TARGET_CHANNEL_ID)
                        if not channel:
                            raise Exception(f"Canal {TARGET_CHANNEL_ID} introuvable")

                        # Create Discord file from processed image
                        filename = f"notification_bg_{uuid.uuid4()}.png"
                        discord_file = discord.File(img_byte_arr, filename=filename)

                        # Send to Discord channel
                        upload_message = await channel.send(file=discord_file)

                        # Get the Discord attachment URL
                        if upload_message.attachments:
                            discord_url = upload_message.attachments[0].url
                            config["background_image"] = discord_url
                            config.pop("background_color", None)
                            print(f"✅ [UPLOAD IMAGE] Configuration mise à jour avec URL Discord: {discord_url}")
                        else:
                            raise Exception("Aucun attachement trouvé dans le message Discord")

                    except Exception as discord_error:
                        print(f"❌ [UPLOAD IMAGE] Erreur Discord upload: {discord_error}")
                        raise Exception(f"Discord upload failed: {discord_error}")

                except Exception as e:
                    print(f"❌ [UPLOAD IMAGE] Erreur lors du traitement de l'image de fond: {e}")
                    import traceback
                    print(f"❌ [UPLOAD IMAGE] Traceback détaillé: {traceback.format_exc()}")

                    error_embed = discord.Embed(
                        title="<:ErrorLOGO:1407071682031648850> Processing Error",
                        description=f"Failed to process the background image:\n```{str(e)[:100]}...```\nPlease try again with a different image.",
                        color=discord.Color.red()
                    )
                    await message.channel.send(embed=error_embed, delete_after=10)
                    print(f"📤 [UPLOAD IMAGE] Message d'erreur détaillé envoyé")
                    return False

            elif view.current_image_type == "profile_outline":
                print(f"👤 [UPLOAD IMAGE] Traitement d'une image de contour de profil")
                # For profile outline, upload directly to Discord
                try:
                    image_data = await attachment.read()
                    TARGET_CHANNEL_ID = 1409970452570312819
                    channel = view.bot.get_channel(TARGET_CHANNEL_ID)
                    if not channel:
                        raise Exception(f"Canal {TARGET_CHANNEL_ID} introuvable")

                    filename = f"notification_outline_{uuid.uuid4()}.{attachment.filename.split('.')[-1]}"
                    discord_file = discord.File(io.BytesIO(image_data), filename=filename)
                    upload_message = await channel.send(file=discord_file)

                    if upload_message.attachments:
                        discord_url = upload_message.attachments[0].url
                        config["outline_image"] = discord_url
                        print(f"✅ [UPLOAD IMAGE] Image de contour de profil configurée: {discord_url}")
                    else:
                        raise Exception("Aucun attachement trouvé dans le message Discord")
                        
                except Exception as e:
                    print(f"❌ [UPLOAD IMAGE] Échec de l'upload de l'image de contour de profil: {e}")
                    error_embed = discord.Embed(
                        title="<:ErrorLOGO:1407071682031648850> Upload Error",
                        description="Failed to upload image. Please try again.",
                        color=discord.Color.red()
                    )
                    await message.channel.send(embed=error_embed, delete_after=5)
                    return False

            elif view.current_image_type in ["level_text", "username_text", "messages_text", "information_text"]:
                print(f"📝 [UPLOAD IMAGE] Traitement d'une image de texte: {view.current_image_type}")
                text_key = f"{view.current_image_type.replace('_text', '')}_text_image"
                print(f"📝 [UPLOAD IMAGE] Clé de configuration: {text_key}")

                # Upload directly to Discord
                try:
                    image_data = await attachment.read()
                    TARGET_CHANNEL_ID = 1409970452570312819
                    channel = view.bot.get_channel(TARGET_CHANNEL_ID)
                    if not channel:
                        raise Exception(f"Canal {TARGET_CHANNEL_ID} introuvable")

                    filename = f"notification_text_{uuid.uuid4()}.{attachment.filename.split('.')[-1]}"
                    discord_file = discord.File(io.BytesIO(image_data), filename=filename)
                    upload_message = await channel.send(file=discord_file)

                    if upload_message.attachments:
                        discord_url = upload_message.attachments[0].url
                        config[text_key] = discord_url
                        print(f"✅ [UPLOAD IMAGE] Image de texte configurée: {discord_url}")
                    else:
                        raise Exception("Aucun attachement trouvé dans le message Discord")
                        
                except Exception as e:
                    print(f"❌ [UPLOAD IMAGE] Échec de l'upload de l'image de texte: {e}")
                    error_embed = discord.Embed(
                        title="<:ErrorLOGO:1407071682031648850> Upload Error",
                        description="Failed to upload image. Please try again.",
                        color=discord.Color.red()
                    )
                    await message.channel.send(embed=error_embed, delete_after=5)
                    return False

            print(f"💾 [UPLOAD IMAGE] Sauvegarde de la configuration...")
            view.save_config(config)
            view.waiting_for_image = False
            print(f"✅ [UPLOAD IMAGE] Configuration sauvegardée, attente d'image désactivée")

            # Generate new preview
            print(f"🖼️ [UPLOAD IMAGE] Génération de la nouvelle prévisualisation...")
            await view.generate_preview_image(message.author)
            print(f"✅ [UPLOAD IMAGE] Prévisualisation générée")

            # Update view mode
            view.mode = view.current_image_type
            print(f"🔄 [UPLOAD IMAGE] Mode de vue mis à jour: {view.mode}")

            # Get appropriate embed
            if view.current_image_type == "background":
                embed = view.get_background_embed()
                embed.title = "<:SucessLOGO:1407071637840592977> Background Image Set"
                embed.description = "Your custom background image has been applied successfully!"
                print(f"📝 [UPLOAD IMAGE] Embed de succès créé pour image de fond")
            elif view.current_image_type == "profile_outline":
                embed = view.get_profile_outline_embed()
                embed.title = "<:SucessLOGO:1407071637840592977> Profile Outline Image Set"
                embed.description = "Your custom profile outline image has been applied successfully!"
                print(f"📝 [UPLOAD IMAGE] Embed de succès créé pour contour de profil")
            elif view.current_image_type in ["level_text", "username_text", "messages_text", "information_text"]:
                element_type = view.current_image_type.replace("_text", "")
                embed = view.get_text_element_embed(element_type)
                embed.title = f"<:SucessLOGO:1407071637840592977> {element_type.title()} Text Image Set"
                embed.description = f"Your custom {element_type} text image overlay has been applied successfully!"
                print(f"📝 [UPLOAD IMAGE] Embed de succès créé pour texte {element_type}")
            else:
                embed = view.get_main_embed()
                print(f"📝 [UPLOAD IMAGE] Embed principal par défaut créé")

            view.update_buttons()
            print(f"🔄 [UPLOAD IMAGE] Boutons mis à jour")

            # Find and update the original message
            try:
                print(f"🔍 [UPLOAD IMAGE] Recherche du message original à mettre à jour...")
                channel = message.channel
                updated = False
                async for msg in channel.history(limit=50):
                    if msg.author == view.bot.user and msg.embeds:
                        if "Upload Image" in msg.embeds[0].title:
                            await msg.edit(embed=embed, view=view)
                            print(f"✅ [UPLOAD IMAGE] Message original mis à jour avec succès")
                            updated = True
                            break

                if not updated:
                    print(f"⚠️ [UPLOAD IMAGE] Message original 'Upload Image' non trouvé dans les 50 derniers messages")

            except Exception as e:
                print(f"❌ [UPLOAD IMAGE] Erreur lors de la mise à jour du message: {e}")

            print(f"🎉 [UPLOAD IMAGE] Processus d'upload terminé avec succès!")
            return True

        except Exception as e:
            print(f"❌ [UPLOAD IMAGE] Erreur générale lors du traitement de l'upload: {e}")
            import traceback
            print(f"❌ [UPLOAD IMAGE] Traceback complet: {traceback.format_exc()}")
            return False

    

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

            # Text outline settings
            text_outline_enabled = config.get("text_outline_enabled", True)
            outline_color = tuple(config.get("text_outline_color", [0, 0, 0]))
            outline_width = config.get("text_outline_width", 2)

            # Draw username with optional image overlay
            username_pos = config.get("username_position", {"x": 540, "y": 200})
            username_color = tuple(config.get("username_color", [255, 255, 255]))
            username_text = user.name
            username_image_url = config.get("username_text_image")

            if username_image_url and username_image_url != "None":
                username_surface = await self.create_text_with_image_overlay(
                    username_text, font_username, username_color, username_image_url
                )
                background.paste(username_surface, 
                               (username_pos["x"] - 30, username_pos["y"] - 30), 
                               username_surface)
            else:
                if text_outline_enabled:
                    self.draw_text_with_outline(draw, username_text, (username_pos["x"], username_pos["y"]), 
                                              font_username, username_color, outline_color, outline_width)
                else:
                    draw.text((username_pos["x"], username_pos["y"]), username_text, font=font_username, fill=username_color)

            # Draw level with optional image overlay
            level_pos = config.get("level_position", {"x": 540, "y": 300})
            level_color = tuple(config.get("level_text_color", [255, 255, 255]))
            level_text = f"LEVEL {level}"
            level_image_url = config.get("level_text_image")

            if level_image_url and level_image_url != "None":
                level_surface = await self.create_text_with_image_overlay(
                    level_text, font_level, level_color, level_image_url
                )
                background.paste(level_surface, 
                               (level_pos["x"] - 30, level_pos["y"] - 30), 
                               level_surface)
            else:
                if text_outline_enabled:
                    self.draw_text_with_outline(draw, level_text, (level_pos["x"], level_pos["y"]), 
                                              font_level, level_color, outline_color, outline_width)
                else:
                    draw.text((level_pos["x"], level_pos["y"]), level_text, font=font_level, fill=level_color)

            # Draw message with optional image overlay
            message_pos = config.get("message_position", {"x": 540, "y": 450})
            message_color = tuple(config.get("message_text_color", [255, 255, 255]))
            message_text = "You just reached a new level !"
            message_image_url = config.get("message_text_image")

            if message_image_url and message_image_url != "None":
                message_surface = await self.create_text_with_image_overlay(
                    message_text, font_message, message_color, message_image_url
                )
                background.paste(message_surface, 
                               (message_pos["x"] - 30, message_pos["y"] - 30), 
                               message_surface)
            else:
                if text_outline_enabled:
                    self.draw_text_with_outline(draw, message_text, (message_pos["x"], message_pos["y"]), 
                                              font_message, message_color, outline_color, outline_width)
                else:
                    draw.text((message_pos["x"], message_pos["y"]), message_text, font=font_message, fill=message_color)

            # Draw info with optional image overlay
            info_pos = config.get("info_position", {"x": 540, "y": 550})
            info_color = tuple(config.get("info_text_color", [200, 200, 200]))
            info_text = "Type /level for more information"
            info_image_url = config.get("information_text_image")

            if info_image_url and info_image_url != "None":
                info_surface = await self.create_text_with_image_overlay(
                    info_text, font_info, info_color, info_image_url
                )
                background.paste(info_surface, 
                               (info_pos["x"] - 30, info_pos["y"] - 30), 
                               info_surface)
            else:
                if text_outline_enabled:
                    self.draw_text_with_outline(draw, info_text, (info_pos["x"], info_pos["y"]), 
                                              font_info, info_color, outline_color, outline_width)
                else:
                    draw.text((info_pos["x"], info_pos["y"]), info_text, font=font_info, fill=info_color)

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

                # Upload to Discord
                try:
                    TARGET_CHANNEL_ID = 1409970452570312819
                    channel = self.bot.get_channel(TARGET_CHANNEL_ID)
                    if channel:
                        # Create Discord file
                        discord_file = discord.File(file_path, filename=filename)
                        
                        # Send to Discord channel
                        message = await channel.send(file=discord_file)
                        
                        # Get the Discord attachment URL
                        if message.attachments:
                            self.preview_image_url = f"{message.attachments[0].url}?t={timestamp}"
                            
                            # Delete local file
                            try:
                                os.remove(file_path)
                            except:
                                pass
                                
                            return True
                except Exception as e:
                    print(f"Discord upload error: {e}")

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

        elif self.mode == "main":
            # Main buttons
            background_button = discord.ui.Button(
                label="Background",
                style=discord.ButtonStyle.secondary,
                emoji="<:BackgroundLOGO:1408834163309805579>",
                row=0
            )
            background_button.callback = self.background_settings

            profile_outline_button = discord.ui.Button(
                label="Profile Outline",
                style=discord.ButtonStyle.secondary,
                emoji="<:ProfileLOGO:1408830057819930806>",
                row=0
            )
            profile_outline_button.callback = self.profile_outline_settings

            text_settings_button = discord.ui.Button(
                label="Text Settings",
                style=discord.ButtonStyle.secondary,
                emoji="<:DescriptionLOGO:1407733417172533299>",
                row=0
            )
            text_settings_button.callback = self.text_settings

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1407071474233114766>",
                row=1
            )
            back_button.callback = self.back_to_notification

            self.add_item(background_button)
            self.add_item(profile_outline_button)
            self.add_item(text_settings_button)
            self.add_item(back_button)

        elif self.mode == "background":
            # Background buttons
            color_button = discord.ui.Button(
                label="Color",
                style=discord.ButtonStyle.secondary,
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
                emoji="<:BackLOGO:1407071474233114766>"
            )
            back_button.callback = self.back_to_main

            self.add_item(color_button)
            self.add_item(image_button)
            self.add_item(back_button)

        elif self.mode == "profile_outline":
            # Profile outline buttons
            config = self.get_config()
            outline_enabled = config.get("outline_enabled", True)

            toggle_button = discord.ui.Button(
                label="ON" if outline_enabled else "OFF",
                style=discord.ButtonStyle.success if outline_enabled else discord.ButtonStyle.danger,
                emoji="<:OnLOGO:1407072463883472978>" if outline_enabled else "<:OffLOGO:1407072621836894380>"
            )
            toggle_button.callback = self.toggle_profile_outline

            color_button = discord.ui.Button(
                label="Color",
                style=discord.ButtonStyle.secondary,
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
                emoji="<:BackLOGO:1407071474233114766>"
            )
            back_button.callback = self.back_to_main

            self.add_item(toggle_button)
            self.add_item(color_button)
            self.add_item(image_button)
            self.add_item(back_button)

        elif self.mode == "text_settings":
            # Text settings buttons
            level_button = discord.ui.Button(
                label="Level",
                style=discord.ButtonStyle.secondary,
                emoji="<a:XPLOGO:1409634015043915827>",
                row=0
            )
            level_button.callback = self.level_text_settings

            username_button = discord.ui.Button(
                label="Username",
                style=discord.ButtonStyle.secondary,
                emoji="<:ParticipantsLOGO:1407733929389199460>",
                row=0
            )
            username_button.callback = self.username_text_settings

            messages_button = discord.ui.Button(
                label="Messages", 
                style=discord.ButtonStyle.secondary,
                emoji="<:MessagesLOGO:1409586848577093837>",
                row=1
            )
            messages_button.callback = self.messages_text_settings

            information_button = discord.ui.Button(
                label="Information",
                style=discord.ButtonStyle.secondary,
                emoji="<:InfoLOGO:1409635426507583508>", 
                row=1
            )
            information_button.callback = self.information_text_settings

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1407071474233114766>",
                row=2
            )
            back_button.callback = self.back_to_main

            self.add_item(level_button)
            self.add_item(username_button)
            self.add_item(messages_button)
            self.add_item(information_button)
            self.add_item(back_button)

        elif self.mode in ["level_text", "username_text", "messages_text", "information_text"]:
            # Text element buttons
            color_button = discord.ui.Button(
                label="Color",
                style=discord.ButtonStyle.secondary,
                emoji="<:ColorLOGO:1408828590241615883>"
            )
            color_button.callback = self.text_color_settings

            image_button = discord.ui.Button(
                label="Image",
                style=discord.ButtonStyle.secondary,
                emoji="<:ImageLOGO:1407072328134951043>"
            )
            image_button.callback = self.text_image_settings

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1407071474233114766>"
            )
            back_button.callback = self.back_to_text_settings

            self.add_item(color_button)
            self.add_item(image_button)
            self.add_item(back_button)

        elif self.mode.endswith("_color"):
            # Color settings buttons
            hex_button = discord.ui.Button(
                label="Hex Code",
                style=discord.ButtonStyle.secondary,
                emoji="<:HEXcodeLOGO:1408833347404304434>"
            )
            hex_button.callback = self.hex_color_modal

            rgb_button = discord.ui.Button(
                label="RGB Code",
                style=discord.ButtonStyle.secondary,
                emoji="<:RGBcodeLOGO:1408831982141575290>"
            )
            rgb_button.callback = self.rgb_color_modal

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1407071474233114766>"
            )
            back_button.callback = self.back_to_parent_mode

            self.add_item(hex_button)
            self.add_item(rgb_button)
            self.add_item(back_button)

        elif self.mode.endswith("_image"):
            # Image settings buttons
            url_button = discord.ui.Button(
                label="Set URL",
                style=discord.ButtonStyle.secondary,
                emoji="<:URLLOGO:1407071963809054931>"
            )
            url_button.callback = self.image_url_modal

            upload_button = discord.ui.Button(
                label="Upload Image",
                style=discord.ButtonStyle.secondary,
                emoji="<:UploadLOGO:1407072005567545478>"
            )
            upload_button.callback = self.upload_image

            # Show clear button if image exists
            config = self.get_config()
            has_image = False
            if self.mode == "background_image":
                has_image = config.get("background_image") and config["background_image"] != "None"
            elif self.mode == "profile_outline_image":
                has_image = config.get("outline_image") and config["outline_image"] != "None"
            elif self.mode.endswith("_text_image"):
                text_key = f"{self.mode.replace('_text_image', '')}_text_image"
                has_image = config.get(text_key) and config[text_key] != "None"

            if has_image:
                clear_button = discord.ui.Button(
                    label="Clear Image",
                    style=discord.ButtonStyle.danger,
                    emoji="<:DeleteLOGO:1407071421363916841>"
                )
                clear_button.callback = self.clear_image
                self.add_item(clear_button)

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1407071474233114766>"
            )
            back_button.callback = self.back_to_parent_mode

            self.add_item(url_button)
            self.add_item(upload_button)
            self.add_item(back_button)

    # Button callbacks
    async def background_settings(self, interaction: discord.Interaction):
        self.mode = "background"
        embed = self.get_background_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def profile_outline_settings(self, interaction: discord.Interaction):
        self.mode = "profile_outline"
        embed = self.get_profile_outline_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def text_settings(self, interaction: discord.Interaction):
        self.mode = "text_settings"
        embed = self.get_text_settings_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def background_color_settings(self, interaction: discord.Interaction):
        self.mode = "background_color"
        embed = self.get_background_embed()
        embed.title = "<:ColorLOGO:1408828590241615883> Background Color"
        embed.description = "Choose how to set your background color"
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def background_image_settings(self, interaction: discord.Interaction):
        self.mode = "background_image"
        embed = self.get_background_embed()
        embed.title = "<:ImageLOGO:1407072328134951043> Background Image"
        embed.description = "Set a custom background image"
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def profile_outline_color_settings(self, interaction: discord.Interaction):
        self.mode = "profile_outline_color"
        embed = self.get_profile_outline_embed()
        embed.title = "<:ColorLOGO:1408828590241615883> Profile Outline Color"
        embed.description = "Choose how to set your profile outline color"
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def profile_outline_image_settings(self, interaction: discord.Interaction):
        self.mode = "profile_outline_image"
        embed = self.get_profile_outline_embed()
        embed.title = "<:ImageLOGO:1407072328134951043> Profile Outline Image"
        embed.description = "Set a custom profile outline image"
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def toggle_profile_outline(self, interaction: discord.Interaction):
        await interaction.response.defer()
        config = self.get_config()
        config["outline_enabled"] = not config.get("outline_enabled", True)
        self.save_config(config)

        await self.generate_preview_image(interaction.user)
        embed = self.get_profile_outline_embed()
        self.update_buttons()
        await interaction.edit_original_response(embed=embed, view=self)

    async def level_text_settings(self, interaction: discord.Interaction):
        self.mode = "level_text"
        embed = self.get_text_element_embed("level")
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def username_text_settings(self, interaction: discord.Interaction):
        self.mode = "username_text"
        embed = self.get_text_element_embed("username")
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def messages_text_settings(self, interaction: discord.Interaction):
        self.mode = "messages_text"
        embed = self.get_text_element_embed("messages")
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def information_text_settings(self, interaction: discord.Interaction):
        self.mode = "information_text"
        embed = self.get_text_element_embed("information")
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def text_color_settings(self, interaction: discord.Interaction):
        self.mode = self.mode + "_color"
        embed = self.get_text_element_embed(self.mode.replace("_text_color", ""))
        embed.title = embed.title.replace("Settings", "Color")
        embed.description = "Choose how to set the text color"
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def text_image_settings(self, interaction: discord.Interaction):
        self.mode = self.mode + "_image"
        embed = self.get_text_element_embed(self.mode.replace("_text_image", ""))
        embed.title = embed.title.replace("Settings", "Image")
        embed.description = "Set a custom text image overlay"
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def hex_color_modal(self, interaction: discord.Interaction):
        modal = NotificationHexColorModal(self)
        await interaction.response.send_modal(modal)

    async def rgb_color_modal(self, interaction: discord.Interaction):
        modal = NotificationRGBColorModal(self)
        await interaction.response.send_modal(modal)

    async def image_url_modal(self, interaction: discord.Interaction):
        modal = NotificationImageURLModal(self)
        await interaction.response.send_modal(modal)

    async def upload_image(self, interaction: discord.Interaction):
        print(f"📤 [UPLOAD IMAGE] Bouton 'Upload Image' cliqué par {interaction.user.name} (ID: {interaction.user.id})")
        print(f"📤 [UPLOAD IMAGE] Mode actuel: {self.mode}")

        self.waiting_for_image = True
        self.current_image_type = self.mode.replace("_image", "")

        print(f"📤 [UPLOAD IMAGE] Attente d'image activée, type: {self.current_image_type}")
        print(f"📤 [UPLOAD IMAGE] User ID surveillé: {self.user_id}")

        embed = discord.Embed(
            title="<:UploadLOGO:1407072005567545478> Upload Image",
            description="Please send an image file in this channel.\n\n**Only you can upload the image for security reasons.**",
            color=0xFFFFFF
        )
        self.update_buttons()

        print(f"📤 [UPLOAD IMAGE] Embed 'Upload Image' affiché, en attente d'un fichier...")
        await interaction.response.edit_message(embed=embed, view=self)

    async def clear_image(self, interaction: discord.Interaction):
        await interaction.response.defer()

        config = self.get_config()

        if self.mode == "background_image":
            config.pop("background_image", None)
            # Restore default background color
            if "background_color" not in config:
                config["background_color"] = [245, 55, 48]
        elif self.mode == "profile_outline_image":
            config.pop("outline_image", None)
        elif self.mode.endswith("_text_image"):
            text_key = f"{self.mode.replace('_text_image', '')}_text_image"
            config.pop(text_key, None)

        self.save_config(config)
        await self.generate_preview_image(interaction.user)

        # Go back to appropriate embed
        self.mode = self.mode.replace("_image", "")
        if self.mode == "background":
            embed = self.get_background_embed()
        elif self.mode == "profile_outline":
            embed = self.get_profile_outline_embed()
        elif self.mode in ["level_text", "username_text", "messages_text", "information_text"]:
            element_type = self.mode.replace("_text", "")
            embed = self.get_text_element_embed(element_type)
        else:
            embed = self.get_main_embed()

        self.update_buttons()
        await interaction.edit_original_response(embed=embed, view=self)

    # Navigation callbacks
    async def back_to_main(self, interaction: discord.Interaction):
        self.mode = "main"
        embed = self.get_main_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def back_to_text_settings(self, interaction: discord.Interaction):
        self.mode = "text_settings"
        embed = self.get_text_settings_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def back_to_parent_mode(self, interaction: discord.Interaction):
        if self.mode.endswith("_color"):
            self.mode = self.mode.replace("_color", "")
        elif self.mode.endswith("_image"):
            self.mode = self.mode.replace("_image", "")

        if self.mode == "background":
            embed = self.get_background_embed()
        elif self.mode == "profile_outline":
            embed = self.get_profile_outline_embed()
        elif self.mode in ["level_text", "username_text", "messages_text", "information_text"]:
            element_type = self.mode.replace("_text", "")
            embed = self.get_text_element_embed(element_type)
        else:
            embed = self.get_main_embed()

        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def back_from_image_upload(self, interaction: discord.Interaction):
        self.waiting_for_image = False
        self.mode = self.current_image_type + "_image"

        if self.mode == "background_image":
            embed = self.get_background_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Background Image"
            embed.description = "Set a custom background image"
        elif self.mode == "profile_outline_image":
            embed = self.get_profile_outline_embed()
            embed.title = "<:ImageLOGO:1407072328134951043> Profile Outline Image"
            embed.description = "Set a custom profile outline image"
        else:
            embed = self.get_main_embed()

        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def back_to_notification(self, interaction: discord.Interaction):
        view = LevelNotificationView(self.bot, self.user_id)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

# Modal classes
class NotificationHexColorModal(discord.ui.Modal):
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
            config = self.view.get_config()

            if self.view.mode == "background_color":
                config["background_color"] = list(rgb)
                config.pop("background_image", None)
            elif self.view.mode == "profile_outline_color":
                config["outline_color"] = list(rgb)
            elif self.view.mode == "level_text_color":
                config["level_text_color"] = list(rgb)
            elif self.view.mode == "username_text_color":
                config["username_color"] = list(rgb)
            elif self.view.mode == "messages_text_color":
                config["message_text_color"] = list(rgb)
            elif self.view.mode == "information_text_color":
                config["info_text_color"] = list(rgb)

            self.view.save_config(config)
            await self.view.generate_preview_image(interaction.user)

            # Return to appropriate embed
            self.view.mode = self.view.mode.replace("_color", "")
            if self.view.mode == "background":
                embed = self.view.get_background_embed()
            elif self.view.mode == "profile_outline":
                embed = self.view.get_profile_outline_embed()
            elif self.view.mode in ["level_text", "username_text", "messages_text", "information_text"]:
                element_type = self.view.mode.replace("_text", "")
                embed = self.view.get_text_element_embed(element_type)

            self.view.update_buttons()
            await interaction.edit_original_response(embed=embed, view=self.view)

        except ValueError:
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid Hex Color",
                description="Please enter a valid hex color code (e.g., #FF0000 or FF0000)",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

class NotificationRGBColorModal(discord.ui.Modal):
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

            config = self.view.get_config()

            if self.view.mode == "background_color":
                config["background_color"] = [r, g, b]
                config.pop("background_image", None)
            elif self.view.mode == "profile_outline_color":
                config["outline_color"] = [r, g, b]
            elif self.view.mode == "level_text_color":
                config["level_text_color"] = [r, g, b]
            elif self.view.mode == "username_text_color":
                config["username_color"] = [r, g, b]
            elif self.view.mode == "messages_text_color":
                config["message_text_color"] = [r, g, b]
            elif self.view.mode == "information_text_color":
                config["info_text_color"] = [r, g, b]

            self.view.save_config(config)
            await self.view.generate_preview_image(interaction.user)

            # Return to appropriate embed
            self.view.mode = self.view.mode.replace("_color", "")
            if self.view.mode == "background":
                embed = self.view.get_background_embed()
            elif self.view.mode == "profile_outline":
                embed = self.view.get_profile_outline_embed()
            elif self.view.mode in ["level_text", "username_text", "messages_text", "information_text"]:
                element_type = self.view.mode.replace("_text", "")
                embed = self.view.get_text_element_embed(element_type)

            self.view.update_buttons()
            await interaction.edit_original_response(embed=embed, view=self.view)

        except ValueError:
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid RGB Values",
                description="Please enter valid RGB values (0-255 for each color)",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

class NotificationImageURLModal(discord.ui.Modal):
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

        config = self.view.get_config()

        if self.view.mode == "background_image":
            config["background_image"] = url
            config.pop("background_color", None)
        elif self.view.mode == "profile_outline_image":
            config["outline_image"] = url
        elif self.view.mode.endswith("_text_image"):
            # Handle text image overlays
            text_key = f"{self.view.mode.replace('_text_image', '')}_text_image"
            config[text_key] = url

        self.view.save_config(config)
        await self.view.generate_preview_image(interaction.user)

        # Return to appropriate embed
        self.view.mode = self.view.mode.replace("_image", "")
        if self.view.mode == "background":
            embed = self.view.get_background_embed()
        elif self.view.mode == "profile_outline":
            embed = self.view.get_profile_outline_embed()
        elif self.view.mode in ["level_text", "username_text", "messages_text", "information_text"]:
            element_type = self.view.mode.replace("_text", "")
            embed = self.view.get_text_element_embed(element_type)

        self.view.update_buttons()
        await interaction.edit_original_response(embed=embed, view=self.view)
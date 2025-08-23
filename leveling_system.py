
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
                    "xp_bar_position": {"x": 30, "y": 726, "width": 1988, "height": 30}
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
    return next_level_xp - current_level_xp, current_xp - current_level_xp

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

    async def create_level_card(self, user):
        """Create level card for user"""
        try:
            data = load_leveling_data()
            user_data = data["user_data"].get(str(user.id), {"xp": 0, "level": 1})
            config = data["leveling_settings"]["level_card"]
            
            # Create white background (2048x756)
            background = Image.new("RGBA", (2048, 756), (255, 255, 255, 255))
            
            # Download and add level bar image
            levelbar_data = await self.download_image(config["background_image"])
            if levelbar_data:
                levelbar = Image.open(io.BytesIO(levelbar_data)).convert("RGBA")
                # Position level bar in bottom right with 30px margin
                levelbar_x = 2048 - levelbar.width - 30
                levelbar_y = 756 - levelbar.height - 30
                background.paste(levelbar, (levelbar_x, levelbar_y), levelbar)
                
                # Create XP progress bar overlay
                xp_needed, current_xp_in_level = get_xp_for_next_level(user_data["xp"])
                if xp_needed > 0:
                    progress = current_xp_in_level / xp_needed
                else:
                    progress = 1.0
                
                # Create darker version of level bar for XP progress
                xp_bar = levelbar.copy()
                # Convert to darker color (darker gray)
                xp_data = list(xp_bar.getdata())
                new_xp_data = []
                for pixel in xp_data:
                    if len(pixel) == 4 and pixel[3] > 0:  # Si le pixel n'est pas transparent
                        # Appliquer une couleur plus foncée (gris foncé)
                        new_xp_data.append((100, 100, 100, pixel[3]))
                    else:
                        new_xp_data.append(pixel)
                xp_bar.putdata(new_xp_data)
                
                # Crop XP bar to show only progress percentage
                if progress > 0:
                    crop_width = int(levelbar.width * progress)
                    if crop_width > 0:
                        xp_bar_cropped = xp_bar.crop((0, 0, crop_width, levelbar.height))
                        background.paste(xp_bar_cropped, (levelbar_x, levelbar_y), xp_bar_cropped)
            
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
            
            # Draw text
            draw = ImageDraw.Draw(background)
            
            try:
                font_username = ImageFont.truetype("PlayPretend.otf", config["username_position"]["font_size"])
                font_level = ImageFont.truetype("PlayPretend.otf", config["level_position"]["font_size"])
            except:
                # Fallback vers les polices système si PlayPretend.otf n'est pas disponible
                try:
                    font_username = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", config["username_position"]["font_size"])
                    font_level = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", config["level_position"]["font_size"])
                except:
                    font_username = ImageFont.load_default()
                    font_level = ImageFont.load_default()
            
            # Draw username (en noir sur fond blanc)
            username = user.display_name
            draw.text((config["username_position"]["x"], config["username_position"]["y"]), 
                     username, font=font_username, fill=(0, 0, 0))
            
            # Draw level (en gris)
            level_text = f"LEVEL {user_data['level']}"
            username_bbox = draw.textbbox((0, 0), username, font=font_username)
            level_x = config["username_position"]["x"] + username_bbox[2] + 20
            draw.text((level_x, config["level_position"]["y"]), 
                     level_text, font=font_level, fill=(154, 154, 154))
            
            # Draw XP progress text
            xp_needed, current_xp_in_level = get_xp_for_next_level(user_data["xp"])
            total_xp_for_next = current_xp_in_level + xp_needed
            xp_text = f"{current_xp_in_level}/{total_xp_for_next} XP"
            
            try:
                font_xp = ImageFont.truetype("PlayPretend.otf", 40)
            except:
                # Fallback vers les polices système
                try:
                    font_xp = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
                except:
                    font_xp = ImageFont.load_default()
            
            # Position XP text below the level bar
            xp_text_x = config["xp_bar_position"]["x"]
            xp_text_y = config["xp_bar_position"]["y"] + config["xp_bar_position"]["height"] + 10
            draw.text((xp_text_x, xp_text_y), xp_text, font=font_xp, fill=(100, 100, 100))
            
            # Convert to bytes
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
            file = discord.File(level_card, filename="level_card.png")
            embed = discord.Embed(title=f"{interaction.user.display_name}'s Level Card", color=0x5865f2)
            embed.set_image(url="attachment://level_card.png")
            await interaction.followup.send(embed=embed, file=file)
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

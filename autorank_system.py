
import discord
from discord.ext import commands
import json
import re
from datetime import datetime

# File management functions
def load_autorank_data():
    try:
        with open('autorank_data.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"autoranks": {}}

def save_autorank_data(data):
    with open('autorank_data.json', 'w') as f:
        json.dump(data, f, indent=2)

# Main AutoRank Management View
class AutoRankMainView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user

    def get_main_embed(self):
        data = load_autorank_data()
        autoranks = data.get("autoranks", {})
        
        embed = discord.Embed(
            title="Auto-Rank Management",
            description=f"Welcome back {self.user.mention}!\n\nManage your server's auto-ranking system below:",
            color=0x5865f2
        )
        
        if autoranks:
            autorank_list = []
            for autorank_id, autorank in autoranks.items():
                role_mention = f"<@&{autorank['role_id']}>"
                autorank_type = autorank['type'].replace('_', ' ').title()
                autorank_list.append(f"• {role_mention} ({autorank_type})")
            
            embed.add_field(
                name="**AutoRank(s)**",
                value="\n".join(autorank_list),
                inline=False
            )
        else:
            embed.add_field(
                name="**AutoRank(s)**",
                value="No autoranks configured",
                inline=False
            )
            
        return embed

    @discord.ui.button(label='Create', style=discord.ButtonStyle.success, emoji='➕')
    async def create_autorank(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = AutoRankCreateView(self.user)
        embed = view.get_create_embed(interaction.client)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='Edit', style=discord.ButtonStyle.primary, emoji='✏️')
    async def edit_autorank(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_autorank_data()
        autoranks = data.get("autoranks", {})
        
        if not autoranks:
            await interaction.response.send_message("❌ No autoranks to edit!", ephemeral=True)
            return
            
        view = AutoRankEditView(self.user)
        embed = discord.Embed(
            title="✏️ Edit AutoRanks",
            description="Select an AutoRank to edit:",
            color=0xffa500
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='Delete', style=discord.ButtonStyle.danger, emoji='🗑️')
    async def delete_autorank(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_autorank_data()
        autoranks = data.get("autoranks", {})
        
        if not autoranks:
            await interaction.response.send_message("❌ No autoranks to delete!", ephemeral=True)
            return
            
        view = AutoRankDeleteView(self.user)
        await interaction.response.edit_message(embed=self.get_main_embed(), view=view)

# Create AutoRank View
class AutoRankCreateView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user
        self.add_item(AutoRankTypeSelect())
        self.add_item(BackToMainButton(user))

    def get_create_embed(self, client):
        embed = discord.Embed(
            title="🎯 Create New AutoRank",
            description="Choose the type of AutoRank you want to create:",
            color=0x5865f2
        )
        embed.set_footer(text="Wplace Pantheon - Automated Role Management")
        embed.set_thumbnail(url=client.user.display_avatar.url)
        return embed

# AutoRank Type Selection
class AutoRankTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="AutoRank New Members",
                value="new_members",
                description="Give roles to new server members",
                emoji="👋"
            ),
            discord.SelectOption(
                label="AutoRank Reaction",
                value="reaction",
                description="Give roles when users react to a message",
                emoji="⭐"
            ),
            discord.SelectOption(
                label="AutoRank Button",
                value="button",
                description="Give roles when users click a button",
                emoji="🔘"
            )
        ]
        super().__init__(placeholder="Select AutoRank type...", options=options)

    async def callback(self, interaction: discord.Interaction):
        autorank_type = self.values[0]
        
        if autorank_type == "new_members":
            view = NewMembersConfigView(self.view.user)
            embed = view.get_embed()
            await interaction.response.edit_message(embed=embed, view=view)
        elif autorank_type == "reaction":
            view = ReactionConfigView(self.view.user)
            embed = view.get_embed()
            await interaction.response.edit_message(embed=embed, view=view)
        elif autorank_type == "button":
            view = ButtonConfigView(self.view.user)
            embed = view.get_embed()
            await interaction.response.edit_message(embed=embed, view=view)

# New Members Configuration View
class NewMembersConfigView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user
        self.selected_role = None
        self.all_members_enabled = True
        self.update_view()

    def update_view(self):
        self.clear_items()
        self.add_item(RoleSelect(self))
        
        # All Members Toggle Button
        toggle_button = discord.ui.Button(
            label="All Members",
            style=discord.ButtonStyle.success if self.all_members_enabled else discord.ButtonStyle.danger,
            emoji="🟢" if self.all_members_enabled else "🔴"
        )
        toggle_button.callback = self.toggle_all_members
        self.add_item(toggle_button)
        
        if self.selected_role:
            confirm_button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
            confirm_button.callback = self.confirm_new_members
            self.add_item(confirm_button)
        
        self.add_item(BackToCreateButton(self.user))

    async def toggle_all_members(self, interaction: discord.Interaction):
        self.all_members_enabled = not self.all_members_enabled
        self.update_view()
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def confirm_new_members(self, interaction: discord.Interaction):
        data = load_autorank_data()
        autorank_id = str(len(data.get("autoranks", {})) + 1)
        
        if "autoranks" not in data:
            data["autoranks"] = {}
            
        data["autoranks"][autorank_id] = {
            "type": "new_members",
            "role_id": self.selected_role.id,
            "all_members": self.all_members_enabled,
            "created_at": datetime.now().isoformat()
        }
        
        save_autorank_data(data)
        
        # Apply to existing members if enabled
        if self.all_members_enabled:
            await self.apply_to_existing_members(interaction)
        
        view = AutoRankMainView(self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    async def apply_to_existing_members(self, interaction):
        try:
            guild = interaction.guild
            role = self.selected_role
            count = 0
            
            for member in guild.members:
                if not member.bot and role not in member.roles:
                    try:
                        await member.add_roles(role)
                        count += 1
                    except:
                        pass
                        
            if count > 0:
                await interaction.followup.send(f"✅ Applied role to {count} existing members!", ephemeral=True)
        except:
            pass

    def get_embed(self):
        embed = discord.Embed(
            title="👋 New Members AutoRank",
            description="Which role would you like to give to all new server members?",
            color=0x5865f2
        )
        
        if self.selected_role:
            embed.add_field(
                name="Selected Role",
                value=self.selected_role.mention,
                inline=False
            )
            
        status = "✅ Enabled" if self.all_members_enabled else "❌ Disabled"
        embed.add_field(
            name="Apply to Existing Members",
            value=f"{status} - Apply role to current server members (excluding bots)",
            inline=False
        )
        
        return embed

# Reaction Configuration View
class ReactionConfigView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user
        self.selected_role = None
        self.message_link = None
        self.update_view()

    def update_view(self):
        self.clear_items()
        self.add_item(RoleSelect(self))
        
        if self.selected_role:
            message_button = discord.ui.Button(label="Message Link", style=discord.ButtonStyle.primary, emoji="🔗")
            message_button.callback = self.set_message_link
            self.add_item(message_button)
            
            if self.message_link:
                confirm_button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
                confirm_button.callback = self.confirm_reaction
                self.add_item(confirm_button)
        
        self.add_item(BackToCreateButton(self.user))

    async def set_message_link(self, interaction: discord.Interaction):
        modal = MessageLinkModal(self)
        await interaction.response.send_modal(modal)

    async def confirm_reaction(self, interaction: discord.Interaction):
        data = load_autorank_data()
        autorank_id = str(len(data.get("autoranks", {})) + 1)
        
        if "autoranks" not in data:
            data["autoranks"] = {}
            
        # Parse message link
        parts = self.message_link.split('/')
        guild_id = int(parts[-3])
        channel_id = int(parts[-2])
        message_id = int(parts[-1])
        
        data["autoranks"][autorank_id] = {
            "type": "reaction",
            "role_id": self.selected_role.id,
            "guild_id": guild_id,
            "channel_id": channel_id,
            "message_id": message_id,
            "created_at": datetime.now().isoformat()
        }
        
        save_autorank_data(data)
        
        view = AutoRankMainView(self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    def get_embed(self):
        embed = discord.Embed(
            title="⭐ Reaction AutoRank",
            description="Which role would you like to give to members who react to a message?",
            color=0x5865f2
        )
        
        if self.selected_role:
            embed.add_field(
                name="Selected Role",
                value=self.selected_role.mention,
                inline=False
            )
            
        if self.message_link:
            embed.add_field(
                name="Message Link",
                value=f"[Jump to Message]({self.message_link})",
                inline=False
            )
            
        return embed

# Button Configuration View
class ButtonConfigView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user
        self.selected_role = None
        self.message_link = None
        self.button_color = "green"
        self.button_text = ""
        self.button_emoji = "<:ConfirmLOGO:1407072680267481249>"
        self.update_view()

    def update_view(self):
        self.clear_items()
        self.add_item(RoleSelect(self))
        
        if self.selected_role:
            # Button customization buttons
            color_button = discord.ui.Button(label="Button Color", style=discord.ButtonStyle.secondary, emoji="🎨")
            color_button.callback = self.set_button_color
            self.add_item(color_button)
            
            text_button = discord.ui.Button(label="Button Text", style=discord.ButtonStyle.secondary, emoji="📝")
            text_button.callback = self.set_button_text
            self.add_item(text_button)
            
            emoji_button = discord.ui.Button(label="Button Emoji", style=discord.ButtonStyle.secondary, emoji="😀")
            emoji_button.callback = self.set_button_emoji
            self.add_item(emoji_button)
            
            message_button = discord.ui.Button(label="Message Link", style=discord.ButtonStyle.primary, emoji="🔗")
            message_button.callback = self.set_message_link
            self.add_item(message_button)
            
            if self.message_link:
                confirm_button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
                confirm_button.callback = self.confirm_button
                self.add_item(confirm_button)
        
        self.add_item(BackToCreateButton(self.user))

    async def set_button_color(self, interaction: discord.Interaction):
        view = ButtonColorSelectView(self)
        embed = discord.Embed(
            title="🎨 Button Color",
            description="Choose the color for your button:",
            color=0x5865f2
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def set_button_text(self, interaction: discord.Interaction):
        modal = ButtonTextModal(self)
        await interaction.response.send_modal(modal)

    async def set_button_emoji(self, interaction: discord.Interaction):
        modal = ButtonEmojiModal(self)
        await interaction.response.send_modal(modal)

    async def set_message_link(self, interaction: discord.Interaction):
        modal = MessageLinkModal(self)
        await interaction.response.send_modal(modal)

    async def confirm_button(self, interaction: discord.Interaction):
        data = load_autorank_data()
        autorank_id = str(len(data.get("autoranks", {})) + 1)
        
        if "autoranks" not in data:
            data["autoranks"] = {}
            
        # Parse message link
        parts = self.message_link.split('/')
        guild_id = int(parts[-3])
        channel_id = int(parts[-2])
        message_id = int(parts[-1])
        
        data["autoranks"][autorank_id] = {
            "type": "button",
            "role_id": self.selected_role.id,
            "guild_id": guild_id,
            "channel_id": channel_id,
            "message_id": message_id,
            "button_color": self.button_color,
            "button_text": self.button_text,
            "button_emoji": self.button_emoji,
            "created_at": datetime.now().isoformat()
        }
        
        save_autorank_data(data)
        
        # Add button to message
        await self.add_button_to_message(interaction, data["autoranks"][autorank_id])
        
        view = AutoRankMainView(self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    async def add_button_to_message(self, interaction, autorank_data):
        try:
            channel = interaction.guild.get_channel(autorank_data["channel_id"])
            message = await channel.fetch_message(autorank_data["message_id"])
            
            style_map = {
                "blue": discord.ButtonStyle.primary,
                "green": discord.ButtonStyle.success,
                "red": discord.ButtonStyle.danger,
                "grey": discord.ButtonStyle.secondary
            }
            
            view = discord.ui.View(timeout=None)
            button = discord.ui.Button(
                label=autorank_data["button_text"] or None,
                style=style_map[autorank_data["button_color"]],
                emoji=autorank_data["button_emoji"],
                custom_id=f"autorank_button_{len(load_autorank_data().get('autoranks', {}))}"
            )
            view.add_item(button)
            
            await message.edit(view=view)
        except:
            pass

    def get_embed(self):
        embed = discord.Embed(
            title="🔘 Button AutoRank",
            description="Which role would you like to give to members who interact with a button?",
            color=0x5865f2
        )
        
        if self.selected_role:
            embed.add_field(
                name="Selected Role",
                value=self.selected_role.mention,
                inline=False
            )
            
        # Button preview
        color_emoji = {"blue": "🟦", "green": "🟩", "red": "🟥", "grey": "⬛"}
        preview = f"{color_emoji[self.button_color]} "
        if self.button_text:
            preview += f"**{self.button_text}** "
        preview += self.button_emoji
        
        embed.add_field(
            name="Button Preview",
            value=preview,
            inline=False
        )
            
        if self.message_link:
            embed.add_field(
                name="Message Link",
                value=f"[Jump to Message]({self.message_link})",
                inline=False
            )
            
        return embed

# Button Color Selection View
class ButtonColorSelectView(discord.ui.View):
    def __init__(self, parent_view):
        super().__init__(timeout=300)
        self.parent_view = parent_view
        self.add_item(ButtonColorSelect(parent_view))
        self.add_item(BackToButtonConfigButton(parent_view))

class ButtonColorSelect(discord.ui.Select):
    def __init__(self, parent_view):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(label="Blue", value="blue", emoji="🟦"),
            discord.SelectOption(label="Green", value="green", emoji="🟩"),
            discord.SelectOption(label="Red", value="red", emoji="🟥"),
            discord.SelectOption(label="Grey", value="grey", emoji="⬛")
        ]
        super().__init__(placeholder="Choose button color...", options=options)

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.button_color = self.values[0]
        self.parent_view.update_view()
        embed = self.parent_view.get_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

# Role Selection with Search
class RoleSelect(discord.ui.RoleSelect):
    def __init__(self, parent_view):
        self.parent_view = parent_view
        super().__init__(placeholder="Select a role...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.selected_role = self.values[0]
        self.parent_view.update_view()
        embed = self.parent_view.get_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

# Delete AutoRank View
class AutoRankDeleteView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user
        self.add_item(AutoRankDeleteSelect())
        self.add_item(BackToMainButton(user))

class AutoRankDeleteSelect(discord.ui.Select):
    def __init__(self):
        data = load_autorank_data()
        autoranks = data.get("autoranks", {})
        
        options = []
        for autorank_id, autorank in autoranks.items():
            autorank_type = autorank['type'].replace('_', ' ').title()
            options.append(discord.SelectOption(
                label=f"Role ID: {autorank['role_id']} ({autorank_type})",
                value=autorank_id,
                description=f"Created: {autorank.get('created_at', 'Unknown')[:10]}"
            ))
            
        super().__init__(placeholder="Select autorank to delete...", options=options)

    async def callback(self, interaction: discord.Interaction):
        data = load_autorank_data()
        del data["autoranks"][self.values[0]]
        save_autorank_data(data)
        
        view = AutoRankMainView(self.view.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

# Modals
class MessageLinkModal(discord.ui.Modal):
    def __init__(self, parent_view):
        super().__init__(title="Message Link")
        self.parent_view = parent_view

    message_link = discord.ui.TextInput(
        label="Message Link",
        placeholder="https://discord.com/channels/guild_id/channel_id/message_id",
        required=True,
        max_length=200
    )

    async def on_submit(self, interaction: discord.Interaction):
        link = self.message_link.value
        pattern = r'https://discord\.com/channels/\d+/\d+/\d+'
        
        if re.match(pattern, link):
            self.parent_view.message_link = link
            self.parent_view.update_view()
            embed = self.parent_view.get_embed()
            await interaction.response.edit_message(embed=embed, view=self.parent_view)
        else:
            await interaction.response.send_message("❌ Invalid message link format! Please use: https://discord.com/channels/guild_id/channel_id/message_id", ephemeral=True)

class ButtonTextModal(discord.ui.Modal):
    def __init__(self, parent_view):
        super().__init__(title="Button Text")
        self.parent_view = parent_view

    button_text = discord.ui.TextInput(
        label="Button Text",
        placeholder="Enter button text (optional)",
        required=False,
        max_length=80
    )

    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.button_text = self.button_text.value
        self.parent_view.update_view()
        embed = self.parent_view.get_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

class ButtonEmojiModal(discord.ui.Modal):
    def __init__(self, parent_view):
        super().__init__(title="Button Emoji")
        self.parent_view = parent_view

    button_emoji = discord.ui.TextInput(
        label="Button Emoji",
        placeholder="Enter emoji (Unicode or <:name:id>)",
        required=False,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        emoji = self.button_emoji.value or "<:ConfirmLOGO:1407072680267481249>"
        self.parent_view.button_emoji = emoji
        self.parent_view.update_view()
        embed = self.parent_view.get_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

# Navigation Buttons
class BackToMainButton(discord.ui.Button):
    def __init__(self, user):
        super().__init__(label="Back", style=discord.ButtonStyle.secondary, emoji="⬅️")
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        view = AutoRankMainView(self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class BackToCreateButton(discord.ui.Button):
    def __init__(self, user):
        super().__init__(label="Back", style=discord.ButtonStyle.secondary, emoji="⬅️")
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        view = AutoRankCreateView(self.user)
        embed = view.get_create_embed(interaction.client)
        await interaction.response.edit_message(embed=embed, view=view)

class BackToButtonConfigButton(discord.ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="Back", style=discord.ButtonStyle.secondary, emoji="⬅️")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        embed = self.parent_view.get_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

# Persistent AutoRank Button View for button autoranks
class PersistentAutoRankButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="", style=discord.ButtonStyle.success, custom_id="persistent_autorank_button")
    async def autorank_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle persistent autorank button clicks"""
        data = load_autorank_data()
        autoranks = data.get("autoranks", {})
        
        for autorank_id, autorank in autoranks.items():
            if (autorank["type"] == "button" and 
                autorank.get("message_id") == interaction.message.id):
                try:
                    role = interaction.guild.get_role(autorank["role_id"])
                    if role:
                        if role in interaction.user.roles:
                            await interaction.user.remove_roles(role)
                            await interaction.response.send_message(f"❌ Removed role {role.mention}!", ephemeral=True)
                        else:
                            await interaction.user.add_roles(role)
                            await interaction.response.send_message(f"✅ Added role {role.mention}!", ephemeral=True)
                    return
                except Exception as e:
                    await interaction.response.send_message("❌ Error processing role assignment!", ephemeral=True)

# Edit AutoRank View
class AutoRankEditView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user
        self.add_item(AutoRankEditSelect())
        self.add_item(BackToMainButton(user))

class AutoRankEditSelect(discord.ui.Select):
    def __init__(self):
        data = load_autorank_data()
        autoranks = data.get("autoranks", {})
        
        options = []
        for autorank_id, autorank in autoranks.items():
            autorank_type = autorank['type'].replace('_', ' ').title()
            created_at = autorank.get('created_at', 'Unknown')
            timestamp = created_at[:19] if len(created_at) > 19 else created_at
            
            options.append(discord.SelectOption(
                label=f"<@&{autorank['role_id']}> ({autorank_type})",
                value=autorank_id,
                description=f"Made At: {timestamp}"
            ))
            
        super().__init__(placeholder="Select autorank to edit...", options=options)

    async def callback(self, interaction: discord.Interaction):
        autorank_id = self.values[0]
        data = load_autorank_data()
        autorank = data["autoranks"][autorank_id]
        
        if autorank["type"] == "new_members":
            view = EditNewMembersConfigView(self.view.user, autorank_id)
            embed = view.get_embed()
            await interaction.response.edit_message(embed=embed, view=view)
        elif autorank["type"] == "reaction":
            view = EditReactionConfigView(self.view.user, autorank_id)
            embed = view.get_embed()
            await interaction.response.edit_message(embed=embed, view=view)
        elif autorank["type"] == "button":
            view = EditButtonConfigView(self.view.user, autorank_id)
            embed = view.get_embed()
            await interaction.response.edit_message(embed=embed, view=view)

# Edit Views for each autorank type
class EditNewMembersConfigView(discord.ui.View):
    def __init__(self, user, autorank_id):
        super().__init__(timeout=300)
        self.user = user
        self.autorank_id = autorank_id
        data = load_autorank_data()
        autorank = data["autoranks"][autorank_id]
        self.selected_role = None
        self.all_members_enabled = autorank.get("all_members", True)
        self.update_view()

    def update_view(self):
        self.clear_items()
        self.add_item(RoleSelect(self))
        
        toggle_button = discord.ui.Button(
            label="All Members",
            style=discord.ButtonStyle.success if self.all_members_enabled else discord.ButtonStyle.danger,
            emoji="🟢" if self.all_members_enabled else "🔴"
        )
        toggle_button.callback = self.toggle_all_members
        self.add_item(toggle_button)
        
        if self.selected_role:
            confirm_button = discord.ui.Button(label="Update", style=discord.ButtonStyle.success, emoji="✅")
            confirm_button.callback = self.update_autorank
            self.add_item(confirm_button)
        
        delete_button = discord.ui.Button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
        delete_button.callback = self.delete_autorank
        self.add_item(delete_button)
        
        self.add_item(BackToEditButton(self.user))

    async def toggle_all_members(self, interaction: discord.Interaction):
        self.all_members_enabled = not self.all_members_enabled
        self.update_view()
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def update_autorank(self, interaction: discord.Interaction):
        data = load_autorank_data()
        data["autoranks"][self.autorank_id].update({
            "role_id": self.selected_role.id,
            "all_members": self.all_members_enabled
        })
        save_autorank_data(data)
        
        view = AutoRankMainView(self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    async def delete_autorank(self, interaction: discord.Interaction):
        data = load_autorank_data()
        del data["autoranks"][self.autorank_id]
        save_autorank_data(data)
        
        view = AutoRankMainView(self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    def get_embed(self):
        data = load_autorank_data()
        autorank = data["autoranks"][self.autorank_id]
        current_role = f"<@&{autorank['role_id']}>"
        
        embed = discord.Embed(
            title="✏️ Edit New Members AutoRank",
            description=f"Currently configured role: {current_role}\n\nSelect a new role if you want to change it:",
            color=0xffa500
        )
        
        if self.selected_role:
            embed.add_field(
                name="New Selected Role",
                value=self.selected_role.mention,
                inline=False
            )
            
        status = "✅ Enabled" if self.all_members_enabled else "❌ Disabled"
        embed.add_field(
            name="Apply to Existing Members",
            value=f"{status} - Apply role to current server members (excluding bots)",
            inline=False
        )
        
        return embed

class EditReactionConfigView(discord.ui.View):
    def __init__(self, user, autorank_id):
        super().__init__(timeout=300)
        self.user = user
        self.autorank_id = autorank_id
        data = load_autorank_data()
        autorank = data["autoranks"][autorank_id]
        self.selected_role = None
        self.message_link = f"https://discord.com/channels/{autorank['guild_id']}/{autorank['channel_id']}/{autorank['message_id']}"
        self.update_view()

    def update_view(self):
        self.clear_items()
        self.add_item(RoleSelect(self))
        
        if self.selected_role:
            message_button = discord.ui.Button(label="Message Link", style=discord.ButtonStyle.primary, emoji="🔗")
            message_button.callback = self.set_message_link
            self.add_item(message_button)
            
            confirm_button = discord.ui.Button(label="Update", style=discord.ButtonStyle.success, emoji="✅")
            confirm_button.callback = self.update_autorank
            self.add_item(confirm_button)
        
        delete_button = discord.ui.Button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
        delete_button.callback = self.delete_autorank
        self.add_item(delete_button)
        
        self.add_item(BackToEditButton(self.user))

    async def set_message_link(self, interaction: discord.Interaction):
        modal = MessageLinkModal(self)
        await interaction.response.send_modal(modal)

    async def update_autorank(self, interaction: discord.Interaction):
        data = load_autorank_data()
        parts = self.message_link.split('/')
        guild_id = int(parts[-3])
        channel_id = int(parts[-2])
        message_id = int(parts[-1])
        
        data["autoranks"][self.autorank_id].update({
            "role_id": self.selected_role.id,
            "guild_id": guild_id,
            "channel_id": channel_id,
            "message_id": message_id
        })
        save_autorank_data(data)
        
        view = AutoRankMainView(self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    async def delete_autorank(self, interaction: discord.Interaction):
        data = load_autorank_data()
        del data["autoranks"][self.autorank_id]
        save_autorank_data(data)
        
        view = AutoRankMainView(self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    def get_embed(self):
        data = load_autorank_data()
        autorank = data["autoranks"][self.autorank_id]
        current_role = f"<@&{autorank['role_id']}>"
        
        embed = discord.Embed(
            title="✏️ Edit Reaction AutoRank",
            description=f"Currently configured role: {current_role}\n\nSelect a new role if you want to change it:",
            color=0xffa500
        )
        
        if self.selected_role:
            embed.add_field(
                name="New Selected Role",
                value=self.selected_role.mention,
                inline=False
            )
            
        embed.add_field(
            name="Message Link",
            value=f"[Jump to Message]({self.message_link})",
            inline=False
        )
        
        return embed

class EditButtonConfigView(discord.ui.View):
    def __init__(self, user, autorank_id):
        super().__init__(timeout=300)
        self.user = user
        self.autorank_id = autorank_id
        data = load_autorank_data()
        autorank = data["autoranks"][autorank_id]
        self.selected_role = None
        self.message_link = f"https://discord.com/channels/{autorank['guild_id']}/{autorank['channel_id']}/{autorank['message_id']}"
        self.button_color = autorank.get("button_color", "green")
        self.button_text = autorank.get("button_text", "")
        self.button_emoji = autorank.get("button_emoji", "<:ConfirmLOGO:1407072680267481249>")
        self.update_view()

    def update_view(self):
        self.clear_items()
        self.add_item(RoleSelect(self))
        
        if self.selected_role:
            color_button = discord.ui.Button(label="Button Color", style=discord.ButtonStyle.secondary, emoji="🎨")
            color_button.callback = self.set_button_color
            self.add_item(color_button)
            
            text_button = discord.ui.Button(label="Button Text", style=discord.ButtonStyle.secondary, emoji="📝")
            text_button.callback = self.set_button_text
            self.add_item(text_button)
            
            emoji_button = discord.ui.Button(label="Button Emoji", style=discord.ButtonStyle.secondary, emoji="😀")
            emoji_button.callback = self.set_button_emoji
            self.add_item(emoji_button)
            
            message_button = discord.ui.Button(label="Message Link", style=discord.ButtonStyle.primary, emoji="🔗")
            message_button.callback = self.set_message_link
            self.add_item(message_button)
            
            confirm_button = discord.ui.Button(label="Update", style=discord.ButtonStyle.success, emoji="✅")
            confirm_button.callback = self.update_autorank
            self.add_item(confirm_button)
        
        delete_button = discord.ui.Button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
        delete_button.callback = self.delete_autorank
        self.add_item(delete_button)
        
        self.add_item(BackToEditButton(self.user))

    async def set_button_color(self, interaction: discord.Interaction):
        view = ButtonColorSelectView(self)
        embed = discord.Embed(
            title="🎨 Button Color",
            description="Choose the color for your button:",
            color=0x5865f2
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def set_button_text(self, interaction: discord.Interaction):
        modal = ButtonTextModal(self)
        await interaction.response.send_modal(modal)

    async def set_button_emoji(self, interaction: discord.Interaction):
        modal = ButtonEmojiModal(self)
        await interaction.response.send_modal(modal)

    async def set_message_link(self, interaction: discord.Interaction):
        modal = MessageLinkModal(self)
        await interaction.response.send_modal(modal)

    async def update_autorank(self, interaction: discord.Interaction):
        data = load_autorank_data()
        parts = self.message_link.split('/')
        guild_id = int(parts[-3])
        channel_id = int(parts[-2])
        message_id = int(parts[-1])
        
        data["autoranks"][self.autorank_id].update({
            "role_id": self.selected_role.id,
            "guild_id": guild_id,
            "channel_id": channel_id,
            "message_id": message_id,
            "button_color": self.button_color,
            "button_text": self.button_text,
            "button_emoji": self.button_emoji
        })
        save_autorank_data(data)
        
        # Update button on message
        await self.update_button_on_message(interaction, data["autoranks"][self.autorank_id])
        
        view = AutoRankMainView(self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    async def update_button_on_message(self, interaction, autorank_data):
        try:
            channel = interaction.guild.get_channel(autorank_data["channel_id"])
            message = await channel.fetch_message(autorank_data["message_id"])
            
            style_map = {
                "blue": discord.ButtonStyle.primary,
                "green": discord.ButtonStyle.success,
                "red": discord.ButtonStyle.danger,
                "grey": discord.ButtonStyle.secondary
            }
            
            view = PersistentAutoRankButtonView()
            button = view.children[0]
            button.label = autorank_data["button_text"] or None
            button.style = style_map[autorank_data["button_color"]]
            button.emoji = autorank_data["button_emoji"]
            
            await message.edit(view=view)
        except:
            pass

    async def delete_autorank(self, interaction: discord.Interaction):
        data = load_autorank_data()
        del data["autoranks"][self.autorank_id]
        save_autorank_data(data)
        
        view = AutoRankMainView(self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    def get_embed(self):
        data = load_autorank_data()
        autorank = data["autoranks"][self.autorank_id]
        current_role = f"<@&{autorank['role_id']}>"
        
        embed = discord.Embed(
            title="✏️ Edit Button AutoRank",
            description=f"Currently configured role: {current_role}\n\nSelect a new role if you want to change it:",
            color=0xffa500
        )
        
        if self.selected_role:
            embed.add_field(
                name="New Selected Role",
                value=self.selected_role.mention,
                inline=False
            )
            
        # Button preview
        color_emoji = {"blue": "🟦", "green": "🟩", "red": "🟥", "grey": "⬛"}
        preview = f"{color_emoji[self.button_color]} "
        if self.button_text:
            preview += f"**{self.button_text}** "
        preview += self.button_emoji
        
        embed.add_field(
            name="Button Preview",
            value=preview,
            inline=False
        )
            
        embed.add_field(
            name="Message Link",
            value=f"[Jump to Message]({self.message_link})",
            inline=False
        )
        
        return embed

# Additional Navigation Button
class BackToEditButton(discord.ui.Button):
    def __init__(self, user):
        super().__init__(label="Back", style=discord.ButtonStyle.secondary, emoji="⬅️")
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        view = AutoRankEditView(self.user)
        embed = discord.Embed(
            title="✏️ Edit AutoRanks",
            description="Select an AutoRank to edit:",
            color=0xffa500
        )
        await interaction.response.edit_message(embed=embed, view=view)

# Function to restore autorank buttons
async def restore_autorank_buttons(bot):
    """Restore autorank buttons when bot starts"""
    try:
        data = load_autorank_data()
        autoranks = data.get("autoranks", {})
        
        for autorank_id, autorank in autoranks.items():
            if autorank["type"] == "button":
                try:
                    guild = bot.get_guild(autorank["guild_id"])
                    if guild:
                        channel = guild.get_channel(autorank["channel_id"])
                        if channel:
                            message = await channel.fetch_message(autorank["message_id"])
                            if message:
                                style_map = {
                                    "blue": discord.ButtonStyle.primary,
                                    "green": discord.ButtonStyle.success,
                                    "red": discord.ButtonStyle.danger,
                                    "grey": discord.ButtonStyle.secondary
                                }
                                
                                view = PersistentAutoRankButtonView()
                                button = view.children[0]
                                button.label = autorank.get("button_text") or None
                                button.style = style_map[autorank.get("button_color", "green")]
                                button.emoji = autorank.get("button_emoji", "<:ConfirmLOGO:1407072680267481249>")
                                
                                await message.edit(view=view)
                except Exception as e:
                    print(f"❌ Error restoring autorank button {autorank_id}: {e}")
        
        print("✅ AutoRank buttons restored successfully")
    except Exception as e:
        print(f"❌ Error restoring autorank buttons: {e}")

# Event Handlers
class AutoRankSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Handle new member autoranks"""
        data = load_autorank_data()
        autoranks = data.get("autoranks", {})
        
        for autorank_id, autorank in autoranks.items():
            if autorank["type"] == "new_members":
                try:
                    role = member.guild.get_role(autorank["role_id"])
                    if role:
                        await member.add_roles(role)
                except:
                    pass

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle reaction autoranks"""
        if user.bot:
            return
            
        data = load_autorank_data()
        autoranks = data.get("autoranks", {})
        
        for autorank_id, autorank in autoranks.items():
            if (autorank["type"] == "reaction" and 
                autorank.get("message_id") == reaction.message.id):
                try:
                    role = reaction.message.guild.get_role(autorank["role_id"])
                    if role and role not in user.roles:
                        await user.add_roles(role)
                except:
                    pass

    @discord.app_commands.command(name="autorank", description="Manage server auto-ranking system")
    async def autorank(self, interaction: discord.Interaction):
        """Main autorank management command"""
        view = AutoRankMainView(interaction.user)
        embed = view.get_main_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AutoRankSystem(bot))
    # Add persistent view to bot
    bot.add_view(PersistentAutoRankButtonView())
    # Restore existing autorank buttons
    await restore_autorank_buttons(bot)

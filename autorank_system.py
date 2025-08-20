
import discord
from discord.ext import commands, tasks
import json
import re
from datetime import datetime
import asyncio

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
        self.update_view()

    def update_view(self):
        self.clear_items()
        self.add_item(RoleSelect(self))
        
        if self.selected_role:
            confirm_button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
            confirm_button.callback = self.confirm_new_members
            self.add_item(confirm_button)
        
        self.add_item(BackToCreateButton(self.user))

    async def confirm_new_members(self, interaction: discord.Interaction):
        data = load_autorank_data()
        autorank_id = str(len(data.get("autoranks", {})) + 1)
        
        if "autoranks" not in data:
            data["autoranks"] = {}
            
        data["autoranks"][autorank_id] = {
            "type": "new_members",
            "role_id": self.selected_role.id,
            "created_at": datetime.now().isoformat()
        }
        
        save_autorank_data(data)
        
        view = AutoRankMainView(self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

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
        
        return embed

# Reaction Configuration View
class ReactionConfigView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user
        self.selected_role = None
        self.message_link = None
        self.reaction_emoji = "⭐"
        self.update_view()

    def update_view(self):
        self.clear_items()
        self.add_item(RoleSelect(self))
        
        if self.selected_role:
            # Première ligne - Message Link et Reaction Emoji
            message_button = discord.ui.Button(label="Message Link", style=discord.ButtonStyle.primary, emoji="🔗", row=1)
            message_button.callback = self.set_message_link
            self.add_item(message_button)
            
            reaction_emoji_button = discord.ui.Button(label="Reaction Emoji", style=discord.ButtonStyle.secondary, emoji="⭐", row=1)
            reaction_emoji_button.callback = self.set_reaction_emoji
            self.add_item(reaction_emoji_button)
            
            if self.message_link:
                # Deuxième ligne - Confirm et Back
                confirm_button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅", row=2)
                confirm_button.callback = self.confirm_reaction
                self.add_item(confirm_button)
        
        # Back toujours à droite
        back_button = BackToCreateButton(self.user)
        back_button.row = 2
        self.add_item(back_button)

    async def set_reaction_emoji(self, interaction: discord.Interaction):
        modal = ReactionEmojiModal(self)
        await interaction.response.send_modal(modal)

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
            "reaction_emoji": self.reaction_emoji,
            "created_at": datetime.now().isoformat()
        }
        
        save_autorank_data(data)
        
        # Ajouter la réaction au message
        await self.add_reaction_to_message(interaction, data["autoranks"][autorank_id])
        
        view = AutoRankMainView(self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    async def add_reaction_to_message(self, interaction, autorank_data):
        try:
            channel = interaction.guild.get_channel(autorank_data["channel_id"])
            message = await channel.fetch_message(autorank_data["message_id"])
            await message.add_reaction(autorank_data["reaction_emoji"])
        except:
            pass

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
            
        embed.add_field(
            name="Reaction Emoji",
            value=self.reaction_emoji,
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
        if not autoranks:
            options.append(discord.SelectOption(
                label="No autoranks found",
                value="none",
                description="No autoranks available in autorank_data.json"
            ))
        else:
            for autorank_id, autorank in autoranks.items():
                autorank_type = autorank['type'].replace('_', ' ').title()
                created_at = autorank.get('created_at', 'Unknown')
                
                # Format date to "Made the DD/MM/YYYY At HH:MM"
                if created_at != 'Unknown':
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        formatted_date = f"Made the {dt.strftime('%d/%m/%Y At %H:%M')}"
                    except:
                        formatted_date = f"Made At: {created_at[:16]}"
                else:
                    formatted_date = "Made At: Unknown"
                
                options.append(discord.SelectOption(
                    label=f"Role ID {autorank['role_id']} ({autorank_type})",
                    value=autorank_id,
                    description=formatted_date
                ))
            
        super().__init__(placeholder="Select autorank to delete...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("❌ No autoranks to delete!", ephemeral=True)
            return
            
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
        
        if not re.match(pattern, link):
            await interaction.response.send_message("❌ Invalid message link format! Please use: https://discord.com/channels/guild_id/channel_id/message_id", ephemeral=True)
            return
        
        # Validate if message is accessible and editable
        try:
            parts = link.split('/')
            guild_id = int(parts[-3])
            channel_id = int(parts[-2])
            message_id = int(parts[-1])
            
            # Check if it's the correct guild
            if guild_id != interaction.guild.id:
                await interaction.response.send_message("❌ The message link must be from this server!", ephemeral=True)
                return
            
            # Try to access the channel and message
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message("❌ Cannot access the specified channel! Make sure the bot has permissions.", ephemeral=True)
                return
            
            try:
                message = await channel.fetch_message(message_id)
                # Pour les réactions, pas besoin que le message soit du bot
                # Pour les boutons, on vérifie si c'est un message du bot
                if hasattr(self.parent_view, 'button_color'):  # C'est un ButtonConfig
                    if message.author != interaction.client.user:
                        await interaction.response.send_message("❌ Cannot modify this message! The bot can only add buttons to messages it sent. Please provide a message link from a message sent by this bot.", ephemeral=True)
                        return
            except discord.NotFound:
                await interaction.response.send_message("❌ Message not found! Please verify the message link is correct.", ephemeral=True)
                return
            except discord.Forbidden:
                await interaction.response.send_message("❌ Cannot access this message! Make sure the bot has the necessary permissions in that channel.", ephemeral=True)
                return
            
            # If all validations pass
            self.parent_view.message_link = link
            self.parent_view.update_view()
            embed = self.parent_view.get_embed()
            await interaction.response.edit_message(embed=embed, view=self.parent_view)
            
        except (ValueError, IndexError):
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

class ReactionEmojiModal(discord.ui.Modal):
    def __init__(self, parent_view):
        super().__init__(title="Reaction Emoji")
        self.parent_view = parent_view

    reaction_emoji = discord.ui.TextInput(
        label="Reaction Emoji",
        placeholder="Enter emoji (Unicode or <:name:id>)",
        required=False,
        max_length=100,
        default="⭐"
    )

    async def on_submit(self, interaction: discord.Interaction):
        emoji = self.reaction_emoji.value or "⭐"
        self.parent_view.reaction_emoji = emoji
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
        if not autoranks:
            options.append(discord.SelectOption(
                label="No autoranks found",
                value="none",
                description="No autoranks available in autorank_data.json"
            ))
        else:
            for autorank_id, autorank in autoranks.items():
                autorank_type = autorank['type'].replace('_', ' ').title()
                created_at = autorank.get('created_at', 'Unknown')
                
                # Format date to "Made the DD/MM/YYYY At HH:MM"
                if created_at != 'Unknown':
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        formatted_date = f"Made the {dt.strftime('%d/%m/%Y At %H:%M')}"
                    except:
                        formatted_date = f"Made At: {created_at[:16]}"
                else:
                    formatted_date = "Made At: Unknown"
                
                # Get role name instead of mention
                role_name = f"Role ID {autorank['role_id']}"  # Fallback
                
                options.append(discord.SelectOption(
                    label=f"{role_name} ({autorank_type})",
                    value=autorank_id,
                    description=formatted_date
                ))
            
        super().__init__(placeholder="Select autorank to edit...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("❌ No autoranks to edit!", ephemeral=True)
            return
            
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
        self.selected_role = None
        self.update_view()

    def update_view(self):
        self.clear_items()
        self.add_item(RoleSelect(self))
        
        if self.selected_role:
            confirm_button = discord.ui.Button(label="Update", style=discord.ButtonStyle.success, emoji="✅")
            confirm_button.callback = self.update_autorank
            self.add_item(confirm_button)
        
        delete_button = discord.ui.Button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
        delete_button.callback = self.delete_autorank
        self.add_item(delete_button)
        
        self.add_item(BackToEditButton(self.user))

    async def update_autorank(self, interaction: discord.Interaction):
        data = load_autorank_data()
        data["autoranks"][self.autorank_id].update({
            "role_id": self.selected_role.id
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
        self.reaction_emoji = autorank.get("reaction_emoji", "⭐")
        self.update_view()

    def update_view(self):
        self.clear_items()
        self.add_item(RoleSelect(self))
        
        if self.selected_role:
            # Première ligne - Message Link et Reaction Emoji
            message_button = discord.ui.Button(label="Message Link", style=discord.ButtonStyle.primary, emoji="🔗", row=1)
            message_button.callback = self.set_message_link
            self.add_item(message_button)
            
            reaction_emoji_button = discord.ui.Button(label="Reaction Emoji", style=discord.ButtonStyle.secondary, emoji="⭐", row=1)
            reaction_emoji_button.callback = self.set_reaction_emoji
            self.add_item(reaction_emoji_button)
            
            # Deuxième ligne - Update, Delete et Back
            confirm_button = discord.ui.Button(label="Update", style=discord.ButtonStyle.success, emoji="✅", row=2)
            confirm_button.callback = self.update_autorank
            self.add_item(confirm_button)
        
        delete_button = discord.ui.Button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️", row=2)
        delete_button.callback = self.delete_autorank
        self.add_item(delete_button)
        
        back_button = BackToEditButton(self.user)
        back_button.row = 2
        self.add_item(back_button)

    async def set_reaction_emoji(self, interaction: discord.Interaction):
        modal = ReactionEmojiModal(self)
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
            "reaction_emoji": self.reaction_emoji
        })
        save_autorank_data(data)
        
        # Ajouter la nouvelle réaction au message
        await self.add_reaction_to_message(interaction, data["autoranks"][self.autorank_id])
        
        view = AutoRankMainView(self.user)
        embed = view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    async def add_reaction_to_message(self, interaction, autorank_data):
        try:
            channel = interaction.guild.get_channel(autorank_data["channel_id"])
            message = await channel.fetch_message(autorank_data["message_id"])
            await message.add_reaction(autorank_data["reaction_emoji"])
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
            name="Reaction Emoji",
            value=self.reaction_emoji,
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

# Function to restore autorank buttons and reactions
async def restore_autorank_buttons(bot):
    """Restore autorank buttons and reactions when bot starts"""
    try:
        data = load_autorank_data()
        autoranks = data.get("autoranks", {})
        
        for autorank_id, autorank in autoranks.items():
            # Restaurer les boutons
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
                                print(f"✅ Bouton AutoRank {autorank_id} restauré")
                except Exception as e:
                    print(f"❌ Error restoring autorank button {autorank_id}: {e}")
            
            # Restaurer les réactions
            elif autorank["type"] == "reaction":
                try:
                    guild = bot.get_guild(autorank["guild_id"])
                    if guild:
                        channel = guild.get_channel(autorank["channel_id"])
                        if channel:
                            message = await channel.fetch_message(autorank["message_id"])
                            if message:
                                reaction_emoji = autorank.get("reaction_emoji", "⭐")
                                
                                # Decoder l'emoji Unicode si nécessaire
                                if reaction_emoji.startswith("\\u"):
                                    try:
                                        reaction_emoji = reaction_emoji.encode().decode('unicode_escape')
                                    except:
                                        pass
                                
                                # Vérifier si la réaction existe déjà
                                reaction_exists = False
                                for reaction in message.reactions:
                                    if str(reaction.emoji) == reaction_emoji:
                                        reaction_exists = True
                                        break
                                
                                # Ajouter la réaction si elle n'existe pas
                                if not reaction_exists:
                                    await message.add_reaction(reaction_emoji)
                                    print(f"✅ Réaction AutoRank {autorank_id} restaurée: {reaction_emoji}")
                                else:
                                    print(f"ℹ️ Réaction AutoRank {autorank_id} déjà présente: {reaction_emoji}")
                                    
                except Exception as e:
                    print(f"❌ Erreur restauration réaction AutoRank {autorank_id}: {e}")
        
        print("✅ AutoRank buttons et reactions restored successfully")
    except Exception as e:
        print(f"❌ Error restoring autorank buttons: {e}")

# Event Handlers
class AutoRankSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.new_member_monitor.start()

    def cog_unload(self):
        self.new_member_monitor.cancel()

    @tasks.loop(seconds=5.0)
    async def new_member_monitor(self):
        """Surveille en permanence les nouveaux membres pour les AutoRanks new_members"""
        try:
            data = load_autorank_data()
            autoranks = data.get("autoranks", {})
            
            # Vérifier s'il y a des autoranks new_members actifs
            new_member_autoranks = [ar for ar in autoranks.values() if ar["type"] == "new_members"]
            
            if not new_member_autoranks:
                return
            
            # Pour chaque serveur où le bot est présent
            for guild in self.bot.guilds:
                try:
                    # Récupérer tous les membres du serveur
                    async for member in guild.fetch_members(limit=None):
                        if member.bot:
                            continue
                            
                        # Vérifier chaque autorank new_members
                        for autorank in new_member_autoranks:
                            role_id = autorank["role_id"]
                            role = guild.get_role(role_id)
                            
                            if not role:
                                continue
                                
                            # Si le membre n'a pas le rôle, le lui donner
                            if role not in member.roles:
                                try:
                                    await self.give_role_to_new_member(autorank, member)
                                    print(f"✅ Rôle {role.name} donné à {member.display_name}")
                                except Exception as e:
                                    print(f"❌ Erreur attribution rôle à {member.display_name}: {e}")
                                    
                except Exception as e:
                    print(f"❌ Erreur surveillance membres serveur {guild.name}: {e}")
                    
        except Exception as e:
            print(f"❌ Erreur surveillance nouveaux membres: {e}")

    @new_member_monitor.before_loop
    async def before_new_member_monitor(self):
        await self.bot.wait_until_ready()

    async def give_role_to_new_member(self, autorank, new_member):
        """Give role to a new member"""
        try:
            role_id = autorank["role_id"]
            role = new_member.guild.get_role(role_id)
            
            if not role:
                return
            
            # Check bot permissions
            bot_member = new_member.guild.get_member(self.bot.user.id)
            if not bot_member.guild_permissions.manage_roles:
                return
            
            # Check if bot's role is higher than target role
            if role >= bot_member.top_role:
                return
            
            # Add role to new member
            await new_member.add_roles(role, reason="AutoRank: New Member")
                
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Handle new member autoranks - Attribution immédiate"""
        try:
            data = load_autorank_data()
            autoranks = data.get("autoranks", {})
            
            for autorank_id, autorank in autoranks.items():
                if autorank["type"] == "new_members":
                    await self.give_role_to_new_member(autorank, member)
                    print(f"🎯 Nouveau membre {member.display_name} - Rôle attribué immédiatement")
        except Exception as e:
            print(f"❌ Erreur on_member_join: {e}")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle reaction autoranks"""
        print(f"🎯 Réaction détectée: {reaction.emoji} par {user.display_name} sur message {reaction.message.id}")
        
        if user.bot:
            print(f"❌ Ignoré: {user.display_name} est un bot")
            return
            
        data = load_autorank_data()
        autoranks = data.get("autoranks", {})
        
        print(f"📊 {len(autoranks)} autoranks trouvés dans le fichier")
        
        for autorank_id, autorank in autoranks.items():
            print(f"🔍 Vérification autorank {autorank_id}: type={autorank['type']}")
            
            if autorank["type"] == "reaction":
                print(f"🎯 AutoRank Reaction trouvé:")
                print(f"   - Message ID config: {autorank.get('message_id')}")
                print(f"   - Message ID actuel: {reaction.message.id}")
                print(f"   - Channel ID config: {autorank.get('channel_id')}")
                print(f"   - Channel ID actuel: {reaction.message.channel.id}")
                
                if (autorank.get("message_id") == reaction.message.id and
                    autorank.get("channel_id") == reaction.message.channel.id):
                    
                    # Gérer l'emoji Unicode échappé et normal
                    reaction_emoji = autorank.get("reaction_emoji", "⭐")
                    user_emoji = str(reaction.emoji)
                    
                    # Decoder l'emoji Unicode si nécessaire
                    if reaction_emoji.startswith("\\u"):
                        try:
                            reaction_emoji = reaction_emoji.encode().decode('unicode_escape')
                        except:
                            pass
                    
                    print(f"🔍 Comparaison emojis: Config='{reaction_emoji}' vs User='{user_emoji}'")
                    print(f"🔍 Emoji décodé: '{reaction_emoji}'")
                    
                    # Comparaison directe des emojis
                    if reaction_emoji == user_emoji:
                        print(f"✅ Emojis correspondent ! Attribution du rôle...")
                        try:
                            role = reaction.message.guild.get_role(autorank["role_id"])
                            if role:
                                if role not in user.roles:
                                    await user.add_roles(role, reason="AutoRank: Reaction")
                                    print(f"✅ Rôle {role.name} donné à {user.display_name} via réaction {reaction.emoji}")
                                else:
                                    print(f"ℹ️ {user.display_name} a déjà le rôle {role.name}")
                            else:
                                print(f"❌ Rôle {autorank['role_id']} introuvable sur le serveur")
                        except Exception as e:
                            print(f"❌ Erreur attribution rôle via réaction: {e}")
                    else:
                        print(f"❌ Emojis ne correspondent pas: '{reaction_emoji}' != '{user_emoji}'")
                else:
                    print(f"❌ Message ou channel ne correspond pas")

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

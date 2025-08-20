import discord
from discord.ext import commands
import json
import asyncio
from datetime import datetime
import copy

# Variable globale pour stocker l'instance du bot
_bot_instance = None

def set_bot_instance(bot):
    """Définit l'instance globale du bot"""
    global _bot_instance
    _bot_instance = bot

def get_bot_name(bot=None):
    """Récupère le nom d'affichage du bot actuel"""
    # Utilise le bot passé en paramètre, sinon l'instance globale
    bot_to_use = bot or _bot_instance
    if bot_to_use and bot_to_use.user:
        return bot_to_use.user.display_name or bot_to_use.user.name
    return "Ticket Bot"

# Default permissions constants
DEFAULT_PERMISSIONS = {
    "owner": {
        "view_channel": True,
        "create_instant_invite": False,
        "send_messages": True,
        "send_messages_in_threads": True,
        "embed_links": True,
        "attach_files": True,
        "add_reactions": True,
        "use_external_emojis": True,
        "use_external_stickers": True,
        "read_message_history": True,
        "manage_channels": False,
        "manage_permissions": False,
        "create_public_threads": False,
        "create_private_threads": False,
        "use_application_commands": False,
        "manage_messages": False
    },
    "staff": {
        "view_channel": True,
        "create_instant_invite": True,
        "send_messages": True,
        "send_messages_in_threads": True,
        "embed_links": True,
        "attach_files": True,
        "add_reactions": True,
        "use_external_emojis": True,
        "use_external_stickers": True,
        "read_message_history": True,
        "manage_channels": True,
        "manage_permissions": True,
        "create_public_threads": True,
        "create_private_threads": True,
        "use_application_commands": True,
        "manage_messages": True
    },
    "authorized": {
        "view_channel": True,
        "create_instant_invite": False,
        "send_messages": True,
        "send_messages_in_threads": True,
        "embed_links": True,
        "attach_files": True,
        "add_reactions": True,
        "use_external_emojis": True,
        "use_external_stickers": True,
        "read_message_history": True,
        "manage_channels": False,
        "manage_permissions": False,
        "create_public_threads": False,
        "create_private_threads": False,
        "use_application_commands": False,
        "manage_messages": False
    }
}

def load_ticket_data():
    """Load ticket data from JSON file"""
    try:
        with open('ticket_bot.json', 'r', encoding='utf-8') as f:
            data = json.load(f)

            # Ensure all required top-level keys exist
            if "staff_roles" not in data:
                data["staff_roles"] = []

            if "settings" not in data:
                data["settings"] = {
                    "default_embed": {
                        "title": "",
                        "outside_description": "",
                        "description": "Support will be with you shortly. To close this ticket.",
                        "thumbnail": "",
                        "image": "",
                        "footer": f"{get_bot_name()} - Ticket Bot"
                    },
                    "button_enabled": True,
                    "button_emoji": "<:CloseLOGO:1407072519420248256>",
                    "button_label": "Close Ticket",
                    "ai_enabled": False,
                    "log_settings": {
                        "ticket_opened": True,
                        "ticket_claimed": True,
                        "ticket_closed": True,
                        "ticket_deleted": True,
                        "ticket_reopened": True,
                        "transcript_saved": True
                    }
                }

            # Ensure log_settings exist in settings
            if "log_settings" not in data["settings"]:
                data["settings"]["log_settings"] = {
                    "ticket_opened": True,
                    "ticket_claimed": True,
                    "ticket_closed": True,
                    "ticket_deleted": True,
                    "ticket_reopened": True,
                    "transcript_saved": True
                }

            if "ticket_counters" not in data:
                data["ticket_counters"] = {}

            if "closed_tickets" not in data:
                data["closed_tickets"] = {}

            # Migrate old data structure to new sub_panels structure
            if "tickets" in data:
                for panel_id, panel in data["tickets"].items():
                    if "sub_panels" not in panel and "name" in panel:
                        # Convert old structure to new structure
                        panel["sub_panels"] = {
                            "1": {
                                "id": "1",
                                "name": panel["name"],
                                "title": panel.get("title", "Default"),
                                "description": panel.get("description", "Default ticket"),
                                "permissions": panel.get("permissions", copy.deepcopy(DEFAULT_PERMISSIONS)),
                                "ai_enabled": panel.get("ai_enabled", False),
                                "button_visible": True,
                                "button_emoji": "<:TicketLOGO:1407730639343714397>",
                                "button_text": "",
                                "ticket_description": "Support will be with you shortly. To close this ticket.",
                                "ticket_footer": f"{get_bot_name()} - Ticket Bot"
                            }
                        }
                        panel["display_type"] = "buttons"
                        # Remove old fields that are now in sub_panels
                        if "permissions" in panel:
                            del panel["permissions"]
                        if "ai_enabled" in panel:
                            del panel["ai_enabled"]

                # Save migrated data
                save_ticket_data(data)

            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "tickets": {},
            "staff_roles": [],
            "settings": {
                "default_embed": {
                    "title": "",
                    "outside_description": "",
                    "description": "Support will be with you shortly. To close this ticket.",
                    "thumbnail": "",
                    "image": "",
                    "footer": f"{get_bot_name()} - Ticket Bot"
                },
                "button_enabled": True,
                "button_emoji": "<:CloseLOGO:1407072519420248256>",
                "button_label": "Close Ticket",
                "ai_enabled": False,
                "log_settings": {
                    "ticket_opened": True,
                    "ticket_claimed": True,
                    "ticket_closed": True,
                    "ticket_deleted": True,
                    "ticket_reopened": True,
                    "transcript_saved": True
                }
            },
            "ticket_counters": {},
            "closed_tickets": {}
        }

def save_ticket_data(data):
    """Save ticket data to JSON file"""
    with open('ticket_bot.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_next_ticket_number(data, ticket_name):
    """Get next ticket number for a given ticket name"""
    if "ticket_counters" not in data:
        data["ticket_counters"] = {}

    if ticket_name not in data["ticket_counters"]:
        data["ticket_counters"][ticket_name] = 0

    data["ticket_counters"][ticket_name] += 1
    return data["ticket_counters"][ticket_name]

# Modals
class PanelEditModal(discord.ui.Modal, title='Edit Ticket Panel'):
    def __init__(self, panel_id, current_panel):
        super().__init__()
        self.panel_id = panel_id

        # Pre-fill with current values
        self.title_input.default = current_panel.get("title", "")
        self.description_input.default = current_panel.get("description", "")
        self.thumbnail_input.default = current_panel.get("thumbnail", "")
        self.footer_input.default = current_panel.get("footer", "")

    title_input = discord.ui.TextInput(
        label='Panel Title',
        placeholder='Panel title for the embed',
        required=True,
        max_length=256
    )

    description_input = discord.ui.TextInput(
        label='Panel Description',
        placeholder='Panel description',
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=4000
    )

    thumbnail_input = discord.ui.TextInput(
        label='Thumbnail URL',
        placeholder='Thumbnail URL (optional)',
        required=False,
        max_length=2000
    )

    footer_input = discord.ui.TextInput(
        label='Footer Text',
        placeholder='Footer text (optional)',
        required=False,
        max_length=2048
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        data = load_ticket_data()
        data["tickets"][self.panel_id]["title"] = self.title_input.value
        data["tickets"][self.panel_id]["description"] = self.description_input.value
        data["tickets"][self.panel_id]["thumbnail"] = self.thumbnail_input.value
        data["tickets"][self.panel_id]["footer"] = self.footer_input.value
        save_ticket_data(data)

        # Return to panel management
        view = PanelManagementView(self.panel_id)
        embed = create_panel_management_embed(data, self.panel_id)
        await interaction.edit_original_response(embed=embed, view=view)

class TicketCreateModal(discord.ui.Modal, title='Create New Ticket Panel'):
    def __init__(self):
        super().__init__()

    name_input = discord.ui.TextInput(
        label='Ticket Name',
        placeholder='This will appear in the server ticket manager...',
        required=True,
        max_length=50
    )

    title_input = discord.ui.TextInput(
        label='Panel Title',
        placeholder='Panel title for the embed (Required)',
        required=True,
        max_length=256
    )

    description_input = discord.ui.TextInput(
        label='Panel Description',
        placeholder='Panel description (Required)',
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=4000
    )

    thumbnail_input = discord.ui.TextInput(
        label='Thumbnail URL',
        placeholder='Thumbnail URL (Optional)',
        required=False,
        max_length=2000
    )

    footer_input = discord.ui.TextInput(
        label='Footer Text',
        placeholder='Footer text (Optional)',
        required=False,
        max_length=2048
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        data = load_ticket_data()

        # Ensure tickets key exists
        if "tickets" not in data:
            data["tickets"] = {}

        # Create new ticket panel ID
        panel_id = str(len(data["tickets"]) + 1)

        # Initialize counter for this ticket name
        if "ticket_counters" not in data:
            data["ticket_counters"] = {}
        data["ticket_counters"][self.name_input.value] = 0

        # Create ticket panel with sub-panels structure
        ticket_panel = {
            "id": panel_id,
            "title": self.title_input.value,
            "description": self.description_input.value,
            "thumbnail": self.thumbnail_input.value,
            "footer": self.footer_input.value,
            "created_at": datetime.now().isoformat(),
            "sub_panels": {
                "1": {
                    "id": "1",
                    "name": self.name_input.value,
                    "title": "Default Ticket",
                    "description": "Default ticket type",
                    "permissions": copy.deepcopy(DEFAULT_PERMISSIONS),
                    "ai_enabled": False,
                    "button_visible": True,
                    "button_emoji": "<:TicketLOGO:1407730639343714397>",
                    "button_text": "",
                    "ticket_title": "Default Ticket",
                    "ticket_description": "Support will be with you shortly. To close this ticket.",
                    "ticket_footer": f"{get_bot_name()} - Ticket Bot",
                    "close_button_text": "<:CloseLOGO:1407072519420248256>",
                    "panel_emoji": "<:TicketLOGO:1407730639343714397>",
                    "panel_title": "Default Ticket",
                    "panel_description": ""
                }
            },
            "display_type": "buttons"
        }

        data["tickets"][panel_id] = ticket_panel
        save_ticket_data(data)

        # Update main panel
        view = TicketPanelView()
        embed = create_ticket_panel_embed(data)
        await interaction.edit_original_response(embed=embed, view=view)

class TicketNameEditModal(discord.ui.Modal, title='Edit Ticket Name'):
    def __init__(self, panel_id, current_name):
        super().__init__()
        self.panel_id = panel_id
        self.name_input.default = current_name

    name_input = discord.ui.TextInput(
        label='Ticket Name',
        placeholder='New ticket name (will reset counter to 0)',
        required=True,
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        data = load_ticket_data()
        old_name = data["tickets"][self.panel_id]["name"]
        new_name = self.name_input.value

        # Update ticket name
        data["tickets"][self.panel_id]["name"] = new_name

        # Reset counter for new name
        if "ticket_counters" not in data:
            data["ticket_counters"] = {}
        data["ticket_counters"][new_name] = 0

        save_ticket_data(data)

        # Return to edit view
        view = TicketEditDetailView(self.panel_id)
        embed = create_ticket_edit_detail_embed(data, self.panel_id)
        await interaction.edit_original_response(embed=embed, view=view)

class TicketEmbedEditModal(discord.ui.Modal, title='Edit Embed Content'):
    def __init__(self, current_settings):
        super().__init__()
        self.current_settings = current_settings

        # Pre-fill with current values
        self.title_input.default = current_settings.get("title", "")
        self.outside_description_input.default = current_settings.get("outside_description", "")
        self.embed_description_input.default = current_settings.get("description", "Support will be with you shortly. To close this ticket.")
        self.thumbnail_input.default = current_settings.get("thumbnail", "")
        self.footer_input.default = current_settings.get("footer", f"{get_bot_name()} - Ticket Bot")

    title_input = discord.ui.TextInput(
        label='Title',
        placeholder='Embed title (optional)',
        required=False,
        max_length=256
    )

    outside_description_input = discord.ui.TextInput(
        label='Outside Description',
        placeholder='Description outside embed (optional)',
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=2000
    )

    embed_description_input = discord.ui.TextInput(
        label='Embed Description',
        placeholder='Description inside embed',
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=4000
    )

    thumbnail_input = discord.ui.TextInput(
        label='Thumbnail URL',
        placeholder='Thumbnail URL (optional)',
        required=False,
        max_length=2000
    )

    footer_input = discord.ui.TextInput(
        label='Footer Text',
        placeholder='Footer text (optional)',
        required=False,
        max_length=2048
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        data = load_ticket_data()

        # Update settings
        data["settings"]["default_embed"] = {
            "title": self.title_input.value,
            "outside_description": self.outside_description_input.value,
            "description": self.embed_description_input.value or "Support will be with you shortly. To close this ticket.",
            "thumbnail": self.thumbnail_input.value,
            "image": data["settings"]["default_embed"].get("image", ""),
            "footer": self.footer_input.value or f"{get_bot_name()} - Ticket Bot"
        }

        save_ticket_data(data)

        # Return to content edit menu
        view = EmbedContentEditView()
        embed = create_embed_content_edit_embed(data)
        await interaction.edit_original_response(embed=embed, view=view)

class SubPanelButtonEditModal(discord.ui.Modal, title='Edit Sub-Panel Button'):
    def __init__(self, panel_id, sub_panel_id, current_emoji, current_text):
        super().__init__()
        self.panel_id = panel_id
        self.sub_panel_id = sub_panel_id
        self.emoji_input.default = current_emoji
        self.text_input.default = current_text

    emoji_input = discord.ui.TextInput(
        label='Button Emoji',
        placeholder='<:TicketLOGO:1407730639343714397> (emoji for the button)',
        required=True,
        max_length=10
    )

    text_input = discord.ui.TextInput(
        label='Button Text',
        placeholder='Additional text after emoji (optional)',
        required=False,
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        data = load_ticket_data()
        data["tickets"][self.panel_id]["sub_panels"][self.sub_panel_id]["button_emoji"] = self.emoji_input.value
        data["tickets"][self.panel_id]["sub_panels"][self.sub_panel_id]["button_text"] = self.text_input.value
        save_ticket_data(data)

        # Return to sub-panel edit view
        view = SubPanelEditView(self.panel_id, self.sub_panel_id)
        embed = create_sub_panel_edit_embed(data, self.panel_id, self.sub_panel_id)
        await interaction.edit_original_response(embed=embed, view=view)

class SubPanelCreateModal(discord.ui.Modal, title='Create Sub-Panel'):
    def __init__(self, panel_id):
        super().__init__()
        self.panel_id = panel_id

    ticket_title_input = discord.ui.TextInput(
        label='Ticket Title',
        placeholder='Title of the ticket embed (e.g., "Support Ticket")',
        required=True,
        max_length=256
    )

    name_input = discord.ui.TextInput(
        label='Sub-Panel Name',
        placeholder='e.g., "support", "report", "giveaway"',
        required=True,
        max_length=50
    )

    description_input = discord.ui.TextInput(
        label='Ticket Description',
        placeholder='Description shown in the ticket',
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=4000
    )

    footer_input = discord.ui.TextInput(
        label='Ticket Footer',
        placeholder='Footer text (default: Ticket Bot)',
    )

    close_button_input = discord.ui.TextInput(
        label='Close Bouton',
        placeholder='Universal Emoji or Other...',
        required=False,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        data = load_ticket_data()
        sub_panels = data["tickets"][self.panel_id]["sub_panels"]

        # Create new sub-panel ID - find the next available ID
        existing_ids = [int(id_str) for id_str in sub_panels.keys() if id_str.isdigit()]
        if existing_ids:
            sub_panel_id = str(max(existing_ids) + 1)
        else:
            sub_panel_id = "1"

        # Initialize counter for this sub-panel name if it doesn't exist
        if "ticket_counters" not in data:
            data["ticket_counters"] = {}
        if self.name_input.value not in data["ticket_counters"]:
            data["ticket_counters"][self.name_input.value] = 0

        # Create sub-panel with all required fields
        sub_panel = {
            "id": sub_panel_id,
            "name": self.name_input.value,
            "title": self.ticket_title_input.value,
            "description": self.name_input.value + " ticket type",
            "permissions": copy.deepcopy(DEFAULT_PERMISSIONS),
            "ai_enabled": False,
            "button_visible": True,
            "button_emoji": "<:TicketLOGO:1407730639343714397>",
            "button_text": "",
            "ticket_title": self.ticket_title_input.value,
            "ticket_description": self.description_input.value or "Support will be with you shortly. To close this ticket.",
            "ticket_footer": self.footer_input.value or f"{get_bot_name()} - Ticket Bot",
            "close_button_text": self.close_button_input.value or "<:CloseLOGO:1407072519420248256>",
            "panel_emoji": "<:TicketLOGO:1407730639343714397>",
            "panel_title": self.ticket_title_input.value,
            "panel_description": ""
        }

        sub_panels[sub_panel_id] = sub_panel
        save_ticket_data(data)

        # Return to panel management view
        view = PanelManagementView(self.panel_id)
        embed = create_panel_management_embed(data, self.panel_id)
        await interaction.edit_original_response(embed=embed, view=view)

class PanelInterfaceEditModal(discord.ui.Modal):
    def __init__(self, panel_id, sub_panel_id):
        super().__init__(title='Edit Panel Interface')
        self.panel_id = panel_id
        self.sub_panel_id = sub_panel_id
        data = load_ticket_data()
        sub_panel = data["tickets"][self.panel_id]["sub_panels"][self.sub_panel_id]
        self.panel_emoji_input.default = sub_panel.get("panel_emoji", "<:TicketLOGO:1407730639343714397>")
        self.panel_title_input.default = sub_panel.get("panel_title", sub_panel.get("title", ""))
        self.panel_description_input.default = sub_panel.get("panel_description", "")

    panel_emoji_input = discord.ui.TextInput(
        label='Panel Emoji',
        placeholder='Emoji for panel (default: <:TicketLOGO:1407730639343714397>)',
        required=False,
        max_length=50
    )

    panel_title_input = discord.ui.TextInput(
        label='Panel Title',
        placeholder='Title for the panel',
        required=False,
        max_length=256
    )

    panel_description_input = discord.ui.TextInput(
        label='Panel Description',
        placeholder='Description for the panel',
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=4000
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        data = load_ticket_data()
        sub_panel = data["tickets"][self.panel_id]["sub_panels"][self.sub_panel_id]

        data["tickets"][self.panel_id]["sub_panels"][self.sub_panel_id]["panel_emoji"] = self.panel_emoji_input.value or "<:TicketLOGO:1407730639343714397>"

        # Allow independent Panel Title editing (doesn't affect ticket_title)
        new_panel_title = self.panel_title_input.value or sub_panel.get("title", "")
        data["tickets"][self.panel_id]["sub_panels"][self.sub_panel_id]["panel_title"] = new_panel_title

        data["tickets"][self.panel_id]["sub_panels"][self.sub_panel_id]["panel_description"] = self.panel_description_input.value or ""

        # Update button emoji to match panel emoji
        data["tickets"][self.panel_id]["sub_panels"][self.sub_panel_id]["button_emoji"] = self.panel_emoji_input.value or "<:TicketLOGO:1407730639343714397>"

        save_ticket_data(data)

        # Return to sub-panel edit view
        view = SubPanelEditView(self.panel_id, self.sub_panel_id)
        embed = create_sub_panel_edit_embed(data, self.panel_id, self.sub_panel_id)
        await interaction.edit_original_response(embed=embed, view=view)

class PanelManagementView(discord.ui.View):
    def __init__(self, panel_id):
        super().__init__(timeout=None)
        self.panel_id = panel_id

    @discord.ui.button(label='Create Sub-Panel', style=discord.ButtonStyle.success, emoji='➕', row=0)
    async def create_sub_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SubPanelCreateModal(self.panel_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Edit Sub-Panel', style=discord.ButtonStyle.primary, emoji='<:EditLOGO:1407071307022995508>', row=0)
    async def edit_sub_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Reload data to get latest changes
        data = load_ticket_data()
        sub_panels = data["tickets"][self.panel_id]["sub_panels"]

        if not sub_panels:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> No sub-panels to edit.", ephemeral=True)
            return

        view = discord.ui.View(timeout=None)
        view.add_item(SubPanelSelect(self.panel_id, "edit"))
        view.add_item(BackButton("panel_management", self.panel_id))

        embed = discord.Embed(
            title="<:EditLOGO:1407071307022995508> Edit Sub-Panel",
            description="Select the sub-panel you want to edit:",
            color=0x2b2d31
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='Delete Sub-Panel', style=discord.ButtonStyle.danger, emoji='<:DeleteLOGO:1407071421363916841>', row=0)
    async def delete_sub_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_data()
        sub_panels = data["tickets"][self.panel_id]["sub_panels"]

        if len(sub_panels) <= 1:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Cannot delete the last sub-panel.", ephemeral=True)
            return

        view = discord.ui.View(timeout=None)
        view.add_item(SubPanelSelect(self.panel_id, "delete"))
        view.add_item(BackButton("panel_management", self.panel_id))

        embed = discord.Embed(
            title="<:DeleteLOGO:1407071421363916841> Delete Sub-Panel",
            description="<:WarningLOGO:1407072569487659198> **Warning:** This action is irreversible!\n\nSelect the sub-panel to delete:",
            color=0xed4245
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='Edit Panel', style=discord.ButtonStyle.primary, emoji='<:EditLOGO:1407071307022995508>', row=1)
    async def edit_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_data()
        current_panel = data["tickets"][self.panel_id]
        modal = PanelEditModal(self.panel_id, current_panel)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Display Type', style=discord.ButtonStyle.secondary, emoji='<:UpdateLOGO:1407072818214080695>', row=1)
    async def toggle_display_type(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_data()
        current_type = data["tickets"][self.panel_id].get("display_type", "buttons")
        new_type = "dropdown" if current_type == "buttons" else "buttons"
        data["tickets"][self.panel_id]["display_type"] = new_type
        save_ticket_data(data)

        view = PanelManagementView(self.panel_id)
        embed = create_panel_management_embed(data, self.panel_id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='Back', style=discord.ButtonStyle.secondary, emoji='<:BackLOGO:1407071474233114766>', row=2)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = TicketPanelView()
        data = load_ticket_data()
        embed = create_ticket_panel_embed(data)
        await interaction.response.edit_message(embed=embed, view=view)

class SubPanelSelect(discord.ui.Select):
    def __init__(self, panel_id, action_type):
        self.panel_id = panel_id
        self.action_type = action_type

        # Reload data to get the most current information
        data = load_ticket_data()
        
        # Check if panel still exists
        if panel_id not in data.get("tickets", {}):
            options = [discord.SelectOption(
                label="Panel not found",
                value="none",
                description="This panel no longer exists"
            )]
        else:
            sub_panels = data["tickets"][panel_id]["sub_panels"]
            options = []
            for sub_panel_id, sub_panel in sub_panels.items():
                ai_status = "🤖" if sub_panel.get("ai_enabled", False) else ""
                description = f"Name: {sub_panel['name']} {ai_status}"
                # Use the most current title information, prioritizing ticket_title, then panel_title, then title
                current_title = sub_panel.get("ticket_title") or sub_panel.get("panel_title") or sub_panel.get("title", "Ticket")
                options.append(discord.SelectOption(
                    label=current_title,
                    value=sub_panel_id,
                    description=description
                ))

        super().__init__(placeholder=f"Select a sub-panel to {action_type}", options=options)

    async def callback(self, interaction: discord.Interaction):
        try:
            sub_panel_id = self.values[0]
            
            # Handle case where panel doesn't exist
            if sub_panel_id == "none":
                await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> This panel no longer exists. Please refresh the interface.", ephemeral=True)
                return
            
            # Reload data again to ensure we have the latest information
            data = load_ticket_data()

            # Verify panel and sub-panel still exist
            if self.panel_id not in data.get("tickets", {}):
                await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> This panel no longer exists. Please refresh the interface.", ephemeral=True)
                return
                
            if sub_panel_id not in data["tickets"][self.panel_id].get("sub_panels", {}):
                await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> This sub-panel no longer exists. Please refresh the interface.", ephemeral=True)
                return

            if self.action_type == "edit":
                view = SubPanelEditView(self.panel_id, sub_panel_id)
                embed = create_sub_panel_edit_embed(data, self.panel_id, sub_panel_id)
                await interaction.response.edit_message(embed=embed, view=view)
            elif self.action_type == "delete":
                # Delete sub-panel
                del data["tickets"][self.panel_id]["sub_panels"][sub_panel_id]
                save_ticket_data(data)

                # Return to panel management
                view = PanelManagementView(self.panel_id)
                embed = create_panel_management_embed(data, self.panel_id)
                await interaction.response.edit_message(embed=embed, view=view)
                
        except Exception as e:
            print(f"Error in SubPanelSelect callback: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> An error occurred. Please try again or refresh the interface.", ephemeral=True)
            else:
                await interaction.followup.send("<:ErrorLOGO:1407071682031648850> An error occurred. Please try again or refresh the interface.", ephemeral=True)

class SubPanelEditView(discord.ui.View):
    def __init__(self, panel_id, sub_panel_id):
        super().__init__(timeout=None)
        self.panel_id = panel_id
        self.sub_panel_id = sub_panel_id

    @discord.ui.button(label='Permissions', style=discord.ButtonStyle.primary, emoji='<:ParticipantsLOGO:1407733929389199460>', row=0)
    async def manage_permissions(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = PermissionSelectView(self.panel_id, self.sub_panel_id)
        embed = discord.Embed(
            title="<:ParticipantsLOGO:1407733929389199460> Permission Management",
            description="Select the permission type you want to modify:",
            color=0x2b2d31
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='Toggle Visibility', style=discord.ButtonStyle.secondary, emoji='👁️', row=0)
    async def toggle_visibility(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_data()
        current_visibility = data["tickets"][self.panel_id]["sub_panels"][self.sub_panel_id].get("button_visible", True)
        data["tickets"][self.panel_id]["sub_panels"][self.sub_panel_id]["button_visible"] = not current_visibility
        save_ticket_data(data)

        view = SubPanelEditView(self.panel_id, self.sub_panel_id)
        embed = create_sub_panel_edit_embed(data, self.panel_id, self.sub_panel_id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='Edit Panel Interface', style=discord.ButtonStyle.primary, emoji='<:EditLOGO:1407071307022995508>', row=1)
    async def edit_panel_interface(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PanelInterfaceEditModal(self.panel_id, self.sub_panel_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Edit Description', style=discord.ButtonStyle.primary, emoji='<:DescriptionLOGO:1407733417172533299>', row=1)
    async def edit_description(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SubPanelDescriptionEditModal(self.panel_id, self.sub_panel_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Back', style=discord.ButtonStyle.secondary, emoji='<:BackLOGO:1407071474233114766>', row=2)
    async def back_to_panel_management(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = PanelManagementView(self.panel_id)
        data = load_ticket_data()
        embed = create_panel_management_embed(data, self.panel_id)
        await interaction.response.edit_message(embed=embed, view=view)

class SubPanelDescriptionEditModal(discord.ui.Modal, title='Edit Sub-Panel Description'):
    def __init__(self, panel_id, sub_panel_id):
        super().__init__()
        self.panel_id = panel_id
        self.sub_panel_id = sub_panel_id
        data = load_ticket_data()
        sub_panel = data["tickets"][self.panel_id]["sub_panels"][self.sub_panel_id]
        self.ticket_title_input.default = sub_panel.get("ticket_title", "Ticket")
        self.description_input.default = sub_panel.get("ticket_description", "Support will be with you shortly. To close this ticket.")
        self.footer_input.default = sub_panel.get("ticket_footer", f"{get_bot_name()} - Ticket Bot")
        self.close_button_input.default = sub_panel.get("close_button_text", "<:CloseLOGO:1407072519420248256>")

    ticket_title_input = discord.ui.TextInput(
        label='Ticket Title',
        placeholder='Title of the ticket embed',
        required=False,
        max_length=256
    )

    description_input = discord.ui.TextInput(
        label='Ticket Description',
        placeholder='Description for the ticket',
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=4000
    )

    footer_input = discord.ui.TextInput(
        label='Ticket Footer',
        placeholder='Footer for the ticket',
        required=False,
        max_length=2048
    )

    close_button_input = discord.ui.TextInput(
        label='Close Bouton',
        placeholder='Close button text/emoji',
        required=False,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        data = load_ticket_data()

        # Update ticket title with new value or default to "Ticket"
        new_ticket_title = self.ticket_title_input.value or "Ticket"
        data["tickets"][self.panel_id]["sub_panels"][self.sub_panel_id]["ticket_title"] = new_ticket_title

        # Synchronize Panel Title with Ticket Title (Edit Sub-Panel Description has priority)
        data["tickets"][self.panel_id]["sub_panels"][self.sub_panel_id]["panel_title"] = new_ticket_title

        # Update other fields
        data["tickets"][self.panel_id]["sub_panels"][self.sub_panel_id]["ticket_description"] = self.description_input.value or "Support will be with you shortly. To close this ticket."
        data["tickets"][self.panel_id]["sub_panels"][self.sub_panel_id]["ticket_footer"] = self.footer_input.value or f"{get_bot_name()} - Ticket Bot"
        data["tickets"][self.panel_id]["sub_panels"][self.sub_panel_id]["close_button_text"] = self.close_button_input.value or "<:CloseLOGO:1407072519420248256>"

        save_ticket_data(data)

        # Return to sub-panel edit view
        view = SubPanelEditView(self.panel_id, self.sub_panel_id)
        embed = create_sub_panel_edit_embed(data, self.panel_id, self.sub_panel_id)
        await interaction.edit_original_response(embed=embed, view=view)

class PermissionButtonView(discord.ui.View):
    def __init__(self, panel_id, sub_panel_id, permission_type):
        super().__init__(timeout=300)
        self.panel_id = panel_id
        self.sub_panel_id = sub_panel_id
        self.permission_type = permission_type

        data = load_ticket_data()
        permissions = data["tickets"][self.panel_id]["sub_panels"][self.sub_panel_id]["permissions"][self.permission_type]
        perm_keys = list(permissions.keys())

        # Create 16 buttons (4 rows of 4)
        for i in range(16):
            if i < len(perm_keys):
                perm_key = perm_keys[i]
                enabled = permissions[perm_key]
                style = discord.ButtonStyle.success if enabled else discord.ButtonStyle.danger
                emoji = "<:SucessLOGO:1407071637840592977>" if enabled else "<:ErrorLOGO:1407071682031648850>"
            else:
                style = discord.ButtonStyle.secondary
                emoji = "➖"

            button = discord.ui.Button(
                label=str(i + 1),
                style=style,
                emoji=emoji,
                row=i // 4,
                custom_id=f"perm_{i}"
            )
            button.callback = self.create_button_callback(i)
            self.add_item(button)

        # Add back button
        back_button = discord.ui.Button(
            label="Back",
            style=discord.ButtonStyle.secondary,
            emoji="<:BackLOGO:1407071474233114766>",
            row=4
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    def create_button_callback(self, index):
        async def button_callback(interaction):
            data = load_ticket_data()
            permissions = data["tickets"][self.panel_id]["sub_panels"][self.sub_panel_id]["permissions"][self.permission_type]
            perm_keys = list(permissions.keys())

            if index < len(perm_keys):
                perm_key = perm_keys[index]
                permissions[perm_key] = not permissions[perm_key]
                save_ticket_data(data)

                # Update the view
                new_view = PermissionButtonView(self.panel_id, self.sub_panel_id, self.permission_type)
                embed = create_permission_button_embed(self.panel_id, self.sub_panel_id, self.permission_type)
                await interaction.response.edit_message(embed=embed, view=new_view)
            else:
                await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Permission slot not available", ephemeral=True)

        return button_callback

    async def back_callback(self, interaction):
        view = PermissionSelectView(self.panel_id, self.sub_panel_id)
        embed = discord.Embed(
            title="<:ParticipantsLOGO:1407733929389199460> Permission Management",
            description="Select the permission type you want to modify:",
            color=0x2b2d31
        )
        await interaction.response.edit_message(embed=embed, view=view)

# Select classes
class TicketSelect(discord.ui.Select):
    def __init__(self, tickets, action_type):
        self.action_type = action_type

        if action_type == "edit":
            placeholder = "Select a ticket panel to edit"
        elif action_type == "delete":
            placeholder = "Select a ticket panel to delete"
        elif action_type == "publish":
            placeholder = "Select a ticket panel to publish"
        else:
            placeholder = "Select a ticket panel"

        options = []
        for panel_id, ticket in tickets.items():
            # Handle missing 'name' field for backward compatibility
            ticket_name = ticket.get("name", "unknown")
            if ticket_name == "unknown" and "sub_panels" in ticket:
                first_sub_panel = next(iter(ticket["sub_panels"].values()), {})
                ticket_name = first_sub_panel.get("name", "unknown")

            description = f"Name: {ticket_name} | {ticket['description'][:30]}{'...' if len(ticket['description']) > 30 else ''}"
            options.append(discord.SelectOption(
                label=ticket["title"],
                value=panel_id,
                description=description
            ))

        if not options:
            options.append(discord.SelectOption(
                label="No ticket panels available",
                value="none",
                description="Create a ticket panel first"
            ))

        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> No ticket panels available.", ephemeral=True)
            return

        panel_id = self.values[0]
        data = load_ticket_data()

        if self.action_type == "edit":
            view = PanelManagementView(panel_id)
            embed = create_panel_management_embed(data, panel_id)
            await interaction.response.edit_message(embed=embed, view=view)
        elif self.action_type == "delete":
            # Show confirmation dialog before deletion
            panel_name = data["tickets"][panel_id]["title"]
            view = PanelDeleteConfirmView(panel_id, panel_name)
            embed = discord.Embed(
                title="<:WarningLOGO:1407072569487659198> Confirm Deletion",
                description=f"Are you sure you want to delete the panel **{panel_name}**?\n\n<:WarningLOGO:1407072569487659198> **This action is irreversible!**",
                color=0xed4245
            )
            await interaction.response.edit_message(embed=embed, view=view)
        elif self.action_type == "publish":
            view = ChannelSelectView(panel_id)
            embed = discord.Embed(
                title="<:SendLOGO:1407071529015181443> Publish Ticket Panel",
                description="Select the channel where you want to publish this ticket panel:",
                color=0x2b2d31
            )
            await interaction.response.edit_message(embed=embed, view=view)

class PanelSelect(discord.ui.Select):
    def __init__(self, panel_id, tickets):
        self.panel_id = panel_id

        options = []
        for pid, ticket in tickets.items():
            if pid == panel_id:
                continue
            options.append(discord.SelectOption(
                label=ticket["title"],
                value=pid,
                description=f"Name: {ticket['name']}"
            ))

        if not options:
            options.append(discord.SelectOption(
                label="No other panels available",
                value="none",
                description="Create more panels first"
            ))

        super().__init__(placeholder="Switch to another panel", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> No other panels available.", ephemeral=True)
            return

        new_panel_id = self.values[0]
        data = load_ticket_data()

        view = TicketEditView(new_panel_id)
        embed = create_ticket_edit_overview_embed(data, new_panel_id)
        await interaction.response.edit_message(embed=embed, view=view)

class PermissionSelect(discord.ui.Select):
    def __init__(self, panel_id, sub_panel_id):
        self.panel_id = panel_id
        self.sub_panel_id = sub_panel_id
        options = [
            discord.SelectOption(
                label="Ticket Owner",
                value="owner",
                description="Permissions for ticket owner"
            ),
            discord.SelectOption(
                label="Staff",
                value="staff",
                description="Permissions for staff members"
            ),
            discord.SelectOption(
                label="Authorized Users",
                value="authorized",
                description="Permissions for authorized users"
            )
        ]
        super().__init__(placeholder="Select permission type", options=options)

    async def callback(self, interaction: discord.Interaction):
        permission_type = self.values[0]

        view = PermissionButtonView(self.panel_id, self.sub_panel_id, permission_type)
        embed = create_permission_button_embed(self.panel_id, self.sub_panel_id, permission_type)
        await interaction.response.edit_message(embed=embed, view=view)

class PublishSelectionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.selected_panel = None
        self.selected_channel = None

        # Add panel selector
        self.add_item(PublishPanelSelect())

        # Add channel selector
        self.add_item(PublishChannelSelect())

        # Add back button
        self.add_item(BackButton("main"))

    def update_view(self, interaction):
        """Update the view when selections change"""
        # Clear existing items
        self.clear_items()

        # Re-add selectors
        panel_select = PublishPanelSelect()
        if self.selected_panel:
            panel_select.placeholder = f"Panel: {self.selected_panel['title']}"
        self.add_item(panel_select)

        channel_select = PublishChannelSelect()
        if self.selected_channel:
            channel_select.placeholder = f"Channel: #{self.selected_channel.name}"
        self.add_item(channel_select)

        # Add confirm button if both selections are made
        if self.selected_panel and self.selected_channel:
            confirm_button = discord.ui.Button(
                label="Confirm Publication",
                style=discord.ButtonStyle.success,
                emoji="<:SucessLOGO:1407071637840592977>",
                custom_id="confirm_publish"
            )
            confirm_button.callback = self.confirm_publish
            self.add_item(confirm_button)

        # Add back button
        self.add_item(BackButton("main"))

    async def confirm_publish(self, interaction: discord.Interaction):
        """Confirm and publish the selected panel to the selected channel"""
        try:
            ticket = self.selected_panel
            selected_channel = self.selected_channel

            # Get the actual channel object
            channel = selected_channel
            if hasattr(selected_channel, 'id'):
                channel = interaction.guild.get_channel(selected_channel.id)

            if not channel:
                await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Error: Channel not found.", ephemeral=True)
                return

            # Create ticket embed for publication (in English)
            embed = discord.Embed(
                title=ticket["title"],
                description=ticket["description"],
                color=0x5865f2
            )

            if ticket.get("thumbnail"):
                embed.set_thumbnail(url=ticket["thumbnail"])
            if ticket.get("footer"):
                embed.set_footer(text=ticket["footer"])

            # Create view with ticket buttons/dropdown
            publish_view = PublishedTicketView(ticket["id"])

            # Publish to channel
            await channel.send(embed=embed, view=publish_view)

            # Return to main menu
            view = TicketPanelView()
            data = load_ticket_data()
            main_embed = create_ticket_panel_embed(data)

            await interaction.response.edit_message(
                embed=main_embed,
                view=view
            )

        except Exception as e:
            await interaction.response.send_message(f"<:ErrorLOGO:1407071682031648850> Error during publication: {str(e)}", ephemeral=True)

class PublishPanelSelect(discord.ui.Select):
    def __init__(self):
        data = load_ticket_data()
        tickets = data.get("tickets", {})

        options = []
        for panel_id, ticket in tickets.items():
            # Handle missing 'name' field for backward compatibility
            ticket_name = ticket.get("name", "unknown")
            if ticket_name == "unknown" and "sub_panels" in ticket:
                first_sub_panel = next(iter(ticket["sub_panels"].values()), {})
                ticket_name = first_sub_panel.get("name", "unknown")

            description = f"Name: {ticket_name} | {ticket['description'][:30]}{'...' if len(ticket['description']) > 30 else ''}"
            options.append(discord.SelectOption(
                label=ticket["title"],
                value=panel_id,
                description=description
            ))

        if not options:
            options.append(discord.SelectOption(
                label="No panels available",
                value="none",
                description="Create a ticket panel first"
            ))

        super().__init__(placeholder="Select a ticket panel", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> No ticket panels available.", ephemeral=True)
            return

        panel_id = self.values[0]
        data = load_ticket_data()

        # Store selection in view
        view = self.view
        view.selected_panel = data["tickets"][panel_id]
        view.selected_panel["id"] = panel_id

        # Update the view
        view.update_view(interaction)

        # Create updated embed
        embed = create_publish_selection_embed(view.selected_panel, view.selected_channel)

        await interaction.response.edit_message(embed=embed, view=view)

class PublishChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            placeholder="Select a channel",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        selected_channel = self.values[0]

        # Store selection in view
        view = self.view
        view.selected_channel = selected_channel

        # Update the view
        view.update_view(interaction)

        # Create updated embed
        embed = create_publish_selection_embed(view.selected_panel, view.selected_channel)

        await interaction.response.edit_message(embed=embed, view=view)

def create_publish_selection_embed(selected_panel, selected_channel):
    """Create embed for publish selection interface"""
    embed = discord.Embed(
        title="<:SendLOGO:1407071529015181443> Ticket Panel Publication",
        description="Select the panel and channel for publication:",
        color=0x2b2d31
    )

    # Panel selection status
    if selected_panel:
        embed.add_field(
            name="<:TicketLOGO:1407730639343714397> Selected Panel",
            value=f"**{selected_panel['title']}**\n{selected_panel['description'][:100]}{'...' if len(selected_panel['description']) > 100 else ''}",
            inline=False
        )
    else:
        embed.add_field(
            name="<:TicketLOGO:1407730639343714397> Panel",
            value="<:ErrorLOGO:1407071682031648850> No panel selected",
            inline=True
        )

    # Channel selection status
    if selected_channel:
        embed.add_field(
            name="<:SettingLOGO:1407071854593839239> Selected Channel",
            value=f"**{selected_channel.mention}**",
            inline=False
        )
    else:
        embed.add_field(
            name="<:SettingLOGO:1407071854593839239> Channel",
            value="<:ErrorLOGO:1407071682031648850> No channel selected",
            inline=True
        )

    # Confirmation status
    if selected_panel and selected_channel:
        embed.add_field(
            name="<:SucessLOGO:1407071637840592977> Ready for Publication",
            value="Click **Confirm Publication** to publish the panel.",
            inline=False
        )
        embed.color = 0x57f287
    else:
        embed.set_footer(text="Select a panel and channel to continue")

    return embed

class ChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, panel_id):
        self.panel_id = panel_id
        super().__init__(
            placeholder="Select a channel",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        # This is kept for backward compatibility but redirects to new system
        view = PublishSelectionView()
        embed = create_publish_selection_embed(None, None)
        await interaction.response.edit_message(embed=embed, view=view)

class TicketTypeSelect(discord.ui.Select):
    def __init__(self, panel_id, sub_panels):
        self.panel_id = panel_id

        options = []
        for sub_panel_id, sub_panel in sub_panels.items():
            ai_indicator = "🤖" if sub_panel.get("ai_enabled", False) else ""
            button_emoji = sub_panel.get("panel_emoji", sub_panel.get("button_emoji", "<:TicketLOGO:1407730639343714397>"))
            panel_title = sub_panel.get("panel_title", sub_panel.get("title", "Default Ticket"))
            panel_description = sub_panel.get("panel_description", sub_panel["description"])

            # Use panel_description if available, otherwise fallback to description
            description_text = panel_description if panel_description else sub_panel["description"]
            description = description_text[:100] if len(description_text) > 100 else description_text

            options.append(discord.SelectOption(
                label=f"{panel_title} {ai_indicator}".strip(),
                value=sub_panel_id,
                description=description,
                emoji=button_emoji
            ))

        super().__init__(placeholder="Select ticket type...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        sub_panel_id = self.values[0]
        view = PublishedTicketView(self.panel_id)
        await view.create_ticket_channel(interaction, self.panel_id, sub_panel_id)

class StaffRoleSelect(discord.ui.RoleSelect):
    def __init__(self, action):
        self.action = action
        placeholder = "Add a staff role" if action == "add" else "Remove a staff role"
        super().__init__(placeholder=placeholder, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        role = self.values[0]
        data = load_ticket_data()

        if self.action == "add":
            if role.id not in data["staff_roles"]:
                data["staff_roles"].append(role.id)
        else:  # remove
            if role.id in data["staff_roles"]:
                data["staff_roles"].remove(role.id)

        save_ticket_data(data)

        # Update display
        view = StaffRoleManageView()
        embed = create_staff_role_embed(data, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=view)

# Sub-panel ticket selection view
class SubPanelTicketSelectView(discord.ui.View):
    def __init__(self, panel_id):
        super().__init__(timeout=60)
        self.panel_id = panel_id

        data = load_ticket_data()
        sub_panels = data["tickets"][panel_id]["sub_panels"]

        # Create buttons for each visible sub-panel
        for sub_panel_id, sub_panel in sub_panels.items():
            if not sub_panel.get("button_visible", True):
                continue

            ai_indicator = "<:BotLOGO:1407071803150569472>" if sub_panel.get("ai_enabled", False) else ""
            button_emoji = sub_panel.get("panel_emoji", sub_panel.get("button_emoji", "<:TicketLOGO:1407730639343714397>"))
            button_text = sub_panel.get("button_text", "")
            panel_title = sub_panel.get("panel_title", sub_panel.get("title", "Default Ticket"))

            if button_text:
                button_label = f"{panel_title} {button_text} {ai_indicator}".strip()
            else:
                button_label = f"{panel_title} {ai_indicator}".strip()

            button = discord.ui.Button(
                label=button_label,
                style=discord.ButtonStyle.primary,
                emoji=button_emoji,
                custom_id=f"subpanel_{sub_panel_id}"
            )
            button.callback = self.create_button_callback(sub_panel_id)
            self.add_item(button)

    def create_button_callback(self, sub_panel_id):
        async def button_callback(interaction):
            await self.create_ticket_channel(interaction, self.panel_id, sub_panel_id)
        return button_callback

    async def create_ticket_channel(self, interaction, panel_id, sub_panel_id):
        try:
            data = load_ticket_data()
            sub_panel = data["tickets"][panel_id]["sub_panels"][sub_panel_id]

            # Get next ticket number
            ticket_number = get_next_ticket_number(data, sub_panel["name"])
            channel_name = f"{sub_panel['name']}-{ticket_number:04d}"

            # Create new ticket channel
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )
            }

            # Add staff roles permissions
            for role_id in data["staff_roles"]:
                role = interaction.guild.get_role(role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        manage_messages=True,
                        read_message_history=True
                    )

            # Create the channel
            ticket_channel = await interaction.guild.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                reason=f"Ticket created by {interaction.user}"
            )

            # Save ticket data
            save_ticket_data(data)

            # Track ticket status
            update_ticket_status(ticket_channel.id, {
                "original_name": channel_name,
                "status": "open",
                "created_by": interaction.user.id,
                "created_at": datetime.now().isoformat(),
                "ticket_type": sub_panel["name"],
                "transcript_saved": False
            })

            # Create ticket embed
            ticket_title = sub_panel.get("ticket_title", "Default Ticket")
            ticket_description = sub_panel.get("ticket_description", "Support will be with you shortly. To close this ticket.")

            # Ensure description is not empty
            if not ticket_description or ticket_description.strip() == "":
                ticket_description = "Support will be with you shortly. To close this ticket."

            embed = discord.Embed(
                title=f"<:TicketLOGO:1407730639343714397> {ticket_title}",
                description=ticket_description if ticket_description else "Support will be with you shortly. To close this ticket.",
                color=0x5865f2
            )

            if data["settings"]["default_embed"].get("thumbnail"):
                embed.set_thumbnail(url=data["settings"]["default_embed"]["thumbnail"])

            footer_text = sub_panel.get("ticket_footer", f"{get_bot_name()} - Ticket Bot")
            embed.set_footer(text=footer_text)

            # Create close button view with custom close button text
            close_button_text = sub_panel.get("close_button_text", "<:CloseLOGO:1407072519420248256>")
            close_view = TicketCloseView(close_button_text, ticket_channel.id)

            # Send ticket message
            welcome_message = f"{interaction.user.mention} Welcome to your ticket!"

            await ticket_channel.send(
                content=welcome_message,
                embed=embed,
                view=close_view
            )

            # Log ticket opening
            await log_ticket_action(interaction.guild, "ticket_opened", {
                "channel": ticket_channel.mention,
                "created_by": interaction.user,
                "ticket_type": sub_panel["name"]
            })

            await interaction.response.send_message(
                f"<:SucessLOGO:1407071637840592977> Ticket created! {ticket_channel.mention}",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(f"<:ErrorLOGO:1407071682031648850> Error creating ticket: {str(e)}", ephemeral=True)

# Published Ticket View (for the actual ticket panel message)
class PublishedTicketView(discord.ui.View):
    def __init__(self, panel_id):
        super().__init__(timeout=None)
        self.panel_id = panel_id

        data = load_ticket_data()
        display_type = data["tickets"][panel_id].get("display_type", "buttons")
        sub_panels = data["tickets"][panel_id]["sub_panels"]

        # Only show visible sub-panels
        visible_sub_panels = {k: v for k, v in sub_panels.items() if v.get("button_visible", True)}

        if display_type == "buttons":
            # Create buttons for each visible sub-panel
            for sub_panel_id, sub_panel in visible_sub_panels.items():
                ai_indicator = "<:BotLOGO:1407071803150569472>" if sub_panel.get("ai_enabled", False) else ""
                button_emoji = sub_panel.get("panel_emoji", sub_panel.get("button_emoji", "<:TicketLOGO:1407730639343714397>"))
                button_text = sub_panel.get("button_text", "")
                panel_title = sub_panel.get("panel_title", sub_panel.get("title", "Default Ticket"))

                if button_text:
                    button_label = f"{panel_title} {button_text} {ai_indicator}".strip()
                else:
                    button_label = f"{panel_title} {ai_indicator}".strip()

                button = discord.ui.Button(
                    label=button_label,
                    style=discord.ButtonStyle.primary,
                    emoji=button_emoji,
                    custom_id=f"ticket_{sub_panel_id}"
                )
                button.callback = self.create_button_callback(sub_panel_id)
                self.add_item(button)
        else:
            # Create dropdown menu - always use dropdown when display_type is dropdown
            self.add_item(TicketTypeSelect(panel_id, visible_sub_panels))

    def create_button_callback(self, sub_panel_id):
        async def button_callback(interaction):
            await self.create_ticket_channel(interaction, self.panel_id, sub_panel_id)
        return button_callback

    async def create_ticket_channel(self, interaction, panel_id, sub_panel_id):
        try:
            data = load_ticket_data()
            sub_panel = data["tickets"][panel_id]["sub_panels"][sub_panel_id]

            # Get next ticket number
            ticket_number = get_next_ticket_number(data, sub_panel["name"])
            channel_name = f"{sub_panel['name']}-{ticket_number:04d}"

            # Create new ticket channel
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )
            }

            # Add staff roles permissions
            for role_id in data["staff_roles"]:
                role = interaction.guild.get_role(role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        manage_messages=True,
                        read_message_history=True
                    )

            # Create the channel
            ticket_channel = await interaction.guild.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                reason=f"Ticket created by {interaction.user}"
            )

            # Save ticket data
            save_ticket_data(data)

            # Track ticket status
            update_ticket_status(ticket_channel.id, {
                "original_name": channel_name,
                "status": "open",
                "created_by": interaction.user.id,
                "created_at": datetime.now().isoformat(),
                "ticket_type": sub_panel["name"],
                "transcript_saved": False
            })

            # Create ticket embed
            ticket_title = sub_panel.get("ticket_title", "Default Ticket")
            ticket_description = sub_panel.get("ticket_description", "Support will be with you shortly. To close this ticket.")

            # Ensure description is not empty
            if not ticket_description or ticket_description.strip() == "":
                ticket_description = "Support will be with you shortly. To close this ticket."

            embed = discord.Embed(
                title=f"<:TicketLOGO:1407730639343714397> {ticket_title}",
                description=ticket_description if ticket_description else "Support will be with you shortly. To close this ticket.",
                color=0x5865f2
            )

            if data["settings"]["default_embed"].get("thumbnail"):
                embed.set_thumbnail(url=data["settings"]["default_embed"]["thumbnail"])

            footer_text = sub_panel.get("ticket_footer", f"{get_bot_name()} - Ticket Bot")
            embed.set_footer(text=footer_text)

            # Create close button view with custom close button text
            close_button_text = sub_panel.get("close_button_text", "<:CloseLOGO:1407072519420248256>")
            close_view = TicketCloseView(close_button_text, ticket_channel.id)

            # Send ticket message
            welcome_message = f"{interaction.user.mention} Welcome to your ticket!"

            await ticket_channel.send(
                content=welcome_message,
                embed=embed,
                view=close_view
            )

            # Log ticket opening
            await log_ticket_action(interaction.guild, "ticket_opened", {
                "channel": ticket_channel.mention,
                "created_by": interaction.user,
                "ticket_type": sub_panel["name"]
            })

            await interaction.response.send_message(
                f"<:SucessLOGO:1407071637840592977> Ticket created! {ticket_channel.mention}",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(f"<:ErrorLOGO:1407071682031648850> Error creating ticket: {str(e)}", ephemeral=True)

class TicketCloseView(discord.ui.View):
    def __init__(self, close_button_text="<:CloseLOGO:1407072519420248256>", channel_id=None):
        super().__init__(timeout=None)
        self.channel_id = channel_id

        # Load settings for button customization
        data = load_ticket_data()
        button_enabled = data["settings"].get("button_enabled", True)

        if button_enabled:
            # Use custom close button text if provided, otherwise use default settings
            if close_button_text and close_button_text != "<:CloseLOGO:1407072519420248256>":
                close_button = discord.ui.Button(
                    label=close_button_text,
                    style=discord.ButtonStyle.danger,
                    custom_id='persistent_close_ticket_btn'
                )
            else:
                button_emoji = data["settings"].get("button_emoji", "<:CloseLOGO:1407072519420248256>")
                button_label = data["settings"].get("button_label", "Close Ticket")
                close_button = discord.ui.Button(
                    label=button_label,
                    style=discord.ButtonStyle.danger,
                    emoji=button_emoji,
                    custom_id='persistent_close_ticket_btn'
                )

            close_button.callback = self.close_ticket
            self.add_item(close_button)

    async def close_ticket(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="<:TicketLOGO:1407730639343714397> Close Ticket",
            description="Are you sure you want to close this ticket?",
            color=0xed4245
        )

        confirm_view = ConfirmCloseView()
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)

class ConfirmCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label='Yes', style=discord.ButtonStyle.danger, emoji='<:ConfirmLOGO:1407072680267481249>')
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Save ticket data before closing
            data = load_ticket_data()
            if "closed_tickets" not in data:
                data["closed_tickets"] = {}

            ticket_name = interaction.channel.name
            ticket_data = {
                "original_name": ticket_name,
                "channel_id": interaction.channel.id,
                "closed_by": interaction.user.id,
                "closed_at": datetime.now().isoformat(),
                "permissions": {}
            }

            # Save current permissions
            for member in interaction.channel.members:
                if not member.bot:
                    perms = interaction.channel.permissions_for(member)
                    ticket_data["permissions"][str(member.id)] = {
                        "view_channel": perms.view_channel,
                        "send_messages": perms.send_messages,
                        "read_message_history": perms.read_message_history
                    }

            data["closed_tickets"][str(interaction.channel.id)] = ticket_data
            save_ticket_data(data)

            # Send closing message
            closing_embed = discord.Embed(
                title="<a:LoadingLOGO:1407732919476424814> Closing Ticket...",
                description="Closing the ticket in 3 seconds...",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=closing_embed, ephemeral=False)
            await asyncio.sleep(3)

            # Remove non-staff members
            staff_roles = data["staff_roles"]
            staff_members = []
            for role_id in staff_roles:
                role = interaction.guild.get_role(role_id)
                if role:
                    for member in role.members:
                        staff_members.append(member.id)

            for member in interaction.channel.members:
                if not member.bot and member.id not in staff_members and not member.guild_permissions.administrator:
                    await interaction.channel.set_permissions(member, view_channel=False)

            # Rename the ticket (with delay to avoid rate limiting)
            ticket_type = ticket_name.split('-')[0]
            new_channel_name = f"closed-{ticket_type}-{ticket_name.split('-')[1]}"

            # Only rename if it's not already closed
            if not interaction.channel.name.startswith("closed-"):
                await asyncio.sleep(1)  # Small delay to prevent rate limiting
                await interaction.channel.edit(name=new_channel_name)


            # Log ticket closing
            await log_ticket_action(interaction.guild, "ticket_closed", {
                "channel": interaction.channel.mention,
                "closed_by": interaction.user
            })

            # Send closed actions view
            closed_embed = discord.Embed(
                title="<:CloseLOGO:1407072519420248256> Ticket Closed",
                description="This ticket has been closed. What would you like to do?",
                color=0x57f287
            )

            closed_view = TicketClosedActionsView()
            await interaction.channel.send(embed=closed_embed, view=closed_view)

            # Update ticket status
            update_ticket_status(interaction.channel.id, {"status": "closed"})

        except Exception as e:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"<:ErrorLOGO:1407071682031648850> Error closing ticket: {str(e)}", ephemeral=True)
            else:
                await interaction.followup.send(f"<:ErrorLOGO:1407071682031648850> Error closing ticket: {str(e)}", ephemeral=True)

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.secondary, emoji='<:CloseLOGO:1407072519420248256>')
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Ticket close cancelled.", embed=None, view=None)

# Main Views
class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Create', style=discord.ButtonStyle.success, emoji='<:CreateLOGO:1407071205026168853>', row=0)
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = TicketCreateModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Edit', style=discord.ButtonStyle.primary, emoji='<:EditLOGO:1407071307022995508>', row=0)
    async def edit_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_data()

        tickets = data.get("tickets", {})
        if not tickets:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> No ticket panels to edit.", ephemeral=True)
            return

        view = discord.ui.View(timeout=None)
        view.add_item(TicketSelect(tickets, "edit"))
        view.add_item(BackButton("main"))

        embed = discord.Embed(
            title="<:EditLOGO:1407071307022995508> Edit Ticket Panel",
            description="Select the ticket panel you want to edit:",
            color=0x2b2d31
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='Delete', style=discord.ButtonStyle.danger, emoji='<:DeleteLOGO:1407071421363916841>', row=0)
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_data()
        tickets = data.get("tickets", {})
        if not tickets:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> No ticket panels to delete.", ephemeral=True)
            return

        view = discord.ui.View(timeout=None)
        view.add_item(TicketSelect(tickets, "delete"))
        view.add_item(BackButton("main"))

        embed = discord.Embed(
            title="<:DeleteLOGO:1407071421363916841> Delete Ticket Panel",
            description="<:WarningLOGO:1407072569487659198> **Warning:** This action is irreversible!\n\nSelect the panel to delete:",
            color=0xed4245
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='Publish', style=discord.ButtonStyle.secondary, emoji='<:SendLOGO:1407071529015181443>', row=1)
    async def publish_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_data()
        tickets = data.get("tickets", {})
        if not tickets:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> No ticket panels to publish.", ephemeral=True)
            return

        view = PublishSelectionView()
        embed = create_publish_selection_embed(None, None)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='Logs', style=discord.ButtonStyle.secondary, emoji='<:SettingLOGO:1407071854593839239>', row=1)
    async def logs_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = LogsManagementView()
        embed = create_logs_management_embed(load_ticket_data(), interaction.guild)
        await interaction.response.edit_message(embed=embed, view=view)

class TicketEditView(discord.ui.View):
    def __init__(self, panel_id):
        super().__init__(timeout=None)
        self.panel_id = panel_id

        # Add panel selector dropdown
        data = load_ticket_data()
        if len(data["tickets"]) > 1:
            self.add_item(PanelSelect(panel_id, data["tickets"]))

    @discord.ui.button(label='Manage', style=discord.ButtonStyle.primary, emoji='<:EditLOGO:1407071307022995508>', row=1)
    async def manage_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = PanelManagementView(self.panel_id)
        data = load_ticket_data()
        embed = create_panel_management_embed(data, self.panel_id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='Delete Panel', style=discord.ButtonStyle.danger, emoji='<:DeleteLOGO:1407071421363916841>', row=1)
    async def delete_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_data()
        if self.panel_id in data["tickets"]:
            panel_name = data["tickets"][self.panel_id]["title"]
            del data["tickets"][self.panel_id]
            save_ticket_data(data)

        view = TicketPanelView()
        embed = create_ticket_panel_embed(data)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='Back', style=discord.ButtonStyle.secondary, emoji='<:BackLOGO:1407071474233114766>', row=1)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = TicketPanelView()
        data = load_ticket_data()
        embed = create_ticket_panel_embed(data)
        await interaction.response.edit_message(embed=embed, view=view)

class TicketEditDetailView(discord.ui.View):
    def __init__(self, panel_id):
        super().__init__(timeout=None)
        self.panel_id = panel_id

    @discord.ui.button(label='Permissions', style=discord.ButtonStyle.primary, emoji='<:ParticipantsLOGO:1407733929389199460>', row=0)
    async def manage_permissions(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = PermissionSelectView(self.panel_id)
        embed = discord.Embed(
            title="<:ParticipantsLOGO:1407733929389199460> Permission Management",
            description="Select the permission type you want to modify:",
            color=0x2b2d31
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='Embed Content', style=discord.ButtonStyle.primary, emoji='<:DescriptionLOGO:1407733417172533299>', row=0)
    async def edit_embed_content(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = EmbedContentEditView()
        embed = create_embed_content_edit_embed(load_ticket_data())
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='Staff Roles', style=discord.ButtonStyle.primary, emoji='<:ParticipantsLOGO:1407733929389199460>', row=1)
    async def manage_staff_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = StaffRoleManageView()
        data = load_ticket_data()
        embed = create_staff_role_embed(data, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='Ticket Name', style=discord.ButtonStyle.secondary, emoji='<:TicketLOGO:1407730639343714397>', row=1)
    async def edit_ticket_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_data()
        current_name = data["tickets"][self.panel_id]["name"]
        modal = TicketNameEditModal(self.panel_id, current_name)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Back', style=discord.ButtonStyle.secondary, emoji='<:BackLOGO:1407071474233114766>', row=1)
    async def back_to_overview(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = TicketEditView(self.panel_id)
        data = load_ticket_data()
        embed = create_ticket_edit_overview_embed(data, self.panel_id)
        await interaction.response.edit_message(embed=embed, view=view)

class PermissionSelectView(discord.ui.View):
    def __init__(self, panel_id, sub_panel_id):
        super().__init__(timeout=None)
        self.add_item(PermissionSelect(panel_id, sub_panel_id))
        self.add_item(BackButton("sub_panel_edit", panel_id, sub_panel_id))

class PermissionEditView(discord.ui.View):
    def __init__(self, panel_id, permission_type):
        super().__init__(timeout=None)
        self.panel_id = panel_id
        self.permission_type = permission_type

    @discord.ui.button(label='Reset', style=discord.ButtonStyle.secondary, emoji='<:UpdateLOGO:1407072818214080695>')
    async def reset_permissions(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_data()
        data["tickets"][self.panel_id]["sub_panels"][self.sub_panel_id]["permissions"][self.permission_type] = copy.deepcopy(DEFAULT_PERMISSIONS[self.permission_type])
        save_ticket_data(data)

        embed = create_permission_edit_embed(self.panel_id, self.permission_type)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='Modify', style=discord.ButtonStyle.primary, emoji='<:EditLOGO:1407071307022995508>')
    async def modify_permissions(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_data()
        permissions = data["tickets"][self.panel_id]["sub_panels"][self.sub_panel_id]["permissions"][self.permission_type]

        modal = PermissionEditModal(self.panel_id, self.permission_type, permissions)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Back', style=discord.ButtonStyle.secondary, emoji='<:BackLOGO:1407071474233114766>')
    async def back_to_permissions(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = PermissionSelectView(self.panel_id, self.sub_panel_id)
        embed = discord.Embed(
            title="<:ParticipantsLOGO:1407733929389199460> Permission Management",
            description="Select the permission type you want to modify:",
            color=0x2b2d31
        )
        await interaction.response.edit_message(embed=embed, view=view)

class EmbedContentEditView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Edit Message', style=discord.ButtonStyle.primary, emoji='<:EditLOGO:1407071307022995508>', row=0)
    async def edit_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_data()
        modal = TicketEmbedEditModal(data["settings"]["default_embed"])
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Back', style=discord.ButtonStyle.secondary, emoji='<:BackLOGO:1407071474233114766>', row=0)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = TicketPanelView()
        data = load_ticket_data()
        embed = create_ticket_panel_embed(data)
        await interaction.response.edit_message(embed=embed, view=view)

class StaffRoleManageView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Add Role', style=discord.ButtonStyle.success, emoji='➕')
    async def add_staff_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View(timeout=None)
        view.add_item(StaffRoleSelect("add"))
        view.add_item(BackButton("staff_manage"))

        embed = discord.Embed(
            title="➕ Add Staff Role",
            description="Select the role to add:",
            color=0x57f287
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='Remove Role', style=discord.ButtonStyle.danger, emoji='➖')

    async def remove_staff_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View(timeout=None)
        view.add_item(StaffRoleSelect("remove"))
        view.add_item(BackButton("staff_manage"))

        embed = discord.Embed(
            title="➖ Remove Staff Role",
            description="Select the role to remove:",
            color=0xed4245
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='Back', style=discord.ButtonStyle.secondary, emoji='<:BackLOGO:1407071474233114766>')
    async def back_to_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = TicketPanelView()
        data = load_ticket_data()
        embed = create_ticket_panel_embed(data)
        await interaction.response.edit_message(embed=embed, view=view)

class PanelDeleteConfirmView(discord.ui.View):
    def __init__(self, panel_id, panel_name):
        super().__init__(timeout=None)
        self.panel_id = panel_id
        self.panel_name = panel_name

    @discord.ui.button(label='Yes, Delete', style=discord.ButtonStyle.danger, emoji='<:SucessLOGO:1407071637840592977>')
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_data()
        if self.panel_id in data["tickets"]:
            del data["tickets"][self.panel_id]
            save_ticket_data(data)

        # Return to main panel
        view = TicketPanelView()
        embed = create_ticket_panel_embed(data)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.secondary, emoji='<:CloseLOGO:1407072519420248256>')
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Return to main panel
        view = TicketPanelView()
        data = load_ticket_data()
        embed = create_ticket_panel_embed(data)
        await interaction.response.edit_message(embed=embed, view=view)

class ChannelSelectView(discord.ui.View):
    def __init__(self, panel_id):
        super().__init__(timeout=None)
        self.add_item(ChannelSelect(panel_id))
        self.add_item(BackButton("main"))

class BackButton(discord.ui.Button):
    def __init__(self, return_to, panel_id=None, sub_panel_id=None):
        super().__init__(label='Back', style=discord.ButtonStyle.secondary, emoji='<:BackLOGO:1407071474233114766>')
        self.return_to = return_to
        self.panel_id = panel_id
        self.sub_panel_id = sub_panel_id

    async def callback(self, interaction: discord.Interaction):
        data = load_ticket_data()

        if self.return_to == "main":
            view = TicketPanelView()
            embed = create_ticket_panel_embed(data)
        elif self.return_to == "logs":
            view = LogsManagementView()
            embed = create_logs_management_embed(data, interaction.guild)
        elif self.return_to == "edit" and self.panel_id:
            view = TicketEditView(self.panel_id)
            embed = create_ticket_edit_overview_embed(data, self.panel_id)
        elif self.return_to == "panel_management" and self.panel_id:
            view = PanelManagementView(self.panel_id)
            embed = create_panel_management_embed(data, self.panel_id)
        elif self.return_to == "sub_panel_edit" and self.panel_id and hasattr(self, 'sub_panel_id'):
            view = SubPanelEditView(self.panel_id, self.sub_panel_id)
            embed = create_sub_panel_edit_embed(data, self.panel_id, self.sub_panel_id)
        elif self.return_to == "staff_manage":
            view = StaffRoleManageView()
            embed = create_staff_role_embed(data, interaction.guild)
        else:
            view = TicketPanelView()
            embed = create_ticket_panel_embed(data)

        await interaction.response.edit_message(embed=embed, view=view)

# Embed creation functions
def create_ticket_panel_embed(data):
    """Create main panel embed"""
    embed = discord.Embed(
        title="<:TicketLOGO:1407730639343714397> Ticket Management Panel",
        color=0x2b2d31
    )

    # Handle missing 'tickets' key or empty data
    tickets = data.get("tickets", {})

    if not tickets:
        embed.description = "No ticket panels have been created yet."
        embed.add_field(
            name="Getting Started",
            value="Click **Create** to create your first ticket panel.",
            inline=False
        )
    else:
        panels_list = []
        for panel_id, ticket in tickets.items():
            # Get name from first sub-panel if main panel doesn't have one
            ticket_name = ticket.get("name", "unknown")
            if ticket_name == "unknown" and "sub_panels" in ticket:
                first_sub_panel = next(iter(ticket["sub_panels"].values()), {})
                ticket_name = first_sub_panel.get("name", "unknown")

            ticket_title = ticket.get("title", "Untitled Panel")
            counter = data.get("ticket_counters", {}).get(ticket_name, 0)
            panels_list.append(f"**{ticket_title}**\nName: `{ticket_name}` | Counter: `{counter}`")

        embed.description = "\n\n".join(panels_list)

    embed.set_footer(text="Use the buttons below to manage your ticket panels")
    return embed

def create_panel_management_embed(data, panel_id):
    """Create panel management embed"""
    ticket = data["tickets"][panel_id]
    sub_panels = ticket["sub_panels"]
    display_type = ticket.get("display_type", "buttons")

    embed = discord.Embed(
        title=f"<:SettingLOGO:1407071854593839239> Managing Panel: {ticket['title']}",
        description=f"**Panel ID:** `{panel_id}`\n**Sub-Panels Count:** `{len(sub_panels)}`\n**Display Type:** `{display_type.title()}`",
        color=0x2b2d31
    )

    # List sub-panels
    sub_panel_list = []
    for sub_panel_id, sub_panel in sub_panels.items():
        counter = data.get("ticket_counters", {}).get(sub_panel["name"], 0)
        ai_status = "🤖" if sub_panel.get("ai_enabled", False) else ""
        visibility_status = "Visible" if sub_panel.get("button_visible", True) else "Hidden"
        button_emoji = sub_panel.get("button_emoji", "<:TicketLOGO:1407730639343714397>")
        button_text = sub_panel.get("button_text", "")
        button_display = f"{button_emoji} {button_text}".strip()
        sub_panel_list.append(f"**{sub_panel['title']}** {ai_status}\nName: `{sub_panel['name']}` | Counter: `{counter}` | Status: `{visibility_status}`\nButton: `{button_display}`")

    embed.add_field(
        name="Sub-Panels",
        value="\n\n".join(sub_panel_list) if sub_panel_list else "No sub-panels",
        inline=False
    )

    embed.set_footer(text=f"Created: {ticket.get('created_at', 'Unknown')}")
    return embed

def create_sub_panel_edit_embed(data, panel_id, sub_panel_id):
    """Create sub-panel edit embed"""
    sub_panel = data["tickets"][panel_id]["sub_panels"][sub_panel_id]
    counter = data.get("ticket_counters", {}).get(sub_panel["name"], 0)

    embed = discord.Embed(
        title=f"🔧 Editing Sub-Panel: {sub_panel['title']}",
        description=f"**Name:** `{sub_panel['name']}`\n**Counter:** `{counter}`\n**Next Ticket:** `{sub_panel['name']}-{counter+1:04d}`",
        color=0x2b2d31
    )

    ai_status = "<:OnLOGO:1407072463883472978> Enabled" if sub_panel.get("ai_enabled", False) else "<:OffLOGO:1407072621836894380> Disabled"
    embed.add_field(name="AI System", value=ai_status, inline=True)

    visibility_status = "<:OnLOGO:1407072463883472978> Visible" if sub_panel.get("button_visible", True) else "<:OffLOGO:1407072621836894380> Hidden"
    embed.add_field(name="Button Visibility", value=visibility_status, inline=True)

    close_button_text = sub_panel.get("close_button_text", "<:CloseLOGO:1407072519420248256>")
    embed.add_field(name="Close Button", value=f"`{close_button_text}`", inline=True)

    embed.add_field(
        name="Description",
        value=sub_panel["description"][:100] + ("..." if len(sub_panel["description"]) > 100 else ""),
        inline=False
    )

    embed.set_footer(text=f"Sub-Panel ID: {sub_panel_id}")
    return embed

def create_permission_button_embed(panel_id, sub_panel_id, permission_type):
    """Create permission button edit embed"""
    data = load_ticket_data()
    permissions = data["tickets"][panel_id]["sub_panels"][sub_panel_id]["permissions"][permission_type]

    type_names = {
        "owner": "Ticket Owner",
        "staff": "Staff Members",
        "authorized": "Authorized Users"
    }

    embed = discord.Embed(
        title=f"<:ParticipantsLOGO:1407733929389199460> Permissions: {type_names[permission_type]}",
        description="Click the numbered buttons to toggle permissions:",
        color=0x2b2d31
    )

    perm_list = []
    for i, (perm_name, enabled) in enumerate(permissions.items(), 1):
        status = "<:SucessLOGO:1407071637840592977>" if enabled else "<:ErrorLOGO:1407071682031648850>"
        perm_display = perm_name.replace("_", " ").title()
        perm_list.append(f"`{i}.` {status} {perm_display}")

    # Split into chunks for multiple fields
    chunk_size = 8
    chunks = [perm_list[i:i + chunk_size] for i in range(0, len(perm_list), chunk_size)]

    for i, chunk in enumerate(chunks):
        field_name = f"Permissions {i*chunk_size + 1}-{min((i+1)*chunk_size, len(perm_list))}"
        embed.add_field(name=field_name, value="\n".join(chunk), inline=True)

    return embed

def create_ticket_edit_detail_embed(data, panel_id):
    """Create detailed edit menu embed"""
    ticket = data["tickets"][panel_id]

    embed = discord.Embed(
        title=f"🔧 Modifying: {ticket['title']}",
        description="Select the element you want to modify:",
        color=0x2b2d31
    )

    ai_status = "<:OnLOGO:1407072463883472978> Enabled" if data["settings"]["ai_enabled"] else "<:OffLOGO:1407072621836894380> Disabled"
    embed.add_field(name="AI System", value=ai_status, inline=True)

    staff_count = len(data["staff_roles"])
    embed.add_field(name="Staff Roles", value=f"{staff_count} role(s)", inline=True)

    counter = data.get("ticket_counters", {}).get(ticket["name"], 0)
    embed.add_field(name="Ticket Counter", value=f"`{counter}`", inline=True)

    embed.set_footer(text=f"Ticket Name: {ticket['name']} • Panel ID: {panel_id}")
    return embed

def create_ticket_edit_overview_embed(data, panel_id):
    """Create ticket edit overview embed"""
    ticket = data["tickets"][panel_id]

    embed = discord.Embed(
        title=f"<:EditLOGO:1407071307022995508> Editing Panel: {ticket['title']}",
        description=f"**Panel ID:** `{panel_id}`\n**Created:** {ticket.get('created_at', 'Unknown')}",
        color=0x2b2d31
    )

    embed.add_field(
        name="Description",
        value=ticket["description"][:100] + ("..." if len(ticket["description"]) > 100 else ""),
        inline=False
    )

    if ticket.get("thumbnail"):
        embed.add_field(name="Thumbnail", value="<:SucessLOGO:1407071637840592977> Configured", inline=True)

    if ticket.get("footer"):
        embed.add_field(name="Footer", value=f"`{ticket['footer']}`", inline=True)

    embed.set_footer(text="Use the buttons below to manage this panel")
    return embed

def create_permission_edit_embed(panel_id, permission_type):
    """Create permission edit embed"""
    data = load_ticket_data()
    permissions = data["tickets"][panel_id]["sub_panels"][self.sub_panel_id]["permissions"][permission_type]

    type_names = {
        "owner": "Ticket Owner",
        "staff": "Staff Members",
        "authorized": "Authorized Users"
    }

    embed = discord.Embed(
        title=f"<:ParticipantsLOGO:1407733929389199460> Permissions: {type_names[permission_type]}",
        color=0x2b2d31
    )

    perm_list = []
    for i, (perm_name, enabled) in enumerate(permissions.items(), 1):
        status = "<:SucessLOGO:1407071637840592977>" if enabled else "<:ErrorLOGO:1407071682031648850>"
        perm_display = perm_name.replace("_", " ").title()
        perm_list.append(f"`{i}.` {status} {perm_display}")

    # Split into chunks of 10 to avoid embed limit
    chunk_size = 10
    chunks = [perm_list[i:i + chunk_size] for i in range(0, len(perm_list), chunk_size)]

    for i, chunk in enumerate(chunks):
        field_name = f"Permissions {i*chunk_size + 1}-{min((i+1)*chunk_size, len(perm_list))}"
        embed.add_field(name=field_name, value="\n".join(chunk), inline=True)

    embed.set_footer(text="Use the Modify button to change permissions using format: 1:1 2:0 3:1 (number:enabled)")
    return embed

def create_embed_content_edit_embed(data):
    """Create content edit embed"""
    # Ensure settings exist with default values
    if "settings" not in data:
        data["settings"] = {
            "default_embed": {
                "title": "",
                "outside_description": "",
                "description": "Support will be with you shortly. To close this ticket.",
                "thumbnail": "",
                "image": "",
                "footer": f"{get_bot_name()} - Ticket Bot"
            }
        }
        save_ticket_data(data)

    settings = data["settings"]["default_embed"]

    embed = discord.Embed(
        title="<:DescriptionLOGO:1407733417172533299> Default Embed Content",
        description="Edit the default content for created tickets:",
        color=0x2b2d31
    )

    if settings.get("title"):
        embed.add_field(name="Title", value=f"`{settings['title']}`", inline=False)

    if settings.get("outside_description"):
        embed.add_field(name="Outside Description", value=f"`{settings['outside_description'][:100]}{'...' if len(settings['outside_description']) > 100 else ''}`", inline=False)

    embed.add_field(name="Embed Description", value=f"`{settings['description'][:100]}{'...' if len(settings['description']) > 100 else ''}`", inline=False)

    if settings.get("thumbnail"):
        embed.add_field(name="Thumbnail", value="<:SucessLOGO:1407071637840592977> Configured", inline=True)

    if settings.get("footer"):
        embed.add_field(name="Footer", value=f"`{settings['footer']}`", inline=False)

    return embed

def create_staff_role_embed(data, guild):
    """Create staff role management embed"""
    embed = discord.Embed(
        title="👥 Staff Role Management",
        description="Roles authorized to manage tickets:",
        color=0x2b2d31
    )

    if not data["staff_roles"]:
        embed.add_field(
            name="No Roles Configured",
            value="Add roles so they can manage tickets",
            inline=False
        )
    else:
        roles_list = []
        valid_roles = []

        for role_id in data["staff_roles"]:
            role = guild.get_role(role_id)
            if role:
                roles_list.append(f"• {role.mention}")
                valid_roles.append(role_id)
            else:
                roles_list.append(f"• ~~Deleted Role~~ `(ID: {role_id})`")

        # Clean up deleted roles
        if len(valid_roles) != len(data["staff_roles"]):
            data["staff_roles"] = valid_roles
            save_ticket_data(data)

        embed.add_field(
            name=f"Staff Roles ({len(valid_roles)})",
            value="\n".join(roles_list) if roles_list else "No valid roles",
            inline=False
        )

    return embed

async def handle_ai_message(message):
    """Handle AI responses in ticket channels using existing AI system"""
    if message.author.bot:
        return False

    # Check if this is a ticket channel with AI enabled
    channel_name = message.channel.name
    if not any(pattern in channel_name for pattern in ['-0', '-1', '-2', '-3', '-4', '-5', '-6', '-7', '-8', '-9']):
        return False

    # Extract ticket type from channel name
    ticket_type = channel_name.split('-')[0]

    # Check if AI is enabled for this ticket type
    data = load_ticket_data()
    ai_enabled = False

    for panel_id, panel in data["tickets"].items():
        # Handle both old and new data structures
        if "sub_panels" in panel:
            # New structure with sub_panels
            for sub_panel_id, sub_panel in panel["sub_panels"].items():
                if sub_panel["name"].lower() == ticket_type.lower() and sub_panel.get("ai_enabled", False):
                    ai_enabled = True
                    break
        else:
            # Old structure without sub_panels
            if panel.get("name", "").lower() == ticket_type.lower() and panel.get("ai_enabled", False):
                ai_enabled = True
                break

        if ai_enabled:
            break

    if not ai_enabled:
        return False

    # Generate AI response using the existing AI system
    try:
        from AI import generate_ai_response
        ai_response = generate_ai_response(message.content, message.author.display_name)

        if ai_response:
            # Send AI response with a small delay to seem more natural
            import asyncio
            await asyncio.sleep(2)
            await message.channel.send(f"<:BotLOGO:1407071803150569472> **Assistant AI:** {ai_response}")
            return True
    except Exception as e:
        print(f"Error generating AI response in ticket channel: {e}")

    return False

# Helper function to check if a channel is a ticket channel
def is_ticket_channel(channel_name):
    """Check if a channel name matches the ticket channel pattern."""
    # Check if channel name contains ticket patterns
    return any(pattern in channel_name for pattern in ['-0', '-1', '-2', '-3', '-4', '-5', '-6', '-7', '-8', '-9']) or channel_name.startswith("closed-")

# Helper function to update ticket status in @ticket_data.json
def update_ticket_status(channel_id, new_data):
    """Update ticket status in @ticket_data.json."""
    try:
        with open('ticket_data.json', 'r', encoding='utf-8') as f:
            ticket_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        ticket_data = {}

    ticket_data[str(channel_id)] = new_data
    with open('ticket_data.json', 'w', encoding='utf-8') as f:
        json.dump(ticket_data, f, indent=4, ensure_ascii=False)

# Helper function to remove ticket status from @ticket_data.json
def remove_ticket_status(channel_id):
    """Remove ticket status from @ticket_data.json when the ticket is deleted."""
    try:
        with open('ticket_data.json', 'r', encoding='utf-8') as f:
            ticket_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return  # If the file doesn't exist or is corrupted, there's nothing to remove

    channel_id_str = str(channel_id)
    if channel_id_str in ticket_data:
        del ticket_data[channel_id_str]

        with open('ticket_data.json', 'w', encoding='utf-8') as f:
            json.dump(ticket_data, f, indent=4, ensure_ascii=False)

# Persistent views setup function for main bot
def setup_persistent_views(bot):
    """Setup persistent views when bot starts"""
    try:
        # Add persistent views with custom_id
        data = load_ticket_data()

        # Ensure data structure is complete
        if not isinstance(data, dict):
            print("<:ErrorLOGO:1407071682031648850> Invalid ticket data structure")
            return

        # Add views for published panels
        tickets = data.get("tickets", {})
        if isinstance(tickets, dict):
            for panel_id in tickets:
                try:
                    view = PublishedTicketView(panel_id)
                    bot.add_view(view)
                except Exception as e:
                    print(f"<:ErrorLOGO:1407071682031648850> Error adding view for panel {panel_id}: {e}")

        # Add ticket close views
        bot.add_view(TicketCloseView())
        bot.add_view(TicketClosedActionsView())

        print("<:SucessLOGO:1407071637840592977> Ticket system persistent views loaded successfully")
    except Exception as e:
        print(f"<:ErrorLOGO:1407071682031648850> Error setting up ticket persistent views: {e}")
        # Initialize with empty data if there's an error
        try:
            empty_data = {
                "tickets": {},
                "staff_roles": [],
                "settings": {
                    "default_embed": {
                        "title": "",
                        "outside_description": "",
                        "description": "Support will be with you shortly. To close this ticket.",
                        "thumbnail": "",
                        "image": "",
                        "footer": f"{get_bot_name()} - Ticket Bot"
                    },
                    "button_enabled": True,
                    "button_emoji": "<:CloseLOGO:1407072519420248256>",
                    "button_label": "Close Ticket",
                    "ai_enabled": False,
                    "log_settings": {
                        "ticket_opened": True,
                        "ticket_claimed": True,
                        "ticket_closed": True,
                        "ticket_deleted": True,
                        "ticket_reopened": True,
                        "transcript_saved": True
                    }
                },
                "ticket_counters": {},
                "closed_tickets": {}
            }
            save_ticket_data(empty_data)
            print("<:SucessLOGO:1407071637840592977> Initialized empty ticket data structure")
        except Exception as init_error:
            print(f"<:ErrorLOGO:1407071682031648850> Failed to initialize ticket data: {init_error}")

# New Views for Logs and Closed Tickets
class LogsManagementView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Set Log Channel', style=discord.ButtonStyle.primary, emoji='<:SettingLOGO:1407071854593839239>', row=0)
    async def set_log_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View(timeout=None)
        view.add_item(LogChannelSelect())
        view.add_item(BackButton("logs"))

        embed = discord.Embed(
            title="<:SettingLOGO:1407071854593839239> Set Log Channel",
            description="Select the channel where ticket logs will be sent:",
            color=0x2b2d31
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(emoji='<:TicketLOGO:1407730639343714397>',label='Ticket Opened', style=discord.ButtonStyle.success, row=1)
    async def toggle_opened_logs(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_data()
        if "log_settings" not in data["settings"]:
            data["settings"]["log_settings"] = {}

        current = data["settings"]["log_settings"].get("ticket_opened", True)
        data["settings"]["log_settings"]["ticket_opened"] = not current
        save_ticket_data(data)

        view = LogsManagementView()
        embed = create_logs_management_embed(data, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(emoji='<:UnviewLOGO:1407072750220345475>',label='Ticket Claimed', style=discord.ButtonStyle.success, row=1)
    async def toggle_claimed_logs(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_data()
        if "log_settings" not in data["settings"]:
            data["settings"]["log_settings"] = {}

        current = data["settings"]["log_settings"].get("ticket_claimed", True)
        data["settings"]["log_settings"]["ticket_claimed"] = not current
        save_ticket_data(data)

        view = LogsManagementView()
        embed = create_logs_management_embed(data, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(emoji='<:CloseLOGO:1407072519420248256>',label='Ticket Closed', style=discord.ButtonStyle.success, row=1)
    async def toggle_closed_logs(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_data()
        if "log_settings" not in data["settings"]:
            data["settings"]["log_settings"] = {}

        current = data["settings"]["log_settings"].get("ticket_closed", True)
        data["settings"]["log_settings"]["ticket_closed"] = not current
        save_ticket_data(data)

        view = LogsManagementView()
        embed = create_logs_management_embed(data, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(emoji='<:DeleteLOGO:1407071421363916841>',label='Ticket Deleted', style=discord.ButtonStyle.success, row=2)
    async def toggle_deleted_logs(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_data()
        if "log_settings" not in data["settings"]:
            data["settings"]["log_settings"] = {}

        current = data["settings"]["log_settings"].get("ticket_deleted", True)
        data["settings"]["log_settings"]["ticket_deleted"] = not current
        save_ticket_data(data)

        view = LogsManagementView()
        embed = create_logs_management_embed(data, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(emoji='<:TXTFileLOGO:1407735600752361622> ',label='Transcript', style=discord.ButtonStyle.success, row=2)
    async def toggle_transcript_logs(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_data()
        if "log_settings" not in data["settings"]:
            data["settings"]["log_settings"] = {}

        current = data["settings"]["log_settings"].get("transcript_saved", True)
        data["settings"]["log_settings"]["transcript_saved"] = not current
        save_ticket_data(data)

        view = LogsManagementView()
        embed = create_logs_management_embed(data, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='Back', style=discord.ButtonStyle.secondary, emoji='<:BackLOGO:1407071474233114766>', row=2)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = TicketPanelView()
        data = load_ticket_data()
        embed = create_ticket_panel_embed(data)
        await interaction.response.edit_message(embed=embed, view=view)

class LogChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            placeholder="Select a channel for logs",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        data = load_ticket_data()
        data["settings"]["log_channel_id"] = self.values[0].id
        save_ticket_data(data)

        view = LogsManagementView()
        embed = create_logs_management_embed(data, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=view)

class TicketClosedActionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Reopen', style=discord.ButtonStyle.success, emoji='<:ViewLOGO:1407071916824461435>', custom_id='persistent_reopen_ticket')
    async def reopen_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)

            data = load_ticket_data()
            channel_data = data.get("closed_tickets", {}).get(str(interaction.channel.id))

            if not channel_data:
                await interaction.followup.send("<:ErrorLOGO:1407071682031648850> Ticket data not found.", ephemeral=True)
                return

            # Restore original name (with delay to avoid rate limiting)
            original_name = channel_data["original_name"]

            # Only rename if it's currently closed
            if interaction.channel.name.startswith("closed-"):
                await asyncio.sleep(2)  # Delay to prevent rate limiting
                await interaction.channel.edit(name=original_name)


            # Restore permissions
            for member_id, perms in channel_data["permissions"].items():
                member = interaction.guild.get_member(int(member_id))
                if member:
                    await interaction.channel.set_permissions(
                        member,
                        view_channel=perms["view_channel"],
                        send_messages=perms["send_messages"],
                        read_message_history=perms["read_message_history"]
                    )

            # Remove from closed tickets
            del data["closed_tickets"][str(interaction.channel.id)]
            save_ticket_data(data)

            # Log reopening
            await log_ticket_action(interaction.guild, "ticket_reopened", {
                "channel": interaction.channel.mention,
                "reopened_by": interaction.user
            })

            # Send new message for reopening instead of editing
            reopen_embed = discord.Embed(
                title="<:ViewLOGO:1407071916824461435> Ticket Reopened",
                description="This ticket has been reopened successfully!",
                color=0x57f287
            )

            close_view = TicketCloseView()
            await interaction.channel.send(embed=reopen_embed, view=close_view)

            await interaction.followup.send("<:SucessLOGO:1407071637840592977> Ticket reopened successfully!", ephemeral=True)

            # Update ticket status
            update_ticket_status(interaction.channel.id, {"status": "open"})

        except Exception as e:
            await interaction.followup.send(f"<:ErrorLOGO:1407071682031648850> Error reopening ticket: {str(e)}", ephemeral=True)

    @discord.ui.button(label='Delete', style=discord.ButtonStyle.danger, emoji='<:DeleteLOGO:1407071421363916841>', custom_id='persistent_delete_ticket')
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)

            # Log deletion
            await log_ticket_action(interaction.guild, "ticket_deleted", {
                "channel": interaction.channel.mention,
                "deleted_by": interaction.user
            })

            # Remove from closed tickets data
            data = load_ticket_data()
            if str(interaction.channel.id) in data.get("closed_tickets", {}):
                del data["closed_tickets"][str(interaction.channel.id)]
                save_ticket_data(data)

            # Send deletion message as a new message
            deletion_embed = discord.Embed(
                title="<:DeleteLOGO:1407071421363916841> Deleting Ticket...",
                description="Deleting the ticket in 3 seconds...",
                color=discord.Color.red()
            )
            await interaction.channel.send(embed=deletion_embed)
            await asyncio.sleep(3)

            # Delete the channel
            await interaction.channel.delete(reason=f"Ticket deleted by {interaction.user}")

            # Remove ticket status
            remove_ticket_status(interaction.channel.id)

        except Exception as e:
            await interaction.followup.send(f"<:ErrorLOGO:1407071682031648850> Error deleting ticket: {str(e)}", ephemeral=True)

    @discord.ui.button(label='Transcript', style=discord.ButtonStyle.primary, emoji='<:TXTFileLOGO:1407735600752361622>', custom_id='persistent_save_transcript')
    async def save_transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)

            # Get ticket data
            data = load_ticket_data()

            # Find ticket owner and panel info
            ticket_owner = None
            panel_name = "Unknown Panel"
            panel_emoji = "<:TicketLOGO:1407730639343714397>"
            ticket_type = "unknown"

            # Extract ticket type from channel name
            channel_name = interaction.channel.name
            if channel_name.startswith("closed-"):
                # For closed tickets: closed-support-0001 -> support
                parts = channel_name.replace("closed-", "").split('-')
                if len(parts) >= 1:
                    ticket_type = parts[0]
            else:
                # For regular tickets: support-0001 -> support
                parts = channel_name.split('-')
                if len(parts) >= 1:
                    ticket_type = parts[0]

            # Find matching panel with better search
            for panel_id, panel in data.get("tickets", {}).items():
                if "sub_panels" in panel:
                    for sub_panel_id, sub_panel in panel["sub_panels"].items():
                        sub_panel_name = sub_panel["name"].lower().strip()
                        if sub_panel_name == ticket_type.lower().strip():
                            # Prioritize panel_title, then ticket_title, then title
                            panel_title = sub_panel.get("panel_title") or sub_panel.get("ticket_title") or sub_panel.get("title", "Default Panel")
                            panel_name = f"<:TicketLOGO:1407730639343714397> {panel_title}"
                            break
                    else:
                        continue
                    break
            else:
                # If no exact match found, try partial matching
                for panel_id, panel in data.get("tickets", {}).items():
                    if "sub_panels" in panel:
                        for sub_panel_id, sub_panel in panel["sub_panels"].items():
                            sub_panel_name = sub_panel["name"].lower().strip()
                            if ticket_type.lower().strip() in sub_panel_name or sub_panel_name in ticket_type.lower().strip():
                                panel_title = sub_panel.get("panel_title") or sub_panel.get("ticket_title") or sub_panel.get("title", "Default Panel")
                                panel_name = f"<:TicketLOGO:1407730639343714397> {panel_title}"
                                break
                        else:
                            continue
                        break

            # Find ticket owner from closed ticket data or channel permissions
            ticket_owner_id = None
            closed_ticket_data = data.get("closed_tickets", {}).get(str(interaction.channel.id))

            if closed_ticket_data and "permissions" in closed_ticket_data:
                # Find owner from closed ticket permissions
                for member_id_str, perms in closed_ticket_data["permissions"].items():
                    member = interaction.guild.get_member(int(member_id_str))
                    if member and not member.bot and not any(role.id in data.get("staff_roles", []) for role in member.roles):
                        ticket_owner = member
                        ticket_owner_id = member.id
                        break

            if not ticket_owner:
                # Find from current channel members
                for member in interaction.channel.members:
                    if not member.bot and member != interaction.guild.me:
                        perms = interaction.channel.permissions_for(member)
                        if perms.send_messages and not any(role.id in data.get("staff_roles", []) for role in member.roles):
                            ticket_owner_id = member.id
                            ticket_owner = member
                            break

            # If still not found, get from first message
            if not ticket_owner:
                async for message in interaction.channel.history(limit=100, oldest_first=True):
                    if not message.author.bot and message.author != interaction.guild.me:
                        ticket_owner = message.author
                        ticket_owner_id = message.author.id
                        break

            # Generate enhanced transcript
            transcript_data = {
                "server_info": {
                    "server_name": interaction.guild.name,
                    "server_id": interaction.guild.id,
                    "channel_name": interaction.channel.name,
                    "channel_id": interaction.channel.id
                },
                "ticket_info": {
                    "ticket_owner": {
                        "name": ticket_owner.display_name if ticket_owner else "Unknown User",
                        "username": f"{ticket_owner.name}#{ticket_owner.discriminator}" if ticket_owner and ticket_owner.discriminator != "0" else ticket_owner.name if ticket_owner else "Unknown",
                        "id": ticket_owner_id,
                        "avatar_url": ticket_owner.display_avatar.url if ticket_owner else None
                    },
                    "ticket_name": interaction.channel.name,
                    "panel_name": panel_name,
                    "panel_emoji": panel_emoji,
                    "created_at": datetime.now().isoformat(),
                    "transcript_saved_by": {
                        "name": interaction.user.display_name,
                        "username": f"{interaction.user.name}#{interaction.user.discriminator}" if interaction.user.discriminator != "0" else interaction.user.name,
                        "id": interaction.user.id,
                        "avatar_url": interaction.user.display_avatar.url
                    }
                },
                "statistics": {
                    "total_messages": 0,
                    "attachments_saved": 0,
                    "attachments_skipped": 0,
                    "users_in_transcript": {}
                },
                "messages": []
            }

            # Count messages and get participants
            message_count = 0
            attachments_count = 0
            users_in_transcript = {}

            async for message in interaction.channel.history(limit=None, oldest_first=True):
                message_count += 1
                attachments_count += len(message.attachments)

                # Track users
                user_key = f"{message.author.display_name} - {message.author.name}#{message.author.discriminator}" if message.author.discriminator != "0" else f"{message.author.display_name} - {message.author.name}"
                if user_key not in users_in_transcript:
                    users_in_transcript[user_key] = {
                        "message_count": 0,
                        "is_bot": message.author.bot,
                        "roles": [role.name for role in message.author.roles] if hasattr(message.author, 'roles') else []
                    }
                users_in_transcript[user_key]["message_count"] += 1

                message_data = {
                    "id": message.id,
                    "author": {
                        "name": message.author.display_name,
                        "username": f"{message.author.name}#{message.author.discriminator}" if message.author.discriminator != "0" else message.author.name,
                        "id": message.author.id,
                        "bot": message.author.bot,
                        "avatar_url": message.author.display_avatar.url
                    },
                    "content": message.content,
                    "timestamp": message.created_at.isoformat(),
                    "embeds": [embed.to_dict() for embed in message.embeds],
                    "attachments": [{"filename": att.filename, "url": att.url, "size": att.size} for att in message.attachments]
                }
                transcript_data["messages"].append(message_data)

            # Update statistics
            transcript_data["statistics"]["total_messages"] = message_count
            transcript_data["statistics"]["attachments_saved"] = attachments_count
            transcript_data["statistics"]["attachments_skipped"] = 0
            transcript_data["statistics"]["users_in_transcript"] = users_in_transcript

            # Save to transcript file
            try:
                with open('ticket_transcript.json', 'r', encoding='utf-8') as f:
                    transcripts = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                transcripts = {}

            transcripts[str(interaction.channel.id)] = transcript_data

            with open('ticket_transcript.json', 'w', encoding='utf-8') as f:
                json.dump(transcripts, f, indent=4, ensure_ascii=False)

            # Create transcript file
            transcript_filename = f"transcript_{interaction.channel.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            transcript_content = []

            # Generate readable transcript
            transcript_content.append(f"=== TICKET TRANSCRIPT ===")
            transcript_content.append(f"Server: {interaction.guild.name}")
            transcript_content.append(f"Channel: #{interaction.channel.name}")
            transcript_content.append(f"Owner: {ticket_owner.display_name if ticket_owner else 'Unknown'}")
            transcript_content.append(f"Panel Type: {panel_name}")
            transcript_content.append(f"Saved by: {interaction.user.display_name}")
            transcript_content.append(f"Date: {datetime.now().strftime('%d/%m/%Y at %H:%M:%S')}")
            transcript_content.append(f"Messages: {message_count}")
            transcript_content.append(f"Participants: {len(users_in_transcript)}")
            transcript_content.append("=" * 50)
            transcript_content.append("")

            # Add all messages
            for msg_data in transcript_data["messages"]:
                timestamp = datetime.fromisoformat(msg_data["timestamp"]).strftime('%d/%m/%Y %H:%M:%S')
                author_name = msg_data["author"]["name"]
                content = msg_data["content"] or "[No content message]"

                transcript_content.append(f"[{timestamp}] {author_name}: {content}")

                # Add embeds info if any
                if msg_data["embeds"]:
                    transcript_content.append(f"   └── {len(msg_data['embeds'])} embed(s)")

                # Add attachments info if any
                if msg_data["attachments"]:
                    for att in msg_data["attachments"]:
                        transcript_content.append(f"   └── File: {att['filename']} ({att['size']} bytes)")

                transcript_content.append("")

            # Save transcript file
            with open(transcript_filename, 'w', encoding='utf-8') as f:
                f.write('\n'.join(transcript_content))

            # Log transcript saving with file attachment
            await log_ticket_action(interaction.guild, "transcript_saved", {
                "channel": interaction.channel.mention,
                "saved_by": interaction.user,
                "message_count": message_count,
                "ticket_type": ticket_type,
                "transcript_file": transcript_filename,
                "ticket_owner": ticket_owner.mention if ticket_owner else "Unknown",
                "panel_name": panel_name
            })

            # Send ephemeral success message without modifying the main embed
            await interaction.followup.send("<:SucessLOGO:1407071637840592977> Transcript saved successfully and sent to logs!", ephemeral=True)

            # Update ticket status
            update_ticket_status(interaction.channel.id, {"transcript_saved": True})

        except Exception as e:
            await interaction.followup.send(f"<:ErrorLOGO:1407071682031648850> Error saving transcript: {str(e)}", ephemeral=True)

# Logging system
async def log_ticket_action(guild, action_type, details):
    """Log ticket actions to a specified channel with simplified styling like the example."""
    data = load_ticket_data()
    log_channel_id = data["settings"].get("log_channel_id")
    log_settings = data["settings"].get("log_settings", {})

    # Check if this log type is enabled
    if not log_settings.get(action_type, True):
        return

    log_channel = guild.get_channel(log_channel_id) if log_channel_id else None

    if not log_channel:
        print("Log channel not configured or not found.")
        return

    # Get user object from details - extract ID from mention properly
    user = None
    user_mention = ""

    # Extract user object from various possible keys in 'details'
    user_keys_to_check = ["created_by", "claimed_by", "closed_by", "reopened_by", "deleted_by", "saved_by"]
    found_user = None

    for key in user_keys_to_check:
        if key in details:
            user_data = details[key]
            if isinstance(user_data, discord.User):
                found_user = user_data
                break
            elif isinstance(user_data, discord.Member):
                found_user = user_data
                break
            elif isinstance(user_data, int):
                # If it's an ID, try to get the member
                found_user = guild.get_member(user_data)
                if found_user:
                    break
            elif isinstance(user_data, str) and "<@" in user_data and ">" in user_data:
                # If it's a mention, extract ID and get member
                user_id_str = user_data.replace("<@", "").replace(">", "").replace("!", "")
                try:
                    user_id = int(user_id_str)
                    found_user = guild.get_member(user_id)
                    if found_user:
                        break
                except ValueError:
                    pass # Ignore if ID is not valid

    user = found_user # Assign the found user to the 'user' variable

    # Color mapping for different actions (left border color)
    color_mapping = {
        "ticket_opened": 0x57f287,  # Green
        "ticket_claimed": 0xfee75c, # Yellow
        "ticket_closed": 0xed4245,  # Red
        "ticket_reopened": 0x57f287, # Green
        "ticket_deleted": 0x99aab5,  # Gray
        "transcript_saved": 0x5865f2  # Blurple
    }

    # Action mapping
    action_mapping = {
        "ticket_opened": "Created",
        "ticket_claimed": "Claimed",
        "ticket_closed": "Closed",
        "ticket_reopened": "Reopened",
        "ticket_deleted": "Deleted",
        "transcript_saved": "Transcript Saved"
    }

    # Extract ticket info from channel mention
    channel_name = "Unknown"
    ticket_name = "Unknown"
    ticket_type = "unknown"

    if "channel" in details:
        channel_mention = details["channel"]
        if isinstance(channel_mention, discord.TextChannel): # If it's already a channel object
            channel_name = channel_mention.name
        elif isinstance(channel_mention, str) and "<#" in channel_mention:
            channel_id_str = channel_mention.replace("<#", "").replace(">", "")
            try:
                channel_id = int(channel_id_str)
                channel_obj = guild.get_channel(channel_id)
                if channel_obj:
                    channel_name = channel_obj.name
            except ValueError:
                pass
        else:
            channel_name = channel_mention

    # Extract ticket info from channel name
    if "-" in channel_name:
        if channel_name.startswith("closed-"):
            # For closed tickets: closed-support-0048 -> support, Ticket-0048
            parts = channel_name.replace("closed-", "").split('-')
            if len(parts) >= 2: # Expecting at least type and number
                ticket_type = parts[0]
                ticket_name = f"Ticket-{parts[1]}"
        else:
            # For regular tickets: support-0048 -> support, Ticket-0048
            parts = channel_name.split("-")
            if len(parts) >= 2: # Expecting at least type and number
                ticket_type = parts[0]
                ticket_name = f"Ticket-{parts[1]}"

    # Find panel info - better search logic
    panel_name = "<:TicketLOGO:1407730639343714397> Default Panel"

    # Check if panel_name is already provided in details
    if "panel_name" in details and details["panel_name"]:
        panel_name = f"<:TicketLOGO:1407730639343714397> {details['panel_name']}"
    elif "ticket_type" in details:
        ticket_type = details["ticket_type"]
        # Search for matching panel
        for panel_id, panel in data.get("tickets", {}).items():
            if "sub_panels" in panel:
                for sub_panel_id, sub_panel in panel["sub_panels"].items():
                    sub_panel_name = sub_panel["name"].lower().strip()
                    if sub_panel_name == ticket_type.lower().strip():
                        # Prioritize panel_title, then ticket_title, then title
                        panel_title = sub_panel.get("panel_title") or sub_panel.get("ticket_title") or sub_panel.get("title", "Default Panel")
                        panel_name = f"<:TicketLOGO:1407730639343714397> {panel_title}"
                        break
                else:
                    continue
                break
    else:
        # Try to find panel from extracted ticket_type
        for panel_id, panel in data.get("tickets", {}).items():
            if "sub_panels" in panel:
                for sub_panel_id, sub_panel in panel["sub_panels"].items():
                    sub_panel_name = sub_panel["name"].lower().strip()
                    if sub_panel_name == ticket_type.lower().strip():
                        panel_title = sub_panel.get("panel_title") or sub_panel.get("ticket_title") or sub_panel.get("title", "Default Panel")
                        panel_name = f"<:TicketLOGO:1407730639343714397> {panel_title}"
                        break
                else:
                    continue
                break

    # Create simplified embed like the example
    embed = discord.Embed(
        color=color_mapping.get(action_type, 0x7289da)
    )

    # Set user as author with avatar (top of embed) - this is crucial
    if user:
        embed.set_author(
            name=user.display_name,
            icon_url=user.display_avatar.url
        )
    else:
        # Fallback if user not found
        embed.set_author(
            name="Unknown User",
            icon_url="https://cdn.discordapp.com/embed/avatars/0.png"
        )

    # Create the main content fields exactly like the example
    logged_info = f"**Logged Info**\nTicket: {ticket_name}\nAction: {action_mapping.get(action_type, 'Action')}"

    panel_info = f"**Panel**\n{panel_name}"

    embed.add_field(name="", value=logged_info, inline=True)
    embed.add_field(name="", value=panel_info, inline=True)

    # For transcript action, add simplified info
    if action_type == "transcript_saved" and "message_count" in details:
        embed.add_field(name="", value=f"**Messages:** {details['message_count']}", inline=False)

    # Send the log message
    if action_type == "transcript_saved" and "transcript_file" in details:
        # Send with transcript file attachment but don't overload the embed
        try:
            with open(details["transcript_file"], 'rb') as f:
                file = discord.File(f, filename=details["transcript_file"])
                await log_channel.send(embed=embed, file=file)

            # Clean up the file after sending
            import os
            os.remove(details["transcript_file"])
        except Exception as e:
            print(f"Error sending transcript file: {e}")
            await log_channel.send(embed=embed)
    else:
        await log_channel.send(embed=embed)

# setup commands
def setup_ticket_system(bot):
    """Setup ticket system"""
    # Définir l'instance globale du bot
    set_bot_instance(bot)

    @bot.tree.command(name="ticket_panel", description="Open the ticket management panel")
    async def ticket_panel(interaction: discord.Interaction):
        data = load_ticket_data()
        view = TicketPanelView()
        embed = create_ticket_panel_embed(data)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

    @bot.tree.command(name="close", description="Ferme le ticket actuel")
    async def close_command(interaction: discord.Interaction):
        # Check if the command is used in a ticket channel
        channel_name = interaction.channel.name
        is_ticket = any(pattern in channel_name for pattern in ['-0', '-1', '-2', '-3', '-4', '-5', '-6', '-7', '-8', '-9'])

        if not is_ticket:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Cette commande ne peut être utilisée que dans un channel de ticket.", ephemeral=True)
            return

        try:
            # Save ticket data before closing
            data = load_ticket_data()
            if "closed_tickets" not in data:
                data["closed_tickets"] = {}

            ticket_name = interaction.channel.name
            ticket_data = {
                "original_name": ticket_name,
                "channel_id": interaction.channel.id,
                "closed_by": interaction.user.id,
                "closed_at": datetime.now().isoformat(),
                "permissions": {}
            }

            # Save current permissions
            for member in interaction.channel.members:
                if not member.bot:
                    perms = interaction.channel.permissions_for(member)
                    ticket_data["permissions"][str(member.id)] = {
                        "view_channel": perms.view_channel,
                        "send_messages": perms.send_messages,
                        "read_message_history": perms.read_message_history
                    }

            data["closed_tickets"][str(interaction.channel.id)] = ticket_data
            save_ticket_data(data)

            # Send closing message
            closing_embed = discord.Embed(
                title="<a:LoadingLOGO:1407732919476424814> Closing Ticket...",
                description="Closing the ticket in 3 seconds...",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=closing_embed, ephemeral=False)
            await asyncio.sleep(3)

            # Remove non-staff members
            staff_roles = data.get("staff_roles", [])
            staff_members = []
            for role_id in staff_roles:
                role = interaction.guild.get_role(role_id)
                if role:
                    for member in role.members:
                        staff_members.append(member.id)

            for member in interaction.channel.members:
                if not member.bot and member.id not in staff_members and not member.guild_permissions.administrator:
                    await interaction.channel.set_permissions(member, view_channel=False)

            # Rename the ticket (with delay to avoid rate limiting)
            ticket_type = ticket_name.split('-')[0]
            new_channel_name = f"closed-{ticket_type}-{ticket_name.split('-')[1]}"

            # Only rename if it's not already closed
            if not interaction.channel.name.startswith("closed-"):
                await asyncio.sleep(1)  # Small delay to prevent rate limiting
                await interaction.channel.edit(name=new_channel_name)


            # Log ticket closing
            await log_ticket_action(interaction.guild, "ticket_closed", {
                "channel": interaction.channel.mention,
                "closed_by": interaction.user
            })

            # Send closed actions view
            closed_embed = discord.Embed(
                title="<:TicketLOGO:1407730639343714397> Ticket Closed",
                description="This ticket has been closed. What would you like to do?",
                color=0x57f287
            )

            closed_view = TicketClosedActionsView()
            await interaction.channel.send(embed=closed_embed, view=closed_view)

            # Update ticket status
            update_ticket_status(interaction.channel.id, {"status": "closed"})

        except Exception as e:
            await interaction.followup.send(f"<:ErrorLOGO:1407071682031648850> Erreur lors de la fermeture du ticket: {str(e)}", ephemeral=True)

    @bot.tree.command(name="delete", description="Supprime le ticket actuel")
    async def delete_command(interaction: discord.Interaction):
        # Check if the command is used in a ticket channel
        channel_name = interaction.channel.name
        is_ticket = any(pattern in channel_name for pattern in ['-0', '-1', '-2', '-3', '-4', '-5', '-6', '-7', '-8', '-9']) or channel_name.startswith("closed-")

        if not is_ticket:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Cette commande ne peut être utilisée que dans un channel de ticket.", ephemeral=True)
            return

        try:
            # Log deletion
            await log_ticket_action(interaction.guild, "ticket_deleted", {
                "channel": interaction.channel.mention,
                "deleted_by": interaction.user
            })

            # Send deletion message
            deletion_embed = discord.Embed(
                title="<:DeleteLOGO:1407071421363916841> Deleting Ticket...",
                description="Deleting the ticket in 3 seconds...",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=deletion_embed, ephemeral=False)
            await asyncio.sleep(3)

            # Delete the channel
            await interaction.channel.delete(reason=f"Ticket supprimé par {interaction.user}")

            # Remove ticket status
            remove_ticket_status(interaction.channel.id)

        except Exception as e:
            await interaction.response.send_message(f"<:ErrorLOGO:1407071682031648850> Erreur lors de la suppression du ticket: {str(e)}", ephemeral=True)

    @bot.tree.command(name="claim", description="Prend possession du ticket, supprime tous les autres staff")
    async def claim_command(interaction: discord.Interaction):
        # Check if the command is used in a ticket channel
        channel_name = interaction.channel.name
        is_ticket = any(pattern in channel_name for pattern in ['-0', '-1', '-2', '-3', '-4', '-5', '-6', '-7', '-8', '-9'])

        if not is_ticket:
            embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Erreur",
                description="Cette commande ne peut être utilisée que dans un channel de ticket.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            # Get the staff roles from the ticket data
            data = load_ticket_data()
            staff_roles = data.get("staff_roles", [])

            # Identify staff members to keep based on the command executor's roles
            staff_to_keep = [interaction.user.id]
            for role_id in staff_roles:
                role = interaction.guild.get_role(role_id)
                if role and interaction.user.top_role >= role:
                    for member in role.members:
                        if member.top_role <= interaction.user.top_role:
                            staff_to_keep.append(member.id)

            # Remove all other staff members from the ticket
            for member in interaction.channel.members:
                if not member.bot and member.id not in staff_to_keep and not member.guild_permissions.administrator:
                    await interaction.channel.set_permissions(member, view_channel=False)

            # Log ticket claiming
            await log_ticket_action(interaction.guild, "ticket_claimed", {
                "channel": interaction.channel.mention,
                "claimed_by": interaction.user
            })

            embed = discord.Embed(
                title="<:SucessLOGO:1407071637840592977> Ticket Claimed",
                description="This ticket has been claimed.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"<:ErrorLOGO:1407071682031648850> Erreur lors de la prise en charge: {str(e)}", ephemeral=True)

    @bot.tree.command(name="reopen", description="Rouvre un ticket fermé")
    async def reopen_command(interaction: discord.Interaction):
        # Check if the command is used in a ticket channel
        channel_name = interaction.channel.name
        is_closed_ticket = channel_name.startswith("closed-")

        if not is_closed_ticket:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Cette commande ne peut être utilisée que dans un ticket fermé.", ephemeral=True)
            return

        try:
            data = load_ticket_data()
            channel_data = data.get("closed_tickets", {}).get(str(interaction.channel.id))

            if not channel_data:
                await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Ce ticket n'est pas dans l'état fermé ou les données sont introuvables.", ephemeral=True)
                return

            # Restore original name (with delay to avoid rate limiting)
            original_name = channel_data["original_name"]

            # Only rename if it's currently closed
            if interaction.channel.name.startswith("closed-"):
                await asyncio.sleep(2)  # Delay to prevent rate limiting
                await interaction.channel.edit(name=original_name)


            # Restore permissions
            for member_id, perms in channel_data.get("permissions", {}).items():
                member = interaction.guild.get_member(int(member_id))
                if member:
                    await interaction.channel.set_permissions(
                        member,
                        view_channel=perms["view_channel"],
                        send_messages=perms["send_messages"],
                        read_message_history=perms["read_message_history"]
                    )

            # Remove from closed tickets
            if str(interaction.channel.id) in data["closed_tickets"]:
                del data["closed_tickets"][str(interaction.channel.id)]
                save_ticket_data(data)

            # Log reopening
            await log_ticket_action(interaction.guild, "ticket_reopened", {
                "channel": interaction.channel.mention,
                "reopened_by": interaction.user
            })

            # Send reopening message with new close button
            reopen_embed = discord.Embed(
                title="<:ViewLOGO:1407071916824461435> Ticket Reopened",
                description="This ticket has been reopened successfully!",
                color=0x57f287
            )

            # Create new close view
            close_view = TicketCloseView()
            await interaction.channel.send(embed=reopen_embed, view=close_view)

            # Update ticket status
            update_ticket_status(interaction.channel.id, {
                "status": "open",
                "original_name": original_name,
                "reopened_by": interaction.user.id,
                "reopened_at": datetime.now().isoformat()
            })

        except Exception as e:
            await interaction.response.send_message(f"<:ErrorLOGO:1407071682031648850> Erreur lors de la réouverture du ticket: {str(e)}", ephemeral=True)

    @bot.tree.command(name="transcript", description="Sauvegarde la transcription du ticket")
    async def transcript_command(interaction: discord.Interaction):
        # Check if the command is used in a ticket channel
        channel_name = interaction.channel.name
        is_ticket = any(pattern in channel_name for pattern in ['-0', '-1', '-2', '-3', '-4', '-5', '-6', '-7', '-8', '-9']) or channel_name.startswith("closed-")

        if not is_ticket:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Cette commande ne peut être utilisée que dans un channel de ticket.", ephemeral=True)
            return

        try:
            await interaction.response.defer(ephemeral=True)

            # Get ticket data
            data = load_ticket_data()

            # Find ticket owner and panel info
            ticket_owner = None
            panel_name = "Unknown Panel"
            panel_emoji = "<:TicketLOGO:1407730639343714397>"
            ticket_type = "unknown"

            # Extract ticket type from channel name
            if channel_name.startswith("closed-"):
                # For closed tickets: closed-support-0001 -> support
                parts = channel_name.replace("closed-", "").split('-')
                if len(parts) >= 1:
                    ticket_type = parts[0]
            else:
                # For regular tickets: support-0001 -> support
                parts = channel_name.split('-')
                if len(parts) >= 1:
                    ticket_type = parts[0]

            # Find matching panel
            for panel_id, panel in data.get("tickets", {}).items():
                if "sub_panels" in panel:
                    for sub_panel_id, sub_panel in panel["sub_panels"].items():
                        sub_panel_name = sub_panel["name"].lower().strip()
                        if sub_panel_name == ticket_type.lower().strip():
                            panel_name = sub_panel.get("panel_title", sub_panel.get("ticket_title", sub_panel.get("title", "Panel par Défaut")))
                            panel_emoji = sub_panel.get("panel_emoji", sub_panel.get("button_emoji", "<:TicketLOGO:1407730639343714397>"))
                            break
                    else:
                        continue
                    break

            # Find ticket owner
            for member in interaction.channel.members:
                if not member.bot and member != interaction.guild.me:
                    perms = interaction.channel.permissions_for(member)
                    if perms.send_messages and not any(role.id in data.get("staff_roles", []) for role in member.roles):
                        ticket_owner = member
                        break

            if not ticket_owner:
                async for message in interaction.channel.history(limit=100, oldest_first=True):
                    if not message.author.bot and message.author != interaction.guild.me:
                        ticket_owner = message.author
                        break

            # Generate transcript
            transcript_data = {
                "server_info": {
                    "server_name": interaction.guild.name,
                    "server_id": interaction.guild.id,
                    "channel_name": interaction.channel.name,
                    "channel_id": interaction.channel.id
                },
                "ticket_info": {
                    "ticket_owner": {
                        "name": ticket_owner.display_name if ticket_owner else "Utilisateur Inconnu",
                        "username": f"{ticket_owner.name}#{ticket_owner.discriminator}" if ticket_owner and ticket_owner.discriminator != "0" else ticket_owner.name if ticket_owner else "Inconnu",
                        "id": ticket_owner.id if ticket_owner else None,
                        "avatar_url": ticket_owner.display_avatar.url if ticket_owner else None
                    },
                    "ticket_name": interaction.channel.name,
                    "panel_name": panel_name,
                    "panel_emoji": panel_emoji,
                    "created_at": datetime.now().isoformat(),
                    "transcript_saved_by": {
                        "name": interaction.user.display_name,
                        "username": f"{interaction.user.name}#{interaction.user.discriminator}" if interaction.user.discriminator != "0" else interaction.user.name,
                        "id": interaction.user.id,
                        "avatar_url": interaction.user.display_avatar.url
                    }
                },
                "messages": []
            }

            # Count messages
            message_count = 0
            async for message in interaction.channel.history(limit=None, oldest_first=True):
                message_count += 1
                message_data = {
                    "id": message.id,
                    "author": {
                        "name": message.author.display_name,
                        "username": f"{message.author.name}#{message.author.discriminator}" if message.author.discriminator != "0" else message.author.name,
                        "id": message.author.id,
                        "bot": message.author.bot,
                        "avatar_url": message.author.display_avatar.url
                    },
                    "content": message.content,
                    "timestamp": message.created_at.isoformat(),
                    "embeds": [embed.to_dict() for embed in message.embeds],
                    "attachments": [{"filename": att.filename, "url": att.url, "size": att.size} for att in message.attachments]
                }
                transcript_data["messages"].append(message_data)

            # Save to transcript file
            try:
                with open('ticket_transcript.json', 'r', encoding='utf-8') as f:
                    transcripts = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                transcripts = {}

            transcripts[str(interaction.channel.id)] = transcript_data

            with open('ticket_transcript.json', 'w', encoding='utf-8') as f:
                json.dump(transcripts, f, indent=4, ensure_ascii=False)

            # Create readable transcript file
            transcript_filename = f"transcript_{interaction.channel.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            transcript_content = []

            transcript_content.append(f"=== TRANSCRIPTION TICKET ===")
            transcript_content.append(f"Serveur: {interaction.guild.name}")
            transcript_content.append(f"Canal: #{interaction.channel.name}")
            transcript_content.append(f"Propriétaire: {ticket_owner.display_name if ticket_owner else 'Inconnu'}")
            transcript_content.append(f"Type de Panel: {panel_name}")
            transcript_content.append(f"Sauvegardé par: {interaction.user.display_name}")
            transcript_content.append(f"Date: {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}")
            transcript_content.append(f"Messages: {message_count}")
            transcript_content.append("=" * 50)
            transcript_content.append("")

            # Add all messages
            for msg_data in transcript_data["messages"]:
                timestamp = datetime.fromisoformat(msg_data["timestamp"]).strftime('%d/%m/%Y %H:%M:%S')
                author_name = msg_data["author"]["name"]
                content = msg_data["content"] or "[No content message]"

                transcript_content.append(f"[{timestamp}] {author_name}: {content}")

                # Add embed details
                if msg_data["embeds"]:
                    for i, embed_data in enumerate(msg_data["embeds"], 1):
                        transcript_content.append(f"   └── Embed {i}:")
                        if embed_data.get("title"):
                            transcript_content.append(f"       Title: {embed_data['title']}")
                        if embed_data.get("description"):
                            transcript_content.append(f"       Description: {embed_data['description'][:200]}{'...' if len(embed_data.get('description', '')) > 200 else ''}")
                        if embed_data.get("fields"):
                            transcript_content.append(f"       Fields: {len(embed_data['fields'])}")

                if msg_data["attachments"]:
                    for att in msg_data["attachments"]:
                        transcript_content.append(f"   └── File: {att['filename']} ({att['size']} bytes)")

                transcript_content.append("")

            # Save transcript file
            with open(transcript_filename, 'w', encoding='utf-8') as f:
                f.write('\n'.join(transcript_content))

            # Log transcript saving
            await log_ticket_action(interaction.guild, "transcript_saved", {
                "channel": interaction.channel.mention,
                "saved_by": interaction.user,
                "message_count": message_count,
                "ticket_type": ticket_type,
                "transcript_file": transcript_filename,
                "ticket_owner": ticket_owner.mention if ticket_owner else "Inconnu",
                "panel_name": panel_name
            })

            await interaction.followup.send("<:SucessLOGO:1407071637840592977> Transcript saved successfully and sent to logs!", ephemeral=True)

            # Update ticket status
            update_ticket_status(interaction.channel.id, {"transcript_saved": True})

        except Exception as e:
            await interaction.followup.send(f"<:ErrorLOGO:1407071682031648850> Erreur lors de la sauvegarde de la transcription: {str(e)}", ephemeral=True)

    @bot.event
    async def on_message(message):
        """Handle AI responses in ticket channels"""
        await handle_ai_message(message)

# setup commands
def setup_ticket_system(bot):
    """Setup ticket system"""
    # Définir l'instance globale du bot
    set_bot_instance(bot)

    @bot.tree.command(name="ticket_panel", description="Open the ticket management panel")
    async def ticket_panel(interaction: discord.Interaction):
        data = load_ticket_data()
        view = TicketPanelView()
        embed = create_ticket_panel_embed(data)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

    @bot.tree.command(name="close", description="Ferme le ticket actuel")
    async def close_command(interaction: discord.Interaction):
        # Check if the command is used in a ticket channel
        channel_name = interaction.channel.name
        is_ticket = any(pattern in channel_name for pattern in ['-0', '-1', '-2', '-3', '-4', '-5', '-6', '-7', '-8', '-9'])

        if not is_ticket:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Cette commande ne peut être utilisée que dans un channel de ticket.", ephemeral=True)
            return

        try:
            # Save ticket data before closing
            data = load_ticket_data()
            if "closed_tickets" not in data:
                data["closed_tickets"] = {}

            ticket_name = interaction.channel.name
            ticket_data = {
                "original_name": ticket_name,
                "channel_id": interaction.channel.id,
                "closed_by": interaction.user.id,
                "closed_at": datetime.now().isoformat(),
                "permissions": {}
            }

            # Save current permissions
            for member in interaction.channel.members:
                if not member.bot:
                    perms = interaction.channel.permissions_for(member)
                    ticket_data["permissions"][str(member.id)] = {
                        "view_channel": perms.view_channel,
                        "send_messages": perms.send_messages,
                        "read_message_history": perms.read_message_history
                    }

            data["closed_tickets"][str(interaction.channel.id)] = ticket_data
            save_ticket_data(data)

            # Send closing message
            closing_embed = discord.Embed(
                title="<a:LoadingLOGO:1407732919476424814> Closing Ticket...",
                description="Closing the ticket in 3 seconds...",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=closing_embed, ephemeral=False)
            await asyncio.sleep(3)

            # Remove non-staff members
            staff_roles = data.get("staff_roles", [])
            staff_members = []
            for role_id in staff_roles:
                role = interaction.guild.get_role(role_id)
                if role:
                    for member in role.members:
                        staff_members.append(member.id)

            for member in interaction.channel.members:
                if not member.bot and member.id not in staff_members and not member.guild_permissions.administrator:
                    await interaction.channel.set_permissions(member, view_channel=False)

            # Rename the ticket (with delay to avoid rate limiting)
            ticket_type = ticket_name.split('-')[0]
            new_channel_name = f"closed-{ticket_type}-{ticket_name.split('-')[1]}"

            # Only rename if it's not already closed
            if not interaction.channel.name.startswith("closed-"):
                await asyncio.sleep(1)  # Small delay to prevent rate limiting
                await interaction.channel.edit(name=new_channel_name)


            # Log ticket closing
            await log_ticket_action(interaction.guild, "ticket_closed", {
                "channel": interaction.channel.mention,
                "closed_by": interaction.user
            })

            # Send closed actions view
            closed_embed = discord.Embed(
                title="<:TicketLOGO:1407730639343714397> Ticket Closed",
                description="This ticket has been closed. What would you like to do?",
                color=0x57f287
            )

            closed_view = TicketClosedActionsView()
            await interaction.channel.send(embed=closed_embed, view=closed_view)

            # Update ticket status
            update_ticket_status(interaction.channel.id, {"status": "closed"})

        except Exception as e:
            await interaction.followup.send(f"<:ErrorLOGO:1407071682031648850> Erreur lors de la fermeture du ticket: {str(e)}", ephemeral=True)

    @bot.tree.command(name="delete", description="Supprime le ticket actuel")
    async def delete_command(interaction: discord.Interaction):
        # Check if the command is used in a ticket channel
        channel_name = interaction.channel.name
        is_ticket = any(pattern in channel_name for pattern in ['-0', '-1', '-2', '-3', '-4', '-5', '-6', '-7', '-8', '-9']) or channel_name.startswith("closed-")

        if not is_ticket:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Cette commande ne peut être utilisée que dans un channel de ticket.", ephemeral=True)
            return

        try:
            # Log deletion
            await log_ticket_action(interaction.guild, "ticket_deleted", {
                "channel": interaction.channel.mention,
                "deleted_by": interaction.user
            })

            # Send deletion message
            deletion_embed = discord.Embed(
                title="<:DeleteLOGO:1407071421363916841> Deleting Ticket...",
                description="Deleting the ticket in 3 seconds...",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=deletion_embed, ephemeral=False)
            await asyncio.sleep(3)

            # Delete the channel
            await interaction.channel.delete(reason=f"Ticket supprimé par {interaction.user}")

            # Remove ticket status
            remove_ticket_status(interaction.channel.id)

        except Exception as e:
            await interaction.response.send_message(f"<:ErrorLOGO:1407071682031648850> Erreur lors de la suppression du ticket: {str(e)}", ephemeral=True)

    @bot.tree.command(name="claim", description="Prend possession du ticket, supprime tous les autres staff")
    async def claim_command(interaction: discord.Interaction):
        # Check if the command is used in a ticket channel
        channel_name = interaction.channel.name
        is_ticket = any(pattern in channel_name for pattern in ['-0', '-1', '-2', '-3', '-4', '-5', '-6', '-7', '-8', '-9'])

        if not is_ticket:
            embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Erreur",
                description="Cette commande ne peut être utilisée que dans un channel de ticket.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            # Get the staff roles from the ticket data
            data = load_ticket_data()
            staff_roles = data.get("staff_roles", [])

            # Identify staff members to keep based on the command executor's roles
            staff_to_keep = [interaction.user.id]
            for role_id in staff_roles:
                role = interaction.guild.get_role(role_id)
                if role and interaction.user.top_role >= role:
                    for member in role.members:
                        if member.top_role <= interaction.user.top_role:
                            staff_to_keep.append(member.id)

            # Remove all other staff members from the ticket
            for member in interaction.channel.members:
                if not member.bot and member.id not in staff_to_keep and not member.guild_permissions.administrator:
                    await interaction.channel.set_permissions(member, view_channel=False)

            # Log ticket claiming
            await log_ticket_action(interaction.guild, "ticket_claimed", {
                "channel": interaction.channel.mention,
                "claimed_by": interaction.user
            })

            embed = discord.Embed(
                title="<:SucessLOGO:1407071637840592977> Ticket Claimed",
                description="This ticket has been claimed.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"<:ErrorLOGO:1407071682031648850> Erreur lors de la prise en charge: {str(e)}", ephemeral=True)

    @bot.tree.command(name="reopen", description="Rouvre un ticket fermé")
    async def reopen_command(interaction: discord.Interaction):
        # Check if the command is used in a ticket channel
        channel_name = interaction.channel.name
        is_closed_ticket = channel_name.startswith("closed-")

        if not is_closed_ticket:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Cette commande ne peut être utilisée que dans un ticket fermé.", ephemeral=True)
            return

        try:
            data = load_ticket_data()
            channel_data = data.get("closed_tickets", {}).get(str(interaction.channel.id))

            if not channel_data:
                await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Ce ticket n'est pas dans l'état fermé ou les données sont introuvables.", ephemeral=True)
                return

            # Restore original name (with delay to avoid rate limiting)
            original_name = channel_data["original_name"]

            # Only rename if it's currently closed
            if interaction.channel.name.startswith("closed-"):
                await asyncio.sleep(2)  # Delay to prevent rate limiting
                await interaction.channel.edit(name=original_name)


            # Restore permissions
            for member_id, perms in channel_data.get("permissions", {}).items():
                member = interaction.guild.get_member(int(member_id))
                if member:
                    await interaction.channel.set_permissions(
                        member,
                        view_channel=perms["view_channel"],
                        send_messages=perms["send_messages"],
                        read_message_history=perms["read_message_history"]
                    )

            # Remove from closed tickets
            if str(interaction.channel.id) in data["closed_tickets"]:
                del data["closed_tickets"][str(interaction.channel.id)]
                save_ticket_data(data)

            # Log reopening
            await log_ticket_action(interaction.guild, "ticket_reopened", {
                "channel": interaction.channel.mention,
                "reopened_by": interaction.user
            })

            # Send reopening message with new close button
            reopen_embed = discord.Embed(
                title="<:ViewLOGO:1407071916824461435> Ticket Reopened",
                description="This ticket has been reopened successfully!",
                color=0x57f287
            )

            # Create new close view
            close_view = TicketCloseView()
            await interaction.channel.send(embed=reopen_embed, view=close_view)

            # Update ticket status
            update_ticket_status(interaction.channel.id, {
                "status": "open",
                "original_name": original_name,
                "reopened_by": interaction.user.id,
                "reopened_at": datetime.now().isoformat()
            })

        except Exception as e:
            await interaction.response.send_message(f"<:ErrorLOGO:1407071682031648850> Erreur lors de la réouverture du ticket: {str(e)}", ephemeral=True)

    @bot.tree.command(name="transcript", description="Sauvegarde la transcription du ticket")
    async def transcript_command(interaction: discord.Interaction):
        # Check if the command is used in a ticket channel
        channel_name = interaction.channel.name
        is_ticket = any(pattern in channel_name for pattern in ['-0', '-1', '-2', '-3', '-4', '-5', '-6', '-7', '-8', '-9']) or channel_name.startswith("closed-")

        if not is_ticket:
            await interaction.response.send_message("<:ErrorLOGO:1407071682031648850> Cette commande ne peut être utilisée que dans un channel de ticket.", ephemeral=True)
            return

        try:
            await interaction.response.defer(ephemeral=True)

            # Get ticket data
            data = load_ticket_data()

            # Find ticket owner and panel info
            ticket_owner = None
            panel_name = "Unknown Panel"
            panel_emoji = "<:TicketLOGO:1407730639343714397>"
            ticket_type = "unknown"

            # Extract ticket type from channel name
            if channel_name.startswith("closed-"):
                # For closed tickets: closed-support-0001 -> support
                parts = channel_name.replace("closed-", "").split('-')
                if len(parts) >= 1:
                    ticket_type = parts[0]
            else:
                # For regular tickets: support-0001 -> support
                parts = channel_name.split('-')
                if len(parts) >= 1:
                    ticket_type = parts[0]

            # Find matching panel
            for panel_id, panel in data.get("tickets", {}).items():
                if "sub_panels" in panel:
                    for sub_panel_id, sub_panel in panel["sub_panels"].items():
                        sub_panel_name = sub_panel["name"].lower().strip()
                        if sub_panel_name == ticket_type.lower().strip():
                            panel_name = sub_panel.get("panel_title", sub_panel.get("ticket_title", sub_panel.get("title", "Panel par Défaut")))
                            panel_emoji = sub_panel.get("panel_emoji", sub_panel.get("button_emoji", "<:TicketLOGO:1407730639343714397>"))
                            break
                    else:
                        continue
                    break

            # Find ticket owner
            for member in interaction.channel.members:
                if not member.bot and member != interaction.guild.me:
                    perms = interaction.channel.permissions_for(member)
                    if perms.send_messages and not any(role.id in data.get("staff_roles", []) for role in member.roles):
                        ticket_owner = member
                        break

            if not ticket_owner:
                async for message in interaction.channel.history(limit=100, oldest_first=True):
                    if not message.author.bot and message.author != interaction.guild.me:
                        ticket_owner = message.author
                        break

            # Generate transcript
            transcript_data = {
                "server_info": {
                    "server_name": interaction.guild.name,
                    "server_id": interaction.guild.id,
                    "channel_name": interaction.channel.name,
                    "channel_id": interaction.channel.id
                },
                "ticket_info": {
                    "ticket_owner": {
                        "name": ticket_owner.display_name if ticket_owner else "Utilisateur Inconnu",
                        "username": f"{ticket_owner.name}#{ticket_owner.discriminator}" if ticket_owner and ticket_owner.discriminator != "0" else ticket_owner.name if ticket_owner else "Inconnu",
                        "id": ticket_owner.id if ticket_owner else None,
                        "avatar_url": ticket_owner.display_avatar.url if ticket_owner else None
                    },
                    "ticket_name": interaction.channel.name,
                    "panel_name": panel_name,
                    "panel_emoji": panel_emoji,
                    "created_at": datetime.now().isoformat(),
                    "transcript_saved_by": {
                        "name": interaction.user.display_name,
                        "username": f"{interaction.user.name}#{interaction.user.discriminator}" if interaction.user.discriminator != "0" else interaction.user.name,
                        "id": interaction.user.id,
                        "avatar_url": interaction.user.display_avatar.url
                    }
                },
                "messages": []
            }

            # Count messages
            message_count = 0
            async for message in interaction.channel.history(limit=None, oldest_first=True):
                message_count += 1
                message_data = {
                    "id": message.id,
                    "author": {
                        "name": message.author.display_name,
                        "username": f"{message.author.name}#{message.author.discriminator}" if message.author.discriminator != "0" else message.author.name,
                        "id": message.author.id,
                        "bot": message.author.bot,
                        "avatar_url": message.author.display_avatar.url
                    },
                    "content": message.content,
                    "timestamp": message.created_at.isoformat(),
                    "embeds": [embed.to_dict() for embed in message.embeds],
                    "attachments": [{"filename": att.filename, "url": att.url, "size": att.size} for att in message.attachments]
                }
                transcript_data["messages"].append(message_data)

            # Save to transcript file
            try:
                with open('ticket_transcript.json', 'r', encoding='utf-8') as f:
                    transcripts = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                transcripts = {}

            transcripts[str(interaction.channel.id)] = transcript_data

            with open('ticket_transcript.json', 'w', encoding='utf-8') as f:
                json.dump(transcripts, f, indent=4, ensure_ascii=False)

            # Create readable transcript file
            transcript_filename = f"transcript_{interaction.channel.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            transcript_content = []

            transcript_content.append(f"=== TRANSCRIPTION TICKET ===")
            transcript_content.append(f"Serveur: {interaction.guild.name}")
            transcript_content.append(f"Canal: #{interaction.channel.name}")
            transcript_content.append(f"Propriétaire: {ticket_owner.display_name if ticket_owner else 'Inconnu'}")
            transcript_content.append(f"Type de Panel: {panel_name}")
            transcript_content.append(f"Sauvegardé par: {interaction.user.display_name}")
            transcript_content.append(f"Date: {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}")
            transcript_content.append(f"Messages: {message_count}")
            transcript_content.append("=" * 50)
            transcript_content.append("")

            # Add all messages
            for msg_data in transcript_data["messages"]:
                timestamp = datetime.fromisoformat(msg_data["timestamp"]).strftime('%d/%m/%Y %H:%M:%S')
                author_name = msg_data["author"]["name"]
                content = msg_data["content"] or "[No content message]"

                transcript_content.append(f"[{timestamp}] {author_name}: {content}")

                # Add embed details
                if msg_data["embeds"]:
                    for i, embed_data in enumerate(msg_data["embeds"], 1):
                        transcript_content.append(f"   └── Embed {i}:")
                        if embed_data.get("title"):
                            transcript_content.append(f"       Title: {embed_data['title']}")
                        if embed_data.get("description"):
                            transcript_content.append(f"       Description: {embed_data['description'][:200]}{'...' if len(embed_data.get('description', '')) > 200 else ''}")
                        if embed_data.get("fields"):
                            transcript_content.append(f"       Fields: {len(embed_data['fields'])}")

                if msg_data["attachments"]:
                    for att in msg_data["attachments"]:
                        transcript_content.append(f"   └── File: {att['filename']} ({att['size']} bytes)")

                transcript_content.append("")

            # Save transcript file
            with open(transcript_filename, 'w', encoding='utf-8') as f:
                f.write('\n'.join(transcript_content))

            # Log transcript saving
            await log_ticket_action(interaction.guild, "transcript_saved", {
                "channel": interaction.channel.mention,
                "saved_by": interaction.user,
                "message_count": message_count,
                "ticket_type": ticket_type,
                "transcript_file": transcript_filename,
                "ticket_owner": ticket_owner.mention if ticket_owner else "Inconnu",
                "panel_name": panel_name
            })

            await interaction.followup.send("<:SucessLOGO:1407071637840592977> Transcript saved successfully and sent to logs!", ephemeral=True)

            # Update ticket status
            update_ticket_status(interaction.channel.id, {"transcript_saved": True})

        except Exception as e:
            await interaction.followup.send(f"<:ErrorLOGO:1407071682031648850> Erreur lors de la sauvegarde de la transcription: {str(e)}", ephemeral=True)

    @bot.event
    async def on_message(message):
        """Handle AI responses in ticket channels"""
        await handle_ai_message(message)

# Helper function to check if a channel is a ticket channel
def is_ticket_channel(channel_name):
    """Check if a channel name matches the ticket channel pattern."""
    # Check if channel name contains ticket patterns
    return any(pattern in channel_name for pattern in ['-0', '-1', '-2', '-3', '-4', '-5', '-6', '-7', '-8', '-9']) or channel_name.startswith("closed-")

# Helper function to update ticket status in @ticket_data.json
def update_ticket_status(channel_id, new_data):
    """Update ticket status in @ticket_data.json."""
    try:
        with open('ticket_data.json', 'r', encoding='utf-8') as f:
            ticket_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        ticket_data = {}

    ticket_data[str(channel_id)] = new_data
    with open('ticket_data.json', 'w', encoding='utf-8') as f:
        json.dump(ticket_data, f, indent=4, ensure_ascii=False)

# Helper function to remove ticket status from @ticket_data.json
def remove_ticket_status(channel_id):
    """Remove ticket status from @ticket_data.json when the ticket is deleted."""
    try:
        with open('ticket_data.json', 'r', encoding='utf-8') as f:
            ticket_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return  # If the file doesn't exist or is corrupted, there's nothing to remove

    channel_id_str = str(channel_id)
    if channel_id_str in ticket_data:
        del ticket_data[channel_id_str]

        with open('ticket_data.json', 'w', encoding='utf-8') as f:
            json.dump(ticket_data, f, indent=4, ensure_ascii=False)

# Persistent views setup function for main bot
def setup_persistent_views(bot):
    """Setup persistent views when bot starts"""
    try:
        # Add persistent views with custom_id
        data = load_ticket_data()

        # Ensure data structure is complete
        if not isinstance(data, dict):
            print("<:ErrorLOGO:1407071682031648850> Invalid ticket data structure")
            return

        # Add views for published panels
        tickets = data.get("tickets", {})
        if isinstance(tickets, dict):
            for panel_id in tickets:
                try:
                    view = PublishedTicketView(panel_id)
                    bot.add_view(view)
                except Exception as e:
                    print(f"<:ErrorLOGO:1407071682031648850> Error adding view for panel {panel_id}: {e}")

        # Add ticket close views
        bot.add_view(TicketCloseView())
        bot.add_view(TicketClosedActionsView())

        print("<:SucessLOGO:1407071637840592977> Ticket system persistent views loaded successfully")
    except Exception as e:
        print(f"<:ErrorLOGO:1407071682031648850> Error setting up ticket persistent views: {e}")
        # Initialize with empty data if there's an error
        try:
            empty_data = {
                "tickets": {},
                "staff_roles": [],
                "settings": {
                    "default_embed": {
                        "title": "",
                        "outside_description": "",
                        "description": "Support will be with you shortly. To close this ticket.",
                        "thumbnail": "",
                        "image": "",
                        "footer": f"{get_bot_name()} - Ticket Bot"
                    },
                    "button_enabled": True,
                    "button_emoji": "<:CloseLOGO:1407072519420248256>",
                    "button_label": "Close Ticket",
                    "ai_enabled": False,
                    "log_settings": {
                        "ticket_opened": True,
                        "ticket_claimed": True,
                        "ticket_closed": True,
                        "ticket_deleted": True,
                        "ticket_reopened": True,
                        "transcript_saved": True
                    }
                },
                "ticket_counters": {},
                "closed_tickets": {}
            }
            save_ticket_data(empty_data)
            print("<:SucessLOGO:1407071637840592977> Initialized empty ticket data structure")
        except Exception as init_error:
            print(f"<:ErrorLOGO:1407071682031648850> Failed to initialize ticket data: {init_error}")

# Helper functions for logs
def create_logs_management_embed(data, guild):
    """Create logs management embed"""
    embed = discord.Embed(
        title="<:DescriptionLOGO:1407733417172533299> Logs Management",
        description="Configure ticket logging settings:",
        color=0x2b2d31
    )

    # Check if log channel is set
    log_channel_id = data["settings"].get("log_channel_id")
    log_channel = guild.get_channel(log_channel_id) if log_channel_id else None

    if log_channel:
        embed.add_field(
            name="<:SettingLOGO:1407071854593839239> Log Channel",
            value=f"{log_channel.mention}",
            inline=False
        )
    else:
        embed.add_field(
            name="<:SettingLOGO:1407071854593839239> Log Channel",
            value="<:ErrorLOGO:1407071682031648850> Not configured",
            inline=False
        )

    # Log settings
    log_settings = data["settings"].get("log_settings", {})

    log_types = [
        ("<:TicketLOGO:1407730639343714397> Ticket Opened", "ticket_opened"),
        ("<:UnviewLOGO:1407072750220345475> Ticket Claimed", "ticket_claimed"),
        ("<:CloseLOGO:1407072519420248256> Ticket Closed", "ticket_closed"),
        ("<:DeleteLOGO:1407071421363916841> Ticket Deleted", "ticket_deleted"),
        ("<:TXTFileLOGO:1407735600752361622> Transcript", "transcript_saved")
    ]

    status_list = []
    for name, key in log_types:
        status = "<:OnLOGO:1407072463883472978> On" if log_settings.get(key, True) else "<:OffLOGO:1407072621836894380> Off"
        status_list.append(f"{name}: {status}")

    embed.add_field(
        name="Log Types",
        value="\n".join(status_list),
        inline=False
    )

    return embed

# Logging system
async def log_ticket_action(guild, action_type, details):
    """Log ticket actions to a specified channel with simplified styling like the example."""
    data = load_ticket_data()
    log_channel_id = data["settings"].get("log_channel_id")
    log_settings = data["settings"].get("log_settings", {})

    # Check if this log type is enabled
    if not log_settings.get(action_type, True):
        return

    log_channel = guild.get_channel(log_channel_id) if log_channel_id else None

    if not log_channel:
        print("Log channel not configured or not found.")
        return

    # Get user object from details - extract ID from mention properly
    user = None
    user_mention = ""

    # Extract user object from various possible keys in 'details'
    user_keys_to_check = ["created_by", "claimed_by", "closed_by", "reopened_by", "deleted_by", "saved_by"]
    found_user = None

    for key in user_keys_to_check:
        if key in details:
            user_data = details[key]
            if isinstance(user_data, discord.User):
                found_user = user_data
                break
            elif isinstance(user_data, discord.Member):
                found_user = user_data
                break
            elif isinstance(user_data, int):
                # If it's an ID, try to get the member
                found_user = guild.get_member(user_data)
                if found_user:
                    break
            elif isinstance(user_data, str) and "<@" in user_data and ">" in user_data:
                # If it's a mention, extract ID and get member
                user_id_str = user_data.replace("<@", "").replace(">", "").replace("!", "")
                try:
                    user_id = int(user_id_str)
                    found_user = guild.get_member(user_id)
                    if found_user:
                        break
                except ValueError:
                    pass # Ignore if ID is not valid

    user = found_user # Assign the found user to the 'user' variable

    # Color mapping for different actions (left border color)
    color_mapping = {
        "ticket_opened": 0x57f287,  # Green
        "ticket_claimed": 0xfee75c, # Yellow
        "ticket_closed": 0xed4245,  # Red
        "ticket_reopened": 0x57f287, # Green
        "ticket_deleted": 0x99aab5,  # Gray
        "transcript_saved": 0x5865f2  # Blurple
    }

    # Action mapping
    action_mapping = {
        "ticket_opened": "Created",
        "ticket_claimed": "Claimed",
        "ticket_closed": "Closed",
        "ticket_reopened": "Reopened",
        "ticket_deleted": "Deleted",
        "transcript_saved": "Transcript Saved"
    }

    # Extract ticket info from channel mention
    channel_name = "Unknown"
    ticket_name = "Unknown"
    ticket_type = "unknown"

    if "channel" in details:
        channel_mention = details["channel"]
        if isinstance(channel_mention, discord.TextChannel): # If it's already a channel object
            channel_name = channel_mention.name
        elif isinstance(channel_mention, str) and "<#" in channel_mention:
            channel_id_str = channel_mention.replace("<#", "").replace(">", "")
            try:
                channel_id = int(channel_id_str)
                channel_obj = guild.get_channel(channel_id)
                if channel_obj:
                    channel_name = channel_obj.name
            except ValueError:
                pass
        else:
            channel_name = channel_mention

    # Extract ticket info from channel name
    if "-" in channel_name:
        if channel_name.startswith("closed-"):
            # For closed tickets: closed-support-0048 -> support, Ticket-0048
            parts = channel_name.replace("closed-", "").split('-')
            if len(parts) >= 2: # Expecting at least type and number
                ticket_type = parts[0]
                ticket_name = f"Ticket-{parts[1]}"
        else:
            # For regular tickets: support-0048 -> support, Ticket-0048
            parts = channel_name.split("-")
            if len(parts) >= 2: # Expecting at least type and number
                ticket_type = parts[0]
                ticket_name = f"Ticket-{parts[1]}"

    # Find panel info - better search logic
    panel_name = "<:TicketLOGO:1407730639343714397> Default Panel"

    # Check if panel_name is already provided in details
    if "panel_name" in details and details["panel_name"]:
        panel_name = f"<:TicketLOGO:1407730639343714397> {details['panel_name']}"
    elif "ticket_type" in details:
        ticket_type = details["ticket_type"]
        # Search for matching panel
        for panel_id, panel in data.get("tickets", {}).items():
            if "sub_panels" in panel:
                for sub_panel_id, sub_panel in panel["sub_panels"].items():
                    sub_panel_name = sub_panel["name"].lower().strip()
                    if sub_panel_name == ticket_type.lower().strip():
                        # Prioritize panel_title, then ticket_title, then title
                        panel_title = sub_panel.get("panel_title") or sub_panel.get("ticket_title") or sub_panel.get("title", "Default Panel")
                        panel_name = f"<:TicketLOGO:1407730639343714397> {panel_title}"
                        break
                else:
                    continue
                break
    else:
        # Try to find panel from extracted ticket_type
        for panel_id, panel in data.get("tickets", {}).items():
            if "sub_panels" in panel:
                for sub_panel_id, sub_panel in panel["sub_panels"].items():
                    sub_panel_name = sub_panel["name"].lower().strip()
                    if sub_panel_name == ticket_type.lower().strip():
                        panel_title = sub_panel.get("panel_title") or sub_panel.get("ticket_title") or sub_panel.get("title", "Default Panel")
                        panel_name = f"<:TicketLOGO:1407730639343714397> {panel_title}"
                        break
                else:
                    continue
                break

    # Create simplified embed like the example
    embed = discord.Embed(
        color=color_mapping.get(action_type, 0x7289da)
    )

    # Set user as author with avatar (top of embed) - this is crucial
    if user:
        embed.set_author(
            name=user.display_name,
            icon_url=user.display_avatar.url
        )
    else:
        # Fallback if user not found
        embed.set_author(
            name="Unknown User",
            icon_url="https://cdn.discordapp.com/embed/avatars/0.png"
        )

    # Create the main content fields exactly like the example
    logged_info = f"**Logged Info**\nTicket: {ticket_name}\nAction: {action_mapping.get(action_type, 'Action')}"

    panel_info = f"**Panel**\n{panel_name}"

    embed.add_field(name="", value=logged_info, inline=True)
    embed.add_field(name="", value=panel_info, inline=True)

    # For transcript action, add simplified info
    if action_type == "transcript_saved" and "message_count" in details:
        embed.add_field(name="", value=f"**Messages:** {details['message_count']}", inline=False)

    # Send the log message
    if action_type == "transcript_saved" and "transcript_file" in details:
        # Send with transcript file attachment but don't overload the embed
        try:
            with open(details["transcript_file"], 'rb') as f:
                file = discord.File(f, filename=details["transcript_file"])
                await log_channel.send(embed=embed, file=file)

            # Clean up the file after sending
            import os
            os.remove(details["transcript_file"])
        except Exception as e:
            print(f"Error sending transcript file: {e}")
            await log_channel.send(embed=embed)
    else:
        await log_channel.send(embed=embed)
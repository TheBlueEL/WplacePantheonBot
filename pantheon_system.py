
import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import aiohttp
import uuid
import base64
import requests
import time

def get_bot_name(bot):
    """Get the bot's display name"""
    return bot.user.display_name if bot.user else "Bot"

class PantheonArtwork:
    def __init__(self):
        self.id = self.generate_unique_id()
        self.title = ""
        self.description = ""
        self.location = ""
        self.image_url = ""
        self.author_enabled = False
        self.author_name = ""
        self.author_icon = ""
        self.created_by = ""

    def generate_unique_id(self):
        """Generate a unique ID based on timestamp and random UUID"""
        timestamp = str(int(time.time() * 1000))
        unique_part = str(uuid.uuid4())[:8]
        return f"artwork_{timestamp}_{unique_part}"

class PantheonManagerView(discord.ui.View):
    def __init__(self, bot, creator_id):
        super().__init__(timeout=300)
        self.bot = bot
        self.creator_id = creator_id
        self.artworks_data = self.load_artworks()
        self.current_artwork = PantheonArtwork()
        self.creating_mode = False
        self.edit_mode = False
        self.edit_select_mode = False
        self.editing_index = None
        self.image_mode = False
        self.waiting_for_image = False
        self.delete_mode = False
        self.delete_select_mode = False

    def load_artworks(self):
        try:
            with open('pantheon_data.json', 'r') as f:
                data = json.load(f)
                # Add IDs to existing artworks that don't have them
                for artwork in data.get("artworks", []):
                    if "id" not in artwork:
                        artwork["id"] = PantheonArtwork().generate_unique_id()
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            return {"artworks": []}

    def save_artworks(self):
        with open('pantheon_data.json', 'w') as f:
            json.dump(self.artworks_data, f, indent=2)

    def save_current_artwork(self):
        """Save the current artwork to the artworks list"""
        if (self.current_artwork.title or 
            self.current_artwork.description or 
            self.current_artwork.image_url):
            
            artwork_dict = {
                "id": self.current_artwork.id,
                "title": self.current_artwork.title,
                "description": self.current_artwork.description,
                "location": self.current_artwork.location,
                "image_url": self.current_artwork.image_url,
                "author_enabled": self.current_artwork.author_enabled,
                "author_name": self.current_artwork.author_name,
                "author_icon": self.current_artwork.author_icon,
                "created_by": self.current_artwork.created_by
            }

            if self.edit_mode and self.editing_index is not None:
                existing_artwork = self.artworks_data["artworks"][self.editing_index]
                if existing_artwork.get("id") == self.current_artwork.id:
                    self.artworks_data["artworks"][self.editing_index] = artwork_dict
                else:
                    for i, artwork in enumerate(self.artworks_data["artworks"]):
                        if artwork.get("id") == self.current_artwork.id:
                            self.artworks_data["artworks"][i] = artwork_dict
                            break
            else:
                existing_index = None
                for i, artwork in enumerate(self.artworks_data["artworks"]):
                    if artwork.get("id") == self.current_artwork.id:
                        existing_index = i
                        break

                if existing_index is not None:
                    self.artworks_data["artworks"][existing_index] = artwork_dict
                else:
                    self.artworks_data["artworks"].append(artwork_dict)

            self.save_artworks()

    def get_main_embed(self, username):
        artworks_count = len(self.artworks_data["artworks"])

        embed = discord.Embed(
            title="<:WplacePantheonLOGO:1407152471226187776> Wplace Pantheon",
            description=f"Welcome back @{username}!\n\nWelcome to the Wplace Pantheon! Where all the most beautiful artworks are showcased and protected by our teams!",
            color=0x5865F2
        )

        if artworks_count > 0:
            embed.add_field(
                name="Pantheonized Artworks",
                value=f"**{artworks_count}** artwork(s) in the pantheon",
                inline=False
            )

        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Wplace Pantheon", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_create_embed(self):
        title = "Edit Artwork" if self.edit_mode else "Create Artwork"
        action = "Editing Artwork" if self.edit_mode else "Creating Artwork"
        
        embed = discord.Embed(
            title=f"<:CreateLOGO:1407071205026168853> {title}",
            description="Configure your artwork settings using the buttons below.",
            color=0x00D166
        )

        status = ""
        if self.current_artwork.title:
            status += f"Title: {self.current_artwork.title[:30]}\n"
        if self.current_artwork.description:
            status += f"Description: {self.current_artwork.description[:50]}...\n"
        if self.current_artwork.location:
            status += f"Location: {self.current_artwork.location[:30]}\n"

        if self.current_artwork.author_enabled:
            if self.current_artwork.author_name:
                status += f"Author: {self.current_artwork.author_name} (Enabled)\n"
            else:
                status += "Author: None (Enabled)\n"
        else:
            status += "Author: Disabled\n"

        if self.current_artwork.image_url:
            status += "Image: Set\n"

        if status:
            embed.add_field(
                name="Current Settings",
                value=status,
                inline=False
            )

        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | {action}", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_edit_embed(self):
        embed = discord.Embed(
            title="<:EditLOGO:1407071307022995508> Edit Artwork",
            description="Which artwork would you like to edit?",
            color=discord.Color.orange()
        )

        if not self.artworks_data["artworks"]:
            embed.description = "You cannot edit artworks because no artworks have been created."

        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Edit Artwork", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_delete_embed(self):
        embed = discord.Embed(
            title="<:DeleteLOGO:1407071421363916841> Delete Artwork",
            description="Which artwork would you like to delete?",
            color=discord.Color.red()
        )

        if not self.artworks_data["artworks"]:
            embed.description = "You cannot delete artworks because no artworks have been created."

        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Delete Artwork", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_image_settings_embed(self):
        embed = discord.Embed(
            title="<:ImageLOGO:1407072328134951043> Image Settings",
            description="Configure image settings for your artwork",
            color=discord.Color.purple()
        )

        status = ""
        if self.current_artwork.image_url:
            status += "<:SucessLOGO:1407071637840592977> Image: Set\n"
        else:
            status += "<:ErrorLOGO:1407071682031648850> Image: Not set\n"

        embed.add_field(
            name="Current Status",
            value=status,
            inline=False
        )

        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Image Settings", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_waiting_image_embed(self):
        embed = discord.Embed(
            title="<:UploadLOGO:1407072005567545478> Upload Image",
            description="Please send an image file in this channel.\n\n**Only you can upload the image for security reasons.**",
            color=discord.Color.blue()
        )

        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Upload Image", icon_url=self.bot.user.display_avatar.url)

        return embed

    def update_buttons(self):
        self.clear_items()

        if self.waiting_for_image:
            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>",
                row=0
            )

            async def back_callback(interaction):
                self.waiting_for_image = False
                embed = self.get_image_settings_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            back_button.callback = back_callback
            self.add_item(back_button)

        elif self.image_mode:
            image_url_button = discord.ui.Button(
                label="Image URL",
                style=discord.ButtonStyle.primary,
                emoji="<:URLLOGO:1407071963809054931>",
                row=0
            )

            async def image_url_callback(interaction):
                modal = PantheonImageURLModal(self.current_artwork, self)
                await interaction.response.send_modal(modal)

            image_url_button.callback = image_url_callback

            upload_image_button = discord.ui.Button(
                label="Upload Image",
                style=discord.ButtonStyle.secondary,
                emoji="<:UploadLOGO:1407072005567545478>",
                row=0
            )

            async def upload_image_callback(interaction):
                self.waiting_for_image = True
                embed = self.get_waiting_image_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            upload_image_button.callback = upload_image_callback

            clear_button = discord.ui.Button(
                label="Clear Image",
                style=discord.ButtonStyle.danger,
                emoji="<:DeleteLOGO:1407071421363916841>",
                row=0
            )

            async def clear_callback(interaction):
                self.current_artwork.image_url = ""
                embed = self.get_image_settings_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)
                self.save_current_artwork()

            clear_button.callback = clear_callback

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>",
                row=1
            )

            async def back_callback(interaction):
                self.image_mode = False
                embed = self.get_create_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            back_button.callback = back_callback

            self.add_item(image_url_button)
            self.add_item(upload_image_button)
            self.add_item(clear_button)
            self.add_item(back_button)

        elif self.delete_select_mode:
            if self.artworks_data["artworks"]:
                select = ArtworkDeleteSelect(self.artworks_data["artworks"])
                self.add_item(select)

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )

            async def back_callback(interaction):
                self.delete_select_mode = False
                self.delete_mode = False
                embed = self.get_main_embed(interaction.user.display_name)
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            back_button.callback = back_callback
            self.add_item(back_button)

        elif self.edit_select_mode:
            if self.artworks_data["artworks"]:
                select = ArtworkEditSelect(self.artworks_data["artworks"])
                self.add_item(select)

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )

            async def back_callback(interaction):
                self.edit_select_mode = False
                embed = self.get_main_embed(interaction.user.display_name)
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            back_button.callback = back_callback
            self.add_item(back_button)

        elif not self.creating_mode:
            create_button = discord.ui.Button(
                label="Create",
                style=discord.ButtonStyle.success,
                emoji="<:CreateLOGO:1407071205026168853>",
                row=0
            )

            async def create_callback(interaction):
                self.creating_mode = True
                self.edit_mode = False
                self.editing_index = None
                self.current_artwork = PantheonArtwork()
                self.current_artwork.created_by = str(interaction.user.id)
                self.current_artwork.author_enabled = False
                embed = self.get_create_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            create_button.callback = create_callback
            self.add_item(create_button)

            if self.artworks_data["artworks"]:
                edit_button = discord.ui.Button(
                    label="Edit",
                    style=discord.ButtonStyle.primary,
                    emoji="<:EditLOGO:1407071307022995508>",
                    row=0
                )

                async def edit_callback(interaction):
                    self.edit_select_mode = True
                    embed = self.get_edit_embed()
                    self.update_buttons()
                    await interaction.response.edit_message(embed=embed, view=self)

                edit_button.callback = edit_callback
                self.add_item(edit_button)

                delete_button = discord.ui.Button(
                    label="Delete",
                    style=discord.ButtonStyle.danger,
                    emoji="<:DeleteLOGO:1407071421363916841>",
                    row=0
                )

                async def delete_callback(interaction):
                    self.delete_select_mode = True
                    embed = self.get_delete_embed()
                    self.update_buttons()
                    await interaction.response.edit_message(embed=embed, view=self)

                delete_button.callback = delete_callback
                self.add_item(delete_button)

        else:
            image_button = discord.ui.Button(
                label="Image Settings",
                style=discord.ButtonStyle.primary,
                emoji="<:ImageLOGO:1407072328134951043>"
            )

            async def image_callback(interaction):
                self.image_mode = True
                embed = self.get_image_settings_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            image_button.callback = image_callback
            self.add_item(image_button)

            basic_button = discord.ui.Button(
                label="Basic Settings",
                style=discord.ButtonStyle.primary,
                emoji="<:SettingLOGO:1407071854593839239>"
            )

            async def basic_callback(interaction):
                modal = PantheonBasicModal(self.current_artwork)
                await interaction.response.send_modal(modal)

            basic_button.callback = basic_callback
            self.add_item(basic_button)

            author_button = discord.ui.Button(
                label="Author Settings",
                style=discord.ButtonStyle.secondary,
                emoji="<:ParticipantsLOGO:1391530606977880145>"
            )

            async def author_callback(interaction):
                view = PantheonAuthorSettingsView(self.current_artwork, interaction.guild, self)
                embed = discord.Embed(
                    title="<:ParticipantLOGO:1407072406329360478> Author Settings",
                    description="Configure the artwork author settings",
                    color=discord.Color.orange()
                )

                if self.current_artwork.author_enabled:
                    if self.current_artwork.author_name:
                        embed.add_field(
                            name="Current Author",
                            value=f"**{self.current_artwork.author_name}** (Enabled)",
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name="Current Author",
                            value="None (Enabled)",
                            inline=False
                        )
                else:
                    embed.add_field(
                        name="Current Author",
                        value="Disabled",
                        inline=False
                    )

                bot_name = get_bot_name(self.bot)
                embed.set_thumbnail(url=self.bot.user.display_avatar.url)
                embed.set_footer(text=f"{bot_name} | Author Settings", icon_url=self.bot.user.display_avatar.url)

                await interaction.response.edit_message(embed=embed, view=view)

            author_button.callback = author_callback
            self.add_item(author_button)

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )

            async def back_callback(interaction):
                self.save_current_artwork()
                self.creating_mode = False
                self.edit_mode = False
                self.editing_index = None
                embed = self.get_main_embed(interaction.user.display_name)
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            back_button.callback = back_callback
            self.add_item(back_button)

class PantheonImageURLModal(discord.ui.Modal):
    def __init__(self, artwork_data, parent_view):
        super().__init__(title='Set Image URL')
        self.artwork_data = artwork_data
        self.parent_view = parent_view

        self.url_input = discord.ui.TextInput(
            label='Image URL',
            placeholder='https://example.com/image.png',
            required=True,
            max_length=500
        )

        self.add_item(self.url_input)

    async def on_submit(self, interaction: discord.Interaction):
        image_url = self.url_input.value.strip()
        self.artwork_data.image_url = image_url
        
        self.parent_view.image_mode = True
        embed = self.parent_view.get_image_settings_embed()
        self.parent_view.update_buttons()
        self.parent_view.save_current_artwork()
        
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

class PantheonBasicModal(discord.ui.Modal):
    def __init__(self, artwork_data):
        super().__init__(title='Basic Artwork Settings')
        self.artwork_data = artwork_data

        self.title_input = discord.ui.TextInput(
            label='Title',
            placeholder='Enter the artwork title...',
            required=True,
            max_length=256,
            default=artwork_data.title
        )

        self.description_input = discord.ui.TextInput(
            label='Description',
            placeholder='Enter the artwork description...',
            required=True,
            max_length=4000,
            style=discord.TextStyle.paragraph,
            default=artwork_data.description
        )

        self.location_input = discord.ui.TextInput(
            label='Location (Optional)',
            placeholder='Enter the artwork location...',
            required=False,
            max_length=256,
            default=artwork_data.location
        )

        self.add_item(self.title_input)
        self.add_item(self.description_input)
        self.add_item(self.location_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.artwork_data.title = self.title_input.value
        self.artwork_data.description = self.description_input.value
        self.artwork_data.location = self.location_input.value

        await interaction.response.defer()

class PantheonAuthorSettingsView(discord.ui.View):
    def __init__(self, artwork_data, guild, parent_view=None):
        super().__init__(timeout=300)
        self.artwork_data = artwork_data
        self.guild = guild
        self.parent_view = parent_view

        self.toggle_button = discord.ui.Button(
            label="ON" if self.artwork_data.author_enabled else "OFF",
            style=discord.ButtonStyle.success if self.artwork_data.author_enabled else discord.ButtonStyle.danger,
            emoji="<:ONLOGO:1391530620366094440>" if self.artwork_data.author_enabled else "<:OFFLOGO:1391535388065271859>"
        )
        self.toggle_button.callback = self.toggle_author

        self.add_item(self.toggle_button)

    async def toggle_author(self, interaction: discord.Interaction):
        self.artwork_data.author_enabled = not self.artwork_data.author_enabled

        if self.artwork_data.author_enabled and not self.artwork_data.author_name:
            self.artwork_data.author_name = interaction.user.display_name
            self.artwork_data.author_icon = interaction.user.display_avatar.url

        self.toggle_button.label = "ON" if self.artwork_data.author_enabled else "OFF"
        self.toggle_button.style = discord.ButtonStyle.success if self.artwork_data.author_enabled else discord.ButtonStyle.danger
        self.toggle_button.emoji = "<:ONLOGO:1391530620366094440>" if self.artwork_data.author_enabled else "<:OFFLOGO:1391535388065271859>"

        embed = discord.Embed(
            title="<:ParticipantLOGO:1407072406329360478> Author Settings",
            description="Configure the artwork author settings",
            color=discord.Color.orange()
        )

        if self.artwork_data.author_enabled:
            embed.add_field(
                name="Current Author",
                value=f"**{self.artwork_data.author_name}** (Enabled)",
                inline=False
            )
        else:
            embed.add_field(
                name="Current Author",
                value="Disabled",
                inline=False
            )

        if self.parent_view:
            bot_name = get_bot_name(self.parent_view.bot)
            embed.set_thumbnail(url=self.parent_view.bot.user.display_avatar.url)
            embed.set_footer(text=f"{bot_name} | Author Settings", icon_url=self.parent_view.bot.user.display_avatar.url)

        await interaction.response.edit_message(embed=embed, view=self)

        if self.parent_view and hasattr(self.parent_view, 'save_current_artwork'):
            self.parent_view.save_current_artwork()

    @discord.ui.button(label="Set Author", style=discord.ButtonStyle.secondary, emoji="<:EditLOGO:1391511560500940942>")
    async def set_custom_author(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PantheonCustomAuthorModal(self.artwork_data, self.guild, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1391511633431494666>")
    async def back_to_create(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.parent_view:
            embed = self.parent_view.get_create_embed()
            self.parent_view.update_buttons()
            await interaction.response.edit_message(embed=embed, view=self.parent_view)

class PantheonCustomAuthorModal(discord.ui.Modal):
    def __init__(self, artwork_data, guild, parent_view):
        super().__init__(title='Set Custom Author')
        self.artwork_data = artwork_data
        self.guild = guild
        self.parent_view = parent_view

        self.user_input = discord.ui.TextInput(
            label='User ID or Username',
            placeholder='Enter user ID or username',
            required=True,
            max_length=100
        )

        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_input = self.user_input.value.strip()
        user = None

        if user_input.isdigit():
            try:
                user = self.guild.get_member(int(user_input))
                if not user:
                    user = await self.guild.fetch_member(int(user_input))
            except:
                pass

        if not user:
            for member in self.guild.members:
                if member.name.lower() == user_input.lower() or member.display_name.lower() == user_input.lower():
                    user = member
                    break

        if user:
            self.artwork_data.author_name = user.display_name
            self.artwork_data.author_icon = user.display_avatar.url
            self.artwork_data.author_enabled = True

            embed = discord.Embed(
                title="<:ParticipantLOGO:1407072406329360478> Author Settings",
                description="Configure the artwork author settings",
                color=discord.Color.orange()
            )

            embed.add_field(
                name="Current Author",
                value=f"**{self.artwork_data.author_name}** (Enabled)",
                inline=False
            )

            if self.parent_view and hasattr(self.parent_view, 'parent_view'):
                bot_name = get_bot_name(self.parent_view.parent_view.bot)
                embed.set_thumbnail(url=self.parent_view.parent_view.bot.user.display_avatar.url)
                embed.set_footer(text=f"{bot_name} | Author Settings", icon_url=self.parent_view.parent_view.bot.user.display_avatar.url)

            self.parent_view.toggle_button.label = "ON"
            self.parent_view.toggle_button.style = discord.ButtonStyle.success
            self.parent_view.toggle_button.emoji = "<:ONLOGO:1391530620366094440>"

            await interaction.response.edit_message(embed=embed, view=self.parent_view)

            if self.parent_view and hasattr(self.parent_view, 'parent_view') and hasattr(self.parent_view.parent_view, 'save_current_artwork'):
                self.parent_view.parent_view.save_current_artwork()
        else:
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> User Not Found",
                description="Could not find a user with that ID or username in this server.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

class ArtworkEditSelect(discord.ui.Select):
    def __init__(self, artworks_list):
        self.artworks_list = artworks_list
        options = []

        for i, artwork_data in enumerate(artworks_list[:25]):
            title = artwork_data.get("title", "Untitled")
            if not title.strip():
                title = "Untitled"
            if len(title) > 50:
                title = title[:47] + "..."

            description = artwork_data.get("description", "No description")
            if not description.strip():
                description = "No description"
            if len(description) > 50:
                description = description[:47] + "..."

            options.append(discord.SelectOption(
                label=title,
                description=description,
                value=str(i)
            ))

        super().__init__(
            placeholder="Search and select an artwork to edit...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        selected_index = int(self.values[0])
        selected_artwork = self.artworks_list[selected_index]

        parent_view = self.view
        parent_view.current_artwork = PantheonArtwork()
        parent_view.current_artwork.id = selected_artwork.get("id", parent_view.current_artwork.generate_unique_id())
        parent_view.current_artwork.title = selected_artwork.get("title", "")
        parent_view.current_artwork.description = selected_artwork.get("description", "")
        parent_view.current_artwork.location = selected_artwork.get("location", "")
        parent_view.current_artwork.image_url = selected_artwork.get("image_url", "")
        parent_view.current_artwork.author_enabled = selected_artwork.get("author_enabled", False)
        parent_view.current_artwork.author_name = selected_artwork.get("author_name", "")
        parent_view.current_artwork.author_icon = selected_artwork.get("author_icon", "")
        parent_view.current_artwork.created_by = selected_artwork.get("created_by", "")

        parent_view.editing_index = selected_index
        parent_view.creating_mode = True
        parent_view.edit_mode = True
        parent_view.edit_select_mode = False

        # Show confirm button
        confirm_button = discord.ui.Button(
            label="Confirm",
            style=discord.ButtonStyle.success,
            emoji="<:ConfirmLOGO:1407072680267481249>"
        )

        async def confirm_callback(confirm_interaction):
            embed = parent_view.get_create_embed()
            parent_view.update_buttons()
            await confirm_interaction.response.edit_message(embed=embed, view=parent_view)

        confirm_button.callback = confirm_callback
        
        # Clear existing items and add confirm button
        parent_view.clear_items()
        parent_view.add_item(confirm_button)
        
        # Add back button
        back_button = discord.ui.Button(
            label="Back",
            style=discord.ButtonStyle.gray,
            emoji="<:BackLOGO:1391511633431494666>"
        )

        async def back_callback(back_interaction):
            parent_view.edit_select_mode = False
            embed = parent_view.get_main_embed(back_interaction.user.display_name)
            parent_view.update_buttons()
            await back_interaction.response.edit_message(embed=embed, view=parent_view)

        back_button.callback = back_callback
        parent_view.add_item(back_button)

        embed = discord.Embed(
            title="<:EditLOGO:1407071307022995508> Confirm Edit",
            description=f"You selected: **{selected_artwork.get('title', 'Untitled')}**\n\nClick Confirm to proceed with editing this artwork.",
            color=discord.Color.orange()
        )

        bot_name = get_bot_name(parent_view.bot)
        embed.set_thumbnail(url=parent_view.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Confirm Edit", icon_url=parent_view.bot.user.display_avatar.url)

        await interaction.response.edit_message(embed=embed, view=parent_view)

class ArtworkDeleteSelect(discord.ui.Select):
    def __init__(self, artworks_list):
        self.artworks_list = artworks_list
        options = []

        for i, artwork_data in enumerate(artworks_list[:25]):
            title = artwork_data.get("title", "Untitled")
            if not title.strip():
                title = "Untitled"
            if len(title) > 50:
                title = title[:47] + "..."

            description = artwork_data.get("description", "No description")
            if not description.strip():
                description = "No description"
            if len(description) > 50:
                description = description[:47] + "..."

            options.append(discord.SelectOption(
                label=title,
                description=description,
                value=str(i)
            ))

        super().__init__(
            placeholder="Search and select an artwork to delete...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        selected_index = int(self.values[0])
        selected_artwork = self.artworks_list[selected_index]

        # Show confirm button for deletion
        confirm_button = discord.ui.Button(
            label="Confirm",
            style=discord.ButtonStyle.success,
            emoji="<:ConfirmLOGO:1407072680267481249>"
        )

        async def confirm_callback(confirm_interaction):
            view = PantheonDeleteConfirmView(selected_index, selected_artwork, self.view)

            embed = discord.Embed(
                title="<:WarningLOGO:1407072569487659198> Confirm Deletion",
                description=f"Are you sure you want to delete the artwork **'{selected_artwork.get('title', 'Untitled')}'**?\n\n**This action is irreversible!**",
                color=discord.Color.red()
            )

            parent_view = self.view
            bot_name = get_bot_name(parent_view.bot)
            embed.set_thumbnail(url=parent_view.bot.user.display_avatar.url)
            embed.set_footer(text=f"{bot_name} | Delete Artwork", icon_url=parent_view.bot.user.display_avatar.url)

            await confirm_interaction.response.edit_message(embed=embed, view=view)

        confirm_button.callback = confirm_callback
        
        parent_view = self.view
        parent_view.clear_items()
        parent_view.add_item(confirm_button)
        
        # Add back button
        back_button = discord.ui.Button(
            label="Back",
            style=discord.ButtonStyle.gray,
            emoji="<:BackLOGO:1391511633431494666>"
        )

        async def back_callback(back_interaction):
            parent_view.delete_select_mode = False
            embed = parent_view.get_main_embed(back_interaction.user.display_name)
            parent_view.update_buttons()
            await back_interaction.response.edit_message(embed=embed, view=parent_view)

        back_button.callback = back_callback
        parent_view.add_item(back_button)

        embed = discord.Embed(
            title="<:DeleteLOGO:1407071421363916841> Confirm Selection",
            description=f"You selected: **{selected_artwork.get('title', 'Untitled')}**\n\nClick Confirm to proceed with deleting this artwork.",
            color=discord.Color.red()
        )

        bot_name = get_bot_name(parent_view.bot)
        embed.set_thumbnail(url=parent_view.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Confirm Selection", icon_url=parent_view.bot.user.display_avatar.url)

        await interaction.response.edit_message(embed=embed, view=parent_view)

class PantheonDeleteConfirmView(discord.ui.View):
    def __init__(self, artwork_index, artwork_data, parent_view):
        super().__init__(timeout=300)
        self.artwork_index = artwork_index
        self.artwork_data = artwork_data
        self.parent_view = parent_view

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="<:DeleteLOGO:1407071421363916841>")
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.parent_view.artworks_data["artworks"].pop(self.artwork_index)
        self.parent_view.save_artworks()

        self.parent_view.delete_select_mode = False
        self.parent_view.delete_mode = False
        embed = self.parent_view.get_main_embed(interaction.user.display_name)
        self.parent_view.update_buttons()

        await interaction.response.edit_message(embed=embed, view=self.parent_view)

        confirm_embed = discord.Embed(
            title="<:SucessLOGO:1407071637840592977> Artwork Deleted",
            description="The artwork has been successfully deleted from the pantheon.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=confirm_embed, ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray, emoji="<:CloseLOGO:1391531593524318271>")
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.parent_view.get_delete_embed()
        self.parent_view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

class PantheonCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_managers = {}

    async def download_image(self, image_url):
        """Download image from URL, save locally, sync to GitHub, then delete locally"""
        try:
            os.makedirs('images', exist_ok=True)
            filename = f"{uuid.uuid4()}.png"
            file_path = os.path.join('images', filename)

            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        with open(file_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                f.write(chunk)

                        from github_sync import GitHubSync
                        github_sync = GitHubSync()
                        sync_success = await github_sync.sync_image_to_pictures_repo(file_path)

                        if sync_success:
                            try:
                                os.remove(file_path)
                            except Exception as e:
                                print(f"Error removing local file: {e}")

                            filename = os.path.basename(file_path)
                            github_url = f"https://raw.githubusercontent.com/TheBlueEL/pictures/main/{filename}"
                            return github_url
                        else:
                            return None
            return None
        except Exception as e:
            print(f"Error downloading image: {e}")
            return None

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        user_id = message.author.id
        if user_id in self.active_managers:
            manager = self.active_managers[user_id]
            if manager.waiting_for_image and message.attachments:
                attachment = message.attachments[0]
                allowed_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg']
                if any(attachment.filename.lower().endswith(ext) for ext in allowed_extensions):
                    local_file = await self.download_image(attachment.url)

                    if local_file:
                        try:
                            await message.delete()
                        except:
                            pass

                        manager.current_artwork.image_url = local_file
                        manager.waiting_for_image = False
                        manager.save_current_artwork()

                        embed = discord.Embed(
                            title="<:ImageLOGO:1407072328134951043> Image Settings",
                            description="<:SucessLOGO:1407071637840592977> **Image successfully uploaded!**",
                            color=discord.Color.green()
                        )

                        embed.add_field(
                            name="Current Status",
                            value="<:SucessLOGO:1407071637840592977> Image: Set",
                            inline=False
                        )

                        bot_name = get_bot_name(self.bot)
                        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
                        embed.set_footer(text=f"{bot_name} | Image Settings", icon_url=self.bot.user.display_avatar.url)

                        manager.update_buttons()

                        try:
                            channel = message.channel
                            async for msg in channel.history(limit=50):
                                if msg.author == self.bot.user and msg.embeds:
                                    if "Upload Image" in msg.embeds[0].title:
                                        await msg.edit(embed=embed, view=manager)
                                        break
                        except Exception as e:
                            print(f"Error updating message: {e}")
                else:
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

    @app_commands.command(name="pantheon", description="Manage Wplace Pantheon artworks")
    async def pantheon_command(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Permission Denied",
                description="You need 'Manage Messages' permission to use this command.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        view = PantheonManagerView(self.bot, interaction.user.id)
        view.guild = interaction.guild
        embed = view.get_main_embed(interaction.user.display_name)
        view.update_buttons()

        self.active_managers[interaction.user.id] = view

        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(PantheonCommand(bot))

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
    """Récupère le nom d'affichage du bot"""
    return bot.user.display_name if bot.user else "Bot"

class EmbedData:
    def __init__(self):
        self.id = self.generate_unique_id()
        self.message_content = ""
        self.title = ""
        self.description = ""
        self.color = discord.Color.blurple()
        self.footer = ""
        self.author_enabled = False
        self.author_name = ""
        self.author_icon = ""
        self.image_url = ""
        self.thumbnail_url = ""
        self.decoration_preset = "none"

    def generate_unique_id(self):
        """Generate a unique ID based on timestamp and random UUID"""
        timestamp = str(int(time.time() * 1000))  # Milliseconds timestamp
        unique_part = str(uuid.uuid4())[:8]  # Short UUID part
        return f"embed_{timestamp}_{unique_part}"

class EmbedManagerView(discord.ui.View):
    def __init__(self, bot, creator_id):
        super().__init__(timeout=300)
        self.bot = bot
        self.creator_id = creator_id
        self.embeds_data = self.load_embeds()
        self.current_embed = EmbedData()
        self.creating_mode = False
        self.delete_mode = False
        self.edit_mode = False
        self.edit_select_mode = False
        self.editing_index = None
        self.image_mode = False
        self.waiting_for_image = False
        self.publish_mode = False
        self.selected_embed_index = None
        self.selected_channel = None

    def load_embeds(self):
        try:
            with open('embed_command.json', 'r') as f:
                data = json.load(f)
                # Add IDs to existing embeds that don't have them
                for embed in data.get("created", []):
                    if "id" not in embed:
                        embed["id"] = EmbedData().generate_unique_id()
                for embed in data.get("published", []):
                    if "id" not in embed:
                        embed["id"] = EmbedData().generate_unique_id()
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            return {"created": [], "published": []}

    def save_embeds(self):
        with open('embed_command.json', 'w') as f:
            json.dump(self.embeds_data, f, indent=2)

    def save_current_embed(self):
        """Save the current embed to the created list"""
        # Validate that at least one field is filled
        if (self.current_embed.message_content or 
            self.current_embed.title or 
            self.current_embed.description or 
            self.current_embed.footer):
            # No default thumbnail unless explicitly set

            embed_dict = {
                "id": self.current_embed.id,
                "message_content": self.current_embed.message_content,
                "title": self.current_embed.title,
                "description": self.current_embed.description,
                "color": self.current_embed.color.value,
                "footer": self.current_embed.footer,
                "author_enabled": self.current_embed.author_enabled,
                "author_name": self.current_embed.author_name,
                "author_icon": self.current_embed.author_icon,
                "image_url": self.current_embed.image_url,
                "thumbnail_url": self.current_embed.thumbnail_url,
                "decoration_preset": self.current_embed.decoration_preset
            }

            if self.edit_mode and self.editing_index is not None:
                # Update existing embed by ID
                existing_embed = self.embeds_data["created"][self.editing_index]
                if existing_embed.get("id") == self.current_embed.id:
                    self.embeds_data["created"][self.editing_index] = embed_dict
                else:
                    # Find by ID if index doesn't match
                    for i, embed in enumerate(self.embeds_data["created"]):
                        if embed.get("id") == self.current_embed.id:
                            self.embeds_data["created"][i] = embed_dict
                            break
            else:
                # Check if embed with this ID already exists
                existing_index = None
                for i, embed in enumerate(self.embeds_data["created"]):
                    if embed.get("id") == self.current_embed.id:
                        existing_index = i
                        break

                if existing_index is not None:
                    # Update existing embed
                    self.embeds_data["created"][existing_index] = embed_dict
                else:
                    # Add new embed
                    self.embeds_data["created"].append(embed_dict)

            self.save_embeds()

    def get_main_embed(self):
        created_count = len(self.embeds_data["created"])

        embed = discord.Embed(
            title="Embed Manager",
            color=0x5865F2
        )

        if created_count == 0:
            embed.description = "No embeds created yet. Click the button below to create one!"
        else:
            embed.description = f"You have {created_count} embed(s) created."

            if self.embeds_data["created"]:
                embed_list = ""
                for i, embed_data in enumerate(self.embeds_data["created"][:5]):
                    title = embed_data.get("title", "Untitled")[:30]
                    if not title.strip():
                        title = "Untitled"
                    embed_list += f"• {title}\n"

                if len(self.embeds_data["created"]) > 5:
                    embed_list += f"... and {len(self.embeds_data['created']) - 5} more"

                embed.add_field(
                    name="Your Embeds",
                    value=embed_list,
                    inline=False
                )

        # Add bot branding to main embed
        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Embed Manager", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_create_embed(self):
        title = "Edit Embed" if self.edit_mode else "Create Embed"
        action = "Editing Embed" if self.edit_mode else "Creating Embed"
        embed = discord.Embed(
            title=title,
            description="Configure your embed settings using the buttons below.",
            color=0x00D166
        )

        status = ""
        if self.current_embed.title:
            status += f"Title: {self.current_embed.title[:30]}\n"
        if self.current_embed.description:
            status += f"Description: {self.current_embed.description[:50]}...\n"
        if self.current_embed.footer:
            status += f"Footer: {self.current_embed.footer[:30]}\n"

        # Author status
        if self.current_embed.author_enabled:
            if self.current_embed.author_name:
                status += f"Author: {self.current_embed.author_name} (Enabled)\n"
            else:
                status += "Author: None (Enabled)\n"
        else:
            status += "Author: Disabled\n"

        # Image status
        if self.current_embed.image_url:
            status += "Image: Set\n"
        if self.current_embed.thumbnail_url:
            status += "Thumbnail: Set\n"

        if status:
            embed.add_field(
                name="Current Settings",
                value=status,
                inline=False
            )

        # Add bot branding to create embed
        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | {action}", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_edit_embed(self):
        embed = discord.Embed(
            title="<:EditLOGO:1391511560500940942> Edit Embed",
            description="Which embed would you like to edit?",
            color=discord.Color.orange()
        )

        if not self.embeds_data["created"]:
            embed.description = "You cannot edit embeds because no embeds have been created."

        # Add bot branding to edit embed
        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Edit Embed", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_delete_embed(self):
        embed = discord.Embed(
            title="<:DeleteLOGO:1391511582261116938> Delete Embed",
            description="Which embed would you like to delete?",
            color=discord.Color.red()
        )

        if not self.embeds_data["created"]:
            embed.description = "You cannot delete embeds because no embeds have been created."

        # Add bot branding to delete embed
        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Delete Embed", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_image_settings_embed(self):
        embed = discord.Embed(
            title="<:ImageLOGO:1391530555517960263> Image Settings",
            description="Configure image settings for your embed",
            color=discord.Color.purple()
        )

        status = ""
        if self.current_embed.image_url:
            status += "<:SucessLOGO:1391511887065121020> Classic Image: Set\n"
        else:
            status += "<:ErrorLOGO:1391511903196549201> Classic Image: Not set\n"

        if self.current_embed.thumbnail_url:
            status += "<:SucessLOGO:1391511887065121020> Thumbnail: Set\n"
        else:
            status += "<:ErrorLOGO:1391511903196549201> Thumbnail: Not set\n"

        embed.add_field(
            name="Current Status",
            value=status,
            inline=False
        )

        # Add bot branding to image settings embed
        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Image Settings", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_waiting_image_embed(self):
        embed = discord.Embed(
            title="<:UploadLOGO:1391530531916742726> Upload Image",
            description="Please send an image file in this channel.\n\n**Only you can upload the image for security reasons.**",
            color=discord.Color.blue()
        )

        # Add bot branding to waiting image embed
        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Upload Image", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_image_format_embed(self):
        embed = discord.Embed(
            title="<:ImageLOGO:1391530555517960263> Image Format Selection",
            description="How would you like the image to appear in your embed?",
            color=discord.Color.gold()
        )

        # Add bot branding to image format embed
        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Image Format", icon_url=self.bot.user.display_avatar.url)

        return embed

    def get_publish_embed(self):
        embed = discord.Embed(
            title="<:SendLOGO:1391511616138379294> Publish Embed",
            description="Please choose the embed you want to post and the channel where you want to publish it.",
            color=discord.Color.green()
        )

        status = ""
        if self.selected_embed_index is not None:
            selected_embed = self.embeds_data["created"][self.selected_embed_index]
            embed_title = selected_embed.get("title", "Untitled")[:30]
            status += f"<:SucessLOGO:1391511887065121020> Selected Embed: {embed_title}\n"
        else:
            status += "<:ErrorLOGO:1391511903196549201> Embed: Not selected\n"

        if self.selected_channel:
            status += f"<:SucessLOGO:1391511887065121020> Selected Channel: #{self.selected_channel.name}\n"
        else:
            status += "<:ErrorLOGO:1391511903196549201> Channel: Not selected\n"

        if status:
            embed.add_field(
                name="Current Selection",
                value=status,
                inline=False
            )

        # Add bot branding to publish embed
        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Publish Embed", icon_url=self.bot.user.display_avatar.url)

        return embed

    def is_valid_url(self, url):
        """Check if URL is valid and accessible by Discord"""
        if not url:
            return False
        # Allow both http/https URLs and local file paths (which will be converted to URLs)
        return url.startswith(('http://', 'https://')) or url.startswith('images/')

    def update_buttons(self):
        self.clear_items()

        if self.waiting_for_image:
            # Back button only when waiting for image
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
            # Image settings buttons - First row
            image_url_button = discord.ui.Button(
                label="Image URL",
                style=discord.ButtonStyle.primary,
                emoji="<:URLLOGO:1391530519560454185>",
                row=0
            )

            async def image_url_callback(interaction):
                modal = ImageURLModal(self.current_embed, self)
                await interaction.response.send_modal(modal)

            image_url_button.callback = image_url_callback

            upload_image_button = discord.ui.Button(
                label="Upload Image",
                style=discord.ButtonStyle.secondary,
                emoji="<:UploadLOGO:1391530531916742726>",
                row=0
            )

            async def upload_image_callback(interaction):
                self.waiting_for_image = True
                embed = self.get_waiting_image_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            upload_image_button.callback = upload_image_callback

            # Clear image button
            clear_button = discord.ui.Button(
                label="Clear Images",
                style=discord.ButtonStyle.danger,
                emoji="<:DeleteLOGO:1391511582261116938>",
                row=0
            )

            async def clear_callback(interaction):
                self.current_embed.image_url = ""
                self.current_embed.thumbnail_url = ""
                embed = self.get_image_settings_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

                # Auto-save embed after clearing images
                self.save_current_embed()

            clear_button.callback = clear_callback

            # Back button - Second row
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

        elif self.delete_mode:
            if self.embeds_data["created"]:
                # Add select menu for embed deletion
                select = EmbedDeleteSelect(self.embeds_data["created"])
                self.add_item(select)

            # Back button
            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )

            async def back_callback(interaction):
                self.delete_mode = False
                embed = self.get_main_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            back_button.callback = back_callback
            self.add_item(back_button)

        elif self.publish_mode:
            if self.embeds_data["created"]:
                # Add select menu for embed selection with current selection
                embed_select = EmbedPublishSelect(self.embeds_data["created"], self.selected_embed_index)
                self.add_item(embed_select)

                # Add select menu for channel selection with current selection
                channel_select = ChannelPublishSelect(getattr(self, 'guild', None), self.selected_channel)
                self.add_item(channel_select)

                # Add publish button if both selections are made
                if self.selected_embed_index is not None and self.selected_channel:
                    publish_button = discord.ui.Button(
                        label="Publish",
                        style=discord.ButtonStyle.success,
                        emoji="<:SendLOGO:1391511616138379294>"
                    )

                    async def publish_final_callback(interaction):
                        selected_embed = self.embeds_data["created"][self.selected_embed_index]

                        # Get embed content
                        title = selected_embed.get("title", "").strip()
                        description = selected_embed.get("description", "").strip()
                        footer = selected_embed.get("footer", "").strip()
                        image_url = selected_embed.get("image_url", "").strip()
                        thumbnail_url = selected_embed.get("thumbnail_url", "").strip()
                        message_content = selected_embed.get("message_content", "").strip()

                        # Check if embed has any content at all
                        has_content = any([title, description, footer, image_url, thumbnail_url, message_content])

                        if not has_content:
                            error_embed = discord.Embed(
                                title="<:ErrorLOGO:1391511903196549201> Empty Embed",
                                description="The embed must have at least some content (title, description, footer, image, thumbnail, or message content).",
                                color=discord.Color.red()
                            )
                            await interaction.response.send_message(embed=error_embed, ephemeral=True)
                            return

                        # Create the embed - Discord needs at least title OR description, use invisible character if both empty
                        if not title and not description:
                            description = "​"  # Use invisible character as fallback

                        publish_embed = discord.Embed(
                            title=title if title else None,
                            description=description if description else None,
                            color=discord.Color(selected_embed.get("color", discord.Color.blurple().value))
                        )

                        # Pas de thumbnail par défaut

                        # Footer seulement si spécifié
                        if selected_embed.get("footer"):
                            publish_embed.set_footer(text=selected_embed.get("footer"))

                        # Handle bot_standard decoration for publish
                        if selected_embed.get("decoration_preset") == "bot_standard":
                            bot_name = get_bot_name(self.bot)
                            #Retire l'author quand j'active Bot standart
                            #publish_embed.set_author(name=bot_name, icon_url=self.bot.user.display_avatar.url)
                            footer_text = selected_embed.get("footer", "")
                            if footer_text:
                                publish_embed.set_footer(text=f"{bot_name} | {footer_text}", icon_url=self.bot.user.display_avatar.url)
                            else:
                                publish_embed.set_footer(text=bot_name, icon_url=self.bot.user.display_avatar.url)
                            publish_embed.set_thumbnail(url=self.bot.user.display_avatar.url)
                        else:
                            if selected_embed.get("author_enabled") and selected_embed.get("author_name"):
                                author_icon = selected_embed.get("author_icon", "")
                                publish_embed.set_author(
                                    name=selected_embed.get("author_name"),
                                    icon_url=author_icon if author_icon.startswith(('http://', 'https://')) else None
                                )

                        # Handle images - GitHub URLs work directly
                        if selected_embed.get("image_url"):
                            image_url = selected_embed.get("image_url")
                            if image_url.startswith(('http://', 'https://')):
                                publish_embed.set_image(url=image_url)

                        # Handle thumbnail - but not if bot_standard is enabled (it overrides)
                        if selected_embed.get("thumbnail_url") and selected_embed.get("decoration_preset") != "bot_standard":
                            thumbnail_url = selected_embed.get("thumbnail_url")
                            if thumbnail_url.startswith(('http://', 'https://')):
                                publish_embed.set_thumbnail(url=thumbnail_url)

                        try:
                            # Send the embed to the selected channel
                            message_content = selected_embed.get("message_content", "")
                            await self.selected_channel.send(
                                content=message_content if message_content else None,
                                embed=publish_embed
                            )

                            # Success message in English
                            success_embed = discord.Embed(
                                title="<:SucessLOGO:1391511887065121020> Successfully Published",
                                description=f"Your embed has been published successfully in {self.selected_channel.mention}!",
                                color=discord.Color.green()
                            )

                            # Go back to main menu after successful publication
                            self.publish_mode = False
                            self.selected_embed_index = None
                            self.selected_channel = None
                            embed = self.get_main_embed()
                            self.update_buttons()

                            # Edit the original message first
                            await interaction.response.edit_message(embed=embed, view=self)

                            # Then send the success message as ephemeral
                            await interaction.followup.send(embed=success_embed, ephemeral=True)

                        except discord.Forbidden:
                            error_embed = discord.Embed(
                                title="<:ErrorLOGO:1391511903196549201> Permission Error",
                                description="I don't have permission to send messages in that channel.",
                                color=discord.Color.red()
                            )
                            await interaction.response.send_message(embed=error_embed, ephemeral=True)
                        except Exception as e:
                            error_embed = discord.Embed(
                                title="<:ErrorLOGO:1391511903196549201> Error",
                                description=f"An error occurred while publishing: {str(e)}",
                                color=discord.Color.red()
                            )
                            await interaction.response.send_message(embed=error_embed, ephemeral=True)

                    publish_button.callback = publish_final_callback
                    self.add_item(publish_button)

            # Back button
            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )

            async def back_callback(interaction):
                self.publish_mode = False
                self.selected_embed_index = None
                self.selected_channel = None
                embed = self.get_main_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            back_button.callback = back_callback
            self.add_item(back_button)

        elif hasattr(self, 'edit_select_mode') and self.edit_select_mode:
            if self.embeds_data["created"]:
                # Add select menu for embed editing
                select = EmbedEditSelect(self.embeds_data["created"])
                self.add_item(select)

            # Back button
            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )

            async def back_callback(interaction):
                self.edit_select_mode = False
                embed = self.get_main_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            back_button.callback = back_callback
            self.add_item(back_button)

        elif not self.creating_mode:
            # Collect all buttons to organize them properly
            buttons = []

            # Create button (always present)
            create_button = discord.ui.Button(
                label="Create",
                style=discord.ButtonStyle.success,
                emoji="<:CreateLOGO:1391511510475472899>",
                row=0
            )

            async def create_callback(interaction):
                self.creating_mode = True
                self.edit_mode = False
                self.editing_index = None
                self.current_embed = EmbedData()
                # Author disabled by default
                self.current_embed.author_enabled = False
                embed = self.get_create_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            create_button.callback = create_callback
            buttons.append(create_button)

            # Add edit button if there are embeds to edit
            if self.embeds_data["created"]:
                edit_button = discord.ui.Button(
                    label="Edit",
                    style=discord.ButtonStyle.primary,
                    emoji="<:EditLOGO:1391511560500940942>",
                    row=0
                )

                async def edit_callback(interaction):
                    self.edit_select_mode = True
                    embed = self.get_edit_embed()
                    self.update_buttons()
                    await interaction.response.edit_message(embed=embed, view=self)

                edit_button.callback = edit_callback
                buttons.append(edit_button)

            # Add delete button if there are embeds to delete
            if self.embeds_data["created"]:
                delete_button = discord.ui.Button(
                    label="Delete",
                    style=discord.ButtonStyle.danger,
                    emoji="<:DeleteLOGO:1391511582261116938>",
                    row=0
                )

                async def delete_callback(interaction):
                    self.delete_mode = True
                    embed = self.get_delete_embed()
                    self.update_buttons()
                    await interaction.response.edit_message(embed=embed, view=self)

                delete_button.callback = delete_callback
                buttons.append(delete_button)

            # Add publish button if there are embeds to publish
            if self.embeds_data["created"]:
                publish_button = discord.ui.Button(
                    label="Publish",
                    style=discord.ButtonStyle.secondary,
                    emoji="<:SendLOGO:1391511616138379294>",
                    row=0
                )

                async def publish_callback(interaction):
                    self.publish_mode = True
                    self.selected_embed_index = None
                    self.selected_channel = None
                    embed = self.get_publish_embed()
                    self.update_buttons()
                    await interaction.response.edit_message(embed=embed, view=self)

                publish_button.callback = publish_callback
                buttons.append(publish_button)

            # Organize buttons in rows of 3
            for i, button in enumerate(buttons):
                button.row = i // 3
                self.add_item(button)
        else:
            # Collect all buttons for creation mode
            buttons = []

            basic_button = discord.ui.Button(
                label="Configure",
                style=discord.ButtonStyle.primary,
                emoji="<:SettingLOGO:1391530472487653429>"
            )

            async def basic_callback(interaction):
                modal = BasicParametersModal(self.current_embed)
                await interaction.response.send_modal(modal)

            basic_button.callback = basic_callback
            buttons.append(basic_button)

            author_button = discord.ui.Button(
                label="Author Settings",
                style=discord.ButtonStyle.secondary,
                emoji="<:ParticipantsLOGO:1391530606977880145>"
            )

            async def author_callback(interaction):
                view = AuthorSettingsView(self.current_embed, interaction.guild, self)
                embed = discord.Embed(
                    title="<:ParticipantsLOGO:1391530606977880145> Author Settings",
                    description="Configure the embed author settings",
                    color=discord.Color.orange()
                )

                # Show current author status
                if self.current_embed.author_enabled:
                    if self.current_embed.author_name:
                        embed.add_field(
                            name="Current Author",
                            value=f"**{self.current_embed.author_name}** (Enabled)",
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

        # Add bot branding to create embed
                bot_name = get_bot_name(self.bot)
                embed.set_thumbnail(url=self.bot.user.display_avatar.url)
                embed.set_footer(text=f"{bot_name} | Author Settings", icon_url=self.bot.user.display_avatar.url)

                await interaction.response.edit_message(embed=embed, view=view)

            author_button.callback = author_callback
            buttons.append(author_button)

            # Image settings button
            image_button = discord.ui.Button(
                label="Image Settings",
                style=discord.ButtonStyle.secondary,
                emoji="<:ImageLOGO:1391530555517960263>"
            )

            async def image_callback(interaction):
                self.image_mode = True
                embed = self.get_image_settings_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            image_button.callback = image_callback
            buttons.append(image_button)

            # Decoration settings button
            decoration_button = discord.ui.Button(
                label="Decoration",
                style=discord.ButtonStyle.secondary,
                emoji="<:DecorationLOGO:1391530410655219722>"
            )

            async def decoration_callback(interaction):
                view = DecorationSettingsView(self.current_embed, self)
                view.update_button_style()  # Update button style based on current state
                embed = view.get_embed()
                await interaction.response.edit_message(embed=embed, view=view)

            decoration_button.callback = decoration_callback
            buttons.append(decoration_button)

            preview_button = discord.ui.Button(
                label="Preview",
                style=discord.ButtonStyle.secondary,
                emoji="<:ViewLGOO:1391530502812602478>"
            )

            async def preview_callback(interaction):
                preview_embed = discord.Embed(
                    title=self.current_embed.title or "Preview Embed",
                    description=self.current_embed.description or "This is a preview of your embed",
                    color=self.current_embed.color
                )

                # Pas de thumbnail par défaut

                # Determine current action for footer
                action = "Creating Embed" if not self.edit_mode else "Editing Embed"

                # Footer seulement si spécifié
                if self.current_embed.footer:
                    preview_embed.set_footer(text=self.current_embed.footer)

                if self.current_embed.author_enabled and self.current_embed.author_name:
                    preview_embed.set_author(
                        name=self.current_embed.author_name,
                        icon_url=self.current_embed.author_icon if self.current_embed.author_icon.startswith(('http://', 'https://')) else None
                    )

                # Handle image URL - GitHub URLs work directly
                if self.current_embed.image_url:
                    if self.current_embed.image_url.startswith(('http://', 'https://')):
                        preview_embed.set_image(url=self.current_embed.image_url)

                # Handle thumbnail URL
                if self.current_embed.thumbnail_url and not self.current_embed.decoration_preset == "bot_standard":
                    if self.current_embed.thumbnail_url.startswith(('http://', 'https://')):
                        preview_embed.set_thumbnail(url=self.current_embed.thumbnail_url)

                if self.current_embed.decoration_preset == "bot_standard":
                    bot_name = get_bot_name(self.bot)
                    # Retire l'author quand j'active Bot standart
                    footer_text = self.current_embed.footer if self.current_embed.footer else ""
                    if footer_text:
                        preview_embed.set_footer(text=f"{bot_name} | {footer_text}", icon_url=self.bot.user.display_avatar.url)
                    else:
                        preview_embed.set_footer(text=bot_name, icon_url=self.bot.user.display_avatar.url)
                    preview_embed.set_thumbnail(url=self.bot.user.display_avatar.url)

                # Send preview as ephemeral message
                await interaction.response.send_message(
                    content=self.current_embed.message_content if self.current_embed.message_content else None,
                    embed=preview_embed,
                    ephemeral=True
                )

            preview_button.callback = preview_callback
            buttons.append(preview_button)

            back_button = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="<:BackLOGO:1391511633431494666>"
            )

            async def back_callback(interaction):
                # Save the current embed before going back
                self.save_current_embed()
                self.creating_mode = False
                self.edit_mode = False
                self.editing_index = None
                embed = self.get_main_embed()
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

            back_button.callback = back_callback
            buttons.append(back_button)

            # Organize buttons in rows of 3
            for i, button in enumerate(buttons):
                button.row = i // 3
                self.add_item(button)

class ImageFormatView(discord.ui.View):
    def __init__(self, embed_data, image_url, parent_view):
        super().__init__(timeout=300)
        self.embed_data = embed_data
        self.image_url = image_url
        self.parent_view = parent_view

    @discord.ui.button(label="Classic Image", style=discord.ButtonStyle.primary, emoji="<:ImageLOGO:1391530555517960263>")
    async def classic_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Save the image data (keep the local file path)
        self.embed_data.image_url = self.image_url
        self.embed_data.thumbnail_url = ""  # Clear thumbnail if setting classic image

        # Go back to image settings
        self.parent_view.image_mode = True
        embed = self.parent_view.get_image_settings_embed()
        self.parent_view.update_buttons()

        # Auto-save embed after image changes
        if self.parent_view:
            self.parent_view.save_current_embed()

        await interaction.response.edit_message(embed=embed, view=self.parent_view)

    @discord.ui.button(label="Thumbnail Image", style=discord.ButtonStyle.secondary, emoji="🔍")
    async def thumbnail_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Save the image data (keep the local file path)
        self.embed_data.thumbnail_url = self.image_url
        self.embed_data.image_url = ""  # Clear classic image if setting thumbnail

        # Go back to image settings
        self.parent_view.image_mode = True
        embed = self.parent_view.get_image_settings_embed()
        self.parent_view.update_buttons()

        # Auto-save embed after image changes
        if self.parent_view:
            self.parent_view.save_current_embed()

        await interaction.response.edit_message(embed=embed, view=self.parent_view)

class ImageURLModal(discord.ui.Modal):
    def __init__(self, embed_data, parent_view):
        super().__init__(title='<:URLLOGO:1391530519560454185> Set Image URL')
        self.embed_data = embed_data
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

        # Show format selection
        view = ImageFormatView(self.embed_data, image_url, self.parent_view)
        embed = self.parent_view.get_image_format_embed()

        await interaction.response.edit_message(embed=embed, view=view)

class EmbedEditSelect(discord.ui.Select):
    def __init__(self, embeds_list):
        self.embeds_list = embeds_list
        options = []

        for i, embed_data in enumerate(embeds_list[:25]):  # Discord limit of 25 options
            title = embed_data.get("title", "Untitled")
            if not title.strip():
                title = "Untitled"
            if len(title) > 50:
                title = title[:47] + "..."

            description = embed_data.get("description", "No description")
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
            placeholder="Select an embed to edit...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        selected_index = int(self.values[0])
        selected_embed = self.embeds_list[selected_index]

        # Load the selected embed data into current_embed
        parent_view = self.view
        parent_view.current_embed = EmbedData()
        # Preserve the original ID or generate one if missing
        parent_view.current_embed.id = selected_embed.get("id", parent_view.current_embed.generate_unique_id())
        parent_view.current_embed.message_content = selected_embed.get("message_content", "")
        parent_view.current_embed.title = selected_embed.get("title", "")
        parent_view.current_embed.description = selected_embed.get("description", "")
        parent_view.current_embed.color = discord.Color(selected_embed.get("color", discord.Color.blurple().value))
        parent_view.current_embed.footer = selected_embed.get("footer", "")
        parent_view.current_embed.author_enabled = selected_embed.get("author_enabled", False)
        parent_view.current_embed.author_name = selected_embed.get("author_name", "")
        parent_view.current_embed.author_icon = selected_embed.get("author_icon", "")
        parent_view.current_embed.image_url = selected_embed.get("image_url", "")
        parent_view.current_embed.thumbnail_url = selected_embed.get("thumbnail_url", "")
        parent_view.current_embed.decoration_preset = selected_embed.get("decoration_preset", "none")

        # Store the index for updating later
        parent_view.editing_index = selected_index

        # Switch to edit mode properly
        parent_view.creating_mode = True
        parent_view.edit_mode = True
        parent_view.edit_select_mode = False

        embed = parent_view.get_create_embed()
        parent_view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=parent_view)

class EmbedPublishSelect(discord.ui.Select):
    def __init__(self, embeds_list, selected_index=None):
        self.embed_list = embeds_list
        options = []

        for i, embed_data in enumerate(embeds_list[:25]):  # Discord limit of 25 options
            title = embed_data.get("title", "Untitled")
            if not title.strip():
                title = "Untitled"
            if len(title) > 50:
                title = title[:47] + "..."

            description = embed_data.get("description", "No description")
            if not description.strip():
                description = "No description"
            if len(description) > 50:
                description = description[:47] + "..."

            option = discord.SelectOption(
                label=title,
                description=description,
                value=str(i)
            )

            # Mark as default if this is the selected index
            if selected_index is not None and i == selected_index:
                option.default = True

            options.append(option)

        super().__init__(
            placeholder="Select an embed to publish...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        selected_index = int(self.values[0])
        parent_view = self.view
        parent_view.selected_embed_index = selected_index

        embed = parent_view.get_publish_embed()
        parent_view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=parent_view)

class ChannelPublishSelect(discord.ui.Select):
    def __init__(self, guild, selected_channel=None):
        self.guild = guild
        options = []

        if guild:
            # Filter channels where @everyone can view
            text_channels = []
            everyone_role = guild.default_role
            for ch in guild.channels:
                if isinstance(ch, discord.TextChannel):
                    # Check if @everyone can view the channel
                    permissions = ch.permissions_for(everyone_role)
                    if permissions.view_channel:
                        text_channels.append(ch)

            for channel in text_channels[:25]:  # Discord limit of 25 options
                option = discord.SelectOption(
                    label=f"#{channel.name}",
                    description=f"Category: {channel.category.name if channel.category else 'No category'}",
                    value=str(channel.id)
                )

                # Mark as default if this is the selected channel
                if selected_channel and channel.id == selected_channel.id:
                    option.default = True

                options.append(option)

        if not options:
            options.append(discord.SelectOption(
                label="No channels available",
                description="No text channels found",
                value="none"
            ))

        super().__init__(
            placeholder="Select a channel to publish to...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            return

        channel_id = int(self.values[0])
        channel = interaction.guild.get_channel(channel_id)

        parent_view = self.view
        parent_view.selected_channel = channel

        embed = parent_view.get_publish_embed()
        parent_view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=parent_view)

class EmbedDeleteSelect(discord.ui.Select):
    def __init__(self, embeds_list):
        self.embeds_list = embeds_list
        options = []

        for i, embed_data in enumerate(embeds_list[:25]):  # Discord limit of 25 options
            title = embed_data.get("title", "Untitled")
            if not title.strip():
                title = "Untitled"
            if len(title) > 50:
                title = title[:47] + "..."

            description = embed_data.get("description", "No description")
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
            placeholder="Select an embed to delete...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        selected_index = int(self.values[0])
        selected_embed = self.embeds_list[selected_index]

        view = DeleteConfirmView(selected_index, selected_embed, self.view)

        embed = discord.Embed(
            title="<:WarningLOGO:1391533273267572890> Confirm Deletion",
            description=f"Are you sure you want to delete the embed **'{selected_embed.get('title', 'Untitled')}'**?\n\n**This action is irreversible!**",
            color=discord.Color.red()
        )

        # Add bot branding to delete embed
        parent_view = self.view
        bot_name = get_bot_name(parent_view.bot)
        embed.set_thumbnail(url=parent_view.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Delete Embed", icon_url=parent_view.bot.user.display_avatar.url)

        await interaction.response.edit_message(embed=embed, view=view)

class DeleteConfirmView(discord.ui.View):
    def __init__(self, embed_index, embed_data, parent_view):
        super().__init__(timeout=300)
        self.embed_index = embed_index
        self.embed_data = embed_data
        self.parent_view = parent_view

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="<:DeleteLOGO:1391511582261116938>")
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Remove the embed from the list
        self.parent_view.embeds_data["created"].pop(self.embed_index)
        self.parent_view.save_embeds()

        # Go back to main view
        self.parent_view.delete_mode = False
        embed = self.parent_view.get_main_embed()
        self.parent_view.update_buttons()

        await interaction.response.edit_message(embed=embed, view=self.parent_view)

        # Send ephemeral confirmation
        confirm_embed = discord.Embed(
            title="<:SucessLOGO:1391511887065121020> Embed Deleted",
            description="The embed has been successfully deleted.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=confirm_embed, ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray, emoji="<:CloseLOGO:1391531593524318271>")
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Go back to delete selection
        embed = self.parent_view.get_delete_embed()
        self.parent_view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

class BasicParametersModal(discord.ui.Modal):
    def __init__(self, embed_data):
        super().__init__(title='Basic Embed Parameters')
        self.embed_data = embed_data

        self.message_content = discord.ui.TextInput(
            label='Message Content',
            placeholder='Text that appears above the embed...',
            required=False,
            max_length=2000,
            style=discord.TextStyle.paragraph,
            default=embed_data.message_content
        )

        self.embed_title = discord.ui.TextInput(
            label='Embed Title',
            placeholder='Enter the embed title...',
            required=False,
            max_length=256,
            default=embed_data.title
        )

        self.description = discord.ui.TextInput(
            label='Embed Description',
            placeholder='Enter the embed description...',
            required=False,
            max_length=4000,
            style=discord.TextStyle.paragraph,
            default=embed_data.description
        )

        self.color = discord.ui.TextInput(
            label='Embed Color',
            placeholder='Hexadecimal Color',
            required=False,
            max_length=7
        )

        self.footer = discord.ui.TextInput(
            label='Footer Text',
            placeholder='Footer text...',
            required=False,
            max_length=2048,
            default=embed_data.footer
        )

        self.add_item(self.message_content)
        self.add_item(self.embed_title)
        self.add_item(self.description)
        self.add_item(self.color)
        self.add_item(self.footer)

    async def on_submit(self, interaction: discord.Interaction):
        # Check if at least one field is filled
        if not (self.message_content.value.strip() or 
                self.embed_title.value.strip() or 
                self.description.value.strip() or 
                self.footer.value.strip()):
            error_embed = discord.Embed(
                title="<:ErrorLOGO:1391511903196549201> Validation Error",
                description="At least one field (Message Content, Title, Description, or Footer) must be filled.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return

        self.embed_data.message_content = self.message_content.value
        self.embed_data.title = self.embed_title.value
        self.embed_data.description = self.description.value
        self.embed_data.footer = self.footer.value

        if self.color.value:
            try:
                if self.color.value.startswith('#'):
                    self.embed_data.color = discord.Color(int(self.color.value[1:], 16))
                else:
                    self.embed_data.color = discord.Color(int(self.color.value, 16))
            except ValueError:
                self.embed_data.color = discord.Color.blurple()

        # Auto-save embed after configuration changes
        if hasattr(interaction, 'client') and hasattr(interaction.client, 'get_cog'):
            embed_cog = interaction.client.get_cog('EmbedCommand')
            if embed_cog:
                for user_id, manager in embed_cog.active_managers.items():
                    if manager.current_embed == self.embed_data:
                        manager.save_current_embed()
                        break

        await interaction.response.defer()

class AuthorSettingsView(discord.ui.View):
    def __init__(self, embed_data, guild, parent_view=None):
        super().__init__(timeout=300)
        self.embed_data = embed_data
        self.guild = guild
        self.parent_view = parent_view

        self.toggle_button = discord.ui.Button(
            label="ON" if self.embed_data.author_enabled else "OFF",
            style=discord.ButtonStyle.success if self.embed_data.author_enabled else discord.ButtonStyle.danger,
            emoji="<:ONLOGO:1391530620366094440>" if self.embed_data.author_enabled else "<:OFFLOGO:1391535388065271859>"
        )
        self.toggle_button.callback = self.toggle_author

        self.add_item(self.toggle_button)

    async def toggle_author(self, interaction: discord.Interaction):
        self.embed_data.author_enabled = not self.embed_data.author_enabled

        if self.embed_data.author_enabled and not self.embed_data.author_name:
            self.embed_data.author_name = interaction.user.display_name
            self.embed_data.author_icon = interaction.user.display_avatar.url

        # Update button appearance
        self.toggle_button.label = "ON" if self.embed_data.author_enabled else "OFF"
        self.toggle_button.style = discord.ButtonStyle.success if self.embed_data.author_enabled else discord.ButtonStyle.danger
        self.toggle_button.emoji = "<:ONLOGO:1391530620366094440>" if self.embed_data.author_enabled else "<:OFFLOGO:1391535388065271859>"

        embed = discord.Embed(
            title="<:ParticipantsLOGO:1391530606977880145> Author Settings",
            description="Configure the embed author settings",
            color=discord.Color.orange()
        )

        if self.embed_data.author_enabled:
            embed.add_field(
                name="Current Author",
                value=f"**{self.embed_data.author_name}** (Enabled)",
                inline=False
            )
        else:
            embed.add_field(
                name="Current Author",
                value="Disabled",
                inline=False
            )

        # Add bot branding to create embed
        if self.parent_view:
            bot_name = get_bot_name(self.parent_view.bot)
            embed.set_thumbnail(url=self.parent_view.bot.user.display_avatar.url)
            embed.set_footer(text=f"{bot_name} | Author Settings", icon_url=self.parent_view.bot.user.display_avatar.url)

        await interaction.response.edit_message(embed=embed, view=self)

        # Auto-save embed after author changes
        if self.parent_view and hasattr(self.parent_view, 'save_current_embed'):
            self.parent_view.save_current_embed()

    @discord.ui.button(label="Set Author", style=discord.ButtonStyle.secondary, emoji="<:EditLOGO:1391511560500940942>")
    async def set_custom_author(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomAuthorModal(self.embed_data, self.guild, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1391511633431494666>")
    async def back_to_create(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.parent_view:
            embed = self.parent_view.get_create_embed()
            self.parent_view.update_buttons()
            await interaction.response.edit_message(embed=embed, view=self.parent_view)



class DecorationSettingsView(discord.ui.View):
    def __init__(self, embed_data, parent_view):
        super().__init__(timeout=300)
        self.embed_data = embed_data
        self.parent_view = parent_view

    def get_embed(self):
        embed = discord.Embed(
            title="<:DecorationLOGO:1391530410655219722> Decoration Settings",
            description="Toggle Bot Standard decoration for your embed:",
            color=discord.Color.purple()
        )

        # Show current preset in a more readable format
        preset_display = "Bot Standard" if self.embed_data.decoration_preset == "bot_standard" else "None"
        embed.add_field(name="Current Preset", value=preset_display)

        # Add bot branding to create embed
        bot_name = get_bot_name(self.parent_view.bot)
        embed.set_thumbnail(url=self.parent_view.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Decoration Settings", icon_url=self.parent_view.bot.user.display_avatar.url)

        return embed

    @discord.ui.button(label="Bot Standard", style=discord.ButtonStyle.secondary, emoji="🤖")
    async def toggle_bot_standard(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Toggle between bot_standard and none
        if self.embed_data.decoration_preset == "bot_standard":
            self.embed_data.decoration_preset = "none"
            button.style = discord.ButtonStyle.danger
            button.emoji = "<:OFFLOGO:1391535388065271859>"
            status_msg = f"{get_bot_name(self.parent_view.bot)} decoration disabled"
        else:
            self.embed_data.decoration_preset = "bot_standard"
            button.style = discord.ButtonStyle.success
            button.emoji = "<:ONLOGO:1391530620366094440>"
            status_msg = f"{get_bot_name(self.parent_view.bot)} decoration enabled"

        self.parent_view.save_current_embed()
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="<:BackLOGO:1391511633431494666>")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.parent_view.get_create_embed()
        self.parent_view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

    def update_button_style(self):
        """Update button style based on current preset"""
        bot_button = self.children[0]  # First button is the Bot Standard button
        if self.embed_data.decoration_preset == "bot_standard":
            bot_button.style = discord.ButtonStyle.success
            bot_button.emoji = "<:ONLOGO:1391530620366094440>"
        else:
            bot_button.style = discord.ButtonStyle.danger
            bot_button.emoji = "<:OFFLOGO:1391535388065271859>"

class CustomAuthorModal(discord.ui.Modal):
    def __init__(self, embed_data, guild, parent_view):
        super().__init__(title='<:ParticipantsLOGO:1391530606977880145> Set Custom Author')
        self.embed_data = embed_data
        self.guild = guild
        self.parent_view = parent_view

        self.user_input = discord.ui.TextInput(
            label='User ID or Username',
            placeholder='Enter user ID (e.g., 123456789) or username',
            required=True,
            max_length=100
        )

        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_input = self.user_input.value.strip()
        user = None

        # Try to find user by ID first
        if user_input.isdigit():
            try:
                user = self.guild.get_member(int(user_input))
                if not user:
                    user = await self.guild.fetch_member(int(user_input))
            except:
                pass

        # If not found by ID, try by username
        if not user:
            for member in self.guild.members:
                if member.name.lower() == user_input.lower() or member.display_name.lower() == user_input.lower():
                    user = member
                    break

        if user:
            self.embed_data.author_name = user.display_name
            self.embed_data.author_icon = user.display_avatar.url
            self.embed_data.author_enabled = True

            # Update the author settings view
            embed = discord.Embed(
                title="<:ParticipantsLOGO:1391530606977880145> Author Settings",
                description="Configure the embed author settings",
                color=discord.Color.orange()
            )

            embed.add_field(
                name="Current Author",
                value=f"**{self.embed_data.author_name}** (Enabled)",
                inline=False
            )

        # Add bot branding to create embed
            bot_name = get_bot_name(self.parent_view.bot)
            embed.set_thumbnail(url=self.parent_view.bot.user.display_avatar.url)
            embed.set_footer(text=f"{bot_name} | Author Settings", icon_url=self.parent_view.bot.user.display_avatar.url)

            # Update toggle button appearance
            self.parent_view.toggle_button.label = "ON" if self.embed_data.author_enabled else "OFF"
            self.parent_view.toggle_button.style = discord.ButtonStyle.success if self.embed_data.author_enabled else discord.ButtonStyle.danger
            self.parent_view.toggle_button.emoji = "<:ONLOGO:1391530620366094440>" if self.embed_data.author_enabled else "<:OFFLOGO:1391535388065271859>"

            await interaction.response.edit_message(embed=embed, view=self.parent_view)

            # Auto-save embed after author changes
            if self.parent_view and hasattr(self.parent_view, 'parent_view') and hasattr(self.parent_view.parent_view, 'save_current_embed'):
                self.parent_view.parent_view.save_current_embed()
        else:
            error_embed = discord.Embed(
                title="<:SucessLOGO:1391511887065121020> User Not Found",
                description="Could not find a user with that ID or username in this server.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

class EmbedCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_managers = {}  # Track active embed managers

    async def download_image(self, image_url):
        """Download image from URL, save locally, sync to GitHub, then delete locally"""
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
                        with open(file_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                f.write(chunk)

                        # Synchronize with GitHub
                        from github_sync import GitHubSync
                        github_sync = GitHubSync()
                        sync_success = await github_sync.sync_image_to_pictures_repo(file_path)

                        if sync_success:
                            # Delete local file after successful sync
                            try:
                                os.remove(file_path)
                                print(f"<:DeleteLOGO:1391511582261116938> Fichier local supprimé: {file_path}")
                            except Exception as e:
                                print(f"<:WarningLOGO:1391533273267572890> Erreur lors de la suppression locale: {e}")

                            # Return GitHub raw URL from public pictures repo
                            filename = os.path.basename(file_path)
                            github_url = f"https://raw.githubusercontent.com/TheBlueEL/pictures/main/{filename}"
                            return github_url
                        else:
                            print("<:SucessLOGO:1391511887065121020> Échec de la synchronisation, fichier local conservé")
                            return None
            return None
        except Exception as e:
            print(f"Error downloading image: {e}")
            return None

    

    @commands.Cog.listener()
    async def on_message(self, message):
        # Check if message is from someone with an active embed manager waiting for images
        if message.author.bot:
            return

        user_id = message.author.id
        if user_id in self.active_managers:
            manager = self.active_managers[user_id]
            if manager.waiting_for_image and message.attachments:
                # Check if the attachment is an image with allowed extensions
                attachment = message.attachments[0]
                allowed_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg']
                if any(attachment.filename.lower().endswith(ext) for ext in allowed_extensions):
                    # Download the image locally first
                    local_file = await self.download_image(attachment.url)

                    # Only delete the message if the image was successfully downloaded
                    if local_file:
                        try:
                            await message.delete()
                        except:
                            pass

                        # Create embed showing the image for confirmation
                        embed = discord.Embed(
                            title="<:ImageLOGO:1391530555517960263> Image Format Selection",
                            description="<:SucessLOGO:1391511887065121020> **Image successfully uploaded!**\n\nHow would you like the image to appear in your embed?",
                            color=discord.Color.green()
                        )

                        # Show the image in the embed using GitHub URL
                        embed.set_image(url=local_file)

                        # Store the GitHub URL for later use
                        view = ImageFormatView(manager.current_embed, local_file, manager)
                        manager.waiting_for_image = False

                        # Update the manager view showing the image
                        try:
                            # Find the original interaction message and edit it
                            channel = message.channel
                            async for msg in channel.history(limit=50):
                                if msg.author == self.bot.user and msg.embeds:
                                    if "Upload Image" in msg.embeds[0].title:
                                        await msg.edit(embed=embed, view=view)
                                        break
                        except Exception as e:
                            print(f"Error updating message: {e}")
                            # Fallback: send new message
                            try:
                                await channel.send(embed=embed, view=view)
                            except:
                                pass
                else:
                    # File is not a valid image format
                    try:
                        await message.delete()
                    except:
                        pass

                    error_embed = discord.Embed(
                        title="<:SucessLOGO:1391511887065121020> Invalid File Type",
                        description="Please upload only image files with these extensions:\n`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp`, `.svg`",
                        color=discord.Color.red()
                    )

                    try:
                        channel = message.channel
                        await channel.send(embed=error_embed, delete_after=5)
                    except:
                        pass

    @app_commands.command(name="embed", description="Create and manage custom embeds")
    async def embed_command(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            embed = discord.Embed(
                title="<:SucessLOGO:1391511887065121020> Permission Denied",
                description="You need 'Manage Messages' permission to use this command.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        view = EmbedManagerView(self.bot, interaction.user.id)
        view.guild = interaction.guild  # Store guild reference
        embed = view.get_main_embed()
        view.update_buttons()

        # Store the active manager
        self.active_managers[interaction.user.id] = view

        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

async def setup(bot):
    await bot.add_cog(EmbedCommand(bot))
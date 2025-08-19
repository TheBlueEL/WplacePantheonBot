
import discord
from discord.ext import commands
from discord import app_commands
import json
import random
from datetime import datetime
import math

def get_bot_name(bot):
    return getattr(bot, 'user', {}).display_name or "Bot"

class NotationData:
    def __init__(self):
        self.artwork_id = None
        self.title = ""
        self.description = ""
        self.author_name = "Anonymous"
        self.image_url = ""
        self.location = ""
        self.votes = []  # List of {user_id: int, rating: int, timestamp: str}
        self.average_rating = 0.0
        self.last_shown = None
        self.times_shown = 0

class VotingView(discord.ui.View):
    def __init__(self, artwork_data, bot):
        super().__init__(timeout=300)
        self.artwork_data = artwork_data
        self.bot = bot
        self.current_rating = 0
        self.confirmed = False
        
        # Create star buttons
        for i in range(1, 6):
            button = discord.ui.Button(
                label="",
                style=discord.ButtonStyle.secondary,
                emoji="<:StarOffLOGO:1407166957719126158>",
                custom_id=f"star_{i}"
            )
            button.callback = self.create_star_callback(i)
            self.add_item(button)

    def create_star_callback(self, star_number):
        async def star_callback(interaction: discord.Interaction):
            self.current_rating = star_number
            await self.update_stars(interaction)
        return star_callback

    async def update_stars(self, interaction: discord.Interaction):
        # Update button styles
        for i, button in enumerate(self.children):
            if i < 5:  # Only star buttons
                if i < self.current_rating:
                    button.emoji = "<:StarOnLOGO:1407162360027942912>"
                else:
                    button.emoji = "<:StarOffLOGO:1407166957719126158>"

        # Show confirmation embed
        stars_display = ""
        for i in range(5):
            if i < self.current_rating:
                stars_display += "<:StarOnLOGO:1407162360027942912>"
            else:
                stars_display += "<:StarOffLOGO:1407166957719126158>"

        embed = discord.Embed(
            title="<:WplacePantheonLOGO:1407152471226187776> Confirm Your Rating",
            description=f"Are you sure you want to give this rate to the artwork \"{self.artwork_data.title}\" by {self.artwork_data.author_name}?\n\n **Actual Rate:** {stars_display}",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )

        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Rating Confirmation", icon_url=self.bot.user.display_avatar.url)

        # Clear existing buttons and add confirm/back
        self.clear_items()
        
        confirm_button = discord.ui.Button(
            label="Confirm",
            style=discord.ButtonStyle.success,
            emoji="<:ConfirmLOGO:1407072680267481249>"
        )
        confirm_button.callback = self.confirm_vote
        
        back_button = discord.ui.Button(
            label="Back",
            style=discord.ButtonStyle.gray,
            emoji="<:BackLOGO:1391511633431494666>"
        )
        back_button.callback = self.back_to_voting
        
        self.add_item(confirm_button)
        self.add_item(back_button)

        await interaction.response.edit_message(embed=embed, view=self)

    async def confirm_vote(self, interaction: discord.Interaction):
        # Save vote to notation data
        notation_manager = NotationManager()
        success = notation_manager.add_vote(self.artwork_data.artwork_id, interaction.user.id, self.current_rating)
        
        if success:
            # Get updated artwork data with new average
            updated_data = notation_manager.get_artwork_by_id(self.artwork_data.artwork_id)
            if updated_data:
                self.artwork_data.average_rating = updated_data.average_rating
                self.artwork_data.votes = updated_data.votes

            stars_display = ""
            for i in range(5):
                if i < self.current_rating:
                    stars_display += "<:StarOnLOGO:1407162360027942912>"
                else:
                    stars_display += "<:StarOffLOGO:1407166957719126158>"

            embed = discord.Embed(
                title="<:SucessLOGO:1407071637840592977> Voted Successfully!",
                description=f"Your rating of **{stars_display}** has been successfully recorded!",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )

            # Update the original message with new rating
            try:
                # Find the original message and update it
                channel = interaction.channel
                async for message in channel.history(limit=50):
                    if (message.author == self.bot and message.embeds and 
                        "Wplace Pantheon" in message.embeds[0].title and
                        self.artwork_data.title in message.embeds[0].description):
                        
                        # Create updated embed with new rating
                        updated_embed = discord.Embed(
                            title="<:WplacePantheonLOGO:1407152471226187776> Wplace Pantheon",
                            color=discord.Color.purple(),
                            timestamp=datetime.utcnow()
                        )

                        # Add image if available
                        if self.artwork_data.image_url:
                            updated_embed.set_image(url=self.artwork_data.image_url)
                        else:
                            updated_embed.set_thumbnail(url=self.bot.user.display_avatar.url)

                        # Create description with updated rating
                        description = f"**Title:** {self.artwork_data.title}\n"
                        description += f"**Description:** {self.artwork_data.description}\n"
                        if self.artwork_data.location:
                            description += f"**Location:** {self.artwork_data.location}\n"
                        
                        rating_display = notation_manager.get_rating_display(self.artwork_data.average_rating)
                        description += f"**Global Rating:** {rating_display}"
                        
                        updated_embed.description = description

                        # Set footer
                        bot_name = get_bot_name(self.bot)
                        updated_embed.set_footer(text=f"{bot_name}", icon_url=self.bot.user.display_avatar.url)

                        # Update the original message
                        original_view = RandomArtView(self.artwork_data, self.bot)
                        await message.edit(embed=updated_embed, view=original_view)
                        break
            except Exception as e:
                print(f"Error updating original message: {e}")

        else:
            embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Already Voted",
                description="You have already voted for this artwork!",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )

        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Vote Result", icon_url=self.bot.user.display_avatar.url)

        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)

    async def back_to_voting(self, interaction: discord.Interaction):
        # Reset to voting interface
        self.clear_items()
        
        # Recreate star buttons
        for i in range(1, 6):
            button = discord.ui.Button(
                label="",
                style=discord.ButtonStyle.secondary,
                emoji="<:StarOffLOGO:1407166957719126158>",
                custom_id=f"star_{i}"
            )
            button.callback = self.create_star_callback(i)
            self.add_item(button)

        embed = discord.Embed(
            title="<:StarOnLOGO:1407162360027942912> Rate This Artwork",
            description=f"How many stars would you like to give to the artwork \"{self.artwork_data.title}\" by {self.artwork_data.author_name}?",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Artwork Rating", icon_url=self.bot.user.display_avatar.url)

        await interaction.response.edit_message(embed=embed, view=self)

class RandomArtView(discord.ui.View):
    def __init__(self, artwork_data, bot):
        super().__init__(timeout=300)
        self.artwork_data = artwork_data
        self.bot = bot

    @discord.ui.button(label="Vote", style=discord.ButtonStyle.primary, emoji="<:SendLOGO:1407071529015181443>")
    async def vote_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user already voted
        notation_manager = NotationManager()
        if notation_manager.has_user_voted(self.artwork_data.artwork_id, interaction.user.id):
            embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Already Voted",
                description="You have already voted for this artwork!",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            
            bot_name = get_bot_name(self.bot)
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            embed.set_footer(text=f"{bot_name}", icon_url=self.bot.user.display_avatar.url)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Show voting interface
        embed = discord.Embed(
            title="<:StarOnLOGO:1407162360027942912> Rate This Artwork",
            description=f"How many stars would you like to give to the artwork \"{self.artwork_data.title}\" by {self.artwork_data.author_name}?",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        bot_name = get_bot_name(self.bot)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{bot_name} | Artwork Rating", icon_url=self.bot.user.display_avatar.url)

        voting_view = VotingView(self.artwork_data, self.bot)
        await interaction.response.send_message(embed=embed, view=voting_view, ephemeral=True)

class NotationManager:
    def __init__(self):
        self.data_file = 'notation_data.json'
        self.pantheon_file = 'pantheon_data.json'

    def load_notation_data(self):
        try:
            with open(self.data_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"artworks": []}

    def save_notation_data(self, data):
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=2)

    def load_pantheon_data(self):
        try:
            with open(self.pantheon_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"artworks": []}

    def get_random_artwork(self):
        pantheon_data = self.load_pantheon_data()
        notation_data = self.load_notation_data()
        
        if not pantheon_data.get("artworks"):
            return None

        # Create a mapping of notation data by artwork ID
        notation_map = {artwork.get("artwork_id"): artwork for artwork in notation_data.get("artworks", [])}

        # Prioritize artworks that have never been shown
        never_shown = []
        shown_artworks = []

        for artwork in pantheon_data["artworks"]:
            artwork_id = artwork.get("id")
            if artwork_id not in notation_map:
                never_shown.append(artwork)
            else:
                shown_artworks.append((artwork, notation_map[artwork_id]))

        # If there are never shown artworks, pick one randomly
        if never_shown:
            selected = random.choice(never_shown)
            return self.create_notation_data_from_pantheon(selected)

        # If all have been shown, pick the one shown longest ago
        if shown_artworks:
            # Sort by last_shown timestamp (oldest first)
            shown_artworks.sort(key=lambda x: x[1].get("last_shown", ""))
            selected_pantheon, selected_notation = shown_artworks[0]
            
            # Update the artwork data
            notation_artwork = NotationData()
            notation_artwork.artwork_id = selected_notation.get("artwork_id")
            notation_artwork.title = selected_notation.get("title", "")
            notation_artwork.description = selected_notation.get("description", "")
            notation_artwork.author_name = selected_notation.get("author_name", "Anonymous")
            notation_artwork.image_url = selected_notation.get("image_url", "")
            notation_artwork.location = selected_notation.get("location", "")
            notation_artwork.votes = selected_notation.get("votes", [])
            notation_artwork.average_rating = selected_notation.get("average_rating", 0.0)
            notation_artwork.last_shown = datetime.utcnow().isoformat()
            notation_artwork.times_shown = selected_notation.get("times_shown", 0) + 1

            return notation_artwork

        return None

    def create_notation_data_from_pantheon(self, pantheon_artwork):
        notation_artwork = NotationData()
        notation_artwork.artwork_id = pantheon_artwork.get("id")
        notation_artwork.title = pantheon_artwork.get("title", "Untitled")
        notation_artwork.description = pantheon_artwork.get("description", "No description")
        notation_artwork.author_name = pantheon_artwork.get("author_name", "Anonymous")
        notation_artwork.image_url = pantheon_artwork.get("image_url", "")
        notation_artwork.location = pantheon_artwork.get("location", "")
        notation_artwork.votes = []
        notation_artwork.average_rating = 0.0
        notation_artwork.last_shown = datetime.utcnow().isoformat()
        notation_artwork.times_shown = 1

        return notation_artwork

    def update_artwork_shown(self, artwork_data):
        notation_data = self.load_notation_data()
        
        # Find existing artwork or create new entry
        existing_artwork = None
        for i, artwork in enumerate(notation_data.get("artworks", [])):
            if artwork.get("artwork_id") == artwork_data.artwork_id:
                existing_artwork = i
                break

        artwork_dict = {
            "artwork_id": artwork_data.artwork_id,
            "title": artwork_data.title,
            "description": artwork_data.description,
            "author_name": artwork_data.author_name,
            "image_url": artwork_data.image_url,
            "location": artwork_data.location,
            "votes": artwork_data.votes,
            "average_rating": artwork_data.average_rating,
            "last_shown": artwork_data.last_shown,
            "times_shown": artwork_data.times_shown
        }

        if existing_artwork is not None:
            notation_data["artworks"][existing_artwork] = artwork_dict
        else:
            if "artworks" not in notation_data:
                notation_data["artworks"] = []
            notation_data["artworks"].append(artwork_dict)

        self.save_notation_data(notation_data)

    def has_user_voted(self, artwork_id, user_id):
        notation_data = self.load_notation_data()
        
        for artwork in notation_data.get("artworks", []):
            if artwork.get("artwork_id") == artwork_id:
                for vote in artwork.get("votes", []):
                    if vote.get("user_id") == user_id:
                        return True
        return False

    def add_vote(self, artwork_id, user_id, rating):
        if self.has_user_voted(artwork_id, user_id):
            return False

        notation_data = self.load_notation_data()
        
        # Find artwork
        for artwork in notation_data.get("artworks", []):
            if artwork.get("artwork_id") == artwork_id:
                # Add vote
                vote = {
                    "user_id": user_id,
                    "rating": rating,
                    "timestamp": datetime.utcnow().isoformat()
                }
                artwork["votes"].append(vote)
                
                # Calculate new average
                total_rating = sum(vote["rating"] for vote in artwork["votes"])
                artwork["average_rating"] = round(total_rating / len(artwork["votes"]), 3)
                
                self.save_notation_data(notation_data)
                return True
        
        return False

    def get_artwork_by_id(self, artwork_id):
        """Get artwork data by ID"""
        notation_data = self.load_notation_data()
        
        for artwork in notation_data.get("artworks", []):
            if artwork.get("artwork_id") == artwork_id:
                # Convert to NotationData object
                notation_artwork = NotationData()
                notation_artwork.artwork_id = artwork.get("artwork_id")
                notation_artwork.title = artwork.get("title", "")
                notation_artwork.description = artwork.get("description", "")
                notation_artwork.author_name = artwork.get("author_name", "Anonymous")
                notation_artwork.image_url = artwork.get("image_url", "")
                notation_artwork.location = artwork.get("location", "")
                notation_artwork.votes = artwork.get("votes", [])
                notation_artwork.average_rating = artwork.get("average_rating", 0.0)
                notation_artwork.last_shown = artwork.get("last_shown")
                notation_artwork.times_shown = artwork.get("times_shown", 0)
                return notation_artwork
        
        return None

    def get_rating_display(self, average_rating):
        if average_rating == 0:
            return "<:StarOffLOGO:1407166957719126158>" * 5

        # Round to nearest 0.5
        rounded_rating = round(average_rating * 2) / 2
        
        stars = ""
        for i in range(5):
            if i < int(rounded_rating):
                stars += "<:StarOnLOGO:1407162360027942912>"
            elif i == int(rounded_rating) and rounded_rating % 1 != 0:
                stars += "<:HalfStarLOGO:1407305169875505224>"
            else:
                stars += "<:StarOffLOGO:1407166957719126158>"
        
        return stars

class NotationSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="random_art", description="Display a random artwork from the Pantheon for rating")
    async def random_art(self, interaction: discord.Interaction):
        notation_manager = NotationManager()
        artwork_data = notation_manager.get_random_artwork()
        
        if not artwork_data:
            embed = discord.Embed(
                title="❌ No Artworks Available",
                description="There are no artworks in the Pantheon to display.",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            
            bot_name = get_bot_name(self.bot)
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            embed.set_footer(text=f"{bot_name} | Random Art", icon_url=self.bot.user.display_avatar.url)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Create embed
        embed = discord.Embed(
            title="<:WplacePantheonLOGO:1407152471226187776> Wplace Pantheon",
            color=discord.Color.purple(),
            timestamp=datetime.utcnow()
        )

        # Add image if available
        if artwork_data.image_url:
            embed.set_image(url=artwork_data.image_url)
        else:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        # Create description
        description = f"**Title:** {artwork_data.title}\n"
        description += f"**Description:** {artwork_data.description}\n"
        if artwork_data.location:
            description += f"**Location:** {artwork_data.location}\n"
        
        rating_display = notation_manager.get_rating_display(artwork_data.average_rating)
        description += f"**Global Rating:** {rating_display}"
        
        embed.description = description

        # Set footer
        bot_name = get_bot_name(self.bot)
        embed.set_footer(text=f"{bot_name}", icon_url=self.bot.user.display_avatar.url)

        # Update artwork shown data
        notation_manager.update_artwork_shown(artwork_data)

        # Create view with vote button
        view = RandomArtView(artwork_data, self.bot)
        
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(NotationSystem(bot))

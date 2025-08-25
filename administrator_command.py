
import discord
from discord.ext import commands
from discord import app_commands

class AdministratorCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="clear_dm", description="Clear bot messages sent to a specific user in DMs")
    @app_commands.describe(
        user="The user whose DM messages to clear",
        amount="Number of messages to clear (1-999)"
    )
    async def clear_dm_command(self, interaction: discord.Interaction, user: discord.User, amount: int):
        # Check if user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Permission Denied",
                description="You need 'Administrator' permission to use this command.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Validate amount
        if amount < 1 or amount > 999:
            embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Invalid Amount",
                description="Amount must be between 1 and 999.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Get DM channel with the user
            dm_channel = user.dm_channel
            if dm_channel is None:
                dm_channel = await user.create_dm()

            # Fetch messages and count bot messages
            deleted_count = 0
            async for message in dm_channel.history(limit=amount * 3):  # Get more to account for user messages
                if message.author == self.bot.user and deleted_count < amount:
                    try:
                        await message.delete()
                        deleted_count += 1
                    except discord.NotFound:
                        pass  # Message already deleted
                    except discord.Forbidden:
                        break  # Can't delete messages

            # Success response
            embed = discord.Embed(
                title="<:SucessLOGO:1407071637840592977> Messages Cleared",
                description=f"Successfully cleared {deleted_count} bot message(s) from {user.mention}'s DMs.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except discord.Forbidden:
            embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Access Denied",
                description="I don't have permission to access that user's DMs or delete messages.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="<:ErrorLOGO:1407071682031648850> Error",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdministratorCommands(bot))

import io
import logging
from datetime import datetime, timezone
from typing import Optional

import aiohttp
import discord
from PIL.ImageFont import FreeTypeFont
from discord.ext import tasks
from PIL import Image, ImageDraw, ImageFont
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.data_manager import bundled_data_path
from redbot.core.i18n import Translator, set_contextual_locales_from_guild

from mdi.participant_character import ParticipantCharacter

log = logging.getLogger("red.karlo-cogs.wowtools")
_ = Translator("MDI", __file__)

TEAMS = [  # Tank, Healer, DPS, DPS, DPS
    ["Xcotli", "Winmeron", "Filezmaj", "Mageisback", "Uzgo"],
    ["Nayelli", "Medeni", "Himen", "Drvoje", "Tymyfanz"],
    ["Bonsaí", "Mylkan", "Retilol", "Djosa", "Vortax"],
    ["Bloodykurton", "Tithrál", "Mooasko", "Sljivah", "Morganlefey"],
]


class MDI(commands.Cog):
    def __init__(self, bot):
        self.bot: Red = bot
        self.config = Config.get_conf(self, identifier=87446677010550784)

        default_guild = {"mdi_channel": None, "mdi_message": None}
        self.config.register_guild(**default_guild)

        self.session = aiohttp.ClientSession(headers={"User-Agent": "Red-DiscordBot/WoWToolsCog"})
        self.update_mdi_scoreboard.start()

    @commands.group()
    @commands.admin()
    @commands.guild_only()
    async def mdiset(self, ctx: commands.Context):
        """MDI postavke."""
        pass

    @mdiset.command(name="channel")
    @commands.admin()
    @commands.guild_only()
    async def mdiset_channel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Postavi kanal za MDI ljestvicu."""
        mdi_channel_id: int = await self.config.guild(ctx.guild).mdi_channel()
        mdi_msg_id: int = await self.config.guild(ctx.guild).mdi_message()
        if not channel:
            if mdi_channel_id:  # Remove the scoreboard message if it exists
                await self._delete_scoreboard(
                    ctx,
                    mdi_channel_id,
                    mdi_msg_id,
                )
            await self.config.guild(ctx.guild).mdi_channel.clear()
            await self.config.guild(ctx.guild).mdi_message.clear()
            await ctx.send(_("Scoreboard channel cleared."))
            return
        if mdi_msg_id:  # Remove the old scoreboard
            await self._delete_scoreboard(
                ctx,
                mdi_channel_id,
                mdi_msg_id,
            )
        await self.config.guild(ctx.guild).mdi_channel.set(channel.id)
        embed, img_file = await self._generate_mdi_scoreboard(ctx)
        sb_msg = await channel.send(file=img_file, embed=embed)
        await self.config.guild(ctx.guild).mdi_message.set(sb_msg.id)
        await ctx.send("Kanal za MDI ljestvicu postavljen.")

    @staticmethod
    async def _delete_scoreboard(ctx: commands.Context, sb_channel_id: int, sb_msg_id: int):
        try:
            sb_channel: discord.TextChannel = ctx.guild.get_channel(sb_channel_id)
            sb_msg: discord.Message = await sb_channel.fetch_message(sb_msg_id)
        except discord.NotFound:
            log.info(f"Scoreboard message in {ctx.guild} ({ctx.guild.id}) not found.")
            return
        if sb_msg:
            await sb_msg.delete()

    async def _generate_mdi_scoreboard(self, ctx: commands.Context):
        embed = discord.Embed(
            title="MDI timovi",
            color=await ctx.embed_color(),
        )
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url)
        img_file = await self._generate_mdi_image()
        embed.set_image(url=f"attachment://{img_file.filename}")
        return embed, img_file

    async def _generate_mdi_image(self):
        team_data: list[list[Optional[ParticipantCharacter]]] = [[], [], [], []]
        for i, team in enumerate(TEAMS):
            for player in team:
                if player == "":
                    team_data[i].append(None)
                    continue
                try:
                    character = await ParticipantCharacter.create(player)
                except KeyError:  # character doesn't exist yet?
                    character = None
                team_data[i].append(character)

        img = Image.open(bundled_data_path(self) / "mdi_scoreboard.png")
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype(str(bundled_data_path(self) / "Roboto-Bold.ttf"), 40)

        # Team 1
        x = 194
        y = 275
        await self.draw_team(draw, font, img, team_data[0], x, y)

        # Team 2
        x = 1235
        y = 275
        await self.draw_team(draw, font, img, team_data[1], x, y)

        # Team 3
        x = 194
        y = 953
        await self.draw_team(draw, font, img, team_data[2], x, y)

        # Team 4
        x = 1235
        y = 953
        await self.draw_team(draw, font, img, team_data[3], x, y)

        img_obj = io.BytesIO()
        img.save(img_obj, format="PNG")
        img_obj.seek(0)

        return discord.File(fp=img_obj, filename="scoreboard.png")

    async def draw_team(
        self,
        draw: ImageDraw,
        font: FreeTypeFont,
        img,
        team: list[Optional[ParticipantCharacter]],
        x,
        y,
    ):
        offset = 7
        draw.text((x + 375, y - offset - 100), str(self.get_team_avg_ilvl(team)), font=font)
        draw.text((x + 540, y - offset - 100), str(self.get_team_avg_score(team)), font=font)
        for character in team:
            if character is None:
                draw.text((x + 15, y - offset), "???", font=font)
                y += 113
                continue

            async with self.session.request("GET", character.thumbnail_url) as resp:
                image = await resp.content.read()
                image = Image.open(io.BytesIO(image))
                image = image.resize((97, 97))
                img.paste(image, (x - 100, y - 30))

            draw.text((x + 15, y - offset), character.name, character.get_class_color(), font=font)
            draw.text(
                (x + 375, y - offset),
                f"{str(round(character.item_level))}",
                self._get_ilvl_color(character.item_level),
                font=font,
            )
            draw.text((x + 540, y - offset), str(int(character.score)), character.color, font=font)
            y += 113

    @staticmethod
    def get_team_avg_ilvl(team: list[Optional[ParticipantCharacter]]) -> int:
        ilvls = [character.item_level for character in team if character]
        return int(sum(ilvls) / len(ilvls))

    @staticmethod
    def get_team_avg_score(team: list[Optional[ParticipantCharacter]]) -> int:
        scores = [character.score for character in team if character]
        return int(sum(scores) / len(scores))

    @staticmethod
    def _get_ilvl_color(ilvl: int) -> str:
        if ilvl >= 485:
            return "#f16960"
        elif ilvl >= 482:
            return "#FF69B4"
        elif ilvl >= 479:
            return "#FFA500"
        elif ilvl >= 474:
            return "#b040c2"
        elif ilvl >= 469:
            return "#445bc2"
        elif ilvl >= 464:
            return "#00ff1a"
        else:
            return "#FFFFFF"

    @tasks.loop(minutes=10)
    async def update_mdi_scoreboard(self):
        for guild in self.bot.guilds:
            if await self.bot.cog_disabled_in_guild(self, guild):
                continue
            await set_contextual_locales_from_guild(self.bot, guild)

            mdi_channel_id = await self.config.guild(guild).mdi_channel()
            mdi_msg_id = await self.config.guild(guild).mdi_message()
            if not (mdi_channel_id and mdi_msg_id):
                continue
            mdi_channel = guild.get_channel(mdi_channel_id)

            try:
                mdi_msg = await mdi_channel.fetch_message(mdi_msg_id)
            except discord.HTTPException:
                log.error(f"Failed to fetch MDI scoreboard message in {guild} ({guild.id}).")
                continue
            if not mdi_msg:
                continue

            embed = discord.Embed(
                title="MDI timovi",
                color=await self.bot.get_embed_color(mdi_msg),
            )
            embed.set_author(name=guild.name, icon_url=guild.icon.url)

            desc = f"Zadnji put ažurirano <t:{int(datetime.now(timezone.utc).timestamp())}:R>\n"
            desc += "Prvi dan MDI-a počinje <t:1708543800:R>\n"

            img_file = await self._generate_mdi_image()
            embed.set_image(url=f"attachment://{img_file.filename}")
            embed.set_footer(text="Ažurira se svakih 10 minuta")
            embed.description = desc

            try:
                await mdi_msg.edit(embed=embed, attachments=[img_file])
            except discord.HTTPException:
                log.error(f"Failed to edit MDI scoreboard message in {guild} ({guild.id}).")

    @update_mdi_scoreboard.error
    async def update_mdi_scoreboard_error(self, error):
        log.error(f"Unhandled exception in update_mdi_scoreboard task: {error}", exc_info=True)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
        self.update_mdi_scoreboard.stop()

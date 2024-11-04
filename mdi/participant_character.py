from raiderio_async import RaiderIO
from redbot.core.bot import Red

from aiowowapi import API, WowApi


class ParticipantCharacter:
    def __init__(self):
        self.name: str = ""
        self.thumbnail_url: str = ""
        self.item_level: int = 0
        self.score: float = 0
        self.color: str = ""
        self.player_class: str = ""

    @classmethod
    async def create(cls, name: str, wow_api):
        self = cls()
        self.name = name

        async with RaiderIO() as rio:
            player_data = await rio.get_character_profile(
                "eu",
                "ragnaros" if "-" not in name else "-".join(name.split("-")[1:]),
                name.split("-")[0],
                ["mythic_plus_scores_by_season:current"],
            )
        blizz_profile = await wow_api.Retail.Profile.get_character_profile_summary(
            "ragnaros" if "-" not in name else "-".join(name.split("-")[1:]).lower(),
            name.split("-")[0].lower(),
        )
        player_ilvl: int = blizz_profile.get("equipped_item_level", 0)

        try:
            self.thumbnail_url = player_data["thumbnail_url"]
            self.item_level = player_ilvl
            self.score = player_data["mythic_plus_scores_by_season"][0]["segments"]["all"]["score"]
            self.color = player_data["mythic_plus_scores_by_season"][0]["segments"]["all"]["color"]
            self.player_class = player_data["class"]
        except KeyError:
            return self

        return self

    def get_class_color(self):
        return {
            "DEATH KNIGHT": "#C41F3B",
            "DEMON HUNTER": "#A330C9",
            "DRUID": "#FF7D0A",
            "HUNTER": "#ABD473",
            "MAGE": "#69CCF0",
            "MONK": "#00FF96",
            "PALADIN": "#F58CBA",
            "PRIEST": "#FFFFFF",
            "ROGUE": "#FFF569",
            "SHAMAN": "#0070DE",
            "WARLOCK": "#9482C9",
            "WARRIOR": "#C79C6E",
            "EVOKER": "#1F594D",
        }[self.player_class.upper()]

    def to_row(self):
        return [
            self.name.split("-")[0],
            self.player_class,
            f"{int(round(self.item_level, 0))}{'✔️' if self.item_level >= 610 else ''}",
            int(self.score),
        ]

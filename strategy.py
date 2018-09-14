from sc2.constants import *


class BaseStrategy():
    def __init__(self, bot):
        self.bot = bot
        ...

    def is_need_to_expand(self):
        raise NotImplementedError

    def is_need_food(self):
        raise NotImplementedError

    def is_need_combat_units(self):
        raise NotImplementedError

    def is_need_workers(self):
        raise NotImplementedError

    def is_need_research(self):
        raise NotImplementedError

    def is_need_upgrades(self):
        raise NotImplementedError

    def is_need_buildings(self):
        raise NotImplementedError

    async def add_food(self):
        raise NotImplementedError

    async def train_workers(self):
        raise NotImplementedError

    async def train_units(self):
        raise NotImplementedError

    async def build_buildings(self):
        raise NotImplementedError

    async def upgrade_buildings(self):
        raise NotImplementedError

    async def do_upgrades(self):
        raise NotImplementedError

    async def do_research(self):
        raise NotImplementedError


class BaseZergStrategy(BaseStrategy):
    def __init__(self, bot):
        BaseStrategy.__init__(self, bot)

    def is_need_food(self):
        return self.bot.supply_left < (2 * self.bot.townhalls.amount) \
                and self.bot.already_pending(UnitTypeId.OVERLORD) < self.bot.townhalls.amount \
                and self.bot.supply_cap < 200

    async def add_food(self):
        if self.is_need_food():
            if self.bot.can_train(UnitTypeId.OVERLORD):
                await self.bot.train(UnitTypeId.OVERLORD)


class TestStrategy(BaseZergStrategy):
    def __init__(self, bot):
        BaseStrategy.__init__(self, bot)

    def is_need_to_expand(self):
        return self.bot.total_amount(UnitTypeId.DRONE) / self.bot.townhalls.amount > 16 \
               or self.bot.workers.idle.amount > 8 and self.bot.already_pending(UnitTypeId.HATCHERY) < 1

    def is_need_combat_units(self):
        return True

    def is_need_workers(self):
        return self.bot.total_amount(UnitTypeId.DRONE) < 82

    def is_need_research(self):
        return True

    def is_need_upgrades(self):
        return True

    def is_need_buildings(self):
        return True

    async def train_workers(self):
        if not self.is_need_workers():
            return

        if self.bot.can_train(UnitTypeId.DRONE, None, 82):
            await self.bot.train(UnitTypeId.DRONE)

    async def train_units(self):
        if not self.is_need_combat_units():
            return

        unit_list = ((UnitTypeId.ZERGLING, UnitTypeId.SPAWNINGPOOL, 20),
                     (UnitTypeId.ROACH, UnitTypeId.SPAWNINGPOOL, 20),
                     (UnitTypeId.HYDRALISK, UnitTypeId.SPAWNINGPOOL, 20),)

        for unit, req, count in unit_list:
            if self.bot.can_train(unit, req, count):
                await self.bot.train(unit)

    async def build_buildings(self):
        if not self.is_need_buildings():
            return

        building_list = ((UnitTypeId.SPAWNINGPOOL, UnitTypeId.HATCHERY, 1),
                         (UnitTypeId.EVOLUTIONCHAMBER, UnitTypeId.QUEEN, 2),
                         (UnitTypeId.ROACHWARREN, UnitTypeId.QUEEN, 1),
                         (UnitTypeId.HYDRALISKDEN, UnitTypeId.LAIR, 1),
                         (UnitTypeId.INFESTATIONPIT, UnitTypeId.HYDRALISKDEN, 1),)

        for building, req, count in building_list:
            if self.bot.can_build(building, req, count):
                if not (building == UnitTypeId.SPAWNINGPOOL and self.bot.supply_used < 16):
                    await self.bot.build(building)
                    break

    async def upgrade_buildings(self):
        if self.bot.hq is None or not self.bot.hq.is_ready:
            return

        if self.bot.units(UnitTypeId.ROACHWARREN).ready.exists and not self.bot.units(UnitTypeId.LAIR).exists\
                and self.bot.can_afford(UnitTypeId.LAIR) and not self.bot.units(UnitTypeId.HIVE).exists:
            await self.bot.queue.push(self.bot.hq.build(UnitTypeId.LAIR))
        elif self.bot.units(UnitTypeId.INFESTATIONPIT).ready.exists and self.bot.units(UnitTypeId.LAIR).ready.exists\
                and not self.bot.units(UnitTypeId.HIVE).exists and self.bot.can_afford(UnitTypeId.HIVE):
            await self.bot.queue.push(self.bot.hq.build(UnitTypeId.HIVE))

    async def do_upgrades(self):
        if not self.is_need_upgrades():
            return

        upgrade_list = ((UpgradeId.ZERGGROUNDARMORSLEVEL3, UnitTypeId.HIVE, UnitTypeId.EVOLUTIONCHAMBER),
                        (UpgradeId.ZERGGROUNDARMORSLEVEL2, UnitTypeId.LAIR, UnitTypeId.EVOLUTIONCHAMBER),
                        (UpgradeId.ZERGMELEEWEAPONSLEVEL3, UnitTypeId.HIVE, UnitTypeId.EVOLUTIONCHAMBER),
                        (UpgradeId.ZERGMISSILEWEAPONSLEVEL3, UnitTypeId.HIVE, UnitTypeId.EVOLUTIONCHAMBER),
                        (UpgradeId.ZERGMELEEWEAPONSLEVEL2, UnitTypeId.LAIR, UnitTypeId.EVOLUTIONCHAMBER),
                        (UpgradeId.ZERGMISSILEWEAPONSLEVEL2, UnitTypeId.LAIR, UnitTypeId.EVOLUTIONCHAMBER),
                        (UpgradeId.ZERGGROUNDARMORSLEVEL1, UnitTypeId.HATCHERY, UnitTypeId.EVOLUTIONCHAMBER),
                        (UpgradeId.ZERGMELEEWEAPONSLEVEL1, UnitTypeId.HATCHERY, UnitTypeId.EVOLUTIONCHAMBER),
                        (UpgradeId.ZERGMISSILEWEAPONSLEVEL1, UnitTypeId.HATCHERY, UnitTypeId.EVOLUTIONCHAMBER),)
        for upgrade, requirement, builder in upgrade_list:
            if await self.bot.upgrade(upgrade, requirement, builder):
                break

    async def do_research(self):
        if not self.is_need_research():
            return

        research_list = ((UpgradeId.ZERGLINGMOVEMENTSPEED, UnitTypeId.SPAWNINGPOOL, UnitTypeId.SPAWNINGPOOL),
                         (UpgradeId.ZERGLINGATTACKSPEED, UnitTypeId.HIVE, UnitTypeId.SPAWNINGPOOL),
                         (UpgradeId.GLIALRECONSTITUTION, UnitTypeId.ROACHWARREN, UnitTypeId.ROACHWARREN),
                         (UpgradeId.EVOLVEGROOVEDSPINES, UnitTypeId.HYDRALISKDEN, UnitTypeId.HYDRALISKDEN),
                         (UpgradeId.EVOLVEMUSCULARAUGMENTS, UnitTypeId.INFESTATIONPIT, UnitTypeId.HYDRALISKDEN),
                         (UpgradeId.CHITINOUSPLATING, UnitTypeId.ULTRALISKCAVERN, UnitTypeId.ULTRALISKCAVERN))
        for upgrade, requirement, builder in research_list:
            if await self.bot.research(upgrade, requirement, builder):
                break


class DefensiveStrategy(BaseZergStrategy):
    def __init__(self, bot):
        BaseStrategy.__init__(self, bot)

    def is_need_to_expand(self):
        return False

    def is_need_combat_units(self):
        return True

    def is_need_workers(self):
        return False

    def is_need_research(self):
        return True

    def is_need_upgrades(self):
        return False

    def is_need_buildings(self):
        return True

    async def train_workers(self):
        return

    async def train_units(self):
        if not self.is_need_combat_units():
            return

        unit_list = ((UnitTypeId.ROACH, UnitTypeId.SPAWNINGPOOL, 30),
                     (UnitTypeId.HYDRALISK, UnitTypeId.SPAWNINGPOOL, 20),)
        for unit, req, count in unit_list:
            if self.bot.can_train(unit, req, count):
                await self.bot.train(unit)

    async def build_buildings(self):
        if not self.is_need_buildings():
            return

        building_list = ((UnitTypeId.SPAWNINGPOOL, UnitTypeId.HATCHERY, 1),
                         (UnitTypeId.ROACHWARREN, UnitTypeId.QUEEN, 1),
                         (UnitTypeId.HYDRALISKDEN, UnitTypeId.LAIR, 1),)

        for building, req, count in building_list:
            if self.bot.can_build(building, req, count):
                if not (building == UnitTypeId.SPAWNINGPOOL and self.bot.supply_used < 16):
                    await self.bot.build(building)
                    break

    async def upgrade_buildings(self):
        if not self.bot.townhalls.ready.exists:
            return

        if self.bot.units(UnitTypeId.ROACHWARREN).ready.exists and not self.bot.units(UnitTypeId.LAIR).exists\
                and self.bot.can_afford(UnitTypeId.LAIR) and not self.bot.units(UnitTypeId.HIVE).exists:
            hat = self.bot.units(UnitTypeId.HATCHERY).ready.first
            await self.bot.queue.push(hat.build(UnitTypeId.LAIR))

    async def do_upgrades(self):
        ...

    async def do_research(self):
        ...

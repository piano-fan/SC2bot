import random
import sc2
from sc2 import run_game, maps, Race, Difficulty
from sc2.player import Bot, Computer, Human
from sc2.constants import *
from sc2.game_data import GameData
from sc2.unit import Unit

from strategy import *


class ActionQueue():
    def __init__(self, bot):
        self.__bot = bot
        self.__actions = []

    async def push(self, action):
        cost = self.__bot._game_data.calculate_ability_cost(action.ability)
        self.__bot.minerals -= cost.minerals
        self.__bot.vespene -= cost.vespene
        self.__bot.supply_left -= self.__bot.get_supply_cost(action.unit.type_id)
        self.__actions.append(action)

    async def push_list(self, action_list):
        for action in action_list:
            cost = self.__bot._game_data.calculate_ability_cost(action.ability)
            self.__bot.minerals -= cost.minerals
            self.__bot.vespene -= cost.vespene
            self.__bot.supply_left -= self.__bot.get_supply_cost(action.unit.type_id)
        self.__actions.extend(action_list)

    async def flush(self):
        await self.__bot._client.actions(self.__actions, game_data=self.__bot._game_data)
        self.__actions = []


class FirstBot(sc2.BotAI):
    def __init__(self):
        self.queue = ActionQueue(self)
        self.__strategy = TestStrategy(self)
        self.hq = None

    def total_amount(self, unit):
        return self.units(unit).amount + self.already_pending(unit)

    def get_supply_cost(self, item_id):
        return self._game_data.units[item_id.value]._proto.food_required

    def get_cost(self, item_id):
        if isinstance(item_id, UnitTypeId):
            unit = self._game_data.units[item_id.value]
            cost = self._game_data.calculate_ability_cost(unit.creation_ability)
            cost.supply = unit._proto.food_required
        elif isinstance(item_id, UpgradeId):
            cost = self._game_data.upgrades[item_id.value].cost
        else:
            cost = self._game_data.calculate_ability_cost(item_id)

        return cost

    def can_build(self, building, requirement=None, max_count=None):
        return self.can_afford(building) and (requirement is None or self.units(requirement).ready.exists) \
            and (max_count is None or self.total_amount(building) < max_count)

    def can_train(self, unit, requirement=None, max_count=None):
        return self.can_afford(unit) and (requirement is None or self.units(requirement).ready.exists) \
            and (max_count is None or self.total_amount(unit) < max_count) \
            and self.units(UnitTypeId.LARVA).exists and self.supply_left >= self.get_supply_cost(unit)

    async def build(self, building, near=None, max_distance=20, unit=None, random_alternative=True, placement_step=2):
        if near is None:
            near = self.townhalls.random
        if isinstance(near, Unit):
            near = near.position.to2
        elif near is not None:
            near = near.to2

        p = await self.find_placement(building, near.rounded, max_distance, random_alternative, placement_step)
        if p is None:
            return None

        unit = unit or self.select_build_worker(p)
        if unit is None:
            return None
        await self.queue.push(unit.build(building, p))

    async def train(self, unit: UnitTypeId):
        await self.queue.push(self.units(UnitTypeId.LARVA).random.train(unit))

    async def research(self, tech: UpgradeId, requirement: UnitTypeId, builder: UnitTypeId):
        if self.can_afford(tech) and self.units(requirement).ready.exists and self.units(builder).ready.idle.exists and not self.already_pending_upgrade(tech):
            await self.queue.push(self.units(builder).ready.idle.first.research(tech))
            return True
        return False

    async def upgrade(self, upgrade: UpgradeId, requirement: UnitTypeId, builder: UnitTypeId):
        if self.can_afford(upgrade) and self.units(requirement).ready.exists and not self.already_pending_upgrade(upgrade):
            if self.units(builder).ready.noqueue.exists:
                await self.queue.push(self.units(builder).ready.noqueue.first.research(upgrade))
                return True
        return False

    async def on_step(self, iteration):
        await self.think(iteration)
        await self.queue.flush()

    async def think(self, iteration):
        if self.townhalls.ready.exists and self.hq is None:
            self.hq = self.townhalls.ready.first

        drone_count = self.total_amount(UnitTypeId.DRONE)
        #Expand
        if self.__strategy.is_need_to_expand():
            if not self.already_pending(UnitTypeId.HATCHERY):
                if self.can_afford(UnitTypeId.HATCHERY):
                    location = await self.get_next_expansion()
                    await self.build(UnitTypeId.HATCHERY, location, 10, placement_step=1)
                else:
                    cost = self.get_cost(UnitTypeId.HATCHERY)
                    self.minerals -= cost.minerals
                    self.vespene -= cost.vespene

        await self.__strategy.add_food()
        await self.__strategy.do_upgrades()

        for hat in self.townhalls:
            if not hat.is_ready:
                continue
            #Inject larva
            if self.units(UnitTypeId.QUEEN).closer_than(10, hat).exists:
                queen = self.units(UnitTypeId.QUEEN).closer_than(10, hat).first
                if await self.can_cast(queen, AbilityId.EFFECT_INJECTLARVA, hat, True):
                    await self.queue.push(queen(AbilityId.EFFECT_INJECTLARVA, hat))
            #Train Queen
            if self.units(UnitTypeId.SPAWNINGPOOL).ready.exists and self.can_afford(UnitTypeId.QUEEN) and self.supply_left >= 2:
                if not self.units(UnitTypeId.QUEEN).closer_than(10, hat).exists and hat.noqueue:
                    await self.queue.push(hat.train(UnitTypeId.QUEEN))
            if self.workers.exists:
                #Idle worker send gather mineral
                if hat.assigned_harvesters < hat.ideal_harvesters:
                    if self.workers.idle.exists:
                        await self.queue.push(self.workers.idle.first.gather(self.state.mineral_field.closer_than(10,hat).random))
                    else:
                        await self.__strategy.train_workers()

                if hat.assigned_harvesters > hat.ideal_harvesters:
                    workers = self.workers.closer_than(5,self.state.mineral_field.closest_to(hat))
                    if workers.exists:
                        await self.queue.push(workers.first.stop())

                #Build extractors
                max_extractors = 1
                if self.units(UnitTypeId.INFESTATIONPIT).ready.exists:
                    max_extractors = 2
                if self.units(UnitTypeId.EXTRACTOR).closer_than(20, hat).amount < max_extractors\
                        and (self.units(UnitTypeId.SPAWNINGPOOL).exists or self.already_pending(UnitTypeId.SPAWNINGPOOL)):
                    if self.can_afford(UnitTypeId.EXTRACTOR) and not self.already_pending(UnitTypeId.EXTRACTOR):
                        pos = self.state.vespene_geyser.closer_than(20, hat)
                        workers = self.workers.closer_than(20,hat)
                        if pos.exists and workers.exists:
                            await self.queue.push(workers.first.build(UnitTypeId.EXTRACTOR, pos.first))

                #Get workers in extractors
                if self.units(UnitTypeId.EXTRACTOR).closer_than(10, hat).exists and hat.assigned_harvesters > 12:
                    for extr in self.units(UnitTypeId.EXTRACTOR).closer_than(10, hat):
                        if extr.assigned_harvesters < extr.ideal_harvesters:
                            if self.workers.idle.exists:
                                await self.queue.push(self.workers.idle.random.gather(extr))
                            else:
                                if self.workers.closer_than(10, hat).exists:
                                    await self.queue.push(self.workers.closer_than(10, hat).random.gather(extr))
                                else:
                                    await self.__strategy.train_workers()
                        if extr.assigned_harvesters > extr.ideal_harvesters:
                            workers = self.workers.closer_than(1,extr)
                            if workers.exists:
                                await self.queue.push(workers.random.stop())

        await self.__strategy.train_units()
        await self.__strategy.do_research()
        await self.__strategy.build_buildings()
        await self.__strategy.upgrade_buildings()

        def select_target():
            if self.known_enemy_structures.exists:
                return random.choice(self.known_enemy_structures).position

            return self.enemy_start_locations[0]

        army = self.units.of_type([UnitTypeId.ZERGLING, UnitTypeId.ROACH, UnitTypeId.HYDRALISK, UnitTypeId.ULTRALISK])
        if army.exists:
            #Defend bases
            for hat in self.townhalls:
                enemy_near_base = self.state.units.enemy.closer_than(20, hat)
                if enemy_near_base.exists:
                    if not isinstance(self.__strategy, DefensiveStrategy):
                        self.__strategy = DefensiveStrategy(self)
                    await self.queue.push_list([unit.attack(enemy_near_base.center) for unit in army.idle])
                    break
            else:
                if not isinstance(self.__strategy, TestStrategy):
                    self.__strategy = TestStrategy(self)

            if army.amount >= 60:
                await self.queue.push_list([unit.attack(select_target()) for unit in army.idle])

run_game(maps.get("(2)16-BitLE"), [
    Bot(Race.Zerg, FirstBot()),
    Computer(Race.Protoss, Difficulty.VeryHard)
], realtime=False, save_replay_as="Test.SC2Replay")

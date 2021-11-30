import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

import time

import random
from typing import Set

from sc2 import maps
from sc2.bot_ai import BotAI
from sc2.data import Difficulty, Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.main import run_game
from sc2.player import Bot, Computer
from sc2.position import Point2, Point3
from sc2.unit import Unit
from sc2.units import Units


class DSC(BotAI):
    natural_was_taken = False
    overmine_workers = []
    base_harvester = []


    async def on_step(self, iteration):
        await self.cashe_variables()
        await self.train_workers()
        await self.build_supply()
        await self.build_barrack()
        await self.idles()
        await self.supply_cond()
        await self.speedmine(self.units(UnitTypeId.SCV))
        if self.time < 1:
            await self.split_workers()
        await self.build_gases()
        await self.gathering_gases()
        await self.expand()
        await self.replace_natural()
        await self.gathering_minerals()




    async def cashe_variables(self):
        self.townhalls_flying = (self.townhalls(UnitTypeId.COMMANDCENTERFLYING) |
                                 self.townhalls(UnitTypeId.ORBITALCOMMANDFLYING))
        self.planned_locations: Set[Point2] = {placeholder.position for placeholder in self.placeholders}
        self.my_structure_locations: Set[Point2] = {structure.position for structure in self.structures}
        self.enemy_structure_locations: Set[Point2] = {structure.position for structure in self.enemy_structures}
        self.blocked_locations: Set[Point2] = (
            self.my_structure_locations | self.planned_locations | self.enemy_structure_locations
        )
        if self.townhalls_flying.amount + self.townhalls.amount == 1:
            self.natural = await self.get_next_expansion()


#   find idles
    async def idles(self):
        if not self.townhalls:
            return
        
        closest_mineral_field = self.mineral_field.closest_to(self.townhalls[0])
        for worker in self.workers:
            if worker.is_idle:
                self.do(worker.gather(closest_mineral_field))

#   split workers
    async def split_workers(self):
        mfs = self.mineral_field.closer_than(10, self.townhalls.first.position)
        workers = self.units(UnitTypeId.SCV)
        for mf in mfs:  # type: Unit
            if workers:
                worker = workers.closest_to(mf)
                self.do(worker.gather(mf))
                workers.remove(worker)
        for w in workers:  # type: Unit
            self.do(w.gather(mfs.closest_to(w)))




#   train workers
    async def train_workers(self):
        townhalls = (self.townhalls(UnitTypeId.COMMANDCENTER).ready or self.townhalls(UnitTypeId.ORBITALCOMMAND) or
                     self.townhalls(UnitTypeId.PLANETARYFORTRESS))
        for CC in townhalls:
            if (self.can_afford(UnitTypeId.SCV) and CC.is_idle and self.workers.amount < 88
                and (CC.position == self.start_location or CC.position in self.expansion_locations_list)):
                self.do(CC(AbilityId.COMMANDCENTERTRAIN_SCV))



#   build supply
    async def build_supply(self):
        depot_placement_positions: Set[Point2] = self.main_base_ramp.corner_depots
        depots: Units = self.structures.of_type({UnitTypeId.SUPPLYDEPOT, UnitTypeId.SUPPLYDEPOTLOWERED})
        if depots:
            depot_placement_positions: Set[Point2] = {
                dep for dep in depot_placement_positions if depots.closest_distance_to(dep) > 1
            }
        if ((self.structures(UnitTypeId.SUPPLYDEPOT).amount + self.structures(UnitTypeId.SUPPLYDEPOTLOWERED).amount < 2)
             and self.supply_left < 5 and not self.already_pending(UnitTypeId.SUPPLYDEPOT)):
            if self.can_afford(UnitTypeId.SUPPLYDEPOT):
                if len(depot_placement_positions) == 0:
                    return
                target_depot_location: Point2 = depot_placement_positions.pop()
                if self.workers.amount == 12:
                    self.do(self.townhalls.ready.not_flying.first(AbilityId.RALLY_COMMANDCENTER, target_depot_location))
                else:
                    if self.townhalls.amount != 0:
                        field = self.mineral_field.closest_to(self.townhalls.ready.not_flying.first)
                    self.do(self.townhalls.ready.not_flying.first(AbilityId.RALLY_COMMANDCENTER, field))
                workers: Units = self.workers
                if workers: 
                    worker: Unit = workers.closest_to(target_depot_location)
                    if worker.is_idle or worker.is_gathering:
                        if self.workers.amount >= 13:
                            self.do(worker.build(UnitTypeId.SUPPLYDEPOT, target_depot_location))
                    else:
                        return
        if ((self.structures(UnitTypeId.SUPPLYDEPOT).amount + self.structures(UnitTypeId.SUPPLYDEPOTLOWERED).amount >= 2) and self.supply_left < 6
             and not self.already_pending (UnitTypeId.SUPPLYDEPOT)and self.can_afford(UnitTypeId.SUPPLYDEPOT)):
                workers: Units = self.workers
                if self.townhalls:
                    depotloc = await self.find_placement(UnitTypeId.SUPPLYDEPOT, near=self.townhalls[0].position.towards(self.game_info.map_center,12), placement_step = 4)
                    if workers: 
                        worker: Unit = workers.closest_to(depotloc)
                        if worker.is_idle or worker.is_gathering:
                            self.do(worker.build(UnitTypeId.SUPPLYDEPOT, depotloc))
                        else:
                            return

#   build barrack
    async def build_barrack(self):
        barrack_placement_positions: Set[Point2] = self.main_base_ramp.barracks_in_middle
        barraks: Units = self.structures.of_type(UnitTypeId.BARRACKS)
        if ((self.structures(UnitTypeId.SUPPLYDEPOT).ready or self.structures(UnitTypeId.SUPPLYDEPOTLOWERED).ready)
             and self.can_afford(UnitTypeId.BARRACKS) and self.already_pending(UnitTypeId.BARRACKS) == 0):
            if self.structures(UnitTypeId.BARRACKS).amount + self.already_pending(UnitTypeId.BARRACKS) > 0:
                return
            target_barrack_location: Point2 = barrack_placement_positions
            workers: Units = self.workers
            if workers:
                worker: Unit = workers.closest_to(target_barrack_location)
                if worker.is_idle or worker.is_gathering:
                    self.do(worker.build(UnitTypeId.BARRACKS, target_barrack_location))
                else:
                    return


#  up/down supply
    async def supply_cond(self):
        for depo in self.structures(UnitTypeId.SUPPLYDEPOT).ready:
            for unit in self.enemy_units:
                if unit.distance_to(depo) < 15:
                    break
            else:
                depo(AbilityId.MORPH_SUPPLYDEPOT_LOWER)

    
        for depo in self.structures(UnitTypeId.SUPPLYDEPOTLOWERED).ready:
            for unit in self.enemy_units:
                if unit.distance_to(depo) < 10:
                    depo(AbilityId.MORPH_SUPPLYDEPOT_RAISE)
                    break

#   advanced gathering
    async def speedmine(self, workers: Units):
        if not self.townhalls.not_flying.ready:
            return
        for worker in workers:
            await self.speedmine_single(worker)


    async def speedmine_single(self, worker: Unit):
        townhall = self.townhalls.not_flying.ready.closest_to(worker)
        field = self.mineral_field.closest_to(worker)
        if len(worker.orders) != 1:
            return
        if self.enemy_units.closer_than(15, townhall):
            return
        if worker.is_carrying_minerals:
            target: Point2 = townhall.position.towards(worker, townhall.radius + worker.radius)
            if worker.distance_to(target) > 0.5:
                self.do(worker.move(target))
                self.do(worker(AbilityId.SMART, townhall, True))
                return


    async def build_gases(self):
        if (self.workers.amount > 13 and self.units(UnitTypeId.BARRACKS).amount != 0 and self.can_afford(UnitTypeId.REFINERY)
            and self.structures(UnitTypeId.REFINERY).amount <= 0 and not self.already_pending(UnitTypeId.REFINERY)):
            workers: Units = self.workers
            CCs = self.townhalls(UnitTypeId.COMMANDCENTER)
            if workers: 
                for cc in CCs:
                    vgs = self.vespene_geyser.closer_than(10, cc)
                for vg in vgs:
                    worker: Unit = workers.closest_to(vg)
                    if (worker.is_idle or worker.is_gathering) and not self.gas_buildings.closer_than(1, vg):
                        worker.build_gas(vg)
        if self.workers.amount > 19 and self.can_afford(UnitTypeId.REFINERY) and self.gas_buildings.amount < 2 * self.townhalls.amount:
            workers: Units = self.workers
            CCs = self.townhalls(UnitTypeId.COMMANDCENTER).ready
            if workers: 
                for cc in CCs:
                    vgs = self.vespene_geyser.closer_than(10, cc)
                for vg in vgs:
                    worker: Unit = workers.closest_to(vg)
                    if (worker.is_idle or worker.is_gathering) and not self.gas_buildings.closer_than(1, vg):
                        worker.build_gas(vg)


    async def gathering_gases(self):
        if self.vespene > self.minerals + 200:
            self.gas_workers = 2
        else:
            self.gas_workers = 3

        for refinery in self.gas_buildings:
            if self.gas_workers == 2:
                if refinery.assigned_harvesters < refinery.ideal_harvesters - 1:
                    worker: Units = self.workers.closer_than(10, refinery)
                    if worker:
                        worker.random.gather(refinery)
                
            else:
                if refinery.assigned_harvesters < refinery.ideal_harvesters:
                    worker: Units = self.workers.closer_than(10, refinery)
                    if worker:
                        worker.random.gather(refinery)
                elif refinery.assigned_harvesters > refinery.ideal_harvesters:
                    for worker in self.workers:
                        if worker.is_carrying_vespene:
                            self.do(worker.gather(self.mineral_field.closest_to(worker)))


    async def gathering_minerals(self):
        for townhall in self.townhalls.ready.not_flying:
            ind = self.townhalls.not_flying.index(townhall)
            while len(self.base_harvester) < len(self.townhalls.not_flying):
                self.base_harvester.append([])
            self.base_harvester[ind] = [
            worker for worker in self.workers.closer_than(10, townhall)
            if not worker.is_carrying_vespene and not worker.is_constructing_scv
        ]

        for townhall in self.townhalls.ready.not_flying:
            ind = self.townhalls.not_flying.index(townhall)
            for worker in self.base_harvester[ind]:
                if worker.is_gathering:
                    if townhall.ideal_harvesters < len(self.base_harvester[ind]):
                        if len(self.base_harvester[ind]) - len(self.overmine_workers) > townhall.ideal_harvesters:
                            self.overmine_workers.append(worker)
        for townhall in self.townhalls:
            if townhall.ideal_harvesters > len(self.base_harvester[ind]):
                for worker in self.overmine_workers:
                    field = self.mineral_field.closer_than(10, townhall).random
                    self.do(worker.gather(field))
                    self.overmine_workers.remove(worker)




    async def expand(self):
        if self.can_afford(UnitTypeId.COMMANDCENTER) and not self.already_pending(UnitTypeId.COMMANDCENTER):
            if self.townhalls.amount == 1:
                CC_placement_pos = await self.find_placement(UnitTypeId.COMMANDCENTER, near=self.townhalls[0].position.towards(self.natural, 12))
            elif self.natural in self.blocked_locations:
                CC_placement_pos = await self.get_next_expansion()
            else:
                return
            if CC_placement_pos not in self.blocked_locations:
                if self.workers:
                    for worker in self.workers:
                        if worker.is_idle or worker.is_gathering:
                            self.do(worker.build(UnitTypeId.COMMANDCENTER, CC_placement_pos))



    async def replace_natural(self):
        if self.natural_was_taken == False:
            if self.structures(UnitTypeId.COMMANDCENTER).ready.amount + self.townhalls_flying.amount == 2:
                townhall = self.townhalls.closest_to(self.natural) 
                self.do(townhall(AbilityId.LIFT))
                for townhall in self.townhalls_flying:
                    townhall(AbilityId.LAND, self.natural)
                    self.natural_was_taken = True





    
def unique_file(file_path, ext):
    actualname = f"{file_path}.{ext}"
    c = 1
    while os.path.exists(actualname):
        actualname = f"{file_path}({c}).{ext}"
        c += 1
    return actualname


def main():
    map = random.choice(
        [
            "DeathAuraLE",
            "JagannathaLE",
            "LightshadeLE",
            "OxideLE",
            "PillarsofGoldLE",
            "RomanticideLE",
            "SubmarineLE",
            "EternalEmpireLE",
            "EverDreamLE",  
            "GoldenWallLE",  
            "IceandChromeLE", 
            "PillarsofGoldLE",
            "AcropolisLE",
            "DiscoBloodbathLE",
            "EphemeronLE",
            "ThunderbirdLE",
            "TritonLE",
            "WintersGateLE",
            "WorldofSleepersLE",
            ]
    )
    run_game(
        maps.get(map),
        [Bot(Race.Terran, DSC()), Computer(Race.Random, Difficulty.Hard)],
        realtime=False,
        save_replay_as= unique_file('replays/DSCRep', 'SC2Replay')
    )


if __name__ == "__main__":
    main()

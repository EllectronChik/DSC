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
    async def on_step(self, iteration):
        await self.train_workers()
        await self.build_supply()
        await self.build_barrack()
        await self.idles()
        await self.supply_cond()
        await self.speedmine(self.units(UnitTypeId.SCV))
        if self.time < 1:
            await self.split_workers()
#   find idles
    async def idles(self):          
        for worker in self.workers:
            if worker.is_idle:
                self.do(worker.gather(self.mineral_field.closest_to(self.townhalls[0])))

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
        for CC in self.structures(UnitTypeId.COMMANDCENTER).ready:
            if self.can_afford(UnitTypeId.SCV) and CC.is_idle and self.workers.amount < 88:
                self.do(CC.train(UnitTypeId.SCV))


#   build supply
    async def build_supply(self):
        depot_placement_positions: Set[Point2] = self.main_base_ramp.corner_depots
        depots: Units = self.structures.of_type({UnitTypeId.SUPPLYDEPOT, UnitTypeId.SUPPLYDEPOTLOWERED})
        if depots:
            depot_placement_positions: Set[Point2] = {
                dep for dep in depot_placement_positions if depots.closest_distance_to(dep) > 1
            }
        if self.structures(UnitTypeId.SUPPLYDEPOT).amount < 2 and self.supply_left < 5 and not self.already_pending(UnitTypeId.SUPPLYDEPOT):
            if self.can_afford(UnitTypeId.SUPPLYDEPOT):
                if len(depot_placement_positions) == 0:
                    return
                target_depot_location: Point2 = depot_placement_positions.pop()
                workers: Units = self.workers.gathering
                if workers: 
                    worker: Unit = workers.closest_to(target_depot_location)
                    if worker.is_idle or worker.is_gathering:
                        self.do(worker.build(UnitTypeId.SUPPLYDEPOT, target_depot_location))
                    else:
                        return
        if (self.structures(UnitTypeId.SUPPLYDEPOT).amount or self.structures(UnitTypeId.SUPPLYDEPOTLOWERED).amount >= 2) and self.supply_left < 6 and not self.already_pending (UnitTypeId.SUPPLYDEPOT)and self.can_afford(UnitTypeId.SUPPLYDEPOT):
                workers: Units = self.workers
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
        if (self.structures(UnitTypeId.SUPPLYDEPOT).ready or self.structures(UnitTypeId.SUPPLYDEPOTLOWERED).ready) and self.can_afford(UnitTypeId.BARRACKS) and self.already_pending(UnitTypeId.BARRACKS) == 0:
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
        if worker.is_carrying_minerals or (worker.is_carrying_vespene and self.gas_harvester_target == 2):
            target: Point2 = townhall.position.towards(worker, townhall.radius + worker.radius)
            if worker.distance_to(target) > 0.5:
                self.do(worker.move(target))
                self.do(worker(AbilityId.SMART, townhall, True))
                return
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
        [Bot(Race.Terran, DSC()), Computer(Race.Terran, Difficulty.Hard)],
        realtime=False,
        save_replay_as="replays/DSCRep.SC2Replay"
        # sc2_version="4.10.1",
    )


if __name__ == "__main__":
    main()

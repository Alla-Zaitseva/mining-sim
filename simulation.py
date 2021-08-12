import simpy
import random
import config
import json
from enum import Enum
from datetime import datetime, timedelta
from bisect import bisect_left
import numpy as np


def get_nearest_left(coord, explosions):
    keys = np.array(list(explosions.keys()))
    return keys[keys <= coord].max()

def get_nearest_right(coord, explosions):
    keys = np.array(list(explosions.keys()))
    return keys[keys >= coord].min()

def get_nearest(coord, explosions):
    if len(explosions) == 0:
        return -10000
    keys = np.array(list(explosions.keys()))
    if len(keys[keys <= coord]) == 0:
        return get_nearest_right(coord, explosions)
    if len(keys[keys >= coord]) == 0:
        return get_nearest_left(coord, explosions)

    nearest_left = get_nearest_left(coord, explosions)
    nearest_right = get_nearest_right(coord, explosions)

    if coord - nearest_left < nearest_right - coord:
        return nearest_left
    else:
        return nearest_right

class RepairCrew(object):
    class Status(Enum):
        VACANT = 1,
        REPAIRING = 2,
        MOVING = 3
        pass
    
    def __init__(self, env, speed, repair_time, start_coord, field):
        self.env = env
        self.speed = speed
        self.repair_time = repair_time
        self.status = self.Status.VACANT
        self.coord = start_coord
        self.field = field
        self.direction = 'Right'

    def update_coord(self):
        if self.status == self.Status.MOVING:
            # print('  -  Car coord prev: ', self.coord)
            road_time = self.env.now - self.prev_time
            if self.direction == 'Right':
                self.coord += int(road_time * self.speed)
            else:
                self.coord -= int(road_time * self.speed)
            # print('  -  Car coord now: ', self.coord)
            self.prev_time = self.env.now

    def setup(self):
        '''
        Логика ремонтной команды (машины)
        '''

        while True:
            if self.status == self.Status.VACANT:
                self.status = self.Status.MOVING
            elif self.status == self.Status.MOVING:
                while abs(get_nearest(self.coord, self.field.explosions) - self.coord) >= 10:

                    if self.direction == 'Right' and abs(config.ROAD_LENGTH - self.coord) <= 10:
                        self.direction = 'Left'
                    elif self.direction == 'Left' and abs(self.coord) <= 10:
                        self.direction = 'Right'
                    try:
                        if len(self.field.explosions_found) == 0:
                            if self.direction == 'Right':
                                explosions = self.field.explosions.copy()
                                explosions[config.ROAD_LENGTH] = 1
                                self.nearest_point = get_nearest_right(self.coord, explosions)
                                time = (self.nearest_point - self.coord) / self.speed
                                self.prev_time = self.env.now
                                yield self.env.timeout(time)
                            else:
                                explosions = self.field.explosions.copy()
                                explosions[0] = 1
                                nearest_point = get_nearest_left(self.coord, explosions)
                                time = (self.coord - nearest_point) / self.speed
                                self.prev_time = self.env.now
                                yield self.env.timeout(time)
                        else:
                            explosions = self.field.explosions.copy()
                            explosions[config.ROAD_LENGTH] = 1
                            explosions[0] = 1
                            nearest_right = get_nearest_right(self.coord, explosions)
                            nearest_left = get_nearest_left(self.coord, explosions)
                            if nearest_left == 0 or nearest_right - self.coord < self.coord - nearest_left:
                                self.nearest_point = nearest_right
                                self.direction = 'Right'
                                diff = nearest_right - self.coord
                            else:
                                self.nearest_point = nearest_left
                                self.direction = 'Left'
                                diff = self.coord - nearest_left
                            time = diff / self.speed
                            self.prev_time = self.env.now
                            yield self.env.timeout(time)
                    except simpy.Interrupt as i:
                        pass

                    self.update_coord()
                self.coord = get_nearest(self.coord, self.field.explosions)
                self.status = self.Status.REPAIRING
            elif self.status == self.Status.REPAIRING:
                print('---------------')
                print('   Repairing   ')
                print(' Coord: ', self.coord)
                print('---------------')
                explosion_id = self.field.explosions[self.coord]['ID']
                yield self.env.timeout(self.repair_time[explosion_id])
                del self.field.explosions[self.coord]
                self.field.explosions_found.pop(self.coord, None)
                self.status = self.Status.VACANT




        pass


class Dron(object):
    class Status(Enum):
        WAITING = 1,
        SEARCHING = 2,
        COMES_BACK = 3,
        CHARGING = 4
        pass

    def __init__(self, env, field, repair_crew, speed, flight_time, charging_time):
        self.env = env
        self.field = field
        self.repair_crew = repair_crew
        self.speed = speed
        self.flight_time = flight_time
        self.charging_time = charging_time
        self.status = self.Status.WAITING
        self.direction = 'Right'
        self.coord = self.repair_crew.coord
        self.t_search = (self.speed * self.flight_time) / (2 * self.speed + self.repair_crew.speed)
        self.t_back = self.flight_time - self.t_search

    def setup(self):
        '''
        Логика дрона
        '''

        while True:
            if self.status == self.Status.WAITING:
                self.status = self.Status.SEARCHING
                self.direction = 'Left'
            elif self.status == self.Status.SEARCHING:

                if self.direction == 'Right' and abs(self.coord - config.ROAD_LENGTH) <= 10:
                    self.direction = 'Left'
                elif self.direction == 'Left' and abs(self.coord - 0) <= 10:
                    self.direction = 'Right'

                self.real_time = 0
                while abs(self.t_search - self.real_time) >= 5:

                    if self.direction == 'Right':
                        explosions = self.field.explosions.copy()
                        explosions[config.ROAD_LENGTH] = 1
                        self.nearest_point = get_nearest_right(self.coord, explosions)
                        time = (self.nearest_point - self.coord) / self.speed
                    else:
                        explosions = self.field.explosions.copy()
                        explosions[0] = 1
                        nearest_point = get_nearest_left(self.coord, explosions)
                        time = (self.coord - nearest_point) / self.speed
                    time = min(self.t_search - self.real_time, time)
                    if abs(time) < 2:
                       break
                    self.prev_time = self.env.now
                    try:
                        yield self.env.timeout(time)
                    except simpy.Interrupt as i:
                        pass
                    delta = self.env.now - self.prev_time
                    self.real_time += delta
                    if self.direction == 'Right':
                        self.coord += int(delta * self.speed)
                    else:
                        self.coord -= int(delta * self.speed)
                    nearest_point = get_nearest(self.coord, self.field.explosions)
                    if abs(self.coord - nearest_point) <= 10:
                        self.field.explosions_found[nearest_point] = self.field.explosions[nearest_point]
                        if self.repair_crew.status == self.repair_crew.Status.MOVING:
                            self.field.crew_proc.interrupt('')
                    self.repair_crew.update_coord()

                self.status = self.Status.COMES_BACK
            elif self.status == self.Status.COMES_BACK:
                if self.direction == 'Right':
                    self.direction = 'Left'
                else:
                    self.direction = 'Right'
                self.real_time = 0
                while abs(self.coord - self.repair_crew.coord) >= 10:

                    self.repair_crew.update_coord()

                    if self.direction == 'Right':
                        explosions = self.field.explosions.copy()
                        explosions[self.repair_crew.coord] = 1
                        explosions[config.ROAD_LENGTH] = 1
                        nearest_point = get_nearest_right(self.coord, explosions)
                        time = (nearest_point - self.coord) / self.speed
                    else:
                        explosions = self.field.explosions.copy()
                        explosions[0] = 1
                        explosions[self.repair_crew.coord] = 1
                        nearest_point = get_nearest_left(self.coord, explosions)
                        time = (self.coord - nearest_point) / self.speed
                    time = min(self.t_back - self.real_time, time)
                    self.prev_time = self.env.now
                    try:
                        yield self.env.timeout(time)
                    except simpy.Interrupt as i:
                        pass
                    delta = self.env.now - self.prev_time
                    self.real_time += delta
                    if self.direction == 'Right':
                        self.coord += int(delta * self.speed)
                    else:
                        self.coord -= int(delta * self.speed)
                    nearest_point = get_nearest(self.coord, self.field.explosions)
                    if abs(self.coord - nearest_point) <= 10:
                        self.field.explosions_found[nearest_point] = self.field.explosions[nearest_point]
                    if self.direction == 'Right' and self.coord < self.repair_crew.coord:
                        break
                    elif self.direction == 'Left' and self.coord > self.repair_crew.coord:
                        break

                self.coord = self.repair_crew.coord
                self.status = self.Status.CHARGING
            elif self.status == self.Status.CHARGING:
                yield self.env.timeout(self.charging_time)
                self.repair_crew.update_coord()
                self.coord = self.repair_crew.coord
                self.status = self.Status.SEARCHING





        pass


class Field(object):
    def __init__(self, env):
        self.env = env
        # Объект служба ремонта (машина)
        self.crew = RepairCrew(env, config.REPAIRING_CREW_SPEED, config.REPAIRING_TIME, config.REPAIRING_CREW_START_COORD, self)
        # Объект дрон
        self.drone = Dron(env, self, self.crew, config.DRON_SPEED, config.DRON_FLIGHT_TIME, config.DRON_CHARGING_TIME)

        # Это словарик, который будет хранить реальные неустраненные взрывы
        #   Ключ - координата
        #   Значение - взрыв из json файла
        # 
        # Пример:
        # {
        #     "ID": 4,
        #     "Time": "00:00:44",
        #     "Coord": 866
        # }
        self.explosions = {}
        
        # Это словарик, который будет хранить обнаруженные неустранненые взрывы
        self.explosions_found = {}
        
        # Загружаем файлик расписания взрывов
        with open(config.PATH_TO_EXPLOSIONS_CONFIG, 'r') as file:
            self.explosions_timetable = json.load(file)
    
    def explosion_generator(self):
        '''
        Функция которая генерирует в нужные времена взрывы
        '''
        current_time = datetime.strptime(config.START_TIME, config.TIME_FORMAT)

        for explosion in self.explosions_timetable['Events']:
            time = datetime.strptime(explosion['Time'], config.TIME_FORMAT)
            delta = (time - current_time).seconds
            current_time = time

            yield self.env.timeout(delta)

            print(explosion)
            self.explosions[explosion['Coordinates']] = explosion
            if self.crew.status == self.crew.Status.MOVING:
                self.crew_proc.interrupt('')
            if self.drone.status == self.drone.Status.SEARCHING or self.drone.status == self.drone.Status.COMES_BACK:
                self.dron_proc.interrupt('')

        pass
    
    def setup(self):
        '''
        Логика поля
        '''
        
        self.expl_gen = self.env.process(self.explosion_generator())
        self.dron_proc = self.env.process(self.drone.setup())
        self.crew_proc = self.env.process(self.crew.setup())


        pass


def simulate():
    env = simpy.Environment()
    field = Field(env)

    field.setup()

    env.run(until=config.MODELING_TIME)
    pass

import simpy
import random
import config
import json
from enum import Enum
from datetime import datetime, timedelta
from bisect import bisect_left
import numpy as np


def get_found_explosions(explosions, respons):
    new_explosions = {}
    for explosion_coord, explosion in explosions.items():
        if explosion.get('ID', 0) in respons:
            new_explosions[explosion_coord] = explosion
    return new_explosions

def get_nearest_left(coord, explosions, respons, including=True):
    new_explosions = get_found_explosions(explosions, respons)
    keys = np.array(list(new_explosions.keys()))
    if including:
        return keys[keys <= coord].max()
    else:
        return keys[keys < coord].max()

def get_nearest_right(coord, explosions, respons, including=True):
    new_explosions = get_found_explosions(explosions, respons)
    keys = np.array(list(new_explosions.keys()))
    if including:
        return keys[keys >= coord].min()
    else:
        return keys[keys > coord].min()

def get_nearest(coord, explosions, respons):
    new_explosions = get_found_explosions(explosions, respons)
    if len(new_explosions) == 0:
        return -10000
    keys = np.array(list(new_explosions.keys()))
    if len(keys[keys <= coord]) == 0:
        return get_nearest_right(coord, new_explosions, respons)
    if len(keys[keys >= coord]) == 0:
        return get_nearest_left(coord, new_explosions, respons)

    nearest_left = get_nearest_left(coord, explosions, respons)
    nearest_right = get_nearest_right(coord, explosions, respons)

    if coord - nearest_left < nearest_right - coord:
        return nearest_left
    else:
        return nearest_right

def get_current_time_str(env):
    current_time = datetime(year=1, month=1, day=1, hour=0, minute=0, second=0) + timedelta(seconds=int(env.now))
    return current_time.strftime(config.TIME_FORMAT)

class RepairCrew(object):
    class Status(Enum):
        VACANT = 1,
        REPAIRING = 2,
        MOVING = 3
        pass
    
    def __init__(self, env, name, speed, repair_time, start_coord, field, respons):
        self.name = name
        self.env = env
        self.speed = speed
        self.repair_time = repair_time
        self.status = self.Status.VACANT
        self.coord = start_coord
        self.field = field
        self.respons = respons
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
            if config.DEBUG:
                print('#debug# Внутри цикла', self.name)
            
            if self.status == self.Status.VACANT:
                self.status = self.Status.MOVING
            elif self.status == self.Status.MOVING:
                while abs(get_nearest(self.coord, self.field.explosions, self.respons) - self.coord) >= 10:
                    if self.direction == 'Right' and abs(config.ROAD_LENGTH - self.coord) <= 10:
                        self.direction = 'Left'
                    elif self.direction == 'Left' and abs(self.coord) <= 10:
                        self.direction = 'Right'
                    try:
                        if config.DEBUG:
                            print('#debug#', self.name)
                            print('#debug#', get_found_explosions(self.field.explosions_found, self.respons))
                            # print('#debug#', self.field.explosions_found)
                        if len(get_found_explosions(self.field.explosions_found, self.respons)) == 0:
                            if self.direction == 'Right':
                                explosions = self.field.explosions.copy()
                                explosions[config.ROAD_LENGTH] = {}
                                self.nearest_point = get_nearest_right(self.coord, explosions, self.respons)
                                time = (self.nearest_point - self.coord) / self.speed
                                self.prev_time = self.env.now
                                yield self.env.timeout(time)
                            else:
                                explosions = self.field.explosions.copy()
                                explosions[0] = {}
                                nearest_point = get_nearest_left(self.coord, explosions, self.respons)
                                time = (self.coord - nearest_point) / self.speed
                                self.prev_time = self.env.now
                                yield self.env.timeout(time)
                        else:
                            explosions = self.field.explosions.copy()
                            explosions[0] = {}
                            explosions[config.ROAD_LENGTH] = {}
                            nearest_right = get_nearest_right(self.coord, explosions, self.respons)
                            nearest_left = get_nearest_left(self.coord, explosions, self.respons)
                            self.nearest_point = get_nearest(self.coord, self.field.explosions_found, self.respons)

                            if self.coord < self.nearest_point:
                                self.nearest_point = nearest_right
                                self.direction = 'Right'
                                diff = self.nearest_point - self.coord
                            else:
                                self.nearest_point = nearest_left
                                self.direction = 'Left'
                                diff = self.coord - self.nearest_point
                            time = diff / self.speed
                            self.prev_time = self.env.now
                            yield self.env.timeout(time)
                    except simpy.Interrupt as i:
                        pass

                    self.update_coord()
                self.coord = get_nearest(self.coord, self.field.explosions, self.respons)
                self.status = self.Status.REPAIRING
            elif self.status == self.Status.REPAIRING:
                if config.DEBUG:
                    print('#debug# repairing', self.name)
                explosion_id = self.field.explosions[self.coord]['ID']
                print('{} {} "{}" "начало ремонта МВЗ типа {}"'.format(get_current_time_str(self.env), self.coord, self.name,
                                                                  explosion_id))
                yield self.env.timeout(self.repair_time[explosion_id])
                print('{} {} "{}" "окончание ремонта МВЗ типа {}"'.format(get_current_time_str(self.env), self.coord, self.name,
                                                                  explosion_id))
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

    def __init__(self, env, name, field, repair_crew, speed, flight_time, charging_time):
        self.env = env
        self.name = name
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
            if config.DEBUG:
                print('#debug# Внутри цикла', self.name)
            if self.status == self.Status.WAITING:
                self.status = self.Status.SEARCHING
                self.direction = 'Left'
            elif self.status == self.Status.SEARCHING:
                print('{} {} "{}" "начало патрулирования БПЛА"'.format(get_current_time_str(self.env),
                                                                       self.coord,
                                                                       self.name))

                if self.direction == 'Right' and abs(self.coord - config.ROAD_LENGTH) <= 10:
                    self.direction = 'Left'
                elif self.direction == 'Left' and abs(self.coord - 0) <= 10:
                    self.direction = 'Right'
                self.real_time = 0
                while abs(self.t_search - self.real_time) >= 5:
                    if config.DEBUG:
                        print('#debug# внутри цикла searching', self.name)
                    if self.direction == 'Right':
                        explosions = self.field.explosions.copy()
                        explosions[config.ROAD_LENGTH] = {}
                        self.nearest_point = get_nearest_right(self.coord, explosions, [0, 1, 2, 3, 4])
                        time = (self.nearest_point - self.coord) / self.speed
                    else:
                        explosions = self.field.explosions.copy()
                        explosions[0] = {}
                        nearest_point = get_nearest_left(self.coord, explosions, [0, 1, 2, 3, 4])
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
                    nearest_point = get_nearest(self.coord, self.field.explosions, [0, 1, 2, 3, 4])
                    if abs(self.coord - nearest_point) <= 10:
                        self.field.explosions_found[nearest_point] = self.field.explosions[nearest_point]
                        print('{} {} "{}" "обнаружен взрыв типа {}"'.format(get_current_time_str(self.env),
                                                                            nearest_point,
                                                                            self.name,
                                                                            self.field.explosions_found[nearest_point]['ID']))
                        if self.field.crew.status == self.field.crew.Status.MOVING:
                            self.field.crew_proc.interrupt('')
                        if self.field.crew_2.status == self.field.crew_2.Status.MOVING:
                            self.field.crew_proc_2.interrupt('')
                    self.repair_crew.update_coord()

                self.status = self.Status.COMES_BACK
            elif self.status == self.Status.COMES_BACK:
                self.repair_crew.update_coord()

                if self.coord > self.repair_crew.coord:
                    self.direction = 'Left'
                else:
                    self.direction = 'Right'
                
                if config.DEBUG:
                    print('#Debug# {} "{}" разворот теперь в {}'.format(get_current_time_str(self.env), self.name, self.direction))

                self.real_time = 0
                while abs(self.coord - self.repair_crew.coord) >= 10:
                    self.repair_crew.update_coord()
                    
                    if self.direction == 'Right':
                        if config.DEBUG:
                            print('#debug# Right')
                        explosions = self.field.explosions.copy()
                        explosions.pop(self.coord, 0)
                        explosions[self.repair_crew.coord] = {}
                        explosions[config.ROAD_LENGTH] = {}
                        nearest_point = get_nearest_right(self.coord, explosions, [0, 1, 2, 3, 4], including=True)
                        time = (nearest_point - self.coord) / self.speed
                    else:
                        if config.DEBUG:
                            print('#debug# Left')
                        explosions = self.field.explosions.copy()
                        explosions.pop(self.coord, 0)
                        explosions[0] = {}
                        explosions[self.repair_crew.coord] = {}
                        nearest_point = get_nearest_left(self.coord, explosions, [0, 1, 2, 3, 4], including=True)
                        time = (self.coord - nearest_point) / self.speed
                    time = min(self.t_back - self.real_time, time)
                    self.prev_time = self.env.now

                    if config.DEBUG:
                        print('#debug# внутри цикла comes back', self.name)
                        print('#debug#', self.coord, nearest_point, self.repair_crew.coord)

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
                    nearest_point = get_nearest(self.coord, self.field.explosions, [0, 1, 2, 3, 4])
                    if abs(self.coord - nearest_point) <= 10:
                        self.field.explosions_found[nearest_point] = self.field.explosions[nearest_point]
                        self.coord = nearest_point
                    if self.direction == 'Right' and self.coord >= self.repair_crew.coord:
                        break
                    elif self.direction == 'Left' and self.coord <= self.repair_crew.coord:
                        break

                self.coord = self.repair_crew.coord
                self.status = self.Status.CHARGING
            elif self.status == self.Status.CHARGING:
                print('{} {} "{}" "окончание патрулирования БПЛА"'.format(get_current_time_str(self.env),
                                                                          self.coord,
                                                                          self.name))
                yield self.env.timeout(self.charging_time)
                self.repair_crew.update_coord()
                self.coord = self.repair_crew.coord
                self.status = self.Status.SEARCHING





        pass


class Field(object):
    def __init__(self, env, need_drone):
        self.env = env
        self.need_drone = need_drone
        # Объект служба ремонта (машина)
        self.crew = RepairCrew(env, 'Машина 1', config.REPAIRING_CREW_SPEED, config.REPAIRING_TIME,
                               config.REPAIRING_CREW_START_COORD, self, [0, 1, 2])
        self.crew_2 = RepairCrew(env, 'Машина 2', config.REPAIRING_CREW_SPEED, config.REPAIRING_TIME,
                               config.REPAIRING_CREW_START_COORD, self, [0, 3, 4])

        if self.need_drone:
            # Объект дрон
            self.drone = Dron(env, 'Дрон', self, self.crew, config.DRON_SPEED, config.DRON_FLIGHT_TIME, config.DRON_CHARGING_TIME)

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

            print('{} {} "взрыв типа {}"'.format(explosion['Time'], explosion['Coordinates'], explosion['ID']))
            self.explosions[explosion['Coordinates']] = explosion
            if self.crew.status == self.crew.Status.MOVING:
                self.crew_proc.interrupt('')
            if self.need_drone:
                if self.drone.status == self.drone.Status.SEARCHING or self.drone.status == self.drone.Status.COMES_BACK:
                    self.dron_proc.interrupt('')

        pass
    
    def setup(self):
        '''
        Логика поля
        '''
        
        self.expl_gen = self.env.process(self.explosion_generator())
        if self.need_drone:
            self.dron_proc = self.env.process(self.drone.setup())
        self.crew_proc = self.env.process(self.crew.setup())
        self.crew_proc_2 = self.env.process(self.crew_2.setup())


        pass


def simulate():
    env = simpy.Environment()
    field = Field(env, True)   # bool переменная - отвечает за то, нужен ли дрон

    field.setup()

    env.run(until=config.MODELING_TIME)
    pass

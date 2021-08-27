import simpy
import random
import config
import json
from enum import Enum
from datetime import datetime, timedelta
import numpy as np


class Logger:
    def __init__(self, filepath):
        self.file = open(filepath, 'wb')

    def log(self, *objects):
        objects = [str(object) for object in objects]
        self.file.write((' '.join(objects)).encode('utf-8'))
        self.file.write(b'\n')

    def close(self):
        self.file.close()

logger = None

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
            # logger.log('  -  Car coord prev: ', self.coord)
            road_time = self.env.now - self.prev_time
            if self.direction == 'Right':
                self.coord += int(road_time * self.speed)
            else:
                self.coord -= int(road_time * self.speed)
            # logger.log('  -  Car coord now: ', self.coord)
            self.prev_time = self.env.now

    def setup(self):
        '''
        Логика ремонтной команды (машины)
        '''

        while True:
            if config.DEBUG:
                logger.log('#debug# Внутри цикла', self.name)
            
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
                            logger.log('#debug#', self.name)
                            logger.log('#debug#', get_found_explosions(self.field.explosions_found, self.respons))
                            # logger.log('#debug#', self.field.explosions_found)
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
                    logger.log('#debug# repairing', self.name)
                explosion_id = self.field.explosions[self.coord]['ID']
                logger.log('{} {} "{}" "начало ремонта МВЗ типа {}"'.format(get_current_time_str(self.env), self.coord, self.name,
                                                                  explosion_id))
                yield self.env.timeout(self.repair_time[explosion_id])
                logger.log('{} {} "{}" "окончание ремонта МВЗ типа {}"'.format(get_current_time_str(self.env), self.coord, self.name,
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
        self.t_search = (self.speed * self.flight_time) / (2 * self.speed + self.repair_crew.speed) - 200  # FIXME: remove this fucking shit
        self.t_back = self.flight_time - self.t_search + 200  # FIXME: here too

    def setup(self):
        '''
        Логика дрона
        '''

        while True:
            if config.DEBUG:
                logger.log('#debug# Внутри цикла', self.name)
            if self.status == self.Status.WAITING:
                self.status = self.Status.SEARCHING
                self.direction = 'Left'
            elif self.status == self.Status.SEARCHING:
                logger.log('{} {} "{}" "начало патрулирования БПЛА"'.format(get_current_time_str(self.env),
                                                                       self.coord,
                                                                       self.name))

                if self.direction == 'Right' and abs(self.coord - config.ROAD_LENGTH) <= 10:
                    self.direction = 'Left'
                elif self.direction == 'Left' and abs(self.coord - 0) <= 10:
                    self.direction = 'Right'
                self.real_time = 0
                while abs(self.t_search - self.real_time) >= 5:
                    if config.DEBUG:
                        logger.log('#debug# внутри цикла searching', self.name)
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
                        logger.log('{} {} "{}" "обнаружен взрыв типа {}"'.format(get_current_time_str(self.env),
                                                                            nearest_point,
                                                                            self.name,
                                                                            self.field.explosions_found[nearest_point]['ID']))
                        for crew in self.field.crews.values():
                            if crew['crew'].status == RepairCrew.Status.MOVING:
                                crew['process'].interrupt('')
                            
                    self.repair_crew.update_coord()

                self.status = self.Status.COMES_BACK
            elif self.status == self.Status.COMES_BACK:
                self.repair_crew.update_coord()

                if self.coord > self.repair_crew.coord:
                    self.direction = 'Left'
                else:
                    self.direction = 'Right'
                
                if config.DEBUG:
                    logger.log('#Debug# {} "{}" разворот теперь в {}'.format(get_current_time_str(self.env), self.name, self.direction))
                    logger.log('#debug#', self.coord, self.repair_crew.coord)
                    logger.log('#debug#', self.t_back)
                self.real_time = 0
                while abs(self.coord - self.repair_crew.coord) >= 10:
                    self.repair_crew.update_coord()
                    
                    if self.direction == 'Right':
                        if config.DEBUG:
                            logger.log('#debug# Right')
                        explosions = self.field.explosions.copy()
                        explosions.pop(self.coord, 0)
                        explosions[self.repair_crew.coord] = {}
                        explosions[config.ROAD_LENGTH] = {}
                        nearest_point = get_nearest_right(self.coord, explosions, [0, 1, 2, 3, 4], including=True)
                        time = (nearest_point - self.coord) / self.speed
                    else:
                        if config.DEBUG:
                            logger.log('#debug# Left')
                        explosions = self.field.explosions.copy()
                        explosions.pop(self.coord, 0)
                        explosions[0] = {}
                        explosions[self.repair_crew.coord] = {}
                        nearest_point = get_nearest_left(self.coord, explosions, [0, 1, 2, 3, 4], including=True)
                        time = (self.coord - nearest_point) / self.speed
                    time = min(self.t_back - self.real_time, time)
                    self.prev_time = self.env.now

                    if config.DEBUG:
                        logger.log('#debug# внутри цикла comes back', self.name)
                        logger.log('#debug#', self.coord, nearest_point, self.repair_crew.coord)
                        logger.log('#debug#', self.t_back - self.real_time)

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
                logger.log('{} {} "{}" "окончание патрулирования БПЛА"'.format(get_current_time_str(self.env),
                                                                          self.coord,
                                                                          self.name))
                yield self.env.timeout(self.charging_time)
                self.repair_crew.update_coord()
                self.coord = self.repair_crew.coord
                self.status = self.Status.SEARCHING
        pass


class Field(object):
    def __init__(self, env, config_json, explosions_timetable):
        self.env = env

        self.crews = {}
        self.drones = {}

        for crew_name, crew_params in config_json['repairing_crews'].items():
            self.crews[crew_name] = {
                'crew' : RepairCrew(env,
                                    crew_name,
                                    config.REPAIRING_CREW_SPEED,
                                    config.REPAIRING_TIME,
                                    config.REPAIRING_CREW_START_COORD,
                                    self,
                                    crew_params['responsibility'])
            }

        for drone_name, drone_params in config_json['drones'].items():
            self.drones[drone_name] = {
                'drone' : Dron(env,
                            drone_name,
                            self,
                            self.crews[drone_params['repairing_crew_connected_to']]['crew'],
                            config.DRON_SPEED,
                            config.DRON_FLIGHT_TIME,
                            config.DRON_CHARGING_TIME)
            }

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
        self.explosions_timetable = explosions_timetable
    
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

            logger.log('{} {} "взрыв типа {}"'.format(explosion['Time'], explosion['Coordinates'], explosion['ID']))

            self.explosions[explosion['Coordinates']] = explosion
            for crew in self.crews.values():
                if crew['crew'].status == RepairCrew.Status.MOVING:
                    crew['process'].interrupt('')
            for drone in self.drones.values():
                if drone['drone'].status == Dron.Status.SEARCHING or drone['drone'].status == Dron.Status.COMES_BACK:
                    drone['process'].interrupt('')

        pass
    
    def setup(self):
        '''
        Логика поля
        '''
        
        self.expl_gen = self.env.process(self.explosion_generator())

        for drone in self.drones.values():
            drone['process'] = self.env.process(drone['drone'].setup())
        for crew in self.crews.values():
            crew['process'] = self.env.process(crew['crew'].setup())

        pass

def simulate(config_json):
    params = config_json['params']
    config.ROAD_LENGTH = params['road_length']
    config.REPAIRING_CREW_SPEED = params['repairing_crew_speed']
    config.REPAIRING_CREW_START_COORD = params['repairing_crew_start_coord']
    config.DRON_SPEED = params['drone_speed']
    config.DRON_FLIGHT_TIME = params['drone_flight_time']
    config.DRON_CHARGING_TIME = params['drone_charging_time']
    config.REPAIRING_TIME = params['repairing_time']

    def simulate_start(explosions_timetable):
        env = simpy.Environment()
        field = Field(env, config_json, explosions_timetable)

        field.setup()

        env.run(until=config.MODELING_TIME)
    
    for input_path in config_json['explosions_files']:
        output_path = input_path[:-5] + '_output.txt'
        global logger
        logger = Logger(output_path)

        with open(input_path, 'r') as f:
            explosions_timetable = json.load(f)
        simulate_start(explosions_timetable)

        logger.close()
        logger = None
    
    pass

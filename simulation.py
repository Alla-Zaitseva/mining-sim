import simpy
import random
import config
import json
from dicttoxml import dicttoxml
from enum import Enum
from datetime import datetime, timedelta
import numpy as np


class Logger:
    def __init__(self, txt_path, json_path, xml_path):
        self.txt_file = open(txt_path, 'w')
        self.json_path = json_path
        self.xml_path = xml_path
        self.json_file_content = {
            'logs' : []
        }

    def log(self, time, coord, name, message):
        self.txt_file.write('{} {} "{}" "{}"'.format(time, coord, name, message))
        self.txt_file.write('\n')

        json_log = {
            'time' : str(time),
            'coordinate' : int(coord),
            'object_name' : str(name),
            'message' : message
        }
        self.json_file_content['logs'].append(json_log)

    def close(self):
        self.txt_file.close()
        
        with open(self.json_path, 'w') as f:
            f.write(json.dumps(self.json_file_content, indent=4, ensure_ascii=False))
        
        xml = dicttoxml(self.json_file_content, custom_root='test', attr_type=False)
        with open(self.xml_path, 'wb') as f:
            f.write(xml)


'''
This is class for repair crew contol
:methods:
    choose_explosion_to_move - this method is main control point of repair crew
'''
class RepairCrewControlMove:
    @staticmethod
    def choose_explosion_to_move(coordinate_now, explosions_found, respons):
        '''
        :input:
            coordinate_now - current coordinate of repair crew
            explosions_found - explosions found
            repsons - list of ID explosions, that repair crew can repair
        :return:
            coordinate of point to move
        '''
        point_to_move = get_nearest(coordinate_now, explosions_found, respons)
        return point_to_move





logger = None

def get_found_explosions(explosions, respons):
    new_explosions = {}
    for explosion_coord, explosion in explosions.items():
        if explosion.get('ID', 0) in respons and explosion.get('vacant', True):
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

def get_direction_rus(direction):
    if direction == 'Left':
        return 'налево'
    else:
        return 'направо'


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
        self.point_to_move = None

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
            # if config.DEBUG:
            #     logger.log('#debug# Внутри цикла', self.name)
            
            if self.status == self.Status.VACANT:
                self.status = self.Status.MOVING
            elif self.status == self.Status.MOVING:
                logger.log(get_current_time_str(self.env), self.coord, self.name, "начало марша {}".format(get_direction_rus(self.direction)))
                while abs(get_nearest(self.coord, self.field.explosions, self.respons) - self.coord) >= 10:
                    if self.direction == 'Right' and abs(config.ROAD_LENGTH - self.coord) <= 10:
                        self.direction = 'Left'
                        logger.log(get_current_time_str(self.env), self.coord, self.name, "окончание марша")
                        logger.log(get_current_time_str(self.env), self.coord, self.name, "начало марша {}".format(get_direction_rus(self.direction)))
                    elif self.direction == 'Left' and abs(self.coord) <= 10:
                        self.direction = 'Right'
                        logger.log(get_current_time_str(self.env), self.coord, self.name, "окончание марша")
                        logger.log(get_current_time_str(self.env), self.coord, self.name, "начало марша {}".format(get_direction_rus(self.direction)))
                    try:
                        # if config.DEBUG:
                            # logger.log('#debug#', self.name)
                            # logger.log('#debug#', get_found_explosions(self.field.explosions_found, self.respons))
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
                            # Here is selections between founded explosions
                            explosions = self.field.explosions.copy()
                            explosions[0] = {}
                            explosions[config.ROAD_LENGTH] = {}
                            nearest_right = get_nearest_right(self.coord, explosions, self.respons)
                            nearest_left = get_nearest_left(self.coord, explosions, self.respons)
                            self.point_to_move = RepairCrewControlMove.choose_explosion_to_move(self.coord, self.field.explosions_found, self.respons)
                            self.field.explosions_found[self.point_to_move]['vacant'] = False
                            self.field.explosions[self.point_to_move]['vacant'] = False

                            if self.coord < self.point_to_move:
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
                if (self.point_to_move is not None) and (self.coord != self.point_to_move):
                    self.field.explosions_found[self.point_to_move]['vacant'] = True
                    self.field.explosions[self.point_to_move]['vacant'] = True
                
                self.field.explosions_found[self.coord] = self.field.explosions[self.coord]
                
                self.point_to_move = None
                self.field.explosions_found[self.coord]['vacant'] = False
                self.field.explosions[self.coord]['vacant'] = False

                if config.DEBUG:
                    logger.log('#debug# repairing', self.name)
                explosion_id = self.field.explosions[self.coord]['ID']
                logger.log(get_current_time_str(self.env), self.coord, self.name, "окончание марша")
                logger.log(get_current_time_str(self.env), self.coord, self.name, "начало ремонта МВЗ типа {}".format(explosion_id))
                yield self.env.timeout(self.repair_time[explosion_id])
                logger.log(get_current_time_str(self.env), self.coord, self.name, "окончание ремонта МВЗ типа {}".format(explosion_id))
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
        self.t_search = (self.speed * self.flight_time - self.repair_crew.speed * self.flight_time) / (2 * self.speed)
        self.t_back = self.flight_time - self.t_search

    def setup(self):
        '''
        Логика дрона
        '''

        while True:
            # if config.DEBUG:
            #     logger.log('#debug# Внутри цикла', self.name)
            if self.status == self.Status.WAITING:
                self.status = self.Status.SEARCHING
                self.direction = 'Left'
            elif self.status == self.Status.SEARCHING:
                logger.log(get_current_time_str(self.env), self.coord, self.name, "начало патрулирования БПЛА")

                if self.direction == 'Right' and abs(self.coord - config.ROAD_LENGTH) <= 10:
                    self.direction = 'Left'
                elif self.direction == 'Left' and abs(self.coord - 0) <= 10:
                    self.direction = 'Right'
                self.real_time = 0
                while abs(self.t_search - self.real_time) >= 5:
                    # if config.DEBUG:
                    #     logger.log('#debug# внутри цикла searching', self.name)
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
                        logger.log(get_current_time_str(self.env), nearest_point, self.name, "обнаружен взрыв типа {}".format(self.field.explosions_found[nearest_point]['ID']))
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
                
                # if config.DEBUG:
                #     logger.log('#Debug# {} "{}" разворот теперь в {}'.format(get_current_time_str(self.env), self.name, self.direction))
                #     logger.log('#debug#', self.coord, self.repair_crew.coord)
                #     logger.log('#debug#', self.t_back)
                self.real_time = 0
                while abs(self.coord - self.repair_crew.coord) >= 10:
                    self.repair_crew.update_coord()
                    
                    if self.direction == 'Right':
                        # if config.DEBUG:
                        #     logger.log('#debug# Right')
                        explosions = self.field.explosions.copy()
                        explosions.pop(self.coord, 0)
                        explosions[self.repair_crew.coord] = {}
                        explosions[config.ROAD_LENGTH] = {}
                        nearest_point = get_nearest_right(self.coord, explosions, [0, 1, 2, 3, 4], including=True)
                        time = (nearest_point - self.coord) / self.speed
                    else:
                        # if config.DEBUG:
                        #     logger.log('#debug# Left')
                        explosions = self.field.explosions.copy()
                        explosions.pop(self.coord, 0)
                        explosions[0] = {}
                        explosions[self.repair_crew.coord] = {}
                        nearest_point = get_nearest_left(self.coord, explosions, [0, 1, 2, 3, 4], including=True)
                        time = (self.coord - nearest_point) / self.speed
                    time = min(self.t_back - self.real_time, time)
                    self.prev_time = self.env.now

                    # if config.DEBUG:
                    #     logger.log('#debug# внутри цикла comes back', self.name)
                    #     logger.log('#debug#', self.coord, nearest_point, self.repair_crew.coord)
                    #     logger.log('#debug#', self.t_back - self.real_time)

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
                logger.log(get_current_time_str(self.env), self.coord, self.name, "окончание патрулирования БПЛА")
                yield self.env.timeout(self.charging_time)
                self.repair_crew.update_coord()
                self.coord = self.repair_crew.coord
                self.status = self.Status.SEARCHING
        pass

class Transit(object):
    def __init__(self, env, name, speed, field):
        self.env = env
        self.name = name
        self.speed = speed
        self.coord = 0
        self.field = field
    
    def setup(self):
        # TODO: why is simulation too long?
        logger.log(get_current_time_str(self.env), self.coord, self.name, "колонна начала движение")
        while True:
            explosions = self.field.explosions.copy()
            explosions[config.ROAD_LENGTH] = {}
            self.nearest_point = get_nearest_right(self.coord, explosions, [0, 1, 2, 3, 4], including=False)
            
            time = (self.nearest_point - self.coord) / self.speed

            self.prev_time = self.env.now
            try:
                yield self.env.timeout(time)
            except simpy.Interrupt as i:
                pass

            delta = self.env.now - self.prev_time
            self.coord += int(delta * self.speed)

            if abs(self.coord - config.ROAD_LENGTH) <= 10:
                break

            explosions = self.field.explosions.copy()
            explosions[config.ROAD_LENGTH] = {}
            nearest_point_now = get_nearest(self.coord, explosions, [0, 1, 2, 3, 4])

            if abs(self.coord - nearest_point_now) <= 10 and nearest_point_now not in self.field.explosions_found:
                self.field.explosions_found[nearest_point_now] = self.field.explosions[nearest_point_now]
                self.coord = nearest_point_now
                logger.log(get_current_time_str(self.env), nearest_point_now, self.name, "обнаружен взрыв типа {}".format(self.field.explosions[nearest_point_now]['ID']))
            
        logger.log(get_current_time_str(self.env), self.coord, self.name, "колонна закончила движение")

        self.delete()

    def delete(self):
        del self.field.transits[self.name]

        

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

        self.transits = {}
    
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

            logger.log(explosion['Time'], explosion['Coordinates'], 'Взрыв', "взрыв типа {}".format(explosion['ID']))

            self.explosions[explosion['Coordinates']] = explosion
            for crew in self.crews.values():
                if crew['crew'].status == RepairCrew.Status.MOVING:
                    crew['process'].interrupt('')
            for drone in self.drones.values():
                if drone['drone'].status == Dron.Status.SEARCHING or drone['drone'].status == Dron.Status.COMES_BACK:
                    drone['process'].interrupt('')
            for transit in self.transits.values():
                transit['process'].interrupt('')

        pass

    def transit_generator(self):
        '''
        Функция которая генерирует в нужные времена колонну
        '''
        time_to_sleep = config.TRANSIT_FREQUENCY

        i = 1
        while True:
            name = "transit_" + str(i)
            self.transits[name] = {
                'transit' : Transit(self.env,
                                    name,
                                    config.TRANSIT_SPEED,
                                    self)
            }
            self.transits[name]['process'] = self.env.process(self.transits[name]['transit'].setup())
            
            yield self.env.timeout(time_to_sleep)
            i += 1
            
    
    def setup(self):
        '''
        Логика поля
        '''
        
        self.expl_gen = self.env.process(self.explosion_generator())
        self.trans_gen = self.env.process(self.transit_generator())

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
        txt_path = input_path[:-5] + '_output.txt'
        json_path = input_path[:-5] + '_output.json'
        xml_path = input_path[:-5] + '_output.xml'
        global logger
        logger = Logger(txt_path, json_path, xml_path)

        with open(input_path, 'r') as f:
            explosions_timetable = json.load(f)
        simulate_start(explosions_timetable)

        logger.close()
        logger = None
    
    pass

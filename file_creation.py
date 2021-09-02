import json
import random
from datetime import datetime, timedelta


def generate_explosions_files(config):
    length = config['road_length']

    probabilities = {}
    for explosion in config['explosions']:
        probabilities[explosion['id']] = (explosion['probability'] * (length / 1000)) / 43200
    
    d1 = probabilities[1]
    d2 = probabilities[2]
    d3 = probabilities[3]
    d4 = probabilities[4]
    nothing = 1 - d1 - d2 - d3 - d4

    def generate_file(filename):
        file_json = {
            'Events' : []
        }

        date = datetime(year=1, month=1, day=1, hour=0, minute=0, second=0)

        for i in range(43200):
            prob_expl = random.choices([0, 1, 2, 3, 4], weights=[nothing, d1, d2, d3, d4], k=1)[0]

            if prob_expl == 0:
                continue

            expl = {}
            expl['ID'] = prob_expl
            expl['Coordinates'] = random.randint(0, length)
            expl['Time'] = (date + timedelta(seconds=i)).strftime("%H:%M:%S")

            file_json['Events'].append(expl)

        with open(filename, 'w') as f:
            f.write(json.dumps(file_json, indent=4))

    for i in range(1, config['files_quantity'] + 1):
        filename = config['filename_prefix'] + str(i) + '.json'
        generate_file(filename)

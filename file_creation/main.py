import json
import random
from datetime import datetime, timedelta

LENTH = 50000

def main(file_name):
    file_json = {}

    file_json['Events'] = []

    date = datetime(year=1, month=1, day=1, hour=0, minute=0, second=0)

    d1 = (0.6 * (LENTH / 1000)) / 43200
    d2 = (0.2 * (LENTH / 1000)) / 43200
    d3 = (0.3 * (LENTH / 1000)) / 43200
    d4 = (0.7 * (LENTH / 1000)) / 43200
    nothing = 1 - d1 - d2 - d3 - d4

    for i in range(43200):
        prob_expl = random.choices([0, 1, 2, 3, 4], weights=[nothing, d1, d2, d3, d4], k=1)[0]

        if prob_expl == 0:
            continue

        expl = {}
        expl['ID'] = prob_expl
        expl['Coordinates'] = random.randint(0, LENTH)
        expl['Time'] = (date + timedelta(seconds=i)).strftime("%H:%M:%S")

        file_json['Events'].append(expl)

    with open(file_name, 'w') as f:
        f.write(json.dumps(file_json, indent=4))

if __name__ == '__main__':
    file_name = 'Explosions_50_'
    for i in range(1, 11):
        main(file_name + str(i) + '.json')


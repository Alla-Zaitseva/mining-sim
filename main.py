from simulation import simulate
from file_creation import generate_explosions_files
import argparse
import json


def parse_args():
    """
    Get arguments from shell
    :output: arguments
    """
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers()

    # Encode
    generate_file_args = subparsers.add_parser('generate_file')
    generate_file_args.set_defaults(mode='generate_file')
    generate_file_args.add_argument('--config', type=argparse.FileType('r'), help='Config file', required=True)

    # Decode
    simulate_args = subparsers.add_parser('simulate')
    simulate_args.set_defaults(mode='simulate')
    simulate_args.add_argument('--config', type=argparse.FileType('r'), help='Config file', required=True)

    return parser.parse_args()

def main():
    args = parse_args()

    if args.mode == 'generate_file':
        config = json.load(args.config)
        generate_explosions_files(config)
    elif args.mode == 'simulate':
        config = json.load(args.config)
        simulate(config)
    pass


if __name__ == '__main__':
    main()

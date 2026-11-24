"""Summarize observations in a requested time window."""
import argparse
import json
from pathlib import Path


def load_records(directory):
    records = []
    for path in sorted(Path(directory).glob('shard_*.json')):
        records.extend(json.loads(path.read_text()))
    return records


def summarize(records, start, end):
    selected = [record for record in records if start <= record['time'] < end]
    return {
        'count': len(selected),
        'total': sum(record['value'] for record in selected),
        'first': min((record['time'] for record in selected), default=None),
        'last': max((record['time'] for record in selected), default=None),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    parser.add_argument('start', type=int)
    parser.add_argument('end', type=int)
    args = parser.parse_args()
    print(json.dumps(summarize(load_records(args.directory), args.start, args.end)))

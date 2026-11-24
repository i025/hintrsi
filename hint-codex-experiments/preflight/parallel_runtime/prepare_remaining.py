#!/usr/bin/env python3
"""Prepare at most two additional VM lanes at a time, without model calls."""

import json
import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from prepare_lane import OUT, announce, install_runtime, inspect, start


def prepare(lane, resume):
    started = time.monotonic()
    inspect(lane) if resume else start(lane)
    install_runtime(lane)
    inspect(lane)
    return {'lane':lane,'runtime_ready':True,'elapsed_seconds':time.monotonic()-started,'model_calls':0}


def main(resume=False):
    record = {'started_at_unix':time.time(),'heavy_preparations_limit':2,'model_calls':0,'lanes':[]}
    path = OUT/('remaining_resume.json' if resume else 'remaining_preparation.json')
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(prepare,lane,resume):lane for lane in [2,3,4,5]}
        for future in as_completed(futures):
            lane = futures[future]
            try:
                result = future.result()
            except Exception as error:
                result = {'lane':lane,'runtime_ready':False,'error':str(error)}
            record['lanes'].append(result)
            path.write_text(json.dumps(record,indent=2)+'\n')
            announce(lane,'preparation_finished',**{k:v for k,v in result.items() if k!='lane'})
    record['finished_at_unix'] = time.time()
    record['all_runtime_ready'] = all(row['runtime_ready'] for row in record['lanes'])
    path.write_text(json.dumps(record,indent=2)+'\n')
    return 0 if record['all_runtime_ready'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume',action='store_true')
    raise SystemExit(main(parser.parse_args().resume))

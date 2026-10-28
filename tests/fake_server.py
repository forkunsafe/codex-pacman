"""A subprocess fixture with intentionally hostile and incomplete responses."""
import json
import sys
import time
mode = sys.argv[1]
for line in sys.stdin:
    request = json.loads(line)
    if request['method'] == 'initialize':
        if mode == 'timeout':
            time.sleep(3)
            continue
        if mode == 'malformed':
            print('not-json', flush=True)
            continue
        print(json.dumps({'id': request['id'], 'result': {}}), flush=True)
    elif request['method'] == 'initialized':
        continue
    elif request['method'] == 'account/rateLimits/read':
        if mode == 'unsupported':
            print(json.dumps({'id': request['id'], 'error': {'code': -32601, 'message': 'SECRET'}}), flush=True)
        elif mode == 'auth':
            print(json.dumps({'id': request['id'], 'error': {'code': -1, 'message': 'SECRET'}}), flush=True)
        elif mode == 'schema':
            print(json.dumps({'id': request['id'], 'result': []}), flush=True)
        elif mode == 'eof':
            break
        elif mode == 'huge':
            print('x' * (1024 * 1024 + 10), flush=True)
        else:
            print(json.dumps({'method': 'account/updated', 'params': {}}), flush=True)
            print(json.dumps({'id': request['id'], 'result': {'rateLimits': {'primary': {'usedPercent': 12, 'windowDurationMins': 300, 'resetsAt': 2000000000}, 'secondary': {'usedPercent': 30, 'windowDurationMins': 10080, 'resetsAt': 2000600000}}}}), flush=True)

"""
Created on Fri Sep 11 16:10:39 2026

@author: eneso
"""
import argparse
import json
import sys
import time

from .core import max_range
from .presets import PRESETS, preset
from . import studies, validation


def main(argv=None):
    ap = argparse.ArgumentParser(prog='h2volt', description='H2VOLT – electric and hydrogen aircraft range studio')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('presets')
    r = sub.add_parser('run')
    r.add_argument('preset')
    r.add_argument('--json')
    s = sub.add_parser('size')
    s.add_argument('preset')
    s.add_argument('target_km', type=float)
    sub.add_parser('validate')
    a = ap.parse_args(argv)
    if a.cmd == 'presets':
        for p in PRESETS:
            print('%-18s %s' % (p['id'], p['name']))
        return 0
    if a.cmd == 'run':
        cfg = json.load(open(a.json)) if a.json else preset(a.preset)['config']
        t0 = time.perf_counter()
        res = max_range(cfg)
        s_ = res['summary']
        print('range %.1f km · block %.1f min · MTOW %.0f kg · %s · %.0f ms' % (s_['range_km'], s_['block_time_min'], s_['mtow_kg'], 'feasible' if s_['feasible'] else 'NOT feasible', (time.perf_counter() - t0) * 1000))
        for row in res['segments']:
            print('  %-8s %7.1f min %8.1f km %8.1f kWh' % (row['segment'], row['time_min'], row['dist_km'], row['energy_kwh']))
        for f in s_['flags']:
            print('  ! ' + f)
        return 0
    if a.cmd == 'size':
        sz = studies.size_for_range(preset(a.preset)['config'], a.target_km)
        print(('sized: ' if sz['ok'] else 'not reachable: ') + '%s = %.2f → %.1f km' % (sz['variable'], sz['value'], sz['achievable_km']))
        return 0 if sz['ok'] else 1
    if a.cmd == 'validate':
        t0 = time.perf_counter()
        res = validation.run()
        fail = 0
        for x in res:
            print(('  PASS  ' if x['ok'] else '  FAIL  ') + '[' + x['group'] + '] ' + x['name'] + '  (' + x['detail'] + ')')
            fail += 0 if x['ok'] else 1
        print('%d/%d checks passed in %.2f s' % (len(res) - fail, len(res), time.perf_counter() - t0))
        return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())

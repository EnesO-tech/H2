"""
Created on Fri Sep 11 16:10:39 2026

@author: eneso
"""
import copy
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from h2volt import api, validation
from h2volt.core import max_range
from h2volt.presets import PRESETS

CHECKS = validation.run()


@pytest.mark.parametrize('check', CHECKS, ids=[c['group'] + ': ' + c['name'] for c in CHECKS])
def test_validation(check):
    assert check['ok'], check['detail']


@pytest.mark.parametrize('p', PRESETS, ids=[p['id'] for p in PRESETS])
def test_presets_feasible(p):
    s = max_range(p['config'])['summary']
    assert s['feasible'] and s['mtow_ok'] and s['range_km'] > 10


@pytest.mark.parametrize('fn,args', [('presets', []), ('schema', []), ('atmosphere', [])])
def test_api_plain(fn, args):
    out = json.loads(getattr(api, fn)(*args))
    assert out['ok']


def test_api_run_and_studies():
    cfg = json.dumps(PRESETS[1]['config'])
    r = json.loads(api.run(cfg))
    assert r['ok'] and r['data']['summary']['feasible'] and len(r['data']['series']['t']) <= 701
    assert json.loads(api.payload_range(cfg))['ok']
    assert json.loads(api.compare(cfg))['ok']
    sw = json.loads(api.sweep(cfg, 'airframe.aspect_ratio', 8, 12, 3))
    assert sw['ok'] and sw['data'][2]['range_km'] > sw['data'][0]['range_km']


def test_api_error_is_reported():
    bad = copy.deepcopy(PRESETS[0]['config'])
    del bad['airframe']
    r = json.loads(api.run(json.dumps(bad)))
    assert not r['ok'] and r['error']

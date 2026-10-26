"""
Created on Fri Sep 11 16:10:39 2026

@author: eneso
"""
import copy

from .core import Aircraft, FuelCell, fly, max_range


def get_path(cfg, path):
    o = cfg
    for k in path.split('.'):
        o = o[k]
    return o


def set_path(cfg, path, value):
    o = cfg
    keys = path.split('.')
    for k in keys[:-1]:
        o = o.setdefault(k, {})
    o[keys[-1]] = value


def sizing_variable(cfg):
    return 'battery.energy_kwh' if cfg.get('architecture', 'battery') == 'battery' else 'tank.h2_kg'


def size_for_range(cfg, target_km, tol=1e-3):
    var = sizing_variable(cfg)
    base = copy.deepcopy(cfg)

    def rng(v):
        c = copy.deepcopy(base)
        set_path(c, var, v)
        r = max_range(c, tol_km=0.05)
        return r['summary']['range_km'] if r['summary']['feasible'] else -1.0, r, c

    v0 = max(float(get_path(base, var)), 1.0)
    lo, hi = 0.0, v0
    r_hi, res_hi, c_hi = rng(hi)
    best = (r_hi, hi, res_hi, c_hi)
    it = 0
    while r_hi < target_km and it < 25:
        it += 1
        lo = hi
        hi *= 1.8
        r_new, res_new, c_new = rng(hi)
        if r_new > best[0]:
            best = (r_new, hi, res_new, c_new)
        if r_new <= r_hi + 1e-6 and r_new < target_km:
            return {'ok': False, 'variable': var, 'value': best[1], 'achievable_km': best[0], 'target_km': target_km, 'reason': 'Target range not reachable: adding more energy storage makes the aircraft heavier faster than it adds range (mass snowball).', 'result': best[2], 'config': best[3]}
        r_hi, res_hi, c_hi = r_new, res_new, c_new
    if r_hi < target_km:
        return {'ok': False, 'variable': var, 'value': hi, 'achievable_km': r_hi, 'target_km': target_km, 'reason': 'Target range not reached within the search range.', 'result': res_hi, 'config': c_hi}
    while hi - lo > tol * max(hi, 1.0):
        mid = 0.5 * (lo + hi)
        r_mid, _, _ = rng(mid)
        if r_mid >= target_km:
            hi = mid
        else:
            lo = mid
    r_fin, res_fin, c_fin = rng(hi)
    return {'ok': True, 'variable': var, 'value': hi, 'achievable_km': r_fin, 'target_km': target_km, 'result': res_fin, 'config': c_fin}


def payload_range(cfg, n=9):
    pmax = float(cfg.get('max_payload_kg', cfg.get('payload_kg', 0.0)))
    out = []
    for k in range(n):
        p = pmax * k / (n - 1) if n > 1 else pmax
        c = copy.deepcopy(cfg)
        c['payload_kg'] = p
        r = max_range(c, tol_km=0.2)['summary']
        out.append({'payload_kg': p, 'range_km': r['range_km'] if r['feasible'] else 0.0, 'mtow_kg': r['mtow_kg'], 'feasible': r['feasible'], 'mtow_ok': r['mtow_ok']})
    return out


def sweep(cfg, path, values):
    out = []
    for v in values:
        c = copy.deepcopy(cfg)
        set_path(c, path, float(v))
        r = max_range(c, tol_km=0.2)['summary']
        out.append({'value': float(v), 'range_km': r['range_km'] if r['feasible'] else 0.0, 'mtow_kg': r['mtow_kg'], 'wh_per_pax_km': r['wh_per_pax_km'], 'feasible': r['feasible']})
    return out


def compare(cfg):
    ref = Aircraft(cfg)
    mtow = ref.mtow_limit if ref.mtow_limit > 0 else ref.mtow
    out = []
    for arch in ('battery', 'fuelcell', 'hybrid'):
        c = copy.deepcopy(cfg)
        c['architecture'] = arch
        set_path(c, 'battery.energy_kwh', float(get_path(cfg, 'battery.energy_kwh')) if arch == 'hybrid' else 0.0)
        set_path(c, 'tank.h2_kg', 0.0)
        a0 = Aircraft(c)
        budget = mtow - a0.mtow
        if arch == 'battery':
            if budget <= 0:
                out.append({'architecture': arch, 'feasible': False, 'range_km': 0.0, 'reason': 'no mass budget'})
                continue
            set_path(c, 'battery.energy_kwh', budget * a0.battery.e_spec / 1000.0)
        else:
            gi = a0.tank.grav_index
            if budget <= 0:
                out.append({'architecture': arch, 'feasible': False, 'range_km': 0.0, 'reason': 'no mass budget'})
                continue
            set_path(c, 'tank.h2_kg', budget * gi)
        r = max_range(c, tol_km=0.2)
        s = r['summary']
        out.append({'architecture': arch, 'feasible': s['feasible'], 'range_km': s['range_km'] if s['feasible'] else 0.0, 'mtow_kg': s['mtow_kg'], 'battery_kwh': s['battery_kwh'], 'h2_kg': s['h2_kg'], 'wh_per_pax_km': s['wh_per_pax_km'], 'flags': s['flags'], 'reason': s.get('max_range_reason') or ('energy storage too small for take-off, climb, descent and reserve' if not s['feasible'] and not s['flags'] else ''), 'mass': r['mass']})
    return {'mtow_kg': mtow, 'rows': out}


def fc_curve(cfg):
    return FuelCell(cfg.get('fuelcell', {})).curve()

"""
Created on Fri Sep 11 16:10:39 2026

@author: eneso
"""
import copy
import json
import math

from .core import Aircraft, FuelCell, LHV_H2, V_LHV, fly, isa, max_range
from .presets import PRESETS
from . import studies

SCHEMA = [
    {'id': 'airframe', 'label': 'Airframe', 'fields': [
        {'path': 'airframe.oe_mass_kg', 'label': 'Operating empty mass (without powertrain)', 'unit': 'kg', 'step': 10},
        {'path': 'airframe.mtow_limit_kg', 'label': 'MTOW limit', 'unit': 'kg', 'step': 10},
        {'path': 'airframe.wing_area_m2', 'label': 'Wing area', 'unit': 'm²', 'step': 0.5},
        {'path': 'airframe.aspect_ratio', 'label': 'Aspect ratio', 'unit': '–', 'step': 0.1},
        {'path': 'airframe.oswald', 'label': 'Oswald factor', 'unit': '–', 'step': 0.01},
        {'path': 'airframe.cd0', 'label': 'Zero-lift drag CD0', 'unit': '–', 'step': 0.001},
        {'path': 'airframe.cl_max', 'label': 'CL max', 'unit': '–', 'step': 0.05},
    ]},
    {'id': 'payload', 'label': 'Payload', 'fields': [
        {'path': 'payload_kg', 'label': 'Payload', 'unit': 'kg', 'step': 5},
        {'path': 'max_payload_kg', 'label': 'Max. payload', 'unit': 'kg', 'step': 5},
    ]},
    {'id': 'propulsion', 'label': 'Electric drive', 'fields': [
        {'path': 'propulsion.shaft_power_kw', 'label': 'Installed shaft power', 'unit': 'kW', 'step': 10},
        {'path': 'propulsion.eta_propeller', 'label': 'Propeller efficiency', 'unit': '–', 'step': 0.01},
        {'path': 'propulsion.eta_motor', 'label': 'Motor efficiency', 'unit': '–', 'step': 0.005},
        {'path': 'propulsion.eta_inverter', 'label': 'Inverter efficiency', 'unit': '–', 'step': 0.005},
        {'path': 'propulsion.eta_gearbox', 'label': 'Gearbox efficiency', 'unit': '–', 'step': 0.005},
        {'path': 'propulsion.aux_power_kw', 'label': 'Auxiliary systems', 'unit': 'kW', 'step': 0.5},
        {'path': 'propulsion.motor_kwkg', 'label': 'Motor specific power', 'unit': 'kW/kg', 'step': 0.5},
        {'path': 'propulsion.thermal_kg_per_kw', 'label': 'Cooling mass per kW heat', 'unit': 'kg/kW', 'step': 0.05},
    ]},
    {'id': 'battery', 'label': 'Battery', 'arch': ['battery', 'hybrid'], 'fields': [
        {'path': 'battery.energy_kwh', 'label': 'Pack energy', 'unit': 'kWh', 'step': 1},
        {'path': 'battery.specific_energy_whkg', 'label': 'Specific energy (pack)', 'unit': 'Wh/kg', 'step': 5},
        {'path': 'battery.specific_power_kwkg', 'label': 'Specific power (pack)', 'unit': 'kW/kg', 'step': 0.1},
        {'path': 'battery.soc_min', 'label': 'Minimum state of charge', 'unit': '–', 'step': 0.01},
        {'path': 'battery.efficiency_at_pmax', 'label': 'Efficiency at max. power', 'unit': '–', 'step': 0.01},
    ]},
    {'id': 'fuelcell', 'label': 'Fuel cell', 'arch': ['fuelcell', 'hybrid'], 'fields': [
        {'path': 'fuelcell.power_kw', 'label': 'Net rated power', 'unit': 'kW', 'step': 10},
        {'path': 'fuelcell.specific_power_kwkg', 'label': 'System specific power', 'unit': 'kW/kg', 'step': 0.1},
        {'path': 'fuelcell.bop_fraction', 'label': 'Balance-of-plant share', 'unit': '–', 'step': 0.01},
        {'path': 'fuelcell.model', 'label': 'Model', 'type': 'select', 'options': [['polarization', 'Polarization curve'], ['constant', 'Constant efficiency']]},
        {'path': 'fuelcell.efficiency', 'label': 'Efficiency (constant model)', 'unit': '–', 'step': 0.01},
    ]},
    {'id': 'tank', 'label': 'Hydrogen tank', 'arch': ['fuelcell', 'hybrid'], 'fields': [
        {'path': 'tank.type', 'label': 'Storage', 'type': 'select', 'options': [['LH2', 'Liquid (LH2)'], ['CGH2', 'Compressed 700 bar (CGH2)']]},
        {'path': 'tank.h2_kg', 'label': 'Hydrogen mass', 'unit': 'kg', 'step': 1},
        {'path': 'tank.gravimetric_index', 'label': 'Gravimetric index', 'unit': '–', 'step': 0.01},
        {'path': 'tank.usable_fraction', 'label': 'Usable fraction', 'unit': '–', 'step': 0.01},
    ]},
    {'id': 'mission', 'label': 'Mission', 'fields': [
        {'path': 'mission.cruise_alt_m', 'label': 'Cruise altitude', 'unit': 'm', 'step': 100},
        {'path': 'mission.cruise_tas_mps', 'label': 'Cruise speed (TAS)', 'unit': 'm/s', 'step': 1},
        {'path': 'mission.climb_rate_mps', 'label': 'Climb rate', 'unit': 'm/s', 'step': 0.5},
        {'path': 'mission.climb_tas_mps', 'label': 'Climb speed', 'unit': 'm/s', 'step': 1},
        {'path': 'mission.descent_rate_mps', 'label': 'Descent rate', 'unit': 'm/s', 'step': 0.5},
        {'path': 'mission.reserve_min', 'label': 'Reserve', 'unit': 'min', 'step': 5},
        {'path': 'mission.dt_s', 'label': 'Time step', 'unit': 's', 'step': 1},
    ]},
]

SWEEPS = [
    {'path': 'battery.specific_energy_whkg', 'label': 'Battery specific energy [Wh/kg]', 'from': 150, 'to': 600, 'n': 10},
    {'path': 'fuelcell.specific_power_kwkg', 'label': 'Fuel cell specific power [kW/kg]', 'from': 0.5, 'to': 3.0, 'n': 11},
    {'path': 'tank.gravimetric_index', 'label': 'Tank gravimetric index [–]', 'from': 0.05, 'to': 0.6, 'n': 12},
    {'path': 'airframe.aspect_ratio', 'label': 'Aspect ratio [–]', 'from': 6, 'to': 16, 'n': 11},
    {'path': 'mission.cruise_tas_mps', 'label': 'Cruise speed [m/s]', 'from': 40, 'to': 110, 'n': 15},
    {'path': 'mission.cruise_alt_m', 'label': 'Cruise altitude [m]', 'from': 500, 'to': 7000, 'n': 14},
    {'path': 'payload_kg', 'label': 'Payload [kg]', 'from': 0, 'to': 2000, 'n': 11},
]


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    return o


def _out(obj):
    return json.dumps({'ok': True, 'data': _clean(obj)})


def _err(e):
    return json.dumps({'ok': False, 'error': str(e)})


def _decimate(series, n=700):
    if not series:
        return series
    m = len(series['t'])
    if m <= n:
        return series
    step = m / float(n)
    idx = sorted(set([int(k * step) for k in range(n)] + [m - 1]))
    return {k: [v[i] for i in idx] for k, v in series.items()}


def geometry(cfg):
    ac = Aircraft(cfg)
    return {
        'arch': ac.arch,
        'span_m': math.sqrt(ac.S * ac.AR),
        'wing_area_m2': ac.S,
        'mtow_kg': ac.mtow,
        'battery_kg': ac.battery.mass,
        'battery_kwh': ac.battery.energy_kwh,
        'fc_kg': ac.fc.mass,
        'fc_kw': ac.fc.p_max / 1000.0,
        'tank_kg': ac.tank.mass,
        'h2_kg': ac.tank.h2_kg,
        'tank_volume_m3': ac.tank.volume_m3,
        'tank_type': ac.tank.kind,
        'motor_kg': ac.m_motor,
        'shaft_kw': ac.p_shaft_max / 1000.0,
        'n_motors': int(cfg.get('propulsion', {}).get('n_motors', 1)),
    }


def presets():
    try:
        return _out([{'id': p['id'], 'name': p['name'], 'description': p['description'], 'config': p['config']} for p in PRESETS])
    except Exception as e:
        return _err(e)


def schema():
    try:
        return _out({'groups': SCHEMA, 'sweeps': SWEEPS})
    except Exception as e:
        return _err(e)


def run(cfg_json, cruise_km=None):
    try:
        cfg = json.loads(cfg_json)
        r = max_range(cfg) if cruise_km is None else fly(cfg, float(cruise_km))
        r['series'] = _decimate(r['series'])
        r['geometry'] = geometry(cfg)
        r['fc_curve'] = studies.fc_curve(cfg) if cfg.get('architecture') != 'battery' else []
        return _out(r)
    except Exception as e:
        return _err(e)


def size(cfg_json, target_km):
    try:
        cfg = json.loads(cfg_json)
        s = studies.size_for_range(cfg, float(target_km))
        s['result']['series'] = _decimate(s['result']['series'])
        s['result']['geometry'] = geometry(s['config'])
        s['result']['fc_curve'] = studies.fc_curve(s['config']) if s['config'].get('architecture') != 'battery' else []
        return _out(s)
    except Exception as e:
        return _err(e)


def payload_range(cfg_json):
    try:
        return _out(studies.payload_range(json.loads(cfg_json)))
    except Exception as e:
        return _err(e)


def sweep(cfg_json, path, start, stop, n):
    try:
        n = max(2, int(n))
        vals = [float(start) + (float(stop) - float(start)) * k / (n - 1) for k in range(n)]
        return _out(studies.sweep(json.loads(cfg_json), path, vals))
    except Exception as e:
        return _err(e)


def compare(cfg_json):
    try:
        return _out(studies.compare(json.loads(cfg_json)))
    except Exception as e:
        return _err(e)


def atmosphere():
    try:
        rows = []
        for h in range(0, 12001, 500):
            T, p, rho, a = isa(h)
            rows.append({'h': h, 'T': T, 'p': p, 'rho': rho, 'a': a})
        return _out(rows)
    except Exception as e:
        return _err(e)


def validate():
    try:
        from . import validation
        return _out(validation.run())
    except Exception as e:
        return _err(e)

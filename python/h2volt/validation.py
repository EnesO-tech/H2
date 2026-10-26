"""
Created on Fri Sep 11 16:10:39 2026

@author: eneso
"""
import copy
import math

from .core import G0, LHV_H2, V_LHV, F_CONST, M_H2, Aircraft, FuelCell, fly, isa, max_range
from .presets import preset
from . import studies


def _cruise_only(cfg):
    c = copy.deepcopy(cfg)
    m = c['mission']
    m.update({'taxi_s': 0.0, 'takeoff_s': 0.0, 'landing_s': 0.0, 'reserve_min': 0.0, 'field_alt_m': m['cruise_alt_m'], 'final_alt_m': m['cruise_alt_m']})
    c['propulsion']['aux_power_kw'] = 0.0
    return c


def run():
    R = []

    def add(group, name, ok, detail, ref):
        R.append({'group': group, 'name': name, 'ok': bool(ok), 'detail': detail, 'ref': ref})

    for h, Tr, pr, rr in ((0, 288.15, 101325.0, 1.225), (5000, 255.65, 54019.9, 0.736116), (11000, 216.65, 22632.1, 0.363918), (15000, 216.65, 12044.6, 0.193674)):
        T, p, rho, _ = isa(h)
        ok = abs(T - Tr) < 0.01 and abs(p - pr) / pr < 2e-5 and abs(rho - rr) / rr < 2e-4
        add('Atmosphere', 'ISA at %d m (geopotential): T, p, ρ match the standard atmosphere' % h, ok, 'T = %.2f K, p = %.1f Pa, ρ = %.5f kg/m³' % (T, p, rho), 'ISO 2533')

    fc = FuelCell({'power_kw': 500.0, 'specific_power_kwkg': 1.5})
    worst = 0.0
    for x in (0.05, 0.2, 0.5, 0.8, 1.0):
        r = fc.operate(500e3 * x)
        current = r['p_stack'] / r['v_cell']
        mdot_faraday = current / (2.0 * F_CONST) * M_H2
        worst = max(worst, abs(mdot_faraday - r['mdot']) / r['mdot'], abs(r['eta'] * r['mdot'] * LHV_H2 - r['p_net']) / r['p_net'], abs(r['p_net'] - 500e3 * x) / (500e3 * x))
    add('Fuel cell', 'Faraday law, energy balance and requested net power at 5 loads', worst < 1e-9, 'max rel. deviation %.1e (LHV voltage %.4f V)' % (worst, V_LHV), 'ṁ = I/(2F)·M_H2')
    r = fc.operate(500e3)
    add('Fuel cell', 'Rated point: net power = rating at rated current density', abs(r['p_net'] - 500e3) < 1e-3 and abs(r['i'] - fc.i_rated) < 1e-6, 'P = %.3f kW at i = %.4f A/cm²' % (r['p_net'] / 1000, r['i']), 'design point')
    effs = [fc.operate(500e3 * x)['eta'] for x in (0.1, 0.3, 0.6, 1.0)]
    add('Fuel cell', 'System efficiency falls from part load to rated load (polarization)', effs[1] > effs[2] > effs[3], ' → '.join('%.3f' % e for e in effs), 'PEM polarization curve')

    cb = _cruise_only(preset('trainer_battery')['config'])
    cb['battery']['ideal'] = True
    ac = Aircraft(cb)
    res = max_range(cb, tol_km=1e-5)['summary']
    _, _, rho, _ = isa(cb['mission']['cruise_alt_m'])
    v = cb['mission']['cruise_tas_mps']
    D, cl, cd = ac.drag(ac.mtow, v, rho)
    e_use = ac.battery.e_joule * (ac.battery.soc0 - ac.battery.soc_min)
    r_an = e_use * ac.eta_chain * ac.eta_prop / D / 1000.0
    add('Range equations', 'Battery-electric Breguet: R = E·η_total·(L/D)/(m·g)', abs(res['range_km'] - r_an) / r_an < 1e-6, 'simulation %.4f km vs analytic %.4f km (L/D = %.2f)' % (res['range_km'], r_an, cl / cd), 'Hepperle (2012)')

    ch = _cruise_only(preset('commuter19_fc')['config'])
    ch['fuelcell']['model'] = 'constant'
    ch['fuelcell']['efficiency'] = 0.5
    ch['tank']['usable_fraction'] = 1.0
    ch['mission']['dt_s'] = 2.0
    ac = Aircraft(ch)
    res = max_range(ch, tol_km=1e-3)['summary']
    _, _, rho, _ = isa(ch['mission']['cruise_alt_m'])
    v = ch['mission']['cruise_tas_mps']
    q = 0.5 * rho * v * v
    a = q * ac.S * ac.cd0
    b = ac.k * G0 * G0 / (q * ac.S)
    m0, m1 = ac.mtow, ac.mtow - ac.tank.h2_kg
    eta = 0.5 * ac.eta_chain * ac.eta_prop
    r_an = eta * LHV_H2 / math.sqrt(a * b) * (math.atan(m0 * math.sqrt(b / a)) - math.atan(m1 * math.sqrt(b / a))) / 1000.0
    add('Range equations', 'Hydrogen range with burn-off: exact integral ∫η·LHV/D(m) dm', abs(res['range_km'] - r_an) / r_an < 1e-3, 'simulation %.2f km vs analytic %.2f km' % (res['range_km'], r_an), 'Breguet integral (constant V, h)')

    full = preset('hybrid9')['config']
    rr = max_range(full)
    s = rr['summary']
    e_bal = abs(s['electric_energy_kwh'] - (s['battery_terminal_kwh'] + s['fc_energy_kwh'])) / s['electric_energy_kwh']
    b_bal = abs((s['battery_energy_used_kwh'] - s['battery_terminal_kwh']) - s['battery_loss_kwh']) / max(s['battery_loss_kwh'], 1e-9)
    add('Conservation', 'Electric bus: consumed energy = battery + fuel cell output', e_bal < 1e-9, 'rel. deviation %.1e' % e_bal, 'energy conservation')
    add('Conservation', 'Battery: chemical energy − terminal energy = I²R losses', b_bal < 1e-9, 'rel. deviation %.1e' % b_bal, 'energy conservation')
    m_bal = abs(s['mtow_kg'] - s['h2_used_kg'] - s['landing_mass_kg'])
    add('Conservation', 'Mass: landing mass = take-off mass − hydrogen consumed', m_bal < 1e-9, '|Δ| = %.1e kg' % m_bal, 'mass conservation')
    mb = abs(sum(x['kg'] for x in rr['mass']) - s['mtow_kg'])
    add('Conservation', 'Mass breakdown adds up to take-off mass', mb < 1e-9, '|Δ| = %.1e kg' % mb, 'bookkeeping')

    target = 300.0
    sz = studies.size_for_range(preset('commuter19_fc')['config'], target)
    ok = sz['ok'] and abs(sz['achievable_km'] - target) < 1.0 and sz['result']['summary']['feasible']
    add('Sizing', 'Sizing loop hits the target range (300 km) with a feasible aircraft', ok, '%.2f km with %.1f kg H2' % (sz['achievable_km'], sz['value']), 'mass-snowball loop')

    pr = studies.payload_range(preset('hybrid9')['config'], n=5)
    mono = all(pr[k]['range_km'] >= pr[k + 1]['range_km'] - 1e-6 for k in range(len(pr) - 1))
    add('Studies', 'Payload–range: range decreases with payload', mono, ' → '.join('%.0f' % p['range_km'] for p in pr), 'physics')

    c10 = preset('commuter19_fc')['config']
    c2 = copy.deepcopy(c10)
    c2['mission']['dt_s'] = 2.0
    r10 = max_range(c10)['summary']['range_km']
    r2 = max_range(c2)['summary']['range_km']
    add('Numerics', 'Time-step convergence: dt = 10 s vs 2 s within 0.5 %', abs(r10 - r2) / r2 < 5e-3, '%.2f km vs %.2f km' % (r10, r2), 'discretisation')

    tr = max_range(preset('trainer_battery')['config'])['summary']
    add('Plausibility', 'Two-seat electric trainer: block time incl. 30 min reserve 40–75 min', 40 <= tr['block_time_min'] <= 75, '%.1f min, %.1f km' % (tr['block_time_min'], tr['range_km']), 'certified electric trainers')
    return R

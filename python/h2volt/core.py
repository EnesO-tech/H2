"""
Created on Fri Sep 11 16:10:39 2026

@author: eneso
"""
import copy
import math

G0 = 9.80665
R_AIR = 287.05287
GAMMA_AIR = 1.4
F_CONST = 96485.33212
M_H2 = 2.01588e-3
LHV_H2 = 119.96e6
V_LHV = LHV_H2 * M_H2 / (2.0 * F_CONST)
PAX_KG = 95.0


def isa(h):
    h = max(-1000.0, min(float(h), 20000.0))
    if h <= 11000.0:
        T = 288.15 - 0.0065 * h
        p = 101325.0 * (T / 288.15) ** (G0 / (0.0065 * R_AIR))
    else:
        T = 216.65
        p = 22632.06 * math.exp(-G0 * (h - 11000.0) / (R_AIR * T))
    rho = p / (R_AIR * T)
    return T, p, rho, math.sqrt(GAMMA_AIR * R_AIR * T)


def interp(x, xs, ys):
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    lo, hi = 0, len(xs) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if xs[mid] <= x:
            lo = mid
        else:
            hi = mid
    t = (x - xs[lo]) / (xs[hi] - xs[lo])
    return ys[lo] + t * (ys[hi] - ys[lo])


OCV_SOC = [0.0, 0.05, 0.1, 0.2, 0.35, 0.5, 0.65, 0.8, 0.9, 1.0]
OCV_REL = [0.82, 0.87, 0.90, 0.93, 0.955, 0.97, 0.985, 1.01, 1.03, 1.06]


class Battery:
    def __init__(self, cfg):
        self.energy_kwh = max(0.0, float(cfg.get('energy_kwh', 0.0)))
        self.e_spec = float(cfg.get('specific_energy_whkg', 250.0))
        self.p_spec = float(cfg.get('specific_power_kwkg', 1.5))
        self.soc_min = float(cfg.get('soc_min', 0.15))
        self.soc0 = float(cfg.get('soc0', 1.0))
        self.eta_pmax = float(cfg.get('efficiency_at_pmax', 0.92))
        self.v_nom = float(cfg.get('voltage_v', 800.0))
        self.ideal = bool(cfg.get('ideal', False))
        self.mass = self.energy_kwh * 1000.0 / self.e_spec if self.energy_kwh > 0 else 0.0
        self.p_max = self.p_spec * self.mass * 1000.0
        self.e_joule = self.energy_kwh * 3.6e6
        if self.ideal or self.p_max <= 0 or self.eta_pmax >= 1.0:
            self.r_int = 0.0
        else:
            self.r_int = (1.0 - self.eta_pmax) * self.v_nom ** 2 / self.p_max

    def ocv(self, soc):
        if self.ideal:
            return self.v_nom
        return self.v_nom * interp(soc, OCV_SOC, OCV_REL)

    def draw(self, p_term, soc):
        if self.e_joule <= 0:
            return 0.0, 0.0, 0.0, p_term > 1e-9
        v = self.ocv(max(soc, 0.0))
        r = self.r_int
        limited = False
        if r <= 0:
            i = p_term / v
        else:
            disc = v * v - 4.0 * r * p_term
            if disc < 0:
                disc = 0.0
                limited = True
            i = (v - math.sqrt(disc)) / (2.0 * r)
        p_chem = v * i
        loss = i * i * r
        if p_term > self.p_max * (1 + 1e-9):
            limited = True
        return p_chem, loss, i, limited


class FuelCell:
    def __init__(self, cfg):
        self.p_max = max(0.0, float(cfg.get('power_kw', 0.0))) * 1000.0
        self.p_spec = float(cfg.get('specific_power_kwkg', 1.0))
        self.model = cfg.get('model', 'polarization')
        self.eta_const = float(cfg.get('efficiency', 0.5))
        self.bop_frac = float(cfg.get('bop_fraction', 0.10))
        self.idle_frac = float(cfg.get('idle_fraction', 0.02))
        self.e_oc = float(cfg.get('e_oc_v', 1.0))
        self.tafel = float(cfg.get('tafel_v', 0.03))
        self.i0 = float(cfg.get('i0_acm2', 1e-3))
        self.r_ohm = float(cfg.get('r_ohm_cm2', 0.10))
        self.c_mt = float(cfg.get('mass_transport_v', 0.05))
        self.i_lim = float(cfg.get('i_limit_acm2', 2.0))
        self.i_rated = float(cfg.get('i_rated_acm2', 1.5))
        self.mass = self.p_max / 1000.0 / self.p_spec if self.p_max > 0 else 0.0
        self.p_stack_rated = self.p_max / ((1.0 - self.bop_frac) * (1.0 - self.idle_frac)) if self.p_max > 0 else 0.0
        self._table()

    def v_cell(self, i):
        i = max(i, 1e-9)
        return self.e_oc - self.tafel * math.log(i / self.i0) - self.r_ohm * i + self.c_mt * math.log(max(1e-12, 1.0 - i / self.i_lim))

    def _net_from_i(self, i):
        p_stack = self.p_stack_rated * (self.v_cell(i) * i) / (self.v_cell(self.i_rated) * self.i_rated)
        p_net = p_stack * (1.0 - self.bop_frac) - self.idle_frac * self.p_stack_rated * (1.0 - self.bop_frac)
        return p_stack, p_net

    def _table(self):
        self.tab_i, self.tab_p = [], []
        if self.p_max <= 0 or self.model != 'polarization':
            return
        n = 600
        i_min = self.i0 * 1.0001
        for k in range(n + 1):
            i = i_min + (self.i_rated - i_min) * (k / n) ** 1.6
            _, p_net = self._net_from_i(i)
            self.tab_i.append(i)
            self.tab_p.append(p_net)

    def operate(self, p_net):
        if self.p_max <= 0 or p_net <= 0:
            return {'p_net': 0.0, 'p_stack': 0.0, 'mdot': 0.0, 'heat': 0.0, 'eta': 0.0, 'v_cell': 0.0, 'i': 0.0, 'limited': p_net > 1e-9 and self.p_max <= 0}
        limited = p_net > self.p_max * (1 + 1e-9)
        p_net = min(p_net, self.p_max)
        if self.model != 'polarization':
            mdot = p_net / (self.eta_const * LHV_H2)
            return {'p_net': p_net, 'p_stack': p_net, 'mdot': mdot, 'heat': mdot * LHV_H2 - p_net, 'eta': self.eta_const, 'v_cell': self.eta_const * V_LHV, 'i': 0.0, 'limited': limited}
        i = interp(p_net, self.tab_p, self.tab_i)
        for _ in range(3):
            p_stack, pn = self._net_from_i(i)
            h = 1e-6
            _, pn2 = self._net_from_i(i + h)
            d = (pn2 - pn) / h
            if d <= 0:
                break
            i = min(max(i - (pn - p_net) / d, self.i0 * 1.0001), self.i_rated)
        p_stack, pn = self._net_from_i(i)
        v = self.v_cell(i)
        eta_stack = v / V_LHV
        mdot = p_stack / (eta_stack * LHV_H2)
        return {'p_net': pn, 'p_stack': p_stack, 'mdot': mdot, 'heat': mdot * LHV_H2 - pn, 'eta': pn / (mdot * LHV_H2), 'v_cell': v, 'i': i, 'limited': limited}

    def curve(self, n=60):
        out = []
        if self.p_max <= 0:
            return out
        for k in range(1, n + 1):
            p = self.p_max * k / n
            r = self.operate(p)
            out.append({'load': p / self.p_max, 'p_kw': r['p_net'] / 1000.0, 'eta': r['eta'], 'v_cell': r['v_cell'], 'i': r['i']})
        return out


class Tank:
    def __init__(self, cfg):
        self.kind = cfg.get('type', 'LH2')
        self.h2_kg = max(0.0, float(cfg.get('h2_kg', 0.0)))
        self.grav_index = float(cfg.get('gravimetric_index', 0.35 if self.kind == 'LH2' else 0.06))
        self.usable = float(cfg.get('usable_fraction', 0.97))
        self.mass = self.h2_kg * (1.0 / self.grav_index - 1.0) if self.h2_kg > 0 else 0.0
        rho_h2 = 70.8 if self.kind == 'LH2' else 40.2
        self.volume_m3 = self.h2_kg / rho_h2 * (1.6 if self.kind == 'LH2' else 2.2)


class Aircraft:
    def __init__(self, cfg):
        self.cfg = copy.deepcopy(cfg)
        a = cfg['airframe']
        self.arch = cfg.get('architecture', 'battery')
        self.S = float(a['wing_area_m2'])
        self.AR = float(a['aspect_ratio'])
        self.e = float(a['oswald'])
        self.cd0 = float(a['cd0'])
        self.clmax = float(a.get('cl_max', 1.6))
        self.k = 1.0 / (math.pi * self.AR * self.e)
        p = cfg['propulsion']
        self.eta_prop = float(p['eta_propeller'])
        self.eta_chain = float(p['eta_gearbox']) * float(p['eta_motor']) * float(p['eta_inverter'])
        self.p_shaft_max = float(p['shaft_power_kw']) * 1000.0
        self.p_aux = float(p.get('aux_power_kw', 0.0)) * 1000.0
        bat_cfg = dict(cfg.get('battery', {}))
        fc_cfg = dict(cfg.get('fuelcell', {}))
        tank_cfg = dict(cfg.get('tank', {}))
        if self.arch == 'battery':
            fc_cfg['power_kw'] = 0.0
            tank_cfg['h2_kg'] = 0.0
        elif self.arch == 'fuelcell':
            bat_cfg['energy_kwh'] = 0.0
        self.battery = Battery(bat_cfg)
        self.fc = FuelCell(fc_cfg)
        self.tank = Tank(tank_cfg)
        self.recharge = bool(cfg.get('hybrid', {}).get('recharge', True))
        self.soc_target = float(cfg.get('hybrid', {}).get('soc_target', 0.6))
        self.m_motor = self.p_shaft_max / 1000.0 / float(p.get('motor_kwkg', 5.0))
        p_elec_max = self.p_shaft_max / self.eta_chain + self.p_aux
        self.m_inverter = p_elec_max / 1000.0 / float(p.get('inverter_kwkg', 15.0))
        fc_heat_rated = self.fc.operate(self.fc.p_max)['heat'] if self.fc.p_max > 0 else 0.0
        self.fc_heat_rated = fc_heat_rated
        self.m_thermal = fc_heat_rated / 1000.0 * float(p.get('thermal_kg_per_kw', 0.8))
        self.payload = float(cfg.get('payload_kg', 0.0))
        oe_frac = a.get('oe_fraction')
        m_pt = self.powertrain_mass()
        if oe_frac:
            f = float(oe_frac)
            self.m_oe = f * (self.payload + m_pt) / (1.0 - f)
        else:
            self.m_oe = float(a['oe_mass_kg'])
        self.mtow = self.m_oe + self.payload + m_pt
        self.mtow_limit = float(a.get('mtow_limit_kg', 0.0) or 0.0)

    def powertrain_mass(self):
        return self.battery.mass + self.fc.mass + self.tank.mass + self.tank.h2_kg + self.m_motor + self.m_inverter + self.m_thermal

    def mass_breakdown(self):
        return [
            {'name': 'Airframe & systems (OE)', 'kg': self.m_oe},
            {'name': 'Payload', 'kg': self.payload},
            {'name': 'Battery', 'kg': self.battery.mass},
            {'name': 'Fuel cell system', 'kg': self.fc.mass},
            {'name': 'H2 tank', 'kg': self.tank.mass},
            {'name': 'Hydrogen', 'kg': self.tank.h2_kg},
            {'name': 'Electric motors', 'kg': self.m_motor},
            {'name': 'Inverters', 'kg': self.m_inverter},
            {'name': 'Thermal management', 'kg': self.m_thermal},
        ]

    def drag(self, m, v, rho, gamma=0.0):
        q = 0.5 * rho * v * v
        cl = m * G0 * math.cos(gamma) / (q * self.S)
        cd = self.cd0 + self.k * cl * cl
        return q * self.S * cd, cl, cd

    def elec_available(self, soc):
        p = self.fc.p_max
        if self.battery.e_joule > 0 and soc > 0:
            p += self.battery.p_max
        return p


def _segments(cfg, cruise_km):
    m = cfg['mission']
    segs = []
    alt_c = float(m['cruise_alt_m'])
    v_c = float(m['cruise_tas_mps'])
    segs.append({'type': 'taxi', 'time': float(m.get('taxi_s', 300)), 'frac': float(m.get('taxi_power_frac', 0.05))})
    segs.append({'type': 'takeoff', 'time': float(m.get('takeoff_s', 60)), 'frac': float(m.get('takeoff_power_frac', 1.0))})
    segs.append({'type': 'climb', 'to': alt_c, 'roc': float(m['climb_rate_mps']), 'tas': float(m['climb_tas_mps'])})
    segs.append({'type': 'cruise', 'alt': alt_c, 'tas': v_c, 'dist': cruise_km * 1000.0})
    segs.append({'type': 'descent', 'to': float(m.get('final_alt_m', 0.0)), 'rod': float(m['descent_rate_mps']), 'tas': float(m['descent_tas_mps'])})
    if float(m.get('reserve_min', 0)) > 0:
        segs.append({'type': 'reserve', 'time': float(m['reserve_min']) * 60.0, 'alt': float(m.get('reserve_alt_m', 450.0)), 'tas': float(m.get('reserve_tas_mps', v_c * 0.75))})
    segs.append({'type': 'landing', 'time': float(m.get('landing_s', 240)), 'frac': float(m.get('taxi_power_frac', 0.05))})
    return segs


def fly(cfg, cruise_km, record=True, ac=None):
    ac = ac or Aircraft(cfg)
    dt_base = float(cfg['mission'].get('dt_s', 10.0))
    m = ac.mtow
    soc = ac.battery.soc0
    h2 = ac.tank.h2_kg * ac.tank.usable
    h2_unusable = ac.tank.h2_kg - h2
    h = float(cfg['mission'].get('field_alt_m', 0.0))
    x = 0.0
    t = 0.0
    e_bat_chem = 0.0
    e_bat_term = 0.0
    e_fc_net = 0.0
    e_h2 = 0.0
    e_elec = 0.0
    e_shaft = 0.0
    heat_fc = 0.0
    loss_bat = 0.0
    flags = set()
    series = {k: [] for k in ('t', 'x_km', 'alt_m', 'tas', 'p_shaft_kw', 'p_elec_kw', 'p_fc_kw', 'p_bat_kw', 'soc', 'h2_kg', 'mass_kg', 'cl', 'ld', 'eta_fc', 'fc_heat_kw', 'seg')}
    seg_rows = []
    peak = {'p_shaft': 0.0, 'p_elec': 0.0, 'p_bat': 0.0, 'p_fc': 0.0, 'cl': 0.0, 'c_rate': 0.0}

    def step(seg, dt, p_shaft_req, v, gamma, dx, dh, cl, ld):
        nonlocal m, soc, h2, x, h, t, e_bat_chem, e_bat_term, e_fc_net, e_h2, e_elec, e_shaft, heat_fc, loss_bat
        p_shaft = max(0.0, p_shaft_req)
        if p_shaft > ac.p_shaft_max * (1 + 1e-9):
            flags.add('shaft power limit exceeded in ' + seg)
            p_shaft = ac.p_shaft_max
        p_elec = p_shaft / ac.eta_chain + ac.p_aux
        p_fc_req, p_bat_req = 0.0, 0.0
        if ac.arch == 'battery':
            p_bat_req = p_elec
        elif ac.arch == 'fuelcell':
            p_fc_req = p_elec
        else:
            p_fc_req = min(p_elec, ac.fc.p_max)
            p_bat_req = p_elec - p_fc_req
            if ac.recharge and p_bat_req <= 0 and soc < ac.soc_target and ac.fc.p_max > p_elec:
                p_charge = min(ac.fc.p_max - p_elec, ac.battery.p_max * 0.5)
                p_fc_req += p_charge
                p_bat_req -= p_charge
        fcr = ac.fc.operate(p_fc_req)
        if fcr['limited']:
            flags.add('fuel cell power limit exceeded in ' + seg)
            if ac.arch == 'hybrid':
                p_bat_req += p_fc_req - fcr['p_net']
        p_chem, loss, _, lim = ac.battery.draw(p_bat_req, soc)
        if lim and abs(p_bat_req) > 1e-9:
            flags.add('battery power limit exceeded in ' + seg)
        if ac.battery.e_joule > 0:
            soc -= p_chem * dt / ac.battery.e_joule
        dm = fcr['mdot'] * dt
        h2 -= dm
        m -= dm
        e_bat_chem += p_chem * dt
        e_bat_term += p_bat_req * dt
        loss_bat += loss * dt
        e_fc_net += fcr['p_net'] * dt
        e_h2 += dm * LHV_H2
        heat_fc += fcr['heat'] * dt
        e_elec += p_elec * dt
        e_shaft += p_shaft * dt
        x += dx
        h += dh
        t += dt
        peak['p_shaft'] = max(peak['p_shaft'], p_shaft)
        peak['p_elec'] = max(peak['p_elec'], p_elec)
        peak['p_bat'] = max(peak['p_bat'], p_bat_req)
        peak['p_fc'] = max(peak['p_fc'], fcr['p_net'])
        peak['cl'] = max(peak['cl'], cl)
        if ac.battery.energy_kwh > 0:
            peak['c_rate'] = max(peak['c_rate'], p_bat_req / (ac.battery.energy_kwh * 1000.0))
        if cl > ac.clmax:
            flags.add('CL above CLmax in ' + seg)
        if record:
            series['t'].append(t)
            series['x_km'].append(x / 1000.0)
            series['alt_m'].append(h)
            series['tas'].append(v)
            series['p_shaft_kw'].append(p_shaft / 1000.0)
            series['p_elec_kw'].append(p_elec / 1000.0)
            series['p_fc_kw'].append(fcr['p_net'] / 1000.0)
            series['p_bat_kw'].append(p_bat_req / 1000.0)
            series['soc'].append(soc)
            series['h2_kg'].append(max(h2, -1e9))
            series['mass_kg'].append(m)
            series['cl'].append(cl)
            series['ld'].append(ld)
            series['eta_fc'].append(fcr['eta'])
            series['fc_heat_kw'].append(fcr['heat'] / 1000.0)
            series['seg'].append(seg)

    for seg in _segments(cfg, cruise_km):
        t_start, x_start, e_start, soc_start, h2_start = t, x, e_elec, soc, h2
        typ = seg['type']
        if typ in ('taxi', 'takeoff', 'landing'):
            n = max(1, int(math.ceil(seg['time'] / dt_base - 1e-9)))
            dt = seg['time'] / n
            for _ in range(n):
                p_av = min(ac.p_shaft_max, (ac.elec_available(soc) - ac.p_aux) * ac.eta_chain)
                step(typ, dt, seg['frac'] * min(ac.p_shaft_max, max(0.0, p_av)), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        elif typ in ('climb', 'descent'):
            target = seg['to']
            rate = seg['roc'] if typ == 'climb' else -seg['rod']
            v = seg['tas']
            guard = 0
            while (typ == 'climb' and h < target - 1e-6) or (typ == 'descent' and h > target + 1e-6):
                guard += 1
                if guard > 200000:
                    flags.add('segment did not finish: ' + typ)
                    break
                _, _, rho, _ = isa(h)
                rr = rate
                gamma = math.asin(max(-0.99, min(0.99, rr / v)))
                D, cl, cd = ac.drag(m, v, rho, gamma)
                p_req = (D + m * G0 * math.sin(gamma)) * v / ac.eta_prop
                if typ == 'climb':
                    p_av = min(ac.p_shaft_max, (ac.elec_available(soc) - ac.p_aux) * ac.eta_chain)
                    if p_req > p_av:
                        rr = (p_av * ac.eta_prop - D * v) / (m * G0)
                        if rr <= 0.05:
                            flags.add('insufficient power to climb')
                            rr = 0.05
                        gamma = math.asin(min(0.99, rr / v))
                        D, cl, cd = ac.drag(m, v, rho, gamma)
                        p_req = min((D + m * G0 * math.sin(gamma)) * v / ac.eta_prop, p_av)
                dt = dt_base
                remaining = target - h
                if abs(rr * dt) > abs(remaining):
                    dt = abs(remaining / rr)
                vh = v * math.cos(gamma)
                step(typ, dt, p_req, v, gamma, vh * dt, rr * dt, cl, cl / cd)
        elif typ == 'cruise':
            v = seg['tas']
            dist = seg['dist']
            done = 0.0
            while done < dist - 1e-9:
                _, _, rho, _ = isa(h)
                D, cl, cd = ac.drag(m, v, rho)
                p_req = D * v / ac.eta_prop
                dt = min(dt_base, (dist - done) / v)
                step('cruise', dt, p_req, v, 0.0, v * dt, 0.0, cl, cl / cd)
                done += v * dt
        elif typ == 'reserve':
            h_res = seg['alt']
            v = seg['tas']
            n = max(1, int(math.ceil(seg['time'] / dt_base - 1e-9)))
            dt = seg['time'] / n
            for _ in range(n):
                _, _, rho, _ = isa(h_res)
                D, cl, cd = ac.drag(m, v, rho)
                step('reserve', dt, D * v / ac.eta_prop, v, 0.0, 0.0, 0.0, cl, cl / cd)
        seg_rows.append({'segment': typ, 'time_min': (t - t_start) / 60.0, 'dist_km': (x - x_start) / 1000.0, 'energy_kwh': (e_elec - e_start) / 3.6e6, 'soc_end': soc, 'h2_used_kg': h2_start - h2})

    soc_ok = ac.battery.e_joule <= 0 or soc >= ac.battery.soc_min - 1e-12
    h2_ok = h2 >= -1e-12
    power_ok = not any(('limit' in f) or ('insufficient' in f) or ('did not finish' in f) for f in flags)
    range_km = sum(r['dist_km'] for r in seg_rows if r['segment'] in ('climb', 'cruise', 'descent'))
    summary = {
        'feasible': bool(soc_ok and h2_ok and power_ok),
        'energy_ok': bool(soc_ok and h2_ok),
        'power_ok': bool(power_ok),
        'range_km': range_km,
        'cruise_km': cruise_km,
        'block_time_min': t / 60.0,
        'mtow_kg': ac.mtow,
        'landing_mass_kg': m,
        'soc_end': soc,
        'h2_used_kg': ac.tank.h2_kg * ac.tank.usable - h2,
        'h2_left_kg': h2 + h2_unusable,
        'battery_energy_used_kwh': e_bat_chem / 3.6e6,
        'battery_terminal_kwh': e_bat_term / 3.6e6,
        'battery_loss_kwh': loss_bat / 3.6e6,
        'h2_energy_kwh': e_h2 / 3.6e6,
        'fc_energy_kwh': e_fc_net / 3.6e6,
        'fc_heat_kwh': heat_fc / 3.6e6,
        'electric_energy_kwh': e_elec / 3.6e6,
        'shaft_energy_kwh': e_shaft / 3.6e6,
        'source_energy_kwh': (e_bat_chem + e_h2) / 3.6e6,
        'wh_per_km': (e_bat_chem + e_h2) / 3600.0 / max(range_km, 1e-9),
        'wh_per_pax_km': (e_bat_chem + e_h2) / 3600.0 / max(range_km, 1e-9) / max(ac.payload / PAX_KG, 1e-9),
        'peak_shaft_kw': peak['p_shaft'] / 1000.0,
        'peak_elec_kw': peak['p_elec'] / 1000.0,
        'peak_battery_kw': peak['p_bat'] / 1000.0,
        'peak_fc_kw': peak['p_fc'] / 1000.0,
        'peak_c_rate': peak['c_rate'],
        'peak_cl': peak['cl'],
        'fc_heat_rated_kw': ac.fc_heat_rated / 1000.0,
        'battery_kwh': ac.battery.energy_kwh,
        'h2_kg': ac.tank.h2_kg,
        'tank_volume_m3': ac.tank.volume_m3,
        'architecture': ac.arch,
        'flags': sorted(flags),
        'mtow_limit_kg': ac.mtow_limit,
        'mtow_ok': bool(ac.mtow_limit <= 0 or ac.mtow <= ac.mtow_limit + 1e-9),
    }
    return {'summary': summary, 'segments': seg_rows, 'series': series if record else None, 'mass': ac.mass_breakdown()}


def max_range(cfg, tol_km=0.01):
    ac = Aircraft(cfg)
    if not fly(cfg, 0.0, record=False, ac=ac)['summary']['feasible']:
        r = fly(cfg, 0.0, record=True, ac=ac)
        r['summary']['max_range_reason'] = 'energy storage too small for take-off, climb, descent and reserve'
        return r
    probe = fly(cfg, 1.0, record=False, ac=ac)['summary']
    if not probe['power_ok']:
        r = fly(cfg, 1.0, record=True, ac=ac)
        r['summary']['feasible'] = False
        r['summary']['max_range_reason'] = 'insufficient power: ' + '; '.join(probe['flags'])
        return r
    lo, hi = 0.0, 50.0
    while fly(cfg, hi, record=False, ac=ac)['summary']['feasible']:
        lo = hi
        hi *= 2.0
        if hi > 1e6:
            break
    while hi - lo > tol_km:
        mid = 0.5 * (lo + hi)
        if fly(cfg, mid, record=False, ac=ac)['summary']['feasible']:
            lo = mid
        else:
            hi = mid
    return fly(cfg, lo, record=True, ac=ac)

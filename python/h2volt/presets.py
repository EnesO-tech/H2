"""
Created on Fri Sep 11 16:10:39 2026

@author: eneso
"""
PRESETS = [
    {
        'id': 'commuter19_fc',
        'name': '19-seat commuter · hydrogen fuel cell (LH2)',
        'description': 'Dornier-228-class twin turboprop converted to a liquid-hydrogen fuel-cell powertrain with two electric propeller drives.',
        'config': {
            'architecture': 'fuelcell',
            'payload_kg': 1710.0, 'max_payload_kg': 1805.0,
            'airframe': {'oe_mass_kg': 2850.0, 'mtow_limit_kg': 6400.0, 'wing_area_m2': 32.0, 'aspect_ratio': 9.0, 'oswald': 0.80, 'cd0': 0.030, 'cl_max': 1.8},
            'propulsion': {'eta_propeller': 0.85, 'eta_gearbox': 0.98, 'eta_motor': 0.96, 'eta_inverter': 0.98, 'shaft_power_kw': 600.0, 'aux_power_kw': 10.0, 'motor_kwkg': 6.0, 'inverter_kwkg': 18.0, 'thermal_kg_per_kw': 0.6, 'n_motors': 2},
            'battery': {'energy_kwh': 50.0, 'specific_energy_whkg': 220.0, 'specific_power_kwkg': 2.5, 'soc_min': 0.2, 'efficiency_at_pmax': 0.92, 'voltage_v': 800.0},
            'fuelcell': {'power_kw': 700.0, 'specific_power_kwkg': 1.5, 'model': 'polarization', 'bop_fraction': 0.10},
            'tank': {'type': 'LH2', 'h2_kg': 180.0, 'gravimetric_index': 0.35, 'usable_fraction': 0.97},
            'hybrid': {'recharge': True, 'soc_target': 0.6},
            'mission': {'cruise_alt_m': 3000.0, 'cruise_tas_mps': 85.0, 'climb_rate_mps': 5.0, 'climb_tas_mps': 70.0, 'descent_rate_mps': 5.0, 'descent_tas_mps': 85.0, 'reserve_min': 30.0, 'reserve_alt_m': 1000.0, 'reserve_tas_mps': 70.0, 'taxi_s': 300.0, 'takeoff_s': 60.0, 'landing_s': 240.0, 'dt_s': 10.0},
        },
    },
    {
        'id': 'hybrid9',
        'name': '9-seat utility · fuel cell + battery hybrid',
        'description': 'Single-engine utility aircraft: the fuel cell covers cruise, the battery covers take-off and climb peaks and is recharged in cruise.',
        'config': {
            'architecture': 'hybrid',
            'payload_kg': 855.0, 'max_payload_kg': 900.0,
            'airframe': {'oe_mass_kg': 1750.0, 'mtow_limit_kg': 3995.0, 'wing_area_m2': 26.0, 'aspect_ratio': 9.7, 'oswald': 0.78, 'cd0': 0.034, 'cl_max': 1.9},
            'propulsion': {'eta_propeller': 0.84, 'eta_gearbox': 0.98, 'eta_motor': 0.96, 'eta_inverter': 0.98, 'shaft_power_kw': 500.0, 'aux_power_kw': 5.0, 'motor_kwkg': 6.0, 'inverter_kwkg': 18.0, 'thermal_kg_per_kw': 0.6, 'n_motors': 1},
            'battery': {'energy_kwh': 60.0, 'specific_energy_whkg': 220.0, 'specific_power_kwkg': 3.5, 'soc_min': 0.2, 'efficiency_at_pmax': 0.92, 'voltage_v': 800.0},
            'fuelcell': {'power_kw': 420.0, 'specific_power_kwkg': 1.5, 'model': 'polarization', 'bop_fraction': 0.10},
            'tank': {'type': 'LH2', 'h2_kg': 60.0, 'gravimetric_index': 0.30, 'usable_fraction': 0.97},
            'hybrid': {'recharge': True, 'soc_target': 0.6},
            'mission': {'cruise_alt_m': 3000.0, 'cruise_tas_mps': 85.0, 'climb_rate_mps': 5.0, 'climb_tas_mps': 60.0, 'descent_rate_mps': 4.0, 'descent_tas_mps': 75.0, 'reserve_min': 30.0, 'reserve_alt_m': 1000.0, 'reserve_tas_mps': 60.0, 'taxi_s': 300.0, 'takeoff_s': 60.0, 'landing_s': 240.0, 'dt_s': 10.0},
        },
    },
    {
        'id': 'trainer_battery',
        'name': '2-seat trainer · battery-electric',
        'description': 'Light two-seat electric trainer with a lithium-ion pack, typical of today\'s certified electric training aircraft.',
        'config': {
            'architecture': 'battery',
            'payload_kg': 180.0, 'max_payload_kg': 200.0,
            'airframe': {'oe_mass_kg': 300.0, 'mtow_limit_kg': 650.0, 'wing_area_m2': 9.5, 'aspect_ratio': 8.5, 'oswald': 0.78, 'cd0': 0.032, 'cl_max': 1.5},
            'propulsion': {'eta_propeller': 0.80, 'eta_gearbox': 1.0, 'eta_motor': 0.95, 'eta_inverter': 0.98, 'shaft_power_kw': 60.0, 'aux_power_kw': 0.5, 'motor_kwkg': 5.0, 'inverter_kwkg': 15.0, 'thermal_kg_per_kw': 0.6, 'n_motors': 1},
            'battery': {'energy_kwh': 24.0, 'specific_energy_whkg': 165.0, 'specific_power_kwkg': 1.2, 'soc_min': 0.10, 'efficiency_at_pmax': 0.92, 'voltage_v': 400.0},
            'fuelcell': {'power_kw': 40.0, 'specific_power_kwkg': 1.0, 'model': 'polarization', 'bop_fraction': 0.10},
            'tank': {'type': 'CGH2', 'h2_kg': 4.0, 'gravimetric_index': 0.06, 'usable_fraction': 0.95},
            'hybrid': {'recharge': True, 'soc_target': 0.6},
            'mission': {'cruise_alt_m': 600.0, 'cruise_tas_mps': 46.0, 'climb_rate_mps': 3.0, 'climb_tas_mps': 38.0, 'descent_rate_mps': 3.0, 'descent_tas_mps': 45.0, 'reserve_min': 30.0, 'reserve_alt_m': 450.0, 'reserve_tas_mps': 36.0, 'taxi_s': 300.0, 'takeoff_s': 60.0, 'landing_s': 240.0, 'dt_s': 10.0},
        },
    },
]


def preset(pid):
    for p in PRESETS:
        if p['id'] == pid:
            return p
    raise KeyError(pid)

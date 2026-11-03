"""Protoss game facts: ids, costs, footprints, who makes what, and what needs what. The Protoss
counterpart of gary/terran.py and gary/zerg.py, in the same form (docs/REFACTOR.md: the race object
proven on three races; no Protoss executor yet).

Unit and building ids are the game's (units.dat), tech and upgrade ids too. Upgrade costs are
level-1 costs. Checked against units.dat by tests/test_game_data.py.
"""

from __future__ import annotations

# units
CORSAIR, DARK_TEMPLAR, DARK_ARCHON, PROBE, ZEALOT, DRAGOON, HIGH_TEMPLAR, ARCHON = 60, 61, 63, 64, 65, 66, 67, 68
SHUTTLE, SCOUT, ARBITER, CARRIER, INTERCEPTOR, REAVER, OBSERVER, SCARAB = 69, 70, 71, 72, 73, 83, 84, 85
# buildings
NEXUS, ROBOTICS, PYLON, ASSIMILATOR, OBSERVATORY, GATEWAY, CANNON = 154, 155, 156, 157, 159, 160, 162
CITADEL, CYBER, TEMPLAR_ARCHIVES, FORGE, STARGATE = 163, 164, 165, 166, 167
FLEET_BEACON, ARBITER_TRIBUNAL, SUPPORT_BAY, BATTERY = 169, 170, 171, 172
GEYSER = 188
TOWN_HALLS = {NEXUS}

COST = {  # (minerals, gas)
    PROBE: (50, 0), ZEALOT: (100, 0), DRAGOON: (125, 50), HIGH_TEMPLAR: (50, 150), DARK_TEMPLAR: (125, 100),
    SHUTTLE: (200, 0), REAVER: (200, 100), OBSERVER: (25, 75), SCOUT: (275, 125), CORSAIR: (150, 100),
    CARRIER: (350, 250), ARBITER: (100, 350),
    NEXUS: (400, 0), PYLON: (100, 0), ASSIMILATOR: (100, 0), GATEWAY: (150, 0), FORGE: (150, 0),
    CANNON: (150, 0), CYBER: (200, 0), BATTERY: (100, 0), CITADEL: (150, 100), ROBOTICS: (200, 200),
    STARGATE: (150, 150), TEMPLAR_ARCHIVES: (150, 200), OBSERVATORY: (50, 100), SUPPORT_BAY: (150, 100),
    FLEET_BEACON: (300, 200), ARBITER_TRIBUNAL: (200, 150),
}
SUPPLY = {  # whole supply
    PROBE: 1, ZEALOT: 2, DRAGOON: 2, HIGH_TEMPLAR: 2, DARK_TEMPLAR: 2, ARCHON: 4, DARK_ARCHON: 4,
    SHUTTLE: 2, REAVER: 4, OBSERVER: 1, SCOUT: 3, CORSAIR: 2, CARRIER: 6, ARBITER: 4,
}
SUPPLY_PROVIDED = {PYLON: 8, NEXUS: 9}
SIZE = {  # footprint in tiles
    NEXUS: (4, 3), PYLON: (2, 2), ASSIMILATOR: (4, 2), GATEWAY: (4, 3), FORGE: (3, 2), CANNON: (2, 2),
    CYBER: (3, 2), BATTERY: (3, 2), CITADEL: (3, 2), ROBOTICS: (3, 2), STARGATE: (4, 3),
    TEMPLAR_ARCHIVES: (3, 2), OBSERVATORY: (3, 2), SUPPORT_BAY: (3, 2), FLEET_BEACON: (3, 2),
    ARBITER_TRIBUNAL: (3, 2),
}

# who makes what: the building that warps a unit in, and the pair two units merge from
PRODUCER = {PROBE: NEXUS, ZEALOT: GATEWAY, DRAGOON: GATEWAY, HIGH_TEMPLAR: GATEWAY, DARK_TEMPLAR: GATEWAY,
            SHUTTLE: ROBOTICS, REAVER: ROBOTICS, OBSERVER: ROBOTICS,
            SCOUT: STARGATE, CORSAIR: STARGATE, CARRIER: STARGATE, ARBITER: STARGATE}
MERGE = {ARCHON: HIGH_TEMPLAR, DARK_ARCHON: DARK_TEMPLAR}
# what a unit fires that it builds itself (it is built empty): its ammunition and the minerals of one
AMMO = {REAVER: (SCARAB, 15), CARRIER: (INTERCEPTOR, 25)}
# where the pros start each building, per matchup: (until this minute, its shares at the main, the natural and a newer
# base, its share on that base's mineral side), drawn by the executor (option place); eval/placement.py over 240
# modern games of each matchup, each building by the base it stands nearest of all the player's by 12:00 (the forge-
# first wall at the natural before its Nexus: the natural's), windows with 0.1 a game at least; a stop-gap (AGENTS.md,
# #65)
PLACE = {
    "PvZ": {
        ROBOTICS: [(12, (0.07, 0.9, 0.03), 0.23)],
        PYLON: [(5, (0.52, 0.46, 0.02), 0.19), (8, (0.73, 0.26, 0.02), 0.34), (12, (0.68, 0.17, 0.15), 0.21)],
        OBSERVATORY: [(12, (0.72, 0.28, 0.0), 0.23)],
        GATEWAY: [(5, (0.14, 0.86, 0.0), 0.03), (8, (0.87, 0.13, 0.0), 0.05), (12, (0.93, 0.05, 0.03), 0.01)],
        CANNON: [(5, (0.08, 0.9, 0.03), 0.03), (8, (0.29, 0.71, 0.0), 0.33), (12, (0.26, 0.45, 0.29), 0.39)],
        CITADEL: [(5, (0.94, 0.06, 0.0), 0.19), (8, (0.97, 0.03, 0.0), 0.23)],
        CYBER: [(5, (0.71, 0.29, 0.0), 0.27), (8, (0.92, 0.08, 0.0), 0.46)],
        TEMPLAR_ARCHIVES: [(8, (0.95, 0.05, 0.0), 0.23), (12, (0.94, 0.06, 0.0), 0.25)],
        FORGE: [(5, (0.17, 0.83, 0.0), 0.07), (8, (0.9, 0.1, 0.0), 0.17), (12, (0.85, 0.15, 0.0), 0.19)],
        STARGATE: [(5, (0.9, 0.1, 0.0), 0.13), (8, (0.87, 0.13, 0.0), 0.15)],
    },
    "PvT": {
        ROBOTICS: [(5, (0.96, 0.04, 0.0), 0.14), (8, (0.96, 0.04, 0.0), 0.08), (12, (0.75, 0.25, 0.0), 0.35)],
        PYLON: [(5, (0.67, 0.3, 0.02), 0.15), (8, (0.36, 0.35, 0.28), 0.14), (12, (0.32, 0.17, 0.52), 0.16)],
        OBSERVATORY: [(5, (0.88, 0.12, 0.0), 0.25), (8, (0.84, 0.16, 0.01), 0.17), (12, (0.68, 0.32, 0.0), 0.11)],
        GATEWAY: [(5, (0.83, 0.15, 0.02), 0.03), (8, (0.94, 0.04, 0.01), 0.02), (12, (0.88, 0.06, 0.06), 0.01)],
        CANNON: [(8, (0.42, 0.25, 0.33), 0.92), (12, (0.12, 0.12, 0.75), 0.53)],
        CITADEL: [(5, (0.87, 0.13, 0.0), 0.04), (8, (0.88, 0.09, 0.04), 0.2), (12, (0.95, 0.04, 0.01), 0.24)],
        CYBER: [(5, (0.95, 0.05, 0.0), 0.32)],
        TEMPLAR_ARCHIVES: [(5, (0.85, 0.15, 0.0), 0.15), (8, (0.86, 0.11, 0.04), 0.18), (12, (0.9, 0.09, 0.01), 0.16)],
        FORGE: [(8, (0.77, 0.15, 0.08), 0.19), (12, (0.84, 0.05, 0.12), 0.2)],
        STARGATE: [(8, (0.87, 0.08, 0.06), 0.04), (12, (0.75, 0.17, 0.07), 0.05)],
        FLEET_BEACON: [(8, (0.83, 0.0, 0.17), 0.0)],
        ARBITER_TRIBUNAL: [(12, (0.83, 0.07, 0.1), 0.1)],
        SUPPORT_BAY: [(5, (0.88, 0.12, 0.0), 0.06), (8, (0.95, 0.05, 0.0), 0.18), (12, (0.9, 0.1, 0.0), 0.15)],
    },
    "PvP": {
        ROBOTICS: [(5, (0.77, 0.22, 0.01), 0.03), (8, (0.57, 0.42, 0.01), 0.07), (12, (0.33, 0.67, 0.0), 0.14)],
        PYLON: [(5, (0.82, 0.17, 0.02), 0.19), (8, (0.62, 0.32, 0.06), 0.18), (12, (0.51, 0.33, 0.16), 0.19)],
        OBSERVATORY: [(5, (1.0, 0.0, 0.0), 0.25), (8, (0.99, 0.01, 0.0), 0.28), (12, (0.85, 0.15, 0.0), 0.26)],
        GATEWAY: [(5, (0.91, 0.08, 0.01), 0.05), (8, (0.98, 0.02, 0.0), 0.04), (12, (0.94, 0.05, 0.01), 0.01)],
        CANNON: [(5, (0.07, 0.93, 0.0), 0.06), (8, (0.21, 0.78, 0.02), 0.28), (12, (0.29, 0.34, 0.37), 0.55)],
        CITADEL: [(5, (1.0, 0.0, 0.0), 0.28), (8, (0.97, 0.03, 0.0), 0.26), (12, (0.97, 0.0, 0.03), 0.19)],
        CYBER: [(5, (1.0, 0.0, 0.0), 0.26)],
        TEMPLAR_ARCHIVES: [(5, (1.0, 0.0, 0.0), 0.26), (8, (1.0, 0.0, 0.0), 0.21), (12, (0.94, 0.03, 0.03), 0.26)],
        FORGE: [(5, (0.86, 0.14, 0.0), 0.34), (8, (0.86, 0.14, 0.0), 0.11), (12, (0.81, 0.16, 0.03), 0.22)],
        SUPPORT_BAY: [(5, (0.97, 0.03, 0.0), 0.21), (8, (0.99, 0.01, 0.0), 0.16), (12, (0.96, 0.04, 0.0), 0.12)],
        BATTERY: [(5, (0.65, 0.35, 0.0), 0.04), (8, (0.21, 0.79, 0.0), 0.0)],
    },
}
# each building's first and second of the game apart: [(its shares at the main, the natural and a newer base, its
# share on the mineral side)] (eval/placement.py's firsts, where 3 games in 10 have it at least): a window's shares
# mix them, while the pros' first Pylon in PvZ stands at the natural in 92% of games and the second in the main in 84%
# (the window's share 47%), the first Gateway with the first Pylon in all 80 of a sample
PLACE_FIRST = {
    "PvZ": {
        ROBOTICS: [((0.08, 0.9, 0.02), 0.23)],
        PYLON: [((0.08, 0.92, 0.0), 0.02), ((0.85, 0.11, 0.04), 0.3)],
        OBSERVATORY: [((0.73, 0.27, 0.0), 0.24)],
        GATEWAY: [((0.09, 0.91, 0.0), 0.01), ((0.63, 0.36, 0.0), 0.1)],
        CANNON: [((0.05, 0.93, 0.02), 0.03), ((0.25, 0.73, 0.02), 0.19)],
        CITADEL: [((0.96, 0.04, 0.0), 0.23)],
        CYBER: [((0.73, 0.27, 0.0), 0.29)],
        TEMPLAR_ARCHIVES: [((0.96, 0.04, 0.0), 0.23)],
        FORGE: [((0.2, 0.8, 0.0), 0.07), ((0.85, 0.15, 0.0), 0.19)],
        STARGATE: [((0.92, 0.08, 0.0), 0.1)],
    },
    "PvT": {
        ROBOTICS: [((0.95, 0.05, 0.0), 0.12)],
        PYLON: [((0.79, 0.2, 0.0), 0.1), ((0.8, 0.19, 0.01), 0.25)],
        OBSERVATORY: [((0.83, 0.17, 0.0), 0.17)],
        GATEWAY: [((0.76, 0.23, 0.01), 0.02), ((0.95, 0.04, 0.01), 0.03)],
        CANNON: [((0.17, 0.08, 0.75), 0.58), ((0.13, 0.14, 0.73), 0.54)],
        CITADEL: [((0.92, 0.07, 0.02), 0.21)],
        CYBER: [((0.95, 0.05, 0.0), 0.32)],
        TEMPLAR_ARCHIVES: [((0.88, 0.1, 0.02), 0.16)],
        FORGE: [((0.82, 0.07, 0.11), 0.22)],
        SUPPORT_BAY: [((0.93, 0.07, 0.0), 0.16)],
    },
    "PvP": {
        ROBOTICS: [((0.64, 0.35, 0.01), 0.06)],
        PYLON: [((0.96, 0.04, 0.0), 0.1), ((0.85, 0.15, 0.0), 0.29)],
        OBSERVATORY: [((0.96, 0.04, 0.0), 0.26)],
        GATEWAY: [((0.9, 0.08, 0.02), 0.03), ((0.94, 0.05, 0.0), 0.05)],
        CANNON: [((0.15, 0.75, 0.11), 0.32), ((0.23, 0.67, 0.1), 0.34)],
        CITADEL: [((0.98, 0.01, 0.01), 0.25)],
        CYBER: [((1.0, 0.0, 0.0), 0.25)],
        TEMPLAR_ARCHIVES: [((0.99, 0.01, 0.0), 0.25)],
        FORGE: [((0.88, 0.11, 0.01), 0.25)],
        SUPPORT_BAY: [((0.98, 0.02, 0.0), 0.17)],
    },
}
# ... and per build style (gary/styles.py's labels, 20 of its games at least): an opening is one plan (PvZ's forge-
# first pros build all of it at the natural, the gateway-first ones their Forge in the main in 45% of games)
PLACE_FIRST_STYLE = {
    "PvZ": {
        20: {
            ROBOTICS: [((0.07, 0.91, 0.02), 0.18)],
            PYLON: [((0.17, 0.83, 0.0), 0.04), ((0.97, 0.03, 0.0), 0.37)],
            OBSERVATORY: [((0.77, 0.23, 0.0), 0.28)],
            GATEWAY: [((0.17, 0.83, 0.0), 0.03), ((0.66, 0.34, 0.0), 0.07)],
            CANNON: [((0.04, 0.96, 0.0), 0.05), ((0.14, 0.84, 0.01), 0.16)],
            CITADEL: [((0.96, 0.04, 0.0), 0.22)],
            CYBER: [((0.74, 0.26, 0.0), 0.2)],
            TEMPLAR_ARCHIVES: [((0.97, 0.03, 0.0), 0.27)],
            FORGE: [((0.45, 0.55, 0.0), 0.14)],
            STARGATE: [((0.95, 0.05, 0.0), 0.11)],
        },
        21: {
            ROBOTICS: [((0.05, 0.92, 0.03), 0.3)],
            PYLON: [((0.0, 1.0, 0.0), 0.0), ((0.78, 0.16, 0.06), 0.31)],
            OBSERVATORY: [((0.69, 0.31, 0.0), 0.17)],
            GATEWAY: [((0.0, 1.0, 0.0), 0.0), ((0.62, 0.38, 0.0), 0.15)],
            CANNON: [((0.02, 0.94, 0.04), 0.0), ((0.31, 0.66, 0.03), 0.2)],
            CITADEL: [((0.96, 0.04, 0.0), 0.22)],
            CYBER: [((0.82, 0.18, 0.0), 0.34)],
            TEMPLAR_ARCHIVES: [((0.94, 0.06, 0.0), 0.25)],
            FORGE: [((0.0, 1.0, 0.0), 0.0)],
            STARGATE: [((0.91, 0.09, 0.0), 0.09)],
        },
        22: {
            ROBOTICS: [((0.09, 0.91, 0.0), 0.09)],
            PYLON: [((0.03, 0.97, 0.0), 0.03), ((0.79, 0.17, 0.03), 0.21)],
            OBSERVATORY: [((0.8, 0.2, 0.0), 0.4)],
            GATEWAY: [((0.03, 0.97, 0.0), 0.0), ((0.72, 0.28, 0.0), 0.03)],
            CANNON: [((0.0, 1.0, 0.0), 0.0), ((0.21, 0.79, 0.0), 0.28)],
            CITADEL: [((0.93, 0.07, 0.0), 0.31)],
            CYBER: [((0.34, 0.66, 0.0), 0.31)],
            TEMPLAR_ARCHIVES: [((0.97, 0.03, 0.0), 0.07)],
            FORGE: [((0.14, 0.86, 0.0), 0.07), ((0.77, 0.23, 0.0), 0.08)],
            STARGATE: [((0.86, 0.14, 0.0), 0.17)],
        },
    },
    "PvT": {
        0: {
            ROBOTICS: [((0.97, 0.03, 0.0), 0.14)],
            PYLON: [((0.7, 0.29, 0.01), 0.12), ((0.93, 0.07, 0.0), 0.29)],
            OBSERVATORY: [((0.87, 0.13, 0.0), 0.18)],
            GATEWAY: [((0.68, 0.31, 0.01), 0.02), ((0.99, 0.01, 0.0), 0.01)],
            CANNON: [((0.17, 0.05, 0.78), 0.62), ((0.08, 0.13, 0.79), 0.57)],
            CITADEL: [((0.94, 0.05, 0.02), 0.24)],
            CYBER: [((0.94, 0.06, 0.0), 0.37)],
            TEMPLAR_ARCHIVES: [((0.87, 0.11, 0.02), 0.17)],
            FORGE: [((0.84, 0.05, 0.11), 0.2)],
            SUPPORT_BAY: [((0.95, 0.05, 0.0), 0.13)],
        },
        1: {
            ROBOTICS: [((0.94, 0.06, 0.0), 0.11)],
            PYLON: [((0.98, 0.02, 0.0), 0.09), ((0.41, 0.59, 0.0), 0.17)],
            OBSERVATORY: [((0.76, 0.22, 0.02), 0.19)],
            GATEWAY: [((0.96, 0.02, 0.02), 0.04), ((0.89, 0.07, 0.04), 0.06)],
            CANNON: [((0.12, 0.06, 0.82), 0.45), ((0.15, 0.15, 0.7), 0.44)],
            CITADEL: [((0.89, 0.09, 0.02), 0.2)],
            CYBER: [((1.0, 0.0, 0.0), 0.28)],
            TEMPLAR_ARCHIVES: [((0.91, 0.09, 0.0), 0.14)],
            FORGE: [((0.78, 0.07, 0.15), 0.22)],
            STARGATE: [((0.88, 0.06, 0.06), 0.0)],
            SUPPORT_BAY: [((0.88, 0.12, 0.0), 0.26)],
        },
        2: {
            ROBOTICS: [((0.82, 0.18, 0.0), 0.0)],
            PYLON: [((0.9, 0.1, 0.0), 0.05), ((0.95, 0.05, 0.0), 0.2)],
            OBSERVATORY: [((0.5, 0.5, 0.0), 0.1)],
            GATEWAY: [((0.8, 0.15, 0.05), 0.0), ((0.85, 0.15, 0.0), 0.0)],
            CANNON: [((0.23, 0.23, 0.54), 0.54), ((0.25, 0.17, 0.58), 0.58)],
            CITADEL: [((0.84, 0.16, 0.0), 0.05)],
            CYBER: [((0.95, 0.05, 0.0), 0.15)],
            TEMPLAR_ARCHIVES: [((0.89, 0.11, 0.0), 0.16)],
            FORGE: [((0.81, 0.12, 0.06), 0.38)],
            STARGATE: [((0.92, 0.08, 0.0), 0.08), ((1.0, 0.0, 0.0), 0.17)],
            ARBITER_TRIBUNAL: [((1.0, 0.0, 0.0), 0.11)],
        },
    },
    "PvP": {
        40: {
            ROBOTICS: [((0.7, 0.29, 0.01), 0.04)],
            PYLON: [((0.96, 0.04, 0.01), 0.09), ((0.88, 0.12, 0.0), 0.32)],
            OBSERVATORY: [((0.99, 0.01, 0.0), 0.25)],
            GATEWAY: [((0.9, 0.08, 0.02), 0.02), ((0.94, 0.06, 0.01), 0.03)],
            CANNON: [((0.12, 0.76, 0.12), 0.4)],
            CYBER: [((1.0, 0.0, 0.0), 0.23)],
            FORGE: [((0.87, 0.13, 0.0), 0.2)],
            SUPPORT_BAY: [((0.98, 0.02, 0.0), 0.15)],
        },
        41: {
            ROBOTICS: [((0.47, 0.53, 0.0), 0.09)],
            PYLON: [((0.97, 0.03, 0.0), 0.18), ((0.95, 0.05, 0.0), 0.31)],
            OBSERVATORY: [((0.94, 0.06, 0.0), 0.34)],
            GATEWAY: [((0.95, 0.05, 0.0), 0.08), ((0.95, 0.05, 0.0), 0.13)],
            CANNON: [((0.21, 0.68, 0.11), 0.29), ((0.26, 0.63, 0.11), 0.33)],
            CITADEL: [((1.0, 0.0, 0.0), 0.26)],
            CYBER: [((1.0, 0.0, 0.0), 0.31)],
            TEMPLAR_ARCHIVES: [((1.0, 0.0, 0.0), 0.29)],
            FORGE: [((0.94, 0.06, 0.0), 0.29)],
        },
    },
}
# how near the workers' lanes (a town hall to each of its minerals) the pros start a building on a base's mineral
# side: the median gap from its footprint, in tiles (eval/placement.py, 10 starts there at least): cannons hug the
# Nexus over the lanes' start, Pylons stand behind the mineral line
PLACE_LANE = {
    "PvZ": {ROBOTICS: 0.4, PYLON: 0.8, OBSERVATORY: 0.6, GATEWAY: 1.0, CANNON: 0.1, CITADEL: 0.6, CYBER: 0.6,
            TEMPLAR_ARCHIVES: 1.3, FORGE: 0.6, STARGATE: 0.5},
    "PvT": {ROBOTICS: 1.0, PYLON: 0.8, OBSERVATORY: 1.0, GATEWAY: 1.2, CANNON: -0.6, CITADEL: 1.9, CYBER: 0.6,
            TEMPLAR_ARCHIVES: 1.3, FORGE: 1.0, SUPPORT_BAY: 0.6},
    "PvP": {ROBOTICS: 1.0, PYLON: 0.8, OBSERVATORY: 1.0, GATEWAY: 2.2, CANNON: -0.1, CITADEL: 1.3, CYBER: 1.0,
            TEMPLAR_ARCHIVES: 1.4, FORGE: 0.7, SUPPORT_BAY: 1.0},
}

# what must exist (completed) before something can be made (buildings also need a pylon's power)
REQUIRES = {
    GATEWAY: [NEXUS], FORGE: [NEXUS], CYBER: [GATEWAY], CANNON: [FORGE], BATTERY: [GATEWAY],
    CITADEL: [CYBER], ROBOTICS: [CYBER], STARGATE: [CYBER], TEMPLAR_ARCHIVES: [CITADEL],
    OBSERVATORY: [ROBOTICS], SUPPORT_BAY: [ROBOTICS], FLEET_BEACON: [STARGATE],
    ARBITER_TRIBUNAL: [TEMPLAR_ARCHIVES, STARGATE],
    ZEALOT: [GATEWAY], DRAGOON: [CYBER], HIGH_TEMPLAR: [TEMPLAR_ARCHIVES], DARK_TEMPLAR: [TEMPLAR_ARCHIVES],
    SHUTTLE: [ROBOTICS], REAVER: [SUPPORT_BAY], OBSERVER: [OBSERVATORY], SCOUT: [STARGATE],
    CORSAIR: [STARGATE], CARRIER: [FLEET_BEACON], ARBITER: [ARBITER_TRIBUNAL],
}

# research (tech id -> building, cost) and upgrades (upgrade id -> building, level-1 cost, levels)
RESEARCH = {19: (TEMPLAR_ARCHIVES, (200, 200)),   # psionic storm
            20: (TEMPLAR_ARCHIVES, (150, 150)),   # hallucination
            27: (TEMPLAR_ARCHIVES, (200, 200)),   # mind control
            31: (TEMPLAR_ARCHIVES, (100, 100)),   # maelstrom
            21: (ARBITER_TRIBUNAL, (150, 150)),   # recall
            22: (ARBITER_TRIBUNAL, (150, 150)),   # stasis field
            25: (FLEET_BEACON, (200, 200))}       # disruption web
UPGRADE = {5: (FORGE, (100, 100), 3),             # ground armor
           13: (FORGE, (100, 100), 3),            # ground weapons
           15: (FORGE, (200, 200), 3),            # plasma shields
           6: (CYBER, (150, 150), 3),             # air armor
           14: (CYBER, (100, 100), 3),            # air weapons
           33: (CYBER, (150, 150), 1),            # singularity charge (dragoon range)
           34: (CITADEL, (150, 150), 1),          # leg enhancements (zealot speed)
           35: (SUPPORT_BAY, (200, 200), 1),      # scarab damage
           36: (SUPPORT_BAY, (200, 200), 1),      # reaver capacity
           37: (SUPPORT_BAY, (200, 200), 1),      # gravitic drive (shuttle speed)
           38: (OBSERVATORY, (100, 100), 1),      # sensor array
           39: (OBSERVATORY, (100, 100), 1),      # gravitic boosters
           40: (TEMPLAR_ARCHIVES, (150, 150), 1),   # khaydarin amulet
           49: (TEMPLAR_ARCHIVES, (150, 150), 1),   # argus talisman
           41: (FLEET_BEACON, (100, 100), 1),     # apial sensors
           42: (FLEET_BEACON, (200, 200), 1),     # gravitic thrusters
           43: (FLEET_BEACON, (100, 100), 1),     # carrier capacity
           47: (FLEET_BEACON, (100, 100), 1),     # argus jewel
           44: (ARBITER_TRIBUNAL, (150, 150), 1)}   # khaydarin core
UPGRADE_LEVEL_2_NEEDS = {5: TEMPLAR_ARCHIVES, 13: TEMPLAR_ARCHIVES, 15: CYBER, 6: FLEET_BEACON, 14: FLEET_BEACON}

ARMY = {ZEALOT, DRAGOON, HIGH_TEMPLAR, DARK_TEMPLAR, ARCHON, DARK_ARCHON, REAVER, SCOUT, CORSAIR, CARRIER,
        ARBITER}
PRODUCTION = {NEXUS, GATEWAY, ROBOTICS, STARGATE}
NAMES = {CORSAIR: "Corsair", DARK_TEMPLAR: "Dark Templar", DARK_ARCHON: "Dark Archon", PROBE: "Probe",
         ZEALOT: "Zealot", DRAGOON: "Dragoon", HIGH_TEMPLAR: "High Templar", ARCHON: "Archon",
         SHUTTLE: "Shuttle", SCOUT: "Scout", ARBITER: "Arbiter", CARRIER: "Carrier", INTERCEPTOR: "Interceptor",
         REAVER: "Reaver", OBSERVER: "Observer", SCARAB: "Scarab",
         NEXUS: "Nexus", ROBOTICS: "Robotics Facility", PYLON: "Pylon", ASSIMILATOR: "Assimilator",
         OBSERVATORY: "Observatory", GATEWAY: "Gateway", CANNON: "Photon Cannon", CITADEL: "Citadel of Adun",
         CYBER: "Cybernetics Core", TEMPLAR_ARCHIVES: "Templar Archives", FORGE: "Forge", STARGATE: "Stargate",
         FLEET_BEACON: "Fleet Beacon", ARBITER_TRIBUNAL: "Arbiter Tribunal", SUPPORT_BAY: "Robotics Support Bay",
         BATTERY: "Shield Battery"}
TECH_NAMES = {19: "Psionic Storm", 20: "Hallucination", 27: "Mind Control", 31: "Maelstrom", 21: "Recall",
              22: "Stasis Field", 25: "Disruption Web"}
UPGRADE_NAMES = {5: "Protoss Ground Armor", 13: "Protoss Ground Weapons", 15: "Protoss Plasma Shields",
                 6: "Protoss Air Armor", 14: "Protoss Air Weapons", 33: "Singularity Charge",
                 34: "Leg Enhancements", 35: "Scarab Damage", 36: "Reaver Capacity", 37: "Gravitic Drive",
                 38: "Sensor Array", 39: "Gravitic Boosters", 40: "Khaydarin Amulet", 49: "Argus Talisman",
                 41: "Apial Sensors", 42: "Gravitic Thrusters", 43: "Carrier Capacity", 47: "Argus Jewel",
                 44: "Khaydarin Core"}

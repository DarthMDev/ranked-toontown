from panda3d.core import Point3

DEFAULT_ELEVATOR_COUNTDOWN = 10.0  # How much time to wait for boss elevators, building elevators, facility entrances
ELEVATOR_NORMAL = 0
ELEVATOR_VP = 1
ELEVATOR_CJ = 4

ElevatorData = {
    ELEVATOR_NORMAL: {
        'openTime': 2.0,
        'closeTime': 2.0,
        'width': 3.5,
        'countdown': DEFAULT_ELEVATOR_COUNTDOWN,
        'sfxVolume': 1.0,
        'collRadius': 5
    },
    ELEVATOR_VP: {
        'openTime': 4.0,
        'closeTime': 4.0,
        'width': 11.5,
        'countdown': DEFAULT_ELEVATOR_COUNTDOWN,
        'sfxVolume': 0.7,
        'collRadius': 7.5
    },
    ELEVATOR_CJ: {
        'openTime': 4.0,
        'closeTime': 4.0,
        'width': 15.8,
        'countdown': DEFAULT_ELEVATOR_COUNTDOWN,
        'sfxVolume': 0.7,
        'collRadius': 7.5
    },
}


def getLeftClosePoint(type):
    width = ElevatorData[type]['width']
    return Point3(width, 0, 0)


def getRightClosePoint(type):
    width = ElevatorData[type]['width']
    return Point3(-width, 0, 0)


def getLeftOpenPoint(type):
    return Point3(0, 0, 0)


def getRightOpenPoint(type):
    return Point3(0, 0, 0)
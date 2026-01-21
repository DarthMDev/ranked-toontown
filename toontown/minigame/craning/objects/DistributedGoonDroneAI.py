"""
DEPRECATED: This file is kept for backwards compatibility.
The drone system has been refactored into specialized classes.

New structure:
- DistributedGoonDroneBaseAI - Base AI class with common functionality
- DistributedGoonDroneLaserAI - Laser drone AI implementation
- DistributedGoonDroneHealAI - Heal drone AI implementation
- DistributedGoonDroneExplodeyAI - Explodey drone AI implementation
- DistributedGoonDroneStunAI - Stun drone AI implementation

This file now acts as a factory that routes to the appropriate class based on droneType.
"""

from direct.directnotify import DirectNotifyGlobal
from toontown.minigame.craning import CraneGameGlobals


def create_drone_ai(air, boss, ownerId, droneType=None):
    """
    Factory function to create the appropriate drone AI class.
    This maintains backwards compatibility with code that uses the old DistributedGoonDroneAI.
    """
    if droneType is None:
        droneType = CraneGameGlobals.DroneType.LASER
    
    # Convert to enum if needed
    if isinstance(droneType, int):
        droneType = CraneGameGlobals.DroneType(droneType)
    
    # Route to the appropriate specialized class
    if droneType == CraneGameGlobals.DroneType.LASER:
        from toontown.minigame.craning.objects.DistributedGoonDroneLaserAI import DistributedGoonDroneLaserAI
        return DistributedGoonDroneLaserAI(air, boss, ownerId)
    elif droneType == CraneGameGlobals.DroneType.HEAL:
        from toontown.minigame.craning.objects.DistributedGoonDroneHealAI import DistributedGoonDroneHealAI
        return DistributedGoonDroneHealAI(air, boss, ownerId)
    elif droneType == CraneGameGlobals.DroneType.EXPLODEY:
        from toontown.minigame.craning.objects.DistributedGoonDroneExplodeyAI import DistributedGoonDroneExplodeyAI
        return DistributedGoonDroneExplodeyAI(air, boss, ownerId)
    elif droneType == CraneGameGlobals.DroneType.STUN:
        from toontown.minigame.craning.objects.DistributedGoonDroneStunAI import DistributedGoonDroneStunAI
        return DistributedGoonDroneStunAI(air, boss, ownerId)
    elif droneType == CraneGameGlobals.DroneType.SHIELD:
        from toontown.minigame.craning.objects.DistributedGoonDroneShieldAI import DistributedGoonDroneShieldAI
        return DistributedGoonDroneShieldAI(air, boss, ownerId)
    elif droneType == CraneGameGlobals.DroneType.GHOSTY:
        from toontown.minigame.craning.objects.DistributedGoonDroneGhostyAI import DistributedGoonDroneGhostyAI
        return DistributedGoonDroneGhostyAI(air, boss, ownerId)
    else:
        # Default to laser for unknown types
        from toontown.minigame.craning.objects.DistributedGoonDroneLaserAI import DistributedGoonDroneLaserAI
        return DistributedGoonDroneLaserAI(air, boss, ownerId)


# For backwards compatibility, create a class that acts as a factory
class DistributedGoonDroneAI:
    """
    Backwards compatibility wrapper class.
    Acts as a factory that routes to the appropriate specialized drone class.
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGoonDroneAI')
    
    def __new__(cls, air, boss, ownerId, droneType=None):
        """
        Factory method - creates the appropriate specialized drone class.
        This allows old code like:
            drone = DistributedGoonDroneAI(air, boss, ownerId, droneType)
        to continue working.
        """
        return create_drone_ai(air, boss, ownerId, droneType)

"""
DEPRECATED: This file is kept for backwards compatibility.
The drone system has been refactored into specialized classes.

New structure:
- DistributedCashbotDroneBaseAI - Base AI class with common functionality
- DistributedCashbotDroneLaserAI - Laser drone AI implementation
- DistributedCashbotDroneHealAI - Heal drone AI implementation
- DistributedCashbotDroneExplodeyAI - Explodey drone AI implementation
- DistributedCashbotDroneStunAI - Stun drone AI implementation

This file now acts as a factory that routes to the appropriate class based on droneType.
"""

from direct.directnotify import DirectNotifyGlobal
from toontown.minigame.craning import CraneGameGlobals


def create_drone_ai(air, boss, ownerId, droneType=None):
    """
    Factory function to create the appropriate drone AI class.
    This maintains backwards compatibility with code that uses the old DistributedCashbotDroneAI.
    """
    if droneType is None:
        droneType = CraneGameGlobals.DroneType.LASER
    
    # Convert to enum if needed
    if isinstance(droneType, int):
        droneType = CraneGameGlobals.DroneType(droneType)
    
    # Route to the appropriate specialized class
    if droneType == CraneGameGlobals.DroneType.LASER:
        from toontown.minigame.craning.objects.DistributedCashbotDroneLaserAI import DistributedCashbotDroneLaserAI
        return DistributedCashbotDroneLaserAI(air, boss, ownerId)
    elif droneType == CraneGameGlobals.DroneType.HEAL:
        from toontown.minigame.craning.objects.DistributedCashbotDroneHealAI import DistributedCashbotDroneHealAI
        return DistributedCashbotDroneHealAI(air, boss, ownerId)
    elif droneType == CraneGameGlobals.DroneType.EXPLODEY:
        from toontown.minigame.craning.objects.DistributedCashbotDroneExplodeyAI import DistributedCashbotDroneExplodeyAI
        return DistributedCashbotDroneExplodeyAI(air, boss, ownerId)
    elif droneType == CraneGameGlobals.DroneType.STUN:
        from toontown.minigame.craning.objects.DistributedCashbotDroneStunAI import DistributedCashbotDroneStunAI
        return DistributedCashbotDroneStunAI(air, boss, ownerId)
    elif droneType == CraneGameGlobals.DroneType.SHIELD:
        from toontown.minigame.craning.objects.DistributedCashbotDroneShieldAI import DistributedCashbotDroneShieldAI
        return DistributedCashbotDroneShieldAI(air, boss, ownerId)
    elif droneType == CraneGameGlobals.DroneType.GHOSTY:
        from toontown.minigame.craning.objects.DistributedCashbotDroneGhostyAI import DistributedCashbotDroneGhostyAI
        return DistributedCashbotDroneGhostyAI(air, boss, ownerId)
    else:
        # Default to laser for unknown types
        from toontown.minigame.craning.objects.DistributedCashbotDroneLaserAI import DistributedCashbotDroneLaserAI
        return DistributedCashbotDroneLaserAI(air, boss, ownerId)


# For backwards compatibility, create a class that acts as a factory
class DistributedCashbotDroneAI:
    """
    Backwards compatibility wrapper class.
    Acts as a factory that routes to the appropriate specialized drone class.
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedCashbotDroneAI')
    
    def __new__(cls, air, boss, ownerId, droneType=None):
        """
        Factory method - creates the appropriate specialized drone class.
        This allows old code like:
            drone = DistributedCashbotDroneAI(air, boss, ownerId, droneType)
        to continue working.
        """
        return create_drone_ai(air, boss, ownerId, droneType)

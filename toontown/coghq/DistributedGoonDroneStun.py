"""
Stun Drone - Stuns all goons and the CFO.
"""

from panda3d.core import *
from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from toontown.coghq import CraneLeagueGlobals
from toontown.coghq.DistributedGoonDroneBase import DistributedGoonDroneBase


class DistributedGoonDroneStun(DistributedGoonDroneBase):
    """
    Stun drone that:
    1. Spawns above owner
    2. After 1 second, stuns all active goons
    3. Stuns the CFO
    4. Vanishes after 3.5 seconds
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGoonDroneStun')
    
    def getDroneType(self):
        return CraneLeagueGlobals.DroneType.STUN
    
    def needsOpponents(self):
        """Stun drones don't need opponents to function."""
        return False
    
    def startBehavior(self):
        """Start the stun drone behavior."""
        owner = base.cr.doId2do.get(self.ownerId)
        if not owner:
            self.vanishWithPoof()
            return
        
        ownerPos = owner.getPos(render)
        hoverPos = Point3(ownerPos.getX(), ownerPos.getY(), ownerPos.getZ() + 15)
        self.setPos(hoverPos)
        # The AI will trigger the stun after 1 second and send performVisualEffect


"""
Heal Drone - Hovers above owner and heals them to full laff.
"""

from panda3d.core import *
from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from toontown.coghq import CraneLeagueGlobals
from toontown.coghq.DistributedGoonDroneBase import DistributedGoonDroneBase


class DistributedGoonDroneHeal(DistributedGoonDroneBase):
    """
    Heal drone that:
    1. Spawns above owner
    2. Hovers for 2 seconds
    3. Heals owner to full laff (handled by AI)
    4. Vanishes
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGoonDroneHeal')
    
    def getDroneType(self):
        return CraneLeagueGlobals.DroneType.HEAL
    
    def needsOpponents(self):
        """Heal drones don't need opponents to function."""
        return False
    
    def startBehavior(self):
        """Start the heal drone hovering behavior."""
        self.startHovering()
    
    def startHovering(self):
        """Start hovering behavior - just hovers above owner."""
        owner = base.cr.doId2do.get(self.ownerId)
        if not owner:
            self.vanishWithPoof()
            return
        
        ownerPos = owner.getPos(render)
        hoverPos = Point3(ownerPos.getX(), ownerPos.getY(), ownerPos.getZ() + 15)
        self.setPos(hoverPos)
        # The AI will trigger the heal after 2 seconds and send performVisualEffect


"""
Explosive Drone - Flies to CFO and explodes, dealing damage.
"""

from panda3d.core import *
from direct.interval.IntervalGlobal import *
from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from toontown.coghq import CraneLeagueGlobals
from toontown.coghq.DistributedGoonDroneBase import DistributedGoonDroneBase


class DistributedGoonDroneExplosive(DistributedGoonDroneBase):
    """
    Explosive drone that:
    1. Spawns above owner
    2. Flies to CFO over 3 seconds
    3. Explodes on arrival, dealing damage to CFO
    4. Vanishes
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGoonDroneExplosive')
    
    def getDroneType(self):
        return CraneLeagueGlobals.DroneType.EXPLOSIVE
    
    def needsOpponents(self):
        """Explosive drones don't need opponents - they target the boss."""
        return False
    
    def startBehavior(self):
        """Start the explosive drone flying to CFO behavior."""
        # Explosive drone flies to CFO (targetId should be CFO's doId)
        if self.targetId or self.boss:
            self.startFlyingToCFO()
        else:
            self.vanishWithPoof()
    
    def startFlyingToCFO(self):
        """Start flying to CFO for explosive drone."""
        # Find boss if not set
        if not self.boss:
            self._findBoss()
        
        if not self.boss:
            self.notify.warning('Explosive drone could not find CFO boss')
            self.vanishWithPoof()
            return
        
        owner = base.cr.doId2do.get(self.ownerId)
        if not owner:
            self.vanishWithPoof()
            return
        
        ownerPos = owner.getPos(render)
        startPos = Point3(ownerPos.getX(), ownerPos.getY(), ownerPos.getZ() + 15)
        self.setPos(startPos)
        
        # Get CFO position
        bossPos = self.boss.getPos(render)
        targetPos = Point3(bossPos.getX(), bossPos.getY(), bossPos.getZ() + 10)
        
        # Lerp to CFO position over 3 seconds
        lerpDuration = 3.0
        self.behaviorSequence = Sequence(
            LerpPosInterval(self, lerpDuration, targetPos, startPos=startPos, blendType='easeInOut'),
            Func(self.onReachedCFO)
        )
        self.behaviorSequence.start()
    
    def onReachedCFO(self):
        """Called when explosive drone reaches CFO."""
        # The AI will trigger the explosion, we just wait for the visual
        pass


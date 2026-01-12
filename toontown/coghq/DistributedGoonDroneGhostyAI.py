"""
Ghosty Drone AI - Server-side logic for ghosting opponent safes.
"""

from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from toontown.coghq import CraneLeagueGlobals
from toontown.coghq.DistributedGoonDroneBaseAI import DistributedGoonDroneBaseAI


class DistributedGoonDroneGhostyAI(DistributedGoonDroneBaseAI):
    """
    Ghosty drone AI that:
    1. Tracks ghost state
    2. Handles cleanup after 6 seconds
    3. Cleans up when destroyed
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGoonDroneGhostyAI')
    
    def __init__(self, air, boss, ownerId):
        DistributedGoonDroneBaseAI.__init__(self, air, boss, ownerId)
        self.ghostDuration = 6.0  # 6 seconds
        self.ghostActive = False
    
    def getDroneType(self):
        return CraneLeagueGlobals.DroneType.GHOSTY
    
    def startBehavior(self):
        """Initialize ghosty drone behavior."""
        self.ghostActive = True
        self.notify.debug(f'Ghosty drone activated for toon {self.ownerId}')
        
        # Schedule cleanup after 6 seconds
        taskMgr.doMethodLater(self.ghostDuration, self.expireGhost, self.uniqueName('expireGhost'))
    
    def expireGhost(self, task=None):
        """Called when ghost effect expires naturally."""
        if not self.ghostActive:
            if task:
                return Task.done
            return
        
        self.ghostActive = False
        self.notify.debug(f'Ghost expired for toon {self.ownerId}')
        
        # Vanish after expiration
        taskMgr.doMethodLater(0.5, self.vanishWithPoof, self.uniqueName('vanishAfterExpire'))
        
        if task:
            return Task.done
    
    def delete(self):
        """Clean up ghosty-specific resources."""
        self.ghostActive = False
        taskMgr.remove(self.uniqueName('expireGhost'))
        taskMgr.remove(self.uniqueName('vanishAfterExpire'))
        DistributedGoonDroneBaseAI.delete(self)


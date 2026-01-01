"""
Stun Drone AI - Stuns all goons and the CFO.
"""

import random
from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from toontown.coghq import CraneLeagueGlobals
from toontown.coghq.DistributedGoonDroneBaseAI import DistributedGoonDroneBaseAI


class DistributedGoonDroneStunAI(DistributedGoonDroneBaseAI):
    """
    Stun drone AI that:
    1. After 1 second, stuns all active goons
    2. Stuns the CFO
    3. Vanishes after 3.5 seconds
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGoonDroneStunAI')
    
    def getDroneType(self):
        return CraneLeagueGlobals.DroneType.STUN
    
    def startBehavior(self):
        """Initialize stun drone behavior."""
        taskMgr.doMethodLater(1.0, self.performStun, self.uniqueName('performStun'))
    
    def performStun(self, task):
        """Stun all goons and the CFO."""
        if not self.boss:
            self.vanishWithPoof()
            return Task.done
        
        # Send stun request to client for visual feedback
        self.sendUpdate('performVisualEffect', [CraneLeagueGlobals.DroneType.STUN.value])
        
        # Disable every goon in the arena
        if hasattr(self.boss, 'game') and self.boss.game:
            for goon in self.boss.game.goons:
                taskMgr.doMethodLater(2 + random.random() / 4, goon.stun, goon.uniqueName('droneStun'), extraArgs=[self.ownerId, 10])
        
        # Stun the boss
        def stunBoss(_=None):
            self.boss.game.recordHit(0, forceStun=True, avIdOverride=self.ownerId)
        taskMgr.doMethodLater(2.25, stunBoss, self.boss.game.uniqueName('droneStun'))
        
        # Vanish after stun
        taskMgr.doMethodLater(3.5, self.vanishWithPoof, self.uniqueName('vanishAfterStun'))
        return Task.done
    
    def delete(self):
        """Clean up stun-specific resources."""
        taskMgr.remove(self.uniqueName('performStun'))
        taskMgr.remove(self.uniqueName('vanishAfterStun'))
        
        DistributedGoonDroneBaseAI.delete(self)


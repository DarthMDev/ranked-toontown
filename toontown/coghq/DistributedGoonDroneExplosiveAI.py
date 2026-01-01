"""
Explosive Drone AI - Flies to CFO and explodes, dealing damage.
"""

from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from toontown.coghq import CraneLeagueGlobals
from toontown.coghq.DistributedGoonDroneBaseAI import DistributedGoonDroneBaseAI


class DistributedGoonDroneExplosiveAI(DistributedGoonDroneBaseAI):
    """
    Explosive drone AI that:
    1. Flies to CFO position (client handles visual)
    2. After 3 seconds, explodes and deals damage to CFO
    3. Vanishes
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGoonDroneExplosiveAI')
    
    def getDroneType(self):
        return CraneLeagueGlobals.DroneType.EXPLOSIVE
    
    def startBehavior(self):
        """Initialize explosive drone behavior."""
        # Explosive drone targets the CFO
        # Set target to CFO's doId (for client-side visual targeting)
        if self.boss:
            self.setTargetId(self.boss.doId)
        # Wait 3 seconds for it to fly to CFO, then explode
        taskMgr.doMethodLater(3.0, self.performExplosion, self.uniqueName('performExplosion'))
    
    def performExplosion(self, task):
        """Explode and deal damage to CFO."""
        if not self.boss:
            self.vanishWithPoof()
            return Task.done
        
        # Send explosion request to client for visual feedback
        self.sendUpdate('performVisualEffect', [CraneLeagueGlobals.DroneType.EXPLOSIVE.value])
        
        # Deal damage to CFO (50 damage)
        explosionDamage = 50
        if hasattr(self.boss, 'game') and self.boss.game:
            # Use game's recordHit method
            self.boss.game.recordHit(explosionDamage, impact=0.99, craneId=-1, objId=0, isGoon=False, isDOT=False, avIdOverride=self.ownerId, forceStun=True)
        
        # Vanish after explosion
        taskMgr.doMethodLater(0.5, self.vanishWithPoof, self.uniqueName('vanishAfterExplosion'))
        return Task.done
    
    def delete(self):
        """Clean up explosive-specific resources."""
        taskMgr.remove(self.uniqueName('performExplosion'))
        taskMgr.remove(self.uniqueName('vanishAfterExplosion'))
        
        DistributedGoonDroneBaseAI.delete(self)


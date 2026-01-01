"""
Explodey Drone AI - Charges at CFO and explodes on impact, dealing damage.
"""

from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from toontown.coghq import CraneLeagueGlobals
from toontown.coghq.DistributedGoonDroneBaseAI import DistributedGoonDroneBaseAI


class DistributedGoonDroneExplodeyAI(DistributedGoonDroneBaseAI):
    """
    Explodey drone AI that:
    1. Waits for client to report collision with CFO
    2. When collision detected, deals 35 damage and stuns CFO
    3. Vanishes
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGoonDroneExplodeyAI')
    
    def __init__(self, air, boss, ownerId):
        DistributedGoonDroneBaseAI.__init__(self, air, boss, ownerId)
        self.hitCFO = False
    
    def getDroneType(self):
        return CraneLeagueGlobals.DroneType.EXPLODEY
    
    def startBehavior(self):
        """Initialize explodey drone behavior."""
        # Explodey drone targets the CFO
        # Set target to CFO's doId (for client-side visual targeting)
        if self.boss:
            self.setTargetId(self.boss.doId)
        # Client will handle the charge and collision detection
        # We wait for requestExplode when it hits
    
    def requestExplode(self):
        """Called by client when explodey drone hits the CFO."""
        avId = self.air.getAvatarIdFromSender()
        
        # Verify it's the owner
        if avId != self.ownerId:
            self.notify.warning(f'Explodey drone explode request from non-owner: {avId} != {self.ownerId}')
            return
        
        if self.hitCFO or not self.boss:
            return
        
        self.hitCFO = True
        
        # Deal 35 damage to CFO
        explosionDamage = 35
        
        # Check if CFO has a helmet - if so, don't stun
        # self.boss is the CFO boss object (DistributedCashbotBossStrippedAI)
        shouldStun = True
        if hasattr(self.boss, 'heldObject') and self.boss.heldObject is not None:
            # CFO has a helmet, don't stun
            shouldStun = False
        
        if hasattr(self.boss, 'game') and self.boss.game:
            # Use game's recordHit method with forceStun only if CFO doesn't have helmet
            self.boss.game.recordHit(
                explosionDamage,
                impact=0.99,
                craneId=-1,
                objId=0,
                isGoon=False,
                isDOT=False,
                avIdOverride=self.ownerId,
                forceStun=shouldStun
            )
        
        # Send explosion visual to all clients
        self.sendUpdate('performVisualEffect', [CraneLeagueGlobals.DroneType.EXPLODEY.value])
        
        # Vanish after explosion
        taskMgr.doMethodLater(0.5, self.vanishWithPoof, self.uniqueName('vanishAfterExplosion'))
    
    def delete(self):
        """Clean up explodey-specific resources."""
        taskMgr.remove(self.uniqueName('vanishAfterExplosion'))
        
        DistributedGoonDroneBaseAI.delete(self)


"""
Stun Drone AI - Goes high above CFO, grows, then launches down to stun.
"""

import random
from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from toontown.coghq import CraneLeagueGlobals
from toontown.coghq.DistributedGoonDroneBaseAI import DistributedGoonDroneBaseAI
from toontown.toonbase import ToontownGlobals


class DistributedGoonDroneStunAI(DistributedGoonDroneBaseAI):
    """
    Stun drone AI that:
    1. Waits for client to report collision with CFO
    2. When collision detected, removes helmet if present, then stuns CFO and goons
    3. Vanishes
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGoonDroneStunAI')
    
    def getDroneType(self):
        return CraneLeagueGlobals.DroneType.STUN
    
    def startBehavior(self):
        """Initialize stun drone behavior."""
        # Stun drone targets the CFO
        # Set target to CFO's doId (for client-side visual targeting)
        if self.boss:
            self.setTargetId(self.boss.doId)
        # Client will handle the ascent, growth, and collision detection
        # We wait for requestStun when it hits
    
    def requestStun(self):
        """Called by client when stun drone hits the CFO."""
        avId = self.air.getAvatarIdFromSender()
        
        # Verify it's the owner
        if avId != self.ownerId:
            self.notify.warning(f'Stun drone stun request from non-owner: {avId} != {self.ownerId}')
            return
        
        if not self.boss:
            return
        
        # Stun all goons
        if hasattr(self.boss, 'game') and self.boss.game:
            for goon in self.boss.game.goons:
                taskMgr.doMethodLater(0.1 + random.random() * 0.2, goon.stun, goon.uniqueName('droneStun'), extraArgs=[self.ownerId, 10])
        
        # Stun the CFO with flinch
        # Send visual effect first to trigger flinch on client, then stun
        self.sendUpdate('performVisualEffect', [CraneLeagueGlobals.DroneType.STUN.value])
        
        def stunBoss(_=None):
            if hasattr(self.boss, 'game') and self.boss.game:
                # Record hit with 0 damage but forceStun=True to stun
                self.boss.game.recordHit(
                    0,
                    impact=0.99,
                    craneId=-1,
                    objId=0,
                    isGoon=False,
                    isDOT=False,
                    avIdOverride=self.ownerId,
                    forceStun=True
                )
        
        taskMgr.doMethodLater(0.1, stunBoss, self.boss.game.uniqueName('droneStun'))
        
        # Check if CFO has a helmet - remove it AFTER stun (with delay to let drone explode first)
        def removeHelmet(_=None):
            if hasattr(self.boss, 'heldObject') and self.boss.heldObject is not None:
                # Remove the helmet
                helmet = self.boss.heldObject
                # Use a special craneId that won't trigger __hitBoss collision
                # Pass -1 or 0 to avoid setting crane to boss
                helmet.demand('Dropped', avId, 0)  # Use 0 instead of boss.doId
                helmet.avoidHelmet = 1
                self.boss.heldObject = None
                self.boss.avoidHelmet = 1
                # Wait for next helmet
                self.boss.waitForNextHelmet()
        
        # Remove helmet after drone has exploded (0.5 second delay)
        taskMgr.doMethodLater(0.5, removeHelmet, self.uniqueName('removeHelmet'))
        
        # Vanish after stun
        taskMgr.doMethodLater(1.0, self.vanishWithPoof, self.uniqueName('vanishAfterStun'))
    
    def delete(self):
        """Clean up stun-specific resources."""
        taskMgr.remove(self.uniqueName('vanishAfterStun'))
        
        DistributedGoonDroneBaseAI.delete(self)

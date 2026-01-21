"""
Stun Drone AI - Goes high above CFO, grows, then launches down to stun.
"""

import random
from direct.directnotify import DirectNotifyGlobal
from toontown.minigame.craning import CraneGameGlobals
from toontown.minigame.craning.objects.DistributedCashbotDroneBaseAI import DistributedCashbotDroneBaseAI


class DistributedCashbotDroneStunAI(DistributedCashbotDroneBaseAI):
    """
    Stun drone AI that:
    1. Waits for client to report collision with CFO
    2. When collision detected, removes helmet if present, then stuns CFO and goons
    3. Vanishes
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedCashbotDroneStunAI')
    
    def getDroneType(self):
        return CraneGameGlobals.DroneType.STUN
    
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
        
        # Stun the CFO immediately to interrupt any ongoing attacks
        # Send visual effect first to trigger flinch on client, then stun immediately
        self.sendUpdate('performVisualEffect', [CraneGameGlobals.DroneType.STUN.value])
        
        # Stun immediately - no delay to prevent gear attacks from completing
        if hasattr(self.boss, 'game') and self.boss.game:
            # Record hit with 0 damage but forceStun=True to stun
            # Use objId=999999 to identify this as Stunna drone (for 10 point stun reward)
            # This large number won't conflict with real object IDs
            self.boss.game.recordHit(
                0,
                impact=0.99,
                craneId=-1,
                objId=999999,  # Special objId to identify Stunna drone
                isGoon=False,
                isDOT=False,
                avIdOverride=self.ownerId,
                forceStun=True
            )
        
        # Check if CFO has a helmet - remove it AFTER stun (with delay to let drone explode first)
        def removeHelmet(_=None):
            if hasattr(self.boss, 'heldObject') and self.boss.heldObject is not None:
                # Award 10 points for knocking off helmet with Stunna
                if hasattr(self.boss, 'game') and self.boss.game:
                    from toontown.minigame.craning import CraneGameGlobals
                    self.boss.game.addScore(
                        self.ownerId,
                        10,
                        reason=CraneGameGlobals.ScoreReason.REMOVE_HELMET
                    )
                
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
        
        DistributedCashbotDroneBaseAI.delete(self)

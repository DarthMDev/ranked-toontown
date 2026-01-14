"""
Explodey Drone AI - Charges at CFO and explodes on impact, dealing damage.
"""

from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from toontown.minigame.craning import CraneGameGlobals
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
        return CraneGameGlobals.DroneType.EXPLODEY
    
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
        
        # Deal 35 damage to CFO (no stun)
        explosionDamage = 35
        
        if hasattr(self.boss, 'game') and self.boss.game:
            # Use game's recordHit method with isGoon=True to make CFO react like a goon hit (faster recovery)
            # This prevents the long recovery animation that safe hits cause
            self.boss.game.recordHit(
                explosionDamage,
                impact=0.99,
                craneId=-1,
                objId=0,
                isGoon=True,  # Treat as goon hit for faster CFO recovery
                isDOT=False,
                avIdOverride=self.ownerId,
                forceStun=False  # Never stun - just deal damage
            )
            
            # Destroy all goons in the room and award points to owner
            goonsToDestroy = []
            
            # Try to get goons from game first, then from boss as fallback
            if hasattr(self.boss.game, 'goons'):
                goonsToDestroy = self.boss.game.goons[:]
                self.notify.debug(f'Xplodey: Found {len(goonsToDestroy)} goons in game.goons')
            elif hasattr(self.boss, 'goons'):
                goonsToDestroy = self.boss.goons[:]
                self.notify.debug(f'Xplodey: Found {len(goonsToDestroy)} goons in boss.goons')
            else:
                self.notify.warning('Xplodey: Could not find goons list')
            
            for goon in goonsToDestroy:
                if not goon:
                    continue
                
                # Check if goon is already destroyed (AI objects don't have isEmpty, check state instead)
                if hasattr(goon, 'state') and goon.state == 'Off':
                    continue
                
                try:
                    goonId = goon.doId if hasattr(goon, 'doId') else 'unknown'
                    self.notify.debug(f'Xplodey: Attempting to destroy goon {goonId}')
                    
                    # Try destroyedByTNT first (awards points automatically)
                    if hasattr(goon, 'destroyedByTNT'):
                        # destroyedByTNT checks if avId is in boss.avIdList, but owner might not be
                        # So we'll try it, and if it fails, fall back to manual destruction
                        try:
                            goon.destroyedByTNT(self.ownerId)
                            self.notify.debug(f'Xplodey: Successfully destroyed goon {goonId} via destroyedByTNT')
                            continue
                        except Exception as e:
                            self.notify.debug(f'Xplodey: destroyedByTNT failed for goon {goonId}: {e}, trying manual destruction')
                    
                    # Fallback: destroy goon and manually award points
                    if hasattr(goon, 'b_destroyGoon'):
                        goon.b_destroyGoon()
                        # Award points manually
                        if hasattr(self.boss.game, 'ruleset'):
                            self.boss.game.addScore(
                                self.ownerId,
                                self.boss.game.ruleset.POINTS_GOON_KILLED_BY_SAFE,
                                reason=CraneGameGlobals.ScoreReason.GOON_KILL

                            )
                            self.notify.debug(f'Xplodey: Successfully destroyed goon {goonId} via b_destroyGoon and awarded points')
                    else:
                        self.notify.warning(f'Xplodey: Goon {goonId} has no destruction method')
                except Exception as e:
                    self.notify.warning(f'Error destroying goon {goonId if hasattr(goon, "doId") else "unknown"}: {e}')
                    import traceback
                    self.notify.warning(traceback.format_exc())
                    # Continue destroying other goons even if one fails
        
        # Send explosion visual to all clients
        self.sendUpdate('performVisualEffect', [CraneGameGlobals.DroneType.EXPLODEY.value])

        
        # Vanish after explosion
        taskMgr.doMethodLater(0.5, self.vanishWithPoof, self.uniqueName('vanishAfterExplosion'))
    
    def delete(self):
        """Clean up explodey-specific resources."""
        taskMgr.remove(self.uniqueName('vanishAfterExplosion'))
        
        DistributedGoonDroneBaseAI.delete(self)


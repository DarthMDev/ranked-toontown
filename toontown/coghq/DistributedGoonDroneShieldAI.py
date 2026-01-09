"""
Shield Drone AI - Tracks shield state and handles shield protection mechanics.
"""

from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from toontown.coghq import CraneLeagueGlobals
from toontown.coghq.DistributedGoonDroneBaseAI import DistributedGoonDroneBaseAI


class DistributedGoonDroneShieldAI(DistributedGoonDroneBaseAI):
    """
    Shield drone AI that:
    1. Activates shield for owner almost instantly
    2. Tracks shield state (active/broken)
    3. Provides method for game to check if player has shield
    4. Provides method for game to break shield
    5. Shield lasts 8 seconds or until hit
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGoonDroneShieldAI')
    
    def __init__(self, air, boss, ownerId):
        DistributedGoonDroneBaseAI.__init__(self, air, boss, ownerId)
        self.shieldActive = False
        self.shieldDuration = 8.0  # 8 seconds
    
    def getDroneType(self):
        return CraneLeagueGlobals.DroneType.SHIELD
    
    def startBehavior(self):
        """Initialize shield drone behavior."""
        # Activate shield almost instantly
        taskMgr.doMethodLater(0.05, self.activateShield, self.uniqueName('activateShield'))
    
    def activateShield(self, task=None):
        """Activate the shield for the owner."""
        self.shieldActive = True
        
        # Register shield with boss/game
        if self.boss and hasattr(self.boss, 'game') and self.boss.game:
            if not hasattr(self.boss.game, 'activeShields'):
                self.boss.game.activeShields = {}
            self.boss.game.activeShields[self.ownerId] = self
            self.notify.debug(f'Shield activated for toon {self.ownerId}')
        
        # Schedule shield expiration after 8 seconds
        taskMgr.doMethodLater(self.shieldDuration, self.expireShield, self.uniqueName('expireShield'))
        
        if task:
            return Task.done
    
    def breakShield(self, grantIframes=True):
        """
        Break the shield (called by game when player is hit, or by client when safe hits).
        
        Args:
            grantIframes: If True or 1, grant i-frames to owner (enemy hit). 
                         If False or 0, no i-frames (safe hit).
                         Can be bool or uint8 (0/1) when called from client.
        """
        # Handle both bool and uint8 (from client calls)
        if isinstance(grantIframes, int):
            grantIframes = bool(grantIframes)
        
        if not self.shieldActive:
            return False
        
        self.shieldActive = False
        
        # Unregister shield from game
        if self.boss and hasattr(self.boss, 'game') and self.boss.game:
            if hasattr(self.boss.game, 'activeShields') and self.ownerId in self.boss.game.activeShields:
                del self.boss.game.activeShields[self.ownerId]
        
        # Send visual effect to clients (convert boolean to uint8 for DC compatibility)
        # The client will handle granting i-frames without visual effects
        self.sendUpdate('breakShield', [1 if grantIframes else 0])
        
        if grantIframes:
            self.notify.debug(f'Shield broken by enemy for toon {self.ownerId}, i-frames will be granted by client')
        else:
            self.notify.debug(f'Shield broken by safe for toon {self.ownerId}, no i-frames')
        
        # Don't vanish drone here - it should already be vanished after 1 second of activation
        # Shield cleanup is handled by client
        
        return True
    
    
    def expireShield(self, task=None):
        """Called when shield expires naturally (not hit)."""
        if not self.shieldActive:
            if task:
                return Task.done
            return False
        
        self.shieldActive = False
        
        # Unregister shield from game
        if self.boss and hasattr(self.boss, 'game') and self.boss.game:
            if hasattr(self.boss.game, 'activeShields') and self.ownerId in self.boss.game.activeShields:
                del self.boss.game.activeShields[self.ownerId]
        
        self.notify.debug(f'Shield expired for toon {self.ownerId}')
        
        # Don't send breakShield update - client handles natural expiration with fade-out
        # (no shattering effect on natural expiration)
        # The client's own timer will call expireShield which does a smooth fade-out
        
        # Don't vanish drone here - it should already be vanished after 1 second of activation
        # Shield cleanup is handled by client
        
        if task:
            return Task.done
        return True
    
    def isShieldActive(self):
        """Check if shield is currently active."""
        return self.shieldActive
    
    def delete(self):
        """Clean up shield-specific resources."""
        # Unregister shield if still active
        if self.shieldActive:
            if self.boss and hasattr(self.boss, 'game') and self.boss.game:
                if hasattr(self.boss.game, 'activeShields') and self.ownerId in self.boss.game.activeShields:
                    del self.boss.game.activeShields[self.ownerId]
        
        taskMgr.remove(self.uniqueName('activateShield'))
        taskMgr.remove(self.uniqueName('expireShield'))
        taskMgr.remove(self.uniqueName('vanishAfterBreak'))
        taskMgr.remove(self.uniqueName('vanishAfterExpire'))
        
        DistributedGoonDroneBaseAI.delete(self)

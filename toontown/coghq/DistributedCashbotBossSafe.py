from panda3d.core import *
from panda3d.physics import *
from direct.interval.IntervalGlobal import *
from direct.directnotify import DirectNotifyGlobal
from toontown.toonbase import ToontownGlobals
from otp.otpbase import OTPGlobals
from . import DistributedCashbotBossObject
import copy

from toontown.coghq import CraneLeagueGlobals

class DistributedCashbotBossSafe(DistributedCashbotBossObject.DistributedCashbotBossObject):

    """ This is a safe sitting around in the Cashbot CFO final battle
    room.  It's used as a prop for toons to pick up and throw at the
    CFO's head.  Also, the special safe with self.index == 0
    represents the safe that the CFO uses to put on his own head as a
    safety helmet from time to time. """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedCashbotBossSafe')
    
    grabPos = (0, 0, -8.2)
    
    # What happens to the crane and its cable when this object is picked up?
    craneFrictionCoef = 0.2
    craneSlideSpeed = 11
    craneRotateSpeed = 16

    # A safe remains under physical control of whichever client
    # last dropped it, even after it stops moving.  This allows
    # goons to push safes out of the way.
    wantsWatchDrift = 1

    def __init__(self, cr):
        DistributedCashbotBossObject.DistributedCashbotBossObject.__init__(self, cr)
        NodePath.__init__(self, 'object')
        self.index = None
        
        self.flyToMagnetSfx = loader.loadSfx('phase_5/audio/sfx/TL_rake_throw_only.ogg')
        self.hitMagnetSfx = loader.loadSfx('phase_5/audio/sfx/AA_drop_safe.ogg')
        # We want these sfx's to overlap just a smidge for effect.
        self.toMagnetSoundInterval = Parallel(SoundInterval(self.flyToMagnetSfx, duration=ToontownGlobals.CashbotBossToMagnetTime, node=self), Sequence(Wait(ToontownGlobals.CashbotBossToMagnetTime - 0.02), SoundInterval(self.hitMagnetSfx, duration=1.0, node=self)))
        self.hitFloorSfx = loader.loadSfx('phase_5/audio/sfx/AA_drop_bigweight_miss.ogg')
        self.hitFloorSoundInterval = SoundInterval(self.hitFloorSfx, node=self)
        self.name = 'safe'
        return

    def announceGenerate(self):
        DistributedCashbotBossObject.DistributedCashbotBossObject.announceGenerate(self)
        self.name = 'safe-%s' % self.doId
        self.setName(self.name)
        
        self.boss.safe.copyTo(self)
        self.shadow = self.find('**/shadow')
        
        self.collisionNode.setName('safe')
        cs = CollisionSphere(0, 0, 4, 4) #TTR Collisions
        #cs = CollisionCapsule(0, 0, 4, 0, 0, 4, 4) #TTCC Collisions
        self.collisionNode.addSolid(cs)
        
        if self.index == 0:
            # If this is safe 0, it's the safe that the CFO uses when
            # he wants to put on his own helmet.  This one can't be
            # picked up by magnets, and it doesn't stick around for
            # any length of time when it's knocked off his head--it
            # just falls through the floor and resets.
            
            self.collisionNode.setIntoCollideMask(ToontownGlobals.PieBitmask | OTPGlobals.WallBitmask)
            self.collisionNode.setFromCollideMask(ToontownGlobals.PieBitmask)
            
        self.boss.safes[self.index] = self
        
        # Initialize color management system - store true original color scale
        self._initializeColorManagement()
        
        self.setupPhysics('safe')
        self.resetToInitialPosition()

    def disable(self):
        del self.boss.safes[self.index]
        DistributedCashbotBossObject.DistributedCashbotBossObject.disable(self)

    def hideShadows(self):
        self.shadow.hide()

    def showShadows(self):
        self.shadow.show()
        
    def setupPhysics(self, name):
        # Call parent to set up physics with collision velocity correction
        # The parent class handles world-space collision responses to prevent orientation from affecting trajectory
        # This allows visual orientation to change freely (e.g., when grabbed by crane) without affecting physics
        DistributedCashbotBossObject.DistributedCashbotBossObject.setupPhysics(self, name)

    def getMinImpact(self):
        # This method returns the minimum impact, in feet per second,
        # with which the object should hit the boss before we bother
        # to tell the server.
        if self.boss.getBoss().heldObject:
            return self.boss.ruleset.MIN_DEHELMET_IMPACT
        else:
            return self.boss.ruleset.MIN_SAFE_IMPACT

    def doHitGoon(self, goon):
        # Prevent duplicate destruction calls for the same goon
        goonId = goon.doId if hasattr(goon, 'doId') else id(goon)
        if not hasattr(self, '_destroyedGoons'):
            self._destroyedGoons = set()
        
        # Check if this is a drone and if it belongs to the safe's controller or a teammate
        if hasattr(goon, 'ownerId') and goon.ownerId:
            # This is a drone - check for friendly fire
            if self.avId == goon.ownerId:
                # Can't destroy your own drone
                return
            
            # Check if they're on the same team (both are participants, not opponents)
            if hasattr(self.boss, 'game') and self.boss.game:
                participants = self.boss.game.getParticipantIdsNotSpectating()
                # If both the safe controller and drone owner are participants, they're teammates
                if self.avId in participants and goon.ownerId in participants:
                    return
            
            # Check if this is a stun drone that's growing (invulnerable)
            if hasattr(goon, 'isGrowing') and goon.isGrowing:
                # Stun drone is invulnerable during growth phase - can collide but not destroy
                return
        
        # Check if we already destroyed this goon (prevent duplicates)
        if goonId in self._destroyedGoons:
            return
        
        # Should we disable or destroy?
        destroyed = False
        if self.boss.ruleset.SAFES_STUN_GOONS:
            goon.doLocalStun()
            destroyed = True
        else:
            goon.b_destroyGoon()
            destroyed = True
        
        # Only send destroyedGoon if we actually destroyed it (not friendly fire, not invulnerable)
        if destroyed:
            self._destroyedGoons.add(goonId)
            # Pass goon ID to server so it can track individual goons
            self.sendUpdate('destroyedGoon', [goonId])
            # Clean up the set after a delay to prevent memory leaks
            taskMgr.doMethodLater(1.0, lambda task, gId=goonId: self._destroyedGoons.discard(gId), self.uniqueName('cleanupDestroyedGoon'))
    
    def doHitShield(self, shieldDrone, shieldOwnerId):
        """Called when this safe hits an opponent's shield."""
        # Break the shield without granting i-frames (safe hit counterplay)
        if shieldDrone and hasattr(shieldDrone, 'breakShield'):
            # Send to AI to break the shield with grantIframes=False (safe hit, no i-frames)
            # breakShield has clsend flag, so it will notify the AI
            shieldDrone.sendUpdate('breakShield', [0])  # 0 = no i-frames
            self.notify.debug(f'Safe {self.doId} broke shield of toon {shieldOwnerId}')

    def resetToInitialPosition(self):
        posHpr = CraneLeagueGlobals.SAFE_POSHPR[self.index]
        self.setPosHpr(*posHpr)
        self.physicsObject.setVelocity(0, 0, 0)

    def fellOut(self):
        # The safe fell out of the world.  Reset it back to its
        # original position.
        self.deactivatePhysics()
        self.d_requestInitial()
        
    def setIndex(self, index):
        self.index = index

        
 
    ##### Messages To/From The Server #####
    
    def setObjectState(self, state, avId, craneId):
        if state == 'I':
            self.demand('Initial')
        else:
            DistributedCashbotBossObject.DistributedCashbotBossObject.setObjectState(self, state, avId, craneId)

    def d_requestInitial(self):
        self.sendUpdate('requestInitial')



    ### FSM States ###
    
    def enterInitial(self):
        self.resetSpeedCaching()
        self.resetToInitialPosition()
        self.showShadows()
        
        if self.index == 0:
            # The special "helmet-only" safe goes away completely when
            # it's in Initial mode.
            self.stash()

    def exitInitial(self):
        if self.index == 0:
            self.unstash()
            
    def move(self, x, y, z, rotation):
        if self.state in ['LocalGrabbed', 'LocalDropped', 'Grabbed', 'Dropped']:
            return
        self.setPosHpr(x, y, z, rotation, 0, 0)
    
    # ===== Color Management System =====
    # Centralized system to handle all color scale modifications and prevent conflicts
    
    def _initializeColorManagement(self):
        """Initialize the color management system with the true original color scale."""
        # Store the true original color scale when the safe is first created
        # This should only be called once in announceGenerate()
        if not hasattr(self, '_trueOriginalColorScale'):
            originalColor = self.getColorScale()
            # Validate the color is reasonable
            if (0.0 <= originalColor.getX() <= 2.0 and 
                0.0 <= originalColor.getY() <= 2.0 and 
                0.0 <= originalColor.getZ() <= 2.0 and 
                0.0 <= originalColor.getW() <= 2.0):
                self._trueOriginalColorScale = originalColor
            else:
                # Color is corrupted, use default white
                self._trueOriginalColorScale = VBase4(1, 1, 1, 1)
        
        # Track active color modifications
        # Priority: GHOST (highest) > ELEMENTAL_EFFECTS (lowest)
        if not hasattr(self, '_activeColorModifications'):
            self._activeColorModifications = {
                'ghost': None,  # Ghost effect (highest priority)
                'elemental': None,  # Elemental status effects (burned, drenched, etc.)
            }
        
        # Track active color intervals to cancel them when needed
        if not hasattr(self, '_activeColorInterval'):
            self._activeColorInterval = None
    
    def _cancelActiveColorInterval(self):
        """Cancel any active color scale interval to prevent conflicts."""
        if hasattr(self, '_activeColorInterval') and self._activeColorInterval:
            try:
                self._activeColorInterval.finish()
            except:
                pass
            self._activeColorInterval = None
    
    def registerColorModification(self, modType, colorScale, priority='elemental'):
        """
        Register a color modification.
        
        Args:
            modType: Unique identifier for this modification (e.g., 'burned', 'drenched', 'ghost')
            colorScale: The target color scale (VBase4)
            priority: 'ghost' (highest) or 'elemental' (lower)
        """
        if not hasattr(self, '_activeColorModifications'):
            self._initializeColorManagement()
        
        # Cancel any existing interval
        self._cancelActiveColorInterval()
        
        # Store the modification
        if priority == 'ghost':
            self._activeColorModifications['ghost'] = (modType, colorScale)
        else:
            self._activeColorModifications['elemental'] = (modType, colorScale)
        
        # Apply the highest priority modification
        self._applyActiveColorModification()
    
    def unregisterColorModification(self, modType, priority='elemental'):
        """
        Unregister a color modification.
        
        Args:
            modType: The identifier of the modification to remove
            priority: 'ghost' or 'elemental'
        """
        if not hasattr(self, '_activeColorModifications'):
            return
        
        # Remove the modification if it matches
        if priority == 'ghost':
            if (self._activeColorModifications.get('ghost') and 
                self._activeColorModifications['ghost'][0] == modType):
                self._activeColorModifications['ghost'] = None
        else:
            if (self._activeColorModifications.get('elemental') and 
                self._activeColorModifications['elemental'][0] == modType):
                self._activeColorModifications['elemental'] = None
        
        # Reapply the highest priority remaining modification
        self._applyActiveColorModification()
    
    def _applyActiveColorModification(self):
        """Apply the highest priority active color modification."""
        if not hasattr(self, '_activeColorModifications'):
            return
        
        # Cancel any existing interval
        self._cancelActiveColorInterval()
        
        # Determine target color based on priority
        targetColor = None
        
        # Ghost effect has highest priority
        if self._activeColorModifications.get('ghost'):
            targetColor = self._activeColorModifications['ghost'][1]
        # Otherwise use elemental effect
        elif self._activeColorModifications.get('elemental'):
            targetColor = self._activeColorModifications['elemental'][1]
        # No modifications - restore to true original
        else:
            if hasattr(self, '_trueOriginalColorScale'):
                targetColor = self._trueOriginalColorScale
            else:
                targetColor = VBase4(1, 1, 1, 1)
        
        # Apply the color with a smooth transition
        if targetColor:
            self._activeColorInterval = LerpColorScaleInterval(
                self,
                duration=0.4,
                colorScale=targetColor,
                blendType='easeInOut'
            )
            self._activeColorInterval.start()
    
    def getTrueOriginalColorScale(self):
        """Get the true original color scale stored when the safe was created."""
        if hasattr(self, '_trueOriginalColorScale'):
            return self._trueOriginalColorScale
        return VBase4(1, 1, 1, 1)
    
    def forceRestoreOriginalColor(self):
        """Force immediate restoration to original color (no fade)."""
        self._cancelActiveColorInterval()
        
        # Clear all modifications
        if hasattr(self, '_activeColorModifications'):
            self._activeColorModifications['ghost'] = None
            self._activeColorModifications['elemental'] = None
        
        # Restore immediately
        if hasattr(self, '_trueOriginalColorScale'):
            self.setColorScale(self._trueOriginalColorScale)
        else:
            self.setColorScale(1.0, 1.0, 1.0, 1.0)
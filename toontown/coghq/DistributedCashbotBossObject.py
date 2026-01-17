import time
from enum import IntEnum
from panda3d.core import *
from panda3d.physics import *
from panda3d.core import CollisionHandlerQueue
from direct.interval.IntervalGlobal import *
from direct.directnotify import DirectNotifyGlobal
from direct.distributed import DistributedSmoothNode
from toontown.toonbase import ToontownGlobals
from otp.otpbase import OTPGlobals
from direct.fsm import FSM
from direct.task import Task
from direct.task.TaskManagerGlobal import taskMgr
from toontown.minigame.statuseffects.StatusEffectGlobals import StatusEffect
smileyDoId = 1

class DummyTaskClass:
    def setDelay(self, blah):
        pass

DummyTask = DummyTaskClass()

class DistributedCashbotBossObject(DistributedSmoothNode.DistributedSmoothNode, FSM.FSM):

    """ This is an object that can be picked up an dropped in the
    final battle scene with the Cashbot CFO.  In particular, it's a
    safe or a goon.  """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedCashbotBossObject')

    # This should be true for objects that will eventually transition
    # from SlidingFloor to Free when they stop moving.
    wantsWatchDrift = 1

    def __init__(self, cr):
        DistributedSmoothNode.DistributedSmoothNode.__init__(self, cr)
        FSM.FSM.__init__(self, 'DistributedCashbotBossObject')
        
        self.boss = None
        self.avId = 0
        self.craneId = 0
        self.cleanedUp = 0
        
        # An attribute to cache the last 7 speeds and velocities for the object
        self.speeds = []
        self.velocities = []
        
        # Reference to the platform this object is on (if any)
        # This allows the object to move with the platform when in Free state
        self.platformNode = None
        self.platformIndex = -1  # Platform index from server (-1 means not on platform)
            
        # A CollisionNode to keep me out of walls and floors, and to
        # keep others from bumping into me.  We use PieBitmask instead
        # of WallBitmask, to protect against objects (like goons)
        # self-colliding.
        self.collisionNode = CollisionNode('object')
        self.collisionNode.setIntoCollideMask(ToontownGlobals.PieBitmask | OTPGlobals.WallBitmask | ToontownGlobals.CashbotBossObjectBitmask | OTPGlobals.CameraBitmask)
        self.collisionNode.setFromCollideMask(ToontownGlobals.PieBitmask | OTPGlobals.FloorBitmask)
        self.collisionNodePath = NodePath(self.collisionNode)
        
        self.physicsActivated = 0
        
        self.toMagnetSoundInterval = Sequence()
        self.hitFloorSoundInterval = Sequence()
        
        # A solid sound for when we get a good hit on the boss.
        self.hitBossSfx = loader.loadSfx('phase_5/audio/sfx/AA_drop_safe_miss.ogg')
        self.hitBossRapidlySfx = loader.loadSfx('phase_14/audio/sfx/safe_double.ogg')
        self.hitBossSoundInterval = SoundInterval(self.hitBossSfx)
        self.hitBossRapidlyInterval = SoundInterval(self.hitBossRapidlySfx)

        # A squishy sound for when we hit the boss, but not hard enough.
        self.touchedBossSfx = loader.loadSfx('phase_5/audio/sfx/AA_drop_sandbag.ogg')
        self.touchedBossSoundInterval = SoundInterval(self.touchedBossSfx, duration=0.8)
        
        # Cranes will fill in this with the interval to lerp the
        # object to the crane.
        self.lerpInterval = None
        
        self.setBroadcastStateChanges(True)

        self.__broadcastPeriod = None
        self.broadcasting = False

    def disable(self):
        self.cleanup()
        self.stopSmooth()
        DistributedSmoothNode.DistributedSmoothNode.disable(self)

    def cleanup(self):
        # is this being called twice?
        if self.cleanedUp:
            return
        else:
            self.cleanedUp = 1
            
        self.demand('Off')
        self.detachNode()
        
        self.toMagnetSoundInterval.finish()
        self.hitFloorSoundInterval.finish()
        self.hitBossSoundInterval.finish()
        self.hitBossRapidlyInterval.finish()
        self.touchedBossSoundInterval.finish()
        del self.toMagnetSoundInterval
        del self.hitFloorSoundInterval
        del self.hitBossSoundInterval
        del self.hitBossRapidlyInterval
        del self.touchedBossSoundInterval
        
        self.boss = None
        return

    def setupPhysics(self, name):
        an = ActorNode('%s-%s' % (name, self.doId))
        anp = NodePath(an)
        if not self.isEmpty():
            self.reparentTo(anp)

        # It is important that there be no messenger hooks added on
        # this object at the time we reassign the NodePath.
        NodePath.assign(self, anp)
        
        self.physicsObject = an.getPhysicsObject()
        self.setTag('object', str(self.doId))
       
        self.collisionNodePath.reparentTo(self)
        self.handler = PhysicsCollisionHandler()
        self.handler.addCollider(self.collisionNodePath, self)

        base.cTrav.setRespectPrevTransform(False)

        # Set up a collision event so we know when the object hits the
        # floor, or the boss's target.
        self.collideName = self.uniqueName('collide')
        self.handler.addInPattern(self.collideName + '-%in')
        self.handler.addAgainPattern(self.collideName + '-%in')
        
        self.watchDriftName = self.uniqueName('watchDrift')
        self.startCacheName = self.uniqueName('startSpeedCaching')
        self.resetSpeedCaching()
        
    def startSpeedCaching(self, task):

        speed = self.physicsObject.getVelocity().length()
        vel = self.physicsObject.getVelocity()

        if len(self.speeds) > 6:
            self.speeds.pop(0)

        if len(self.velocities) > 6:
            self.velocities.pop(0)
        
        self.speeds.append(speed)
        self.velocities.append(vel)

        return Task.again
        
    def resetSpeedCaching(self):
        
        self.speeds = []
        self.velocities = []
        taskMgr.remove(self.startCacheName)

    def activatePhysics(self):
        if not self.physicsActivated:
            self.speeds.append(self.physicsObject.getVelocity().length())
            self.velocities.append(self.physicsObject.getVelocity())
            taskMgr.doMethodLater(0.1, self.startSpeedCaching, self.startCacheName)
            self.boss.physicsMgr.attachPhysicalNode(self.node())
            base.cTrav.addCollider(self.collisionNodePath, self.handler)
            self.physicsActivated = 1
            self.accept(self.collideName + '-floor', self.__hitFloor)
            self.accept(self.collideName + '-goon', self.__hitGoon)
            self.acceptOnce(self.collideName + '-headTarget', self.__hitBoss)
            self.accept(self.collideName + '-dropPlane', self.__hitDropPlane)
            self.accept(self.collideName + '-shield', self.__hitShield)
            # Platform collisions: MovingPlatform nodes have dynamic names like 'MovingPlatform-platform-12345'
            # We need to intercept all collision events and check if they're platform collisions
            # We'll use a wrapper that catches all collision events for this object
            self._setupPlatformCollisionDetection()

    def _setupPlatformCollisionDetection(self):
        """Set up detection for platform collisions with dynamic names."""
        # Find all FloatingPlatform objects and accept their MovingPlatform collision events
        # The MovingPlatform collision nodes have names stored in platform._name
        # We need to find these and accept the collision events for them
        self._acceptedPlatformEvents = []
        self._setupPlatformEvents()
        
        # Also set up a task to periodically check for new platforms
        self.platformCheckTask = taskMgr.add(self._checkForNewPlatforms, self.uniqueName('checkForNewPlatforms'))
    
    def _setupPlatformEvents(self):
        """Find all FloatingPlatform objects and accept their collision events."""
        if not hasattr(base, 'cr') or not base.cr:
            return
        
        # Find all FloatingPlatform objects in the scene
        for doId, obj in list(base.cr.doId2do.items()):
            if hasattr(obj, '__class__') and 'FloatingPlatform' in obj.__class__.__name__:
                # This is a FloatingPlatform, get its MovingPlatform collision node name
                if hasattr(obj, 'platform') and obj.platform and hasattr(obj.platform, '_name'):
                    # The MovingPlatform has a _name attribute that's the collision node name
                    platformCollisionName = obj.platform._name
                    if platformCollisionName:
                        # Accept the collision event for this platform
                        eventName = self.collideName + '-' + platformCollisionName
                        if eventName not in self._acceptedPlatformEvents:
                            self.accept(eventName, self.__hitPlatform)
                            self._acceptedPlatformEvents.append(eventName)
                            self.notify.debug('Accepted platform collision event: %s' % eventName)
    
    def _checkForNewPlatforms(self, task):
        """Periodically check for new FloatingPlatform objects and accept their collision events."""
        if not self.physicsActivated:
            return Task.done
        
        # Check for new platforms every 0.5 seconds
        self._setupPlatformEvents()
        
        return Task.cont
    
    def deactivatePhysics(self):
        if self.physicsActivated:
            self.boss.physicsMgr.removePhysicalNode(self.node())
            base.cTrav.removeCollider(self.collisionNodePath)
            self.physicsActivated = 0
            self.ignore(self.collideName + '-floor')
            self.ignore(self.collideName + '-goon')
            self.ignore(self.collideName + '-headTarget')
            self.ignore(self.collideName + '-dropPlane')
            # Clean up platform collision detection
            if hasattr(self, '_acceptedPlatformEvents'):
                for eventName in self._acceptedPlatformEvents:
                    self.ignore(eventName)
                del self._acceptedPlatformEvents
            if hasattr(self, 'platformCheckTask'):
                taskMgr.remove(self.platformCheckTask)
                del self.platformCheckTask

    def hideShadows(self):
        pass

    def showShadows(self):
        pass

    def stashCollisions(self):
        self.collisionNodePath.stash()

    def unstashCollisions(self):
        self.collisionNodePath.unstash()

    def __hitFloor(self, entry):
        # Check if this is actually a platform collision
        # MovingPlatform nodes have names like 'MovingPlatform-platform-12345'
        # and may trigger floor collision events, so we need to check the collision entry
        if entry:
            intoNodePath = entry.getIntoNodePath()
            if intoNodePath and not intoNodePath.isEmpty():
                nodeName = intoNodePath.getName()
                # Check for platform tag or MovingPlatform name pattern
                if intoNodePath.getTag('platform') == '1' or (nodeName and nodeName.startswith('MovingPlatform')):
                    # This is actually a platform collision, handle it as such
                    self.__hitPlatform(entry)
                    return
        
        # Clear platform reference since we hit the floor, not a platform
        self.platformNode = None
        
        if self.state == 'Falling':
            self.doHitFloor()

        if self.state in ('Dropped', 'LocalDropped'):
            self.d_hitFloor()
            self.demand('SlidingFloor', localAvatar.doId)
        elif self.state == 'SlidingPlatform':
            # We were sliding on a platform but now hit the floor
            # Clear platform index and transition to SlidingFloor
            self.d_hitFloor()
            self.demand('SlidingFloor', localAvatar.doId)
    
    def __hitPlatform(self, entry):
        """Called when object hits a platform. Behaves the same as hitting the floor."""
        # Find the platform's model node and index so we can parent to it later
        platformIndex = -1
        if entry:
            intoNodePath = entry.getIntoNodePath()
            if intoNodePath and not intoNodePath.isEmpty():
                # The collision node is part of the MovingPlatform, which is parented to
                # the DistributedFloatingPlatform's model node (named 'FloatingPlatform-{index}')
                # Traverse up to find the model node
                current = intoNodePath
                while current and not current.isEmpty():
                    nodeName = current.getName()
                    if nodeName and nodeName.startswith('FloatingPlatform-'):
                        self.platformNode = current
                        # Extract platform index from node name: "FloatingPlatform-{index}"
                        try:
                            platformIndex = int(nodeName.split('-')[1])
                        except (ValueError, IndexError):
                            platformIndex = -1
                        break
                    current = current.getParent()
        
        # Send platform index to server so it can broadcast to all clients
        if platformIndex >= 0 and self.state in ('Dropped', 'LocalDropped', 'SlidingFloor', 'SlidingPlatform'):
            self.d_hitPlatform(platformIndex)
        
        if self.state == 'Falling':
            self.doHitFloor()

        if self.state in ('Dropped', 'LocalDropped'):
            # Transition to SlidingPlatform if we hit a platform, otherwise SlidingFloor
            if platformIndex >= 0:
                self.d_hitPlatform(platformIndex)
                self.demand('SlidingPlatform', localAvatar.doId)
            else:
                self.d_hitFloor()
                self.demand('SlidingFloor', localAvatar.doId)

    def __hitGoon(self, entry):
        if self.state in ('Dropped', 'LocalDropped', 'Falling'):
            goonId = int(entry.getIntoNodePath().getNetTag('doId'))
            goon = self.cr.doId2do.get(goonId)
            if goon:
                self.doHitGoon(goon)

    def doHitGoon(self, goon):
        # Override in a derived class to do something if the object is
        # dropped on a goon.
        pass
    
    def __hitShield(self, entry):
        """Called when safe hits a shield."""
        # Only safes in 'Dropped' state can break shields
        if self.state == 'Dropped':
            # Get the shield owner ID from the collision node tag
            shieldNodePath = entry.getIntoNodePath()
            if shieldNodePath and not shieldNodePath.isEmpty():
                shieldOwnerIdStr = shieldNodePath.getNetTag('shieldOwnerId')
                droneIdStr = shieldNodePath.getNetTag('droneId')
                
                if shieldOwnerIdStr and droneIdStr:
                    try:
                        shieldOwnerId = int(shieldOwnerIdStr)
                        droneId = int(droneIdStr)
                        
                        # Get the shield drone
                        shieldDrone = self.cr.doId2do.get(droneId)
                        if shieldDrone and hasattr(shieldDrone, 'shieldActive') and shieldDrone.shieldActive:
                            # Only break shield if it's not our own shield
                            if shieldOwnerId != self.avId:
                                # Break the shield without granting i-frames (safe hit)
                                self.doHitShield(shieldDrone, shieldOwnerId)
                    except (ValueError, TypeError):
                        pass
    
    def doHitShield(self, shieldDrone, shieldOwnerId):
        """Override in a derived class to handle shield hits."""
        pass

    def doHitFloor(self):
        """
        Override in a derived class to do something if this object hits the floor.
        Note that this function is only called if the previous state was falling, dropped, or local dropped.
        """
        pass

    def __hitBoss(self, entry):
        if (self.state == 'Dropped' or self.state == 'LocalDropped') and self.craneId != self.boss.doId:
            
            # Safety check: if crane doesn't exist or is not a real crane (e.g., it's the boss), skip this collision
            # This can happen when helmet is dropped by stun drone with craneId=0 or boss.doId
            if not hasattr(self, 'crane') or not self.crane:
                return
            if not hasattr(self.crane, 'root'):
                # crane is not a real crane (might be the boss), skip collision
                return
            
            #get the velocity of the object, relative to the crane
            speed = max(self.speeds)
            vel = max(self.velocities)
            vel = self.crane.root.getRelativeVector(render, vel)
            vel.normalize()
            # Check if impact cap should be removed
            removeCap = False
            if hasattr(self.boss, 'ruleset') and hasattr(self.boss.ruleset, 'REMOVE_IMPACT_CAP'):
                removeCap = self.boss.ruleset.REMOVE_IMPACT_CAP
            if removeCap:
                clash_impact = max(pow(speed, 1.75)/466.475, 0.0)
            else:
                clash_impact = min(1.0, max(pow(speed, 1.75)/466.475, 0.0))
            ttr_impact = vel[1]
            impact = max(clash_impact, ttr_impact)

            if impact >= self.getMinImpact():
                self.hitBossSoundInterval.start()
            else:
                self.touchedBossSoundInterval.start()

            self.doHitBoss(impact, self.craneId)
            self.resetSpeedCaching()

    def showTempHitEffect(self, impact, craneId):

        if not hasattr(self.boss.getBoss(), 'attackCode'):
            return

        if self.boss.getBoss().heldObject or self.boss.getBoss().attackCode != ToontownGlobals.BossCogDizzy:
            return

        # Check if we performed a pretty quick hit.
        now = time.time()
        isRapidHit = now - self.boss.getBoss().lastLocalHit < 1
        self.boss.getBoss().lastLocalHit = time.time()
        if isRapidHit:
            self.hitBossRapidlyInterval.start()
        
        timeUntilStunEnd = self.boss.getBoss().stunEndTime - globalClock.getFrameTime()
        if self.boss.getBoss().stunEndTime == 0 or timeUntilStunEnd < 1.5:
            return

        # Get the crane to check its damage multiplier 
        crane = self.cr.doId2do.get(craneId)
        if not crane:
            return

        damage = int(impact * 50)
        damage *= crane.getDamageMultiplier()
        damage *= self.boss.ruleset.SAFE_CFO_DAMAGE_MULTIPLIER
        
        # Apply GROUNDED damage multiplier if active on this safe
        if self.boss.getStatusEffectSystem().hasStatusEffect(self.doId, StatusEffect.GROUNDED):
            groundedBonus = int(damage * 0.25)
            damage += groundedBonus
        
        # Apply SHATTERED damage vulnerability if active
        if self.boss.getStatusEffectSystem().hasStatusEffect(self.boss.getBoss().doId, StatusEffect.SHATTERED):
            vulnerabilityBonus = int(damage * 0.5)  # 50% bonus damage
            damage += vulnerabilityBonus

        damage = int(damage)

        if damage <= 0:
            return

        if self.boss.processingHp:
            curHp = self.boss.tempHp
        else:
            curHp = self.boss.ruleset.CFO_MAX_HP - self.boss.getBoss().bossDamage
        
        self.boss.tempHp = curHp - damage

        if damage < curHp:
            self.boss.getBoss().myHits.append(self.doId)
            self.boss.getBoss().processingHp = True
            self.boss.getBoss().flashRed()
            if self.boss.ruleset.CFO_FLINCHES_ON_HIT:
                self.boss.getBoss().doAnimate('hit', now=1)
            self.boss.getBoss().showHpText(-damage, scale=5)

    def doHitBoss(self, impact, craneId):
        # Derived classes can override this to do something specific
        # when we successfully hit the boss.
        self.d_hitBoss(impact, craneId)
        self.showTempHitEffect(impact, craneId)

    def __hitDropPlane(self, entry):
        self.notify.info('%s fell out of the world.' % self.doId)
        self.fellOut()

    def fellOut(self):
        # Override in a derived class to do the right thing when the
        # object falls out of the world.
        raise Exception('fellOut unimplented')

    def getMinImpact(self):
        # This method returns the minimum impact, in feet per second,
        # with which the object should hit the boss before we bother
        # to tell the server.
        return 0

    def __watchDrift(self, task):
        # Checks the object for non-zero velocity.  When the velocity
        # reaches zero in the XY plane, we tell the AI we're done
        # moving it around.
        v = self.physicsObject.getVelocity()
        
        if abs(v[0]) < 0.0001 and abs(v[1]) < 0.0001:
            self.d_requestFree()
            self.demand('Free')
            
        return Task.cont

    def prepareGrab(self):
        # Specialized classes will override this method to do
        # something appropriate when the object is grabbed by a
        # magnet.
        pass

    def prepareRelease(self):
        pass


        
    ##### Messages To/From The Server #####

    def setBossCogId(self, bossCogId):
        self.bossCogId = bossCogId

        # This would be risky if we had toons entering the zone during
        # a battle--but since all the toons are always there from the
        # beginning, we can be confident that the BossCog has already
        # been generated by the time we receive the generate for its
        # associated objects.
        self.boss = base.cr.doId2do[bossCogId]

    def setObjectState(self, state, avId, craneId):
        if self.state == 'Off':
            return

        if state == 'G':
            if self.state in ['SlidingFloor', 'SlidingPlatform']:
                if avId == localAvatar.doId:
                    return
            if self.state != 'LocalDropped':
                self.demand('Grabbed', avId, craneId)
        elif state == 'D':
            if self.state in ['SlidingFloor', 'SlidingPlatform']:
                if avId == localAvatar.doId:
                    return
            self.demand('Dropped', avId, craneId)
        elif state == 's':
            if self.state != 'SlidingFloor':
                self.demand('SlidingFloor', avId)
        elif state == 'P':
            if self.state != 'SlidingPlatform':
                self.demand('SlidingPlatform', avId)
        elif state == 'F':
            if self.state in ['LocalGrabbed', 'LocalDropped']:
                return
            self.demand('Free')
        else:
            self.notify.error('Invalid state from AI: %s' % state)

    def d_requestGrab(self):
        self.sendUpdate('requestGrab')

    def rejectGrab(self):
        # The server tells us we can't have it for whatever reason.
        if self.state == 'LocalGrabbed':
            self.demand('LocalDropped', self.avId, self.craneId)

    def d_requestDrop(self):
        self.sendUpdate('requestDrop')

    def d_hitFloor(self):
        self.sendUpdate('hitFloor')
    
    def d_hitPlatform(self, platformIndex):
        self.sendUpdate('hitPlatform', [platformIndex])

    def d_requestFree(self):
        self.sendUpdate('requestFree', [self.getX(),
         self.getY(),
         self.getZ(),
         self.getH()])

    def d_hitBoss(self, impact, craneId):
        self.sendUpdate('hitBoss', [impact, craneId])

    def defaultFilter(self, request, args):
        # We overload the default filter function to disallow *any*
        # state transitions after the object has been disabled or
        # deleted, or before it has been fully generated.
        if self.boss == None:
            raise FSM.RequestDenied(request)
            
        return FSM.FSM.defaultFilter(self, request, args)
        
    def setPlatformIndex(self, platformIndex):
        """Called by server to tell us which platform this object is on.
        platformIndex of -1 means not on a platform."""
        self.platformIndex = platformIndex
        # Find the platform node using the index
        self.platformNode = None
        if platformIndex >= 0:
            # Find the FloatingPlatform object with this index
            if hasattr(base, 'cr') and base.cr:
                for doId, obj in list(base.cr.doId2do.items()):
                    if hasattr(obj, '__class__') and 'FloatingPlatform' in obj.__class__.__name__:
                        if hasattr(obj, 'index') and obj.index == platformIndex:
                            if hasattr(obj, 'model') and obj.model and not obj.model.isEmpty():
                                self.platformNode = obj.model
                                break
            
            # If we're in Free or SlidingPlatform state, parent to the platform now
            # This handles the case where setPlatformIndex is called after enterFree or enterSlidingPlatform
            if self.state in ('Free', 'SlidingPlatform'):
                self._parentToPlatformIfNeeded()
        else:
            # Platform index is -1, meaning we're not on a platform
            # Unparent from platform if we were parented to it
            if self.platformNode and not self.platformNode.isEmpty() and self.getParent() == self.platformNode:
                currentPos = self.getPos(render)
                currentHpr = self.getHpr(render)
                self.reparentTo(render)
                self.setPos(currentPos)
                self.setHpr(currentHpr)
            self.platformNode = None
    
    def _parentToPlatformIfNeeded(self):
        """Helper method to parent the object to its platform if needed."""
        if self.platformNode and not self.platformNode.isEmpty():
            # Get our current position relative to render (world position)
            currentPos = self.getPos(render)
            currentHpr = self.getHpr(render)
            # Only reparent if we're not already parented to this platform
            if self.getParent() != self.platformNode:
                # Parent to the platform
                self.reparentTo(self.platformNode)
                # Calculate relative position (world position - platform world position = relative position)
                platformPos = self.platformNode.getPos(render)
                relativePos = currentPos - platformPos
                self.setPos(relativePos)
                self.setHpr(currentHpr)
            else:
                # Already parented - ensure the relative position is correct
                # Get current world position and platform world position to calculate correct relative position
                currentWorldPos = self.getPos(render)
                platformWorldPos = self.platformNode.getPos(render)
                # Calculate what the relative position should be
                correctRelativePos = currentWorldPos - platformWorldPos
                # Get current relative position
                currentRelativePos = self.getPos()
                # Only update if there's a significant difference (avoid floating point errors)
                if (correctRelativePos - currentRelativePos).length() > 0.01:
                    self.setPos(correctRelativePos)
        else:
            # Not on a platform, unparent if we were parented
            if not self.getParent().isEmpty() and self.getParent().getName().startswith('FloatingPlatform-'):
                self.reparentTo(render)

    def updateClientPositions(self, x, y, z, h, p, r):
        if self.state in ['LocalGrabbed', 'LocalDropped', 'Grabbed', 'Dropped']:
            return
        else:
            # If we're parented to a platform, don't update position from AI
            # The platform movement will handle our position
            if self.platformNode and not self.platformNode.isEmpty() and self.getParent() == self.platformNode:
                # We're on a platform, don't override with AI position
                # Just update rotation if needed
                self.setHpr(h, p, r)
            else:
                self.setPosHpr(x, y, z, h, p, r)

    ### FSM States ###

    def enterOff(self):
        # In state Off, the object is not parented to the scene graph.
        # In all other states, it is.
        self.detachNode()
        
        if self.lerpInterval:
            self.lerpInterval.finish()
            self.lerpInterval = None
        return

    def exitOff(self):
        self.reparentTo(render)

    def enterLocalGrabbed(self, avId, craneId):
        # This state is like Grabbed, except that it is only triggered
        # locally.  In this state, we have requested a grab, and we
        # will act as if we have grabbed the object successfully, but
        # we have not yet heard confirmation from the AI so we might
        # later discover that we didn't grab it after all.

        # We're not allowed to drop the object directly from this
        # state.
        
        # Unparent from platform if we were on one
        if self.platformNode and not self.platformNode.isEmpty() and self.getParent() == self.platformNode:
            currentPos = self.getPos(render)
            currentHpr = self.getHpr(render)
            self.reparentTo(render)
            self.setPos(currentPos)
            self.setHpr(currentHpr)
            self.platformNode = None
            self.platformIndex = -1
        
        self.avId = avId
        self.craneId = craneId

        self.crane = self.cr.doId2do.get(craneId)

        self.hideShadows()
        self.prepareGrab()

        # Add this to establish local control and
        # stop receiving incoming position updates
        # from other players:
        self.stopSmooth()
        self.localControl = True 
        self.crane.grabObject(self)

    def exitLocalGrabbed(self):
        if self.newState != 'Grabbed':
            if self.crane:
                self.crane.dropObject(self)
            self.prepareRelease()
            del self.crane

            self.showShadows()

    def enterGrabbed(self, avId, craneId):
        # Grabbed by a crane, or by the boss for a helmet. craneId is
        # the doId of the crane or the doId of the boss himself.

        if avId != base.localAvatar.doId:
            self.localControl = False

        if self.oldState == 'LocalGrabbed':
            if craneId == self.craneId:
                # This is just the confirmation from the AI that we
                # did, in fact, grab this object with the expected
                # crane; we don't need to do anything else in this
                # state.
                return
            else:
                # Whoops, we had previously grabbed it locally, but it
                # turns out someone else grabbed it instead.
                self.crane.dropObject(self)
                self.prepareRelease()
        
        # Unparent from platform if we were on one
        if self.platformNode and not self.platformNode.isEmpty() and self.getParent() == self.platformNode:
            currentPos = self.getPos(render)
            currentHpr = self.getHpr(render)
            self.reparentTo(render)
            self.setPos(currentPos)
            self.setHpr(currentHpr)
            self.platformNode = None
            self.platformIndex = -1
        
        self.avId = avId
        self.craneId = craneId

        self.crane = self.cr.doId2do.get(craneId)

        # The "crane" might actually be the boss cog himself!  This
        # happens when the boss takes a safe to wear as a helmet.

        self.hideShadows()
        self.prepareGrab()
        self.crane.grabObject(self)

    def exitGrabbed(self):
        if hasattr(self, 'crane'):
            if self.crane:
                self.crane.dropObject(self)
        self.prepareRelease()
        self.showShadows()
        if hasattr(self, 'crane'):
            del self.crane

    def enterLocalDropped(self, avId, craneId):
        # As in LocalGrabbed, above, this state is entered locally
        # when we drop the safe, but we have not yet received
        # acknowledgement from the AI that we've dropped it.
        
        self.avId = avId
        self.craneId = craneId

        self.crane = self.cr.doId2do.get(craneId)
        
        self.activatePhysics()
        self.startPosHprBroadcast(avId=self.avId, period=.05)
        self.hideShadows()

        # Set slippery physics so it will slide off the boss.
        self.handler.setStaticFrictionCoef(0)
        self.handler.setDynamicFrictionCoef(0)

    def exitLocalDropped(self):
        if self.newState not in ('SlidingFloor', 'SlidingPlatform', 'Dropped'):
            self.deactivatePhysics()
            self.stopPosHprBroadcast()
        del self.crane
        self.showShadows()

    def enterDropped(self, avId, craneId):
        
        self.avId = avId
        self.craneId = craneId

        self.crane = self.cr.doId2do.get(craneId)
        
        # If I'm the one who dropped it
        # Then I should be the one to broadcast
        # the position updates
        if self.avId == base.localAvatar.doId:
            self.activatePhysics()
            self.startPosHprBroadcast(avId=self.avId, period=.05)
            self.handler.setStaticFrictionCoef(0)
            self.handler.setDynamicFrictionCoef(0)
        # Otherwise, I'm the one receiving the
        # position updates
        else:
            if self.broadcasting:
                self.deactivatePhysics()
                self.stopPosHprBroadcast()
            self.startSmooth()
        self.hideShadows()

    def exitDropped(self):
        # If I'm the one who dropped it
        # Then I should stop broadcasting
        # the position updates
        if self.avId == base.localAvatar.doId:
            if self.newState not in ('SlidingFloor', 'SlidingPlatform'):
                self.deactivatePhysics()
                self.stopPosHprBroadcast()
        # Otherwise, I'm the one receiving the
        # position updates so I should stop
        else:
            self.stopSmooth()

        if hasattr(self, 'crane'):
            del self.crane
        self.showShadows()

    def enterSlidingFloor(self, avId):
        # The object is now sliding across the floor under local
        # control.  Crank up the friction so it will slow down more
        # quickly.
        
        self.avId = avId
        
        # Unparent from platform if we're parented
        # Check if we're parented to any FloatingPlatform node
        parent = self.getParent()
        if not parent.isEmpty():
            parentName = parent.getName() if hasattr(parent, 'getName') else ''
            if parentName.startswith('FloatingPlatform-') or (self.platformNode and not self.platformNode.isEmpty() and parent == self.platformNode):
                # Unparent - but handle position differently for local vs other clients
                
                if self.avId == base.localAvatar.doId:
                    # Local client: use physics position (it's authoritative)
                    currentPos = self.getPos(render)
                    currentHpr = self.getHpr(render)
                    self.reparentTo(render)
                    self.setPos(currentPos)
                    self.setHpr(currentHpr)
                else:
                    # Other clients: just unparent and let smooth following handle the position
                    # Don't set position here because we're using the platform's Z which is wrong
                    # The server will send the correct floor position via updateClientPositions
                    self.reparentTo(render)
                    # Don't call setPos - let the server position updates handle it
        
        # Always clear platform references when entering SlidingFloor (we're on the floor now)
        self.platformNode = None
        self.platformIndex = -1
        
        if self.lerpInterval:
            self.lerpInterval.finish()
            self.lerpInterval = None
            
        if self.avId == base.localAvatar.doId:
            self.activatePhysics()
            self.startPosHprBroadcast(avId=self.avId, period=.05)
            
            self.handler.setStaticFrictionCoef(0.9)
            self.handler.setDynamicFrictionCoef(0.5)

            # Start up a task to watch for it to actually stop drifting.
            # When it does, we notify the AI.
            if self.wantsWatchDrift:
                taskMgr.add(self.__watchDrift, self.watchDriftName)
        else:
            if self.broadcasting:
                self.deactivatePhysics()
                self.stopPosHprBroadcast()
            # Start smooth following - this will interpolate from the current position
            self.startSmooth()
            
        self.hitFloorSoundInterval.start()

    def exitSlidingFloor(self):
        if self.avId == base.localAvatar.doId:
            taskMgr.remove(self.watchDriftName)
            self.deactivatePhysics()
            self.stopPosHprBroadcast()
        else:
            self.stopSmooth()

    def enterSlidingPlatform(self, avId):
        # The object is now sliding across a platform under local
        # control. Similar to SlidingFloor but we're on a platform.
        
        self.avId = avId
        
        if self.lerpInterval:
            self.lerpInterval.finish()
            self.lerpInterval = None
        
        # If we have a platform node (from collision detection) or platform index (from server),
        # parent to the platform immediately so all clients see it move with the platform
        if self.platformNode and not self.platformNode.isEmpty():
            # Local client: we already have the platform node from collision detection
            currentPos = self.getPos(render)
            currentHpr = self.getHpr(render)
            self.reparentTo(self.platformNode)
            platformPos = self.platformNode.getPos(render)
            relativePos = currentPos - platformPos
            self.setPos(relativePos)
            self.setHpr(currentHpr)
        elif self.platformIndex >= 0:
            # Other clients: find platform using index (setPlatformIndex will be called by server)
            # Try to find it now
            if hasattr(base, 'cr') and base.cr:
                for doId, obj in list(base.cr.doId2do.items()):
                    if hasattr(obj, '__class__') and 'FloatingPlatform' in obj.__class__.__name__:
                        if hasattr(obj, 'index') and obj.index == self.platformIndex:
                            if hasattr(obj, 'model') and obj.model and not obj.model.isEmpty():
                                self.platformNode = obj.model
                                currentPos = self.getPos(render)
                                currentHpr = self.getHpr(render)
                                self.reparentTo(self.platformNode)
                                platformPos = self.platformNode.getPos(render)
                                relativePos = currentPos - platformPos
                                self.setPos(relativePos)
                                self.setHpr(currentHpr)
                                break
            
        if self.avId == base.localAvatar.doId:
            self.activatePhysics()
            self.startPosHprBroadcast(avId=self.avId, period=.05)
            
            # Use similar friction to floor sliding
            self.handler.setStaticFrictionCoef(0.9)
            self.handler.setDynamicFrictionCoef(0.5)

            # Start up a task to watch for it to actually stop drifting.
            # When it does, we notify the AI.
            if self.wantsWatchDrift:
                taskMgr.add(self.__watchDrift, self.watchDriftName)
        else:
            if self.broadcasting:
                self.deactivatePhysics()
                self.stopPosHprBroadcast()
            self.startSmooth()
            
        self.hitFloorSoundInterval.start()

    def exitSlidingPlatform(self):
        # Only unparent from platform if we're transitioning to Free state
        # For SlidingFloor transition, we'll unparent in enterSlidingFloor instead
        # This matches the pattern of Dropped -> SlidingFloor where the safe is already unparented
        if self.newState == 'Free':
            # Keep parented to platform for Free state
            pass
        
        if self.avId == base.localAvatar.doId:
            taskMgr.remove(self.watchDriftName)
            self.deactivatePhysics()
            self.stopPosHprBroadcast()
        else:
            self.stopSmooth()

    def enterFree(self):
        self.localControl = False
        self.resetSpeedCaching()
        self.avId = 0
        self.craneId = 0
        
        # First, ensure we're not incorrectly parented to a platform if platformIndex is -1
        # This handles the case where we slid off a platform onto the floor
        if self.platformIndex < 0:
            # Not on a platform - make sure we're unparented
            parent = self.getParent()
            if not parent.isEmpty():
                parentName = parent.getName() if hasattr(parent, 'getName') else ''
                if parentName.startswith('FloatingPlatform-') or (self.platformNode and not self.platformNode.isEmpty() and parent == self.platformNode):
                    # Still parented to platform - unparent now
                    # Get position before unparenting (while still in platform's coordinate space)
                    # This ensures we get the correct world position
                    currentPos = self.getPos(render)
                    currentHpr = self.getHpr(render)
                    self.reparentTo(render)
                    # Set the world position we captured
                    self.setPos(currentPos)
                    self.setHpr(currentHpr)
                    # Ensure the safe is visible (not at origin or invalid position)
                    if currentPos.length() < 0.01:
                        # Position seems invalid, try to get it from AI update
                        # This will be set by updateClientPositions
                        pass
            self.platformNode = None
        else:
            # We might be on a platform - find the platform node if we don't have it
            if self.platformIndex >= 0 and (not self.platformNode or self.platformNode.isEmpty()):
                # Find the FloatingPlatform object with this index
                if hasattr(base, 'cr') and base.cr:
                    for doId, obj in list(base.cr.doId2do.items()):
                        if hasattr(obj, '__class__') and 'FloatingPlatform' in obj.__class__.__name__:
                            if hasattr(obj, 'index') and obj.index == self.platformIndex:
                                if hasattr(obj, 'model') and obj.model and not obj.model.isEmpty():
                                    self.platformNode = obj.model
                                    break
            
            # Parent to platform if we have one (setPlatformIndex will be called by server)
            # Use the helper method to handle parenting
            self._parentToPlatformIfNeeded()

    def exitFree(self):
        pass

    class BroadcastTypes(IntEnum):
        FULL = 0
        XYH = 1
        XY = 2

    def _posHprBroadcast(self, task=DummyTask):
        # TODO: we explicitly stagger the initial task timing in
        # startPosHprBroadcast; we should at least make an effort to keep
        # this task accurately aligned with its period and starting time.
        if base.localAvatar.doId == self.avId:
            self.d_broadcastPosHpr()
            task.setDelay(self.__broadcastPeriod)
            return Task.again
        else:
            return Task.done

    def setPosHprBroadcastPeriod(self, period):
        # call this at any time to change the delay between broadcasts
        self.__broadcastPeriod = period

    def getPosHprBroadcastPeriod(self):
        # query the current delay between broadcasts
        return self.__broadcastPeriod
    
    def startPosHprBroadcast(self, avId=None, period=.01568, stagger=0, type=None):
        if self.cnode is None:
            self.initializeCnode()

        BT = self.BroadcastTypes
        if type is None:
            type = BT.FULL
        # set the broadcast type
        self.broadcastType = type

        broadcastFuncs = {
            BT.FULL: self.cnode.broadcastPosHprFull,
            BT.XYH:  self.cnode.broadcastPosHprXyh,
            BT.XY:  self.cnode.broadcastPosHprXy,
            }
        # this comment is here so it will show up in a grep for 'def d_broadcastPosHpr'
        self.d_broadcastPosHpr = broadcastFuncs[self.broadcastType]

        # Set stagger to non-zero to randomly delay the initial task execution
        # over 'period' seconds, to spread out task processing over time
        # when a large number of SmoothNodes are created simultaneously.
        taskName = self.getPosHprBroadcastTaskName() + '-%s' % avId

        # Set up telemetry optimization variables
        self.cnode.initialize(self, self.dclass, self.doId)

        self.setPosHprBroadcastPeriod(period)
        # Broadcast our initial position
        self.b_clearSmoothing()
        self.cnode.sendEverything()

        # remove any old tasks
        taskMgr.remove(taskName)
        # spawn the new task
        delay = 0.
        if stagger:
            delay = randFloat(period)
        if self.wantSmoothPosBroadcastTask():
            taskMgr.doMethodLater(self.__broadcastPeriod + delay,
                                  self._posHprBroadcast, taskName)
        
        self.broadcasting = True
            
    def stopPosHprBroadcast(self):
        taskMgr.remove(self.getPosHprBroadcastTaskName() + '-%s' % base.localAvatar.doId)
        # Delete this callback because it maintains a reference to self
        self.d_broadcastPosHpr = None
        self.broadcasting = False
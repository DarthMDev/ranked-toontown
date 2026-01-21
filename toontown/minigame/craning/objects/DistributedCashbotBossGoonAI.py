from panda3d.core import *
from direct.task.TaskManagerGlobal import *
from direct.task.Task import Task
from toontown.toonbase import ToontownGlobals
from toontown.minigame.craning.objects import DistributedCashbotBossObjectAI
from toontown.minigame.craning import CraneGameGlobals
from direct.showbase import PythonUtil
from toontown.minigame.utils.objects import DistributedGoonAI, GoonGlobals
import math
import random

class DistributedCashbotBossGoonAI(DistributedGoonAI.DistributedGoonAI, DistributedCashbotBossObjectAI.DistributedCashbotBossObjectAI):

    """ This is a goon that walks around in the Cashbot CFO final
    battle scene, tormenting Toons, and also providing ammo for
    defeating the boss. """
    
    legLength = 10
    
    # A table of likely directions for the next choice at each point.
    # The table contains (heading, weight), where heading is the
    # direction of choice, and weight is the relative preference of
    # this direction over the others.
    directionTable = [(0, 15),
     (10, 10),
     (-10, 10),
     (20, 8),
     (-20, 8),
     (40, 5),
     (-40, 5),
     (60, 4),
     (-60, 4),
     (80, 3),
     (-80, 3),
     (120, 2),
     (-120, 2),
     (180, 1)]
     
    offMask = BitMask32(0)
    onMask = CollisionNode.getDefaultCollideMask()

    def __init__(self, air, boss):
        DistributedGoonAI.DistributedGoonAI.__init__(self, air, 0)
        DistributedCashbotBossObjectAI.DistributedCashbotBossObjectAI.__init__(self, air, boss)

        air.memoryDebugger.track_weak(self, "CraneGameGoon")
        # A tube covering our intended path, so other goons will see
        # and avoid us.
        cn = CollisionNode('tubeNode')
        self.tube = CollisionTube(0, 0, 0, 0, 0, 0, 2)
        cn.addSolid(self.tube)
        self.tubeNode = cn
        self.tubeNodePath = self.attachNewNode(self.tubeNode)

        # A spray of feeler wires so we can choose an empty path.
        self.feelers = []
        cn = CollisionNode('feelerNode')
        self.feelerLength = self.legLength * 1.5
        feelerStart = 1
        for heading, weight in self.directionTable:
            rad = deg2Rad(heading)
            x = -math.sin(rad)
            y = math.cos(rad)
            seg = CollisionSegment(x * feelerStart, y * feelerStart, 0, x * self.feelerLength, y * self.feelerLength, 0)
            cn.addSolid(seg)
            self.feelers.append(seg)

        cn.setIntoCollideMask(self.offMask)
        self.feelerNodePath = self.attachNewNode(cn)
        self.isWalking = 0
        self.cTrav = CollisionTraverser('goon')
        self.cQueue = CollisionHandlerQueue()
        self.cTrav.addCollider(self.feelerNodePath, self.cQueue)

        # Add safeDetectionFeelers from -45° to 45°
        cn = CollisionNode('safeDetectionFeelers')
        cn.addSolid(CollisionSphere(0, 0, 0, 1.8))  # Sphere to detect safes
        cn.setFromCollideMask(ToontownGlobals.CashbotBossObjectBitmask)
        cn.setIntoCollideMask(BitMask32(0))  # Only detect safes, no collisions INTO these segments
        self.safeDetectionFeelersPath = self.attachNewNode(cn)

        # Add safeDetectionFeelers to cTrav
        self.cTrav.addCollider(self.safeDetectionFeelersPath, self.cQueue)
        self.isStunned = 0

    def __syncEmergePosition(self, task):
        now = globalClock.getFrameTime()
        elapsedTime = now - self.departureTime
        totalTime = self.arrivalTime - self.departureTime

        if elapsedTime >= totalTime:
            self.setPos(self.emergeEndPos)  # Finalize position at the end
            return task.done

        # Linear interpolation of position
        progress = elapsedTime / totalTime
        newPos = self.emergeStartPos + (self.emergeEndPos - self.emergeStartPos) * progress
        self.setPos(newPos)

        return task.cont

    def _pushSafe(self, safe):
        goonPos = self.getPos()
        safePos = safe.getPos()

        direction = safePos - goonPos
        direction[2] = 0 #prevents pushing safes up/down
        direction.normalize()

        pushDistance = self.velocity * globalClock.getDt()
        newSafePos = safePos + direction * pushDistance
        safe.push(newSafePos[0], newSafePos[1], newSafePos[2], safe.getH(), self)

    def __checkSafeCollisions(self, task):
        self.cTrav.traverse(self.boss.scene)

        for i in range(self.cQueue.getNumEntries()):
            entry = self.cQueue.getEntry(i)
            intoNodePath = entry.getIntoNodePath()
            intoNode = intoNodePath.node()
            fromNode = entry.getFromNode()

            # Only process safe collisions from safe detection feelers
            if 'safe' in intoNode.getName() and 'safeDetectionFeelers' in fromNode.getName():
                # Get the safe's doId
                safeDoIdTag = intoNodePath.getNetTag('doId')
                if safeDoIdTag:
                    safeDoId = int(safeDoIdTag)
                    safe = simbase.air.doId2do.get(safeDoId)
                    if safe and safe.state in ['Sliding Floor', 'Free']:
                        self._pushSafe(safe)
        return task.cont

    def requestBattle(self, pauseTime):
        avId = self.air.getAvatarIdFromSender()

        # Here we ask the boss to damage the toon, instead of asking
        # the level to do it.
        
        avatar = self.air.doId2do.get(avId)
        if avatar:
            self.boss.damageToon(avatar, self.strength)
            
        DistributedGoonAI.DistributedGoonAI.requestBattle(self, pauseTime)

    def sendMovie(self, type, avId = 0, pauseTime = 0):
        # Overridden from DistributedGoonAI.
        if type == GoonGlobals.GOON_MOVIE_WALK:
            # Check if the goon is on a platform - if so, don't allow walking
            if hasattr(self, 'platformIndex') and self.platformIndex >= 0:
                # On a platform - stay in Stunned, don't walk
                return
            else:
                self.demand('Walk')
        elif type == GoonGlobals.GOON_MOVIE_BATTLE:
            self.demand('Battle')
        elif type == GoonGlobals.GOON_MOVIE_STUNNED:
            self.demand('Stunned')
        elif type == GoonGlobals.GOON_MOVIE_RECOVERY:
            # Check if the goon is on a platform - if so, don't allow recovery (stay stunned)
            if hasattr(self, 'platformIndex') and self.platformIndex >= 0:
                # On a platform - stay in Stunned, don't recover
                return
            self.demand('Recovery')
        else:
            self.notify.warning('Ignoring movie type %s' % type)

    def __chooseTarget(self, extraDelay = 0):
        # Chooses a random point to walk towards.
        direction = self.__chooseDirection()
        if direction == None:
            # No place to go; just blow up.
            self.target = None
            self.arrivalTime = None
            self.b_destroyGoon()
            return False
            
        heading, dist = direction
        dist = min(dist, self.legLength)
        targetH = PythonUtil.reduceAngle(self.getH() + heading)
        
        # How long will it take to rotate to position?
        origH = self.getH()
        h = PythonUtil.fitDestAngle2Src(origH, targetH)
        delta = h - origH
        turnTime = abs(delta) / (self.velocity * 5)
        
        # And how long will it take to walk to position?
        walkTime = dist / self.velocity
        self.target = self.boss.scene.getRelativePoint(self, Point3(dist * math.cos(deg2Rad(delta) + math.pi / 2),
                                                              dist * math.sin(deg2Rad(delta) + math.pi / 2),
                                                              0))

        taskMgr.doMethodLater(turnTime, self.setH, self.uniqueName('turnedToTarget'), extraArgs=[targetH])
        taskMgr.doMethodLater(turnTime, self.__startWalk, self.uniqueName('startingWalk'), extraArgs=[])

        self.departureTime = globalClock.getFrameTime()
        self.arrivalTime = self.departureTime + turnTime + walkTime + extraDelay
        self.d_setTarget(self.target[0], self.target[1], h, turnTime + walkTime + extraDelay)
        return True

    def __chooseDirection(self):

        # Chooses a direction to walk in next.  We do this by
        # examining a few likely directions, and we choose the one
        # with the clearest path (e.g. the fewest safes and other
        # goons in the way), with some randomness thrown in for fun.

        # Hack to prevent self-intersection.
        self.tubeNode.setIntoCollideMask(self.offMask)
        self.cTrav.traverse(self.boss.scene)
        self.tubeNode.setIntoCollideMask(self.onMask)

        entries = {}

        # Walk through the entries from farthest to nearest, so that
        # nearer collisions on the same segment will override farther
        # ones.
        self.cQueue.sortEntries()

        for i in range(self.cQueue.getNumEntries() - 1, -1, -1):
            entry = self.cQueue.getEntry(i)
            dist = Vec3(entry.getSurfacePoint(self)).length()

            if dist < 1.2:
                # Too close; forget it.
                dist = 0

            entries[entry.getFrom()] = dist

        # Now get the lengths of the various paths, and accumulate a
        # score table.  Each direction gets a score based on the
        # distance to the next obstruction, and its weighted
        # preference.
        netScore = 0
        scoreTable = []
        for i in range(len(self.directionTable)):
            heading, weight = self.directionTable[i]
            seg = self.feelers[i]
            dist = entries.get(seg, self.feelerLength)

            score = dist * weight
            netScore += score
            scoreTable.append(score)

        if netScore == 0:
            # If no paths were any good, bail.
            self.notify.info('Could not find a path for %s' % self.doId)
            return None

        # And finally, choose a random direction from the table,
        # with a random distribution weighted by score.
        s = random.uniform(0, netScore)
        for i in range(len(self.directionTable)):
            s -= scoreTable[i]
            if s <= 0:
                heading, weight = self.directionTable[i]
                seg = self.feelers[i]
                dist = entries.get(seg, self.feelerLength)
                return (heading, dist)

        # Shouldn't be possible to fall off the end, but maybe there
        # was a roundoff error.
        self.notify.warning('Fell off end of weighted table.')
        return (0, self.legLength)

    def __updatePosition(self):
        #Updates goon position/orientation when states change while walking
        currentTime = globalClock.getFrameTime()
        turnTask = taskMgr.getTasksNamed(self.uniqueName('turnedToTarget'))
        if turnTask:
            delayTime = turnTask[0].delayTime
            wakeTime = turnTask[0].wakeTime

            origH = self.getH()
            targetH = turnTask[0].getArgs()[0]
            taskMgr.remove(self.uniqueName('turnedToTarget'))
            taskMgr.remove(self.uniqueName('startingWalk'))
            correctedH = (1 - (wakeTime - currentTime) / max(0.1, delayTime)) * PythonUtil.reduceAngle((targetH - origH)) + origH
            self.setH(correctedH)

        if taskMgr.getTasksNamed(self.uniqueName('reachedTarget')):
            self.__stopWalk()
            taskMgr.remove(self.uniqueName('reachedTarget'))



    def __startWalk(self):
        # Generate a do-later method to "walk" the goon to his target
        # square by the specified time.  Actually, on the AI the goon
        # just stands where he is until the time expires, but no one
        # cares about that.
        if self.arrivalTime == None:
            return

        now = globalClock.getFrameTime()
        availableTime = self.arrivalTime - now

        if availableTime > 0:
            # Change the tube to encapsulate our path to our target point.
            point = self.getRelativePoint(self.boss.scene, self.target)
            self.tube.setPointB(point)
            self.node().resetPrevTransform()

            taskMgr.doMethodLater(availableTime, self.__reachedTarget, self.uniqueName('reachedTarget'))

            self.isWalking = 1
        else:
            self.__reachedTarget(None)
        return

    def __stopWalk(self, pauseTime = None):
        if self.isWalking:
            # Stop the walk do-later.
            taskMgr.remove(self.uniqueName('reachedTarget'))

            # Place us at the appropriate point along the path.
            if pauseTime == None:
                now = globalClock.getFrameTime()
                t = (now - self.departureTime) / (self.arrivalTime - self.departureTime)
            else:
                t = pauseTime / (self.arrivalTime - self.departureTime)

            t = min(t, 1.0)
            pos = self.getPos()
            self.setPos(pos + (self.target - pos) * t)

            # The tube is now a sphere.
            self.tube.setPointB(0, 0, 0)

            self.isWalking = 0
        return

    def __reachedTarget(self, task):
        self.__stopWalk()
        self.__chooseTarget()

    def __recoverWalk(self, task):
        # Check if the goon is on a platform - if so, stay stunned (can't walk on moving platforms)
        if hasattr(self, 'platformIndex') and self.platformIndex >= 0:
            # On a platform - transition back to Stunned (don't walk, don't recover)
            self.demand('Stunned')
            return Task.done
        
        self.demand('Walk')
        return Task.done

    def doFree(self, task):
        # This method is fired as a do-later when we enter WaitFree.
        DistributedCashbotBossObjectAI.DistributedCashbotBossObjectAI.doFree(self, task)
        
        # Check if the goon is on a platform
        onPlatform = hasattr(self, 'platformIndex') and self.platformIndex >= 0
        
        if onPlatform:
            # On a platform - stay in Stunned (never wake up)
            self.demand('Stunned')
        elif self.isStunned:
            # Stunned but not on platform - go to Recovery (will wake up)
            self.demand('Recovery')
        else:
            self.demand('Walk')
        return Task.done

    def stun(self, avId, pauseTime):

        av = self.air.doId2do.get(avId)
        if av and av.getHp() <= 0:
            return
        if avId not in self.boss.avIdList:
            return
        if self.state == 'Stunned' or self.state == 'Grabbed':
            # Already stunned, or just picked up by a magnet; don't
            # stun again.
            return

        taskMgr.remove(self.uniqueName('droneStun'))

        if self.boss.ruleset.GOONS_DIE_ON_STOMP:
            self.b_destroyGoon()
            self.boss.addScore(avId, self.boss.ruleset.POINTS_GOON_KILLED_BY_SAFE,
                               reason=CraneGameGlobals.ScoreReason.GOON_KILL)
            return

        # Stop the goon right where he is.
        self.__stopWalk(pauseTime)

        # And it poops out a treasure right there.
        self.boss.makeTreasure(self)

        # Update stats and add track combo for points
        self.boss.addScore(avId, self.boss.ruleset.POINTS_GOON_STOMP, reason=CraneGameGlobals.ScoreReason.GOON_STOMP)
        comboTracker = self.boss.comboTrackers[avId]
        comboTracker.incrementCombo(math.ceil((comboTracker.combo + 1.0) / 4.0))
        # Check if the goon is on a platform - if so, don't schedule recovery (stay stunned forever)
        if hasattr(self, 'platformIndex') and self.platformIndex >= 0:
            # On a platform - just transition to Stunned but don't schedule recovery
            # Call sendMovie directly instead of parent's requestStunned (which schedules recovery)
            self.sendMovie(GoonGlobals.GOON_MOVIE_STUNNED, avId, pauseTime)
            # Don't call parent's requestStunned - it would schedule recovery task that wakes the goon
        else:
            # Not on platform - normal behavior (will recover after STUN_TIME)
            DistributedGoonAI.DistributedGoonAI.requestStunned(self, pauseTime)


    ### Messages ###

    def hitPlatform(self, platformIndex):
        # Override parent's hitPlatform to immediately stun goons when they hit a platform
        avId = self.air.getAvatarIdFromSender()
        
        if avId == self.avId and self.state in ('Dropped', 'Falling', 'SlidingFloor'):
            # Goon hit a platform - immediately stun it
            self.platformIndex = platformIndex
            # Transition to Stunned immediately (goons on platforms stay stunned forever)
            # Don't schedule recovery task - goons on platforms never wake up
            self.demand('Stunned')
            # Broadcast platform index to all clients
            self.sendUpdate('setPlatformIndex', [platformIndex])
        else:
            # For other states, use parent's behavior
            DistributedCashbotBossObjectAI.DistributedCashbotBossObjectAI.hitPlatform(self, platformIndex)

    def requestStunned(self, pauseTime):
        avId = self.air.getAvatarIdFromSender()

        if avId not in self.air.doId2do:
            return

        self.stun(avId, pauseTime)

    def getMinImpact(self):
        return self.boss.ruleset.MIN_GOON_IMPACT

    def hitBoss(self, impact, craneId):
        avId = self.air.getAvatarIdFromSender()
        
        # Check if impact cap should be removed
        removeCap = False
        if hasattr(self.boss, 'ruleset') and hasattr(self.boss.ruleset, 'REMOVE_IMPACT_CAP'):
            removeCap = self.boss.ruleset.REMOVE_IMPACT_CAP
        
        # Validate impact based on whether cap is removed
        if removeCap:
            self.validate(avId, impact >= 0, 'invalid hitBoss impact %s' % impact)
        else:
            self.validate(avId, 1.0 >= impact >= 0, 'invalid hitBoss impact %s' % impact)
        if avId not in self.boss.avIdList:
            return

        if impact <= self.getMinImpact():
            self.boss.addScore(avId, self.boss.ruleset.POINTS_PENALTY_SANDBAG, reason=CraneGameGlobals.ScoreReason.LOW_IMPACT)
            return

        avatar = self.air.doId2do.get(avId)
        if self.state == 'Dropped' or self.state == 'Grabbed':
            # A goon can only hurt the boss when he's got a helmet on.
            if not self.boss.getBoss().heldObject:
                damage = int(impact * 25 * self.scale * 0.8)
                crane = simbase.air.doId2do.get(craneId)
                # Apply a multiplier if needed (heavy cranes)
                damage *= crane.getDamageMultiplier()
                damage *= self.boss.ruleset.GOON_CFO_DAMAGE_MULTIPLIER
                damage = math.ceil(damage)
                self.boss.recordHit(max(damage, 2), impact, craneId, isGoon=True)
        self.b_destroyGoon()

    def d_setTarget(self, x, y, h, travelTime):
        self.sendUpdate('setTarget', [x,
         y,
         h,
         travelTime])

    def d_destroyGoon(self):
        self.sendUpdate('destroyGoon')
    
    def d_destroyedByTNT(self, avId):
        """Called from client when goon is destroyed by TNT explosion"""
        self.sendUpdate('destroyedByTNT', [avId])

    def b_destroyGoon(self):
        self.d_destroyGoon()
        self.destroyGoon()
    
    def destroyedByTNT(self, avId):
        """Award points when goon is destroyed by TNT"""
        self.notify.debug('destroyedByTNT: avId=%d, goon state=%s' % (avId, self.state))
        
        # Prevent duplicate awards - check if goon is already destroyed
        if self.state == 'Off':
            self.notify.debug('destroyedByTNT: Goon already destroyed, skipping')
            return
        
        if not self.boss:
            self.notify.warning('destroyedByTNT: No boss reference')
            return
        
        if not hasattr(self.boss, 'avIdList'):
            self.notify.warning('destroyedByTNT: Boss has no avIdList')
            return
        
        if avId not in self.boss.avIdList:
            self.notify.debug('destroyedByTNT: avId %d not in avIdList' % avId)
            return
        
        # Award points for TNT goon destruction (same as safe destruction)
        self.notify.debug('destroyedByTNT: Awarding points to avId %d' % avId)
        self.boss.addScore(avId, self.boss.ruleset.POINTS_GOON_KILLED_BY_SAFE, reason=CraneGameGlobals.ScoreReason.GOON_KILL)
        # Then destroy the goon
        self.b_destroyGoon()

    def destroyGoon(self):
        # The client or AI informs the world that the goon has
        # shuffled off this mortal coil.

        self.demand('Off')
        if self in self.boss.goons:
            self.boss.goons.remove(self)

        self.requestDelete()


    ### FSM States ###

    def enterOff(self):
        # Check if NodePaths exist before trying to stash them
        if hasattr(self, 'tubeNodePath') and self.tubeNodePath is not None:
            self.tubeNodePath.stash()
        if hasattr(self, 'feelerNodePath') and self.feelerNodePath is not None:
            self.feelerNodePath.stash()
        taskMgr.remove(self.uniqueName('reachedTarget'))
        taskMgr.remove(self.uniqueName('turnedToTarget'))
        taskMgr.remove(self.uniqueName('startingWalk'))

    def exitOff(self):
        # Check if NodePaths exist before trying to unstash them
        if hasattr(self, 'tubeNodePath') and self.tubeNodePath is not None:
            self.tubeNodePath.unstash()
        if hasattr(self, 'feelerNodePath') and self.feelerNodePath is not None:
            self.feelerNodePath.unstash()

    def enterGrabbed(self, avId, craneId):
        crane = simbase.air.doId2do.get(craneId)
        DistributedCashbotBossObjectAI.DistributedCashbotBossObjectAI.enterGrabbed(self, avId, craneId)

        # If a goon is grabbed while he's just waking up, it
        # interrupts the wake-up process.  Ditto for a goon in battle
        # mode.
        self.__updatePosition()
        taskMgr.remove(self.taskName('recovery'))
        taskMgr.remove(self.taskName('resumeWalk'))
        taskMgr.remove(self.uniqueName('recoverWalk'))

    def enterWalk(self):
        # Check if the goon is on a platform - if so, don't enter Walk (can't walk on moving platforms)
        if hasattr(self, 'platformIndex') and self.platformIndex >= 0:
            # On a platform - transition back to Stunned instead (stay stunned forever)
            self.demand('Stunned')
            return
        
        self.avId = 0
        self.craneId = 0
        self.isStunned = 0

        if self.__chooseTarget():
            self.d_setObjectState('W', 0, 0)

    def exitWalk(self):
        self.__stopWalk()

    def enterEmergeA(self):
        # The goon is emerging from door a.
        self.avId = 0
        self.craneId = 0

        h = 0
        dist = 15
        pos = self.boss.getBoss().getPos()
        walkTime = dist / self.velocity

        self.setPosHpr(pos[0], pos[1], pos[2], h, 0, 0)
        self.d_setPosHpr(pos[0], pos[1], pos[2], h, 0, 0)
        self.target = self.boss.scene.getRelativePoint(self, Point3(0, dist, 0))
        self.departureTime = globalClock.getFrameTime()
        self.arrivalTime = self.departureTime + walkTime

        self.emergeStartPos = self.getPos()
        self.emergeEndPos = self.target

        self.d_setTarget(self.target[0], self.target[1], h, walkTime)

        self.__startWalk()
        taskMgr.remove(self.uniqueName('reachedTarget'))
        self.d_setObjectState('a', 0, 0)

        # Start synchronization task
        taskMgr.add(self.__syncEmergePosition, self.uniqueName('syncEmergePosition'))

        taskMgr.doMethodLater(walkTime, self.__recoverWalk, self.uniqueName('recoverWalk'))
        self.safeDetectionFeelersPath.unstash()
        taskMgr.add(self.__checkSafeCollisions, self.uniqueName('checkSafeCollisions'))

    def exitEmergeA(self):
        self.__stopWalk()
        taskMgr.remove(self.uniqueName('recoverWalk'))
        taskMgr.remove(self.uniqueName('syncEmergePosition'))
        self.safeDetectionFeelersPath.stash()
        taskMgr.remove(self.uniqueName('checkSafeCollisions'))

    def enterEmergeB(self):
        # The goon is emerging from door b.
        self.avId = 0
        self.craneId = 0

        h = 180
        dist = 15
        pos = self.boss.getBoss().getPos()
        walkTime = dist / self.velocity

        self.setPosHpr(pos[0], pos[1], pos[2], h, 0, 0)
        self.d_setPosHpr(pos[0], pos[1], pos[2], h, 0, 0)
        self.target = self.boss.scene.getRelativePoint(self, Point3(0, dist, 0))
        self.departureTime = globalClock.getFrameTime()
        self.arrivalTime = self.departureTime + walkTime

        self.emergeStartPos = self.getPos()
        self.emergeEndPos = self.target

        self.d_setTarget(self.target[0], self.target[1], h, walkTime)
        
        self.__startWalk()
        taskMgr.remove(self.uniqueName('reachedTarget'))
        self.d_setObjectState('b', 0, 0)

        # Start synchronization task
        taskMgr.add(self.__syncEmergePosition, self.uniqueName('syncEmergePosition'))
        
        taskMgr.doMethodLater(walkTime, self.__recoverWalk, self.uniqueName('recoverWalk'))
        self.safeDetectionFeelersPath.unstash()
        taskMgr.add(self.__checkSafeCollisions, self.uniqueName('checkSafeCollisions'))

    def exitEmergeB(self):
        self.__stopWalk()
        taskMgr.remove(self.uniqueName('recoverWalk'))
        taskMgr.remove(self.uniqueName('syncEmergePosition'))
        self.safeDetectionFeelersPath.stash()
        taskMgr.remove(self.uniqueName('checkSafeCollisions'))

    def enterBattle(self):
        self.__updatePosition()
        self.d_setObjectState('B', 0, 0)

    def exitBattle(self):
        taskMgr.remove(self.taskName('resumeWalk'))

    def enterStunned(self):
        self.isStunned = 1
        self.__updatePosition()
        self.d_setObjectState('S', 0, 0)

    def exitStunned(self):
        taskMgr.remove(self.taskName('recovery'))

    def enterRecovery(self):
        self.d_setObjectState('R', 0, 0)
        taskMgr.doMethodLater(2.0, self.__recoverWalk, self.uniqueName('recoverWalk'))

    def exitRecovery(self):
        self.__stopWalk()
        taskMgr.remove(self.uniqueName('recoverWalk'))

    def requestWalk(self):
        avId = self.air.getAvatarIdFromSender()
        if avId == self.avId and self.state == 'Stunned' and self.state != 'Off':
            # Check if the goon is on a platform - if so, don't allow walking
            if hasattr(self, 'platformIndex') and self.platformIndex >= 0:
                return
            craneId, objectId = self.getCraneAndObject(avId)
            if craneId != 0 and objectId == self.doId:
                self.demand('Walk', avId, craneId)

    def startSmooth(self):
        self.sendUpdate('startSmooth')
        DistributedSmoothNodeAI.startSmooth(self)

    def stopSmooth(self):
        self.sendUpdate('stopSmooth')
        DistributedSmoothNodeAI.stopSmooth(self)

    def enterFalling(self):
        self.avId = 0
        self.craneId = 0
        self.isStunned = 1
        self.d_setObjectState('F', 0, 0)
        # Schedule recovery after landing
        taskMgr.doMethodLater(2.5, self.__recoverFromFall, self.uniqueName('recoverFromFall'))

    def exitFalling(self):
        taskMgr.remove(self.uniqueName('recoverFromFall'))

    def __recoverFromFall(self, task):
        # Check if the goon is on a platform - if so, preserve Z position and stay in Stunned
        if hasattr(self, 'platformIndex') and self.platformIndex >= 0:
            # On a platform - don't reset Z to 0, preserve current Z
            pos = self.getPos()
            # Don't change Z position (it's at the platform's height)
            self.d_setXY(pos[0], pos[1])
            # Transition to Stunned (will stay stunned forever on platform)
            self.demand('Stunned')
        else:
            # On the floor - make sure we're at ground level
            pos = self.getPos()
            self.setPos(pos[0], pos[1], 0)
            self.d_setXY(pos[0], pos[1])
            # Only transition to Recovery if stunned, otherwise go to Walk
            if self.isStunned:
                self.demand('Recovery')
            else:
                self.demand('Walk')
        return Task.done
    
    def cleanup(self):
        """Clean up collision system and node paths to prevent memory leaks"""
        # Clean up collision system
        if hasattr(self, 'cTrav') and self.cTrav is not None:
            self.cTrav.clearColliders()
            del self.cTrav
        if hasattr(self, 'cQueue') and self.cQueue is not None:
            del self.cQueue
        # Clear feelers list
        if hasattr(self, 'feelers') and self.feelers is not None:
            self.feelers.clear()
        # Clean up collision nodes
        if hasattr(self, 'tubeNode') and self.tubeNode is not None:
            self.tubeNode = None
        
        # Remove all tasks
        taskMgr.remove(self.uniqueName('droneStun'))
        taskMgr.remove(self.uniqueName('reachedTarget'))
        taskMgr.remove(self.uniqueName('turnedToTarget'))
        taskMgr.remove(self.uniqueName('startingWalk'))
        taskMgr.remove(self.uniqueName('syncEmergePosition'))
        taskMgr.remove(self.uniqueName('recoverWalk'))
        taskMgr.remove(self.uniqueName('checkSafeCollisions'))
        taskMgr.remove(self.uniqueName('recoverFromFall'))

    def cleanupNodePaths(self):
        """Clean up node paths - called only when safe to do so (after FSM is done)"""
        # Clean up node paths - check both existence and not None
        if hasattr(self, 'tubeNodePath') and self.tubeNodePath is not None:
            self.tubeNodePath.removeNode()
            self.tubeNodePath = None
        if hasattr(self, 'feelerNodePath') and self.feelerNodePath is not None:
            self.feelerNodePath.removeNode()
            self.feelerNodePath = None
        if hasattr(self, 'safeDetectionFeelersPath') and self.safeDetectionFeelersPath is not None:
            self.safeDetectionFeelersPath.removeNode()
            self.safeDetectionFeelersPath = None

    def delete(self):
        # Clean up resources before deletion, but handle NodePaths carefully
        self.cleanup()
        # Clean up NodePaths only after FSM is done
        self.cleanupNodePaths()
        DistributedGoonAI.DistributedGoonAI.delete(self)
        DistributedCashbotBossObjectAI.DistributedCashbotBossObjectAI.delete(self)
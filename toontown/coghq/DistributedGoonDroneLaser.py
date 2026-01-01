"""
Laser Drone - Flies to nearest opponent and shoots 3 lasers.
"""

from panda3d.core import *
from direct.interval.IntervalGlobal import *
from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from toontown.coghq import CraneLeagueGlobals
from toontown.coghq.DistributedGoonDroneBase import DistributedGoonDroneBase


class DistributedGoonDroneLaser(DistributedGoonDroneBase):
    """
    Laser drone that:
    1. Spawns above owner
    2. Flies to position near nearest opponent
    3. Locks orientation to target
    4. Fires 3 lasers over 1 second
    5. Pauses 2 seconds
    6. Vanishes
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGoonDroneLaser')
    
    def __init__(self, cr):
        DistributedGoonDroneBase.__init__(self, cr)
        self.laserShots = []
        self.hitToons = set()  # Track toons hit to prevent multiple hits bypassing iframes
        self.flyTask = None
    
    def getDroneType(self):
        return CraneLeagueGlobals.DroneType.LASER
    
    def needsOpponents(self):
        """Laser drones need opponents to function."""
        return True
    
    def startBehavior(self):
        """Start the laser drone flying and shooting behavior."""
        if not self.targetId:
            # If still no target after delay, vanish
            self.vanishWithPoof()
            return
        
        self.startFlying()
    
    def startFlying(self):
        """Start the flying behavior sequence."""
        # Get owner position
        owner = base.cr.doId2do.get(self.ownerId)
        if not owner:
            return
        
        ownerPos = owner.getPos(render)
        startPos = Point3(ownerPos.getX(), ownerPos.getY(), ownerPos.getZ() + 15)
        self.setPos(startPos)
        
        # Use the target that was determined at spawn (from AI)
        if not self.targetId:
            self.vanishWithPoof()
            return
        
        target = base.cr.doId2do.get(self.targetId)
        if not target:
            self.vanishWithPoof()
            return
        
        # Ensure target is not the owner
        if target.doId == self.ownerId:
            self.vanishWithPoof()
            return
        
        targetPos = target.getPos(render)
        
        # Calculate final position - in front of target
        direction = startPos - targetPos
        direction.setZ(0)
        if direction.length() > 0:
            direction.normalize()
        else:
            direction = Vec3(0, 1, 0)
        
        finalPos = Point3(
            targetPos.getX() + direction.getX() * 5,
            targetPos.getY() + direction.getY() * 5,
            targetPos.getZ() + 10
        )
        
        # Avoid going through the CFO boss
        lerpPath = self._calculatePathAvoidingBoss(startPos, finalPos)
        
        # Create task to continuously look at target
        def lookAtTargetTask(task):
            if not self.isEmpty():
                currentTarget = base.cr.doId2do.get(self.targetId)
                if currentTarget:
                    currentTargetPos = currentTarget.getPos(render)
                    self.lookAt(currentTargetPos)
                    self.setP(0)  # Keep level
            return Task.cont
        
        self.behaviorSequence = Sequence(
            # Hover over owner for 1 second
            Wait(1.0),
            
            # Lerp to final position over 2 seconds while looking at target
            Func(taskMgr.add, lookAtTargetTask, self.uniqueName('lookAtTarget')),
            lerpPath,
            
            # Lock orientation to target for 1 second
            Wait(1.0),
            
            # Fire 3 lasers over 1 second
            Func(self.shootLasers, None),
            Wait(1.0),
            
            # Stop adjusting HPR
            Func(taskMgr.remove, self.uniqueName('lookAtTarget')),
            
            # Pause 2 seconds
            Wait(2.0),
            
            # Vanish
            Func(self.vanishWithPoof)
        )
        self.behaviorSequence.start()
    
    def _calculatePathAvoidingBoss(self, startPos, finalPos):
        """Calculate a path that avoids the CFO boss."""
        # Make sure we have a valid boss reference
        if not self.boss:
            self._findBoss()
        
        if self.boss and hasattr(self.boss, 'getPos'):
            try:
                bossPos = self.boss.getPos(render)
                bossRadius = 10.0
                
                # Check if the direct path would go through the boss
                pathVec = finalPos - startPos
                pathLength = pathVec.length()
                if pathLength > 0:
                    pathDir = pathVec / pathLength
                    
                    # Check multiple points along the path
                    numChecks = 10
                    minDist = float('inf')
                    closestPointOnPath = None
                    
                    for i in range(numChecks + 1):
                        t = float(i) / numChecks
                        checkPoint = startPos + pathDir * (pathLength * t)
                        distToBoss = (checkPoint - bossPos).length()
                        if distToBoss < minDist:
                            minDist = distToBoss
                            closestPointOnPath = checkPoint
                    
                    # If path is too close to boss, create waypoint
                    if minDist < bossRadius + 8.0:
                        perp = Vec3(-pathDir.getY(), pathDir.getX(), 0)
                        if perp.length() < 0.1:
                            perp = Vec3(1, 0, 0)
                        perp.normalize()
                        
                        # Choose side further from boss
                        if perp.dot(bossPos - closestPointOnPath) > 0:
                            perp = -perp
                        
                        avoidDistance = bossRadius + 8.0 - minDist
                        if avoidDistance < 0:
                            avoidDistance = 8.0
                        
                        waypointBase = startPos + pathDir * (pathLength * 0.5)
                        waypoint = waypointBase + perp * (avoidDistance + 5.0)
                        waypoint.setZ((startPos.getZ() + finalPos.getZ()) / 2)
                        
                        # Use smooth curve through waypoint
                        return Sequence(
                            LerpPosInterval(self, duration=1.0, pos=waypoint, startPos=startPos),
                            LerpPosInterval(self, duration=1.0, pos=finalPos, startPos=waypoint)
                        )
            except:
                pass
        
        # Direct path if no boss or no collision
        return LerpPosInterval(self, duration=2.0, pos=finalPos, startPos=startPos)
    
    def shootLasers(self, task):
        """Shoot 3 lasers at the target over 1 second."""
        # Clear hit tracking for new volley
        self.hitToons.clear()
        
        if not self.targetId:
            self.vanishWithPoof()
            return Task.done if task else None
        
        target = base.cr.doId2do.get(self.targetId)
        if not target:
            self.vanishWithPoof()
            return Task.done if task else None
        
        # Ensure target is not the owner
        if target.doId == self.ownerId:
            self.vanishWithPoof()
            return Task.done if task else None
        
        # Shoot 3 lasers with 0.5 seconds between each
        for i in range(3):
            delay = i * 0.5
            def makeShootLaserTask(tgt):
                def shootLaserTask(task):
                    return self.shootSingleLaser(tgt, task)
                return shootLaserTask
            taskMgr.doMethodLater(delay, makeShootLaserTask(target), 
                                 self.uniqueName('shootLaser-%d' % i))
        
        return Task.done if task else None
    
    def shootSingleLaser(self, target, task=None):
        """Shoot a single laser at the target."""
        if not target or target.isEmpty():
            if task:
                return Task.done
            return
        
        # Get eye position from the goon model
        if hasattr(self, 'eye') and not self.eye.isEmpty():
            eyePos = self.eye.getPos(render)
        elif hasattr(self, 'head') and not self.head.isEmpty():
            eyePos = self.head.getPos(render)
            eyePos.setZ(eyePos.getZ() + 0.5)
        else:
            dronePos = self.getPos(render)
            eyePos = Point3(dronePos.getX(), dronePos.getY(), dronePos.getZ() + 3.0)
        
        targetPos = target.getPos(render)
        
        # Create laser visual effect
        self.createLaserEffect(eyePos, targetPos, target)
        
        # Send attack to server
        self.sendUpdate('shootLaser', [target.doId])
        
        if task:
            return Task.done
    
    def createLaserEffect(self, startPos, targetPos, target):
        """Create a straight laser beam that travels from start to target over 0.3 seconds."""
        from panda3d.core import LineSegs, TransparencyAttrib, Point3
        
        distance = (targetPos - startPos).length()
        
        if distance < 0.01:
            return
        
        direction = (targetPos - startPos) / distance
        
        # Create container node
        laserNP = render.attachNewNode('laser')
        laserNP.setTransparency(TransparencyAttrib.MAlpha)
        laserNP.setDepthWrite(False)
        
        currentLaserNode = None
        
        # Initialize with zero-length line
        initialLines = LineSegs('laser')
        initialLines.setColor(1, 0, 0, 1)
        initialLines.setThickness(3.0)
        initialLines.moveTo(startPos.getX(), startPos.getY(), startPos.getZ())
        initialLines.drawTo(startPos.getX(), startPos.getY(), startPos.getZ())
        currentLaserNode = laserNP.attachNewNode(initialLines.create())
        
        # Animate the laser traveling
        def updateLaser(t):
            nonlocal currentLaserNode
            
            currentDist = t * distance
            currentEndPos = startPos + direction * currentDist
            
            if currentLaserNode:
                currentLaserNode.removeNode()
            
            newLines = LineSegs('laser')
            newLines.setColor(1, 0, 0, 1)
            newLines.setThickness(3.0)
            newLines.moveTo(startPos.getX(), startPos.getY(), startPos.getZ())
            newLines.drawTo(currentEndPos.getX(), currentEndPos.getY(), currentEndPos.getZ())
            
            currentLaserNode = laserNP.attachNewNode(newLines.create())
            
            return t
        
        # Create animation sequence
        travelDuration = 0.3
        laserInterval = Sequence(
            # Travel from eye to target
            LerpFunctionInterval(updateLaser, duration=travelDuration, fromData=0.0, toData=1.0),
            # After travel completes, check collisions and apply damage
            Func(lambda: self.checkLaserCollisions(startPos, targetPos)),
            # Fade out
            LerpColorScaleInterval(laserNP, duration=0.7, colorScale=(1, 0, 0, 0), startColorScale=(1, 0, 0, 1)),
            Func(laserNP.removeNode)
        )
        laserInterval.start()
    
    def checkLaserCollisions(self, startPos, targetPos):
        """Check if the laser beam hits any toons and apply damage."""
        # Get all toons in the game
        toons = []
        
        if self.boss:
            if hasattr(self.boss, 'game') and self.boss.game:
                if hasattr(self.boss.game, 'getParticipants'):
                    toons = self.boss.game.getParticipants()
                elif hasattr(self.boss.game, 'getParticipantIdsNotSpectating'):
                    participantIds = self.boss.game.getParticipantIdsNotSpectating()
                    toons = [base.cr.doId2do.get(avId) for avId in participantIds if base.cr.doId2do.get(avId)]
            elif hasattr(self.boss, 'getInvolvedToonsNotSpectating'):
                involvedIds = self.boss.getInvolvedToonsNotSpectating()
                toons = [base.cr.doId2do.get(avId) for avId in involvedIds if base.cr.doId2do.get(avId)]
        
        # Fallback: check all toons in doId2do
        if not toons:
            for obj in base.cr.doId2do.values():
                if hasattr(obj, 'hp') and hasattr(obj, 'getPos'):
                    try:
                        obj.getPos(render)
                        toons.append(obj)
                    except:
                        pass
        
        # Check each toon for laser collision
        hitRadius = 2.0
        
        for toon in toons:
            if not toon or toon.isEmpty():
                continue
            
            # Don't hit the owner
            if toon.doId == self.ownerId:
                continue
            
            # Skip if already hit by this drone's lasers
            if toon.doId in self.hitToons:
                continue
            
            try:
                # Get toon's position
                toonPos = toon.getPos(render)
                
                # Calculate distance from toon to laser line segment
                lineVec = targetPos - startPos
                toonVec = toonPos - startPos
                
                lineLength = lineVec.length()
                if lineLength < 0.01:
                    continue
                
                lineDir = lineVec / lineLength
                projectionLength = toonVec.dot(lineDir)
                
                # Clamp projection to line segment
                projectionLength = max(0.0, min(lineLength, projectionLength))
                
                # Find closest point on line segment
                closestPoint = startPos + lineDir * projectionLength
                
                # Distance from toon to closest point
                distToLine = (toonPos - closestPoint).length()
                
                # Check if within hit radius
                if distToLine < hitRadius:
                    self.applyLaserDamage(toon)
            except:
                continue
    
    def applyLaserDamage(self, toon):
        """Apply damage to a toon hit by the laser."""
        if not toon or toon.isEmpty():
            return
        
        # Check and mark hit atomically to prevent race conditions
        if toon.doId in self.hitToons:
            return
        
        # Mark this toon as checked immediately
        self.hitToons.add(toon.doId)
        
        # Check iframes
        if toon.isStunned:
            return
        
        if toon.hp <= 0:
            return
        
        # Grant iframes immediately
        toon.stunToon()
        
        # Send damage request to AI
        self.sendUpdate('requestLaserHit', [toon.doId])
        
        # Knock toon off crane if they're on one
        if toon == base.localAvatar:
            messenger.send('exitCrane')
    
    def disable(self):
        """Clean up laser-specific resources."""
        # Remove laser shooting tasks
        for i in range(3):
            taskMgr.remove(self.uniqueName('shootLaser-%d' % i))
        taskMgr.remove(self.uniqueName('lookAtTarget'))
        if self.flyTask:
            taskMgr.remove(self.flyTask)
            self.flyTask = None
        
        DistributedGoonDroneBase.disable(self)


"""
DEPRECATED: This file is kept for backwards compatibility.
The drone system has been refactored into specialized classes.

New structure:
- DistributedGoonDroneBase - Base class with common functionality
- DistributedGoonDroneLaser - Laser drone implementation
- DistributedGoonDroneHeal - Heal drone implementation  
- DistributedGoonDroneExplosive - Explosive drone implementation
- DistributedGoonDroneStun - Stun drone implementation

This file now acts as a compatibility layer that routes to the appropriate class.
"""

from direct.directnotify import DirectNotifyGlobal
from toontown.coghq import CraneLeagueGlobals
from toontown.coghq.DistributedGoonDroneLaser import DistributedGoonDroneLaser
from toontown.coghq.DistributedGoonDroneHeal import DistributedGoonDroneHeal
from toontown.coghq.DistributedGoonDroneExplosive import DistributedGoonDroneExplosive
from toontown.coghq.DistributedGoonDroneStun import DistributedGoonDroneStun

# For backwards compatibility, map the old class name to Laser drone
# (since Laser was the default/original type)
class DistributedGoonDrone(DistributedGoonDroneLaser):
    """
    Backwards compatibility wrapper.
    Defaults to Laser drone behavior.
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGoonDrone')
    
    def __init__(self, cr):
        DistributedCrushableEntity.DistributedCrushableEntity.__init__(self, cr)
        DistributedGoon.DistributedGoon.__init__(self, cr)
        self.boss = None
        self.ownerId = 0  # Toon who deployed this drone
        self.targetId = None  # Target toon ID
        self.droneType = CraneLeagueGlobals.DroneType.LASER  # Default to laser
        self.deployTime = 0
        self.propeller = None
        self.propellerSpinTask = None
        self.flyTask = None
        self.laserShots = []
        self.behaviorSequence = None
        self.hitToons = set()  # Track toons hit by this drone's lasers to prevent multiple hits bypassing iframes
        
    def setOwnerId(self, ownerId):
        """Set the owner ID (received from AI)."""
        self.ownerId = ownerId
        
    def setDroneType(self, droneTypeValue):
        """Set the drone type (received from AI)."""
        self.droneType = CraneLeagueGlobals.DroneType(droneTypeValue)
        # Update hat color based on drone type
        self.updateHatColor()
    
    def updateHatColor(self):
        """Update the hat color based on drone type."""
        hatColor = self.droneType.getHatColor()
        
        # Try multiple methods to find the hat
        hat = None
        
        # Method 1: Try hat directly (if goon has created it)
        if hasattr(self, 'hat') and self.hat and not self.hat.isEmpty():
            hat = self.hat
        
        # Method 2: Try finding via head
        if not hat and hasattr(self, 'head') and self.head and not self.head.isEmpty():
            hat = self.head.find('**/hat')
        
        # Method 3: Try finding via joint8 (hat joint)
        if hat.isEmpty() if hat else True:
            hat = self.find('**/joint8')
        
        # Method 4: Try finding any hat in the model
        if hat.isEmpty() if hat else True:
            hat = self.find('**/hat')
        
        if hat and not hat.isEmpty():
            hat.setColorScale(hatColor)
        else:
            # Hat not found yet, try again later (head might not be set up)
            taskMgr.remove(self.uniqueName('updateHatColor'))
            taskMgr.doMethodLater(0.2, self.updateHatColor, self.uniqueName('updateHatColor'))
    
    def setTargetId(self, targetId):
        """Set the target ID (received from AI)."""
        if targetId == 0:
            targetId = None
        self.targetId = targetId
        
        # If we're already set up and waiting for target, start the behavior now
        if targetId and hasattr(self, 'propeller') and self.propeller:
            # Check if behavior hasn't started yet
            if not hasattr(self, 'behaviorSequence') or self.behaviorSequence is None:
                taskMgr.remove(self.uniqueName('startBehavior'))
                if self.droneType == CraneLeagueGlobals.DroneType.LASER:
                    self.startFlying()
                elif self.droneType == CraneLeagueGlobals.DroneType.EXPLOSIVE:
                    self.startFlyingToCFO()
        
    def generate(self):
        DistributedCrushableEntity.DistributedCrushableEntity.generate(self)
        DistributedGoon.DistributedGoon.generate(self)
        
    def announceGenerate(self):
        DistributedCrushableEntity.DistributedCrushableEntity.announceGenerate(self)
        DistributedGoon.DistributedGoon.announceGenerate(self)
        
        # Get boss reference from owner or find it
        # First try to get from game if owner is in a crane game
        owner = base.cr.doId2do.get(self.ownerId)
        if owner:
            # Check if owner is in a minigame that has a boss
            if hasattr(base, 'curMinigame') and base.curMinigame:
                if hasattr(base.curMinigame, 'boss') and base.curMinigame.boss:
                    self.boss = base.curMinigame.boss
        
        # Fallback: try other methods
        if not self.boss:
            if hasattr(base, 'boss'):
                self.boss = base.boss
            elif hasattr(base, 'cr') and hasattr(base.cr, 'doId2do'):
                # Try to find boss in scene
                for obj in base.cr.doId2do.values():
                    if hasattr(obj, '__class__') and 'CashbotBoss' in obj.__class__.__name__:
                        self.boss = obj
                        break
        
        # Check if there are any opponents (only for laser drones)
        # Heal and explosive drones don't need opponents
        if not hasattr(self, 'droneType'):
            self.droneType = CraneLeagueGlobals.DroneType.LASER  # Default
        
        if self.droneType == CraneLeagueGlobals.DroneType.LASER:
            if not self.hasOpponents():
                # No opponents, vanish immediately with poof
                def vanishNoOpponents(task):
                    self.vanishWithPoof()
                    return Task.done
                taskMgr.doMethodLater(0.1, vanishNoOpponents, self.uniqueName('vanishNoOpponents'))
                return
        
        # Make sure the drone is visible and in the right state
        # The parent announceGenerate might have put us in 'Off' state which hides us
        # Use a small delay to ensure parent setup is complete
        def setupDrone(task):
            if not self.isEmpty():
                # Create poof effect when appearing (like cannons/chairs in Lawbot CJ)
                self.dustCloud = DustCloud.DustCloud(render, wantSound=1)
                self.dustCloud.setBillboardPointEye()
                owner = base.cr.doId2do.get(self.ownerId)
                if owner:
                    ownerPos = owner.getPos(render)
                    poofPos = Point3(ownerPos.getX(), ownerPos.getY(), ownerPos.getZ() + 15)
                    self.dustCloud.setPos(render, poofPos)
                    self.dustCloud.setScale(0.5)
                    self.dustCloud.play()
                
                self.show()
                self.reparentTo(render)
                # Request 'Stunned' state to show the collapsed animation
                self.request('Stunned')
                
                # Set up collision for safe detection (can be destroyed by safes)
                self.setupSafeCollision()
                
                # Set up as disabled goon (collapsed animation)
                self.loop('collapse')
                
                # Attach propellers to head
                self.attachPropellers()
                
                # Start propeller rotation
                self.startPropellerSpin()
                
                # Update hat color based on drone type (will be set via setDroneType)
                # We'll update it when setDroneType is called
                
                # Wait for drone type and target to be set before starting behavior
                # Use a small delay to ensure data is received
                def startBehavior(task):
                    if self.droneType == CraneLeagueGlobals.DroneType.LASER:
                        if self.targetId:
                            self.startFlying()
                        else:
                            # If still no target after delay, vanish
                            self.vanishWithPoof()
                    elif self.droneType == CraneLeagueGlobals.DroneType.HEAL:
                        # Heal drone doesn't need target, just hover above owner
                        self.startHovering()
                    elif self.droneType == CraneLeagueGlobals.DroneType.EXPLOSIVE:
                        # Explosive drone flies to CFO (targetId should be CFO's doId)
                        if self.targetId or self.boss:
                            self.startFlyingToCFO()
                        else:
                            self.vanishWithPoof()
                    return Task.done
                taskMgr.doMethodLater(0.2, startBehavior, self.uniqueName('startBehavior'))
            return Task.done
        
        taskMgr.doMethodLater(0.1, setupDrone, self.uniqueName('setupDrone'))
        
    def setupSafeCollision(self):
        """Set up collision detection so safes can destroy this drone."""
        # Add collision sphere for safe detection
        # Name it 'goon' so the safe's collision event pattern '-goon' matches
        cn = CollisionNode('goon')
        cs = CollisionSphere(0, 0, 4, 4)  # Same as regular goons
        cn.addSolid(cs)
        # Use PieBitmask so safes (which have PieBitmask in FromCollideMask) can collide with us
        cn.setIntoCollideMask(ToontownGlobals.PieBitmask | ToontownGlobals.CashbotBossObjectBitmask)
        self.droneCollisionNodePath = self.attachNewNode(cn)
        
        # Set the doId tag on both the collision node path and the drone itself
        self.droneCollisionNodePath.setTag('doId', str(self.doId))
        self.setTag('doId', str(self.doId))
    def vanishWithPoof(self, task=None):
        """Vanish the drone with a poof effect (called from AI or locally)."""
        if self.isEmpty():
            if task:
                return Task.done
            return
        
        # Create poof effect using DustCloud (same as when appearing)
        self.poof()
        
        # Disable the drone after a short delay to let the poof play
        def disableAfterPoof():
            self.disable()
        taskMgr.doMethodLater(0.3, lambda task: disableAfterPoof(), self.uniqueName('vanishPoof'))
        
        if task:
            return Task.done

    def poof(self):
        dronePos = self.getPos(render)
        poofPos = Point3(dronePos.getX(), dronePos.getY(), dronePos.getZ())
        # Create a new DustCloud for the vanish poof (same approach as spawn)
        vanishDustCloud = DustCloud.DustCloud(render, wantSound=1)
        vanishDustCloud.setBillboardPointEye()
        vanishDustCloud.setPos(render, poofPos)
        vanishDustCloud.setScale(0.5)
        vanishDustCloud.play()
        self.hide()
    
    def b_destroyGoon(self):
        """Called by safes when they hit this drone."""
        # Send update to AI to destroy this drone
        self.sendUpdate('destroyDrone', [])
        # Don't call destroyDrone() locally - wait for the AI broadcast
    
    def doLocalStun(self):
        """Called by safes when SAFES_STUN_GOONS is enabled."""
        # For drones, stunning just destroys them
        self.b_destroyGoon()
    
    def destroyDrone(self):
        """Destroy the drone visually (called from AI broadcast)."""
        if not self.isEmpty():
            # Use the same crush effect as regular goons
            self.playCrushMovie(None, None)
        # Don't call disable() here - playCrushMovie handles cleanup via dead()
        
    def attachPropellers(self):
        """Attach rotating propellers to the goon's head."""
        if self.propeller is None:
            self.propeller = BattleProps.globalPropPool.getProp('propeller')
            head = self.find('**/joint35')
            if head.isEmpty():
                head = self.find('**/joint40')
            if not head.isEmpty():
                self.propeller.reparentTo(head)
                self.propeller.setPos(0, 0, 0)
                self.propeller.setHpr(0, 0, 0)
                
                # Find the propeller blades (not the handle)
                # The handle stays fixed, only blades rotate
                self.propellerBlades = []
                index = 1
                blade = self.propeller.find('**/propeller%d' % index)
                while not blade.isEmpty():
                    self.propellerBlades.append(blade)
                    index += 1
                    blade = self.propeller.find('**/propeller%d' % index)
                
                # If no numbered propellers found, try finding any child that might be blades
                if not self.propellerBlades:
                    # Try common blade names
                    for name in ['blade', 'prop', 'rotor']:
                        blade = self.propeller.find('**/%s' % name)
                        if not blade.isEmpty():
                            self.propellerBlades.append(blade)
                
    def startPropellerSpin(self):
        """Start rotating the propellers."""
        if self.propeller and not self.propeller.isEmpty():
            self.propellerSpinTask = taskMgr.add(self.spinPropeller, self.uniqueName('spinPropeller'))
            
    def spinPropeller(self, task):
        """Rotate only the propeller blades, not the handle."""
        if self.propeller and not self.propeller.isEmpty():
            # Rotate each blade
            if hasattr(self, 'propellerBlades') and self.propellerBlades:
                for blade in self.propellerBlades:
                    blade.setH(blade.getH() + 360 * globalClock.getDt())
            else:
                # Fallback: if we can't find blades, try rotating children
                # but exclude the handle/base
                for child in self.propeller.getChildren():
                    if 'handle' not in child.getName().lower() and 'base' not in child.getName().lower():
                        child.setH(child.getH() + 360 * globalClock.getDt())
        return Task.cont
        
    def startFlying(self):
        """Start the flying behavior sequence."""
        # Get owner position
        owner = base.cr.doId2do.get(self.ownerId)
        if not owner:
            return
        
        ownerPos = owner.getPos(render)
        startPos = Point3(ownerPos.getX(), ownerPos.getY(), ownerPos.getZ() + 15)  # 15 units above owner
        self.setPos(startPos)
        
        # Use the target that was determined at spawn (from AI)
        if not self.targetId:
            # No target set, vanish
            self.vanishWithPoof()
            return
        
        target = base.cr.doId2do.get(self.targetId)
        if not target:
            # Target no longer exists, vanish
            self.vanishWithPoof()
            return
        
        # Ensure target is not the owner (safety check)
        if target.doId == self.ownerId:
            self.vanishWithPoof()
            return
        
        targetPos = target.getPos(render)
        # Position above and in front of target (10 units above, 5 units away horizontally)
        # Calculate direction from target to owner (opposite direction) to place drone in front
        direction = startPos - targetPos
        direction.setZ(0)  # Horizontal only
        if direction.length() > 0:
            direction.normalize()
        else:
            # If target and owner are at same position, use a default direction
            direction = Vec3(0, 1, 0)  # Default to forward
        
        # Calculate final position - in front of target (opposite direction from owner)
        finalPos = Point3(
            targetPos.getX() + direction.getX() * 5,
            targetPos.getY() + direction.getY() * 5,
            targetPos.getZ() + 10
        )
        
        # Avoid going through the CFO boss - check if path would intersect boss
        # Make sure we have a valid boss reference
        if not self.boss:
            # Try to find boss again
            if hasattr(base, 'boss'):
                self.boss = base.boss
            elif hasattr(base, 'cr') and hasattr(base.cr, 'doId2do'):
                for obj in base.cr.doId2do.values():
                    if hasattr(obj, '__class__') and 'CashbotBoss' in obj.__class__.__name__:
                        self.boss = obj
                        break
        
        if self.boss and hasattr(self.boss, 'getPos'):
            try:
                bossPos = self.boss.getPos(render)
                bossRadius = 10.0  # Larger radius to ensure we avoid the boss
                
                # Check if the direct path would go through the boss
                pathVec = finalPos - startPos
                pathLength = pathVec.length()
                if pathLength > 0:
                    pathDir = pathVec / pathLength
                    
                    # Check multiple points along the path to see if any are too close to boss
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
                    
                    # If any point along the path is too close to boss, create waypoint
                    if minDist < bossRadius + 8.0:  # 8 unit buffer
                        # Calculate perpendicular direction to avoid boss
                        perp = Vec3(-pathDir.getY(), pathDir.getX(), 0)
                        if perp.length() < 0.1:
                            # If path is vertical, use a different perpendicular
                            perp = Vec3(1, 0, 0)
                        perp.normalize()
                        
                        # Choose the side that's further from the boss
                        if perp.dot(bossPos - closestPointOnPath) > 0:
                            perp = -perp
                        
                        # Create waypoint far enough from boss
                        avoidDistance = bossRadius + 8.0 - minDist
                        if avoidDistance < 0:
                            avoidDistance = 8.0  # Minimum buffer
                        
                        # Create waypoint at the midpoint of the path, offset from boss
                        waypointT = 0.5  # Middle of path
                        waypointBase = startPos + pathDir * (pathLength * waypointT)
                        waypoint = waypointBase + perp * (avoidDistance + 5.0)  # Extra safety margin
                        waypoint.setZ((startPos.getZ() + finalPos.getZ()) / 2)
                        
                        # Use a smooth curve through the waypoint instead of direct lerp
                        # Store waypoint for use in the lerp
                        self.avoidWaypoint = waypoint
            except:
                # If boss position can't be determined, just use direct path
                pass
        
        # Sequence:
        # 1. Hover over owner for 1 second
        # 2. Lerp to final position over 2 seconds
        # 3. Lock orientation to target for 1 second
        # 4. Fire 3 lasers over 1 second
        # 5. Pause 2 seconds
        # 6. Vanish
        
        # Create a task to continuously look at target (runs during lerp, lock, and shooting)
        def lookAtTargetTask(task):
            if not self.isEmpty():
                # Get current target position (target might be moving)
                currentTarget = base.cr.doId2do.get(self.targetId)
                if currentTarget:
                    currentTargetPos = currentTarget.getPos(render)
                    self.lookAt(currentTargetPos)
                    self.setP(0)  # Keep level
            return Task.cont
        
        # Create smooth path - use waypoint if boss avoidance is needed
        if hasattr(self, 'avoidWaypoint') and self.avoidWaypoint:
            # Smooth curve through waypoint using two lerps
            waypoint = self.avoidWaypoint
            delattr(self, 'avoidWaypoint')  # Clean up
            
            # Create a smooth path: start -> waypoint -> final
            # Split the 2 seconds: 1s to waypoint, 1s to final
            lerpPath = Sequence(
                LerpPosInterval(self, duration=1.0, pos=waypoint, startPos=startPos),
                LerpPosInterval(self, duration=1.0, pos=finalPos, startPos=waypoint)
            )
        else:
            # Direct path
            lerpPath = LerpPosInterval(self, duration=2.0, pos=finalPos, startPos=startPos)
        
        self.behaviorSequence = Sequence(
            # Hover over owner for 1 second
            Wait(1.0),
            
            # Lerp to final position over 2 seconds while looking at target
            Func(taskMgr.add, lookAtTargetTask, self.uniqueName('lookAtTarget')),
            lerpPath,
            
            # Lock orientation to target for 1 second (still adjusting continuously)
            Wait(1.0),
            
            # Fire 3 lasers over 1 second (1/3 second each) - still adjusting to face target
            Func(self.shootLasers, None),
            Wait(1.0),  # Wait for all lasers to finish
            
            # Stop adjusting HPR after all lasers are done
            Func(taskMgr.remove, self.uniqueName('lookAtTarget')),
            
            # Pause 2 seconds
            Wait(2.0),
            
            # Vanish
            Func(self.vanishWithPoof)
        )
        self.behaviorSequence.start()
        
    def hasOpponents(self):
        """Check if there are any opponents."""
        if not self.boss:
            return False
        # Check if boss has game attribute (crane game) or involvedToons (standalone boss)
        if hasattr(self.boss, 'game') and self.boss.game:
            # Crane game - use game's participant list
            involvedToons = self.boss.game.getParticipantIdsNotSpectating()
        elif hasattr(self.boss, 'involvedToons'):
            # Standalone boss - use boss's involvedToons
            involvedToons = self.boss.involvedToons
        else:
            return False
        opponents = [tid for tid in involvedToons if tid != self.ownerId]
        return len(opponents) > 0
    
    def findNearestOpponent(self):
        """Find the nearest opponent toon."""
        if not self.boss:
            return None
            
        nearest = None
        nearestDist = float('inf')
        currentPos = self.getPos()
        
        # Get all toons in the battle - check if boss has game attribute (crane game) or involvedToons (standalone boss)
        if hasattr(self.boss, 'game') and self.boss.game:
            # Crane game - use game's participant list
            involvedToons = self.boss.game.getParticipantIdsNotSpectating()
        elif hasattr(self.boss, 'involvedToons'):
            # Standalone boss - use boss's involvedToons
            involvedToons = self.boss.involvedToons
        else:
            return None
        
        for toonId in involvedToons:
            if toonId == self.ownerId:
                continue  # Skip owner
            toon = base.cr.doId2do.get(toonId)
            if toon and hasattr(toon, 'getPos'):
                dist = (toon.getPos(render) - currentPos).length()
                if dist < nearestDist:
                    nearestDist = dist
                    nearest = toon
                    
        return nearest
        
    def shootLasers(self, task):
        """Shoot 3 lasers at the target over 1 second (1/3 second each)."""
        # Clear hit tracking for new volley (prevents multiple lasers from bypassing iframes)
        self.hitToons.clear()
        
        # Use the target that was determined at spawn (from AI)
        if not self.targetId:
            # No target found, vanish with poof
            self.vanishWithPoof()
            return Task.done if task else None
        
        target = base.cr.doId2do.get(self.targetId)
        if not target:
            # Target no longer exists, vanish
            self.vanishWithPoof()
            return Task.done if task else None
        
        # Ensure target is not the owner (safety check)
        if target.doId == self.ownerId:
            self.vanishWithPoof()
            return Task.done if task else None
            
        # Shoot 3 lasers with 0.5 seconds between each
        for i in range(3):
            delay = i * 0.5  # 0.0, 0.5, 1.0 seconds
            # Create a closure to capture target
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
            # Fallback to head position if eye not found
            eyePos = self.head.getPos(render)
            eyePos.setZ(eyePos.getZ() + 0.5)  # Offset slightly up
        else:
            # Last resort: use drone position with offset
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
        
        # Calculate the distance and direction
        distance = (targetPos - startPos).length()
        
        if distance < 0.01:
            # Too close, skip laser
            return
        
        direction = (targetPos - startPos) / distance
        
        # Create a container node to hold the laser (allows dynamic updates)
        laserNP = render.attachNewNode('laser')
        laserNP.setTransparency(TransparencyAttrib.MAlpha)
        laserNP.setDepthWrite(False)
        
        # Store reference to current laser node for replacement
        currentLaserNode = None
        
        # Initialize with zero-length line at start position
        initialLines = LineSegs('laser')
        initialLines.setColor(1, 0, 0, 1)
        initialLines.setThickness(3.0)
        initialLines.moveTo(startPos.getX(), startPos.getY(), startPos.getZ())
        initialLines.drawTo(startPos.getX(), startPos.getY(), startPos.getZ())  # Zero length initially
        currentLaserNode = laserNP.attachNewNode(initialLines.create())
        
        # Animate the laser traveling from eye to target over 0.3 seconds
        def updateLaser(t):
            nonlocal currentLaserNode
            
            # Calculate current position along the path (0.0 to 1.0)
            currentDist = t * distance
            currentEndPos = startPos + direction * currentDist
            
            # Remove old laser node if it exists
            if currentLaserNode:
                currentLaserNode.removeNode()
            
            # Create new line geometry with updated end position
            newLines = LineSegs('laser')
            newLines.setColor(1, 0, 0, 1)
            newLines.setThickness(3.0)
            newLines.moveTo(startPos.getX(), startPos.getY(), startPos.getZ())
            newLines.drawTo(currentEndPos.getX(), currentEndPos.getY(), currentEndPos.getZ())
            
            # Attach the new laser node
            currentLaserNode = laserNP.attachNewNode(newLines.create())
            
            return t
        
        # Create animation sequence
        travelDuration = 0.3  # 0.3 seconds to travel
        laserInterval = Sequence(
            # Travel from eye to target over 0.3 seconds
            LerpFunctionInterval(updateLaser, duration=travelDuration, fromData=0.0, toData=1.0),
            # After travel completes, check for collisions and apply damage
            Func(lambda: self.checkLaserCollisions(startPos, targetPos)),
            # Fade out over 0.7 seconds (1 second total - 0.3 travel)
            LerpColorScaleInterval(laserNP, duration=0.7, colorScale=(1, 0, 0, 0), startColorScale=(1, 0, 0, 1)),
            Func(laserNP.removeNode)
        )
        laserInterval.start()
    
    def checkLaserCollisions(self, startPos, targetPos):
        """Check if the laser beam hits any toons and apply damage."""
        # Get all toons in the game
        toons = []
        
        # Try to get participants from the game or boss
        if self.boss:
            if hasattr(self.boss, 'game') and self.boss.game:
                # Get participants from the game
                if hasattr(self.boss.game, 'getParticipants'):
                    toons = self.boss.game.getParticipants()
                elif hasattr(self.boss.game, 'getParticipantIdsNotSpectating'):
                    participantIds = self.boss.game.getParticipantIdsNotSpectating()
                    toons = [base.cr.doId2do.get(avId) for avId in participantIds if base.cr.doId2do.get(avId)]
            elif hasattr(self.boss, 'getInvolvedToonsNotSpectating'):
                # Get involved toons from boss
                involvedIds = self.boss.getInvolvedToonsNotSpectating()
                toons = [base.cr.doId2do.get(avId) for avId in involvedIds if base.cr.doId2do.get(avId)]
        
        # Fallback: check all toons in doId2do
        if not toons:
            for obj in base.cr.doId2do.values():
                if hasattr(obj, 'hp') and hasattr(obj, 'getPos'):
                    # Check if it's a toon (has hp and getPos)
                    try:
                        obj.getPos(render)  # Make sure it's a valid node path
                        toons.append(obj)
                    except:
                        pass
        
        # Check each toon to see if the laser line passes close to them
        hitRadius = 2.0  # Radius around toon to consider a hit
        
        for toon in toons:
            if not toon or toon.isEmpty():
                continue
            
            # Don't hit the owner
            if toon.doId == self.ownerId:
                continue
            
            # Skip if already hit by this drone's lasers (prevents multiple lasers from bypassing iframes)
            if toon.doId in self.hitToons:
                continue
            
            try:
                # Get toon's position
                toonPos = toon.getPos(render)
                
                # Calculate distance from toon to the laser line segment
                # Using point-to-line-segment distance formula
                lineVec = targetPos - startPos
                toonVec = toonPos - startPos
                
                # Project toon position onto the line
                lineLength = lineVec.length()
                if lineLength < 0.01:
                    continue
                
                lineDir = lineVec / lineLength
                projectionLength = toonVec.dot(lineDir)
                
                # Clamp projection to line segment
                projectionLength = max(0.0, min(lineLength, projectionLength))
                
                # Find closest point on line segment
                closestPoint = startPos + lineDir * projectionLength
                
                # Distance from toon to closest point on line
                distToLine = (toonPos - closestPoint).length()
                
                # Check if within hit radius
                if distToLine < hitRadius:
                    self.applyLaserDamage(toon)
            except:
                # Skip this toon if there's an error
                continue
    
    def applyLaserDamage(self, toon):
        """Apply damage to a toon hit by the laser - send to AI like goons do."""
        if not toon or toon.isEmpty():
            return
        
        # CRITICAL: Check and mark hit atomically FIRST to prevent race conditions
        # Multiple lasers can call this simultaneously, so we need to ensure only one proceeds
        # This must be checked BEFORE iframe checks to prevent multiple lasers from hitting
        if toon.doId in self.hitToons:
            return  # Already checked by this drone in this volley, skip
        
        # Mark this toon as checked IMMEDIATELY (atomic operation)
        # Once marked, they stay marked for the entire volley (until hitToons.clear())
        # This prevents ANY laser in this volley from hitting them, regardless of iframes
        self.hitToons.add(toon.doId)
        
        # NOW check iframes - if toon has iframes, skip damage entirely
        # We DON'T remove from hitToons, so subsequent lasers in this volley also skip
        if toon.isStunned:
            return  # Toon has iframes, skip damage (but keep in hitToons)
        
        if toon.hp <= 0:
            return  # Toon is dead, skip damage (but keep in hitToons)
        
        # Grant iframes IMMEDIATELY (before sending damage request)
        # stunToon() sets isStunned=1 synchronously via Func(setStunned, 1)
        toon.stunToon()
        
        # Use the same system as goons - send a message to AI to apply damage
        # Goons send 'requestBattle', we'll send 'requestLaserHit'
        self.sendUpdate('requestLaserHit', [toon.doId])
        
        # Knock toon off crane if they're on one - same as goons do
        if toon == base.localAvatar:
            messenger.send('exitCrane')
        
    def startHovering(self):
        """Start hovering behavior for heal drone - just hovers above owner."""
        owner = base.cr.doId2do.get(self.ownerId)
        if not owner:
            self.vanishWithPoof()
            return
        
        ownerPos = owner.getPos(render)
        hoverPos = Point3(ownerPos.getX(), ownerPos.getY(), ownerPos.getZ() + 15)
        self.setPos(hoverPos)
        # Heal drone just hovers - the AI will trigger the heal after 2 seconds
    
    def startFlyingToCFO(self):
        """Start flying to CFO for explosive drone."""
        # Find boss if not set - try multiple methods
        if not self.boss:
            # Method 1: Get from minigame
            if hasattr(base, 'curMinigame') and base.curMinigame:
                if hasattr(base.curMinigame, 'boss') and base.curMinigame.boss:
                    self.boss = base.curMinigame.boss
            
            # Method 2: Try base.boss
            if not self.boss and hasattr(base, 'boss'):
                self.boss = base.boss
            
            # Method 3: Search in doId2do
            if not self.boss and hasattr(base, 'cr') and hasattr(base.cr, 'doId2do'):
                for obj in base.cr.doId2do.values():
                    if hasattr(obj, '__class__') and 'CashbotBoss' in obj.__class__.__name__:
                        self.boss = obj
                        break
        
        if not self.boss:
            self.notify.warning('Explosive drone could not find CFO boss')
            self.vanishWithPoof()
            return
        
        owner = base.cr.doId2do.get(self.ownerId)
        if not owner:
            self.vanishWithPoof()
            return
        
        ownerPos = owner.getPos(render)
        startPos = Point3(ownerPos.getX(), ownerPos.getY(), ownerPos.getZ() + 15)
        self.setPos(startPos)
        
        # Get CFO position
        bossPos = self.boss.getPos(render)
        targetPos = Point3(bossPos.getX(), bossPos.getY(), bossPos.getZ() + 10)  # 10 units above CFO
        
        # Lerp to CFO position over 3 seconds
        lerpDuration = 3.0
        self.behaviorSequence = Sequence(
            LerpPosInterval(self, lerpDuration, targetPos, startPos=startPos, blendType='easeInOut'),
            Func(self.onReachedCFO)
        )
        self.behaviorSequence.start()
    
    def onReachedCFO(self):
        """Called when explosive drone reaches CFO."""
        # The AI will trigger the explosion, we just wait for the visual
        pass
    
    def performHealVisualEffect(self):
        """Handle heal request from AI - show heal effect."""
        owner = base.cr.doId2do.get(self.ownerId)
        if owner:
            # Show heal effect (green particles or similar)
            # For now, just play a sound if available
            if hasattr(base, 'playSfx'):
                # Could add heal sound here
                pass
            # Vanish after showing effect
            taskMgr.doMethodLater(1.0, self.vanishWithPoof, self.uniqueName('vanishAfterHeal'))
    
    def performExplodeVisualEffect(self):
        """Handle explosion request from AI - show explosion effect."""
        # Create explosion effect
        if hasattr(self, 'dustCloud'):
            explosionPos = self.getPos(render)
            explosion = DustCloud.DustCloud(render, wantSound=1)
            explosion.setBillboardPointEye()
            explosion.setPos(render, explosionPos)
            explosion.setScale(2.0)  # Larger scale for explosion
            explosion.play()
        
        # Vanish immediately after explosion
        self.vanishWithPoof()

    def performStunVisualEffect(self):
        """Handle stun request from AI - show stun effect."""
        # Lerp to CFO position over 3 seconds
        lerpDuration = 1.75
        startPos = self.getPos()
        targetPos = (self.getX(), self.getY(), self.getZ() - 16)
        sfx = base.loader.loadSfx('phase_3.5/audio/sfx/ENC_cogfall_apart.ogg')
        self.behaviorSequence = Sequence(
                Wait(lerpDuration * .2),
                LerpScaleInterval(self, lerpDuration * .7, 3),
                LerpPosInterval(self, lerpDuration * .1, targetPos, startPos=startPos, blendType='easeIn'),
                Parallel(
                Func(base.playSfx, sfx),
                Func(self.poof)
            )
        )
        self.behaviorSequence.start()

    def performVisualEffect(self, droneType: int):
        if droneType == CraneLeagueGlobals.DroneType.STUN.value:
            self.performStunVisualEffect()
        elif droneType == CraneLeagueGlobals.DroneType.HEAL.value:
            self.performHealVisualEffect()
        elif droneType == CraneLeagueGlobals.DroneType.EXPLOSIVE.value:
            self.performExplodeVisualEffect()
    
    def disable(self):
        """Clean up when disabled."""
        if self.propellerSpinTask:
            taskMgr.remove(self.propellerSpinTask)
            self.propellerSpinTask = None
        if self.flyTask:
            taskMgr.remove(self.flyTask)
            self.flyTask = None
        if hasattr(self, 'behaviorSequence') and self.behaviorSequence:
            self.behaviorSequence.pause()
            self.behaviorSequence = None
        taskMgr.remove(self.uniqueName('vanishAfterHeal'))
        taskMgr.remove(self.uniqueName('lookAtTarget'))
        if hasattr(self, 'dustCloud') and self.dustCloud:
            self.dustCloud.destroy()
            self.dustCloud = None
        if self.propeller:
            self.propeller.cleanup()
            self.propeller.removeNode()
            self.propeller = None
        if hasattr(self, 'droneCollisionNodePath'):
            self.droneCollisionNodePath.removeNode()
        taskMgr.remove(self.uniqueName('shootLasers'))
        # Remove all shootLaser tasks
        for i in range(3):
            taskMgr.remove(self.uniqueName('shootLaser-%d' % i))
        taskMgr.remove(self.uniqueName('vanishAfterAttack'))
        taskMgr.remove(self.uniqueName('vanishNoOpponents'))
        
        # Clean up DistributedGoon tasks and animations before calling disable
        # to avoid FSM state issues
        taskMgr.remove(self.taskName('resumeWalk'))
        taskMgr.remove(self.taskName('recoveryDone'))
        if hasattr(self, 'animTrack') and self.animTrack:
            self.animTrack.finish()
            self.animTrack = None
        if hasattr(self, 'walkTrack') and self.walkTrack:
            self.walkTrack.pause()
            self.walkTrack = None
        
        # Manually handle the FSM state to avoid show() being called on empty node
        # Instead of calling DistributedGoon.disable which calls request('Off'),
        # we'll manually clean up what we need
        if hasattr(self, 'disableBodyCollisions'):
            self.disableBodyCollisions()
        if hasattr(self, 'disableClipPlanes'):
            self.disableClipPlanes()
        
        # Only call parent disable if node is not empty and properly initialized
        if not self.isEmpty():
            try:
                DistributedCrushableEntity.DistributedCrushableEntity.disable(self)
            except:
                pass
        
    def delete(self):
        """Clean up when deleted."""
        self.disable()
        DistributedGoon.DistributedGoon.delete(self)
        DistributedCrushableEntity.DistributedCrushableEntity.delete(self)


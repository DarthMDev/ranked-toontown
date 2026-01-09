"""
Ghosty Drone - Sabotages opponent's nearest 2 safes by making them completely transparent (only visible to targeted toon).
Safes remain grabbable despite being transparent.
"""

from panda3d.core import *
from panda3d.physics import *
from direct.interval.IntervalGlobal import *
from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from toontown.coghq import CraneLeagueGlobals
from toontown.coghq.DistributedGoonDroneBase import DistributedGoonDroneBase
from toontown.effects import DustCloud
import math


class DistributedGoonDroneGhosty(DistributedGoonDroneBase):
    """
    Ghosty drone that:
    1. Spawns and flies to opponent's side
    2. Finds the 2 nearest safes
    3. Makes them completely transparent (only visible to targeted toon)
    4. Safes remain grabbable (collisions not disabled)
    5. Lasts 6 seconds or until drone is destroyed
    6. Safes return to normal after duration or drone destruction
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGoonDroneGhosty')
    
    def __init__(self, cr):
        DistributedGoonDroneBase.__init__(self, cr)
        self.ghostDuration = 6.0  # 6 seconds
        self.ghostedSafes = []  # Track which safes are ghosted
        self.ghostStartTime = None
        self.pulseTask = None
        self.ghostParticles = None
        self.targetSafes = []
        self.opponentIds = []  # Store opponent IDs to check if local toon should see transparency
    
    def getDroneType(self):
        return CraneLeagueGlobals.DroneType.GHOSTY
    
    def needsOpponents(self):
        """Ghosty drones need opponents to target their safes."""
        return True
    
    def startBehavior(self):
        """Start the ghosty drone behavior."""
        self.findAndFlyToSafes()
    
    def findAndFlyToSafes(self):
        """Find the 2 nearest safes and fly to position between them."""
        # Get opponent IDs
        opponentIds = []
        if self.boss:
            if hasattr(self.boss, 'game') and self.boss.game:
                if hasattr(self.boss.game, 'getParticipantIdsNotSpectating'):
                    participantIds = self.boss.game.getParticipantIdsNotSpectating()
                    opponentIds = [tid for tid in participantIds if tid != self.ownerId]
            elif hasattr(self.boss, 'involvedToons'):
                opponentIds = [tid for tid in self.boss.involvedToons if tid != self.ownerId]
        
        # Store opponent IDs for later use in applyGhostEffect
        self.opponentIds = opponentIds
        
        if not opponentIds:
            self.notify.warning('No opponents found for ghosty drone')
            # Vanish if no opponents
            taskMgr.doMethodLater(0.5, self.vanishWithPoof, self.uniqueName('vanishNoOpponents'))
            return
        
        # Get all safes in the scene
        # Try to get safes from boss/game first (client-side)
        allSafes = []
        if self.boss and hasattr(self.boss, 'game') and self.boss.game:
            # Client-side game object has safes as a dict
            if hasattr(self.boss.game, 'safes'):
                # Client-side safes is a dict {doId: safeObject}
                if isinstance(self.boss.game.safes, dict):
                    allSafes = [safe for safe in self.boss.game.safes.values() if safe]
                elif isinstance(self.boss.game.safes, list):
                    allSafes = [safe for safe in self.boss.game.safes if safe]
        
        # Fallback: search all objects in doId2do
        if not allSafes:
            for obj in base.cr.doId2do.values():
                # Check if it's a safe by class name
                if hasattr(obj, '__class__'):
                    className = obj.__class__.__name__
                    if 'Safe' in className and 'AI' not in className:
                        allSafes.append(obj)
        
        self.notify.debug(f'Found {len(allSafes)} total safes in scene, {len(opponentIds)} opponents')
        
        # Filter safes - get all valid safes (not already ghosted, not the helmet safe)
        validSafes = []
        skippedGhosted = 0
        skippedHelmet = 0
        skippedNotOpponent = 0
        skippedNoPosition = 0
        
        for obj in allSafes:
            if not obj or obj.isEmpty():
                continue
                
            # Skip if already ghosted
            if hasattr(obj, '_isGhosted') and obj._isGhosted:
                skippedGhosted += 1
                continue
            
            # Skip the helmet safe (index 0) - this is the CFO's safety helmet that can't be picked up
            if hasattr(obj, 'index') and obj.index == 0:
                skippedHelmet += 1
                continue
            
            # Check if safe belongs to an opponent or is ungrabbed
            # Note: Grabbed safes (state == 'Grabbed') should still be included if they belong to opponents
            safeAvId = 0
            if hasattr(obj, 'avId'):
                safeAvId = obj.avId
            elif hasattr(obj, 'getAvId'):
                safeAvId = obj.getAvId()
            
            # Include safes that belong to opponents (regardless of state - Grabbed, Dropped, etc.)
            # Also include ALL ungrabbed safes (avId == 0) regardless of distance
            shouldInclude = False
            if safeAvId in opponentIds:
                # Safe belongs to an opponent - include it (even if grabbed)
                shouldInclude = True
            elif safeAvId == 0:
                # Ungrabbed safe - include all ungrabbed safes (no distance limit)
                shouldInclude = True
            
            if not shouldInclude:
                skippedNotOpponent += 1
                continue
            
            if shouldInclude:
                try:
                    # Make sure safe has a position
                    safePos = obj.getPos(render)
                    validSafes.append(obj)
                except Exception as e:
                    skippedNoPosition += 1
                    self.notify.debug(f'Error getting safe position: {e}')
                    continue
        
        self.notify.debug(f'Safe filtering: {len(validSafes)} valid, {skippedGhosted} already ghosted, {skippedHelmet} helmet, {skippedNotOpponent} not opponent, {skippedNoPosition} no position')
        
        # Sort by distance to nearest opponent (prioritize safes near opponents)
        if validSafes:
            try:
                # Calculate distance to nearest opponent for each safe
                def getDistanceToNearestOpponent(safe):
                    try:
                        safePos = safe.getPos(render)
                        minDist = float('inf')
                        for oppId in opponentIds:
                            opp = base.cr.doId2do.get(oppId)
                            if opp and not opp.isEmpty():
                                try:
                                    oppPos = opp.getPos(render)
                                    dist = (safePos - oppPos).length()
                                    minDist = min(minDist, dist)
                                except:
                                    continue
                        return minDist
                    except:
                        return float('inf')
                
                # Sort by distance to nearest opponent
                validSafes.sort(key=getDistanceToNearestOpponent)
                
                # Get the 2 nearest safes (always try to get 2 if available)
                numToGhost = min(2, len(validSafes))
                targetSafes = validSafes[:numToGhost]
                
                self.notify.debug(f'Found {len(validSafes)} valid safes, targeting {numToGhost} safes')
                if len(validSafes) < 2:
                    self.notify.debug(f'Only {len(validSafes)} valid safes found (need 2 for full effect)')
                
                if numToGhost > 0:
                    # Calculate position between the safes at high height
                    self.targetSafes = targetSafes
                    self.flyToSafesPosition()
                else:
                    self.notify.warning('No safes to ghost')
                    taskMgr.doMethodLater(0.5, self.vanishWithPoof, self.uniqueName('vanishNoSafes'))
            except Exception as e:
                self.notify.warning(f'Error finding safes: {e}')
                import traceback
                traceback.print_exc()
        else:
            self.notify.warning(f'No valid safes found to ghost (checked {len(allSafes)} total safes, {len(opponentIds)} opponents: {opponentIds})')
            taskMgr.doMethodLater(0.5, self.vanishWithPoof, self.uniqueName('vanishNoSafes'))
    
    def flyToSafesPosition(self):
        """Fly to a position between the target safes at high height."""
        if not hasattr(self, 'targetSafes') or not self.targetSafes:
            return
        
        # Get current position (should be above owner)
        owner = base.cr.doId2do.get(self.ownerId)
        if owner:
            ownerPos = owner.getPos(render)
            startPos = Point3(ownerPos.getX(), ownerPos.getY(), ownerPos.getZ() + 15)
        else:
            startPos = self.getPos(render)
        
        # Calculate midpoint between the safes
        safePositions = []
        for safe in self.targetSafes:
            try:
                safePos = safe.getPos(render)
                safePositions.append(safePos)
            except:
                continue
        
        if not safePositions:
            # Can't get positions, just ghost immediately
            self.ghostSafes()
            return
        
        # Calculate midpoint
        if len(safePositions) == 1:
            midpoint = safePositions[0]
        else:
            # Average of all safe positions
            avgX = sum(p.getX() for p in safePositions) / len(safePositions)
            avgY = sum(p.getY() for p in safePositions) / len(safePositions)
            avgZ = sum(p.getZ() for p in safePositions) / len(safePositions)
            midpoint = Point3(avgX, avgY, avgZ)
        
        # Position at high height above the midpoint
        finalPos = Point3(midpoint.getX(), midpoint.getY(), midpoint.getZ() + 20)
        
        # Calculate path avoiding CFO
        lerpPath = self._calculatePathAvoidingBoss(startPos, finalPos)
        
        # After flying, ghost the safes
        self.behaviorSequence = Sequence(
            lerpPath,
            Func(self.ghostSafes)
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
                    
                    # If path is too close to boss, create waypoint (same logic as laser drone)
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
                        
                        # Use smooth curve through waypoint (split 1 second total)
                        return Sequence(
                            LerpPosInterval(self, duration=0.5, pos=waypoint, startPos=startPos, blendType='easeInOut'),
                            LerpPosInterval(self, duration=0.5, pos=finalPos, startPos=waypoint, blendType='easeInOut')
                        )
            except Exception as e:
                self.notify.debug(f'Error calculating boss avoidance: {e}')
        
        # Direct path if no boss or no avoidance needed
        return LerpPosInterval(
            self,
            duration=1.0,
            pos=finalPos,
            startPos=startPos,
            blendType='easeInOut'
        )
    
    def ghostSafes(self):
        """Apply ghost effect to the target safes."""
        if not hasattr(self, 'targetSafes') or not self.targetSafes:
            return
        
        # Create particle effects
        self.createGhostParticles()
        
        # Apply ghost effect to each safe
        for safe in self.targetSafes:
            if safe and not safe.isEmpty():
                self.applyGhostEffect(safe)
        
        self.notify.debug(f'Ghosted {len(self.targetSafes)} safes')
        
        # Start ghost timer
        self.ghostStartTime = globalClock.getFrameTime()
        
        # Start pulse task
        self.pulseTask = taskMgr.add(self.updateGhostPulse, self.uniqueName('ghostPulse'))
        
        # Schedule removal after 6 seconds
        taskMgr.doMethodLater(self.ghostDuration, self.removeGhostEffects, self.uniqueName('removeGhost'))
    
    def createGhostParticles(self):
        """Create particle effects when ghosting safes."""
        try:
            from direct.particles import ParticleEffect, Particles, ForceGroup
            
            self.ghostParticles = ParticleEffect.ParticleEffect('GhostyParticles')
            self.ghostParticles.reparentTo(self)
            
            # Create purple sparkles/aura particles
            sparkles = Particles.Particles('ghostSparkles')
            sparkles.setFactory('PointParticleFactory')
            sparkles.setRenderer('SpriteParticleRenderer')
            sparkles.setEmitter('SphereVolumeEmitter')
            self.ghostParticles.addParticles(sparkles)
            
            # Configure particles
            sparkles.setPoolSize(30)
            sparkles.setBirthRate(0.1)
            sparkles.setLitterSize(3)
            sparkles.setLitterSpread(1)
            sparkles.factory.setLifespanBase(1.5)
            sparkles.factory.setLifespanSpread(0.5)
            sparkles.factory.setMassBase(0.1)
            sparkles.factory.setMassSpread(0.05)
            
            # Renderer - purple sparkles
            sparkles.renderer.setAlphaMode(BaseParticleRenderer.PRALPHAOUT)
            sparkles.renderer.setUserAlpha(1.0)
            sparkles.renderer.setColor(Vec4(0.7, 0.2, 1.0, 1.0))  # Light purple
            sparkles.renderer.setInitialXScale(0.1)
            sparkles.renderer.setFinalXScale(0.05)
            sparkles.renderer.setInitialYScale(0.1)
            sparkles.renderer.setFinalYScale(0.05)
            
            # Emitter - sphere around drone
            sparkles.emitter.setEmissionType(BaseParticleEmitter.ETRADIATE)
            sparkles.emitter.setAmplitude(2.0)
            sparkles.emitter.setAmplitudeSpread(0.5)
            sparkles.emitter.setOffsetForce(Vec3(0.0, 0.0, 0.0))
            sparkles.emitter.setRadius(1.5)
            
            # Start particles
            self.ghostParticles.start(parent=self, renderParent=render)
            
            # Stop particles after 6 seconds
            taskMgr.doMethodLater(self.ghostDuration, self.stopGhostParticles, self.uniqueName('stopGhostParticles'))
        except Exception as e:
            self.notify.warning(f'Error creating ghost particles: {e}')
    
    def stopGhostParticles(self, task=None):
        """Stop the ghost particle effects."""
        if hasattr(self, 'ghostParticles') and self.ghostParticles:
            try:
                self.ghostParticles.softStop()
                self.ghostParticles.cleanup()
            except:
                pass
            self.ghostParticles = None
        if task:
            return Task.done
    
    def applyGhostEffect(self, safe):
        """Apply ghost visual effect - makes safe completely transparent (only visible to targeted toon)."""
        if not safe or safe.isEmpty():
            return
        
        # Get the safe's owner (if any)
        safeAvId = 0
        if hasattr(safe, 'avId'):
            safeAvId = safe.avId
        elif hasattr(safe, 'getAvId'):
            safeAvId = safe.getAvId()
        
        # Check if the local toon should see this safe as transparent
        # Only the targeted toon (opponent) should see their safes as transparent
        localAvatarId = base.localAvatar.doId if hasattr(base, 'localAvatar') and base.localAvatar else None
        
        # If safe belongs to a specific opponent, only that opponent sees it transparent
        # If safe is ungrabbed (avId == 0), all opponents see it transparent
        shouldApplyEffect = False
        if safeAvId == 0:
            # Ungrabbed safe - all opponents see it transparent
            shouldApplyEffect = localAvatarId in self.opponentIds if localAvatarId else False
        elif safeAvId in self.opponentIds:
            # Safe belongs to an opponent - only that specific opponent sees it transparent
            shouldApplyEffect = (localAvatarId == safeAvId) if localAvatarId else False
        
        # Only apply transparency effect if this client is the targeted toon
        if not shouldApplyEffect:
            # Not the targeted toon - don't apply any visual effect
            self.notify.debug(f'Not applying ghost effect to safe {safe.doId} - local toon is not targeted (safeAvId={safeAvId}, localAvatarId={localAvatarId})')
            return
        
        # Store original safe properties
        if not hasattr(safe, '_originalColorScale'):
            safe._originalColorScale = safe.getColorScale()
        
        # Mark as ghosted
        safe._isGhosted = True
        safe._ghostStartTime = globalClock.getFrameTime()
        self.ghostedSafes.append(safe)
        
        # Apply ghost visual: completely transparent (alpha = 0)
        # Keep original color scale RGB values, but set alpha to 0
        originalColor = safe._originalColorScale
        safe.setColorScale(originalColor.getX(), originalColor.getY(), originalColor.getZ(), 0.0)  # Completely transparent
        safe.setTransparency(TransparencyAttrib.MAlpha)
        
        # NOTE: We do NOT disable collisions - safes should still be grabbable!
        # The original code disabled collisions, but we want them to remain grabbable.
        
        self.notify.debug(f'Ghosted safe {safe.doId} - made completely transparent for targeted toon (safeAvId={safeAvId})')
    
    def updateGhostPulse(self, task):
        """Keep ghosted safes transparent (no pulsing needed)."""
        if not self.ghostedSafes:
            return Task.done
        
        localAvatarId = base.localAvatar.doId if hasattr(base, 'localAvatar') and base.localAvatar else None
        
        for safe in self.ghostedSafes:
            if safe and not safe.isEmpty() and hasattr(safe, '_isGhosted') and safe._isGhosted:
                try:
                    # Check if this safe should be transparent for the local toon
                    safeAvId = 0
                    if hasattr(safe, 'avId'):
                        safeAvId = safe.avId
                    elif hasattr(safe, 'getAvId'):
                        safeAvId = safe.getAvId()
                    
                    # Determine if local toon should see this safe as transparent
                    shouldBeTransparent = False
                    if safeAvId == 0:
                        # Ungrabbed safe - all opponents see it transparent
                        shouldBeTransparent = localAvatarId in self.opponentIds if localAvatarId else False
                    elif safeAvId in self.opponentIds:
                        # Safe belongs to an opponent - only that specific opponent sees it transparent
                        shouldBeTransparent = (localAvatarId == safeAvId) if localAvatarId else False
                    
                    if shouldBeTransparent:
                        # Keep completely transparent (alpha = 0)
                        originalColor = safe._originalColorScale if hasattr(safe, '_originalColorScale') else VBase4(1, 1, 1, 1)
                        safe.setColorScale(originalColor.getX(), originalColor.getY(), originalColor.getZ(), 0.0)
                except:
                    continue
        
        return Task.cont
    
    def removeGhostEffects(self, task=None):
        """Remove ghost effects from all safes."""
        localAvatarId = base.localAvatar.doId if hasattr(base, 'localAvatar') and base.localAvatar else None
        
        for safe in self.ghostedSafes:
            if safe and not safe.isEmpty() and hasattr(safe, '_isGhosted'):
                try:
                    # Check if this safe should have been transparent for the local toon
                    safeAvId = 0
                    if hasattr(safe, 'avId'):
                        safeAvId = safe.avId
                    elif hasattr(safe, 'getAvId'):
                        safeAvId = safe.getAvId()
                    
                    # Determine if local toon should have seen this safe as transparent
                    shouldHaveBeenTransparent = False
                    if safeAvId == 0:
                        # Ungrabbed safe - all opponents see it transparent
                        shouldHaveBeenTransparent = localAvatarId in self.opponentIds if localAvatarId else False
                    elif safeAvId in self.opponentIds:
                        # Safe belongs to an opponent - only that specific opponent sees it transparent
                        shouldHaveBeenTransparent = (localAvatarId == safeAvId) if localAvatarId else False
                    
                    # Only restore if we applied the effect (i.e., if we're the targeted toon)
                    if shouldHaveBeenTransparent:
                        # Restore original properties
                        if hasattr(safe, '_originalColorScale'):
                            safe.setColorScale(safe._originalColorScale)
                        else:
                            safe.setColorScale(1.0, 1.0, 1.0, 1.0)
                        
                        safe.clearTransparency()
                    
                    safe._isGhosted = False
                    
                    self.notify.debug(f'Unghosted safe {safe.doId}')
                except:
                    pass
        
        self.ghostedSafes = []
        
        # Stop pulse task
        if self.pulseTask:
            taskMgr.remove(self.pulseTask)
            self.pulseTask = None
        
        # Vanish the drone
        taskMgr.doMethodLater(0.5, self.vanishWithPoof, self.uniqueName('vanishAfterGhost'))
        
        if task:
            return Task.done
    
    def disable(self):
        """Clean up when disabled."""
        # Remove ghost effects when drone is destroyed
        self.removeGhostEffects()
        self.stopGhostParticles()
        taskMgr.remove(self.uniqueName('ghostPulse'))
        taskMgr.remove(self.uniqueName('removeGhost'))
        taskMgr.remove(self.uniqueName('vanishAfterGhost'))
        taskMgr.remove(self.uniqueName('vanishNoOpponents'))
        taskMgr.remove(self.uniqueName('vanishNoSafes'))
        taskMgr.remove(self.uniqueName('stopGhostParticles'))
        DistributedGoonDroneBase.disable(self)
    
    def delete(self):
        """Clean up ghosty-specific resources."""
        self.removeGhostEffects()
        DistributedGoonDroneBase.delete(self)


"""
Custom Physics Collision Handler built from scratch that ensures collision responses
are calculated in world space, independent of the object's orientation (H value).

This handler is completely custom and does NOT inherit from PhysicsCollisionHandler.
It implements all physics integration manually to have full control over collision responses.
"""

from panda3d.core import *
from panda3d.physics import PhysicsObject
from direct.task import Task
from direct.task.TaskManagerGlobal import taskMgr
import math

class OrientationIndependentPhysicsHandler(CollisionHandlerPusher):
    """
    A completely custom physics collision handler built from scratch.
    
    This handler:
    - Does NOT inherit from PhysicsCollisionHandler
    - Implements all physics integration manually
    - Calculates collision responses purely in world space
    - Prevents object orientation from affecting post-collision trajectory
    
    This is particularly important for spherical collision objects where
    orientation should not affect how they bounce off surfaces.
    """
    
    def __init__(self):
        CollisionHandlerPusher.__init__(self)
        
        # Physics properties (similar to PhysicsCollisionHandler but we control them)
        self._almost_stationary_speed = 0.01
        self._static_friction_coef = 0.0
        self._dynamic_friction_coef = 0.0
        
        # Friction application rates (configurable)
        # These control how aggressively friction is applied
        self._frictionRate = 2.0  # Base rate for friction application (lower = less aggressive)
        self._aggressiveFactor = 4.0  # Multiplier for non-contact friction (lower = less aggressive)
        self._contactTimeThreshold = 0.3  # How long to consider object "in contact" after collision (seconds)
        
        # Track colliders and their physics objects
        self._colliderPhysicsObjects = {}
        
        # Track active physics objects for continuous friction
        # Maps physicsObject -> (lastCollisionNormal, lastCollisionTime, isInContact)
        self._activePhysicsObjects = {}
        
        # Task name for continuous friction
        self._frictionTaskName = 'orientationIndependentPhysicsHandler-friction'
        
        # Start the continuous friction task
        self._startFrictionTask()
        
    def setStaticFrictionCoef(self, coef):
        """Set static friction coefficient."""
        self._static_friction_coef = coef
    
    def getStaticFrictionCoef(self):
        """Get static friction coefficient."""
        return self._static_friction_coef
    
    def setDynamicFrictionCoef(self, coef):
        """Set dynamic friction coefficient."""
        self._dynamic_friction_coef = coef
    
    def getDynamicFrictionCoef(self):
        """Get dynamic friction coefficient."""
        return self._dynamic_friction_coef
    
    def setAlmostStationarySpeed(self, speed):
        """Set the speed threshold for considering an object almost stationary."""
        self._almost_stationary_speed = speed
    
    def getAlmostStationarySpeed(self):
        """Get the speed threshold for considering an object almost stationary."""
        return self._almost_stationary_speed
    
    def setFrictionRate(self, rate):
        """Set the base friction application rate. Lower values = less aggressive friction."""
        self._frictionRate = rate
    
    def getFrictionRate(self):
        """Get the base friction application rate."""
        return self._frictionRate
    
    def setAggressiveFactor(self, factor):
        """Set the aggressive factor for non-contact friction. Lower values = less aggressive."""
        self._aggressiveFactor = factor
    
    def getAggressiveFactor(self):
        """Get the aggressive factor for non-contact friction."""
        return self._aggressiveFactor
    
    def setContactTimeThreshold(self, threshold):
        """Set how long (in seconds) to consider an object 'in contact' after collision."""
        self._contactTimeThreshold = threshold
    
    def getContactTimeThreshold(self):
        """Get the contact time threshold."""
        return self._contactTimeThreshold
    
    def addCollider(self, fromNodePath, target):
        """
        Add a collider to this handler.
        We override this to track the physics object associated with each collider.
        """
        CollisionHandlerPusher.addCollider(self, fromNodePath, target)
        
        # Find and store the physics object for this collider
        # Store both the target and physics object for later lookup
        physicsObject = self._findPhysicsObject(fromNodePath, target)
        if physicsObject:
            self._colliderPhysicsObjects[fromNodePath] = physicsObject
            # Add to active physics objects for continuous friction tracking
            # Start tracking immediately so friction applies even before first collision
            if physicsObject not in self._activePhysicsObjects:
                # Initialize with current time so it's immediately eligible for friction
                currentTime = globalClock.getFrameTime()
                self._activePhysicsObjects[physicsObject] = (None, currentTime, False)
        else:
            # Store the target itself so we can look it up later
            self._colliderPhysicsObjects[fromNodePath] = target
    
    def removeCollider(self, fromNodePath):
        """Remove a collider from this handler."""
        CollisionHandlerPusher.removeCollider(self, fromNodePath)
        if fromNodePath in self._colliderPhysicsObjects:
            storedObj = self._colliderPhysicsObjects[fromNodePath]
            # Remove from active physics objects if it's a physics object
            if isinstance(storedObj, PhysicsObject):
                if storedObj in self._activePhysicsObjects:
                    del self._activePhysicsObjects[storedObj]
            elif hasattr(storedObj, 'physicsObject'):
                physicsObj = storedObj.physicsObject
                if physicsObj in self._activePhysicsObjects:
                    del self._activePhysicsObjects[physicsObj]
            del self._colliderPhysicsObjects[fromNodePath]
    
    def _startFrictionTask(self):
        """Start the continuous friction task."""
        # Run at higher priority to ensure it runs after physics updates
        # Physics typically runs at priority 50, so we run at 55 to apply friction after physics
        taskMgr.add(self._applyContinuousFriction, self._frictionTaskName, priority=55)
    
    def _stopFrictionTask(self):
        """Stop the continuous friction task."""
        taskMgr.remove(self._frictionTaskName)
    
    def cleanup(self):
        """Clean up the handler and stop the friction task."""
        self._stopFrictionTask()
        self._activePhysicsObjects.clear()
        self._colliderPhysicsObjects.clear()
    
    def _applyContinuousFriction(self, task):
        """
        Continuous task that applies friction to all active physics objects.
        This runs every frame to ensure objects slow down over time when in contact with surfaces.
        """
        # Check all tracked physics objects, and also check all colliders for objects with velocity
        # This ensures we catch objects that might not be in activePhysicsObjects yet
        allPhysicsObjects = set(self._activePhysicsObjects.keys())
        
        # Also check all colliders for physics objects with velocity
        for fromNodePath, storedObj in list(self._colliderPhysicsObjects.items()):
            physicsObject = None
            if isinstance(storedObj, PhysicsObject):
                physicsObject = storedObj
            elif hasattr(storedObj, 'physicsObject'):
                physicsObject = storedObj.physicsObject
            else:
                # storedObj is the target itself, try to find physics object from it
                physicsObject = self._findPhysicsObject(fromNodePath, storedObj)
            
            if physicsObject and physicsObject not in allPhysicsObjects:
                # Found a physics object that's not being tracked - add it
                currentTime = globalClock.getFrameTime()
                self._activePhysicsObjects[physicsObject] = (None, currentTime, False)
                allPhysicsObjects.add(physicsObject)
        
        if not self._activePhysicsObjects:
            return Task.cont
        
        dt = globalClock.getDt()
        if dt <= 0:
            return Task.cont
        
        # Get current time
        currentTime = globalClock.getFrameTime()
        
        # Use configurable contact time threshold
        contactTimeThreshold = self._contactTimeThreshold
        
        objectsToRemove = []
        
        for physicsObject, (lastNormal, lastCollisionTime, isInContact) in list(self._activePhysicsObjects.items()):
            if not physicsObject:
                objectsToRemove.append(physicsObject)
                continue
            
            currentVel = physicsObject.getVelocity()
            speed = currentVel.length()
            
            # If object is almost stationary, remove it from tracking
            # Use a slightly higher threshold to allow objects to fully stop before removing
            if speed < self._almost_stationary_speed:
                objectsToRemove.append(physicsObject)
                # Stop the object completely
                physicsObject.setVelocity(Vec3(0, 0, 0))
                continue
            
            # Check if object is still in contact with a surface
            # Calculate this BEFORE using it in the condition below
            timeSinceCollision = currentTime - lastCollisionTime
            isCurrentlyInContact = isInContact and (timeSinceCollision < contactTimeThreshold)
            
            # Also remove from tracking if object hasn't been in contact for a while AND has very low velocity
            # This helps goons recover faster when they're no longer sliding
            if not isCurrentlyInContact and speed < self._almost_stationary_speed * 2.0:
                # Object is moving slowly and not in contact - remove from tracking to allow recovery
                objectsToRemove.append(physicsObject)
                continue
            
            # Apply friction - ALWAYS apply friction if object has velocity and friction is set
            # For sliding objects, we want to apply friction even if not "in contact" recently
            if isCurrentlyInContact and lastNormal and lastNormal.length() > 0.1:
                # Object is in contact with a surface - apply friction based on surface normal
                newVel = self._applyContinuousFrictionToVelocity(currentVel, lastNormal, dt)
            else:
                # Object is not in contact - but still apply friction if coefficients are set
                # This ensures objects slow down even when not actively colliding
                if self._dynamic_friction_coef > 0.0 or self._static_friction_coef > 0.0:
                    # Apply general damping based on friction coefficients
                    # Use dynamic friction for general damping, be EXTREMELY aggressive
                    # For sliding on floor, we want significant deceleration
                    # Calculate how much to reduce velocity per second
                    # Use configurable aggressive factor (lower = less aggressive)
                    frictionReductionPerSecond = self._dynamic_friction_coef
                    frictionReductionPerFrame = frictionReductionPerSecond * dt * self._aggressiveFactor
                    # Cap the reduction to prevent too-aggressive damping
                    dampingFactor = 1.0 - min(frictionReductionPerFrame, 0.5)  # Cap at 50% reduction per frame max
                    newVel = currentVel * dampingFactor
                else:
                    # No friction set, just apply very light air resistance
                    dampingFactor = 0.9995
                    newVel = currentVel * dampingFactor
                
                # Update tracking to indicate not in contact, but keep tracking
                self._activePhysicsObjects[physicsObject] = (None, lastCollisionTime, False)
            
            # ALWAYS update velocity - the physics manager might be overriding it, so we need to be persistent
            # Apply velocity change every frame to ensure friction actually works
            # Use a more aggressive approach - directly set velocity every frame
            # IMPORTANT: We must set velocity every frame, even if it seems like it's not working
            # The physics manager integration might be running, but we persist our changes
            physicsObject.setVelocity(newVel)
            
            # Also try to get the velocity back and verify it was set
            # If it wasn't set correctly, we know the physics manager is overriding it
            # (This is just for debugging - we'll remove the check later)
            verifyVel = physicsObject.getVelocity()
            if (verifyVel - newVel).length() > 0.1:
                # Velocity was overridden - this means the physics manager is running after us
                # We need to be even more aggressive or run at a different time
                pass
        
        # Clean up removed objects
        for obj in objectsToRemove:
            if obj in self._activePhysicsObjects:
                del self._activePhysicsObjects[obj]
        
        return Task.cont
    
    def _applyContinuousFrictionToVelocity(self, velocity, surfaceNormal, dt):
        """
        Apply continuous friction to velocity when object is in contact with a surface.
        This reduces the tangential (sliding) component of velocity over time.
        """
        if velocity.length() < self._almost_stationary_speed:
            return Vec3(0, 0, 0)
        
        # Normalize the surface normal
        normal = surfaceNormal
        if normal.length() > 0.1:
            normal.normalize()
        else:
            # No valid normal, just apply general damping
            return velocity * 0.95
        
        # Calculate tangential velocity (component perpendicular to normal)
        velDotNormal = velocity.dot(normal)
        tangential = velocity - normal * velDotNormal
        
        # Determine friction coefficient
        speed = velocity.length()
        frictionCoef = self._dynamic_friction_coef
        if speed < self._almost_stationary_speed:
            frictionCoef = self._static_friction_coef
        
        # Apply friction over time
        # Friction reduces tangential velocity: v_new = v_old * (1 - friction * dt * frictionRate)
        # Use configurable friction rate (lower = less aggressive)
        frictionFactor = 1.0 - (frictionCoef * dt * self._frictionRate)
        frictionFactor = max(0.0, frictionFactor)  # Clamp to prevent negative
        
        # Cap the maximum reduction to prevent too-aggressive friction
        # Don't force minimum reduction - let the friction rate control it
        frictionFactor = max(frictionFactor, 0.7)  # Don't reduce by more than 30% per frame
        
        # Reduce tangential component
        tangential = tangential * frictionFactor
        
        # Also apply some damping to the normal component (bounce decay)
        normalComponent = normal * velDotNormal
        bounceDamping = 0.99  # Slight damping on bounce component
        normalComponent = normalComponent * bounceDamping
        
        # Reconstruct velocity
        newVel = normalComponent + tangential
        
        # If velocity is very small, stop it completely
        if newVel.length() < self._almost_stationary_speed:
            return Vec3(0, 0, 0)
        
        return newVel
    
    def _findPhysicsObject(self, fromNodePath, target):
        """
        Find the PhysicsObject associated with the given node path.
        """
        # Check if target has physicsObject attribute directly
        if hasattr(target, 'physicsObject'):
            return target.physicsObject
        
        # Try to find ActorNode in the target's node hierarchy
        if isinstance(target, NodePath) and not target.isEmpty():
            currentPath = target
            while currentPath and not currentPath.isEmpty():
                node = currentPath.node()
                if isinstance(node, ActorNode):
                    return node.getPhysicsObject()
                currentPath = currentPath.getParent()
        
        # Try to find ActorNode in the fromNodePath's hierarchy
        if isinstance(fromNodePath, NodePath) and not fromNodePath.isEmpty():
            currentPath = fromNodePath
            while currentPath and not currentPath.isEmpty():
                node = currentPath.node()
                if isinstance(node, ActorNode):
                    return node.getPhysicsObject()
                currentPath = currentPath.getParent()
        
        return None
    
    def handleCollision(self, entry):
        """
        Handle a collision entry. This is where we process the collision
        and apply physics forces/velocities in world space.
        """
        if not entry:
            return
        
        # Get the collider node path
        fromNodePath = entry.getFromNodePath()
        if not fromNodePath or fromNodePath.isEmpty():
            return
        
        # Get the physics object or target for this collider
        storedObj = self._colliderPhysicsObjects.get(fromNodePath)
        physicsObject = None
        
        if storedObj:
            # Check if it's a PhysicsObject or a target that has one
            if isinstance(storedObj, PhysicsObject):
                physicsObject = storedObj
            elif hasattr(storedObj, 'physicsObject'):
                physicsObject = storedObj.physicsObject
            else:
                # It's a target, try to find physics object from it
                physicsObject = self._findPhysicsObject(fromNodePath, storedObj)
        
        if not physicsObject:
            # Try to find it from the entry
            target = entry.getFromNodePath()
            physicsObject = self._findPhysicsObject(fromNodePath, target)
            if physicsObject:
                self._colliderPhysicsObjects[fromNodePath] = physicsObject
                # Add to active physics objects for continuous friction tracking
                if physicsObject not in self._activePhysicsObjects:
                    self._activePhysicsObjects[physicsObject] = (None, 0.0, False)
        
        if not physicsObject:
            # No physics object, fall back to basic pusher behavior
            CollisionHandlerPusher.handleCollision(self, entry)
            return
        
        # Get collision information in world space
        collisionNormal = self._getWorldSpaceNormal(entry)
        if not collisionNormal or collisionNormal.length() < 0.1:
            # Fall back to basic pusher behavior
            CollisionHandlerPusher.handleCollision(self, entry)
            return
        
        collisionNormal.normalize()
        
        # Get current velocity (already in world space)
        currentVel = physicsObject.getVelocity()
        
        if currentVel.length() < self._almost_stationary_speed:
            # Object is almost stationary, just push it away
            self._applyPushAway(entry, collisionNormal, physicsObject)
            return
        
        # Calculate collision response in world space
        self._applyWorldSpaceCollisionResponse(entry, collisionNormal, physicsObject, currentVel)
        
        # IMPORTANT: Also apply friction immediately during collision handling
        # This ensures friction is applied every time we collide, not just in the continuous task
        # This is critical for objects sliding on surfaces - they collide continuously
        if self._dynamic_friction_coef > 0.0 or self._static_friction_coef > 0.0:
            # Get velocity after collision response
            postCollisionVel = physicsObject.getVelocity()
            if postCollisionVel.length() > self._almost_stationary_speed:
                # Apply friction to the post-collision velocity
                frictionVel = self._applyFriction(postCollisionVel, collisionNormal, postCollisionVel)
                physicsObject.setVelocity(frictionVel)
    
    def _getWorldSpaceNormal(self, entry):
        """
        Get the collision normal in world space (render space).
        This ensures the normal is independent of object orientation.
        """
        try:
            # Try to get normal in render space (world space)
            return entry.getSurfaceNormal(render)
        except:
            # Fallback: get normal in the into node's space and transform to world space
            intoNodePath = entry.getIntoNodePath()
            if intoNodePath and not intoNodePath.isEmpty():
                normal = entry.getSurfaceNormal(intoNodePath)
                # Transform to world space
                return render.getRelativeVector(intoNodePath, normal)
            return None
    
    def _applyPushAway(self, entry, normal, physicsObject):
        """
        Apply a simple push-away force when the object is almost stationary.
        """
        # Push the object away from the surface
        pushForce = normal * 0.1  # Small push force
        currentVel = physicsObject.getVelocity()
        newVel = currentVel + pushForce
        physicsObject.setVelocity(newVel)
    
    def _applyWorldSpaceCollisionResponse(self, entry, normal, physicsObject, currentVel):
        """
        Apply collision response calculated purely in world space.
        This is the core method that ensures orientation doesn't affect trajectory.
        """
        # Calculate dot product of velocity and normal
        # Negative means moving towards surface (colliding)
        velDotNormal = currentVel.dot(normal)
        
        if velDotNormal >= 0:
            # Moving away from surface, no collision response needed
            return
        
        # Calculate reflection: newVel = oldVel - 2 * (oldVel · normal) * normal
        # This gives us the bounce direction in world space
        reflection = currentVel - normal * (2 * velDotNormal)
        
        # Apply immediate friction to the tangential component during collision
        reflection = self._applyFriction(reflection, normal, currentVel)
        
        # Track this physics object for continuous friction
        # Store the collision normal and time so we can apply continuous friction
        currentTime = globalClock.getFrameTime()
        self._activePhysicsObjects[physicsObject] = (normal, currentTime, True)
        
        # Use the reflection's length (which includes friction reduction)
        # This ensures friction actually reduces speed, not just changes direction
        if reflection.length() > 0.001:
            physicsObject.setVelocity(reflection)
        else:
            # Velocity too small, stop the object
            physicsObject.setVelocity(Vec3(0, 0, 0))
            # Remove from active tracking
            if physicsObject in self._activePhysicsObjects:
                del self._activePhysicsObjects[physicsObject]
    
    def _applyFriction(self, velocity, normal, originalVel):
        """
        Apply friction to the velocity component tangential to the surface.
        Friction reduces the tangential (sliding) component of velocity.
        """
        if self._dynamic_friction_coef == 0.0 and self._static_friction_coef == 0.0:
            return velocity
        
        # Calculate tangential velocity (component perpendicular to normal)
        # This is the component that slides along the surface
        # tangential = velocity - (velocity · normal) * normal
        velDotNormal = velocity.dot(normal)
        tangential = velocity - normal * velDotNormal
        
        # Determine which friction coefficient to use
        speed = velocity.length()
        frictionCoef = self._dynamic_friction_coef
        if speed < self._almost_stationary_speed:
            frictionCoef = self._static_friction_coef
        
        # Apply friction: reduce tangential component
        # Friction coefficient of 1.0 = complete stop, 0.0 = no friction
        tangentialLength = tangential.length()
        if tangentialLength > 0.001:
            # Reduce tangential velocity by friction coefficient
            tangential = tangential * (1.0 - frictionCoef)
        
        # Reconstruct velocity: normal component (bounce) + reduced tangential component (sliding)
        # The normal component represents the bounce, tangential represents sliding
        return normal * velDotNormal + tangential
    

"""
CustomGravityWalker.py - A custom GravityWalker with configurable jump delays
"""
from direct.controls.GravityWalker import GravityWalker
from direct.showbase.InputStateGlobal import inputState
from direct.showbase import DirectObject
from direct.task.Task import Task
from panda3d.core import *
from direct.extensions_native import VBase3_extensions
from direct.extensions_native import VBase4_extensions
import math


class CustomGravityWalker(GravityWalker):
    """
    A GravityWalker subclass that allows configurable jump delays for hard and normal landings.
    """
    
    def __init__(self, hardLandingDelay=0.3, normalLandingDelay=0.2, gravity=64.348, 
                 standableGround=0.707, hardLandingForce=16.0, legacyLifter=False):
        """
        Initialize the custom gravity walker with configurable jump delays.
        
        Args:
            hardLandingDelay: Delay in seconds before allowing jump after hard landing (default: 0.3)
            normalLandingDelay: Delay in seconds before allowing jump after normal landing (default: 0.2)
            gravity: Gravity value (default: 64.348)
            standableGround: Standable ground threshold (default: 0.707)
            hardLandingForce: Hard landing force threshold (default: 16.0)
            legacyLifter: Whether to use legacy lifter (default: False)
        """
        GravityWalker.__init__(self, gravity=gravity, standableGround=standableGround,
                              hardLandingForce=hardLandingForce, legacyLifter=legacyLifter)
        self.hardLandingDelay = hardLandingDelay
        self.normalLandingDelay = normalLandingDelay

    def handleAvatarControls(self, task):
        """
        Check on the arrow keys and update the avatar.
        This is a copy of the parent method with custom delay values.
        """
        # get the button states:
        run = inputState.isSet("run")
        forward = inputState.isSet("forward")
        reverse = inputState.isSet("reverse")
        turnLeft = inputState.isSet("turnLeft")
        turnRight = inputState.isSet("turnRight")
        slideLeft = inputState.isSet("slideLeft")
        slideRight = inputState.isSet("slideRight")
        jump = inputState.isSet("jump")

        # Check for Auto-Run
        if 'localAvatar' in __builtins__:
            if base.localAvatar and base.localAvatar.getAutoRun():
                forward = 1
                reverse = 0

        # Determine what the speeds are based on the buttons:
        self.speed=(forward and self.avatarControlForwardSpeed or
                    reverse and -self.avatarControlReverseSpeed)
        # Slide speed is a scaled down version of forward speed
        # Note: you can multiply a factor in here if you want slide to
        # be slower than normal walk/run. Let's try full speed.
        #self.slideSpeed=(slideLeft and -self.avatarControlForwardSpeed*0.75 or
        #                 slideRight and self.avatarControlForwardSpeed*0.75)
        self.slideSpeed=(reverse and slideLeft and -self.avatarControlReverseSpeed*0.75 or
                         reverse and slideRight and self.avatarControlReverseSpeed*0.75 or
                         slideLeft and -self.avatarControlForwardSpeed*0.75 or
                         slideRight and self.avatarControlForwardSpeed*0.75)
        self.rotationSpeed=not (slideLeft or slideRight) and (
                (turnLeft and self.avatarControlRotateSpeed) or
                (turnRight and -self.avatarControlRotateSpeed))

        if self.speed and self.slideSpeed:
            self.speed *= GravityWalker.DiagonalFactor
            self.slideSpeed *= GravityWalker.DiagonalFactor

        debugRunning = inputState.isSet("debugRunning")
        if(debugRunning):
            self.speed*=base.debugRunningMultiplier
            self.slideSpeed*=base.debugRunningMultiplier
            self.rotationSpeed*=1.25

        if self.needToDeltaPos:
            self.setPriorParentVector()
            self.needToDeltaPos = 0
        if self.wantDebugIndicator:
            self.displayDebugInfo()
        if self.lifter.isOnGround():
            if self.isAirborne:
                self.isAirborne = 0
                assert self.debugPrint("isAirborne 0 due to isOnGround() true")
                impact = self.lifter.getImpactVelocity()
                
                # Check if we're landing on a Floating Platform
                # MovingPlatform sets a flag on localAvatar when entering/exiting the platform
                isFloatingPlatform = False
                if hasattr(base, 'localAvatar') and base.localAvatar:
                    # Check if the flag is set (set by DistributedCashbotFloatingPlatform.onToonEnter)
                    if hasattr(base.localAvatar, '_onFloatingPlatform') and base.localAvatar._onFloatingPlatform:
                        isFloatingPlatform = True
                
                if isFloatingPlatform:
                    # Landing on Floating Platform - use very short delay
                    messenger.send("jumpLand")
                    self.startJumpDelay(0.05)
                elif impact < -30.0:
                    messenger.send("jumpHardLand")
                    # Use custom hard landing delay
                    self.startJumpDelay(self.hardLandingDelay)
                else:
                    messenger.send("jumpLand")
                    if impact < -5.0:
                        # Use custom normal landing delay
                        self.startJumpDelay(self.normalLandingDelay)
                    # else, ignore the little potholes.
            assert self.isAirborne == 0
            self.priorParent = Vec3.zero()
            if jump and self.mayJump:
                # The jump button is down and we're close
                # enough to the ground to jump.
                self.lifter.addVelocity(self.avatarControlJumpForce)
                messenger.send("jumpStart")
                self.isAirborne = 1
                assert self.debugPrint("isAirborne 1 due to jump")
        else:
            if self.isAirborne == 0:
                assert self.debugPrint("isAirborne 1 due to isOnGround() false")
            self.isAirborne = 1

        self.__oldPosDelta = self.avatarNodePath.getPosDelta(render)
        # How far did we move based on the amount of time elapsed?
        self.__oldDt = ClockObject.getGlobalClock().getDt()
        dt=self.__oldDt

        # Check to see if we're moving at all:
        self.moving = self.speed or self.slideSpeed or self.rotationSpeed or (self.priorParent!=Vec3.zero())
        if self.moving:
            distance = dt * self.speed
            slideDistance = dt * self.slideSpeed
            rotation = dt * self.rotationSpeed

            # Take a step in the direction of our previous heading.
            if distance or slideDistance or self.priorParent != Vec3.zero():
                # rotMat is the rotation matrix corresponding to
                # our previous heading.
                rotMat=Mat3.rotateMatNormaxis(self.avatarNodePath.getH(), Vec3.up())
                if self.isAirborne:
                    forward = Vec3.forward()
                else:
                    contact = self.lifter.getContactNormal()
                    forward = contact.cross(Vec3.right())
                    # Consider commenting out this normalize.  If you do so
                    # then going up and down slops is a touch slower and
                    # steeper terrain can cut the movement in half.  Without
                    # the normalize the movement is slowed by the cosine of
                    # the slope (i.e. it is multiplied by the sign as a
                    # side effect of the cross product above).
                    forward.normalize()
                self.vel=Vec3(forward * distance)
                if slideDistance:
                    if self.isAirborne:
                        right = Vec3.right()
                    else:
                        right = forward.cross(contact)
                        # See note above for forward.normalize()
                        right.normalize()
                    self.vel=Vec3(self.vel + (right * slideDistance))
                self.vel=Vec3(rotMat.xform(self.vel))
                step=self.vel + (self.priorParent * dt)
                self.avatarNodePath.setFluidPos(Point3(
                        self.avatarNodePath.getPos()+step))
            self.avatarNodePath.setH(self.avatarNodePath.getH()+rotation)
        else:
            self.vel.set(0.0, 0.0, 0.0)
        if self.moving or jump:
            messenger.send("avatarMoving")
        return Task.cont

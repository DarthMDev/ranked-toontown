from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObject import DistributedObject
from panda3d.core import CollisionSphere, CollisionNode
from toontown.toonbase import ToontownGlobals
from direct.interval.IntervalGlobal import Sequence, LerpPosInterval, Wait
from panda3d.core import Vec3
from toontown.coghq import MovingPlatform

class DistributedFloatingPlatform(DistributedObject):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFloatingPlatform')

    def __init__(self, cr):
        DistributedObject.__init__(self, cr)
        self.index = 0
        self.model = None
        self.hoverIval = None
        self.basePos = None  # Base position (x, y, z) for hovering
        self.hoverRange = 4.0  # How far up and down to hover
        self.hoverDuration = 4.0  # Duration for one complete hover cycle (up and down)

    def setIndex(self, index):
        self.index = index

    def announceGenerate(self):
        DistributedObject.announceGenerate(self)
        self.loadModel()
        self.setupCollision()

    def loadModel(self):
        """Load the mint lava room platform model."""
        # Use the same platform model as the mint lava room
        model = loader.loadModel('phase_9/models/cogHQ/platform1')
        if not model:
            self.notify.warning('Failed to load platform model!')
            return
        
        # Use MovingPlatform to properly set up the platform with its built-in collision
        # This is the same approach used by DistributedSinkingPlatform
        self.platform = MovingPlatform.MovingPlatform()
        self.platform.setupCopyModel(self.uniqueName('platform'), model, 'platformcollision')
        # Rename the collision node to 'platform' so Cashbot Boss objects can detect it
        # The MovingPlatform sets the name to something like 'MovingPlatform-platform-12345'
        # We'll rename it to just 'platform' so it can be detected by the collision handler
        platformCollisions = self.platform.findAllMatches('**/MovingPlatform-*')
        for collision in platformCollisions:
            collision.setName('platform')
        
        # Create a parent node for positioning
        # Note: The node name contains "FloatingPlatform" so CustomGravityWalker can detect it
        self.model = render.attachNewNode('FloatingPlatform-%s' % self.index)
        self.platform.reparentTo(self.model)
        self.platform.setPos(0, 0, 0)
        
        # If basePos was set (via setPosition called before model loaded), set position now
        if self.basePos is not None:
            self.model.setPos(self.basePos[0], self.basePos[1], self.basePos[2])
            self.notify.debug('Platform %s: Loaded model at position %s' % (self.index, self.basePos))
        else:
            # Default position if setPosition hasn't been called yet
            self.model.setPos(0, 0, 0)
            self.notify.debug('Platform %s: Loaded model at default position' % self.index)
        
        # Scale if needed
        self.model.setScale(1.0)
        
        # Start hover animation if basePos is set
        if self.basePos is not None:
            self.startHoverAnimation()

    def setupCollision(self):
        """Setup collision for the platform so toons can stand on it."""
        # The MovingPlatform already handles collision setup using the model's built-in
        # 'platformcollision' geometry, so we don't need to add extra collision here.
        # The platform's collision is already properly configured by MovingPlatform.
        
        # Listen for when toons get hit so we can release them from the platform
        # This prevents them from being sent to oblivion when the platform moves during knockback
        self.accept('LocalSetOuchMode', self.onToonHit)
        self.accept('toonStunned-' + str(base.localAvatar.doId), self.onToonStunned)
    
    def onToonHit(self):
        """Called when the local toon gets hit. Release them from the platform."""
        if hasattr(self, 'platform') and self.platform:
            # Release the toon from the platform so they can be knocked back properly
            self.platform.releaseLocalToon()
    
    def onToonStunned(self, isStunned):
        """Called when the local toon gets stunned/unstunned."""
        if isStunned and hasattr(self, 'platform') and self.platform:
            # Release the toon from the platform when they get stunned (hit)
            self.platform.releaseLocalToon()

    def setPosition(self, x, y, z):
        """Set the platform position and start hovering animation."""
        self.basePos = (x, y, z)
        self.notify.debug('Platform %s: setPosition called with (%s, %s, %s)' % (self.index, x, y, z))
        if self.model:
            # Model is already loaded, set position and start animation
            self.model.setPos(x, y, z)
            self.startHoverAnimation()
        # If model isn't loaded yet, basePos is stored and will be used in loadModel

    def startHoverAnimation(self):
        """Start the continuous up and down hovering animation."""
        if not self.model:
            return
        
        # Stop any existing animation
        if self.hoverIval:
            self.hoverIval.pause()
            self.hoverIval = None
        
        # Get the current position
        currentPos = self.model.getPos()
        if self.basePos is not None:
            basePos = Vec3(self.basePos[0], self.basePos[1], self.basePos[2])
        else:
            basePos = Vec3(currentPos[0], currentPos[1], currentPos[2])
        
        # Create positions relative to base
        # Add an offset to the lower bound so it doesn't go too low
        lowerBoundOffset = self.hoverRange * 0.3  # Keep the lower bound 30% of hoverRange above base
        downPos = Vec3(basePos[0], basePos[1], basePos[2] + lowerBoundOffset)
        upPos = Vec3(basePos[0], basePos[1], basePos[2] + self.hoverRange)
        
        # Create the hover interval: up once, then down once, then repeat
        # Animate the model node (which contains the platform)
        self.hoverIval = Sequence(
            LerpPosInterval(
                self.model,
                self.hoverDuration / 2.0,  # Half duration to go up
                upPos,
                startPos=downPos,
                blendType='easeInOut',
                name='platform-hover-up-%s' % self.index
            ),
            LerpPosInterval(
                self.model,
                self.hoverDuration / 2.0,  # Half duration to go down
                downPos,
                startPos=upPos,
                blendType='easeInOut',
                name='platform-hover-down-%s' % self.index
            )
        )
        
        # Loop the animation
        self.hoverIval.loop()

    def disable(self):
        DistributedObject.disable(self)
        # Stop listening to hit events
        self.ignore('LocalSetOuchMode')
        if hasattr(base, 'localAvatar') and base.localAvatar:
            self.ignore('toonStunned-' + str(base.localAvatar.doId))
        if self.hoverIval:
            self.hoverIval.pause()
            self.hoverIval = None

    def delete(self):
        if self.hoverIval:
            self.hoverIval.pause()
            self.hoverIval = None
        if hasattr(self, 'platform') and self.platform:
            self.platform.destroy()
            del self.platform
        if self.model:
            self.model.removeNode()
            self.model = None
        DistributedObject.delete(self)

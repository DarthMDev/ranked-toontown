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
        
        print('[DistributedFloatingPlatform] loadModel: doId=%s, index=%s' % (self.doId, self.index))
        
        # Create a parent node for positioning first
        # Note: The node name contains "FloatingPlatform" so CustomGravityWalker can detect it
        self.model = render.attachNewNode('FloatingPlatform-%s' % self.index)
        print('[DistributedFloatingPlatform] Created model node: %s, parent=%s' % (self.model, self.model.getParent()))
        
        # Create a separate parenting node for avatars under render (so it's visible during setup)
        # This prevents MovingPlatform's fallback from using render directly, which breaks relative positioning
        # We'll reparent this node to the platform after setup, similar to how ConveyorBelt works
        self.platform = MovingPlatform.MovingPlatform()
        self.platform.parentingNode = render.attachNewNode('parentTarget-%s' % self.index)
        print('[DistributedFloatingPlatform] Created parentingNode: %s, parent=%s, getTop()=%s' % (
            self.platform.parentingNode, self.platform.parentingNode.getParent(), self.platform.parentingNode.getTop()))
        
        # Use MovingPlatform to properly set up the platform with its built-in collision
        # Use doId as parentToken (converted to SPDynamic) so it's consistent across all clients
        # Pass the parentingNode so avatars get parented to it (it's visible, so no fallback to render)
        self.platform.setupCopyModel(self.doId, model, 'platformcollision', parentingNode=self.platform.parentingNode)
        print('[DistributedFloatingPlatform] After setupCopyModel: parentToken=%s, parentingNode=%s, parentingNode.getTop()=%s' % (
            self.platform.parentToken, self.platform.parentingNode, self.platform.parentingNode.getTop()))
        
        # Now reparent the parenting node to the platform so avatars move with it
        self.platform.parentingNode.reparentTo(self.platform)
        print('[DistributedFloatingPlatform] After reparenting parentingNode to platform: parent=%s, getTop()=%s' % (
            self.platform.parentingNode.getParent(), self.platform.parentingNode.getTop()))
        
        # The MovingPlatform sets collision node names to self._name (e.g., 'MovingPlatform-...')
        # We need to keep this name for the collision events to work, but we can add a tag
        # for Cashbot Boss objects to detect it, and also add a Python tag for identification
        platformCollisions = self.platform.findAllMatches('**/MovingPlatform-*')
        for collision in platformCollisions:
            # Keep the original name for MovingPlatform collision events to work
            # But add a tag so other systems can find it
            collision.setTag('platform', '1')
            collision.setPythonTag('FloatingPlatform', True)
        
        self.platform.reparentTo(self.model)
        self.platform.setPos(0, 0, 0)
        print('[DistributedFloatingPlatform] After reparenting platform to model: platform.parent=%s, parentingNode.getTop()=%s' % (
            self.platform.getParent(), self.platform.parentingNode.getTop()))
        
        # Update the parenting node registration after all reparenting is complete
        # This ensures ParentMgr has the final, correct node reference that moves with the platform
        # Force re-registration to ensure the node is properly registered after all reparenting
        base.cr.parentMgr.unregisterParent(self.platform.parentToken)
        base.cr.parentMgr.registerParent(self.platform.parentToken, self.platform.parentingNode)
        print('[DistributedFloatingPlatform] Re-registered parentToken=%s with parentingNode=%s, getTop()=%s' % (
            self.platform.parentToken, self.platform.parentingNode, self.platform.parentingNode.getTop()))
        
        # Verify the registration
        registeredNode = base.cr.parentMgr.getParent(self.platform.parentToken)
        print('[DistributedFloatingPlatform] ParentMgr.getParent(%s) = %s, getTop()=%s' % (
            self.platform.parentToken, registeredNode, registeredNode.getTop() if registeredNode and not registeredNode.isEmpty() else 'EMPTY'))
        
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
        
        # Listen to MovingPlatform enter/exit events to track when local toon is on platform
        # This allows CustomGravityWalker to detect when landing on a FloatingPlatform
        if hasattr(self, 'platform') and self.platform:
            enterEvent = self.platform.getEnterEvent()
            exitEvent = self.platform.getExitEvent()
            self.accept(enterEvent, self.onToonEnter)
            self.accept(exitEvent, self.onToonExit)
    
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
    
    def onToonEnter(self, collEntry=None):
        """Called when the local toon enters the platform."""
        # Set a flag on the local avatar so CustomGravityWalker can detect it
        if hasattr(base, 'localAvatar') and base.localAvatar:
            base.localAvatar._onFloatingPlatform = True
    
    def onToonExit(self, collEntry=None):
        """Called when the local toon exits the platform."""
        # Clear the flag
        if hasattr(base, 'localAvatar') and base.localAvatar:
            base.localAvatar._onFloatingPlatform = False

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
        # Stop listening to platform enter/exit events
        if hasattr(self, 'platform') and self.platform:
            self.ignore(self.platform.getEnterEvent())
            self.ignore(self.platform.getExitEvent())
        # Clear the flag if toon is still on platform
        if hasattr(base, 'localAvatar') and base.localAvatar:
            if hasattr(base.localAvatar, '_onFloatingPlatform'):
                base.localAvatar._onFloatingPlatform = False
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

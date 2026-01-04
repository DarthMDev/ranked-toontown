from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObject import DistributedObject
from panda3d.core import CollisionSphere, CollisionNode, BitMask32, Point3
from toontown.toonbase import ToontownGlobals
from direct.interval.IntervalGlobal import Sequence, Wait, Func

class DistributedCFOPieStand(DistributedObject):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedCFOPieStand')

    def __init__(self, cr):
        DistributedObject.__init__(self, cr)
        self.index = 0
        self.model = None
        self.collisionNode = None
        self.collisionNodePath = None
        self.pies = []
        self.touchCooldown = False
        self.TOUCH_COOLDOWN_TIME = 2.0  # 2 second cooldown between touches

    def setIndex(self, index):
        self.index = index

    def announceGenerate(self):
        DistributedObject.announceGenerate(self)
        self.loadModel()
        self.setupCollision()

    def loadModel(self):
        """Load the wheelbarrow model and add cream pies to it."""
        # Load the wheelbarrow model
        self.model = loader.loadModel('phase_5.5/models/estate/wheelbarrel.bam')
        
        # Get position from the side crane positions
        from toontown.coghq import CraneLeagueGlobals
        poshpr = CraneLeagueGlobals.SIDE_CRANE_POSHPR[self.index]
        # Rotate by 90 degrees (H)
        newH = poshpr[3] + 90
        self.model.setPosHpr(poshpr[0], poshpr[1], poshpr[2], newH, poshpr[4], poshpr[5])
        self.model.reparentTo(render)
        
        # Scale the wheelbarrow appropriately
        self.model.setScale(2.0)
        
        # Remove the dirt node
        dirtNode = self.model.find('**/dirt')
        if not dirtNode.isEmpty():
            dirtNode.removeNode()
        
        # Add cream pies to the wheelbarrow
        self.loadPies()

    def loadPies(self):
        """Load cream pie models into the wheelbarrow."""
        # Load a few cream pies and place them in the wheelbarrow
        # Arrange them in a spread-out pattern, stacked in layers
        pie_positions = [
            # Layer 1 (bottom)
            (-0.2, -0.3, 1.1),
            (0.0, -0.0, 1.1),
            (-0.2, 0.0, 1.1),
            (0.0, 0.0, 1.0),
            (0.0, 0.6, 1.0),
            # Layer 2 (middle)
            (-0.1, -0.3, 1.2),
            (0.0, -0.3, 1.1),
            (-0.1, 0.3, 1.2),
            (-0.2, 0.3, 1.2),
            # Layer 3 (top)
            (-0.15, -0.1, 1.4),
            (0.0, 0.55, 1.3),
        ]
        
        for i, (x_offset, y_offset, z_offset) in enumerate(pie_positions):
            pie = loader.loadModel('phase_3.5/models/props/tart.bam')
            pie.reparentTo(self.model)
            
            pie.setPos(x_offset, y_offset, z_offset)
            pie.setScale(0.55)  # Make pies smaller
            pie.setH(i * 30)  # Rotate each pie differently
            
            # Set cream pie color (white/cream colored)
            pie.setColorScale(1.0, 0.95, 0.85, 1.0)
            
            self.pies.append(pie)

    def setupCollision(self):
        """Setup collision sphere for detecting when toons touch the pie stand."""
        # Create a collision sphere around the wheelbarrow for toon detection
        # Match the cage pattern - simpler setup
        collSphere = CollisionSphere(0, 0, 1.0, 2.5)  # 2.5 foot radius
        collSphere.setTangible(0)  # Non-tangible so toons can pass through but trigger event
        
        collNodeName = 'PieStand-%s' % self.index
        collNode = CollisionNode(collNodeName)
        collNode.addSolid(collSphere)
        # Use setCollideMask like the cage does - this sets both from and into masks
        collNode.setCollideMask(ToontownGlobals.WallBitmask)
        
        self.collisionNodePath = self.model.attachNewNode(collNode)
        self.collisionNodePath.setTag('doId', str(self.doId))
        
        # Accept collisions with this pie stand (using the node name pattern)
        # The collision system automatically generates 'enter' + nodeName events
        eventName = 'enter' + collNodeName
        self.accept(eventName, self.handleEnterPieStand)
        self.notify.debug('Pie stand %s: Accepting collision event: %s' % (self.index, eventName))

    def handleEnterPieStand(self, collisionEntry):
        """Handle when a toon enters the pie stand collision."""
        self.notify.debug('Pie stand %s: handleEnterPieStand called!' % self.index)
        # Check if we're on cooldown
        if self.touchCooldown:
            self.notify.debug('Pie stand %s: On cooldown, ignoring' % self.index)
            return
        
        # Get the from node (the toon's collision sphere that entered)
        fromNode = collisionEntry.getFromNodePath()
        if fromNode.isEmpty():
            self.notify.debug('Pie stand %s: Empty fromNode' % self.index)
            return
        
        # The collision system should only trigger for local avatar collisions
        # So we can trust that if this event fired, it's the local avatar
        # (Similar to how the cage works - it doesn't check, just trusts the collision system)
        
        self.notify.debug('Pie stand %s: Sending touchPieStand to server' % self.index)
        # Send touch request to server
        self.sendUpdate('touchPieStand', [])
        
        # Start cooldown
        self.touchCooldown = True
        Sequence(
            Wait(self.TOUCH_COOLDOWN_TIME),
            Func(self.resetCooldown)
        ).start()
        
        # Play a sound effect (Sellbot Boss cage sound)
        base.playSfx(base.loader.loadSfx('phase_9/audio/sfx/CHQ_SOS_pies_restock.ogg'))

    def resetCooldown(self):
        """Reset the touch cooldown."""
        self.touchCooldown = False

    def disable(self):
        DistributedObject.disable(self)
        self.ignoreAll()

    def delete(self):
        if self.model:
            self.model.removeNode()
            self.model = None
        if self.collisionNodePath:
            self.collisionNodePath.removeNode()
            self.collisionNodePath = None
        self.pies = []
        DistributedObject.delete(self)


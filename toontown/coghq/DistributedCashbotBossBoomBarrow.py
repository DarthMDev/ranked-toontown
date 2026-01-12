from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObject import DistributedObject
from panda3d.core import CollisionSphere, CollisionNode, BitMask32, Point3
from toontown.toonbase import ToontownGlobals
from direct.interval.IntervalGlobal import Sequence, Wait, Func

class DistributedCashbotBossBoomBarrow(DistributedObject):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedCashbotBossBoomBarrow')

    def __init__(self, cr):
        DistributedObject.__init__(self, cr)
        self.index = 0
        self.model = None
        self.collisionNode = None
        self.collisionNodePath = None
        self.tnts = []
        self.touchCooldown = False
        self.TOUCH_COOLDOWN_TIME = 2.0  # 2 second cooldown between touches (client-side debounce)
        self.onCooldown = False  # Server-controlled cooldown state

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
        from toontown.minigame.craning import CraneGameGlobals
        poshpr = CraneGameGlobals.SIDE_CRANE_POSHPR[self.index]
        # Rotate by 90 degrees (H)
        newH = poshpr[3] + 90
        self.model.setPosHpr(poshpr[0], poshpr[1], poshpr[2], newH, poshpr[4], poshpr[5])
        self.model.reparentTo(render)
        
        # Scale the wheelbarrow appropriately
        self.model.setScale(2.0)
        
        # Change wheelbarrow color from blue to green
        # Apply dark greyish green color scale to the bed
        wheelbarrowNode = self.model.find('**/bed')
        if not wheelbarrowNode.isEmpty():
            wheelbarrowNode.setColorScale(0.15, 0.3, 0.15, 1.0)  # Dark greyish green
        
        # Make handles dark grey
        handle1 = self.model.find('**/handle1')
        if not handle1.isEmpty():
            handle1.setColorScale(0.2, 0.2, 0.2, 1.0)  # Dark grey
        handle2 = self.model.find('**/handle2')
        if not handle2.isEmpty():
            handle2.setColorScale(0.2, 0.2, 0.2, 1.0)  # Dark grey
        
        # Remove the dirt node
        dirtNode = self.model.find('**/dirt')
        if not dirtNode.isEmpty():
            dirtNode.removeNode()
        
        # Add TNT to the wheelbarrow
        self.loadTNTs()

    def loadTNTs(self):
        """Load TNT models into the wheelbarrow."""
        # Load TNT props and place them in the wheelbarrow
        # Arrange them in a spread-out pattern, stacked in layers
        from toontown.battle import BattleProps
        
        tnt_positions = [
            # Layer 1 (bottom)
            (-0.3, -0.4, 1.2),
            (0.0, -0.1, 1.2),
            (-0.3, 0.1, 1.2),
            (0.0, 0.1, 1.1),
            (0.0, 0.7, 1.1),
            (0.3, -0.3, 1.1),
            (-0.25, 0.4, 1.1),
            # Layer 2 (middle)
            (-0.2, -0.4, 1.3),
            (0.0, -0.4, 1.2),
            (-0.2, 0.4, 1.3),
            (-0.3, 0.4, 1.3),
            (0.2, -0.2, 1.3),
            (0.25, 0.3, 1.3),
            (-0.35, 0.2, 1.3),
            # Layer 3 (top)
            (-0.25, -0.2, 1.5),
            (0.0, 0.65, 1.4),
            (0.2, 0.1, 1.4),
            (-0.2, 0.5, 1.4),
            (0.3, 0.4, 1.4),
            # Layer 4 (topmost)
            (0.0, 0.3, 1.6),
            (-0.2, 0.2, 1.6),
            (0.2, 0.5, 1.6),
        ]
        
        for i, (x_offset, y_offset, z_offset) in enumerate(tnt_positions):
            tnt = BattleProps.globalPropPool.getProp('tnt')
            tnt.reparentTo(self.model)
            
            tnt.setPos(x_offset, y_offset, z_offset)
            tnt.setScale(0.4)  # Make TNT smaller to fit in wheelbarrow
            tnt.setH(i * 30)  # Rotate each TNT differently
            
            self.tnts.append(tnt)

    def setupCollision(self):
        """Setup collision sphere for detecting when toons touch the pie stand."""
        # Create a collision sphere around the wheelbarrow for toon detection
        # Match the cage pattern - simpler setup
        collSphere = CollisionSphere(0, 0, 1.0, 2.5)  # 2.5 foot radius
        collSphere.setTangible(0)  # Non-tangible so toons can pass through but trigger event
        
        collNodeName = 'BoomBarrow-%s' % self.index
        collNode = CollisionNode(collNodeName)
        collNode.addSolid(collSphere)
        # Use setCollideMask like the cage does - this sets both from and into masks
        collNode.setCollideMask(ToontownGlobals.WallBitmask)
        
        self.collisionNodePath = self.model.attachNewNode(collNode)
        self.collisionNodePath.setTag('doId', str(self.doId))
        
        # Accept collisions with this boom barrow (using the node name pattern)
        # The collision system automatically generates 'enter' + nodeName events
        eventName = 'enter' + collNodeName
        self.accept(eventName, self.handleEnterBoomBarrow)
        self.notify.debug('Boom Barrow %s: Accepting collision event: %s' % (self.index, eventName))

    def handleEnterBoomBarrow(self, collisionEntry):
        """Handle when a toon enters the boom barrow collision."""
        self.notify.debug('Boom Barrow %s: handleEnterBoomBarrow called!' % self.index)
        # Check if we're on client-side cooldown (debounce)
        if self.touchCooldown:
            self.notify.debug('Boom Barrow %s: On client cooldown, ignoring' % self.index)
            return
        
        # Check if stand is on server-side cooldown for this player
        if self.onCooldown:
            self.notify.debug('Boom Barrow %s: On server cooldown, ignoring' % self.index)
            return
        
        # Get the from node (the toon's collision sphere that entered)
        fromNode = collisionEntry.getFromNodePath()
        if fromNode.isEmpty():
            self.notify.debug('Boom Barrow %s: Empty fromNode' % self.index)
            return
        
        # The collision system should only trigger for local avatar collisions
        # So we can trust that if this event fired, it's the local avatar
        # (Similar to how the cage works - it doesn't check, just trusts the collision system)
        
        self.notify.debug('Boom Barrow %s: Sending touchBoomBarrow to server' % self.index)
        # Send touch request to server
        self.sendUpdate('touchBoomBarrow', [])
        
        # Start client-side debounce cooldown
        self.touchCooldown = True
        Sequence(
            Wait(self.TOUCH_COOLDOWN_TIME),
            Func(self.resetCooldown)
        ).start()
        
        # Play TNT fuse/preparation sound effect (first 0.7 seconds only)
        # This is the appropriate gag sfx for TNT - the fuse/prepare sound
        from direct.interval.SoundInterval import SoundInterval
        tntSound = base.loader.loadSfx('phase_5/audio/sfx/TL_dynamite.ogg')
        if tntSound:
            SoundInterval(tntSound, duration=0.7, volume=2.0, node=self.model).start()

    def resetCooldown(self):
        """Reset the touch cooldown."""
        self.touchCooldown = False
    
    def setCooldownState(self, onCooldown, avId):
        """Called by server to update cooldown visual state.
        Only show visual if it's for the local player."""
        # Only show cooldown visual if it's for the local player
        if avId != base.localAvatar.doId:
            return
        
        self.onCooldown = onCooldown
        if self.model:
            if onCooldown:
                # Make stand transparent to show it's on cooldown
                self.model.setTransparency(1)
                self.model.setAlphaScale(0.4)  # 40% opacity
            else:
                # Restore full opacity
                self.model.setAlphaScale(1.0)  # 100% opacity
                self.model.setTransparency(0)

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
        self.tnts = []
        DistributedObject.delete(self)


from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from panda3d.core import CollisionSphere, CollisionNode, NodePath
from toontown.toonbase import ToontownGlobals

class DistributedCashbotFloatingPlatformAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedCashbotFloatingPlatformAI')

    def __init__(self, air, boss, index):
        DistributedObjectAI.__init__(self, air)
        self.boss = boss
        self.index = index
        # Create collision node so goons can detect and avoid the platform
        self.collisionNode = CollisionNode('floatingPlatform')
        self.collisionNode.addSolid(CollisionSphere(0, 0, 0, 3.0))  # Platform radius
        self.collisionNode.setIntoCollideMask(ToontownGlobals.CashbotBossObjectBitmask)
        # Create a NodePath manually since we don't extend DistributedSmoothNodeAI
        self.collisionNodePath = NodePath(self.collisionNode)
        # Attach to boss's scene for collision detection (like safes do)
        self.collisionNodePath.reparentTo(self.boss.scene)
        
    def announceGenerate(self):
        DistributedObjectAI.announceGenerate(self)
        # Set position based on platform positions (near door and vault)
        # Positions will be set by the crane game
        pass

    def setIndex(self, index):
        self.index = index

    def d_setIndex(self, index):
        self.sendUpdate('setIndex', [index])

    def b_setIndex(self, index):
        self.setIndex(index)
        self.d_setIndex(index)

    def getIndex(self):
        return self.index
    
    def setPosition(self, x, y, z):
        """Set the platform position."""
        self.collisionNodePath.setPos(x, y, z)
        self.d_setPosition(x, y, z)
    
    def d_setPosition(self, x, y, z):
        self.sendUpdate('setPosition', [x, y, z])
    
    def delete(self):
        if hasattr(self, 'collisionNodePath') and self.collisionNodePath:
            self.collisionNodePath.removeNode()
            self.collisionNodePath = None
        DistributedObjectAI.delete(self)

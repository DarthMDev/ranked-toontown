from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.toonbase import ToontownGlobals
from panda3d.core import CollisionSphere, CollisionNode, NodePath

class DistributedCFOPieStandAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedCFOPieStandAI')

    def __init__(self, air, boss, index):
        DistributedObjectAI.__init__(self, air)
        self.boss = boss
        self.index = index
        # Create collision node so goons can detect and avoid the pie stand
        # This matches how safes are detected by goons
        self.collisionNode = CollisionNode('pieStand')
        self.collisionNode.addSolid(CollisionSphere(0, 0, 0, 2.5))  # Smaller radius for goon detection
        self.collisionNode.setIntoCollideMask(ToontownGlobals.CashbotBossObjectBitmask)
        # Create a NodePath manually since we don't extend DistributedSmoothNodeAI
        self.collisionNodePath = NodePath(self.collisionNode)
        # Attach to boss's scene for collision detection (like safes do)
        self.collisionNodePath.reparentTo(self.boss.scene)
        
    def announceGenerate(self):
        DistributedObjectAI.announceGenerate(self)
        # Set position based on side crane positions (same as where pie stands spawn)
        from toontown.coghq import CraneLeagueGlobals
        poshpr = CraneLeagueGlobals.SIDE_CRANE_POSHPR[self.index]
        self.collisionNodePath.setPosHpr(poshpr[0], poshpr[1], poshpr[2], poshpr[3], poshpr[4], poshpr[5])

    def setIndex(self, index):
        self.index = index

    def d_setIndex(self, index):
        self.sendUpdate('setIndex', [index])

    def b_setIndex(self, index):
        self.setIndex(index)
        self.d_setIndex(index)

    def getIndex(self):
        return self.index

    def touchPieStand(self):
        """Called when a toon touches the pie stand."""
        avId = self.air.getAvatarIdFromSender()
        
        # Validate the avatar - crane game uses getParticipants()
        if not hasattr(self.boss, 'getParticipants') or avId not in self.boss.getParticipants():
            self.notify.warning('touchPieStand from unknown avatar %s' % avId)
            return
            
        # Get the toon
        toon = self.air.doId2do.get(avId)
        if not toon:
            self.notify.warning('touchPieStand: could not find toon %s' % avId)
            return
        
        # Check if toon is alive
        if not hasattr(toon, 'hp') or toon.hp <= 0:
            self.notify.debug('touchPieStand: toon %s is not alive' % avId)
            return
            
        # Give the toon exactly 1 cream pie (never more than 1)
        currentPies = toon.numPies if hasattr(toon, 'numPies') else 0
        
        # Always set to 1 pie (don't add, just set to 1)
        # Set pie type to cream pie (type 4)
        toon.b_setPieType(4)  # Cream pie type
        toon.b_setNumPies(1)  # Always exactly 1 pie
        
        self.notify.debug('Gave toon %s exactly 1 cream pie (was %s)' % (avId, currentPies))
    
    def delete(self):
        if hasattr(self, 'collisionNodePath') and self.collisionNodePath:
            self.collisionNodePath.removeNode()
            self.collisionNodePath = None
        DistributedObjectAI.delete(self)


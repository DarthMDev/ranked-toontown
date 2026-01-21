from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from direct.task import Task
from direct.task.TaskManagerGlobal import taskMgr
from direct.showbase.ShowBaseGlobal import globalClock
from toontown.toonbase import ToontownGlobals
from panda3d.core import CollisionSphere, CollisionNode, NodePath

class DistributedCashbotBoomBarrowAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedCashbotBoomBarrowAI')

    def __init__(self, air, boss, index):
        DistributedObjectAI.__init__(self, air)
        self.boss = boss
        self.index = index
        # Track cooldowns per player (avId -> cooldown end time)
        self.playerCooldowns = {}  # {avId: cooldownEndTime}
        self.COOLDOWN_DURATION = 15.0  # 15 seconds cooldown
        # Create collision node so goons can detect and avoid the boom barrow
        # This matches how safes are detected by goons
        self.collisionNode = CollisionNode('boomBarrow')
        self.collisionNode.addSolid(CollisionSphere(0, 0, 0, 4))  # for goon detection
        self.collisionNode.setIntoCollideMask(ToontownGlobals.CashbotBossObjectBitmask)
        # Create a NodePath manually since we don't extend DistributedSmoothNodeAI
        self.collisionNodePath = NodePath(self.collisionNode)
        # Attach to boss's scene for collision detection (like safes do)
        self.collisionNodePath.reparentTo(self.boss.scene)
        
    def announceGenerate(self):
        DistributedObjectAI.announceGenerate(self)
        # Set position based on side crane positions (same as where boom barrows spawn)
        from toontown.minigame.craning import CraneGameGlobals
        poshpr = CraneGameGlobals.SIDE_CRANE_POSHPR[self.index]
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

    def touchBoomBarrow(self):
        """Called when a toon touches the boom barrow."""
        avId = self.air.getAvatarIdFromSender()
        
        # Validate the avatar - crane game uses getParticipants()
        if not hasattr(self.boss, 'getParticipants') or avId not in self.boss.getParticipants():
            self.notify.warning('touchBoomBarrow from unknown avatar %s' % avId)
            return
            
        # Get the toon
        toon = self.air.doId2do.get(avId)
        if not toon:
            self.notify.warning('touchBoomBarrow: could not find toon %s' % avId)
            return
        
        # Check if toon is alive
        if not hasattr(toon, 'hp') or toon.hp <= 0:
            self.notify.debug('touchBoomBarrow: toon %s is not alive' % avId)
            return
        
        # Check if player is on cooldown for this stand
        from direct.distributed.ClockDelta import globalClockDelta
        currentTime = globalClock.getFrameTime()
        if avId in self.playerCooldowns:
            cooldownEndTime = self.playerCooldowns[avId]
            if currentTime < cooldownEndTime:
                remainingTime = cooldownEndTime - currentTime
                self.notify.debug('touchBoomBarrow: toon %s is on cooldown for %.2f more seconds' % (avId, remainingTime))
                # Send cooldown state update to client (stand is already on cooldown for this player)
                return
        
        # Give the toon exactly 1 TNT pie (never more than 1)
        currentPies = toon.numPies if hasattr(toon, 'numPies') else 0
        
        # Always set to 1 pie (don't add, just set to 1)
        # Set pie type to TNT (type 8)
        toon.b_setPieType(8)  # TNT pie type
        toon.b_setNumPies(1)  # Always exactly 1 pie
        
        # Set cooldown for this player
        self.playerCooldowns[avId] = currentTime + self.COOLDOWN_DURATION
        
        # Schedule cooldown cleanup
        taskMgr.doMethodLater(self.COOLDOWN_DURATION, self.__clearCooldown, self.uniqueName('clearCooldown-%s' % avId), extraArgs=[avId])
        
        # Notify the specific client to show cooldown visual
        # Send update only to the player who triggered it
        self.sendUpdateToAvatarId(avId, 'setCooldownState', [True, avId])
        
        self.notify.debug('Gave toon %s exactly 1 TNT pie (was %s), cooldown until %.2f' % (avId, currentPies, self.playerCooldowns[avId]))
    
    def __clearCooldown(self, avId):
        """Clear cooldown for a specific player."""
        if avId in self.playerCooldowns:
            del self.playerCooldowns[avId]
            # Notify the specific client to hide cooldown visual
            self.sendUpdateToAvatarId(avId, 'setCooldownState', [False, avId])
        return Task.done
    
    
    def delete(self):
        # Clean up all cooldown tasks
        for avId in list(self.playerCooldowns.keys()):
            taskMgr.remove(self.uniqueName('clearCooldown-%s' % avId))
        self.playerCooldowns.clear()
        if hasattr(self, 'collisionNodePath') and self.collisionNodePath:
            self.collisionNodePath.removeNode()
            self.collisionNodePath = None
        DistributedObjectAI.delete(self)


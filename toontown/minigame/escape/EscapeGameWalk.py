from toontown.minigame.utils.OrthoWalk import *

class EscapeGameWalk(OrthoWalk):
    notify = DirectNotifyGlobal.directNotify.newCategory('EscapeGameWalk')
    BROADCAST_POS_TASK = 'EscapeGameWalkBroadcastPos'

    def doBroadcast(self, task):
        dt = globalClock.getDt()
        self.timeSinceLastPosBroadcast += dt
        if self.timeSinceLastPosBroadcast >= self.broadcastPeriod:
            self.timeSinceLastPosBroadcast = 0
            self.lt.cnode.broadcastPosHprFull()
        return Task.cont

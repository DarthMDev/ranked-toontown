from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectGlobal import DistributedObjectGlobal


class TTOffChatManager(DistributedObjectGlobal):
    notify = DirectNotifyGlobal.directNotify.newCategory('TTOffChatManager')

    def sendChatMessage(self, message):
        if message is None or len(message) == 0:
            return
        if len(message) > 1024:
            message = message[:1024]
        self.sendUpdate('chatMessage', [message])

    def sendWhisperMessage(self, message, receiverAvId):
        if message is None or len(message) == 0:
            return
        if len(message) > 1024:
            message = message[:1024]
        self.sendUpdate('whisperMessage', [message, receiverAvId])

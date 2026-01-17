from panda3d.core import *
from direct.interval.IntervalGlobal import *
from direct.showbase import DirectObject
from toontown.toonbase import ToontownGlobals
from direct.directnotify import DirectNotifyGlobal
import types

class MovingPlatform(DirectObject.DirectObject, NodePath):
    notify = DirectNotifyGlobal.directNotify.newCategory('MovingPlatform')

    def __init__(self):
        self.hasLt = 0
        DirectObject.DirectObject.__init__(self)
        NodePath.__init__(self)

    def setupCopyModel(self, parentToken, model, floorNodeName = None, parentingNode = None):
        if floorNodeName is None:
            floorNodeName = 'floor'
        if type(parentToken) == int:
            parentToken = ToontownGlobals.SPDynamic + parentToken
        self.parentToken = parentToken
        self._name = 'MovingPlatform-%s' % parentToken
        self.assign(hidden.attachNewNode(self._name))
        self.model = model.copyTo(self)
        self.ownsModel = 1
        floorList = self.model.findAllMatches('**/%s' % floorNodeName)
        if len(floorList) == 0:
            MovingPlatform.notify.warning('no floors in model')
            return
        for floor in floorList:
            floor.setName(self._name)

        if parentingNode == None:
            parentingNode = self
        # Ensure the parenting node is visible - if it's under hidden, use render as fallback
        # This prevents remote toons from becoming invisible when they get reparented
        # Note: Using render breaks relative positioning, but at least toons remain visible
        if not parentingNode.isEmpty():
            topNode = parentingNode.getTop()
            if topNode.compareTo(hidden) == 0:
                # The parenting node is under hidden, use render instead
                # This ensures toons remain visible even if the platform entity is under hidden
                # The trade-off is that toons won't move with the platform, but visibility is more important
                parentingNode = render
        base.cr.parentMgr.registerParent(self.parentToken, parentingNode)
        self.parentingNode = parentingNode
        self.accept('enter%s' % self._name, self.__handleEnter)
        self.accept('exit%s' % self._name, self.__handleExit)
        return

    def updateParentingNode(self, newParentingNode):
        """Update the registered parenting node to a new visible node.
        This should be called after reparenting the platform to a visible node
        to ensure remote toons remain visible when they get reparented."""
        if newParentingNode != self.parentingNode:
            base.cr.parentMgr.unregisterParent(self.parentToken)
            base.cr.parentMgr.registerParent(self.parentToken, newParentingNode)
            self.parentingNode = newParentingNode

    def destroy(self):
        base.cr.parentMgr.unregisterParent(self.parentToken)
        self.ignoreAll()
        if self.hasLt:
            self.__releaseLt()
        if self.ownsModel:
            self.model.removeNode()
            del self.model
        if hasattr(self, 'parentingNode') and self.parentingNode is self:
            del self.parentingNode

    def getEnterEvent(self):
        return '%s-enter' % self._name

    def getExitEvent(self):
        return '%s-exit' % self._name

    def releaseLocalToon(self):
        if self.hasLt:
            self.__releaseLt()

    def __handleEnter(self, collEntry):
        self.notify.debug('on movingPlatform %s' % self._name)
        self.__grabLt()
        messenger.send(self.getEnterEvent())

    def __handleExit(self, collEntry):
        self.notify.debug('off movingPlatform %s' % self._name)
        self.__releaseLt()
        messenger.send(self.getExitEvent())

    def __handleOnFloor(self, collEntry):
        if collEntry.getIntoNode().getName() == self._name:
            self.__handleEnter(collEntry)

    def __handleOffFloor(self, collEntry):
        if collEntry.getIntoNode().getName() == self._name:
            self.__handleExit(collEntry)

    def __grabLt(self):
        base.localAvatar.b_setParent(self.parentToken)
        self.hasLt = 1

    def __releaseLt(self):
        if base.localAvatar.getParent().compareTo(self.parentingNode) == 0:
            base.localAvatar.b_setParent(ToontownGlobals.SPRender)
            base.localAvatar.controlManager.currentControls.doDeltaPos()
        self.hasLt = 0

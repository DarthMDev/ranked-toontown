from panda3d.core import ModifierButtons
from direct.showbase.DirectObject import DirectObject

class ArrowKeys(DirectObject):
    UP_INDEX = 0
    DOWN_INDEX = 1
    LEFT_INDEX = 2
    RIGHT_INDEX = 3
    JUMP_INDEX = 4
    NULL_HANDLERS = (None, None, None, None, None)

    def __init__(self):
        self.__jumpPost = 0
        self.setPressHandlers(self.NULL_HANDLERS)
        self.setReleaseHandlers(self.NULL_HANDLERS)
        self.origMb = base.buttonThrowers[0].node().getModifierButtons()
        base.buttonThrowers[0].node().setModifierButtons(ModifierButtons())
        self.enable()

    def enable(self):
        self.disable()
        # Accept both binds for each control
        up_binds = base.settings.getControlBinds("MOVE_UP")
        down_binds = base.settings.getControlBinds("MOVE_DOWN")
        left_binds = base.settings.getControlBinds("MOVE_LEFT")
        right_binds = base.settings.getControlBinds("MOVE_RIGHT")
        jump_binds = base.settings.getControlBinds("JUMP")
        
        for bind in up_binds:
            if bind:
                self.accept(bind, self.__upKeyPressed)
        for bind in down_binds:
            if bind:
                self.accept(bind, self.__downKeyPressed)
        for bind in left_binds:
            if bind:
                self.accept(bind, self.__leftKeyPressed)
        for bind in right_binds:
            if bind:
                self.accept(bind, self.__rightKeyPressed)
        for bind in jump_binds:
            if bind:
                self.accept(bind, self.__jumpKeyPressed)

    def disable(self):
        self.__upPressed = 0
        self.__downPressed = 0
        self.__leftPressed = 0
        self.__rightPressed = 0
        self.__jumpPressed = 0
        
        # Ignore all binds for each control
        up_binds = base.settings.getControlBinds("MOVE_UP")
        down_binds = base.settings.getControlBinds("MOVE_DOWN")
        left_binds = base.settings.getControlBinds("MOVE_LEFT")
        right_binds = base.settings.getControlBinds("MOVE_RIGHT")
        jump_binds = base.settings.getControlBinds("JUMP")
        
        for bind in up_binds:
            if bind:
                self.ignore(bind)
                self.ignore(bind + '-up')
        for bind in down_binds:
            if bind:
                self.ignore(bind)
                self.ignore(bind + '-up')
        for bind in left_binds:
            if bind:
                self.ignore(bind)
                self.ignore(bind + '-up')
        for bind in right_binds:
            if bind:
                self.ignore(bind)
                self.ignore(bind + '-up')
        for bind in jump_binds:
            if bind:
                self.ignore(bind)
                self.ignore(bind + '-up')

    def destroy(self):
        base.buttonThrowers[0].node().setModifierButtons(self.origMb)
        # Get all binds for each control
        up_binds = base.settings.getControlBinds("MOVE_UP")
        down_binds = base.settings.getControlBinds("MOVE_DOWN")
        left_binds = base.settings.getControlBinds("MOVE_LEFT")
        right_binds = base.settings.getControlBinds("MOVE_RIGHT")
        jump_binds = base.settings.getControlBinds("JUMP")
        
        all_events = up_binds + down_binds + left_binds + right_binds + jump_binds
        for event in all_events:
            if event:
                self.ignore(event)
                self.ignore(event + '-up')

    def upPressed(self):
        return self.__upPressed

    def downPressed(self):
        return self.__downPressed

    def leftPressed(self):
        return self.__leftPressed

    def rightPressed(self):
        return self.__rightPressed

    def jumpPressed(self):
        return self.__jumpPressed

    def jumpPost(self):
        jumpCache = self.__jumpPost
        self.__jumpPost = 0
        return jumpCache

    def setPressHandlers(self, handlers):
        if len(handlers) == 4:
            handlers.append(None)
        self.__checkCallbacks(handlers)
        self.__pressHandlers = handlers
        return

    def setReleaseHandlers(self, handlers):
        if len(handlers) == 4:
            handlers.append(None)
        self.__checkCallbacks(handlers)
        self.__releaseHandlers = handlers
        return

    def clearPressHandlers(self):
        self.setPressHandlers(self.NULL_HANDLERS)

    def clearReleaseHandlers(self):
        self.setReleaseHandlers(self.NULL_HANDLERS)

    def __checkCallbacks(self, callbacks):
        for callback in callbacks:
            pass

    def __doCallback(self, callback):
        if callback:
            callback()

    def __upKeyPressed(self):
        # Ignore all up binds and accept their -up events
        up_binds = base.settings.getControlBinds("MOVE_UP")
        for bind in up_binds:
            if bind:
                self.ignore(bind)
                self.accept(bind + '-up', self.__upKeyReleased)
        self.__upPressed = 1
        self.__doCallback(self.__pressHandlers[self.UP_INDEX])

    def __downKeyPressed(self):
        # Ignore all down binds and accept their -up events
        down_binds = base.settings.getControlBinds("MOVE_DOWN")
        for bind in down_binds:
            if bind:
                self.ignore(bind)
                self.accept(bind + '-up', self.__downKeyReleased)
        self.__downPressed = 1
        self.__doCallback(self.__pressHandlers[self.DOWN_INDEX])

    def __leftKeyPressed(self):
        # Ignore all left binds and accept their -up events
        left_binds = base.settings.getControlBinds("MOVE_LEFT")
        for bind in left_binds:
            if bind:
                self.ignore(bind)
                self.accept(bind + '-up', self.__leftKeyReleased)
        self.__leftPressed = 1
        self.__doCallback(self.__pressHandlers[self.LEFT_INDEX])

    def __rightKeyPressed(self):
        # Ignore all right binds and accept their -up events
        right_binds = base.settings.getControlBinds("MOVE_RIGHT")
        for bind in right_binds:
            if bind:
                self.ignore(bind)
                self.accept(bind + '-up', self.__rightKeyReleased)
        self.__rightPressed = 1
        self.__doCallback(self.__pressHandlers[self.RIGHT_INDEX])

    def __jumpKeyPressed(self):
        # Ignore all jump binds and accept their -up events
        jump_binds = base.settings.getControlBinds("JUMP")
        for bind in jump_binds:
            if bind:
                self.ignore(bind)
                self.accept(bind + '-up', self.__jumpKeyReleased)
        self.__jumpPressed = 1
        self.__jumpPost = 1
        self.__doCallback(self.__pressHandlers[self.JUMP_INDEX])

    def __upKeyReleased(self):
        # Re-accept all up binds
        up_binds = base.settings.getControlBinds("MOVE_UP")
        for bind in up_binds:
            if bind:
                self.ignore(bind + '-up')
                self.accept(bind, self.__upKeyPressed)
        self.__upPressed = 0
        self.__doCallback(self.__releaseHandlers[self.UP_INDEX])

    def __downKeyReleased(self):
        # Re-accept all down binds
        down_binds = base.settings.getControlBinds("MOVE_DOWN")
        for bind in down_binds:
            if bind:
                self.ignore(bind + '-up')
                self.accept(bind, self.__downKeyPressed)
        self.__downPressed = 0
        self.__doCallback(self.__releaseHandlers[self.DOWN_INDEX])

    def __leftKeyReleased(self):
        # Re-accept all left binds
        left_binds = base.settings.getControlBinds("MOVE_LEFT")
        for bind in left_binds:
            if bind:
                self.ignore(bind + '-up')
                self.accept(bind, self.__leftKeyPressed)
        self.__leftPressed = 0
        self.__doCallback(self.__releaseHandlers[self.LEFT_INDEX])

    def __rightKeyReleased(self):
        # Re-accept all right binds
        right_binds = base.settings.getControlBinds("MOVE_RIGHT")
        for bind in right_binds:
            if bind:
                self.ignore(bind + '-up')
                self.accept(bind, self.__rightKeyPressed)
        self.__rightPressed = 0
        self.__doCallback(self.__releaseHandlers[self.RIGHT_INDEX])

    def __jumpKeyReleased(self):
        # Re-accept all jump binds
        jump_binds = base.settings.getControlBinds("JUMP")
        for bind in jump_binds:
            if bind:
                self.ignore(bind + '-up')
                self.accept(bind, self.__jumpKeyPressed)
        self.__jumpPressed = 0
        self.__jumpPost = 0
        self.__doCallback(self.__releaseHandlers[self.JUMP_INDEX])

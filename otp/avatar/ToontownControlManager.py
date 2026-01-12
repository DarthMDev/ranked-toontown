from direct.controls.ControlManager import ControlManager
from direct.directnotify import DirectNotifyGlobal
from direct.showbase.InputStateGlobal import inputState


class ToontownControlManager(ControlManager):
    notify = DirectNotifyGlobal.directNotify.newCategory("TTControlManager")

    def __init__(self, enable=True):
        self.forceTokens = None
        self.craneControlsEnabled = False
        super().__init__(enable)

    def enable(self):
        assert self.notify.debugCall(id(self))

        if self.isEnabled:
            assert self.notify.debug('already isEnabled')
            return

        self.isEnabled = 1

        self.enableControls()

        # keep track of what we do on the inputState so we can undo it later on
        # self.inputStateTokens = []

        controls = base.controls
        # Get both binds for each control
        up_binds = base.settings.getControlBinds("MOVE_UP")
        down_binds = base.settings.getControlBinds("MOVE_DOWN")
        left_binds = base.settings.getControlBinds("MOVE_LEFT")
        right_binds = base.settings.getControlBinds("MOVE_RIGHT")
        jump_binds = base.settings.getControlBinds("JUMP")
        
        # Removed arrow key fallback checks - arrow keys now only work if explicitly bound

        # Build tokens list with all binds
        tokens = [
            inputState.watch("run", 'runningEvent', "running-on", "running-off"),
            inputState.watch("forward", "force-forward", "force-forward-stop"),
            inputState.watch("turnLeft", "mouse-look_left", "mouse-look_left-done"),
            inputState.watch("turnLeft", "force-turnLeft", "force-turnLeft-stop"),
            inputState.watch("turnRight", "mouse-look_right", "mouse-look_right-done"),
            inputState.watch("turnRight", "force-turnRight", "force-turnRight-stop"),
        ]
        
        # Register all forward binds
        for bind in up_binds:
            if bind:
                tokens.append(inputState.watchWithModifiers("forward", bind, inputSource=inputState.ArrowKeys))
        
        # Register all reverse binds
        for bind in down_binds:
            if bind:
                tokens.append(inputState.watchWithModifiers("reverse", bind, inputSource=inputState.ArrowKeys))
        tokens.append(inputState.watchWithModifiers("reverse", "mouse4", inputSource=inputState.Mouse))
        
        # Register all turnLeft binds
        for bind in left_binds:
            if bind:
                tokens.append(inputState.watchWithModifiers("turnLeft", bind, inputSource=inputState.ArrowKeys))
        
        # Register all turnRight binds
        for bind in right_binds:
            if bind:
                tokens.append(inputState.watchWithModifiers("turnRight", bind, inputSource=inputState.ArrowKeys))
        
        # Register all jump binds
        for bind in jump_binds:
            if bind:
                tokens.append(inputState.watchWithModifiers("jump", bind))
        
        self.inputStateTokens.extend(tokens)

        # Removed hardcoded arrow key fallbacks - arrow keys now only work if explicitly bound by the user

        self.setTurn(1)

        if self.currentControls:
            self.currentControls.enableAvatarControls()

    def enableControls(self):
        if self.forceTokens:
            for token in self.forceTokens:
                token.release()
            self.forceTokens = []

    def disableControls(self):
        self.forceTokens = [
            inputState.force('jump', 0, 'TTControlManager.disableControls'),
            inputState.force('forward', 0, 'TTControlManager.disableControls'),
            inputState.force('turnLeft', 0, 'TTControlManager.disableControls'),
            inputState.force('slideLeft', 0, 'TTControlManager.disableControls'),
            inputState.force('reverse', 0, 'TTControlManager.disableControls'),
            inputState.force('turnRight', 0, 'TTControlManager.disableControls'),
            inputState.force('slideRight', 0, 'TTControlManager.disableControls')
        ]

    def setTurn(self, turn):
        self.__WASDTurn = turn

        if not self.isEnabled:
            return

        turnLeftWASDSet = inputState.isSet("turnLeft", inputSource=inputState.ArrowKeys)
        turnRightWASDSet = inputState.isSet("turnRight", inputSource=inputState.ArrowKeys)
        slideLeftWASDSet = inputState.isSet("slideLeft", inputSource=inputState.ArrowKeys)
        slideRightWASDSet = inputState.isSet("slideRight", inputSource=inputState.ArrowKeys)

        for token in self.WASDTurnTokens:
            token.release()

        # Get both binds for left and right
        left_binds = base.settings.getControlBinds("MOVE_LEFT")
        right_binds = base.settings.getControlBinds("MOVE_RIGHT")

        if turn:
            turn_tokens = []
            # Register all turnLeft binds
            for bind in left_binds:
                if bind:
                    turn_tokens.append(inputState.watchWithModifiers("turnLeft", bind, inputSource=inputState.ArrowKeys))
            # Register all turnRight binds
            for bind in right_binds:
                if bind:
                    turn_tokens.append(inputState.watchWithModifiers("turnRight", bind, inputSource=inputState.ArrowKeys))
            
            # Removed hardcoded arrow key fallbacks - arrow keys now only work if explicitly bound by the user
            
            self.WASDTurnTokens = tuple(turn_tokens)

            inputState.set("turnLeft", slideLeftWASDSet, inputSource=inputState.ArrowKeys)
            inputState.set("turnRight", slideRightWASDSet, inputSource=inputState.ArrowKeys)

            inputState.set("slideLeft", False, inputSource=inputState.ArrowKeys)
            inputState.set("slideRight", False, inputSource=inputState.ArrowKeys)

        else:
            slide_tokens = []
            # Register all slideLeft binds
            for bind in left_binds:
                if bind:
                    slide_tokens.append(inputState.watchWithModifiers("slideLeft", bind, inputSource=inputState.ArrowKeys))
            # Register all slideRight binds
            for bind in right_binds:
                if bind:
                    slide_tokens.append(inputState.watchWithModifiers("slideRight", bind, inputSource=inputState.ArrowKeys))
            
            # Removed hardcoded arrow key fallbacks - arrow keys now only work if explicitly bound by the user
            
            self.WASDTurnTokens = tuple(slide_tokens)

            inputState.set("slideLeft", turnLeftWASDSet, inputSource=inputState.ArrowKeys)
            inputState.set("slideRight", turnRightWASDSet, inputSource=inputState.ArrowKeys)

            inputState.set("turnLeft", False, inputSource=inputState.ArrowKeys)
            inputState.set("turnRight", False, inputSource=inputState.ArrowKeys)

    def enableCraneControls(self):
        """
        This function should only be called for when our controls are disabled,
        but we need to map our movement keys to functions. (i.e. on a crane, on a banquet table, etc.)
        This serves as an improved implementation of 'passMessagesThrough'.
        """

        if self.isEnabled and self.craneControlsEnabled:
            return

        # Get both binds for each control
        up_binds = base.settings.getControlBinds("MOVE_UP")
        down_binds = base.settings.getControlBinds("MOVE_DOWN")
        left_binds = base.settings.getControlBinds("MOVE_LEFT")
        right_binds = base.settings.getControlBinds("MOVE_RIGHT")

        crane_tokens = []
        
        # Register all forward binds
        for bind in up_binds:
            if bind:
                crane_tokens.append(inputState.watchWithModifiers("forward", bind, inputSource=inputState.ArrowKeys))
        
        # Register all reverse binds
        for bind in down_binds:
            if bind:
                crane_tokens.append(inputState.watchWithModifiers("reverse", bind, inputSource=inputState.ArrowKeys))
        
        # Register all turnLeft binds
        for bind in left_binds:
            if bind:
                crane_tokens.append(inputState.watchWithModifiers("turnLeft", bind, inputSource=inputState.ArrowKeys))
        
        # Register all turnRight binds
        for bind in right_binds:
            if bind:
                crane_tokens.append(inputState.watchWithModifiers("turnRight", bind, inputSource=inputState.ArrowKeys))
        
        # Removed hardcoded arrow key fallbacks - arrow keys now only work if explicitly bound by the user

        self.inputStateTokens.extend(crane_tokens)

    def disableCraneControls(self):
        """
        Disables crane controls.
        """

        if not self.isEnabled and not self.craneControlsEnabled:
            return

        for token in self.inputStateTokens:
            token.release()
        self.inputStateTokens = []

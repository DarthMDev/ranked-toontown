"""OptionsPage module: contains the OptionsPage class"""
import os
from enum import IntEnum, auto
from typing import Optional

from panda3d.core import TextNode, Vec4
from direct.directnotify import DirectNotifyGlobal
from direct.fsm.FSM import FSM
from direct.gui.DirectGui import *
from direct.showbase.MessengerGlobal import messenger

from toontown.chat.SpeedChatLocalizer import SpeedChatPhrases
from otp.speedchat.SpeedChatGlobals import speedChatStyles
from toontown.settings.Settings import Setting
from toontown.shtiker.ShtikerPage import ShtikerPage
from toontown.toonbase import TTLocalizer
from toontown.toontowngui import TTDialog
from toontown.toontowngui.ToontownScrolledFrame import ToontownScrolledFrame

from direct.distributed.ClockDelta import *


class OptionTypes(IntEnum):
    BUTTON = auto()
    DROPDOWN = auto()
    SLIDER = auto()
    CONTROL = auto()
    BUTTON_SPEEDCHAT = auto()


OptionToType = {
    # Gameplay
    'camSensitivityX': OptionTypes.SLIDER,
    'camSensitivityY': OptionTypes.SLIDER,
    'movement_mode': OptionTypes.BUTTON,
    'sprint_mode': OptionTypes.BUTTON,
    'fovEffects': OptionTypes.BUTTON,
    'cam-toggle-lock': OptionTypes.BUTTON,
    'speedchat-style': OptionTypes.BUTTON_SPEEDCHAT,
    'discord-rich-presence': OptionTypes.BUTTON,
    'archipelago-textsize': OptionTypes.SLIDER,
    'color-blind-mode': OptionTypes.BUTTON,
    'want-legacy-models': OptionTypes.BUTTON,
    'laff-display': OptionTypes.BUTTON,

    # Privacy
    "report-errors": OptionTypes.BUTTON,

    # Video
    "borderless": OptionTypes.BUTTON,
    "resolution": OptionTypes.DROPDOWN,
    "vertical-sync": OptionTypes.BUTTON,
    "anisotropic-filter": OptionTypes.DROPDOWN,
    "anti-aliasing": OptionTypes.DROPDOWN,
    "frame-rate-meter": OptionTypes.BUTTON,
    "fps-limit": OptionTypes.DROPDOWN,

    # Audio
    "music": OptionTypes.BUTTON,
    "sfx": OptionTypes.BUTTON,
    "music-volume": OptionTypes.SLIDER,
    "sfx-volume": OptionTypes.SLIDER,
    "toon-chat-sounds": OptionTypes.BUTTON,
}

# All control options are naturally going to be of the CONTROL option type,
# so let's fill the dictionary as such.
controls = list(base.settings.getControls())
OptionToType.update(dict(zip(controls, [OptionTypes.CONTROL for _ in range(len(controls))])))


class OptionsPage(ShtikerPage):
    """OptionsPage class"""

    notify = DirectNotifyGlobal.directNotify.newCategory("OptionsPage")

    # special methods
    def __init__(self):
        """__init__(self)
        OptionsPage constructor: create the options page
        """
        super().__init__()

        if __debug__:
            base.op = self

    def load(self):
        assert self.notify.debugStateCall(self)
        super().load()

        # Create the OptionsTabPage
        self.optionsTabPage = OptionsTabPage(self)
        self.optionsTabPage.hide()

        titleHeight = 0.6  # bigger number means higher the title
        self.title = DirectLabel(
            parent=self,
            relief=None,
            text=TTLocalizer.OptionsPageTitle,
            text_scale=0.12,
            pos=(0, 0, titleHeight),
        )

    def enter(self):
        assert self.notify.debugStateCall(self)

        messenger.send('wakeup')

        self.optionsTabPage.enter()

        # Make the call to the superclass enter method.
        super().enter()

    def exit(self):
        assert self.notify.debugStateCall(self)
        self.optionsTabPage.exit()

        # Make the call to the superclass exit method.
        super().exit()

    def unload(self):
        assert self.notify.debugStateCall(self)
        self.optionsTabPage.unload()

        # Cleanup the direct label.
        self.title.destroy()
        del self.title

        # Make the call to the superclass unload method.
        super().unload()


class OptionsTabPage(DirectFrame, FSM):
    tabOptions = {
        "Gameplay": [
            'camSensitivityX',
            'camSensitivityY',
            'movement_mode',
            'sprint_mode',
            'fovEffects',
            'cam-toggle-lock',
            'speedchat-style',
            'discord-rich-presence',
            'archipelago-textsize',
            'color-blind-mode',
            'want-legacy-models',
            'laff-display'

        ],
        "Privacy": [
            "report-errors"
        ],
        "Controls": [*list(base.settings.getControls())],
        "Video": [
            "borderless", "resolution", "vertical-sync", "anisotropic-filter",
            "anti-aliasing", "frame-rate-meter", "fps-limit",
        ],
        "Audio": [
            "music", "sfx", "music-volume", "sfx-volume", "toon-chat-sounds",
        ],
    }

    def __init__(self, parent=aspect2d, **kw):
        DirectFrame.__init__(self, parent, **kw)
        FSM.__init__(self, "OptionsTabPageNEW")

        self._parent = parent

        self.tabs: dict[str, DirectButton] = {}
        self.options: dict[str, OptionsScrolledFrame] = {}

        self.load()

    def load(self) -> None:
        # Load the Fish Page to borrow its tabs
        self.loadTabs(base.loader.loadModel("phase_3.5/models/gui/fishingBook"))
        # Load the "Exit Toontown" button
        self.createExitButton(base.loader.loadModel("phase_3/models/gui/quit_button"))
        # Load (& hide) the options frames
        self.createTabs(base.loader.loadModel("phase_3/models/gui/quit_button"))

    def loadTabs(self, gui):
        # The blue and yellow colors are trying to match the
        # rollover and select colors on the options page:
        normalColor = (1, 1, 1, 1)
        clickColor = (.8, .8, 0, 1)
        rolloverColor = (0.15, 0.82, 1.0, 1)
        disabledColor = (1.0, 0.98, 0.15, 1)

        initial = -0.175 * len(self.tabOptions)
        interval = 1.95 * (1 / len(self.tabOptions))

        for i, tab in enumerate(list(self.tabOptions)):
            x = initial + i * interval
            self.tabs[tab] = DirectButton(
                parent=self, relief=None, text=TTLocalizer.OptionsPageTabs[i],
                text_scale=0.06, text_align=TextNode.ACenter,
                text_pos=(0.1, 0.0, 0.0),
                image=gui.find("**/tabs/polySurface1"),
                image_pos=(0.525, 1, -0.91), image_hpr=(0, 0, -90),
                image_scale=(0.033, 0.033, 0.035),
                image_color=normalColor, image1_color=clickColor,
                image2_color=rolloverColor, image3_color=disabledColor,
                text_fg=Vec4(0.2, 0.1, 0, 1), command=self.request,
                extraArgs=[tab], pos=(x, 0, 0.77)
            )

        gui.remove_node()

    def createExitButton(self, gui) -> None:
        self.exitButton = DirectButton(
            parent=self, relief=None,
            image=(gui.find("**/QuitBtn_UP"),
                   gui.find("**/QuitBtn_DN"),
                   gui.find("**/QuitBtn_RLVR"),
                   ),
            image_scale=1.15,
            text=TTLocalizer.OptionsPageExitToontown,
            text_scale=0.052,
            text_pos=(0, -0.02),
            textMayChange=False,
            pos=(0.45, 0, -0.6),
            command=self.__handleExitShowWithConfirm,
        )

        gui.remove_node()

    def createTabs(self, gui) -> None:
        for tab, options in self.tabOptions.items():
            frame = OptionsScrolledFrame(parent=self._parent, options=options, gui=gui)
            frame.hide()
            self.options[tab] = frame

        gui.remove_node()

    def unload(self) -> None:
        for tab in self.tabs.values():
            tab.destroy()

        self.tabs = {}

        self.destroyOptions()

        self.exitButton.destroy()
        self.exitButton = None

    def enter(self) -> None:
        self.show()

        base.localAvatar.disableOldPieKeys()
        self.request("Gameplay")

    def exit(self) -> None:
        self.hide()
        self.request("Off")

        # Write the settings to the local JSON file.
        base.settings.write()
        base.localAvatar.resetPieKeys()
        base.localAvatar.updateOverhead()

    def updateTabs(self) -> None:
        messenger.send("wakeup")

        for tab in self.tabs.values():
            tab["state"] = DGG.NORMAL

        currState = self.getCurrentOrNextState()
        if currState in self.tabs:
            self.tabs[currState]["state"] = DGG.DISABLED

    def destroyOptions(self) -> None:
        for frame in self.options.values():
            frame.destroy()

        self.options = {}

    """
    FSM states
    """

    def enterGameplay(self) -> None:
        self.updateTabs()
        self.options["Gameplay"].show()

    def exitGameplay(self) -> None:
        self.options["Gameplay"].hide()

    def enterPrivacy(self) -> None:
        self.updateTabs()
        self.options["Privacy"].show()

    def exitPrivacy(self) -> None:
        self.options["Privacy"].hide()

    def enterControls(self) -> None:
        self.updateTabs()
        self.options["Controls"].show()

    def exitControls(self) -> None:
        self.options["Controls"].hide()

    def enterVideo(self) -> None:
        self.updateTabs()
        self.options["Video"].show()

    def exitVideo(self) -> None:
        self.options["Video"].hide()

    def enterAudio(self) -> None:
        self.updateTabs()
        self.options["Audio"].show()

    def exitAudio(self) -> None:
        self.options["Audio"].hide()

    """
    Exit button
    """

    def __handleExitShowWithConfirm(self):
        # For exiting from the options panel to the avatar chooser.
        """__handleExitShowWithConfirm(self)
        """
        self.confirm = TTDialog.TTGlobalDialog(
            doneEvent="confirmDone",
            message=TTLocalizer.OptionsPageExitConfirm,
            style=TTDialog.TwoChoice)
        self.confirm.show()
        self._parent.doneStatus = {
            "mode": "exit",
            "exitTo": "closeShard"}
        self.accept("confirmDone", self.__handleConfirm)

    def __handleConfirm(self):
        """__handleConfirm(self)
        """
        status = self.confirm.doneStatus
        self.ignore("confirmDone")
        self.confirm.cleanup()
        del self.confirm
        if (status == "ok"):
            base.cr._userLoggingOut = True
            messenger.send(self._parent.doneEvent)
            # self.cr.loginFSM.request("chooseAvatar", [self.cr.avList])


class OptionsScrolledFrame(ToontownScrolledFrame):
    width = 0.8
    height = 0.53

    def __init__(self, parent=None, options: list[str] = None, gui=None, **kw) -> None:
        super().__init__(
            parent, relief=None,
            pos=(0, 0, 0),
            canvasSize=(-self.width, self.width, -self.height, self.height),
            frameSize=(-self.width, self.width, -self.height, self.height),
            **kw
        )
        self.initialiseoptions(OptionsScrolledFrame)

        self.optionNames = options or []

        self.optionElements = []
        for index, option in enumerate(self.optionNames):
            element = OptionElement(parent, parent=self.getCanvas(), name=option, index=index, gui=gui)
            self.bindToScroll(element)
            self.optionElements.append(element)

        optionAmt = len(self.optionElements)

        # Update the scrollbar if there are more than x elements.
        canvasHeight = ((optionAmt * 0.1) - self.height) if optionAmt > 10 else self.height

        self["canvasSize"] = (-self.width, self.width, -canvasHeight, self.height)
        self.setCanvasSize()

    def destroy(self) -> None:
        if hasattr(self, "optionElements"):
            for option in self.optionElements:
                option.destroy()
            del self.optionElements

        super().destroy()


class DropdownScrolledFrame(ToontownScrolledFrame):
    width = 0.3
    height = 0.3
    offset = 0.225

    def __init__(self, optionName: str, parent=None, pos=(0, 0, 0), options: list[str] = None, command=None, **kw
                 ) -> None:
        super().__init__(
            parent, relief=None,
            pos=(pos[0], pos[1], pos[2] - self.offset),
            canvasSize=(-self.width, self.width, -self.height, self.height),
            frameSize=(-self.width, self.width, -self.height, self.height),
            **kw
        )
        self.initialiseoptions(DropdownScrolledFrame)

        self.optionName = optionName
        self.optionNames = options or []

        gui = base.loader.loadModel("phase_3/models/gui/quit_button")

        self.optionElements = []
        for index, option in enumerate(self.optionNames):
            element = DirectButton(
                parent=self.getCanvas(), relief=None, pos=(0, 0, self.offset - (index * 0.1)),
                text=self.formatSetting(option),
                text_scale=0.052, image_pos=(0, 0, 0.02),
                image=(
                    gui.find("**/QuitBtn_UP"),
                    gui.find("**/QuitBtn_DN"),
                    gui.find("**/QuitBtn_RLVR"),
                ),
                image_scale=(0.7, 1, 1),
                command=command, extraArgs=[option]
            )
            self.bindToScroll(element)
            self.optionElements.append(element)

        gui.remove_node()

        optionAmt = len(self.optionElements)

        # Update the scrollbar if there are more than x elements.
        canvasHeight = ((optionAmt * 0.1) - self.height) if optionAmt > 4 else self.height

        self["canvasSize"] = (-self.width, self.width, -canvasHeight, self.height)
        self.setCanvasSize()

        base.transitions.fadeScreen(0.5)

    def formatSetting(self, setting: Setting) -> str:
        """Given the type of setting we're dealing with, handle
        how the text on the button will display.
        """
        if isinstance(setting, list):
            # When dealing with list options, strip the brackets and
            # join the parts together.
            if self.optionName == "resolution":
                string = "x"
            else:
                string = ""

            return string.join([str(e) for e in setting]).replace("[", "").replace("[", "")
        elif isinstance(setting, int):
            # We're most likely dealing with a list of integer settings,
            # so return the string from the localizer given the current setting.
            if self.optionName == "anti-aliasing":
                return TTLocalizer.OptionAntiAlias[setting]
            if self.optionName == "anisotropic-filter":
                return TTLocalizer.OptionAnisotropic[setting]
            if self.optionName == "fps-limit":
                return TTLocalizer.OptionFPSLimit[setting]

        return str(setting)

    def destroy(self) -> None:
        if hasattr(self, "optionElements"):
            for option in self.optionElements:
                option.destroy()
            del self.optionElements

        base.transitions.noFade()

        super().destroy()


class OptionElement(DirectFrame):
    """
    Option types:
    Button: Clicking on the button will scroll through the options
    - i.e (true, false), (red, yellow, orange, blue, green), etc.
    Slider: Slide between two extremes
    - i.e (0% vol, 100% vol), (50 fov, 150 fov), etc.

    See toontown.settings.Settings.py for the default settings.
    """

    optionOptions = {}
    for option, default in base.settings.defaultSettings.items():
        if isinstance(default, bool):
            optionOptions[option] = [True, False]
        elif option == "movement_mode":
            optionOptions[option] = ["TTCC", "TTR"]
        elif option == "sprint_mode":
            optionOptions[option] = ["Hold", "Toggle"]

    optionOptions.update({
        "resolution": base.possibleScreenSizes,
        "anisotropic-filter": list(TTLocalizer.OptionAnisotropic),
        "anti-aliasing": list(TTLocalizer.OptionAntiAlias),
        "fps-limit": list(TTLocalizer.OptionFPSLimit)
    })

    def __init__(self, page, parent, name: str, index: int, gui, **kw):
        super().__init__(parent, **kw)

        self.page = page

        # The name of the setting.
        self.optionName = name
        self.optionType = OptionToType[self.optionName]

        if self.optionType == OptionTypes.CONTROL:
            # For controls, we'll handle the display differently with two buttons
            currSetting = None  # Not used for controls
        elif self.optionType == OptionTypes.BUTTON_SPEEDCHAT:
            currSetting = self.formatSpeedchat(base.localAvatar.getSpeedChatStyleIndex())
        else:
            currSetting = base.settings.get(name)

        z = 0.45 - (index * 0.1)

        # Make the label which will appear on the left-hand side of
        # the page.
        self.label = DirectLabel(
            parent=self, relief=None, pos=(-0.4, 0, z),
            text=TTLocalizer.OptionNames[self.optionName],
            text_scale=0.052,
        )

        # A separate frame for dropdown options which contains a list of option buttons.
        self.dropdownFrame: Optional[DropdownScrolledFrame] = None

        # Make the button(s) which will appear on the right-hand side of
        # the page.
        if self.optionType == OptionTypes.CONTROL:
            # For controls, create two buttons (primary and secondary bind)
            self.optionModifier = DirectButton(
                parent=self, relief=None, pos=(0.25, 0, z),
                text=self.formatKeybind(base.settings.getControl(self.optionName)),
                text_scale=0.052, image_pos=(0, 0, 0.02),
                image=(
                    gui.find("**/QuitBtn_UP"),
                    gui.find("**/QuitBtn_DN"),
                    gui.find("**/QuitBtn_RLVR"),
                ),
                image_scale=(0.6, 1, 1),
            )
            self.optionModifier["command"] = self._updateButtonOption
            
            # Secondary bind button
            self.optionModifier2 = DirectButton(
                parent=self, relief=None, pos=(0.49, 0, z),
                text=self.formatKeybind(base.settings.getControlBinds(self.optionName)[1] or "None"),
                text_scale=0.052, image_pos=(0, 0, 0.02),
                image=(
                    gui.find("**/QuitBtn_UP"),
                    gui.find("**/QuitBtn_DN"),
                    gui.find("**/QuitBtn_RLVR"),
                ),
                image_scale=(0.6, 1, 1),
            )
            self.optionModifier2["command"] = self._updateButtonOption2
            
            self.checkForDuplicates()
            self.accept("controls_findDuplicates", self.checkForDuplicates)
            self.registeringBindIndex = 0  # Track which bind we're currently setting
        elif self.optionType in (OptionTypes.BUTTON, OptionTypes.BUTTON_SPEEDCHAT, OptionTypes.DROPDOWN):
            self.optionModifier = DirectButton(
                parent=self, relief=None, pos=(0.37, 0, z),
                text=self.formatSetting(currSetting),
                text_scale=0.052, image_pos=(0, 0, 0.02),
                image=(
                    gui.find("**/QuitBtn_UP"),
                    gui.find("**/QuitBtn_DN"),
                    gui.find("**/QuitBtn_RLVR"),
                ),
                image_scale=(0.7, 1, 1),
            )
            if self.optionType == OptionTypes.DROPDOWN:
                self.optionModifier["command"] = self._openDropdown
            else:
                self.optionModifier["command"] = self._updateButtonOption
        # Make the slider which will appear on the right-hand side of
        # the page.
        elif self.optionType == OptionTypes.SLIDER:
            self.optionModifier = DirectSlider(
                parent=self, relief=DGG.SUNKEN, pos=(0.37, 0, z), thumb_relief=None,
                thumb_image_scale=(0.3, 0.8, 0.8),
                frameSize=(-0.25, 0.25, -0.1, 0.1),
                image_pos=(0, 0, 0.02),
                thumb_image=(
                    gui.find("**/QuitBtn_UP"),
                    gui.find("**/QuitBtn_DN"),
                    gui.find("**/QuitBtn_RLVR"),
                ),
                value=currSetting,
                command=self._updateSliderOption,
            )

            self.sliderLabel = DirectLabel(
                parent=self.optionModifier, relief=None, pos=(0.3, 0, -0.01),
                text=str(round(currSetting * 100)), text_scale=0.052,
            )
        else:
            raise Exception(f"Undefined option type: {self.optionType}")

        self.controlTask = ""

    def destroy(self) -> None:
        self.doneRegisterKey()

        self.ignore("controls_findDuplicates")

        if hasattr(self, "sliderLabel"):
            self.sliderLabel.destroy()
            del self.sliderLabel

        self.optionModifier.destroy()
        del self.optionModifier
        
        if hasattr(self, "optionModifier2"):
            self.optionModifier2.destroy()
            del self.optionModifier2

        self.label.destroy()
        del self.label

        super().destroy()

    @staticmethod
    def formatKeybind(keybind: str) -> str:
        if not keybind:
            return "None"
        return " ".join(keybind.split("_")).title()

    @staticmethod
    def formatSpeedchat(index: int) -> str:
        return SpeedChatPhrases[speedChatStyles[index][0]]

    def formatSetting(self, setting: Setting) -> str:
        """Given the type of setting we're dealing with, handle
        how the text on the button will display.
        """
        if isinstance(setting, list):
            # When dealing with list options, strip the brackets and
            # join the parts together.
            if self.optionName == "resolution":
                string = "x"
            else:
                string = ""

            return string.join([str(e) for e in setting]).replace("[", "").replace("[", "")
        elif isinstance(setting, bool):
            return TTLocalizer.OptionEnabled if setting else TTLocalizer.OptionDisabled
        elif isinstance(setting, int):
            # We're most likely dealing with a list of integer settings,
            # so return the string from the localizer given the current setting.
            if self.optionName == "anti-aliasing":
                return TTLocalizer.OptionAntiAlias[setting]
            if self.optionName == "anisotropic-filter":
                return TTLocalizer.OptionAnisotropic[setting]
            if self.optionName == "fps-limit":
                return TTLocalizer.OptionFPSLimit[setting]

        return str(setting)

    def registerKey(self, keybind: str, mouse=None, bind_index: int = 0) -> None:
        """
        Called when we are in the accepting keybind state. If mouse param is not None, that means this was a mouse button
        event and the keybind parameter is garbage. A bit hacky, but it makes event cleanup and management easier.
        Args:
            keybind: The keybind string
            mouse: Mouse button if this was a mouse event
            bind_index: Which bind to set (0 for primary, 1 for secondary)
        """
        print(f"[DEBUG] registerKey called: control={self.optionName}, keybind={keybind}, mouse={mouse}, bind_index={bind_index}")
        
        if mouse is not None:
            keybind = mouse
            print(f"[DEBUG] Using mouse keybind: {keybind}")
        
        # Clear the registering flags to prevent controls_stopListening from interfering
        if hasattr(self, '_registeringPrimary'):
            self._registeringPrimary = False
        if hasattr(self, '_registeringSecondary'):
            self._registeringSecondary = False
        
        # Ignore controls_stopListening before saving to prevent it from interfering
        self.ignore("controls_stopListening")
        
        # Get current binds before setting
        old_binds = base.settings.getControlBinds(self.optionName)
        print(f"[DEBUG] Old binds for {self.optionName}: {old_binds}")
        
        # Save the keybind
        base.settings.setControl(self.optionName, keybind, bind_index)
        
        # Verify it was saved
        new_binds = base.settings.getControlBinds(self.optionName)
        print(f"[DEBUG] New binds for {self.optionName}: {new_binds}")
        print(f"[DEBUG] Setting bind_index {bind_index} to '{keybind}', result: {new_binds[bind_index] if len(new_binds) > bind_index else 'OUT OF RANGE'}")
        
        # Update the UI
        self.doneRegisterKey(bind_index)

    def doneRegisterKey(self, bind_index: int = 0) -> None:
        print(f"[DEBUG] doneRegisterKey called: control={self.optionName}, bind_index={bind_index}")
        self.ignore("controls_stopListening")
        if hasattr(self, "controlTask"):
            self.ignore(self.controlTask)
        messenger.send("enable-hotkeys")

        if self.optionType == OptionTypes.CONTROL:
            # Update the appropriate button
            if bind_index == 0:
                primary = base.settings.getControl(self.optionName)
                print(f"[DEBUG] Updating primary bind display: {primary}")
                self.optionModifier.configure(
                    text=self.formatKeybind(primary),
                    image_color=Vec4(1, 1, 1, 1),
                )
            elif bind_index == 1:
                binds = base.settings.getControlBinds(self.optionName)
                print(f"[DEBUG] Current binds when updating secondary: {binds}")
                secondary_bind = binds[1] if len(binds) > 1 and binds[1] else ""
                print(f"[DEBUG] Updating secondary bind display: '{secondary_bind}' (formatted: '{self.formatKeybind(secondary_bind)}')")
                self.optionModifier2.configure(
                    text=self.formatKeybind(secondary_bind),
                    image_color=Vec4(1, 1, 1, 1),
                )
        else:
            self.optionModifier.configure(
                text=self.formatKeybind(base.settings.getControl(self.optionName)),
                image_color=Vec4(1, 1, 1, 1),
            )

        messenger.send("controls_findDuplicates")

    def checkForDuplicates(self) -> None:
        """Iterate through our control schema to find if there are any
        duplicates. In the case that there is, change the button color
        to RED, to indicate that.
        """
        if self.optionType != OptionTypes.CONTROL:
            return
            
        currentBinds = base.settings.getControlBinds(self.optionName)
        all_controls = base.settings.getControls()
        
        # Check primary bind
        primary_has_duplicate = False
        if currentBinds[0]:
            for control, keybinds in all_controls.items():
                if control == self.optionName:
                    continue
                # Handle both old (string) and new (list) formats
                if isinstance(keybinds, str):
                    if keybinds == currentBinds[0]:
                        primary_has_duplicate = True
                        break
                elif isinstance(keybinds, list):
                    if currentBinds[0] in keybinds:
                        primary_has_duplicate = True
                        break
        
        # Check secondary bind
        secondary_has_duplicate = False
        if len(currentBinds) > 1 and currentBinds[1]:
            for control, keybinds in all_controls.items():
                if control == self.optionName:
                    continue
                # Handle both old (string) and new (list) formats
                if isinstance(keybinds, str):
                    if keybinds == currentBinds[1]:
                        secondary_has_duplicate = True
                        break
                elif isinstance(keybinds, list):
                    if currentBinds[1] in keybinds:
                        secondary_has_duplicate = True
                        break
        
        # Update button colors
        self.optionModifier["image_color"] = Vec4(1, 0.1, 0.1, 1) if primary_has_duplicate else Vec4(1, 1, 1, 1)
        if hasattr(self, "optionModifier2"):
            self.optionModifier2["image_color"] = Vec4(1, 0.1, 0.1, 1) if secondary_has_duplicate else Vec4(1, 1, 1, 1)

    def _openDropdown(self) -> None:
        self.dropdownFrame = DropdownScrolledFrame(
            self.optionName, parent=self.page, pos=self.optionModifier.getPos(),
            options=self.optionOptions[self.optionName],
            command=self._updateDropdownOption
        )
        self.dropdownFrame.setBin('gui-popup', 5000)

    def _updateDropdownOption(self, newSetting) -> None:
        if self.dropdownFrame is not None:
            self.dropdownFrame.destroy()
            self.dropdownFrame = None

        # Update the new setting.
        base.settings.set(self.optionName, newSetting)

        if self.optionName in ("resolution", "anisotropic-filter"):
            base.updateDisplay()
        elif self.optionName == "fps-limit":
            if newSetting != 0:
                globalClock.setMode(ClockObject.MLimited)
                globalClock.setFrameRate(newSetting)
            else:
                globalClock.setMode(ClockObject.MNormal)

        # Update the button text with the new setting.
        self.optionModifier["text"] = self.formatSetting(newSetting)

    def _updateButtonOption(self) -> None:
        """Handle primary bind button click"""
        messenger.send("wakeup")

        if self.optionType == OptionTypes.CONTROL:
            # Tell any controls that are listening for input to stop doing that.
            messenger.send("controls_stopListening")
            # Then, listen for that same message on this control in the case
            # of another control being clicked.
            # Store bind_index in a way that the lambda can access it correctly
            bind_idx = 0
            
            # Create a flag to track if we're currently registering
            self._registeringPrimary = True
            
            def handleStopListening():
                # Only call doneRegisterKey if we're still registering
                # This prevents it from being called after the keybind is saved
                if hasattr(self, '_registeringPrimary') and self._registeringPrimary:
                    self._registeringPrimary = False
                    self.doneRegisterKey(bind_idx)
            
            self.accept("controls_stopListening", handleStopListening)

            self.controlTask = f"{self.optionName}-updateControl-0"
            self.registeringBindIndex = 0

            self.optionModifier.configure(text='...', image_color=Vec4(0.2, 0.9, 0.9, 1))

            bt = base.buttonThrowers[0].node()
            mw = base.buttonThrowers[0].getParent().node()
            bt.setButtonDownEvent(self.controlTask)
            mw.setButtonDownPattern(self.controlTask)

            messenger.send("disable-hotkeys")
            # Use the existing registerKey method with the bind_index
            # The event handler receives the keybind as the first argument
            # We need to create a wrapper that calls registerKey with the correct bind_index
            def registerKeyWrapper(keybind, mouse=None):
                # Mark that we're no longer registering (keybind was received)
                if hasattr(self, '_registeringPrimary'):
                    self._registeringPrimary = False
                # Ignore controls_stopListening before registering to prevent interference
                self.ignore("controls_stopListening")
                # Call registerKey with the correct bind_index
                self.registerKey(keybind, mouse, 0)  # Use 0 directly instead of bind_idx to avoid closure issues
            
            self.accept(self.controlTask, registerKeyWrapper)
            return

    def _updateButtonOption2(self) -> None:
        """Handle secondary bind button click"""
        print(f"[DEBUG] _updateButtonOption2 called for {self.optionName}")
        messenger.send("wakeup")

        if self.optionType == OptionTypes.CONTROL:
            # Tell any controls that are listening for input to stop doing that.
            messenger.send("controls_stopListening")
            # Then, listen for that same message on this control in the case
            # of another control being clicked.
            # Store bind_index in a way that the lambda can access it correctly
            bind_idx = 1
            
            # Create a flag to track if we're currently registering
            self._registeringSecondary = True
            print(f"[DEBUG] Set _registeringSecondary = True for {self.optionName}")
            
            def handleStopListening():
                print(f"[DEBUG] handleStopListening called for {self.optionName}, _registeringSecondary={getattr(self, '_registeringSecondary', 'NOT SET')}")
                # Only call doneRegisterKey if we're still registering
                # This prevents it from being called after the keybind is saved
                if hasattr(self, '_registeringSecondary') and self._registeringSecondary:
                    print(f"[DEBUG] Calling doneRegisterKey(1) from handleStopListening")
                    self._registeringSecondary = False
                    self.doneRegisterKey(bind_idx)
                else:
                    print(f"[DEBUG] Skipping doneRegisterKey - not registering or already registered")
            
            self.accept("controls_stopListening", handleStopListening)

            self.controlTask = f"{self.optionName}-updateControl-1"
            self.registeringBindIndex = 1
            print(f"[DEBUG] Set controlTask to: {self.controlTask}")

            self.optionModifier2.configure(text='...', image_color=Vec4(0.2, 0.9, 0.9, 1))

            bt = base.buttonThrowers[0].node()
            mw = base.buttonThrowers[0].getParent().node()
            bt.setButtonDownEvent(self.controlTask)
            mw.setButtonDownPattern(self.controlTask)
            print(f"[DEBUG] Set buttonDownEvent and pattern to: {self.controlTask}")

            messenger.send("disable-hotkeys")
            # Use the existing registerKey method with the bind_index
            # The event handler receives the keybind as the first argument
            # We need to create a wrapper that calls registerKey with the correct bind_index
            def registerKeyWrapper(keybind, mouse=None):
                print(f"[DEBUG] registerKeyWrapper called for {self.optionName}: keybind={keybind}, mouse={mouse}")
                # Mark that we're no longer registering (keybind was received)
                if hasattr(self, '_registeringSecondary'):
                    self._registeringSecondary = False
                    print(f"[DEBUG] Set _registeringSecondary = False")
                # Ignore controls_stopListening before registering to prevent interference
                self.ignore("controls_stopListening")
                # Call registerKey with the correct bind_index
                self.registerKey(keybind, mouse, 1)  # Use 1 directly instead of bind_idx to avoid closure issues
            
            self.accept(self.controlTask, registerKeyWrapper)
            print(f"[DEBUG] Accepted event: {self.controlTask}")
            return

        elif self.optionType == OptionTypes.BUTTON_SPEEDCHAT:
            # Increment the speedchat index.
            current = base.localAvatar.getSpeedChatStyleIndex()
            new = current + 1
            if new >= len(speedChatStyles):
                new = 0

            # We handle this differently, as it gets saved on the toon itself.
            base.localAvatar.b_setSpeedChatStyleIndex(new)

            # Update the button text with the new setting.
            self.optionModifier["text"] = self.formatSpeedchat(new)
            return

        # Get the current setting.
        currSetting = base.settings.get(self.optionName)

        # Get the index of the next element of the list of options
        # for this setting.
        index = self.optionOptions[self.optionName].index(currSetting) + 1

        # If it's beyond the scope, set it to 0.
        if index >= len(self.optionOptions[self.optionName]):
            index = 0

        # Index into the options with the new index.
        newSetting = self.optionOptions[self.optionName][index]

        # Update the new setting.
        base.settings.set(self.optionName, newSetting)

        # Update the client with the new value.
        if self.optionName == "music":
            base.enableMusic(newSetting)
        elif self.optionName == "sfx":
            base.enableSoundEffects(newSetting)
        elif self.optionName == "toon-chat-sounds":
            base.toonChatSounds = newSetting
        elif self.optionName == 'report-errors':
            os.environ['WANT_ERROR_REPORTING'] = 'true' if newSetting else 'false'
        elif self.optionName in ("borderless", "vertical-sync"):
            base.updateDisplay()
        elif self.optionName == "frame-rate-meter":
            base.setFrameRateMeter(newSetting)
        elif self.optionName == "movement_mode":
            base.localAvatar.updateMovementMode()
        elif self.optionName == "fovEffects":
            base.WANT_FOV_EFFECTS = newSetting
        elif self.optionName == 'discord-rich-presence':
            pass
        elif self.optionName == "cam-toggle-lock":
            base.CAM_TOGGLE_LOCK = newSetting
        elif self.optionName == "color-blind-mode":
            base.colorBlindMode = newSetting
        elif self.optionName == "want-legacy-models":
            base.WANT_LEGACY_MODELS = newSetting
        elif self.optionName == "laff-display":
            base.laffMeterDisplay = newSetting

        # Update the button text with the new setting.
        self.optionModifier["text"] = self.formatSetting(newSetting)

    def _updateSliderOption(self) -> None:
        messenger.send("wakeup")

        newSetting = self.optionModifier["value"]

        # Save the new option and update the gui.
        if self.optionName == "music-volume":
            base.musicManager.setVolume(newSetting ** 2)
        elif self.optionName == "sfx-volume":
            for sfm in base.sfxManagerList:
                sfm.setVolume(newSetting ** 2)

        self.sliderLabel["text"] = str(round(newSetting * 100))
        base.settings.set(self.optionName, newSetting)

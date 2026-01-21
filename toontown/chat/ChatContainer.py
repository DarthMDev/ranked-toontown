import dataclasses
import random
import re
import time
from typing import Callable

from direct.gui import DirectGuiGlobals
from direct.gui.DirectEntry import DirectEntry
from direct.gui.DirectScrolledFrame import DirectScrolledFrame
from direct.gui.DirectButton import DirectButton
from direct.interval.FunctionInterval import Wait, Func
from direct.interval.LerpInterval import LerpColorScaleInterval
from direct.interval.MetaInterval import Sequence
from panda3d.core import TextNode, PGButton, MouseButton, PGMouseWatcherParameter

from toontown.archipelago.util import global_text_properties
from toontown.archipelago.util.global_text_properties import MinimalJsonMessagePart
from toontown.spellbook import MagicWordConfig


@dataclasses.dataclass
class ChatMessageAuthor:
    avId: int
    name: str

class ChatContainerMessage(DirectButton):

    WORDWRAP = 25

    TEXT_HORIZONTAL_OFFSET = -.4
    TEXT_SCALE = 0.3
    VERTICAL_PADDING_PER_LINE = .3

    SCROLL_SPEED = .075

    def __init__(self, author: ChatMessageAuthor, content: str, **kwargs):
        self.author: ChatMessageAuthor | None = author
        kwargs['text'] = f"{content}"
        kwargs['text_wordwrap'] = self.WORDWRAP
        kwargs['relief'] = DirectGuiGlobals.RAISED
        kwargs['text_pos'] = (0, self.TEXT_HORIZONTAL_OFFSET)
        kwargs['text_align'] = TextNode.ALeft
        kwargs['text_scale'] = self.TEXT_SCALE
        kwargs['relief'] = DirectGuiGlobals.TEXTUREBORDER
        kwargs['text_fg'] = (.9, .9, .9, 1)
        kwargs['text_shadow'] = (0, 0, 0, 1)
        kwargs['frameSize'] = (-0.1, 7.75, -.55, -.1)
        kwargs['command'] = self.__handleClicked
        super().__init__(**kwargs)
        self.initialiseoptions(ChatContainerMessage)
        self['frameSize'] = (-0.1, 7.75, -.3 - self.VERTICAL_PADDING_PER_LINE * self.getNumLines(), -.1)
        self.fadeSeq = None
        self.addBackground()
        self.fadeOutLater()
        self['state'] = DirectGuiGlobals.DISABLED
        self.scrollFunc: Callable | None = None

    def toggleHoverFunctionality(self, enable: bool):
        if enable:
            self.bind(DirectGuiGlobals.ENTER, self.__handleEnterHover)
            self.bind(DirectGuiGlobals.EXIT, self.__handleExitHover)
        else:
            self.unbind(DirectGuiGlobals.ENTER)
            self.unbind(DirectGuiGlobals.EXIT)

    def __handleEnterHover(self, _):
        WHEELUP = PGButton.getReleasePrefix() + MouseButton.wheelUp().getName() + '-'
        WHEELDOWN = PGButton.getReleasePrefix() + MouseButton.wheelDown().getName() + '-'
        self.bind(WHEELUP, lambda _: self.scrollFunc(-self.SCROLL_SPEED) if self.scrollFunc is not None else None)
        self.bind(WHEELDOWN, lambda _: self.scrollFunc(self.SCROLL_SPEED) if self.scrollFunc is not None else None)
        self.addBackground((.5, .5, .5, .75))

    def __handleExitHover(self, _):
        self.clearBackground()
        WHEELUP = PGButton.getReleasePrefix() + MouseButton.wheelUp().getName() + '-'
        WHEELDOWN = PGButton.getReleasePrefix() + MouseButton.wheelDown().getName() + '-'
        self.unbind(WHEELUP)
        self.unbind(WHEELDOWN)

    def getNumLines(self):
        return self.component('text0').textNode.getWordwrappedText().count('\n') + 1

    def clearBackground(self):
        self.__cleanupFadeSequence()
        self['frameColor'] = (0, 0, 0, 0)
        self.setColorScale(1, 1, 1, 1)

    def addBackground(self, color=(.1, .1, .1, .5)):
        self.__cleanupFadeSequence()
        self['frameColor'] = color
        self.setColorScale(1, 1, 1, 1)

    def __cleanupFadeSequence(self):
        if self.fadeSeq is not None:
            self.fadeSeq.finish()
            self.fadeSeq = None

    def fadeOutLater(self):
        self.__cleanupFadeSequence()
        self.fadeSeq = Sequence(
            Wait(10),
            LerpColorScaleInterval(self, 3, (1, 1, 1, 0)),
        )
        self.fadeSeq.start()

    def __handleClicked(self):
        if self.author is None:
            return

        av = base.cr.getDo(self.author.avId)
        if av is not None:
            messenger.send('clickedNametag', sentArgs=[av])

        if self.author.avId != base.localAvatar.getDoId():
            base.localAvatar.chatMgr.whisperTo(self.author.name, self.author.avId)

    def destroy(self):
        super().destroy()
        self.unbind(DirectGuiGlobals.EXIT)
        self.ignoreAll()


class ChatContainer(DirectScrolledFrame):

    FRAME_COLOR = (0.1, 0.1, 0.1, .5)
    FRAME_SIZE = (-0.003, .803, 0, .5)
    FRAME_POS = (0.05, 0, -0.55)
    INPUT_HEIGHT = .06
    INPUT_COLOR = (0.1, 0.1, 0.1, .75)

    SCROLLBAR_WIDTH = .0345
    SCROLLBAR_COLOR = (.4, .4, .4, .5)

    TOP_MESSAGE_ANCHOR = 0.0
    MESSAGE_HORIZONTAL_PADDING = 0.01

    # Change this to update how often we should hold on to messages.
    MESSAGE_CACHE_LIMIT = 100

    # Change this to set the sfx for when a message is added.
    MESSAGE_SFX_PATH = 'phase_3/audio/sfx/GUI_balloon_popup.ogg'

    INITIAL_PREFIX = global_text_properties.get_colored_string(' All: ', color='blue')

    def __init__(self, **kwargs):
        if 'frameColor' not in kwargs:
            kwargs['frameColor'] = self.FRAME_COLOR
        if 'frameSize' not in kwargs:
            kwargs['frameSize'] = self.FRAME_SIZE
        if 'pos' not in kwargs:
            kwargs['pos'] = self.FRAME_POS

        kwargs['manageScrollBars'] = True
        kwargs['scrollBarWidth'] = self.SCROLLBAR_WIDTH
        kwargs['canvasSize'] = (self.FRAME_SIZE[0], self.FRAME_SIZE[1]-self.SCROLLBAR_WIDTH, 0, self.FRAME_SIZE[3])

        kwargs['verticalScroll_relief'] = None
        kwargs['verticalScroll_manageButtons'] = False
        kwargs['verticalScroll_thumb_frameColor'] = self.SCROLLBAR_COLOR
        kwargs['verticalScroll_thumb_relief'] = DirectGuiGlobals.TEXTUREBORDER
        kwargs['verticalScroll_incButton_relief'] = None
        kwargs['verticalScroll_decButton_relief'] = None

        kwargs['horizontalScroll_incButton_relief'] = None
        kwargs['horizontalScroll_decButton_relief'] = None
        kwargs['horizontalScroll_thumb_relief'] = None
        kwargs['horizontalScroll_manageButtons'] = False
        kwargs['horizontalScroll_thumb_frameColor'] = (0, 0, 0, 0)

        super().__init__(**kwargs)
        self.initialiseoptions(ChatContainer)

        self._input_prefix = self.INITIAL_PREFIX
        self._input = DirectEntry(
            parent=self,
            scale=.03,
            frameColor=self.INPUT_COLOR,
            pos=(0, 0, -.04),
            text_pos=(0.01, 0.024),
            text_fg=(.9, .9, .9, 1),
            width=25,
            overflow=True,
            initialText=self.INITIAL_PREFIX,
            textMayChange=True,
            command=self.__handleInputSent
        )
        self._starting_cursor_position = self._input.getCursorPosition()
        self._input.bind(DirectGuiGlobals.TYPE, self.__onType)
        self._input.bind(DirectGuiGlobals.ERASE, self.__onErase)

        self._speedchat = DirectButton(
            parent=self._input,
            pos=(26, 0, 0.38),
            text='...',
            text_scale=1,
            text_pos=(0, -.075),
            text_fg=(.9, .9, .9, 1),
            text_shadow=(0, 0, 0, 1),
            frameSize=(-.7525, .7525, -.7525, .7525),
            frameColor=self.INPUT_COLOR,
            relief=DirectGuiGlobals.TEXTUREBORDER,
            command=self.__handleSpeedchatClicked,
            clickSound=None
        )

        self._messages: list[ChatContainerMessage] = []
        self._msg_sfx = loader.loadSfx(self.MESSAGE_SFX_PATH)
        self._msg_sfx.setVolume(.5)

        self.isActive = True
        # If this set to an instance of an author, the next message we send will whisper to them instead of talk.
        self._whisperTarget: ChatMessageAuthor | None = None

        self.deactivate()


    def activate(self):
        """
        Focuses the chatbox and chatlog for chat entry and interaction
        """
        self['frameColor'] = self.FRAME_COLOR
        self._input.show()
        self._speedchat.show()
        self.isActive = True
        self._input['focus'] = True
        self['verticalScroll_thumb_frameColor'] = self.SCROLLBAR_COLOR
        for msg in self._messages:
            msg.toggleHoverFunctionality(True)
            msg.clearBackground()
            msg['state'] = DirectGuiGlobals.NORMAL
        self.acceptOnce('escape', self.__handleEscapePressedWhileTyping)

    def deactivate(self):
        """
        Unfocuses the chatbox and chatlog.
        """
        self['frameColor'] = (0, 0, 0, 0)
        self._input.hide()
        self._speedchat.hide()
        self['verticalScroll_thumb_frameColor'] = (0, 0, 0, 0)
        for msg in self._messages:
            msg.addBackground()
            msg.toggleHoverFunctionality(False)
            msg.fadeOutLater()
            msg['state'] = DirectGuiGlobals.DISABLED
        self.ignore('escape')
        self.isActive = False
        base.localAvatar.chatMgr.chatInputSpeedChat.hide()

    def setPrefix(self, prefix: str):
        """
        Sets the prefix of the chat input. By default, this usually just says "All: " But it can be changed to fit
        whatever needs you have.
        """
        old_input = self._input.get()
        old_input_clean = self._input.get(plain=True)
        old_cursor_position = self._input.getCursorPosition()
        self._input.set(f"{prefix}{old_input.replace(self._input_prefix, '')}")
        self._input_prefix = prefix
        cursor_diff = len(self._input.get(plain=True)) - len(old_input_clean)
        self._input.setCursorPosition(old_cursor_position + cursor_diff)
        self._starting_cursor_position += cursor_diff

    def getWhisperTarget(self) -> ChatMessageAuthor | None:
        return self._whisperTarget

    def setWhisperTarget(self, target: ChatMessageAuthor | None = None):
        """
        Sets the state of the chatbox to prepare to send a whisper to a target instead of saying a message out loud.
        Pass in None to clear the current target and revert back to default behavior.
        """
        self._whisperTarget = target

        if target is not None:
            self.setPrefix(global_text_properties.get_colored_string(f" To {self._whisperTarget.name}: ", color='magenta'))
        else:
            self.setPrefix(self.INITIAL_PREFIX)

    def setInputText(self, text: str):
        self._input.set(f"{self._input_prefix}{text}")
        self._input.setCursorPosition(len(self._input.get(plain=True)))

    def __start_tracking_message(self, message: ChatContainerMessage):
        """
        Adds a message the log in the interface. Should be called everytime you construct a ChatContainerMessage and want to track it.
        """
        self._messages.append(message)
        if len(self._messages) > self.MESSAGE_CACHE_LIMIT:
            old = self._messages.pop(0)
            old.destroy()
        message.setScale(.1)
        message.reparentTo(self.getCanvas())
        message.scrollFunc = self.scrollFunc
        self._repositionMessages()
        self._msg_sfx.play()

        if self.isActive:
            message.toggleHoverFunctionality(True)
            message.clearBackground()
            message['state'] = DirectGuiGlobals.NORMAL
        else:
            self.verticalScroll['value'] = 1

    def addRawMessage(self, text: str, author: ChatMessageAuthor = None):
        """
        Adds raw text to the log. Can be used for various purposes. Pass in an author to emulate whisper clicking
        behavior when the entry is clicked.
        """
        self.__start_tracking_message(ChatContainerMessage(author, text))

    def addDefaultMessage(self, author: ChatMessageAuthor, message: str, nameColor: str | tuple | None=None, italicize: bool = False):
        """
        Adds a new message to the chat log with the default format.
        nameColor parameter can either be a tuple or a JSON color string key.
        """
        name = author.name if author.avId != base.localAvatar.getDoId() else 'You'
        namePrefix = name + ": " if nameColor is None \
            else global_text_properties.get_colored_string(name + ": ", color=nameColor) if isinstance(nameColor, str) \
            else global_text_properties.create_text_with_undefined_color(name + ": ", color=nameColor)
        if italicize:
            message = global_text_properties.get_colored_string(message, color='bold')
        allText = namePrefix + message
        self.addRawMessage(allText, author)

    def addOutgoingWhisper(self, recipient: ChatMessageAuthor, message: str, italicize: bool = False):
        """
        Adds an outgoing whisper message to the chat log.
        """
        if message is None or len(message) == 0:
            return
        text = global_text_properties.get_colored_string(f"To {recipient.name}: ", color='yellow')
        if italicize:
            message = global_text_properties.get_colored_string(message, color='bold')
        self.addRawMessage(f"{text}{message}", recipient)

    def addIncomingWhisper(self, _from: ChatMessageAuthor, message: str, italicize: bool = False):
        """
        Adds an incoming whisper message to the chat log.
        """
        text = global_text_properties.get_colored_string(f"From {_from.name}: ", color='magenta')
        if italicize:
            message = global_text_properties.get_colored_string(message, color='bold')
        self.addRawMessage(f"{text}{message}", _from)
        base.playSfx(base.localAvatar.soundWhisper)

    def scrollFunc(self, multiplier):
        """
        Callable object that can be used to scroll the chat log up and down.
        Negative multiplier will "scroll up" while positive ones will scroll down.
        The multiplier should be a float between 0 and 1.
        """
        content_height = self['canvasSize'][3] - self['canvasSize'][2]
        view_height = self.FRAME_SIZE[3] - self.FRAME_SIZE[2]
        if content_height <= view_height:
            self.verticalScroll['value'] = 0.0
            return
        content_height = max(0, content_height)
        view_height = max(0, view_height)
        self.verticalScroll['value'] += multiplier / max(1, content_height-view_height)
        self.verticalScroll['value'] = min(max(0, self.verticalScroll['value']), 1)

    def _repositionMessages(self):
        """
        Utility method to reposition all the messages currently cached.
        """
        height_offset = 0
        height_offset += .015
        for message in reversed(self._messages):
            height_offset += abs(message.bounds[2] - message.bounds[3]) * message.getScale()[2]
            message.setPos(self.MESSAGE_HORIZONTAL_PADDING, 0, height_offset)

        self['canvasSize'] = (self.FRAME_SIZE[0], self.FRAME_SIZE[1]-self.SCROLLBAR_WIDTH, 0, max(self.FRAME_SIZE[3], height_offset))

    def __onType(self, mw: PGMouseWatcherParameter):
        """
        Handler for when the chatbox is typed into.
        """
        mw_prefix = global_text_properties.get_colored_string('execute ', 'yellow')
        if self._input.get().replace(self._input_prefix, '').startswith(MagicWordConfig.PREFIX_DEFAULT):
            if self._whisperTarget is not None:
                self.setWhisperTarget(None)

            if self._input_prefix != mw_prefix:
                self.setPrefix(mw_prefix)
        elif self._input_prefix == mw_prefix:
            self.setPrefix(self.INITIAL_PREFIX)

    def __onErase(self, mw: PGMouseWatcherParameter):
        """
        Handler for when the chatbox registers a backspace.
        """
        if self._input.getCursorPosition() < self._starting_cursor_position:
            self._input.set(self._input_prefix)
            self._input.setCursorPosition(self._starting_cursor_position)
            if self._whisperTarget is not None:
                self.setWhisperTarget(None)
            if self._input_prefix != self.INITIAL_PREFIX:
                self.setPrefix(self.INITIAL_PREFIX)

    def __handleEscapePressedWhileTyping(self):
        """
        Handler for when escape is pressed while the chatbox is focused.
        """
        if self._whisperTarget is not None:
            self._input.set(self._input_prefix)
        self.setWhisperTarget(None)
        base.localAvatar.chatMgr.fsm.request('mainMenu')

    def __handleInputSent(self, text):
        """
        Handler for when the text input registers an "enter" press.
        """
        text = text.replace(self._input_prefix, '')
        self._input.enterText(self._input_prefix)
        if self._whisperTarget is not None:
            base.talkAssistant.sendWhisperTalk(text, self._whisperTarget.avId)
            self.addOutgoingWhisper(self._whisperTarget, text)
        else:
            base.talkAssistant.sendOpenTalk(text)
        base.localAvatar.chatMgr.fsm.request('mainMenu')
        base.localAvatar.chatMgr.lastSendTime = time.time()
        if text is None or len(text) == 0:
            return
        self.verticalScroll['value'] = 1
        self.setWhisperTarget(None)

    def __handleSpeedchatClicked(self):
        """
        Handler for when the speedchat shortcut button is clicked.
        """
        base.localAvatar.chatMgr.openScSfx.play()
        if base.localAvatar.chatMgr.chatInputSpeedChat.isHidden():
            base.localAvatar.chatMgr.chatInputSpeedChat.show()
        else:
            base.localAvatar.chatMgr.chatInputSpeedChat.hide()




if __name__ == "__main__":
    from direct.gui.DirectButton import DirectButton
    from direct.showbase.ShowBase import ShowBase

    class MyApp(ShowBase):

        def __init__(self):
            ShowBase.__init__(self)

            self.test_button = DirectButton(command=self.__test_action)
            self.test_button.reparentTo(self.aspect2d)

            # Test code goes here
            self.chatbox = ChatContainer(scale=1.25)
            self.chatbox.reparentTo(self.a2dLeftCenter)
            self.chatbox.activate()


        def __test_action(self):
            msg = ChatContainerMessage(
                ChatMessageAuthor(123, 'test user'),
                'a' * random.randint(10, 500),
            )
            self.chatbox.addDefaultMessage(msg)
            print(self.chatbox.verticalScroll['value'])


    app = MyApp()
    app.run()
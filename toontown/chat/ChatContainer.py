import dataclasses
import random
import time
from typing import Callable

from direct.gui import DirectGuiGlobals
from direct.gui.DirectEntry import DirectEntry
from direct.gui.DirectScrolledFrame import DirectScrolledFrame
from direct.gui.DirectButton import DirectButton
from direct.interval.FunctionInterval import Wait, Func
from direct.interval.LerpInterval import LerpColorScaleInterval
from direct.interval.MetaInterval import Sequence
from panda3d.core import TextNode, PGButton, MouseButton


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
        self.author: ChatMessageAuthor = author
        kwargs['text'] = f"{author.name}{content}"
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
        av = base.cr.getDo(self.author.avId)
        if av is not None:
            messenger.send('clickedNametag', sentArgs=[av])

    def destroy(self):
        super().destroy()
        self.unbind(DirectGuiGlobals.EXIT)
        self.ignoreAll()


class ChatContainer(DirectScrolledFrame):

    FRAME_COLOR = (0.1, 0.1, 0.1, .5)
    FRAME_SIZE = (-0.0035, .803, 0, .5)
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

        self._input = DirectEntry(
            parent=self,
            scale=.03,
            frameColor=self.INPUT_COLOR,
            pos=(0, 0, -.04),
            text_pos=(0.01, 0.02),
            text_fg=(.9, .9, .9, 1),
            width=25,
            overflow=True,
            command=self.__handle_input_sent
        )

        self._speedchat = DirectButton(
            parent=self._input,
            pos=(26, 0, 0.38),
            text='...',
            text_scale=1,
            text_pos=(0, -.075),
            text_fg=(.9, .9, .9, 1),
            text_shadow=(0, 0, 0, 1),
            frameSize=(-.76, .76, -.76, .76),
            frameColor=self.INPUT_COLOR,
            relief=DirectGuiGlobals.TEXTUREBORDER,
            command=self.__handle_speedchat_clicked,
            clickSound=None
        )

        self._messages: list[ChatContainerMessage] = []
        self._msg_sfx = loader.loadSfx(self.MESSAGE_SFX_PATH)
        self._msg_sfx.setVolume(.5)

        self.isActive = True
        self.deactivate()

    def activate(self):
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
        self.acceptOnce('escape', lambda : base.localAvatar.chatMgr.fsm.request('mainMenu'))

    def deactivate(self):
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

    def __handle_input_sent(self, text):
        self._input.enterText('')
        base.localAvatar.chatMgr.fsm.request('mainMenu')
        base.localAvatar.chatMgr.lastSendTime = time.time()
        if text is None or len(text) == 0:
            return
        self.verticalScroll['value'] = 1
        base.talkAssistant.sendOpenTalk(text)

    def __handle_speedchat_clicked(self):
        base.localAvatar.chatMgr.toggleSpeedChatMenu()

    def _reposition_messages(self):
        height_offset = 0
        height_offset += .015
        for message in reversed(self._messages):
            height_offset += abs(message.bounds[2] - message.bounds[3]) * message.getScale()[2]
            message.setPos(self.MESSAGE_HORIZONTAL_PADDING, 0, height_offset)

        self['canvasSize'] = (self.FRAME_SIZE[0], self.FRAME_SIZE[1]-self.SCROLLBAR_WIDTH, 0, max(self.FRAME_SIZE[3], height_offset))

    def add_message(self, message: ChatContainerMessage):
        self._messages.append(message)
        if len(self._messages) > self.MESSAGE_CACHE_LIMIT:
            old = self._messages.pop(0)
            old.destroy()
        message.setScale(.1)
        message.reparentTo(self.getCanvas())
        message.scrollFunc = self.scroll_func
        self._reposition_messages()
        self._msg_sfx.play()

        if self.isActive:
            message.toggleHoverFunctionality(True)
            message.clearBackground()
            message['state'] = DirectGuiGlobals.NORMAL
        else:
            self.verticalScroll['value'] = 1

    def add_entry(self, avId: int, text: str):
        """
        Adds raw text to the log. Can be used for various purposes.
        """
        self.add_message(ChatContainerMessage(ChatMessageAuthor(avId, ''), text))

    def scroll_func(self, multiplier):
        content_height = self['canvasSize'][3] - self['canvasSize'][2]
        view_height = self.FRAME_SIZE[3] - self.FRAME_SIZE[2]
        if content_height <= view_height:
            self.verticalScroll['value'] = 0.0
            return
        content_height = max(0, content_height)
        view_height = max(0, view_height)
        self.verticalScroll['value'] += multiplier / max(1, content_height-view_height)
        self.verticalScroll['value'] = min(max(0, self.verticalScroll['value']), 1)

if __name__ == "__main__":
    from direct.gui.DirectButton import DirectButton
    from direct.showbase.ShowBase import ShowBase

    class MyApp(ShowBase):

        def __init__(self):
            ShowBase.__init__(self)

            self.test_button = DirectButton(command=self.__test_action)
            self.test_button.reparentTo(self.aspect2d)

            # Test code goes here
            self.chatbox = ChatContainer()
            self.chatbox.reparentTo(self.a2dLeftCenter)


        def __test_action(self):
            msg = ChatContainerMessage(
                ChatMessageAuthor(123, 'test user'),
                'a' * random.randint(10, 500),
            )
            self.chatbox.add_message(msg)
            print(self.chatbox.verticalScroll['value'])


    app = MyApp()
    app.run()
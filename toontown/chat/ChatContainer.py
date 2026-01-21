import dataclasses
import random
import time

from direct.gui import DirectGuiGlobals
from direct.gui.DirectEntry import DirectEntry
from direct.gui.DirectScrolledFrame import DirectScrolledFrame
from direct.gui.DirectButton import DirectButton
from direct.interval.FunctionInterval import Wait, Func
from direct.interval.LerpInterval import LerpColorScaleInterval
from direct.interval.MetaInterval import Sequence
from panda3d.core import TextNode


@dataclasses.dataclass
class ChatMessageAuthor:
    avId: int
    name: str

class ChatContainerMessage(DirectButton):

    WORDWRAP = 25

    TEXT_HORIZONTAL_OFFSET = -.4
    TEXT_SCALE = 0.3
    VERTICAL_PADDING_PER_LINE = .3

    def __init__(self, author: ChatMessageAuthor, content: str, **kwargs):
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
        super().__init__(**kwargs)
        self.initialiseoptions(ChatContainerMessage)
        self['frameSize'] = (-0.1, 7.75, -.3 - self.VERTICAL_PADDING_PER_LINE * self.getNumLines(), -.1)
        self.fadeSeq = None
        self.addBackground()
        self.fadeOutLater()

    def toggleHoverFunctionality(self, enable: bool):
        if enable:
            self.bind(DirectGuiGlobals.ENTER, lambda _: self.addBackground((.5, .5, .5, .75)))
            self.bind(DirectGuiGlobals.EXIT, lambda _: self.clearBackground())
        else:
            self.unbind(DirectGuiGlobals.ENTER)
            self.unbind(DirectGuiGlobals.EXIT)

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

    def destroy(self):
        super().destroy()
        self.unbind(DirectGuiGlobals.EXIT)
        self.ignoreAll()


class ChatContainer(DirectScrolledFrame):

    FRAME_COLOR = (0.1, 0.1, 0.1, .5)
    FRAME_SIZE = (-0.0035, .803, 0, .5)
    FRAME_POS = (0.05, 0, -0.45)
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
            scale=7.5,
            frameColor=self.INPUT_COLOR,
            relief=DirectGuiGlobals.TEXTUREBORDER,
            command=self.__handle_send_clicked
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

    def __handle_send_clicked(self):
        self.__handle_input_sent(self._input['text'])

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
        self._reposition_messages()
        self._msg_sfx.play()

        if self.isActive:
            message.toggleHoverFunctionality(True)
            message.clearBackground()
        else:
            self.verticalScroll['value'] = 1

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
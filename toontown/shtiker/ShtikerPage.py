from . import ShtikerBook
from direct.fsm import StateData
from direct.gui.DirectGui import *
from panda3d.core import *

class ShtikerPage(DirectFrame, StateData.StateData):

    def __init__(self):
        DirectFrame.__init__(self, relief=None, sortOrder=DGG.BACKGROUND_SORT_INDEX)
        self.initialiseoptions(ShtikerPage)
        StateData.StateData.__init__(self, 'shtiker-page-done')
        self.book = None
        self.hide()
        return

    def load(self):
        pass

    def unload(self):
        self.ignoreAll()
        del self.book

    def enter(self):
        self.show()

    def exit(self):
        self.hide()

    def setBook(self, book):
        self.book = book

    def setPageName(self, pageName):
        self.pageName = pageName


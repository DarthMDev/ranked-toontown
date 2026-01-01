import webbrowser

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectGlobal import DistributedObjectGlobal
from direct.gui.DirectEntry import DirectEntry

from otp.distributed.PotentialAvatar import PotentialAvatar
from otp.otpgui.OTPDialog import OTPDialog, YesNo, CancelOnly
from otp.uberdog.authentication import AuthenticationGlobals
from toontown.toontowngui.TTDialog import TTDialog, TTGlobalDialog
from panda3d.core import WindowProperties


class GameServicesManager(DistributedObjectGlobal):
    notify = DirectNotifyGlobal.directNotify.newCategory('GameServicesManager')

    def __init__(self, cr):
        DistributedObjectGlobal.__init__(self, cr)
        self.doneEvent = None
        self._callback = None
        self.authenticationScheme: int = AuthenticationGlobals.AUTHENTICATION_SCHEME_DEVTOKEN
        self.session: str = ""
        self.link: str = ""
        self.discordAuthChoice = None
        self.playtokenInputEntry = None

    def d_requestAuthScheme(self):
        """
        Sends a request to the UD. The UD should tell us what authentication flow to proceed with.
        """
        self.sendUpdate('requestAuthScheme')

    def setAuthScheme(self, authScheme: int, session: str, link: str):
        """
        Called from the UD. Sets the authentication scheme that UD is doing and what we should proceed with.
        """
        self.authenticationScheme = authScheme
        self.session = session
        self.link = link
        messenger.send('authSchemeReceived')

    def getAuthenticationScheme(self) -> int:
        return self.authenticationScheme

    def login(self, doneEvent):
        self.doneEvent = doneEvent

        if self.authenticationScheme == AuthenticationGlobals.AUTHENTICATION_SCHEME_DEVTOKEN:
            self.__askForPlaytokenInput()
            return

        # If we are using discord authentication scheme, we actually need to use our discord access token.
        self.discordAuthChoice = TTGlobalDialog(
            message='Discord is required to login. Would you like to authenticate with Discord? If you choose Cancel, the game will close.\n\nClicking OK will open your web browser!',
            doneEvent='ackDiscordAuthChoice',
            style=YesNo,
            command=self.__handleDiscordAuthChoice
        )

    def __askForPlaytokenInput(self):
        self.discordAuthChoice = TTGlobalDialog(
            message="This server uses a username login scheme. Please enter a username!",
            doneEvent='ackDiscordAuthChoice',
            style=YesNo,
            command=self.__handlePlaytokenInput
        )
        self.playtokenInputEntry = DirectEntry(parent=self.discordAuthChoice, text="", scale=0.0625, pos=(-0.3, 0, -0.18),
                                 command=self.__determinePlaytokenAuthenticity,
                                 cursorKeys=1, obscured=1, initialText="Username", numLines=1, focus=1,
                                 focusInCommand=lambda : self.playtokenInputEntry.enterText(""))

    def __determinePlaytokenAuthenticity(self, text):
        if len(text) == 0:
            self.__askForPlaytokenInput()
            return
        self.d_login(text)

    def __handlePlaytokenInput(self, value):
        if value <= 0:
            exit(0)

        self.__determinePlaytokenAuthenticity(self.playtokenInputEntry.text())

    def __handleDiscordAuthChoice(self, value):
        # If they said yes, open a tab that will let the user log in. If they consent, they will be logged in!
        if value > 0:
            webbrowser.open_new_tab(f'{self.link}')
        else:
            exit(0)

        self.discordAuthChoice = TTGlobalDialog(
            message="Waiting for you to authenticate!",
            doneEvent='ackDiscordAuthChoiceWaiting',
            style=CancelOnly,
            command=lambda: self.__handleDiscordAuthChoice(0),
        )

    def d_login(self, playToken):
        self.sendUpdate('login', [playToken])

    def __bringToFront(self, wp):
        wp.setZOrder(WindowProperties.ZTop)
        base.win.requestProperties(wp)
        base.graphicsEngine.openWindows()

    def __bringToNormal(self, wp, task=None):
        wp.setZOrder(WindowProperties.ZNormal)
        base.win.requestProperties(wp)
        base.graphicsEngine.openWindows()

    def acceptLogin(self):
        # Bring window to foreground
        wp = WindowProperties()
        self.__bringToFront(wp)
        taskMgr.doMethodLater(0.5, self.__bringToNormal, 'bringToNormal', extraArgs=[wp])

        messenger.send(self.doneEvent, [{'mode': 'success'}])

        if self.discordAuthChoice is not None:
            self.discordAuthChoice.cleanup()
            self.discordAuthChoice = None

    def requestAvatarList(self):
        self.sendUpdate('requestAvatarList')

    def avatarListResponse(self, avatarList):
        avList = []
        for avatarInfo in avatarList:
            avNum, avName, avDNA, avPosition, nameState = avatarInfo

            nameOpen = int(nameState == 1)
            names = [avName, '', '', '']
            if nameState == 2:  # Pending
                names[1] = avName
            elif nameState == 3:  # Approved
                names[2] = avName
            elif nameState == 4:  # Rejected
                names[3] = avName

            avList.append(PotentialAvatar(avNum, names, avDNA, avPosition, nameOpen))

        self.cr.handleAvatarsList(avList)

    def requestRemoveAvatar(self, avId):
        self.sendUpdate('requestRemoveAvatar', [avId])

    def requestPlayAvatar(self, avId):
        self.sendUpdate('requestPlayAvatar', [avId])

    def receiveAccountDays(self, accountDays):
        base.cr.accountDays = accountDays

import builtins
import os
import re
import subprocess
import sys
import glob
from direct.showbase.DirectObject import DirectObject
from direct.gui.DirectGui import *
from otp.otpbase import OTPGlobals
from otp.otpgui import OTPDialog
from otp.otpbase.OTPLocalizer import (
    CREnterUsername,
    CRInvalidUsername,
    CREmptyUsername,
    CREnterGameserver,
    CREmptyGameserver,
    CRLoadingGameServices,
    CRSpecifyServerSelection,
    CRSingleplayer,
    CRLocalMultiplayer,
    CRPublicServer,
    CRSelectDatabaseBackend,
    CRFilesystem,
    CRMongoDB
)

class OpeningUserInput(DirectObject):
    def __init__(self, cr, launcher):
        self.cr = cr
        self.launcher = launcher
        self.dialogClass = OTPGlobals.getGlobalDialogClass()

        self.askServerPreference()

    def cleanup(dialogClass):
        dialogClass.cleanup()
        del dialogClass

    def clearText(self):
        self.entry.enterText('')

    def specifyGameserver(self, textEntered):
        gameserver = textEntered
        if not gameserver:
            base.startShow(self.cr, '127.0.0.1:7198')
        else:
            base.startShow(self.cr, gameserver)

    def localMultiplayerScreen(self):
        self.askForGameserver = self.dialogClass(message=CREnterGameserver, style=OTPDialog.NoButtons,
                                     doneEvent='cleanup', text_wordwrap=20, midPad=0.2, extraArgs=['askForGameserver'])
        self.accept('cleanup', self.cleanup, extraArgs=[self.askForGameserver])

        self.entry = DirectEntry(parent=self.askForGameserver , text="", scale=0.075, pos=(-0.6, 0, -0.3), command=self.specifyGameserver,
                                 width=16, cursorKeys=1, obscured=0, initialText="Gameserver", numLines=1, focus=1, focusInCommand=self.clearText)

        self.askForGameserver.show()

    def publicServerScreen(self):
        base.startShow(self.cr, config.ConfigVariableString('public-server-ip', '').getValue())

    def singlePlayerScreen(self):
        # Check if MongoDB is available
        mongodb_available = self.check_mongodb_available()
        
        if mongodb_available:
            # Show dialog to choose database backend
            self.askDatabaseBackend = self.dialogClass(
                message=CRSelectDatabaseBackend,
                style=OTPDialog.TwoChoiceCustom,
                text_wordwrap=25,
                okButtonText=CRFilesystem,
                cancelButtonText=CRMongoDB,
                doneEvent='databaseBackendSelected'
            )
            self.askDatabaseBackend.show()
            self.accept('databaseBackendSelected', self.onDatabaseBackendSelected)
        else:
            # MongoDB not available, use filesystem
            self.startDedicatedServer(useMongoDB=False)
    
    def check_mongodb_available(self):
        """Check if MongoDB is installed and running."""
        try:
            result = subprocess.run(
                ['mongod', '--version'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                # Also check if it's running by trying to connect
                try:
                    from pymongo import MongoClient
                    from pymongo.errors import ServerSelectionTimeoutError
                    client = MongoClient('mongodb://127.0.0.1:27017/', serverSelectionTimeoutMS=2000)
                    client.admin.command('ping')
                    client.close()
                    return True
                except Exception as e:
                    # MongoDB is installed but not running - still show option
                    # User can choose MongoDB and we'll warn them if it's not running
                    return True  # Return True to show the option, DedicatedServer will handle the check
        except FileNotFoundError:
            # Check common Windows installation paths
            if sys.platform == 'win32':
                import glob
                common_paths = [
                    r'C:\Program Files\MongoDB\Server\*\bin\mongod.exe',
                    r'C:\Program Files (x86)\MongoDB\Server\*\bin\mongod.exe',
                    os.path.expanduser(r'~\AppData\Local\Programs\MongoDB\Server\*\bin\mongod.exe'),
                ]
                for path_pattern in common_paths:
                    if glob.glob(path_pattern):
                        return True  # MongoDB is installed, show option
        except:
            pass
        return False
    
    def onDatabaseBackendSelected(self):
        """Handle database backend selection."""
        if not hasattr(self, 'askDatabaseBackend'):
            return
        
        # Check doneStatus: 'ok' = Filesystem (first button), 'cancel' = MongoDB (second button)
        status = self.askDatabaseBackend.doneStatus
        useMongoDB = (status == 'cancel')  # Second button (MongoDB)
        
        # Clean up dialog
        self.askDatabaseBackend.cleanup()
        del self.askDatabaseBackend
        self.ignore('databaseBackendSelected')
        
        # Start the server
        self.startDedicatedServer(useMongoDB=useMongoDB)
    
    def startDedicatedServer(self, useMongoDB=False):
        """Start the dedicated server with the specified database backend."""
        # Start DedicatedServer
        builtins.gameServicesDialog = self.dialogClass(message=CRLoadingGameServices)
        builtins.gameServicesDialog.show()

        from toontown.toonbase.DedicatedServer import DedicatedServer
        builtins.clientServer = DedicatedServer(localServer=True, useMongoDB=useMongoDB)
        builtins.clientServer.start()

        def localServerReady():
            builtins.gameServicesDialog.cleanup()
            del builtins.gameServicesDialog
            base.startShow(self.cr)

        self.accept('localServerReady', localServerReady)

    def decision(self, buttonValue = None):
        if buttonValue == -1: # buttonValue returning -1 will connect us to the Local Multiplayer server.
            self.localMultiplayerScreen()
        elif buttonValue == 0: # buttonValue returning 0 will connect us to the public server.
            self.publicServerScreen()
        elif buttonValue == 1: # buttonValue returning 1 will startup the Singleplayer server.
            self.singlePlayerScreen()

    def askServerPreference(self):

        # Is an env var set?
        gameserver = os.getenv('GAMESERVER')
        if gameserver is not None:
            base.startShow(self.cr, gameserver)
            return

        if not config.ConfigVariableBool('local-multiplayer', False).getValue():
            self.askServerSpecification = self.dialogClass(message=CRSpecifyServerSelection, style=OTPDialog.ThreeChoiceCustom,
                                                           yesButtonText=CRSingleplayer, noButtonText=CRPublicServer, cancelButtonText=CRLocalMultiplayer,
                                                           command=self.decision, doneEvent='cleanup', text_wordwrap=20, buttonPadSF=5)
            self.askServerSpecification.show()
            self.accept('cleanup', self.cleanup, extraArgs=[self.askServerSpecification])
            return

        # Default behavior
        if not self.launcher.isDummy():
            base.startShow(self.cr, self.launcher.getGameServer())
        else:
            base.startShow(self.cr)
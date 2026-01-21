from __future__ import annotations

import random
from typing import List

from libotp import *
from direct.interval.IntervalGlobal import *
from direct.distributed.ClockDelta import *
from direct.showbase.PythonUtil import *
from direct.gui.DirectGui import *
from direct.task import Task

from libotp.nametag import WhisperGlobals
from libotp.nametag.WhisperGlobals import WhisperType
from otp.avatar import LocalAvatar
from otp.login import LeaveToPayDialog
from otp.avatar import PositionExaminer
from otp.otpbase import OTPGlobals
from otp.avatar import DistributedPlayer
from toontown.shtiker import ShtikerBook
from toontown.shtiker import OptionsPage
from toontown.shtiker import FishPage
from toontown.shtiker import NametagPage
from toontown.quest import QuestParser
from toontown.toonbase.ToontownGlobals import *
from toontown.toonbase import ToontownGlobals
from toontown.toonbase import TTLocalizer
from toontown.chat import ToontownChatManager, ResistanceChat
from toontown.chat import TTTalkAssistant
from toontown.battle.BattleSounds import *
from toontown.toon import ElevatorNotifier
from toontown.shtiker import WordPage
from . import DistributedToon
from . import Toon
from . import LaffMeter
from toontown.archipelago.gui.ArchipelagoOnscreenLog import ArchipelagoOnscreenLog
from ..archipelago.definitions.color_profile import ColorProfile
from ..archipelago.definitions.death_reason import DeathReason
from ..archipelago.util import global_text_properties
from ..chat.ChatContainer import ChatContainer
from ..groups.GroupManager import GroupManager
from ..shtiker.LeaderboardPage import LeaderboardPage
from ..shtiker.ShtikerPage import ShtikerPage

class LocalToon(DistributedToon.DistributedToon, LocalAvatar.LocalAvatar):
    neverDisable = 1
    piePowerSpeed = base.config.GetDouble('pie-power-speed', 0.2)
    piePowerExponent = base.config.GetDouble('pie-power-exponent', 0.75)

    def __init__(self, cr):
        try:
            self.LocalToon_initialized
        except:
            self.LocalToon_initialized = 1
            self.neverSleep = False
            self.numFlowers = 0
            self.maxFlowerBasket = 0
            DistributedToon.DistributedToon.__init__(self, cr)
            chatMgr = ToontownChatManager.ToontownChatManager(cr, self)
            talkAssistant = TTTalkAssistant.TTTalkAssistant()
            LocalAvatar.LocalAvatar.__init__(self, cr, chatMgr, talkAssistant, passMessagesThrough=True)
            self.soundRun = base.loader.loadSfx('phase_3.5/audio/sfx/AV_footstep_runloop.ogg')
            self.soundWalk = base.loader.loadSfx('phase_3.5/audio/sfx/AV_footstep_walkloop.ogg')
            self.soundWhisper = base.loader.loadSfx('phase_3.5/audio/sfx/GUI_whisper_3.ogg')
            self.soundPhoneRing = base.loader.loadSfx('phase_3.5/audio/sfx/telephone_ring.ogg')
            self.soundSystemMessage = base.loader.loadSfx('phase_3/audio/sfx/clock03.ogg')
            self.positionExaminer = PositionExaminer.PositionExaminer()
            friendsGui = loader.loadModel('phase_3.5/models/gui/friendslist_gui')
            friendsButtonNormal = friendsGui.find('**/FriendsBox_Closed')
            friendsButtonPressed = friendsGui.find('**/FriendsBox_Rollover')
            friendsButtonRollover = friendsGui.find('**/FriendsBox_Rollover')
            newScale = oldScale = 0.8
            self.bFriendsList = DirectButton(image=(friendsButtonNormal, friendsButtonPressed, friendsButtonRollover), relief=None, pos=(-0.141, 0, -0.125), parent=base.a2dTopRight, scale=newScale, text=('', TTLocalizer.FriendsListLabel, TTLocalizer.FriendsListLabel), text_scale=0.09, text_fg=Vec4(1, 1, 1, 1), text_shadow=Vec4(0, 0, 0, 1), text_pos=(0, -0.18), text_font=ToontownGlobals.getInterfaceFont(), sortOrder=100, command=self.sendFriendsListEvent)
            self.bFriendsList.hide()
            self.friendsListButtonActive = 0
            self.friendsListButtonObscured = 0
            self.moveFurnitureButtonObscured = 0
            friendsGui.removeNode()
            self.__furnitureGui = None
            self.furnitureManager = None
            self.furnitureDirector = None
            Toon.loadDialog()
            self.isIt = 0
            self.cantLeaveGame = 0
            self.tunnelX = 0.0
            self.estate = None
            self.__pieBubble = None
            self.allowPies = 0
            self.__pieButton = None
            self.__piePowerMeter = None
            self.__piePowerMeterSequence = None
            self.__pieButtonType = None
            self.__pieButtonCount = None
            self.tossPieStart = None
            self.__trajectoryLine = None
            self.__trajectoryTarget = None
            self.__finalPiePower = None  # Store final power after charging stops
            self.__presentingPie = 0
            self.__pieSequence = 0
            self.__pieFlyNodes = {}  # Track flyPie and pieBubble by sequence for cleanup
            self.wantBattles = base.config.GetBool('want-battles', 1)
            self.seeGhosts = base.config.GetBool('see-ghosts', 0)
            wantNameTagAvIds = base.config.GetBool('want-nametag-avids', 0)
            if wantNameTagAvIds:
                messenger.send('nameTagShowAvId', [])
                base.idTags = 1
            self.glitchX = 0
            self.glitchY = 0
            self.glitchZ = 0
            self.glitchCount = 0
            self.ticker = 0
            self.glitchOkay = 1
            self.tempGreySpacing = 0
            self.wantStatePrint = base.config.GetBool('want-statePrint', 0)
            self.guiConflict = 0
            self.lastElevatorLeft = 0
            self.elevatorNotifier = ElevatorNotifier.ElevatorNotifier()
            self.accept(OTPGlobals.AvatarFriendAddEvent, self.sbFriendAdd)
            self.accept(OTPGlobals.AvatarFriendUpdateEvent, self.sbFriendUpdate)
            self.accept(OTPGlobals.AvatarFriendRemoveEvent, self.sbFriendRemove)
            self._zoneId = None
            self.accept('system message aknowledge', self.systemWarning)
            self.systemMsgAckGuiDoneEvent = 'systemMsgAckGuiDoneEvent'
            self.accept(self.systemMsgAckGuiDoneEvent, self.hideSystemMsgAckGui)
            self.systemMsgAckGui = None
            self.createSystemMsgAckGui()
            if not hasattr(base.cr, 'lastLoggedIn'):
                base.cr.lastLoggedIn = self.cr.toontownTimeManager.convertStrToToontownTime('')
            self.setLastTimeReadNews(base.cr.lastLoggedIn)
            self.acceptingNonFriendWhispers = (base.settings.get('accepting-non-friend-whispers') and
                                               base.config.GetBool('accepting-non-friend-whispers-default', True))
            self.physControls.event.addAgainPattern('again%in')
            self.oldPos = None
            self.prevToonIdx = 0
            self.teleporting = False
            self.camStart = [0, 0, 0, 0, 0, 0]
            self.camPoints = []
            self.camera = camera

            self.groupManager: GroupManager | None = None
            self.archipelagoLog: ArchipelagoOnscreenLog = None
            self.chatbox: ChatContainer | None = None
            self.currentlyInHQ = False
            self.wantCompetitiveBossScoring = base.settings.get('competitive-boss-scoring')
            self.accept("disableControls", self.disableControls)

            self.currentOnscreenInterface = None  # We can only exclusively show one hotkey interface at a time

            self.showPosInit()

    def wantLegacyLifter(self):
        return True

    def startGlitchKiller(self):
        if localAvatar.getZoneId() not in GlitchKillerZones:
            return
        if __dev__:
            self.glitchMessage = 'START GLITCH KILLER'
            randChoice = random.randint(0, 3)
            if randChoice == 0:
                self.glitchMessage = 'START GLITCH KILLER'
            elif randChoice == 1:
                self.glitchMessage = 'GLITCH KILLER ENGAGED'
            elif randChoice == 2:
                self.glitchMessage = 'GLITCH KILLER GO!'
            elif randChoice == 3:
                self.glitchMessage = 'GLITCH IN YO FACE FOOL!'
            self.notify.debug(self.glitchMessage)
        taskMgr.remove(self.uniqueName('glitchKiller'))
        taskMgr.add(self.glitchKiller, self.uniqueName('glitchKiller'))
        self.glitchOkay = 1

    def pauseGlitchKiller(self):
        self.tempGreySpacing = 1

    def unpauseGlitchKiller(self):
        self.tempGreySpacing = 0

    def stopGlitchKiller(self):
        if __dev__ and hasattr(self, 'glitchMessage'):
            if self.glitchMessage == 'START GLITCH KILLER':
                self.notify.debug('STOP GLITCH KILLER')
            elif self.glitchMessage == 'GLITCH KILLER ENGAGED':
                self.notify.debug('GLITCH KILLER DISENGAGED')
            elif self.glitchMessage == 'GLITCH KILLER GO!':
                self.notify.debug('GLITCH KILLER NO GO!')
            elif self.glitchMessage == 'GLITCH IN YO FACE FOOL!':
                self.notify.debug('GLITCH OFF YO FACE FOOL!')
        taskMgr.remove(self.uniqueName('glitchKiller'))
        self.glitchOkay = 1

    def glitchKiller(self, taskFooler = 0):
        if base.greySpacing or self.tempGreySpacing:
            return Task.cont
        self.ticker += 1
        if not self.physControls.lifter.hasContact() and not self.glitchOkay:
            self.glitchCount += 1
        else:
            self.glitchX = self.getX()
            self.glitchY = self.getY()
            self.glitchZ = self.getZ()
            self.glitchCount = 0
            if self.physControls.lifter.hasContact():
                self.glitchOkay = 0
        if hasattr(self, 'physControls'):
            if self.ticker >= 10:
                self.ticker = 0
        if self.glitchCount >= 7:
            print('GLITCH MAXED!!! resetting pos')
            self.setX(self.glitchX - 1 * (self.getX() - self.glitchX))
            self.setY(self.glitchY - 1 * (self.getY() - self.glitchY))
            self.glitchCount = 0
        return Task.cont

    def announceGenerate(self):
        self.startLookAround()
        if base.wantNametags:
            self.nametag.manage(base.marginManager)
        DistributedToon.DistributedToon.announceGenerate(self)

    def disable(self):
        # Clean up all pie fly nodes before disabling
        for sequence in list(self.__pieFlyNodes.keys()):
            self.__cleanupPieFlyNodes(sequence)
        self.laffMeter.destroy()
        del self.laffMeter
        if hasattr(self, 'purchaseButton'):
            self.purchaseButton.destroy()
            del self.purchaseButton
        self.book.unload()
        del self.optionsPage
        del self.nametagPage
        del self.fishPage
        del self.wordPage
        del self.book
        if base.wantNametags:
            self.nametag.unmanage(base.marginManager)
        taskMgr.removeTasksMatching('*ioorrd234*')
        self.chatbox.destroy()
        del self.chatbox
        self.archipelagoLog.destroy()
        del self.archipelagoLog
        self.ignoreAll()
        DistributedToon.DistributedToon.disable(self)

    def disableBodyCollisions(self):
        pass

    def delete(self):
        try:
            self.LocalToon_deleted
        except:
            self.LocalToon_deleted = 1
            self.cleanupShowPos()
            Toon.unloadDialog()
            QuestParser.clear()
            DistributedToon.DistributedToon.delete(self)
            LocalAvatar.LocalAvatar.delete(self)
            self.bFriendsList.destroy()
            del self.bFriendsList
            if self.__pieButton:
                self.__pieButton.destroy()
                self.__pieButton = None
            if self.__piePowerMeter:
                self.__piePowerMeter.destroy()
                self.__piePowerMeter = None
            self.__removeTrajectoryLine()
            self.__removeTrajectoryTarget()
            taskMgr.remove('lerpFurnitureButton')
            if self.__furnitureGui:
                self.__furnitureGui.destroy()
            del self.__furnitureGui
        return

    def initInterface(self):
        self.book = ShtikerBook.ShtikerBook('bookDone')
        self.book.load()
        self.book.hideButton()
        self.optionsPage = OptionsPage.OptionsPage()
        self.optionsPage.load()
        self.book.addPage(self.optionsPage, pageName=TTLocalizer.OptionsPageTitle)
        self.leaderboardPage = LeaderboardPage()
        self.leaderboardPage.load()
        self.book.addPage(self.leaderboardPage, pageName=TTLocalizer.LeaderboardPageTitle)
        self.fishPage = FishPage.FishPage()
        self.fishPage.setAvatar(self)
        self.fishPage.load()
        self.book.addPage(self.fishPage, pageName=TTLocalizer.FishPageTitle)
        # Load nametag page - always available
        self.nametagPage = NametagPage.NametagPage()
        self.nametagPage.load()
        self.book.addPage(self.nametagPage, pageName=TTLocalizer.NametagPageTitle)
        self.wordPage = WordPage.WordPage()
        self.wordPage.load()
        self.book.addPage(self.wordPage, pageName=TTLocalizer.SpellbookPageTitle)
        # self.book.setPage(self.mapPage, enterPage=False)
        self.laffMeter = LaffMeter.LaffMeter(self.style, self.hp, self.maxHp)
        self.laffMeter.setAvatar(self)
        self.laffMeter.setScale(0.075)
        self.laffMeter.reparentTo(base.a2dBottomLeft)
        if self.style.getAnimal() == 'monkey':
            self.laffMeter.setPos(0.153, 0.0, 0.13)
        else:
            self.laffMeter.setPos(0.133, 0.0, 0.13)
        self.laffMeter.stop()
        if not base.cr.isPaid():
            guiButton = loader.loadModel('phase_3/models/gui/quit_button')
            self.purchaseButton = DirectButton(parent=aspect2d, relief=None, image=(guiButton.find('**/QuitBtn_UP'), guiButton.find('**/QuitBtn_DN'), guiButton.find('**/QuitBtn_RLVR')), image_scale=0.9, text=TTLocalizer.OptionsPagePurchase, text_scale=0.05, text_pos=(0, -0.01), textMayChange=0, pos=(0.885, 0, -0.94), sortOrder=100, command=self.__handlePurchase)
            base.setCellsAvailable([base.bottomCells[4]], 0)

        self.archipelagoLog = ArchipelagoOnscreenLog()
        self.chatbox = ChatContainer(parent=base.a2dLeftCenter, scale=1.1)

        controls = base.controls
        # Accept both binds for SECONDARY_ACTION
        secondary_binds = base.settings.getControlBinds("SECONDARY_ACTION")
        for bind in secondary_binds:
            if bind:
                self.accept(bind, self.__zeroPowerToss)
        
        # Accept both binds for ACTION_BUTTON
        action_binds = base.settings.getControlBinds("ACTION_BUTTON")
        for bind in action_binds:
            if bind:
                self.accept('time-' + bind, self.__beginTossPie)
                self.accept('time-' + bind + '-up', self.__endTossPie)
        self.accept('pieHit', self.__pieHit)
        self.accept('interrupt-pie', self.interruptPie)
        self.accept('InputState-jump', self.__toonMoved)
        self.accept('InputState-forward', self.__toonMoved)
        self.accept('InputState-reverse', self.__toonMoved)
        self.accept('InputState-turnLeft', self.__toonMoved)
        self.accept('InputState-turnRight', self.__toonMoved)
        self.accept('InputState-slide', self.__toonMoved)
        QuestParser.init()
        return

    # Pass in a book page to give exclusive control for an onscreen hotkey interface
    # Pass in None to free up the on screen hotkey interface slot
    def setCurrentOnscreenInterface(self, interface):
        self.currentOnscreenInterface = interface

    # Returns a ShtickerPage instance that currently owns the onscreen page slot
    def getCurrentOnscreenInterface(self) -> ShtikerPage | None:
        return self.currentOnscreenInterface

    # True if no display via hotkey is currently displaying, False otherwise
    def allowOnscreenInterface(self) -> bool:
        return self.currentOnscreenInterface is None

    def __handlePurchase(self):
        self.purchaseButton.hide()
        if (base.cr.isWebPlayToken() or __dev__):
            if base.cr.isPaid():
                if base.cr.productName in ['DisneyOnline-UK', 'DisneyOnline-AP', 'JP', 'DE', 'BR', 'FR']:
                    paidNoParentPassword = launcher and launcher.getParentPasswordSet()
                else:
                    paidNoParentPassword = launcher and not launcher.getParentPasswordSet()
            else:
                paidNoParentPassword = 0
            self.leaveToPayDialog = LeaveToPayDialog.LeaveToPayDialog(paidNoParentPassword, self.purchaseButton.show)
            self.leaveToPayDialog.show()
        else:
            self.notify.error('You should not get here without a PlayToken')

    def setWantBattles(self, wantBattles):
        self.wantBattles = wantBattles

    def setAsGM(self, state):
        self.notify.debug('Setting GM State: %s in LocalToon' % state)
        DistributedToon.DistributedToon.setAsGM(self, state)
        if self.gmState:
            if base.config.GetString('gm-nametag-string', '') != '':
                self.gmNameTagString = base.config.GetString('gm-nametag-string')
            if base.config.GetString('gm-nametag-color', '') != '':
                self.gmNameTagColor = base.config.GetString('gm-nametag-color')
            if base.config.GetInt('gm-nametag-enabled', 0):
                self.gmNameTagEnabled = 1
            self.d_updateGMNameTag()

    def displayTalkWhisper(self, fromId, avatarName, rawString, mods):
        sender = base.cr.identifyAvatar(fromId)
        if sender:
            chatString, scrubbed = sender.scrubTalk(rawString, mods)
        else:
            chatString, scrubbed = self.scrubTalk(rawString, mods)
        sender = self
        sfx = self.soundWhisper
        chatString = avatarName + ': ' + chatString
        whisper = WhisperPopup(chatString, OTPGlobals.getInterfaceFont(), WhisperType.WTNormal)
        whisper.setClickable(avatarName, fromId)
        whisper.manage(base.marginManager)
        base.playSfx(sfx)

    def displayTalkAccount(self, fromId, senderName, rawString, mods):
        sender = None
        playerInfo = None
        sfx = self.soundWhisper
        playerInfo = base.cr.playerFriendsManager.playerId2Info.get(fromId, None)
        if playerInfo == None:
            return
        senderAvId = base.cr.playerFriendsManager.findAvIdFromPlayerId(fromId)
        if not senderName and base.cr.playerFriendsManager.playerId2Info.get(fromId):
            senderName = base.cr.playerFriendsManager.playerId2Info.get(fromId).playerName
        senderAvatar = base.cr.identifyAvatar(senderAvId)
        if sender:
            chatString, scrubbed = senderAvatar.scrubTalk(rawString, mods)
        else:
            chatString, scrubbed = self.scrubTalk(rawString, mods)
        chatString = senderName + ': ' + chatString
        whisper = WhisperPopup(chatString, OTPGlobals.getInterfaceFont(), WhisperType.WTNormal)
        if playerInfo != None:
            whisper.setClickable(senderName, fromId, 1)
        whisper.manage(base.marginManager)
        base.playSfx(sfx)
        return

    def isLocal(self):
        return 1

    def canChat(self):
        if not self.cr.allowAnyTypedChat():
            return 0
        if self.commonChatFlags & (ToontownGlobals.CommonChat | ToontownGlobals.SuperChat):
            return 1
        if base.cr.whiteListChatEnabled:
            return 1
        for friendId, flags in self.friendsList:
            if flags & ToontownGlobals.FriendChat:
                return 1

        return 0

    def startChat(self):
        if self.tutorialAck:
            self.notify.info('calling LocalAvatar.startchat')
            LocalAvatar.LocalAvatar.startChat(self)
            self.accept('chatUpdateSCToontask', self.b_setSCToontask)
            self.accept('chatUpdateSCResistance', self.d_reqSCResistance)
            self.accept('chatUpdateSCSinging', self.b_setSCSinging)
            self.accept('whisperUpdateSCToontask', self.whisperSCToontaskTo)
        else:
            self.notify.info('NOT calling LocalAvatar.startchat, in tutorial')

    def stopChat(self):
        LocalAvatar.LocalAvatar.stopChat(self)
        self.ignore('chatUpdateSCToontask')
        self.ignore('chatUpdateSCResistance')
        self.ignore('chatUpdateSCSinging')
        self.ignore('whisperUpdateSCToontask')

    def tunnelIn(self, tunnelOrigin):
        self.b_setTunnelIn(self.tunnelX * 0.8, tunnelOrigin)

    def tunnelOut(self, tunnelOrigin):
        self.tunnelX = self.getX(tunnelOrigin)
        tunnelY = self.getY(tunnelOrigin)
        self.b_setTunnelOut(self.tunnelX * 0.95, tunnelY, tunnelOrigin)

    def handleTunnelIn(self, startTime, endX, x, y, z, h):
        self.notify.debug('LocalToon.handleTunnelIn')
        tunnelOrigin = render.attachNewNode('tunnelOrigin')
        tunnelOrigin.setPosHpr(x, y, z, h, 0, 0)
        self.b_setAnimState('run', self.animMultiplier)
        self.stopLookAround()
        self.reparentTo(render)
        self.runSound()
        camera.reparentTo(render)
        camera.setPosHpr(tunnelOrigin, 0, 20, 12, 180, -20, 0)
        base.transitions.irisIn(0.4)
        toonTrack = self.getTunnelInToonTrack(endX, tunnelOrigin)

        def cleanup(self = self, tunnelOrigin = tunnelOrigin):
            self.stopSound()
            tunnelOrigin.removeNode()
            messenger.send('tunnelInMovieDone')

        self.tunnelTrack = Sequence(toonTrack, Func(cleanup))
        self.tunnelTrack.start(globalClock.getFrameTime() - startTime)

    def handleTunnelOut(self, startTime, startX, startY, x, y, z, h):
        self.notify.debug('LocalToon.handleTunnelOut')
        tunnelOrigin = render.attachNewNode('tunnelOrigin')
        tunnelOrigin.setPosHpr(x, y, z, h, 0, 0)
        self.b_setAnimState('run', self.animMultiplier)
        self.runSound()
        self.stopLookAround()
        tracks = Parallel()
        camera.wrtReparentTo(render)
        startPos = camera.getPos(tunnelOrigin)
        startHpr = camera.getHpr(tunnelOrigin)
        camLerpDur = 1.0
        reducedCamH = fitDestAngle2Src(startHpr[0], 180)
        tracks.append(LerpPosHprInterval(camera, camLerpDur, pos=Point3(0, 20, 12), hpr=Point3(reducedCamH, -20, 0), startPos=startPos, startHpr=startHpr, other=tunnelOrigin, blendType='easeInOut', name='tunnelOutLerpCamPos'))
        toonTrack = self.getTunnelOutToonTrack(startX, startY, tunnelOrigin)
        tracks.append(toonTrack)
        irisDur = 0.4
        tracks.append(Sequence(Wait(toonTrack.getDuration() - (irisDur + 0.1)), Func(base.transitions.irisOut, irisDur)))

        def cleanup(self = self, tunnelOrigin = tunnelOrigin):
            self.stopSound()
            self.detachNode()
            tunnelOrigin.removeNode()
            messenger.send('tunnelOutMovieDone')

        self.tunnelTrack = Sequence(tracks, Func(cleanup))
        self.tunnelTrack.start(globalClock.getFrameTime() - startTime)

    def getPieBubble(self):
        if self.__pieBubble == None:
            bubble = CollisionSphere(0, 0, 0, 1)
            node = CollisionNode('pieBubble')
            node.addSolid(bubble)
            node.setFromCollideMask(ToontownGlobals.PieBitmask | ToontownGlobals.CameraBitmask | ToontownGlobals.FloorBitmask)
            node.setIntoCollideMask(BitMask32.allOff())
            self.__pieBubble = NodePath(node)
            self.pieHandler = CollisionHandlerEvent()
            self.pieHandler.addInPattern('pieHit')
            self.pieHandler.addInPattern('pieHit-%in')
        return self.__pieBubble

    def __beginTossPieMouse(self, mouseParam):
        self.__beginTossPie(globalClock.getFrameTime())

    def __endTossPieMouse(self, mouseParam):
        self.__endTossPie(globalClock.getFrameTime())

    def __beginTossPie(self, time):
        if self.tossPieStart != None:
            return
        if not self.allowPies:
            return
        if self.numPies == 0:
            messenger.send('outOfPies')
            return
        if self.__pieInHand():
            return
        # Allow all pies to be charged while in the air
        # Removed the isAirborne check to allow charging while airborne
        messenger.send('wakeup')
        self.localPresentPie(time)
        taskName = self.uniqueName('updatePiePower')
        taskMgr.add(self.__updatePiePower, taskName)
        return

    def __endTossPie(self, time):
        if self.tossPieStart == None:
            return
        taskName = self.uniqueName('updatePiePower')
        taskMgr.remove(taskName)
        messenger.send('wakeup')
        power = self.__getPiePower(time)
        self.tossPieStart = None
        # Store final power and start updating trajectory line based on toon movement
        self.__finalPiePower = power
        # Start a task to keep updating trajectory line until pie is released
        updateTaskName = self.uniqueName('updateTrajectoryAfterCharge')
        taskMgr.add(self.__updateTrajectoryAfterCharge, updateTaskName)
        # Don't remove trajectory line here - it will be removed when pie leaves hand
        self.localTossPie(power)
        return

    def __zeroPowerToss(self):
        self.__beginTossPie(0)
        self.__endTossPie(0)

    def localPresentPie(self, time):
        from otp.avatar import Emote
        self.__stopPresentPie()
        if self.tossTrack:
            tossTrack = self.tossTrack
            self.tossTrack = None
            tossTrack.finish()
        self.interruptPie()
        self.tossPieStart = time
        self.__pieSequence = self.__pieSequence + 1 & 255
        sequence = self.__pieSequence
        self.__presentingPie = 1
        pos = self.getPos()
        hpr = self.getHpr()
        timestamp32 = globalClockDelta.getFrameNetworkTime(bits=32)
        self.sendUpdate('presentPie', [pos[0],
         pos[1],
         pos[2],
         hpr[0] % 360.0,
         hpr[1],
         hpr[2],
         timestamp32])
        Emote.globalEmote.disableBody(self)
        messenger.send('begin-pie')
        ival = self.getPresentPieInterval(pos[0], pos[1], pos[2], hpr[0], hpr[1], hpr[2])
        ival = Sequence(ival, name=self.uniqueName('localPresentPie'))
        self.tossTrack = ival
        ival.start()
        self.makePiePowerMeter()
        self.__piePowerMeter.show()
        self.__piePowerMeterSequence = sequence
        self.__piePowerMeter['value'] = 0
        # Create initial trajectory line
        self.__createTrajectoryLine(0)
        return

    def __stopPresentPie(self):
        if self.__presentingPie:
            from otp.avatar import Emote
            Emote.globalEmote.releaseBody(self)
            messenger.send('end-pie')
            self.__presentingPie = 0
        taskName = self.uniqueName('updatePiePower')
        taskMgr.remove(taskName)

    def __getPiePower(self, time):
        elapsed = max(time - self.tossPieStart, 0.0)
        t = elapsed / self.piePowerSpeed
        t = math.pow(t, self.piePowerExponent)
        power = int(t * 100) % 200
        if power > 100:
            power = 200 - power
        return power

    def __updatePiePower(self, task):
        if not self.__piePowerMeter:
            return Task.done
        power = self.__getPiePower(globalClock.getFrameTime())
        self.__piePowerMeter['value'] = power
        # Update trajectory line
        self.__updateTrajectoryLine(power)
        return Task.cont

    def __createTrajectoryLine(self, power):
        """Create a trajectory line showing where the pie will land - OPTIMIZED VERSION"""
        from panda3d.core import LineSegs, TransparencyAttrib, Point3, CollisionTraverser, CollisionHandlerQueue, \
            CollisionNode, BitMask32
        from direct.interval.ProjectileInterval import ProjectileInterval
        from otp.otpbase import OTPGlobals
        
        # Remove existing line and target if any
        self.__removeTrajectoryLine()
        self.__removeTrajectoryTarget()
        
        # Calculate trajectory using same logic as getTossPieInterval
        pos = self.getPos()
        hpr = self.getHpr()
        t = power / 100.0
        dist = 100 - 70 * t
        time = 1 + 0.5 * t
        
        # Create a ProjectileInterval to get the velocity
        proj = ProjectileInterval(None, startPos=Point3(0, 0, 0), endPos=Point3(0, dist, 0), duration=time)
        relVel = proj.startVel
        
        # Get velocity in world space
        startVel = render.getRelativeVector(self, relVel)
        
        # Calculate trajectory points
        from ..minigame.utils import Trajectory
        startTime = globalClock.getFrameTime()
        # Use the same hand position offset as in getTossPieInterval (relative to toon)
        handOffset = render.getRelativePoint(self, Point3(0.52, 0.97, 2.24))
        startPos = handOffset
        
        # Create trajectory
        trajectory = Trajectory.Trajectory(startTime, startPos, startVel)
        
        # Find ground impact time
        groundTime = trajectory.calcTimeOfImpactOnPlane(0.0)
        if groundTime < 0:
            maxTime = 3.0
        else:
            maxTime = groundTime - startTime
            maxTime = min(maxTime, 3.0)
        
        # OPTIMIZATION: Use fewer sample points for collision detection (20 instead of 100)
        # We'll interpolate visual points between them for smooth line
        numCollisionSamples = 10  # Reduced from 100
        numVisualPoints = 50  # For smooth line rendering
        
        points = []
        hitPoint = None
        surfaceNormal = None
        
        # Set up collision detection - SINGLE traverser and collider, reused
        collisionTrav = CollisionTraverser()
        collisionQueue = CollisionHandlerQueue()
        from panda3d.core import CollisionSegment
        collisionSegment = CollisionSegment()
        collisionNode = CollisionNode('trajectorySegment')
        collisionNode.addSolid(collisionSegment)
        from toontown.toonbase import ToontownGlobals
        collisionNode.setFromCollideMask(OTPGlobals.WallBitmask | OTPGlobals.FloorBitmask | ToontownGlobals.PieBitmask | ToontownGlobals.TNTBitmask)
        collisionNode.setIntoCollideMask(BitMask32.allOff())
        segmentNodePath = render.attachNewNode(collisionNode)
        collisionTrav.addCollider(segmentNodePath, collisionQueue)
        
        points.append(startPos)
        prevPoint = startPos
        hitTimeRatio = 1.0  # Ratio of time where we hit something
        
        # OPTIMIZED: Check collisions only at sample points
        for i in range(1, numCollisionSamples + 1):
            t = (i / float(numCollisionSamples)) * maxTime
            point = trajectory.getPos(startTime + t)
            
            if hitPoint is None:
                segDist = (point - prevPoint).length()
                if segDist > 0.01:
                    collisionSegment.setPointA(prevPoint)
                    collisionSegment.setPointB(point)
                    collisionQueue.clearEntries()
                    collisionTrav.traverse(render)  # ONLY ONE TRAVERSAL PER SAMPLE
                    
                    if collisionQueue.getNumEntries() > 0:
                        collisionQueue.sortEntries()
                        
                        # Find first valid collision (ignore NearBoss and self)
                        for j in range(collisionQueue.getNumEntries()):
                            entry = collisionQueue.getEntry(j)
                            intoNode = entry.getIntoNodePath()
                            nodeName = intoNode.getName() if not intoNode.isEmpty() else ''
                            
                            if nodeName == 'NearBoss':
                                continue
                            
                            # Check if it's toon geometry (skip self-collisions)
                            checkNode = intoNode
                            isSelf = False
                            for _ in range(10):  # Limit parent traversal
                                if checkNode.isEmpty() or checkNode == render:
                                    break
                                if checkNode == self:
                                    isSelf = True
                                    break
                                checkNode = checkNode.getParent()
                            
                            if isSelf:
                                continue
                            
                            # Valid collision found
                            hitPoint = entry.getSurfacePoint(render)
                            distanceFromStart = (hitPoint - startPos).length()
                            
                            if distanceFromStart >= 2.0:  # Min distance to avoid hand collisions
                                if entry.hasSurfaceNormal():
                                    surfaceNormal = entry.getSurfaceNormal(render)
                                    surfaceNormal.normalize()
                                hitTimeRatio = i / float(numCollisionSamples)
                                break
                            else:
                                hitPoint = None
                        
                        if hitPoint is not None:
                            break
            
            prevPoint = point
        
        segmentNodePath.removeNode()
        
        # Now create visual line with more points for smoothness
        visualPoints = []
        maxVisualTime = maxTime * hitTimeRatio
        
        for i in range(numVisualPoints + 1):
            t = (i / float(numVisualPoints)) * maxVisualTime
            point = trajectory.getPos(startTime + t)
            visualPoints.append(point)
        
        # Add hit point at the end if we found one
        if hitPoint is not None:
            visualPoints.append(hitPoint)
        
        if len(visualPoints) < 2:
            return
        
        # Create line geometry
        lines = LineSegs('trajectoryLine')
        lines.setColor(1, 1, 0, 0.6)
        lines.setThickness(3.5)
        
        for i, point in enumerate(visualPoints):
            if i == 0:
                lines.moveTo(point.getX(), point.getY(), point.getZ())
            else:
                lines.drawTo(point.getX(), point.getY(), point.getZ())
        
        self.__trajectoryLine = render.attachNewNode(lines.create())
        self.__trajectoryLine.setTransparency(TransparencyAttrib.MAlpha)
        self.__trajectoryLine.setDepthWrite(False)
        self.__trajectoryLine.setBin('fixed', 0)
        
        # Create target indicator
        landingPoint = hitPoint if hitPoint else visualPoints[-1]
        self.__createTrajectoryTarget(landingPoint, surfaceNormal)
    
    def __updateTrajectoryLine(self, power):
        """Update the trajectory line based on current power"""
        if self.__presentingPie:
            self.__createTrajectoryLine(power)
    
    def __updateTrajectoryAfterCharge(self, task):
        """Update trajectory line after charging stops, following toon movement until pie is released"""
        # Check if pie is still being presented (hasn't been released yet)
        if not self.__presentingPie:
            # Pie has been released, stop updating
            self.__finalPiePower = None
            return Task.done
        
        # Update trajectory line with final power but current toon position/orientation
        if self.__finalPiePower is not None:
            self.__createTrajectoryLine(self.__finalPiePower)
        
        return Task.cont
    
    def __removeTrajectoryLine(self):
        """Remove the trajectory line"""
        if self.__trajectoryLine:
            self.__trajectoryLine.removeNode()
            self.__trajectoryLine = None
    
    def __createTrajectoryTarget(self, landingPoint, surfaceNormal=None):
        """Create a target indicator (red circle with +) at the landing point, oriented to the surface"""
        from panda3d.core import LineSegs, TransparencyAttrib, Vec3
        import math
        
        # Remove existing target if any
        self.__removeTrajectoryTarget()
        
        # Create circle
        circle = LineSegs('trajectoryTarget')
        circle.setColor(1, 0, 0, 0.8)  # Red, semi-transparent
        circle.setThickness(3.0)
        
        radius = 1.0
        crossSize = 0.8
        numSegments = 32
        
        # If we have a surface normal, orient the target to the surface
        if surfaceNormal is not None:
            # Create a coordinate system on the surface plane
            # Use the surface normal as the Z axis (up from surface)
            up = Vec3(surfaceNormal)
            up.normalize()
            
            # Create a right vector (perpendicular to up)
            # Use world up (0,0,1) as reference, but if surface normal is too close to it, use (1,0,0)
            worldUp = Vec3(0, 0, 1)
            if abs(up.dot(worldUp)) > 0.9:
                worldUp = Vec3(1, 0, 0)
            
            # Right vector is perpendicular to both up and worldUp
            right = up.cross(worldUp)
            right.normalize()
            
            # Forward vector completes the orthonormal basis
            forward = right.cross(up)
            forward.normalize()
            
            # Draw circle in the surface plane
            for i in range(numSegments + 1):
                angle = (i / float(numSegments)) * 360.0
                rad = math.radians(angle)
                # Create point in the plane using right and forward vectors
                offset = right * (radius * math.cos(rad)) + forward * (radius * math.sin(rad))
                point = landingPoint + offset
                if i == 0:
                    circle.moveTo(point.getX(), point.getY(), point.getZ())
                else:
                    circle.drawTo(point.getX(), point.getY(), point.getZ())
            
            # Draw crosshair (+) in the surface plane
            # Horizontal line (along right vector)
            p1 = landingPoint - right * crossSize
            p2 = landingPoint + right * crossSize
            circle.moveTo(p1.getX(), p1.getY(), p1.getZ())
            circle.drawTo(p2.getX(), p2.getY(), p2.getZ())
            # Vertical line (along forward vector)
            p3 = landingPoint - forward * crossSize
            p4 = landingPoint + forward * crossSize
            circle.moveTo(p3.getX(), p3.getY(), p3.getZ())
            circle.drawTo(p4.getX(), p4.getY(), p4.getZ())
        else:
            # No surface normal - draw flat on horizontal plane (default behavior)
            for i in range(numSegments + 1):
                angle = (i / float(numSegments)) * 360.0
                rad = math.radians(angle)
                x = landingPoint.getX() + radius * math.cos(rad)
                y = landingPoint.getY() + radius * math.sin(rad)
                z = landingPoint.getZ()
                if i == 0:
                    circle.moveTo(x, y, z)
                else:
                    circle.drawTo(x, y, z)
            
            # Create crosshair (+)
            # Horizontal line
            circle.moveTo(landingPoint.getX() - crossSize, landingPoint.getY(), landingPoint.getZ())
            circle.drawTo(landingPoint.getX() + crossSize, landingPoint.getY(), landingPoint.getZ())
            # Vertical line
            circle.moveTo(landingPoint.getX(), landingPoint.getY() - crossSize, landingPoint.getZ())
            circle.drawTo(landingPoint.getX(), landingPoint.getY() + crossSize, landingPoint.getZ())
        
        # Create node path for the target
        self.__trajectoryTarget = render.attachNewNode(circle.create())
        self.__trajectoryTarget.setTransparency(TransparencyAttrib.MAlpha)
        self.__trajectoryTarget.setDepthWrite(False)
        self.__trajectoryTarget.setBin('fixed', 0)
    
    def __removeTrajectoryTarget(self):
        """Remove the trajectory target"""
        if self.__trajectoryTarget:
            self.__trajectoryTarget.removeNode()
            self.__trajectoryTarget = None

    def interruptPie(self):
        self.cleanupPieInHand()
        self.__stopPresentPie()
        if self.__piePowerMeter:
            self.__piePowerMeter.hide()
        # Stop trajectory update task if running
        updateTaskName = self.uniqueName('updateTrajectoryAfterCharge')
        taskMgr.remove(updateTaskName)
        self.__finalPiePower = None
        self.__removeTrajectoryLine()
        self.__removeTrajectoryTarget()
        pie = self.pieTracks.get(self.__pieSequence)
        if pie and pie.getT() < 14.0 / 24.0:
            del self.pieTracks[self.__pieSequence]
            pie.pause()
            # Clean up flyPie and pieBubble if they exist
            self.__cleanupPieFlyNodes(self.__pieSequence)

    def __pieInHand(self):
        pie = self.pieTracks.get(self.__pieSequence)
        return pie and pie.getT() < 15.0 / 24.0

    def __toonMoved(self, isSet):
        return
        if isSet:
            self.interruptPie()

    def localTossPie(self, power):
        if not self.__presentingPie:
            return
        pos = self.getPos()
        hpr = self.getHpr()
        timestamp32 = globalClockDelta.getFrameNetworkTime(bits=32)
        sequence = self.__pieSequence
        if self.tossTrack:
            tossTrack = self.tossTrack
            self.tossTrack = None
            tossTrack.finish()
        if sequence in self.pieTracks:
            pieTrack = self.pieTracks[sequence]
            del self.pieTracks[sequence]
            pieTrack.finish()
        if sequence in self.splatTracks:
            splatTrack = self.splatTracks[sequence]
            del self.splatTracks[sequence]
            splatTrack.finish()
        self.makePiePowerMeter()
        self.__piePowerMeter['value'] = power
        self.__piePowerMeter.show()
        self.__piePowerMeterSequence = sequence
        pieBubble = self.getPieBubble().instanceTo(NodePath())

        def pieFlies(self = self, pos = pos, hpr = hpr, sequence = sequence, power = power, timestamp32 = timestamp32, pieBubble = pieBubble):
            # Remove trajectory line when pie leaves hand
            # Stop the trajectory update task
            updateTaskName = self.uniqueName('updateTrajectoryAfterCharge')
            taskMgr.remove(updateTaskName)
            self.__finalPiePower = None
            self.__removeTrajectoryLine()
            self.__removeTrajectoryTarget()
            self.sendUpdate('tossPie', [pos[0],
             pos[1],
             pos[2],
             hpr[0] % 360.0,
             hpr[1],
             hpr[2],
             sequence,
             power,
             timestamp32])
            if self.numPies != ToontownGlobals.FullPies:
                self.setNumPies(self.numPies - 1)
            # Update pie bubble collision mask based on pie type (TNT uses TNTBitmask)
            from toontown.toonbase import ToontownBattleGlobals
            pieName = ToontownBattleGlobals.pieNames[self.pieType]
            if pieName == 'tnt':
                # TNT pies use TNTBitmask and need to collide with walls, floors, goons, and CFO
                from otp.otpbase import OTPGlobals
                pieBubble.node().setFromCollideMask(ToontownGlobals.TNTBitmask | OTPGlobals.WallBitmask | OTPGlobals.FloorBitmask | ToontownGlobals.CameraBitmask)
            else:
                # Regular pies use PieBitmask
                pieBubble.node().setFromCollideMask(ToontownGlobals.PieBitmask | ToontownGlobals.CameraBitmask | ToontownGlobals.FloorBitmask)
            base.cTrav.addCollider(pieBubble, self.pieHandler)

        toss, pie, flyPie = self.getTossPieInterval(pos[0], pos[1], pos[2], hpr[0], hpr[1], hpr[2], power, beginFlyIval=Func(pieFlies))
        pieBubble.reparentTo(flyPie)
        flyPie.setTag('pieSequence', str(sequence))
        # Store flyPie and pieBubble for cleanup
        self.__pieFlyNodes[sequence] = {'flyPie': flyPie, 'pieBubble': pieBubble}
        toss = Sequence(toss)
        self.tossTrack = toss
        toss.start()
        pie = Sequence(pie, Func(base.cTrav.removeCollider, pieBubble), Func(self.pieFinishedFlying, sequence), Func(self.__cleanupPieFlyNodes, sequence))
        self.pieTracks[sequence] = pie
        pie.start()
        return

    def pieFinishedFlying(self, sequence):
        DistributedToon.DistributedToon.pieFinishedFlying(self, sequence)
        if self.__piePowerMeterSequence == sequence:
            self.__piePowerMeter.hide()

    def __cleanupPieFlyNodes(self, sequence):
        """Clean up flyPie and pieBubble for a given sequence."""
        if sequence in self.__pieFlyNodes:
            flyData = self.__pieFlyNodes[sequence]
            flyPie = flyData.get('flyPie')
            pieBubble = flyData.get('pieBubble')
            
            # Remove collider if it's still in the traverser
            if pieBubble and not pieBubble.isEmpty():
                try:
                    base.cTrav.removeCollider(pieBubble)
                except:
                    pass  # Collider may have already been removed
            
            # Detach flyPie if it still exists
            if flyPie and not flyPie.isEmpty():
                flyPie.detachNode()
            
            # Clean up pieBubble
            if pieBubble and not pieBubble.isEmpty():
                pieBubble.removeNode()
            
            del self.__pieFlyNodes[sequence]

    def __finishPieTrack(self, sequence):
        if sequence in self.pieTracks:
            pieTrack = self.pieTracks[sequence]
            del self.pieTracks[sequence]
            pieTrack.finish()
        # Clean up flyPie and pieBubble if they exist
        self.__cleanupPieFlyNodes(sequence)

    def __pieHit(self, entry):
        if not entry.hasSurfacePoint() or not entry.hasInto():
            return
        if not entry.getInto().isTangible():
            return
        sequenceStr = entry.getFromNodePath().getNetTag('pieSequence')
        if not sequenceStr:
            return  # No valid sequence tag, can't process this hit
        sequence = int(sequenceStr)
        self.__finishPieTrack(sequence)
        if sequence in self.splatTracks:
            splatTrack = self.splatTracks[sequence]
            del self.splatTracks[sequence]
            splatTrack.finish()
        pieCode = 0
        pieCodeStr = entry.getIntoNodePath().getNetTag('pieCode')
        if pieCodeStr:
            pieCode = int(pieCodeStr)
        
        # Check if this is a TNT pie hitting a goon's toonSphere
        from toontown.toonbase import ToontownBattleGlobals
        pieName = ToontownBattleGlobals.pieNames[self.pieType]
        intoNode = entry.getIntoNodePath()
        intoName = intoNode.getName() if not intoNode.isEmpty() else ''
        
        pos = entry.getSurfacePoint(render)
        
        # If TNT pie hits a goon's toonSphere, destroy the goon and award points
        if pieName == 'tnt' and 'toonSphere' in intoName:
            # Find the goon by traversing up the node path
            goonNode = intoNode.getParent()
            while goonNode and not goonNode.isEmpty():
                if 'goon-' in goonNode.getName():
                    # Found the goon - destroy it and award points
                    goon = base.cr.doId2do.get(int(goonNode.getName().split('-')[1]))
                    if goon:
                        if hasattr(goon, 'd_destroyedByTNT'):
                            goon.d_destroyedByTNT(localAvatar.doId)
                        elif hasattr(goon, 'b_destroyGoon'):
                            # Fallback for goons that don't support TNT destruction points
                            goon.b_destroyGoon()
                    break
                goonNode = goonNode.getParent()
        
        # If TNT pie hits a crane's safetyBubble or tube, disable the crane
        if pieName == 'tnt' and (intoName == 'safetyBubble' or intoName == 'tube'):
            # Get crane doId from collision node tag
            craneDoIdStr = intoNode.getNetTag('craneDoId')
            if craneDoIdStr:
                craneDoId = int(craneDoIdStr)
                crane = base.cr.doId2do.get(craneDoId)
                if crane and hasattr(crane, 'd_tntHit'):
                    crane.d_tntHit()
        
        # TNT explosion radius check - destroy all goons within 15 units
        goonsDestroyed = False
        if pieName == 'tnt':
            goonsDestroyed = self.__checkTNTExplosionRadius(pos)
            # Also check if we directly hit a goon
            if 'toonSphere' in intoName:
                goonsDestroyed = True
        
        timestamp32 = globalClockDelta.getFrameNetworkTime(bits=32)
        self.sendUpdate('pieSplat', [pos[0],
         pos[1],
         pos[2],
         sequence,
         pieCode,
         timestamp32])
        # Pass goonsDestroyed flag to splat interval for TNT
        splat = self.getPieSplatInterval(pos[0], pos[1], pos[2], pieCode, goonsDestroyed=goonsDestroyed if pieName == 'tnt' else False)
        splat = Sequence(splat, Func(self.pieFinishedSplatting, sequence))
        self.splatTracks[sequence] = splat
        splat.start()
        messenger.send('pieSplat', [self, pieCode])
        messenger.send('localPieSplat', [pieCode, entry])

    def __checkTNTExplosionRadius(self, explosionPos):
        """Check for goons within 10 units of TNT explosion and destroy them."""
        # Find the game to get goons list (goons are stored on the game, not the boss)
        game = None
        
        # Try to get game from current minigame
        if hasattr(base, 'curMinigame') and base.curMinigame:
            game = base.curMinigame
        
        # Fallback: search for game in doId2do
        if not game:
            for obj in base.cr.doId2do.values():
                if hasattr(obj, '__class__') and 'CraneGame' in obj.__class__.__name__ and 'AI' not in obj.__class__.__name__:
                    game = obj
                    break
        
        if not game:
            return False
        
        if not hasattr(game, 'goons'):
            return False
        
        # Check all goons within 10 units
        explosionRadius = 10.0
        goonsDestroyed = False
        goonsChecked = 0
        for goon in game.goons:
            if not goon:
                continue
            if hasattr(goon, 'isEmpty') and goon.isEmpty():
                continue
            try:
                goonPos = goon.getPos(render)
                distance = (explosionPos - goonPos).length()
                goonsChecked += 1
                self.notify.debug('__checkTNTExplosionRadius: Goon at %s, distance=%.2f' % (goonPos, distance))
                if distance <= explosionRadius:
                    # Goon is within explosion radius - destroy it and award points
                    if hasattr(goon, 'd_destroyedByTNT'):
                        self.notify.debug('__checkTNTExplosionRadius: Destroying goon at distance %.2f' % distance)
                        goon.d_destroyedByTNT(localAvatar.doId)
                        goonsDestroyed = True
                    elif hasattr(goon, 'b_destroyGoon'):
                        # Fallback for goons that don't support TNT destruction points
                        self.notify.debug('__checkTNTExplosionRadius: Destroying goon (no TNT points) at distance %.2f' % distance)
                        goon.b_destroyGoon()
                        goonsDestroyed = True
            except Exception as e:
                # Skip goon if there's an error getting position
                self.notify.debug('__checkTNTExplosionRadius: Error checking goon: %s' % str(e))
                continue
        
        self.notify.debug('__checkTNTExplosionRadius: Checked %d goons, destroyed=%s' % (goonsChecked, goonsDestroyed))
        return goonsDestroyed

    def beginAllowPies(self):
        self.allowPies = 1
        self.updatePieButton()

    def endAllowPies(self):
        self.allowPies = 0
        self.updatePieButton()

    def makePiePowerMeter(self):
        from direct.gui.DirectGui import DirectWaitBar, DGG
        if self.__piePowerMeter == None:
            self.__piePowerMeter = DirectWaitBar(frameSize=(-0.2,
             0.2,
             -0.03,
             0.03), relief=DGG.SUNKEN, borderWidth=(0.005, 0.005), barColor=(0.4, 0.6, 1.0, 1), pos=(0, 0.1, 0.7))
            self.__piePowerMeter.hide()
        return

    def updatePieButton(self):
        from toontown.toonbase import ToontownBattleGlobals
        from direct.gui.DirectGui import DirectButton, DGG
        wantButton = 0
        if self.allowPies and self.numPies > 0:
            wantButton = 1
        haveButton = self.__pieButton != None
        if not haveButton and not wantButton:
            return
        if haveButton and not wantButton:
            self.__pieButton.destroy()
            self.__pieButton = None
            self.__pieButtonType = None
            self.__pieButtonCount = None
            return
        if self.__pieButtonType != self.pieType:
            if self.__pieButton:
                self.__pieButton.destroy()
                self.__pieButton = None
        if self.__pieButton == None:
            inv = self.inventory
            if self.pieType == 8:
                # TNT (pieType 8) uses the trap TNT icon
                invModel = loader.loadModel('phase_3.5/models/gui/inventory_icons')
                pieGui = invModel.find('**/inventory_tnt')
                pieGui = pieGui.copyTo(NodePath('tntIcon'))  # Copy to a new NodePath so we can remove the model
                invModel.removeNode()
                pieScale = 0.85
                gui = None
            elif self.pieType >= len(inv.invModels[ToontownBattleGlobals.THROW_TRACK]):
                # Lawbook (pieType 7) and other out-of-range types use summons icon
                gui = loader.loadModel('phase_3.5/models/gui/stickerbook_gui')
                pieGui = gui.find('**/summons')
                pieScale = 0.1
            else:
                gui = None
                pieGui = (inv.invModels[ToontownBattleGlobals.THROW_TRACK][self.pieType],)
                pieScale = 0.85
            self.__pieButton = DirectButton(image=(inv.upButton, inv.downButton, inv.rolloverButton), geom=pieGui, text='50', text_scale=0.04, text_align=TextNode.ARight, geom_scale=pieScale, geom_pos=(-0.01, 0, 0), text_fg=Vec4(1, 1, 1, 1), text_pos=(0.07, -0.04), relief=None, image_color=(0, 0.6, 1, 1), pos=(0, 0.1, 0.8))
            self.__pieButton.bind(DGG.B1PRESS, self.__beginTossPieMouse)
            self.__pieButton.bind(DGG.B1RELEASE, self.__endTossPieMouse)
            self.__pieButtonType = self.pieType
            self.__pieButtonCount = None
            if gui:
                del gui
        if self.__pieButtonCount != self.numPies:
            if self.numPies == ToontownGlobals.FullPies:
                self.__pieButton['text'] = ''
            else:
                self.__pieButton['text'] = str(self.numPies)
            self.__pieButtonCount = self.numPies
        return

    def setBattleId(self, battleId):
        super().setBattleId(battleId)
        # When we have our battle ID set, we should determine if we should have unites enabled
        disableUnitesFlag: bool = self.isBattling()
        messenger.send(ResistanceChat.RESISTANCE_TOGGLE_EVENT, [disableUnitesFlag])

    def setSystemMessage(self, aboutId: int, chatString: str, whisperType: WhisperType = WhisperType.WTSystem):
        prefix = global_text_properties.create_text_with_undefined_color('System: ', WhisperGlobals.WHISPER_COLORS.get(whisperType)[1].getPrimaryColor())
        base.localAvatar.chatbox.addRawMessage(f"{prefix}{chatString}")
        base.playSfx(self.soundSystemMessage)

    def displayWhisper(self, fromId, chatString, whisperType, colorProfileOverride: ColorProfile = None):
        sender = None
        sfx = self.soundWhisper
        if fromId != 0:
            sender = base.cr.identifyAvatar(fromId)
        if whisperType == WhisperType.WTNormal or whisperType == WhisperType.WTQuickTalker:
            if sender is None:
                return

            chatString = sender.getName() + ': ' + chatString
        elif whisperType == WhisperType.WTSystem:
            sfx = self.soundSystemMessage

        whisper = WhisperPopup(chatString, OTPGlobals.getInterfaceFont(), whisperType, bg_override=colorProfileOverride)

        if sender is not None:
            whisper.setClickable(sender.getName(), fromId)

        whisper.manage(base.marginManager)
        base.playSfx(sfx)
        return

    def displaySystemClickableWhisper(self, fromId, chatString, whisperType):
        sender = None
        sfx = self.soundWhisper
        if fromId != 0:
            sender = base.cr.identifyAvatar(fromId)
        if whisperType == WhisperType.WTNormal or whisperType == WhisperType.WTQuickTalker:
            if sender == None:
                return
            chatString = sender.getName() + ': ' + chatString
        elif whisperType == WhisperType.WTSystem:
            sfx = self.soundSystemMessage
        whisper = WhisperPopup(chatString, OTPGlobals.getInterfaceFont(), whisperType)
        whisper.setClickable('', fromId)
        whisper.manage(base.marginManager)
        base.playSfx(sfx)
        return

    def loadFurnitureGui(self):
        if self.__furnitureGui:
            return
        guiModels = loader.loadModel('phase_5.5/models/gui/house_design_gui')
        self.__furnitureGui = DirectFrame(relief=None, parent=base.a2dTopLeft, pos=(0.143333, 0, -0.67), scale=0.04,
                                          image=guiModels.find('**/attic'))
        DirectLabel(parent=self.__furnitureGui, relief=None, image=guiModels.find('**/rooftile'))
        bMoveStartUp = guiModels.find('**/bu_attic/bu_attic_up')
        bMoveStartDown = guiModels.find('**/bu_attic/bu_attic_down')
        bMoveStartRollover = guiModels.find('**/bu_attic/bu_attic_rollover')
        DirectButton(parent=self.__furnitureGui, relief=None, image=[bMoveStartUp,
         bMoveStartDown,
         bMoveStartRollover,
         bMoveStartUp], text=['', TTLocalizer.HDMoveFurnitureButton, TTLocalizer.HDMoveFurnitureButton], text_fg=(1, 1, 1, 1), text_shadow=(0, 0, 0, 1), text_font=ToontownGlobals.getInterfaceFont(), pos=(-0.3, 0, 9.4), command=self.__startMoveFurniture)
        self.__furnitureGui.hide()
        guiModels.removeNode()
        return

    def showFurnitureGui(self):
        self.loadFurnitureGui()
        self.__furnitureGui.show()

    def hideFurnitureGui(self):
        if self.__furnitureGui:
            self.__furnitureGui.hide()

    def __startMoveFurniture(self):
        self.oldPos = self.getPos()
        if base.config.GetBool('want-qa-regression', 0):
            self.notify.info('QA-REGRESSION: ESTATE:  Furniture Placement')
        if self.cr.furnitureManager != None:
            self.cr.furnitureManager.d_suggestDirector(self.doId)
        elif self.furnitureManager != None:
            self.furnitureManager.d_suggestDirector(self.doId)
        return

    def stopMoveFurniture(self):
        if self.oldPos:
            self.setPos(self.oldPos)
        if self.furnitureManager != None:
            self.furnitureManager.d_suggestDirector(0)
        return

    def setFurnitureDirector(self, avId, furnitureManager):
        if avId == 0:
            if self.furnitureManager == furnitureManager:
                messenger.send('exitFurnitureMode', [furnitureManager])
                self.furnitureManager = None
                self.furnitureDirector = None
        elif avId != self.doId:
            if self.furnitureManager == None or self.furnitureDirector != avId:
                self.furnitureManager = furnitureManager
                self.furnitureDirector = avId
                messenger.send('enterFurnitureMode', [furnitureManager, 0])
        else:
            if self.furnitureManager != None:
                messenger.send('exitFurnitureMode', [self.furnitureManager])
                self.furnitureManager = None
            self.furnitureManager = furnitureManager
            self.furnitureDirector = avId
            messenger.send('enterFurnitureMode', [furnitureManager, 1])
        self.refreshOnscreenButtons()
        return

    def getAvPosStr(self):
        pos = self.getPos()
        hpr = self.getHpr()
        serverVersion = base.cr.getServerVersion()
        districtName = base.cr.getShardName(base.localAvatar.defaultShard)
        if hasattr(base.cr.playGame.hood, 'loader') and hasattr(base.cr.playGame.hood.loader, 'place') and base.cr.playGame.getPlace() != None:
            zoneId = base.cr.playGame.getPlace().getZoneId()
        else:
            zoneId = '?'
        strPosCoordText = 'X: %.3f' % pos[0] + ', Y: %.3f' % pos[1] + '\nZ: %.3f' % pos[2] + ', H: %.3f' % hpr[0] + '\nZone: %s' % str(zoneId) + ', Ver: %s, ' % serverVersion + 'District: %s' % districtName
        return strPosCoordText
        self.refreshOnscreenButtons()
        return

    def thinkPos(self):
        pos = self.getPos()
        hpr = self.getHpr()
        serverVersion = base.cr.getServerVersion()
        districtName = base.cr.getShardName(base.localAvatar.defaultShard)
        if hasattr(base.cr.playGame.hood, 'loader') and hasattr(base.cr.playGame.hood.loader, 'place') and base.cr.playGame.getPlace() != None:
            zoneId = base.cr.playGame.getPlace().getZoneId()
        else:
            zoneId = '?'
        strPos = '(%.3f' % pos[0] + '\n %.3f' % pos[1] + '\n %.3f)' % pos[2] + '\nH: %.3f' % hpr[0] + '\nZone: %s' % str(zoneId) + ',\nVer: %s, ' % serverVersion + '\nDistrict: %s' % districtName
        print('Current position=', strPos.replace('\n', ', '))
        self.setChatAbsolute(strPos, CFThought | CFTimeout)
        return

    def showPosInit(self):
        strPosOnScreenText = 'toon id: ' + \
                             '\npos: ' + \
                             '\nang: ' + \
                             '\nzone: ' # + \
#                             '\ndistrict:'

        self.strPosOnScreen = OnscreenText(parent=base.a2dTopLeft,
                                     pos = (0, -0.4),
                                     text = strPosOnScreenText,
                                     scale=0.05,
                                     fg=VBase4(1.0, 1.0, 1.0, 1.0),
                                     bg=(0, 0, 0, 0),
                                     shadow=(0, 0, 0, 1),
                                     align=TextNode.ALeft,
                                     mayChange=True)

        taskMgr.add(self.__updateShowPos, 'updateShowPos')
        self.strPosOnScreen.hide()

    def showPos(self):
        if self.strPosOnScreen.isHidden():
            self.strPosOnScreen.show()
        else:
            self.strPosOnScreen.hide()

    def stopShowPos(self):
        taskMgr.remove('updateShowPos')

    def cleanupShowPos(self):
        self.stopShowPos()
        self.strPosOnScreen.cleanup()
        del self.strPosOnScreen

    def __updateShowPos(self, task=None):
        pos = self.getPos()
        hpr = self.getHpr()
        districtName = base.cr.getShardName(base.localAvatar.defaultShard)
        if hasattr(base.cr.playGame.hood, 'loader') and hasattr(base.cr.playGame.hood.loader, 'place') and base.cr.playGame.getPlace() != None:
            zoneId = base.cr.playGame.getPlace().getZoneId()
        else:
            zoneId = '?'
        self.strPosOnScreen.setText(f"toon id: {str(self.doId - 100000000)}\
                             \npos: {pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}\
                             \nang: {hpr[0]:.2f}\
                             \nzone: {zoneId}")
                             # \ndistrict: {districtName}")
        return Task.cont

    def __placeMarker(self):
        pos = self.getPos()
        hpr = self.getHpr()
        chest = loader.loadModel('phase_4/models/props/coffin')
        chest.reparentTo(render)
        chest.setColor(1, 0, 0, 1)
        chest.setPosHpr(pos, hpr)
        chest.setScale(0.5)

    def setFriendsListButtonActive(self, active):
        self.friendsListButtonActive = active
        self.refreshOnscreenButtons()

    def obscureFriendsListButton(self, increment):
        self.friendsListButtonObscured += increment
        self.refreshOnscreenButtons()

    def obscureMoveFurnitureButton(self, increment):
        self.moveFurnitureButtonObscured += increment
        self.refreshOnscreenButtons()

    def refreshOnscreenButtons(self):
        self.bFriendsList.hide()
        self.hideFurnitureGui()
        self.ignore(ToontownGlobals.FriendsListHotkey)
        if self.friendsListButtonActive and self.friendsListButtonObscured <= 0:
            self.bFriendsList.show()
            self.accept(ToontownGlobals.FriendsListHotkey, self.sendFriendsListEvent)
        if self.moveFurnitureButtonObscured <= 0:
            if self.furnitureManager != None and self.furnitureDirector == self.doId:
                self.loadFurnitureGui()
                self.__furnitureGui.setPos(0.173333, 1, -1.03)
                self.__furnitureGui.setScale(0.06)
            elif self.cr.furnitureManager != None:
                self.showFurnitureGui()
                taskMgr.remove('lerpFurnitureButton')
                self.__furnitureGui.posHprScaleInterval(pos=Point3(0.143333, 0, -0.67), hpr=Vec3(0.0, 0.0, 0.0),
                                                        scale=Vec3(0.04, 0.04, 0.04), duration=1.0,
                                                        blendType='easeInOut', name='lerpFurnitureButton').start()
        return

    def setGhostMode(self, flag):
        if flag == 2:
            self.seeGhosts = 1
        DistributedToon.DistributedToon.setGhostMode(self, flag)

    def allowHardLand(self):
        retval = LocalAvatar.LocalAvatar.allowHardLand(self)
        return retval and not self.isDisguised

    def changeButtonText(self, button, text):
        button['text'] = text

    def setGuiConflict(self, con):
        self.guiConflict = con

    def getGuiConflict(self, con):
        return self.guiConflict

    def verboseState(self):
        self.lastPlaceState = 'None'
        taskMgr.add(self.__expressState, 'expressState', extraArgs=[])

    def __expressState(self, task = None):
        place = base.cr.playGame.getPlace()
        if place:
            state = place.fsm.getCurrentState()
            if state.getName() != self.lastPlaceState:
                print('Place State Change From %s to %s' % (self.lastPlaceState, state.getName()))
                self.lastPlaceState = state.getName()
        return Task.cont

    def b_setAnimState(self, animName, animMultiplier = 1.0, callback = None, extraArgs = []):
        if self.wantStatePrint:
            print('Local Toon Anim State %s' % animName)
        DistributedToon.DistributedToon.b_setAnimState(self, animName, animMultiplier, callback, extraArgs)

    def swimTimeoutAction(self):
        self.ignore('wakeup')
        self.takeOffSuit()
        base.cr.playGame.getPlace().fsm.request('final')
        self.b_setAnimState('TeleportOut', 1, self.__handleSwimExitTeleport, [0])
        return Task.done

    def __handleSwimExitTeleport(self, requestStatus):
        self.notify.info('closing shard...')
        base.cr.gameFSM.request('closeShard', ['afkTimeout'])

    def sbFriendAdd(self, id, info):
        print('sbFriendAdd')

    def sbFriendUpdate(self, id, info):
        print('sbFriendUpdate')

    def sbFriendRemove(self, id):
        print('sbFriendRemove')

    def addNewsPage(self):
        self.newsPage = NewsPage.NewsPage()
        self.newsPage.load()
        self.book.addPage(self.newsPage, pageName=TTLocalizer.NewsPageName)

    def setPinkSlips(self, pinkSlips):
        DistributedToon.DistributedToon.setPinkSlips(self, pinkSlips)
        self.inventory.updateTotalPropsText()

    def getAccountDays(self):
        days = 0
        defaultDays = base.cr.config.GetInt('account-days', -1)
        if defaultDays >= 0:
            days = defaultDays
        elif hasattr(base.cr, 'accountDays'):
            days = base.cr.accountDays
        return days

    def hasActiveBoardingGroup(self):
        if hasattr(localAvatar, 'boardingParty') and localAvatar.boardingParty:
            return localAvatar.boardingParty.hasActiveGroup(localAvatar.doId)
        else:
            return False

    def getZoneId(self):
        return self._zoneId

    def setZoneId(self, value):
        if value == -1:
            self.notify.error('zoneId should not be set to -1, tell Redmond')
        self._zoneId = value

    zoneId = property(getZoneId, setZoneId)

    def systemWarning(self, warningText = 'Acknowledge this system message.'):
        self.createSystemMsgAckGui()
        self.systemMsgAckGui['text'] = warningText
        self.systemMsgAckGui.show()

    def createSystemMsgAckGui(self):
        if self.systemMsgAckGui == None or self.systemMsgAckGui.isEmpty():
            message = 'o' * 100
            self.systemMsgAckGui = TTDialog.TTGlobalDialog(doneEvent=self.systemMsgAckGuiDoneEvent, message=message, style=TTDialog.Acknowledge)
            self.systemMsgAckGui.hide()
        return

    def hideSystemMsgAckGui(self):
        if self.systemMsgAckGui != None and not self.systemMsgAckGui.isEmpty():
            self.systemMsgAckGui.hide()
        return

    def setSleepAutoReply(self, fromId):
        av = base.cr.identifyAvatar(fromId)
        if isinstance(av, DistributedToon.DistributedToon):
            base.localAvatar.setSystemMessage(0, TTLocalizer.sleep_auto_reply % av.getName(), WhisperType.WTToontownBoardingGroup)
        elif av is not None:
            self.notify.warning('setSleepAutoReply from non-toon %s' % fromId)
        return

    def setLastTimeReadNews(self, newTime):
        self.lastTimeReadNews = newTime

    def getLastTimeReadNews(self):
        return self.lastTimeReadNews

    def cheatCogdoMazeGame(self, kindOfCheat = 0):
        if base.config.GetBool('allow-cogdo-maze-suit-hit-cheat'):
            maze = base.cr.doFind('DistCogdoMazeGame')
            if maze:
                if kindOfCheat == 0:
                    for suitNum in list(maze.game.suitsById.keys()):
                        suit = maze.game.suitsById[suitNum]
                        maze.sendUpdate('requestSuitHitByGag', [suit.type, suitNum])

                elif kindOfCheat == 1:
                    for joke in maze.game.pickups:
                        maze.sendUpdate('requestPickUp', [joke.serialNum])

        else:
            self.sendUpdate('logSuspiciousEvent', ['cheatCogdoMazeGame'])

    def isReadingNews(self):
        result = False
        if base.cr and base.cr.playGame and base.cr.playGame.getPlace() and hasattr(base.cr.playGame.getPlace(), 'fsm') and base.cr.playGame.getPlace().fsm:
            fsm = base.cr.playGame.getPlace().fsm
            curState = fsm.getCurrentState().getName()
            if curState == 'stickerBook' and WantNewsPage:
                if hasattr(self, 'newsPage'):
                    if self.book.isOnPage(self.newsPage):
                        result = True
        return result

    def doTeleportResponse(self, fromAvatar, toAvatar, avId, available, shardId, hoodId, zoneId, sendToId):
        localAvatar.d_teleportResponse(avId, available, shardId, hoodId, zoneId, sendToId)

    def d_teleportResponse(self, avId, available, shardId, hoodId, zoneId, sendToId = None):
        if base.config.GetBool('want-tptrack', False):
            if available == 1:
                self.notify.debug('sending teleportResponseToAI')
                self.sendUpdate('teleportResponseToAI', [avId,
                 available,
                 shardId,
                 hoodId,
                 zoneId,
                 sendToId])
            else:
                self.sendUpdate('teleportResponse', [avId,
                 available,
                 shardId,
                 hoodId,
                 zoneId], sendToId)
        else:
            DistributedPlayer.DistributedPlayer.d_teleportResponse(self, avId, available, shardId, hoodId, zoneId, sendToId)

    def _startZombieCheck(self):
        pass

    def _stopZombieCheck(self):
        pass

    def setTeleporting(self, teleporting):
        self.teleporting = teleporting

    def getTeleporting(self):
        return self.teleporting

    def enableSleeping(self):
        messenger.send('wakeup')
        self.neverSleep = False

    def disableSleeping(self):
        messenger.send('wakeup')
        self.neverSleep = True

    def startSleepWatch(self, callback):
        if self.neverSleep:
            return

        super().startSleepWatch(callback)

    # Prints a message to the AP log
    def sendArchipelagoMessages(self, messages: List[str]) -> None:
        for msg in messages:
            self.archipelagoLog.addToLog(msg)

    # Tells the server what our death reason should be.
    # We need this because in some circumstances the server is unaware why we are taking damage.
    # When setting death reasons, always make sure to set it BEFORE the damage is taken.
    def d_setDeathReason(self, reason: DeathReason):
        self.sendUpdate('setDeathReason', [reason.to_astron()])

    def enterPlaceWalk(self):
       pass

    def enableCraneControls(self) -> None:
        self.controlManager.enableCraneControls()

    def disableCraneControls(self) -> None:
        self.controlManager.disableCraneControls()

    def enableControls(self) -> None:
        self.allowControls = True

        place = base.cr.playGame.getPlace()
        if place and place.getState() in ("walk", "finalBattle"):
            self.enableAvatarControls()

    def disableControls(self) -> None:
        self.allowControls = False
        self.disableAvatarControls()

    # Update pie throw keys without needing a game restart
    def disableOldPieKeys(self) -> None:
        controls = base.controls
        # Ignore both binds for SECONDARY_ACTION
        secondary_binds = base.settings.getControlBinds("SECONDARY_ACTION")
        for bind in secondary_binds:
            if bind:
                self.ignore(bind)
        
        # Ignore both binds for ACTION_BUTTON
        action_binds = base.settings.getControlBinds("ACTION_BUTTON")
        for bind in action_binds:
            if bind:
                self.ignore('time-' + bind)
                self.ignore('time-' + bind + '-up')

    def resetPieKeys(self) -> None:
        controls = base.controls
        # Accept both binds for SECONDARY_ACTION
        secondary_binds = base.settings.getControlBinds("SECONDARY_ACTION")
        for bind in secondary_binds:
            if bind:
                self.accept(bind, self.__zeroPowerToss)
        
        # Accept both binds for ACTION_BUTTON
        action_binds = base.settings.getControlBinds("ACTION_BUTTON")
        for bind in action_binds:
            if bind:
                self.accept('time-' + bind, self.__beginTossPie)
                self.accept('time-' + bind + '-up', self.__endTossPie)

    def updateOverhead(self) -> None:
        if base.laffMeterDisplay:
            self.makeOverheadLaffMeter()
        else:
            self.destroyOverheadLaffMeter()

    def d_requestNametagStyle(self, nametagStyle):
        """Request nametag style change from server"""
        self.sendUpdate('requestNametagStyle', [nametagStyle])

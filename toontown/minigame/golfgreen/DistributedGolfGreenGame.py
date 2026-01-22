import random

from direct.fsm.ClassicFSM import ClassicFSM
from direct.fsm.State import State
from panda3d.core import Point3

from toontown.minigame.DistributedMinigame import DistributedMinigame
from toontown.minigame.MinigameAvatarScorePanel import MinigameAvatarScorePanel
from toontown.minigame.golfgreen import GolfGreenConstants
from toontown.minigame.golfgreen.GolfGreenBoard import GolfGreenBoard
from toontown.toonbase import TTLocalizer
from toontown.toonbase.ToontownTimer import ToontownTimer


class DistributedGolfGreenGame(DistributedMinigame):

    def __init__(self, cr):
        super().__init__(cr)
        self.scorePanels = {}
        self.toonPoints = list(
            Point3(
                3 * ((offset // 2) + 1) * ((-1) ** offset),
                13.0,
                0
            )
            for offset in range(16)
        )
        self.timer = None
        self.hasEntered = 0
        self.trackClosed = 0
        self.finished = 0

        # The UI element that handles the golf green game
        self.boardInterface: GolfGreenBoard = GolfGreenBoard()

        self.gameFSM = ClassicFSM(self.__class__.__name__,
                                  [
                                      State('off',
                                            self.enterOff,
                                            self.exitOff,
                                            ['play']),
                                      State('play',
                                            self.enterPlay,
                                            self.exitPlay,
                                            ['cleanup']),
                                      State('cleanup',
                                            self.enterCleanup,
                                            self.exitCleanup,
                                            []),
                                  ],
                                  # Initial State
                                  'off',
                                  # Final State
                                  'cleanup',
                                  )

        # Add our game ClassicFSM to the framework ClassicFSM
        self.addChildGameFSM(self.gameFSM)

    def getTitle(self):
        return TTLocalizer.GolfGreenGameTitle

    def getInstructions(self):
        return TTLocalizer.GolfGreenGameInstructions

    def getMaxDuration(self):
        return GolfGreenConstants.GAME_DURATION

    def load(self):
        self.notify.debug("load")
        super().load()

        # Load music
        rng = random.Random()
        rng.seed(self.getDoId())
        musicName = rng.choice(
            ['phase_12/audio/bgm/Bossbot_Factory_v1.ogg', 'phase_12/audio/bgm/Bossbot_Factory_v2.ogg',
             'phase_12/audio/bgm/Bossbot_Factory_v3.ogg'])
        self.music = base.loader.loadMusic(musicName)

        # Load geometry
        self.geom = loader.loadModel("phase_12/models/bossbotHQ/BossbotGreenRoom_A")
        self.geom.reparentTo(render)

        # Setup base node
        self.baseNode = render.attachNewNode('GolfGreenGameBase')

        # Ground elements
        groundCircle = loader.loadModel('phase_12/models/bossbotHQ/bust_a_cog_golf_green')
        groundCircle.reparentTo(self.baseNode)
        groundCircle.setScale(0.24)
        self.groundFlag = loader.loadModel('phase_12/models/bossbotHQ/bust_a_cog_golf_flag')
        self.groundFlag.reparentTo(self.baseNode)
        self.groundFlag.setScale(0.5)
        self.groundFlag.setH(-45)
        self.groundFlag.setPos(3.0, 4.0, 0.0)

        groundCircle.setDepthWrite(False)
        groundCircle.setDepthTest(True)
        groundCircle.setBin('ground', 1)

        # Load models for the board
        model = loader.loadModel('phase_5.5/models/gui/package_delivery_panel')
        model1 = loader.loadModel('phase_3.5/models/gui/matching_game_gui')

        # Load sounds
        sounds = {
            'fire': base.loader.loadSfx('phase_6/audio/sfx/Golf_Hit_Ball.ogg'),
            'land': base.loader.loadSfx('phase_4/audio/sfx/MG_maze_pickup.ogg'),
            'burst': base.loader.loadSfx('phase_5/audio/sfx/Toon_bodyfall_synergy.ogg'),
            'bomb': base.loader.loadSfx('phase_4/audio/sfx/MG_cannon_fire_alt.ogg'),
            'lose': base.loader.loadSfx('phase_11/audio/sfx/LB_capacitor_discharge_3.ogg'),
            'win': base.loader.loadSfx('phase_4/audio/sfx/MG_pairing_match_bonus_both.ogg'),
            'done': base.loader.loadSfx('phase_3/audio/sfx/GUI_create_toon_back.ogg'),
            'move': base.loader.loadSfx('phase_3.5/audio/sfx/SA_shred.ogg'),
        }

        # Initialize the board
        models = {'model': model, 'model1': model1}
        self.boardInterface.load(self.baseNode, models, sounds)

        # Set up callbacks
        self.boardInterface.onBoardWin = self.__handleBoardWin
        self.boardInterface.onBoardFail = self.__handleBoardFail

        self.focusPoint = self.baseNode.attachNewNode('GolfGreenGameFrame')

    def unload(self):
        self.notify.debug("unload")
        super().unload()

        # Remove our game ClassicFSM from the framework ClassicFSM
        self.removeChildGameFSM(self.gameFSM)
        del self.gameFSM

        self.geom.removeNode()
        del self.geom

        self.music.stop()
        del self.music

        self.baseNode.removeNode()
        del self.baseNode

        self.boardInterface.unload()
        self.ignoreAll()

    def onstage(self):
        self.notify.debug("onstage")
        super().onstage()

    def offstage(self):
        self.notify.debug("offstage")
        super().offstage()

    def handleDisabledAvatar(self, avId):
        """This will be called if an avatar exits unexpectedly"""
        self.notify.debug("handleDisabledAvatar")
        self.notify.debug("avatar " + str(avId) + " disabled")
        super().handleDisabledAvatar(avId)

    def setGameReady(self):
        if not self.hasLocalToon: return
        self.notify.debug("setGameReady")
        if super().setGameReady():
            return

        # Show toons
        for index, avId in enumerate(self.avIdList):
            toon = self.getAvatar(avId)
            if toon:
                toon.reparentTo(render)
                toon.setPos(self.toonPoints[index])
                toon.setHpr(180, 0, 0)
                toon.loop('neutral')

        base.playMusic(self.music, looping=1, volume=1)

        self.__setCamera()

    def setGameStart(self, timestamp):
        if not self.hasLocalToon: return
        self.notify.debug("setGameStart")
        super().setGameStart(timestamp)
        self.gameFSM.request("play")

    def enterOff(self):
        self.notify.debug("enterOff")

    def exitOff(self):
        pass

    def enterPlay(self):
        self.notify.debug("enterPlay")
        spacing = .4
        for i in range(self.numPlayers):
            avId = self.avIdList[i]
            avName = self.getAvatarName(avId)
            scorePanel = MinigameAvatarScorePanel(avId, avName)
            scorePanel.setScale(.9)
            scorePanel.setPos(.75 - spacing * ((len(self.avIdList) - 1) - i), 0.0, .875)
            scorePanel.makeTransparent(.75)
            self.scorePanels[avId] = scorePanel

        self.timer = ToontownTimer()
        self.timer.posInTopRightCorner()
        self.timer.setTime(GolfGreenConstants.GAME_DURATION)
        self.timer.countdown(GolfGreenConstants.GAME_DURATION, self.timerExpired)

        # Setup and show the board
        self.boardInterface.setup()
        self.boardInterface.show()
        self.groundFlag.hide()
        self.__setCamera()
        base.setCellsAvailable([base.bottomCells[1], base.bottomCells[2], base.bottomCells[3]], 0)

    def timerExpired(self):
        self.notify.debug('local timer expired')
        self.gameOver()

    def exitPlay(self):
        self.timer.destroy()
        del self.timer

        for panel in self.scorePanels.values():
            panel.cleanup()

        self.scorePanels = {}

        self.boardInterface.hide()
        self.boardInterface.stop()
        self.groundFlag.show()
        base.setCellsAvailable([base.bottomCells[1], base.bottomCells[2], base.bottomCells[3]], 1)

    def enterCleanup(self):
        self.notify.debug("enterCleanup")

    def exitCleanup(self):
        pass

    def startBoard(self, board, attackPattern):
        """Start a new board"""
        if self.finished:
            return
        self.boardInterface.startBoard(board, attackPattern)

    def __handleBoardWin(self):
        """Callback when board is won"""
        self.sendUpdate('requestBoard', [True])

    def __handleBoardFail(self):
        """Callback when board is failed"""
        self.sendUpdate('requestBoard', [False])

    def __setCamera(self):
        camera.setPos(0, 0, 0)
        camera.setH(0)
        camera.setP(-70)
        camera.reparentTo(self.focusPoint)
        base.camLens.setMinFov(46.8265)
        self.focusPoint.setPos(0, 12, 27)
        self.focusPoint.setH(180)

    def boardCleared(self, avId):
        """Server notification that board was cleared"""
        self.boardInterface.doFail()

    def scoreData(self, scoreList):
        """Update score panels"""
        for avId, score in scoreList:
            p: MinigameAvatarScorePanel = self.scorePanels[avId]
            p.setScore(score)

    def helpOthers(self, avId):
        """Someone helped with a bonus"""
        if avId != localAvatar.doId and self.boardInterface.running:
            self.boardInterface.setGiftId(7)
            toonName = ''
            toon = base.cr.doId2do.get(avId)
            if toon:
                toonName = toon.getName()
            if self.boardInterface.bonusBoard:
                self.boardInterface.bonusBoard['text'] = TTLocalizer.GolfGreenGameGotHelp % toonName
                imageBall = loader.loadModel('phase_12/models/bossbotHQ/bust_a_cog_ball_fire')
                imageBall.setHpr(0, 90, 0)
                self.boardInterface.bonusBoard['image'] = imageBall
                self.boardInterface.bonusBoard['image_scale'] = 0.13
                self.boardInterface.bonusBoard.show()
                taskMgr.doMethodLater(4.0, self._hideBonusBoard, 'hide bonus')

    def _hideBonusBoard(self, task):
        """Hide the bonus board after delay"""
        self.boardInterface.hideBonusBoard()
        return task.done

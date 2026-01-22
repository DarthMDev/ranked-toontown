import functools
import math

from direct.distributed import DistributedSmoothNode
from direct.fsm import ClassicFSM
from direct.fsm import State
from direct.gui.OnscreenText import OnscreenText
from direct.interval.FunctionInterval import Func, Wait
from direct.interval.LerpInterval import LerpPosHprInterval
from direct.interval.MetaInterval import Parallel, Sequence
from otp.otpbase.PythonUtil import reduceAngle
from direct.task.TaskManagerGlobal import taskMgr
from panda3d.core import CollisionPlane, Plane, Vec3, Point3, CollisionNode, NodePath, CollisionPolygon, BitMask32, \
    VBase3, VBase4, ColorBlendAttrib, GeomVertexData, GeomVertexWriter, Geom, GeomTrifans, GeomNode, GeomVertexFormat, CollisionRay, \
    CollisionHandlerQueue, CollisionTube, TextNode
from panda3d.physics import LinearVectorForce, ForceNode, LinearEulerIntegrator, PhysicsManager

from libotp.nametag import NametagGlobals
from otp.otpbase import OTPGlobals
from toontown.minigame.craning.CraneGameGlobals import RED_COUNTDOWN_COLOR, ORANGE_COUNTDOWN_COLOR, \
    YELLOW_COUNTDOWN_COLOR
from toontown.minigame.craning.managers.client.DroneManager import DroneManager
from toontown.minigame.craning.managers.client.ForfeitRestartManager import ForfeitRestartManager
from toontown.minigame.craning.managers.client.ModifierManager import ModifierManager
from toontown.minigame.craning.managers.client.PlayerManager import PlayerManager
from toontown.minigame.craning.managers.client.RoundManager import RoundManager
from toontown.minigame.craning.ui.ModifierPanelUI import ModifierPanelUI
from toontown.minigame.craning.ui.DroneSelectionUI import DroneSelectionUI
from toontown.minigame.craning.ui.GameButtonsUI import GameButtonsUI
from toontown.minigame.craning.ui.ForfeitRestartDialogsUI import ForfeitRestartDialogsUI
from toontown.minigame.utils.boss.BossSpeedrunTimer import BossSpeedrunTimedTimer, BossSpeedrunTimer
from toontown.minigame.craning.boss.CashbotBossScoreboard import CashbotBossScoreboard
from toontown.coghq.CraneLeagueHeatDisplay import CraneLeagueHeatDisplay
from toontown.minigame.DistributedMinigame import DistributedMinigame
from toontown.minigame.craning.CraneWalk import CraneWalk
from toontown.toonbase import TTLocalizer, ToontownGlobals
from toontown.minigame.craning.CraneGameSettingsPanel import CraneGameSettingsPanel
from toontown.minigame.utils.statuseffects.DistributedStatusEffectSystem import DistributedStatusEffectSystem
from direct.showbase.ShowBaseGlobal import aspect2d
from direct.task import Task
from toontown.minigame.craning import CraneGameGlobals


class DistributedCraneGame(DistributedMinigame):

    # define constants that you won't want to tweak here
    BASE_HEAT = 500

    def __init__(self, cr):
        DistributedMinigame.__init__(self, cr)

        self.cranes = {}
        self.safes = {}
        self.goons = []

        # Setup collision detection for clicking
        self.clickRay = CollisionRay()
        self.clickRayNode = CollisionNode('mouseRay')
        self.clickRayNode.addSolid(self.clickRay)
        self.clickRayNodePath = camera.attachNewNode(self.clickRayNode)
        # Create a special bitmask for our spotlight clicks
        self.spotlightBitMask = BitMask32.bit(3)  # Using bit 3 for our spotlight clicks
        self.clickRayNode.setFromCollideMask(self.spotlightBitMask)
        self.clickRayNode.setIntoCollideMask(BitMask32.allOff())
        self.clickRayQueue = CollisionHandlerQueue()
        base.cTrav.addCollider(self.clickRayNodePath, self.clickRayQueue)

        self.overlayText = OnscreenText('', shadow=(0, 0, 0, 1), font=ToontownGlobals.getCompetitionFont(), pos=(0, 0), scale=0.35, mayChange=1)
        self.overlayText.hide()
        self.rulesPanel = None
        self.rulesPanelToggleButton = None
        self.playButton = None
        self.participantsButton = None
        
        # Initialize managers
        self.playerManager = PlayerManager(self)
        self.modifierManager = ModifierManager(self)
        self.droneManager = DroneManager(self)
        self.roundManager = RoundManager(self)
        self.forfeitRestartManager = ForfeitRestartManager(self)
        
        # Initialize UI components
        self.modifierPanelUI = ModifierPanelUI(self, self.modifierManager)
        self.droneSelectionUI = DroneSelectionUI(self, self.droneManager)
        self.gameButtonsUI = GameButtonsUI(self, self.roundManager, self.modifierPanelUI)
        self.forfeitRestartDialogsUI = ForfeitRestartDialogsUI(self, self.forfeitRestartManager)
        
        # Expose properties for backward compatibility (only what's actually used)
        self.participantsPanel = None
        self.participantsList = None
        self.participantsPanelVisible = False
        
        # bestOfButton removed - First to X Wins is now handled by modifier
        self.bestOfButton = None
        
        self.boss = None
        self.bossRequest = None
        self.ruleset = CraneGameGlobals.CraneGameRuleset()  # Setup a default ruleset as a fallback
        self.heatDisplay = CraneLeagueHeatDisplay()
        self.heatDisplay.hide()
        self.endVault = None
        self.statusIndicators = {}  # Dictionary to store status indicators for each toon
        
        # Status effect system will be set via setStatusEffectSystemId
        self.statusEffectSystem : DistributedStatusEffectSystem | None = None
        


        self.warningSfx = None

        self.timerTickSfx = None
        self.goSfx = None

        self.latency = 0.5  # default latency for updating object posHpr

        # Spawn order managed by PlayerManager
        self.toonSpawnpointOrder = self.playerManager.toonSpawnpointOrder
        self.stunEndTime = 0
        self.myHits = []
        self.tempHp = self.ruleset.CFO_MAX_HP
        self.processingHp = False

        self.bossSpeedrunTimer = BossSpeedrunTimer()
        self.bossSpeedrunTimer.hide()
        self.bossSpeedrunTimer.stop_updating()

        # The crane round scoreboard
        self.scoreboard = CashbotBossScoreboard(ruleset=self.ruleset)
        self.scoreboard.hide()

        self.walkStateData = CraneWalk('walkDone')

        self.gameFSM = ClassicFSM.ClassicFSM('DistributedMinigameTemplate',
                               [
                                State.State('off',
                                            self.enterOff,
                                            self.exitOff,
                                            ['prepare']),
                                State.State('prepare',
                                            self.enterPrepare,
                                            self.exitPrepare,
                                            ['play', 'cleanup']),
                                State.State('play',
                                            self.enterPlay,
                                            self.exitPlay,
                                            ['victory', 'cleanup', 'prepare']),
                                State.State('victory',
                                            self.enterVictory,
                                            self.exitVictory,
                                            ['cleanup', 'prepare']),
                                State.State('cleanup',
                                            self.enterCleanup,
                                            self.exitCleanup,
                                            []),
                                ],
                               # Initial State
                               'off',
                               # Final State
                               'cleanup',
                               )

        # it's important for the final state to do cleanup;
        # on disconnect, the ClassicFSM will be forced into the
        # final state. All states (except 'off') should
        # be prepared to transition to 'cleanup' at any time.

        # Add our game ClassicFSM to the framework ClassicFSM
        self.addChildGameFSM(self.gameFSM)

        self.overtimeActive = False

        # Modifier UI managed by ModifierPanelUI - no backward compatibility needed

    def getTitle(self):
        return TTLocalizer.CraneGameTitle

    def getInstructions(self):
        return TTLocalizer.CraneGameInstructions

    def getMaxDuration(self):
        # how many seconds can this minigame possibly last (within reason)?
        # this is for debugging only
        return 0

    def setSpectators(self, spectatorIds):
        """
        Called by the server to update the list of spectators.
        This is the distributed method that gets called on all clients.
        """
        super().setSpectators(spectatorIds)

        if self.gameFSM.getCurrentState() is not None:
            if self.gameFSM.getCurrentState().getName() == 'play':
                return

        # Update all toon indicators based on their spectator status
        for i, avId in enumerate(self.avIdList):
            toon = self.cr.getDo(avId)
            if toon:
                isPlayer = avId not in spectatorIds
                if avId in self.statusIndicators:
                    self.updateStatusIndicator(toon, isPlayer)
                else:
                    self.createStatusIndicator(toon, isPlayer)

    def __checkSpectatorState(self, spectate=True):
        # If we're in the rules state, don't apply any visibility changes
        if hasattr(self, 'rulesPanel') and self.rulesPanel is not None:
            return

        for toon in self.getSpectatingToons():
            if self.gameFSM.getCurrentState().getName() == 'play':
                toon.setGhostMode(True)
                toon.setPos(100, 100, 1000)

        # Loop through every non-spectator and make sure we can see them
        for toon in self.getParticipantsNotSpectating():
            toon.setGhostMode(False)
            toon.clearColorScale()
            toon.clearTransparency()
            toon.show()

        # If we are spectating, make sure the boss cannot touch us
        if self.boss is not None:
            if self.localToonSpectating():
                self.boss.makeLocalToonSafe()
            else:
                self.boss.makeLocalToonUnsafe()

        if spectate and self.scoreboard is not None:
            if self.localToonSpectating():
                self.scoreboard.enableSpectating()
            else:
                self.scoreboard.disableSpectating()

    def load(self):
        self.notify.debug("load")
        DistributedMinigame.load(self)
        # load resources and create objects here

        self.music = base.loader.loadMusic('phase_7/audio/bgm/encntr_suit_winning_indoor.ogg')
        self.winSting = base.loader.loadSfx("phase_4/audio/sfx/MG_win.ogg")
        self.loseSting = base.loader.loadSfx("phase_4/audio/sfx/MG_lose.ogg")

        self.timerTickSfx = base.loader.loadSfx("phase_14/audio/sfx/tick.ogg")
        self.timerTickSfx.setPlayRate(.8)
        self.timerTickSfx.setVolume(.1)
        self.goSfx = base.loader.loadSfx('phase_14/audio/sfx/tick.ogg')
        self.goSfx.setVolume(.1)

        base.cr.forbidCheesyEffects(1)

        self.loadEnvironment()

        # Set up a physics manager for the cables and the objects
        # falling around in the room.
        self.physicsMgr = PhysicsManager()
        integrator = LinearEulerIntegrator()
        self.physicsMgr.attachLinearIntegrator(integrator)
        fn = ForceNode('gravity')
        self.fnp = self.geom.attachNewNode(fn)
        gravity = LinearVectorForce(0, 0, -32)
        fn.addForce(gravity)
        self.physicsMgr.addLinearForce(gravity)

        self.warningSfx = loader.loadSfx('phase_9/audio/sfx/CHQ_GOON_tractor_beam_alarmed.ogg')

    def loadEnvironment(self):
        self.endVault = loader.loadModel('phase_10/models/cogHQ/EndVault.bam')
        self.lightning = loader.loadModel('phase_10/models/cogHQ/CBLightning.bam')
        self.magnet = loader.loadModel('phase_10/models/cogHQ/CBMagnetBlue.bam')
        self.sideMagnet = loader.loadModel('phase_10/models/cogHQ/CBMagnetRed.bam')
        if base.config.GetBool('want-legacy-heads'):
            self.magnet = loader.loadModel('phase_10/models/cogHQ/CBMagnet.bam')
            self.sideMagnet = loader.loadModel('phase_10/models/cogHQ/CBMagnetRed.bam')
        self.craneArm = loader.loadModel('phase_10/models/cogHQ/CBCraneArm.bam')
        self.controls = loader.loadModel('phase_10/models/cogHQ/CBCraneControls.bam')
        self.stick = loader.loadModel('phase_10/models/cogHQ/CBCraneStick.bam')
        self.safe = loader.loadModel('phase_10/models/cogHQ/CBSafe.bam')
        self.cableTex = self.craneArm.findTexture('MagnetControl')

        # Position the two rooms relative to each other, and so that
        # the floor is at z == 0
        self.geom = NodePath('geom')
        self.endVault.setPos(84, -201, -6)
        self.endVault.reparentTo(self.geom)

        # Clear out unneeded backstage models from the EndVault, if
        # they're in the file.
        self.endVault.findAllMatches('**/MagnetArms').detach()
        self.endVault.findAllMatches('**/Safes').detach()
        self.endVault.findAllMatches('**/MagnetControlsAll').detach()

        # Flag the collisions in the end vault so safes and magnets
        # don't try to go through the wall.
        self.disableBackWall()

        # Get the rolling doors.

        # This is the door from the end vault back to the mid vault.
        # The boss makes his "escape" through this door.
        self.door3 = self.endVault.find('**/SlidingDoor/')

        # Find all the wall polygons and replace them with planes,
        # which are solid, so there will be zero chance of safes or
        # toons slipping through a wall.
        walls = self.endVault.find('**/RollUpFrameCillison')
        walls.detachNode()
        self.evWalls = self.replaceCollisionPolysWithPlanes(walls)
        self.evWalls.reparentTo(self.endVault)
        
        # Set up wall collision mask to accept both regular pies and TNT pies
        wallsCollisionNode = self.evWalls.node()
        if wallsCollisionNode:
            backWallMask = BitMask32.lowerOn(3) << 21
            wallsCollisionNode.setIntoCollideMask(OTPGlobals.WallBitmask | ToontownGlobals.PieBitmask | ToontownGlobals.TNTBitmask | backWallMask)

        # Initially, these new planar walls are stashed, so they don't
        # cause us trouble in the intro movie or in battle one.  We
        # will unstash them when we move to battle three.
        self.evWalls.stash()

        # Also replace the floor polygon with a plane, and rename it
        # so we can detect a collision with it.
        floor = self.endVault.find('**/EndVaultFloorCollision')
        floor.detachNode()
        self.evFloor = self.replaceCollisionPolysWithPlanes(floor)
        self.evFloor.reparentTo(self.endVault)
        self.evFloor.setName('floor')

        # Also, put a big plane across the universe a few feet below
        # the floor, to catch things that fall out of the world.
        plane = CollisionPlane(Plane(Vec3(0, 0, 1), Point3(0, 0, -50)))
        planeNode = CollisionNode('dropPlane')
        planeNode.addSolid(plane)
        planeNode.setCollideMask(ToontownGlobals.PieBitmask)
        self.geom.attachNewNode(planeNode)
        self.geom.reparentTo(render)

    def replaceCollisionPolysWithPlanes(self, model):
        newCollisionNode = CollisionNode('collisions')
        newCollideMask = BitMask32(0)
        planes = []
        collList = model.findAllMatches('**/+CollisionNode')
        if not collList:
            collList = [model]
        for cnp in collList:
            cn = cnp.node()
            if not isinstance(cn, CollisionNode):
                self.notify.warning('Not a collision node: %s' % repr(cnp))
                break
            newCollideMask = newCollideMask | cn.getIntoCollideMask()
            for i in range(cn.getNumSolids()):
                solid = cn.getSolid(i)
                if isinstance(solid, CollisionPolygon):
                    # Save the plane defined by this polygon
                    plane = Plane(solid.getPlane())
                    planes.append(plane)
                else:
                    self.notify.warning('Unexpected collision solid: %s' % repr(solid))
                    newCollisionNode.addSolid(plane)

        newCollisionNode.setIntoCollideMask(newCollideMask)

        # Now sort all of the planes and remove the nonunique ones.
        # We can't use traditional dictionary-based tricks, because we
        # want to use Plane.compareTo(), not Plane.__hash__(), to make
        # the comparison.
        threshold = 0.1
        planes.sort(key=functools.cmp_to_key(lambda p1, p2: p1.compareTo(p2, threshold)))
        lastPlane = None
        for plane in planes:
            if lastPlane is None or plane.compareTo(lastPlane, threshold) != 0:
                cp = CollisionPlane(plane)
                newCollisionNode.addSolid(cp)
                lastPlane = plane

        return NodePath(newCollisionNode)

    def disableBackWall(self):
        if self.endVault is None:
            return

        try:
            # The walls collision is in evWalls, which is created by replaceCollisionPolysWithPlanes
            if not hasattr(self, 'evWalls') or self.evWalls is None or self.evWalls.isEmpty():
                return
            
            # evWalls IS the collision node (replaceCollisionPolysWithPlanes returns NodePath(newCollisionNode))
            # So we can get the node directly
            cn = self.evWalls.node()
            if cn is None or not isinstance(cn, CollisionNode):
                # Try to find the collision node if evWalls itself isn't the node
                wallsCollision = self.evWalls.find('**/+CollisionNode')
                if wallsCollision.isEmpty():
                    return
                cn = wallsCollision.node()
                if cn is None:
                    return
            
            cn.setIntoCollideMask(OTPGlobals.WallBitmask | ToontownGlobals.PieBitmask)  # TTCC No Back Wall
            self.notify.debug('[Crane League] Back wall disabled')
        except Exception as e:
            self.notify.warning(f'[Crane League] Failed to disable back wall: {e}')

    def enableBackWall(self):
        if self.endVault is None:
            self.notify.warning('[Crane League] Cannot enable back wall: endVault is None')
            return

        try:
            # The walls collision is in evWalls, which is created by replaceCollisionPolysWithPlanes
            if not hasattr(self, 'evWalls') or self.evWalls is None or self.evWalls.isEmpty():
                self.notify.warning('[Crane League] Cannot enable back wall: evWalls not found')
                return
            
            # evWalls IS the collision node (replaceCollisionPolysWithPlanes returns NodePath(newCollisionNode))
            # So we can get the node directly
            cn = self.evWalls.node()
            if cn is None or not isinstance(cn, CollisionNode):
                # Try to find the collision node if evWalls itself isn't the node
                wallsCollision = self.evWalls.find('**/+CollisionNode')
                if wallsCollision.isEmpty():
                    self.notify.warning('[Crane League] Cannot enable back wall: collision node not found in evWalls')
                    return
                cn = wallsCollision.node()
                if cn is None:
                    self.notify.warning('[Crane League] Cannot enable back wall: collision node is None')
                    return
            
            backWallMask = BitMask32.lowerOn(3) << 21
            newMask = OTPGlobals.WallBitmask | ToontownGlobals.PieBitmask | ToontownGlobals.TNTBitmask | backWallMask
            cn.setIntoCollideMask(newMask)
            self.notify.debug(f'[Crane League] Back wall enabled with mask: {newMask}')
        except Exception as e:
            self.notify.warning(f'[Crane League] Failed to enable back wall: {e}')

    def setToonsToBattleThreePos(self):
        """
        Places each toon at the desired position and orientation without creating
        or returning any animation tracks. The position and orientation are
        applied immediately.
        """
        participants = self.getParticipantsNotSpectating()
        participantIds = self.getParticipantIdsNotSpectating()
        
        # Ensure spawn order is valid and has enough entries
        # If spawn order hasn't been received yet or is too short, use default sequential order
        if len(self.toonSpawnpointOrder) < len(self.avIdList):
            self.notify.warning(f"Spawn order too short ({len(self.toonSpawnpointOrder)} < {len(self.avIdList)}), using default sequential order")
            # Use sequential positions as fallback
            for i, toon in enumerate(participants):
                spawn_index = i if i < len(CraneGameGlobals.TOON_SPAWN_POSITIONS) else 0
                posHpr = CraneGameGlobals.TOON_SPAWN_POSITIONS[spawn_index]
                pos = Point3(*posHpr[0:3])
                hpr = VBase3(*posHpr[3:6])
                toon.setPosHpr(pos, hpr)
        else:
            # When spectators are present, remap spawn positions so non-spectating players
            # use positions 0, 1, 2, etc. based on their order in the non-spectating list
            # This ensures players shift up when spectators are removed
            hasSpectators = len(self.getSpectators()) > 0
            
            if hasSpectators:
                # Simple remapping: use sequential positions 0, 1, 2 for non-spectating players
                for participantIndex, toon in enumerate(participants):
                    spawn_index = participantIndex if participantIndex < len(CraneGameGlobals.TOON_SPAWN_POSITIONS) else 0
                    posHpr = CraneGameGlobals.TOON_SPAWN_POSITIONS[spawn_index]
                    pos = Point3(*posHpr[0:3])
                    hpr = VBase3(*posHpr[3:6])
                    toon.setPosHpr(pos, hpr)
            else:
                # No spectators: use the original spawn order based on avIdList index
                for toon in participants:
                    avId = toon.doId
                    # Find this player's index in the original avIdList
                    if avId not in self.avIdList:
                        self.notify.warning(f"Toon {avId} not found in avIdList, using sequential position")
                        participantIndex = participantIds.index(avId)
                        spawn_index = participantIndex if participantIndex < len(CraneGameGlobals.TOON_SPAWN_POSITIONS) else 0
                    else:
                        avIdIndex = self.avIdList.index(avId)
                        # Use the avId's index to get their spawn position from the order
                        if avIdIndex >= len(self.toonSpawnpointOrder):
                            self.notify.warning(f"avIdIndex {avIdIndex} out of range for spawn order, using sequential position")
                            participantIndex = participantIds.index(avId)
                            spawn_index = participantIndex if participantIndex < len(CraneGameGlobals.TOON_SPAWN_POSITIONS) else 0
                        else:
                            spawn_index = self.toonSpawnpointOrder[avIdIndex]
                        
                        # Bounds check to prevent index errors
                        if spawn_index >= len(CraneGameGlobals.TOON_SPAWN_POSITIONS):
                            self.notify.warning(f"Invalid spawn index {spawn_index} for avId {avId}, using sequential position")
                            participantIndex = participantIds.index(avId)
                            spawn_index = participantIndex if participantIndex < len(CraneGameGlobals.TOON_SPAWN_POSITIONS) else 0
                    
                    posHpr = CraneGameGlobals.TOON_SPAWN_POSITIONS[spawn_index]
                    pos = Point3(*posHpr[0:3])
                    hpr = VBase3(*posHpr[3:6])
                    toon.setPosHpr(pos, hpr)

        for toon in self.getSpectatingToons():
            toon.setPos(self.getBoss().getPos())

    def __displayOverlayText(self, text, color=(1, 1, 1, 1), duration=None, scale=None):
        self.overlayText['text'] = text
        self.overlayText['fg'] = color
        if scale:
            self.overlayText['scale'] = scale
        else:
            self.overlayText['scale'] = 0.35
        self.overlayText.show()
        
        if duration:
            taskMgr.doMethodLater(duration, lambda task: self.__hideOverlayText(), 
                                  self.uniqueName('hide-overlay-text'))

    def __hideOverlayText(self):
        if hasattr(self, 'overlayText') and self.overlayText and not self.overlayText.isEmpty():
            self.overlayText.hide()

    def __generatePrepareInterval(self):
        """
        Generates a cute little sequence where we pan the camera to our toon before we start a round.
        """

        players = self.getParticipantsNotSpectating()
        # This is just an edge case to prevent the client from crashing if somehow everyone is spectating.
        if len(players) <= 0:
            return Sequence(
                Wait(CraneGameGlobals.PREPARE_DELAY + CraneGameGlobals.PREPARE_LATENCY_FACTOR),
                Func(self.gameFSM.request, 'play'),
            )

        # If this is a solo crane round, we are not going to play a cutscene. Get right into the action.
        if len(players) == 1:
            return Sequence(
                Wait(CraneGameGlobals.PREPARE_LATENCY_FACTOR),
                Func(self.gameFSM.request, 'play'),
            )

        # Generate a camera track so that the camera slowly pans on to the toon.
        toon = base.localAvatar if not self.localToonSpectating() else self.getParticipantsNotSpectating()[0]
        targetCameraPos = render.getRelativePoint(toon, Vec3(0, -10, toon.getHeight()))
        startCameraHpr = Point3(reduceAngle(camera.getH()), camera.getP(), camera.getR())
        cameraTrack = LerpPosHprInterval(camera, CraneGameGlobals.PREPARE_DELAY / 2.5, Point3(*targetCameraPos), Point3(reduceAngle(toon.getH()), 0, 0), startPos=camera.getPos(), startHpr=startCameraHpr, blendType='easeInOut')

        # Setup a countdown track to display when the round will start. Also at the end, start the game.
        countdownTrack = Sequence()
        for secondsLeft in range(5, 0, -1):
            color = RED_COUNTDOWN_COLOR if secondsLeft > 2 else (ORANGE_COUNTDOWN_COLOR if secondsLeft > 1 else YELLOW_COUNTDOWN_COLOR)
            countdownTrack.append(Func(self.__displayOverlayText, f"{secondsLeft}", color))
            countdownTrack.append(Func(base.playSfx, self.timerTickSfx))
            countdownTrack.append(Wait(1))
        countdownTrack.append(Func(self.__displayOverlayText, 'GO!', CraneGameGlobals.GREEN_COUNTDOWN_COLOR))
        countdownTrack.append(Func(base.playSfx, self.goSfx))
        countdownTrack.append(Wait(CraneGameGlobals.PREPARE_LATENCY_FACTOR))
        countdownTrack.append(Func(self.gameFSM.request, 'play'))

        return Parallel(cameraTrack, countdownTrack)

    def unload(self):
        self.notify.debug("unload")
        DistributedMinigame.unload(self)

        self.geom.removeNode()
        del self.geom

        self.fnp.removeNode()
        self.physicsMgr.clearLinearForces()
        self.music.stop()
        base.cr.forbidCheesyEffects(0)
        localAvatar.setCameraFov(ToontownGlobals.CogHQCameraFov)
        self.music.stop()
        taskMgr.remove(self.uniqueName('physics'))

        # unload resources and delete objects from load() here
        # remove our game ClassicFSM from the framework ClassicFSM
        self.removeChildGameFSM(self.gameFSM)
        del self.gameFSM

    def onstage(self):
        self.notify.debug("onstage")
        DistributedMinigame.onstage(self)
        # start up the minigame; parent things to render, start playing
        # music...
        # at this point we cannot yet show the remote players' toons
        base.localAvatar.reparentTo(render)
        base.localAvatar.loop('neutral')
        base.camLens.setFar(450.0)
        base.transitions.irisIn(0.4)
        NametagGlobals.setMasterArrowsOn(1)
        camera.reparentTo(render)
        camera.setPosHpr(119.541, -260.886, 20, 180, -20, 0)

        #self.setToonsToBattleThreePos()

        # All trolley games call this function, but I am commenting it oukkl12t because I have a suspicion that
        # global smooth node predictions are fighting with physics calculations with CFO objects.
        # I could be wrong, but this seems to be unnecessary since CFO objects appear just fine without this set.
        # DistributedSmoothNode.activateSmoothing(1, 1)

    def offstage(self):
        self.notify.debug("offstage")
        # stop the minigame; parent things to hidden, stop the
        # music...
        DistributedSmoothNode.activateSmoothing(1, 0)
        NametagGlobals.setMasterArrowsOn(0)
        base.camLens.setFar(ToontownGlobals.DefaultCameraFar)

        # the base class parents the toons to hidden, so consider
        # calling it last
        DistributedMinigame.offstage(self)

    def handleDisabledAvatar(self, avId):
        """This will be called if an avatar exits unexpectedly"""
        self.notify.debug("handleDisabledAvatar")
        self.notify.debug("avatar " + str(avId) + " disabled")
        # clean up any references to the disabled avatar before he disappears

        # then call the base class
        DistributedMinigame.handleDisabledAvatar(self, avId)

    def setGameReady(self):
        if not self.hasLocalToon: return
        self.notify.debug("setGameReady")
        if DistributedMinigame.setGameReady(self):
            return
        # all of the remote toons have joined the game;
        # it's safe to show them now.

        self.setToonsToRulesPositions()

        for toon in self.getParticipants():
            toon.startSmooth()

        base.localAvatar.d_clearSmoothing()
        base.localAvatar.sendCurrentPosition()
        base.localAvatar.b_setAnimState('neutral', 1)
        base.localAvatar.b_setParent(ToontownGlobals.SPRender)

    def __generateRulesPanel(self):
        panel = CraneGameSettingsPanel(self.getTitle(), self.rulesDoneEvent)
        # Create buttons via GameButtonsUI
        if hasattr(self, 'gameButtonsUI'):
            self.gameButtonsUI.createButtons(self.rulesDoneEvent)
        return panel

    # Button handlers now delegated to GameButtonsUI
    # Old methods removed - see GameButtonsUI class
    
    # Modifier panel state sync removed - not needed, UI class manages its own state
    
    # Modifier panel UI methods now delegated to ModifierPanelUI
    # Old methods removed - see ModifierPanelUI class

    def __cleanupRulesPanel(self):
        self.ignore(self.rulesDoneEvent)
        self.ignore('spotStatusChanged')
        # Clean up buttons via GameButtonsUI
        if hasattr(self, 'gameButtonsUI'):
            self.gameButtonsUI.cleanup()
        # Clean up modifier panel UI
        if hasattr(self, 'modifierPanelUI'):
            self.modifierPanelUI.cleanup()
        if self.rulesPanel is not None:
            self.rulesPanel.cleanup()
            self.rulesPanel = None
    
    def __createDroneSelectionUI(self):
        """Create the drone selection UI - delegate to DroneSelectionUI"""
        self.droneSelectionUI.createSelectionUI()
    
    # Drone selection state sync removed - not needed, UI class manages its own state
    
    def __cleanupDroneSelectionUI(self):
        """Clean up the drone selection UI - delegate to DroneSelectionUI"""
        if hasattr(self, 'droneSelectionUI'):
            self.droneSelectionUI.cleanup()
    
    # Drone selection UI methods now delegated to DroneSelectionUI
    # Old methods removed - see DroneSelectionUI class
    
    def __areDronesEnabled(self):
        """Check if drones are enabled via the modifier system."""
        if hasattr(self, 'droneSelectionUI'):
            return self.droneSelectionUI._areDronesEnabled()
        # Fallback if UI doesn't exist yet
        if not hasattr(self, 'ruleset') or not self.ruleset:
            return False
        return getattr(self.ruleset, 'WANT_DRONES', False)
    
    def __updateDroneUIVisibility(self):
        """Update drone UI visibility - delegate to DroneSelectionUI"""
        if hasattr(self, 'droneSelectionUI'):
            self.droneSelectionUI.updateVisibility()
    
    def __updateDroneSlotUI(self, slotIndex):
        """Update the UI for a specific drone slot - delegate to DroneSelectionUI"""
        if hasattr(self, 'droneSelectionUI'):
            self.droneSelectionUI.updateSlotUI(slotIndex)
    
    def setDroneTypeForToon(self, avId, slotIndex, droneTypeValue):
        """Delegate to DroneManager"""
        self.droneManager.setDroneTypeForToon(avId, slotIndex, droneTypeValue)
        
        # Update UI if it's the local toon or the spectated player
        localAvId = base.localAvatar.doId
        spectatedAvId = None
        if hasattr(self, 'scoreboard') and self.scoreboard is not None:
            spectatedAvId = self.scoreboard.getSpectatedAvId()
        
        if avId == localAvId or (spectatedAvId is not None and avId == spectatedAvId):
            if hasattr(self, 'droneSelectionUI'):
                self.droneSelectionUI.updateSlotUI(slotIndex)

    def updateRequiredElements(self):
        # Clean up existing timer if it exists
        if hasattr(self, 'bossSpeedrunTimer') and self.bossSpeedrunTimer is not None:
            self.bossSpeedrunTimer.cleanup()
        
        # Recreate timer
        self.bossSpeedrunTimer = BossSpeedrunTimedTimer(
            time_limit=self.ruleset.TIMER_MODE_TIME_LIMIT) if self.ruleset.TIMER_MODE else BossSpeedrunTimer()
        self.bossSpeedrunTimer.hide()
        self.updateRulesetDependencies()

    def updateRulesetDependencies(self):
        # Recreate scoreboard if it doesn't exist
        if not hasattr(self, 'scoreboard') or self.scoreboard is None:
            self.scoreboard = CashbotBossScoreboard(ruleset=self.ruleset)
            self.scoreboard.hide()
        else:
            # If the scoreboard exists, update the ruleset
            self.scoreboard.set_ruleset(self.ruleset)

        # Recreate heat display if it doesn't exist
        if not hasattr(self, 'heatDisplay') or self.heatDisplay is None:
            self.heatDisplay = CraneLeagueHeatDisplay()
            self.heatDisplay.hide()
        
        self.heatDisplay.update(self.modifierManager.modifiers)

        if self.boss is not None:
            self.boss.setRuleset(self.ruleset)
        
        # Update back wall based on ruleset
        if self.ruleset.WANT_BACKWALL:
            self.enableBackWall()
        else:
            self.disableBackWall()
        
        # Update drone UI visibility when ruleset changes
        self.__updateDroneUIVisibility()

    def setRawRuleset(self, attrs):
        self.ruleset = CraneGameGlobals.CraneGameRuleset.fromStruct(attrs)
        self.notify.debug(f"setRawRuleset: WANT_DRONES = {getattr(self.ruleset, 'WANT_DRONES', 'NOT_SET')}")
        self.updateRulesetDependencies()
        # Update drone UI visibility when ruleset changes
        if hasattr(self, 'droneSelectionUI'):
            self.droneSelectionUI.updateVisibility()

    def getRawRuleset(self):
        return self.ruleset.asStruct()

    def getRuleset(self):
        return self.ruleset

    def __doPhysics(self, task):
        dt = globalClock.getDt()
        self.physicsMgr.doPhysics(dt)
        return task.cont

    def setGameStart(self, timestamp):
        if not self.hasLocalToon: return
        self.notify.debug("setGameStart")
        # base class will cause gameFSM to enter initial state
        DistributedMinigame.setGameStart(self, timestamp)
        # all players have finished reading the rules,
        # and are ready to start playing.
        # transition to the appropriate state
        self.gameFSM.request("prepare")

    # these are enter and exit functions for the game's
    # fsm (finite state machine)

    def enterOff(self):
        self.notify.debug("enterOff")
        self.__checkSpectatorState(spectate=False)
        self.__cleanupRulesPanel()
        # Clean up drone UI
        if hasattr(self, 'droneSelectionUI'):
            self.droneSelectionUI.cleanup()
        # Clean up forfeit/restart dialogs via UI
        if hasattr(self, 'forfeitRestartDialogsUI'):
            self.forfeitRestartDialogsUI.cleanup()

    def exitOff(self):
        pass

    def enterPrepare(self):
        camera.wrtReparentTo(render)
        self.setToonsToBattleThreePos()
        base.localAvatar.d_clearSmoothing()
        base.localAvatar.sendCurrentPosition()
        base.localAvatar.b_setAnimState('neutral', 1)
        base.localAvatar.b_setParent(ToontownGlobals.SPRender)

        # Display Modifiers Heat
        self.updateRequiredElements()

        # Ensure scoreboard exists (updateRequiredElements should have created it, but double-check)
        if not hasattr(self, 'scoreboard') or self.scoreboard is None:
            self.scoreboard = CashbotBossScoreboard(ruleset=self.ruleset)
            self.scoreboard.hide()

        # Setup the scoreboard
        self.scoreboard.clearToons()
        

        # Normal mode: show all non-spectators
        for avId in self.getParticipantIdsNotSpectating():
            self.scoreboard.addToon(avId)
        
        # Normal flow: start countdown immediately
        self.introductionMovie = self.__generatePrepareInterval()
        self.introductionMovie.start()

        # Clean up all status effects when starting a new round
        if hasattr(self, 'statusEffectSystem') and self.statusEffectSystem:
            self.statusEffectSystem.cleanup()

        # Make absolutely sure all indicators are cleaned up
        self.removeStatusIndicators()
        self.boss.prepareBossForBattle()

    def exitPrepare(self):
        if self.introductionMovie:
            self.introductionMovie.pause()
            self.introductionMovie = None
        self.__hideOverlayText()
        # Clean up match ready UI

    def enterPlay(self):
        self.__cleanupRulesPanel()
        taskMgr.remove(self.uniqueName("craneGameVictory"))
        self.notify.debug("enterPlay")
        self.evWalls.unstash()
        base.playMusic(self.music, looping=1, volume=0.9)

        # Make absolutely sure all indicators are cleaned up
        self.removeStatusIndicators()

        # It is important to make sure this task runs immediately
        # before the collisionLoop of ShowBase.  That will fix up the
        # z value of the safes, etc., before their position is
        # distributed.
        taskMgr.remove(self.uniqueName("physics"))
        taskMgr.add(self.__doPhysics, self.uniqueName('physics'), priority=25)

        # Allow us to play the game.
        self.walkStateData.enter()
        localAvatar.orbitalCamera.start()
        localAvatar.setCameraFov(ToontownGlobals.BossBattleCameraFov)
        self.toFinalBattleMode()

        # Display Boss Timer
        self.bossSpeedrunTimer.reset()
        self.bossSpeedrunTimer.start_updating()
        self.bossSpeedrunTimer.show()

        self.accept("LocalSetFinalBattleMode", self.toFinalBattleMode)
        self.accept("LocalSetOuchMode", self.toOuchMode)
        self.accept("ChatMgr-enterMainMenu", self.chatClosed)
        self.accept("spectatedPlayerChanged", self.__onSpectatedPlayerChanged)
        
        # Only enable drones if the modifier is active
        if self.__areDronesEnabled():
            # Enable drone deployment keybinds for 3 slots from settings (both binds)
            slotKeyNames = ['DRONE_SLOT_0_KEY', 'DRONE_SLOT_1_KEY', 'DRONE_SLOT_2_KEY']
            if hasattr(self, 'droneSelectionUI'):
                self.droneSelectionUI.droneSlotKeybinds = []
                for i, keyName in enumerate(slotKeyNames):
                    # Get both binds for this slot
                    binds = base.settings.getControlBinds(keyName)
                    for bind in binds:
                        if bind:
                            self.droneSelectionUI.droneSlotKeybinds.append(bind)
                            self.accept(bind, self.__deployDrone, [i])
            
            # Move drone UI next to laff meter (right side) and show it
            # If drone UI doesn't exist (shouldn't happen, but be safe), create it
            if not hasattr(self, 'droneSelectionUI') or self.droneSelectionUI.droneSelectionFrame is None:
                self.droneSelectionUI.createSelectionUI()
            
            if self.droneSelectionUI.droneSelectionFrame:
                # Laff meter is at base.a2dBottomLeft with pos around (0.133-0.153, 0.0, 0.13)
                # Position drone UI to the right of it with sufficient spacing
                self.droneSelectionUI.droneSelectionFrame.reparentTo(base.a2dBottomLeft)
                self.droneSelectionUI.droneSelectionFrame.setPos(0.72, 0.0, 0.13)
                # Show the UI
                self.droneSelectionUI.droneSelectionFrame.show()
            
            # Initialize cooldown displays for all slots
            # Use spectated player's data if spectating, otherwise use local toon's data
            localAvId = base.localAvatar.doId
            targetAvId = localAvId
            if hasattr(self, 'scoreboard') and self.scoreboard is not None:
                spectatedAvId = self.scoreboard.getSpectatedAvId()
                if spectatedAvId is not None:
                    targetAvId = spectatedAvId
            
            for i in range(3):
                if targetAvId in self.droneManager.droneCooldowns and i in self.droneManager.droneCooldowns[targetAvId]:
                    startTime, duration = self.droneManager.droneCooldowns[targetAvId][i]
                    self.droneSelectionUI.updateSlotCooldown(i, startTime, duration)
                else:
                    self.droneSelectionUI.updateSlotCooldown(i, None, None)
        else:
            # Drones disabled - hide UI if it exists
            if hasattr(self, 'droneSelectionUI') and self.droneSelectionUI.droneSelectionFrame:
                self.droneSelectionUI.droneSelectionFrame.hide()

        if base.WANT_FOV_EFFECTS and base.localAvatar.isSprinting:
            base.localAvatar.lerpFov(base.localAvatar.fov, base.localAvatar.fallbackFov + base.localAvatar.currentMovementMode[base.localAvatar.FOV_INCREASE_ENUM])

        self.__checkSpectatorState()
    
    def __deployDrone(self, slotIndex=0):
        """Deploy a drone above the local toon using the selected slot."""
        if not self.hasLocalToon:
            return
        
        # Check if this specific slot is on cooldown
        currentTime = globalClock.getFrameTime()
        localAvId = base.localAvatar.doId
        if localAvId in self.droneManager.droneCooldowns and slotIndex in self.droneManager.droneCooldowns[localAvId]:
            startTime, duration = self.droneManager.droneCooldowns[localAvId][slotIndex]
            endTime = startTime + duration
            if currentTime < endTime:
                # Still on cooldown, don't send request
                return
        
        # Request drone deployment from server with slot index
        self.sendUpdate('requestDeployDrone', [slotIndex])

    def exitPlay(self):

        if self.boss is not None:
            self.boss.cleanupBossBattle()

        self.scoreboard.disableSpectating()
        self.scoreboard.finish()

        self.walkStateData.exit()
        
        # Clean up drone UI (includes cooldown tasks)
        if hasattr(self, 'droneSelectionUI'):
            # Note: We don't fully cleanup here, just hide, as UI may be needed in next round
            if self.droneSelectionUI.droneSelectionFrame:
                self.droneSelectionUI.droneSelectionFrame.hide()
            # Clean up cooldown tasks
            if self.droneSelectionUI.droneSelectionSlots:
                for slot in self.droneSelectionUI.droneSelectionSlots:
                    if slot.get('cooldownTask'):
                        taskMgr.remove(slot['cooldownTask'])
                        slot['cooldownTask'] = None
        
        # Disable drone deployment keybinds
        if hasattr(self, 'droneSelectionUI') and self.droneSelectionUI.droneSlotKeybinds:
            for keybind in self.droneSelectionUI.droneSlotKeybinds:
                self.ignore(keybind)
            self.droneSelectionUI.droneSlotKeybinds = []
        

        # Clean up all status effects when exiting play state
        if hasattr(self, 'statusEffectSystem') and self.statusEffectSystem:
            self.statusEffectSystem.cleanup()
    
    def setDroneCooldown(self, avId, slotIndex, duration):
        """Delegate to DroneManager"""
        self.droneManager.setDroneCooldown(avId, slotIndex, duration)
        
        # Update UI for local toon or spectated player
        localAvId = base.localAvatar.doId
        spectatedAvId = None
        if hasattr(self, 'scoreboard') and self.scoreboard is not None:
            spectatedAvId = self.scoreboard.getSpectatedAvId()
        
        if avId == localAvId or (spectatedAvId is not None and avId == spectatedAvId):
            # Get cooldown info from manager
            if avId in self.droneManager.droneCooldowns and slotIndex in self.droneManager.droneCooldowns[avId]:
                startTime, duration = self.droneManager.droneCooldowns[avId][slotIndex]
                if hasattr(self, 'droneSelectionUI'):
                    self.droneSelectionUI.updateSlotCooldown(slotIndex, startTime, duration)
    
    def clearAllDroneCooldowns(self):
        """Delegate to DroneManager"""
        self.droneManager.clearAllDroneCooldowns()
        # Update all slot cooldown displays
        if hasattr(self, 'droneSelectionUI'):
            for i in range(3):
                self.droneSelectionUI.updateSlotCooldown(i, None, None)
    
    def __onSpectatedPlayerChanged(self, avId):
        """Called when the spectator switches to a different player."""
        # Update all drone slot UIs and cooldowns for the new spectated player
        if not self.__areDronesEnabled():
            return
        
        # Get target avId (spectated player or local toon)
        localAvId = base.localAvatar.doId
        targetAvId = avId if avId is not None else localAvId
        
        # Update all slots
        if hasattr(self, 'droneSelectionUI'):
            for i in range(3):
                # Update drone type display
                self.droneSelectionUI.updateSlotUI(i)
                
                # Update cooldown display
                if targetAvId in self.droneManager.droneCooldowns and i in self.droneManager.droneCooldowns[targetAvId]:
                    startTime, duration = self.droneManager.droneCooldowns[targetAvId][i]
                    self.droneSelectionUI.updateSlotCooldown(i, startTime, duration)
                else:
                    self.droneSelectionUI.updateSlotCooldown(i, None, None)

    def __updateDroneSlotCooldown(self, slotIndex, startTime, duration):
        """Update the cooldown display for a specific drone slot - delegate to DroneSelectionUI"""
        if hasattr(self, 'droneSelectionUI'):
            self.droneSelectionUI.updateSlotCooldown(slotIndex, startTime, duration)
    
    def __showDroneCooldownIndicator(self, startTime, duration):
        """Display the drone cooldown indicator near the leave button."""

        # Clean up existing indicator
        self.__cleanupDroneCooldownIndicator()
        
        # Create cooldown text indicator (simple version)
        # Note: Change the first value in pos (X coordinate) to move left/right
        # Increase X to move right, decrease to move left
        self.droneCooldownText = OnscreenText(
            text='',
            pos=(1.6, -0.9),  # Changed from 1.05 to 1.6 (moved right)
            scale=0.05,
            fg=(1, 0.3, 0.3, 1),
            align=TextNode.ACenter,
            mayChange=True,
            parent=aspect2d
        )
        
        # Store cooldown info
        self.droneCooldownStartTime = startTime
        self.droneCooldownDuration = duration
        
        # Start update task
        if self.droneCooldownTask:
            taskMgr.remove(self.droneCooldownTask)
        self.droneCooldownTask = taskMgr.add(
            self.__updateDroneCooldownTask,
            'droneCooldownTask',
            extraArgs=[],
            appendTask=True
        )
    
    def __updateDroneCooldownTask(self, task):
        """Update the drone cooldown display."""
        if not self.droneCooldownText:
            return task.done
        
        currentTime = globalClock.getFrameTime()
        elapsed = currentTime - self.droneCooldownStartTime
        remaining = max(0, self.droneCooldownDuration - elapsed)
        
        if remaining <= 0:
            # Cooldown finished - keep showing "Ready" until round ends
            self.droneCooldownText['text'] = 'Drone Ready!'
            self.droneCooldownText['fg'] = (0.3, 1.0, 0.3, 1)
            # Keep the task running to maintain the display
            return task.cont
        else:
            # Show remaining time
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            self.droneCooldownText['text'] = f'Drone: {minutes}:{seconds:02d}'
        
        return task.cont
    
    def __cleanupDroneCooldownIndicator(self, task=None):
        """Remove the drone cooldown indicator."""
        if self.droneCooldownTask:
            taskMgr.remove(self.droneCooldownTask)
            self.droneCooldownTask = None
        
        if self.droneCooldownText:
            self.droneCooldownText.destroy()
            self.droneCooldownText = None
        
        return task.done if task else None
    
    def __initializeDroneIndicator(self):
        """Initialize the drone indicator at the start of play."""
        # Check if local toon has an active cooldown
        localAvId = base.localAvatar.doId
        # Note: This method seems to expect a single cooldown, but we now have per-slot cooldowns
        # This method may need refactoring, but for now we'll check the first slot
        if localAvId in self.droneManager.droneCooldowns and 0 in self.droneManager.droneCooldowns[localAvId]:
            startTime, duration = self.droneManager.droneCooldowns[localAvId][0]
            # If cooldown is still active, show it
            self.__showDroneCooldownIndicator(startTime, duration)
        else:
            # No cooldown, show "Drone Ready!"
            self.__showDroneReadyIndicator()
    
    def __showDroneReadyIndicator(self):
        """Show the 'Drone Ready!' indicator without a cooldown."""

        # Clean up existing indicator
        self.__cleanupDroneCooldownIndicator()
        
        # Create "Drone Ready!" text
        self.droneCooldownText = OnscreenText(
            text='Drone Ready!',
            pos=(1.4, -0.9),
            scale=0.05,
            fg=(0.3, 1.0, 0.3, 1),
            align=TextNode.ACenter,
            mayChange=True,
            parent=aspect2d
        )
    
    def __cleanupAllDrones(self):
        """Request the server to clean up all active drones."""
        # Send a request to the AI to clean up all drones
        self.sendUpdate('requestCleanupDrones', [])

    def enterVictory(self):
        if self.victor == 0:
            return

        # Clean up all drones when round ends
        self.__cleanupAllDrones()
        
        # Clear local cooldown cache (delegated to DroneManager)
        self.droneManager.clearAllDroneCooldowns()
        
        # Clean up drone slot cooldown tasks
        if hasattr(self, 'droneSelectionSlots'):
            for slot in self.droneSelectionSlots:
                if slot.get('cooldownTask'):
                    taskMgr.remove(slot['cooldownTask'])
                    slot['cooldownTask'] = None
        
        # Clean up all status effects when round ends
        if hasattr(self, 'statusEffectSystem') and self.statusEffectSystem:
            self.statusEffectSystem.cleanup()

        victor = base.cr.getDo(self.victor)
        if self.victor == self.localAvId:
            base.playSfx(self.winSting)
        else:
            base.playSfx(self.loseSting)
        camera.reparentTo(victor)
        camera.setPosHpr(0, 8, victor.getHeight() / 2.0, 180, 0, 0)

        victor.setAnimState("victory")

        # Check if this is a multi-round match
        if self.roundManager.bestOfValue > 1:
            # Check round wins
            roundWins = self.roundManager.roundWins.get(self.victor, 0)
            winsNeeded = (self.roundManager.bestOfValue + 1) // 2
            if roundWins >= winsNeeded:
                # Match is over - use normal victory flow
                taskMgr.doMethodLater(5, self.gameOver, self.uniqueName("craneGameVictory"), extraArgs=[])
                # Safety timeout: force gameOver after 30 seconds if something goes wrong
                taskMgr.doMethodLater(30, self.gameOver, self.uniqueName("craneGameVictorySafety"), extraArgs=[])
            else:
                # Round is over, but match continues - shorter victory time
                taskMgr.doMethodLater(5, self.__nextRound, self.uniqueName("craneGameNextRound"), extraArgs=[])
                # Safety timeout: force next round after 15 seconds if something goes wrong
                taskMgr.doMethodLater(15, self.__nextRound, self.uniqueName("craneGameNextRoundSafety"), extraArgs=[])
        else:
            # Single round match
            taskMgr.doMethodLater(5, self.gameOver, self.uniqueName("craneGameVictory"), extraArgs=[])
            # Safety timeout: force gameOver after 30 seconds if something goes wrong
            taskMgr.doMethodLater(30, self.gameOver, self.uniqueName("craneGameVictorySafety"), extraArgs=[])
        
        for crane in self.cranes.values():
            crane.stopFlicker()

    def exitVictory(self):
        taskMgr.remove(self.uniqueName("craneGameVictory"))
        taskMgr.remove(self.uniqueName("craneGameNextRound"))
        taskMgr.remove(self.uniqueName("craneGameVictorySafety"))
        taskMgr.remove(self.uniqueName("craneGameNextRoundSafety"))
        camera.reparentTo(base.localAvatar)

    def enterCleanup(self):
        self.notify.debug("enterCleanup")
        self.__cleanupRulesPanel()
        
        # Clean up forfeit/restart dialogs via UI
        if hasattr(self, 'forfeitRestartDialogsUI'):
            self.forfeitRestartDialogsUI.cleanup()
        
        # Clean up all drones when entering cleanup
        self.__cleanupAllDrones()
        
        # Clear local cooldown cache (delegated to DroneManager)
        self.droneManager.clearAllDroneCooldowns()
        
        # Clean up drone slot cooldown tasks
        if hasattr(self, 'droneSelectionSlots'):
            for slot in self.droneSelectionSlots:
                if slot.get('cooldownTask'):
                    taskMgr.remove(slot['cooldownTask'])
                    slot['cooldownTask'] = None
        
        # Clean up drone selection UI
        self.__cleanupDroneSelectionUI()
        
        for toon in self.getParticipants():
            toon.setGhostMode(False)
            toon.show()
            toon.setZ(0) # Reset Z position
        self.overlayText.removeNode()

        self.scoreboardShowAllParticipants = False
        
        # Clean up timer
        if hasattr(self, 'bossSpeedrunTimer') and self.bossSpeedrunTimer is not None:
            self.bossSpeedrunTimer.cleanup()
            self.bossSpeedrunTimer = None
        
        # Clean up scoreboard
        if hasattr(self, 'scoreboard') and self.scoreboard is not None:
            self.scoreboard.cleanup()
            self.scoreboard = None
        
        # Clean up heat display
        if hasattr(self, 'heatDisplay') and self.heatDisplay is not None:
            self.heatDisplay.cleanup()
            self.heatDisplay = None
        
        self.boss = None
        
        # Cleanup status effect system
        if hasattr(self, 'statusEffectSystem') and self.statusEffectSystem:
            self.statusEffectSystem.cleanup()

    def exitCleanup(self):
        pass

    """
    Updates from server to client
    """

    def setBossCogId(self, bossCogId: int) -> None:
        self.boss = base.cr.getDo(bossCogId)
        self.boss.game = self
        self.boss.setRuleset(self.ruleset)

    def getStatusEffectSystem(self) -> DistributedStatusEffectSystem | None:
        return self.statusEffectSystem
    
    def setStatusEffectSystemId(self, statusEffectSystemId: int) -> None:
        self.statusEffectSystem = base.cr.getDo(statusEffectSystemId)

    def addScore(self, avId: int, score: int, reason: str):

        # Convert the reason into a valid reason enum that our scoreboard accepts.
        convertedReason = CraneGameGlobals.ScoreReason.from_astron(reason)
        if convertedReason is None:
            convertedReason = CraneGameGlobals.ScoreReason.DEFAULT
        self.scoreboard.addScore(avId, score, convertedReason)

    def updateCombo(self, avId, comboLength):
        if self.scoreboard is None:
            return
        self.scoreboard.setCombo(avId, comboLength)

    def updateTimer(self, secs):
        if self.bossSpeedrunTimer:
            self.bossSpeedrunTimer.override_time(secs)
            self.bossSpeedrunTimer.update_time()

    def declareVictor(self, avId: int) -> None:
        self.victor = avId
        self.gameFSM.request("victory")

    def setOvertime(self, flag):
        if flag == CraneGameGlobals.OVERTIME_FLAG_START:
            self.overtimeActive = True
            self.ruleset.REVIVE_TOONS_UPON_DEATH = False
        elif flag == CraneGameGlobals.OVERTIME_FLAG_ENABLE:
            if self.bossSpeedrunTimer:
                self.bossSpeedrunTimer.show_overtime()
        else:
            self.overtimeActive = False
            if self.bossSpeedrunTimer:
                self.bossSpeedrunTimer.hide_overtime()

    # setModifiers now delegated to ModifierManager - see method at line 2321

    def restart(self):
        """
        Called via astron update. Do any client side logic needed in order to restart the game.
        """
        self.gameFSM.request('prepare')

    """
    Everything else!!!!
    """

    def deactivateCranes(self):
        # This locally knocks all toons off cranes.
        for crane in self.cranes.values():
            crane.demand('Free')

    def hideBattleThreeObjects(self):
        # This turns off all the goons, safes, and cranes on the local
        # client. It's played only during the victory movie, to get
        # these guys out of the way.
        for goon in self.goons:
            goon.demand('Off')

        for safe in self.safes.values():
            safe.demand('Off')

        for crane in self.cranes.values():
            crane.demand('Off')

    def toonDied(self, avId):
        self.scoreboard.toonDied(avId)

    def revivedToon(self, avId):
        self.scoreboard.toonRevived(avId)
        if avId == base.localAvatar.doId:
            self.boss.localToonIsSafe = False
            base.localAvatar.stunToon()

    def getBoss(self):
        return self.boss

    def toCraneMode(self):
        self.walkStateData.fsm.request('crane')

    def toFinalBattleMode(self, checkForOuch: bool = False):
        if not checkForOuch or self.walkStateData.fsm.getCurrentState().getName() != 'ouch':
            self.walkStateData.fsm.request('walking')

    def toOuchMode(self):
        self.walkStateData.fsm.request('ouch')

    def chatClosed(self):
        if self.walkStateData.fsm.getCurrentState().getName() == "walking":
            base.localAvatar.enableAvatarControls()

    def setToonsToRulesPositions(self):
        """
        Places toons in front of the vault during the rules state.
        Creates a symmetric linear layout with multiple rows that expand from the center.
        """
        centerPoint = self.endVault.getPos()
        spacing = 5.5  # Horizontal space between toons
        rowSpacing = 5.5  # Space between rows
        
        # Get all participants, both playing and spectating
        allToons = self.getParticipants()
        numToons = len(allToons)
        
        # Calculate optimal row configuration
        if numToons <= 6:
            # Single row for 6 or fewer toons
            numRows = 1
            toonsPerRow = numToons
            baseY = centerPoint.getY() - 92  # Center position for single row
        elif numToons <= 12:
            # Two rows for 7-12 toons
            numRows = 2
            toonsPerRow = (numToons + 1) // 2
            baseY = centerPoint.getY() - 90  # Move first row forward from center
        else:
            # Three rows for 13-16 toons
            numRows = 3
            toonsPerRow = (numToons + 2) // 3
            baseY = centerPoint.getY() - 88  # Move first row even more forward
        
        # Position each toon
        toonIndex = 0
        for row in range(numRows):
            # Calculate how many toons go in this row
            toonsThisRow = min(toonsPerRow, numToons - (row * toonsPerRow))
            if toonsThisRow <= 0:
                break
                
            # Calculate row-specific adjustments
            rowWidth = (toonsThisRow - 1) * spacing
            rowStartX = centerPoint.getX() + 36 - (rowWidth / 2)
            rowY = baseY - (row * rowSpacing)  # Each back row moves back by rowSpacing
            
            # Position toons in this row
            for i in range(toonsThisRow):
                toon = allToons[toonIndex]
                if not toon:
                    continue
                
                # Calculate position
                x = rowStartX + (i * spacing)
                y = rowY
                z = 0
                h = 0
                
                # Position the toon
                if toon.doId == base.localAvatar.doId:
                    toon.setPos(x, y, z)
                    toon.setH(h)
                    toon.d_setXY(x, y)
                    toon.d_setH(h)
                    if hasattr(toon, 'd_clearSmoothing'):
                        toon.d_clearSmoothing()
                    if hasattr(toon, 'sendCurrentPosition'):
                        toon.sendCurrentPosition()
                else:
                    toon.setPos(x, y, z)
                    toon.setH(h)
                    if hasattr(toon, 'clearSmoothing'):
                        toon.clearSmoothing()
                    if hasattr(toon, 'startSmooth'):
                        toon.startSmooth()
                
                # Create or update status indicator
                isPlayer = toon.doId not in self.getSpectators()
                if toon.doId in self.statusIndicators:
                    self.updateStatusIndicator(toon, isPlayer)
                else:
                    self.createStatusIndicator(toon, isPlayer)
                
                toonIndex += 1

    def enterFrameworkRules(self):
        self.notify.debug('enterFrameworkRules')
        self.accept(self.rulesDoneEvent, self.handleRulesDone)
        
        # Create and show the rules panel
        self.rulesPanel = self.__generateRulesPanel()
        self.rulesPanel.load()
        # Hide the panel by default
        self.rulesPanel.hide()



        # Show buttons via GameButtonsUI
        if hasattr(self, 'gameButtonsUI'):
            self.gameButtonsUI.showButtons()

        # Position toons in the rules formation
        self.setToonsToRulesPositions()

        # Only setup click detection for the leader
        if self.isLocalToonHost():
            # Make sure the click ray is using our spotlight bitmask
            self.clickRayNode.setFromCollideMask(self.spotlightBitMask)
            self.accept('mouse1', self.handleMouseClick)

        # Hide all toon shadows
        for toon in self.getParticipants():
            if toon and hasattr(toon, 'dropShadow') and toon.dropShadow:
                toon.dropShadow.hide()

        # Accept spot status change messages
        self.accept('spotStatusChanged', self.handleSpotStatusChanged)
        
        # Clean up any existing drone UI first (in case of restart)
        self.__cleanupDroneSelectionUI()
        
        # Always load saved drone setup from toon (even if drones aren't enabled yet)
        # This ensures the setup is ready when the modifier is added
        # Load drone setup via DroneSelectionUI
        if hasattr(self, 'droneSelectionUI'):
            self.droneSelectionUI._loadDroneSetupFromToon()
        
        # Always create drone selection UI (it will be hidden if drones aren't enabled)
        self.__createDroneSelectionUI()
        
        # Update visibility based on current modifier state
        self.__updateDroneUIVisibility()

    def exitFrameworkRules(self):
        # Restore all toon shadows
        for toon in self.getParticipants():
            if toon and hasattr(toon, 'dropShadow') and toon.dropShadow:
                toon.dropShadow.show()
        
        # Clean up click detection
        self.ignore('mouse1')
        
        # Clean up any pending auto-ready task
        taskMgr.remove(self.uniqueName('auto-ready'))
            
        # Make sure to clean up all indicators
        self.removeStatusIndicators()
        self.__cleanupRulesPanel()
        # Don't destroy drone UI - just hide it, we'll show it again in enterPlay
        if hasattr(self, 'droneSelectionUI') and self.droneSelectionUI.droneSelectionFrame:
            self.droneSelectionUI.droneSelectionFrame.hide()

    def handleMouseClick(self):
        """Handle mouse clicks during the rules state to detect clicks on spotlights."""
        # Only the leader can click
        if not self.isLocalToonHost():
            return
        
        # Get the mouse position
        if not base.mouseWatcherNode.hasMouse():
            return
        
        mpos = base.mouseWatcherNode.getMouse()
        
        # Set up the collision ray
        self.clickRay.setFromLens(base.camNode, mpos.getX(), mpos.getY())
        
        # Traverse and check for collisions
        base.cTrav.traverse(render)
        
        # Check the collision queue
        if self.clickRayQueue.getNumEntries() > 0:
            self.clickRayQueue.sortEntries()
            entry = self.clickRayQueue.getEntry(0)
            clickedNode = entry.getIntoNodePath()
            pickedObject = clickedNode.findNetTag('toonId')
            
            if not pickedObject.isEmpty():
                avId = int(pickedObject.getTag('toonId'))
                # Find the index of this toon in avIdList
                if avId in self.avIdList:
                    spotIndex = self.avIdList.index(avId)
                    # Toggle the status - if they're in spectators, make them a player and vice versa
                    currentlySpectating = avId in self.getSpectators()
                    # Send update to server to handle the status change
                    self.sendUpdate('handleSpotStatusChanged', [spotIndex, currentlySpectating])

    def handleRulesDone(self):
        self.notify.debug('BASE: handleRulesDone')
        self.sendUpdate('setAvatarReady', [])
        self.frameworkFSM.request('frameworkWaitServerStart')

    def handleSpotStatusChanged(self, spotIndex, isPlayer):
        """
        Called when a spot's status is changed between Player and Spectator.
        This is called on all clients when any client changes a spot's status.
        """
        if spotIndex >= len(self.avIdList):
            return
            
        changedAvId = self.avIdList[spotIndex]
        changedToon = self.cr.getDo(changedAvId)
        if changedToon:
                if changedAvId in self.statusIndicators:
                    self.updateStatusIndicator(changedToon, isPlayer)
                else:
                    self.createStatusIndicator(changedToon, isPlayer)

    def createStatusIndicator(self, toon, isPlayer):
        """Creates a spotlight indicator for a toon's status (player or spectator)"""
        # Create the camera model and spotlight effect
        indicator = NodePath('statusIndicator')
        indicator.reparentTo(render)
            
        # Position the camera above
        cameraHeight = 8
        projector = Point3(0, 0, cameraHeight)
        
        # Create the beam and floor nodes
        beamNode = indicator.attachNewNode('beamNode')
        floorNode = indicator.attachNewNode('floorNode')
        
        # Setup rendering attributes for both
        for node in (beamNode, floorNode):
            node.setTransparency(1)
            node.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
            node.setTwoSided(False)
            node.setDepthWrite(False)
        
        # Create geometry for beam and floor
        beamVertexData = GeomVertexData('beam', GeomVertexFormat.getV3cp(), Geom.UHDynamic)
        floorVertexData = GeomVertexData('floor', GeomVertexFormat.getV3cp(), Geom.UHDynamic)
        
        beamVertexWriter = GeomVertexWriter(beamVertexData, 'vertex')
        beamColorWriter = GeomVertexWriter(beamVertexData, 'color')
        floorVertexWriter = GeomVertexWriter(floorVertexData, 'vertex')
        floorColorWriter = GeomVertexWriter(floorVertexData, 'color')
        
        # Default colors (will be updated in updateStatusIndicator)
        normalColor = VBase4(0.2, 0.2, 0.2, 0.3)
        
        # Create beam geometry (from projector to ground)
        radius = 1.8
        beamVertexWriter.addData3f(projector[0], projector[1], projector[2])
        beamColorWriter.addData4f(normalColor)
        
        # Create circle points for beam
        for angle in range(0, 360, 45):
            x = radius * math.cos(math.radians(angle))
            y = radius * math.sin(math.radians(angle))
            beamVertexWriter.addData3f(x, y, 0.025)
            beamColorWriter.addData4f(VBase4(0, 0, 0, 0))
            
        # Create floor geometry (circle on ground)
        floorVertexWriter.addData3f(0, 0, 0.025)
        floorColorWriter.addData4f(normalColor)
        
        # Create circle points for floor
        for angle in range(0, 360, 10):
            x = radius * math.cos(math.radians(angle))
            y = radius * math.sin(math.radians(angle))
            floorVertexWriter.addData3f(x, y, 0.025)
            floorColorWriter.addData4f(VBase4(0, 0, 0, 0))
            
        # Create beam triangles
        beamTris = GeomTrifans(Geom.UHStatic)
        beamTris.addVertex(0)
        for i in range(1, 9):
            beamTris.addVertex(i)
        beamTris.addVertex(1)
        beamTris.closePrimitive()
        
        # Create floor triangles
        floorTris = GeomTrifans(Geom.UHStatic)
        floorTris.addVertex(0)
        for i in range(1, 37):
            floorTris.addVertex(i)
        floorTris.addVertex(1)
        floorTris.closePrimitive()
        
        # Create and attach geometry nodes
        beamGeom = Geom(beamVertexData)
        beamGeom.addPrimitive(beamTris)
        beamGeomNode = GeomNode('beam')
        beamGeomNode.addGeom(beamGeom)
        beamNode.attachNewNode(beamGeomNode)
        
        floorGeom = Geom(floorVertexData)
        floorGeom.addPrimitive(floorTris)
        floorGeomNode = GeomNode('floor')
        floorGeomNode.addGeom(floorGeom)
        floorNode.attachNewNode(floorGeomNode)

        # Add collision cylinder for clicking
        if self.isLocalToonHost():  # Only leader gets collision
            radius = 1  # Same radius as the spotlight
            collTube = CollisionTube(0, 0, 4, 0, 0, 1.2, radius)  # point1_x, point1_y, point1_z, point2_x, point2_y, point2_z, radius
            collNode = CollisionNode(f'spotlightSphere-{toon.doId}')  # Keep the same node name for consistency
            collNode.addSolid(collTube)
            collNode.setIntoCollideMask(self.spotlightBitMask)
            collPath = indicator.attachNewNode(collNode)
            collPath.setTag('toonId', str(toon.doId))
        
        # Store the indicator
        self.statusIndicators[toon.doId] = indicator
        
        # Update position and appearance
        self.updateStatusIndicator(toon, isPlayer)

    def updateStatusIndicator(self, toon, isPlayer):
        """Updates an existing status indicator's position and appearance"""
        indicator = self.statusIndicators.get(toon.doId)
        if indicator:
            # Update position to follow toon
            pos = toon.getPos(render)
            indicator.setPos(pos[0], pos[1], 0)
            
            # Remaining vertices (bottom of beam) fade to transparent
            transparent = VBase4(0, 0, 0, 0)
            # Set color based on player status with reduced intensity
            if isPlayer:
                color = VBase4(0.1, 0.8, 0.1, 1)  # Softer green for players
                transparent = VBase4(0, 0.1, 0, 0.1)
            else:
                color = VBase4(0.8, 0.1, 0.1, 1)  # Softer red for spectators
                transparent = VBase4(0.1, 0, 0, 0.1)
            # Update the color for both beam and floor nodes
            beamNode = indicator.find('beamNode')
            floorNode = indicator.find('floorNode')
            
            # Get the GeomNode for each
            beamGeom = beamNode.find('beam').node()
            floorGeom = floorNode.find('floor').node()
            
            # Update vertex colors for beam
            beamVertexData = beamGeom.modifyGeom(0).modifyVertexData()
            beamColorWriter = GeomVertexWriter(beamVertexData, 'color')
            
            # First vertex (top of beam) gets full color
            beamColorWriter.setData4f(color)
            for _ in range(8):
                beamColorWriter.setData4f(transparent)
                
            # Update vertex colors for floor
            floorVertexData = floorGeom.modifyGeom(0).modifyVertexData()
            floorColorWriter = GeomVertexWriter(floorVertexData, 'color')
            
            # Center point gets full color
            floorColorWriter.setData4f(color)
            # Outer points fade to transparent
            for _ in range(36):
                floorColorWriter.setData4f(transparent)

    def removeStatusIndicators(self):
        """Removes all status indicators and cleans up their nodes."""
        for indicator in self.statusIndicators.values():
            if not indicator.isEmpty():
                indicator.removeNode()
        self.statusIndicators.clear()

    def enterFrameworkWaitServerStart(self):
        self.notify.debug('BASE: enterFrameworkWaitServerStart')
        if self.numPlayers > 1:
            msg = TTLocalizer.MinigameWaitingForOtherPlayers
        else:
            msg = TTLocalizer.MinigamePleaseWait
        self.waitingStartLabel['text'] = msg
        self.waitingStartLabel.show()

    def setToonSpawnpointOrder(self, order):
        """Delegate to PlayerManager"""
        self.playerManager.setToonSpawnpointOrder(order)
        # Sync for backward compatibility
        self.toonSpawnpointOrder = self.playerManager.toonSpawnpointOrder

    # Best-of button handler now delegated to GameButtonsUI
    def setBestOf(self, value):
        """Deprecated: Best Of is now controlled by the First to X Wins modifier"""
        # This method is kept for backward compatibility but does nothing
        # The modifier system now handles this
        self.roundManager.setBestOf(value)

    def setRoundInfo(self, currentRound, roundWins):
        """Delegate to RoundManager"""
        self.roundManager.setRoundInfo(currentRound, roundWins)
        # No sync needed - managers handle their own state

    def setModifiers(self, mods):
        """Delegate to ModifierManager"""
        self.modifierManager.setModifiers(mods)

    def __nextRound(self, task=None):
        """Transition to the next round"""
        # Clean up all drones when round restarts
        self.__cleanupAllDrones()
        
        # Clear local cooldown cache for next round (delegated to DroneManager)
        self.droneManager.clearAllDroneCooldowns()
        
        # The server will handle the transition to the next round automatically
        # We just need to clean up the victory state
        return Task.done

    def __removeModifier(self, modifierIndex):
        """Remove a modifier from the game"""
        if self.isLocalToonHost() and modifierIndex < len(self.modifierManager.modifiers):
            modifierEnum = self.modifierManager.modifiers[modifierIndex].MODIFIER_ENUM
            self.sendUpdate('removeModifier', [modifierEnum])
    
    def setRequestForfeit(self, requesterAvId):
        """Delegate to ForfeitRestartManager and show dialog via UI"""
        self.forfeitRestartManager.setRequestForfeit(requesterAvId)
        # Show dialog via UI
        if hasattr(self, 'forfeitRestartDialogsUI'):
            self.forfeitRestartDialogsUI.showForfeitDialog(requesterAvId)
    
    def setUpdateForfeitConsents(self, consentAvIds):
        """Update forfeit consent status and UI"""
        # Update manager state
        self.forfeitRestartManager.forfeitConsents = set(consentAvIds)
        # Update dialog via UI
        if hasattr(self, 'forfeitRestartDialogsUI'):
            self.forfeitRestartDialogsUI.updateForfeitConsents(list(consentAvIds))
    
    def setCancelForfeit(self):
        """Delegate to ForfeitRestartManager"""
        self.forfeitRestartManager.setCancelForfeit()
        # Clean up dialogs via UI
        if hasattr(self, 'forfeitRestartDialogsUI'):
            self.forfeitRestartDialogsUI._cleanupForfeitDialogs()
        
        base.localAvatar.setSystemMessage(0, "Forfeit request has been cancelled.")
    
    def setCleanupForfeitDialogs(self):
        """Clean up forfeit dialogs without showing cancellation message (used when forfeit is executed)"""
        # Clean up dialogs via UI
        if hasattr(self, 'forfeitRestartDialogsUI'):
            self.forfeitRestartDialogsUI._cleanupForfeitDialogs()
    
    # Forfeit dialog handlers now delegated to ForfeitRestartDialogsUI
    # Old methods removed - see ForfeitRestartDialogsUI class
    
    def setRequestRestart(self, requesterAvId):
        """Update manager state, then show UI dialogs"""
        # Update manager state
        self.forfeitRestartManager.pendingRestartRequester = requesterAvId
        self.forfeitRestartManager.restartConsents.clear()
        self.forfeitRestartManager.restartConsents.add(requesterAvId)  # Requester automatically consents
        
        # Show dialog via UI
        if hasattr(self, 'forfeitRestartDialogsUI'):
            self.forfeitRestartDialogsUI.showRestartDialog(requesterAvId)
    
    def setUpdateRestartConsents(self, consentAvIds):
        """Update restart consent status and UI"""
        # Update manager state
        self.forfeitRestartManager.restartConsents = set(consentAvIds)
        # Update dialog via UI
        if hasattr(self, 'forfeitRestartDialogsUI'):
            self.forfeitRestartDialogsUI.updateRestartConsents(list(consentAvIds))
    
    def setCancelRestart(self):
        """Delegate to ForfeitRestartManager"""
        self.forfeitRestartManager.setCancelRestart()
        # Clean up dialogs via UI
        if hasattr(self, 'forfeitRestartDialogsUI'):
            self.forfeitRestartDialogsUI._cleanupRestartDialogs()
        
        base.localAvatar.setSystemMessage(0, "Restart request has been cancelled.")
    
    def setCleanupRestartDialogs(self):
        """Clean up restart dialogs without showing cancellation message (used when restart is executed)"""
        # Clean up dialogs via UI
        if hasattr(self, 'forfeitRestartDialogsUI'):
            self.forfeitRestartDialogsUI._cleanupRestartDialogs()
    
    # Restart dialog handlers now delegated to ForfeitRestartDialogsUI
    # Old methods removed - see ForfeitRestartDialogsUI class
    
    # Sync methods removed - not needed. Only bestOfButton is synced where actually used (RoundManager)
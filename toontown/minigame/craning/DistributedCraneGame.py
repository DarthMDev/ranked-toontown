import functools
import random
import math

from direct.distributed import DistributedSmoothNode
from direct.fsm import ClassicFSM
from direct.fsm import State
from direct.gui.OnscreenText import OnscreenText
from direct.interval.FunctionInterval import Func, Wait
from direct.interval.LerpInterval import LerpPosHprInterval, LerpScaleInterval, LerpColorScaleInterval
from direct.interval.MetaInterval import Parallel, Sequence
from direct.showbase.MessengerGlobal import messenger
from otp.otpbase.PythonUtil import reduceAngle
from direct.task.TaskManagerGlobal import taskMgr
from panda3d.core import CollisionPlane, Plane, Vec3, Point3, CollisionNode, NodePath, CollisionPolygon, BitMask32, \
    VBase3, VBase4, ColorBlendAttrib, GeomVertexData, GeomVertexWriter, Geom, GeomTrifans, GeomNode, GeomVertexFormat, CollisionRay, \
    CollisionHandlerQueue, CollisionTube, TextNode, Vec4
from panda3d.physics import LinearVectorForce, ForceNode, LinearEulerIntegrator, PhysicsManager

from libotp.nametag import NametagGlobals
from otp.otpbase import OTPGlobals
from toontown.minigame.craning import CraneLeagueGlobals
from toontown.minigame.craning.CraneLeagueGlobals import RED_COUNTDOWN_COLOR, ORANGE_COUNTDOWN_COLOR, \
    YELLOW_COUNTDOWN_COLOR
from toontown.coghq.BossSpeedrunTimer import BossSpeedrunTimedTimer, BossSpeedrunTimer
from toontown.coghq.CashbotBossScoreboard import CashbotBossScoreboard
from toontown.coghq.CraneLeagueHeatDisplay import CraneLeagueHeatDisplay
from toontown.minigame.DistributedMinigame import DistributedMinigame
from toontown.minigame.craning.CraneWalk import CraneWalk
from toontown.toonbase import TTLocalizer, ToontownGlobals
from toontown.minigame.craning.CraneGameSettingsPanel import CraneGameSettingsPanel
from toontown.minigame.statuseffects.DistributedStatusEffectSystem import DistributedStatusEffectSystem
from toontown.minigame.statuseffects.StatusEffectGlobals import StatusEffect, SAFE_ALLOWED_EFFECTS
from toontown.minigame.tournament import TournamentType, TournamentStage
from direct.gui.DirectGui import DGG, DirectFrame
from direct.gui.DirectScrolledList import DirectScrolledList
from direct.gui.DirectLabel import DirectLabel
from direct.gui.DirectButton import DirectButton
from direct.showbase.ShowBaseGlobal import aspect2d
from direct.task import Task
from toontown.minigame.craning import CraneLeagueGlobals


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
        self.bestOfButton = None
        self.participantsPanel = None
        self.participantsList = None
        self.participantsPanelVisible = False
        self.bestOfValue = 1  # Default to Best of 1
        self.currentRound = 1
        self.roundWins = {}  # Maps avId -> number of rounds won
        self.pendingForfeitRequester = None  # avId of player who requested forfeit
        self.forfeitConsents = set()  # Set of avIds who have consented
        self.forfeitDialog = None  # Dialog for forfeit confirmation (for non-requesters)
        self.forfeitRequesterDialog = None  # Dialog for requester (shows status and cancel)
        self.pendingRestartRequester = None  # avId of player who requested restart
        self.restartConsents = set()  # Set of avIds who have consented
        self.restartDialog = None  # Dialog for restart confirmation (for non-requesters)
        self.restartRequesterDialog = None  # Dialog for requester (shows status and cancel)
        
        # Tournament system
        self.tournamentActive = False  # Is a tournament active?
        self.tournamentType = TournamentType.NONE
        self.tournamentButton = None  # Button to open tournament settings
        
        # Tournament match ready-up system (distinct from framework ready-up)
        self.waitingForMatchReady = False
        self.matchPlayers = []
        self.matchReadyUI = None  # UI elements for match ready-up
        self.matchReadyButton = None  # Ready button
        self.matchReadyPlayerHeads = {}  # Track toon heads for cleanup
        self.matchReadyStatusLabels = {}  # Track ready status labels
        self.matchReadyAnimTrack = None  # Track entrance animation
        self.tournamentProgressLabel = None  # Label showing tournament progress
        self.tournamentPanel = None  # Tournament panel (like modifiers panel)
        self.tournamentPanelVisible = False  # Is tournament panel visible?
        self.tournamentParticipantsList = None  # ScrolledList for participants
        self.tournamentSpectatorsList = None  # ScrolledList for spectators
        self.tournamentParticipantsList_selected = []  # List of selected tournament participants
        self.tournamentParticipants = []  # All tournament participants (from server)
        self.tournamentCurrentMatchPlayers = []  # Current match players
        self.tournamentStandings = {}  # Tournament standings: {avId: {'matchWins': int, 'totalPoints': int}}
        self.scoreboardShowAllParticipants = False  # Toggle for scoreboard display
        
        self.boss = None
        self.bossRequest = None
        self.ruleset = CraneLeagueGlobals.CraneGameRuleset()  # Setup a default ruleset as a fallback
        self.modifiers = []
        self.heatDisplay = CraneLeagueHeatDisplay()
        self.heatDisplay.hide()
        self.endVault = None
        self.statusIndicators = {}  # Dictionary to store status indicators for each toon
        self.droneCooldowns = {}  # Track drone cooldowns per slot {avId: {slotIndex: (startTime, duration)}}
        self.selectedDroneTypes = {}  # Track selected drone types per player {avId: [slot0Type, slot1Type, slot2Type]}
        
        # Drone cooldown UI elements (shown near leave button when on crane)
        self.droneCooldownIndicator = None
        self.droneCooldownText = None
        self.droneCooldownTask = None
        
        # Drone selection UI elements (shown during rules phase)
        self.droneSelectionSlots = []  # List of 3 slot UI elements
        self.droneSelectionDialog = None
        
        # Status effect system will be set via setStatusEffectSystemId
        self.statusEffectSystem : DistributedStatusEffectSystem | None = None
        


        self.warningSfx = None

        self.timerTickSfx = None
        self.goSfx = None

        self.latency = 0.5  # default latency for updating object posHpr

        self.toonSpawnpointOrder = [i for i in range(16)]
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

        # Initialize modifiers panel variables
        self.modifiersPanel = None
        self.modifiersPanelVisible = False
        
        # Initialize modifier config dialog variable
        self.modifierConfigDialog = None

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
        
        # If a tournament is active, update the scoreboard to reflect spectator changes
        if self.tournamentActive and hasattr(self, 'scoreboard') and self.scoreboard:
            self.__updateTournamentScoreboard()

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
                spawn_index = i if i < len(CraneLeagueGlobals.TOON_SPAWN_POSITIONS) else 0
                posHpr = CraneLeagueGlobals.TOON_SPAWN_POSITIONS[spawn_index]
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
                    spawn_index = participantIndex if participantIndex < len(CraneLeagueGlobals.TOON_SPAWN_POSITIONS) else 0
                    posHpr = CraneLeagueGlobals.TOON_SPAWN_POSITIONS[spawn_index]
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
                        spawn_index = participantIndex if participantIndex < len(CraneLeagueGlobals.TOON_SPAWN_POSITIONS) else 0
                    else:
                        avIdIndex = self.avIdList.index(avId)
                        # Use the avId's index to get their spawn position from the order
                        if avIdIndex >= len(self.toonSpawnpointOrder):
                            self.notify.warning(f"avIdIndex {avIdIndex} out of range for spawn order, using sequential position")
                            participantIndex = participantIds.index(avId)
                            spawn_index = participantIndex if participantIndex < len(CraneLeagueGlobals.TOON_SPAWN_POSITIONS) else 0
                        else:
                            spawn_index = self.toonSpawnpointOrder[avIdIndex]
                        
                        # Bounds check to prevent index errors
                        if spawn_index >= len(CraneLeagueGlobals.TOON_SPAWN_POSITIONS):
                            self.notify.warning(f"Invalid spawn index {spawn_index} for avId {avId}, using sequential position")
                            participantIndex = participantIds.index(avId)
                            spawn_index = participantIndex if participantIndex < len(CraneLeagueGlobals.TOON_SPAWN_POSITIONS) else 0
                    
                    posHpr = CraneLeagueGlobals.TOON_SPAWN_POSITIONS[spawn_index]
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
                Wait(CraneLeagueGlobals.PREPARE_DELAY + CraneLeagueGlobals.PREPARE_LATENCY_FACTOR),
                Func(self.gameFSM.request, 'play'),
            )

        # If this is a solo crane round, we are not going to play a cutscene. Get right into the action.
        if len(players) == 1:
            return Sequence(
                Wait(CraneLeagueGlobals.PREPARE_LATENCY_FACTOR),
                Func(self.gameFSM.request, 'play'),
            )

        # Generate a camera track so that the camera slowly pans on to the toon.
        toon = base.localAvatar if not self.localToonSpectating() else self.getParticipantsNotSpectating()[0]
        targetCameraPos = render.getRelativePoint(toon, Vec3(0, -10, toon.getHeight()))
        startCameraHpr = Point3(reduceAngle(camera.getH()), camera.getP(), camera.getR())
        cameraTrack = LerpPosHprInterval(camera, CraneLeagueGlobals.PREPARE_DELAY / 2.5, Point3(*targetCameraPos), Point3(reduceAngle(toon.getH()), 0, 0), startPos=camera.getPos(), startHpr=startCameraHpr, blendType='easeInOut')

        # Setup a countdown track to display when the round will start. Also at the end, start the game.
        countdownTrack = Sequence()
        for secondsLeft in range(5, 0, -1):
            color = RED_COUNTDOWN_COLOR if secondsLeft > 2 else (ORANGE_COUNTDOWN_COLOR if secondsLeft > 1 else YELLOW_COUNTDOWN_COLOR)
            countdownTrack.append(Func(self.__displayOverlayText, f"{secondsLeft}", color))
            countdownTrack.append(Func(base.playSfx, self.timerTickSfx))
            countdownTrack.append(Wait(1))
        countdownTrack.append(Func(self.__displayOverlayText, 'GO!', CraneLeagueGlobals.GREEN_COUNTDOWN_COLOR))
        countdownTrack.append(Func(base.playSfx, self.goSfx))
        countdownTrack.append(Wait(CraneLeagueGlobals.PREPARE_LATENCY_FACTOR))
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
        # Create toggle button
        from direct.gui.DirectButton import DirectButton
        btnGeom = loader.loadModel('phase_3/models/gui/quit_button')

        # Create play button next to settings
        self.playButton = DirectButton(
            parent=base.a2dTopLeft,
            relief=None,
            text='Play',
            text_scale=0.055,
            text_pos=(0, -0.02),
            geom=(btnGeom.find('**/QuitBtn_UP'),
                  btnGeom.find('**/QuitBtn_DN'),
                  btnGeom.find('**/QuitBtn_RLVR')),
            geom_scale=(0.7, 1, 1),
            pos=(0.7, 0, -0.2),
            command=self.__handlePlayButton
        )
        self.playButton.hide()  # Play button starts hidden
        
        # Create modifiers button next to play button (was participants)
        self.modifiersButton = DirectButton(
            parent=base.a2dTopLeft,
            relief=None,
            text='Modifiers',
            text_scale=0.055,
            text_pos=(0, -0.02),
            geom=(btnGeom.find('**/QuitBtn_UP'),
                  btnGeom.find('**/QuitBtn_DN'),
                  btnGeom.find('**/QuitBtn_RLVR')),
            geom_scale=(0.7, 1, 1),
            pos=(1, 0, -0.2),
            command=self.__handleModifiersButton
        )
        self.modifiersButton.hide()  # Modifiers button starts hidden
        
        # Create best of button next to modifiers button
        self.bestOfButton = DirectButton(
            parent=base.a2dTopLeft,
            relief=None,
            text=f'Best of {self.bestOfValue}',
            text_scale=0.055,
            text_pos=(0, -0.02),
            geom=(btnGeom.find('**/QuitBtn_UP'),
                  btnGeom.find('**/QuitBtn_DN'),
                  btnGeom.find('**/QuitBtn_RLVR')),
            geom_scale=(0.7, 1, 1),
            pos=(1.3, 0, -0.2),
            command=self.__handleBestOfButton
        )
        self.bestOfButton.hide()  # Best of button starts hidden
        
        # Create tournament button next to best of button
        self.tournamentButton = DirectButton(
            parent=base.a2dTopLeft,
            relief=None,
            text='Tournament',
            text_scale=0.055,
            text_pos=(0, -0.02),
            geom=(btnGeom.find('**/QuitBtn_UP'),
                  btnGeom.find('**/QuitBtn_DN'),
                  btnGeom.find('**/QuitBtn_RLVR')),
            geom_scale=(0.7, 1, 1),
            pos=(1.6, 0, -0.2),
            command=self.__handleTournamentButton
        )
        self.tournamentButton.hide()  # Tournament button starts hidden
        
        btnGeom.removeNode()
        
        return panel

    def __handlePlayButton(self):
        # Clean up the ready timeout timer when play is pressed
        self._destroyReadyTimeoutTimer()
        messenger.send(self.rulesDoneEvent)

    def __handleModifiersButton(self):
        """Toggle the modifiers panel visibility"""
        if self.modifiersPanelVisible:
            self.__hideModifiersPanel()
        else:
            self.__showModifiersPanel()
    
    def __showModifiersPanel(self):
        """Create and show the modifiers panel"""
        if self.modifiersPanel is None:
            self.__createModifiersPanel()
        
        self.modifiersPanel.show()
        self.modifiersPanelVisible = True
    
    def __hideModifiersPanel(self):
        """Hide the modifiers panel"""
        if self.modifiersPanel is not None:
            self.modifiersPanel.hide()
        self.modifiersPanelVisible = False
    
    def __createModifiersPanel(self):
        """Create the modifiers management panel using proper game UI conventions"""
        
        # Create the main panel frame using proper dialog styling
        self.modifiersPanel = DirectFrame(
            relief=None,
            image=DGG.getDefaultDialogGeom(),
            image_color=ToontownGlobals.GlobalDialogColor,
            image_scale=(1.6, 1, 1.4),
            pos=(0, 0, 0),
            parent=aspect2d,
            sortOrder=DGG.NO_FADE_SORT_INDEX
        )
        
        # Title label
        titleLabel = DirectLabel(
            parent=self.modifiersPanel,
            relief=None,
            text="Manage Modifiers",
            text_scale=0.08,
            text_pos=(0, 0.55),
            text_fg=(0.1, 0.1, 0.4, 1),
            text_font=ToontownGlobals.getInterfaceFont()
        )
        
        # Instructions label
        instructionsLabel = DirectLabel(
            parent=self.modifiersPanel,
            relief=None,
            text="Add and remove modifiers for the game",
            text_scale=0.05,
            text_pos=(0, 0.45),
            text_fg=(0.3, 0.3, 0.3, 1),
            text_font=ToontownGlobals.getInterfaceFont()
        )
        
        # Load GUI assets for scroll list
        gui = loader.loadModel('phase_3.5/models/gui/friendslist_gui')
        
        # Current modifiers section
        currentModsLabel = DirectLabel(
            parent=self.modifiersPanel,
            relief=None,
            text="Current Modifiers:",
            text_scale=0.06,
            text_pos=(-0.75, 0.3),
            text_fg=(0.2, 0.2, 0.6, 1),
            text_font=ToontownGlobals.getInterfaceFont(),
            text_align=TextNode.ALeft
        )
        
        # Create scrolled list for current modifiers
        self.currentModifiersList = DirectScrolledList(
            parent=self.modifiersPanel,
            relief=DGG.SUNKEN,
            frameColor=(0.85, 0.95, 1, 1),
            borderWidth=(0.01, 0.01),
            pos=(-0.35, 0, 0.2),
            frameSize=(-0.4, 0.2, -0.24, 0.0),
            numItemsVisible=4,
            forceHeight=0.06,
            itemFrame_frameSize=(-0.38, 0.38, -0.03, 0.03),
            itemFrame_pos=(0, 0, -0.032),
            itemFrame_relief=None,
            # Scroll buttons using proper assets
            incButton_image=(gui.find('**/FndsLst_ScrollUp'),
                           gui.find('**/FndsLst_ScrollDN'),
                           gui.find('**/FndsLst_ScrollUp_Rllvr'),
                           gui.find('**/FndsLst_ScrollUp')),
            incButton_relief=None,
            incButton_scale=(0.3, 0.3, -1.1),
            incButton_pos=(0.15, 0, -0.26),
            incButton_image3_color=Vec4(0.6, 0.6, 0.6, 0.6),
            decButton_image=(gui.find('**/FndsLst_ScrollUp'),
                           gui.find('**/FndsLst_ScrollDN'),
                           gui.find('**/FndsLst_ScrollUp_Rllvr'),
                           gui.find('**/FndsLst_ScrollUp')),
            decButton_relief=None,
            decButton_scale=(0.3, 0.3, 1.1),
            decButton_pos=(0.15, 0, 0.03),
            decButton_image3_color=Vec4(0.6, 0.6, 0.6, 0.6)
        )
        
        # Available modifiers section
        availableModsLabel = DirectLabel(
            parent=self.modifiersPanel,
            relief=None,
            text="Available Modifiers:",
            text_scale=0.06,
            text_pos=(0.1, 0.3),
            text_fg=(0.2, 0.2, 0.6, 1),
            text_font=ToontownGlobals.getInterfaceFont(),
            text_align=TextNode.ALeft
        )
        
        # Create scrolled list for available modifiers
        self.availableModifiersList = DirectScrolledList(
            parent=self.modifiersPanel,
            relief=DGG.SUNKEN,
            frameColor=(0.95, 0.85, 1, 1),
            borderWidth=(0.01, 0.01),
            pos=(0.5, 0, 0.2),
            frameSize=(-0.4, 0.2, -0.24, 0.0),
            numItemsVisible=4,
            forceHeight=0.06,
            itemFrame_frameSize=(-0.38, 0.38, -0.03, 0.03),
            itemFrame_pos=(0, 0, -0.032),
            itemFrame_relief=None,
            # Scroll buttons using proper assets
            incButton_image=(gui.find('**/FndsLst_ScrollUp'),
                           gui.find('**/FndsLst_ScrollDN'),
                           gui.find('**/FndsLst_ScrollUp_Rllvr'),
                           gui.find('**/FndsLst_ScrollUp')),
            incButton_relief=None,
            incButton_scale=(0.3, 0.3, -1.1),
            incButton_pos=(0.15, 0, -0.26),
            incButton_image3_color=Vec4(0.6, 0.6, 0.6, 0.6),
            decButton_image=(gui.find('**/FndsLst_ScrollUp'),
                           gui.find('**/FndsLst_ScrollDN'),
                           gui.find('**/FndsLst_ScrollUp_Rllvr'),
                           gui.find('**/FndsLst_ScrollUp')),
            decButton_relief=None,
            decButton_scale=(0.3, 0.3, 1.1),
            decButton_pos=(0.15, 0, 0.03),
            decButton_image3_color=Vec4(0.6, 0.6, 0.6, 0.6)
        )
        
        # Load button assets
        buttons = loader.loadModel('phase_3/models/gui/dialog_box_buttons_gui')
        closeButtonImage = (buttons.find('**/CloseBtn_UP'), 
                          buttons.find('**/CloseBtn_DN'), 
                          buttons.find('**/CloseBtn_Rllvr'))
        
        # Close button using proper styling
        closeButton = DirectButton(
            parent=self.modifiersPanel,
            relief=None,
            image=closeButtonImage,
            text="Close",
            text_scale=0.05,
            text_pos=(0, -0.1),
            pos=(0, 0, -0.55),
            command=self.__hideModifiersPanel
        )
        
        # Clean up loaded models
        gui.removeNode()
        buttons.removeNode()
        
        # Populate the lists with current and available modifiers
        self.__updateModifiersLists()
        
        # Initially hide the panel
        self.modifiersPanel.hide()
    
    def __updateModifiersLists(self):
        """Update the modifiers lists with current and available modifiers"""
        if self.currentModifiersList is None or self.availableModifiersList is None:
            return
            
        # Clear existing items
        self.currentModifiersList.removeAllItems()
        self.availableModifiersList.removeAllItems()
        
        # Load button assets for add/remove buttons
        gui = loader.loadModel('phase_3.5/models/gui/friendslist_gui')
        addButtonImage = (gui.find('**/Horiz_Arrow_UP'),
                         gui.find('**/Horiz_Arrow_DN'),
                         gui.find('**/Horiz_Arrow_Rllvr'),
                         gui.find('**/Horiz_Arrow_UP'))
        removeButtonImage = (gui.find('**/Horiz_Arrow_UP'),
                           gui.find('**/Horiz_Arrow_DN'),
                           gui.find('**/Horiz_Arrow_Rllvr'),
                           gui.find('**/Horiz_Arrow_UP'))
        
        # Populate current modifiers list
        for i, mod in enumerate(self.modifiers):
            itemFrame = DirectFrame(
                relief=None,
                frameSize=(-0.38, 0.38, -0.03, 0.03)
            )
            
            # Modifier name label
            nameLabel = DirectLabel(
                parent=itemFrame,
                relief=None,
                text=mod.getName(),
                text_scale=0.025,
                text_pos=(-0.35, 0, 0),
                text_fg=mod.TITLE_COLOR,
                text_font=ToontownGlobals.getInterfaceFont(),
                text_align=TextNode.ALeft
            )
            
            # Remove button
            removeButton = DirectButton(
                parent=itemFrame,
                relief=None,
                image=removeButtonImage,
                image_scale=(0.3, 1, 0.3),
                image_hpr=(0, 0, 180),  # Rotate to make it a remove arrow
                pos=(0.17, 0, 0),
                command=self.__removeModifier,
                extraArgs=[i]
            )
            
            self.currentModifiersList.addItem(itemFrame)

        currentModEnums = [mod.MODIFIER_ENUM for mod in self.modifiers]
        availableModClasses = []
        
        # Get all modifier classes and filter out currently active ones
        for modEnum, modClass in CraneLeagueGlobals.CFORulesetModifierBase.MODIFIER_SUBCLASSES.items():
            if modEnum not in currentModEnums:
                availableModClasses.append(modClass)
        
        # Sort by type (Helpful, Hurtful, Special)
        availableModClasses.sort(key=lambda x: (x.MODIFIER_TYPE, x.MODIFIER_ENUM))
        
        # Populate available modifiers list
        for i, modClass in enumerate(availableModClasses):
            mod = modClass()  # Create instance for display
            
            itemFrame = DirectFrame(
                relief=None,
                frameSize=(-0.38, 0.38, -0.03, 0.03)
            )
            
            # Modifier name label
            nameLabel = DirectLabel(
                parent=itemFrame,
                relief=None,
                text=mod.getName(),
                text_scale=0.025,
                text_pos=(-0.35, 0, 0),
                text_fg=mod.TITLE_COLOR,
                text_font=ToontownGlobals.getInterfaceFont(),
                text_align=TextNode.ALeft
            )
            
            # Add button
            addButton = DirectButton(
                parent=itemFrame,
                relief=None,
                image=addButtonImage,
                image_scale=(0.3, 1, 0.3),
                pos=(0.17, 0, 0),
                command=self.__addModifier,
                extraArgs=[modClass.MODIFIER_ENUM]
            )
            
            self.availableModifiersList.addItem(itemFrame)
        
        # Clean up loaded model
        gui.removeNode()
    
    def __addModifier(self, modifierEnum):
        """Add a modifier to the game"""
        if self.isLocalToonHost():
            # Check if this modifier has configurable parameters
            if self.__modifierHasParameters(modifierEnum):
                self.__showModifierConfigDialog(modifierEnum)
            else:
                # Add directly with default tier 1
                self.sendUpdate('addModifier', [modifierEnum, 1])
    
    def __modifierHasParameters(self, modifierEnum):
        # Get the modifier class
        modifierClass = CraneLeagueGlobals.CFORulesetModifierBase.MODIFIER_SUBCLASSES.get(modifierEnum)
        if not modifierClass:
            return False
        
        # Create a temporary instance to check if it uses tiers meaningfully
        tempMod = modifierClass()
        
        # Check some common modifiers that have meaningful tier differences
        tieredModifiers = [
            27,  # ModifierTimerEnabler (Margin Call)
            2,   # ModifierCFOHPIncreaser (Financial Aid)
            3,   # ModifierCFOHPDecreaser (Budget Cuts)
            0,   # ModifierComboExtender (Chains of Finesse)
            1,   # ModifierComboShortener (Chain Locker)
            4,   # ModifierDesafeImpactIncreaser (Strong/Tough/Reinforced Safes)
            9,   # ModifierGoonDamageInflictIncreaser (Goon damage)
            10,  # ModifierSafeDamageInflictIncreaser (Safe damage)
            11,  # ModifierGoonSpeedIncreaser (Goon speed)
            12,  # ModifierGoonCapIncreaser (Goon cap)
            16,  # ModifierTreasureHealDecreaser (Treasure heal decrease)
            17,  # ModifierTreasureRNG (Treasure drop chance)
            18,  # ModifierTreasureCapDecreaser (Treasure cap)
            19,  # ModifierUberBonusIncreaser (Uber bonus)
            29,  # ModifierLaffDrain (Leaky Laff)
        ]
        
        return modifierEnum in tieredModifiers
    
    def __showModifierConfigDialog(self, modifierEnum):
        """Show configuration dialog for a modifier"""
        # Get the modifier class
        modifierClass = CraneLeagueGlobals.CFORulesetModifierBase.MODIFIER_SUBCLASSES.get(modifierEnum)
        if not modifierClass:
            return
        
        # Hide the modifiers panel temporarily
        if self.modifiersPanel:
            self.modifiersPanel.hide()
        
        # Create configuration dialog - make it wider for two-column layout
        self.modifierConfigDialog = DirectFrame(
            relief=None,
            image=DGG.getDefaultDialogGeom(),
            image_color=ToontownGlobals.GlobalDialogColor,
            image_scale=(1.8, 1, 1.4),  # Made wider for two columns
            pos=(0, 0, 0),
            parent=aspect2d,
            sortOrder=DGG.NO_FADE_SORT_INDEX + 1
        )
        
        # Create a sample modifier to get information
        sampleMod = modifierClass()
        
        # Title
        titleLabel = DirectLabel(
            parent=self.modifierConfigDialog,
            relief=None,
            text=f"Configure {sampleMod.getName()}",
            text_scale=0.07,
            text_pos=(0, 0.55),
            text_fg=sampleMod.TITLE_COLOR,
            text_font=ToontownGlobals.getInterfaceFont()
        )
        
        # Instructions
        instructionsLabel = DirectLabel(
            parent=self.modifierConfigDialog,
            relief=None,
            text="Choose the intensity/duration:",
            text_scale=0.05,
            text_pos=(0, 0.45),
            text_fg=(0.3, 0.3, 0.3, 1),
            text_font=ToontownGlobals.getInterfaceFont()
        )
        
        # Load button assets
        buttons = loader.loadModel('phase_3/models/gui/dialog_box_buttons_gui')
        buttonImage = (buttons.find('**/ChtBx_OKBtn_UP'), 
                      buttons.find('**/ChtBx_OKBtn_DN'), 
                      buttons.find('**/ChtBx_OKBtn_Rllvr'))
        
        cancelButtonImage = (buttons.find('**/CloseBtn_UP'), 
                          buttons.find('**/CloseBtn_DN'), 
                          buttons.find('**/CloseBtn_Rllvr'))
        
        # Create tier selection options based on modifier type
        self.__createTierOptions(modifierEnum, modifierClass, buttonImage)
        
        # Cancel button
        cancelButton = DirectButton(
            parent=self.modifierConfigDialog,
            relief=None,
            image=cancelButtonImage,
            text="Cancel",
            text_scale=0.05,
            text_pos=(0, -0.1),
            pos=(0, 0, -0.5),
            command=self.__cancelModifierConfig
        )
        
        buttons.removeNode()
    
    def __createTierOptions(self, modifierEnum, modifierClass, buttonImage):
        """Create tier selection options with two-column layout"""
        
        # Special handling for different modifier types
        if modifierEnum == 27:  # ModifierTimerEnabler (Margin Call)
            self.__createTimeSelectionOptions(modifierEnum, buttonImage)
        elif modifierEnum in [2, 3]:  # HP modifiers
            self.__createPercentageOptions(modifierEnum, modifierClass, buttonImage, "HP")
        elif modifierEnum in [0, 1]:  # Combo modifiers
            self.__createPercentageOptions(modifierEnum, modifierClass, buttonImage, "Combo Duration")
        elif modifierEnum == 29:  # ModifierLaffDrain (Leaky Laff)
            self.__createLaffDrainOptions(modifierEnum, buttonImage)
        else:
            # Generic tier options (1-5)
            self.__createGenericTierOptions(modifierEnum, modifierClass, buttonImage)
    
    def __createTimeSelectionOptions(self, modifierEnum, buttonImage):
        """Create time selection options for Margin Call modifier"""
        timeOptions = [
            (1, "1 minute"),
            (2, "2 minutes"), 
            (3, "3 minutes"),
            (5, "5 minutes"),
            (10, "10 minutes")
        ]
        
        startY = 0.3
        for i, (tier, label) in enumerate(timeOptions):
            currentY = startY - i * 0.08
            
            # Description label on the left
            descLabel = DirectLabel(
                parent=self.modifierConfigDialog,
                relief=None,
                text=label,
                text_scale=0.045,
                text_pos=(-0.35, currentY),
                text_fg=(0.2, 0.2, 0.2, 1),
                text_font=ToontownGlobals.getInterfaceFont(),
                text_align=TextNode.ALeft
            )
            
            # Selection button on the right
            selectButton = DirectButton(
                parent=self.modifierConfigDialog,
                relief=None,
                image=buttonImage,
                pos=(0.4, 0, currentY+0.015),
                scale=(0.7, 1, 0.7),
                command=self.__confirmModifierConfig,
                extraArgs=[modifierEnum, tier]
            )
    
    def __createPercentageOptions(self, modifierEnum, modifierClass, buttonImage, statName):
        """Create percentage-based tier options"""
        
        # Create sample modifiers to get percentage values
        tiers = [1, 2, 3, 4, 5]
        startY = 0.3
        
        for i, tier in enumerate(tiers):
            try:
                sampleMod = modifierClass(tier)
                currentY = startY - i * 0.08
                
                # Get the percentage or value for display
                if hasattr(sampleMod, '_perc_increase'):
                    value = sampleMod._perc_increase()
                    description = f"Tier {tier}: +{value}% {statName}"
                elif hasattr(sampleMod, '_perc_decrease'):
                    value = sampleMod._perc_decrease()
                    description = f"Tier {tier}: -{value}% {statName}"
                elif hasattr(sampleMod, '_duration'):
                    value = sampleMod._duration()
                    description = f"Tier {tier}: +{value}% {statName}"
                else:
                    description = f"Tier {tier}"
                
                # Description label on the left
                descLabel = DirectLabel(
                    parent=self.modifierConfigDialog,
                    relief=None,
                    text=description,
                    text_scale=0.04,
                    text_pos=(-0.4, currentY),
                    text_fg=(0.2, 0.2, 0.2, 1),
                    text_font=ToontownGlobals.getInterfaceFont(),
                    text_align=TextNode.ALeft
                )
                
                # Selection button on the right
                selectButton = DirectButton(
                    parent=self.modifierConfigDialog,
                    relief=None,
                    image=buttonImage,
                    pos=(0.4, 0, currentY+0.015),
                    scale=(0.7, 1, 0.7),
                    command=self.__confirmModifierConfig,
                    extraArgs=[modifierEnum, tier]
                )
            except:
                # Fallback for tiers that might not work
                break
    
    def __createLaffDrainOptions(self, modifierEnum, buttonImage):
        """Create laff drain rate selection options"""
        drainOptions = [
            (1, "Every 1.0 seconds"),
            (2, "Every 1.0 seconds"),
            (3, "Every 0.75 seconds"),
            (4, "Every 0.5 seconds"),
            (5, "Every 0.25 seconds"),
            (6, "Every 0.1 seconds")
        ]
        
        startY = 0.3
        for i, (tier, label) in enumerate(drainOptions):
            currentY = startY - i * 0.08
            description = f"Tier {tier}: {label}"
            
            # Description label on the left
            descLabel = DirectLabel(
                parent=self.modifierConfigDialog,
                relief=None,
                text=description,
                text_scale=0.04,
                text_pos=(-0.4, currentY),
                text_fg=(0.2, 0.2, 0.2, 1),
                text_font=ToontownGlobals.getInterfaceFont(),
                text_align=TextNode.ALeft
            )
            
            # Selection button on the right
            selectButton = DirectButton(
                parent=self.modifierConfigDialog,
                relief=None,
                image=buttonImage,
                pos=(0.4, 0, currentY+0.015),
                scale=(0.7, 1, 0.7),
                command=self.__confirmModifierConfig,
                extraArgs=[modifierEnum, tier]
            )
    
    def __createGenericTierOptions(self, modifierEnum, modifierClass, buttonImage):
        """Create generic tier 1-5 options with descriptions"""
        tiers = [1, 2, 3, 4, 5]
        startY = 0.3
        
        for i, tier in enumerate(tiers):
            currentY = startY - i * 0.08
            
            # Try to get a meaningful description
            try:
                sampleMod = modifierClass(tier)
                if hasattr(sampleMod, '_perc_increase'):
                    value = sampleMod._perc_increase()
                    description = f"Tier {tier}: +{value}% effect"
                elif hasattr(sampleMod, '_perc_decrease'):
                    value = sampleMod._perc_decrease()
                    description = f"Tier {tier}: -{value}% effect"
                elif hasattr(sampleMod, 'getDescription'):
                    # Get the description and try to extract meaningful info
                    desc = sampleMod.getDescription()
                    description = f"Tier {tier}: {sampleMod.getName()}"
                else:
                    description = f"Tier {tier}: Standard intensity"
            except:
                description = f"Tier {tier}: Standard intensity"
            
            # Description label on the left
            descLabel = DirectLabel(
                parent=self.modifierConfigDialog,
                relief=None,
                text=description,
                text_scale=0.04,
                text_pos=(-0.4, currentY),
                text_fg=(0.2, 0.2, 0.2, 1),
                text_font=ToontownGlobals.getInterfaceFont(),
                text_align=TextNode.ALeft
            )
            
            # Selection button on the right
            selectButton = DirectButton(
                parent=self.modifierConfigDialog,
                relief=None,
                image=buttonImage,
                pos=(0.4, 0, currentY+0.015),
                scale=(0.7, 1, 0.7),
                command=self.__confirmModifierConfig,
                extraArgs=[modifierEnum, tier]
            )
    
    def __confirmModifierConfig(self, modifierEnum, tier):
        """Confirm the modifier configuration and add it"""
        # Clean up the config dialog
        self.__cancelModifierConfig()
        
        # Add the modifier with the selected tier
        self.sendUpdate('addModifier', [modifierEnum, tier])
    
    def __cancelModifierConfig(self):
        """Cancel modifier configuration"""
        if hasattr(self, 'modifierConfigDialog') and self.modifierConfigDialog:
            self.modifierConfigDialog.destroy()
            self.modifierConfigDialog = None
        
        # Show the modifiers panel again
        if self.modifiersPanel and self.modifiersPanelVisible:
            self.modifiersPanel.show()

    def __cleanupRulesPanel(self):
        self.ignore(self.rulesDoneEvent)
        self.ignore('spotStatusChanged')
        if self.playButton is not None:
            self.playButton.destroy()
            self.playButton = None
        if self.modifiersButton is not None:
            self.modifiersButton.destroy()
            self.modifiersButton = None
        if self.bestOfButton is not None:
            self.bestOfButton.destroy()
            self.bestOfButton = None
        if self.tournamentButton is not None:
            self.tournamentButton.destroy()
            self.tournamentButton = None
        if self.modifiersPanel is not None:
            self.modifiersPanel.destroy()
            self.modifiersPanel = None
            self.currentModifiersList = None
            self.availableModifiersList = None
        self.modifiersPanelVisible = False
        # Clean up tournament panel
        if self.tournamentPanel is not None:
            self.tournamentPanel.destroy()
            self.tournamentPanel = None
            self.tournamentParticipantsList = None
            self.tournamentSpectatorsList = None
        self.tournamentPanelVisible = False
        # Clean up modifier config dialog if it exists
        if hasattr(self, 'modifierConfigDialog') and self.modifierConfigDialog is not None:
            self.modifierConfigDialog.destroy()
            self.modifierConfigDialog = None
        if self.rulesPanel is not None:
            self.rulesPanel.cleanup()
            self.rulesPanel = None
    
    def __createDroneSelectionUI(self):
        """Create the drone selection UI with 3 slots at the bottom of the screen."""
        from toontown.minigame.craning import CraneLeagueGlobals
        
        # Initialize selected drone types for local toon (default: Laser, Heal, Explodey)
        localAvId = base.localAvatar.doId
        if localAvId not in self.selectedDroneTypes:
            self.selectedDroneTypes[localAvId] = [
                CraneLeagueGlobals.DroneType.LASER,
                CraneLeagueGlobals.DroneType.HEAL,
                CraneLeagueGlobals.DroneType.EXPLODEY
            ]
        
        # Create container frame for all slots
        self.droneSelectionFrame = DirectFrame(
            relief=None,
            parent=aspect2d,
            pos=(0, 0, -0.85),  # Bottom of screen
            sortOrder=DGG.NO_FADE_SORT_INDEX
        )
        
        # Get keybinds from settings for the 3 slots
        slotKeyNames = ['DRONE_SLOT_0_KEY', 'DRONE_SLOT_1_KEY', 'DRONE_SLOT_2_KEY']
        slotKeys = [base.settings.getControl(keyName) for keyName in slotKeyNames]
        slotSpacing = 0.25  # Space between slots
        
        # Helper function to format keybind for display
        def formatKeybindDisplay(keybind):
            """Format a keybind string for display in the UI."""
            if len(keybind) == 1:
                # Single character key -> uppercase
                return keybind.upper()
            elif keybind.startswith('arrow_'):
                # Arrow keys -> show arrow symbol
                direction = keybind.replace('arrow_', '')
                arrowMap = {'up': '↑', 'down': '↓', 'left': '←', 'right': '→'}
                return arrowMap.get(direction, keybind.upper())
            elif keybind.startswith('page_'):
                # Page keys
                return keybind.replace('page_', 'Pg').upper()
            elif keybind in ['control', 'shift', 'alt']:
                # Modifier keys
                return keybind.capitalize()
            else:
                # Other keys -> uppercase first letter of each word
                return keybind.replace('_', ' ').title()
        
        self.droneSelectionSlots = []
        self.droneSlotKeybinds = []  # Store keybinds for cleanup
        for i in range(3):
            slotType = self.selectedDroneTypes[localAvId][i]
            slotKey = slotKeys[i]
            self.droneSlotKeybinds.append(slotKey)
            
            # Create slot button (was a frame before but redundant)
            slotButton = DirectButton(
                relief=DGG.RAISED,
                frameSize=(-0.12, 0.12, -0.08, 0.08),
                frameColor=(0.2, 0.2, 0.2, 0.8),
                borderWidth=(0.01, 0.01),
                parent=self.droneSelectionFrame,
                pos=(-0.25 + i * slotSpacing, 0, 0),
                command = self.__handleDroneSlotClick,
                extraArgs = [i]
            )
            
            # Keybind label (top right)
            keybindText = OnscreenText(
                text=formatKeybindDisplay(slotKey),
                pos=(0.1, 0.06),
                scale=0.04,
                fg=(1, 1, 1, 0.7),
                align=TextNode.ARight,
                parent=slotButton,
                mayChange=True  # Allow changes if keybind updates
            )
            
            # Drone icon/name (center)
            droneName = OnscreenText(
                text=slotType.getName(),
                pos=(0, -0.01),
                scale=0.03,
                fg=slotType.getHatColor(),
                align=TextNode.ACenter,
                parent=slotButton,
                mayChange=True
            )
            
            # Cooldown text (bottom of slot, shows remaining time or "Ready")
            cooldownText = OnscreenText(
                text='Ready',
                pos=(0, -0.06),
                scale=0.025,
                fg=(0.3, 1.0, 0.3, 1),
                align=TextNode.ACenter,
                parent=slotButton,
                mayChange=True
            )
            
            slotData = {
                'keybindText': keybindText,
                'droneName': droneName,
                'cooldownText': cooldownText,
                'button': slotButton,
                'slotIndex': i,
                'cooldownTask': None
            }
            self.droneSelectionSlots.append(slotData)
    
    def __cleanupDroneSelectionUI(self):
        """Clean up the drone selection UI."""
        if hasattr(self, 'droneSelectionSlots'):
            for slot in self.droneSelectionSlots:
                if slot.get('button'):
                    slot['button'].destroy()
            self.droneSelectionSlots = []
        
        if hasattr(self, 'droneSelectionFrame') and self.droneSelectionFrame:
            self.droneSelectionFrame.destroy()
            self.droneSelectionFrame = None
        
        if hasattr(self, 'droneSelectionDialog') and self.droneSelectionDialog:
            self.droneSelectionDialog.destroy()
            self.droneSelectionDialog = None
    
    def __openDroneSelectionDialog(self, slotIndex):
        """Open dialog to select drone type for a slot."""
        from toontown.minigame.craning import CraneLeagueGlobals
        
        # Clean up existing dialog
        if hasattr(self, 'droneSelectionDialog') and self.droneSelectionDialog:
            self.droneSelectionDialog.destroy()
        
        # Create selection dialog
        self.droneSelectionDialog = DirectFrame(
            relief=None,
            image=DGG.getDefaultDialogGeom(),
            image_color=ToontownGlobals.GlobalDialogColor,
            image_scale=(1.0, 1, 0.8),
            pos=(0, 0, 0),
            parent=aspect2d,
            sortOrder=DGG.NO_FADE_SORT_INDEX + 2
        )
        
        # Title
        titleLabel = DirectLabel(
            parent=self.droneSelectionDialog,
            relief=None,
            text=f"Select Drone Type (Slot {slotIndex + 1})",
            text_scale=0.06,
            text_pos=(0, 0.3),
            text_fg=(0.1, 0.1, 0.4, 1),
            text_font=ToontownGlobals.getInterfaceFont()
        )
        
        # Load button assets
        buttons = loader.loadModel('phase_3/models/gui/dialog_box_buttons_gui')
        buttonImage = (buttons.find('**/ChtBx_OKBtn_UP'), 
                      buttons.find('**/ChtBx_OKBtn_DN'), 
                      buttons.find('**/ChtBx_OKBtn_Rllvr'))
        closeButtonImage = (buttons.find('**/CloseBtn_UP'), 
                          buttons.find('**/CloseBtn_DN'), 
                          buttons.find('**/CloseBtn_Rllvr'))
        
        # Create buttons for each drone type - dynamically get all drone types from enum
        droneTypes = list(CraneLeagueGlobals.DroneType)

        for i, droneType in enumerate(droneTypes):
            currentY = i // 4 * -.15 + .1
            currentX = i % 4 * .2 - .3
            
            # Drone type button
            typeButton = DirectButton(
                parent=self.droneSelectionDialog,
                relief=None,
                image=buttonImage,
                text=droneType.getName(),
                text_scale=0.04,
                text_pos=(0, -0.02),
                text_fg=droneType.getHatColor(),
                pos=(currentX, 0, currentY),
                command=self.__selectDroneType,
                extraArgs=[slotIndex, droneType]
            )
        
        # Close button
        closeButton = DirectButton(
            parent=self.droneSelectionDialog,
            relief=None,
            image=closeButtonImage,
            text="Cancel",
            text_scale=0.05,
            text_pos=(0, -0.1),
            pos=(0, 0, -0.3),
            command=self.__closeDroneSelectionDialog
        )
        
        buttons.removeNode()
    
    def __handleDroneSlotClick(self, slotIndex):
        """Handle clicking on a drone slot - behavior depends on game state."""
        # Check if drones are enabled
        if not self.__areDronesEnabled():
            return
        
        # Check if we're in rules phase (can change drone) or play phase (deploy drone)
        if hasattr(self, 'frameworkFSM') and self.frameworkFSM.getCurrentState():
            currentState = self.frameworkFSM.getCurrentState().getName()
            if currentState == 'frameworkRules':
                # During rules phase - open selection dialog
                self.__openDroneSelectionDialog(slotIndex)
            else:
                # During play phase - deploy the drone
                self.__deployDrone(slotIndex)
        else:
            # Fallback: if we can't determine state, try to deploy
            self.__deployDrone(slotIndex)
    
    def __selectDroneType(self, slotIndex, droneType):
        """Select a drone type for a slot. Prevents duplicates by swapping."""
        from toontown.minigame.craning import CraneLeagueGlobals
        
        localAvId = base.localAvatar.doId
        if localAvId not in self.selectedDroneTypes:
            self.selectedDroneTypes[localAvId] = [
                CraneLeagueGlobals.DroneType.LASER,
                CraneLeagueGlobals.DroneType.HEAL,
                CraneLeagueGlobals.DroneType.EXPLODEY
            ]
        
        # Check if this drone type is already in another slot
        currentSlots = self.selectedDroneTypes[localAvId]
        for otherSlotIndex, otherDroneType in enumerate(currentSlots):
            if otherSlotIndex != slotIndex and otherDroneType == droneType:
                # Swap: put the current slot's drone type into the other slot
                oldDroneType = currentSlots[slotIndex]
                currentSlots[otherSlotIndex] = oldDroneType
                # Update UI for the swapped slot
                self.__updateDroneSlotUI(otherSlotIndex)
                # Send update for swapped slot
                self.sendUpdate('setDroneTypeForToon', [base.localAvatar.doId, otherSlotIndex, oldDroneType.value])
                break
        
        # Update local selection
        self.selectedDroneTypes[localAvId][slotIndex] = droneType
        
        # Update UI
        self.__updateDroneSlotUI(slotIndex)
        
        # Send to server (avId, slotIndex, droneTypeValue)
        self.sendUpdate('setDroneTypeForToon', [base.localAvatar.doId, slotIndex, droneType.value])
        
        # Save the updated setup to the toon's database
        self.__saveDroneSetupToToon()
        
        # Close dialog
        self.__closeDroneSelectionDialog()
    
    def __closeDroneSelectionDialog(self):
        """Close the drone selection dialog."""
        if hasattr(self, 'droneSelectionDialog') and self.droneSelectionDialog:
            self.droneSelectionDialog.destroy()
            self.droneSelectionDialog = None
    
    def __loadDroneSetupFromToon(self):
        """Load the saved drone setup from the local toon."""
        if not hasattr(base, 'localAvatar') or not base.localAvatar:
            return
        
        # Get saved setup from toon
        if hasattr(base.localAvatar, 'droneSetup') and base.localAvatar.droneSetup:
            savedSetup = base.localAvatar.droneSetup
            if len(savedSetup) == 3:
                from toontown.minigame.craning import CraneLeagueGlobals
                localAvId = base.localAvatar.doId
                # Convert uint8 values to DroneType enums
                self.selectedDroneTypes[localAvId] = [
                    CraneLeagueGlobals.DroneType(savedSetup[0]),
                    CraneLeagueGlobals.DroneType(savedSetup[1]),
                    CraneLeagueGlobals.DroneType(savedSetup[2])
                ]
                # Send to server to sync with other clients
                for i, droneType in enumerate(self.selectedDroneTypes[localAvId]):
                    self.sendUpdate('setDroneTypeForToon', [localAvId, i, droneType.value])
    
    def __saveDroneSetupToToon(self):
        """Save the current drone setup to the local toon's database."""
        if not hasattr(base, 'localAvatar') or not base.localAvatar:
            return
        
        localAvId = base.localAvatar.doId
        if localAvId not in self.selectedDroneTypes:
            return
        
        # Convert DroneType enums to uint8 values
        setup = [droneType.value for droneType in self.selectedDroneTypes[localAvId]]
        
        # Save to toon (this will persist to database via sendUpdate)
        # The AI will handle the database save via b_setDroneSetup
        base.localAvatar.sendUpdate('setDroneSetup', [setup])
    
    def __areDronesEnabled(self):
        """Check if drones are enabled via the modifier system."""
        if not hasattr(self, 'ruleset') or not self.ruleset:
            return False
        enabled = getattr(self.ruleset, 'WANT_DRONES', False)
        self.notify.debug(f"__areDronesEnabled: {enabled}, ruleset.WANT_DRONES = {getattr(self.ruleset, 'WANT_DRONES', 'NOT_SET')}")
        return enabled
    
    def __updateDroneUIVisibility(self):
        """Update drone UI visibility based on whether drones are enabled."""
        # Create UI if it doesn't exist and drones are enabled
        if (not hasattr(self, 'droneSelectionFrame') or self.droneSelectionFrame is None) and self.__areDronesEnabled():
            self.__loadDroneSetupFromToon()
            self.__createDroneSelectionUI()
        
        if not hasattr(self, 'droneSelectionFrame') or self.droneSelectionFrame is None:
            return
        
        if self.__areDronesEnabled():
            # Show drone UI if we're in play state or rules state
            if hasattr(self, 'gameFSM') and self.gameFSM.getCurrentState():
                currentState = self.gameFSM.getCurrentState().getName()
                if currentState == 'play':
                    self.droneSelectionFrame.show()
                elif currentState == 'frameworkRules':
                    self.droneSelectionFrame.show()
                else:
                    self.droneSelectionFrame.hide()
            elif hasattr(self, 'frameworkFSM') and self.frameworkFSM.getCurrentState():
                # Check framework FSM if game FSM doesn't exist yet
                frameworkState = self.frameworkFSM.getCurrentState().getName()
                if frameworkState == 'frameworkRules':
                    self.droneSelectionFrame.show()
                else:
                    self.droneSelectionFrame.hide()
        else:
            # Hide drone UI if drones are disabled
            self.droneSelectionFrame.hide()
    
    def __updateDroneSlotUI(self, slotIndex):
        """Update the UI for a specific drone slot."""
        from toontown.minigame.craning import CraneLeagueGlobals
        
        if slotIndex >= len(self.droneSelectionSlots):
            return
        
        # Use spectated player's data if spectating, otherwise use local toon's data
        localAvId = base.localAvatar.doId
        targetAvId = localAvId
        if hasattr(self, 'scoreboard') and self.scoreboard is not None:
            spectatedAvId = self.scoreboard.getSpectatedAvId()
            if spectatedAvId is not None:
                targetAvId = spectatedAvId
        
        if targetAvId not in self.selectedDroneTypes:
            return
        
        slot = self.droneSelectionSlots[slotIndex]
        droneType = self.selectedDroneTypes[targetAvId][slotIndex]
        
        # Update drone name
        if slot.get('droneName'):
            slot['droneName']['text'] = droneType.getName()
            slot['droneName']['fg'] = droneType.getHatColor()
    
    def setDroneTypeForToon(self, avId, slotIndex, droneTypeValue):
        """Receive drone type update from server."""
        from toontown.minigame.craning import CraneLeagueGlobals
        
        droneType = CraneLeagueGlobals.DroneType(droneTypeValue)
        
        if avId not in self.selectedDroneTypes:
            self.selectedDroneTypes[avId] = [
                CraneLeagueGlobals.DroneType.LASER,
                CraneLeagueGlobals.DroneType.HEAL,
                CraneLeagueGlobals.DroneType.EXPLODEY
            ]
        
        if slotIndex >= 0 and slotIndex < 3:
            self.selectedDroneTypes[avId][slotIndex] = droneType
            
            # Update UI if it's the local toon or the spectated player
            localAvId = base.localAvatar.doId
            spectatedAvId = None
            if hasattr(self, 'scoreboard') and self.scoreboard is not None:
                spectatedAvId = self.scoreboard.getSpectatedAvId()
            
            if avId == localAvId or (spectatedAvId is not None and avId == spectatedAvId):
                self.__updateDroneSlotUI(slotIndex)

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
        
        self.heatDisplay.update(self.modifiers)

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
        self.ruleset = CraneLeagueGlobals.CraneGameRuleset.fromStruct(attrs)
        self.notify.debug(f"setRawRuleset: WANT_DRONES = {getattr(self.ruleset, 'WANT_DRONES', 'NOT_SET')}")
        self.updateRulesetDependencies()
        # Update drone UI visibility when ruleset changes
        self.__updateDroneUIVisibility()

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
        self.__cleanupDroneSelectionUI()
        # Clean up forfeit dialogs
        if self.forfeitDialog:
            self.forfeitDialog.cleanup()
            self.forfeitDialog = None
        if self.forfeitRequesterDialog:
            self.forfeitRequesterDialog.cleanup()
            self.forfeitRequesterDialog = None
        # Clean up restart dialogs
        if self.restartDialog:
            self.restartDialog.cleanup()
            self.restartDialog = None
        if self.restartRequesterDialog:
            self.restartRequesterDialog.cleanup()
            self.restartRequesterDialog = None

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
        
        # In tournament mode, use tournament scoreboard logic
        if self.tournamentActive and hasattr(self, 'tournamentCurrentMatchPlayers'):
            # Tournament mode: update scoreboard based on toggle state
            self.__updateTournamentScoreboard()
        else:
            # Normal mode: show all non-spectators
            for avId in self.getParticipantIdsNotSpectating():
                self.scoreboard.addToon(avId)

        # Check if we're waiting for match ready-up (tournament break state)
        if self.waitingForMatchReady:
            # Don't start countdown yet - show match ready UI instead
            # Position camera during break phase (same as prepare phase)
            self.__positionCameraForMatchReady()
            self.boss.prepareBossForBattle()
            # Clean up all status effects when starting a new round
            if hasattr(self, 'statusEffectSystem') and self.statusEffectSystem:
                self.statusEffectSystem.cleanup()
            # Make absolutely sure all indicators are cleaned up
            self.removeStatusIndicators()
            return  # Exit early, countdown will start when all players ready
        
        # If we're in a tournament with match players, wait briefly to see if ready request arrives
        # This prevents countdown from starting before requestMatchReady arrives
        if self.tournamentActive and hasattr(self, 'tournamentCurrentMatchPlayers') and self.tournamentCurrentMatchPlayers:
            # Give requestMatchReady a chance to arrive (it should come before restart)
            taskMgr.doMethodLater(0.15, lambda task: self.__checkIfShouldWaitForReady(),
                                 self.uniqueName('check-ready-wait'))
            # Do basic setup but don't start countdown yet
            self.boss.prepareBossForBattle()
            if hasattr(self, 'statusEffectSystem') and self.statusEffectSystem:
                self.statusEffectSystem.cleanup()
            self.removeStatusIndicators()
            return
        
        # Normal flow: start countdown immediately
        self.introductionMovie = self.__generatePrepareInterval()
        self.introductionMovie.start()
        self.boss.prepareBossForBattle()

        # Clean up all status effects when starting a new round
        if hasattr(self, 'statusEffectSystem') and self.statusEffectSystem:
            self.statusEffectSystem.cleanup()

        # Make absolutely sure all indicators are cleaned up
        self.removeStatusIndicators()

    def exitPrepare(self):
        if self.introductionMovie:
            self.introductionMovie.pause()
            self.introductionMovie = None
        self.__hideOverlayText()
        # Clean up match ready UI
        self.__hideMatchReadyUI()

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

        self.boss.prepareBossForBattle()

        self.accept("LocalSetFinalBattleMode", self.toFinalBattleMode)
        self.accept("LocalSetOuchMode", self.toOuchMode)
        self.accept("ChatMgr-enterMainMenu", self.chatClosed)
        self.accept("spectatedPlayerChanged", self.__onSpectatedPlayerChanged)
        
        # Only enable drones if the modifier is active
        if self.__areDronesEnabled():
            # Enable drone deployment keybinds for 3 slots from settings (both binds)
            slotKeyNames = ['DRONE_SLOT_0_KEY', 'DRONE_SLOT_1_KEY', 'DRONE_SLOT_2_KEY']
            self.droneSlotKeybinds = []
            for i, keyName in enumerate(slotKeyNames):
                # Get both binds for this slot
                binds = base.settings.getControlBinds(keyName)
                for bind in binds:
                    if bind:
                        self.droneSlotKeybinds.append(bind)
                        self.accept(bind, self.__deployDrone, [i])
            
            # Move drone UI next to laff meter (right side) and show it
            # If drone UI doesn't exist (shouldn't happen, but be safe), create it
            if not hasattr(self, 'droneSelectionFrame') or self.droneSelectionFrame is None:
                self.__createDroneSelectionUI()
            
            if hasattr(self, 'droneSelectionFrame') and self.droneSelectionFrame:
                # Laff meter is at base.a2dBottomLeft with pos around (0.133-0.153, 0.0, 0.13)
                # Laff meter width ~0.15, so it extends to ~0.283 (non-monkey) or ~0.303 (monkey)
                # Position drone UI to the right of it with sufficient spacing to avoid overlap
                # First slot is at framePos - 0.25 relative to frame, and slot width is 0.24 (from -0.12 to +0.12),
                # so first slot extends from framePos - 0.37 to framePos - 0.13 in world space.
                # To avoid overlap with laff meter ending at ~0.303, we need framePos - 0.37 >= 0.35,
                # which means framePos >= 0.72. Using 0.72 to provide comfortable spacing.
                self.droneSelectionFrame.reparentTo(base.a2dBottomLeft)
                self.droneSelectionFrame.setPos(0.72, 0.0, 0.13)
                # Update slot positions to be horizontal with more spacing (0.2 instead of 0.15)
                slotSpacing = 0.25
                if hasattr(self, 'droneSelectionSlots'):
                    for i, slot in enumerate(self.droneSelectionSlots):
                        if slot.get('button'):
                            # Slots are already positioned correctly relative to frame during creation
                            # No need to reposition them here
                            pass
                # Show the UI
                self.droneSelectionFrame.show()
            
            # Initialize cooldown displays for all slots
            # Use spectated player's data if spectating, otherwise use local toon's data
            localAvId = base.localAvatar.doId
            targetAvId = localAvId
            if hasattr(self, 'scoreboard') and self.scoreboard is not None:
                spectatedAvId = self.scoreboard.getSpectatedAvId()
                if spectatedAvId is not None:
                    targetAvId = spectatedAvId
            
            for i in range(3):
                if targetAvId in self.droneCooldowns and i in self.droneCooldowns[targetAvId]:
                    startTime, duration = self.droneCooldowns[targetAvId][i]
                    self.__updateDroneSlotCooldown(i, startTime, duration)
                else:
                    self.__updateDroneSlotCooldown(i, None, None)
        else:
            # Drones disabled - hide UI if it exists
            if hasattr(self, 'droneSelectionFrame') and self.droneSelectionFrame:
                self.droneSelectionFrame.hide()

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
        if localAvId in self.droneCooldowns and slotIndex in self.droneCooldowns[localAvId]:
            startTime, duration = self.droneCooldowns[localAvId][slotIndex]
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
        
        # Clean up drone slot cooldown tasks
        if hasattr(self, 'droneSelectionSlots'):
            for slot in self.droneSelectionSlots:
                if slot.get('cooldownTask'):
                    taskMgr.remove(slot['cooldownTask'])
                    slot['cooldownTask'] = None
        
        # Hide drone UI when exiting play
        if hasattr(self, 'droneSelectionFrame') and self.droneSelectionFrame:
            self.droneSelectionFrame.hide()
        
        # Disable drone deployment keybinds
        if hasattr(self, 'droneSlotKeybinds'):
            for keybind in self.droneSlotKeybinds:
                self.ignore(keybind)
            self.droneSlotKeybinds = []
        

        # Clean up all status effects when exiting play state
        if hasattr(self, 'statusEffectSystem') and self.statusEffectSystem:
            self.statusEffectSystem.cleanup()
    
    def setDroneCooldown(self, avId, slotIndex, duration):
        """Receive drone cooldown from server and update UI."""
        startTime = globalClock.getFrameTime()
        if avId not in self.droneCooldowns:
            self.droneCooldowns[avId] = {}
        self.droneCooldowns[avId][slotIndex] = (startTime, duration)
        
        # Update UI for local toon or spectated player
        localAvId = base.localAvatar.doId
        spectatedAvId = None
        if hasattr(self, 'scoreboard') and self.scoreboard is not None:
            spectatedAvId = self.scoreboard.getSpectatedAvId()
        
        if avId == localAvId or (spectatedAvId is not None and avId == spectatedAvId):
            self.__updateDroneSlotCooldown(slotIndex, startTime, duration)
    
    def clearAllDroneCooldowns(self):
        """Clear all drone cooldowns (called by server on round restart)."""
        self.droneCooldowns.clear()
        # Update all slot cooldown displays
        if hasattr(self, 'droneSelectionSlots'):
            for i in range(3):
                self.__updateDroneSlotCooldown(i, None, None)
    
    def __onSpectatedPlayerChanged(self, avId):
        """Called when the spectator switches to a different player."""
        # Update all drone slot UIs and cooldowns for the new spectated player
        if not self.__areDronesEnabled():
            return
        
        # Get target avId (spectated player or local toon)
        localAvId = base.localAvatar.doId
        targetAvId = avId if avId is not None else localAvId
        
        # Update all slots
        for i in range(3):
            # Update drone type display
            self.__updateDroneSlotUI(i)
            
            # Update cooldown display
            if targetAvId in self.droneCooldowns and i in self.droneCooldowns[targetAvId]:
                startTime, duration = self.droneCooldowns[targetAvId][i]
                self.__updateDroneSlotCooldown(i, startTime, duration)
            else:
                self.__updateDroneSlotCooldown(i, None, None)

    def __updateDroneSlotCooldown(self, slotIndex, startTime, duration):
        """Update the cooldown display for a specific drone slot."""
        if not hasattr(self, 'droneSelectionSlots') or slotIndex >= len(self.droneSelectionSlots):
            return
        
        slot = self.droneSelectionSlots[slotIndex]
        if not slot.get('cooldownText'):
            return
        
        # Clean up existing task for this slot
        if slot.get('cooldownTask'):
            taskMgr.remove(slot['cooldownTask'])
            slot['cooldownTask'] = None
        
        if startTime is None or duration is None:
            # No cooldown - show "Ready"
            slot['cooldownText']['text'] = 'Ready'
            slot['cooldownText']['fg'] = (0.3, 1.0, 0.3, 1)
            return
        
        # Start update task for this slot
        def updateTask(task, slotIdx=slotIndex, start=startTime, dur=duration):
            if slotIdx >= len(self.droneSelectionSlots):
                return task.done
            slotData = self.droneSelectionSlots[slotIdx]
            if not slotData.get('cooldownText'):
                return task.done
            
            currentTime = globalClock.getFrameTime()
            elapsed = currentTime - start
            remaining = max(0, dur - elapsed)
            
            if remaining <= 0:
                slotData['cooldownText']['text'] = 'Ready'
                slotData['cooldownText']['fg'] = (0.3, 1.0, 0.3, 1)
                slotData['cooldownTask'] = None
                return task.done
            else:
                # Show remaining time (MM:SS format)
                minutes = int(remaining // 60)
                seconds = int(remaining % 60)
                slotData['cooldownText']['text'] = f'{minutes}:{seconds:02d}'
                slotData['cooldownText']['fg'] = (1.0, 0.3, 0.3, 1)  # Red when on cooldown
                return task.cont
        
        slot['cooldownTask'] = taskMgr.add(
            updateTask,
            f'droneSlotCooldown{slotIndex}',
            extraArgs=[],
            appendTask=True
        )
    
    def __showDroneCooldownIndicator(self, startTime, duration):
        """Display the drone cooldown indicator near the leave button."""
        from panda3d.core import TransparencyAttrib
        
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
        if localAvId in self.droneCooldowns:
            startTime, duration = self.droneCooldowns[localAvId]
            # If cooldown is still active, show it
            self.__showDroneCooldownIndicator(startTime, duration)
        else:
            # No cooldown, show "Drone Ready!"
            self.__showDroneReadyIndicator()
    
    def __showDroneReadyIndicator(self):
        """Show the 'Drone Ready!' indicator without a cooldown."""
        from panda3d.core import TransparencyAttrib
        
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
        
        # Clear local cooldown cache
        self.droneCooldowns.clear()
        
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
        if self.bestOfValue > 1:
            # Check round wins
            roundWins = self.roundWins.get(self.victor, 0)
            winsNeeded = (self.bestOfValue + 1) // 2
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
        
        # Clean up forfeit dialogs
        if self.forfeitDialog:
            self.forfeitDialog.cleanup()
            self.forfeitDialog = None
        if self.forfeitRequesterDialog:
            self.forfeitRequesterDialog.cleanup()
            self.forfeitRequesterDialog = None
        # Clean up restart dialogs
        if self.restartDialog:
            self.restartDialog.cleanup()
            self.restartDialog = None
        if self.restartRequesterDialog:
            self.restartRequesterDialog.cleanup()
            self.restartRequesterDialog = None
        
        # Clean up all drones when entering cleanup
        self.__cleanupAllDrones()
        
        # Clear local cooldown cache
        self.droneCooldowns.clear()
        
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
        
        # Clean up tournament UI elements
        if hasattr(self, 'tournamentProgressLabel') and self.tournamentProgressLabel is not None:
            self.tournamentProgressLabel.destroy()
            self.tournamentProgressLabel = None
        
        # Disable F2 keybind
        self.ignore('f2')
        
        # Reset tournament state
        self.tournamentActive = False
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
        self.boss.prepareBossForBattle()
        self.boss.setRuleset(self.ruleset)

    def getStatusEffectSystem(self) -> DistributedStatusEffectSystem | None:
        return self.statusEffectSystem
    
    def setStatusEffectSystemId(self, statusEffectSystemId: int) -> None:
        self.statusEffectSystem = base.cr.getDo(statusEffectSystemId)

    def addScore(self, avId: int, score: int, reason: str):

        # Convert the reason into a valid reason enum that our scoreboard accepts.
        convertedReason = CraneLeagueGlobals.ScoreReason.from_astron(reason)
        if convertedReason is None:
            convertedReason = CraneLeagueGlobals.ScoreReason.DEFAULT
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
        if flag == CraneLeagueGlobals.OVERTIME_FLAG_START:
            self.overtimeActive = True
            self.ruleset.REVIVE_TOONS_UPON_DEATH = False
        elif flag == CraneLeagueGlobals.OVERTIME_FLAG_ENABLE:
            if self.bossSpeedrunTimer:
                self.bossSpeedrunTimer.show_overtime()
        else:
            self.overtimeActive = False
            if self.bossSpeedrunTimer:
                self.bossSpeedrunTimer.hide_overtime()

    def setModifiers(self, mods):
        modsToSet = []  # A list of CFORulesetModifierBase subclass instances
        for modStruct in mods:
            modsToSet.append(CraneLeagueGlobals.CFORulesetModifierBase.fromStruct(modStruct))

        self.modifiers = modsToSet
        self.modifiers.sort(key=lambda m: m.MODIFIER_TYPE)
        self.heatDisplay.update(self.modifiers)

    def restart(self):
        """
        Called via astron update. Do any client side logic needed in order to restart the game.
        """
        # If we're in a tournament and waiting for match ready, don't enter prepare yet
        # The requestMatchReady call will handle entering prepare when ready
        if self.tournamentActive and self.waitingForMatchReady:
            # We're already waiting, don't enter prepare again
            return
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



        # Show the play button for all players (everyone needs to ready up)
        self.playButton.show()
        
        # Only show the modifiers, best-of, and tournament buttons for the leader
        if self.isLocalToonHost():
            self.modifiersButton.show()
            self.bestOfButton.show()
            self.tournamentButton.show()

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
        self.__loadDroneSetupFromToon()
        
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
        if hasattr(self, 'droneSelectionFrame') and self.droneSelectionFrame:
            self.droneSelectionFrame.hide()
        
        # Hide tournament button
        if self.tournamentButton:
            self.tournamentButton.hide()

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
        """Receive updated spawn order from server"""
        self.toonSpawnpointOrder = order[:]
        self.notify.info(f"Received spawn order update: {self.toonSpawnpointOrder}")

    def __handleBestOfButton(self):
        """Handle the "Best of" button click"""
        # Cycle through Best of 1, 3, 5, 7
        if self.bestOfValue == 1:
            self.bestOfValue = 3
        elif self.bestOfValue == 3:
            self.bestOfValue = 5
        elif self.bestOfValue == 5:
            self.bestOfValue = 7
        else:
            self.bestOfValue = 1
        
        # Update button text
        self.bestOfButton['text'] = f'Best of {self.bestOfValue}'
        
        # Send update to server if we're the leader
        if self.isLocalToonHost():
            self.sendUpdate('setBestOf', [self.bestOfValue])

    def setBestOf(self, value):
        """Receive best-of setting from server"""
        self.bestOfValue = value
        if self.bestOfButton:
            self.bestOfButton['text'] = f'Best of {self.bestOfValue}'
        self.notify.info(f"Best of value set to: {self.bestOfValue}")

    def setRoundInfo(self, currentRound, roundWins):
        """Receive round information from server"""
        self.currentRound = currentRound
        
        # Convert roundWins list back to dict using avIdList
        self.roundWins = {}
        for i, avId in enumerate(self.avIdList):
            if i < len(roundWins):
                self.roundWins[avId] = roundWins[i]
        
        # Update scoreboard with round information
        # Pass avIdList to ensure correct order matching server
        if self.scoreboard:
            self.scoreboard.setRoundInfo(currentRound, roundWins, self.bestOfValue, self.avIdList)

    def setModifiers(self, mods):
        """Receive modifier updates from the server"""
        modsToSet = []  # A list of CFORulesetModifierBase subclass instances
        for modStruct in mods:
            modsToSet.append(CraneLeagueGlobals.CFORulesetModifierBase.fromStruct(modStruct))

        self.modifiers = modsToSet
        self.modifiers.sort(key=lambda m: m.MODIFIER_TYPE)
        self.heatDisplay.update(self.modifiers)
        
        # Update the modifiers panel if it's visible
        if self.modifiersPanelVisible and self.currentModifiersList is not None:
            self.__updateModifiersLists()

    def __nextRound(self, task=None):
        """Transition to the next round"""
        # Clean up all drones when round restarts
        self.__cleanupAllDrones()
        
        # Clear local cooldown cache for next round
        self.droneCooldowns.clear()
        
        # The server will handle the transition to the next round automatically
        # We just need to clean up the victory state
        return Task.done

    def __removeModifier(self, modifierIndex):
        """Remove a modifier from the game"""
        if self.isLocalToonHost() and modifierIndex < len(self.modifiers):
            modifierEnum = self.modifiers[modifierIndex].MODIFIER_ENUM
            self.sendUpdate('removeModifier', [modifierEnum])
    
    def setRequestForfeit(self, requesterAvId):
        """Receive forfeit request from server"""
        self.pendingForfeitRequester = requesterAvId
        self.forfeitConsents.clear()
        self.forfeitConsents.add(requesterAvId)  # Requester automatically consents
        
        requesterToon = self.cr.getDo(requesterAvId)
        if not requesterToon:
            self.notify.warning(f"Could not find requester toon {requesterAvId}")
            return
        
        requesterName = requesterToon.getName()
        requesterDNA = requesterToon.getStyle()
        
        # Clean up any existing dialogs
        if self.forfeitDialog:
            self.forfeitDialog.cleanup()
            self.forfeitDialog = None
        if self.forfeitRequesterDialog:
            self.forfeitRequesterDialog.cleanup()
            self.forfeitRequesterDialog = None
        
        # Check if local player is a spectator - don't show dialog to spectators
        if base.localAvatar.doId in self.getSpectators():
            self.notify.info(f"Forfeit requested by {requesterName} (spectator, no dialog shown)")
            return
        
        # Show different dialogs based on whether this is the requester
        from toontown.toontowngui import ToonHeadDialog
        from toontown.toontowngui import TTDialog
        from otp.otpbase import OTPLocalizer
        from direct.gui.DirectGui import DGG
        
        if requesterAvId == base.localAvatar.doId:
            # Requester sees status dialog with cancel button (like BoardingGroupInvitingPanel)
            participants = self.getParticipantIdsNotSpectating()
            numNeeded = len(participants)
            message = f"Forfeit requested!\n\n"
            message += f"Waiting for {numNeeded - 1} other player(s) to confirm."
            
            # Create dialog with desired scale
            desiredScale = 0.4
            self.forfeitRequesterDialog = ToonHeadDialog.ToonHeadDialog(
                dna=requesterDNA,
                text=message,
                style=TTDialog.CancelOnly,
                buttonTextList=[OTPLocalizer.GuildInviterCancel],
                command=self.__handleForfeitRequesterDialog,
                image_color=(1.0, 0.89, 0.77, 1.0),
                geom_scale=0.2,
                geom_pos=(-0.1, 0, -0.025),
                pad=(0.075, 0.075),
                topPad=0,
                midPad=0,
                pos=(0.45, 0, 0.75),
                scale=desiredScale
            )
            # The default OTPDialog animation is hardcoded to animate to scale 1.0, which overrides
            # our scale parameter. We can't easily stop it since it starts in OTPDialog.__init__,
            # but we can create our own animation that runs and overrides it.
            # The default animation: 0.2s to 1.1, then 0.09s to 1.0 (total ~0.29s)
            from direct.interval.IntervalGlobal import Sequence, LerpScaleInterval, Wait
            # Create our custom animation that ends at desiredScale instead of 1.0
            # We'll start it immediately to compete with/override the default animation
            self.forfeitRequesterDialog.setScale(0.01)  # Match the default animation's start
            customAnim = Sequence(
                LerpScaleInterval(self.forfeitRequesterDialog, 0.2, desiredScale * 1.1, 0.01, blendType='easeInOut'),
                LerpScaleInterval(self.forfeitRequesterDialog, 0.09, desiredScale, blendType='easeInOut')
            )
            customAnim.start()
            self.forfeitRequesterDialog.show()
        else:
            # Other players see confirmation dialog (like GroupInvitee)
            message = f"{requesterName} has requested to FORFEIT the match.\n\n"
            
            # Create dialog with desired scale
            desiredScale = 0.5
            self.forfeitDialog = ToonHeadDialog.ToonHeadDialog(
                dna=requesterDNA,
                text=message,
                style=TTDialog.TwoChoice,
                buttonTextList=[OTPLocalizer.FriendInviteeOK, OTPLocalizer.FriendInviteeNo],
                command=self.__handleForfeitDialog,
                image_color=(1.0, 0.89, 0.77, 1.0),
                geom_scale=0.2,
                geom_pos=(-0.1, 0, -0.025),
                pad=(0.075, 0.075),
                text_wordwrap=14,
                topPad=0,
                midPad=0,
                pos=(0.45, 0, 0.75),
                scale=desiredScale
            )
            # The default OTPDialog animation is hardcoded to animate to scale 1.0, which overrides
            # our scale parameter. We can't easily stop it since it starts in OTPDialog.__init__,
            # but we can create our own animation that runs and overrides it.
            # The default animation: 0.2s to 1.1, then 0.09s to 1.0 (total ~0.29s)
            from direct.interval.IntervalGlobal import Sequence, LerpScaleInterval, Wait
            # Create our custom animation that ends at desiredScale instead of 1.0
            # We'll start it immediately to compete with/override the default animation
            self.forfeitDialog.setScale(0.01)  # Match the default animation's start
            customAnim = Sequence(
                LerpScaleInterval(self.forfeitDialog, 0.2, desiredScale * 1.1, 0.01, blendType='easeInOut'),
                LerpScaleInterval(self.forfeitDialog, 0.09, desiredScale, blendType='easeInOut')
            )
            customAnim.start()
            self.forfeitDialog.show()
        
        self.notify.info(f"Forfeit requested by {requesterName}")
    
    def setUpdateForfeitConsents(self, consentAvIds):
        """Receive updated consent list from server"""
        self.forfeitConsents = set(consentAvIds)
        
        participants = self.getParticipantIdsNotSpectating()
        numConsented = len(self.forfeitConsents)
        numNeeded = len(participants)
        
        if numConsented < numNeeded:
            # Update requester dialog to show progress
            if self.forfeitRequesterDialog and not self.forfeitRequesterDialog.isEmpty():
                requesterToon = self.cr.getDo(self.pendingForfeitRequester)
                requesterDNA = requesterToon.getStyle() if requesterToon else None
                if requesterDNA:
                    message = f"Forfeit requested!\n\n"
                    message += f"Progress: {numConsented}/{numNeeded} players confirmed."
                    self.forfeitRequesterDialog['text'] = message
            
            # Update non-requester dialog to show progress
            if self.forfeitDialog and not self.forfeitDialog.isEmpty():
                requesterToon = self.cr.getDo(self.pendingForfeitRequester)
                requesterName = requesterToon.getName() if requesterToon else "Unknown"
                message = f"{requesterName} has requested to FORFEIT the match.\n\n"
                message += f"Progress: {numConsented}/{numNeeded} players confirmed"
                self.forfeitDialog['text'] = message
    
    def setCancelForfeit(self):
        """Receive forfeit cancellation from server"""
        self.pendingForfeitRequester = None
        self.forfeitConsents.clear()
        
        # Clean up dialogs
        if self.forfeitDialog:
            self.forfeitDialog.cleanup()
            self.forfeitDialog = None
        if self.forfeitRequesterDialog:
            self.forfeitRequesterDialog.cleanup()
            self.forfeitRequesterDialog = None
        
        base.localAvatar.setSystemMessage(0, "Forfeit request has been cancelled.")
    
    def setCleanupForfeitDialogs(self):
        """Clean up forfeit dialogs without showing cancellation message (used when forfeit is executed)"""
        self.pendingForfeitRequester = None
        self.forfeitConsents.clear()
        
        # Clean up dialogs without showing message
        if self.forfeitDialog:
            self.forfeitDialog.cleanup()
            self.forfeitDialog = None
        if self.forfeitRequesterDialog:
            self.forfeitRequesterDialog.cleanup()
            self.forfeitRequesterDialog = None
    
    def __handleForfeitDialog(self, value):
        """Handle forfeit dialog button click (for non-requesters)"""
        from direct.gui.DirectGui import DGG
        
        if self.forfeitDialog:
            self.forfeitDialog.cleanup()
            self.forfeitDialog = None
        
        if value == DGG.DIALOG_OK:  # OK/Yes button
            self.sendUpdate('confirmForfeit', [])
        else:  # No button - reject the forfeit
            self.sendUpdate('rejectForfeit', [])
    
    def __handleForfeitRequesterDialog(self, value):
        """Handle forfeit requester dialog button click (cancel button)"""
        if self.forfeitRequesterDialog:
            self.forfeitRequesterDialog.cleanup()
            self.forfeitRequesterDialog = None
        
        # Cancel button was clicked - send cancel request to server
        self.sendUpdate('cancelForfeitRequest', [])
    
    def setRequestRestart(self, requesterAvId):
        """Receive restart request from server"""
        self.pendingRestartRequester = requesterAvId
        self.restartConsents.clear()
        self.restartConsents.add(requesterAvId)  # Requester automatically consents
        
        requesterToon = self.cr.getDo(requesterAvId)
        if not requesterToon:
            self.notify.warning(f"Could not find requester toon {requesterAvId}")
            return
        
        requesterName = requesterToon.getName()
        requesterDNA = requesterToon.getStyle()
        
        # Clean up any existing dialogs
        if self.restartDialog:
            self.restartDialog.cleanup()
            self.restartDialog = None
        if self.restartRequesterDialog:
            self.restartRequesterDialog.cleanup()
            self.restartRequesterDialog = None
        
        # Check if local player is a spectator - don't show dialog to spectators
        if base.localAvatar.doId in self.getSpectators():
            self.notify.info(f"Restart requested by {requesterName} (spectator, no dialog shown)")
            return
        
        # Show different dialogs based on whether this is the requester
        from toontown.toontowngui import ToonHeadDialog
        from toontown.toontowngui import TTDialog
        from otp.otpbase import OTPLocalizer
        from direct.gui.DirectGui import DGG
        
        if requesterAvId == base.localAvatar.doId:
            # Requester sees status dialog with cancel button (like BoardingGroupInvitingPanel)
            participants = self.getParticipantIdsNotSpectating()
            numNeeded = len(participants)
            message = f"Restart requested!\n\n"
            message += f"Waiting for {numNeeded - 1} other player(s) to confirm."
            
            # Create dialog with desired scale
            desiredScale = 0.4
            self.restartRequesterDialog = ToonHeadDialog.ToonHeadDialog(
                dna=requesterDNA,
                text=message,
                style=TTDialog.CancelOnly,
                buttonTextList=[OTPLocalizer.GuildInviterCancel],
                command=self.__handleRestartRequesterDialog,
                image_color=(1.0, 0.89, 0.77, 1.0),
                geom_scale=0.2,
                geom_pos=(-0.1, 0, -0.025),
                pad=(0.075, 0.075),
                topPad=0,
                midPad=0,
                pos=(0.45, 0, 0.75),
                scale=desiredScale
            )
            # The default OTPDialog animation is hardcoded to animate to scale 1.0, which overrides
            # our scale parameter. We can't easily stop it since it starts in OTPDialog.__init__,
            # but we can create our own animation that runs and overrides it.
            # The default animation: 0.2s to 1.1, then 0.09s to 1.0 (total ~0.29s)
            from direct.interval.IntervalGlobal import Sequence, LerpScaleInterval, Wait
            # Create our custom animation that ends at desiredScale instead of 1.0
            # We'll start it immediately to compete with/override the default animation
            self.restartRequesterDialog.setScale(0.01)  # Match the default animation's start
            customAnim = Sequence(
                LerpScaleInterval(self.restartRequesterDialog, 0.2, desiredScale * 1.1, 0.01, blendType='easeInOut'),
                LerpScaleInterval(self.restartRequesterDialog, 0.09, desiredScale, blendType='easeInOut')
            )
            customAnim.start()
            self.restartRequesterDialog.show()
        else:
            # Other players see confirmation dialog (like GroupInvitee)
            message = f"{requesterName} has requested to restart the match.\n\n"
            
            # Create dialog with desired scale
            desiredScale = 0.5
            self.restartDialog = ToonHeadDialog.ToonHeadDialog(
                dna=requesterDNA,
                text=message,
                style=TTDialog.TwoChoice,
                buttonTextList=[OTPLocalizer.FriendInviteeOK, OTPLocalizer.FriendInviteeNo],
                command=self.__handleRestartDialog,
                image_color=(1.0, 0.89, 0.77, 1.0),
                geom_scale=0.2,
                geom_pos=(-0.1, 0, -0.025),
                pad=(0.075, 0.075),
                topPad=0,
                midPad=0,
                pos=(0.45, 0, 0.75),
                scale=desiredScale
            )
            # The default OTPDialog animation is hardcoded to animate to scale 1.0, which overrides
            # our scale parameter. We can't easily stop it since it starts in OTPDialog.__init__,
            # but we can create our own animation that runs and overrides it.
            # The default animation: 0.2s to 1.1, then 0.09s to 1.0 (total ~0.29s)
            from direct.interval.IntervalGlobal import Sequence, LerpScaleInterval, Wait
            # Create our custom animation that ends at desiredScale instead of 1.0
            # We'll start it immediately to compete with/override the default animation
            self.restartDialog.setScale(0.01)  # Match the default animation's start
            customAnim = Sequence(
                LerpScaleInterval(self.restartDialog, 0.2, desiredScale * 1.1, 0.01, blendType='easeInOut'),
                LerpScaleInterval(self.restartDialog, 0.09, desiredScale, blendType='easeInOut')
            )
            customAnim.start()
            self.restartDialog.show()
        
        self.notify.info(f"Restart requested by {requesterName}")
    
    def setUpdateRestartConsents(self, consentAvIds):
        """Receive updated consent list from server"""
        self.restartConsents = set(consentAvIds)
        
        participants = self.getParticipantIdsNotSpectating()
        numConsented = len(self.restartConsents)
        numNeeded = len(participants)
        
        if numConsented < numNeeded:
            # Update requester dialog to show progress
            if self.restartRequesterDialog and not self.restartRequesterDialog.isEmpty():
                requesterToon = self.cr.getDo(self.pendingRestartRequester)
                requesterDNA = requesterToon.getStyle() if requesterToon else None
                if requesterDNA:
                    message = f"Restart requested!\n\n"
                    message += f"Progress: {numConsented}/{numNeeded} players confirmed."
                    self.restartRequesterDialog['text'] = message
            
            # Update non-requester dialog to show progress
            if self.restartDialog and not self.restartDialog.isEmpty():
                requesterToon = self.cr.getDo(self.pendingRestartRequester)
                requesterName = requesterToon.getName() if requesterToon else "Unknown"
                message = f"{requesterName} has requested to restart the match.\n\n"
                message += f"Progress: {numConsented}/{numNeeded} players confirmed"
                self.restartDialog['text'] = message
    
    def setCancelRestart(self):
        """Receive restart cancellation from server"""
        self.pendingRestartRequester = None
        self.restartConsents.clear()
        
        # Clean up dialogs
        if self.restartDialog:
            self.restartDialog.cleanup()
            self.restartDialog = None
        if self.restartRequesterDialog:
            self.restartRequesterDialog.cleanup()
            self.restartRequesterDialog = None
        
        base.localAvatar.setSystemMessage(0, "Restart request has been cancelled.")
    
    def setCleanupRestartDialogs(self):
        """Clean up restart dialogs without showing cancellation message (used when restart is executed)"""
        self.pendingRestartRequester = None
        self.restartConsents.clear()
        
        # Clean up dialogs without showing message
        if self.restartDialog:
            self.restartDialog.cleanup()
            self.restartDialog = None
        if self.restartRequesterDialog:
            self.restartRequesterDialog.cleanup()
            self.restartRequesterDialog = None
    
    def __handleRestartDialog(self, value):
        """Handle restart dialog button click (for non-requesters)"""
        from direct.gui.DirectGui import DGG
        
        if self.restartDialog:
            self.restartDialog.cleanup()
            self.restartDialog = None
        
        if value == DGG.DIALOG_OK:  # OK/Yes button
            self.sendUpdate('confirmRestart', [])
        else:  # No button - reject the restart
            self.sendUpdate('rejectRestart', [])
    
    def __handleRestartRequesterDialog(self, value):
        """Handle restart requester dialog button click (cancel button)"""
        if self.restartRequesterDialog:
            self.restartRequesterDialog.cleanup()
            self.restartRequesterDialog = None
        
        # Cancel button was clicked - send cancel request to server
        self.sendUpdate('cancelRestartRequest', [])
    
    # ============================================
    # Tournament System Methods
    # ============================================
    
    def __handleTournamentButton(self):
        """Handle tournament button click - toggles tournament panel"""
        if not self.isLocalToonHost():
            return
        
        if self.tournamentPanelVisible:
            self.__hideTournamentPanel()
        else:
            self.__showTournamentPanel()
    
    def __showTournamentPanel(self):
        """Show the tournament panel"""
        if self.tournamentPanel is None:
            self.__createTournamentPanel()
        
        self.tournamentPanel.show()
        self.tournamentPanelVisible = True
    
    def __hideTournamentPanel(self):
        """Hide the tournament panel"""
        if self.tournamentPanel is not None:
            self.tournamentPanel.hide()
        self.tournamentPanelVisible = False
    
    def __createTournamentPanel(self):
        """Create the tournament panel using the same pattern as modifiers panel"""
        
        # Create the main panel frame using proper dialog styling
        self.tournamentPanel = DirectFrame(
            relief=None,
            image=DGG.getDefaultDialogGeom(),
            image_color=ToontownGlobals.GlobalDialogColor,
            image_scale=(1.6, 1, 1.4),
            pos=(0, 0, 0),
            parent=aspect2d,
            sortOrder=DGG.NO_FADE_SORT_INDEX
        )
        
        # Title label
        titleLabel = DirectLabel(
            parent=self.tournamentPanel,
            relief=None,
            text="Manage Tournament Participants",
            text_scale=0.08,
            text_pos=(0, 0.55),
            text_fg=(0.1, 0.1, 0.4, 1),
            text_font=ToontownGlobals.getInterfaceFont()
        )
        
        # Instructions label
        instructionsLabel = DirectLabel(
            parent=self.tournamentPanel,
            relief=None,
            text="Select participants for the tournament (Round Robin: Everyone plays everyone once)",
            text_scale=0.05,
            text_pos=(0, 0.45),
            text_fg=(0.3, 0.3, 0.3, 1),
            text_font=ToontownGlobals.getInterfaceFont()
        )
        
        # Load GUI assets for scroll list
        gui = loader.loadModel('phase_3.5/models/gui/friendslist_gui')
        
        # Participants section (left side - like "Current Modifiers")
        participantsLabel = DirectLabel(
            parent=self.tournamentPanel,
            relief=None,
            text="Participants:",
            text_scale=0.06,
            text_pos=(-0.75, 0.3),
            text_fg=(0.2, 0.2, 0.6, 1),
            text_font=ToontownGlobals.getInterfaceFont(),
            text_align=TextNode.ALeft
        )
        
        # Create scrolled list for participants
        self.tournamentParticipantsList = DirectScrolledList(
            parent=self.tournamentPanel,
            relief=DGG.SUNKEN,
            frameColor=(0.85, 0.95, 1, 1),
            borderWidth=(0.01, 0.01),
            pos=(-0.35, 0, 0.2),
            frameSize=(-0.4, 0.2, -0.24, 0.0),
            numItemsVisible=4,
            forceHeight=0.06,
            itemFrame_frameSize=(-0.38, 0.38, -0.03, 0.03),
            itemFrame_pos=(0, 0, -0.032),
            itemFrame_relief=None,
            # Scroll buttons using proper assets
            incButton_image=(gui.find('**/FndsLst_ScrollUp'),
                           gui.find('**/FndsLst_ScrollDN'),
                           gui.find('**/FndsLst_ScrollUp_Rllvr'),
                           gui.find('**/FndsLst_ScrollUp')),
            incButton_relief=None,
            incButton_scale=(0.3, 0.3, -1.1),
            incButton_pos=(0.15, 0, -0.26),
            incButton_image3_color=Vec4(0.6, 0.6, 0.6, 0.6),
            decButton_image=(gui.find('**/FndsLst_ScrollUp'),
                           gui.find('**/FndsLst_ScrollDN'),
                           gui.find('**/FndsLst_ScrollUp_Rllvr'),
                           gui.find('**/FndsLst_ScrollUp')),
            decButton_relief=None,
            decButton_scale=(0.3, 0.3, 1.1),
            decButton_pos=(0.15, 0, 0.03),
            decButton_image3_color=Vec4(0.6, 0.6, 0.6, 0.6)
        )
        
        # Spectators section (right side - like "Available Modifiers")
        spectatorsLabel = DirectLabel(
            parent=self.tournamentPanel,
            relief=None,
            text="Spectators:",
            text_scale=0.06,
            text_pos=(0.1, 0.3),
            text_fg=(0.2, 0.2, 0.6, 1),
            text_font=ToontownGlobals.getInterfaceFont(),
            text_align=TextNode.ALeft
        )
        
        # Create scrolled list for spectators
        self.tournamentSpectatorsList = DirectScrolledList(
            parent=self.tournamentPanel,
            relief=DGG.SUNKEN,
            frameColor=(0.95, 0.85, 1, 1),
            borderWidth=(0.01, 0.01),
            pos=(0.5, 0, 0.2),
            frameSize=(-0.4, 0.2, -0.24, 0.0),
            numItemsVisible=4,
            forceHeight=0.06,
            itemFrame_frameSize=(-0.38, 0.38, -0.03, 0.03),
            itemFrame_pos=(0, 0, -0.032),
            itemFrame_relief=None,
            # Scroll buttons using proper assets
            incButton_image=(gui.find('**/FndsLst_ScrollUp'),
                           gui.find('**/FndsLst_ScrollDN'),
                           gui.find('**/FndsLst_ScrollUp_Rllvr'),
                           gui.find('**/FndsLst_ScrollUp')),
            incButton_relief=None,
            incButton_scale=(0.3, 0.3, -1.1),
            incButton_pos=(0.15, 0, -0.26),
            incButton_image3_color=Vec4(0.6, 0.6, 0.6, 0.6),
            decButton_image=(gui.find('**/FndsLst_ScrollUp'),
                           gui.find('**/FndsLst_ScrollDN'),
                           gui.find('**/FndsLst_ScrollUp_Rllvr'),
                           gui.find('**/FndsLst_ScrollUp')),
            decButton_relief=None,
            decButton_scale=(0.3, 0.3, 1.1),
            decButton_pos=(0.15, 0, 0.03),
            decButton_image3_color=Vec4(0.6, 0.6, 0.6, 0.6)
        )
        
        # Load button assets
        buttons = loader.loadModel('phase_3/models/gui/dialog_box_buttons_gui')
        closeButtonImage = (buttons.find('**/CloseBtn_UP'), 
                          buttons.find('**/CloseBtn_DN'), 
                          buttons.find('**/CloseBtn_Rllvr'))
        
        # Load quit button for Start Tournament button (same as other buttons)
        btnGeom = loader.loadModel('phase_3/models/gui/quit_button')
        
        # Start Tournament button (centered, no close button - use Tournament button to close)
        startButton = DirectButton(
            parent=self.tournamentPanel,
            relief=None,
            geom=(btnGeom.find('**/QuitBtn_UP'),
                  btnGeom.find('**/QuitBtn_DN'),
                  btnGeom.find('**/QuitBtn_RLVR')),
            geom_scale=(0.9, 1, 1),
            text="Start Tournament",
            text_scale=0.055,
            text_pos=(0, -0.02),
            pos=(0, 0, -0.55),
            command=self.__startRoundRobinTournament
        )
        
        # Clean up loaded models
        gui.removeNode()
        buttons.removeNode()
        btnGeom.removeNode()
        
        # Initialize participant list with all non-spectators
        self.tournamentParticipantsList_selected = list(self.getParticipantIdsNotSpectating())
        
        # Populate the lists with participants and spectators
        self.__updateTournamentLists()
        
        # Initially hide the panel
        self.tournamentPanel.hide()
    
    def __updateTournamentLists(self):
        """Update the tournament lists with participants and spectators"""
        if self.tournamentParticipantsList is None or self.tournamentSpectatorsList is None:
            return
            
        # Clear existing items
        self.tournamentParticipantsList.removeAllItems()
        self.tournamentSpectatorsList.removeAllItems()
        
        # Load button assets for add/remove buttons
        gui = loader.loadModel('phase_3.5/models/gui/friendslist_gui')
        addButtonImage = (gui.find('**/Horiz_Arrow_UP'),
                         gui.find('**/Horiz_Arrow_DN'),
                         gui.find('**/Horiz_Arrow_Rllvr'),
                         gui.find('**/Horiz_Arrow_UP'))
        removeButtonImage = (gui.find('**/Horiz_Arrow_UP'),
                           gui.find('**/Horiz_Arrow_DN'),
                           gui.find('**/Horiz_Arrow_Rllvr'),
                           gui.find('**/Horiz_Arrow_UP'))
        
        # Get all non-spectator avIds
        allAvIds = [avId for avId in self.avIdList if avId not in self.getSpectators()]
        
        # Populate participants list (those selected for tournament)
        for avId in allAvIds:
            if avId in self.tournamentParticipantsList_selected:
                toon = self.cr.getDo(avId)
                if not toon:
                    continue
                
                itemFrame = DirectFrame(
                    relief=None,
                    frameSize=(-0.38, 0.38, -0.03, 0.03)
                )
                
                # Toon name label
                nameLabel = DirectLabel(
                    parent=itemFrame,
                    relief=None,
                    text=toon.getName(),
                    text_scale=0.025,
                    text_pos=(-0.35, 0, 0),
                    text_fg=(0.1, 0.1, 0.1, 1),
                    text_font=ToontownGlobals.getInterfaceFont(),
                    text_align=TextNode.ALeft
                )
                
                # Remove button (move to spectators)
                removeButton = DirectButton(
                    parent=itemFrame,
                    relief=None,
                    image=removeButtonImage,
                    image_scale=(0.3, 1, 0.3),
                    image_hpr=(0, 0, 180),  # Rotate to make it a remove arrow
                    pos=(0.17, 0, 0),
                    command=self.__removeTournamentParticipant,
                    extraArgs=[avId]
                )
                
                self.tournamentParticipantsList.addItem(itemFrame)
        
        # Populate spectators list (those not selected for tournament)
        for avId in allAvIds:
            if avId not in self.tournamentParticipantsList_selected:
                toon = self.cr.getDo(avId)
                if not toon:
                    continue
                
                itemFrame = DirectFrame(
                    relief=None,
                    frameSize=(-0.38, 0.38, -0.03, 0.03)
                )
                
                # Toon name label
                nameLabel = DirectLabel(
                    parent=itemFrame,
                    relief=None,
                    text=toon.getName(),
                    text_scale=0.025,
                    text_pos=(-0.35, 0, 0),
                    text_fg=(0.1, 0.1, 0.1, 1),
                    text_font=ToontownGlobals.getInterfaceFont(),
                    text_align=TextNode.ALeft
                )
                
                # Add button (move to participants)
                addButton = DirectButton(
                    parent=itemFrame,
                    relief=None,
                    image=addButtonImage,
                    image_scale=(0.3, 1, 0.3),
                    pos=(0.17, 0, 0),
                    command=self.__addTournamentParticipant,
                    extraArgs=[avId]
                )
                
                self.tournamentSpectatorsList.addItem(itemFrame)
        
        # Clean up loaded model
        gui.removeNode()
    
    def __addTournamentParticipant(self, avId):
        """Add a participant to the tournament (move from spectators to participants)"""
        if avId not in self.tournamentParticipantsList_selected:
            self.tournamentParticipantsList_selected.append(avId)
            self.__updateTournamentLists()
    
    def __removeTournamentParticipant(self, avId):
        """Remove a participant from the tournament (move from participants to spectators)"""
        if avId in self.tournamentParticipantsList_selected:
            self.tournamentParticipantsList_selected.remove(avId)
            self.__updateTournamentLists()
    
    def __startRoundRobinTournament(self):
        """Start a round robin tournament"""
        # Validate we have enough participants
        if len(self.tournamentParticipantsList_selected) < 2:
            base.localAvatar.setSystemMessage(0, "Need at least 2 participants for tournament!")
            return
        
        # Hide the panel
        self.__hideTournamentPanel()
        
        # First, set non-tournament participants as spectators
        allParticipants = self.getParticipantIds()
        nonTournamentParticipants = [avId for avId in allParticipants if avId not in self.tournamentParticipantsList_selected]
        
        if nonTournamentParticipants:
            # Temporarily make them spectators for the tournament
            currentSpectators = list(self.getSpectators())
            for avId in nonTournamentParticipants:
                if avId not in currentSpectators:
                    spotIndex = self.avIdList.index(avId)
                    self.sendUpdate('handleSpotStatusChanged', [spotIndex, False])
        
        # Send request to server to start tournament with selected participants
        self.sendUpdate('startTournament', [TournamentType.ROUND_ROBIN, TournamentStage.ONE_STAGE, TournamentType.NONE, self.tournamentParticipantsList_selected])
        
        # Show confirmation message
        numMatches = (len(self.tournamentParticipantsList_selected) * (len(self.tournamentParticipantsList_selected) - 1)) // 2
        base.localAvatar.setSystemMessage(0, f"Starting Round Robin tournament with {len(self.tournamentParticipantsList_selected)} players ({numMatches} matches)...")
    
    
    def setTournamentActive(self, tournamentType):
        """
        Receive tournament activation status from server.
        
        Args:
            tournamentType: TournamentType value (NONE if inactive)
        """
        self.tournamentActive = (tournamentType != TournamentType.NONE)
        self.tournamentType = tournamentType
        
        if self.tournamentActive:
            self.notify.info(f"Tournament activated: type={tournamentType}")
            # Show tournament progress label
            self.__showTournamentProgress()
            self.tournamentActive = True
            # Enable keybind to toggle scoreboard view
            self.accept('f2', self.__toggleScoreboardView)
        else:
            self.notify.info("Tournament deactivated")
            # Hide tournament progress label
            self.__hideTournamentProgress()
            self.tournamentActive = False
            self.ignore('f2')
    
    def setTournamentProgress(self, currentStage, totalStages, currentMatch, totalMatches):
        """
        Receive tournament progress update from server.
        
        Args:
            currentStage: Current stage number (1-based)
            totalStages: Total number of stages
            currentMatch: Current match number (1-based)
            totalMatches: Total number of matches in current stage
        """
        self.notify.debug(f"Tournament progress: Stage {currentStage}/{totalStages}, Match {currentMatch}/{totalMatches}")
        
        # Update progress display
        if self.tournamentProgressLabel:
            progressText = f"Tournament: Match {currentMatch}/{totalMatches}"
            if totalStages > 1:
                progressText += f" (Stage {currentStage}/{totalStages})"
            self.tournamentProgressLabel['text'] = progressText
    
    def setTournamentStandings(self, participantIds, matchWins, totalPoints, currentMatchPlayers):
        """
        Receive tournament standings update from server.
        
        Args:
            participantIds: List of avatar IDs in tournament
            matchWins: List of match wins for each participant
            totalPoints: List of total points for each participant
            currentMatchPlayers: List of avatar IDs currently playing
        """
        # Build standings dict
        standings = {}
        for i, avId in enumerate(participantIds):
            standings[avId] = {
                'matchWins': matchWins[i],
                'totalPoints': totalPoints[i],
                'matchLosses': 0  # Can calculate if needed
            }
        
        # Store tournament participants for scoreboard management
        self.tournamentParticipants = list(standings.keys())
        self.tournamentCurrentMatchPlayers = currentMatchPlayers
        # Store tournament standings for scoreboard updates
        self.tournamentStandings = standings  # {avId: {'matchWins': int, 'totalPoints': int}}
        
        # Update wins when standings are received (when match ends)
        # But only update wins, not the scoreboard display (to preserve spectating state)
        if self.tournamentActive and hasattr(self, 'scoreboard') and self.scoreboard:
            # Update wins for all players currently on scoreboard
            for avId, row in self.scoreboard.rows.items():
                if avId in self.tournamentStandings:
                    tournamentWins = self.tournamentStandings[avId]['matchWins']
                    row.roundWins = tournamentWins
                    row.updateRoundWins(tournamentWins)
    
    def declareTournamentWinner(self, winnerId):
        """
        Receive tournament winner announcement from server.
        
        Args:
            winnerId: Avatar ID of tournament winner
        """
        winner = self.cr.getDo(winnerId)
        winnerName = winner.getName() if winner else "Unknown"
        
        self.notify.info(f"Tournament winner: {winnerName} ({winnerId})")
        
        # Show big announcement
        self.__displayOverlayText(f"TOURNAMENT WINNER:\n{winnerName}!", (1, 0.8, 0, 1), scale=0.15)
        
        # Hide after a few seconds
        taskMgr.doMethodLater(5, lambda task: self.__hideOverlayText(), 
                              self.uniqueName('hide-tournament-winner'))
    
    def requestMatchReady(self, matchPlayers, player1, player2):
        """
        Server requests ready-up for tournament match.
        Shows matchup display and ready button.
        
        Args:
            matchPlayers: List of avatar IDs who need to ready up
            player1: Avatar ID of first player in match
            player2: Avatar ID of second player in match
        """
        self.waitingForMatchReady = True
        self.matchPlayers = matchPlayers
        
        # Enter prepare state if we're not already there
        # This ensures we're in prepare state when showing the ready UI
        currentState = self.gameFSM.getCurrentState()
        if currentState is None or currentState.getName() != 'prepare':
            # Request prepare state - this will call enterPrepare which will check waitingForMatchReady
            self.gameFSM.request('prepare')
            # Show UI after a tiny delay to ensure enterPrepare has run
            taskMgr.doMethodLater(0.1, lambda task: self.__showMatchReadyUI(player1, player2),
                                 self.uniqueName('show-match-ready-ui'))
        else:
            # We're already in prepare, show UI immediately
            self.__showMatchReadyUI(player1, player2)
    
    def startMatchCountdown(self):
        """Server signals all players ready, start countdown"""
        self.waitingForMatchReady = False
        self.__hideMatchReadyUI()
        # Now start the normal countdown
        if not hasattr(self, 'introductionMovie') or self.introductionMovie is None:
            self.introductionMovie = self.__generatePrepareInterval()
            self.introductionMovie.start()
    
    def setMatchReady(self):
        """Client calls this when player clicks ready button"""
        if not self.waitingForMatchReady:
            return
        self.sendUpdate('setMatchReady', [])
        
        # Update button to show ready state
        if self.matchReadyButton:
            self.matchReadyButton['text'] = 'Ready!'
            self.matchReadyButton['state'] = 'disabled'
        
        # Update status label for local player immediately
        localAvId = base.localAvatar.getDoId()
        if localAvId in self.matchReadyStatusLabels:
            statusLabel = self.matchReadyStatusLabels[localAvId]
            statusLabel['text'] = 'Ready!'
            statusLabel['text_fg'] = (0.2, 0.7, 0.2, 1)
    
    def setPlayerReadyStatus(self, avId, isReady):
        """
        Update ready status for a player (called when any player readies up).
        
        Args:
            avId: Avatar ID of the player
            isReady: True if ready, False if not ready
        """
        if avId in self.matchReadyStatusLabels:
            statusLabel = self.matchReadyStatusLabels[avId]
            if isReady:
                statusLabel['text'] = 'Ready!'
                statusLabel['text_fg'] = (0.2, 0.7, 0.2, 1)
            else:
                statusLabel['text'] = 'Waiting...'
                statusLabel['text_fg'] = (0.6, 0.6, 0.6, 1)
    
    def __positionCameraForMatchReady(self):
        """Position camera during match ready break phase (same as prepare phase)"""
        players = self.getParticipantsNotSpectating()
        if len(players) <= 0:
            return
        
        # Use same camera positioning as prepare phase
        toon = base.localAvatar if not self.localToonSpectating() else self.getParticipantsNotSpectating()[0]
        targetCameraPos = render.getRelativePoint(toon, Vec3(0, -10, toon.getHeight()))
        startCameraHpr = Point3(reduceAngle(camera.getH()), camera.getP(), camera.getR())
        
        # Smoothly move camera to position (same duration as prepare phase)
        cameraInterval = LerpPosHprInterval(
            camera, 
            CraneGameGlobals.PREPARE_DELAY / 2.5, 
            Point3(*targetCameraPos), 
            Point3(reduceAngle(toon.getH()), 0, 0), 
            startPos=camera.getPos(), 
            startHpr=startCameraHpr, 
            blendType='easeInOut'
        )
        cameraInterval.start()
    
    def __showMatchReadyUI(self, player1, player2):
        """
        Show enhanced matchup display with toon heads, animations, and ready status.
        Styled to match crane game UI with improved visual hierarchy.
        """
        from toontown.toon import ToonHead
        
        # Hide any existing UI
        self.__hideMatchReadyUI()
        
        # Get button geometry (same as other crane game buttons)
        btnGeom = loader.loadModel('phase_3/models/gui/quit_button')
        
        # Get player toons and names
        p1Toon = self.cr.getDo(player1) if player1 else None
        p2Toon = self.cr.getDo(player2) if player2 else None
        p1Name = p1Toon.getName() if p1Toon else "Player 1"
        p2Name = p2Toon.getName() if p2Toon else "Player 2"
        
        # Get tournament progress info if available
        matchInfo = ""
        if hasattr(self, 'tournamentProgress') and self.tournamentProgress:
            currentMatch = self.tournamentProgress.get('currentMatch', 0)
            totalMatches = self.tournamentProgress.get('totalMatches', 0)
            if totalMatches > 0:
                matchInfo = f"Match {currentMatch}/{totalMatches}"
        
        # Create larger frame for side-by-side layout
        self.matchReadyUI = DirectFrame(
            relief=None,
            image=DGG.getDefaultDialogGeom(),
            image_color=ToontownGlobals.GlobalDialogColor,
            image_scale=(2.0, 1, 0.85),
            pos=(0, 0, 0),
            parent=aspect2d
        )
        
        # Start hidden for animation
        self.matchReadyUI.setScale(0.01)
        self.matchReadyUI.setColorScale(1, 1, 1, 0)
        
        # Match title with tournament info
        titleText = "Next Match"
        if matchInfo:
            titleText = f"{titleText} - {matchInfo}"
        matchLabel = DirectLabel(
            text=titleText,
            text_scale=0.09,
            text_fg=(0.1, 0.1, 0.4, 1),
            text_font=ToontownGlobals.getInterfaceFont(),
            relief=None,
            pos=(0, 0, 0.32),
            parent=self.matchReadyUI
        )
        
        localAvId = base.localAvatar.getDoId()
        
        # Player 1 section (left side) - closer to center
        p1Frame = DirectFrame(
            relief=None,
            frameSize=(-0.6, 0.0, -0.3, 0.2),
            pos=(-0.35, 0, 0.05),
            parent=self.matchReadyUI
        )
        
        # Player 1 toon head - larger and correct orientation
        if p1Toon and hasattr(p1Toon, 'style'):
            p1HeadNode = p1Frame.attachNewNode('p1Head')
            p1HeadNode.setPosHprScale(-0.3, 0, 0, 0, 0, 0, 1.2, 1.2, 1.2)
            p1HeadModel = ToonHead.ToonHead()
            p1HeadModel.setupHead(p1Toon.style, forGui=1)
            p1HeadModel.fitAndCenterHead(0.175, forGui=1)
            p1HeadModel.reparentTo(p1HeadNode)
            p1HeadModel.startBlink()
            p1HeadModel.startLookAround()
            self.matchReadyPlayerHeads[player1] = p1HeadModel
        
        # Player 1 name
        p1Label = DirectLabel(
            text=p1Name,
            text_scale=0.07,
            text_fg=(0, 0, 0, 1),
            text_font=ToontownGlobals.getInterfaceFont(),
            relief=None,
            pos=(-0.3, 0, -0.15),
            parent=p1Frame,
            text_align=TextNode.ACenter
        )
        
        # Player 1 ready status - start as "Waiting..." for everyone
        p1StatusLabel = DirectLabel(
            text="Waiting...",
            text_scale=0.055,
            text_fg=(0.6, 0.6, 0.6, 1),
            text_font=ToontownGlobals.getInterfaceFont(),
            relief=None,
            pos=(-0.3, 0, -0.22),
            parent=p1Frame,
            text_align=TextNode.ACenter
        )
        self.matchReadyStatusLabels[player1] = p1StatusLabel
        
        # VS label in center - closer to players
        vsLabel = DirectLabel(
            text="VS",
            text_scale=0.08,
            text_fg=(0.4, 0.4, 0.4, 1),
            text_font=ToontownGlobals.getCompetitionFont(),
            relief=None,
            pos=(0, 0, 0.05),
            parent=self.matchReadyUI
        )
        
        # Player 2 section (right side) - closer to center
        p2Frame = DirectFrame(
            relief=None,
            frameSize=(0.0, 0.6, -0.3, 0.2),
            pos=(0.35, 0, 0.05),
            parent=self.matchReadyUI
        )
        
        # Player 2 toon head - larger and correct orientation
        if p2Toon and hasattr(p2Toon, 'style'):
            p2HeadNode = p2Frame.attachNewNode('p2Head')
            p2HeadNode.setPosHprScale(0.3, 0, 0, 0, 0, 0, 1.2, 1.2, 1.2)
            p2HeadModel = ToonHead.ToonHead()
            p2HeadModel.setupHead(p2Toon.style, forGui=1)
            p2HeadModel.fitAndCenterHead(0.175, forGui=1)
            p2HeadModel.reparentTo(p2HeadNode)
            p2HeadModel.startBlink()
            p2HeadModel.startLookAround()
            self.matchReadyPlayerHeads[player2] = p2HeadModel
        
        # Player 2 name
        p2Label = DirectLabel(
            text=p2Name,
            text_scale=0.07,
            text_fg=(0, 0, 0, 1),
            text_font=ToontownGlobals.getInterfaceFont(),
            relief=None,
            pos=(0.3, 0, -0.15),
            parent=p2Frame,
            text_align=TextNode.ACenter
        )
        
        # Player 2 ready status - start as "Waiting..." for everyone
        p2StatusLabel = DirectLabel(
            text="Waiting...",
            text_scale=0.055,
            text_fg=(0.6, 0.6, 0.6, 1),
            text_font=ToontownGlobals.getInterfaceFont(),
            relief=None,
            pos=(0.3, 0, -0.22),
            parent=p2Frame,
            text_align=TextNode.ACenter
        )
        self.matchReadyStatusLabels[player2] = p2StatusLabel
        
        # Ready button (only show if local player is in match) - styled like other buttons
        if localAvId in self.matchPlayers:
            self.matchReadyButton = DirectButton(
                relief=None,
                text="Ready Up",
                text_scale=0.06,
                text_pos=(0, -0.02),
                geom=(btnGeom.find('**/QuitBtn_UP'),
                      btnGeom.find('**/QuitBtn_DN'),
                      btnGeom.find('**/QuitBtn_RLVR')),
                geom_scale=(0.9, 1, 1),
                pos=(0, 0, -0.35),
                parent=self.matchReadyUI,
                command=self.setMatchReady
            )
        else:
            # Spectator - show waiting message
            waitLabel = DirectLabel(
                text="Waiting for players to ready up...",
                text_scale=0.055,
                text_fg=(0.5, 0.5, 0.5, 1),
                text_font=ToontownGlobals.getInterfaceFont(),
                relief=None,
                pos=(0, 0, -0.35),
                parent=self.matchReadyUI
            )
        
        # Animate entrance: scale and fade in
        self.matchReadyAnimTrack = Sequence(
            Parallel(
                LerpScaleInterval(self.matchReadyUI, 0.25, 1.05, 0.01, blendType='easeOut'),
                LerpColorScaleInterval(self.matchReadyUI, 0.25, Vec4(1, 1, 1, 1), Vec4(1, 1, 1, 0), blendType='easeOut')
            ),
            LerpScaleInterval(self.matchReadyUI, 0.1, 1.0, 1.05, blendType='easeIn')
        )
        self.matchReadyAnimTrack.start()
        
        self.matchReadyUI.show()
    
    def __hideMatchReadyUI(self):
        """Hide match ready UI and cleanup resources"""
        # Stop any running animations
        if self.matchReadyAnimTrack:
            self.matchReadyAnimTrack.finish()
            self.matchReadyAnimTrack = None
        
        # Clean up toon heads
        for avId, headModel in list(self.matchReadyPlayerHeads.items()):
            if headModel:
                headModel.stopBlink()
                headModel.stopLookAroundNow()
                headModel.delete()
        self.matchReadyPlayerHeads.clear()
        
        # Clean up status labels
        self.matchReadyStatusLabels.clear()
        
        # Destroy UI
        if self.matchReadyUI:
            self.matchReadyUI.destroy()
            self.matchReadyUI = None
        if self.matchReadyButton:
            self.matchReadyButton = None
    
    def __checkIfShouldWaitForReady(self):
        """Check if we should wait for ready-up or start countdown"""
        if self.waitingForMatchReady:
            # We're waiting, don't start countdown
            return
        # Not waiting, start countdown now
        if not hasattr(self, 'introductionMovie') or self.introductionMovie is None:
            self.introductionMovie = self.__generatePrepareInterval()
            self.introductionMovie.start()
        self.boss.prepareBossForBattle()
        # Clean up all status effects when starting a new round
        if hasattr(self, 'statusEffectSystem') and self.statusEffectSystem:
            self.statusEffectSystem.cleanup()
        # Make absolutely sure all indicators are cleaned up
        self.removeStatusIndicators()
    
    def __showTournamentProgress(self):
        """Show tournament progress label"""
        if self.tournamentProgressLabel is None:
            self.tournamentProgressLabel = DirectLabel(
                text="Tournament: Match 1/1",
                text_scale=0.05,
                text_fg=(1, 1, 1, 1),
                text_shadow=(0, 0, 0, 1),
                text_font=ToontownGlobals.getInterfaceFont(),
                relief=None,
                pos=(-1.35, 0, 0.92),  # Top left corner
                parent=aspect2d
            )
        self.tournamentProgressLabel.show()
    
    def __hideTournamentProgress(self):
        """Hide tournament progress label"""
        if self.tournamentProgressLabel:
            self.tournamentProgressLabel.hide()
    
    def __toggleScoreboardView(self):
        """Toggle between showing only active players or all tournament participants"""
        if not self.tournamentActive:
            return
        
        self.scoreboardShowAllParticipants = not self.scoreboardShowAllParticipants
        self.__updateTournamentScoreboard()
        

    
    def __updateTournamentScoreboard(self):
        """Update scoreboard to show appropriate players during tournament"""
        if not hasattr(self, 'scoreboard') or not self.scoreboard:
            return
        
        # Store current scores and data before clearing (for current match points)
        savedScores = {}
        savedData = {}
        if hasattr(self.scoreboard, 'rows'):
            for avId, row in self.scoreboard.rows.items():
                savedScores[avId] = row.points  # Current match points
                savedData[avId] = {
                    'damage': row.damage,
                    'stuns': row.stuns,
                    'stomps': row.stomps
                }
        
        # Save spectating state before clearing
        spectatedAvId = self.scoreboard.saveSpectatingState() if hasattr(self.scoreboard, 'saveSpectatingState') else None
        wasSpectating = spectatedAvId is not None
        
        # Clear current scoreboard - preserve spectating if we were spectating
        self.scoreboard.clearToons(preserveSpectating=wasSpectating)
        
        # Determine which players to show and in what order
        # IMPORTANT: Only show tournament participants
        # Tournament participants not in current match are spectators, but we can still show them on scoreboard
        # The scoreboard is just a display - it doesn't affect spectator status
        if self.scoreboardShowAllParticipants:
            # Show all tournament participants, active players first
            # Active = in current match (playing)
            # Inactive = tournament participant but not in current match (spectating this match)
            activePlayers = [avId for avId in self.tournamentParticipants 
                           if avId in self.tournamentCurrentMatchPlayers]
            inactivePlayers = [avId for avId in self.tournamentParticipants 
                             if avId not in self.tournamentCurrentMatchPlayers]
            playersToShow = activePlayers + inactivePlayers  # Active at top, inactive at bottom
        else:
            # Show only current match players (who are tournament participants)
            playersToShow = [avId for avId in self.tournamentCurrentMatchPlayers 
                           if avId in self.tournamentParticipants]
        
        # Add players in order
        # Only add tournament participants - don't add non-tournament participants (they should remain spectators)
        for avId in playersToShow:
            # Only add if they're tournament participants
            if avId not in self.tournamentParticipants:
                continue
                
            # Add to scoreboard - this is just for display, doesn't affect spectator status
            self.scoreboard.addToon(avId)
            row = self.scoreboard.rows.get(avId)
            if row:
                # Points: Always show CURRENT MATCH points, not tournament total
                if avId in savedScores:
                    # Restore current match points
                    row.points = savedScores[avId]
                    row.points_text.setText(str(savedScores[avId]))
                else:
                    # No saved score yet (new match), start at 0
                    row.points = 0
                    row.points_text.setText("0")
                
                # Restore other stats
                if avId in savedData:
                    row.damage = savedData[avId]['damage']
                    row.stuns = savedData[avId]['stuns']
                    row.stomps = savedData[avId]['stomps']
                
                # Wins: Always show TOURNAMENT MATCH WINS (total across all matches)
                if hasattr(self, 'tournamentStandings') and avId in self.tournamentStandings:
                    tournamentWins = self.tournamentStandings[avId]['matchWins']
                    row.roundWins = tournamentWins
                    row.updateRoundWins(tournamentWins)
                    row.round_wins_text.show()  # Make sure wins column is visible
                else:
                    # If no tournament standings yet, show 0 wins
                    row.roundWins = 0
                    row.updateRoundWins(0)
                    row.round_wins_text.show()
                
                # Grey out non-active players
                if self.scoreboardShowAllParticipants and avId not in self.tournamentCurrentMatchPlayers:
                    row.frame.setColorScale(0.6, 0.6, 0.6, 0.7)
                else:
                    row.frame.setColorScale(1, 1, 1, 1)  # Fully visible
        
        # Update scoreboard sorting - sort by current match points (for active players) or tournament wins (for inactive)
        rows = list(self.scoreboard.rows.values())
        if rows:
            def sortKey(row):
                avId = row.avId
                isActive = avId in self.tournamentCurrentMatchPlayers
                
                if isActive:
                    # Active players: sort by current match points (descending)
                    return (-row.points, 0)
                else:
                    # Inactive players: sort by tournament wins, then total points (descending)
                    if hasattr(self, 'tournamentStandings') and avId in self.tournamentStandings:
                        wins = self.tournamentStandings[avId]['matchWins']
                        totalPoints = self.tournamentStandings[avId]['totalPoints']
                        return (1, -wins, -totalPoints)  # 1 to put inactive after active
                    return (1, 0, 0)
            
            rows.sort(key=sortKey)
            # Update positions
            for i, r in enumerate(rows):
                r.place = i
                r.updatePosition()
        
        # Restore spectating state if we were spectating before AND we're still a spectator
        # This ensures that pressing F2 doesn't break spectating for spectators
        if wasSpectating and self.localToonSpectating():
            # First, enable spectating on all the new rows so they can be clicked (but don't auto-spectate first row)
            self.scoreboard.enableSpectating(autoSpectateFirst=False)
            # Then restore spectating to the specific player
            if hasattr(self.scoreboard, 'restoreSpectatingState'):
                self.scoreboard.restoreSpectatingState(spectatedAvId, autoSpectate=False)
    

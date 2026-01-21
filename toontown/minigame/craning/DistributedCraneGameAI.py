import math
import random

from direct.fsm import ClassicFSM
from direct.fsm import State
from otp.otpbase.PythonUtil import clamp
from direct.task.TaskManagerGlobal import taskMgr
from panda3d.core import CollisionInvSphere, CollisionNode, CollisionSphere, CollisionTube, NodePath, Vec3, Point3
from toontown.minigame.craning.boss.CashbotBossComboTracker import CashbotBossComboTracker
from toontown.minigame.craning.CraneGameGlobals import ScoreReason
from toontown.minigame.craning.objects.DistributedCashbotCraneAI import DistributedCashbotCraneAI
from toontown.minigame.craning.objects.DistributedCashbotHeavyCraneAI import DistributedCashbotHeavyCraneAI
from toontown.minigame.craning.objects.DistributedCashbotSafeAI import DistributedCashbotSafeAI
from toontown.minigame.craning.objects.DistributedCashbotSideCraneAI import DistributedCashbotSideCraneAI
from toontown.minigame.craning.objects.DistributedCashbotTreasureAI import DistributedCashbotTreasureAI
from toontown.minigame.craning.objects.DistributedCashbotBoomBarrowAI import DistributedCashbotBoomBarrowAI
from toontown.minigame.craning.objects.DistributedCashbotFloatingPlatformAI import DistributedCashbotFloatingPlatformAI
from toontown.matchmaking.skill_profile_keys import SkillProfileKey
from toontown.minigame.DistributedMinigameAI import DistributedMinigameAI
from toontown.minigame.craning import CraneGameGlobals
from toontown.minigame.craning.objects.DistributedCashbotGoonAI import DistributedCashbotGoonAI
from toontown.minigame.craning.boss.DistributedCashbotBossAI import DistributedCashbotBossAI
from toontown.toon.DistributedToonAI import DistributedToonAI
from toontown.toonbase import ToontownGlobals
from toontown.minigame.utils.statuseffects.DistributedStatusEffectSystemAI import DistributedStatusEffectSystemAI
from toontown.minigame.utils.statuseffects.StatusEffectGlobals import StatusEffect, SAFE_ALLOWED_EFFECTS


class DistributedCraneGameAI(DistributedMinigameAI):
    DESPERATION_MODE_ACTIVATE_THRESHOLD = 1800

    # If time limit is enabled, how many seconds should be remaining to activate when an overtake happens?
    OVERTIME_OVERTAKE_ACTIVATION_THRESHOLD = 15

    def __init__(self, air, minigameId):
        DistributedMinigameAI.__init__(self, air, minigameId)
        air.memoryDebugger.track_weak(self, "CraneGame")
        self.setProfileSkillKey(None)  # By default, no ranked mode.

        self.ruleset = CraneGameGlobals.CraneGameRuleset()
        self.modifiers = []  # A list of CFORulesetModifierBase instances
        self.goonCache = ("Recent emerging side", 0) # Cache for goon spawn bad luck protection
        self.cranes = []
        self.safes = []
        self.goons = []
        self.treasures = {}
        self.grabbingTreasures = {}
        self.boomBarrows = []  # List to hold boom barrow objects
        self.floatingPlatforms = []  # List to hold floating platform objects
        self.recycledTreasures = []
        self.boss = None

        # We need a scene to do the collision detection in.
        self.scene = NodePath('scene')

        self.toonsWon = False

        self.rollModsOnStart = False
        self.numModsWanted = 5
        self.desiredModifiers = []  # Modifiers added manually via commands or by the host during game settings. Will always ensure these are added every crane round.
        self.defaultModifiersInitialized = False  # Track if we've initialized default modifiers

        self.customSpawnPositions = {}
        self.customSpawnOrderSet = False  # Track if spawn order has been manually set by leader
        self.bestOfValue = 1  # Default to Best of 1
        self.currentRound = 1
        self.roundWins = {}  # Maps avId -> number of rounds won
        self.originalSpawnOrder = []  # Store original spawn order for rotation
        self.goonMinScale = 0.8
        self.goonMaxScale = 2.4

        self.comboTrackers = {}

        self.gameFSM = ClassicFSM.ClassicFSM('DistributedMinigameTemplateAI',
                               [
                                State.State('inactive',
                                            self.enterInactive,
                                            self.exitInactive,
                                            ['prepare']),
                                State.State('prepare',
                                            self.enterPrepare,
                                            self.exitPrepare,
                                            ['play']),
                                State.State('play',
                                            self.enterPlay,
                                            self.exitPlay,
                                            ['victory', 'cleanup']),
                                State.State('victory',
                                            self.enterVictory,
                                            self.exitVictory,
                                            ['cleanup']),
                                State.State('cleanup',
                                            self.enterCleanup,
                                            self.exitCleanup,
                                            ['inactive']),
                                ],
                               # Initial State
                               'inactive',
                               # Final State
                               'inactive',
                               )

        # Add our game ClassicFSM to the framework ClassicFSM
        self.addChildGameFSM(self.gameFSM)
        
        # Track safe effect tasks
        self.safeEffectTasks = set()

        # State tracking related to the overtime mechanic.
        self.overtimeWillHappen = False  # Setting this to True will cause the CFO to enter "overtime" mode when time runs out.
        self.currentlyInOvertime = False  # Only true when the game is currently in overtime.
        self.currentWinners: list[int] = []  # Keeps track of who's in the lead so we know when to trigger overtime.

        self.statusEffectSystem: DistributedStatusEffectSystemAI | None = None
        self.droneCooldowns = {}  # Track drone deployment cooldowns per player per slot {avId: {slotIndex: nextAvailableTime}}
        self.selectedDroneTypes = {}  # Track selected drone types per player {avId: [slot0Type, slot1Type, slot2Type]}

        # Memory leak prevention - track event listeners and task names
        self._deathListenerEvents = []
        self._allTaskNames = set()
        
        # Forfeit consent system
        self.pendingForfeitRequest = None  # avId of player who requested forfeit, or None if no pending request
        self.forfeitConsents = set()  # Set of avIds who have consented to forfeit
        self.pendingRestartRequest = None  # avId of player who requested restart, or None if no pending request
        self.restartConsents = set()  # Set of avIds who have consented to restart

    def isRanked(self) -> bool:
        # Use base class check (skillProfileKey is not None) AND player count check
        # This ensures we don't try to adjust ratings if skillProfileKey is None
        return super().isRanked()

    def generate(self):
        self.notify.debug("generate")
        self.__makeBoss()
        DistributedMinigameAI.generate(self)

    def announceGenerate(self):
        self.notify.debug("announceGenerate")
        self.__updateSkillProfile()

    def __makeBoss(self):
        self.__deleteBoss()

        self.boss = DistributedCashbotBossAI(self.air, self)
        self.boss.generateWithRequired(self.zoneId)
        self.statusEffectSystem = DistributedStatusEffectSystemAI(self, self.air,
                                        StatusEffect.BURNED,
                                        StatusEffect.DRENCHED,
                                        StatusEffect.WINDED,
                                        StatusEffect.GROUNDED,
                                        StatusEffect.EXPLODE,
                                        StatusEffect.FROZEN,
                                        StatusEffect.SHATTERED
                                        )
        self.statusEffectSystem.generateWithRequired(self.zoneId)
        self.d_setBossCogId()
        self.d_setStatusEffectSystemId()
        self.boss.reparentTo(self.scene)

        # And some solids to keep the goons constrained to our room.
        cn = CollisionNode('walls')
        #cs = CollisionSphere(0, 0, 0, 13)
        #cn.addSolid(cs)

        collisionSolids = [CollisionTube(6.5, -7.5, 0, 6.5, 7.5, 0, 2.5), #tube1
                           CollisionTube(-6.5, -7.5, 0, -6.5, 7.5, 0, 2.5), #tube2
                           CollisionSphere(0, 0, 0, 8.35) #box (as sphere)
        ]

        for collisionSolid in collisionSolids:
            cn.addSolid(collisionSolid)

        cs = CollisionInvSphere(0, 0, 0, 42)
        cn.addSolid(cs)
        self.boss.attachNewNode(cn)

    def __deleteBoss(self):
        if self.__bossExists():
            self.boss.cleanupBossBattle()
            self.boss.requestDelete()
            self.boss.removeNode()
            self.statusEffectSystem.requestDelete()
        self.boss = None
        self.statusEffectSystem = None

    def __bossExists(self) -> bool:
        return self.boss is not None

    # Disable is never called on the AI so we do not define one
    def cleanup(self):
        """Clean up all resources to prevent memory leaks"""
        # Clean up event listeners
        self.ignoreToonDeaths()
        
        # Clean up all tracked tasks
        for taskName in self._allTaskNames:
            taskMgr.remove(taskName)
        self._allTaskNames.clear()
        
        # Clean up safe effect tasks
        for taskName in self.safeEffectTasks:
            taskMgr.remove(taskName)
        self.safeEffectTasks.clear()
        
        # Clean up specific known tasks
        taskMgr.remove(self.uniqueName('times-up-task'))
        taskMgr.remove(self.uniqueName('post-times-up-task'))
        taskMgr.remove(self.uniqueName('NextGoon'))
        taskMgr.remove(self.uniqueName('safe-effects'))
        taskMgr.remove(self.uniqueName('laff-drain-task'))
        taskMgr.remove(self.uniqueName('craneGameVictory'))
        taskMgr.remove(self.uniqueName('craneGameNextRound'))
        taskMgr.remove(self.uniqueName('startNextRound'))
        
        # Clean up combo trackers
        self.cleanupComboTrackers()
        
        # Clean up objects
        self.__deleteCraningObjects()
        self.__deleteBoss()
        
        # Clean up scene
        if self.scene is not None:
            self.scene.removeNode()
            self.scene = None

    def delete(self):
        self.notify.debug("delete")
        # Clean up all resources
        
        self.cleanup()
        del self.gameFSM
        DistributedMinigameAI.delete(self)

    # override some network message handlers
    def setGameReady(self):
        self.notify.debug("setGameReady")
        DistributedMinigameAI.setGameReady(self)
        # all of the players have checked in
        # they will now be shown the rules
        self.d_setBossCogId()
        self.setupRuleset()
        self.setupSpawnpoints()
        # Reset custom spawn order flag for new games (not restarts)
        self.resetCustomSpawnOrder()
        # Reset round information for new games
        self.roundWins = {}
        self.originalSpawnOrder = []
        self._inMultiRoundMatch = False
        
        # Clear any pending forfeit requests
        self.pendingForfeitRequest = None
        self.forfeitConsents.clear()
        # Clear any pending restart requests
        self.pendingRestartRequest = None
        self.restartConsents.clear()
        
        # Initialize best-of settings
        self.d_setBestOf()
        self.d_setRoundInfo()

    def setupRuleset(self):
        self.ruleset = CraneGameGlobals.CraneGameRuleset()
        self.modifiers.clear()
        modifiers = []
        for modifier in self.desiredModifiers:
            modifiers.append(modifier)
        # Should we randomize some modifiers?
        if self.rollModsOnStart:
            modifiers += self.rollRandomModifiers()

        # Add default competitive modifiers only on first setup for 2+ players
        if len(self.getParticipantsNotSpectating()) >= 2 and not self.defaultModifiersInitialized:
            invincibleBoss = CraneGameGlobals.ModifierInvincibleBoss()
            timerEnabler = CraneGameGlobals.ModifierTimerEnabler(3)
            sideCranesEnabler = CraneGameGlobals.ModifierSideCranesEnabler()
            modifiers.append(invincibleBoss)
            modifiers.append(timerEnabler)
            modifiers.append(sideCranesEnabler)
            # Also add them to desiredModifiers so they persist until explicitly removed
            self.desiredModifiers.append(invincibleBoss)
            self.desiredModifiers.append(timerEnabler)
            self.desiredModifiers.append(sideCranesEnabler)
            self.defaultModifiersInitialized = True

        self.applyModifiers(modifiers, updateClient=True)

        if self.getBoss() is not None:
            self.getBoss().setRuleset(self.ruleset)

    # Call to update the ruleset with the modifiers active, note calling more than once can cause unexpected behavior
    # if the ruleset doesn't fallback to an initial value, for example if a cfo hp increasing modifier is active and we
    # call this multiply times, his hp will be 1500 * 1.5 * 1.5 * 1.5 etc etc
    def applyModifiers(self, modifiers: list[CraneGameGlobals.CFORulesetModifierBase], updateClient=False):
        for modifier in modifiers:
            self.applyModifier(modifier, updateClient=False)
        if updateClient:
            self.d_setRawRuleset()
            self.d_setModifiers()

    def applyModifier(self, modifier: CraneGameGlobals.CFORulesetModifierBase, updateClient=False):
        self.modifiers.append(modifier)
        modifier.apply(self.ruleset)
        self.ruleset.validate()
        if updateClient:
            self.d_setRawRuleset()
            self.d_setModifiers()

    def removeModifier(self, modifierClass):
        modifiers = list(self.modifiers)
        for mod in self.modifiers:
            if mod.__class__ == modifierClass:
                modifiers.remove(mod)
        for mod in list(self.desiredModifiers):
            if mod.__class__ == modifierClass:
                self.desiredModifiers.remove(mod)
        self.modifiers = modifiers
        self.d_setRawRuleset()
        self.d_setModifiers()

    # Any time you change the ruleset, you should call this to sync the clients
    def d_setRawRuleset(self):
        self.sendUpdate('setRawRuleset', [self.getRawRuleset()])

    def __getRawModifierList(self):
        mods = []
        for modifier in self.modifiers:
            mods.append(modifier.asStruct())
        return mods

    def d_setModifiers(self):
        self.sendUpdate('setModifiers', [self.__getRawModifierList()])

    def rollRandomModifiers(self):
        tierLeftBound = self.ruleset.MODIFIER_TIER_RANGE[0]
        tierRightBound = self.ruleset.MODIFIER_TIER_RANGE[1]
        pool: list[CraneGameGlobals.CFORulesetModifierBase] = [c(random.randint(tierLeftBound, tierRightBound)) for c in
                                                                 CraneGameGlobals.NON_SPECIAL_MODIFIER_CLASSES]

        alreadyApplied = [mod.MODIFIER_ENUM for mod in self.desiredModifiers]
        for choice in list(pool):
            if choice.MODIFIER_ENUM in alreadyApplied:
                pool.remove(choice)

        if len(pool) <= 0:
            return

        random.shuffle(pool)

        modifiers = [pool.pop() for _ in range(self.numModsWanted)]

        # If we roll a % roll, go ahead and make this a special cfo
        # Doing this last also ensures any rules that the special mod needs to set override
        if random.randint(0, 99) < CraneGameGlobals.SPECIAL_MODIFIER_CHANCE:
            cls = random.choice(CraneGameGlobals.SPECIAL_MODIFIER_CLASSES)
            tier = random.randint(tierLeftBound, tierRightBound)
            mod_instance = cls(tier)
            modifiers.append(mod_instance)

        return modifiers

    def setGameStart(self, timestamp):
        self.notify.debug("setGameStart")
        # base class will cause gameFSM to enter initial state
        DistributedMinigameAI.setGameStart(self, timestamp)
        # all of the players are ready to start playing the game
        # transition to the appropriate ClassicFSM state
        self.gameFSM.request('prepare')

    def setGameAbort(self):
        self.notify.debug("setGameAbort")
        # this is called when the minigame is unexpectedly
        # ended (a player got disconnected, etc.)
        if self.gameFSM.getCurrentState():
            self.gameFSM.request('cleanup')

        DistributedMinigameAI.setGameAbort(self)
        if self.scene is not None:
            self.scene.removeNode()
            self.scene = None

    def gameOver(self):
        self.notify.debug("gameOver")
        # call this when the game is done
        # clean things up in this class
        
        self.gameFSM.request('cleanup')
        # tell the base class to wrap things up
        DistributedMinigameAI.gameOver(self)
        if self.scene is not None:
            self.scene.removeNode()
            self.scene = None

    def clearObjectSpeedCaching(self):
        for safe in self.safes:
            safe.d_resetSpeedCaching()

        for goon in self.goons:
            goon.d_resetSpeedCaching()

    def __makeCraningObjects(self):

        # Generate all of the cranes.
        self.cranes.clear()
        ind = 0

        for _ in CraneGameGlobals.NORMAL_CRANE_POSHPR:
            crane = DistributedCashbotCraneAI(self.air, self, ind)
            crane.generateWithRequired(self.zoneId)
            self.cranes.append(crane)
            ind += 1

        # Generate the sidecranes if wanted
        if self.ruleset.WANT_SIDECRANES:
            for _ in CraneGameGlobals.SIDE_CRANE_POSHPR:
                crane = DistributedCashbotSideCraneAI(self.air, self, ind)
                crane.generateWithRequired(self.zoneId)
                self.cranes.append(crane)
                ind += 1
        # Generate boom barrows if wanted (alternative to side cranes)
        elif self.ruleset.WANT_BOOM_BARROWS:
            for boomBarrowIndex, _ in enumerate(CraneGameGlobals.SIDE_CRANE_POSHPR):
                boomBarrow = DistributedCashbotBoomBarrowAI(self.air, self, boomBarrowIndex)
                boomBarrow.generateWithRequired(self.zoneId)
                boomBarrow.b_setIndex(boomBarrowIndex)
                self.boomBarrows.append(boomBarrow)
            
            # Generate floating platforms near door and vault (in front of and behind CFO)
            # CFO is at approximately (120, -315, 0)
            # Door is at (84, -201, -6) - towards positive Y from CFO
            # Vault is behind CFO - towards negative Y from CFO
            # Platform positions: one in front of CFO (towards door), one behind CFO (towards vault)
            # Positioned further away and at appropriate height so toons can reach them
            platformPositions = [
                (120, -278, 4),   # Front platform (towards door, in front of CFO) - 40 units away
                (120, -357, 4),   # Back platform (behind CFO, towards vault) - 40 units away
            ]
            for platformIndex, (x, y, z) in enumerate(platformPositions):
                platform = DistributedCashbotFloatingPlatformAI(self.air, self, platformIndex)
                platform.generateWithRequired(self.zoneId)
                platform.b_setIndex(platformIndex)
                platform.setPosition(x, y, z)
                self.floatingPlatforms.append(platform)

        # Generate the heavy cranes if wanted
        if self.ruleset.WANT_HEAVY_CRANES:
            for _ in CraneGameGlobals.HEAVY_CRANE_POSHPR:
                crane = DistributedCashbotHeavyCraneAI(self.air, self, ind)
                crane.generateWithRequired(self.zoneId)
                self.cranes.append(crane)
                ind += 1

        # And all of the safes.
        self.safes.clear()
        for index in range(min(self.ruleset.SAFES_TO_SPAWN, len(CraneGameGlobals.SAFE_POSHPR))):
            safe = DistributedCashbotSafeAI(self.air, self, index)
            safe.generateWithRequired(self.zoneId)
            self.safes.append(safe)

        self.goons.clear()
        return

    def __resetCraningObjects(self):
        for crane in self.cranes:
            crane.request('Free')

        for safe in self.safes:
            safe.request('Initial')

    def __deleteCraningObjects(self):
        for crane in self.cranes:
            crane.request('Off')
            crane.requestDelete()

        self.cranes.clear()

        for safe in self.safes:
            safe.request('Off')
            safe.requestDelete()
        self.safes.clear()

        # Clean up boom barrows
        for boomBarrow in self.boomBarrows:
            boomBarrow.requestDelete()
        self.boomBarrows.clear()
        
        # Clean up floating platforms
        for platform in self.floatingPlatforms:
            platform.requestDelete()
        self.floatingPlatforms.clear()

        for goon in self.goons:
            goon.request('Off')
            goon.requestDelete()
        self.goons.clear()

    # Call to listen for toon death events. Useful for catching deaths caused by DeathLink.
    def listenForToonDeaths(self):
        self.ignoreToonDeaths()
        for toon in self.getParticipatingToons():
            self.__listenForToonDeath(toon)

    # Ignore toon death events. We don't need to worry about toons dying in specific scenarios
    # Such as turn based battles as BattleBase handles that for us.
    def ignoreToonDeaths(self):
        for event in self._deathListenerEvents:
            self.ignore(event)
        self._deathListenerEvents.clear()

    def __listenForToonDeath(self, toon):
        event = toon.getGoneSadMessage()
        self.accept(event, self.toonDied, [toon])
        self._deathListenerEvents.append(event)

    def __ignoreToonDeath(self, avId):
        self.ignore(DistributedToonAI.getGoneSadMessageForAvId(avId))

    def toonDied(self, toon):
        self.resetCombo(toon.doId)
        self.sendUpdate('toonDied', [toon.doId])

        # If we are in overtime, we don't need to do anything else.
        if self.currentlyInOvertime:
            self.__checkOvertimeState()
            return

        # Toons are expected to die in overtime. Only penalize them if it is in the normal round.
        self.addScore(toon.doId, self.ruleset.POINTS_PENALTY_GO_SAD, reason=ScoreReason.WENT_SAD)

        # Add a task to revive the toon.
        taskMgr.doMethodLater(self.ruleset.REVIVE_TOONS_TIME, self.reviveToon,
                              self.uniqueName(f"reviveToon-{toon.doId}"), extraArgs=[toon.doId])

    def getHighestScorers(self):
        """
        Gets a list of who is currently in the lead.
        If the list is empty, we have no players playing.
        If the list has one person, someone is in the lead.
        If the last has multiple people, they are tied for 1st place.
        """

        all_scores = self.getScoringContext().get_round(self.currentRound).get_all_scores()

        # Are there no players?
        if len(all_scores) <= 0:
            return []

        # Create a reversed dict where we map score to the players who have that score.
        results = {}
        highestScore = -999_999
        for player, score in all_scores.items():
            toonsWithScore = results.get(score, [])
            toonsWithScore.append(player)
            results[score] = toonsWithScore
            highestScore = max(highestScore, score)

        # Query the players with the highest score.
        return results[highestScore]

    def reviveToon(self, toonId: int) -> None:
        toon = self.air.getDo(toonId)
        if toon is None:
            return

        toon.b_setHp(int(self.ruleset.REVIVE_TOONS_LAFF_PERCENTAGE * toon.getMaxHp()))

        self.sendUpdate("revivedToon", [toonId])

    def d_updateCombo(self, avId, comboLength):
        self.sendUpdate('updateCombo', [avId, comboLength])

    def handleExitedAvatar(self, avId):
        taskMgr.remove(self.uniqueName(f"reviveToon-{avId}"))
        self.removeToon(avId)

        super().handleExitedAvatar(avId)

    def removeToon(self, avId):
        # The toon leaves the zone, either through disconnect, death,
        # or something else.  Tell all of the safes, cranes, and goons.
        for crane in self.cranes:
            crane.removeToon(avId)

        for safe in self.safes:
            safe.removeToon(avId)

        for goon in self.goons:
            goon.removeToon(avId)

    def initializeComboTrackers(self):
        self.cleanupComboTrackers()
        for avId in self.getParticipants():
            if avId in self.air.doId2do:
                self.comboTrackers[avId] = CashbotBossComboTracker(self, avId)

    def incrementCombo(self, avId, amount):
        tracker = self.comboTrackers.get(avId)
        if not tracker:
            return

        tracker.incrementCombo(amount)

    def resetCombo(self, avId):
        tracker = self.comboTrackers.get(avId)
        if not tracker:
            return

        tracker.resetCombo()

    def getComboLength(self, avId):
        tracker = self.comboTrackers.get(avId)
        if not tracker:
            return 0

        return tracker.combo

    def getComboAmount(self, avId):
        tracker = self.comboTrackers.get(avId)
        if not tracker:
            return 0

        return tracker.pointBonus

    def cleanupComboTrackers(self):
        for comboTracker in self.comboTrackers.values():
            comboTracker.cleanup()

    def grabAttempt(self, avId, treasureId):
        """
        A toon wants to grab a certain treasure. Validates the treasure is valid to grab
        """

        # First, try to see if we can find the treasure that was grabbed.
        treasure = self.treasures.get(treasureId)
        if treasure is None:
            return

        # Now get the toon that wants to grab it.
        toon = simbase.air.getDo(avId)
        if toon is None:
            return

        # Are they allowed to take this treasure?
        if not treasure.validAvatar(toon):
            treasure.d_setReject()
            return

        del self.treasures[treasureId]
        treasure.d_setGrab(avId)  # Todo a lot of logic is in this method call. This is such bad design and should prob be refactored.
        self.grabbingTreasures[treasureId] = treasure

        # Wait a few seconds for the animation to play, then
        # recycle the treasure.
        taskMgr.doMethodLater(5, self.__recycleTreasure, treasure.uniqueName('recycleTreasure'), extraArgs=[treasure])

    def __recycleTreasure(self, treasure):
        if treasure.doId in self.grabbingTreasures:
            del self.grabbingTreasures[treasure.doId]
            self.recycledTreasures.append(treasure)

    def deleteAllTreasures(self):
        for treasure in self.treasures.values():
            treasure.requestDelete()

        self.treasures = {}
        for treasure in self.grabbingTreasures.values():
            taskMgr.remove(treasure.uniqueName('recycleTreasure'))
            treasure.requestDelete()

        self.grabbingTreasures = {}
        for treasure in self.recycledTreasures:
            treasure.requestDelete()

        self.recycledTreasures = []

    def makeTreasure(self, goon):
        # Places a treasure, as pooped out by the given goon.  We
        # place the treasure at the goon's current position, or at
        # least at the beginning of its current path.  Actually, we
        # ignore Z, and always place the treasure at Z == 0,
        # presumably the ground.

        # Too many treasures on the field?
        if len(self.treasures) >= self.ruleset.MAX_TREASURE_AMOUNT:
            return

        # Drop chance?
        if self.ruleset.GOON_TREASURE_DROP_CHANCE < 1.0:
            if random.random() > self.ruleset.GOON_TREASURE_DROP_CHANCE:
                return

        # The BossCog acts like a treasure planner as far as the
        # treasure is concerned.
        pos = goon.getPos(self.boss)

        # The treasure pops out and lands somewhere nearby.  Let's
        # start by choosing a point on a ring around the boss, based
        # on our current angle to the boss.
        v = Vec3(pos[0], pos[1], 0.0)
        if not v.normalize():
            v = Vec3(1, 0, 0)
        v = v * 27

        # Then perterb that point by a distance in some random
        # direction.
        angle = random.uniform(0.0, 2.0 * math.pi)
        radius = 10
        dx = radius * math.cos(angle)
        dy = radius * math.sin(angle)

        fpos = self.scene.getRelativePoint(self.boss, Point3(v[0] + dx, v[1] + dy, 0))

        # Find an index based on the goon strength we should use
        treasureHealIndex = 1.0 * (goon.strength - self.ruleset.MIN_GOON_DAMAGE) / (
                    self.ruleset.MAX_GOON_DAMAGE - self.ruleset.MIN_GOON_DAMAGE)
        treasureHealIndex *= len(self.ruleset.GOON_HEALS)
        treasureHealIndex = int(clamp(treasureHealIndex, 0, len(self.ruleset.GOON_HEALS) - 1))
        healAmount = self.ruleset.GOON_HEALS[treasureHealIndex]
        availStyles = self.ruleset.TREASURE_STYLES[treasureHealIndex]
        style = random.choice(availStyles)

        if self.recycledTreasures:
            # Reuse a previous treasure object
            treasure = self.recycledTreasures.pop(0)
            treasure.d_setGrab(0)
            treasure.b_setGoonId(goon.doId)
            treasure.b_setStyle(style)
            treasure.b_setPosition(pos[0], pos[1], 0)
            treasure.b_setFinalPosition(fpos[0], fpos[1], 0)
        else:
            # Create a new treasure object
            treasure = DistributedCashbotTreasureAI(self.air, self, goon, style, fpos[0], fpos[1], 0)
            treasure.generateWithRequired(self.zoneId)
        treasure.healAmount = healAmount
        self.treasures[treasure.doId] = treasure

    def getMaxGoons(self):
        return self.progressValue(self.ruleset.MAX_GOON_AMOUNT_START, self.ruleset.MAX_GOON_AMOUNT_END)

    def __chooseGoonEmergeSide(self) -> str:
        """
        Determines the next side for a goon to emerge from.
        To limit the amount of RNG present, we prevent goons from spawning from the same side over and over in a row.
        """

        # Default goon spawning logic.
        # Is it okay to pick a random side?
        if self.goonCache[1] < 2:
            return random.choice(['EmergeA', 'EmergeB'])

        # There's too many goons coming from a certain side. Pick the opposite one.
        if self.goonCache[0] == 'EmergeA':
            return 'EmergeB'
        return 'EmergeA'

    def __isPositionClear(self, x, y, minDistance=5):
        # Check distance to all safes
        for safe in self.safes:
            safePos = safe.getPos()
            if abs(safePos[0] - x) < minDistance and abs(safePos[1] - y) < minDistance:
                return False
                
        # Check distance to all cranes
        for crane in self.cranes:
            # Get crane position based on its type and index
            if isinstance(crane, DistributedCashbotSideCraneAI):
                poshpr = CraneGameGlobals.SIDE_CRANE_POSHPR[crane.index - len(CraneGameGlobals.NORMAL_CRANE_POSHPR)]
            else:
                poshpr = CraneGameGlobals.NORMAL_CRANE_POSHPR[crane.index]
            cranePos = (poshpr[0], poshpr[1], poshpr[2])
            if abs(cranePos[0] - x) < minDistance and abs(cranePos[1] - y) < minDistance:
                return False
                
        return True

    def makeGoon(self, side=None, forceNormalSpawn=False, fallingChance=0.5):
        # Picks a side for a goon to generate on if not specified
        if side is None:
            side = self.__chooseGoonEmergeSide()

        # Should this goon fall if we are in overtime?
        falling = random.random() < fallingChance

        # Long logic process to determine whether a goon should be made and what type.
        # If we are at max goon size, do not make a new goon
        if len(self.goons) >= self.getMaxGoons():
            return

        #Only 2 current cases where goons should spawn when the CFO is stunned
        if self.boss.isStunned():
            #If we are in OT and we roll a falling goon and it's not a forced normal spawn
            if self.currentlyInOvertime and falling and not forceNormalSpawn:
                pass
            else:
                return

        #From here on out, a goon is guaranteed to be created on a specific side of the room
        self.__updateGoonCache(side)

        # Create and generate the goon
        goon = DistributedCashbotGoonAI(self.air, self)
        goon.generateWithRequired(self.zoneId)
        self.goons.append(goon)

        # Attributes for desperation mode goons
        goon_stun_time = 6
        goon_velocity = 7
        goon_hfov = 90
        goon_attack_radius = 17
        goon_strength = self.ruleset.MAX_GOON_DAMAGE + 10
        goon_scale = self.goonMaxScale + .1

        # If the battle isn't in desperation yet override the values to normal values
        if self.getBattleThreeTime() <= 1.0:
            goon_stun_time = self.progressValue(30, 8)
            goon_velocity = self.progressRandomValue(3, 7)
            goon_hfov = self.progressRandomValue(70, 80)
            goon_attack_radius = self.progressRandomValue(6, 15)
            goon_strength = int(self.progressRandomValue(self.ruleset.MIN_GOON_DAMAGE, self.ruleset.MAX_GOON_DAMAGE))
            goon_scale = self.progressRandomValue(self.goonMinScale, self.goonMaxScale)

        # Apply multipliers if necessary
        goon_velocity *= self.ruleset.GOON_SPEED_MULTIPLIER

        # Apply attributes to the goon
        goon.STUN_TIME = goon_stun_time
        goon.b_setupGoon(velocity=goon_velocity, hFov=goon_hfov, attackRadius=goon_attack_radius,
                         strength=goon_strength, scale=goon_scale)

        # Properly set up the goon in "Falling" state if necessary
        if self.currentlyInOvertime and falling:
            self.__makeFallingGoon(goon, side)
        else:
            goon.request(side)

    def __updateGoonCache(self, side):
        if side == self.goonCache[0]:
            self.goonCache = (side, self.goonCache[1] + 1)
        else:
            self.goonCache = (side, 1)

    def __makeFallingGoon(self, goon, side):
        bossPos = self.boss.getPos()

        # Keep trying positions until we find a clear one
        # Took out prevent infinite loops code because 8 safes give a maximum of 200pi area covered
        # Half of our allotted area for falling goons is 250 pi. Chance of 21+ iterations is 1.15%. 41+ is 0.013%.
        while True:
            # Random position 15-20 units away from CFO on correct side
            radius = random.uniform(20, 30)
            theta = random.uniform(-math.pi, math.pi)
            xPos = bossPos[0] + radius * math.cos(theta)

            #Bad luck protection position calculation
            if side == "EmergeA":
                yPos = bossPos[1] + abs(radius * math.sin(theta))
            else:
                yPos = bossPos[1] - abs(radius * math.sin(theta))

            # Check if position is clear
            if self.__isPositionClear(xPos, yPos):
                randomH = random.uniform(0, 360)  # Random heading between 0-360 degrees
                goon.b_setPosHpr(xPos, yPos, 40, randomH, 0, 0)
                goon.request('Falling')
                return

    def waitForNextGoon(self, delayTime):
        taskName = self.uniqueName('NextGoon')
        taskMgr.remove(taskName)
        self._allTaskNames.add(taskName)
        taskMgr.doMethodLater(delayTime, self.doNextGoon, taskName)

    def stopGoons(self):
        taskName = self.uniqueName('NextGoon')
        taskMgr.remove(taskName)

    def doNextGoon(self, task):
        self.makeGoon()
        # How long to wait for the next goon?
        delayTime = self.progressValue(10, 2)
        self.waitForNextGoon(delayTime)

    def progressValue(self, fromValue, toValue):
        if self.ruleset.TIMER_MODE:
            elapsed = globalClock.getFrameTime() - self.battleThreeStart
            t = elapsed / float(self.ruleset.TIMER_MODE_TIME_LIMIT)
        else:
            t0 = float(self.getBoss().bossDamage) / float(self.ruleset.CFO_MAX_HP)
            elapsed = globalClock.getFrameTime() - self.battleThreeStart
            t1 = elapsed / float(self.DESPERATION_MODE_ACTIVATE_THRESHOLD)
            t = max(t0, t1)
        return fromValue + (toValue - fromValue) * min(t, 1)

    def progressRandomValue(self, fromValue, toValue, radius=0.2, noRandom=False):
        t = self.progressValue(0, 1)
        radius = radius * (1.0 - abs(t - 0.5) * 2.0)
        if noRandom:
            t += radius
        else:
            t += radius * random.uniform(-1, 1)
        t = max(min(t, 1.0), 0.0)
        return fromValue + (toValue - fromValue) * t

    def getBattleThreeTime(self):
        elapsed = globalClock.getFrameTime() - self.battleThreeStart
        duration = self.ruleset.TIMER_MODE_TIME_LIMIT if self.ruleset.TIMER_MODE else self.DESPERATION_MODE_ACTIVATE_THRESHOLD
        t1 = elapsed / float(duration)
        return t1

    def setupSpawnpoints(self):
        # Only reset spawn order if it hasn't been manually customized by the leader
        if not hasattr(self, 'customSpawnOrderSet') or not self.customSpawnOrderSet:
            self.toonSpawnpointOrder = [i for i in range(16)]
            
            # For best of 1 matches, randomize only the first spawn positions based on number of participants
            if self.bestOfValue == 1:
                # Get number of participating toons (not spectating)
                numParticipants = len(self.getParticipantIdsNotSpectating())
                if numParticipants > 0:
                    # Randomize only the first 'numParticipants' positions
                    firstPositions = self.toonSpawnpointOrder[:numParticipants]
                    random.shuffle(firstPositions)
                    # Put the randomized positions back at the beginning
                    self.toonSpawnpointOrder[:numParticipants] = firstPositions
            # For other matches (best of 3, 5, 7), use the existing ruleset randomization if enabled
            elif self.ruleset.RANDOM_SPAWN_POSITIONS:
                random.shuffle(self.toonSpawnpointOrder)
                
        self.d_setToonSpawnpointOrder()

    def resetCustomSpawnOrder(self):
        """Reset the custom spawn order flag, allowing spawn points to be randomized again"""
        self.customSpawnOrderSet = False

    def d_setToonSpawnpointOrder(self):
        self.sendUpdate('setToonSpawnpointOrder', [self.toonSpawnpointOrder])

    def updateSpawnOrder(self, newOrder):
        """Handle spawn order update from the leader"""
        # Verify the sender is the leader (first player in avIdList)
        senderId = self.air.getAvatarIdFromSender()
        if senderId != self.avIdList[0]:
            self.notify.warning(f"Non-leader {senderId} tried to update spawn order")
            return
            
        # Validate the new order contains the same avatars
        if set(newOrder) != set(self.toonSpawnpointOrder):
            self.notify.warning(f"Invalid spawn order update from {senderId}: {newOrder}")
            return
            
        # Update the spawn order and mark it as customized
        self.toonSpawnpointOrder = newOrder[:]
        self.customSpawnOrderSet = True
        self.d_setToonSpawnpointOrder()

    def setBestOf(self, value):
        """Handle best-of setting from the leader"""
        # Verify the sender is the leader (first player in avIdList)
        senderId = self.air.getAvatarIdFromSender()
        if senderId != self.avIdList[0]:
            self.notify.warning(f"Non-leader {senderId} tried to set best-of value")
            return
            
        # Validate the value
        if value not in [1, 3, 5, 7]:
            self.notify.warning(f"Invalid best-of value from {senderId}: {value}")
            return
            
        self.bestOfValue = value
        self.d_setBestOf()
        self.notify.info(f"Best-of value set to {value} by leader {senderId}")

    def d_setBestOf(self):
        """Send best-of value to all clients"""
        self.sendUpdate('setBestOf', [self.bestOfValue])

    def d_setRoundInfo(self):
        """Send round information to all clients"""
        # Convert roundWins dict to list format for transmission
        roundWinsList = []
        for avId in self.avIdList:
            roundWinsList.append(self.roundWins.get(avId, 0))
        self.sendUpdate('setRoundInfo', [self.currentRound, roundWinsList])

    def nextRound(self):
        """Handle transition to next round in best-of matches"""
        if self.bestOfValue <= 1:
            return  # Not a best-of match
        
        self.currentRound += 1
        self._inMultiRoundMatch = True  # Flag to indicate we're in a multi-round match
        
        # Start the next round after a brief delay
        taskMgr.doMethodLater(0.5, self.__startNextRound, self.uniqueName("startNextRound"))

    def __startNextRound(self, task=None):
        """Start the next round in a best-of match"""
        # Rotate spawn positions for variety
        if not self.customSpawnOrderSet:
            self.__rotateSpawnPositions()

        # Use proper FSM transitions like the RestartCraneRound magic word
        self.gameFSM.request("cleanup")
        self.gameFSM.request('prepare')
        
        # Note: round info will be sent in enterPrepare, no need to send here

    def __rotateSpawnPositions(self):
        """Rotate spawn positions for the next round"""
        # Get participating toons (not spectating)
        participatingToons = self.getParticipantIdsNotSpectating()
        numParticipants = len(participatingToons)
        
        if numParticipants <= 1:
            return  # No rotation needed for single player
        
        # Store the original spawn positions if this is the first rotation
        if not hasattr(self, 'originalSpawnOrder') or not self.originalSpawnOrder:
            self.originalSpawnOrder = self.toonSpawnpointOrder[:numParticipants]
        
        # Get the current spawn positions for participating players
        currentPositions = self.toonSpawnpointOrder[:numParticipants]
        
        # Rotate positions: each player moves to the next position
        # Player at position 0 -> position 1, position 1 -> position 2, etc.
        # Last player wraps around to position 0
        rotatedPositions = [currentPositions[(i + 1) % numParticipants] for i in range(numParticipants)]
        
        # Update the spawn order with rotated positions
        for i in range(numParticipants):
            self.toonSpawnpointOrder[i] = rotatedPositions[i]
        
        # Mark spawn order as customized so setupSpawnpoints() doesn't override it
        self.customSpawnOrderSet = True
        
        self.d_setToonSpawnpointOrder()
        self.notify.info(f"Rotated spawn positions for round {self.currentRound}: {self.toonSpawnpointOrder[:numParticipants]}")

    def getRawRuleset(self):
        return self.ruleset.asStruct()

    def d_setBossCogId(self) -> None:
        self.sendUpdate("setBossCogId", [self.boss.getDoId()])
    
    def d_setStatusEffectSystemId(self) -> None:
        self.sendUpdate("setStatusEffectSystemId", [self.statusEffectSystem.getDoId()])

    def getBoss(self):
        return self.boss

    def damageToon(self, toon, deduction):
        if toon.getHp() <= 0:
            return

        if self.isSpectating(toon.getDoId()):
            return
        
        # Check if toon has active shield
        if hasattr(self, 'activeShields') and toon.getDoId() in self.activeShields:
            shield = self.activeShields[toon.getDoId()]
            if shield.isShieldActive():
                # Shield absorbs the hit, grant i-frames
                shield.breakShield(grantIframes=True)
                return  # No damage applied

        toon.takeDamage(deduction)

    def getToonOutgoingMultiplier(self, avId):
        return 100

    def recordHit(self, damage, impact=0, craneId=-1, objId=0, isGoon=False, isDOT=False, avIdOverride=None, forceStun=False):

        # Don't process a hit if we aren't in the play state.
        if self.gameFSM.getCurrentState().getName() != 'play':
            return

        avId = self.air.getAvatarIdFromSender()
        # Sometimes we want to force damage from other sources and not an update.
        if avIdOverride is not None:
            avId = avIdOverride
        crane = simbase.air.doId2do.get(craneId)
        if not self.validate(avId, avId in self.getParticipants(), 'recordHit from unknown avatar'):
            return
        
        # Apply damage vulnerability if SHATTERED is active
        if self.statusEffectSystem.hasStatusEffect(self.getBoss().doId, StatusEffect.SHATTERED):
            damage += int(damage * 0.5)

        # Record a successful hit in battle three.
        self.boss.b_setBossDamage(self.boss.bossDamage + damage, avId=avId, objId=objId, isGoon=isGoon, isDOT=isDOT)

        # Award bonus points for hits with maximum impact (but not for DOT)
        # Check if impact cap is removed - if so, award for impact >= 1.0, otherwise for impact == 1.0
        removeCap = False
        if hasattr(self.ruleset, 'REMOVE_IMPACT_CAP'):
            removeCap = self.ruleset.REMOVE_IMPACT_CAP
        
        if not isDOT:
            if removeCap:
                if impact >= 1.0:
                    self.addScore(avId, self.ruleset.POINTS_IMPACT, reason=CraneGameGlobals.ScoreReason.FULL_IMPACT)
            else:
                if impact == 1.0:
                    self.addScore(avId, self.ruleset.POINTS_IMPACT, reason=CraneGameGlobals.ScoreReason.FULL_IMPACT)
        self.addScore(avId, damage)

        # DOT damage should not contribute to combos
        if not isDOT:
            comboTracker = self.comboTrackers[avId]
            comboTracker.incrementCombo((comboTracker.combo + 1.0) / 10.0 * damage)

        # The CFO has been defeated, proceed to Victory state
        if self.boss.bossDamage >= self.ruleset.CFO_MAX_HP:
            self.addScore(avId, self.ruleset.POINTS_KILLING_BLOW, CraneGameGlobals.ScoreReason.KILLING_BLOW)
            self.toonsWon = True
            self.gameFSM.request('victory')
            return

        # DOT damage should not cause flinching, stunning, or helmet behavior
        if isDOT:
            return

        # The CFO is already dizzy, OR the crane is None, so get outta here
        # But if forceStun is True, we should still process the stun even if crane is None
        # Also allow processing if isGoon=True (goon hits should always process for fast recovery)
        # BUT: if CFO is already stunned, goon hits should just deal damage and return (don't interfere with stun)
        if not forceStun and not isGoon and (self.boss.attackCode == ToontownGlobals.BossCogDizzy or not crane):
            return

        # If forceStun is True but CFO is already stunned, don't do anything that would affect the stun state
        # This prevents Xplodey and Stunna from canceling an existing stun
        if forceStun and (self.boss.attackCode == ToontownGlobals.BossCogDizzy or self.boss.attackCode == ToontownGlobals.BossCogDizzyNow):
            return
        
        # If CFO is already stunned and this is a goon hit (regular goons or Xplodey), just deal damage and return
        # Don't process flinch/recovery logic that might interfere with the stun
        if isGoon and (self.boss.attackCode == ToontownGlobals.BossCogDizzy or self.boss.attackCode == ToontownGlobals.BossCogDizzyNow):
            return

        self.boss.stopHelmets()

        # Is the damage high enough to stun? or did a side crane hit a high impact hit?
        # For forceStun, we don't need to check considerStun - just check if CFO is not already stunned
        if forceStun:
            # Check if CFO is not already in any stun state
            hitMeetsStunRequirements = (self.boss.attackCode != ToontownGlobals.BossCogDizzy and 
                                        self.boss.attackCode != ToontownGlobals.BossCogDizzyNow)
        else:
            # For goon hits (isGoon=True), don't check stun requirements if crane is None
            # Goon hits should just flinch and recover quickly, not stun
            if isGoon and crane is None:
                hitMeetsStunRequirements = False
            else:
                hitMeetsStunRequirements = (self.boss.considerStun(crane, damage, impact) or forceStun) and self.boss.attackCode != ToontownGlobals.BossCogDizzy
        
        if hitMeetsStunRequirements:
            # A particularly good hit (when he's not already
            # dizzy) will make the boss dizzy for a little while.
            delayTime = self.progressValue(20, 5)
            self.boss.b_setAttackCode(ToontownGlobals.BossCogDizzy, delayTime=delayTime)
            isSideCrane = isinstance(crane, DistributedCashbotSideCraneAI)
            reason = CraneGameGlobals.ScoreReason.SIDE_STUN if isSideCrane else CraneGameGlobals.ScoreReason.STUN
            
            # Determine points based on stun type
            if crane is not None:
                # Regular crane stun
                points = crane.getPointsForStun()
            elif forceStun and crane is None:
                # Check if this is Stunna drone (objId=999999) or pie stun
                if objId == 999999:
                    # Stunna drone - give 10 points
                    points = 10
                else:
                    # Pie stun - give 30 points
                    points = 30
            else:
                # Fallback for other cases
                points = self.ruleset.POINTS_STUN // 2
            
            self.addScore(avId, points, reason=reason)
        else:

            if self.ruleset.CFO_FLINCHES_ON_HIT:
                self.boss.b_setAttackCode(ToontownGlobals.BossCogNoAttack)

            self.boss.waitForNextHelmet()

        # Now at the very end, if we have momentum mechanic on add some damage multiplier
        if self.ruleset.WANT_MOMENTUM_MECHANIC:
            self.increaseToonOutgoingMultiplier(avId, damage)

    def increaseToonOutgoingMultiplier(self, avId, n):
        """
        todo: implement
        """
        pass
    
    def recordHitWithAttribution(self, damage, attributeToAvId, impact=0, craneId=-1, objId=0, isGoon=False, isDOT=False):
        """
        Record a hit with damage attributed to a specific avatar ID.
        Used for status effects that deal damage on behalf of other players.
        """
        # Don't process a hit if we aren't in the play state.
        if self.gameFSM.getCurrentState().getName() != 'play':
            return

        # Validate that the attributed player is in the game
        if not self.validate(attributeToAvId, attributeToAvId in self.getParticipants(), 'recordHitWithAttribution to unknown avatar'):
            return
        
        # Apply damage vulnerability if SHATTERED is active
        if self.statusEffectSystem.hasStatusEffect(self.getBoss().doId, StatusEffect.SHATTERED):
            damage += int(damage * 0.5)

        # Record a successful hit in battle three.
        self.boss.b_setBossDamage(self.boss.bossDamage + damage, avId=attributeToAvId, objId=objId, isGoon=isGoon, isDOT=isDOT)

        # Award points for the damage (no impact bonus for attributed damage)
        self.addScore(attributeToAvId, damage)

        # DOT damage should not contribute to combos
        if not isDOT:
            comboTracker = self.comboTrackers[attributeToAvId]
            comboTracker.incrementCombo((comboTracker.combo + 1.0) / 10.0 * damage)

        # The CFO has been defeated, proceed to Victory state
        if self.boss.bossDamage >= self.ruleset.CFO_MAX_HP:
            self.addScore(attributeToAvId, self.ruleset.POINTS_KILLING_BLOW, CraneGameGlobals.ScoreReason.KILLING_BLOW)
            self.toonsWon = True
            self.gameFSM.request('victory')
            return

        # DOT damage should not cause flinching, stunning, or helmet behavior
        if isDOT:
            return

        # The CFO is already dizzy, OR there's no crane, so get outta here
        if self.boss.attackCode == ToontownGlobals.BossCogDizzy:
            return

        self.boss.stopHelmets()

        # For attributed damage, we don't handle stunning since there's no crane
        if self.ruleset.CFO_FLINCHES_ON_HIT:
            self.boss.b_setAttackCode(ToontownGlobals.BossCogNoAttack)

        self.boss.waitForNextHelmet()

        # Now at the very end, if we have momentum mechanic on add some damage multiplier
        if self.ruleset.WANT_MOMENTUM_MECHANIC:
            self.increaseToonOutgoingMultiplier(attributeToAvId, damage)

    def addScore(self, avId: int, amount: int, reason: CraneGameGlobals.ScoreReason = CraneGameGlobals.ScoreReason.DEFAULT):

        if amount == 0:
            return

        self.getScoringContext().get_round(self.currentRound).add_score(avId, amount)
        self.d_addScore(avId, amount, reason)

        # Update current winners so we can check for position overtakes (where we should enable overtime)
        self.__updateCurrentWinners()

        # If we are in overtime, check the overtime state. There is a chance this toon overtook 1st place when
        # everyone is dead and should be declared winner.
        if self.currentlyInOvertime and reason != CraneGameGlobals.ScoreReason.COIN_FLIP:
            self.__checkOvertimeState()

        # Check if we can award an uber bonus for being low laff
        self.__awardUberBonusIfEligible(avId, amount, reason)

    def __updateCurrentWinners(self):

        newLeaders = self.getHighestScorers()

        # Perform a quick check for overtime enabling.
        # This check basically is making sure that we are the clock is running low and there is a new leader to check.
        if self.ruleset.TIMER_MODE and not self.overtimeWillHappen and len(newLeaders) > 0 and self.__calculateTimeToSend() < self.OVERTIME_OVERTAKE_ACTIVATION_THRESHOLD:

            # Is there a tie (or was there a tie)?
            tie = len(newLeaders) > 1 or len(self.currentWinners) > 1
            # Is the new leader not the previous?
            overtake = newLeaders[0] != self.currentWinners[0]
            if tie or overtake:
                self.enableOvertime()

        # Update who is currently winning
        self.currentWinners = newLeaders


    def __awardUberBonusIfEligible(self, avId, amount, reason):
        if not self.ruleset.WANT_LOW_LAFF_BONUS:
            return

        if reason.ignore_uber_bonus():
            return

        toon = simbase.air.getDo(avId)
        if toon is None:
            return

        if toon.getHp() > self.ruleset.LOW_LAFF_BONUS_THRESHOLD:
            return

        uberAmount = int(self.ruleset.LOW_LAFF_BONUS * amount)
        if uberAmount == 0:
            return

        # Add additional score if uber bonus is on.
        self.addScore(avId, uberAmount, reason=CraneGameGlobals.ScoreReason.LOW_LAFF)


    def d_addScore(self, avId: int, amount: int, reason: CraneGameGlobals.ScoreReason = CraneGameGlobals.ScoreReason.DEFAULT):
        self.sendUpdate('addScore', [avId, amount, reason.to_astron()])

    def setCraneSpawn(self, spawn, toonId):
        self.customSpawnOrderSet = True
        self.toonSpawnpointOrder[self.getParticipantIdsNotSpectating().index(toonId)] = spawn

    """
    FSM states
    """

    def enterInactive(self):
        self.notify.debug("enterInactive")

    def exitInactive(self):
        pass

    def __updateSkillProfile(self):
        # Todo: Not every crane game needs to be ranked. Add in an option to make a game unranked.
        
        # Determine the appropriate skill profile based on player count
        if len(self.getParticipantsNotSpectating()) == 2:
            skillKey = SkillProfileKey.CRANING_SOLOS
        elif len(self.getParticipantsNotSpectating()) >= 3:
            skillKey = SkillProfileKey.CRANING_FFA
        else:
            skillKey = None

        # Normal ranked game - set on both AI and clients
        self.b_setProfileSkillKey(skillKey)

    def enterPrepare(self):
        self.notify.debug("enterPrepare")

        # CRITICAL: Remove any existing play transition tasks to prevent double-scheduling
        # This ensures we don't have leftover tasks from previous prepare calls
        taskMgr.remove(self.uniqueName('start-game-task'))

        # Clear all status effects from any existing objects before recreating them
        if self.statusEffectSystem:
            # Clear from boss if it exists
            if self.boss:
                self.statusEffectSystem.removeAllStatusEffects(self.boss.doId)
            # Clear from all existing safes
            for safe in self.safes:
                if safe:
                    self.statusEffectSystem.removeAllStatusEffects(safe.doId)
        
        if not self.__bossExists():
            self.__makeBoss()
        self.boss.b_setAttackCode(ToontownGlobals.BossCogNoAttack)
        self.__makeCraningObjects()
        self.__resetCraningObjects()
        self.setupRuleset()
        # Setup spawnpoints BEFORE sending updates to ensure clients have correct order
        self.setupSpawnpoints()

        self.__updateSkillProfile()

        # Send round info to clients if this is a best-of match
        # Note: roundWins should persist across restarts (don't reset on restart)
        if self.bestOfValue > 1:
            self.d_setRoundInfo()
        
        # Calculate how long we should wait to actually start the game.
        # If more than 1 player is present, we want to have a delay present for a cutscene to play.
        delayTime = CraneGameGlobals.PREPARE_LATENCY_FACTOR
        if len(self.getParticipantIdsNotSpectating()) != 1:
            delayTime += CraneGameGlobals.PREPARE_DELAY
        print(f"[DistributedCraneGameAI] Scheduling play transition in {delayTime} seconds")
        taskMgr.doMethodLater(delayTime, self.gameFSM.request, self.uniqueName('start-game-task'), extraArgs=['play'])
        self.d_restart()

    def exitPrepare(self):
        self.notify.debug("exitPrepare")
        taskMgr.remove(self.uniqueName('start-game-task'))
        # Clean up match ready barrier if it exists
    
    def setMatchReady(self):
        """
        Called when a player reports they're ready for the match.
        This is distinct from the framework ready-up.
        """
        avId = self.air.getAvatarIdFromSender()
        self.notify.debug(f"Player {avId} is ready for match")
    
    def d_setPlayerReadyStatus(self, avId, isReady):
        """Broadcast player ready status to all clients"""
        self.sendUpdate('setPlayerReadyStatus', [avId, isReady])
    
    def d_requestMatchReady(self, matchPlayers, player1, player2):
        """Notify clients to show match ready-up UI"""
        self.sendUpdate('requestMatchReady', [matchPlayers, player1, player2])
    
    def d_startMatchCountdown(self):
        """Notify clients that all players are ready and countdown should start"""
        self.sendUpdate('startMatchCountdown', [])

    def enterPlay(self):
        self.notify.debug("enterPlay")
        taskMgr.remove(self.uniqueName("craneGameVictory"))
        self.battleThreeStart = globalClock.getFrameTime()

        # Stop toon passive healing.
        for toon in self.getParticipatingToons():
            toon.stopToonUp()

        # Listen to death messages.
        self.listenForToonDeaths()
        self.boss.clearSafeHelmetCooldowns()
        self.__resetCraningObjects()
        self.boss.prepareBossForBattle()

        # Make four goons up front to keep things interesting from the
        # beginning.
        self.makeGoon(side='EmergeA', forceNormalSpawn=True)
        self.makeGoon(side='EmergeB', forceNormalSpawn=True)
        taskName = self.uniqueName('NextGoon')
        taskMgr.remove(taskName)
        taskMgr.doMethodLater(2, self.__doInitialGoons, taskName)

        self.initializeComboTrackers()

        # Fix all toon's HP that are present.
        for toon in self.getParticipatingToons():
            if self.ruleset.FORCE_MAX_LAFF:
                toon.b_setMaxHp(self.ruleset.FORCE_MAX_LAFF_AMOUNT)

            if self.ruleset.HEAL_TOONS_ON_START:
                toon.b_setHp(toon.getMaxHp())

        self.toonsWon = False
        taskMgr.remove(self.uniqueName('times-up-task'))
        taskMgr.remove(self.uniqueName('post-times-up-task'))
        # If timer mode is active, end the crane round later
        if self.ruleset.TIMER_MODE:
            taskMgr.doMethodLater(self.ruleset.TIMER_MODE_TIME_LIMIT, self.__timesUp, self.uniqueName('times-up-task'))

        r = self.getScoringContext().get_round(self.currentRound).reset_scores()

        self.currentWinners = self.getParticipantIdsNotSpectating()

        self.d_setOvertime(CraneGameGlobals.OVERTIME_FLAG_DISABLE)

        # Laff drain?
        if self.ruleset.WANT_LAFF_DRAIN:
            self.startDrainingLaff(self.ruleset.LAFF_DRAIN_FREQUENCY)

        if self.ruleset.WANT_ELEMENTAL_MASTERY_MODE:
            self.startSafeEffectTask()

    def __applyRandomSafeEffects(self, task=None):
        """Apply random status effects to safes periodically"""
        for safe in self.safes:
            if not safe:
                continue
            
            # Skip the special helmet safe (index 0) - it should not receive elemental effects
            if safe.index == 0:
                continue
                
            safeDoId = safe.getDoId()
            hasEffect = self.statusEffectSystem.isObjectStatusEffected(safeDoId)
            
            # Debug logging
            if hasEffect:
                currentEffects = self.statusEffectSystem.getStatusEffects(safeDoId)
                self.notify.debug(f"Safe {safeDoId} already has effects: {currentEffects}, skipping")
            else:
                # 90% chance per safe to get an elemental effect
                if random.random() < 0.9:  # Always true for debugging
                    # Cancel any existing removal task for this safe first
                    existingTaskName = self.uniqueName(f'remove-effect-{safeDoId}')
                    taskMgr.remove(existingTaskName)
                    if existingTaskName in self.safeEffectTasks:
                        self.safeEffectTasks.remove(existingTaskName)
                    
                    statusEffect = random.choice(list(SAFE_ALLOWED_EFFECTS))
                    self.notify.debug(f"Applying {statusEffect} to safe {safeDoId}")
                    self.statusEffectSystem.b_applyStatusEffect(safeDoId, statusEffect)
                    # Store the safe's doId before creating the task
                    # Create task name
                    taskName = self.uniqueName(f'remove-effect-{safeDoId}')
                    # Remove the effect after 10 seconds
                    taskMgr.doMethodLater(10.0, lambda task, doId=safeDoId, effect=statusEffect: self.__removeSafeEffect(doId, effect) or task.done, taskName)
                    # Track the task
                    self.safeEffectTasks.add(taskName)
        return task.again

    def cancelSafeEffectRemovalTask(self, safeDoId):
        """Cancel the scheduled removal task for a safe's effect (called when effect is removed early, e.g., when safe hits boss)"""
        taskName = self.uniqueName(f'remove-effect-{safeDoId}')
        taskMgr.remove(taskName)
        if taskName in self.safeEffectTasks:
            self.safeEffectTasks.remove(taskName)
    
    def __removeSafeEffect(self, doId, effect):
        """Safely remove a status effect from a safe, handling the case where the safe no longer exists"""
        if not hasattr(self, 'statusEffectSystem') or not self.statusEffectSystem:
            return True
            
        # Check if the safe still exists
        safe = self.air.doId2do.get(doId)
        if not safe:
            return True
        
        # Check if the effect still exists before trying to remove it
        if not self.statusEffectSystem.hasStatusEffect(doId, effect):
            self.notify.debug(f"Safe {doId} effect {effect} already removed, skipping")
            return True
            
        # Remove the effect
        self.notify.debug(f"Removing effect {effect} from safe {doId}")
        self.statusEffectSystem.b_removeStatusEffect(doId, effect)
        return True

    def startSafeEffectTask(self):
        """Start the task that periodically applies effects to safes"""
        taskName = self.uniqueName('safe-effects')
        taskMgr.remove(taskName)
        self._allTaskNames.add(taskName)
        taskMgr.add(self.__applyRandomSafeEffects, taskName, delay=10.0)

    # Called when we actually run out of time, simply tell the clients we ran out of time then handle it later
    def __timesUp(self, task=None):
        taskMgr.remove(self.uniqueName('times-up-task'))

        # If we aren't about to enter overtime, feel free to end the game here.
        if not self.overtimeWillHappen:
            self.toonsWon = False
            self.gameFSM.request('victory')
            return

        self.__enterOvertimeMode()

    def enableOvertime(self):
        """
        Marks this game in progress to enter overtime when time is up.
        """
        self.overtimeWillHappen = True
        self.d_setOvertime(CraneGameGlobals.OVERTIME_FLAG_ENABLE)

    def __enterOvertimeMode(self):
        """
        Adjust the state of the boss to force this game to find a winner with more extreme measures.
        """
        self.currentlyInOvertime = True
        self.d_setOvertime(CraneGameGlobals.OVERTIME_FLAG_START)

        modifiers = [
            CraneGameGlobals.ModifierGoonCapIncreaser(tier=1),
            CraneGameGlobals.ModifierNoSafeHelmet(tier=1),
            CraneGameGlobals.ModifierTreasureHealDecreaser(tier=2),
            CraneGameGlobals.ModifierLaffDrain(tier=3),
            CraneGameGlobals.ModifierNoRevives(tier=1),
        ]

        self.applyModifiers(modifiers, updateClient=True)

        # Some modifiers don't exactly support us adding them mid-round based on state. Perform that logic here.
        self.getBoss().stopHelmets()
        self.startDrainingLaff(self.ruleset.LAFF_DRAIN_FREQUENCY)
        self.__cancelReviveTasks()
        self.d_setModifiers()

    def __checkOvertimeState(self):
        """
        Analyze the state of the game right now.
        We can only end overtime if it is impossible for someone else to win.
        """
        aliveToons = []
        for toon in self.getParticipantsNotSpectating():
            if toon.getHp() > 0:
                aliveToons.append(toon)

        allToonsAreDead = len(aliveToons) == 0
        winnerIsAlreadyDetermined = len(aliveToons) == 1 and len(self.currentWinners) == 1 and self.currentWinners[0] == aliveToons[0].getDoId()

        # Absolute freak incident check. Are we STILL tied for first place when everyone died?
        # If so, assign one lucky person the win.
        # In the future, we can probably determine this another way, but right now I am lazy.
        if allToonsAreDead and len(self.currentWinners) > 1:
            self.addScore(random.choice(self.currentWinners), 1, CraneGameGlobals.ScoreReason.COIN_FLIP)

        # End the game if everyone died or if it is literally impossible for the winner to be overtaken.
        if allToonsAreDead or winnerIsAlreadyDetermined:
            self.toonsWon = False
            self.gameFSM.request('victory')
            return

    def __getLaffDrainTaskName(self):
        return self.uniqueName('laff-drain-task')

    def stopDrainingLaff(self):
        taskMgr.remove(self.__getLaffDrainTaskName())

    def startDrainingLaff(self, interval):
        self.stopDrainingLaff()
        taskMgr.add(self.__laffDrainTask, self.__getLaffDrainTaskName(), delay=interval)

    def __laffDrainTask(self, task):
        """
        Drain all present toons' laff by one.
        """
        for toon in self.getParticipantsNotSpectating():
            if not self.ruleset.LAFF_DRAIN_KILLS_TOONS and toon.getHp() <= 1:
                continue
            self.damageToon(toon, 1)
        return task.again

    def __doInitialGoons(self, task):
        # Initial goons should ALWAYS come from doors
        self.makeGoon(side='EmergeA', forceNormalSpawn=True)
        self.makeGoon(side='EmergeB', forceNormalSpawn=True)
        self.goonCache = (None, 0)
        self.waitForNextGoon(10)
        self.__cancelReviveTasks()

    def __cancelReviveTasks(self):
        """
        Cleanup function to cancel any impending revives.
        """
        for toonId in self.getParticipants():
            taskMgr.remove(self.uniqueName(f"reviveToon-{toonId}"))

    def exitPlay(self):

        for comboTracker in self.comboTrackers.values():
            comboTracker.finishCombo()

        # Get rid of all the CFO objects.
        self.deleteAllTreasures()
        self.stopGoons()
        self.__resetCraningObjects()
        self.deleteAllTreasures()
        taskMgr.remove(self.uniqueName('times-up-task'))
        taskName = self.uniqueName('NextGoon')
        taskMgr.remove(taskName)
        taskMgr.remove(self.uniqueName('droneStun'))

        self.stopDrainingLaff()
        self.currentlyInOvertime = False
        self.overtimeWillHappen = False
        self.d_setOvertime(CraneGameGlobals.OVERTIME_FLAG_DISABLE)
        
        # Clear any pending forfeit requests when exiting play
        self.pendingForfeitRequest = None
        self.forfeitConsents.clear()

        # Clear all status effects from boss and safes when exiting play
        if self.statusEffectSystem:
            # Clear from boss
            if self.boss:
                self.statusEffectSystem.removeAllStatusEffects(self.boss.doId)
            # Clear from all safes
            for safe in self.safes:
                if safe:
                    self.statusEffectSystem.removeAllStatusEffects(safe.doId)

        # Ignore death messages.
        self.ignoreToonDeaths()
        self.__cancelReviveTasks()

        for toon in self.getParticipatingToons():
            # Restart toon passive healing.
            toon.startToonUp(ToontownGlobals.PassiveHealFrequency)
            # Restore health.
            toon.b_setHp(toon.getMaxHp())
            # Clear all TNT/pies when round ends or restarts
            toon.b_setNumPies(0)

        if self.boss is not None:
            self.boss.cleanupBossBattle()

        craneTime = globalClock.getFrameTime()
        actualTime = craneTime - self.battleThreeStart
        timeToSend = 0.0 if self.ruleset.TIMER_MODE and not self.toonsWon else actualTime
        self.d_updateTimer(timeToSend)

    def __calculateTimeToSend(self):
        """
        Determine a proper time to send to the client to show on their timers.
        """
        craneTime = globalClock.getFrameTime()
        actualTime = craneTime - self.battleThreeStart
        return actualTime if not self.ruleset.TIMER_MODE else self.ruleset.TIMER_MODE_TIME_LIMIT - actualTime

    def d_updateTimer(self, time=None):
        if time is None:
            time = self.__calculateTimeToSend()
        self.sendUpdate('updateTimer', [time])

    def d_restart(self):
        self.sendUpdate('restart', [])

    def d_setOvertime(self, flag):
        self.sendUpdate('setOvertime', [flag])

    def enterVictory(self):
        highest_scorers = self.getHighestScorers()

        # If nobody is in the lead, check if this is a single-player forfeit
        if len(highest_scorers) == 0:
            participants = self.getParticipantIdsNotSpectating()
            # If there's only one participant, they should be declared the victor (even if they forfeited)
            if len(participants) == 1:
                victorId = participants[0]
                self.sendUpdate("declareVictor", [victorId])
                self.getScoringContext().get_round(self.currentRound).set_winners([victorId])
                # Single round match - end the game
                taskMgr.doMethodLater(5, self.gameOver, self.uniqueName("craneGameVictory"), extraArgs=[])
                return
            # Otherwise, go to next round (shouldn't normally happen)
            self.sendUpdate("declareVictor", [0])
            taskMgr.doMethodLater(5, self.__startNextRound, self.uniqueName("craneGameNextRound"), extraArgs=[])
            return

        # If multiple people are in the lead (?) then just pick the first person. Otherwise, it will be THE winner.
        victorId = highest_scorers[0]
        self.getScoringContext().get_round(self.currentRound).set_winners(highest_scorers)

        # Handle best-of matches
        if self.bestOfValue > 1:
            # Track round wins
            self.roundWins[victorId] = self.roundWins.get(victorId, 0) + 1

            winsNeeded = (self.bestOfValue + 1) // 2
            
            # Send round info to clients
            self.d_setRoundInfo()
            
            # Check if match is complete
            if self.roundWins[victorId] >= winsNeeded:
                # Match is complete
                self.sendUpdate("declareVictor", [victorId])
                taskMgr.doMethodLater(5, self.gameOver, self.uniqueName("craneGameVictory"), extraArgs=[])
            else:
                # Round is complete, but match continues
                self.sendUpdate("declareVictor", [victorId])
                taskMgr.doMethodLater(3, self.__startNextRound, self.uniqueName("craneGameNextRound"), extraArgs=[])
        else:
            # Single round match
            self.sendUpdate("declareVictor", [victorId])
            taskMgr.doMethodLater(5, self.gameOver, self.uniqueName("craneGameVictory"), extraArgs=[])

        # Clean up all status effects from boss and safes before cleanup
        if self.statusEffectSystem:
            # Clear all status effects from the boss
            if self.boss:
                self.statusEffectSystem.removeAllStatusEffects(self.boss.doId)

            # Clear all status effects from all safes
            for safe in self.safes:
                if safe:
                    self.statusEffectSystem.removeAllStatusEffects(safe.doId)

        # Clean up all drones before cleaning up other objects
        if self.boss and hasattr(self.boss, 'drones'):
            for drone in list(self.boss.drones):
                if drone:
                    drone.vanishWithPoof()
            self.boss.drones = []

        # Reset drone cooldowns for all players and broadcast the reset
        self.droneCooldowns.clear()
        self.sendUpdate('clearAllDroneCooldowns', [])

        self.__deleteCraningObjects()
        self.__deleteBoss()

    def getWinners(self):

        # Find who has most round wins.
        most = -1
        for avId, wins in self.roundWins.items():
            if wins > most:
                most = wins

        # Filter who has most round wins
        winners = []
        for avId, wins in self.roundWins.items():
            if wins == most:
                winners.append(avId)

        return winners


    def exitVictory(self):
        taskMgr.remove(self.uniqueName("craneGameVictory"))
        taskMgr.remove(self.uniqueName("craneGameNextRound"))

    def enterCleanup(self):
        self.notify.debug("enterCleanup")
        self.gameFSM.request('inactive')

    def exitCleanup(self):
        pass

    def handleSpotStatusChanged(self, spotIndex, isPlayer):
        """
        Called when the leader changes a spot's status between Player and Spectator
        """
        if spotIndex >= len(self.avIdList):
            return
            
        avId = self.avIdList[spotIndex]
        currentSpectators = list(self.getSpectators())
        
        if isPlayer and avId in currentSpectators:
            currentSpectators.remove(avId)
        elif not isPlayer and avId not in currentSpectators:
            currentSpectators.append(avId)
            
        self.b_setSpectators(currentSpectators)
        # Broadcast the spot status change to all clients
        self.sendUpdate('updateSpotStatus', [spotIndex, isPlayer])

        self.__updateSkillProfile()

    def addModifier(self, modifierEnum, tier=1):
        """Handle request to add a modifier from the client"""
        # Only allow the leader to add modifiers
        avId = self.air.getAvatarIdFromSender()
        if not self.hasHost() or avId != self.getHost():
            self.notify.warning(f"Non-leader {avId} attempted to add modifier")
            return
        
        # Check if modifier already exists
        for mod in self.modifiers:
            if mod.MODIFIER_ENUM == modifierEnum:
                self.notify.warning(f"Modifier {modifierEnum} already exists")
                return
        
        # Get the modifier class and create instance
        if modifierEnum in CraneGameGlobals.CFORulesetModifierBase.MODIFIER_SUBCLASSES:
            modifierClass = CraneGameGlobals.CFORulesetModifierBase.MODIFIER_SUBCLASSES[modifierEnum]
            modifier = modifierClass(tier)
            
            # Add to desired modifiers so it persists across game restarts
            self.desiredModifiers.append(modifier)
            
            self.applyModifier(modifier, updateClient=True)
        else:
            self.notify.warning(f"Unknown modifier enum: {modifierEnum}")
    
    def removeModifier(self, modifierEnum):
        """Handle request to remove a modifier from the client"""
        # Only allow the leader to remove modifiers
        avId = self.air.getAvatarIdFromSender()
        if not self.hasHost() or avId != self.getHost():
            self.notify.warning(f"Non-leader {avId} attempted to remove modifier")
            return
        
        # Find and remove the modifier from both lists
        removedMod = None
        
        # Remove from current modifiers
        for i, mod in enumerate(self.modifiers):
            if mod.MODIFIER_ENUM == modifierEnum:
                removedMod = self.modifiers.pop(i)
                break
        
        # Remove from desired modifiers so it doesn't come back on restart
        for i, mod in enumerate(self.desiredModifiers):
            if mod.MODIFIER_ENUM == modifierEnum:
                self.desiredModifiers.pop(i)
                break
        
        if removedMod:
            # Rebuild ruleset from scratch without the removed modifier
            self.__rebuildRuleset()
        else:
            self.notify.warning(f"Modifier {modifierEnum} not found to remove")
    
    def __rebuildRuleset(self):
        """Rebuild the ruleset from scratch with current modifiers"""
        # Reset to base ruleset
        self.ruleset = CraneGameGlobals.CraneGameRuleset()
        
        # Reapply all remaining modifiers
        for modifier in self.modifiers:
            modifier.apply(self.ruleset)
        
        self.ruleset.validate()
        
        # Update clients
        self.d_setRawRuleset()
        self.d_setModifiers()
        
        # Update boss if it exists
        if self.getBoss() is not None:
            self.getBoss().setRuleset(self.ruleset)
    
    def requestDeployDrone(self, slotIndex=0):
        """Handle request to deploy a drone from client."""
        # Check if drones are enabled
        if not self.ruleset.WANT_DRONES:
            avId = self.air.getAvatarIdFromSender()
            self.notify.warning(f"Client {avId} attempted to deploy drone but drones are disabled")
            return
        avId = self.air.getAvatarIdFromSender()
        if avId not in self.getParticipantIdsNotSpectating():
            return
        
        # Validate slot index
        if slotIndex < 0 or slotIndex > 2:
            self.notify.warning(f'Invalid slot index {slotIndex} from {avId}')
            return
        
        # Check cooldown (90 seconds = 1.5 minutes)
        currentTime = globalClock.getFrameTime()
        DRONE_COOLDOWN = 90  # Integer seconds for DC compatibility
        
        # Initialize per-slot cooldown dict if needed
        if avId not in self.droneCooldowns:
            self.droneCooldowns[avId] = {}
        
        # Check if this specific slot is on cooldown
        if slotIndex in self.droneCooldowns[avId]:
            nextAvailableTime = self.droneCooldowns[avId][slotIndex]
            if currentTime < nextAvailableTime:
                # Still on cooldown
                remainingTime = nextAvailableTime - currentTime
                self.notify.debug(f'Drone slot {slotIndex} on cooldown for {avId}, {remainingTime:.1f}s remaining')
                return
        
        # Get selected drone type for this slot
        from toontown.minigame.craning import CraneGameGlobals
        droneType = self.getDroneTypeForToon(avId, slotIndex)
        if droneType is None:
            # Default to laser if no type selected
            droneType = CraneGameGlobals.DroneType.LASER
        
        # Set cooldown for this specific slot
        self.droneCooldowns[avId][slotIndex] = currentTime + DRONE_COOLDOWN
        
        # Broadcast cooldown to all clients (avId, slotIndex, duration)
        self.sendUpdate('setDroneCooldown', [avId, slotIndex, int(DRONE_COOLDOWN)])
        
        if self.boss:
            self.boss.deployDroneForToon(avId, None, droneType)
    
    def getDroneTypeForToon(self, avId, slotIndex=0):
        """Get the selected drone type for a toon's slot."""
        from toontown.minigame.craning import CraneGameGlobals
        if avId not in self.selectedDroneTypes:
            # Default: all slots are laser
            return CraneGameGlobals.DroneType.LASER
        slotTypes = self.selectedDroneTypes[avId]
        if slotIndex >= len(slotTypes):
            return CraneGameGlobals.DroneType.LASER
        return slotTypes[slotIndex]
    
    def setDroneTypeForToon(self, avId, slotIndex, droneTypeValue):
        """Set the selected drone type for a toon's slot."""
        from toontown.minigame.craning import CraneGameGlobals
        if avId not in self.selectedDroneTypes:
            # Initialize with default (Laser, Heal, Explodey)
            self.selectedDroneTypes[avId] = [
                CraneGameGlobals.DroneType.LASER,
                CraneGameGlobals.DroneType.HEAL,
                CraneGameGlobals.DroneType.EXPLODEY
            ]
        
        # Convert value to enum if needed
        if isinstance(droneTypeValue, int):
            droneType = CraneGameGlobals.DroneType(droneTypeValue)
        else:
            droneType = droneTypeValue
        
        # Update the slot
        if slotIndex >= 0 and slotIndex < 3:
            self.selectedDroneTypes[avId][slotIndex] = droneType
            # Broadcast to all clients
            self.sendUpdate('setDroneTypeForToon', [avId, slotIndex, droneType.value])
            
            # Save the updated setup to the toon's database
            # Only save if all 3 slots have been set (to avoid partial saves)
            if len(self.selectedDroneTypes[avId]) == 3:
                toon = self.air.doId2do.get(avId)
                if toon and hasattr(toon, 'b_setDroneSetup'):
                    # Convert DroneType enums to uint8 values
                    setup = [dt.value for dt in self.selectedDroneTypes[avId]]
                    toon.b_setDroneSetup(setup)
    
    def requestCleanupDrones(self):
        """Handle request to clean up all drones."""
        if self.boss and hasattr(self.boss, 'drones'):
            # Clean up all active drones
            for drone in list(self.boss.drones):
                if drone:
                    # Send vanishWithPoof to clients, which will then requestDelete
                    drone.vanishWithPoof()
            self.boss.drones = []
    
    def requestForfeit(self):
        """Handle forfeit request from a player"""
        avId = self.air.getAvatarIdFromSender()
        
        # Validate player is in the game and not spectating
        if avId not in self.getParticipantIdsNotSpectating():
            self.notify.warning(f"Player {avId} tried to request forfeit but is not a participant")
            return
        
        # If there's already a pending request, cancel it first
        if self.pendingForfeitRequest is not None:
            self.cancelForfeitRequest()
        
        # Start a new forfeit request
        self.pendingForfeitRequest = avId
        self.forfeitConsents.clear()
        self.forfeitConsents.add(avId)  # Requester automatically consents
        
        # Send forfeit request to all players
        self.d_requestForfeit(avId)
    
    def confirmForfeit(self):
        """Handle forfeit confirmation from a player"""
        avId = self.air.getAvatarIdFromSender()
        
        # Validate there's a pending request
        if self.pendingForfeitRequest is None:
            self.notify.warning(f"Player {avId} tried to confirm forfeit but there's no pending request")
            return
        
        # Validate player is in the game and not spectating
        if avId not in self.getParticipantIdsNotSpectating():
            self.notify.warning(f"Player {avId} tried to confirm forfeit but is not a participant")
            return
        
        # Add consent
        self.forfeitConsents.add(avId)
        
        # Check if all players have consented
        participants = self.getParticipantIdsNotSpectating()
        if len(self.forfeitConsents) >= len(participants):
            # All players have consented, proceed with forfeit
            self.executeForfeit(self.pendingForfeitRequest)
        else:
            # Update clients with current consent status
            self.d_updateForfeitConsents(list(self.forfeitConsents))
    
    def rejectForfeit(self):
        """Handle forfeit rejection from a player - cancels the forfeit immediately"""
        avId = self.air.getAvatarIdFromSender()
        
        # Validate there's a pending request
        if self.pendingForfeitRequest is None:
            self.notify.warning(f"Player {avId} tried to reject forfeit but there's no pending request")
            return
        
        # Validate player is in the game and not spectating
        if avId not in self.getParticipantIdsNotSpectating():
            self.notify.warning(f"Player {avId} tried to reject forfeit but is not a participant")
            return
        
        # Rejection cancels the forfeit immediately
        self.pendingForfeitRequest = None
        self.forfeitConsents.clear()
        self.d_cancelForfeit()
    
    def cancelForfeitRequest(self):
        """Cancel the current forfeit request (called from client)"""
        avId = self.air.getAvatarIdFromSender()
        
        # Only the requester can cancel
        if self.pendingForfeitRequest != avId:
            self.notify.warning(f"Player {avId} tried to cancel forfeit but is not the requester")
            return
        
        if self.pendingForfeitRequest is not None:
            self.pendingForfeitRequest = None
            self.forfeitConsents.clear()
            self.d_cancelForfeit()
    
    def executeForfeit(self, forfeiterAvId):
        """Execute the forfeit - put the requester in last place"""
        # Forfeit: Set the forfeiter's score to ensure they come in last place
        context = self.getScoringContext()
        _round = context.get_round(self.currentRound)
        score = _round.get_score(forfeiterAvId)
        num_players = len(self.getParticipantsNotSpectating())
        
        if num_players == 1:
            # Single player game - just subtract their score to put them at 0 or negative
            # No need to give bonus points since they're the only player
            self.addScore(forfeiterAvId, -score, reason=CraneGameGlobals.ScoreReason.FORFEIT)
        else:
            # Multi-player game - ensure all other participants have points so forfeiter is last
            for toon in self.getParticipantsNotSpectating():
                if toon.getDoId() != forfeiterAvId:
                    self.addScore(toon.getDoId(), 2000, reason=CraneGameGlobals.ScoreReason.KILLING_BLOW)
            
            self.addScore(forfeiterAvId, -score, reason=CraneGameGlobals.ScoreReason.FORFEIT)
        
        # Clear forfeit request state
        self.pendingForfeitRequest = None
        self.forfeitConsents.clear()
        
        # Notify clients to clean up forfeit dialogs (without showing cancellation message)
        self.d_cleanupForfeitDialogs()
        
        # End the game
        self.gameFSM.request('victory')
    
    def d_requestForfeit(self, requesterAvId):
        """Send forfeit request to all clients"""
        self.sendUpdate('setRequestForfeit', [requesterAvId])
    
    def d_updateForfeitConsents(self, consentAvIds):
        """Update clients with current consent status"""
        self.sendUpdate('setUpdateForfeitConsents', [consentAvIds])
    
    def d_cancelForfeit(self):
        """Notify clients that forfeit request was cancelled"""
        self.sendUpdate('setCancelForfeit', [])
    
    def d_cleanupForfeitDialogs(self):
        """Clean up forfeit dialogs without showing cancellation message (used when forfeit is executed)"""
        self.sendUpdate('setCleanupForfeitDialogs', [])
    
    def requestRestart(self):
        """Handle restart request from a player"""
        avId = self.air.getAvatarIdFromSender()
        
        # Validate player is in the game and not spectating
        if avId not in self.getParticipantIdsNotSpectating():
            self.notify.warning(f"Player {avId} tried to request restart but is not a participant")
            return
        
        # If there's already a pending request, cancel it first
        if self.pendingRestartRequest is not None:
            self.cancelRestartRequest()
        
        # Start a new restart request
        self.pendingRestartRequest = avId
        self.restartConsents.clear()
        self.restartConsents.add(avId)  # Requester automatically consents
        
        # Send restart request to all players
        self.d_requestRestart(avId)
    
    def confirmRestart(self):
        """Handle restart confirmation from a player"""
        avId = self.air.getAvatarIdFromSender()
        
        # Validate there's a pending request
        if self.pendingRestartRequest is None:
            self.notify.warning(f"Player {avId} tried to confirm restart but there's no pending request")
            return
        
        # Validate player is in the game and not spectating
        if avId not in self.getParticipantIdsNotSpectating():
            self.notify.warning(f"Player {avId} tried to confirm restart but is not a participant")
            return
        
        # Add consent
        self.restartConsents.add(avId)
        
        # Check if all players have consented
        participants = self.getParticipantIdsNotSpectating()
        if len(self.restartConsents) >= len(participants):
            # All players have consented, proceed with restart
            self.executeRestart(self.pendingRestartRequest)
        else:
            # Update clients with current consent status
            self.d_updateRestartConsents(list(self.restartConsents))
    
    def rejectRestart(self):
        """Handle restart rejection from a player - cancels the restart immediately"""
        avId = self.air.getAvatarIdFromSender()
        
        # Validate there's a pending request
        if self.pendingRestartRequest is None:
            self.notify.warning(f"Player {avId} tried to reject restart but there's no pending request")
            return
        
        # Validate player is in the game and not spectating
        if avId not in self.getParticipantIdsNotSpectating():
            self.notify.warning(f"Player {avId} tried to reject restart but is not a participant")
            return
        
        # Rejection cancels the restart immediately
        self.pendingRestartRequest = None
        self.restartConsents.clear()
        self.d_cancelRestart()
    
    def cancelRestartRequest(self):
        """Cancel the current restart request (called from client)"""
        avId = self.air.getAvatarIdFromSender()
        
        # Only the requester can cancel
        if self.pendingRestartRequest != avId:
            self.notify.warning(f"Player {avId} tried to cancel restart but is not the requester")
            return
        
        if self.pendingRestartRequest is not None:
            self.pendingRestartRequest = None
            self.restartConsents.clear()
            self.d_cancelRestart()
    
    def executeRestart(self, requesterAvId):
        """Execute the restart - transition to cleanup then prepare"""
        # Clear restart request state
        self.pendingRestartRequest = None
        self.restartConsents.clear()
        
        # Notify clients to clean up restart dialogs (without showing cancellation message)
        self.d_cleanupRestartDialogs()
        
        # Restart the game
        self.gameFSM.request("cleanup")
        self.gameFSM.request('prepare')
            
    def d_requestRestart(self, requesterAvId):
        """Send restart request to all clients"""
        self.sendUpdate('setRequestRestart', [requesterAvId])
    
    def d_updateRestartConsents(self, consentAvIds):
        """Update clients with current consent status"""
        self.sendUpdate('setUpdateRestartConsents', [consentAvIds])
    
    def d_cancelRestart(self):
        """Notify clients that restart request was cancelled"""
        self.sendUpdate('setCancelRestart', [])
    
    def d_cleanupRestartDialogs(self):
        """Clean up restart dialogs without showing cancellation message (used when restart is executed)"""
        self.sendUpdate('setCleanupRestartDialogs', [])
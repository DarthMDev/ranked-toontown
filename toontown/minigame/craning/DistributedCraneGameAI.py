import random

from direct.fsm import ClassicFSM
from direct.fsm import State
from direct.task.TaskManagerGlobal import taskMgr
from panda3d.core import CollisionInvSphere, CollisionNode, CollisionSphere, CollisionTube, NodePath
from toontown.minigame.craning.objects.DistributedCashbotCraneAI import DistributedCashbotCraneAI
from toontown.minigame.craning.objects.DistributedCashbotHeavyCraneAI import DistributedCashbotHeavyCraneAI
from toontown.minigame.craning.objects.DistributedCashbotSafeAI import DistributedCashbotSafeAI
from toontown.minigame.craning.objects.DistributedCashbotSideCraneAI import DistributedCashbotSideCraneAI
from toontown.minigame.craning.objects.DistributedCashbotBoomBarrowAI import DistributedCashbotBoomBarrowAI
from toontown.minigame.craning.objects.DistributedCashbotFloatingPlatformAI import DistributedCashbotFloatingPlatformAI
from toontown.minigame.DistributedMinigameAI import DistributedMinigameAI
from toontown.minigame.craning import CraneGameGlobals
from toontown.minigame.craning.boss.DistributedCashbotBossAI import DistributedCashbotBossAI
from toontown.toonbase import ToontownGlobals
from toontown.minigame.utils.statuseffects.DistributedStatusEffectSystemAI import DistributedStatusEffectSystemAI
from toontown.minigame.utils.statuseffects.StatusEffectGlobals import StatusEffect
from toontown.minigame.craning.managers.server.PlayerManagerAI import PlayerManagerAI
from toontown.minigame.craning.managers.server.ModifierManagerAI import ModifierManagerAI
from toontown.minigame.craning.managers.server.DroneManagerAI import DroneManagerAI
from toontown.minigame.craning.managers.server.StatusEffectManagerAI import StatusEffectManagerAI
from toontown.minigame.craning.managers.server.ComboManagerAI import ComboManagerAI
from toontown.minigame.craning.managers.server.TreasureManagerAI import TreasureManagerAI
from toontown.minigame.craning.managers.server.GoonManagerAI import GoonManagerAI
from toontown.minigame.craning.managers.server.OvertimeManagerAI import OvertimeManagerAI
from toontown.minigame.craning.managers.server.ForfeitRestartManagerAI import ForfeitRestartManagerAI
from toontown.minigame.craning.managers.server.ScoreManagerAI import ScoreManagerAI
from toontown.minigame.craning.managers.server.RoundManagerAI import RoundManagerAI


class DistributedCraneGameAI(DistributedMinigameAI):
    DESPERATION_MODE_ACTIVATE_THRESHOLD = 1800

    # If time limit is enabled, how many seconds should be remaining to activate when an overtake happens?
    OVERTIME_OVERTAKE_ACTIVATION_THRESHOLD = 15

    def __init__(self, air, minigameId):
        DistributedMinigameAI.__init__(self, air, minigameId)
        air.memoryDebugger.track_weak(self, "CraneGame")
        self.setProfileSkillKey(None)  # By default, no ranked mode.

        # Core game objects
        self.cranes = []
        self.safes = []
        self.goons = []
        self.boomBarrows = []  # List to hold boom barrow objects
        self.floatingPlatforms = []  # List to hold floating platform objects
        self.boss = None

        # We need a scene to do the collision detection in.
        self.scene = NodePath('scene')

        self.toonsWon = False

        # Initialize managers
        self.playerManager = PlayerManagerAI(self)
        self.modifierManager = ModifierManagerAI(self)
        self.droneManager = DroneManagerAI(self)
        self.statusEffectManager = StatusEffectManagerAI(self)
        self.comboManager = ComboManagerAI(self)
        self.treasureManager = TreasureManagerAI(self)
        self.goonManager = GoonManagerAI(self)
        self.overtimeManager = OvertimeManagerAI(self)
        self.forfeitRestartManager = ForfeitRestartManagerAI(self)
        self.scoreManager = ScoreManagerAI(self)
        self.roundManager = RoundManagerAI(self)
        
        # Expose ruleset for backward compatibility and direct access
        # Ruleset is managed by ModifierManager but exposed here for convenience
        self.ruleset = CraneGameGlobals.CraneGameRuleset()
        
        # Reference to the group that created this minigame (if any)
        self.group = None

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

        self.statusEffectSystem: DistributedStatusEffectSystemAI | None = None

        # Memory leak prevention - track task names
        self._allTaskNames = set()

    # Property accessors for backward compatibility
    # These delegate to managers but allow direct access for convenience
    @property
    def currentRound(self):
        return self.roundManager.currentRound
    
    @currentRound.setter
    def currentRound(self, value):
        self.roundManager.currentRound = value
    
    @property
    def bestOfValue(self):
        return self.roundManager.bestOfValue
    
    @bestOfValue.setter
    def bestOfValue(self, value):
        self.roundManager.bestOfValue = value
    
    @property
    def roundWins(self):
        return self.roundManager.roundWins
    
    @property
    def currentWinners(self):
        return self.scoreManager.currentWinners
    
    @currentWinners.setter
    def currentWinners(self, value):
        self.scoreManager.currentWinners = value
    
    @property
    def overtimeWillHappen(self):
        return self.overtimeManager.overtimeWillHappen
    
    @overtimeWillHappen.setter
    def overtimeWillHappen(self, value):
        self.overtimeManager.overtimeWillHappen = value
    
    @property
    def currentlyInOvertime(self):
        return self.overtimeManager.currentlyInOvertime
    
    @currentlyInOvertime.setter
    def currentlyInOvertime(self, value):
        self.overtimeManager.currentlyInOvertime = value
    
    @property
    def treasures(self):
        return self.treasureManager.treasures
    
    @property
    def grabbingTreasures(self):
        return self.treasureManager.grabbingTreasures
    
    @property
    def recycledTreasures(self):
        return self.treasureManager.recycledTreasures
    
    @property
    def comboTrackers(self):
        return self.comboManager.comboTrackers
    
    @property
    def rollModsOnStart(self):
        return self.modifierManager.rollModsOnStart
    
    @rollModsOnStart.setter
    def rollModsOnStart(self, value):
        self.modifierManager.rollModsOnStart = value
    
    @property
    def numModsWanted(self):
        return self.modifierManager.numModsWanted
    
    @numModsWanted.setter
    def numModsWanted(self, value):
        self.modifierManager.numModsWanted = value
    
    @property
    def desiredModifiers(self):
        return self.modifierManager.desiredModifiers
    
    @property
    def droneCooldowns(self):
        return self.droneManager.droneCooldowns
    
    @property
    def selectedDroneTypes(self):
        return self.droneManager.selectedDroneTypes
    
    @property
    def goonCache(self):
        return self.goonManager.goonCache
    
    @goonCache.setter
    def goonCache(self, value):
        self.goonManager.goonCache = value
    
    @property
    def goonMinScale(self):
        return self.goonManager.goonMinScale
    
    @goonMinScale.setter
    def goonMinScale(self, value):
        self.goonManager.goonMinScale = value
    
    @property
    def goonMaxScale(self):
        return self.goonManager.goonMaxScale
    
    @goonMaxScale.setter
    def goonMaxScale(self, value):
        self.goonManager.goonMaxScale = value
    
    @property
    def customSpawnOrderSet(self):
        return self.playerManager.customSpawnOrderSet
    
    @customSpawnOrderSet.setter
    def customSpawnOrderSet(self, value):
        self.playerManager.customSpawnOrderSet = value
    
    @property
    def toonSpawnpointOrder(self):
        return self.playerManager.toonSpawnpointOrder
    
    @toonSpawnpointOrder.setter
    def toonSpawnpointOrder(self, value):
        self.playerManager.toonSpawnpointOrder = value
    
    @property
    def originalSpawnOrder(self):
        return self.roundManager.originalSpawnOrder
    
    @originalSpawnOrder.setter
    def originalSpawnOrder(self, value):
        self.roundManager.originalSpawnOrder = value
    
    @property
    def pendingForfeitRequest(self):
        """Backward compatibility property for MagicWord access"""
        return self.forfeitRestartManager.pendingForfeitRequest
    
    @property
    def pendingRestartRequest(self):
        """Backward compatibility property for MagicWord access"""
        return self.forfeitRestartManager.pendingRestartRequest
    
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
        # Clean up event listeners (delegated to PlayerManager)
        self.playerManager.cleanup()
        
        # Clean up all tracked tasks
        for taskName in self._allTaskNames:
            taskMgr.remove(taskName)
        self._allTaskNames.clear()
        
        # Clean up safe effect tasks (delegated to StatusEffectManager)
        self.statusEffectManager.cleanup()
        
        # Clean up specific known tasks
        taskMgr.remove(self.uniqueName('times-up-task'))
        taskMgr.remove(self.uniqueName('post-times-up-task'))
        taskMgr.remove(self.uniqueName('NextGoon'))
        taskMgr.remove(self.uniqueName('safe-effects'))
        taskMgr.remove(self.uniqueName('laff-drain-task'))
        taskMgr.remove(self.uniqueName('craneGameVictory'))
        taskMgr.remove(self.uniqueName('craneGameNextRound'))
        taskMgr.remove(self.uniqueName('startNextRound'))
        
        # Clean up combo trackers (delegated to ComboManager)
        self.comboManager.cleanupComboTrackers()
        
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
        self.modifierManager.setupRuleset()
        self.playerManager.setupSpawnpoints()
        # Reset custom spawn order flag for new games (not restarts)
        self.playerManager.resetCustomSpawnOrder()
        # Reset round information for new games
        self.roundManager.reset()
        
        # Clear any pending forfeit/restart requests
        self.forfeitRestartManager.reset()
        
        # Initialize best-of settings
        self.roundManager.d_setBestOf()
        self.roundManager.d_setRoundInfo()

    def setupRuleset(self):
        """Delegate to ModifierManager"""
        self.modifierManager.setupRuleset()

    # Delegate modifier methods to ModifierManager
    def applyModifiers(self, modifiers: list[CraneGameGlobals.CFORulesetModifierBase], updateClient=False):
        self.modifierManager.applyModifiers(modifiers, updateClient)
    
    def applyModifier(self, modifier: CraneGameGlobals.CFORulesetModifierBase, updateClient=False):
        self.modifierManager.applyModifier(modifier, updateClient)
    
    def removeModifier(self, modifierClass):
        self.modifierManager.removeModifier(modifierClass)
    
    def d_setRawRuleset(self):
        self.modifierManager.d_setRawRuleset()
    
    def d_setModifiers(self):
        self.modifierManager.d_setModifiers()
    
    def rollRandomModifiers(self):
        return self.modifierManager.rollRandomModifiers()
    
    def setGroup(self, group):
        """
        Set the group reference for this minigame.
        This allows the minigame to save its state back to the group.
        """
        self.group = group
    
    def saveStateToGroup(self):
        """
        Save the current ruleset and modifiers to the group config.
        This ensures the state persists for play-again scenarios.
        """
        if self.group is None:
            self.notify.debug('saveStateToGroup: No group reference, cannot save')
            return
        
        # Save ruleset
        rulesetStruct = self.modifierManager.getRawRuleset()
        self.group.setMinigameRuleset(self.minigameId, rulesetStruct)
        self.notify.debug(f'saveStateToGroup: Saved ruleset for minigame {self.minigameId}')
        
        # Save modifiers
        modifierStructs = self.modifierManager._getRawModifierList()
        self.group.setMinigameModifiers(self.minigameId, modifierStructs)
        self.notify.debug(f'saveStateToGroup: Saved {len(modifierStructs)} modifiers for minigame {self.minigameId}')
    
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

        # Goons are managed by GoonManager and will be cleaned up by __deleteCraningObjects
        # Don't clear here as __deleteCraningObjects handles it
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

    # Delegate player management methods to PlayerManager
    def listenForToonDeaths(self):
        self.playerManager.listenForToonDeaths()
    
    def ignoreToonDeaths(self):
        self.playerManager.ignoreToonDeaths()
    
    def toonDied(self, toon):
        self.playerManager.toonDied(toon)
    
    def reviveToon(self, toonId: int) -> None:
        self.playerManager.reviveToon(toonId)
    
    def getHighestScorers(self):
        """Delegate to ScoreManager"""
        return self.scoreManager.getHighestScorers()

    def d_updateCombo(self, avId, comboLength):
        self.comboManager.d_updateCombo(avId, comboLength)

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

    # Delegate combo methods to ComboManager
    def initializeComboTrackers(self):
        self.comboManager.initializeComboTrackers()
    
    def incrementCombo(self, avId, amount):
        self.comboManager.incrementCombo(avId, amount)
    
    def resetCombo(self, avId):
        self.comboManager.resetCombo(avId)
    
    def getComboLength(self, avId):
        return self.comboManager.getComboLength(avId)
    
    def getComboAmount(self, avId):
        return self.comboManager.getComboAmount(avId)
    
    def cleanupComboTrackers(self):
        self.comboManager.cleanupComboTrackers()

    # Delegate treasure methods to TreasureManager
    def grabAttempt(self, avId, treasureId):
        self.treasureManager.grabAttempt(avId, treasureId)
    
    def deleteAllTreasures(self):
        self.treasureManager.deleteAllTreasures()
    
    def makeTreasure(self, goon):
        """Delegate to TreasureManager"""
        self.treasureManager.makeTreasure(goon)

    # Delegate goon methods to GoonManager
    def getMaxGoons(self):
        return self.goonManager.getMaxGoons()
    
    def makeGoon(self, side=None, forceNormalSpawn=False, fallingChance=0.5):
        self.goonManager.makeGoon(side, forceNormalSpawn, fallingChance)
    
    def waitForNextGoon(self, delayTime):
        self.goonManager.waitForNextGoon(delayTime)
    
    def stopGoons(self):
        self.goonManager.stopGoons()
    
    def doNextGoon(self, task):
        return self.goonManager.doNextGoon(task)

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

    # Delegate spawn/round methods to managers
    def setupSpawnpoints(self):
        self.playerManager.setupSpawnpoints()
    
    def resetCustomSpawnOrder(self):
        self.playerManager.resetCustomSpawnOrder()
    
    def d_setToonSpawnpointOrder(self):
        self.playerManager.d_setToonSpawnpointOrder()
    
    def updateSpawnOrder(self, newOrder):
        self.playerManager.updateSpawnOrder(newOrder)
    
    def setBestOf(self, value):
        self.roundManager.setBestOf(value)
    
    def d_setBestOf(self):
        self.roundManager.d_setBestOf()
    
    def d_setRoundInfo(self):
        self.roundManager.d_setRoundInfo()
    
    def nextRound(self):
        self.roundManager.nextRound()

    def getRawRuleset(self):
        return self.modifierManager.getRawRuleset()

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
        crane = self.air.doId2do.get(craneId)
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
                    self.scoreManager.addScore(avId, self.ruleset.POINTS_IMPACT, reason=CraneGameGlobals.ScoreReason.FULL_IMPACT)
            else:
                if impact == 1.0:
                    self.scoreManager.addScore(avId, self.ruleset.POINTS_IMPACT, reason=CraneGameGlobals.ScoreReason.FULL_IMPACT)
        self.scoreManager.addScore(avId, damage)

        # DOT damage should not contribute to combos
        if not isDOT:
            # Combo tracking handled by ComboManager
            self.comboManager.incrementCombo(avId, (self.comboManager.getComboLength(avId) + 1.0) / 10.0 * damage)

        # The CFO has been defeated, proceed to Victory state
        if self.boss.bossDamage >= self.ruleset.CFO_MAX_HP:
            self.scoreManager.addScore(avId, self.ruleset.POINTS_KILLING_BLOW, CraneGameGlobals.ScoreReason.KILLING_BLOW)
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
            
            self.scoreManager.addScore(avId, points, reason=reason)
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
        self.scoreManager.addScore(attributeToAvId, damage)

        # DOT damage should not contribute to combos
        if not isDOT:
            self.comboManager.incrementCombo(attributeToAvId, (self.comboManager.getComboLength(attributeToAvId) + 1.0) / 10.0 * damage)

        # The CFO has been defeated, proceed to Victory state
        if self.boss.bossDamage >= self.ruleset.CFO_MAX_HP:
            self.scoreManager.addScore(attributeToAvId, self.ruleset.POINTS_KILLING_BLOW, CraneGameGlobals.ScoreReason.KILLING_BLOW)
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

    # Delegate scoring methods to ScoreManager
    def addScore(self, avId: int, amount: int, reason: CraneGameGlobals.ScoreReason = CraneGameGlobals.ScoreReason.DEFAULT):
        self.scoreManager.addScore(avId, amount, reason)
    
    def d_addScore(self, avId: int, amount: int, reason: CraneGameGlobals.ScoreReason = CraneGameGlobals.ScoreReason.DEFAULT):
        self.scoreManager.d_addScore(avId, amount, reason)

    def setCraneSpawn(self, spawn, toonId):
        self.playerManager.customSpawnOrderSet = True
        self.playerManager.toonSpawnpointOrder[self.getParticipantIdsNotSpectating().index(toonId)] = spawn
        self.playerManager.d_setToonSpawnpointOrder()

    """
    FSM states
    """

    def enterInactive(self):
        self.notify.debug("enterInactive")

    def exitInactive(self):
        pass

    def __updateSkillProfile(self):
        """Delegate to PlayerManager"""
        self.playerManager.updateSkillProfile()

    def enterPrepare(self):
        self.notify.debug("enterPrepare")

        # CRITICAL: Remove any existing play transition tasks to prevent double-scheduling
        # This ensures we don't have leftover tasks from previous prepare calls
        taskMgr.remove(self.uniqueName('start-game-task'))

        # CRITICAL: Clean up all existing game objects before creating new ones
        # This prevents duplicates when restarting rounds
        self.__deleteCraningObjects()
        
        # Clean up all drones before recreating objects
        self.droneManager.requestCleanupDrones()
        self.droneManager.clearAllCooldowns()

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
        if self.roundManager.bestOfValue > 1:
            self.roundManager.d_setRoundInfo()
        
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
        self.goonManager.makeGoon(side='EmergeA', forceNormalSpawn=True)
        self.goonManager.makeGoon(side='EmergeB', forceNormalSpawn=True)
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
            taskMgr.doMethodLater(self.ruleset.TIMER_MODE_TIME_LIMIT, self._timesUp, self.uniqueName('times-up-task'))

        r = self.getScoringContext().get_round(self.roundManager.currentRound).reset_scores()

        self.scoreManager.currentWinners = self.getParticipantIdsNotSpectating()

        self.d_setOvertime(CraneGameGlobals.OVERTIME_FLAG_DISABLE)

        # Laff drain?
        if self.ruleset.WANT_LAFF_DRAIN:
            self.startDrainingLaff(self.ruleset.LAFF_DRAIN_FREQUENCY)

        if self.ruleset.WANT_ELEMENTAL_MASTERY_MODE:
            self.statusEffectManager.startSafeEffectTask()
    
    # Delegate status effect methods to StatusEffectManager
    def cancelSafeEffectRemovalTask(self, safeDoId):
        self.statusEffectManager.cancelSafeEffectRemovalTask(safeDoId)

    # Called when we actually run out of time, simply tell the clients we ran out of time then handle it later
    def _timesUp(self, task=None):
        taskMgr.remove(self.uniqueName('times-up-task'))

        # If we aren't about to enter overtime, feel free to end the game here.
        if not self.overtimeManager.overtimeWillHappen:
            self.toonsWon = False
            self.gameFSM.request('victory')
            return

        self.overtimeManager.enterOvertimeMode()

    def enableOvertime(self):
        """
        Marks this game in progress to enter overtime when time is up.
        """
        self.overtimeManager.overtimeWillHappen = True
        self.d_setOvertime(CraneGameGlobals.OVERTIME_FLAG_ENABLE)

    def __enterOvertimeMode(self):
        """
        Adjust the state of the boss to force this game to find a winner with more extreme measures.
        """
        self.overtimeManager.currentlyInOvertime = True
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
        winnerIsAlreadyDetermined = len(aliveToons) == 1 and len(self.scoreManager.currentWinners) == 1 and self.scoreManager.currentWinners[0] == aliveToons[0].getDoId()

        # Absolute freak incident check. Are we STILL tied for first place when everyone died?
        # If so, assign one lucky person the win.
        # In the future, we can probably determine this another way, but right now I am lazy.
        if allToonsAreDead and len(self.scoreManager.currentWinners) > 1:
            self.scoreManager.addScore(random.choice(self.scoreManager.currentWinners), 1, CraneGameGlobals.ScoreReason.COIN_FLIP)

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
        self.goonManager.makeGoon(side='EmergeA', forceNormalSpawn=True)
        self.goonManager.makeGoon(side='EmergeB', forceNormalSpawn=True)
        self.goonManager.resetGoonCache()
        self.goonManager.waitForNextGoon(10)
        # Revive tasks cleanup handled by PlayerManager

    def __cancelReviveTasks(self):
        """Cleanup function to cancel any impending revives - delegated to PlayerManager"""
        # This is handled by PlayerManager.cleanup() but kept for compatibility
        pass

    def exitPlay(self):

        self.comboManager.finishAllCombos()

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
        self.overtimeManager.reset()
        
        # Clear any pending forfeit/restart requests when exiting play
        self.forfeitRestartManager.reset()

        # Clear all status effects from boss and safes when exiting play
        if self.statusEffectSystem:
            # Clear from boss
            if self.boss:
                self.statusEffectSystem.removeAllStatusEffects(self.boss.doId)
            # Clear from all safes (delegated to StatusEffectManager)
            self.statusEffectManager.clearAllSafeEffects()

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

    def _calculateTimeToSend(self):
        """
        Determine a proper time to send to the client to show on their timers.
        """
        craneTime = globalClock.getFrameTime()
        actualTime = craneTime - self.battleThreeStart
        return actualTime if not self.ruleset.TIMER_MODE else self.ruleset.TIMER_MODE_TIME_LIMIT - actualTime
    
    def __calculateTimeToSend(self):
        """Alias for _calculateTimeToSend for backward compatibility"""
        return self._calculateTimeToSend()

    def d_updateTimer(self, time=None):
        if time is None:
            time = self.__calculateTimeToSend()
        self.sendUpdate('updateTimer', [time])

    def d_restart(self):
        self.sendUpdate('restart', [])

    def d_setOvertime(self, flag):
        self.overtimeManager.d_setOvertime(flag)

    def enterVictory(self):
        # Save state to group before ending (for play-again scenarios)
        self.saveStateToGroup()
        
        highest_scorers = self.getHighestScorers()

        # If nobody is in the lead, check if this is a single-player forfeit
        if len(highest_scorers) == 0:
            participants = self.getParticipantIdsNotSpectating()
            # If there's only one participant, they should be declared the victor (even if they forfeited)
            if len(participants) == 1:
                victorId = participants[0]
                self.sendUpdate("declareVictor", [victorId])
                self.getScoringContext().get_round(self.roundManager.currentRound).set_winners([victorId])
                # Single round match - end the game
                taskMgr.doMethodLater(5, self.gameOver, self.uniqueName("craneGameVictory"), extraArgs=[])
                return
            # Otherwise, go to next round (shouldn't normally happen)
            self.sendUpdate("declareVictor", [0])
            taskMgr.doMethodLater(5, self.roundManager._startNextRound, self.uniqueName("craneGameNextRound"), extraArgs=[])
            return

        # If multiple people are in the lead (?) then just pick the first person. Otherwise, it will be THE winner.
        victorId = highest_scorers[0]
        self.getScoringContext().get_round(self.roundManager.currentRound).set_winners(highest_scorers)

        # Handle best-of matches
        if self.roundManager.bestOfValue > 1:
            # Track round wins
            self.roundManager.recordRoundWin(victorId)
            
            # Send round info to clients
            self.roundManager.d_setRoundInfo()
            
            # Check if match is complete
            if self.roundManager.isMatchComplete(victorId):
                # Match is complete
                self.sendUpdate("declareVictor", [victorId])
                taskMgr.doMethodLater(5, self.gameOver, self.uniqueName("craneGameVictory"), extraArgs=[])
            else:
                # Round is complete, but match continues
                self.sendUpdate("declareVictor", [victorId])
                taskMgr.doMethodLater(3, self.roundManager._startNextRound, self.uniqueName("craneGameNextRound"), extraArgs=[])
        else:
            # Single round match
            self.sendUpdate("declareVictor", [victorId])
            taskMgr.doMethodLater(5, self.gameOver, self.uniqueName("craneGameVictory"), extraArgs=[])

        # Clean up all status effects from boss and safes before cleanup
        if self.statusEffectSystem:
            # Clear all status effects from the boss
            if self.boss:
                self.statusEffectSystem.removeAllStatusEffects(self.boss.doId)
            # Clear from all safes (delegated to StatusEffectManager)
            self.statusEffectManager.clearAllSafeEffects()

        # Clean up all drones before cleaning up other objects
        self.droneManager.requestCleanupDrones()
        
        # Reset drone cooldowns for all players and broadcast the reset
        self.droneManager.clearAllCooldowns()

        self.__deleteCraningObjects()
        self.__deleteBoss()

    def getWinners(self):
        """Delegate to RoundManager"""
        return self.roundManager.getWinners()


    def exitVictory(self):
        taskMgr.remove(self.uniqueName("craneGameVictory"))
        taskMgr.remove(self.uniqueName("craneGameNextRound"))

    def enterCleanup(self):
        self.notify.debug("enterCleanup")
        # Clean up all game objects before cleanup state completes
        # This ensures objects are deleted when transitioning to cleanup
        self.__deleteCraningObjects()
        # Clean up all drones
        self.droneManager.requestCleanupDrones()
        self.droneManager.clearAllCooldowns()
        self.gameFSM.request('inactive')

    def exitCleanup(self):
        pass

    def handleSpotStatusChanged(self, spotIndex, isPlayer):
        """Delegate to PlayerManager"""
        self.playerManager.handleSpotStatusChanged(spotIndex, isPlayer)

    def addModifier(self, modifierEnum, tier=1):
        """Handle request to add a modifier from the client"""
        # Only allow the leader to add modifiers
        avId = self.air.getAvatarIdFromSender()
        if not self.hasHost() or avId != self.getHost():
            self.notify.warning(f"Non-leader {avId} attempted to add modifier")
            return
        
        # Check if modifier already exists
        for mod in self.modifierManager.modifiers:
            if mod.MODIFIER_ENUM == modifierEnum:
                self.notify.warning(f"Modifier {modifierEnum} already exists")
                return
        
        # Get the modifier class and create instance
        if modifierEnum in CraneGameGlobals.CFORulesetModifierBase.MODIFIER_SUBCLASSES:
            modifierClass = CraneGameGlobals.CFORulesetModifierBase.MODIFIER_SUBCLASSES[modifierEnum]
            modifier = modifierClass(tier)
            
            # Add to desired modifiers so it persists across game restarts
            self.modifierManager.desiredModifiers.append(modifier)
            
            self.applyModifier(modifier, updateClient=True)
        else:
            self.notify.warning(f"Unknown modifier enum: {modifierEnum}")
    
    # removeModifier already delegated above - this was a duplicate
    
    # Delegate drone methods to DroneManager
    def requestDeployDrone(self, slotIndex=0):
        self.droneManager.requestDeployDrone(slotIndex)
    
    def getDroneTypeForToon(self, avId, slotIndex=0):
        return self.droneManager.getDroneTypeForToon(avId, slotIndex)
    
    def setDroneTypeForToon(self, avId, slotIndex, droneTypeValue):
        self.droneManager.setDroneTypeForToon(avId, slotIndex, droneTypeValue)
    
    def requestCleanupDrones(self):
        self.droneManager.requestCleanupDrones()
    
    # Delegate forfeit methods to ForfeitRestartManager
    def requestForfeit(self):
        self.forfeitRestartManager.requestForfeit()
    
    def confirmForfeit(self):
        self.forfeitRestartManager.confirmForfeit()
    
    def rejectForfeit(self):
        self.forfeitRestartManager.rejectForfeit()
    
    def cancelForfeitRequest(self):
        self.forfeitRestartManager.cancelForfeitRequest()
    
    # Delegate restart methods to ForfeitRestartManager
    def requestRestart(self):
        self.forfeitRestartManager.requestRestart()
    
    def confirmRestart(self):
        self.forfeitRestartManager.confirmRestart()
    
    def rejectRestart(self):
        self.forfeitRestartManager.rejectRestart()
    
    def cancelRestartRequest(self):
        self.forfeitRestartManager.cancelRestartRequest()
    
    def executeForfeit(self, forfeiterAvId):
        """Execute forfeit - delegate to ForfeitRestartManager"""
        self.forfeitRestartManager.executeForfeit(forfeiterAvId)
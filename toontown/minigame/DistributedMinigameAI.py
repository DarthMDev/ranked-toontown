from direct.directnotify.DirectNotifyGlobal import directNotify
from direct.distributed import DistributedObjectAI
from direct.distributed.ClockDelta import *
from direct.fsm import ClassicFSM
from direct.fsm import State

from toontown.ai.ToonBarrier import *
from toontown.shtiker import PurchaseManagerAI
from . import MinigameGlobals
from .utils.scoring_context import ScoringContext
from ..matchmaking.skill_profile_keys import SkillProfileKey
from ..matchmaking.skill_rating import OpenSkillMatch, OpenSkillMatchDeltaResults

EXITED = 0
EXPECTED = 1
JOINED = 2
READY = 3
DEFAULT_POINTS = 1
MAX_POINTS = 7
JOIN_TIMEOUT = 40.0 + MinigameGlobals.latencyTolerance
READY_TIMEOUT = MinigameGlobals.MaxLoadTime + MinigameGlobals.rulesDuration + MinigameGlobals.latencyTolerance
EXIT_TIMEOUT = 20.0 + MinigameGlobals.latencyTolerance


class DistributedMinigameAI(DistributedObjectAI.DistributedObjectAI):
    notify = directNotify.newCategory('DistributedMinigameAI')

    def __init__(self, air, minigameId):

        DistributedObjectAI.DistributedObjectAI.__init__(self, air)
        self.minigameId = minigameId
        self.frameworkFSM = ClassicFSM.ClassicFSM('DistributedMinigameAI', [
            State.State('frameworkOff', self.enterFrameworkOff, self.exitFrameworkOff, ['frameworkWaitClientsJoin']),
            State.State('frameworkWaitClientsJoin', self.enterFrameworkWaitClientsJoin, self.exitFrameworkWaitClientsJoin,['frameworkWaitClientsReady', 'frameworkWaitClientsExit', 'frameworkCleanup']),
            State.State('frameworkWaitClientsReady', self.enterFrameworkWaitClientsReady,self.exitFrameworkWaitClientsReady,['frameworkGame', 'frameworkWaitClientsExit', 'frameworkCleanup']),
            State.State('frameworkGame', self.enterFrameworkGame, self.exitFrameworkGame,['frameworkWaitClientsExit', 'frameworkCleanup']),
            State.State('frameworkWaitClientsExit', self.enterFrameworkWaitClientsExit,self.exitFrameworkWaitClientsExit, ['frameworkCleanup']),
            State.State('frameworkCleanup', self.enterFrameworkCleanup, self.exitFrameworkCleanup, ['frameworkOff'])
        ], 'frameworkOff', 'frameworkOff')

        self.frameworkFSM.enterInitialState()

        # The host of this minigame. It's possible that there isn't a host. If that's the case, this is probably a queued ranked game.
        # Hosts will have the ability to tweak game settings, and toggle things such as cheats.
        self.host: int | None = None
        self.avIdList = []
        self._spectators = []
        self.stateDict = {}
        self.difficultyOverride = None
        self.trolleyZoneOverride = None
        self.context = ScoringContext()

        # The SR context to use for this minigame. If none, we assume this is not a ranked game.
        self.skillProfileKey: SkillProfileKey | None = SkillProfileKey.MINIGAMES
        
        # Generic modifier and round management (available to all minigames)
        from toontown.minigame.utils.managers import ModifierManagerAI, RoundManagerAI
        self.modifierManager = ModifierManagerAI(self)
        self.roundManager = RoundManagerAI(self)
        
        # Reference to the group that created this minigame (if any)
        self.group = None

    def hasHost(self) -> bool:
        """
        Checks if there is a host of this minigame that has elevated privileges.
        """
        return self.host is not None and self.host != 0

    def getHost(self) -> int:
        """
        Gets the host of this minigame. This can be 0, indicating there is no host and the server should determine
        logical flow. (Have to use 0 so astron will work....)
        """
        return self.host if self.host is not None else 0

    def setHost(self, avId: int | None) -> None:
        """
        Updates the host of this match. You can set this to None/0 to make the host surrender their privileges.
        """
        self.host = avId
        if self.host == 0:
            self.host = None

    def d_setHost(self, avId: int | None) -> None:
        """
        Tells the client that a certain avatar is considered the host. Can pass in 0 or None to clear.
        """
        self.sendUpdate('setHost', [avId if avId is not None else 0])

    def b_setHost(self, avId: int | None) -> None:
        """
        Sets the host of this match. Can pass in 0 or None to clear.
        Also tells the client that a certain avatar is considered the host. Can pass in 0 or None to clear.
        """
        self.setHost(avId)
        self.d_setHost(avId)

    def isRanked(self) -> bool:
        """
        Is this minigame going to affect ELO/SR ratings upon completion?
        Override and set to True if you would like to automatically apply ranked calculations.
        """
        # Check if ranked system is enabled globally
        if hasattr(self.air, 'config') and not self.air.config.GetBool('want-ranked-system', True):
            return False
        return self.skillProfileKey is not None and len(self.getParticipantIdsNotSpectating()) > 1

    def getSkillProfileKey(self) -> str:
        """
        What is the minigame going to store ELO/SR ratings under on the toons?
        This key CAN be dynamic, but it needs to be consistent with how you want to store skill.
        """
        return self.skillProfileKey.value if self.skillProfileKey is not None else ''

    def setProfileSkillKey(self, key: SkillProfileKey | None) -> None:
        self.skillProfileKey = key

    def b_setProfileSkillKey(self, key: SkillProfileKey):
        self.setProfileSkillKey(key)
        self.d_setSkillProfileKey(key)

    def d_setSkillProfileKey(self, key: SkillProfileKey) -> None:
        """
        Updates the client on what skill profile key we are using given the context of the minigame.
        Call at any time to sync the client. Sending an empty string will inform the client that the current
        minigame is not going to be ranked. If self.isRanked() is False, an empty string will be automatically provided
        assuming the game is unranked.
        """
        self.sendUpdate('setSkillProfileKey', [key.value if self.isRanked() else ''])

    def d_setReadyTimeout(self, timeout):
        """
        Send the ready timeout duration to clients so they can display a countdown timer.
        """
        self.sendUpdate('setReadyTimeout', [timeout])

    def addChildGameFSM(self, gameFSM):
        self.frameworkFSM.getStateNamed('frameworkGame').addChild(gameFSM)

    def removeChildGameFSM(self, gameFSM):
        self.frameworkFSM.getStateNamed('frameworkGame').removeChild(gameFSM)

    def setExpectedAvatars(self, avIds):
        self.avIdList = avIds
        self.numPlayers = len(self.avIdList)
        self.notify.debug('BASE: setExpectedAvatars: expecting avatars: ' + str(self.avIdList))

    def setSpectators(self, avIds):
        self._spectators = avIds

    def getSpectators(self) -> list[int]:
        """
        Returns a list of toon IDs that are flagged as spectators.
        """
        return list(self._spectators)

    def b_setSpectators(self, avIds):
        self.setSpectators(avIds)
        self.d_setSpectators(avIds)

    def d_setSpectators(self, avIds):
        self.sendUpdate('setSpectators', [avIds])

    def isSpectating(self, avId) -> bool:
        """
        Returns True if the given toon id is flagged as a spectator.
        """
        return avId in self._spectators

    def setTrolleyZone(self, trolleyZone):
        self.trolleyZone = trolleyZone

    def setDifficultyOverrides(self, difficultyOverride, trolleyZoneOverride):
        self.difficultyOverride = difficultyOverride
        if self.difficultyOverride is not None:
            self.difficultyOverride = MinigameGlobals.QuantizeDifficultyOverride(difficultyOverride)
        self.trolleyZoneOverride = trolleyZoneOverride
        return

    def _playing(self):
        if not hasattr(self, 'gameFSM'):
            return False
        if self.gameFSM.getCurrentState() == None:
            return False
        return self.gameFSM.getCurrentState().getName() == 'play'

    def _inState(self, states):
        if not hasattr(self, 'gameFSM'):
            return False
        if self.gameFSM.getCurrentState() == None:
            return False
        return self.gameFSM.getCurrentState().getName() in makeList(states)

    def generate(self):
        DistributedObjectAI.DistributedObjectAI.generate(self)
        self.frameworkFSM.request('frameworkWaitClientsJoin')

    def delete(self):
        self.notify.debug('BASE: delete: deleting AI minigame object')
        
        # Clean up combo trackers
        if hasattr(self, 'comboTrackers'):
            self.cleanupComboTrackers()
        
        # Clean up status effect system
        if hasattr(self, 'statusEffectSystem') and self.statusEffectSystem:
            self.statusEffectSystem.requestDelete()
            self.statusEffectSystem = None
        
        # Ignore all events
        self.ignoreAll()
        
        taskMgr.remove(self.uniqueName('no-host-start-delay'))
        DistributedObjectAI.DistributedObjectAI.delete(self)

    def isSinglePlayer(self):
        if self.numPlayers == 1:
            return 1
        else:
            return 0

    def getScoringContext(self) -> ScoringContext:
        return self.context

    def getParticipants(self) -> list[int]:
        """
        Returns a list of toon IDs that are present in this minigame.
        """
        return self.avIdList

    def getParticipantIdsNotSpectating(self):
        """
        Gets a list of toon IDs that are not spectating.
        These are toons that should be considered to be active players in the minigame.
        We should always opt in to call this method instead of self.avIdList directly for game logic if possible.
        """
        toons = []
        for avId in self.avIdList:
            if avId not in self.getSpectators():
                toons.append(avId)
        return toons

    def getParticipantsNotSpectating(self):
        """
        Gets a list of DistributedToon instances that are not spectating.
        These are toons that should be considered to be active players in the minigame.
        We should always opt in to call this method instead of self.avIdList directly for game logic if possible.
        """
        toons = []
        for avId in self.getParticipantIdsNotSpectating():
            toon = self.air.getDo(avId)
            if toon:
                toons.append(toon)
        return toons

    def getParticipatingToons(self):
        """
        Returns a list of DistributedToon objects that are present in this minigame.
        """
        toons = []
        for avId in self.getParticipants():
            toon = self.air.getDo(avId)
            if toon:
                toons.append(toon)
        return toons

    def getTrolleyZone(self):
        return self.trolleyZone

    def getDifficultyOverrides(self):
        response = [self.difficultyOverride, self.trolleyZoneOverride]
        if response[0] is None:
            response[0] = MinigameGlobals.NoDifficultyOverride
        else:
            response[0] *= MinigameGlobals.DifficultyOverrideMult
            response[0] = int(response[0])
        if response[1] is None:
            response[1] = MinigameGlobals.NoTrolleyZoneOverride
        return response

    def b_setGameReady(self):
        self.setGameReady()
        self.d_setGameReady()

    def d_setGameReady(self):
        self.notify.debug('BASE: Sending setGameReady')
        self.sendUpdate('setGameReady', [])

    def setGameReady(self):
        self.notify.debug('BASE: setGameReady: game ready with avatars: %s' % self.avIdList)
        self.normalExit = 1

    def b_setGameStart(self, timestamp):
        self.d_setGameStart(timestamp)
        self.setGameStart(timestamp)

    def d_setGameStart(self, timestamp):
        self.notify.debug('BASE: Sending setGameStart')
        self.sendUpdate('setGameStart', [timestamp])

    def setGameStart(self, timestamp):
        self.notify.debug('BASE: setGameStart')

    def b_setGameExit(self):
        self.d_setGameExit()
        self.setGameExit()

    def d_setGameExit(self):
        self.notify.debug('BASE: Sending setGameExit')
        self.sendUpdate('setGameExit', [])

    def setGameExit(self):
        self.notify.debug('BASE: setGameExit')

    def setGameAbort(self):
        self.notify.debug('BASE: setGameAbort')
        self.normalExit = 0
        self.sendUpdate('setGameAbort', [])
        self.frameworkFSM.request('frameworkCleanup')

    def handleExitedAvatar(self, avId):
        self.notify.warning('BASE: handleExitedAvatar: avatar id exited: ' + str(avId))
        # If the exiting avatar is a spectator, just clean them up but don't abort the game
        if self.isSpectating(avId):
            self.notify.debug('BASE: handleExitedAvatar: avatar %s is a spectator, cleaning up without aborting game' % avId)
            self.stateDict[avId] = EXITED
            # Remove them from spectators list if they're still in it
            if avId in self._spectators:
                spectators = list(self._spectators)
                spectators.remove(avId)
                self.b_setSpectators(spectators)
            return
        self.stateDict[avId] = EXITED
        self.setGameAbort()

    def gameOver(self):
        self.notify.debug('BASE: gameOver')
        self.frameworkFSM.request('frameworkWaitClientsExit')

    def enterFrameworkOff(self):
        self.notify.debug('BASE: enterFrameworkOff')

    def exitFrameworkOff(self):
        pass

    def enterFrameworkWaitClientsJoin(self):
        self.notify.debug('BASE: enterFrameworkWaitClientsJoin')
        for avId in self.avIdList:
            self.stateDict[avId] = EXPECTED
            self.acceptOnce(self.air.getAvatarExitEvent(avId), self.handleExitedAvatar, extraArgs=[avId])

        def allAvatarsJoined(self = self):
            self.notify.debug('BASE: all avatars joined')
            self.b_setGameReady()
            self.frameworkFSM.request('frameworkWaitClientsReady')

        def handleTimeout(avIds, self = self):
            self.notify.debug('BASE: timed out waiting for clients %s to join' % avIds)
            self.setGameAbort()

        self.__barrier = ToonBarrier('waitClientsJoin', self.uniqueName('waitClientsJoin'), self.avIdList, JOIN_TIMEOUT, allAvatarsJoined, handleTimeout)

    def setAvatarJoined(self):
        if self.frameworkFSM.getCurrentState().getName() != 'frameworkWaitClientsJoin':
            self.notify.debug('BASE: Ignoring setAvatarJoined message')
            return
        avId = self.air.getAvatarIdFromSender()
        self.notify.debug('BASE: setAvatarJoined: avatar id joined: ' + str(avId))
        self.air.writeServerEvent('minigame_joined', avId, '%s|%s' % (self.minigameId, self.trolleyZone))
        self.stateDict[avId] = JOINED
        self.notify.debug('BASE: setAvatarJoined: new states: ' + str(self.stateDict))
        self.__barrier.clear(avId)

    def exitFrameworkWaitClientsJoin(self):
        self.__barrier.cleanup()
        del self.__barrier

    def enterFrameworkWaitClientsReady(self):
        self.notify.debug('BASE: enterFrameworkWaitClientsReady')

        def allAvatarsReady(self = self):
            self.notify.debug('BASE: all avatars ready')
            self.frameworkFSM.request('frameworkGame')

        def handleTimeout(avIds, self = self):
            self.notify.debug("BASE: timed out waiting for clients %s to report 'ready'" % avIds)
            # Instead of aborting, force all remaining players to be ready and start the game
            for avId in avIds:
                if avId in self.stateDict and self.stateDict[avId] != READY:
                    self.notify.debug(f"BASE: Forcing avatar {avId} to ready state due to timeout")
                    self.stateDict[avId] = READY
                    self.__barrier.clear(avId)
            # Check if all avatars are now ready and manually trigger if needed
            # (The barrier should auto-trigger, but this ensures it happens)
            allReady = all(self.stateDict.get(avId, None) == READY for avId in self.avIdList)
            if allReady:
                self.notify.debug("BASE: All avatars are now ready after timeout, starting game")
                allAvatarsReady()

        self.__barrier = ToonBarrier('waitClientsReady', self.uniqueName('waitClientsReady'), self.avIdList, READY_TIMEOUT, allAvatarsReady, handleTimeout)
        for avId in list(self.stateDict.keys()):
            if self.stateDict[avId] == READY:
                self.__barrier.clear(avId)

        # Send the timeout duration to clients so they can display a countdown timer
        self.d_setReadyTimeout(READY_TIMEOUT)

        self.notify.debug('  safezone: %s' % self.getSafezoneId())
        self.notify.debug('difficulty: %s' % self.getDifficulty())

    def setAvatarReady(self):
        if self.frameworkFSM.getCurrentState().getName() not in ['frameworkWaitClientsReady', 'frameworkWaitClientsJoin']:
            self.notify.debug('BASE: Ignoring setAvatarReady message')
            return
        avId = self.air.getAvatarIdFromSender()
        self.notify.debug('BASE: setAvatarReady: avatar id ready: ' + str(avId))
        self.stateDict[avId] = READY
        self.notify.debug('BASE: setAvatarReady: new avId states: ' + str(self.stateDict))
        if self.frameworkFSM.getCurrentState().getName() == 'frameworkWaitClientsReady':
            self.__barrier.clear(avId)

    def exitFrameworkWaitClientsReady(self):
        self.__barrier.cleanup()
        del self.__barrier

    def enterFrameworkGame(self):

        def __start(_=None):
            self.notify.debug('BASE: enterFrameworkGame')
            self.gameStartTime = globalClock.getRealTime()
            self.b_setGameStart(globalClockDelta.localToNetworkTime(self.gameStartTime))

        # If there is no host, we should give them a few seconds to prepare so we don't jumpscare them.
        # No host games only happen from queues, where the players will immediately ready up upon connecting.
        if not self.hasHost():
            taskMgr.doMethodLater(3, __start, self.uniqueName('no-host-start-delay'))
        else:
            __start()

    def exitFrameworkGame(self):
        taskMgr.remove(self.uniqueName('no-host-start-delay'))

    def enterFrameworkWaitClientsExit(self):
        self.notify.debug('BASE: enterFrameworkWaitClientsExit')
        self.b_setGameExit()

        def allAvatarsExited(self = self):
            self.notify.debug('BASE: all avatars exited')
            self.frameworkFSM.request('frameworkCleanup')

        def handleTimeout(avIds, self = self):
            self.notify.debug('BASE: timed out waiting for clients %s to exit' % avIds)
            self.frameworkFSM.request('frameworkCleanup')

        self.__barrier = ToonBarrier('waitClientsExit', self.uniqueName('waitClientsExit'), self.avIdList, EXIT_TIMEOUT, allAvatarsExited, handleTimeout)
        for avId in list(self.stateDict.keys()):
            if self.stateDict[avId] == EXITED:
                self.__barrier.clear(avId)

    def setAvatarExited(self):
        if self.frameworkFSM.getCurrentState().getName() != 'frameworkWaitClientsExit':
            self.notify.debug('BASE: Ignoring setAvatarExit message')
            return
        avId = self.air.getAvatarIdFromSender()
        self.notify.debug('BASE: setAvatarExited: avatar id exited: ' + str(avId))
        self.stateDict[avId] = EXITED
        self.notify.debug('BASE: setAvatarExited: new avId states: ' + str(self.stateDict))
        self.__barrier.clear(avId)

    def exitFrameworkWaitClientsExit(self):
        self.__barrier.cleanup()
        del self.__barrier

    def enterFrameworkCleanup(self):
        self.notify.debug('BASE: enterFrameworkCleanup: normalExit=%s' % self.normalExit)
        self.requestDelete()
        self.handleRegularPurchaseManager()
        self.frameworkFSM.request('frameworkOff')

    def adjustSkillRatings(self) -> OpenSkillMatchDeltaResults:

        # Query all profiles for this context.
        profiles = {}
        for av in self.getParticipantsNotSpectating():
            profiles[av.getDoId()] = av.getOrCreateSkillProfile(self.getSkillProfileKey())

        if len(profiles) == 0:
            self.notify.warning(f"Trolley game with {self.getParticipants()} avIds had no skill profiles for minigame {self.minigameId}, aborting ELO adjustment")
            return OpenSkillMatchDeltaResults()

        if len(profiles) == 1:
            self.notify.warning(f"Trolley game with {self.getParticipants()} avIds had only one participant and tried adjusting ELO in game {self.minigameId}, aborting ELO adjustment")
            return OpenSkillMatchDeltaResults()

        _model = self.skillProfileKey.get_model()

        # Create a match and add the players.
        match = OpenSkillMatch(_model)
        score_rankings = self.context.generate_score_rankings()

        # todo support teams. they are kind of hard to properly support until there is proper team support in trolley games.

        # Loop through all the profiles and add the player and their score.
        for player in profiles.values():
            match.add_player(player, score_rankings.get(player.identifier, 0))

        self.notify.warning(f"pre-openskill adjustment: {[p for p in profiles.values()]}")

        # Adjust!
        results = match.adjust_ratings()

        # Save all the data to the toons.
        updates = []
        for av in self.getParticipantsNotSpectating():
            profile_update = match.new_player_data.get(av.getDoId(), None)
            if profile_update is not None:
                av.addSkillProfile(profile_update)
                updates.append(profile_update)
            av.d_syncSkillProfiles()

        # Updates UD with SR rating cache for leaderboard tracking.
        self.air.leaderboardManager.reportMatchToUd(updates, [[toon.getDoId(), toon.getName()] for toon in self.getParticipantsNotSpectating()])

        return results

    def handleRegularPurchaseManager(self):

        # Adjust ratings if desired.
        deltas = None
        if self.isRanked():
            deltas = self.adjustSkillRatings()
            self.notify.warning(f"post-openskill adjustment deltas: {[p for p in deltas.get_player_results().values()]}")

        points = self.context.get_total_points()
        scoreList = [max(0, points.get(player, 0)) for player in self.avIdList]

        pm = PurchaseManagerAI.PurchaseManagerAI(self.air, self.avIdList, scoreList, self.minigameId, self.trolleyZone, previousHost=self.getHost(), spectators=self.getSpectators(), profileDeltas=deltas.get_player_results().values() if deltas is not None else None)
        pm.generateWithRequired(self.zoneId)

    def exitFrameworkCleanup(self):
        pass

    def requestGroupDebug(self):
        """Called from client to request group debug data to be printed on AI."""
        avId = self.air.getAvatarIdFromSender()
        self.notify.info('\n' + '=' * 80)
        self.notify.info('AI GROUP DEBUG DATA (requested by avatar %s)' % avId)
        self.notify.info('=' * 80)
        
        if not hasattr(self.air, 'groupManager') or self.air.groupManager is None:
            self.notify.info('GroupManagerAI not found!')
            self.notify.info('=' * 80 + '\n')
            return
        
        gm = self.air.groupManager
        
        # Find group for this avatar
        toon = self.air.getDo(avId)
        if toon is None:
            self.notify.info('Avatar %s not found!' % avId)
            self.notify.info('=' * 80 + '\n')
            return
        
        group = gm.getGroup(toon)
        if group is None:
            self.notify.info('Avatar %s is not in any group' % avId)
            self.notify.info('\nGROUP MANAGER STATS')
            self.notify.info('  Total groups: %s' % len(gm.groups))
            if gm.groups:
                self.notify.info('\n  All groups:')
                for idx, g in enumerate(gm.groups, 1):
                    leader = self.air.getDo(g.getLeader())
                    leaderName = leader.getName() if leader else 'Unknown'
                    self.notify.info('    %s. Group ID: %s, Leader: %s (%s), Members: %s' % 
                                   (idx, g.groupId, leaderName, g.getLeader(), len(g.getMemberIds())))
            self.notify.info('=' * 80 + '\n')
            return
        
        from toontown.toonbase import ToontownGlobals
        from toontown.groups import GroupGlobals
        
        # Basic Group Info
        self.notify.info('\nBASIC GROUP INFO')
        self.notify.info('  Group ID: %s' % group.groupId)
        leader = self.air.getDo(group.getLeader())
        leaderName = leader.getName() if leader else 'Unknown'
        self.notify.info('  Leader: %s (%s)' % (leaderName, group.getLeader()))
        self.notify.info('  Capacity: %s / %s' % (group.getMemberCount(), group.getCapacity()))
        self.notify.info('  On Cooldown: %s' % ('Yes' if group.onCooldown() else 'No'))
        
        # Members
        members = group.getMembers()
        participants = [m for m in members if m.team != GroupGlobals.TEAM_SPECTATOR]
        spectators = [m for m in members if m.team == GroupGlobals.TEAM_SPECTATOR]
        
        self.notify.info('\nMEMBERS (%s total)' % len(members))
        self.notify.info('  Participants: %s' % len(participants))
        self.notify.info('  Spectators: %s' % len(spectators))
        
        if members:
            for i, member in enumerate(members, 1):
                toon = self.air.getDo(member.avId)
                toonName = toon.getName() if toon else 'Unknown'
                teamStr = 'Spectator' if member.team == GroupGlobals.TEAM_SPECTATOR else 'Participant'
                statusStr = {GroupGlobals.STATUS_LEADER: 'Leader', 
                            GroupGlobals.STATUS_READY: 'Ready',
                            GroupGlobals.STATUS_UNREADY: 'Not Ready'}.get(member.status, f'Status {member.status}')
                self.notify.info('    %s. %s (%s) - %s, %s' % (i, toonName, member.avId, teamStr, statusStr))
        
        # Minigame Config
        config = group.getMinigameConfig()
        minigameName = ToontownGlobals.MinigameId2Name.get(config.minigameId, f'Unknown ({config.minigameId})')
        
        self.notify.info('\nMINIGAME CONFIG')
        self.notify.info('  Minigame: %s (ID: %s)' % (minigameName, config.minigameId))
        self.notify.info('  Trolley Zone: %s' % config.trolleyZone)
        host = self.air.getDo(config.hostId) if config.hostId else None
        hostName = host.getName() if host else 'Unknown'
        self.notify.info('  Host: %s (%s)' % (hostName, config.hostId))
        self.notify.info('  Desired Minigame (legacy): %s' % group.desiredMinigame)
        
        # Ruleset Data
        rulesetStruct = config.getRuleset(config.minigameId)
        if rulesetStruct is not None:
            self.notify.info('\nRULESET DATA')
            if config.minigameId == ToontownGlobals.CraneGameId:
                # Deserialize and show key Crane Game ruleset values
                try:
                    from toontown.minigame.craning import CraneGameGlobals
                    ruleset = CraneGameGlobals.CraneGameRuleset.fromStruct(rulesetStruct)
                    self.notify.info('  CFO Max HP: %s' % ruleset.CFO_MAX_HP)
                    self.notify.info('  Timer Mode: %s' % ('Yes' if ruleset.TIMER_MODE else 'No'))
                    if ruleset.TIMER_MODE:
                        self.notify.info('  Timer Limit: %s seconds' % ruleset.TIMER_MODE_TIME_LIMIT)
                    self.notify.info('  Side Cranes: %s' % ('Yes' if ruleset.WANT_SIDECRANES else 'No'))
                    self.notify.info('  Drones: %s' % ('Yes' if ruleset.WANT_DRONES else 'No'))
                    self.notify.info('  Back Wall: %s' % ('Yes' if ruleset.WANT_BACKWALL else 'No'))
                    self.notify.info('  Remove Impact Cap: %s' % ('Yes' if ruleset.REMOVE_IMPACT_CAP else 'No'))
                except Exception as e:
                    self.notify.info('  (Error deserializing ruleset: %s)' % e)
                    self.notify.info('  Raw struct length: %s' % len(rulesetStruct))
            else:
                self.notify.info('  (Ruleset data present but format unknown for this minigame)')
                self.notify.info('  Raw struct length: %s' % len(rulesetStruct))
        else:
            self.notify.info('\nRULESET DATA: None (using defaults)')
        
        # Modifiers Data
        # Use self.minigameId instead of config.minigameId to ensure we're checking the correct minigame
        # config.minigameId might be stale or different from the actual minigame being played
        actualMinigameId = getattr(self, 'minigameId', config.minigameId)
        self.notify.debug(f"Debug: Checking modifiers for minigameId={actualMinigameId}, config.minigameId={config.minigameId}")
        self.notify.debug(f"Debug: modifiersData keys={list(config.modifiersData.keys())}")
        modifierStructs = config.getModifiers(actualMinigameId)
        if modifierStructs:
            self.notify.info('\nMODIFIERS (%s)' % len(modifierStructs))
            if config.minigameId == ToontownGlobals.CraneGameId:
                try:
                    from toontown.minigame.craning import CraneGameGlobals
                    for i, modStruct in enumerate(modifierStructs, 1):
                        modifier = CraneGameGlobals.CFORulesetModifierBase.fromStruct(modStruct)
                        tierStr = ' (Tier %s)' % modifier.tier if modifier.tier > 1 else ''
                        self.notify.info('    %s. %s%s' % (i, modifier.getName(), tierStr))
                except Exception as e:
                    self.notify.info('  (Error deserializing modifiers: %s)' % e)
                    for i, modStruct in enumerate(modifierStructs, 1):
                        self.notify.info('    %s. Raw struct: %s' % (i, modStruct))
            else:
                self.notify.info('  (Modifiers present but format unknown for this minigame)')
                for i, modStruct in enumerate(modifierStructs, 1):
                    self.notify.info('    %s. Raw struct: %s' % (i, modStruct))
        else:
            self.notify.info('\nMODIFIERS: None')
        
        # Extra Config
        extraConfig = config.getExtraConfig(config.minigameId)
        if extraConfig:
            self.notify.info('\nEXTRA CONFIG')
            for key, value in extraConfig.items():
                self.notify.info('  %s: %s' % (key, value))
        else:
            self.notify.info('\nEXTRA CONFIG: None')
        
        # Stored data for other minigames
        otherMinigames = set(config.rulesetData.keys()) | set(config.modifiersData.keys()) | set(config.extraConfig.keys())
        otherMinigames.discard(config.minigameId)
        if otherMinigames:
            self.notify.info('\nSTORED DATA FOR OTHER MINIGAMES')
            for mgId in otherMinigames:
                mgName = ToontownGlobals.MinigameId2Name.get(mgId, f'Unknown ({mgId})')
                hasRuleset = mgId in config.rulesetData
                hasModifiers = mgId in config.modifiersData and len(config.modifiersData[mgId]) > 0
                hasExtra = mgId in config.extraConfig and len(config.extraConfig[mgId]) > 0
                flags = []
                if hasRuleset:
                    flags.append('Ruleset')
                if hasModifiers:
                    flags.append('%s Modifiers' % len(config.modifiersData[mgId]))
                if hasExtra:
                    flags.append('Extra Config')
                self.notify.info('  %s (ID: %s): %s' % (mgName, mgId, ', '.join(flags) if flags else 'No data'))
        
        # Group Manager Stats
        self.notify.info('\nGROUP MANAGER STATS')
        self.notify.info('  Total groups: %s' % len(gm.groups))
        
        self.notify.info('\n' + '=' * 80 + '\n')
    
    def requestExit(self):
        self.notify.debug('BASE: requestExit: client has requested the game to end')
        self.setGameAbort()

    def local2GameTime(self, timestamp):
        return timestamp - self.gameStartTime

    def game2LocalTime(self, timestamp):
        return timestamp + self.gameStartTime

    def getCurrentGameTime(self):
        return self.local2GameTime(globalClock.getFrameTime())

    def getDifficulty(self):
        if self.difficultyOverride is not None:
            return self.difficultyOverride
        if hasattr(self.air, 'minigameDifficulty'):
            return float(self.air.minigameDifficulty)
        return MinigameGlobals.getDifficulty(self.getSafezoneId())

    def getSafezoneId(self):
        if self.trolleyZoneOverride is not None:
            return self.trolleyZoneOverride
        if hasattr(self.air, 'minigameSafezoneId'):
            return MinigameGlobals.getSafezoneId(self.air.minigameSafezoneId)
        return MinigameGlobals.getSafezoneId(self.trolleyZone)

    def logPerfectGame(self, avId):
        self.air.writeServerEvent('perfectMinigame', avId, '%s|%s|%s' % (self.minigameId, self.trolleyZone, self.avIdList))

    def logAllPerfect(self):
        for avId in self.avIdList:
            self.logPerfectGame(avId)
    
    def _initializeModifiers(self):
        """Initialize modifiers from group config if available"""
        if hasattr(self, 'group') and self.group is not None:
            config = self.group.getMinigameConfig()
            modifierStructs = config.getModifiers(self.minigameId)
            
            if modifierStructs:
                self.modifierManager.applyModifiersFromStructs(modifierStructs)
                self.notify.debug(f'Initialized {len(modifierStructs)} modifiers from group config')
    
    def setGroup(self, group):
        """
        Set the group reference for this minigame.
        This allows the minigame to save its state back to the group.
        """
        self.group = group
    
    def saveStateToGroup(self):
        """
        Save the current modifiers to the group config.
        This ensures the state persists for play-again scenarios.
        """
        if self.group is None:
            self.notify.debug('saveStateToGroup: No group reference, cannot save')
            return
        
        # Save modifiers
        modifierStructs = self.modifierManager._getRawModifierList()
        self.group.setMinigameModifiers(self.minigameId, modifierStructs)
        self.notify.debug(f'saveStateToGroup: Saved {len(modifierStructs)} modifiers for minigame {self.minigameId}')
    
    def addModifier(self, modifierEnum, tier=1):
        """Handle request to add a modifier from the client"""
        self.modifierManager.addModifier(modifierEnum, tier)
    
    def removeModifier(self, modifierEnum):
        """Handle request to remove a modifier from the client"""
        self.modifierManager.removeModifierByEnum(modifierEnum)
    
    def getHighestScorers(self):
        """
        Get the list of players with the highest scores in the current round.
        This should be overridden by specific minigames to determine winners.
        Returns a list of avId integers.
        """
        # Default implementation: get highest scores from scoring context
        currentRound = self.roundManager.currentRound
        roundContext = self.context.get_round(currentRound)
        allScores = roundContext.get_all_scores()
        
        if not allScores:
            return []
        
        maxScore = max(allScores.values())
        highestScorers = [avId for avId, score in allScores.items() if score == maxScore]
        return highestScorers
    
    def handleGameVictory(self):
        """
        Handle game victory - determines winner and either ends game or continues to next round.
        This should be called by minigames when a round ends.
        """
        highest_scorers = self.getHighestScorers()
        
        # If nobody is in the lead, check if this is a single-player forfeit
        if len(highest_scorers) == 0:
            participants = self.getParticipantIdsNotSpectating()
            # If there's only one participant, they should be declared the victor (even if they forfeited)
            if len(participants) == 1:
                victorId = participants[0]
                self._declareVictor(victorId)
                self.context.get_round(self.roundManager.currentRound).set_winners([victorId])
                # Single round match - end the game
                from direct.task.TaskManagerGlobal import taskMgr
                taskMgr.doMethodLater(5, self.gameOver, self.uniqueName("minigameVictory"), extraArgs=[])
                return
            # Otherwise, go to next round (shouldn't normally happen)
            self._declareVictor(0)
            from direct.task.TaskManagerGlobal import taskMgr
            taskMgr.doMethodLater(5, self.roundManager._startNextRound, self.uniqueName("minigameNextRound"), extraArgs=[])
            return
        
        # If multiple people are in the lead, pick the first person
        victorId = highest_scorers[0]
        self.context.get_round(self.roundManager.currentRound).set_winners(highest_scorers)
        
        # Handle first-to-X-wins matches
        winsNeeded = self.roundManager.getWinsNeeded()
        if winsNeeded > 1:
            # Track round wins
            self.roundManager.recordRoundWin(victorId)
            
            # Send round info to clients
            self.roundManager.d_setRoundInfo()
            
            # Check if match is complete
            if self.roundManager.isMatchComplete(victorId):
                # Match is complete
                self._declareVictor(victorId)
                from direct.task.TaskManagerGlobal import taskMgr
                taskMgr.doMethodLater(5, self.gameOver, self.uniqueName("minigameVictory"), extraArgs=[])
            else:
                # Round is complete, but match continues
                self._declareVictor(victorId)
                from direct.task.TaskManagerGlobal import taskMgr
                taskMgr.doMethodLater(3, self.roundManager._startNextRound, self.uniqueName("minigameNextRound"), extraArgs=[])
        else:
            # Single round match
            self._declareVictor(victorId)
            from direct.task.TaskManagerGlobal import taskMgr
            taskMgr.doMethodLater(5, self.gameOver, self.uniqueName("minigameVictory"), extraArgs=[])
    
    def _declareVictor(self, victorId):
        """
        Declare a victor. Override this if your minigame has a custom declareVictor method.
        """
        if hasattr(self, 'sendUpdate'):
            self.sendUpdate('declareVictor', [victorId])

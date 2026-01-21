import random
import traceback
import time
import weakref
from dataclasses import dataclass

from toontown.toonbase import ToontownGlobals
from . import DistributedMinigameTemplateAI
from .race import DistributedRaceGameAI
from .cannon import DistributedCannonGameAI
from .tag import DistributedTagGameAI
from .pattern import DistributedPatternGameAI
from .ring import DistributedRingGameAI
from .maze import DistributedMazeGameAI
from .tugowar import DistributedTugOfWarGameAI
from .catch import DistributedCatchGameAI
from .diving import DistributedDivingGameAI
from .target import DistributedTargetGameAI
from .pairing import DistributedPairingGameAI
from .photo import DistributedPhotoGameAI
from .vine import DistributedVineGameAI
from .ice import DistributedIceGameAI
from .cogthief import DistributedCogThiefGameAI
from .escape import DistributedEscapeGameAI
from toontown.minigame.crashball.DistributedCrashBallGameAI import DistributedCrashBallGameAI
from .DistributedMinigameAI import DistributedMinigameAI
from .craning.DistributedCraneGameAI import DistributedCraneGameAI
from .golfgreen.DistributedGolfGreenGameAI import DistributedGolfGreenGameAI
from .pie.DistributedPieGameAI import DistributedPieGameAI
from .scale.DistributedScaleGameAI import DistributedScaleGameAI
from .seltzer.DistributedSeltzerGameAI import DistributedSeltzerGameAI
from toontown.groups.Group import Group


@dataclass
class GeneratedMinigame:
    minigame: DistributedMinigameAI
    zone: int
    gameId: int


class MinigameCreatorAI:

    MINIGAME_ID_TO_CLASS = {
        ToontownGlobals.RaceGameId: DistributedRaceGameAI.DistributedRaceGameAI,
        ToontownGlobals.CannonGameId: DistributedCannonGameAI.DistributedCannonGameAI,
        ToontownGlobals.TagGameId: DistributedTagGameAI.DistributedTagGameAI,
        ToontownGlobals.PatternGameId: DistributedPatternGameAI.DistributedPatternGameAI,
        ToontownGlobals.RingGameId: DistributedRingGameAI.DistributedRingGameAI,
        ToontownGlobals.MazeGameId: DistributedMazeGameAI.DistributedMazeGameAI,
        ToontownGlobals.TugOfWarGameId: DistributedTugOfWarGameAI.DistributedTugOfWarGameAI,
        ToontownGlobals.CatchGameId: DistributedCatchGameAI.DistributedCatchGameAI,
        ToontownGlobals.DivingGameId: DistributedDivingGameAI.DistributedDivingGameAI,
        ToontownGlobals.TargetGameId: DistributedTargetGameAI.DistributedTargetGameAI,
        ToontownGlobals.MinigameTemplateId: DistributedMinigameTemplateAI.DistributedMinigameTemplateAI,
        ToontownGlobals.PairingGameId: DistributedPairingGameAI.DistributedPairingGameAI,
        ToontownGlobals.VineGameId: DistributedVineGameAI.DistributedVineGameAI,
        ToontownGlobals.IceGameId: DistributedIceGameAI.DistributedIceGameAI,
        ToontownGlobals.CogThiefGameId: DistributedCogThiefGameAI.DistributedCogThiefGameAI,
        ToontownGlobals.EscapeId: DistributedEscapeGameAI.DistributedEscapeGameAI,
        ToontownGlobals.PhotoGameId: DistributedPhotoGameAI.DistributedPhotoGameAI,
        ToontownGlobals.CrashBallGameId: DistributedCrashBallGameAI,
        ToontownGlobals.CraneGameId: DistributedCraneGameAI,
        ToontownGlobals.PieGameId: DistributedPieGameAI,
        ToontownGlobals.ScaleGameId: DistributedScaleGameAI,
        ToontownGlobals.SeltzerGameId: DistributedSeltzerGameAI,
        ToontownGlobals.GolfGreenGameId: DistributedGolfGreenGameAI,
    }

    def __init__(self, air):
        self.air = air
        self.minigameZoneReferences = {}
        self.minigameRequests = {}  # Now stores (minigameId, timestamp) tuples
        
        # Memory leak prevention
        self._lastCleanupTime = time.time()
        self._createdMinigames = weakref.WeakSet()

    def acquireMinigameZone(self, zoneId):
        if zoneId not in self.minigameZoneReferences:
            self.minigameZoneReferences[zoneId] = 0
        self.minigameZoneReferences[zoneId] += 1

    def releaseMinigameZone(self, zoneId):
        self.minigameZoneReferences[zoneId] -= 1
        if self.minigameZoneReferences[zoneId] <= 0:
            del self.minigameZoneReferences[zoneId]
            self.air.deallocateZone(zoneId)

    def getMinigameChoices(self, numPlayers: int, previousGameId=ToontownGlobals.NoPreviousGameId, allowTrolleyTracks=False) -> list[int]:
        choices = list(ToontownGlobals.MinigameIDs)

        # Remove previous game from the pool
        if previousGameId in choices:
            choices.remove(previousGameId)

        # If a player is solo filter out multiplayer games
        if numPlayers <= 1:
            for multiplayerGame in ToontownGlobals.MultiplayerMinigames:
                if multiplayerGame in choices:
                    choices.remove(multiplayerGame)

        return choices

    def createMinigame(self, playerArray, trolleyZone, minigameZone=None,
                       previousGameId=ToontownGlobals.NoPreviousGameId, hostId=None,
                       spectatorIds=None, desiredNextGame=None) -> GeneratedMinigame:

        if spectatorIds is None:
            spectatorIds = []

        if minigameZone is None:
            minigameZone = self.air.allocateZone()

        self.acquireMinigameZone(minigameZone)

        minigameChoices = self.getMinigameChoices(len(playerArray), previousGameId=previousGameId, allowTrolleyTracks=False)
        mgId = random.choice(minigameChoices)

        # Check for a minigame override.
        if desiredNextGame is not None:
            mgId = desiredNextGame

        # Check for requested minigames via commands, clear request if one was found
        for toonId in playerArray:
            if toonId in self.minigameRequests:
                mgId = self.minigameRequests[toonId]
                self.clearRequest(toonId)
                break

        if mgId not in self.MINIGAME_ID_TO_CLASS:
            print(f"Unable to find minigame constructor matching minigame id: {mgId}, defaulting to crane game")
            traceback.print_exc()
            mg = DistributedCraneGameAI(self.air, ToontownGlobals.CraneGameId)
        else:
            mg = self.MINIGAME_ID_TO_CLASS[mgId](self.air, mgId)

        mg.setExpectedAvatars(playerArray)
        mg.setTrolleyZone(trolleyZone)
        if hostId is not None:
            mg.setHost(hostId)
        mg.generateWithRequired(minigameZone)
        
        # Track created minigame for memory monitoring
        self._createdMinigames.add(mg)
        mg.b_setSpectators(spectatorIds)

        for avId in playerArray:
            toon = self.air.doId2do.get(avId)
            if toon is not None:
                self.air.questManager.toonPlayedMinigame(toon)

        return GeneratedMinigame(mg, minigameZone, mgId)
    
    def createMinigameFromGroup(self, group: Group, minigameZone=None, participantIds=None, spectatorIds=None) -> GeneratedMinigame:
        """
        Create a minigame using data from a Group object.
        This method fetches all necessary data from the group's minigame config,
        including rulesets, modifiers, participants, spectators, etc.
        
        This is the preferred method for creating minigames from groups,
        as it ensures all data persists correctly through the flow.
        
        Args:
            group: The Group object containing all minigame configuration
            minigameZone: Optional zone ID to reuse (e.g., for play-again scenarios).
                         If None, a new zone will be allocated.
            participantIds: Optional list of participant IDs. If None, uses all group members.
            spectatorIds: Optional list of spectator IDs. If None, uses group's spectators.
        """
        config = group.getMinigameConfig()
        
        # Get basic info from group
        # Use provided participantIds if given (e.g., for play-again), otherwise use all group members
        if participantIds is not None:
            playerArray = participantIds
        else:
            playerArray = group.getMemberIds()
        
        # Use provided spectatorIds if given, otherwise use group's spectators
        if spectatorIds is None:
            spectatorIds = group.getSpectators()
        
        minigameId = config.minigameId
        trolleyZone = config.trolleyZone
        hostId = config.hostId
        
        # Allocate minigame zone (or reuse provided one)
        if minigameZone is None:
            minigameZone = self.air.allocateZone()
        self.acquireMinigameZone(minigameZone)
        
        # Create the minigame instance
        if minigameId not in self.MINIGAME_ID_TO_CLASS:
            print(f"Unable to find minigame constructor matching minigame id: {minigameId}, defaulting to crane game")
            traceback.print_exc()
            mg = DistributedCraneGameAI(self.air, ToontownGlobals.CraneGameId)
        else:
            mg = self.MINIGAME_ID_TO_CLASS[minigameId](self.air, minigameId)
        
        # Set basic minigame properties
        mg.setExpectedAvatars(playerArray)
        mg.setTrolleyZone(trolleyZone)
        if hostId is not None:
            mg.setHost(hostId)
        
        # Generate the minigame
        mg.generateWithRequired(minigameZone)
        
        # Track created minigame for memory monitoring
        self._createdMinigames.add(mg)
        mg.b_setSpectators(spectatorIds)
        
        # Store reference to group BEFORE setGameReady is called
        # This allows setupRuleset() to check for saved state and restore it
        if hasattr(mg, 'setGroup'):
            mg.setGroup(group)
        
        # Don't restore ruleset/modifiers here - let setGameReady() -> setupRuleset() handle it
        # setupRuleset() will check for group data and restore if available
        
        # Track quest progress
        for avId in playerArray:
            toon = self.air.doId2do.get(avId)
            if toon is not None:
                self.air.questManager.toonPlayedMinigame(toon)
        
        return GeneratedMinigame(mg, minigameZone, minigameId)
    
    def clearExpiredRequests(self):
        """Clear expired minigame requests to prevent memory buildup"""
        current_time = time.time()
        # Clear requests older than 5 minutes
        expired = [avId for avId, (minigameId, timestamp) in self.minigameRequests.items() 
                  if current_time - timestamp > 300]
        for avId in expired:
            del self.minigameRequests[avId]

    def storeRequest(self, avId, minigameId):
        """Store a minigame request with timestamp for cleanup"""
        # Periodic cleanup
        current_time = time.time()
        if current_time - self._lastCleanupTime > 60:  # Cleanup every minute
            self.clearExpiredRequests()
            self._lastCleanupTime = current_time
        
        self.minigameRequests[avId] = (minigameId, current_time)

    def clearRequest(self, avId):
        """Clear a specific minigame request"""
        if avId in self.minigameRequests:
            del self.minigameRequests[avId]
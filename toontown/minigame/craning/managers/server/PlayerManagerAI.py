"""
PlayerManagerAI - Handles participant/spectator management, skill profiles, and death handling.
"""

from direct.task.TaskManagerGlobal import taskMgr
from toontown.matchmaking.skill_profile_keys import SkillProfileKey
from toontown.toon.DistributedToonAI import DistributedToonAI
from toontown.minigame.craning.CraneGameGlobals import ScoreReason


class PlayerManagerAI:
    """Manages player-related functionality: participants, spectators, skill profiles, death handling."""
    
    def __init__(self, game):
        self.game = game
        self._deathListenerEvents = []
        self.customSpawnOrderSet = False
        self.toonSpawnpointOrder = [i for i in range(16)]
    
    def handleSpotStatusChanged(self, spotIndex, isPlayer):
        """
        Called when the leader changes a spot's status between Player and Spectator
        """
        if spotIndex >= len(self.game.avIdList):
            return
            
        avId = self.game.avIdList[spotIndex]
        currentSpectators = list(self.game.getSpectators())
        
        if isPlayer and avId in currentSpectators:
            currentSpectators.remove(avId)
        elif not isPlayer and avId not in currentSpectators:
            currentSpectators.append(avId)
            
        self.game.b_setSpectators(currentSpectators)
        # Broadcast the spot status change to all clients
        self.game.sendUpdate('updateSpotStatus', [spotIndex, isPlayer])
        
        self.updateSkillProfile()
    
    def updateSkillProfile(self):
        """Update the skill profile based on player count"""
        # Determine the appropriate skill profile based on player count
        if len(self.game.getParticipantsNotSpectating()) == 2:
            skillKey = SkillProfileKey.CRANING_SOLOS
        elif len(self.game.getParticipantsNotSpectating()) >= 3:
            skillKey = SkillProfileKey.CRANING_FFA
        else:
            skillKey = None
        
        # Normal ranked game - set on both AI and clients
        self.game.b_setProfileSkillKey(skillKey)
    
    def listenForToonDeaths(self):
        """Call to listen for toon death events. Useful for catching deaths caused by DeathLink."""
        self.ignoreToonDeaths()
        for toon in self.game.getParticipatingToons():
            self._listenForToonDeath(toon)
    
    def ignoreToonDeaths(self):
        """Ignore toon death events. We don't need to worry about toons dying in specific scenarios
        Such as turn based battles as BattleBase handles that for us.
        """
        for event in self._deathListenerEvents:
            self.game.ignore(event)
        self._deathListenerEvents.clear()
    
    def _listenForToonDeath(self, toon):
        """Internal method to listen for a specific toon's death"""
        event = toon.getGoneSadMessage()
        self.game.accept(event, self.toonDied, [toon])
        self._deathListenerEvents.append(event)
    
    def _ignoreToonDeath(self, avId):
        """Internal method to ignore a specific toon's death"""
        self.game.ignore(DistributedToonAI.getGoneSadMessageForAvId(avId))
    
    def toonDied(self, toon):
        """Handle when a toon dies"""
        # Reset combo (delegated to ComboManager)
        if hasattr(self.game, 'comboManager'):
            self.game.comboManager.resetCombo(toon.doId)
        
        self.game.sendUpdate('toonDied', [toon.doId])
        
        # If we are in overtime, delegate to OvertimeManager
        if hasattr(self.game, 'overtimeManager') and self.game.overtimeManager.currentlyInOvertime:
            self.game.overtimeManager.checkOvertimeState()
            return
        
        # Toons are expected to die in overtime. Only penalize them if it is in the normal round.
        # Delegate scoring to ScoreManager
        if hasattr(self.game, 'scoreManager'):
            self.game.scoreManager.addScore(
                toon.doId, 
                self.game.ruleset.POINTS_PENALTY_GO_SAD, 
                reason=ScoreReason.WENT_SAD
            )
        
        # Add a task to revive the toon.
        taskMgr.doMethodLater(
            self.game.ruleset.REVIVE_TOONS_TIME, 
            self.reviveToon,
            self.game.uniqueName(f"reviveToon-{toon.doId}"), 
            extraArgs=[toon.doId]
        )
    
    def reviveToon(self, toonId: int) -> None:
        """Revive a toon after they died"""
        toon = self.game.air.getDo(toonId)
        if toon is None:
            return
        
        toon.b_setHp(int(self.game.ruleset.REVIVE_TOONS_LAFF_PERCENTAGE * toon.getMaxHp()))
        self.game.sendUpdate("revivedToon", [toonId])
    
    def setupSpawnpoints(self):
        """Setup spawn points for players"""
        # Only reset spawn order if it hasn't been manually customized by the leader
        if not self.customSpawnOrderSet:
            self.toonSpawnpointOrder = [i for i in range(16)]
            
            # Get best-of value from RoundManager if available
            bestOfValue = 1
            if hasattr(self.game, 'roundManager'):
                bestOfValue = self.game.roundManager.bestOfValue
            
            # For best of 1 matches, randomize only the first spawn positions based on number of participants
            if bestOfValue == 1:
                # Get number of participating toons (not spectating)
                numParticipants = len(self.game.getParticipantIdsNotSpectating())
                if numParticipants > 0:
                    # Randomize only the first 'numParticipants' positions
                    firstPositions = self.toonSpawnpointOrder[:numParticipants]
                    import random
                    random.shuffle(firstPositions)
                    # Put the randomized positions back at the beginning
                    self.toonSpawnpointOrder[:numParticipants] = firstPositions
            # For other matches (best of 3, 5, 7), use the existing ruleset randomization if enabled
            elif self.game.ruleset.RANDOM_SPAWN_POSITIONS:
                import random
                random.shuffle(self.toonSpawnpointOrder)
                
        self.d_setToonSpawnpointOrder()
    
    def resetCustomSpawnOrder(self):
        """Reset the custom spawn order flag, allowing spawn points to be randomized again"""
        self.customSpawnOrderSet = False
    
    def d_setToonSpawnpointOrder(self):
        """Send spawn point order to clients"""
        self.game.sendUpdate('setToonSpawnpointOrder', [self.toonSpawnpointOrder])
    
    def updateSpawnOrder(self, newOrder):
        """Handle spawn order update from the leader"""
        # Verify the sender is the leader (first player in avIdList)
        senderId = self.game.air.getAvatarIdFromSender()
        if senderId != self.game.avIdList[0]:
            self.game.notify.warning(f"Non-leader {senderId} tried to update spawn order")
            return
            
        # Validate the new order contains the same avatars
        if set(newOrder) != set(self.toonSpawnpointOrder):
            self.game.notify.warning(f"Invalid spawn order update from {senderId}: {newOrder}")
            return
            
        # Update the spawn order and mark it as customized
        self.toonSpawnpointOrder = newOrder[:]
        self.customSpawnOrderSet = True
        self.d_setToonSpawnpointOrder()
    
    def cleanup(self):
        """Clean up resources"""
        self.ignoreToonDeaths()
        # Clean up revive tasks
        for avId in self.game.getParticipants():
            taskMgr.remove(self.game.uniqueName(f"reviveToon-{avId}"))

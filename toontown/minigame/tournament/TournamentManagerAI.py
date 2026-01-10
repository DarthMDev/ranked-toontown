"""
AI-side tournament manager. Handles tournament logic and match orchestration.
This class is instantiated by minigames that want to run tournaments.
"""

from direct.directnotify.DirectNotifyGlobal import directNotify
from .TournamentGlobals import TournamentType, TournamentStage, BETWEEN_MATCH_DELAY
from .TournamentBracket import createTournamentBracket


class TournamentManagerAI:
    """
    Manages tournament state and orchestrates matches.
    Designed to be composed into minigame AI classes.
    """
    
    notify = directNotify.newCategory('TournamentManagerAI')
    
    def __init__(self, minigameAI):
        """
        Initialize tournament manager.
        
        Args:
            minigameAI: Reference to the parent minigame AI instance
        """
        self.minigameAI = minigameAI
        self.bracket = None
        self.tournamentType = TournamentType.NONE
        self.tournamentStages = TournamentStage.ONE_STAGE
        self.currentStage = 1
        self.stage1Bracket = None
        self.stage2Bracket = None
        self.stage2Type = None
        self.isActive = False
        
        # Track original spectators before tournament started
        self.originalSpectators = []
        
    def isTournamentActive(self):
        """Check if a tournament is currently active"""
        return self.isActive
        
    def getTournamentType(self):
        """Get the current tournament type"""
        return self.tournamentType
        
    def startTournament(self, tournamentType, stageConfig=TournamentStage.ONE_STAGE, stage2Type=None, participants=None):
        """
        Initialize and start a tournament.
        
        Args:
            tournamentType: Type from TournamentType enum
            stageConfig: Single or two-stage tournament (from TournamentStage)
            stage2Type: Tournament type for stage 2 (if two-stage)
            participants: List of avatar IDs to participate (None = use all non-spectators)
            
        Returns:
            True if tournament started successfully, False otherwise
        """
        if participants is None:
            participants = self.minigameAI.getParticipantIdsNotSpectating()
        
        if len(participants) < 2:
            self.notify.warning("Cannot start tournament with less than 2 participants")
            return False
            
        self.notify.info(f"Starting tournament: type={tournamentType}, stages={stageConfig}, participants={participants}")
        
        self.tournamentType = tournamentType
        self.tournamentStages = stageConfig
        self.stage2Type = stage2Type
        self.isActive = True
        self.currentStage = 1
        
        # Store original spectators
        self.originalSpectators = list(self.minigameAI.getSpectators())
        
        try:
            if stageConfig == TournamentStage.TWO_STAGE:
                # Stage 1: Always round robin for seeding
                self.stage1Bracket = createTournamentBracket(
                    TournamentType.ROUND_ROBIN, 
                    participants
                )
                self.bracket = self.stage1Bracket
                self.notify.info(f"Created two-stage tournament, stage 1 has {len(self.bracket.matches)} matches")
            else:
                # Single stage tournament
                self.bracket = createTournamentBracket(tournamentType, participants)
                self.notify.info(f"Created single-stage tournament with {len(self.bracket.matches)} matches")
                
            return True
            
        except Exception as e:
            self.notify.warning(f"Failed to create tournament bracket: {e}")
            self.isActive = False
            return False
            
    def getCurrentMatch(self):
        """
        Get the current match that should be played.
        
        Returns:
            TournamentMatch object or None if no match available
        """
        if not self.isActive or self.bracket is None:
            return None
        return self.bracket.getCurrentMatch()
        
    def setupNextMatch(self):
        """
        Setup the minigame for the next tournament match.
        Configures who plays vs who spectates.
        Skips matches where players have disconnected.
        
        Returns:
            True if there's a match to play, False if tournament is complete
        """
        if not self.isActive:
            return False
        
        # Keep trying to find a valid match (skip invalid ones)
        maxAttempts = len(self.bracket.matches) if self.bracket else 0
        attempts = 0
        
        while attempts < maxAttempts:
            currentMatch = self.getCurrentMatch()
            
            if currentMatch is None:
                # No more matches in current bracket
                if self.tournamentStages == TournamentStage.TWO_STAGE and self.currentStage == 1:
                    # Transition to stage 2
                    return self._startStage2()
                else:
                    # Tournament is complete
                    self.notify.info("No more matches, tournament complete")
                    return False
            
            # Skip if match is already complete (e.g., from a previous forfeit)
            if currentMatch.isComplete():
                self.bracket.advanceToNextMatch()
                attempts += 1
                continue
            
            # Validate both players still exist
            allParticipants = self.minigameAI.getParticipants()
            p1Exists = currentMatch.player1 in allParticipants
            p2Exists = currentMatch.player2 in allParticipants
            
            if not p1Exists and not p2Exists:
                # Both players disconnected - void match (no win awarded)
                self.notify.warning(f"Match {currentMatch.matchId}: Both players ({currentMatch.player1}, {currentMatch.player2}) disconnected, voiding match")
                self._recordForfeit(currentMatch, None, None)  # No winner, no loser
                self.bracket.advanceToNextMatch()
                attempts += 1
                continue
            elif not p1Exists:
                # Player 1 disconnected - void match (no win awarded to player 2)
                self.notify.warning(f"Match {currentMatch.matchId}: Player {currentMatch.player1} disconnected, match voided (no win awarded to {currentMatch.player2})")
                self._recordForfeit(currentMatch, currentMatch.player2, currentMatch.player1)
                self.bracket.advanceToNextMatch()
                attempts += 1
                continue
            elif not p2Exists:
                # Player 2 disconnected - void match (no win awarded to player 1)
                self.notify.warning(f"Match {currentMatch.matchId}: Player {currentMatch.player2} disconnected, match voided (no win awarded to {currentMatch.player1})")
                self._recordForfeit(currentMatch, currentMatch.player1, currentMatch.player2)
                self.bracket.advanceToNextMatch()
                attempts += 1
                continue
            
            # Both players exist - setup the match
            self._setupMatchParticipants(currentMatch)
            self.notify.info(f"Setup match {currentMatch.matchId}: {currentMatch.player1} vs {currentMatch.player2}")
            return True
        
        # If we've exhausted all matches trying to find a valid one, tournament is effectively complete
        self.notify.warning("No valid matches found (all remaining matches have disconnected players)")
        return False
        
    def _setupMatchParticipants(self, match):
        """
        Configure who's playing vs spectating for this match.
        
        Args:
            match: TournamentMatch to setup
        """
        allParticipants = self.minigameAI.getParticipants()
        matchPlayers = [match.player1, match.player2]
        
        # Everyone not in this match becomes a spectator
        spectators = [p for p in allParticipants if p not in matchPlayers]
        self.minigameAI.b_setSpectators(spectators)
        
        self.notify.debug(f"Match participants: {matchPlayers}, Spectators: {spectators}")
    
    def _recordForfeit(self, match, remainingPlayer, disconnectedPlayer):
        """
        Record a forfeit result for a match where a player disconnected.
        Marks the match as complete but does NOT award a win to the remaining player.
        
        Args:
            match: TournamentMatch that was forfeited
            remainingPlayer: Avatar ID of the player who didn't disconnect (None if both disconnected)
            disconnectedPlayer: Avatar ID of the player who disconnected (None if both disconnected)
        """
        # Mark match as complete but don't update standings
        # This allows the tournament to advance without giving credit for beating a disconnected player
        from .TournamentGlobals import MatchState
        match.state = MatchState.COMPLETE
        match.winner = None  # No winner for forfeit matches
        match.loser = None  # No loser either
        match.scores = {}  # No scores recorded
        
        if remainingPlayer is None:
            self.notify.info(f"Match {match.matchId} voided: Both players disconnected")
        else:
            self.notify.info(f"Match {match.matchId} voided: {disconnectedPlayer} disconnected, no win awarded to {remainingPlayer}")
        
    def recordMatchResult(self, winner, scores):
        """
        Record the result of the current match and advance.
        
        Args:
            winner: Avatar ID of the match winner
            scores: Dictionary mapping avatar IDs to their scores
            
        Returns:
            True if tournament continues (more matches), False if complete
        """
        if not self.isActive or self.bracket is None:
            self.notify.warning("Cannot record match result - no active tournament")
            return False
            
        currentMatch = self.getCurrentMatch()
        if currentMatch is None:
            self.notify.warning("Cannot record match result - no current match")
            return False
            
        # Record the result
        self.bracket.recordMatchResult(
            currentMatch.matchId,
            winner,
            scores
        )
        
        # Advance to next match
        self.bracket.advanceToNextMatch()
        
        # Check if we need to continue
        if self.bracket.isComplete():
            if self.tournamentStages == TournamentStage.TWO_STAGE and self.currentStage == 1:
                # Stage 1 complete, move to stage 2
                self.notify.info("Stage 1 complete, transitioning to stage 2")
                return True  # Tournament continues with stage 2
            else:
                # Tournament complete
                self.notify.info("Tournament complete!")
                return False
        else:
            # More matches in current stage
            return True
            
    def _startStage2(self):
        """
        Start the second stage of a two-stage tournament.
        Uses stage 1 results to seed stage 2 bracket.
        
        Returns:
            True if stage 2 started successfully
        """
        self.currentStage = 2
        
        # Get seeding from stage 1 standings
        standings = self.stage1Bracket.getStandings()
        
        # Sort participants by stage 1 performance
        seededParticipants = sorted(
            standings.keys(),
            key=lambda x: (
                -standings[x]['matchWins'],
                -standings[x]['totalPoints']
            )
        )
        
        self.notify.info(f"Stage 2 seeding: {seededParticipants}")
        
        try:
            # Create stage 2 bracket with the specified type
            stage2TournamentType = self.stage2Type if self.stage2Type is not None else self.tournamentType
            self.stage2Bracket = createTournamentBracket(
                stage2TournamentType,
                seededParticipants
            )
            self.bracket = self.stage2Bracket
            
            self.notify.info(f"Stage 2 created with {len(self.bracket.matches)} matches")
            return True
            
        except Exception as e:
            self.notify.warning(f"Failed to create stage 2 bracket: {e}")
            return False
            
    def getTournamentWinner(self):
        """
        Get the final tournament winner.
        
        Returns:
            Avatar ID of winner, or None if tournament not complete
        """
        if not self.isComplete():
            return None
            
        if self.tournamentStages == TournamentStage.TWO_STAGE:
            return self.stage2Bracket.getWinner() if self.stage2Bracket else None
        else:
            return self.bracket.getWinner() if self.bracket else None
            
    def isComplete(self):
        """
        Check if the entire tournament is finished.
        
        Returns:
            True if tournament is complete, False otherwise
        """
        if not self.isActive or self.bracket is None:
            return False
            
        if self.tournamentStages == TournamentStage.TWO_STAGE:
            return self.currentStage == 2 and self.stage2Bracket and self.stage2Bracket.isComplete()
        else:
            return self.bracket.isComplete()
            
    def getProgress(self):
        """
        Get tournament progress information for UI display.
        
        Returns:
            Dictionary with progress information
        """
        if not self.isActive or self.bracket is None:
            return None
            
        currentMatch, totalMatches = self.bracket.getProgress()
        
        return {
            'tournamentType': self.tournamentType,
            'currentStage': self.currentStage,
            'totalStages': 2 if self.tournamentStages == TournamentStage.TWO_STAGE else 1,
            'currentMatchIndex': currentMatch,
            'totalMatches': totalMatches,
            'standings': self.bracket.getStandings(),
            'isComplete': self.isComplete()
        }
        
    def getFinalStandings(self):
        """
        Get final tournament standings (only valid when complete).
        
        Returns:
            Ranked list of (rank, avId, stats) tuples, or None if not complete
        """
        if not self.isComplete():
            return None
            
        finalBracket = self.stage2Bracket if self.tournamentStages == TournamentStage.TWO_STAGE else self.bracket
        
        if hasattr(finalBracket, 'getRankedStandings'):
            return finalBracket.getRankedStandings()
        else:
            # For non-round-robin, just return winner
            winner = finalBracket.getWinner()
            return [(1, winner, {})] if winner else []
            
    def cleanup(self):
        """Clean up tournament state"""
        self.isActive = False
        self.bracket = None
        self.stage1Bracket = None
        self.stage2Bracket = None
        self.tournamentType = TournamentType.NONE
        
        # Restore original spectators
        if self.originalSpectators:
            self.minigameAI.b_setSpectators(self.originalSpectators)
            self.originalSpectators = []
            
        self.notify.info("Tournament cleaned up")


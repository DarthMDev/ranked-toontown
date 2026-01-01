"""
Tournament bracket generation and management.
Handles match pairings, bracket structure, and standings.
"""

from .TournamentGlobals import TournamentType, MatchState
from direct.directnotify.DirectNotifyGlobal import directNotify


class TournamentMatch:
    """Represents a single match in a tournament"""
    
    def __init__(self, matchId, player1, player2, bracketPosition=None):
        """
        Initialize a tournament match.
        
        Args:
            matchId: Unique identifier for this match
            player1: Avatar ID of first player
            player2: Avatar ID of second player
            bracketPosition: Optional position in bracket (for elimination tournaments)
        """
        self.matchId = matchId
        self.player1 = player1
        self.player2 = player2
        self.winner = None
        self.loser = None
        self.state = MatchState.PENDING
        self.bracketPosition = bracketPosition
        self.scores = {}  # Will be populated after match completes
        
    def getPlayers(self):
        """Get both players in this match"""
        return [self.player1, self.player2]
        
    def isComplete(self):
        """Check if this match has been played"""
        return self.state == MatchState.COMPLETE
        
    def __repr__(self):
        return f"TournamentMatch({self.matchId}: {self.player1} vs {self.player2}, winner={self.winner})"


class TournamentBracket:
    """
    Manages tournament bracket structure and match generation.
    Abstract base class - subclass for specific tournament types.
    """
    
    notify = directNotify.newCategory('TournamentBracket')
    
    def __init__(self, participants):
        """
        Initialize tournament bracket.
        
        Args:
            participants: List of avatar IDs participating in tournament
        """
        self.participants = list(participants)
        self.matches = []
        self.currentMatchIndex = 0
        self.standings = {}
        self.notify.info(f"Creating tournament bracket with {len(participants)} participants")
        
    def generateMatches(self):
        """Generate all matches for this tournament type. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement generateMatches()")
        
    def recordMatchResult(self, matchId, winner, scores):
        """
        Record the result of a match.
        
        Args:
            matchId: ID of the match that was completed
            winner: Avatar ID of the winner
            scores: Dictionary mapping avatar IDs to their scores
        """
        raise NotImplementedError("Subclasses must implement recordMatchResult()")
        
    def getCurrentMatch(self):
        """
        Get the current match to be played.
        
        Returns:
            TournamentMatch object or None if no matches remain
        """
        if self.currentMatchIndex < len(self.matches):
            return self.matches[self.currentMatchIndex]
        return None
        
    def advanceToNextMatch(self):
        """Move to the next match in the bracket"""
        self.currentMatchIndex += 1
        self.notify.debug(f"Advanced to match {self.currentMatchIndex}/{len(self.matches)}")
        
    def isComplete(self):
        """
        Check if tournament is finished.
        
        Returns:
            True if all matches have been played
        """
        return self.currentMatchIndex >= len(self.matches)
        
    def getWinner(self):
        """
        Get the tournament winner.
        
        Returns:
            Avatar ID of winner, or None if tournament not complete
        """
        raise NotImplementedError("Subclasses must implement getWinner()")
        
    def getStandings(self):
        """
        Get current tournament standings.
        
        Returns:
            Dictionary mapping avatar IDs to their standing information
        """
        return self.standings
        
    def getProgress(self):
        """
        Get tournament progress information.
        
        Returns:
            Tuple of (current match number, total matches)
        """
        return (self.currentMatchIndex, len(self.matches))


class RoundRobinBracket(TournamentBracket):
    """
    Round robin tournament - everyone plays everyone once.
    Winner determined by most match wins, with total points as tiebreaker.
    """
    
    notify = directNotify.newCategory('RoundRobinBracket')
    
    def generateMatches(self):
        """Generate all round robin match pairings"""
        self.matches = []
        matchId = 0
        
        # Generate every possible pairing
        for i, p1 in enumerate(self.participants):
            for p2 in self.participants[i+1:]:
                match = TournamentMatch(matchId, p1, p2)
                self.matches.append(match)
                self.notify.debug(f"Generated match {matchId}: {p1} vs {p2}")
                matchId += 1
                
        self.notify.info(f"Generated {len(self.matches)} round robin matches")
        
        # Initialize standings for all participants
        for participant in self.participants:
            self.standings[participant] = {
                'matchWins': 0,
                'matchLosses': 0,
                'totalPoints': 0,
                'pointsAgainst': 0,
                'matchResults': {}  # Maps opponent ID to result
            }
            
    def recordMatchResult(self, matchId, winner, scores):
        """
        Record match result and update standings.
        
        Args:
            matchId: ID of the completed match
            winner: Avatar ID of the winner
            scores: Dictionary mapping avatar IDs to their scores
        """
        if matchId >= len(self.matches):
            self.notify.warning(f"Invalid match ID: {matchId}")
            return
            
        match = self.matches[matchId]
        match.winner = winner
        match.scores = scores
        match.state = MatchState.COMPLETE
        
        # Determine loser
        loser = match.player1 if winner == match.player2 else match.player2
        match.loser = loser
        
        # Get scores for both players, ensuring they're non-negative
        winnerScore = max(0, int(scores.get(winner, 0)))
        loserScore = max(0, int(scores.get(loser, 0)))
        
        # Update standings
        self.standings[winner]['matchWins'] += 1
        self.standings[winner]['totalPoints'] += winnerScore
        self.standings[winner]['pointsAgainst'] += loserScore
        self.standings[winner]['matchResults'][loser] = 'win'
        
        self.standings[loser]['matchLosses'] += 1
        self.standings[loser]['totalPoints'] += loserScore
        self.standings[loser]['pointsAgainst'] += winnerScore
        self.standings[loser]['matchResults'][winner] = 'loss'
        
        self.notify.info(f"Match {matchId} complete: {winner} defeated {loser} ({winnerScore} - {loserScore})")
        
    def getWinner(self):
        """
        Determine winner based on standings.
        Tiebreakers: 1) Match wins, 2) Total points, 3) Head-to-head, 4) Point differential
        
        Returns:
            Avatar ID of tournament winner, or None if not complete
        """
        if not self.isComplete():
            self.notify.warning("Tournament not complete, cannot determine winner")
            return None
            
        # Sort participants by standings
        sortedParticipants = self._sortByStandings(self.participants)
        
        if sortedParticipants:
            winner = sortedParticipants[0]
            self.notify.info(f"Tournament winner: {winner}")
            return winner
            
        return None
        
    def _sortByStandings(self, participants):
        """
        Sort participants by tournament standings using tiebreaker rules.
        
        Args:
            participants: List of avatar IDs to sort
            
        Returns:
            List of avatar IDs sorted by standing (best to worst)
        """
        def standingKey(avId):
            standing = self.standings[avId]
            matchWins = standing['matchWins']
            totalPoints = standing['totalPoints']
            pointDiff = standing['totalPoints'] - standing['pointsAgainst']
            
            # Return tuple for sorting (higher is better, so negate for reverse sort)
            return (-matchWins, -totalPoints, -pointDiff)
            
        return sorted(participants, key=standingKey)
        
    def getRankedStandings(self):
        """
        Get standings in ranked order.
        
        Returns:
            List of (rank, avId, standing) tuples sorted by rank
        """
        sortedParticipants = self._sortByStandings(self.participants)
        
        rankedStandings = []
        currentRank = 1
        
        for i, avId in enumerate(sortedParticipants):
            standing = self.standings[avId]
            rankedStandings.append((currentRank, avId, standing))
            
            # Check if next player has same standing (tie)
            if i + 1 < len(sortedParticipants):
                nextAvId = sortedParticipants[i + 1]
                nextStanding = self.standings[nextAvId]
                
                # If standings are different, increment rank
                if (standing['matchWins'] != nextStanding['matchWins'] or 
                    standing['totalPoints'] != nextStanding['totalPoints']):
                    currentRank = i + 2
                    
        return rankedStandings
        
    def getHeadToHeadWinner(self, avId1, avId2):
        """
        Determine who won the head-to-head matchup between two players.
        
        Args:
            avId1: First player's avatar ID
            avId2: Second player's avatar ID
            
        Returns:
            Avatar ID of winner, or None if they haven't played yet
        """
        if avId2 in self.standings[avId1]['matchResults']:
            result = self.standings[avId1]['matchResults'][avId2]
            return avId1 if result == 'win' else avId2
        return None


# Factory function
def createTournamentBracket(tournamentType, participants):
    """
    Factory function to create appropriate bracket type.
    
    Args:
        tournamentType: Type from TournamentType enum
        participants: List of avatar IDs
        
    Returns:
        Initialized TournamentBracket subclass instance
        
    Raises:
        ValueError: If tournament type is unknown or not yet implemented
    """
    if tournamentType == TournamentType.ROUND_ROBIN:
        bracket = RoundRobinBracket(participants)
    elif tournamentType == TournamentType.SINGLE_ELIMINATION:
        raise NotImplementedError("Single elimination not yet implemented")
    elif tournamentType == TournamentType.DOUBLE_ELIMINATION:
        raise NotImplementedError("Double elimination not yet implemented")
    else:
        raise ValueError(f"Unknown tournament type: {tournamentType}")
        
    bracket.generateMatches()
    return bracket


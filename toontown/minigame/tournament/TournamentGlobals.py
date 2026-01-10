"""
Tournament system constants and enumerations.
"""


class TournamentType:
    """Types of tournament formats"""
    NONE = -1  # No tournament active
    ROUND_ROBIN = 0
    SINGLE_ELIMINATION = 1
    DOUBLE_ELIMINATION = 2


class TournamentStage:
    """Tournament stage configuration"""
    ONE_STAGE = 0   # Single tournament format
    TWO_STAGE = 1   # Round robin followed by elimination


class MatchState:
    """State of an individual match within tournament"""
    PENDING = 0
    IN_PROGRESS = 1
    COMPLETE = 2


# Tournament constraints
MIN_TOURNAMENT_PLAYERS = 2
MAX_TOURNAMENT_PLAYERS = 8
IDEAL_MAX_PLAYERS = 6  # Recommended maximum for reasonable match counts

# Timing constants (in seconds)
DEFAULT_TOURNAMENT_READY_TIMEOUT = 300  # 5 minutes for initial setup
BETWEEN_MATCH_DELAY = 3.0  # Delay between tournament matches
MATCH_RESULT_DISPLAY_TIME = 5.0  # How long to show match result before next match
MATCH_READY_TIMEOUT = 60  # Timeout for players to ready up between matches (in seconds)

# Tiebreaker priorities for round robin
TIEBREAKER_MATCH_WINS = 0
TIEBREAKER_TOTAL_POINTS = 1
TIEBREAKER_HEAD_TO_HEAD = 2
TIEBREAKER_POINT_DIFFERENTIAL = 3


def estimateTournamentTime(tournamentType, numPlayers, avgMatchTimeMinutes=3):
    """
    Estimate total tournament time in minutes.
    
    Args:
        tournamentType: Type of tournament (from TournamentType)
        numPlayers: Number of participants
        avgMatchTimeMinutes: Average time per match in minutes
        
    Returns:
        Estimated total time in minutes
    """
    if tournamentType == TournamentType.ROUND_ROBIN:
        # Everyone plays everyone: n*(n-1)/2 matches
        numMatches = (numPlayers * (numPlayers - 1)) // 2
    elif tournamentType == TournamentType.SINGLE_ELIMINATION:
        # Power of 2 bracket: n-1 matches
        numMatches = numPlayers - 1
    elif tournamentType == TournamentType.DOUBLE_ELIMINATION:
        # Approximately 2*(n-1) matches
        numMatches = 2 * (numPlayers - 1)
    else:
        return 0
        
    return numMatches * avgMatchTimeMinutes


def getMatchCountDescription(tournamentType, numPlayers):
    """
    Get a human-readable description of how many matches will be played.
    
    Args:
        tournamentType: Type of tournament (from TournamentType)
        numPlayers: Number of participants
        
    Returns:
        String describing match count (e.g., "6 matches (everyone plays everyone)")
    """
    if tournamentType == TournamentType.ROUND_ROBIN:
        numMatches = (numPlayers * (numPlayers - 1)) // 2
        return f"{numMatches} matches (everyone plays everyone)"
    elif tournamentType == TournamentType.SINGLE_ELIMINATION:
        numMatches = numPlayers - 1
        return f"{numMatches} matches (single elimination)"
    elif tournamentType == TournamentType.DOUBLE_ELIMINATION:
        numMatches = 2 * (numPlayers - 1)
        return f"~{numMatches} matches (double elimination)"
    else:
        return "Unknown"


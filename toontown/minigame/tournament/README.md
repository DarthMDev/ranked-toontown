# Tournament System for Toontown Minigames

## Overview

The tournament system provides a framework for running competitive tournaments within minigames. Currently implemented for the Crane Game (CFO Battle), with support for Round Robin tournaments.

## Architecture

### Core Components

1. **TournamentGlobals.py** - Constants, enums, and utility functions
2. **TournamentBracket.py** - Bracket generation and match management
3. **TournamentManagerAI.py** - Server-side tournament orchestration
4. **Integration** - Hooks into DistributedCraneGameAI and DistributedCraneGame

### Tournament Types

Currently implemented:
- **Round Robin** - Everyone plays everyone once. Winner determined by most match wins, with total points as tiebreaker.

Planned for future:
- **Single Elimination** - Standard bracket, losers are eliminated
- **Double Elimination** - Winner's bracket + Loser's bracket

## How It Works

### Flow

1. **Setup Phase** (Ruleset/Rules Phase)
   - Host clicks "Tournament" button
   - Selects tournament type (currently only Round Robin)
   - Server creates tournament bracket with all non-spectator participants

2. **Match Execution**
   - Each tournament match is a standard crane game round
   - Only the two players in the current match are active
   - All other participants become spectators for that match
   - Match winner is determined by highest score

3. **Match Progression**
   - After each match, results are recorded
   - Tournament standings are updated
   - Next match is automatically setup
   - Process repeats until all matches complete

4. **Tournament Completion**
   - Final winner is determined based on tournament standings
   - Special "Tournament Winner" announcement is displayed
   - Minigame ends normally

### Round Robin Specifics

For N players, there are N×(N-1)/2 total matches.

Example with 4 players (A, B, C, D):
- Match 1: A vs B
- Match 2: A vs C
- Match 3: A vs D
- Match 4: B vs C
- Match 5: B vs D
- Match 6: C vs D

**Winner Determination:**
1. Most match wins
2. If tied: Highest total points across all matches
3. If still tied: Best point differential

## Usage

### For Players

#### As Host (Leader):
1. Enter the Crane Game minigame
2. During the rules/setup phase, click the **"Tournament"** button (bottom left)
3. Select "Round Robin" from the dialog
4. Tournament will start automatically
5. Watch the tournament progress indicator at the top of the screen

#### As Participant:
- Ready up normally during rules phase
- When it's your match, you'll be active
- When it's not your match, you'll spectate
- Tournament progress is shown at top of screen

### For Developers

#### Starting a Tournament (AI-side):

```python
# In DistributedCraneGameAI
from toontown.minigame.tournament import TournamentType

# Start a round robin tournament
success = self.tournamentManager.startTournament(TournamentType.ROUND_ROBIN)

if success:
    # Setup first match
    self.tournamentManager.setupNextMatch()
```

#### Checking Tournament State:

```python
# Is tournament active?
if self.tournamentManager.isTournamentActive():
    # Get current match
    match = self.tournamentManager.getCurrentMatch()
    print(f"Current match: {match.player1} vs {match.player2}")
    
    # Get progress
    progress = self.tournamentManager.getProgress()
    print(f"Match {progress['currentMatchIndex']}/{progress['totalMatches']}")
```

#### Recording Match Results:

```python
# After a match completes
scores = {player1_id: 1500, player2_id: 1200}
hasMoreMatches = self.tournamentManager.recordMatchResult(winner_id, scores)

if hasMoreMatches:
    # Setup next match
    self.tournamentManager.setupNextMatch()
else:
    # Tournament complete
    winner = self.tournamentManager.getTournamentWinner()
```

## Configuration

### Time Estimates

Use `TournamentGlobals.estimateTournamentTime()` to estimate duration:

```python
from toontown.minigame.tournament.TournamentGlobals import estimateTournamentTime, TournamentType

# For 4 players, 3 minutes per match
time = estimateTournamentTime(TournamentType.ROUND_ROBIN, 4, 3)
# Returns: 18 minutes (6 matches × 3 minutes)
```

### Player Limits

- **Minimum:** 2 players
- **Maximum:** 8 players (configurable in TournamentGlobals)
- **Recommended:** 4-6 players for reasonable match counts

## Testing

### Manual Testing Checklist

- [ ] Start tournament with 2 players
- [ ] Start tournament with 3 players
- [ ] Start tournament with 4+ players
- [ ] Verify all matches are played in correct order
- [ ] Verify spectators can watch matches they're not in
- [ ] Verify tournament progress display updates correctly
- [ ] Verify correct winner is determined
- [ ] Test with ties in match wins (should use point tiebreaker)
- [ ] Test tournament cancellation (if implemented)
- [ ] Test player disconnect during tournament

### Automated Testing

```python
# Example unit test for bracket generation
from toontown.minigame.tournament import TournamentType, createTournamentBracket

def test_round_robin_bracket():
    players = [1, 2, 3, 4]
    bracket = createTournamentBracket(TournamentType.ROUND_ROBIN, players)
    
    # Should have 6 matches for 4 players
    assert len(bracket.matches) == 6
    
    # Each player should appear in 3 matches
    for player in players:
        matches_with_player = [m for m in bracket.matches if player in m.getPlayers()]
        assert len(matches_with_player) == 3
```

## Known Limitations

1. **No Save/Resume** - Tournaments must be completed in one session
2. **No Bracket Visualization** - Only text progress indicator
3. **Fixed Match Format** - Each match is a single round (no best-of within tournament)
4. **No Seeding** - Players are matched in order they joined
5. **Limited Tournament Types** - Only Round Robin currently implemented

## Future Enhancements

### Short Term
- [ ] Add Single Elimination support
- [ ] Add Double Elimination support
- [ ] Improve tournament UI with graphical bracket display
- [ ] Add tournament statistics/history tracking

### Long Term
- [ ] Two-stage tournaments (Round Robin → Elimination)
- [ ] Custom seeding options
- [ ] Best-of matches within tournament
- [ ] Tournament save/resume functionality
- [ ] Extend to other minigames beyond Crane Game

## Troubleshooting

### Tournament Won't Start
- Check that at least 2 non-spectator players are present
- Verify host has proper permissions
- Check server logs for error messages

### Matches Not Progressing
- Verify match completion is being detected
- Check that `recordMatchResult()` is being called
- Ensure tournament manager state is valid

### Wrong Winner Declared
- Check tiebreaker logic in `RoundRobinBracket.getWinner()`
- Verify all match results were recorded correctly
- Check standings calculation

## API Reference

See individual class docstrings for detailed API documentation:
- `TournamentManagerAI` - Main tournament orchestration
- `TournamentBracket` - Base bracket class
- `RoundRobinBracket` - Round robin implementation
- `TournamentMatch` - Individual match representation

## Contributing

When adding new tournament types:
1. Create a new bracket class inheriting from `TournamentBracket`
2. Implement `generateMatches()`, `recordMatchResult()`, and `getWinner()`
3. Add to `createTournamentBracket()` factory function
4. Update `TournamentType` enum
5. Add client UI for selection
6. Write tests

## License

Part of Toontown Ranked project.


"""
Managers for DistributedCraneGame to separate concerns and reduce bloat.

Each manager handles a specific domain:
- PlayerManager: Participants, spectators, spawn positions, skill profiles
- ModifierManager: Ruleset and modifier management
- DroneManager: Drone deployment, cooldowns, types
- StatusEffectManager: Status effects on safes and boss
- ComboManager: Combo tracking and bonuses
- TreasureManager: Treasure creation and recycling
- GoonManager: Goon spawning and management
- OvertimeManager: Overtime logic and state
- ForfeitRestartManager: Forfeit and restart consent systems
- ScoreManager: Scoring, winner tracking, bonuses
- RoundManager: Best-of rounds, round wins, spawn rotation
"""

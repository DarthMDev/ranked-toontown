"""
GroupMinigameConfig - Stores all minigame-related configuration for a group.

This includes:
- Minigame type and settings
- Ruleset data (minigame-specific, serialized)
- Modifiers (minigame-specific, serialized)
- Participants vs spectators
- Host information
- Any other data needed for the full minigame flow

This data persists through: Group -> Minigame Creator -> Minigame -> Purchase Manager -> Repeat
"""


class GroupMinigameConfig:
    """
    Stores all configuration needed for minigames in a group.
    This is designed to be generic and work for all minigames, even those without
    rulesets/modifiers yet.
    """
    
    def __init__(self, minigameId, trolleyZone=None, hostId=None):
        # Basic minigame info
        self.minigameId = minigameId
        self.trolleyZone = trolleyZone
        self.hostId = hostId
        
        # Ruleset data - stored as a dict/struct that can be deserialized by the minigame
        # Format: {minigameId: rulesetStruct}
        # For Crane Game: rulesetStruct is the result of CraneGameRuleset.asStruct()
        # For other minigames: can be None or their own ruleset structure
        self.rulesetData = {}  # {minigameId: rulesetStruct}
        
        # Modifiers data - stored as a list of modifier structs
        # Format: {minigameId: [modifierStruct1, modifierStruct2, ...]}
        # For Crane Game: modifierStruct is the result of CFORulesetModifierBase.asStruct()
        # For other minigames: can be empty list or their own modifier structures
        self.modifiersData = {}  # {minigameId: [modifierStruct1, modifierStruct2, ...]}
        
        # Additional minigame-specific config (future-proofing)
        # Can store any other data needed by specific minigames
        self.extraConfig = {}  # {minigameId: {...}}
    
    def setRuleset(self, minigameId, rulesetStruct):
        """
        Set the ruleset data for a specific minigame.
        rulesetStruct should be the result of calling ruleset.asStruct() on the minigame's ruleset.
        """
        self.rulesetData[minigameId] = rulesetStruct
    
    def getRuleset(self, minigameId):
        """
        Get the ruleset data for a specific minigame.
        Returns None if no ruleset is stored for this minigame.
        """
        return self.rulesetData.get(minigameId)
    
    def setModifiers(self, minigameId, modifierStructs):
        """
        Set the modifiers data for a specific minigame.
        modifierStructs should be a list of modifier.asStruct() results.
        """
        self.modifiersData[minigameId] = modifierStructs
    
    def getModifiers(self, minigameId):
        """
        Get the modifiers data for a specific minigame.
        Returns empty list if no modifiers are stored for this minigame.
        """
        return self.modifiersData.get(minigameId, [])
    
    def setExtraConfig(self, minigameId, config):
        """
        Set extra configuration for a specific minigame.
        config should be a dict of any additional data needed.
        """
        self.extraConfig[minigameId] = config
    
    def getExtraConfig(self, minigameId):
        """
        Get extra configuration for a specific minigame.
        Returns empty dict if no extra config is stored for this minigame.
        """
        return self.extraConfig.get(minigameId, {})
    
    def updateMinigameId(self, newMinigameId):
        """Update the minigame ID, preserving all data."""
        self.minigameId = newMinigameId
    
    def updateTrolleyZone(self, trolleyZone):
        """Update the trolley zone."""
        self.trolleyZone = trolleyZone
    
    def updateHostId(self, hostId):
        """Update the host ID."""
        self.hostId = hostId
    
    def asStruct(self):
        """
        Serialize this config to a struct for network transmission.
        Returns a list that can be passed over Astron.
        """
        return [
            self.minigameId,
            self.trolleyZone,
            self.hostId,
            self.rulesetData,
            self.modifiersData,
            self.extraConfig,
        ]
    
    @classmethod
    def fromStruct(cls, struct):
        """
        Deserialize a config from a struct received over the network.
        """
        minigameId, trolleyZone, hostId, rulesetData, modifiersData, extraConfig = struct
        config = cls(minigameId, trolleyZone, hostId)
        config.rulesetData = rulesetData
        config.modifiersData = modifiersData
        config.extraConfig = extraConfig
        return config
    
    def copy(self):
        """Create a deep copy of this config."""
        newConfig = GroupMinigameConfig(self.minigameId, self.trolleyZone, self.hostId)
        newConfig.rulesetData = self.rulesetData.copy()
        newConfig.modifiersData = {k: v.copy() if isinstance(v, list) else v for k, v in self.modifiersData.items()}
        newConfig.extraConfig = {k: v.copy() if isinstance(v, dict) else v for k, v in self.extraConfig.items()}
        return newConfig

"""
DroneManager - Handles client-side drone UI, cooldowns, and type selection.
"""

from direct.showbase.ShowBaseGlobal import globalClock
from direct.task.TaskManagerGlobal import taskMgr
from toontown.minigame.craning import CraneGameGlobals


class DroneManager:
    """Manages client-side drone UI, cooldowns, and type selection."""
    
    def __init__(self, game):
        self.game = game
        self.droneCooldowns = {}  # Track drone cooldowns per slot {avId: {slotIndex: (startTime, duration)}}
        self.selectedDroneTypes = {}  # Track selected drone types per player {avId: [slot0Type, slot1Type, slot2Type]}
        
        # Drone cooldown UI elements (shown near leave button when on crane)
        self.droneCooldownIndicator = None
        self.droneCooldownText = None
        self.droneCooldownTask = None
        
        # Drone selection UI elements (shown during rules phase)
        self.droneSelectionSlots = []  # List of 3 slot UI elements
        self.droneSelectionDialog = None
        self.droneSelectionFrame = None
        self.droneSlotKeybinds = []
    
    def setDroneCooldown(self, avId, slotIndex, duration):
        """Receive drone cooldown update from server"""
        if avId not in self.droneCooldowns:
            self.droneCooldowns[avId] = {}
        startTime = globalClock.getFrameTime()
        self.droneCooldowns[avId][slotIndex] = (startTime, duration)
        
        # Update UI if this is the local toon
        if avId == base.localAvatar.doId:
            self._updateDroneCooldownUI()
    
    def clearAllDroneCooldowns(self):
        """Clear all drone cooldowns"""
        self.droneCooldowns.clear()
        if self.droneCooldownTask:
            taskMgr.remove(self.droneCooldownTask)
            self.droneCooldownTask = None
    
    def setDroneTypeForToon(self, avId, slotIndex, droneTypeValue):
        """Receive drone type update from server"""
        from toontown.minigame.craning import CraneGameGlobals
        if isinstance(droneTypeValue, int):
            droneType = CraneGameGlobals.DroneType(droneTypeValue)
        else:
            droneType = droneTypeValue
        
        if avId not in self.selectedDroneTypes:
            self.selectedDroneTypes[avId] = [
                CraneGameGlobals.DroneType.LASER,
                CraneGameGlobals.DroneType.HEAL,
                CraneGameGlobals.DroneType.EXPLODEY
            ]
        
        if slotIndex >= 0 and slotIndex < 3:
            self.selectedDroneTypes[avId][slotIndex] = droneType
            
            # Update UI if this is the local toon
            if avId == base.localAvatar.doId:
                self._updateDroneSelectionUI()
    
    def _updateDroneCooldownUI(self):
        """Update the drone cooldown UI display"""
        # This will be implemented when we refactor the UI code
        pass
    
    def _updateDroneSelectionUI(self):
        """Update the drone selection UI display"""
        # This will be implemented when we refactor the UI code
        pass

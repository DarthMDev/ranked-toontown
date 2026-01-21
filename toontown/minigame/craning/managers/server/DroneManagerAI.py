"""
DroneManagerAI - Handles drone deployment, cooldowns, and type selection.
"""

from direct.showbase.ShowBaseGlobal import globalClock
from toontown.minigame.craning import CraneGameGlobals


class DroneManagerAI:
    """Manages drone deployment, cooldowns, and type selection per player."""
    
    def __init__(self, game):
        self.game = game
        self.droneCooldowns = {}  # Track drone deployment cooldowns per player per slot {avId: {slotIndex: nextAvailableTime}}
        self.selectedDroneTypes = {}  # Track selected drone types per player {avId: [slot0Type, slot1Type, slot2Type]}
    
    def requestDeployDrone(self, slotIndex=0):
        """Handle request to deploy a drone from client."""
        # Check if drones are enabled
        if not self.game.ruleset.WANT_DRONES:
            avId = self.game.air.getAvatarIdFromSender()
            self.game.notify.warning(f"Client {avId} attempted to deploy drone but drones are disabled")
            return
        
        avId = self.game.air.getAvatarIdFromSender()
        if avId not in self.game.getParticipantIdsNotSpectating():
            return
        
        # Validate slot index
        if slotIndex < 0 or slotIndex > 2:
            self.game.notify.warning(f'Invalid slot index {slotIndex} from {avId}')
            return
        
        # Check cooldown (90 seconds = 1.5 minutes)
        currentTime = globalClock.getFrameTime()
        DRONE_COOLDOWN = 90  # Integer seconds for DC compatibility
        
        # Initialize per-slot cooldown dict if needed
        if avId not in self.droneCooldowns:
            self.droneCooldowns[avId] = {}
        
        # Check if this specific slot is on cooldown
        if slotIndex in self.droneCooldowns[avId]:
            nextAvailableTime = self.droneCooldowns[avId][slotIndex]
            if currentTime < nextAvailableTime:
                # Still on cooldown
                remainingTime = nextAvailableTime - currentTime
                self.game.notify.debug(f'Drone slot {slotIndex} on cooldown for {avId}, {remainingTime:.1f}s remaining')
                return
        
        # Get selected drone type for this slot
        droneType = self.getDroneTypeForToon(avId, slotIndex)
        if droneType is None:
            # Default to laser if no type selected
            droneType = CraneGameGlobals.DroneType.LASER
        
        # Set cooldown for this specific slot
        self.droneCooldowns[avId][slotIndex] = currentTime + DRONE_COOLDOWN
        
        # Broadcast cooldown to all clients (avId, slotIndex, duration)
        self.game.sendUpdate('setDroneCooldown', [avId, slotIndex, int(DRONE_COOLDOWN)])
        
        if self.game.boss:
            self.game.boss.deployDroneForToon(avId, None, droneType)
    
    def getDroneTypeForToon(self, avId, slotIndex=0):
        """Get the selected drone type for a toon's slot."""
        if avId not in self.selectedDroneTypes:
            # Default: all slots are laser
            return CraneGameGlobals.DroneType.LASER
        
        slotTypes = self.selectedDroneTypes[avId]
        if slotIndex >= len(slotTypes):
            return CraneGameGlobals.DroneType.LASER
        
        return slotTypes[slotIndex]
    
    def setDroneTypeForToon(self, avId, slotIndex, droneTypeValue):
        """Set the selected drone type for a toon's slot."""
        if avId not in self.selectedDroneTypes:
            # Initialize with default (Laser, Heal, Explodey)
            self.selectedDroneTypes[avId] = [
                CraneGameGlobals.DroneType.LASER,
                CraneGameGlobals.DroneType.HEAL,
                CraneGameGlobals.DroneType.EXPLODEY
            ]
        
        # Convert value to enum if needed
        if isinstance(droneTypeValue, int):
            droneType = CraneGameGlobals.DroneType(droneTypeValue)
        else:
            droneType = droneTypeValue
        
        # Update the slot
        if slotIndex >= 0 and slotIndex < 3:
            self.selectedDroneTypes[avId][slotIndex] = droneType
            # Broadcast to all clients
            self.game.sendUpdate('setDroneTypeForToon', [avId, slotIndex, droneType.value])
            
            # Save the updated setup to the toon's database
            # Only save if all 3 slots have been set (to avoid partial saves)
            if len(self.selectedDroneTypes[avId]) == 3:
                toon = self.game.air.doId2do.get(avId)
                if toon and hasattr(toon, 'b_setDroneSetup'):
                    # Convert DroneType enums to uint8 values
                    setup = [dt.value for dt in self.selectedDroneTypes[avId]]
                    toon.b_setDroneSetup(setup)
    
    def requestCleanupDrones(self):
        """Handle request to clean up all drones."""
        if self.game.boss and hasattr(self.game.boss, 'drones'):
            # Clean up all active drones
            for drone in list(self.game.boss.drones):
                if drone and not drone.isDeleted():
                    # Send vanishWithPoof to clients, which will then requestDelete
                    try:
                        drone.vanishWithPoof()
                    except Exception as e:
                        # Drone might have been deleted between check and call
                        self.game.notify.debug(f"Error cleaning up drone {drone.doId}: {e}")
            self.game.boss.drones = []
    
    def clearAllCooldowns(self):
        """Clear all drone cooldowns (called when round ends)"""
        self.droneCooldowns.clear()
        self.game.sendUpdate('clearAllDroneCooldowns', [])

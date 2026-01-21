"""
DroneSelectionUI - Handles all UI for drone selection slots, cooldown displays, and selection dialog.
"""

from direct.gui.DirectGui import DGG, DirectFrame, DirectButton, DirectLabel
from direct.gui.OnscreenText import OnscreenText
from direct.showbase.ShowBaseGlobal import aspect2d, globalClock, base
from direct.task.TaskManagerGlobal import taskMgr
from panda3d.core import TextNode
from toontown.toonbase import ToontownGlobals
from toontown.minigame.craning import CraneGameGlobals


class DroneSelectionUI:
    """Manages drone selection UI including slots, cooldown displays, and selection dialog."""
    
    def __init__(self, game, droneManager):
        self.game = game
        self.droneManager = droneManager
        
        # UI elements
        self.droneSelectionFrame = None
        self.droneSelectionSlots = []  # List of 3 slot UI elements
        self.droneSelectionDialog = None
        self.droneSlotKeybinds = []
    
    def createSelectionUI(self):
        """Create the drone selection UI with 3 slots at the bottom of the screen."""
        if self.droneSelectionFrame is not None:
            return  # Already created
        
        # Initialize selected drone types for local toon (default: Laser, Heal, Explodey)
        localAvId = base.localAvatar.doId
        if localAvId not in self.droneManager.selectedDroneTypes:
            self.droneManager.selectedDroneTypes[localAvId] = [
                CraneGameGlobals.DroneType.LASER,
                CraneGameGlobals.DroneType.HEAL,
                CraneGameGlobals.DroneType.EXPLODEY
            ]
        
        # Create container frame for all slots
        self.droneSelectionFrame = DirectFrame(
            relief=None,
            parent=aspect2d,
            pos=(0, 0, -0.85),  # Bottom of screen
            sortOrder=DGG.NO_FADE_SORT_INDEX
        )
        
        # Get keybinds from settings for the 3 slots
        slotKeyNames = ['DRONE_SLOT_0_KEY', 'DRONE_SLOT_1_KEY', 'DRONE_SLOT_2_KEY']
        slotKeys = [base.settings.getControl(keyName) for keyName in slotKeyNames]
        slotSpacing = 0.25  # Space between slots
        
        # Helper function to format keybind for display
        def formatKeybindDisplay(keybind):
            """Format a keybind string for display in the UI."""
            if len(keybind) == 1:
                return keybind.upper()
            elif keybind.startswith('arrow_'):
                direction = keybind.replace('arrow_', '')
                arrowMap = {'up': '↑', 'down': '↓', 'left': '←', 'right': '→'}
                return arrowMap.get(direction, keybind.upper())
            elif keybind.startswith('page_'):
                return keybind.replace('page_', 'Pg').upper()
            elif keybind in ['control', 'shift', 'alt']:
                return keybind.capitalize()
            else:
                return keybind.replace('_', ' ').title()
        
        self.droneSelectionSlots = []
        self.droneSlotKeybinds = []
        for i in range(3):
            slotType = self.droneManager.selectedDroneTypes[localAvId][i]
            slotKey = slotKeys[i]
            self.droneSlotKeybinds.append(slotKey)
            
            # Create slot button
            slotButton = DirectButton(
                relief=DGG.RAISED,
                frameSize=(-0.12, 0.12, -0.08, 0.08),
                frameColor=(0.2, 0.2, 0.2, 0.8),
                borderWidth=(0.01, 0.01),
                parent=self.droneSelectionFrame,
                pos=(-0.25 + i * slotSpacing, 0, 0),
                command=self._onSlotClick,
                extraArgs=[i]
            )
            
            # Keybind label (top right)
            keybindText = OnscreenText(
                text=formatKeybindDisplay(slotKey),
                pos=(0.1, 0.06),
                scale=0.04,
                fg=(1, 1, 1, 0.7),
                align=TextNode.ARight,
                parent=slotButton,
                mayChange=True
            )
            
            # Drone icon/name (center)
            droneName = OnscreenText(
                text=slotType.getName(),
                pos=(0, -0.01),
                scale=0.03,
                fg=slotType.getHatColor(),
                align=TextNode.ACenter,
                parent=slotButton,
                mayChange=True
            )
            
            # Cooldown text (bottom of slot, shows remaining time or "Ready")
            cooldownText = OnscreenText(
                text='Ready',
                pos=(0, -0.06),
                scale=0.025,
                fg=(0.3, 1.0, 0.3, 1),
                align=TextNode.ACenter,
                parent=slotButton,
                mayChange=True
            )
            
            slotData = {
                'keybindText': keybindText,
                'droneName': droneName,
                'cooldownText': cooldownText,
                'button': slotButton,
                'slotIndex': i,
                'cooldownTask': None
            }
            self.droneSelectionSlots.append(slotData)
    
    def _onSlotClick(self, slotIndex):
        """Handle clicking on a drone slot"""
        # Check if drones are enabled
        if not self._areDronesEnabled():
            return
        
        # Check if we're in rules phase (can change drone) or play phase (deploy drone)
        if hasattr(self.game, 'frameworkFSM') and self.game.frameworkFSM.getCurrentState():
            currentState = self.game.frameworkFSM.getCurrentState().getName()
            if currentState == 'frameworkRules':
                # During rules phase - open selection dialog
                self.openSelectionDialog(slotIndex)
            else:
                # During play phase - deploy the drone
                if hasattr(self.game, '__deployDrone'):
                    self.game.__deployDrone(slotIndex)
        else:
            # Fallback: if we can't determine state, try to deploy
            self.game._DroneSelectionUI__deployDrone(slotIndex)
    
    def openSelectionDialog(self, slotIndex):
        """Open dialog to select drone type for a slot."""
        # Clean up existing dialog
        if self.droneSelectionDialog:
            self.droneSelectionDialog.destroy()
        
        # Create selection dialog
        self.droneSelectionDialog = DirectFrame(
            relief=None,
            image=DGG.getDefaultDialogGeom(),
            image_color=ToontownGlobals.GlobalDialogColor,
            image_scale=(1.0, 1, 0.8),
            pos=(0, 0, 0),
            parent=aspect2d,
            sortOrder=DGG.NO_FADE_SORT_INDEX + 2
        )
        
        # Title
        titleLabel = DirectLabel(
            parent=self.droneSelectionDialog,
            relief=None,
            text=f"Select Drone Type (Slot {slotIndex + 1})",
            text_scale=0.06,
            text_pos=(0, 0.3),
            text_fg=(0.1, 0.1, 0.4, 1),
            text_font=ToontownGlobals.getInterfaceFont()
        )
        
        # Load button assets
        buttons = base.loader.loadModel('phase_3/models/gui/dialog_box_buttons_gui')
        buttonImage = (buttons.find('**/ChtBx_OKBtn_UP'), 
                      buttons.find('**/ChtBx_OKBtn_DN'), 
                      buttons.find('**/ChtBx_OKBtn_Rllvr'))
        closeButtonImage = (buttons.find('**/CloseBtn_UP'), 
                          buttons.find('**/CloseBtn_DN'), 
                          buttons.find('**/CloseBtn_Rllvr'))
        
        # Create buttons for each drone type
        droneTypes = list(CraneGameGlobals.DroneType)
        for i, droneType in enumerate(droneTypes):
            currentY = i // 4 * -.15 + .1
            currentX = i % 4 * .2 - .3
            
            # Drone type button
            typeButton = DirectButton(
                parent=self.droneSelectionDialog,
                relief=None,
                image=buttonImage,
                text=droneType.getName(),
                text_scale=0.04,
                text_pos=(0, -0.02),
                text_fg=droneType.getHatColor(),
                pos=(currentX, 0, currentY),
                command=self._onSelectDroneType,
                extraArgs=[slotIndex, droneType]
            )
        
        # Close button
        closeButton = DirectButton(
            parent=self.droneSelectionDialog,
            relief=None,
            image=closeButtonImage,
            text="Cancel",
            text_scale=0.05,
            text_pos=(0, -0.1),
            pos=(0, 0, -0.3),
            command=self.closeSelectionDialog
        )
        
        buttons.removeNode()
    
    def _onSelectDroneType(self, slotIndex, droneType):
        """Handle drone type selection"""
        localAvId = base.localAvatar.doId
        if localAvId not in self.droneManager.selectedDroneTypes:
            self.droneManager.selectedDroneTypes[localAvId] = [
                CraneGameGlobals.DroneType.LASER,
                CraneGameGlobals.DroneType.HEAL,
                CraneGameGlobals.DroneType.EXPLODEY
            ]
        
        # Check if this drone type is already in another slot
        currentSlots = self.droneManager.selectedDroneTypes[localAvId]
        for otherSlotIndex, otherDroneType in enumerate(currentSlots):
            if otherSlotIndex != slotIndex and otherDroneType == droneType:
                # Swap: put the current slot's drone type into the other slot
                oldDroneType = currentSlots[slotIndex]
                currentSlots[otherSlotIndex] = oldDroneType
                # Update UI for the swapped slot
                self.updateSlotUI(otherSlotIndex)
                # Send update for swapped slot
                self.game.sendUpdate('setDroneTypeForToon', [base.localAvatar.doId, otherSlotIndex, oldDroneType.value])
                break
        
        # Update local selection
        self.droneManager.selectedDroneTypes[localAvId][slotIndex] = droneType
        
        # Update UI
        self.updateSlotUI(slotIndex)
        
        # Send to server
        self.game.sendUpdate('setDroneTypeForToon', [base.localAvatar.doId, slotIndex, droneType.value])
        
        # Save the updated setup to the toon's database
        self._saveDroneSetupToToon()
        
        # Close dialog
        self.closeSelectionDialog()
    
    def closeSelectionDialog(self):
        """Close the drone selection dialog."""
        if self.droneSelectionDialog:
            self.droneSelectionDialog.destroy()
            self.droneSelectionDialog = None
    
    def updateSlotUI(self, slotIndex):
        """Update the UI for a specific drone slot."""
        if slotIndex >= len(self.droneSelectionSlots):
            return
        
        # Use spectated player's data if spectating, otherwise use local toon's data
        localAvId = base.localAvatar.doId
        targetAvId = localAvId
        if hasattr(self.game, 'scoreboard') and self.game.scoreboard is not None:
            spectatedAvId = self.game.scoreboard.getSpectatedAvId()
            if spectatedAvId is not None:
                targetAvId = spectatedAvId
        
        if targetAvId not in self.droneManager.selectedDroneTypes:
            return
        
        slot = self.droneSelectionSlots[slotIndex]
        droneType = self.droneManager.selectedDroneTypes[targetAvId][slotIndex]
        
        # Update drone name
        if slot.get('droneName'):
            slot['droneName']['text'] = droneType.getName()
            slot['droneName']['fg'] = droneType.getHatColor()
    
    def updateSlotCooldown(self, slotIndex, startTime, duration):
        """Update the cooldown display for a specific drone slot."""
        if not self.droneSelectionSlots or slotIndex >= len(self.droneSelectionSlots):
            return
        
        slot = self.droneSelectionSlots[slotIndex]
        if not slot.get('cooldownText'):
            return
        
        # Clean up existing task for this slot
        if slot.get('cooldownTask'):
            taskMgr.remove(slot['cooldownTask'])
            slot['cooldownTask'] = None
        
        if startTime is None or duration is None:
            # No cooldown - show "Ready"
            slot['cooldownText']['text'] = 'Ready'
            slot['cooldownText']['fg'] = (0.3, 1.0, 0.3, 1)
            return
        
        # Start update task for this slot
        def updateTask(task, slotIdx=slotIndex, start=startTime, dur=duration):
            if slotIdx >= len(self.droneSelectionSlots):
                return task.done
            slotData = self.droneSelectionSlots[slotIdx]
            if not slotData.get('cooldownText'):
                return task.done
            
            currentTime = globalClock.getFrameTime()
            elapsed = currentTime - start
            remaining = max(0, dur - elapsed)
            
            if remaining <= 0:
                slotData['cooldownText']['text'] = 'Ready'
                slotData['cooldownText']['fg'] = (0.3, 1.0, 0.3, 1)
                slotData['cooldownTask'] = None
                return task.done
            else:
                # Show remaining time (MM:SS format)
                minutes = int(remaining // 60)
                seconds = int(remaining % 60)
                slotData['cooldownText']['text'] = f'{minutes}:{seconds:02d}'
                slotData['cooldownText']['fg'] = (1.0, 0.3, 0.3, 1)  # Red when on cooldown
                return task.cont
        
        slot['cooldownTask'] = taskMgr.add(
            updateTask,
            f'droneSlotCooldown{slotIndex}',
            extraArgs=[],
            appendTask=True
        )
    
    def updateVisibility(self):
        """Update drone UI visibility based on whether drones are enabled."""
        # Create UI if it doesn't exist and drones are enabled
        if (self.droneSelectionFrame is None) and self._areDronesEnabled():
            self._loadDroneSetupFromToon()
            self.createSelectionUI()
        
        if self.droneSelectionFrame is None:
            return
        
        if self._areDronesEnabled():
            # Show drone UI if we're in play state or rules state
            if hasattr(self.game, 'gameFSM') and self.game.gameFSM.getCurrentState():
                currentState = self.game.gameFSM.getCurrentState().getName()
                if currentState == 'play':
                    self.droneSelectionFrame.show()
                elif currentState == 'frameworkRules':
                    self.droneSelectionFrame.show()
                else:
                    self.droneSelectionFrame.hide()
            elif hasattr(self.game, 'frameworkFSM') and self.game.frameworkFSM.getCurrentState():
                # Check framework FSM if game FSM doesn't exist yet
                frameworkState = self.game.frameworkFSM.getCurrentState().getName()
                if frameworkState == 'frameworkRules':
                    self.droneSelectionFrame.show()
                else:
                    self.droneSelectionFrame.hide()
        else:
            # Hide drone UI if drones are disabled
            self.droneSelectionFrame.hide()
    
    def _areDronesEnabled(self):
        """Check if drones are enabled via the modifier system."""
        if not hasattr(self.game, 'ruleset') or not self.game.ruleset:
            return False
        enabled = getattr(self.game.ruleset, 'WANT_DRONES', False)
        return enabled
    
    def _loadDroneSetupFromToon(self):
        """Load the saved drone setup from the local toon."""
        if not hasattr(base, 'localAvatar') or not base.localAvatar:
            return
        
        # Get saved setup from toon
        if hasattr(base.localAvatar, 'droneSetup') and base.localAvatar.droneSetup:
            savedSetup = base.localAvatar.droneSetup
            if len(savedSetup) == 3:
                localAvId = base.localAvatar.doId
                # Convert uint8 values to DroneType enums
                self.droneManager.selectedDroneTypes[localAvId] = [
                    CraneGameGlobals.DroneType(savedSetup[0]),
                    CraneGameGlobals.DroneType(savedSetup[1]),
                    CraneGameGlobals.DroneType(savedSetup[2])
                ]
                # Send to server to sync with other clients
                for i, droneType in enumerate(self.droneManager.selectedDroneTypes[localAvId]):
                    self.game.sendUpdate('setDroneTypeForToon', [localAvId, i, droneType.value])
    
    def _saveDroneSetupToToon(self):
        """Save the current drone setup to the local toon's database."""
        if not hasattr(base, 'localAvatar') or not base.localAvatar:
            return
        
        localAvId = base.localAvatar.doId
        if localAvId not in self.droneManager.selectedDroneTypes:
            return
        
        # Convert DroneType enums to uint8 values
        setup = [droneType.value for droneType in self.droneManager.selectedDroneTypes[localAvId]]
        
        # Save to toon (this will persist to database via sendUpdate)
        base.localAvatar.sendUpdate('setDroneSetup', [setup])
    
    def cleanup(self):
        """Clean up all UI elements"""
        # Clean up cooldown tasks
        if self.droneSelectionSlots:
            for slot in self.droneSelectionSlots:
                if slot.get('cooldownTask'):
                    taskMgr.remove(slot['cooldownTask'])
                    slot['cooldownTask'] = None
                if slot.get('button'):
                    slot['button'].destroy()
            self.droneSelectionSlots = []
        
        if self.droneSelectionFrame:
            self.droneSelectionFrame.destroy()
            self.droneSelectionFrame = None
        
        if self.droneSelectionDialog:
            self.droneSelectionDialog.destroy()
            self.droneSelectionDialog = None
        
        self.droneSlotKeybinds = []

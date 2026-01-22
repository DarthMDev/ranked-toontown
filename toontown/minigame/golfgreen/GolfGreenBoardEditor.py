"""
Golf Green Board Editor - Developer tool for creating custom golf green boards
"""
import math
from math import pi

from direct.gui.DirectButton import DirectButton
from direct.gui.DirectFrame import DirectFrame
from direct.gui.DirectLabel import DirectLabel
from direct.gui import DirectGuiGlobals
from direct.task.TaskManagerGlobal import taskMgr
from panda3d.core import Vec4, TextNode, Point3

from toontown.minigame.golfgreen import GolfGreenGlobals
from toontown.minigame.golfgreen.GolfGreenBoard import GolfGreenBoard
from toontown.toonbase import ToontownGlobals


class GolfGreenBoardEditor(GolfGreenBoard):
    """
    An editor version of GolfGreenBoard that allows placing and removing balls
    to create custom board configurations.
    """

    def __init__(self):
        super().__init__()

        # Editor state
        self.editMode = True
        self.selectedBallType = 0  # Default to red (0)
        self.editorUI = None
        self.ballTypeButtons = []
        self.selectedButton = None
        self.exportButton = None
        self.clearButton = None
        self.instructionLabel = None

        # Available ball types for placing
        # Format: (type_id, name, color, description)
        self.ballTypes = [
            (0, 'r', (1, 0, 0, 1), 'Red'),
            (1, 'b', (0, 0, 1, 1), 'Blue'),
            (2, 'g', (0, 1, 0, 1), 'Green'),
            (3, 'w', (1, 1, 1, 1), 'White (Win)'),
            (4, 'k', (0.2, 0.2, 0.2, 1), 'Black'),
            (5, 'l', (0.5, 0, 0.5, 1), 'Purple'),
            (6, 'y', (1, 1, 0, 1), 'Yellow'),
            (None, '_', (0.5, 0.5, 0.5, 1), 'Empty'),
        ]

    def load(self, baseNode, models, sounds):
        """Load the editor"""
        super().load(baseNode, models, sounds)
        self._createEditorUI()

    def unload(self):
        """Cleanup editor"""
        self._destroyEditorUI()
        super().unload()

    def _createEditorUI(self):
        """Create the editor UI"""
        # Main editor frame - disable mouse blocking so clicks pass through to the 3D board
        self.editorUI = DirectFrame(
            frameSize=(-1.5, 1.5, -1.0, 1.0),
            frameColor=(0.2, 0.2, 0.2, 0.8),
            pos=(0, 0, 0.0),
            relief=DirectGuiGlobals.FLAT,
            state=DirectGuiGlobals.DISABLED  # Don't block mouse events
        )

        # Title
        DirectLabel(
            parent=self.editorUI,
            text="Golf Green Board Editor",
            text_scale=0.08,
            text_fg=(1, 1, 1, 1),
            pos=(0, 0, 0.85),
            relief=None
        )

        # Instructions
        self.instructionLabel = DirectLabel(
            parent=self.editorUI,
            text="Click grid to place balls | Right-click to remove | Scroll to change rows",
            text_scale=0.05,
            text_fg=(1, 1, 1, 1),
            pos=(0, 0, 0.75),
            relief=None
        )

        # Ball type selector buttons
        buttonSpacing = 0.2
        startX = -0.7
        startY = 0.6

        for i, (typeId, char, color, name) in enumerate(self.ballTypes):
            x = startX + (i % 5) * buttonSpacing
            y = startY - (i // 5) * 0.15

            btn = DirectButton(
                parent=self.editorUI,
                text=name,
                text_scale=0.04,
                text_fg=(0, 0, 0, 1),
                frameSize=(-0.09, 0.09, -0.05, 0.05),
                frameColor=color,
                pos=(x, 0, y),
                command=self._selectBallType,
                extraArgs=[typeId, char],
                relief=DirectGuiGlobals.RAISED
            )
            self.ballTypeButtons.append(btn)

        # Select first button by default
        if self.ballTypeButtons:
            self._selectBallType(0, 'r')

        # Export button
        self.exportButton = DirectButton(
            parent=self.editorUI,
            text="Export Board",
            text_scale=0.06,
            text_fg=(1, 1, 1, 1),
            frameSize=(-0.15, 0.15, -0.05, 0.05),
            frameColor=(0, 0.7, 0, 1),
            pos=(-0.5, 0, -0.8),
            command=self._exportBoard,
            relief=DirectGuiGlobals.RAISED
        )

        # Clear button
        self.clearButton = DirectButton(
            parent=self.editorUI,
            text="Clear Board",
            text_scale=0.06,
            text_fg=(1, 1, 1, 1),
            frameSize=(-0.15, 0.15, -0.05, 0.05),
            frameColor=(0.7, 0, 0, 1),
            pos=(0.5, 0, -0.8),
            command=self._clearBoard,
            relief=DirectGuiGlobals.RAISED
        )

        # Close button
        DirectButton(
            parent=self.editorUI,
            text="Close Editor",
            text_scale=0.06,
            text_fg=(1, 1, 1, 1),
            frameSize=(-0.15, 0.15, -0.05, 0.05),
            frameColor=(0.5, 0.5, 0.5, 1),
            pos=(0, 0, -0.8),
            command=self._closeEditor,
            relief=DirectGuiGlobals.RAISED
        )

    def _destroyEditorUI(self):
        """Destroy the editor UI"""
        if self.editorUI:
            self.editorUI.destroy()
            self.editorUI = None
        self.ballTypeButtons = []
        self.selectedButton = None

    def _selectBallType(self, typeId, char):
        """Select a ball type to place"""
        self.selectedBallType = typeId
        self.selectedBallChar = char

        # Find which button was clicked by matching the typeId
        for i, (btnTypeId, btnChar, color, name) in enumerate(self.ballTypes):
            if btnTypeId == typeId and btnChar == char:
                # Reset all button frames
                for btn in self.ballTypeButtons:
                    btn['relief'] = DirectGuiGlobals.RAISED

                # Highlight selected button
                self.ballTypeButtons[i]['relief'] = DirectGuiGlobals.SUNKEN
                self.selectedButton = self.ballTypeButtons[i]
                break

    def setup(self):
        """Setup the editor board"""
        super().setup()

        # Don't start the game loop or countdown
        self.stopCountDown()
        # Stop the game loop task but DON'T ignore mouse events yet
        taskMgr.remove('GolfGreenGameTask')
        self.running = 0

        # NOW set up our editor mouse handling
        self.accept('mouse1', self._handleEditorClick)
        self.accept('mouse3', self._handleEditorRightClick)

    def _handleEditorClick(self):
        """Handle left click to place a ball"""
        # Get mouse position
        if not base.mouseWatcherNode.hasMouse():
            return

        # Convert screen coords to world coords and find grid cell
        mpos = base.mouseWatcherNode.getMouse()

        # Get mouse position in 3D space relative to the board
        nearPoint = Point3()
        farPoint = Point3()
        base.camLens.extrude(mpos, nearPoint, farPoint)

        # Transform to board space
        if self.frame:
            nearPoint = self.frame.getRelativePoint(camera, nearPoint)
            farPoint = self.frame.getRelativePoint(camera, farPoint)

            # Find intersection with board plane (y=0)
            if farPoint.getY() != nearPoint.getY():
                t = -nearPoint.getY() / (farPoint.getY() - nearPoint.getY())
                intersect = nearPoint + (farPoint - nearPoint) * t

                # Convert to grid coordinates
                gridX, gridZ = self._worldToGrid(intersect.getX(), intersect.getZ())

                if gridX is not None and gridZ is not None:
                    self._placeBall(gridX, gridZ)

    def _handleEditorRightClick(self):
        """Handle right click to remove a ball"""
        if not base.mouseWatcherNode.hasMouse():
            return

        mpos = base.mouseWatcherNode.getMouse()

        nearPoint = Point3()
        farPoint = Point3()
        base.camLens.extrude(mpos, nearPoint, farPoint)

        if self.frame:
            nearPoint = self.frame.getRelativePoint(camera, nearPoint)
            farPoint = self.frame.getRelativePoint(camera, farPoint)

            if farPoint.getY() != nearPoint.getY():
                t = -nearPoint.getY() / (farPoint.getY() - nearPoint.getY())
                intersect = nearPoint + (farPoint - nearPoint) * t

                gridX, gridZ = self._worldToGrid(intersect.getX(), intersect.getZ())

                if gridX is not None and gridZ is not None:
                    self._removeBall(gridX, gridZ)

    def _worldToGrid(self, worldX, worldZ):
        """Convert world coordinates to grid coordinates"""
        # Find closest grid cell
        bestX = None
        bestZ = None
        bestDist = 999999

        for x in range(self.gridDimX):
            for z in range(self.gridDimZ):
                cellX = self.grid[x][z][1]
                cellZ = self.grid[x][z][2]
                dist = math.sqrt((worldX - cellX) ** 2 + (worldZ - cellZ) ** 2)

                if dist < bestDist and dist < self.cellSizeX * 0.8:
                    bestDist = dist
                    bestX = x
                    bestZ = z

        return bestX, bestZ

    def _placeBall(self, gridX, gridZ):
        """Place a ball at the given grid position"""
        # Remove existing ball if any
        if self.grid[gridX][gridZ][0] is not None:
            self.killSprite(self.grid[gridX][gridZ][0])

        # Place new ball (unless placing empty)
        if self.selectedBallType is not None:
            newSprite = self.addSprite(self.block, found=1, color=self.selectedBallType)
            self.placeIntoGrid(newSprite, gridX, gridZ)
            # Make the sprite face the camera properly
            if newSprite.nodeObj:
                newSprite.face()
            self.colorGrid()

    def _removeBall(self, gridX, gridZ):
        """Remove a ball at the given grid position"""
        if self.grid[gridX][gridZ][0] is not None:
            self.killSprite(self.grid[gridX][gridZ][0])
            self.colorGrid()

    def _clearBoard(self):
        """Clear all balls from the board"""
        self.clearGrid()

    def _exportBoard(self):
        """Export the current board configuration"""
        # Build the board representation
        rows = []

        # Process from top to bottom (reverse Z order)
        for z in range(self.gridDimZ - 1, -1, -1):
            row = []
            for x in range(self.gridDimX):
                cell = self.grid[x][z]
                if cell[0] is None:
                    row.append('_')
                else:
                    colorType = cell[0].colorType
                    # Map color type to character
                    charMap = {
                        0: 'r',  # Red
                        1: 'b',  # Blue
                        2: 'g',  # Green
                        3: 'w',  # White (win condition)
                        4: 'k',  # Black
                        5: 'l',  # Purple
                        6: 'y',  # Yellow
                    }
                    row.append(charMap.get(colorType, '_'))
            rows.append(''.join(row))

        # Remove trailing empty rows
        while rows and rows[-1] == '_________':
            rows.pop()

        # Format as Python tuple string
        output = "("
        for i, row in enumerate(rows):
            if i == 0:
                output += f"'{row}'"
            else:
                output += f", '{row}'"
        output += ")"

        # Print to console
        print("\n" + "="*60)
        print("EXPORTED BOARD CONFIGURATION")
        print("="*60)
        print("\nAdd this to BOARD_DATA in GolfGreenGlobals.py:")
        print("\n" + output)
        print("\n" + "="*60)
        print("\nBoard has been copied to console. You can now:")
        print("1. Copy the board configuration above")
        print("2. Add it to BOARD_DATA in toontown/minigame/golfgreen/GolfGreenGlobals.py")
        print("3. Don't forget to add the available ball types as the first element!")
        print("   Example: ('rgb', " + output[1:])
        print("="*60 + "\n")

        # Also show in chat
        base.localAvatar.setChatAbsolute("Board exported to console!", 0)

        return output

    def _closeEditor(self):
        """Close the editor"""
        self.hide()
        self.stop()

        # Restore camera
        if hasattr(base, 'localAvatar'):
            camera.reparentTo(base.localAvatar)
            base.localAvatar.startUpdateSmartCamera()

        # Clean up
        self.unload()

        messenger.send('golfEditorClosed')

    def startEditor(self):
        """Start the editor"""
        # Setup board
        self.setup()

        # Raise the board up to avoid clipping with ground
        if self.baseNode:
            self.baseNode.setZ(10)
            # The frame is already pitched 90 degrees in the load() method,
            # which makes it appear flat when viewed from above

        # Show everything
        self.show()

        # Position camera - looking down at the board from above
        camera.setPos(0, 0, 0)
        camera.setH(0)
        camera.setP(-70)  # Look straight down
        camera.reparentTo(self.focusPoint)
        base.camLens.setMinFov(46.8265)
        self.focusPoint.setPos(0, 12, 27)  # Position camera above the board
        self.focusPoint.setH(180)

        base.localAvatar.setChatAbsolute("Golf Green Board Editor opened!", 0)

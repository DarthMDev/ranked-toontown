"""
Base class for status effect visuals.

This provides a consistent interface for creating, updating, and cleaning up
visual effects (particles, models, etc.) for status effects on objects.
"""
from panda3d.core import NodePath, Vec3
from direct.directnotify import DirectNotifyGlobal
from abc import ABC, abstractmethod


class StatusEffectVisualBase(ABC):
    """
    Base class for all status effect visuals.
    
    Each status effect should have its own subclass that implements
    the specific visual behavior (particles, models, color changes, etc.)
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('StatusEffectVisual')
    
    def __init__(self, obj: NodePath, cr):
        """
        Initialize the status effect visual.
        
        Args:
            obj: The object (NodePath) to attach the visual effect to
            cr: The client repository for accessing game resources
        """
        self.obj = obj
        self.cr = cr
        self.effectNode = None  # Root node for all effect visuals
        self.active = False
        self.stackCount = 1  # How many of this effect are stacked
        
        # Calculate object dimensions for proper positioning
        self.objDimensions = self._calculateObjectDimensions()
        
    def _calculateObjectDimensions(self) -> tuple[Vec3, Vec3, Vec3, float]:
        """
        Calculate the tight bounds and dimensions of the object.
        For complex objects like the CFO boss, this includes all component parts.
        
        Returns:
            tuple of (minPoint, maxPoint, center, height)
        """
        # Special handling for BossCog (CFO boss) - need to include all parts
        try:
            from toontown.minigame.utils.boss import BossCog
            if isinstance(self.obj, BossCog.BossCog):
                # CFO boss is composed of legs, torso, head, and treads
                # Get bounds from all parts
                allParts = []
                
                # Get all the main parts
                for partName in ['legs', 'torso', 'head']:
                    part = self.obj.getPart(partName)
                    if part and not part.isEmpty():
                        allParts.append(part)
                
                # Get treads if they exist
                if hasattr(self.obj, 'treadsLeft') and self.obj.treadsLeft:
                    allParts.append(self.obj.treadsLeft)
                if hasattr(self.obj, 'treadsRight') and self.obj.treadsRight:
                    allParts.append(self.obj.treadsRight)
                
                # Get bounds from all parts combined
                if allParts:
                    minX, minY, minZ = float('inf'), float('inf'), float('inf')
                    maxX, maxY, maxZ = float('-inf'), float('-inf'), float('-inf')
                    
                    for part in allParts:
                        try:
                            bounds = part.getTightBounds()
                            if bounds:
                                partMin, partMax = bounds
                                minX = min(minX, partMin.getX())
                                minY = min(minY, partMin.getY())
                                minZ = min(minZ, partMin.getZ())
                                maxX = max(maxX, partMax.getX())
                                maxY = max(maxY, partMax.getY())
                                maxZ = max(maxZ, partMax.getZ())
                        except:
                            continue
                    
                    if minX != float('inf'):  # We got at least one valid bound
                        minPt = Vec3(minX, minY, minZ)
                        maxPt = Vec3(maxX, maxY, maxZ)
                        center = (minPt + maxPt) / 2.0
                        height = maxPt.getZ() - minPt.getZ()
                        self.notify.info(f"Calculated CFO boss dimensions from {len(allParts)} parts: height={height}, bounds=({minPt}, {maxPt})")
                        return (minPt, maxPt, center, height)
        except Exception as e:
            self.notify.debug(f"Error calculating BossCog dimensions: {e}")
        
        # Standard method for other objects
        try:
            # Try to get tight bounds (most accurate)
            bounds = self.obj.getTightBounds()
            if bounds:
                minPt, maxPt = bounds
                center = (minPt + maxPt) / 2.0
                height = maxPt.getZ() - minPt.getZ()
                return (minPt, maxPt, center, height)
        except:
            pass
        
        # Fallback to other methods
        try:
            if hasattr(self.obj, 'getHeight'):
                height = self.obj.getHeight()
                center = Vec3(0, 0, height / 2.0)
                minPt = Vec3(0, 0, 0)
                maxPt = Vec3(0, 0, height)
                return (minPt, maxPt, center, height)
        except:
            pass
        
        # Final fallback - use default values
        self.notify.warning(f"Could not determine dimensions for {self.obj.getName()}, using defaults")
        height = 3.0
        center = Vec3(0, 0, height / 2.0)
        minPt = Vec3(0, 0, 0)
        maxPt = Vec3(0, 0, height)
        return (minPt, maxPt, center, height)
    
    @abstractmethod
    def create(self):
        """
        Create and initialize the visual effect.
        
        This should create the effectNode and any child nodes/particles/etc.
        Should be called once when the effect is first applied.
        """
        pass
    
    @abstractmethod
    def start(self):
        """
        Start the visual effect playback.
        
        This should start any particle systems, animations, or intervals.
        """
        pass
    
    @abstractmethod
    def stop(self):
        """
        Stop the visual effect playback.
        
        This should stop any particle systems or intervals without destroying them.
        """
        pass
    
    @abstractmethod
    def cleanup(self):
        """
        Clean up and destroy the visual effect completely.
        
        This should remove all nodes, stop all intervals, and free resources.
        """
        pass
    
    def updateStack(self, stackCount: int):
        """
        Update the visual to reflect the number of stacked effects.
        
        Args:
            stackCount: The new stack count
            
        Default implementation does nothing. Override to handle stacking visuals.
        """
        self.stackCount = stackCount
    
    def _createEffectNode(self, name: str) -> NodePath:
        """
        Helper to create the root effect node parented to the object.
        
        Args:
            name: Name for the effect node
            
        Returns:
            The created NodePath
        """
        if self.effectNode:
            self.cleanup()
            
        self.effectNode = self.obj.attachNewNode(name)
        return self.effectNode


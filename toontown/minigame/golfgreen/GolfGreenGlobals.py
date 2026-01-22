# A file to put all golf green game settings in one place for easy adjustment

# Game Constants
PREPARE_DELAY = 5
PREPARE_LATENCY_FACTOR = 0.25  # Add a small buffer for latency and showing the "GO!" text

# Colors of the countdown number right before a golf green round starts.
RED_COUNTDOWN_COLOR = (.65, .2, .2, 1)
ORANGE_COUNTDOWN_COLOR = (.65, .45, .2, 1)
YELLOW_COUNTDOWN_COLOR = (.65, .65, .2, 1)
GREEN_COUNTDOWN_COLOR = (.2, .65, .2, 1)

# How long does the game last?
GAME_DURATION = 90

# How long to wait until dragging the board forward?
DRAG_BOARD_FWD_TIME = 3  # 10

# Should a player completing a board reward other players with a bomb?
WANT_GIFTS = True

# Map each ball type to an integer value.
TRANSLATE_DATA = {'r': 0, 'b': 1, 'g': 2, 'w': 3, 'k': 4, 'l': 5, 'y': 6, 'o': 7, 'a': 8, 's': 9, 'R': 10, 'B': 11}

# Board data, indicates what golf balls to give players and where to spawn at which positions.
# The first element of a tuple is the available types of balls to give the player for a puzzle.
# The remaining elements correspond to the rows of the puzzle board.
# Every row of the puzzle board must have 9 balls each. Use underscores for blank spaces.
# You should not have more than 10 rows for a puzzle board.
# Here's a cheat sheet of what the characters mean:

# The following can be used as available balls to the player to shoot as well as spots in the puzzle board.
# r: Red
# g: Green
# b: Blue
# y: Yellow
# l: Purple

# The following can be used only as available balls to the player. Do not use these in the puzzle board.
# o: Explosive (Can only be used as an available ball)
# a: All (Wild) (Can only be used as an available ball)

# The following can only be used in the puzzle board. Do not allow the players to shoot these.
# _: Empty space
# s: Barrier (Nothing can remove. Can only be placed in the puzzle.)
# B: Blue-Wildcard (Next ball is wild ball. Only can be placed in the puzzle.)
# R: Red-Explosive (Next ball is explosive. Only can be placed in the puzzle)
# w: Win Condition (Destroy all to beat the puzzle. Can only be placed in the puzzle)
BOARD_DATA = [
    ('rbygl', 'r_______b', 'byyywgggr', 'r_______b', 'bggyyyggr', 'r_______b', 'byylllyyr', 'r_______b', 'Blllllllr'),
    ('rgby', 'rrrgggbbb', 'rwrgggbwb', 'rrryyybbb', 'bByyyyyRr'),
    ('bygr', 'b_y_b_y__', 'b_y_b_yw_', '_b_y_b_y_', '_b_y_b_g_', '__b_g_r__', '__b_g_r__', '___b_g_r_', '___b_g_R_'),
    ('rgb', '_b__g____', '_r__g____', '_r__r____', '_w__R____'),
    ('lbryg', '___bbb___', '___bwb___', '__lgggr__', 'rrgggggll', '_ybbbbby_', '__ryyyr__', '_________', '_________'),
    ('lbryg', 'l_rr__b__', 'l__w__b__', 'b__b__b__', 'b__b__r__', 'l__g__r__', 'l__g__b__', 'y__y__B__', '_________'),
    ('byr', 'R_______y', 'ygggwgggR', 'B_______B', 'Rgggggggy', 'y_______R', 'BgggggggB', 'R_______y', 'BgggggggR'),
    ('bygr', '____bb___', '___bwb___', '_y__y____', '_y__y____', '_yggg_bbb', '____y____', '____y____', '__b_y__b_', '__b_y__b_', '__rrRrrr_'),
    ('bryg', 'b_yr_by_r', 'by_rb_yr_', 'r_gbwrg_y', 'rg_br_gy_', 'b_yg_yr_b', 'by_gy_Rb_', '_________', '_________'),
    ('lyg', '__lyyyyl_', '__lywyl__', '___lyyl__', '___lyl___', '____ll___', '__ygyg___', 'lyl___lyl', '_________'),
    ('rgbyl', 'l_______r', 'brbrbw__r', 'r_______r', 'r__ylblbl', 'r_______b', 'lglgly__b', '________b', '___yrgrgr'),
    ('rgbyl', 'b_______r', 'bbbw_wrrr', '___b__r__', '__b__r___', '___b__r__', '__g__y___', '___y__g__', 'rrrr_bbbb', 'lbyy_ggrl'),
    ('yrbg', 'ry_____yb', '_yrwwby__', '___yyy___', '_rl__gb__', 'lr_____bg', 'ylyg_gyly', '_________', '_________'),
    ('bylr', 'rrr_r_r_r', '_w__r_r_r', '____r_r_r', 'ggggR_r_r', '______r_r', 'ggggggR_r', '________r', 'ggggggggR', '_________'),
    ('rgbl', '__y_bb_y_', '_y__w_y__', 'yyy____yy', 'y_gyyyr_y', 'y_______y', 'byyyyyyl_', '_________', '_________', '_________', '_________'),
    ('o', 'b_bb_bb_b', 'wb_bb_bw_', 'b_bbbbb_b', 'bb_bb_bb_', 'b_bb_bb_b', 'bb_bb_bb_', '_________', '_________'),
    ('oa', 's________', 'sw_______', 's________', 's________', 's________', 's________', 'ssssss___', '_________')
]

# Text to display in popup text for misc point gains
LOW_LAFF = "UBER BONUS"  # Text to display alongside a low laff bonus
STUN = "STUN!"
PENALTY_GO_SAD = "DIED!"

# Ruleset
# Instance attached to golf green game instances, so we can easily modify stuff dynamically
class GolfGreenGameRuleset:
    """Ruleset for the golf green game. Can be extended with modifiers in the future."""
    
    def __init__(self):
        # Enable for debugging
        self.GENERAL_DEBUG = False
        
        self.TIMER_MODE = False  # When true, the game is timed and ends when time is up
        self.TIMER_MODE_TIME_LIMIT = 90  # How many seconds do we give if TIMER_MODE is active?
        
        # Game settings
        self.GAME_DURATION = 90
        self.DRAG_BOARD_FWD_TIME = 3
        self.WANT_GIFTS = True
        
        # TOON SETTINGS
        self.FORCE_MAX_LAFF = False  # Should we force a laff limit for this round?
        self.FORCE_MAX_LAFF_AMOUNT = 100
        self.HEAL_TOONS_ON_START = False  # Should we set all toons to full laff when starting?
        
        self.WANT_LOW_LAFF_BONUS = True  # Should we award toons with low laff bonus points?
        self.LOW_LAFF_BONUS = 0.1  # How much will the bonus be worth? i.e. .1 = 10% bonus
        self.LOW_LAFF_BONUS_THRESHOLD = 25  # How much laff or less for low laff bonus?
        self.LOW_LAFF_BONUS_INCLUDE_PENALTIES = True  # Should penalties also be increased?
        
        # POINTS SETTINGS
        self.POINTS_BOARD_COMPLETE = 100  # Points for completing a board
        self.POINTS_PENALTY_GO_SAD = -50  # Point deduction for dying
        
        # COMBO SETTINGS
        self.WANT_COMBO_BONUS = False
        self.COMBO_DURATION = 2.0  # How long should combos last?
    
    def validate(self):
        """Call to make sure certain attributes are within certain bounds"""
        pass
    
    def asStruct(self):
        """Sends an astron friendly array over, ONLY STUFF THE CLIENT NEEDS TO KNOW GOES HERE"""
        return [
            self.TIMER_MODE,
            self.TIMER_MODE_TIME_LIMIT,
            self.GAME_DURATION,
            self.WANT_LOW_LAFF_BONUS,
            self.LOW_LAFF_BONUS,
            self.LOW_LAFF_BONUS_THRESHOLD,
            self.LOW_LAFF_BONUS_INCLUDE_PENALTIES,
            self.POINTS_BOARD_COMPLETE,
            self.POINTS_PENALTY_GO_SAD,
            self.COMBO_DURATION
        ]
    
    @classmethod
    def fromStruct(cls, attrs):
        """Restore ruleset from a struct"""
        rulesetInstance = cls()
        
        if len(attrs) >= 10:
            rulesetInstance.TIMER_MODE = attrs[0]
            rulesetInstance.TIMER_MODE_TIME_LIMIT = attrs[1]
            rulesetInstance.GAME_DURATION = attrs[2]
            rulesetInstance.WANT_LOW_LAFF_BONUS = attrs[3]
            rulesetInstance.LOW_LAFF_BONUS = attrs[4]
            rulesetInstance.LOW_LAFF_BONUS_THRESHOLD = attrs[5]
            rulesetInstance.LOW_LAFF_BONUS_INCLUDE_PENALTIES = attrs[6]
            rulesetInstance.POINTS_BOARD_COMPLETE = attrs[7]
            rulesetInstance.POINTS_PENALTY_GO_SAD = attrs[8]
            rulesetInstance.COMBO_DURATION = attrs[9]
        
        return rulesetInstance
    
    def __str__(self):
        return repr(self.__dict__)


# Modifier Base Class
# Instance attached to golf green game instances, so we can easily modify stuff dynamically
class GolfGreenGameModifierBase(object):
    """Base class for all golf green game modifiers."""
    
    # This should be overridden by subclasses, used so that the client knows which class to use when instantiating modifiers
    MODIFIER_ENUM = -1
    
    # This should also be overridden, use to define what type of modifier this is
    UNDEFINED = -1
    SPECIAL = 0
    HELPFUL = 1
    HURTFUL = 2
    MODIFIER_TYPE = UNDEFINED
    
    # Maps the above modifier enums to the classes that extend this one
    MODIFIER_SUBCLASSES = {}
    
    # Some colors to use for titles and percentages etc
    DARK_RED = (230.0 / 255.0, 20 / 255.0, 20 / 255.0, 1)
    RED = (255.0 / 255.0, 85.0 / 255.0, 85.0 / 255.0, 1)
    
    DARK_GREEN = (0, 180 / 255.0, 0, 1)
    GREEN = (85.0 / 255.0, 255.0 / 255.0, 85.0 / 255.0, 1)
    
    DARK_PURPLE = (170.0 / 255.0, 0, 170.0 / 255.0, 1)
    PURPLE = (255.0 / 255.0, 85.0 / 255.0, 255.0 / 255.0, 1)
    
    DARK_CYAN = (0, 0, 170.0 / 255.0, 1)
    CYAN = (85.0 / 255.0, 255.0 / 255.0, 255.0 / 255.0, 1)
    
    # The color that should be used for the title of this modifier
    TITLE_COLOR = DARK_GREEN
    # The color of the alternate color in the description
    DESCRIPTION_COLOR = GREEN
    
    # Tier represents modifiers that have multiple tiers to them
    def __init__(self, tier=1):
        self.tier = tier
    
    # Copied from google bc cba
    @staticmethod
    def numToRoman(n):
        NUM = [1, 4, 5, 9, 10, 40, 50, 90, 100, 400, 500, 900, 1000]
        SYM = ["I", "IV", "V", "IX", "X", "XL", "L", "XC", "C", "CD", "D", "CM", "M"]
        i = 12
        
        romanString = ''
        
        while n:
            div = n // NUM[i]
            n %= NUM[i]
            
            while div:
                romanString += SYM[i]
                div -= 1
            i -= 1
        return romanString
    
    # lazy method to translate ints to percentages since i think percents are cleaner to display
    @staticmethod
    def additivePercent(n):
        return 1.0 + n / 100.0
    
    # lazy method to translate ints to percentages since i think percents are cleaner to display
    @staticmethod
    def subtractivePercent(n):
        return 1.0 - n / 100.0
    
    # The name of this modifier to display to the client
    def getName(self):
        raise NotImplementedError('Please override the getName method from the parent class!')
    
    # The description of this modifier to display to the client
    def getDescription(self):
        raise NotImplementedError('Please override the getDescription method from the parent class!')
    
    # Returns an integer to change the total 'heat' of the game based on this modifier
    # Heat is an arbitrary measurement of difficulty
    def getHeat(self):
        raise NotImplementedError("Please override the getHeat method from the parent class!")
    
    # This method is called to apply this modifier's effect to the game
    def apply(self, game):
        """
        Apply this modifier's effect to the game.
        Override this method to implement modifier-specific behavior.
        """
        pass
    
    # Used to send to the client in an astron friendly way
    def asStruct(self):
        return [
            self.MODIFIER_ENUM,
            self.tier
        ]
    
    # Used to construct modifier instances when received from astron using the asStruct method
    @classmethod
    def fromStruct(cls, attrs):
        # Extract the info from the list
        modifierEnum, tier = attrs
        # Check if the enum isn't garbage
        if modifierEnum not in cls.MODIFIER_SUBCLASSES:
            raise Exception('Invalid modifier %s given from astron' % modifierEnum)
        
        # Extract the registered constructor and instantiate a modifier instance
        cls_constructor = cls.MODIFIER_SUBCLASSES[modifierEnum]
        modifier = cls_constructor(tier)
        return modifier


# Modifiers
class ModifierFirstToXWins(GolfGreenGameModifierBase):
    """First to X Wins modifier for the golf green game."""
    
    MODIFIER_ENUM = 0
    MODIFIER_TYPE = GolfGreenGameModifierBase.SPECIAL
    
    TITLE_COLOR = GolfGreenGameModifierBase.DARK_PURPLE
    DESCRIPTION_COLOR = GolfGreenGameModifierBase.PURPLE
    
    def getName(self):
        return f'First to {self.tier} Win{"s" if self.tier > 1 else ""}'
    
    def getDescription(self):
        return 'Match continues until a player wins %(color_start)s' + str(self.tier) + ' round%(color_end)s'
    
    def getHeat(self):
        return 0  # Neutral modifier, doesn't affect difficulty
    
    def apply(self, game):
        # This modifier doesn't modify the game state directly
        # Instead, it's read by RoundManagerAI to determine match format
        # The tier represents the number of wins needed
        pass


# Register all modifier subclasses
for subclass in GolfGreenGameModifierBase.__subclasses__():
    if hasattr(subclass, 'MODIFIER_ENUM') and subclass.MODIFIER_ENUM != -1:
        GolfGreenGameModifierBase.MODIFIER_SUBCLASSES[subclass.MODIFIER_ENUM] = subclass

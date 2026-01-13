import os
import sys
import time
import atexit
import subprocess
import tempfile
import shutil
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
from direct.showbase.DirectObject import DirectObject
from panda3d.core import ConfigVariableString, ConfigVariableBool
from otp.otpgui import OTPDialog
from otp.otpbase import OTPGlobals
from otp.otpbase.OTPLocalizer import CRAstronAddressAlreadyUsed

from direct.directnotify import DirectNotifyGlobal
from otp.otpbase import OTPLocalizer

AI_NOITFY_CATEGORY_NAME = 'ToontownAIRepository'
UD_NOITFY_CATEGORY_NAME = 'ToontownUberRepository'

ASTRON_EXCEPTION_MSG = ':%s(warning): INTERNAL-EXCEPTION: '
ASTRON_ALREADY_OPEN_MSG = 'Message Director: Failed to bind to address: address already in use'
PYTHON_TRACEBACK_MSG = 'Traceback (most recent call last):'

ASTRON_DONE_MSG = 'Event Logger: Opened new log.'
UD_DONE_MSG = f':{UD_NOITFY_CATEGORY_NAME}: Done.'
AI_DONE_MSG = f':{AI_NOITFY_CATEGORY_NAME}: District is now ready. Have fun in Toontown Ranked!'


class DedicatedServer(DirectObject):
    notify = DirectNotifyGlobal.directNotify.newCategory('DedicatedServer')

    def __init__(self, localServer=False):
        self.notify.info('Starting DedicatedServer.')
        self.localServer = localServer

        self.astronProcess = None
        self.uberDogProcess = None
        self.aiProcess = None

        self.astronLog = None
        self.uberDogLog = None
        self.aiLog = None

        self.uberDogInternalExceptions = []
        self.aiInternalExceptions = []

        # Track temporary config file for cleanup
        self.tempConfigFile = None
        
        # Track if MongoDB is being used for singleplayer
        self.usingMongoDB = False

        # Clean up any orphaned temporary MongoDB config files from previous sessions
        if self.localServer:
            self.cleanup_orphaned_temp_configs()

        self.notify.setInfo(True)
    
    @staticmethod
    def cleanup_orphaned_temp_configs():
        """Clean up any orphaned temporary MongoDB config files from previous sessions."""
        try:
            config_dir = 'astron/config'
            if os.path.exists(config_dir):
                import glob
                temp_files = glob.glob(os.path.join(config_dir, 'astrond_mongo_*.yml'))
                for temp_file in temp_files:
                    try:
                        os.remove(temp_file)
                    except Exception:
                        pass  # Ignore errors when cleaning up
        except Exception:
            pass  # Ignore errors during cleanup

    def start(self):
        # Register self.killProcesses with atexit in the event of a hard exit,
        # so that the server processes are killed if they're running.
        atexit.register(self.killProcesses)

        if self.localServer:
            self.notify.info('Starting local server...')
        else:
            self.notify.info('Starting dedicated server...')

        if not ConfigVariableBool('local-multiplayer', True).getValue() and not self.localServer:
            self.notify.error("You are trying to start the server manually, but local-multiplayer is disabled!\n"
                              "You do not need to run this file in singleplayer mode, the server will automatically start on bootup.")

        taskMgr.add(self.startAstron, 'startAstron')

    def openAstronProcess(self, astronConfig):
        if sys.platform == 'win32':
            self.astronProcess = subprocess.Popen('astron/astrond.exe --loglevel info %s' % astronConfig,
                                                  stdin=self.astronLog, stdout=self.astronLog, stderr=self.astronLog)
        elif sys.platform == 'darwin':
            self.astronProcess = subprocess.Popen('astron/astrondmac --loglevel info %s' % astronConfig,
                                                  stdin=self.astronLog, stdout=self.astronLog, stderr=self.astronLog, shell=True)
        elif sys.platform == 'linux':
            self.astronProcess = subprocess.Popen('astron/astrondlinux --loglevel info %s' % astronConfig,
                                                  stdin=self.astronLog, stdout=self.astronLog, stderr=self.astronLog)
        else:
            self.notify.error(f"The following platform is not supported: {sys.platform}")

        if not ConfigVariableBool('local-multiplayer', True).getValue():
            gameServicesDialog['text'] = OTPLocalizer.CRLoadingGameServices + '\n\n' + OTPLocalizer.CRLoadingGameServicesAstron

    def check_mongodb_available(self):
        """Check if MongoDB is installed and running on the system."""
        # First check if mongod is installed
        mongod_found = False
        try:
            result = subprocess.run(
                ['mongod', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                mongod_found = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        except Exception:
            pass
        
        # Also check common Windows installation paths
        if not mongod_found and sys.platform == 'win32':
            import glob
            common_paths = [
                r'C:\Program Files\MongoDB\Server\*\bin\mongod.exe',
                r'C:\Program Files (x86)\MongoDB\Server\*\bin\mongod.exe',
                os.path.expanduser(r'~\AppData\Local\Programs\MongoDB\Server\*\bin\mongod.exe'),
            ]
            for path_pattern in common_paths:
                if glob.glob(path_pattern):
                    mongod_found = True
                    break
        
        if not mongod_found:
            return False
        
        # Now check if MongoDB is actually running by trying to connect
        try:
            from pymongo import MongoClient
            from pymongo.errors import ServerSelectionTimeoutError
            
            client = MongoClient('mongodb://127.0.0.1:27017/', serverSelectionTimeoutMS=2000)
            # Try to ping the server
            client.admin.command('ping')
            client.close()
            return True
        except (ImportError, ServerSelectionTimeoutError, Exception):
            # MongoDB is installed but not running
            self.notify.warning('MongoDB is installed but not running. Please start MongoDB service.')
            return False

    def create_mongodb_config(self, originalConfigPath):
        """Create a temporary config file with MongoDB backend for singleplayer."""
        if not YAML_AVAILABLE:
            self.notify.error('PyYAML not available. Cannot create MongoDB config.')
            raise Exception('PyYAML is required but not available. Please install PyYAML: pip install PyYAML')
        
        try:
            # Read the original config
            with open(originalConfigPath, 'r') as f:
                config = yaml.safe_load(f)
            
            # Modify the database backend to use MongoDB
            for role in config.get('roles', []):
                if role.get('type') == 'database':
                    role['backend'] = {
                        'type': 'mongodb',
                        'server': 'mongodb://127.0.0.1:27017/astrondb'
                    }
                    break
            
            # Create a temporary config file
            # Use a fixed filename since we only need one at a time for singleplayer
            # This makes cleanup easier and avoids accumulating temp files
            config_dir = 'astron/config'
            temp_path = os.path.join(config_dir, 'astrond_mongo_temp.yml')
            
            # Remove any existing temp file first
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            
            # Write the modified config
            with open(temp_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            
            self.tempConfigFile = temp_path
            self.notify.info(f'Created temporary MongoDB config: {temp_path}')
            return temp_path
        except Exception as e:
            self.notify.error(f'Failed to create MongoDB config: {e}')
            raise

    def startAstron(self, task):
        self.notify.info('Starting Astron...')

        # Create and open the log file to use for Astron.
        astronLogFile = self.generateLog('astron')
        self.astronLog = open(astronLogFile, 'a')
        self.notify.info('Opened new Astron log: %s' % astronLogFile)

        # Use the Astron config file based on the database.
        astronConfig = ConfigVariableString('astron-config-path', 'astron/config/astrond.yml').getValue()

        # For singleplayer, MongoDB is required
        if self.localServer:
            if not self.check_mongodb_available():
                self.notify.error('MongoDB is required but not available.')
                self.notify.error('Please install and start MongoDB before launching singleplayer.')
                self.notify.error('MongoDB must be running on mongodb://127.0.0.1:27017/')
                raise Exception('MongoDB is required but not available.')
            
            self.notify.info('Using MongoDB backend for singleplayer.')
            astronConfig = self.create_mongodb_config(astronConfig)
            self.usingMongoDB = True

        # Start Astron process.
        self.openAstronProcess(astronConfig)
        # Setup a Task to start the UberDOG process when Astron is done.
        taskMgr.add(self.startUberDog, 'startUberDog')

    def startUberDog(self, task):
        # Check if Astron is ready through the log.
        astronLogFile = self.astronLog.name
        astronLog = open(astronLogFile)
        astronLogData = astronLog.read()
        astronLog.close()
        if ASTRON_ALREADY_OPEN_MSG in astronLogData:
            self.killProcesses()
            if not ConfigVariableBool('local-multiplayer', True).getValue():
                dialogClass = OTPGlobals.getGlobalDialogClass()
                astronErrorMsg = dialogClass(message = CRAstronAddressAlreadyUsed, text_wordwrap = 16, style = OTPDialog.Acknowledge, doneEvent = 'astronErrorExit')
                astronErrorMsg.show()
                return task.done
            else:
                self.notify.error("The Astron server has crashed, you will need to restart your server."
                                    "\n\nThere is an instance of Astron already open on this system."
                                    "\nPlease close it to start the dedicated server, it will be automatically started on bootup.")
        elif ASTRON_DONE_MSG not in astronLogData:
            # Astron has not started yet. Rerun the task.
            return task.again

        # Astron has started
        self.notify.info('Astron started successfully!')

        ''' UberDOG '''
        self.notify.info('Starting UberDOG server...')

        # Create and open the log file to use for UberDOG.
        uberDogLogFile = self.generateLog('uberdog')
        self.uberDogLog = open(uberDogLogFile, 'a')
        self.notify.info('Opened new UberDOG log: %s' % uberDogLogFile)

        # Setup UberDOG arguments.
        if "__compile__" not in globals():
            if sys.platform == 'win32':
                uberDogArguments = '%s -m toontown.uberdog.UDStart' % open('launch/windows/PPYTHON_PATH').read()
            else:
                uberDogArguments = 'python3 -m toontown.uberdog.UDStart'

        else:
            if sys.platform == 'win32':
                uberDogArguments = 'RankedEngine.exe --uberdog'
            else:
                uberDogArguments = 'RankedEngine --uberdog'

        if not ConfigVariableBool('local-multiplayer', True).getValue():
            gameServicesDialog['text'] = OTPLocalizer.CRLoadingGameServices + '\n\n' + OTPLocalizer.CRLoadingGameServicesUberdog

        # Set up environment variables for UberDOG
        env = os.environ.copy()
        if self.localServer and self.usingMongoDB:
            # Configure UberDOG to use MongoDB for account storage
            env['PLAYTOKEN_STORAGE_STRATEGY'] = 'MONGODB'
            env['MONGO_CONNECTION_STRING'] = 'mongodb://127.0.0.1:27017/'
            self.notify.info('Configured UberDOG to use MongoDB for account storage.')

        # Start UberDOG process.
        if sys.platform in ['win32', 'linux']:
            self.uberDogProcess = subprocess.Popen(uberDogArguments, stdin=self.uberDogLog, stdout=self.uberDogLog, stderr=self.uberDogLog, env=env)
        elif sys.platform == 'darwin':
            self.uberDogProcess = subprocess.Popen(uberDogArguments, stdin=self.uberDogLog, stdout=self.uberDogLog, stderr=self.uberDogLog, shell=True, env=env)
        # Start the AI process when UberDOG is done.
        taskMgr.add(self.startAI, 'startAI')

        # Once started, we can end this task.
        return task.done

    def startAI(self, task):
        # Check if UberDOG is ready through the log.
        uberDogLogFile = self.uberDogLog.name
        uberDogLog = open(uberDogLogFile)
        uberDogLogData = uberDogLog.read()
        uberDogLog.close()
        if UD_DONE_MSG not in uberDogLogData:
            # UberDOG has not started yet. Rerun the task.
            return task.again

        # UberDOG has started
        self.notify.info('UberDOG started successfully!')

        ''' AI '''
        self.notify.info('Starting AI server...')

        # Create and open the log file to use for AI.
        aiLogFile = self.generateLog('ai')
        self.aiLog = open(aiLogFile, 'a')
        self.notify.info('Opened new AI log: %s' % aiLogFile)

        # Setup AI arguments.
        if "__compile__" not in globals():
            if sys.platform == 'win32':
                aiArguments = '%s -m toontown.ai.AIStart' % open('launch/windows/PPYTHON_PATH').read()
            else:
                aiArguments = 'python3 -m toontown.ai.AIStart'
        else:
            if sys.platform == 'win32':
                aiArguments = 'RankedEngine.exe --ai'
            else:
                aiArguments = 'RankedEngine --ai'

        if not ConfigVariableBool('local-multiplayer', True).getValue():
            gameServicesDialog['text'] = OTPLocalizer.CRLoadingGameServices + '\n\n' + OTPLocalizer.CRLoadingGameServicesAI

        # Start AI process.
        if sys.platform in ['win32', 'linux']:
            self.aiProcess = subprocess.Popen(aiArguments, stdin=self.aiLog, stdout=self.aiLog, stderr=self.aiLog)
        elif sys.platform == 'darwin':
            self.aiProcess = subprocess.Popen(aiArguments, stdin=self.aiLog, stdout=self.aiLog, stderr=self.aiLog, shell=True)
        # Send a message to note the server has started.
        taskMgr.add(self.serverStarted, 'serverStarted')

        # Once started, we can end this task.
        return task.done

    def serverStarted(self, task):
        # Check if the AI is ready through the log.
        aiLogFile = self.aiLog.name
        aiLog = open(aiLogFile)
        aiLogData = aiLog.read()
        aiLog.close()
        if AI_DONE_MSG not in aiLogData:
            # AI has not started yet. Rerun the task.
            return task.again

        # AI has started
        self.notify.info('AI started successfully!')

        # Every aspect of the server has started. Let's finish with the done message.
        self.notify.info('Server now ready. Have fun in Toontown Ranked!')
        if self.localServer:
            messenger.send('localServerReady')

        # Setup a Task to check if the server has crashed.
        taskMgr.add(self.checkForCrashes, 'checkForCrashes')

        # Otherwise, we can end this task.
        return task.done

    def checkForCrashes(self, task):
        # Check if the AI server has crashed.
        aiLogFile = self.aiLog.name
        aiLog = open(aiLogFile)
        aiLogData = aiLog.readlines()
        aiLog.close()
        astronException = ASTRON_EXCEPTION_MSG % AI_NOITFY_CATEGORY_NAME
        for line in aiLogData:
            if PYTHON_TRACEBACK_MSG or astronException in line:
                if PYTHON_TRACEBACK_MSG in line:
                    # The AI server has crashed!
                    self.killProcesses()
                    self.notify.error("The AI server has crashed, you will need to restart your server."
                                      "\n\nIf this problem persists, please report the bug and provide "
                                      "them with your most recent log from the \"logs/ai\" folder.")
                elif astronException in line:
                    if line not in self.aiInternalExceptions:
                        self.aiInternalExceptions.append(line)
                        self.notify.warning(f'An internal exception has occurred in the AI server: {line}')

        # Check if the UberDOG server has crashed.
        uberDogLogFile = self.uberDogLog.name
        uberDogLog = open(uberDogLogFile)
        uberDogLogData = uberDogLog.readlines()
        uberDogLog.close()
        astronException = ASTRON_EXCEPTION_MSG % UD_NOITFY_CATEGORY_NAME
        for line in uberDogLogData:
            if PYTHON_TRACEBACK_MSG or astronException in line:
                if PYTHON_TRACEBACK_MSG in line:
                    # The UberDOG server has crashed!
                    self.killProcesses()
                    self.notify.error("The UberDOG server has crashed, you will need to restart your server."
                                      "\n\nIf this problem persists, please report the bug and provide "
                                      "them with your most recent log from the \"logs/uberdog\" folder.")
                elif astronException in line:
                    if line not in self.uberDogInternalExceptions:
                        self.uberDogInternalExceptions.append(line)
                        self.notify.warning(f'An internal exception has occurred in the UberDOG server: {line}')

        # Keep running this Task if the server has not crashed.
        return task.again

    def killProcesses(self):
        # Terminate server processes in reverse order of how they were started, starting with the AI.
        if self.aiProcess:
            self.aiProcess.terminate()

        # Next is UberDOG.
        if self.uberDogProcess:
            self.uberDogProcess.terminate()

        # And lastly, Astron.
        if self.astronProcess:
            self.astronProcess.terminate()
        
        # Clean up temporary config file if one was created
        if self.tempConfigFile and os.path.exists(self.tempConfigFile):
            try:
                os.remove(self.tempConfigFile)
                self.notify.info(f'Cleaned up temporary config: {self.tempConfigFile}')
            except Exception as e:
                self.notify.warning(f'Failed to clean up temporary config: {e}')

    @staticmethod
    def generateLog(logPrefix):
        ltime = 1 and time.localtime()
        logSuffix = '%02d%02d%02d_%02d%02d%02d' % (ltime[0] - 2000, ltime[1], ltime[2],
                                                   ltime[3], ltime[4], ltime[5])

        if not os.path.exists('logs/'):
            os.mkdir('logs/')

        if not os.path.exists('logs/%s/' % logPrefix):
            os.mkdir('logs/%s/' % logPrefix)

        logFile = 'logs/%s/%s-%s.log' % (logPrefix, logPrefix, logSuffix)

        return logFile

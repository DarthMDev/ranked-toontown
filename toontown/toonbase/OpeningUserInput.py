import builtins
import os
import re
import subprocess
import socket
import time
from direct.showbase.DirectObject import DirectObject
from direct.gui.DirectGui import *
from otp.otpbase import OTPGlobals
from otp.otpgui import OTPDialog
from otp.otpbase.OTPLocalizer import (
    CREnterUsername,
    CRInvalidUsername,
    CREmptyUsername,
    CREnterGameserver,
    CREmptyGameserver,
    CRLoadingGameServices,
    CRSpecifyServerSelection,
    CRLocalMultiplayer,
    CRPublicServer,
    CRSingleplayer
)

class OpeningUserInput(DirectObject):
    def __init__(self, cr, launcher):
        self.cr = cr
        self.launcher = launcher
        self.dialogClass = OTPGlobals.getGlobalDialogClass()

        self.askServerPreference()

    def cleanup(dialogClass):
        dialogClass.cleanup()
        del dialogClass

    def clearText(self):
        self.entry.enterText('')

    def specifyGameserver(self, textEntered):
        gameserver = textEntered
        if not gameserver:
            base.startShow(self.cr, '127.0.0.1:7198')
        else:
            base.startShow(self.cr, gameserver)

    def localMultiplayerScreen(self):
        self.askForGameserver = self.dialogClass(message=CREnterGameserver, style=OTPDialog.NoButtons,
                                     doneEvent='cleanup', text_wordwrap=20, midPad=0.2, extraArgs=['askForGameserver'])
        self.accept('cleanup', self.cleanup, extraArgs=[self.askForGameserver])

        self.entry = DirectEntry(parent=self.askForGameserver , text="", scale=0.075, pos=(-0.6, 0, -0.3), command=self.specifyGameserver,
                                 width=16, cursorKeys=1, obscured=0, initialText="Gameserver", numLines=1, focus=1, focusInCommand=self.clearText)

        self.askForGameserver.show()

    def publicServerScreen(self):
        base.startShow(self.cr, config.ConfigVariableString('public-server-ip', '').getValue())

    def check_docker_available(self):
        """Check if Docker is installed and running."""
        try:
            result = subprocess.run(['docker', '--version'], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                return False
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        except Exception:
            return False
        
        # Check if Docker daemon is running
        try:
            result = subprocess.run(['docker', 'info'], capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False

    def check_port_ready_task(self, task, host, port, timeout, callback):
        """Check if a port is ready to accept connections (non-blocking task)."""
        if not hasattr(task, 'startTime'):
            task.startTime = time.time()
        
        if time.time() - task.startTime >= timeout:
            callback(False)
            return task.done
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                callback(True)
                return task.done
        except Exception:
            pass
        
        # Check again in 1 second
        return task.again

    def start_docker_containers(self):
        """Start Docker containers for singleplayer."""
        # Get the path to launch/docker directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        docker_dir = os.path.join(script_dir, '..', '..', '..', 'launch', 'docker')
        docker_dir = os.path.normpath(docker_dir)
        
        if not os.path.exists(docker_dir):
            print(f'ERROR: Docker directory not found: {docker_dir}')
            return False
        
        # Check if .env exists, create from env.example if not
        env_file = os.path.join(docker_dir, '.env')
        env_example = os.path.join(docker_dir, 'env.example')
        if not os.path.exists(env_file) and os.path.exists(env_example):
            try:
                import shutil
                shutil.copy(env_example, env_file)
            except Exception as e:
                print(f'WARNING: Could not create .env file: {e}')
        
        # Start Docker containers
        try:
            # Change to docker directory and run docker compose
            result = subprocess.run(
                ['docker', 'compose', 'up', '-d'],
                cwd=docker_dir,
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                print(f'ERROR: Failed to start Docker containers: {result.stderr}')
                return False
            return True
        except subprocess.TimeoutExpired:
            print('ERROR: Docker compose command timed out')
            return False
        except Exception as e:
            print(f'ERROR: Error starting Docker containers: {e}')
            return False

    def singlePlayerScreen(self):
        # Use Docker containers for singleplayer (no MongoDB required)
        builtins.gameServicesDialog = self.dialogClass(message=CRLoadingGameServices)
        builtins.gameServicesDialog.show()

        def startDockerAndConnect():
            # Check if Docker is available
            if not self.check_docker_available():
                builtins.gameServicesDialog.cleanup()
                del builtins.gameServicesDialog
                errorDialog = self.dialogClass(
                    message='Docker is not installed or not running. Please install Docker and ensure it is running before using singleplayer mode.',
                    style=OTPDialog.Acknowledge,
                    doneEvent='dockerErrorExit'
                )
                errorDialog.show()
                self.accept('dockerErrorExit', lambda: None)
                return

            # Update dialog message
            builtins.gameServicesDialog['text'] = CRLoadingGameServices + '\n\nStarting Docker containers...'

            # Start Docker containers
            if not self.start_docker_containers():
                builtins.gameServicesDialog.cleanup()
                del builtins.gameServicesDialog
                errorDialog = self.dialogClass(
                    message='Failed to start Docker containers. Please check Docker is running and try again.',
                    style=OTPDialog.Acknowledge,
                    doneEvent='dockerErrorExit'
                )
                errorDialog.show()
                self.accept('dockerErrorExit', lambda: None)
                return

            # Update dialog message
            builtins.gameServicesDialog['text'] = CRLoadingGameServices + '\n\nWaiting for servers to be ready...'

            # Wait for port 7198 to be ready (non-blocking)
            def on_port_check_result(is_ready):
                if not is_ready:
                    builtins.gameServicesDialog.cleanup()
                    del builtins.gameServicesDialog
                    errorDialog = self.dialogClass(
                        message='Servers did not start in time. Please check Docker logs and try again.',
                        style=OTPDialog.Acknowledge,
                        doneEvent='dockerErrorExit'
                    )
                    errorDialog.show()
                    self.accept('dockerErrorExit', lambda: None)
                else:
                    # Servers are ready, connect to localhost
                    builtins.gameServicesDialog.cleanup()
                    del builtins.gameServicesDialog
                    base.startShow(self.cr, '127.0.0.1:7198')
            
            # Start checking port in a task
            base.taskMgr.add(
                lambda task: self.check_port_ready_task(task, '127.0.0.1', 7198, 60, on_port_check_result),
                'checkDockerPort'
            )

        # Run in a task to avoid blocking
        base.taskMgr.doMethodLater(0.1, lambda task: startDockerAndConnect(), 'startDockerContainers')

    def decision(self, buttonValue = None):
        if buttonValue == 1: # buttonValue returning 1 = Singleplayer
            self.singlePlayerScreen()
        elif buttonValue == 0: # buttonValue returning 0 = Public Server
            self.publicServerScreen()
        elif buttonValue == -1: # buttonValue returning -1 = Local Multiplayer/Other Server
            self.localMultiplayerScreen()

    def askServerPreference(self):

        # Is an env var set?
        gameserver = os.getenv('GAMESERVER')
        if gameserver is not None:
            base.startShow(self.cr, gameserver)
            return

        if not config.ConfigVariableBool('local-multiplayer', False).getValue():
            self.askServerSpecification = self.dialogClass(message=CRSpecifyServerSelection, style=OTPDialog.ThreeChoiceCustom,
                                                           yesButtonText=CRSingleplayer, noButtonText=CRPublicServer, cancelButtonText=CRLocalMultiplayer,
                                                           command=self.decision, doneEvent='cleanup', text_wordwrap=20, buttonPadSF=4.0)
            self.askServerSpecification.show()
            self.accept('cleanup', self.cleanup, extraArgs=[self.askServerSpecification])
            return

        # Default behavior
        if not self.launcher.isDummy():
            base.startShow(self.cr, self.launcher.getGameServer())
        else:
            base.startShow(self.cr)
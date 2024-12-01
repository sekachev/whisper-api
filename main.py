import pystray
from PIL import Image
import multiprocessing
import logging
import sys
from pathlib import Path
import webbrowser
import traceback
import time  # Add this import
import api

def setup_tray_logging():
    log_file = Path('whisper.log')
    
    # Clear or truncate the log file at startup
    with open(log_file, 'w') as f:
        f.write('Starting application...\n')
    
    # Create a file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    
    # Configure the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add the file handler
    root_logger.addHandler(file_handler)


class WhisperTray:
    def __init__(self):
        self.icon = None
        self.server_process = None
        self.is_running = False

    def create_menu(self):
        return pystray.Menu(
            pystray.MenuItem("Start Server", self.start_server, checked=lambda item: self.is_running),
            pystray.MenuItem("Stop Server", self.stop_server),
            pystray.MenuItem("Open API docs", self.open_docs),
            pystray.MenuItem("View Logs", self.view_logs),
            pystray.MenuItem("Exit", self.exit_app)
        )

    def start_server(self):
        if not self.is_running:
            try:
                logging.info("Starting server process...")
                self.server_process = multiprocessing.Process(
                    target=api.run_server,
                    daemon=False
                )
                self.server_process.start()
                logging.info(f"Server process PID: {self.server_process.pid}")
                
                # Wait and check if server is actually responding
                import time
                import urllib.request
                import urllib.error
                
                # Try to connect to the server for up to 10 seconds
                start_time = time.time()
                while time.time() - start_time < 10:
                    try:
                        time.sleep(1)
                        if not self.server_process.is_alive():
                            raise Exception("Server process died")
                            
                        # Try to connect to the server
                        urllib.request.urlopen('http://localhost:8000/')
                        self.is_running = True
                        logging.info("Whisper API server started successfully")
                        return
                    except urllib.error.URLError:
                        continue
                    except Exception as e:
                        logging.error(f"Server check error: {e}")
                        break
                        
                # If we get here, server didn't start properly
                logging.error("Server process failed to start")
                if self.server_process.is_alive():
                    self.server_process.terminate()
                self.server_process = None
                    
            except Exception as e:
                logging.error(f"Failed to start server: {e}")
                logging.error(f"Traceback: {traceback.format_exc()}")
            
    def stop_server(self):
        if self.is_running and self.server_process:
            try:
                logging.info(f"Stopping server process (PID: {self.server_process.pid})")
                self.server_process.terminate()
                self.server_process.join(timeout=5)  # Wait up to 5 seconds
                if self.server_process.is_alive():
                    self.server_process.kill()  # Force kill if still alive
                self.is_running = False
                self.server_process = None
                logging.info("Whisper API server stopped")
            except Exception as e:
                logging.error(f"Failed to stop server: {e}")
                logging.error(f"Traceback: {traceback.format_exc()}")

    def open_docs(self):
        webbrowser.open('http://localhost:8000/docs')

    def view_logs(self):
        try:
            if sys.platform == 'win32':
                from os import startfile
                startfile('whisper.log')
            else:
                import subprocess
                subprocess.call(['xdg-open', 'whisper.log'])
        except Exception as e:
            logging.error(f"Failed to open log file: {e}")

    def exit_app(self):
        if self.is_running:
            self.stop_server()
        self.icon.stop()

    def run(self):
        try:
            # Load icon
            icon_path = Path(__file__).parent / 'voice.png'
            image = Image.open(icon_path)
            
            # Create system tray icon
            self.icon = pystray.Icon(
                "WhisperAPI",
                image,
                "Whisper API Server",
                self.create_menu()
            )

            # Start server automatically
            self.start_server()
            
            # Run the system tray
            self.icon.run()

        except Exception as e:
            logging.error(f"Application error: {e}")
            sys.exit(1)

if __name__ == "__main__":
    try:
        setup_tray_logging()  # Setup logging first
        logging.info("Starting application")
        
        # Log Python executable being used
        logging.info(f"Using Python executable: {sys.executable}")
        
        try:
            logging.info("Attempting to import api module")
            import api
            logging.info("Successfully imported api module")
        except Exception as e:
            logging.error(f"Failed to import api module: {str(e)}")
            logging.error(f"Traceback: {traceback.format_exc()}")
            sys.exit(1)
            
        multiprocessing.freeze_support()
        whisper_tray = WhisperTray()
        whisper_tray.run()
    except Exception as e:
        logging.error(f"Startup error: {str(e)}")
        logging.error(f"Full traceback: {traceback.format_exc()}")
        sys.exit(1)
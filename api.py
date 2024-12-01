from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import whisper
import tempfile
import os
import time
from typing import Optional
import logging
import torch
import warnings
from pathlib import Path

def setup_api_logging():
    log_file = Path('whisper.log')
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file)
        ]
    )

# Setup logging first
setup_api_logging()

# Then create the FastAPI app
app = FastAPI(
    title="Local Whisper API",
    description="A simple API for OpenAI's Whisper speech-to-text model",
    version="1.0.0"
)

# Now add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for model management
model = None
last_use_time = None
IDLE_TIMEOUT = 900  # 15 minutes in seconds

class TranscriptionResponse(BaseModel):
    text: str
    language: str
    segments: list

def load_model():
    global model, last_use_time
    if model is None:
        try:
            logging.info("Loading Whisper model...")
            # Check for CUDA
            device = "cuda" if torch.cuda.is_available() else "cpu"
            # Suppress the experimental feature warning
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=FutureWarning)
                warnings.filterwarnings("ignore", category=UserWarning)
                model = whisper.load_model(
                    "base",
                    device=device,
                    download_root=os.path.join(os.path.expanduser("~"), ".cache", "whisper")
                )
            last_use_time = time.time()
            logging.info(f"Model loaded successfully on {device}")
        except Exception as e:
            logging.error(f"Error loading model: {e}")
            raise HTTPException(status_code=500, detail="Failed to load model")
        
def check_and_unload_model():
    global model, last_use_time
    if model and last_use_time:
        if time.time() - last_use_time > IDLE_TIMEOUT:
            logging.info("Unloading model due to inactivity")
            model = None
            last_use_time = None

@app.get("/")
async def root():
    return {
        "message": "Welcome to Local Whisper API",
        "endpoints": {
            "/transcribe": "POST - Transcribe audio file",
            "/models": "GET - List available models"
        }
    }

@app.get("/models")
async def list_models():
    return {
        "available_models": ["base"],
        "current_model": "base",
        "model_loaded": model is not None
    }

@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    task: Optional[str] = "transcribe",
    language: Optional[str] = None
):
    global last_use_time
    
    # Check if model needs to be loaded
    check_and_unload_model()
    load_model()
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file.flush()
            
            options = {"task": task}
            if language:
                options["language"] = language
                
            result = model.transcribe(temp_file.name, **options)
            last_use_time = time.time()  # Reset the timer after successful use
            
        # Clean up
        os.unlink(temp_file.name)
        
        return {
            "text": result["text"],
            "language": result["language"],
            "segments": result["segments"]
        }
        
    except Exception as e:
        logging.error(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def run_server():
    import uvicorn
    try:
        logging.info("Starting uvicorn server...")
        
        # Simplified logging config for uvicorn
        log_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "simple": {
                    "format": "%(asctime)s - %(levelname)s - %(message)s"
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.FileHandler",
                    "filename": "whisper.log",
                    "formatter": "simple",
                }
            },
            "loggers": {
                "uvicorn": {
                    "handlers": ["default"],
                    "level": "INFO",
                }
            }
        }
        
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=8000, 
            log_level="info",
            log_config=log_config,
            access_log=False  # Disable access logging to simplify
        )
    except Exception as e:
        logging.error(f"Uvicorn server error: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    run_server()
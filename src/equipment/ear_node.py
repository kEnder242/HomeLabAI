import os
import time
import logging
import json
import numpy as np
import threading
import torch
from dedup_utils import get_new_text

# NeMo imports
try:
    from nemo.collections.asr.models import EncDecRNNTBPEModel
    from nemo.core.config import hydra_runner
    from nemo.utils import logging as nemo_logging
    # Temporarily set NeMo logging level to ERROR to reduce spam during debug
    nemo_logging.setLevel(logging.ERROR)
except ImportError as e:
    logging.error(f"[EAR_NODE] NeMo import failed: {e}")
    EncDecRNNTBPEModel = None

# Configuration
SILENCE_THRESHOLD = 100

class EarNode:
    def __init__(self, callback=None):
        if EncDecRNNTBPEModel is None:
            raise ImportError("NeMo EncDecRNNTBPEModel is not available. EarNode cannot be initialized.")
        
        self.callback = callback
        self.transcribing = False
        self.stop_event = threading.Event()

        # Configuration
        MODEL_NAME = "nvidia/nemotron-speech-streaming-en-0.6b"
        self.sample_rate = 16000
        self.model = None
        self.cuda_graph_failed = False # Flag to prevent recursive sledgehammering

        # --- Stub model loading if EAR_NODE_STUB_MODEL is set ---
        if os.environ.get("EAR_NODE_STUB_MODEL") == "1":
            logging.warning("👂 EarNode: Model loading stubbed by EAR_NODE_STUB_MODEL=1 environment variable.")
            self.model = None # Ensure model is explicitly None
            self.full_transcript = ""
            self.last_speech_time = time.time()
            self.turn_pending = False
            self.wake_signal_sent = False
            self.frame_buffer = []
            return # Skip full initialization

        logging.info(f"👂 EarNode: Attempting to load {MODEL_NAME}...")
        try:
            # Try to load model
            self.model = EncDecRNNTBPEModel.from_pretrained(model_name=MODEL_NAME)
            self.model.eval()
            
            # FIX: Force FP16 and clear cache to restore ~1.5GB footprint
            self.model = self.model.half() 
            self.model = self.model.to("cuda")
            torch.cuda.empty_cache()
            logging.info("👂 EarNode: Model loaded and moved to CUDA (FP16).")
            
            # Proactively trigger sledgehammer to prevent startup crashes on CUDA 12.8
            self._sledgehammer_disable_graphs()
            torch.cuda.empty_cache()
            logging.info("👂 EarNode: Sledgehammer applied proactively.")

        except Exception as e:
            logging.error(f"[EAR_NODE] FATAL: Error during NeMo model loading or CUDA setup: {e}", exc_info=True)
            # Attempt a fallback: Disable CUDA and try again if not already tried
            if not self.cuda_graph_failed:
                logging.warning("[EAR_NODE] Attempting fallback: Re-initializing with CUDA graphs explicitly disabled.")
                self.cuda_graph_failed = True # Mark as failed
                try:
                    # Clear model and re-attempt load without CUDA graphs
                    del self.model
                    torch.cuda.empty_cache()
                    self.model = EncDecRNNTBPEModel.from_pretrained(model_name=MODEL_NAME)
                    self.model.eval()
                    self.model = self.model.half()
                    self.model = self.model.to("cuda")
                    torch.cuda.empty_cache()
                    self._sledgehammer_disable_graphs() # Ensure disabled
                    logging.info("👂 EarNode: Model loaded successfully in fallback (Eager Mode).")
                except Exception as fallback_e:
                    logging.error(f"[EAR_NODE] FATAL: Fallback failed: {fallback_e}", exc_info=True)
                    raise ImportError(f"EarNode failed to load even with fallback: {e} / {fallback_e}")
            else:
                raise ImportError(f"EarNode failed to load: {e}")


        self.full_transcript = ""
        self.last_speech_time = time.time()
        self.turn_pending = False
        self.wake_signal_sent = False
        self.frame_buffer = []

    def _sledgehammer_disable_graphs(self):
        """Recursively disables CUDA graphs on all loopers in the model."""
        logging.info("[EAR_NODE] Activating _sledgehammer_disable_graphs...")
        self.cuda_graph_failed = True
        
        # NeMo 2.6.1 change_decoding_strategy requires a config object
        try:
            from omegaconf import OmegaConf
            cfg = OmegaConf.create({
                "strategy": "greedy",
                "can_improve_gpu_speed": False,
                "greedy": {"max_symbols": 10} # Standard default
            })
            self.model.change_decoding_strategy(cfg)
            logging.info("[EAR_NODE] Model decoding strategy changed via OmegaConf.")
        except Exception as e:
            logging.warning(f"[EAR_NODE] Failed to change decoding strategy via OmegaConf: {e}")
        
        # Specific to RNNTBPEModel, access the internal greedy_decoder and its looper
        # We need to be very aggressive here to find all looper objects
        found_looper = False
        if self.model and hasattr(self.model, 'decoding') and hasattr(self.model.decoding, 'decoding'):
            # The structure for nemotron-speech-streaming-en-0.6b is nested
            decoding_inner = self.model.decoding.decoding
            if hasattr(decoding_inner, 'decoding_loop'):
                try:
                    logging.info("[EAR_NODE] Forcing decoding_loop.force_cuda_graphs_mode('no_graphs')...")
                    decoding_inner.decoding_loop.force_cuda_graphs_mode('no_graphs')
                    logging.info("[EAR_NODE] CUDA graphs explicitly disabled on decoding_loop.")
                    found_looper = True
                except Exception as e:
                    logging.warning(f"[EAR_NODE] Failed to disable CUDA graphs on decoding_loop: {e}")
            
            # Check for computer loopers
            if hasattr(decoding_inner, 'decoding_computer'):
                computer = decoding_inner.decoding_computer
                if hasattr(computer, 'force_cuda_graphs_mode'):
                    try:
                        logging.info(f"[EAR_NODE] Forcing {type(computer).__name__}.force_cuda_graphs_mode('no_graphs')...")
                        computer.force_cuda_graphs_mode('no_graphs')
                        found_looper = True
                    except Exception as e:
                        logging.warning(f"[EAR_NODE] Failed to disable CUDA graphs on computer: {e}")

        if not found_looper:
            logging.info("[EAR_NODE] Model structure for direct CUDA graph disable not found, attempting generic search.")
            # Generic recursive search for 'force_cuda_graphs_mode'
            for name, module in self.model.named_modules():
                if hasattr(module, 'force_cuda_graphs_mode'):
                    try:
                        logging.info(f"[EAR_NODE] Found looper at {name}, disabling CUDA graphs...")
                        module.force_cuda_graphs_mode('no_graphs')
                        found_looper = True
                    except Exception as e:
                        logging.warning(f"[EAR_NODE] Failed to disable CUDA graphs on {name}: {e}")

    def process_audio(self, audio_chunk):
        """Processes an audio chunk and returns any transcribed text."""
        # This will only be called if self.model is successfully loaded
        try:
            # 1. Silence Check (RMS)
            rms = np.sqrt(np.mean(audio_chunk.astype(np.float32)**2))
            if rms < SILENCE_THRESHOLD:
                return None

            # Normalize audio: int16 to float32 normalized to [-1, 1]
            if audio_chunk.dtype == np.int16:
                audio_float = audio_chunk.astype(np.float32) / 32768.0
            else:
                audio_float = audio_chunk.astype(np.float32)

            # NeMo transcribe expects a list of numpy arrays or paths
            with torch.no_grad():
                hypotheses = self.model.transcribe(audio=[audio_float], verbose=False)
                
            if hypotheses and len(hypotheses) > 0 and hypotheses[0]:
                hyp = hypotheses[0]
                # Handle cases where it returns a list of lists or Hypothesis objects
                if isinstance(hyp, list) and len(hyp) > 0:
                    hyp = hyp[0]
                
                if hasattr(hyp, 'text'):
                    raw_text = hyp.text
                else:
                    raw_text = str(hyp)
                
                # 2. Deduplication via sliding window matching
                incremental_text = get_new_text(self.full_transcript, raw_text)
                
                if incremental_text and incremental_text.strip() != "":
                    self.full_transcript += " " + incremental_text
                    self.last_speech_time = time.time()
                    self.turn_pending = True
                    return incremental_text.strip()
            return None

        except Exception as e:
            logging.error(f"[EAR_NODE] Inference Error: {e}", exc_info=True)
            return None

    def check_turn_end(self, silence_timeout=1.2):
        """Checks if the user has stopped speaking."""
        if self.turn_pending and (time.time() - self.last_speech_time > silence_timeout):
            self.turn_pending = False
            self.wake_signal_sent = False # Reset for next turn
            query = self.full_transcript.strip()
            self.full_transcript = ""
            return query
        return None

    def start_transcribing(self, audio_queue):
        self.transcribing = True
        self.audio_queue = audio_queue
        self.thread = threading.Thread(target=self._transcription_loop)
        self.thread.daemon = True
        self.thread.start()

    def stop_transcribing(self):
        self.transcribing = False
        self.stop_event.set()
        if self.thread:
            self.thread.join()

    def _transcription_loop(self):
        while self.transcribing and not self.stop_event.is_set():
            try:
                audio_chunk = self.audio_queue.get(timeout=0.1)
                self.process_audio(audio_chunk)
            except Exception:
                pass # Queue empty, continue loop

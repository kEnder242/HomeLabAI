# Coffee Break Plan: Voice Gateway Setup
**Date:** Jan 6, 2026
**Time Limit:** 30 Minutes

## Phase 1: Linux Environment (Remote)
1.  [ ] Create `~/VoiceGateway`.
2.  [ ] Initialize `python3 -m venv .venv`.
3.  [ ] Attempt `sudo apt-get install -y ffmpeg libsndfile1 portaudio19-dev` (May fail if password needed; Skip if so).
4.  [ ] `pip install torch torchvision torchaudio` (CUDA version).
5.  [ ] `pip install nemo_toolkit[asr]` (This is the big one).

## Phase 2: Local Bridge (WSL)
1.  [ ] Create `sync_to_linux.sh` to allow rapid deployment of code from `HomeLabAIProject` to `z87-Linux`.

## Phase 3: Model Verification
1.  [ ] Run a Python script on Linux to `import nemo` and check for GPU availability.

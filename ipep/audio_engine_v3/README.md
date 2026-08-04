# EvidenceOps Consensus Transcription Mode v3

A provider-independent forensic transcription mode designed to reduce single-model errors in long legal and disciplinary recordings.

## What it borrows from published systems

- **Faster-Whisper / Whisper large-v3-turbo** for robust multilingual ASR, hotwords, beam search and efficient inference.
- **WhisperX** for VAD-based segmentation and forced word alignment.
- **NVIDIA Parakeet TDT** as an architecturally independent recogniser with timestamps.
- **pyannote Community-1** for speaker diarisation and exclusive speaker tracks.
- **OpenAI gpt-4o-transcribe-diarize** as an optional independent cloud hypothesis.
- **ROVER/MOVER-style voting** for recogniser fusion.

This repository does **not** copy proprietary model weights or hidden implementation code. Adapters call installed/public systems and the consensus layer is original EvidenceOps code.

## EvidenceOps mode

1. Preserve and hash the source.
2. Create zero-based, 16 kHz mono derivatives with 5-second overlap.
3. Run at least two independent recognisers. Recommended production set:
   - faster-whisper `large-v3-turbo` or `large-v3`, beam 5, VAD on, `condition_on_previous_text=False`;
   - NVIDIA `parakeet-tdt-0.6b-v2`, timestamps enabled;
   - optional `gpt-4o-transcribe-diarize` as a third vote.
4. Force-align Whisper output with WhisperX.
5. Diarise with pyannote `speaker-diarization-community-1`, preferably with a known speaker-count range.
6. Fuse words using weighted ROVER-style voting.
7. Apply only approved legal/entity corrections from a case lexicon; every correction is logged.
8. Send low-agreement words and overlap regions to a review queue.
9. Never present consensus output as certified without human listening verification.

## Recommended initial weights

- OpenAI diarised hypothesis: `1.25`
- Parakeet TDT: `1.10`
- Whisper large-v3/large-v3-turbo: `1.00`
- Gemini audio verification: `0.90`
- small/tiny Whisper screening models: `0.45–0.70`

Weights must be calibrated against a manually verified sample from the actual hearing environment.

## Outputs

- `consensus_transcript.txt`
- `consensus_words.json` with alternatives, source models and agreement
- `consensus_review_queue.json`
- `consensus_corrections.json`

## Acceptance gate

A legal passage can be marked `VERIFIED_FOR_QUOTATION` only when:

- at least two independent recognisers agree;
- word alignment and timestamps are present;
- speaker role is supported by diarisation or a recorded procedural handover;
- legal names and case references match the evidence lexicon;
- a human has listened to the cited audio window.

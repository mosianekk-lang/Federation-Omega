# EvidenceOps Consensus Transcription Mode v3.1

A proof-carrying, provider-independent transcription mode for legal, labour and disciplinary recordings.

## Core correction in v3.1

**Model count is not architecture count.** Two Whisper checkpoints, two Whisper runtimes, or a Whisper tiny/base comparison remain one `whisper_encoder_decoder` family. Production consensus requires at least two independently classified ASR architectures.

## Recommended production hypotheses

1. Faster-Whisper `large-v3-turbo` or `large-v3`
   - beam size 5;
   - VAD enabled;
   - `condition_on_previous_text=False`;
   - hearing-specific hotwords.
2. NVIDIA NeMo `parakeet-tdt-0.6b-v2`
   - word and segment timestamps;
   - preserved alignments;
   - case-term word boosting where supported.
3. One independent cloud hypothesis when authorised:
   - OpenAI `gpt-4o-transcribe-diarize`, or
   - Google Speech-to-Text Chirp 3.
4. WhisperX for forced word alignment.
5. pyannote Community-1 for speaker turns and exclusive diarisation.

Alignment and diarisation tools improve timing and speaker attribution, but they do not count as additional ASR architecture votes.

## v3.1 accuracy controls

- multi-architecture gate;
- weighted ROVER-style word fusion;
- disagreement and legal-criticality review priority;
- exact-alias-only legal lexicon corrections;
- repetition suppression with retained raw evidence;
- hearing-specific WER calibration;
- critical-passage escalation instead of full-record expensive reruns;
- quotation release gate requiring human listening and an audio-window hash;
- stereo-channel and conservative denoising opportunities treated as parallel derivatives only.

## Output contracts

- `consensus_transcript.txt`
- `consensus_words.json`
- `consensus_review_queue.json`
- `consensus_corrections.json`
- calibration results
- quotation-release receipt

## Quotation acceptance gate

A passage may be marked `VERIFIED_FOR_QUOTATION` only when:

- at least two independent ASR architecture families support it;
- word timestamps are present;
- speaker role is supported by diarisation or a recorded procedural handover;
- legal names and case references are verified against source documents;
- a human listened to the exact audio window;
- the reviewed audio-window hash is recorded.

## Truth boundary

Consensus reduces individual recogniser errors. It does not make an automated transcript certified or verbatim by itself.

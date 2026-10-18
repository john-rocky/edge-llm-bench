# Answer check of the LiteRT-LM records (outputSample = the first ~200 characters the app stored; not the whole text)

| round | launch | model | ctx | regime | prompt tok | out tok | stop | numbered list starts | refusal / filler words | first 160 chars |
|---|---|---|---:|---|---|---|---|---|---|---|
| 1 | 1 | gemma-4-E4B-it-litert-lm | 8192 | cold | 1654 | 256 | length | yes | — | Here are 25 distinct things on-device AI lets a phone do that a cloud model cannot:\n\n1. **Real-time, Offline Voice Transcription:** On-device AI can transcrib |
| 1 | 1 | gemma-4-E4B-it-litert-lm | 8192 | warm | 1654 | 256 | length | yes | — | Here are 25 distinct things on-device AI lets a phone do that a cloud model cannot:\n\n1. **Real-time, Offline Voice Transcription:** On-device AI can transcrib |
| 1 | 2 | gemma-4-E2B-it-litert-lm | 8192 | cold | 1654 | 256 | length | yes | — | Here are 25 distinct things an on-device AI on a phone can do that a cloud model cannot:\n\n1. **Real-time, low-latency voice commands:** On-device AI can proce |
| 1 | 2 | gemma-4-E2B-it-litert-lm | 8192 | warm | 1654 | 256 | length | yes | — | Here are 25 distinct things an on-device AI on a phone can do that a cloud model cannot:\n\n1. **Real-time, low-latency voice commands:** On-device AI can proce |

LiteRT records: 4; short answers (< budget − 2): 0; samples with refusal / filler words: 0. A lexical screen is not a semantic review: read the samples.

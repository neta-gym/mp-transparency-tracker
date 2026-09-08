"""Neta Gym Voice - ask any Indian MP's record by voice, in Hindi or English.

A voice agent layer over the MP Transparency Tracker dataset. The data
answers are fully deterministic (rule-based, source-backed) - the same
invariant as the scoring pipeline. AssemblyAI powers the voice transport
(speech-to-text, turn-taking, text-to-speech) when ASSEMBLYAI_API_KEY is
set; without a key the text endpoints and the whole test-suite run offline.
"""

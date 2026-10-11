"""Reproduce Onigiri's original tone pairs without third-party audio samples.

Run this file with Python 3 to regenerate the fourteen bundled PCM WAV files.
Start rises into focus; End resolves downward in the same sound family.
"""

import math
from pathlib import Path
import struct
import sys
import wave

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from study_tools.pomodoro_tones import BUILTIN_SOUNDS, TONE_PAIRS  # noqa: E402

SAMPLE_RATE = 44100
OUTPUT_DIR = Path(__file__).resolve().parent

# Fundamental frequency, note length, spacing, attack, partials.
# Inharmonic partials give struck objects their own character; keys and
# digital cues use harmonic partials. Both events share the exact instrument.
INSTRUMENTS = {
    "soft_bell": (
        659.25, 0.90, 0.22, 0.009, ((1, 1), (2.76, .12), (4.07, .04))
    ),
    "classic_chime": (
        783.99, 0.95, 0.20, 0.005, ((1, 1), (2, .28), (3, .10))
    ),
    "bamboo": (
        392.00, 0.34, 0.17, 0.003, ((1, 1), (2.71, .35), (5.1, .12))
    ),
    "glass": (
        1046.50, 0.70, 0.20, 0.004, ((1, 1), (2.32, .24), (4.25, .09))
    ),
    "digital": (523.25, 0.26, 0.19, 0.024, ((1, 1), (2, .08))),
    "warm_keys": (
        329.63, 0.80, 0.24, 0.018, ((1, 1), (2, .25), (3, .08))
    ),
    "singing_bowl": (
        220.00, 1.70, 0.36, 0.028, ((1, 1), (2.71, .30), (5.4, .06))
    ),
}


def render_tone(family, event):
    """Mix three softly enveloped notes with no clipping or hard edges."""
    base, length, spacing, attack, partials = INSTRUMENTS[family]
    # One major-pentatonic motif, rising for Start and resolving for End.
    semitones = (0, 4, 7) if event == "start" else (7, 4, 0)
    duration = length + 2 * spacing + 0.06
    samples = [0.0] * math.ceil(duration * SAMPLE_RATE)
    for note_index, semitone in enumerate(semitones):
        frequency = base * 2 ** (semitone / 12)
        offset = round((0.025 + note_index * spacing) * SAMPLE_RATE)
        for index in range(round(length * SAMPLE_RATE)):
            t = index / SAMPLE_RATE
            envelope = (
                (1 - math.exp(-t / attack)) * math.exp(-5 * t / length)
            )
            # Final fade guarantees a zero-amplitude boundary in every file.
            envelope *= min(1.0, (length - t) / 0.04)
            value = 0.0
            for ratio, amplitude in partials:
                # Upper partials decay sooner for a mellow, non-alarm cue.
                decay = math.exp(-t * (ratio - 1) * 1.5 / length)
                value += amplitude * decay * math.sin(
                    2 * math.pi * frequency * ratio * t
                )
            samples[offset + index] += value * envelope
    peak = max(abs(value) for value in samples)
    # Equal RMS gives quieter instruments a usable level, with a conservative
    # peak ceiling so resonant partials never become sharp or clip.
    rms = math.sqrt(
        sum(value * value for value in samples) / len(samples)
    )
    gain = min(0.10 / rms, 0.50 / peak)
    return b"".join(
        struct.pack("<h", round(value * gain * 32767)) for value in samples
    )


def main():
    for family, label, start_key, end_key in TONE_PAIRS:
        for event, key in (("start", start_key), ("end", end_key)):
            output = OUTPUT_DIR / BUILTIN_SOUNDS[key]
            frames = render_tone(family, event)
            with wave.open(str(output), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(SAMPLE_RATE)
                audio.writeframes(frames)
            print(f"{label} {event}: {output.name}")


if __name__ == "__main__":
    main()

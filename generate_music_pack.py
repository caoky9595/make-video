import math
import os
import random
import struct
import wave

OUT_DIR = "audio_bg"
SAMPLE_RATE = 32000
DURATION_SEC = 18.0
TRACK_COUNT = 40
MASTER_PEAK = 0.92

os.makedirs(OUT_DIR, exist_ok=True)

# Replace previous auto-generated pack to avoid duplicated stale tracks.
for existing in os.listdir(OUT_DIR):
    if existing.startswith("bgm_") and existing.lower().endswith(".wav"):
        os.remove(os.path.join(OUT_DIR, existing))


MOODS = [
    {
        "name": "sad_piano_emotional",
        "bpm": 80,
        "root": 220.0,
        "chords": [[0, 3, 7], [7, 10, 14], [5, 8, 12], [3, 7, 10]],
        "energy": 0.45,
        "lead_mix": 0.20,
    },
    {
        "name": "dark_suspense_cinematic",
        "bpm": 92,
        "root": 174.6,
        "chords": [[0, 6, 7], [2, 5, 9], [0, 5, 10], [3, 7, 10]],
        "energy": 0.62,
        "lead_mix": 0.16,
    },
    {
        "name": "happy_upbeat",
        "bpm": 118,
        "root": 261.6,
        "chords": [[0, 4, 7], [5, 9, 12], [7, 11, 14], [4, 7, 11]],
        "energy": 0.75,
        "lead_mix": 0.30,
    },
    {
        "name": "lofi_chill",
        "bpm": 88,
        "root": 233.1,
        "chords": [[0, 3, 7], [5, 8, 12], [7, 10, 14], [3, 7, 10]],
        "energy": 0.50,
        "lead_mix": 0.22,
    },
    {
        "name": "inspiring_motivational",
        "bpm": 110,
        "root": 246.9,
        "chords": [[0, 4, 7], [2, 5, 9], [5, 9, 12], [7, 11, 14]],
        "energy": 0.68,
        "lead_mix": 0.28,
    },
    {
        "name": "ambient_soft_story",
        "bpm": 76,
        "root": 196.0,
        "chords": [[0, 5, 9], [3, 7, 10], [5, 8, 12], [2, 5, 9]],
        "energy": 0.40,
        "lead_mix": 0.14,
    },
    {
        "name": "romantic_warm",
        "bpm": 98,
        "root": 220.0,
        "chords": [[0, 4, 7], [4, 7, 11], [5, 9, 12], [3, 7, 10]],
        "energy": 0.55,
        "lead_mix": 0.24,
    },
    {
        "name": "epic_trailer_drive",
        "bpm": 126,
        "root": 164.8,
        "chords": [[0, 7, 12], [3, 10, 15], [5, 12, 17], [7, 14, 19]],
        "energy": 0.82,
        "lead_mix": 0.34,
    },
]


def semitone_to_freq(root, semi):
    return root * (2.0 ** (semi / 12.0))


def osc(freq, t, kind="sine"):
    x = 2.0 * math.pi * freq * t
    if kind == "triangle":
        return (2.0 / math.pi) * math.asin(math.sin(x))
    if kind == "soft_saw":
        a = math.sin(x)
        b = 0.5 * math.sin(2.0 * x)
        c = 0.33 * math.sin(3.0 * x)
        return 0.55 * a + 0.30 * b + 0.15 * c
    return math.sin(x)


def smooth_step(edge0, edge1, x):
    if x <= edge0:
        return 0.0
    if x >= edge1:
        return 1.0
    v = (x - edge0) / (edge1 - edge0)
    return v * v * (3.0 - 2.0 * v)


def build_track(idx, mood):
    rng = random.Random(2026 + idx)
    bpm = mood["bpm"] + rng.randint(-4, 4)
    beat = 60.0 / bpm
    bar = beat * 4.0
    total = int(SAMPLE_RATE * DURATION_SEC)
    root = mood["root"] * (1.0 + rng.uniform(-0.02, 0.02))
    stereo_spread = 0.0018 + rng.uniform(0.0, 0.0015)

    left = [0.0] * total
    right = [0.0] * total
    peak = 1e-9

    for n in range(total):
        t = n / SAMPLE_RATE
        bar_pos = int(t / bar) % len(mood["chords"])
        section = 0 if t < DURATION_SEC * 0.52 else 1
        chord = mood["chords"][bar_pos]

        # Intro/outro fade for cleaner looping in short videos.
        fade_in = smooth_step(0.0, 0.6, t)
        fade_out = 1.0 - smooth_step(DURATION_SEC - 1.2, DURATION_SEC, t)
        macro_env = fade_in * fade_out

        # Kick/snare/hat rhythm (simple but effective for TikTok pacing).
        in_beat = t % beat
        kick_env = math.exp(-in_beat * 26.0)
        kick = 0.85 * math.sin(2.0 * math.pi * (46.0 + 18.0 * math.exp(-in_beat * 12.0)) * t) * kick_env

        snare_pos = (t + beat * 0.5) % (beat * 2.0)
        snare_env = math.exp(-snare_pos * 34.0)
        snare_noise = (rng.random() * 2.0 - 1.0)
        snare = 0.28 * snare_noise * snare_env

        hat_pos = t % (beat * 0.5)
        hat_env = math.exp(-hat_pos * 90.0)
        hat = 0.06 * (rng.random() * 2.0 - 1.0) * hat_env

        # Sidechain-like dip when kick hits to keep voice space.
        sidechain = max(0.45, 1.0 - kick_env * 0.42)

        # Chord pad
        pad = 0.0
        for semi in chord:
            f = semitone_to_freq(root, semi)
            pad += osc(f, t + stereo_spread, "soft_saw")
        pad /= max(1, len(chord))
        pad *= 0.42 * mood["energy"]

        # Bass (root + octave)
        bass_f = semitone_to_freq(root * 0.5, chord[0])
        bass = 0.35 * osc(bass_f, t, "triangle")
        bass += 0.12 * osc(bass_f * 2.0, t, "sine")

        # Lead arp
        arp_step = int((t / (beat * 0.5))) % len(chord)
        lead_f = semitone_to_freq(root * (2.0 if section else 1.5), chord[arp_step])
        lead = osc(lead_f, t, "sine") * mood["lead_mix"]
        if section == 1:
            lead += 0.08 * osc(lead_f * 1.5, t, "sine")

        core = (pad + bass + lead) * sidechain
        drums = kick + snare + hat
        mix = (core + drums) * macro_env

        # Slight stereo decorrelation.
        l = mix + 0.04 * osc(lead_f * 1.01, t + stereo_spread, "sine")
        r = mix + 0.04 * osc(lead_f * 0.99, t - stereo_spread, "sine")

        left[n] = l
        right[n] = r
        peak = max(peak, abs(l), abs(r))

    gain = MASTER_PEAK / peak
    return left, right, gain, bpm


def to_i16(v):
    s = int(max(-1.0, min(1.0, v)) * 32767.0)
    if s > 32767:
        return 32767
    if s < -32768:
        return -32768
    return s


generated = 0
for i in range(TRACK_COUNT):
    mood = MOODS[i % len(MOODS)]
    left, right, gain, bpm = build_track(i, mood)
    name = mood["name"]
    filename = f"bgm_{i + 1:02d}_{name}_{bpm}bpm.wav"
    path = os.path.join(OUT_DIR, filename)

    with wave.open(path, "w") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        for l, r in zip(left, right):
            wf.writeframes(struct.pack("<hh", to_i16(l * gain), to_i16(r * gain)))

    generated += 1

print(f"created {generated} emotional tracks in {OUT_DIR}/")


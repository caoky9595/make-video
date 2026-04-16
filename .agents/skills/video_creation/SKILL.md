---
name: Video Creation Automation
description: Automates the process of generating a video from a script, generating TTS, finding background music/videos, and combining them.
---

# Video Creation Skill

This skill allows the agent to automatically build short form videos (like TikToks) based on scripts provided by the user.

## Pre-requisites
- Ensure `tts.py` and `bg_finder.py` are functioning correctly.
- The user should only need to provide a topic or a script text.

## Steps

1. **Script Generation**: Read `script.txt` to get the core content. Edit or improve the script if requested by the user.
2. **Text to Speech (TTS)**: Run `python tts.py` to generate the audio file for the script. Verify that the output audio file was created successfully.
3. **Background Finding**: Run `python bg_finder.py` to fetch appropriate background content (images or videos) that matches the mood of the script.
4. **Assembly**: (If an assembly script exists) run it to combine the TTS audio and the background into a final `.mp4` video.

## Notes
- Be sure to check the output of each Python script for errors. If a script fails, debug it by checking dependencies (e.g., ffmpeg or pip packages).
- Keep video output organized in a dedicated `output/` folder.

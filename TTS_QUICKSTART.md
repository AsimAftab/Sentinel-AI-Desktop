# 🔊 Sentinel AI - Text-to-Speech Quick Start

## Setup in 3 Steps

### Step 1: Get ElevenLabs API Key (2 minutes)
1. Go to **https://elevenlabs.io/**
2. Sign up for free account
3. Go to **Profile → API Key**
4. Copy your API key

### Step 2: Add to .env File (1 minute)
Open `Sentinel-AI-Backend/.env` and add:

```env
ELEVENLABS_API_KEY=your_api_key_here
ELEVENLABS_VOICE_ID=EXAVITQu4vr4xnSDxMaL
TTS_ENABLED=true
```

### Step 3: Test It! (30 seconds)
```bash
python launcher.py
```

Say: **"Sentinel"** → **"Hello"** → Listen for the voice response!

---

## That's It!

Sentinel now speaks responses using natural AI voices!

### What Changed?

**Before:**
1. Say "Sentinel"
2. Say "play some music"
3. See text response ✅
4. No voice ❌

**After:**
1. Say "Sentinel"
2. Say "play some music"
3. See text response ✅
4. **Hear voice response** ✅ 🔊

---

## Voice Options

### Popular Voices:

| Voice | ID | Type |
|-------|-----|------|
| **Sarah** (default) | `EXAVITQu4vr4xnSDxMaL` | Female, warm |
| **Rachel** | `21m00Tcm4TlvDq8ikWAM` | Female, professional |
| **Antoni** | `ErXwobaYiN019PkySvjV` | Male, friendly |
| **Adam** | `pNInz6obpgDQGcFmaJgB` | Male, clear |

To change voice, update `ELEVENLABS_VOICE_ID` in `.env`

### See All Voices:
```bash
cd Sentinel-AI-Backend
python src/utils/text_to_speech.py
```

---

## Troubleshooting

### ❌ "API key not found"
→ Check `.env` file exists in `Sentinel-AI-Backend/` folder
→ Make sure no spaces: `ELEVENLABS_API_KEY=sk_xxx`

### ❌ No sound plays
→ Check system volume
→ Check speakers/headphones connected
→ Run test: `python src/utils/text_to_speech.py`

### ❌ "Quota exceeded" or "Model deprecated"
→ Free tier: 10,000 chars/month (~300 responses)
→ Model updated to `eleven_turbo_v2` (free tier compatible)
→ Temporarily disable: `TTS_ENABLED=false`

---

## Free Tier Limits

- ✅ **10,000 characters/month** FREE
- ✅ All voices included
- ✅ ~7-10 minutes of speech
- ✅ ~300 responses/month
- ✅ No credit card required

---

## Example Conversations

### Weather Query
**You:** "Sentinel, what's the weather in Tokyo?"
**Sentinel:** 🔊 "The temperature in Tokyo is 18 degrees Celsius with clear skies and 65% humidity."

### Music Request
**You:** "Sentinel, play some jazz"
**Sentinel:** 🔊 "I've opened YouTube Music with jazz playlists. The first playlist should start playing!"

### News Request
**You:** "Sentinel, latest tech news"
**Sentinel:** 🔊 "Here are today's top tech headlines. First, Apple announces new AI features..."

---

## Next Steps

✅ **You're done!** Sentinel can now speak!

**Optional:**
- Try different voices (see Voice Options above)
- Read full guide: `ELEVENLABS_SETUP.md`
- Adjust voice settings in `src/utils/text_to_speech.py`

---

**Need Help?** See the full guide at `ELEVENLABS_SETUP.md`

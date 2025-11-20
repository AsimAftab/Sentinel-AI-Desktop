# ElevenLabs Text-to-Speech Setup Guide

## Overview
Sentinel AI now includes ElevenLabs text-to-speech integration, allowing the AI to speak responses back to you with natural-sounding voices!

---

## 1. Get Your ElevenLabs API Key

### Step 1: Create Account
1. Go to [https://elevenlabs.io/](https://elevenlabs.io/)
2. Click **"Sign Up"** (or "Get Started")
3. Create a free account using email or Google

### Step 2: Get API Key
1. Log in to your ElevenLabs account
2. Click on your **profile icon** (top right)
3. Select **"Profile"** from the dropdown
4. Scroll down to find **"API Key"** section
5. Click **"Copy"** to copy your API key

### Free Tier Limits
- **10,000 characters/month** (approximately 7-10 minutes of speech)
- Access to all voices
- Commercial use allowed
- No credit card required

---

## 2. Configure Sentinel AI

### Add API Key to Environment File

1. Open `Sentinel-AI-Backend/.env` file
2. Add your ElevenLabs API key:

```env
# ElevenLabs Text-to-Speech
ELEVENLABS_API_KEY=your_api_key_here_paste_it_here
```

### Optional: Choose a Voice

Default voice is **Sarah** (warm, friendly female voice).

To use a different voice:

```env
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
```

#### Popular Voice IDs:

| Voice Name | Voice ID | Description |
|------------|----------|-------------|
| **Sarah** | `EXAVITQu4vr4xnSDxMaL` | Female, warm and friendly (default) |
| **Rachel** | `21m00Tcm4TlvDq8ikWAM` | Female, calm and professional |
| **Antoni** | `ErXwobaYiN019PkySvjV` | Male, friendly and conversational |
| **Arnold** | `VR6AewLTigWG4xSOukaG` | Male, deep and authoritative |
| **Adam** | `pNInz6obpgDQGcFmaJgB` | Male, clear and engaging |
| **Bella** | `EXAVITQu4vr4xnSDxMaL` | Female, youthful and upbeat |
| **Josh** | `TxGEqnHWrfWFTfGW9XjX` | Male, warm and natural |

### Optional: Enable/Disable TTS

To disable text-to-speech temporarily without removing the API key:

```env
TTS_ENABLED=false
```

To enable (default):

```env
TTS_ENABLED=true
```

---

## 3. View All Available Voices

To see a complete list of all voices available with your account:

```bash
cd Sentinel-AI-Backend
python src/utils/text_to_speech.py
```

This will:
1. Display a list of available voices with IDs
2. Play a test message using your configured voice

---

## 4. How It Works

### Workflow
1. You say: **"Sentinel"** (wake word)
2. You say your command: **"What's the weather in London?"**
3. Sentinel processes the request
4. Sentinel displays the response (text)
5. **Sentinel speaks the response** using ElevenLabs (NEW!)

### Text Cleaning
The TTS system automatically:
- Removes markdown formatting (`**bold**`, `*italic*`)
- Removes emojis (🎵, 🌤️, etc.)
- Removes URLs and links
- Removes agent prefixes like "(Music agent):"
- Keeps only natural speech-friendly text

### Example

**User Command:**
"Play some jazz music"

**LangGraph Text Response:**
```
🎵 (Music agent): I've opened YouTube Music search for **"jazz music playlist."** You can click on the first result to start playing!
```

**What Gets Spoken:**
```
I've opened YouTube Music search for "jazz music playlist." You can click on the first result to start playing!
```

---

## 5. Testing Your Setup

### Quick Test

1. Make sure your `.env` file has the API key:
```env
ELEVENLABS_API_KEY=sk_xxxxxxxxxxxxxxxxxxxxx
```

2. Run Sentinel:
```bash
python launcher.py
```

3. Test the voice:
   - Say: **"Sentinel"**
   - Say: **"Hello"**
   - Listen for the spoken response!

### Test TTS Directly

```bash
cd Sentinel-AI-Backend
python src/utils/text_to_speech.py
```

This runs a standalone test and plays: "Hello! I am Sentinel, your AI assistant. How can I help you today?"

---

## 6. Troubleshooting

### Problem: "ELEVENLABS_API_KEY not found"
**Solution:**
- Make sure `.env` file is in `Sentinel-AI-Backend/` directory
- Verify the key is spelled correctly: `ELEVENLABS_API_KEY`
- No spaces before or after the `=` sign
- No quotes around the key (unless they're part of the actual key)

### Problem: No sound plays
**Solution:**
- Check your system volume
- Make sure speakers/headphones are connected
- Try running the test script: `python src/utils/text_to_speech.py`
- Check that pygame is installed: `pip install pygame`

### Problem: "API key is invalid"
**Solution:**
- Copy the API key again from ElevenLabs dashboard
- Make sure you copied the entire key
- Check if your ElevenLabs account is active

### Problem: Voice sounds robotic
**Solution:**
- Try a different voice ID
- Some voices are more natural than others
- Premium voices (with paid plan) sound even better

### Problem: "Quota exceeded"
**Solution:**
- Free tier: 10,000 characters/month
- Check usage at: https://elevenlabs.io/app/usage
- Wait for monthly reset or upgrade to paid plan
- Temporarily disable TTS: `TTS_ENABLED=false`

---

## 7. Advanced Configuration

### Voice Settings

You can customize voice characteristics in `src/utils/text_to_speech.py`:

```python
voice_settings=VoiceSettings(
    stability=0.5,        # 0-1: Higher = more consistent, Lower = more expressive
    similarity_boost=0.75, # 0-1: How closely to match the original voice
    style=0.0,            # 0-1: Exaggeration of the style
    use_speaker_boost=True # Enhance clarity
)
```

### Changing Voice Model

**Default model:** `eleven_turbo_v2` (FREE tier compatible, fast & high quality)

Other FREE tier compatible models in `text_to_speech.py`:
- `eleven_turbo_v2` - Best for free tier (current default)
- `eleven_multilingual_v2` - Supports multiple languages

**Note:** `eleven_monolingual_v1` and `eleven_multilingual_v1` are NO LONGER available on free tier

---

## 8. Cost Management

### Free Tier (Recommended for Testing)
- **10,000 characters/month** FREE
- All voices included
- Good for ~300 responses/month

### Starter Plan ($5/month)
- **30,000 characters/month**
- ~1,000 responses/month
- More voices and customization

### Creator Plan ($22/month)
- **100,000 characters/month**
- Professional voice cloning
- Commercial use

### Tips to Reduce Usage:
1. Disable TTS for testing: `TTS_ENABLED=false`
2. Use shorter responses
3. Only enable for final demonstrations
4. Monitor usage at: https://elevenlabs.io/app/usage

---

## 9. Alternative: Local TTS (Free, Offline)

If you want free, unlimited TTS (but lower quality), you can use `pyttsx3` instead:

```bash
pip install pyttsx3
```

Then modify `orchestrator.py` to use pyttsx3 instead of ElevenLabs.

---

## 10. Next Steps

### After Setup:
1. ✅ Add API key to `.env`
2. ✅ Test with: `python src/utils/text_to_speech.py`
3. ✅ Run Sentinel: `python launcher.py`
4. ✅ Say "Sentinel" → "Hello" → Listen!

### Customize:
- Try different voices (see section 3)
- Adjust voice settings (see section 7)
- Monitor your usage at ElevenLabs dashboard

---

## 11. Complete .env Example

Here's a complete example with all keys:

```env
# Backend - Sentinel AI Configuration

# Wake Word Detection
PORCUPINE_KEY=your_porcupine_key_here

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your_azure_key_here
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
AZURE_OPENAI_API_VERSION=2023-05-15

# Web Search
TAVILY_API_KEY=tvly-your_key_here

# Spotify Music
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
SPOTIPY_REDIRECT_URI=http://localhost:8888/callback

# ElevenLabs Text-to-Speech (NEW!)
ELEVENLABS_API_KEY=sk_your_elevenlabs_key_here
ELEVENLABS_VOICE_ID=EXAVITQu4vr4xnSDxMaL
TTS_ENABLED=true

# Lyrics (Optional)
GENIUS_API_TOKEN=your_genius_token_here
```

---

## 12. Demo Video Scenario

Perfect for showcasing Sentinel with voice:

1. **Wake word:** "Sentinel"
2. **Command:** "What's the weather in London?"
3. **Sentinel speaks:** "The temperature in London is 15 degrees Celsius with partly cloudy skies..."

4. **Command:** "Play some jazz music"
5. **Sentinel speaks:** "I've opened YouTube with a jazz music playlist. The first video should start playing shortly!"

6. **Command:** "Tell me the latest news"
7. **Sentinel speaks:** "Here are today's headlines. Breaking news: ..."

---

**Questions?** Check the troubleshooting section or create an issue on GitHub!

**Last Updated:** 2025-11-21

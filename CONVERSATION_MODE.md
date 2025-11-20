# 💬 Conversation Continuation Mode

## Overview
Sentinel AI now supports **multi-turn conversations**! When the agent asks follow-up questions, you can continue the conversation without saying "Sentinel" again.

---

## 🎯 How It Works

### Before (Single Turn):
```
You: "Sentinel, create a meeting"
Agent: "What should it be about?"
[Conversation ends - need to say "Sentinel" again]
```

### After (Multi-Turn):
```
You: "Sentinel, create a meeting"
Agent: "What should it be about and when?"
💬 [Automatically listening for follow-up...]
You: "Team standup tomorrow at 2 PM"
Agent: "Meeting scheduled!"
✅ [Conversation complete]
```

---

## 🔄 Conversation Flow

```
1. Wake Word Detected ("Sentinel")
   ↓
2. Listen for Initial Command
   ↓
3. Get AI Response
   ↓
4. Check: Is it a follow-up question?
   ├─ YES → Continue listening (no wake word needed)
   │         ↓
   │      Listen for follow-up (10 sec timeout)
   │         ↓
   │      Add to conversation history
   │         ↓
   │      Back to step 3
   │
   └─ NO → Conversation complete
             ↓
          Wait for wake word again
```

---

## 🎤 Example Conversations

### Example 1: Meeting Scheduling
```
You: "Sentinel, schedule a meeting"

Agent: "Sure, what should the meeting be about and when?"
💬 Waiting for follow-up...

You: "Sprint planning tomorrow at 10 AM"

Agent: "Meeting scheduled! Sprint Planning tomorrow at 10:00 AM"
✅ Conversation complete
```

### Example 2: Music with Clarification
```
You: "Sentinel, play some music"

Agent: "What genre or artist would you like?"
💬 Waiting for follow-up...

You: "Jazz music"

Agent: "Opening YouTube with jazz playlists..."
✅ Conversation complete
```

### Example 3: Cancelling Mid-Conversation
```
You: "Sentinel, schedule a meeting"

Agent: "When would you like to schedule it?"
💬 Waiting for follow-up...

You: "Cancel"

Agent: "Okay, cancelled."
✅ Conversation complete
```

---

## 🎛️ Configuration

### Timeouts

**Follow-up timeout:** 10 seconds
- If you don't respond within 10 seconds, conversation ends

**Phrase time limit:** 15 seconds
- Maximum speaking time for follow-up responses

**Max conversation turns:** 5
- Maximum back-and-forth exchanges before auto-ending

### Exit Phrases

Say any of these to cancel the conversation:
- "cancel"
- "nevermind" / "never mind"
- "stop"
- "quit"
- "exit"

---

## 🔍 Follow-Up Detection

The system detects follow-up questions by looking for:

### Question Keywords:
- "could you"
- "can you"
- "would you"
- "what", "when", "where", "which", "who", "how"
- "do you want"
- "would you like"
- "please provide"
- "please tell"
- "let me know"
- "specify"
- "?" (question mark)

### Example Responses That Trigger Follow-Up:
✅ "What should the meeting be about?"
✅ "Could you tell me when?"
✅ "Which song would you like?"
✅ "Please specify the date and time."

### Example Responses That Don't:
❌ "Meeting created successfully."
❌ "Playing music now."
❌ "Here's the weather for London."

---

## 📊 Visual Indicators

### Console Output:

```
🟢 Waiting for wake word...
🎙️ Listening for command...
🧠 Recognized: create a meeting
🤖 LangGraph response: What should it be about?
🔊 Speaking: What should it be about?
💬 Waiting for follow-up... (or say 'cancel' to stop)
🧠 Follow-up: team standup tomorrow at 2 PM
🤖 LangGraph response: Meeting scheduled!
🔊 Speaking: Meeting scheduled!
✅ Conversation complete
```

---

## 🧪 Testing

### Test 1: Simple Follow-Up
```bash
python launcher.py
```

```
Say: "Sentinel, create a meeting"
Wait for: "What should it be about?"
Say: "Team sync at 3 PM"
```

**Expected:** Meeting created without needing "Sentinel" again

### Test 2: Multiple Turns
```
Say: "Sentinel, schedule a meeting"
Say: "Tomorrow"
Say: "At 2 PM"
Say: "Called Sprint Planning"
```

**Expected:** Each response continues the conversation

### Test 3: Cancellation
```
Say: "Sentinel, create a meeting"
Wait for: "What should it be about?"
Say: "Cancel"
```

**Expected:** "Okay, cancelled" and conversation ends

### Test 4: Timeout
```
Say: "Sentinel, create a meeting"
Wait for: "What should it be about?"
[Wait 10+ seconds without speaking]
```

**Expected:** "No follow-up detected. Ending conversation."

---

## ⚙️ Customization

### Change Timeout Duration

Edit `orchestrator.py`:

```python
# Line 95: Change follow-up timeout (default: 10 seconds)
follow_up = recognizer.listen_command(timeout=10, phrase_time_limit=15)
                                      ↑ Change this
```

### Change Max Conversation Turns

Edit `orchestrator.py`:

```python
# Line 65: Change max turns (default: 5)
max_turns = 5
           ↑ Change this
```

### Add More Exit Phrases

Edit `orchestrator.py`:

```python
# Line 102: Add more exit phrases
exit_phrases = ["cancel", "nevermind", "never mind", "stop", "quit", "exit", "abort"]
                                                                              ↑ Add here
```

---

## 🔧 Technical Details

### Conversation History

Each conversation maintains a history:
```python
conversation_history = [
    "create a meeting",
    "team standup tomorrow at 2 PM"
]
```

This full context is sent to LangGraph for each turn.

### Context Building

```python
full_context = " ".join(conversation_history)
# Result: "create a meeting team standup tomorrow at 2 PM"
```

The agent can use all previous turns to understand context.

---

## 🎯 Benefits

✅ **Natural Conversations**
- No need to repeat wake word
- Flows like human dialogue

✅ **Context Aware**
- Agent remembers previous turns
- Can ask clarifying questions

✅ **Smart Detection**
- Automatically knows when to continue
- Automatically knows when to end

✅ **User Control**
- Can cancel anytime
- Timeout prevents endless waiting

---

## 📋 Conversation State Machine

```
┌─────────────────────┐
│  WAITING_WAKE_WORD  │ ← Default state
└──────────┬──────────┘
           │ Wake word detected
           ↓
┌─────────────────────┐
│   INITIAL_COMMAND   │
└──────────┬──────────┘
           │ Command received
           ↓
┌─────────────────────┐
│   PROCESSING        │
└──────────┬──────────┘
           │
           ↓
      Is follow-up?
           │
     ┌─────┴─────┐
     │           │
    YES          NO
     │           │
     ↓           ↓
┌─────────┐ ┌─────────┐
│ FOLLOW  │ │  DONE   │
│   UP    │ │         │
└────┬────┘ └────┬────┘
     │           │
     │           ↓
     │      Back to
     │   WAITING_WAKE_WORD
     │
     └→ (repeats up to 5 times)
```

---

## ❓ Troubleshooting

### Follow-up not detected
**Cause:** Response doesn't contain question indicators
**Fix:** Adjust keywords in `is_follow_up_question()` function

### Conversation ends too early
**Cause:** Response not recognized as question
**Check:** Does it contain question keywords?

### Timeout too short
**Cause:** 10-second timeout
**Fix:** Increase timeout in `orchestrator.py` line 95

### Too many turns
**Cause:** Max turns set to 5
**Fix:** Increase `max_turns` in line 65

---

## 🌟 Advanced Usage

### Chained Conversations

```
You: "Sentinel, schedule a meeting"
Agent: "When?"
You: "Tomorrow at 2 PM"
Agent: "What should it be called?"
You: "Team standup"
Agent: "Should I add attendees?"
You: "No"
Agent: "Meeting scheduled!"
```

**Result:** 5-turn conversation, all without repeating "Sentinel"

---

## 📝 Code Example

```python
# Simple follow-up detection
def is_follow_up_question(response: str) -> bool:
    question_keywords = ["what", "when", "where", "?"]
    response_lower = response.lower()

    for keyword in question_keywords:
        if keyword in response_lower:
            return True

    return False

# Usage
response = "What should the meeting be about?"
if is_follow_up_question(response):
    # Continue listening...
    follow_up = listen_for_follow_up()
```

---

## ✅ Best Practices

1. **Keep responses conversational**
   - Agents should ask clear questions
   - Use natural language

2. **Provide exit option**
   - Tell users they can say "cancel"
   - Show timeout remaining

3. **Limit conversation turns**
   - Avoid endless loops
   - Max 5 turns recommended

4. **Clear state management**
   - Reset history after conversation
   - Avoid context pollution

---

## 🎉 Summary

Sentinel now supports:
- ✅ Multi-turn conversations
- ✅ Automatic follow-up detection
- ✅ Context preservation
- ✅ Smart timeouts
- ✅ Cancellation support
- ✅ Up to 5 back-and-forth turns

**No more repeating "Sentinel" for follow-ups!**

---

**Last Updated:** 2025-11-21
**Version:** 2.0

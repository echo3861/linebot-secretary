# LINE Gemini Bot

🚀 A LINE chatbot using Gemini API via FastAPI, deployed on Railway for stable, free operation.

## Features
✅ Toxic but kind Gemini persona  
✅ Summarize text, debug Python code  
✅ LINE webhook integration for real-time chatting

## Deployment on Railway

1. Fork this repository.
2. Go to [Railway](https://railway.app/) > New Project > Deploy from GitHub Repo.
3. Add environment variables:
   - `LINE_CHANNEL_SECRET`
   - `LINE_CHANNEL_ACCESS_TOKEN`
   - `GEMINI_API_KEY`
4. Copy the Railway HTTPS URL and set it as your LINE Webhook URL (`https://xxxx.up.railway.app/callback`).
5. Enable Webhook and add your bot as a LINE friend.

You now have your Gemini-powered LINE chatbot running!

---

If you need further help, feel free to ask your AI assistant to guide you.

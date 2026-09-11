Render settings:
Build: pip install -r requirements.txt
Start: gunicorn -w 1 -b 0.0.0.0:$PORT bot:app
Environment variables:
BOT_TOKEN = BotFather token
ADMIN_USER_ID = your Telegram numeric user ID
SUPABASE_URL = Project URL
SUPABASE_SECRET_KEY = Supabase Secret key (NOT publishable key)

\# Telegram Chatbot 🤖



A Telegram chatbot built with `python-telegram-bot`, powered by Groq API (llama-3.3-70b-versatile) and connected to a MySQL database. The bot maintains per-user conversation history and supports searching through past conversations.



\## Features



\- 💬 AI-powered responses using Groq API

\- 🗂 Per-user conversation history

\- 🔍 Search through past conversations

\- 🗑 Delete conversations

\- 📝 Auto-generated conversation summaries



\## Commands



\- `/start` — Welcome message

\- `/new` — Start a fresh conversation

\- `/history` — Show your last conversations

\- `/search` — Search through your conversations



\## Setup



\### 1. Clone the repository 

git clone https://github.com/zoubir-it/Telegram\_Chatbot.git

cd Telegram\_Chatbot



\### 2. Install dependencies

pip install python-telegram-bot groq mysql-connector-python python-dotenv



\### 3. Set up the database

Create a MySQL database and run the `schema.sql` file to create the required tables:

mysql -u root -p your\_database\_name < schema.sql



\### 4. Configure environment variables

Create a `.env` file in the project folder:

BOT\_TOKEN=your\_telegram\_bot\_token

GROQ\_API\_KEY=your\_groq\_api\_key

DB\_HOST=localhost

DB\_USER=your\_mysql\_user

DB\_PASSWORD=your\_mysql\_password

DB\_NAME=your\_database\_name



\### 5. Run the bot

python chatbot.py



\## Database Structure



The database has 2 tables defined in `schema.sql`:



\- \*\*conversations\*\* — stores conversation ID, user ID, auto-generated resume, and start time

\- \*\*messages\*\* — stores every user and assistant message linked to a conversation



\## Deployment



To keep the bot running 24/7, deploy it to \[Railway](https://railway.app):

1\. Push your code to GitHub

2\. Connect your repo on Railway

3\. Add your `.env` variables in Railway's dashboard

4\. Deploy!



\## Notes

\- Never share your `.env` file — it contains sensitive credentials

\- The `.env` file is excluded from the repo via `.gitignore`




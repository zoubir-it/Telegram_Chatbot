import os
from groq import Groq
import secrets
import string
import mysql.connector
from telegram import Update
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# Generate a unique 10-digit ID for each conversation
def generate_conversation_id(cursor):
    while True:
        conversation_id = "".join(secrets.choice(string.digits) for _ in range(10))
        cursor.execute("SELECT conversation_id FROM conversations WHERE conversation_id = %s", (conversation_id,))
        result = cursor.fetchone()
        if result is None:
            return conversation_id

# Generate a unique 10-digit ID for each messages
def generate_message_id(cursor):
    while True:
        message_id = "".join(secrets.choice(string.digits) for _ in range(10))
        cursor.execute("SELECT message_id FROM messages WHERE message_id = %s", (message_id,))
        result = cursor.fetchone()
        if result is None:
            return message_id
        
# Generate a short 5-6 word summary of the assistant's response
def conversations_resume(client, answer):

    task = f"summarize this in five or six words {answer}"

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages= [{"role": "user", "content": task}],
        max_tokens=500,
        stream=False  # ✅
    )

    return completion.choices[0].message.content



# Load Groq API key from environment and initialize client
GROQ_API_KEY  = os.getenv("GROQ_API_KEY")
client = Groq()

# Connect to MySQL database using environment variables
connection = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
)
# Use dictionary cursor so rows are accessible by column name
cursor = connection.cursor(dictionary=True)


async def start(update, context):
    await update.message.reply_text("hello")


# In-memory storage for conversation histories, active conversations, and resume tracking
histories = {}
active_convs = {}     
resume_generated = {}

async def handle_message(update, context):
    global cursor, connection

    # If bot is waiting for a search keyword, redirect to search handler
    if context.user_data.get('waiting_for_search'):
        await search_conversation(update, context)
        return

    user_id = update.message.from_user.id
    user_message = update.message.text
    message_id = generate_message_id(cursor)
    
    # Start a new conversation if user has no active one
    if user_id not in histories:
        conversation_id = generate_conversation_id(cursor)
        active_convs[user_id] = conversation_id
        histories[user_id] = []
        cursor.execute("INSERT INTO conversations (user_id, conversation_id) VALUES (%s, %s)", (user_id, conversation_id,))
    else:
        # Continue existing conversation
        conversation_id = active_convs[user_id]
    
    # Save user message to database
    cursor.execute("INSERT INTO messages (user_id, message_id, conversation_id, role, content) VALUES (%s, %s, %s, %s, %s)", (user_id, message_id, conversation_id, "user", user_message,))
    
    # Add user message to in-memory history and send to Groq
    histories[user_id].append({"role": "user", "content": user_message})
    completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=histories[user_id],
            max_tokens=500,
            stream=False
    )
    message_id = generate_message_id(cursor)
    assistant_message = completion.choices[0].message.content

    # Generate conversation resume from first assistant response only
    if user_id not in resume_generated:
        conversation_resume = conversations_resume(client, assistant_message)
        resume_generated[user_id] = conversation_resume

    # Save assistant message to database and update conversation resume
    histories[user_id].append({"role": "assistant", "content": assistant_message})
    cursor.execute("INSERT INTO messages (user_id, message_id, conversation_id, role, content) VALUES (%s, %s, %s, %s, %s)", (user_id, message_id, conversation_id, "assistant", assistant_message))
    cursor.execute("""
        UPDATE conversations
        SET conversation_resume = %s WHERE conversation_id = %s
    """, (resume_generated[user_id], conversation_id))

    connection.commit()
    await update.message.reply_text(completion.choices[0].message.content)

async def new(update, context):
    global cursor, connection

    # Reset user's conversation state and start fresh
    await update.message.reply_text("new conversation started")
    user_id = update.message.from_user.id
    conversation_id = generate_conversation_id(cursor)
    histories[user_id] = []
    active_convs[user_id] = conversation_id
    # Remove resume flag so a new one is generated for this conversation
    resume_generated.pop(user_id, None)

async def history(update, context):
    global cursor, connection

    # Fetch last conversations for this user ordered by most recent
    user_id = update.message.from_user.id
    cursor.execute("""
        SELECT conversation_id, conversation_resume, started_at
        FROM conversations
        WHERE user_id = %s
        ORDER BY started_at desc;
    """, (user_id,))

    results = cursor.fetchall()

    # Notify user if no conversations exist
    if not results:
        await update.message.reply_text("no history found")
        return

    # Build inline buttons, one per conversation
    buttons = []
    for info in results:
        buttons.append([InlineKeyboardButton(
            text=f"{info['conversation_resume']}",
            callback_data=f"continue_{info['conversation_id']}"
        )])
            
    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("your conversations:", reply_markup=keyboard)


async def complete_conversation(update, context):
    global cursor

    # Extract conversation ID from callback data
    query = update.callback_query
    await query.answer()
    conversation_id = query.data.replace("continue_", "")
    user_id = query.from_user.id

    # Load all messages for this conversation from DB ordered by time
    cursor.execute("""
        SELECT role, content
        FROM messages
        WHERE conversation_id = %s
        ORDER BY sent_at ASC;
    """, (conversation_id,))

    messages = cursor.fetchall()

    # Restore conversation history into memory so Groq has full context
    histories[user_id] = [{"role": row['role'], "content": row['content']} for row in messages]
    active_convs[user_id] = conversation_id
    # Mark resume as already generated so it won't be overwritten
    resume_generated[user_id] = True

    # Show delete button alongside confirmation message
    delete_button = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 Delete this conversation", callback_data=f"delete_{conversation_id}")]
    ])
    await query.message.reply_text("Conversation loaded, continue chatting!", reply_markup=delete_button)


async def delete_conversation(update, context):
    global cursor, connection

    # Extract conversation ID from callback data
    query = update.callback_query
    await query.answer()
    conversation_id = query.data.replace("delete_", "")
    user_id = query.from_user.id

    # Clear conversation from in-memory storage
    histories.pop(user_id, None)
    active_convs.pop(user_id, None)
    resume_generated.pop(user_id, None)

    # Delete messages first, then the conversation (order matters for foreign keys)
    cursor.execute("""
        DELETE FROM messages WHERE conversation_id = %s  
    """, (conversation_id,))
    cursor.execute("""
        DELETE FROM conversations WHERE conversation_id = %s
    """, (conversation_id,))

    connection.commit()
    await query.message.reply_text("conversation deleted successfully")

# Set flag to indicate bot is waiting for a search keyword from this user
async def search_start(update, context):
    context.user_data['waiting_for_search'] = True
    await update.message.reply_text("type your keyword:")


async def search_conversation(update, context):
    global cursor

    # Get keyword typed by user and their ID
    key = update.message.text
    user_id = update.message.from_user.id

    # Search conversations by resume matching the keyword
    cursor.execute("""
        SELECT conversation_id, conversation_resume, started_at
        FROM conversations
        WHERE user_id = %s and conversation_resume LIKE %s
    """, (user_id, "%" + key + "%",))

    results = cursor.fetchall()

    # Reset search flag and notify if no results found
    if not results:
        context.user_data['waiting_for_search'] = False
        await update.message.reply_text("no history found")
        return

    # Build inline buttons for each matching conversation
    buttons = []
    for info in results:
        buttons.append([InlineKeyboardButton(
            text=f"{info['conversation_resume']}",
            callback_data=f"continue_{info['conversation_id']}"
        )])

    # Reset search flag after results are ready
    context.user_data['waiting_for_search'] = False
    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("your conversations:", reply_markup=keyboard)


# Initialize bot and register all handlers
app = Application.builder().token(os.getenv("BOT_TOKEN")).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("new", new))
app.add_handler(CommandHandler("history", history))
app.add_handler(CallbackQueryHandler(complete_conversation, pattern="^continue_"))
app.add_handler(CallbackQueryHandler(delete_conversation, pattern="^delete_"))
app.add_handler(CommandHandler("search", search_start))
# Handle all text messages (must be registered last)
app.add_handler(MessageHandler(filters.TEXT, handle_message))
app.run_polling()
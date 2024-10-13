import logging
import os
import json
import sqlite3
import subprocess
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
from threading import Thread
import time

# Load environment variables from .env file
load_dotenv()

# Configuration
TOKEN = os.getenv('YOUR_TELEGRAM_BOT_TOKEN')
ADMIN_CHAT_ID = int(os.getenv('ADMIN_CHAT_ID'))

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database setup
conn = sqlite3.connect('managers.db', check_same_thread=False)
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS managers (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        role TEXT
    )
''')
conn.commit()

# Load command definitions from JSON file
with open('commands.json', 'r') as f:
    commands_data = json.load(f)

# Helper function to check if a user is a manager
def is_manager(user_id):
    if user_id == ADMIN_CHAT_ID:
        logger.debug(f'User ID {user_id} is the admin.')
        return True
    c.execute('SELECT user_id FROM managers WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    if result:
        logger.debug(f'User ID {user_id} is a manager.')
        return True
    else:
        logger.debug(f'User ID {user_id} is NOT a manager.')
        return False

# Helper function to check if a user has the necessary role for a command
def has_role(user_id, command):
    if user_id == ADMIN_CHAT_ID:
        return True
    c.execute('SELECT role FROM managers WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    if result:
        user_role = result[0]
        required_roles = commands_data[command].get('roles', [])
        if user_role in required_roles:
            return True
    return False

# Function to replace argument placeholder with actual argument
def build_command(command, arg=None):
    if arg:
        return [part.replace("{arg}", arg) for part in command]
    return command

# Function to run the command with optional duration for reversal
async def execute_command(update: Update, context: ContextTypes.DEFAULT_TYPE, command_data, args):
    user = update.effective_user
    user_id = user.id
    arg = args[0] if args else None

    linux_commands = command_data['linux_commands']
    reverse_commands = command_data.get('reverse_commands')
    duration = command_data.get('duration')

    for linux_command in linux_commands:
        # Check if the command requires an argument
        full_command = build_command(linux_command['command'], arg) if linux_command['requires_argument'] else linux_command['command']
        try:
            result = subprocess.run(full_command, capture_output=True, text=True, check=True)
            output = result.stdout
            error = result.stderr
            status = result.returncode
        except subprocess.CalledProcessError as e:
            output = e.stdout
            error = e.stderr
            status = e.returncode

        await update.message.reply_text(f'Command: {" ".join(full_command)}\nExit Status: {status}\nOutput: {output}\nError: {error}')
        logger.info(f'User @{user.username} (ID: {user.id}) executed command: {full_command}, Exit Status: {status}')

    # If duration is provided in JSON, run reverse commands after the duration
    if duration and reverse_commands:
        def reverse_task():
            time.sleep(duration)
            for reverse_command in reverse_commands:
                full_reverse_command = build_command(reverse_command['command'], arg) if reverse_command['requires_argument'] else reverse_command['command']
                try:
                    subprocess.run(full_reverse_command, capture_output=True, text=True, check=True)
                    logger.info(f'Reversed command: {" ".join(full_reverse_command)} after {duration} seconds')
                except subprocess.CalledProcessError as e:
                    logger.error(f'Error executing reverse command: {" ".join(full_reverse_command)}')

        Thread(target=reverse_task).start()

# Dynamic command handler
async def command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    command = update.message.text.split()[0].replace('/', '')

    if command not in commands_data:
        await update.message.reply_text("Unknown command.")
        return

    if not has_role(user_id, command):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    command_data = commands_data[command]
    args = context.args if command_data['arguments'] else []

    await execute_command(update, context, command_data, args)

# Help command handler
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_manager(user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    help_text = "Available Commands:\n"
    for command, data in commands_data.items():
        help_text += f"/{command} - {data['description']}\n"

    await update.message.reply_text(help_text)
    logger.info(f'Sent help information to user @{user.username} (ID: {user.id}).')

# Admin commands
async def add_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("Unauthorized access attempt.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /add_manager <user_id> <role>")
        return
    new_manager_id = int(context.args[0])
    role = context.args[1]
    c.execute('INSERT OR IGNORE INTO managers (user_id, role) VALUES (?, ?)', (new_manager_id, role))
    conn.commit()
    await update.message.reply_text(f"Manager with role '{role}' added.")
    logger.info(f'Added manager with role {role} for user ID {new_manager_id}.')

async def remove_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("Unauthorized access attempt.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /remove_manager <user_id>")
        return
    remove_manager_id = int(context.args[0])
    c.execute('DELETE FROM managers WHERE user_id = ?', (remove_manager_id,))
    conn.commit()
    await update.message.reply_text(f'Manager with ID {remove_manager_id} removed.')
    logger.info(f'Removed manager with ID {remove_manager_id}.')

async def list_managers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("Unauthorized access attempt.")
        return
    c.execute('SELECT user_id, role FROM managers')
    managers = c.fetchall()
    text = 'Managers:\n' + '\n'.join(f'ID: {row[0]}, Role: {row[1]}' for row in managers)
    await update.message.reply_text(text)
    logger.info('Listed managers to admin.')

# Main function
def main():
    application = ApplicationBuilder().token(TOKEN).build()

    # Register dynamic command handlers
    for command in commands_data:
        application.add_handler(CommandHandler(command, command_handler))

    # Register admin and help commands
    application.add_handler(CommandHandler('add_manager', add_manager))
    application.add_handler(CommandHandler('remove_manager', remove_manager))
    application.add_handler(CommandHandler('list_managers', list_managers))
    application.add_handler(CommandHandler('help', help_command))

    # Run the bot
    application.run_polling()

if __name__ == '__main__':
    main()


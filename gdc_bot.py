import logging
import os
import sqlite3
import subprocess
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
TOKEN = os.getenv('YOUR_TELEGRAM_BOT_TOKEN')
ADMIN_CHAT_ID = int(os.getenv('ADMIN_CHAT_ID'))

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Database setup
conn = sqlite3.connect('managers.db', check_same_thread=False)
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS managers (
        user_id INTEGER PRIMARY KEY,
        username TEXT
    )
''')
conn.commit()

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    logger.info(f'Received /start command from user @{user.username} (ID: {user_id}).')
    if is_manager(user_id):
        await update.message.reply_text('Welcome back, manager!')
        logger.debug(f'Access granted to user ID {user_id}.')
    else:
        message = f'User @{user.username} (ID: {user_id}) is requesting access.'
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)
        logger.info(f'Sent access request to admin for user @{user.username} (ID: {user_id}).')
        logger.debug(f'Access denied to user ID {user_id}.')

async def add_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f'User @{user.username} (ID: {user.id}) issued /add_manager command.')
    if user.id != ADMIN_CHAT_ID:
        logger.warning(f'Unauthorized access attempt to /add_manager by user ID {user.id}.')
        return
    if not context.args:
        await update.message.reply_text('Usage: /add_manager <user_id>')
        return
    new_manager_id = int(context.args[0])
    c.execute('INSERT OR IGNORE INTO managers (user_id) VALUES (?)', (new_manager_id,))
    conn.commit()
    await context.bot.send_message(chat_id=new_manager_id, text='You have been approved as a manager. Use /help to see commands.')
    await update.message.reply_text('Manager added.')
    logger.info(f'Added user ID {new_manager_id} as a manager.')

async def remove_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f'User @{user.username} (ID: {user.id}) issued /remove_manager command.')
    if user.id != ADMIN_CHAT_ID:
        logger.warning(f'Unauthorized access attempt to /remove_manager by user ID {user.id}.')
        return
    if not context.args:
        await update.message.reply_text('Usage: /remove_manager <user_id>')
        return
    remove_manager_id = int(context.args[0])
    c.execute('DELETE FROM managers WHERE user_id = ?', (remove_manager_id,))
    conn.commit()
    await context.bot.send_message(chat_id=remove_manager_id, text='Your manager access has been revoked.')
    await update.message.reply_text('Manager removed.')
    logger.info(f'Removed user ID {remove_manager_id} from managers.')

async def list_managers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f'User @{user.username} (ID: {user.id}) issued /list_managers command.')
    if user.id != ADMIN_CHAT_ID:
        logger.warning(f'Unauthorized access attempt to /list_managers by user ID {user.id}.')
        return
    c.execute('SELECT user_id, username FROM managers')
    managers = c.fetchall()
    text = 'Managers:\n' + '\n'.join(f'ID: {row[0]}, Username: {row[1]}' for row in managers)
    await update.message.reply_text(text)
    logger.info('Listed managers to admin.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f'User @{user.username} (ID: {user.id}) issued /help command.')
    if not is_manager(user.id):
        logger.warning(f'User ID {user.id} is not authorized to use /help.')
        return
    if user.id == ADMIN_CHAT_ID:
        text = (
            'Admin commands:\n'
            '/add_manager <user_id> - Add a new manager\n'
            '/remove_manager <user_id> - Remove a manager\n'
            '/list_managers - List all managers\n'
            '\nManager commands:\n'
            '/ensite <site_name> - Enable a site\n'
            '/dissite <site_name> - Disable a site\n'
            '/listsites - List available sites\n'
            '/listensites - List enabled sites\n'
            '/cpugov [governor] - Configure CPU governor\n'
            '/ufw_allow <port> - Allow port through UFW\n'
            '/ufw_deny <port> - Deny port through UFW\n'
            '/ufw_status - Check UFW status\n'
            '/vm_status <vm_name> - Get VM status\n'
            '/vm_start <vm_name> - Start a VM\n'
            '/vm_stop <vm_name> - Stop a VM\n'
            '/list_vms - List all VMs\n'
        )
    else:
        text = (
            'Available commands:\n'
            '/ensite <site_name> - Enable a site\n'
            '/dissite <site_name> - Disable a site\n'
            '/listsites - List available sites\n'
            '/listensites - List enabled sites\n'
            '/cpugov [governor] - Configure CPU governor\n'
            '/ufw_allow <port> - Allow port through UFW\n'
            '/ufw_deny <port> - Deny port through UFW\n'
            '/ufw_status - Check UFW status\n'
            '/vm_status <vm_name> - Get VM status\n'
            '/vm_start <vm_name> - Start a VM\n'
            '/vm_stop <vm_name> - Stop a VM\n'
            '/list_vms - List all VMs\n'
        )
    await update.message.reply_text(text)
    logger.debug(f'Sent help information to user ID {user.id}.')

# VM Management Commands
async def vm_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f'User @{user.username} (ID: {user.id}) issued /vm_status command.')
    if not is_manager(user.id):
        logger.warning(f'Unauthorized access attempt to /vm_status by user ID {user.id}.')
        return
    if not context.args:
        await update.message.reply_text('Usage: /vm_status <vm_name>')
        return
    vm_name = context.args[0]
    try:
        output = subprocess.check_output(['virsh', 'dominfo', vm_name]).decode()
        await update.message.reply_text(f'VM Status for {vm_name}:\n{output}')
        await log_and_notify_admin(update, context, f'Checked status of VM {vm_name}')
        logger.debug(f'Checked status of VM {vm_name} for user ID {user.id}.')
    except subprocess.CalledProcessError as e:
        error_output = e.output.decode()
        await update.message.reply_text(f'Error checking VM status: {error_output}')
        await log_and_notify_admin(update, context, f'Error checking VM status for {vm_name}: {error_output}')
        logger.error(f'Error checking VM status for user ID {user.id}: {error_output}')

async def vm_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f'User @{user.username} (ID: {user.id}) issued /vm_start command.')
    if not is_manager(user.id):
        logger.warning(f'Unauthorized access attempt to /vm_start by user ID {user.id}.')
        return
    if not context.args:
        await update.message.reply_text('Usage: /vm_start <vm_name>')
        return
    vm_name = context.args[0]
    try:
        subprocess.check_output(['virsh', 'start', vm_name])
        await update.message.reply_text(f'VM {vm_name} started.')
        await log_and_notify_admin(update, context, f'Started VM {vm_name}')
        logger.debug(f'Started VM {vm_name} for user ID {user.id}.')
    except subprocess.CalledProcessError as e:
        error_output = e.output.decode()
        await update.message.reply_text(f'Error starting VM: {error_output}')
        await log_and_notify_admin(update, context, f'Error starting VM {vm_name}: {error_output}')
        logger.error(f'Error starting VM {vm_name} for user ID {user.id}: {error_output}')

async def vm_stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f'User @{user.username} (ID: {user.id}) issued /vm_stop command.')
    if not is_manager(user.id):
        logger.warning(f'Unauthorized access attempt to /vm_stop by user ID {user.id}.')
        return
    if not context.args:
        await update.message.reply_text('Usage: /vm_stop <vm_name>')
        return
    vm_name = context.args[0]
    try:
        subprocess.check_output(['virsh', 'shutdown', vm_name])
        await update.message.reply_text(f'VM {vm_name} stopped.')
        await log_and_notify_admin(update, context, f'Stopped VM {vm_name}')
        logger.debug(f'Stopped VM {vm_name} for user ID {user.id}.')
    except subprocess.CalledProcessError as e:
        error_output = e.output.decode()
        await update.message.reply_text(f'Error stopping VM: {error_output}')
        await log_and_notify_admin(update, context, f'Error stopping VM {vm_name}: {error_output}')
        logger.error(f'Error stopping VM {vm_name} for user ID {user.id}: {error_output}')

async def list_vms_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f'User @{user.username} (ID: {user.id}) issued /list_vms command.')
    if not is_manager(user.id):
        logger.warning(f'Unauthorized access attempt to /list_vms by user ID {user.id}.')
        return
    try:
        output = subprocess.check_output(['virsh', 'list', '--all']).decode()
        await update.message.reply_text(f'List of VMs:\n{output}')
        await log_and_notify_admin(update, context, 'Listed all VMs')
        logger.debug(f'Listed all VMs for user ID {user.id}.')
    except subprocess.CalledProcessError as e:
        error_output = e.output.decode()
        await update.message.reply_text(f'Error listing VMs: {error_output}')
        await log_and_notify_admin(update, context, f'Error listing VMs: {error_output}')
        logger.error(f'Error listing VMs for user ID {user.id}: {error_output}')

async def log_and_notify_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, message: str):
    user = update.effective_user
    log_message = f'User @{user.username} (ID: {user.id}) performed action: {message}'
    logger.info(log_message)
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=log_message)

def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('add_manager', add_manager))
    application.add_handler(CommandHandler('remove_manager', remove_manager))
    application.add_handler(CommandHandler('list_managers', list_managers))
    application.add_handler(CommandHandler('help', help_command))

    application.add_handler(CommandHandler('ensite', ensite_command))
    application.add_handler(CommandHandler('dissite', dissite_command))
    application.add_handler(CommandHandler('cpugov', cpugov_command))
    application.add_handler(CommandHandler('ufw_allow', ufw_allow_command))
    application.add_handler(CommandHandler('ufw_deny', ufw_deny_command))
    application.add_handler(CommandHandler('ufw_status', ufw_status_command))
    application.add_handler(CommandHandler('listsites', listsites_command))
    application.add_handler(CommandHandler('listensites', listensites_command))

    # VM Management Commands
    application.add_handler(CommandHandler('vm_status', vm_status_command))
    application.add_handler(CommandHandler('vm_start', vm_start_command))
    application.add_handler(CommandHandler('vm_stop', vm_stop_command))
    application.add_handler(CommandHandler('list_vms', list_vms_command))

    application.run_polling()

if __name__ == '__main__':
    main()


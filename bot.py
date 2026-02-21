import logging
from telethon import TelegramClient, events, functions, types
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from telethon.sessions import StringSession
import asyncio
from datetime import datetime

from config import (
    API_ID, API_HASH, BOT_TOKEN, SESSION_STRING,
    LINK_GROUP_ID, BOTS_TO_ADD
)
from database import db

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Telethon client with session string
session_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# Command handler for /ok
async def ok_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ok command in channels"""
    chat = update.effective_chat
    
    # Check if command is used in a channel
    if chat.type not in ['channel', 'supergroup']:
        await update.message.reply_text("This command can only be used in channels!")
        return
    
    # Check if bot has required permissions
    bot_member = await chat.get_member(context.bot.id)
    if not bot_member.can_post_messages:
        await update.message.reply_text("I need permission to post messages in this channel!")
        return
    
    try:
        # Generate invite link
        invite_link = await generate_channel_invite(chat.id)
        
        # Store channel info in database
        await db.add_channel(
            channel_id=chat.id,
            channel_username=chat.username,
            channel_title=chat.title,
            added_by=update.effective_user.id if update.effective_user else None
        )
        
        # Create inline button with channel link
        channel_link = f"https://t.me/{chat.username}" if chat.username else f"https://t.me/c/{str(chat.id)[4:]}"
        keyboard = [[InlineKeyboardButton("Join Channel", url=channel_link)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send message to link group
        message = await context.bot.send_message(
            chat_id=LINK_GROUP_ID,
            text=f"🔗 New Channel Request\n\n"
                 f"📢 Channel: {chat.title}\n"
                 f"👤 Added by: {update.effective_user.mention_html() if update.effective_user else 'Unknown'}\n"
                 f"🔑 Invite Link: {invite_link}",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
        # Store request in database
        await db.add_request(chat.id, LINK_GROUP_ID, message.message_id, invite_link)
        
        await update.message.reply_text("✅ Request link has been generated and sent!")
        
    except Exception as e:
        logger.error(f"Error in /ok command: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def generate_channel_invite(channel_id):
    """Generate an invite link for the channel using session account"""
    try:
        # Get channel entity
        channel = await session_client.get_entity(channel_id)
        
        # Create invite link
        result = await session_client(functions.messages.ExportChatInviteRequest(
            peer=channel,
            expire_date=None,
            usage_limit=None,
            title=f"Bot Invite {datetime.now().strftime('%Y%m%d')}"
        ))
        
        return result.link
        
    except Exception as e:
        logger.error(f"Error generating invite link: {e}")
        raise

async def join_channel_with_session(channel_id):
    """Make session account join the channel"""
    try:
        channel = await session_client.get_entity(channel_id)
        await session_client(functions.channels.JoinChannelRequest(channel=channel))
        logger.info(f"Session account joined channel {channel_id}")
        return True
    except Exception as e:
        logger.error(f"Error joining channel: {e}")
        return False

async def promote_to_admin(channel_id, user_id):
    """Promote session account to admin"""
    try:
        channel = await session_client.get_entity(channel_id)
        
        # Get full admin rights
        admin_rights = types.ChatAdminRights(
            change_info=True,
            post_messages=True,
            edit_messages=True,
            delete_messages=True,
            ban_users=True,
            invite_users=True,
            pin_messages=True,
            add_admins=True,
            anonymous=True if isinstance(channel, types.Channel) and channel.megagroup else False,
            manage_call=True,
            other=True
        )
        
        await session_client(functions.channels.EditAdminRequest(
            channel=channel,
            user_id=user_id,
            admin_rights=admin_rights,
            rank='Bot Admin'
        ))
        logger.info(f"Session account promoted to admin in {channel_id}")
        return True
    except Exception as e:
        logger.error(f"Error promoting to admin: {e}")
        return False

async def add_bots_to_channel(channel_id):
    """Add configured bots to the channel"""
    added_bots = []
    for bot_username in BOTS_TO_ADD:
        if not bot_username:
            continue
            
        try:
            bot_username = bot_username.strip()
            if bot_username.startswith('@'):
                bot_username = bot_username[1:]
                
            # Get bot entity
            bot = await session_client.get_entity(bot_username)
            
            # Add bot to channel
            channel = await session_client.get_entity(channel_id)
            await session_client(functions.channels.InviteToChannelRequest(
                channel=channel,
                users=[bot]
            ))
            
            # Promote bot to admin with limited rights
            admin_rights = types.ChatAdminRights(
                change_info=False,
                post_messages=True,
                edit_messages=False,
                delete_messages=True,
                ban_users=False,
                invite_users=False,
                pin_messages=True,
                add_admins=False,
                anonymous=False,
                manage_call=False,
                other=False
            )
            
            await session_client(functions.channels.EditAdminRequest(
                channel=channel,
                user_id=bot,
                admin_rights=admin_rights,
                rank='Bot'
            ))
            
            added_bots.append(bot_username)
            logger.info(f"Added bot {bot_username} to channel {channel_id}")
            
        except Exception as e:
            logger.error(f"Error adding bot {bot_username}: {e}")
            
    return added_bots

async def process_channel_join(chat_id):
    """Process the complete channel join and setup workflow"""
    try:
        # Step 1: Join channel with session account
        if not await join_channel_with_session(chat_id):
            return False, "Failed to join channel"
        
        await db.update_channel_status(chat_id, 'session_joined', True)
        
        # Get session account user ID
        me = await session_client.get_me()
        
        # Step 2: Promote session account to admin
        if not await promote_to_admin(chat_id, me.id):
            return False, "Failed to promote to admin"
        
        # Step 3: Add bots to channel
        added_bots = await add_bots_to_channel(chat_id)
        await db.update_channel_status(chat_id, 'bot_added', True)
        
        return True, f"Success! Added bots: {', '.join(added_bots) if added_bots else 'No bots configured'}"
        
    except Exception as e:
        logger.error(f"Error in process_channel_join: {e}")
        return False, str(e)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    # You can add custom button handlers here if needed
    await query.edit_message_text(
        text=query.message.text,
        reply_markup=query.message.reply_markup
    )

async def monitor_join_requests():
    """Monitor and process pending join requests"""
    while True:
        try:
            # This is a simplified version - you might want to implement
            # a more sophisticated queue system based on your needs
            
            # For now, we'll just keep the bot running
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Error in monitor_join_requests: {e}")
            await asyncio.sleep(60)

async def post_init(application: Application):
    """Initialize bot after startup"""
    # Start the session client
    await session_client.start()
    
    # Start monitoring task
    asyncio.create_task(monitor_join_requests())
    
    logger.info("Bot started successfully!")

def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("ok", ok_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Start bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

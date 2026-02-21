from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from config import MONGODB_URI, DATABASE_NAME

class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(MONGODB_URI)
        self.db = self.client[DATABASE_NAME]
        self.channels = self.db['channels']
        self.requests = self.db['requests']
        
    async def add_channel(self, channel_id, channel_username, channel_title, added_by):
        """Add a channel to database"""
        channel_data = {
            'channel_id': channel_id,
            'channel_username': channel_username,
            'channel_title': channel_title,
            'added_by': added_by,
            'added_at': datetime.utcnow(),
            'is_active': True,
            'session_joined': False,
            'bot_added': False
        }
        await self.channels.update_one(
            {'channel_id': channel_id},
            {'$set': channel_data},
            upsert=True
        )
        
    async def get_channel(self, channel_id):
        """Get channel by ID"""
        return await self.channels.find_one({'channel_id': channel_id})
    
    async def update_channel_status(self, channel_id, field, value):
        """Update channel status"""
        await self.channels.update_one(
            {'channel_id': channel_id},
            {'$set': {field: value}}
        )
    
    async def add_request(self, channel_id, chat_id, message_id, request_link):
        """Add a join request to database"""
        request_data = {
            'channel_id': channel_id,
            'chat_id': chat_id,
            'message_id': message_id,
            'request_link': request_link,
            'created_at': datetime.utcnow(),
            'status': 'pending'
        }
        result = await self.requests.insert_one(request_data)
        return result.inserted_id
    
    async def update_request_status(self, request_id, status):
        """Update request status"""
        await self.requests.update_one(
            {'_id': request_id},
            {'$set': {'status': status}}
        )

# Create database instance
db = Database()

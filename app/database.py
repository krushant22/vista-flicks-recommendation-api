from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")

client = AsyncIOMotorClient(MONGO_URI)
print("Connected to MongoDB", client)
db = client[DB_NAME]  # Replace with your actual DB name
print("Connected to DB", db)

reels_collection = db["reels"]
feed_collection = db["feeds"]
users_collection = db["users"]
user_interactions_collection = db["userinteractions"]
reels_recommend_collection = db["reelsrecommends"]

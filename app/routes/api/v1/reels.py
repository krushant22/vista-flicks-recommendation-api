from app.utils.ott_feed import selected_ott_feed
from fastapi import APIRouter, Query, HTTPException, status
from app.database import users_collection, reels_recommend_collection
from app.schemas.reels import ReelSchema
from fastapi.responses import JSONResponse
from pymongo import ASCENDING
from bson import ObjectId
import logging

router = APIRouter(prefix="/reels", tags=["Reels"])

# Node RECOMMENDED_REELS uses /feed; keep /feeds for older callers.
@router.get("/feed")
@router.get("/feeds")
async def recommend_reels(user_id: str = Query(...), limit: int = 10):
    try:
        user = await users_collection.find_one({"_id": ObjectId(user_id)})

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )

        user_prefs = {
            "genre": user.get("genre", []),
            "language": user.get("language", []),
            "contentType": user.get("contentType", []),
            "subtitle": user.get("subTitleLanguage", []),
            "imdbRating": user.get("imdbRating", []),
            "ott": user.get("ottPlatforms", []),
            "region": user.get("region", []),
            "ageRating": user.get("ageRating", [])
        }

        logging.info(f"User {user_id} preferences: {user_prefs}")

        recommended_reels = []

        if not any(user_prefs.values()):
            logging.warning(f"User {user_id} has empty preferences. Using fallback.")
            recommended_reels = await reels_recommend_collection.find({"type": "reel"}).to_list(length=1000)
        else:
            query = {"$and": []}

            mandatory_fields = {
                "genre": user_prefs["genre"],
                "language": user_prefs["language"],
            }

            for field, values in mandatory_fields.items():
                if values:
                    query["$and"].append({field: {"$in": values}})

            optional_filters = []
            if user_prefs["contentType"]:
                optional_filters.append({"contentType": {"$in": user_prefs["contentType"]}})
            if user_prefs["subtitle"]:
                optional_filters.append({"subTitleLanguage": {"$in": user_prefs["subtitle"]}})
            if user_prefs["imdbRating"]:
                optional_filters.append({"imdbRating": {"$in": user_prefs["imdbRating"]}})
            if user_prefs["ott"]:
                optional_filters.append({"ottPlatforms": {"$in": user_prefs["ott"]}})
            if user_prefs["region"]:
                optional_filters.append({"region": {"$in": user_prefs["region"]}})
            if user_prefs["ageRating"]:
                optional_filters.append({"ageRating": {"$in": user_prefs["ageRating"]}})

            if optional_filters:
                query["$and"].append({"$or": optional_filters})

            if query["$and"]:
                logging.info(f"MongoDB query for user {user_id}: {query}")
                recommended_cursor = reels_recommend_collection.find(query)
                recommended_reels = await recommended_cursor.to_list(length=1000)
            else:
                logging.warning(f"No filters constructed. Using fallback for user {user_id}.")
                recommended_reels = await reels_recommend_collection.find({"type": "reel"}).to_list(length=1000)

        # Exclude viewed reels
        viewed_set = set(str(rid) for rid in user.get("viewedReels", []))
        logging.info(f"User {user_id} viewed reels: {viewed_set}")

        final_reel_ids = [
            str(r["reelId"]) for r in recommended_reels
            if str(r["reelId"]) not in viewed_set
        ][:limit]

        return {
            "userId": user_id,
            "requestedReelsKind": "standard",
            "reels": await selected_ott_feed(final_reel_ids, user, reels_recommend_collection, limit)
        }

    except Exception as e:
        logging.exception("Error in recommend_reels")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch recommendations: {str(e)}"
        )

PREFERENCE_FIELDS = {
    'ottPlatforms': 'ottAvailability.id',
    'genre': 'genres',
    'language': 'language',
    'contentType': 'type',
    'subTitleLanguage': 'subtitle',
    'imdbRating': 'imdbRating',
    'region': 'region',
    'ageRating': 'rating',
}


PREFERENCE_COLLECTIONS = {
    'ottPlatforms': 'ottapps', 'genre': 'genres', 'language': 'languages',
    'contentType': 'contenttypes', 'subTitleLanguage': 'subtitlelanguages',
    'imdbRating': 'imdbratings', 'region': 'regions', 'ageRating': 'ageratings',
}


async def get_effective_preferences(user, database):
    """Select All means no narrowing; proper subsets remain strict."""
    import asyncio
    async def resolve(key):
        options = await database[PREFERENCE_COLLECTIONS[key]].find({}, {'_id': 1}).to_list(length=None)
        chosen = {str(value) for value in user[key]}
        all_selected = bool(options) and all(str(row['_id']) in chosen for row in options)
        return None if all_selected else (key, user[key])
    fields = [key for key in PREFERENCE_COLLECTIONS if user.get(key)]
    return dict(item for item in await asyncio.gather(*(resolve(key) for key in fields)) if item)


def build_catalog_filter(user):
    """AND across selected fields; OR within each field. Empty fields impose no constraint."""
    return {catalog: {'$in': user[key]} for key, catalog in PREFERENCE_FIELDS.items()
            if user.get(key)}


async def selected_ott_feed(reel_ids, user, collection, limit):
    """Keep external ordering and backfill only from the fully matching catalog.

    The existing name is retained for compatibility with the live handler.
    Metadata gaps do not weaken or eliminate matches: the current catalog is
    authoritative. Exhausted matches return empty for the backend's existing
    history-reset/refetch; a genuine no-match result never broadens filters.
    """
    filters = build_catalog_filter(await get_effective_preferences(user, collection.database))
    if not filters:
        return reel_ids
    count = max(0, min(int(limit), 1000))
    if not count:
        return []
    db = collection.database
    titles = await db.contents.find(filters, {'_id': 1}).to_list(length=None)
    if not titles:
        return []
    eligible = await db.reels.find({
        'contentId': {'$in': [row['_id'] for row in titles]},
        'type': 'reel', 'status': 'live', 'isApproved': True,
        'isDeleted': {'$ne': True}, 'videoUrl': {'$nin': [None, '']},
    }, {'_id': 1}).to_list(length=None)
    viewed = {str(value) for value in user.get('viewedReels', [])}
    available = {str(row['_id']) for row in eligible} - viewed
    result, seen = [], set()
    for value in list(reel_ids) + [row['_id'] for row in eligible]:
        key = str(value)
        if key in available and key not in seen:
            result.append(key)
            seen.add(key)
            if len(result) == count:
                break
    return result

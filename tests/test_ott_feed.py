import unittest
from types import SimpleNamespace
from app.utils.ott_feed import selected_ott_feed, build_catalog_filter, get_effective_preferences

def match(row, query):
    for key, value in query.items():
        if key == '$and':
            if not all(match(row, q) for q in value): return False
        elif key == '$or':
            if not any(match(row, q) for q in value): return False
        elif isinstance(value, dict):
            got=row.get(key); values=got if isinstance(got,list) else [got]
            if '$in' in value and not any(v in value['$in'] for v in values): return False
            if '$nin' in value and any(v in value['$nin'] for v in values): return False
            if '$ne' in value and got == value['$ne']: return False
        elif row.get(key) != value: return False
    return True
class Cursor:
    def __init__(self, rows): self.rows=rows
    async def to_list(self,length=None): return self.rows[:length]
class Collection:
    def __init__(self,rows): self.rows=rows
    def find(self,query,*args): return Cursor([row for row in self.rows if match(row,query)])
class Database(SimpleNamespace):
    def __getitem__(self, key): return getattr(self, key)
class Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        titles=[{'_id':f't{i}','ottAvailability.id':['netflix' if i<7 else 'other'],'genres':['drama'],'language':['en'],'type':'movie','subtitle':['en'],'imdbRating':'high','region':'india','rating':'adult'} for i in range(10)]
        reels=[{'_id':f'r{i}','contentId':f't{i}','type':'reel','status':'live','isApproved':True,'isDeleted':False,'videoUrl':'media'} for i in range(10)]
        self.metadata=Collection([{'reelId':'r5','genre':['drama'],'language':['en'],'ottPlatforms':['netflix']}])
        self.metadata.database=Database(contents=Collection(titles),reels=Collection(reels))
        self.options={'ottapps':['netflix','other','third'],'genres':['drama','comedy','action'],'languages':['en','hi','fr'],'contenttypes':['movie','tv','short'],'subtitlelanguages':['en','hi'],'imdbratings':['high','low'],'regions':['india','uk'],'ageratings':['adult','child']}
        for name,values in self.options.items():setattr(self.metadata.database,name,Collection([{'_id':value} for value in values]))
        self.user={'ottPlatforms':['netflix'],'genre':['drama'],'language':['en'],'contentType':['movie'],'viewedReels':[]}
    async def test_replenishes_netflix_when_original_candidates_are_other_ott(self):
        result=await selected_ott_feed(['r8','r9'],self.user,self.metadata,5)
        self.assertEqual(len(result),5);self.assertEqual(result[0],'r0')
        self.assertTrue(set(result)<=set(f'r{i}' for i in range(7)))
    async def test_no_preference_metadata_match_still_gets_ott_scoped_backfill(self):
        self.metadata.rows=[]
        result=await selected_ott_feed(['r8'],self.user,self.metadata,5)
        self.assertEqual(len(result),5)
    async def test_preserves_external_order_when_candidates_match(self):
        result=await selected_ott_feed(['r3','r1'],self.user,self.metadata,3)
        self.assertEqual(result,['r3','r1','r0'])
    async def test_all_viewed_returns_empty_then_history_reset_repopulates(self):
        self.user['viewedReels']=[f'r{i}' for i in range(7)]
        self.assertEqual(await selected_ott_feed(['r8'],self.user,self.metadata,5),[])
        self.user['viewedReels']=[]
        self.assertEqual(len(await selected_ott_feed(['r8'],self.user,self.metadata,5)),5)
    async def test_multi_ott_accepts_selected_platforms(self):
        self.user['ottPlatforms']=['netflix','other']
        self.assertEqual((await selected_ott_feed(['r8'],self.user,self.metadata,2))[0],'r8')
    async def test_empty_ott_preserves_original_behavior(self):
        self.user={}
        self.assertEqual(await selected_ott_feed(['r8','r9'],self.user,self.metadata,5),['r8','r9'])
    async def test_no_catalog_match_does_not_broaden_ott(self):
        self.user['ottPlatforms']=['absent']
        self.assertEqual(await selected_ott_feed(['r8'],self.user,self.metadata,5),[])
    async def test_nonlive_and_unplayable_never_backfilled(self):
        for row in self.metadata.database.reels.rows[:7]:row['status']='inReview'
        self.assertEqual(await selected_ott_feed(['r0'],self.user,self.metadata,5),[])
    async def test_netflix_hindi_movie_is_a_strict_intersection(self):
        for row in self.metadata.database.contents.rows:
            row['language']=['hi']
        self.metadata.database.contents.rows[0]['language']=['en']
        self.metadata.database.contents.rows[1]['type']='tv'
        self.user={'ottPlatforms':['netflix'],'language':['hi'],'contentType':['movie']}
        result=await selected_ott_feed(['r0','r1','r8'],self.user,self.metadata,10)
        self.assertEqual(result,['r2','r3','r4','r5','r6'])
    async def test_every_other_selected_field_is_required(self):
        for field,value in [('genre','comedy'),('language','hi'),('contentType','tv'),('subTitleLanguage','hi'),('imdbRating','low'),('region','uk'),('ageRating','child')]:
            with self.subTest(field=field):
                user={'ottPlatforms':['netflix'],field:[value]}
                self.assertEqual(await selected_ott_feed(['r0'],user,self.metadata,5),[])
    async def test_language_filter_works_without_ott(self):
        self.assertEqual(await selected_ott_feed(['r8'],{'language':['hi']},self.metadata,5),[])
    async def test_multiple_values_within_fields_are_or(self):
        user={'ottPlatforms':['netflix','other'],'genre':['comedy','drama'],'language':['hi','en'],'contentType':['movie','tv']}
        self.assertEqual(len(await selected_ott_feed(['r8'],user,self.metadata,10)),10)
    async def test_unknown_required_metadata_is_not_treated_as_match(self):
        del self.metadata.database.contents.rows[0]['language']
        result=await selected_ott_feed(['r0'],{'language':['en']},self.metadata,10)
        self.assertNotIn('r0',result)
    def test_field_mapping_covers_all_saved_preferences(self):
        query=build_catalog_filter({key:['id'] for key in ['ottPlatforms','genre','language','contentType','subTitleLanguage','imdbRating','region','ageRating']})
        self.assertEqual(set(query),{'ottAvailability.id','genres','language','type','subtitle','imdbRating','region','rating'})
    async def test_select_all_subtitles_does_not_require_subtitle_metadata(self):
        for row in self.metadata.database.contents.rows: row.pop('subtitle',None)
        user={'ottPlatforms':['netflix'],'subTitleLanguage':['en','hi']}
        result=await selected_ott_feed(['r8'],user,self.metadata,5)
        self.assertEqual(len(result),5)
        self.assertTrue(set(result)<=set(f'r{i}' for i in range(7)))
    async def test_all_except_one_ott_remains_required_with_all_other_categories(self):
        user={'ottPlatforms':['netflix','other'],'genre':['drama','comedy','action'],'language':['en','hi','fr'],'contentType':['movie','tv','short'],'subTitleLanguage':['en','hi'],'imdbRating':['high','low'],'region':['india','uk'],'ageRating':['adult','child']}
        for row in self.metadata.database.contents.rows:
            row.pop('subtitle',None);row.pop('region',None)
        result=await selected_ott_feed(['r8'],user,self.metadata,10)
        self.assertEqual(len(result),10)
        self.metadata.database.contents.rows[8]['ottAvailability.id']=['third']
        self.assertNotIn('r8',await selected_ott_feed(['r8'],user,self.metadata,10))
    async def test_specific_subtitle_stays_strict_when_metadata_missing(self):
        for row in self.metadata.database.contents.rows:row.pop('subtitle',None)
        self.assertEqual(await selected_ott_feed(['r0'],{'ottPlatforms':['netflix'],'subTitleLanguage':['en']},self.metadata,5),[])
    async def test_select_all_does_not_change_saved_preferences(self):
        user={'language':['en','hi','fr']};original=list(user['language'])
        self.assertEqual(await get_effective_preferences(user,self.metadata.database),{})
        self.assertEqual(user['language'],original)
    async def test_empty_master_does_not_relax_unknown_choice(self):
        self.metadata.database.languages=Collection([])
        self.assertEqual(await get_effective_preferences({'language':['unknown']},self.metadata.database),{'language':['unknown']})
if __name__=='__main__':unittest.main()

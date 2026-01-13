#!/usr/bin/env python3
"""
Launch Date and Country Data Enrichment Script

Enriches satellite documents with launch dates and country data from multiple sources:
1. UNOOSA (date_of_launch, country_of_origin) - highest priority for registered satellites
2. GCAT (Jonathan McDowell's catalog) - comprehensive launch data
3. Kaggle (country) - fallback for country data

Promotes data to canonical.launch_date and canonical.country fields.
"""
import sys
from datetime import datetime, timezone
from collections import defaultdict
import db as db_module

def parse_gcat_date(date_str):
    """Parse GCAT date format: 'YYYY MMM DD' or 'YYYY MMM  D' to ISO date string"""
    if not date_str or date_str.strip() == '':
        return None
    
    try:
        parts = date_str.strip().split()
        if len(parts) != 3:
            return None
        
        year = parts[0]
        month = parts[1]
        day = parts[2].strip()
        
        month_map = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }
        
        if month not in month_map:
            return None
        
        month_num = month_map[month]
        day_num = day.zfill(2)
        
        return f"{year}-{month_num}-{day_num}"
    except Exception as e:
        return None

def load_gcat_data(filename='gcat_satcat.tsv'):
    """Load launch dates and countries from GCAT file"""
    print("\n" + "=" * 60)
    print("Loading GCAT Data")
    print("=" * 60)
    
    gcat_data = {}
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines):
            if line.startswith('#'):
                continue
            
            fields = line.strip().split('\t')
            if len(fields) < 16:
                continue
            
            try:
                norad_id_str = fields[1].strip()
                if not norad_id_str:
                    continue
                
                norad_id = int(norad_id_str)
                launch_date = parse_gcat_date(fields[7])
                owner = fields[14] if len(fields) > 14 and fields[14].strip() else None
                state = fields[15] if len(fields) > 15 and fields[15].strip() else None
                
                gcat_data[str(norad_id)] = {
                    'launch_date': launch_date,
                    'owner': owner,
                    'state': state
                }
            except (ValueError, IndexError):
                continue
        
        print(f"Loaded {len(gcat_data):,} records from GCAT")
        
        dates_count = sum(1 for d in gcat_data.values() if d['launch_date'])
        states_count = sum(1 for d in gcat_data.values() if d['state'])
        print(f"  - Launch dates: {dates_count:,}")
        print(f"  - States: {states_count:,}")
        
        return gcat_data
    
    except FileNotFoundError:
        print(f"❌ GCAT file not found: {filename}")
        return {}
    except Exception as e:
        print(f"❌ Error loading GCAT data: {e}")
        return {}

def enrich_launch_data(dry_run=False):
    """Enrich satellite documents with launch dates and country data"""
    
    print("=" * 60)
    print("Launch Date & Country Data Enrichment")
    print("=" * 60)
    
    if not db_module.connect_mongodb():
        print("❌ Failed to connect to ArangoDB")
        return False
    
    db = db_module.db
    
    gcat_data = load_gcat_data()
    
    print("\n" + "=" * 60)
    print("Step 1: Analyze Current Coverage")
    print("=" * 60)
    
    query = """
    LET total = LENGTH(FOR doc IN @@collection RETURN 1)
    
    LET has_canonical_launch_date = LENGTH(
        FOR doc IN @@collection
            FILTER doc.canonical.launch_date != null
            RETURN 1
    )
    
    LET has_canonical_country = LENGTH(
        FOR doc IN @@collection
            FILTER doc.canonical.country != null
            RETURN 1
    )
    
    LET has_unoosa_launch = LENGTH(
        FOR doc IN @@collection
            FILTER doc.sources.unoosa.date_of_launch != null
            RETURN 1
    )
    
    LET has_unoosa_country = LENGTH(
        FOR doc IN @@collection
            FILTER doc.sources.unoosa.country_of_origin != null
            RETURN 1
    )
    
    LET has_kaggle_country = LENGTH(
        FOR doc IN @@collection
            FILTER doc.sources.kaggle.country != null
            RETURN 1
    )
    
    RETURN {
        total: total,
        canonical_launch_date: has_canonical_launch_date,
        canonical_country: has_canonical_country,
        unoosa_launch: has_unoosa_launch,
        unoosa_country: has_unoosa_country,
        kaggle_country: has_kaggle_country
    }
    """
    
    cursor = db.aql.execute(query, bind_vars={'@collection': db_module.COLLECTION_NAME})
    stats = list(cursor)[0]
    
    print(f"Total satellites: {stats['total']:,}")
    print(f"\nCurrent canonical coverage:")
    print(f"  - Launch date: {stats['canonical_launch_date']:,} ({stats['canonical_launch_date']*100/stats['total']:.1f}%)")
    print(f"  - Country:     {stats['canonical_country']:,} ({stats['canonical_country']*100/stats['total']:.1f}%)")
    print(f"\nSource data available:")
    print(f"  - UNOOSA launch dates: {stats['unoosa_launch']:,} ({stats['unoosa_launch']*100/stats['total']:.1f}%)")
    print(f"  - UNOOSA countries:    {stats['unoosa_country']:,} ({stats['unoosa_country']*100/stats['total']:.1f}%)")
    print(f"  - Kaggle countries:    {stats['kaggle_country']:,} ({stats['kaggle_country']*100/stats['total']:.1f}%)")
    print(f"  - GCAT records:        {len(gcat_data):,}")
    
    print("\n" + "=" * 60)
    print("Step 2: Fetch Satellites Needing Enrichment")
    print("=" * 60)
    
    query = """
    FOR doc IN @@collection
        FILTER doc.canonical.launch_date == null OR doc.canonical.country == null
        RETURN {
            _key: doc._key,
            identifier: doc.identifier,
            norad_cat_id: doc.canonical.norad_cat_id,
            has_canonical_launch_date: doc.canonical.launch_date != null,
            has_canonical_country: doc.canonical.country != null,
            unoosa_launch: doc.sources.unoosa.date_of_launch,
            unoosa_country: doc.sources.unoosa.country_of_origin,
            kaggle_country: doc.sources.kaggle.country
        }
    """
    
    cursor = db.aql.execute(query, bind_vars={'@collection': db_module.COLLECTION_NAME})
    satellites = list(cursor)
    
    print(f"Found {len(satellites):,} satellites needing enrichment")
    
    print("\n" + "=" * 60)
    print("Step 3: Enrich Launch Dates and Countries")
    print("=" * 60)
    
    updates = []
    enrichment_stats = defaultdict(int)
    
    for sat in satellites:
        update = {
            '_key': sat['_key'],
            'identifier': sat['identifier'],
            'changes': {}
        }
        
        needs_launch_date = not sat['has_canonical_launch_date']
        needs_country = not sat['has_canonical_country']
        
        if needs_launch_date:
            if sat['unoosa_launch']:
                update['changes']['launch_date'] = sat['unoosa_launch']
                update['launch_date_source'] = 'unoosa'
                enrichment_stats['launch_date_from_unoosa'] += 1
            elif sat['norad_cat_id'] and sat['norad_cat_id'] in gcat_data:
                gcat_date = gcat_data[sat['norad_cat_id']]['launch_date']
                if gcat_date:
                    update['changes']['launch_date'] = gcat_date
                    update['launch_date_source'] = 'gcat'
                    enrichment_stats['launch_date_from_gcat'] += 1
        
        if needs_country:
            if sat['unoosa_country']:
                update['changes']['country'] = sat['unoosa_country']
                update['country_source'] = 'unoosa'
                enrichment_stats['country_from_unoosa'] += 1
            elif sat['kaggle_country']:
                update['changes']['country'] = sat['kaggle_country']
                update['country_source'] = 'kaggle'
                enrichment_stats['country_from_kaggle'] += 1
            elif sat['norad_cat_id'] and sat['norad_cat_id'] in gcat_data:
                gcat_state = gcat_data[sat['norad_cat_id']]['state']
                if gcat_state:
                    update['changes']['country'] = gcat_state
                    update['country_source'] = 'gcat'
                    enrichment_stats['country_from_gcat'] += 1
        
        if update['changes']:
            updates.append(update)
    
    print(f"\nEnrichment summary:")
    print(f"  - Launch dates from UNOOSA: {enrichment_stats['launch_date_from_unoosa']:,}")
    print(f"  - Launch dates from GCAT:   {enrichment_stats['launch_date_from_gcat']:,}")
    print(f"  - Countries from UNOOSA:    {enrichment_stats['country_from_unoosa']:,}")
    print(f"  - Countries from Kaggle:    {enrichment_stats['country_from_kaggle']:,}")
    print(f"  - Countries from GCAT:      {enrichment_stats['country_from_gcat']:,}")
    print(f"\nTotal updates to apply: {len(updates):,}")
    
    if dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN - No changes applied")
        print("=" * 60)
        print("\nSample updates (first 10):")
        for i, update in enumerate(updates[:10]):
            print(f"\n{i+1}. {update['identifier']}:")
            if 'launch_date' in update['changes']:
                print(f"   Launch date: {update['changes']['launch_date']} (from {update['launch_date_source']})")
            if 'country' in update['changes']:
                print(f"   Country: {update['changes']['country']} (from {update['country_source']})")
        return True
    
    print("\n" + "=" * 60)
    print("Step 4: Apply Updates to Database")
    print("=" * 60)
    
    timestamp = datetime.now(timezone.utc).isoformat()
    success_count = 0
    error_count = 0
    
    for i, update in enumerate(updates):
        try:
            canonical_updates = {}
            transformation_records = []
            
            if 'launch_date' in update['changes']:
                canonical_updates['launch_date'] = update['changes']['launch_date']
                transformation_records.append({
                    'timestamp': timestamp,
                    'source_field': f"sources.{update['launch_date_source']}.date_of_launch" if update['launch_date_source'] == 'unoosa' else f"gcat.launch_date",
                    'target_field': 'canonical.launch_date',
                    'value': update['changes']['launch_date'],
                    'promoted_by': 'enrich_launch_data'
                })
            
            if 'country' in update['changes']:
                canonical_updates['country'] = update['changes']['country']
                if update['country_source'] == 'unoosa':
                    source_field = 'sources.unoosa.country_of_origin'
                elif update['country_source'] == 'kaggle':
                    source_field = 'sources.kaggle.country'
                else:
                    source_field = 'gcat.state'
                
                transformation_records.append({
                    'timestamp': timestamp,
                    'source_field': source_field,
                    'target_field': 'canonical.country',
                    'value': update['changes']['country'],
                    'promoted_by': 'enrich_launch_data'
                })
            
            query = """
            FOR doc IN @@collection
                FILTER doc._key == @key
                UPDATE doc WITH {
                    canonical: MERGE(doc.canonical, @canonical_updates),
                    metadata: MERGE(doc.metadata, {
                        transformations: APPEND(doc.metadata.transformations, @new_transformations, true),
                        last_updated_at: @timestamp
                    })
                } IN @@collection
                RETURN NEW
            """
            
            db.aql.execute(
                query,
                bind_vars={
                    'key': update['_key'],
                    'canonical_updates': canonical_updates,
                    'new_transformations': transformation_records,
                    'timestamp': timestamp,
                    '@collection': db_module.COLLECTION_NAME
                }
            )
            
            success_count += 1
            
            if (i + 1) % 1000 == 0:
                print(f"  Processed {i + 1:,} / {len(updates):,} updates...")
        
        except Exception as e:
            error_count += 1
            if error_count <= 5:
                print(f"  ❌ Error updating {update['identifier']}: {e}")
    
    print(f"\n✓ Successfully updated {success_count:,} satellites")
    if error_count > 0:
        print(f"❌ Errors: {error_count:,}")
    
    print("\n" + "=" * 60)
    print("Step 5: Verify Final Coverage")
    print("=" * 60)
    
    verify_query = """
    LET total = LENGTH(FOR doc IN @@collection RETURN 1)
    
    LET has_canonical_launch_date = LENGTH(
        FOR doc IN @@collection
            FILTER doc.canonical.launch_date != null
            RETURN 1
    )
    
    LET has_canonical_country = LENGTH(
        FOR doc IN @@collection
            FILTER doc.canonical.country != null
            RETURN 1
    )
    
    RETURN {
        total: total,
        canonical_launch_date: has_canonical_launch_date,
        canonical_country: has_canonical_country
    }
    """
    
    cursor = db.aql.execute(verify_query, bind_vars={'@collection': db_module.COLLECTION_NAME})
    final_stats = list(cursor)[0]
    
    print(f"Final canonical coverage:")
    print(f"  - Launch date: {final_stats['canonical_launch_date']:,} ({final_stats['canonical_launch_date']*100/final_stats['total']:.1f}%)")
    print(f"  - Country:     {final_stats['canonical_country']:,} ({final_stats['canonical_country']*100/final_stats['total']:.1f}%)")
    
    print("\n✓ Launch data enrichment complete!")
    return True

if __name__ == "__main__":
    dry_run = '--dry-run' in sys.argv
    
    if dry_run:
        print("Running in DRY RUN mode - no changes will be applied\n")
    
    enrich_launch_data(dry_run=dry_run)

#!/usr/bin/env python3
"""
Source Attribute Promotion Script

Promotes specific attributes from source nodes to canonical fields in MongoDB documents.
Tracks all transformations in the document's metadata.

USAGE:
    python promote_attributes.py <source_field> <target_field> [options]

ARGUMENTS:
    source_field    Source field path (e.g., kaggle.orbital_band, sources.kaggle.orbital_band)
    target_field    Target field path (e.g., canonical.orbital_band)

OPTIONS:
    --dry-run       Preview changes without applying to database
    --all           Process all matching documents (default: 5 samples)
    --filter        Filter documents using "field=value" syntax
    --yes           Skip confirmation prompts for large batches
    --reason        Add custom reason to transformation history
    -v, --verbose   Enable detailed logging

EXAMPLES:
    # Basic promotion (processes 5 sample documents by default)
    python promote_attributes.py kaggle.orbital_band canonical.orbital_band
    
    # Preview changes without applying (dry-run mode)
    python promote_attributes.py --dry-run kaggle.orbital_band canonical.orbital_band
    
    # Process single document by identifier
    python promote_attributes.py --filter "identifier=2025-206B" kaggle.orbital_band canonical.orbital_band
    
    # Process all documents from specific country
    python promote_attributes.py --all --filter "canonical.country_of_origin=USA" kaggle.orbital_band canonical.orbital_band
    
    # Process all matching documents without confirmation
    python promote_attributes.py --all --yes kaggle.orbital_band canonical.orbital_band
    
    # Add custom reason to transformation history
    python promote_attributes.py --reason "Kaggle has more accurate orbital band data" kaggle.orbital_band canonical.orbital_band
    
    # Verbose mode for debugging
    python promote_attributes.py -v --dry-run kaggle.orbital_band canonical.orbital_band
    
    # Nested target fields
    python promote_attributes.py kaggle.apogee canonical.orbit.apogee_km
    
    # Multiple filters
    python promote_attributes.py --filter "canonical.object_type=PAYLOAD,identifier=2025-206B" kaggle.orbital_band canonical.orbital_band

FEATURES:
    - Automatic field path normalization (kaggle.field → sources.kaggle.field)
    - Dry-run mode for safe previewing
    - Confirmation prompts for large batches (>10 documents)
    - Conflict detection (warns if target field already exists)
    - Progress reporting for large operations (>20 documents)
    - Comprehensive transformation history tracking
    - Support for nested fields using dot notation
    - Flexible filtering by any field

TRANSFORMATION HISTORY:
    All promotions are recorded in metadata.transformations array with:
    - timestamp: When the promotion occurred
    - source_field: Source field path
    - target_field: Target field path
    - value: The promoted value
    - reason: Optional custom reason
"""

import argparse
import sys
from typing import Dict, Any, Optional, List
from db import (
    connect_mongodb,
    disconnect_mongodb,
    get_satellites_collection,
    get_nested_field,
    set_nested_field,
    record_transformation
)


def parse_arguments():
    """Parse and validate command line arguments"""
    parser = argparse.ArgumentParser(
        description="Promote source attributes to canonical fields in MongoDB documents",
        epilog="""
Examples:
  %(prog)s kaggle.orbital_band canonical.orbital_band
  %(prog)s --dry-run kaggle.orbital_band canonical.orbital_band
  %(prog)s --filter "identifier=NORAD-25544" kaggle.orbital_band canonical.orbital_band
  %(prog)s --all --yes kaggle.orbital_band canonical.orbital_band
  %(prog)s --reason "Custom reason" kaggle.orbital_band canonical.orbital_band
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "source_field",
        help="Source field path using dot notation (e.g., kaggle.orbital_band, sources.kaggle.orbital_band)"
    )
    
    parser.add_argument(
        "target_field",
        help="Target field path using dot notation (e.g., canonical.orbital_band)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them to the database"
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="Apply to all matching documents without limit"
    )
    
    parser.add_argument(
        "--filter",
        type=str,
        help="Filter documents using field=value syntax (e.g., 'identifier=NORAD-25544', 'canonical.country_of_origin=USA')"
    )
    
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompts and proceed automatically"
    )
    
    parser.add_argument(
        "--reason",
        type=str,
        help="Add a custom reason to the transformation history"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output for detailed logging"
    )
    
    args = parser.parse_args()
    
    return args


def normalize_field_path(field_path: str) -> str:
    """
    Normalize field path to ensure it references the correct location in the document.
    
    Args:
        field_path: Field path (e.g., "kaggle.orbital_band" or "sources.kaggle.orbital_band")
    
    Returns:
        Normalized path (e.g., "sources.kaggle.orbital_band")
    """
    if field_path.startswith("sources.") or field_path.startswith("canonical."):
        return field_path
    
    if field_path.startswith("kaggle.") or field_path.startswith("unoosa.") or \
       field_path.startswith("celestrak.") or field_path.startswith("spacetrack."):
        return f"sources.{field_path}"
    
    return field_path


def parse_filter(filter_str: str) -> Dict[str, Any]:
    """
    Parse filter string into MongoDB query.
    
    Supports multiple formats:
    - Simple equality: "field=value"
    - Multiple filters: "field1=value1,field2=value2"
    - Numeric values: "field=123"
    
    Args:
        filter_str: Filter in "field=value" format
    
    Returns:
        MongoDB query dictionary
    """
    if not filter_str:
        return {}
    
    query = {}
    
    # Split by comma for multiple filters
    filters = [f.strip() for f in filter_str.split(",")]
    
    for filter_part in filters:
        if "=" not in filter_part:
            raise ValueError(f"Invalid filter format: {filter_part}. Expected 'field=value'")
        
        field, value = filter_part.split("=", 1)
        field = field.strip()
        value = value.strip()
        
        # Try to convert to number if possible
        try:
            if "." in value:
                value = float(value)
            else:
                value = int(value)
        except ValueError:
            # Keep as string
            pass
        
        query[field] = value
    
    return query


def validate_field_path(field_path: str) -> bool:
    """
    Validate that a field path is well-formed.
    
    Args:
        field_path: Field path to validate
    
    Returns:
        True if valid, False otherwise
    """
    if not field_path or not field_path.strip():
        return False
    
    # Check for invalid characters
    invalid_chars = ["$", " ", "\n", "\t"]
    for char in invalid_chars:
        if char in field_path:
            print(f"Error: Field path contains invalid character '{char}': {field_path}", file=sys.stderr)
            return False
    
    # Check for consecutive dots
    if ".." in field_path:
        print(f"Error: Field path contains consecutive dots: {field_path}", file=sys.stderr)
        return False
    
    # Check for leading/trailing dots
    if field_path.startswith(".") or field_path.endswith("."):
        print(f"Error: Field path starts or ends with dot: {field_path}", file=sys.stderr)
        return False
    
    return True


def validate_arguments(args) -> bool:
    """
    Validate parsed arguments.
    
    Args:
        args: Parsed arguments from argparse
    
    Returns:
        True if valid, False otherwise
    """
    if not args.source_field:
        print("Error: source_field is required", file=sys.stderr)
        return False
    
    if not args.target_field:
        print("Error: target_field is required", file=sys.stderr)
        return False
    
    # Validate field paths
    if not validate_field_path(args.source_field):
        return False
    
    if not validate_field_path(args.target_field):
        return False
    
    if args.filter:
        try:
            parse_filter(args.filter)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return False
    
    return True


def build_query(source_field: str, filter_str: Optional[str] = None) -> Dict[str, Any]:
    """
    Build MongoDB query to find documents with the source field.
    
    Args:
        source_field: Normalized source field path
        filter_str: Optional filter string in "field=value" format
    
    Returns:
        MongoDB query dictionary
    """
    query = {}
    
    # Add user-provided filters first
    if filter_str:
        query.update(parse_filter(filter_str))
    
    # Add source field existence check
    query[source_field] = {"$exists": True, "$ne": None}
    
    return query


def query_documents(collection, query: Dict[str, Any], limit: Optional[int] = None, verbose: bool = False) -> List[Dict[str, Any]]:
    """
    Query documents from MongoDB collection.
    
    Args:
        collection: MongoDB collection object
        query: MongoDB query dictionary
        limit: Optional limit on number of documents to return
        verbose: Enable verbose logging
    
    Returns:
        List of matching documents
    """
    if verbose:
        print(f"Querying with: {query}")
    
    cursor = collection.find(query)
    
    if limit is not None:
        cursor = cursor.limit(limit)
    
    documents = list(cursor)
    
    if verbose:
        print(f"Retrieved {len(documents)} documents")
    
    return documents


def promote_document(
    doc: Dict[str, Any],
    source_field: str,
    target_field: str,
    reason: Optional[str] = None,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Promote a field from source to target in a single document.
    
    Args:
        doc: Document to process
        source_field: Source field path (normalized)
        target_field: Target field path (normalized)
        reason: Optional reason for the transformation
        verbose: Enable verbose logging
    
    Returns:
        Dictionary with status and details:
        {
            "success": bool,
            "doc_id": str,
            "value": Any,
            "error": str (optional)
        }
    """
    doc_id = str(doc.get("_id", "unknown"))
    result = {"doc_id": doc_id}
    
    try:
        value = get_nested_field(doc, source_field)
        
        if value is None:
            result["success"] = False
            result["error"] = f"Source field '{source_field}' not found or is None"
            return result
        
        if not set_nested_field(doc, target_field, value):
            result["success"] = False
            result["error"] = f"Failed to set target field '{target_field}'"
            return result
        
        record_transformation(doc, source_field, target_field, value, reason)
        
        result["success"] = True
        result["value"] = value
        
        if verbose:
            print(f"  ✓ {doc_id}: {source_field} → {target_field} = {value}")
        
        return result
        
    except Exception as e:
        result["success"] = False
        result["error"] = str(e)
        if verbose:
            print(f"  ✗ {doc_id}: Error - {e}")
        return result


def update_document_in_db(collection, doc: Dict[str, Any], verbose: bool = False) -> bool:
    """
    Update a document in MongoDB.
    
    Args:
        collection: MongoDB collection object
        doc: Document to update
        verbose: Enable verbose logging
    
    Returns:
        True if successful, False otherwise
    """
    try:
        result = collection.replace_one(
            {"_id": doc["_id"]},
            doc
        )
        
        if result.modified_count == 1:
            if verbose:
                print(f"  → Updated document {doc['_id']} in database")
            return True
        else:
            if verbose:
                print(f"  → Document {doc['_id']} not modified (may be unchanged)")
            return False
            
    except Exception as e:
        if verbose:
            print(f"  ✗ Failed to update document {doc['_id']}: {e}")
        return False


def check_target_field_conflicts(collection, query: Dict[str, Any], target_field: str, limit: int = 10) -> Dict[str, Any]:
    """
    Check if target field already exists in matching documents.
    
    Args:
        collection: MongoDB collection object
        query: MongoDB query dictionary
        target_field: Target field path to check
        limit: Number of documents to sample for checking
    
    Returns:
        Dictionary with conflict information:
        {
            "total_conflicts": int,
            "sample_conflicts": list of doc_ids
        }
    """
    # Build query to check for existing target field
    conflict_query = query.copy()
    conflict_query[target_field] = {"$exists": True}
    
    count = collection.count_documents(conflict_query)
    
    if count == 0:
        return {"total_conflicts": 0, "sample_conflicts": []}
    
    # Get sample of conflicting documents
    sample = list(collection.find(conflict_query, {"_id": 1}).limit(limit))
    sample_ids = [str(doc["_id"]) for doc in sample]
    
    return {
        "total_conflicts": count,
        "sample_conflicts": sample_ids
    }


def confirm_operation(
    count: int,
    source_field: str,
    target_field: str,
    dry_run: bool = False,
    conflicts: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Prompt user to confirm large batch operations.
    
    Args:
        count: Number of documents to process
        source_field: Source field path
        target_field: Target field path
        dry_run: Whether this is a dry-run
        conflicts: Optional conflict information from check_target_field_conflicts
    
    Returns:
        True if user confirms, False otherwise
    """
    operation = "preview" if dry_run else "update"
    
    print(f"\n⚠  About to {operation} {count:,} document(s)")
    print(f"   Source: {source_field}")
    print(f"   Target: {target_field}")
    
    # Show conflict warning if present
    if conflicts and conflicts["total_conflicts"] > 0:
        print(f"\n⚠  WARNING: {conflicts['total_conflicts']} document(s) already have {target_field}")
        print("   These values will be OVERWRITTEN!")
        if conflicts["sample_conflicts"]:
            print(f"   Sample IDs: {', '.join(conflicts['sample_conflicts'][:5])}")
    
    response = input("\nProceed? (y/N): ").strip().lower()
    return response in ["y", "yes"]


def process_documents(
    collection,
    documents: List[Dict[str, Any]],
    source_field: str,
    target_field: str,
    reason: Optional[str] = None,
    dry_run: bool = False,
    verbose: bool = False
) -> Dict[str, int]:
    """
    Process multiple documents, promoting fields from source to target.
    
    Args:
        collection: MongoDB collection object
        documents: List of documents to process
        source_field: Source field path (normalized)
        target_field: Target field path (normalized)
        reason: Optional reason for the transformation
        dry_run: If True, don't update database
        verbose: Enable verbose logging
    
    Returns:
        Statistics dictionary with counts:
        {
            "total": int,
            "updated": int,
            "skipped": int,
            "errors": int
        }
    """
    stats = {
        "total": len(documents),
        "updated": 0,
        "skipped": 0,
        "errors": 0
    }
    
    total = len(documents)
    print(f"\nProcessing {total} document(s)...")
    
    # Show progress indicator for batches > 20
    show_progress = total > 20 and not verbose
    
    for i, doc in enumerate(documents, 1):
        if verbose:
            print(f"\n[{i}/{total}] Processing document {doc.get('_id')}")
        elif show_progress and i % 10 == 0:
            # Show progress every 10 documents
            percent = (i / total) * 100
            print(f"  Progress: {i}/{total} ({percent:.1f}%)")
        
        result = promote_document(doc, source_field, target_field, reason, verbose)
        
        if not result["success"]:
            stats["errors"] += 1
            if not verbose:
                print(f"  ✗ Error on {result['doc_id']}: {result.get('error', 'Unknown error')}")
            continue
        
        if dry_run:
            stats["skipped"] += 1
            if not verbose and (i <= 5 or total <= 10):
                # Show first 5 for large batches, all for small batches
                print(f"  [DRY-RUN] Would update {result['doc_id']}: {source_field} → {target_field} = {result['value']}")
        else:
            if update_document_in_db(collection, doc, verbose):
                stats["updated"] += 1
                if not verbose and (i <= 5 or total <= 10):
                    # Show first 5 for large batches, all for small batches
                    print(f"  ✓ Updated {result['doc_id']}: {source_field} → {target_field} = {result['value']}")
            else:
                stats["errors"] += 1
    
    if show_progress:
        print(f"  Progress: {total}/{total} (100.0%)")
    
    return stats


def main():
    """Main entry point for the script"""
    args = parse_arguments()
    
    if not validate_arguments(args):
        sys.exit(1)
    
    if args.verbose:
        print(f"Source field: {args.source_field}")
        print(f"Target field: {args.target_field}")
        print(f"Dry-run mode: {args.dry_run}")
        print(f"Filter: {args.filter}")
        print(f"Reason: {args.reason}")
    
    if not connect_mongodb():
        print("Error: Failed to connect to MongoDB", file=sys.stderr)
        sys.exit(1)
    
    try:
        source_field = normalize_field_path(args.source_field)
        target_field = normalize_field_path(args.target_field)
        
        if args.verbose:
            print(f"Normalized source field: {source_field}")
            print(f"Normalized target field: {target_field}")
        
        print(f"\nPromoting: {source_field} → {target_field}")
        print("-" * 60)
        
        collection = get_satellites_collection()
        
        # Build query
        query = build_query(source_field, args.filter)
        
        if args.verbose:
            print(f"MongoDB query: {query}")
        
        # Count matching documents
        count = collection.count_documents(query)
        print(f"\nFound {count:,} documents with {source_field}")
        
        if count == 0:
            print("No documents to update.")
            disconnect_mongodb()
            sys.exit(0)
        
        if args.dry_run:
            print("\n[DRY-RUN MODE] No changes will be applied.\n")
        
        limit = None if args.all else 5
        documents = query_documents(collection, query, limit=limit, verbose=args.verbose)
        
        if args.verbose:
            print(f"\nRetrieved {len(documents)} documents for processing")
            print(f"Sample document IDs: {[doc.get('_id') for doc in documents[:3]]}")
        
        # Check for target field conflicts
        conflicts = check_target_field_conflicts(collection, query, target_field, limit=10)
        
        if conflicts["total_conflicts"] > 0:
            print(f"\n⚠  Note: {conflicts['total_conflicts']} document(s) already have {target_field}")
            if not args.dry_run:
                print("   These values will be overwritten.")
        
        # Confirmation prompt for large operations (>10 documents)
        if len(documents) > 10 and not args.yes:
            if not confirm_operation(len(documents), source_field, target_field, args.dry_run, conflicts):
                print("\nOperation cancelled by user.")
                disconnect_mongodb()
                sys.exit(0)
        
        stats = process_documents(
            collection,
            documents,
            source_field,
            target_field,
            reason=args.reason,
            dry_run=args.dry_run,
            verbose=args.verbose
        )
        
        print("\n" + "=" * 60)
        print("Summary:")
        print(f"  Total documents: {stats['total']}")
        if args.dry_run:
            print(f"  Would update: {stats['skipped']}")
        else:
            print(f"  Updated: {stats['updated']}")
        print(f"  Errors: {stats['errors']}")
        print("=" * 60)
        
        if stats['errors'] > 0:
            print(f"\n⚠ Warning: {stats['errors']} document(s) had errors")
            disconnect_mongodb()
            sys.exit(1)
        
        if args.dry_run:
            print("\n✓ Dry-run completed successfully. Use without --dry-run to apply changes.")
        else:
            print(f"\n✓ Successfully updated {stats['updated']} document(s)")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        disconnect_mongodb()
        sys.exit(1)
    finally:
        disconnect_mongodb()
    
    sys.exit(0)


if __name__ == "__main__":
    main()

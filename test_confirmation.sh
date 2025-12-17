#!/bin/bash
# Test script to demonstrate confirmation prompt behavior

echo "========================================================================"
echo "  TEST: Confirmation Prompt for Large Batch"
echo "========================================================================"
echo ""
echo "This test will query a large batch (>10 documents) and show the"
echo "confirmation prompt. Type 'n' or press Enter to cancel."
echo ""
echo "Command:"
echo "  python promote_attributes.py --dry-run --all \\"
echo "    --filter 'canonical.country_of_origin=Russian Federation' \\"
echo "    unoosa.country_of_origin canonical.country_of_origin"
echo ""
echo "Expected behavior:"
echo "  1. Finds 967 documents"
echo "  2. Shows confirmation prompt: '⚠  About to preview 967 document(s)'"
echo "  3. Waits for user input: 'Proceed? (y/N): '"
echo "  4. If 'n' or Enter: 'Operation cancelled by user.'"
echo "  5. If 'y' or 'yes': Proceeds with processing"
echo ""
echo "Press Enter to run the test (you can cancel when prompted)..."
read

python promote_attributes.py --dry-run --all \
  --filter 'canonical.country_of_origin=Russian Federation' \
  unoosa.country_of_origin canonical.country_of_origin

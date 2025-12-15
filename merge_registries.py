import pandas as pd

print("Merging registries...")

base_df = pd.read_csv("unoosa_registry.csv")
import_df = pd.read_csv("unoosa_registry_import.csv")

print(f"Base registry: {len(base_df)} records")
print(f"Import file: {len(import_df)} records")

combined = pd.concat([base_df, import_df], ignore_index=True)
combined = combined.drop_duplicates(subset=['Registration Number'], keep='first')

print(f"Combined (deduplicated): {len(combined)} records")

combined.to_csv("unoosa_registry.csv", index=False)
print("✓ Saved to unoosa_registry.csv")

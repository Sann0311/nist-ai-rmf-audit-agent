import pandas as pd

# Read the Excel file
df = pd.read_excel('Audit.xlsx')

# Get the 7 NIST AI RMF categories from Trust-worthiness characteristic
categories = df['Trust-worthiness characteristic'].dropna().unique()
print("7 NIST AI RMF Categories:")
for i, cat in enumerate(categories, 1):
    print(f"{i}. {cat}")

print("\n" + "="*80)

# For each category, show the questions and baseline evidence
for category in categories:
    print(f"\nCATEGORY: {category}")
    print("-" * 50)
    
    category_data = df[df['Trust-worthiness characteristic'] == category]
    
    # Get non-null questions and sub-questions
    for idx, row in category_data.iterrows():
        if pd.notna(row['Question']) and row['Question'].strip():
            print(f"\nMain Question: {row['Question']}")
            if pd.notna(row['NIST AI RMF Control']):
                print(f"NIST Control: {row['NIST AI RMF Control']}")
        
        if pd.notna(row['Sub Question']) and row['Sub Question'].strip():
            print(f"  Sub-Question: {row['Sub Question']}")
            if pd.notna(row['Baseline Evidence ']):
                print(f"  Baseline Evidence: {row['Baseline Evidence '][:200]}...")
    
    print("\n" + "="*80)

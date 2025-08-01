import pandas as pd

# Read the Excel file and get sheet names
excel_file = pd.ExcelFile('Audit.xlsx')
print('Sheet names:')
for sheet in excel_file.sheet_names:
    print(f'- "{sheet}"')

# Read the first sheet to see the data structure
df = pd.read_excel('Audit.xlsx', sheet_name=0)
print(f'\nFirst sheet has {len(df)} rows and {len(df.columns)} columns')
print('\nSample data (first 3 rows):')
print(df.head(3)) 
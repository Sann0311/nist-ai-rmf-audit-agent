import pandas as pd

# Read the Excel file
df = pd.read_excel('Audit.xlsx')

print('Exact columns with quotes:')
for i, col in enumerate(df.columns):
    print(f'{i}: "{col}"')

import pandas as pd

# Read the Excel file
df = pd.read_excel('Audit.xlsx')

print('Shape:', df.shape)
print('\nAll columns:')
for i, col in enumerate(df.columns):
    print(f'{i}: {col}')

print('\nNIST AI RMF Control unique values:')
print(df['NIST AI RMF Control'].dropna().unique())

print('\nSample data:')
print(df[['Question', 'NIST AI RMF Control', 'Sub Question', 'Baseline Evidence ']].head(15))

print('\nTrustworthiness characteristics:')
print(df['Trust-worthiness characteristic'].dropna().unique())

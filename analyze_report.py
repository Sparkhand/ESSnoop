import pandas as pd

# Open report.csv
df = pd.read_csv('ethersolve_report.csv')

# Print the total number of rows
print(f"Total contracts: {df.shape[0]}")

# Print the mean of percentage of solved_percentage
print(f"Mean of solved_percentage: {df['solved_percentage'].mean()}")

# Count the number of unreachable jumps
unreachable_jumps = df['unreachable_jumps'].sum()
print(f"Total unreachable jumps: {unreachable_jumps}")
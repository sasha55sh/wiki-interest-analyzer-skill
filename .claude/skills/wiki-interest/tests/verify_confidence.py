from datetime import date

from wiki_interest.analyze import analyze

print("\n" + "=" * 70)
print("CONFIDENCE SCORING VERIFICATION")
print("=" * 70)

# Test 1: Small volume
print("\nTEST 1: LOW VOLUME (100 views/month)")
daily1 = {}
for m in range(1, 25):
    for d in range(1, 29):
        daily1[date(2023 + m // 12, (m - 1) % 12 + 1, d)] = 4

result1 = analyze(daily1)
print(f"  Total views: {sum(daily1.values())} (median ~112/month)")
print(f"  Months: {len({(d.year, d.month) for d in daily1})}")
print(f"  Confidence: {result1['confidence']}")
print(f"  Caveats: {result1['caveats']}")
print(f"  Result: {result1['yoy_change_pct']}% YoY")

# Test 2: High seasonality
print("\nTEST 2: HIGH SEASONALITY (winter vs summer)")
daily2 = {}
for m in range(1, 25):
    year = 2023 + m // 12
    month = (m - 1) % 12 + 1
    
    # Winter (Jan-Apr, Sep-Dec): 200 views/day
    # Summer (May-Aug): 50 views/day (high seasonality)
    daily_views = 200 if month in [1,2,3,4,9,10,11,12] else 50
    
    for d in range(1, 29):
        daily2[date(year, month, d)] = daily_views

result2 = analyze(daily2)
mean = sum(daily2.values()) / len(daily2)
std = (sum((v - mean)**2 for v in daily2.values()) / len(daily2)) ** 0.5
cv = std / mean
print(f"  Mean: {mean:.0f}, Std: {std:.0f}, CV: {cv:.2f} (threshold 0.5)")
print(f"  Confidence: {result2['confidence']}")
print(f"  Caveats: {result2['caveats']}")
print(f"  Result: {result2['yoy_change_pct']}% YoY")

# Test 3: Good data
print("\nTEST 3: GOOD DATA (stable +15% growth)")
daily3 = {}
for m in range(1, 25):
    year = 2023 + m // 12
    month = (m - 1) % 12 + 1
    
    if year == 2023:
        v = 1000
    else:
        v = 1150  # +15%
    
    for d in range(1, 29):
        daily3[date(year, month, d)] = v

result3 = analyze(daily3)
med = sum(daily3.values()) / 24 / 28
print(f"  Total views: {sum(daily3.values())} (median ~{med:.0f}/day)")
print("  Months: 24, Growth: +15% YoY")
print(f"  Confidence: {result3['confidence']}")
print(f"  Caveats: {result3['caveats']}")
print(f"  Result: {result3['yoy_change_pct']}% YoY")
print(f"  CI95: {result3['ci95']}")

print("\n" + "=" * 70)
print("CONFIDENCE RULES:")
print("=" * 70)
print("  +1 point: median views >= 1000 (monthly)")
print("  +1 point: >= 24 months of data")
print("  +1 point: trend significant (p < 0.05) with non-zero CI95")
print()
print("  Scoring: 0-1 = low, 2 = medium, 3 = high")
print("=" * 70)

import json
import pandas as pd
s = pd.Series([1.0, 2.0, None])
val = s.iloc[2]
try:    json.dumps(pd.isna(val))
except Exception as e: print("SERIES_ISNA_NAN:", e.args[0] if e.args else e)

try:    json.dumps(pd.isna(s.iloc[0]))
except Exception as e: print("SERIES_ISNA_NUM:", e.args[0] if e.args else e)

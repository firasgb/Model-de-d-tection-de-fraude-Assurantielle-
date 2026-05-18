import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from utils.data_loader import DataLoader
loader = DataLoader(os.path.join(os.path.dirname(__file__), 'data'))
loaded = loader.load_all()
print('loaded', loaded)
sin = loader.get_sinistres()
if sin is not None:
    print('sinistres columns:', list(sin.columns))
    print('sample row keys:', list(sin.iloc[0].to_dict().keys()))
else:
    print('sinistres not loaded')

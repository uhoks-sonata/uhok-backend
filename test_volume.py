import os, psutil
process = psutil.Process(os.getpid())
print(f"Memory used: {process.memory_info().rss / 1024**2:.2f} MB")

#!/usr/bin/env python3
import inspect
from migrator.utils.fstab import FstabManager, FstabEntry

# Show the is_portable method
print("Fstab portability logic:")
print(inspect.getsource(FstabEntry.is_portable))

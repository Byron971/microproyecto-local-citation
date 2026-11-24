"""One inference slot shared by article retrieval and citation classification."""
import threading

LOCK = threading.RLock()

from collections import defaultdict
import threading

class EventBus:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EventBus, cls).__new__(cls)
                cls._instance.subscribers = defaultdict(list)
        return cls._instance

    def subscribe(self, event_type: str, callback):
        self.subscribers[event_type].append(callback)

    def publish(self, event_type: str, data: dict = None):
        print(f"[EventBus] Publishing event: {event_type}")
        if data is None:
            data = {}
        # Simple synchronous publish for now, could be dispatched to a worker thread if needed
        for callback in self.subscribers.get(event_type, []):
            try:
                callback(data)
            except Exception as e:
                print(f"[EventBus] Error in subscriber for {event_type}: {e}")

event_bus = EventBus()

import os

# From main.py
main_file = "/app/app/main.py"
_uploads_dir = os.path.join(os.path.dirname(main_file), '..', 'uploads')
print("main _uploads_dir:", _uploads_dir)
print("main normpath:", os.path.normpath(_uploads_dir))

# From storage.py
storage_file = "/app/app/services/storage.py"
_local_root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(storage_file))), "uploads")
print("storage _local_root:", _local_root)
print("storage normpath:", os.path.normpath(_local_root))

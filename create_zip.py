import os
import zipfile

zip_path = "teams-bot-deploy.zip"
if os.path.exists(zip_path):
    os.remove(zip_path)

with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
    for f in ["requirements.txt", "runtime.txt"]:
        if os.path.exists(f):
            zipf.write(f, f)

    for root, dirs, files in os.walk("execution"):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = file_path.replace(os.sep, "/")
            zipf.write(file_path, arcname)

    for root, dirs, files in os.walk(".tmp"):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = file_path.replace(os.sep, "/")
            zipf.write(file_path, arcname)

size = os.path.getsize(zip_path)
print(f"Created {zip_path} ({size:,} bytes)")

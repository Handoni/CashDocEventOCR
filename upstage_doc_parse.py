import os
import requests
from tqdm import tqdm

api_key = "up_3klEdFK7qwq5JOKBhHHKi5eGilHo3"
base_url = "https://api.upstage.ai/v1/document-digitization"

headers = {"Authorization": f"Bearer {api_key}"}
data = {
    "ocr": "force",
    "model": "document-parse",
    "output_formats": '["html", "markdown", "text"]',
}

files = os.listdir("static")

for file in tqdm(files):
    file_path = os.path.join("static", file)
    with open(file_path, "rb") as f:
        response = requests.post(
            base_url, headers=headers, files={"document": f}, data=data
        )
        if response.status_code == 200:
            file_name, _ = os.path.splitext(file)
            with open(f"data/{file_name}_upstage_doc.json", "wb") as output_file:
                output_file.write(response.content)
        else:
            print(
                f"Failed to upload {file}. Status code: {response.status_code} - {response.text}"
            )

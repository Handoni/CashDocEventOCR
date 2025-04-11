# main.py
import glob
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import json
import os
from googletrans import Translator
import urllib.request
import uvicorn

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def load_upstage_annotations_from_file(json_path):
    """try_upstage_document_ai.json 형식의 데이터를 파싱하여 annotation 리스트를 반환"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    annotations = []
    if "pages" in data:
        for page in data["pages"]:
            for line in page["lines"]:
                text = line.get("text", "")
                bounding_box_list = line.get("boundingBox", [])
                all_vertices = []
                for bbox in bounding_box_list:
                    vertices = bbox.get("vertices", [])
                    all_vertices.extend(vertices)
                if all_vertices:
                    xs = [v.get("x", 0) for v in all_vertices]
                    ys = [v.get("y", 0) for v in all_vertices]
                    left = min(xs)
                    top = min(ys)
                    right = max(xs)
                    bottom = max(ys)
                    width = right - left
                    height = bottom - top
                    annotations.append(
                        {
                            "text": text,
                            "left": left,
                            "top": top,
                            "width": width,
                            "height": height,
                        }
                    )
    return annotations


def load_naver_annotations_from_file(json_path):
    """naver.json 형식의 데이터를 파싱하여 annotation 정보와 이미지 URL을 포함한 dict를 반환"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    annotations = []
    for image_data in data.get("images", []):
        for field in image_data.get("fields", []):
            text = field.get("inferText", "")
            vertices = field.get("boundingPoly", {}).get("vertices", [])
            if vertices:
                xs = [float(v.get("x", 0)) for v in vertices]
                ys = [float(v.get("y", 0)) for v in vertices]
                left = min(xs)
                top = min(ys)
                right = max(xs)
                bottom = max(ys)
                width = right - left
                height = bottom - top
                annotations.append(
                    {
                        "text": text,
                        "left": left,
                        "top": top,
                        "width": width,
                        "height": height,
                    }
                )
    original_file = data.get("originalFileName", "")
    image_type = data.get("imageType", "jpg")
    image_url = f"/static/{original_file}.jpg" if original_file else ""
    return {
        "image_url": image_url,
        "annotations": annotations,
        "originalFileName": original_file,
        "imageType": image_type,
    }


def list_image_basenames():
    """static 폴더에 존재하는 .jpg 파일의 베이스 이름 목록을 반환 (확장자 제외)"""
    jpg_files = glob.glob(os.path.join("static", "*.jpg"))
    basenames = [os.path.splitext(os.path.basename(f))[0] for f in jpg_files]
    basenames.sort()  # 알파벳순 정렬
    return basenames


@app.get("/", response_class=HTMLResponse)
async def root():
    basenames = list_image_basenames()
    if not basenames:
        return HTMLResponse("No images found in static directory.", status_code=404)
    first_name = basenames[0]
    return RedirectResponse(url=f"/compare/{first_name}", status_code=302)


@app.get("/compare/{imagename}", response_class=HTMLResponse)
async def compare_images(request: Request, imagename: str):
    basenames = list_image_basenames()
    if imagename not in basenames:
        raise HTTPException(status_code=404, detail="해당 이미지를 찾을 수 없습니다.")

    # 이전/다음 이미지 이름 계산
    current_idx = basenames.index(imagename)
    prev_name = basenames[current_idx - 1] if current_idx > 0 else None
    next_name = basenames[current_idx + 1] if current_idx < len(basenames) - 1 else None

    # JSON 파일 경로 설정
    upstage_json_path = os.path.join("data", f"{imagename}_upstage.json")
    naver_json_path = os.path.join("data", f"{imagename}_naver.json")

    if not os.path.exists(upstage_json_path):
        raise HTTPException(
            status_code=404, detail="Upstage JSON 파일을 찾을 수 없습니다."
        )
    if not os.path.exists(naver_json_path):
        raise HTTPException(
            status_code=404, detail="Naver JSON 파일을 찾을 수 없습니다."
        )

    upstage_annotations = load_upstage_annotations_from_file(upstage_json_path)
    naver_data = load_naver_annotations_from_file(naver_json_path)

    upstage_image_url = f"/static/{imagename}.jpg"

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "upstage": {
                "image_url": upstage_image_url,
                "annotations": upstage_annotations,
            },
            "naver": naver_data,
            "prev_name": prev_name,
            "next_name": next_name,
        },
    )


@app.get("/translate")
async def translate_text(text: str):
    try:
        url = "https://naveropenapi.apigw.ntruss.com/nmt/v1/translation"

        data = f"source=ko&target=en&text={text}"
        request = urllib.request.Request(url)
        request.add_header("X-NCP-APIGW-API-KEY-ID", "ewwkpow2bp")
        request.add_header(
            "X-NCP-APIGW-API-KEY", "BoKHqYFmWNNIklbfoCFGchW1gDYLCBE95vbFGU35"
        )

        response = urllib.request.urlopen(request, data=data.encode("utf-8"))
        response_code = response.getcode()

        if response_code == 200:
            response_body = response.read()
            response_json = json.loads(response_body)
            translated_text = response_json["message"]["result"]["translatedText"]
            return JSONResponse(content={"translated": translated_text})
        else:
            return JSONResponse(
                content={"error": "Translation failed"}, status_code=response_code
            )
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)

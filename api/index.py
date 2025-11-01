from flask import Flask, jsonify, request
import http.client, json, requests, traceback
import re
app = Flask(__name__)
def clean(text: str) -> str:
    """
    Giải mã các ký tự Unicode escape như \u003C -> <, \u003E -> >
    và xoá toàn bộ thẻ HTML khỏi chuỗi.
    """
    if not isinstance(text, str):
        return text

    # Bước 1: chuyển các escape Unicode HTML sang ký tự thật
    text = (
        text.replace("\\u003C", "<")
            .replace("\\u003E", ">")
            .replace("\\u002F", "/")  # trường hợp \/ cũng gặp
    )

    # Bước 2: xoá toàn bộ thẻ HTML
    clean_text = re.sub(r'<[^>]+>', '', text)

    # Bước 3: xoá khoảng trắng thừa
    return clean_text.strip()
def checkroom(code):
  url = "https://wayground.com/play-api/v5/checkRoom"
  payload = {
    "roomCode": code
  }
  headers = {
    'User-Agent': "Mozilla/5.0 (Linux; Android 11; RMX3269 Build/RP1A.201005.001) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.7390.98 Mobile Safari/537.36",
    'Accept': "application/json",
    'Accept-Encoding': "gzip, deflate, br, zstd",
    'Content-Type': "application/json",
    'credentials': "include",
    'sec-ch-ua-platform': "\"Android\"",
    'experiment-name': "main_main",
    'sec-ch-ua': "\"Android WebView\";v=\"141\", \"Not?A_Brand\";v=\"8\", \"Chromium\";v=\"141\"",
    'sec-ch-ua-mobile': "?1",
    'origin': "https://wayground.com",
    'x-requested-with': "mark.via.gp",
    'sec-fetch-site': "same-origin",
    'sec-fetch-mode': "cors",
    'sec-fetch-dest': "empty",
    'accept-language': "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    'priority': "u=1, i",
    }
  response = requests.post(url, json=payload, headers=headers)
  
  try:
    r = response.json()
    if '"success":false' in response.text:
      return{"status": "error", "msg": "Room not found"}
    else:
      return{"status": "success", "msg": r["room"]["hash"]}
  except Exception as e:
    return{"status":"error", "msg": e}
@app.route('/')
def home():
    return jsonify({"status": "ok", "message": "✅ Quizizz Flask API running on Vercel!"})


@app.route('/api/quizizz', methods=['GET'])
def quizizz():
    playid = request.args.get('playid')
    room = request.args.get('room')
    if room is None and playid is None:
      return jsonify({"error": "Thiếu Dữ Liệu Room & Playid"}), 500
    try:
        # --- Gọi Wayground API ---
        roomhash = checkroom(room)
        if roomhash["status"] == "error":
          return jsonify({"error": roomhash["msg"]}), 500
        else:
          roomhashcode = roomhash["msg"]
        
        conn = http.client.HTTPSConnection("wayground.com")

        payload = json.dumps({
            "roomHash": roomhashcode,
            "playerId": playid,
            "startSource": "reconnectRejoin",
            "powerupInternalVersion": "20",
            "type": "live",
            "state": "waiting",
            "soloApis": "v2",
            "serverId": "ax68f7ec51a1507600215982e9",
            "ip": "116.98.240.175",
            "user-agent": "Mozilla/5.0 (Linux; Android 11; RMX3269 Build/RP1A.201005.001) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.7390.98 Mobile Safari/537.36",
            "socketId": "cddRAszPHZNIQ4tAnSLiMk",
            "authCookie": None,
            "socketExperiment": "authRevamp"
        })

        headers = {
            'User-Agent': "Mozilla/5.0 (Linux; Android 11; RMX3269 Build/RP1A.201005.001) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.7390.98 Mobile Safari/537.36",
            'Accept': "application/json",
            'Content-Type': "application/json",
            'origin': "https://wayground.com",
            'x-csrf-token': "LOA1THcb59t0UVj37T2krCaa3Hw",
            'x-quizizz-uid': "33018d94-accc-4ca6-8e4c-a0ee62cca614"
        }

        conn.request("POST", "/play-api/v6/rejoinGame", payload, headers)
        res = conn.getresponse()
        data = res.read()
        x = json.loads(data.decode("utf-8"))
        if 'Player not found' in data.decode("utf-8"):
          return jsonify({"error": f"Không Tìm Thấy Player: {playid} Trong Phòng Vui Lòng Vào Phòng Rồi Nhập Tên Nickname Vào!"}), 500
        if 'Player not found in game' in data.decode("utf-8"):
          return jsonify({"error": f"Không Tìm Thấy Player: {playid} Trong Phòng Vui Lòng Vào Phòng Rồi Nhập Tên Nickname Vào!"}), 500
        # --- Xử lý danh sách câu hỏi ---
        questions = x["room"]["questions"]
        all_data = []
        for qid, qdata in questions.items():
            structure = qdata["structure"]
            question = structure["query"]["text"].replace("<p>", "").replace("</p>", "")
            answers = [opt["text"].replace("<p>", "").replace("</p>", "") for opt in structure["options"]]
            all_data.append({"question": question, "answers": answers})

        # --- Tạo prompt cho Gemini ---
        key = "AIzaSyC-_0Eitzkk42diZ52OxR8Lb5y2TPPU-eQ"
        URL = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={key}"

        prompt = f'''Bạn là một hệ thống trả lời trắc nghiệm.
Nhiệm vụ:
- Chọn duy nhất 1 đáp án phù hợp nhất cho mỗi câu hỏi.
- Không giải thích, không viết thêm.
- Chỉ trả về JSON hợp lệ:

[
  {{"question":"...","answer":"..."}}
]

Dữ liệu:
{all_data}
'''

        payload_ai = {"contents": [{"parts": [{"text": prompt}]}]}
        response = requests.post(URL, json=payload_ai)

        if response.status_code != 200:
            return jsonify({"error": "AI request failed", "detail": response.text}), 500

        ai_data = response.json()
        result = ai_data["candidates"][0]["content"]["parts"][0]["text"]
        result = result.replace("```json", "").replace("```", "")
        xoahtml = clean(result)
        json_result = json.loads(xoahtml)

        return jsonify(json_result)

    except Exception as e:
        print("❌ ERROR:", traceback.format_exc())
        return jsonify({data.decode("utf-8"): str(e)}), 500


if __name__ == "__main__":
    app.run()
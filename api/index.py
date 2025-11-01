from flask import Flask, jsonify
import http.client, json, requests, traceback

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "ok", "message": "✅ Quizizz Flask API running on Vercel!"})


@app.route('/api/quizizz', methods=['GET'])
def quizizz():
    try:
        # --- Gọi Wayground API ---
        conn = http.client.HTTPSConnection("wayground.com")

        payload = json.dumps({
            "roomHash": "6904901854c2459a5e2b0725",
            "playerId": "Ender",
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
        json_result = json.loads(result)

        return jsonify(json_result)

    except Exception as e:
        print("❌ ERROR:", traceback.format_exc())
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run()
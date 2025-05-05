# lambda/index.py
import json
import os
import urllib.request # requests の代わりに urllib を使用
import urllib.error   # エラーハンドリング用
import socket         # タイムアウト判定用

# 環境変数からFastAPIのエンドポイントURLを取得
FASTAPI_ENDPOINT_URL = os.environ.get('FASTAPI_ENDPOINT_URL')

# FastAPIへのリクエストタイムアウト（秒）
REQUEST_TIMEOUT = 20 # 必要に応じて調整

def lambda_handler(event, context):
    # --- [変更なし] リクエストとユーザー情報の処理 ---
    try:
        print("Received event:", json.dumps(event))

        # Cognitoユーザー情報取得など（省略）...
        user_info = None # (前のコードから省略)

        # リクエストボディの解析
        try:
            if isinstance(event.get('body'), str):
                body = json.loads(event['body'])
            else:
                body = event.get('body', {})
        except json.JSONDecodeError:
             print("Error decoding JSON body.")
             raise ValueError("Invalid JSON format in request body")

        if not body or 'message' not in body:
            raise ValueError("Request body must contain a 'message' field.")

        message = body['message']
        conversation_history = body.get('conversationHistory', [])

        print(f"Processing message: '{message}'")
        print(f"Received conversation history length: {len(conversation_history)}")

        # --- [変更箇所] urllib.request を使用してFastAPIを呼び出す ---

        if not FASTAPI_ENDPOINT_URL:
            print("Error: FASTAPI_ENDPOINT_URL environment variable is not set.")
            raise EnvironmentError("FastAPI endpoint URL is not configured.")

        # FastAPIに送信するペイロードを作成
        payload_to_fastapi = {
            'message': message,
            'conversationHistory': conversation_history
        }

        # ヘッダー
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json' # 応答形式を指定
        }

        # ペイロードをJSON形式のバイト列にエンコード
        data = json.dumps(payload_to_fastapi).encode('utf-8')

        # urllib.request.Request オブジェクトを作成
        req = urllib.request.Request(
            FASTAPI_ENDPOINT_URL,
            data=data,
            headers=headers,
            method='POST' # HTTPメソッドを明示的に指定
        )

        print(f"Calling FastAPI endpoint via urllib: {FASTAPI_ENDPOINT_URL}")

        try:
            # リクエストを実行し、レスポンスを取得
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                status_code = response.getcode()
                response_body_bytes = response.read()
                response_body_str = response_body_bytes.decode('utf-8')

                print(f"FastAPI responded with status: {status_code}")
                # print(f"Raw response body: {response_body_str}") # デバッグ用

                if status_code >= 400:
                     # 通常、urlopenは4xx/5xxでHTTPErrorを送出するが念のため
                     raise urllib.error.HTTPError(FASTAPI_ENDPOINT_URL, status_code, "Error received from FastAPI", response.info(), response_body_bytes)

                # FastAPIからの応答 (JSON) をパース
                fastapi_response_data = json.loads(response_body_str)
                print(f"Received and parsed response from FastAPI: {fastapi_response_data}")

                # アシスタントの返信を取得 ('result' キーを期待)
                assistant_response = fastapi_response_data.get('result')
                if assistant_response is None:
                    print("Error: 'result' key not found in FastAPI response.")
                    raise ValueError("Invalid response format received from FastAPI.")

        except urllib.error.HTTPError as e:
            # FastAPIがエラー応答 (4xx, 5xx) を返した場合
            status_code = e.code
            error_body = e.read().decode('utf-8') # FastAPIからのエラーメッセージ本文
            print(f"Error calling FastAPI endpoint: HTTP Status={status_code}, Detail={error_body}")
            # FastAPIエラーとして処理
            return {
                "statusCode": status_code,
                "headers": { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
                "body": json.dumps({
                    "success": False,
                    "error": f"Backend service error (HTTP {status_code})",
                    "detail": error_body # FastAPIからのエラー詳細を含める
                })
            }
        except urllib.error.URLError as e:
            # ネットワークエラー、DNS解決エラー、タイムアウトなど
            error_reason = str(e.reason)
            print(f"Error calling FastAPI endpoint: URLError Reason={error_reason}")
            # タイムアウトかどうかを判定
            if isinstance(e.reason, socket.timeout):
                status_code = 504 # Gateway Timeout
                error_message = "The request to the backend service timed out."
            else:
                status_code = 502 # Bad Gateway (その他ネットワーク関連エラー)
                error_message = f"Failed to communicate with the backend service: {error_reason}"

            return {
                "statusCode": status_code,
                "headers": { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
                "body": json.dumps({
                    "success": False,
                    "error": error_message
                })
            }
        except json.JSONDecodeError:
            # FastAPIからの応答がJSON形式でなかった場合
             print("Error decoding JSON response from FastAPI.")
             # 502 Bad Gateway を返すのが一般的
             return {
                 "statusCode": 502,
                 "headers": { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
                 "body": json.dumps({
                     "success": False,
                     "error": "Invalid response received from backend service (not JSON)."
                 })
             }

        # --- [変更箇所] 会話履歴の更新 (ロジック自体は変更なし) ---
        messages = conversation_history.copy()
        messages.append({ "role": "user", "content": message })
        messages.append({ "role": "assistant", "content": assistant_response })

        # --- [変更なし] 成功レスポンスの返却 ---
        print("Successfully processed request using urllib.")
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": True,
                "response": assistant_response,
                "conversationHistory": messages
            })
        }

    # --- [変更なし] 全体的なエラーハンドリング ---
    except (ValueError, EnvironmentError, Exception) as error:
        error_type = type(error).__name__
        error_message = str(error)
        print(f"Error ({error_type}): {error_message}")
        status_code = 400 if isinstance(error, (ValueError, json.JSONDecodeError)) else 500
        # CORSヘッダーをエラー応答にも含める
        headers = {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "OPTIONS,POST"
        }
        return {
            "statusCode": status_code,
            "headers": headers,
            "body": json.dumps({
                "success": False,
                "error": error_message,
                "errorType": error_type
            })
        }

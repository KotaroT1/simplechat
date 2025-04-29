# lambda/index.py
import json
import os
import re  # 正規表現モジュールをインポート
import urllib.request
import urllib.parse
import urllib.error # エラー処理のためにインポート


# Lambda コンテキストからリージョンを抽出する関数
def extract_region_from_arn(arn):
    # ARN 形式: arn:aws:lambda:region:account-id:function:function-name
    match = re.search('arn:aws:lambda:([^:]+):', arn)
    if match:
        return match.group(1)
    return "us-east-1"  # デフォルト値



# 環境変数からFastAPIのエンドポイントURLを取得
FASTAPI_ENDPOINT_URL = os.environ.get("https://1b6d-35-247-121-2.ngrok-free.app/")

def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")

    # エンドポイントURLが設定されているか確認
    if not FASTAPI_ENDPOINT_URL:
        print("FASTAPI_ENDPOINT_URL environment variable not set.")
        return {
            'statusCode': 500,
            'headers': { 'Content-Type': 'application/json' },
            'body': json.dumps({'response': 'Configuration error: FastAPI endpoint URL not set.'})
        }

    try:
        # API Gatewayからのリクエストペイロードを取得
        # 通常は event['body'] にJSON文字列が入っている
        if 'body' not in event or not isinstance(event['body'], str):
             print("Invalid event format: 'body' missing or not a string.")
             return {
                'statusCode': 400, # Bad Request
                 'headers': { 'Content-Type': 'application/json' },
                'body': json.dumps({'response': 'Invalid request format.'})
            }

        request_body_json_str = event['body']
        request_body = json.loads(request_body_json_str)
        user_message = request_body.get('message')
        # 必要に応じて、リクエストから他のデータ（例: ユーザーID）を取得
        user_id = request_body.get('userId', 'anonymous_lambda')

        if not user_message:
             print("Message not found in request body.")
             return {
                'statusCode': 400, # Bad Request
                 'headers': { 'Content-Type': 'application/json' },
                'body': json.dumps({'response': 'Message field is missing in the request body.'})
            }

        # FastAPIに送信するペイロードを準備
        payload_to_fastapi = {
            "message": user_message,
            "userId": user_id # FastAPI側で利用する場合
        }

        # ペイロードをJSON文字列に変換し、バイトデータにエンコード
        data = json.dumps(payload_to_fastapi).encode('utf-8')

        # FastAPIのエンドポイントURLとパスを結合
        url = FASTAPI_ENDPOINT_URL.rstrip('/') + "/chat/"

        # HTTPリクエストヘッダーを定義
        headers = {
            'Content-Type': 'application/json',
            'Content-Length': len(data) # データ長を指定 (POSTの場合推奨)
        }

        # Requestオブジェクトを作成
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')

        print(f"Sending request to FastAPI: {url}")

        # HTTPリクエストを送信し、応答を取得
        # タイムアウトは seconds で指定
        timeout_seconds = 90
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            # HTTPステータスコードを確認
            status_code = response.getcode()
            print(f"Received status code from FastAPI: {status_code}")

            # 応答ボディを読み込み、デコード
            response_body = response.read().decode('utf-8')
            print(f"Received response body (raw): {response_body}")

            # FastAPIからの応答をJSONとして解析
            fastapi_response = json.loads(response_body)
            print(f"Received response (parsed): {json.dumps(fastapi_response)}")

            # API Gatewayに返す形式に整形
            return {
                'statusCode': status_code, # FastAPIから返されたステータスコードを返す
                'headers': { 'Content-Type': 'application/json' },
                'body': json.dumps(fastapi_response) # FastAPIからの応答ボディをそのまま返す
            }

    except urllib.error.HTTPError as e:
        # HTTPエラー (4xx, 5xxなど)
        print(f"HTTP Error occurred: {e.code} - {e.reason}")
        error_body = e.read().decode('utf-8')
        print(f"HTTP Error response body: {error_body}")
        # エラー応答ボディをそのまま返すか、エラーメッセージを整形して返す
        try:
             error_response_json = json.loads(error_body)
        except json.JSONDecodeError:
             error_response_json = {"response": f"Backend service returned error: {e.code} - {e.reason}", "details": error_body}

        return {
            'statusCode': e.code, # HTTPエラーのステータスコードを返す
            'headers': { 'Content-Type': 'application/json' },
            'body': json.dumps(error_response_json)
        }
    except urllib.error.URLError as e:
        # URLエラー (ネットワーク接続の問題など)
        print(f"URL Error occurred: {e.reason}")
        return {
            'statusCode': 502, # Bad Gateway
            'headers': { 'Content-Type': 'application/json' },
            'body': json.dumps({'response': f'Error communicating with the backend service: {e.reason}'})
        }
    except json.JSONDecodeError:
         # イベントボディまたはFastAPI応答のJSONデコードエラー
         print("Error decoding JSON from API Gateway event body or FastAPI response.")
         return {
            'statusCode': 400, # Bad Request (イベントボディの場合) または 502 (FastAPI応答の場合)
            'headers': { 'Content-Type': 'application/json' },
            'body': json.dumps({'response': 'Invalid JSON format in request or backend service response.'})
        }
    except Exception as e:
        # その他の予期しないエラー
        print(f"An unexpected error occurred: {e}")
        return {
            'statusCode': 500, # Internal Server Error
            'headers': { 'Content-Type': 'application/json' },
            'body': json.dumps({'response': f'An internal server error occurred: {e}'})
        }
       
       
                   
         
    
     
        
     
 

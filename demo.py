#!/usr/bin/env python3

# ライブラリの読み込み
import cv2
import boto3
import os
import datetime
import wave
import glob
import json
import subprocess
from flask_socketio import SocketIO
from flask import Flask, render_template, request
from motion_detector import MotionDetector


#########################################
### AWSを便利に使えるクラスを定義する ###
#########################################
class AWSDemo:
    def __init__(self):
        # Amazon Web Serviceを利用するための準備
        self.rekognition = boto3.client(service_name="rekognition")  # 画像認識サービス
        self.translate = boto3.client(service_name="translate")  # 翻訳サービス
        self.polly = boto3.client(service_name="polly")  # 音声合成サービス

        # 表情認識の単語
        # キー: {キーを翻訳したもの, 発話させるワード}
        self.emotion = {
            "HAPPY": {"translate": "幸せ", "speech": "嬉しそうだね！"},
            "SAD": {"translate": "悲しい", "speech": "悲しそうだね..."},
            "ANGRY": {"translate": "怒り", "speech": "怒ってるの？"},
            "CONFUSED": {"translate": "困惑", "speech": "困惑してる？"},
            "DISGUSTED": {"translate": "うんざり", "speech": "うんざりしたの？"},
            "SURPRISED": {"translate": "驚き", "speech": "驚いているね！"},
            "CALM": {"translate": "穏やか", "speech": "落ち着いているね～"},
            "FEAR": {"translate": "不安", "speech": "不安そうだね..."},
            "UNKNOWN": {"translate": "不明", "speech": "よくわからない表情だね..."},
        }

    def encode_image(self, image):
        """JPEG形式のデータに変換する関数"""

        return cv2.imencode(".JPEG", image)[1].tobytes()

    def detect_labels(self, encode_image):
        """画像からラベル情報を取得する関数"""

        response_data = self.rekognition.detect_labels(Image={"Bytes": encode_image})
        return response_data["Labels"]

    def detect_faces(self, encode_image):
        """画像から顔検出する関数"""

        response_data = self.rekognition.detect_faces(Image={"Bytes": encode_image}, Attributes=["ALL"])
        return response_data["FaceDetails"]

    def transrate_text(self, text):
        """テキストを翻訳する関数"""

        response_data = self.translate.translate_text(Text=text, SourceLanguageCode="en", TargetLanguageCode="ja")
        return response_data["TranslatedText"]

    def synthesize_speech(self, text):
        """テキストから音声合成する関数"""

        return self.polly.synthesize_speech(Text=text, OutputFormat="pcm", VoiceId="Takumi")["AudioStream"]

    def synthesize_speech_wave(self, text, audio_path):
        """テキストから音声合成 + WAVファイルを生成する関数"""

        speech_data = self.synthesize_speech(text)
        wave_data = wave.open(audio_path, "wb")
        wave_data.setnchannels(1)
        wave_data.setsampwidth(2)
        wave_data.setframerate(16000)
        wave_data.writeframes(speech_data.read())
        wave_data.close()


######################################
### ウェブアプリを動かすための準備 ###
######################################
app = Flask(__name__)  # Flaskアプリの準備
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
socketio = SocketIO(app)  # WebSocket通信の準備

aws_demo = AWSDemo()  # AWSを便利に使える自作ライブラリの準備
save_dir = "./static/save_images"  # 画像データの保存場所


############################################
### トップページにアクセスしたときの処理 ###
############################################
@app.route("/")
def main():
    """トップページにアクセスしたときに実行される関数"""
    return render_template("index.html")


#########################################
### WebSocketで接続がされたときの処理 ###
#########################################
@socketio.on("connect")
def connect():
    """WebSocketで接続がされたときに実行される関数"""

    # 総データ量を調べる
    data_usage = subprocess.check_output(["du", "-sh", "{}".format(save_dir)]).decode("utf-8").split()[0] + "B"

    # 現在保存されている最新画像を30枚リストアップする
    records = []
    for image_path in sorted(glob.glob("{}/*.JPG".format(save_dir)), key=os.path.getmtime)[-30:]:
        record = {
            "image_path": image_path,
            "date": datetime.datetime.fromtimestamp(os.path.getctime(image_path)).strftime("%Y年%m月%d日 %H時%M分%S秒"),
            "meta": json.load(open(os.path.splitext(image_path)[0] + ".JSON", "r")),
        }
        records.append(record)

    # ブラウザに送信
    socketio.emit("init", {"records": records, "data_usage": data_usage}, to=request.sid)


######################################################
### ウェブサーバと同時に処理させたいものを書く場所 ###
######################################################
def background_task():
    """ウェブサーバと同時に処理させたいものを書く関数"""
    # カメラの準備
    camera = cv2.VideoCapture(0, cv2.CAP_V4L2)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
    camera.set(cv2.CAP_PROP_FPS, 30)
    print("Webカメラを起動しました。")

    # 動体検出の準備
    motion_detector = MotionDetector(pause_time=3)

    while True:
        # カメラから画像を読み取り
        _, image = camera.read()

        # 動体検出を実行
        is_moving = motion_detector.detect_motion(image)

        # 動体検出していた場合はAWSで分析
        if is_moving == True:
            # タイムスタンプを作成
            timestamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9), "JST"))

            # ファイル名を作成
            base_name = timestamp.strftime("%Y%m%d_%H%M%S")

            # OpenCVの画像データをJPEG画像のデータに変換
            encoded_image = aws_demo.encode_image(image)

            # Amazon Rekognitionで画像からラベル情報を取得する
            detect_labels_response = aws_demo.detect_labels(encode_image=encoded_image)

            # detect_labels_responseから各要素dのName属性の値を抽出してリストに追加
            labels = [d["Name"] for d in detect_labels_response]

            # テキストメッセージの準備
            speech_text = "何か動いたよ！"
            emotion_type_translated = "無し"

            # Personが含まれる場合はさらに顔情報を取得
            if "Person" in labels:
                # Amazon Rekognitionで画像から顔や表情を取得する
                detect_faces_response = aws_demo.detect_faces(encode_image=encoded_image)

                # 結果が空でない場合は処理を継続
                if len(detect_faces_response) > 0:
                    face = detect_faces_response[0]  # 先頭のデータを取得
                    # バウンディングボックスを描画
                    x = int(face["BoundingBox"]["Left"] * image.shape[1])
                    y = int(face["BoundingBox"]["Top"] * image.shape[0])
                    w = int(face["BoundingBox"]["Width"] * image.shape[1])
                    h = int(face["BoundingBox"]["Height"] * image.shape[0])
                    image = cv2.rectangle(image, (x, y), (x + w, y + h), (255, 255, 255), 2)

                    emotion_type = face["Emotions"][0]["Type"]  # 表情を取り出す
                    emotion_type_translated = aws_demo.emotion[emotion_type]["translate"]  # 表情の日本語訳を取り出す
                    speech_text = "{}".format(aws_demo.emotion[emotion_type]["speech"])  # 表情について発話させる文章を取り出す
                else:
                    speech_text = "誰かいるね！"
            if "Cat" in labels:
                speech_text = "猫がいるよ！！"
            if "Dog" in labels:
                speech_text = "犬がいるよ！！"

            # ラベル情報を文字列化
            text_labels = "\n".join(labels)
            # ラベル情報の文字列を翻訳して配列として返す
            transrate_labels = aws_demo.transrate_text(text_labels).split("\n")[:-1]

            # 読み上げる文章の音声ファイルを音声合成で作成
            audio_path = "{}/{}.wav".format(save_dir, base_name)
            aws_demo.synthesize_speech_wave(speech_text, audio_path)

            # 画像の保存
            image_path = "{}/{}.JPG".format(save_dir, base_name)
            cv2.imwrite(image_path, img=image)

            # メタ情報の保存
            meta_path = "{}/{}.JSON".format(save_dir, base_name)
            meta = {"labels": transrate_labels, "emotion_type": emotion_type_translated}
            json.dump(meta, open(meta_path, mode="w"), ensure_ascii=False, indent=4, sort_keys=True)

            # 指定枚数を超えたら古いものから自動削除
            max_image = 1000
            for f in sorted(glob.glob("{}/*.JPG".format(save_dir)), key=os.path.getctime, reverse=True)[max_image:]:
                [os.remove(t) for t in glob.glob("{}*".format(os.path.splitext(f)[0]))]

            # 総データ量を調べる
            data_usage = subprocess.check_output(["du", "-sh", "{}".format(save_dir)]).decode("utf-8").split()[0] + "B"

            # ブラウザに送るデータを作成
            send_message = {
                "speech_text": speech_text,
                "image_path": image_path,
                "audio": audio_path,
                "date": timestamp.strftime("%Y年%m月%d日 %H時%M分%S秒"),
                "meta": meta,
                "data_usage": data_usage,
            }

            # ブラウザに送信
            socketio.emit("message", send_message)


##################################################
### このプログラムを実行したときに実行する内容 ###
##################################################
if __name__ == "__main__":
    os.makedirs(save_dir, exist_ok=True)
    socketio.start_background_task(target=background_task)
    socketio.run(app, host="0.0.0.0", port=8080)

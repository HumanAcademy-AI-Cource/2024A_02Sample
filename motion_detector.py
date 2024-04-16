#!/usr/bin/env python3

# 必要なライブラリをインポート
import cv2
import datetime
import time


class MotionDetector:
    def __init__(self, max_score=10000, pause_time=1):
        self.max_score = max_score
        self.pause_time = pause_time
        self.previous_frame = None
        self.last_detected = 0

    def detect_motion(self, image):
        current_time = time.time()

        # 前回の検出から指定した秒数が経過していない場合は検出処理をスキップ
        if current_time - self.last_detected < self.pause_time:
            self.previous_frame = None
            return False

        # グレースケール変換
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 前のフレームがないときは、現在のフレームを入れる
        if self.previous_frame is None:
            self.previous_frame = gray_image.copy().astype("float")
            return False

        # 加重平均の計算
        cv2.accumulateWeighted(gray_image, self.previous_frame, 0.6)

        # 差分画像の作成
        mask = cv2.absdiff(
            gray_image, cv2.convertScaleAbs(self.previous_frame))

        # 差分画像を2値化
        thresh = cv2.threshold(mask, 3, 255, cv2.THRESH_BINARY)[1]

        # 画像中の黒以外の要素を積算してスコアを算出
        score = cv2.countNonZero(thresh)

        # 指定したスコアを超えたら動体検出したとみなし、時刻を更新
        if score > self.max_score:
            self.last_detected = current_time
            return True
        else:
            return False


if __name__ == "__main__":
    # 動作確認をするためのコード
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    motion_detector = MotionDetector()

    while True:
        success, image = cap.read()

        is_moving = motion_detector.detect_motion(image)
        if is_moving:
            print("[{}]: 動体検出しました".format(datetime.datetime.now()))

        # 画像の表示
        cv2.imshow("USB Camera", image)
        key = cv2.waitKey(1)

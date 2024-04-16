// WebSocketで接続する準備
const ws = io.connect();

// 画像や分析結果を受信したときに呼び出す関数を決める
ws.on("message", messageReceive);

// アプリの初期データを受信したときに呼び出す関数を決める
ws.on("init", initReceive);

// ----------------------------------------------

// サウンドの無効/有効を管理する変数
let isSoundEnable = false;

// 右上のサウンドボタンが押されたときに呼び出される関数
function updateSoundMode() {
  isSoundEnable = !isSoundEnable;
  if (isSoundEnable) {
    // 音声再生の準備として無音ファイルを再生
    new Howl({ src: ["./static/silence.wav"], volume: 0 });
    document.getElementById("sound-icon").setAttribute('icon', 'md-volume-up')
  } else {
    document.getElementById("sound-icon").setAttribute('icon', 'md-volume-off')
  }
}

// ----------------------------------------------

// 画像や分析結果を受信したときに呼び出される関数
function messageReceive(data) {
  // 動体検出された画像を表示する
  document.getElementById("photo-box-portrait").src = data.image_path;
  document.getElementById("photo-box-landscape").src = data.image_path;
  // 検出した時刻を表示する
  document.getElementById("photo-info-portrait").innerHTML = data.date;
  document.getElementById("photo-info-landscape").innerHTML = data.date;
  // 吹き出しにテキストを設定
  document.getElementById("speech-bubble-text").innerText = data.speech_text;
  // 総データ量を表示
  document.getElementById("data-usage").innerText = data.data_usage;

  // サウンドが有効な場合は音声を再生
  if (isSoundEnable) {
    new Howl({ src: [data.audio], preload: true, volume: 1.0, loop: false, autoplay: true });
  }

  // 画像を追加
  addPhotoToList(data);
}

// アプリの初期データを受信したときに呼び出される関数
function initReceive(data) {
  // 総データ量を表示
  document.getElementById("data-usage").innerText = data.data_usage;

  // リストの中身を初期化して新しく追加
  document.getElementById("photos-list").innerHTML = "";
  for (const item of data.records) {
    addPhotoToList(item)
  }
}


// デバイスの向きを調べて表示を切り替える関数
ons.orientation.on("change", (event) => {
  if (event.isPortrait) {
    document.getElementById('portrait').style.display = "";
    document.getElementById('landscape').style.display = "none";
  } else {
    document.getElementById('portrait').style.display = "none";
    document.getElementById('landscape').style.display = "";
  }
});


// 画像をリストに追加する関数
function addPhotoToList(photoData) {
  const photosList = document.getElementById("photos-list");

  // OnsenUIの機能（createElement）で要素を作る
  const item = ons.createElement(`
    <ons-list-item class="records-item">
      <div class="left records-item-left">
        <a href="${photoData.image_path}" target="_blank" rel="noopener noreferrer">
          <img src="${photoData.image_path}" alt="検出された画像">
        </a>
      </div>
      <div class="center records-item-center">
        <p style="text-align: left; font-size: 2.5vw; margin-right: 10px">【表情】${photoData.meta.emotion_type}</p>
        <p style="text-align: left; font-size: 2.5vw; margin-right: 10px; white-space: nowrap">【ラベル】${photoData.meta.labels.join(", ")}</p>
        <p style="text-align: left; font-size: 2.5vw; margin-right: 10px">【日時】${photoData.date}</p>
      </div>
    </ons-list-item>
  `);

  // アイテムを先頭に追加する
  photosList.insertBefore(item, photosList.firstChild);
}

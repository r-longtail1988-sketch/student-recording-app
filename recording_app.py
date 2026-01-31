import streamlit as st
from streamlit_mic_recorder import mic_recorder
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials
import urllib.parse
import os

# --- 1. Googleドライブ連携の設定 ---
def login_with_service_account():
    # service_account.json を使って認証
    scope = ['https://www.googleapis.com/auth/drive']
    gauth = GoogleAuth()
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_name(
        'service_account.json', scope)
    return GoogleDrive(gauth)

def get_or_create_folder(drive, folder_name, parent_id):
    """指定した親フォルダ内に、同名のフォルダがあればIDを返し、なければ作成する"""
    query = f"title = '{folder_name}' and '{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    file_list = drive.ListFile({'q': query}).GetList()
    
    if file_list:
        return file_list[0]['id']
    else:
        folder = drive.CreateFile({
            'title': folder_name,
            'parents': [{'id': parent_id}],
            'mimeType': 'application/vnd.google-apps.folder'
        })
        folder.Upload()
        return folder['id']

# --- 2. 状態管理（URLパラメータの取得） ---
# パラメータ 'l' (lesson) があれば生徒モードとみなす
params = st.query_params
is_student_mode = "l" in params

# 親フォルダ（授業データのルート）のIDを指定してください
PARENT_FOLDER_ID = "1Qsnz2k7GwqdTbF7AoBW_Lu8ZnydBqfun"

# --- 3. アプリケーションのUI構成 ---

# 【先生モード：QRコード発行画面】
if not is_student_mode:
    st.set_page_config(page_title="授業録音管理システム", layout="wide")
    st.sidebar.title("🛠 授業管理・QR発行")
    
    # ① 年度を選択
    year = st.sidebar.selectbox("年度", ["2025年度", "2026年度", "2027年度"])
    
    # ② クラスの選択と作成
    # ※ 本来はドライブから動的に取得可能ですが、ここではシンプルに実装
    existing_classes = ["1年A組", "1年B組", "2年C組"] 
    class_option = st.sidebar.selectbox("クラスを選択", ["＋ 新しいクラスを作成"] + existing_classes)
    
    if class_option == "＋ 新しいクラスを作成":
        target_class = st.sidebar.text_input("新しいクラス名を入力", placeholder="例：1年A組")
    else:
        target_class = class_option

    # ③ 授業の追加（タイトル入力）
    lesson_title = st.sidebar.text_input("授業タイトル", placeholder="例：DNAの抽出実験")

    # ④ 設定の確定とQRコード表示
    if target_class and lesson_title:
        st.title("📢 授業用QRコードの発行")
        st.write(f"現在の設定: **{year} / {target_class} / {lesson_title}**")
        
        # 生徒用URLの組み立て（公開後のURLに変更してください）
        base_url = "http://192.168.150.115:8501" 
        query_str = urllib.parse.urlencode({"y": year, "c": target_class, "l": lesson_title})
        student_url = f"{base_url}?{query_str}"
        
        col1, col2 = st.columns(2)
        with col1:
            # QRコードの生成（外部APIを利用）
            qr_api = f"https://api.qrserver.com/v1/create-qr-code/?data={urllib.parse.quote(student_url)}&size=300x300"
            st.image(qr_api, caption="生徒に提示するQRコード")
        
        with col2:
            st.subheader("💡 導入説明・プレビュー")
            st.write("このボタンを押すと、生徒に表示される画面を別タブで確認できます。")
            st.link_button("生徒用画面をプレビュー", student_url)
            st.info(f"コピー用URL: {student_url}")

# 【生徒モード：録音・保存画面】
else:
    st.set_page_config(page_title="グループワーク録音")
    y, c, l = params["y"], params["c"], params["l"]
    
    st.title("🎙 グループワーク録音")
    st.success(f"対象：{y} {c} \n\n 授業：{l}")
    
    # 班の選択（1〜12班）
    group_num = st.selectbox("自分の班を選んでください", [f"{i}班" for i in range(1, 13)])
    
    # メンバー入力
    members = st.text_input("班員の名前（名字をカンマ区切りで）", placeholder="例：山田, 田中, 佐藤")

    if members:
        st.divider()
        st.write("準備ができたら下のボタンを押して録音を開始してください。")
        
        # 録音コンポーネント
        audio = mic_recorder(
            start_prompt="⏺ 録音スタート",
            stop_prompt="⏹ ストップ・保存（送信）",
            key='recorder'
        )

        if audio:
            with st.spinner('Googleドライブに送信中...'):
                try:
                    drive = login_with_service_account()
                    
                    # 階層フォルダの取得・作成
                    year_id = get_or_create_folder(drive, y, PARENT_FOLDER_ID)
                    class_id = get_or_create_folder(drive, c, year_id)
                    lesson_id = get_or_create_folder(drive, l, class_id)
                    
                    # ファイル名の生成
                    safe_members = members.replace(",", "_").replace(" ", "")
                    filename = f"{group_num}_{safe_members}.wav"
                    
                    # 一時保存してアップロード
                    with open(filename, "wb") as f:
                        f.write(audio['bytes'])
                    
                    gfile = drive.CreateFile({
                        'title': filename,
                        'parents': [{'id': lesson_id}]
                    })
                    gfile.SetContentFile(filename)
                    gfile.Upload()
                    
                    st.success(f"送信完了しました！ {group_num}の皆さん、お疲れ様でした。")
                    os.remove(filename) # 一時ファイルを削除
                    
                    if st.button("もう一度録音する（撮り直しなど）"):
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")
    else:
        st.warning("録音を始める前に、班員の名前を入力してください。")
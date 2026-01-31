import streamlit as st
from streamlit_mic_recorder import mic_recorder
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials
import qrcode
from io import BytesIO

# --- 1. Googleドライブ連携の設定（Secrets対応版） ---
def login_with_service_account():
    # Streamlit CloudのSecretsから情報を取得
    try:
        key_dict = st.secrets["gcp_service_account"]
    except KeyError:
        st.error("Secretsが設定されていません。Streamlit CloudのSettingsからSecretsを設定してください。")
        return None
    
    scope = ['https://www.googleapis.com/auth/drive']
    gauth = GoogleAuth()
    
    # ファイル名(name)ではなく、辞書データ(dict)から読み込む関数を使用
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(
        key_dict, scope)
    return GoogleDrive(gauth)

# --- 2. フォルダ作成・検索用関数 ---
def get_or_create_folder(drive, folder_name, parent_id):
    query = f"'{parent_id}' in parents and title = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    file_list = drive.ListFile({'q': query}).GetList()
    if file_list:
        return file_list[0]['id']
    else:
        folder_metadata = {
            'title': folder_name,
            'parents': [{'id': parent_id}],
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = drive.CreateFile(folder_metadata)
        folder.Upload()
        return folder['id']

# --- 3. メインアプリの構成 ---

# 設定（ここを書き換えてください）
PARENT_FOLDER_ID = "1Qsnz2k7GwqdTbF7AoBW_Lu8ZnydBqfun"
# 公開後に発行される「https://...」から始まるURLをここに入力
BASE_URL = "https://student-recording-app-56wrfl8ne7hwksqkdxwe5h.streamlit.app/" 

st.title("録音ツール")

# 先生用設定画面（サイドバー）
with st.sidebar:
    st.header("管理者設定")
    year = st.text_input("年度", value="2026年度")
    grade_class = st.text_input("クラス", placeholder="例：1年A組")
    lesson_name = st.text_input("授業名", placeholder="例：細胞の観察")
    
    if st.button("QRコードを生成"):
        # URLにパラメータを付与して、スマホで開いた時に直接入力画面が出るようにする
        params = f"?year={year}&class={grade_class}&lesson={lesson_name}"
        target_url = BASE_URL + params
        
        img = qrcode.make(target_url)
        buf = BytesIO()
        img.save(buf)
        st.image(buf.getvalue(), caption="生徒用QRコード")
        st.write(f"URL: {target_url}")

# 生徒用入力・録音画面
st.divider()

# URLパラメータから設定を取得（QRコード経由の場合）
query_params = st.query_params
year_val = query_params.get("year", year)
class_val = query_params.get("class", grade_class)
lesson_val = query_params.get("lesson", lesson_name)

st.subheader(f"{year_val} {class_val}：{lesson_val}")

col1, col2 = st.columns(2)
with col1:
    group_num = st.selectbox("班を選択", [f"{i}班" for i in range(1, 13)])
with col2:
    members = st.text_input("氏名（全員分）", placeholder="例：佐藤・田中・鈴木")

# 録音コンポーネント
st.write("---")
audio = mic_recorder(
    start_prompt="⏺ 録音を開始する",
    stop_prompt="⏹ 録音を終了して送信",
    key='recorder'
)

if audio:
    st.audio(audio['bytes'])
    
    if not members:
        st.warning("氏名を入力してから録音してください。")
    else:
        with st.spinner("Googleドライブに保存中..."):
            try:
                drive = login_with_service_account()
                if drive:
                    # フォルダ階層の作成（年度 > クラス > 授業）
                    y_id = get_or_create_folder(drive, year_val, PARENT_FOLDER_ID)
                    c_id = get_or_create_folder(drive, class_val, y_id)
                    l_id = get_or_create_folder(drive, lesson_val, c_id)
                    
                    # ファイル名の作成
                    filename = f"{group_num}_{members}.wav"
                    
                    # ファイルのアップロード
                    new_file = drive.CreateFile({
                        'title': filename,
                        'parents': [{'id': l_id}]
                    })
                    new_file.SetContentRaw(audio['bytes'])
                    new_file.Upload()
                    
                    st.success(f"✅ 保存完了！ ({filename})")
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")

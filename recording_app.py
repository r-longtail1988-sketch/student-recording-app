import streamlit as st
from streamlit_mic_recorder import mic_recorder
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
import qrcode
from io import BytesIO
import tempfile
import os
import datetime

# --- 1. Googleドライブ連携（edulaboアカウントの権限で実行） ---
def login_with_user_account():
    try:
        # ここでStreamlitのSecretsに保存した「新しい」認証情報を読み込みます
        creds = st.secrets["google_oauth"]
    except KeyError:
        st.error("Secretsに 'google_oauth' が設定されていません。")
        return None
    
    gauth = GoogleAuth()
    from oauth2client.client import OAuth2Credentials
    
    gauth.credentials = OAuth2Credentials(
        access_token=None,
        client_id=creds["client_id"],
        client_secret=creds["client_secret"],
        refresh_token=creds["refresh_token"],
        token_expiry=None,
        token_uri="https://oauth2.googleapis.com/token",
        user_agent="StreamlitApp",
    )
    return GoogleDrive(gauth)

# --- 2. フォルダ作成・検索用関数 ---
def get_or_create_folder(drive, folder_name, parent_id):
    target_name = str(folder_name).strip()
    query = f"'{parent_id}' in parents and title = '{target_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    file_list = drive.ListFile({'q': query}).GetList()
    
    if file_list:
        return file_list[0]['id']
    else:
        folder_metadata = {
            'title': target_name,
            'parents': [{'id': parent_id}],
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = drive.CreateFile(folder_metadata)
        folder.Upload()
        return folder['id']

# --- 3. URLパラメータ取得の安全化 ---
def get_safe_param(params, key, default):
    val = params.get(key, default)
    if isinstance(val, list):
        return val[0]
    return val

# --- 4. メインアプリの構成 ---

# 【★重要：書き換え箇所1】
# 新しい「edulabo」アカウントのドライブ内に作成したフォルダのIDに貼り替えてください
PARENT_FOLDER_ID = "1dbKFTVZNeIQl-BOELTfz9PrbD8D7mJis"

# 【★重要：書き換え箇所2】
# アプリのURLが以前と変わっている場合は、ここを最新のURLに更新してください
BASE_URL = "https://student-recording-app-56wrfl8ne7hwksqkdxwe5h.streamlit.app/" 

st.title("edulabo 録音ツール") # タイトルもお好みのものへ
query_params = st.query_params

# 管理者設定（サイドバー）
with st.sidebar:
    st.header("管理者設定")
    
    current_year = datetime.date.today().year
    year_options = [f"{y}年度" for y in range(current_year - 1, current_year + 10)]
    year_input = st.selectbox("年度", options=year_options, index=1)
    
    class_input = st.text_input("クラス", placeholder="例：1年A組")
    lesson_input = st.text_input("授業名", placeholder="例：細胞の観察")
    
    target_url = f"{BASE_URL}?year={year_input}&class={class_input}&lesson={lesson_input}"
    
    if st.button("QRコードを生成"):
        img = qrcode.make(target_url)
        buf = BytesIO()
        img.save(buf)
        st.image(buf.getvalue(), caption="生徒用QRコード")
        st.markdown(f"生徒用URL: [{target_url}]({target_url})")
    
    st.divider()
    st.link_button("生徒用画面をプレビュー", target_url)

# --- 5. 生徒用録音画面 ---
st.divider()

y_val = get_safe_param(query_params, "year", year_input)
c_val = get_safe_param(query_params, "class", class_input)
l_val = get_safe_param(query_params, "lesson", lesson_input)

st.subheader(f"{y_val} {c_val}：{l_val}")

col1, col2 = st.columns(2)
with col1:
    group_num = st.selectbox("班を選択", [f"{i}班" for i in range(1, 13)])
with col2:
    members = st.text_input("氏名（全員分）", placeholder="例：佐藤・田中・鈴木")

st.write("---")
audio = mic_recorder(
    start_prompt="⏺ 録音を開始する",
    stop_prompt="⏹ 録音を終了して送信",
    key='recorder'
)

if audio:
    if not members:
        st.warning("氏名を入力してから録音してください。")
    else:
        with st.spinner("Googleドライブに保存中..."):
            try:
                drive = login_with_user_account()
                if drive:
                    y_id = get_or_create_folder(drive, y_val, PARENT_FOLDER_ID)
                    c_id = get_or_create_folder(drive, c_val, y_id)
                    l_id = get_or_create_folder(drive, l_val, c_id)
                    
                    filename = f"{group_num}_{members}.wav"
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                        tmp.write(audio['bytes'])
                        tmp_path = tmp.name
                    
                    new_file = drive.CreateFile({
                        'title': filename,
                        'parents': [{'id': l_id}]
                    })
                    new_file.SetContentFile(tmp_path)
                    new_file.Upload()
                    
                    os.remove(tmp_path)
                    st.success(f"✅ 保存完了！ ({filename})")
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")

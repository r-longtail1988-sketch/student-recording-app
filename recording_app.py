import streamlit as st
from streamlit_mic_recorder import mic_recorder
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials
import qrcode
from io import BytesIO

# --- 1. Googleドライブ連携の設定（Secrets対応版） ---
def login_with_service_account():
    try:
        # Streamlit CloudのSecretsから情報を取得
        key_dict = st.secrets["gcp_service_account"]
    except KeyError:
        st.error("Secretsが設定されていません。Streamlit CloudのSettingsからSecretsを設定してください。")
        return None
    
    scope = ['https://www.googleapis.com/auth/drive']
    gauth = GoogleAuth()
    
    # 辞書データ(dict)から読み込む方式
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

# 先生が既に入力されていた大切な設定値（ここを維持しています）
PARENT_FOLDER_ID = "1Qsnz2k7GwqdTbF7AoBW_Lu8ZnydBqfun"
BASE_URL = "https://student-recording-app-56wrfl8ne7hwksqkdxwe5h.streamlit.app/" 

st.title("録音ツール")

# URLパラメータを取得
query_params = st.query_params

# 先生用設定画面（サイドバー）
with st.sidebar:
    st.header("管理者設定")
    year = st.text_input("年度", value="2026年度")
    grade_class = st.text_input("クラス", placeholder="例：1年A組")
    lesson_name = st.text_input("授業名", placeholder="例：細胞の観察")
    
    # 生徒用URLの生成
    params = f"?year={year}&class={grade_class}&lesson={lesson_name}"
    target_url = BASE_URL + params
    
    if st.button("QRコードを生成"):
        img = qrcode.make(target_url)
        buf = BytesIO()
        img.save(buf)
        st.image(buf.getvalue(), caption="生徒用QRコード")
        st.write(f"URL: {target_url}")
    
    st.divider()
    # 【追加】生徒用画面を別タブでプレビューするボタン
    st.link_button("生徒用画面をプレビュー", target_url)

# --- 4. 画面の出し分けロジック ---

# URLにパラメータがある場合（QR経由またはプレビュー時）
if "year" in query_params:
    y_val = query_params.get("year")
    c_val = query_params.get("class")
    l_val = query_params.get("lesson")

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
                    drive = login_with_service_account()
                    if drive:
                        # フォルダ階層の作成
                        y_id = get_or_create_folder(drive, y_val, PARENT_FOLDER_ID)
                        c_id = get_or_create_folder(drive, c_val, y_id)
                        l_id = get_or_create_folder(drive, l_val, c_id)
                        
                        filename = f"{group_num}_{members}.wav"
                        new_file = drive.CreateFile({
                            'title': filename,
                            'parents': [{'id': l_id}]
                        })
                        new_file.SetContentRaw(audio['bytes'])
                        new_file.Upload()
                        st.success(f"✅ 保存完了！ ({filename})")
                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")
else:
    # パラメータがない場合（管理画面として開いた時）
    st.info("左側のサイドバーで「年度・クラス・授業名」を設定し、「QRコードを生成」または「プレビュー」を押してください。")

import streamlit as st
import google.generativeai as genai
import pandas as pd
import time
import re

# 1. Настройка страницы
st.set_page_config(page_title="Bulk Lead Gen AI", layout="wide")
st.title("Bulk B2B Lead Gen & CustDev Assistant")

# ИНСТРУКЦИЯ
st.markdown("""
### 📌 Инструкция:
* **[PRODUCT_DETAILS]:** {Здесь описываешь текущий функционал, например: MCP data gateway, secure chatbot connectors for corporate data, etc.}
* **[TARGET_AUDIENCE]:** {Кого ищем: CTO, CISO, Founders. ЕСЛИ ПУСТО ИЛИ НЕ ЗНАЕШЬ — напиши "Suggest ICP"}
---
""")

# 2. API Конфигурация
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("API ключ не найден. Проверь Secrets.")
    st.stop()

# --- ВРЕМЕННЫЙ БЛОК ДЛЯ ПРОВЕРКИ МОДЕЛЕЙ ---
st.write("### 🤖 Доступные модели для твоего ключа:")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            st.code(m.name)
except Exception as e:
    st.error(f"Ошибка при запросе моделей: {e}")
st.stop() # Останавливаем код здесь, чтобы не грузить остальной интерфейс
# --------------------------------------------

# 3. Поля ввода
col1, col2 = st.columns(2)
with col1:
    product_details = st.text_area("Product Details", "MCP data gateway, secure chatbot connectors for corporate data...")
with col2:
    target_audience = st.text_input("Target Audience", "Suggest ICP")

uploaded_file = st.file_uploader("Загрузи CSV из Apify", type=["csv"])

if uploaded_file is not None:
    df_full = pd.read_csv(uploaded_file)
    
    st.write("### 👀 Превью загруженных данных:")
    st.dataframe(df_full.head(3)) 
    
    available_cols = df_full.columns.tolist()
    text_col_default = next((c for c in ['text', 'content', 'activityDescription'] if c in available_cols), available_cols[0])
    text_column = st.selectbox("Выбери колонку с текстом поста:", available_cols, index=available_cols.index(text_col_default))
    
    url_col = next((c for c in ['url', 'postUrl'] if c in available_cols), None)
    author_url_col = next((c for c in ['authorProfileUrl', 'authorUrl'] if c in available_cols), None)

    # --- НОВЫЙ БЛОК: НАРЕЗКА ФАЙЛА ---
    st.markdown("---")
    st.write(f"📊 **Всего строк в файле:** {len(df_full)}")
    st.warning("⚡ *Streamlit может сбрасывать соединение при работе дольше 20 минут. Обрабатывай по 50-100 строк за раз!*")
    
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        start_row = st.number_input("Начать со строки №", min_value=0, max_value=len(df_full)-1, value=0)
    with col_s2:
        end_row = st.number_input("Закончить на строке №", min_value=1, max_value=len(df_full), value=min(100, len(df_full)))

    # Отрезаем нужный кусок для обработки
    df = df_full.iloc[start_row:end_row].copy()
    st.info(f"Будет обработано строк: **{len(df)}** (с {start_row} по {end_row-1})")
    # ---------------------------------

    if st.button("🚀 Начать анализ выбранных строк"):
        model = genai.GenerativeModel("gemini-1.5-flash")
            
        results = []
        scores = []
        
        progress_bar = st.progress(0)
        total = len(df)
        quota_error = False
        
        # Используем enumerate для правильного заполнения прогресс-бара по срезу
        for i, (index, row) in enumerate(df.iterrows()):
            if quota_error:
                results.append("Пропущено из-за лимитов")
                scores.append(0)
                continue

            lead_text = str(row[text_column])
            
            if pd.isna(row[text_column]) or lead_text.strip() in ["", "nan"]:
                results.append("Нет данных")
                scores.append(0)
                continue
                
            PROMPT = f"""
            Act as an expert B2B Founder & Lead Gen Strategist doing Customer Discovery. My name is Slava. 

            [PRODUCT_DETAILS]: {product_details}
            [TARGET_AUDIENCE]: {target_audience}

            Here is the text/post from the target lead:
            "{lead_text}"

            Step 1: Lead Analysis (in Russian)
            - Relevance Score: [Оцени от 1 до 10. Формат СТРОГО: "Relevance Score: X/10"]
            - The Technical Hook: What specific phrase or problem from their text we can use.

            Step 2: Outreach Drafts (in English)
            STRICT ANTI-AI STYLE RULES: Zero exclamation marks. Use periods. No corporate fluff. 
            Sentences must be short, slightly informal. Goal: Customer Discovery.

            Generate:
            1. Invite Note (<200 chars).
            2. Direct Message (Subject lowercase. 3-4 short sentences max).
            3. 2 options for a LinkedIn Comment (All lowercase. NO fake enthusiasm).
            """
            
            try:
                time.sleep(6.0) # Держим безопасные 10 RPM
                response = model.generate_content(PROMPT)
                output = response.text
                
                score_match = re.search(r'Relevance Score:\s*(\d+)', output, re.IGNORECASE)
                score_val = int(score_match.group(1)) if score_match else 0
                
                results.append(output)
                scores.append(score_val)
            except Exception as e:
                if "429" in str(e):
                    st.warning("🛑 Лимиты исчерпаны. Сохраняем то, что успели.")
                    results.append("Ошибка лимита (429).")
                    scores.append(0)
                    quota_error = True
                else:
                    results.append(f"Ошибка API: {e}")
                    scores.append(0)
                
            progress_bar.progress((i + 1) / total)
            
        df['Score'] = scores
        df['AI_Analysis_and_Drafts'] = results
        df = df.sort_values(by='Score', ascending=False)
        
        st.success(f"✅ Анализ партии ({start_row}-{end_row}) завершен!")
        
        st.subheader("🔥 Топ отобранных лидов")
        
        for index, row in df.iterrows():
            if row['Score'] > 0:
                p_url = row.get(url_col, "#") if url_col and pd.notna(row[url_col]) else "#"
                a_url = row.get(author_url_col, "#") if author_url_col and pd.notna(row[author_url_col]) else "#"

                with st.expander(f"Лид (строка #{index}) | Score: {row['Score']}/10"):
                    st.markdown(f"🔗 [Открыть пост]({p_url}) | 👤 [Профиль автора]({a_url})")
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        st.info("**Исходный текст:**")
                        st.write(row[text_column])
                    with c2:
                        st.success("**Анализ и Сообщения:**")
                        st.write(row['AI_Analysis_and_Drafts'])

        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(f"💾 Скачать результат ({start_row}-{end_row})", csv, f"leads_{start_row}_{end_row}.csv", "text/csv")

import streamlit as st
import google.generativeai as genai
import pandas as pd
import time
import re

# 1. Настройка страницы
st.set_page_config(page_title="Bulk Lead Gen AI", layout="wide")
st.title("Bulk B2B Lead Gen & CustDev Assistant")

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
    st.error("API ключ не найден в Secrets.")
    st.stop()

# --- Инициализация памяти для авто-продолжения ---
if 'is_processing' not in st.session_state:
    st.session_state.is_processing = False
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
if 'scores' not in st.session_state:
    st.session_state.scores = []
if 'results' not in st.session_state:
    st.session_state.results = []
if 'quota_error' not in st.session_state:
    st.session_state.quota_error = False
# ------------------------------------------------

col1, col2 = st.columns(2)
with col1:
    product_details = st.text_area("Product Details", "MCP data gateway, secure chatbot connectors for corporate data...")
with col2:
    target_audience = st.text_area("Target Audience", "Suggest ICP")

uploaded_file = st.file_uploader("Загрузи CSV из Apify", type=["csv"])

if uploaded_file is not None:
    df_full = pd.read_csv(uploaded_file)
    total_rows = len(df_full)
    
    if not st.session_state.is_processing and st.session_state.current_index == 0:
        st.write("### 👀 Превью загруженных данных:")
        st.dataframe(df_full.head(3)) 
    
    available_cols = df_full.columns.tolist()
    text_col_default = next((c for c in ['text', 'content', 'activityDescription'] if c in available_cols), available_cols[0])
    text_column = st.selectbox("Выбери колонку с текстом поста:", available_cols, index=available_cols.index(text_col_default))
    
    url_col = next((c for c in ['url', 'postUrl'] if c in available_cols), None)
    author_url_col = next((c for c in ['authorProfileUrl', 'authorUrl'] if c in available_cols), None)

    st.markdown("---")
    
    # Кнопка запуска
    if not st.session_state.is_processing and st.session_state.current_index < total_rows:
        if st.button(f"🚀 Запустить анализ всех {total_rows} лидов (Авто-режим)"):
            st.session_state.is_processing = True
            st.session_state.current_index = 0
            st.session_state.scores = []
            st.session_state.results = []
            st.session_state.quota_error = False
            st.rerun()

    # --- ЛОГИКА АВТО-ОБРАБОТКИ ---
    if st.session_state.is_processing:
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        # Берем пачку 20 строк
        batch_size = 20
        start = st.session_state.current_index
        end = min(start + batch_size, total_rows)
        
        st.info(f"🔄 Идет обработка: строки с {start} по {end} из {total_rows}... Пожалуйста, не закрывай вкладку.")
        progress_bar = st.progress(start / total_rows)
        
        for i in range(start, end):
            if st.session_state.quota_error:
                break
                
            row = df_full.iloc[i]
            lead_text = str(row[text_column])
            
            if pd.isna(row[text_column]) or lead_text.strip() in ["", "nan"]:
                st.session_state.results.append("Нет данных")
                st.session_state.scores.append(0)
                continue
                
            PROMPT = f"""
            Act as an expert B2B Founder & Lead Gen Strategist doing Customer Discovery. My name is Slava. 

            [PRODUCT_DETAILS]: {product_details}
            [TARGET_AUDIENCE]: {target_audience}

            Here is the text/post from the target lead:
            "{lead_text}"

            Step 1: Lead Analysis (in Russian)
            - Relevance Score: [Оцени от 1 до 10. Формат СТРОГО: "Relevance Score: X/10"]
            - Обоснование оценки: [Детально распиши на 3-4 предложения, почему этот пост совпадает или не совпадает с ценностью продукта. Выдели совпадения по болям (Shadow AI, governance, security) и роли лида. Если оценка снижена — объясни почему].
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
                time.sleep(4.0) # Пауза 4 секунды (15 RPM)
                response = model.generate_content(PROMPT)
                output = response.text
                
                score_match = re.search(r'Relevance Score:\s*(\d+)', output, re.IGNORECASE)
                st.session_state.scores.append(int(score_match.group(1)) if score_match else 0)
                st.session_state.results.append(output)
            except Exception as e:
                if "429" in str(e):
                    st.session_state.quota_error = True
                    st.session_state.results.append("Ошибка лимита (429).")
                    st.session_state.scores.append(0)
                else:
                    st.session_state.results.append(f"Ошибка API: {e}")
                    st.session_state.scores.append(0)
            
            progress_bar.progress((i + 1) / total_rows)
        
        # Обновляем индекс после пачки
        st.session_state.current_index = end
        
        if st.session_state.quota_error or st.session_state.current_index >= total_rows:
            st.session_state.is_processing = False
            st.rerun() # Финальная перезагрузка для вывода результатов
        else:
            time.sleep(2)
            st.rerun() # Перезагрузка для следующей пачки

    # --- ВЫВОД РЕЗУЛЬТАТОВ ---
    if not st.session_state.is_processing and len(st.session_state.results) > 0:
        
        if st.session_state.quota_error:
            st.warning("🛑 Анализ остановлен из-за лимитов Google, но обработанные данные сохранены!")
        else:
            st.success("✅ Весь файл успешно обработан!")
            
        # --- ЖЕСТКАЯ ЗАЩИТА ОТ ОШИБОК ДЛИНЫ МАССИВОВ ---
        min_len = min(len(st.session_state.results), len(st.session_state.scores), len(df_full))
        
        df_result = df_full.iloc[:min_len].copy()
        df_result['Score'] = st.session_state.scores[:min_len]
        df_result['AI_Analysis_and_Drafts'] = st.session_state.results[:min_len]
        
        df_result = df_result.sort_values(by='Score', ascending=False)
        # -----------------------------------------------
        
        st.subheader("🔥 Топ отобранных лидов")
        for index, row in df_result.iterrows():
            if row['Score'] > 0:
                p_url = row.get(url_col, "#") if url_col and pd.notna(row[url_col]) else "#"
                a_url = row.get(author_url_col, "#") if author_url_col and pd.notna(row[author_url_col]) else "#"

                with st.expander(f"Лид (строка #{index}) | Score: {row['Score']}/10"):
                    st.markdown(f"🔗 [Открыть пост]({p_url}) | 👤 [Профиль автора]({a_url})")
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        st.write(row[text_column])
                    with c2:
                        st.write(row['AI_Analysis_and_Drafts'])

        csv = df_result.to_csv(index=False).encode('utf-8')
        st.download_button("💾 Скачать готовый CSV", csv, "leads_fully_scored.csv", "text/csv")
        
        if st.button("🔄 Сбросить и начать заново"):
            st.session_state.current_index = 0
            st.session_state.results = []
            st.session_state.scores = []
            st.rerun()

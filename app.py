import streamlit as st
import google.generativeai as genai
import pandas as pd
import time
import re

# 1. Настройка страницы
st.set_page_config(page_title="Provenyx Lead Gen", layout="wide")
st.title("Bulk B2B Lead Gen & CustDev Assistant")

st.markdown("""
### 📌 Инструкция:
* Используем модель **Gemini 1.5 Flash** для обхода лимитов.
* Пауза между запросами — 4 секунды (безопасный режим).
---
""")

# 2. API Конфигурация
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("API ключ не найден в Secrets. Проверь настройки в Streamlit Cloud.")
    st.stop()

# 3. Поля ввода
col1, col2 = st.columns(2)
with col1:
    product_details = st.text_area("Product Details", "Provenyx: multi-LLM governance поверх BYOS (Drive/S3/Dropbox), гранулярные разрешения на уровне файлов.")
with col2:
    target_audience = st.text_input("Target Audience", "COO, Head of Marketing, CCO, CISO")

uploaded_file = st.file_uploader("Загрузи CSV из Apify", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    
    st.write("### 👀 Превью загруженных данных:")
    st.dataframe(df.head(5)) 
    
    available_cols = df.columns.tolist()
    
    # Авто-подбор колонки с текстом
    text_col_default = next((c for c in ['text', 'content', 'activityDescription'] if c in available_cols), available_cols[0])
    text_column = st.selectbox("Выбери колонку с текстом поста:", available_cols, index=available_cols.index(text_col_default))
    
    # Колонки ссылок
    url_col = next((c for c in ['url', 'postUrl'] if c in available_cols), None)
    author_url_col = next((c for c in ['authorProfileUrl', 'authorUrl'] if c in available_cols), None)

    if st.button("🚀 Начать анализ и скоринг"):
        # Принудительно Flash для стабильности при массовой обработке
        model = genai.GenerativeModel("gemini-1.5-flash")
            
        results = []
        scores = []
        
        progress_bar = st.progress(0)
        total = len(df)
        
        # Флаг для остановки при ошибке лимитов
        quota_error = False
        
        for index, row in df.iterrows():
            if quota_error:
                results.append("Пропущено: превышен лимит API")
                scores.append(0)
                continue

            lead_text = str(row[text_column])
            
            if pd.isna(row[text_column]) or lead_text.strip() in ["", "nan"]:
                results.append("Нет данных")
                scores.append(0)
                continue
                
            PROMPT = f"""
            Act as an expert B2B Lead Gen Strategist. My name is Slava.
            [PRODUCT_DETAILS]: {product_details}
            [TARGET_AUDIENCE]: {target_audience}
            Lead Post: "{lead_text}"

            Step 1: Analysis (Russian)
            - Relevance Score: [Scale 1-10. Format STRICTLY: "Relevance Score: X/10"]
            - Hook: Why this lead?

            Step 2: Outreach (English)
            - 1 Invite Note (<200 chars).
            - 1 DM (Subject lowercase).
            - 2 LinkedIn Comments (lowercase).
            """
            
            try:
                # Пауза 4 сек позволяет делать ~15 запросов в минуту (безопасно для Flash)
                time.sleep(4.0) 
                response = model.generate_content(PROMPT)
                output = response.text
                
                # Извлекаем Score
                score_match = re.search(r'Relevance Score:\s*(\d+)', output, re.IGNORECASE)
                score_val = int(score_match.group(1)) if score_match else 0
                
                results.append(output)
                scores.append(score_val)
            except Exception as e:
                if "429" in str(e):
                    st.warning(f"🛑 Лимиты исчерпаны на лиде #{index+1}. Останавливаем запросы.")
                    results.append(f"Ошибка лимита (429). Попробуйте позже.")
                    scores.append(0)
                    quota_error = True
                else:
                    results.append(f"Ошибка API: {e}")
                    scores.append(0)
                
            progress_bar.progress((index + 1) / total)
            
        df['Score'] = scores
        df['AI_Analysis_and_Drafts'] = results
        
        # Сортировка по Score
        df = df.sort_values(by='Score', ascending=False)
        
        st.success("✅ Анализ завершен!")
        
        st.subheader("🔥 Топ отобранных лидов")
        
        for index, row in df.iterrows():
            if row['Score'] > 0: # Показываем только тех, кто прошел анализ
                p_url = row.get(url_col, "#") if url_col and pd.notna(row[url_col]) else "#"
                a_url = row.get(author_url_col, "#") if author_url_col and pd.notna(row[author_url_col]) else "#"

                with st.expander(f"Лид #{index+1} | Score: {row['Score']}/10"):
                    st.markdown(f"🔗 [Открыть пост]({p_url}) | 👤 [Профиль автора]({a_url})")
                    
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        st.info("**Текст поста:**")
                        st.write(row[text_column])
                    with c2:
                        st.success("**Анализ и Сообщения:**")
                        st.write(row['AI_Analysis_and_Drafts'])

        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("💾 Скачать CSV с оценками", csv, "provenyx_scored_leads.csv", "text/csv")

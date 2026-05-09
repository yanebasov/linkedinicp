import streamlit as st
import google.generativeai as genai
import pandas as pd
import time
import re

# Настройка страницы
st.set_page_config(page_title="Bulk Lead Gen AI", layout="wide")
st.title("Bulk B2B Lead Gen & CustDev Assistant")

# Блок с правилами
st.markdown("""
### 📌 Правила заполнения:
* **[PRODUCT_DETAILS]:** Описание функционала (например: *Provenyx — корпоративный слой знаний для Claude/ChatGPT*).
* **[TARGET_AUDIENCE]:** Кого ищем (например: *COO, CISO, Head of Marketing*).
---
""")

# Настройка API ключа
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("API ключ не найден. Добавьте его в Secrets.")
    st.stop()

# Интерфейс
col1, col2 = st.columns(2)
with col1:
    product_details = st.text_area("Product Details", "Provenyx: multi-LLM governance поверх BYOS (Drive/S3/Dropbox)...")
with col2:
    target_audience = st.text_input("Target Audience", "COO, Head of Marketing, CCO, CISO")

uploaded_file = st.file_uploader("Загрузи CSV из Apify", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.write("Превью данных:")
    st.dataframe(df.head(3))
    
    available_cols = df.columns.tolist()
    text_column = st.selectbox("Выбери колонку с текстом поста:", available_cols, 
                               index=available_cols.index('text') if 'text' in available_cols else 0)
    
    # Колонки для ссылок (если они есть в файле)
    url_col = 'url' if 'url' in available_cols else None
    author_url_col = 'authorProfileUrl' if 'authorProfileUrl' in available_cols else None

    if st.button("🚀 Сгенерировать сообщения для всех лидов"):
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        
        results = []
        scores = [] # Список для новой колонки с оценками
        
        progress_text = "Анализируем лидов..."
        my_bar = st.progress(0, text=progress_text)
        total_rows = len(df)
        
        for index, row in df.iterrows():
            lead_text = str(row[text_column])
            
            if pd.isna(row[text_column]) or lead_text.strip() == "" or lead_text == "nan":
                results.append("Нет данных для анализа")
                scores.append(0)
                continue
                
            PROMPT = f"""
            Act as an expert B2B Founder & Lead Gen Strategist. My name is Slava. 
            [PRODUCT_DETAILS]: {product_details}
            [TARGET_AUDIENCE]: {target_audience}
            Lead Text: "{lead_text}"

            Step 1: Lead Analysis (Russian)
            - Relevance Score: [Scale 1-10. Format STRICTLY: "Relevance Score: X/10"]
            - The Technical Hook: One specific phrase to use.

            Step 2: Outreach Drafts (English)
            - No exclamation marks. Short sentences. Founder-to-founder style.
            - 1 Invite Note (<200 chars).
            - 1 DM (Subject lowercase).
            - 2 LinkedIn Comments (lowercase).
            """
            
            try:
                time.sleep(2) # Защита от лимитов
                response = model.generate_content(PROMPT)
                full_text = response.text
                
                # Извлекаем только цифру оценки для колонки
                score_match = re.search(r'Relevance Score:\s*(\d+)', full_text, re.IGNORECASE)
                score_val = int(score_match.group(1)) if score_match else 0
                
                results.append(full_text)
                scores.append(score_val)
                
            except Exception as e:
                results.append(f"Ошибка API: {e}")
                scores.append(0)
                
            my_bar.progress((index + 1) / total_rows, text=f"Обработано {index + 1} из {total_rows}")
            
        # Добавляем новые данные в DataFrame
        df['Score'] = scores
        df['AI_Analysis_and_Drafts'] = results
        
        st.success("✅ Анализ завершен!")
        
        # Сортируем лидов: сначала самые релевантные (10/10)
        df = df.sort_values(by='Score', ascending=False)
        
        st.subheader("🔥 Топ отобранных лидов")
        
        for index, row in df.iterrows():
            # Отрисовка ссылок
            p_link = f"[🔗 Пост]({row[url_col]})" if url_col and pd.notna(row[url_col]) else "Нет ссылки на пост"
            a_link = f"[👤 Автор]({row[author_url_col]})" if author_url_col and pd.notna(row[author_url_col]) else "Нет ссылки на автора"

            with st.expander(f"Score: {row['Score']}/10 | {a_link} | {p_link}", expanded=False):
                col_left, col_right = st.columns([1, 1.5])
                with col_left:
                    st.info("**Исходный текст:**")
                    st.write(row[text_column])
                with col_right:
                    st.success("**Анализ и Сообщения:**")
                    st.write(row['AI_Analysis_and_Drafts'])
        
        # Экспорт
        st.markdown("---")
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="💾 Скачать итоговый отчет с оценками (CSV)",
            data=csv,
            file_name='provenyx_leads_scored.csv',
            mime='text/csv',
        )
